"""Explicit connection-injected helpers for future admitted dedicated PostgreSQL.

No connection creation, environment DSN lookup, or lifecycle settlement lives here.
Each public mutator owns one transaction and requires an idle controller connection.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
from pathlib import Path

from psycopg import sql
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from contracts.validate import ROOT, load_file, schema_name, seed_hash, validate
from eval.fixtures.validate import validate_corpus

MIGRATIONS = Path(__file__).resolve().parent / 'migrations'
TABLES = {
    'customers': ('customer_id', 'name', 'active'),
    'items': ('item_id', 'name', 'unit', 'currency', 'unit_price_cents', 'active'),
    'projects': ('project_id', 'customer_id', 'name', 'active'),
    'timesheets': ('timesheet_id', 'project_id', 'item_id', 'work_date', 'minutes', 'billable'),
    'invoices': ('invoice_id', 'customer_id', 'invoice_date', 'due_date', 'currency', 'status',
                 'subtotal_cents', 'tax_cents', 'total_cents', 'created_at'),
    'invoice_lines': ('line_id', 'invoice_id', 'item_id', 'quantity', 'unit_price_cents',
                      'line_total_cents', 'line_number'),
    'idempotency_records': ('idempotency_key', 'request_hash', 'invoice_id'),
}
MAPPING_COLUMNS = ('schema_version', 'run_id', 'attempt_id', 'tenant_id', 'principal_id',
                   'allowed_tools', 'schema_name', 'phase', 'generation', 'not_after',
                   'agent_token_sha256', 'verifier_token_sha256', 'verifier_scope',
                   'lock_marker', 'workflow_kind')


class DatabaseStateError(ValueError):
    """Scoped state is incompatible or unsafe for an initialization operation."""


def fixture() -> dict:
    """Load and verify the frozen synthetic corpus, never a caller-provided seed."""
    validate_corpus()
    value = load_file(ROOT.parent / 'eval/fixtures/v1/fixture.json')
    validate('Fixture', value)
    if value['migration_version'] != '1' or value['seed_hash'] != seed_hash(value):
        raise DatabaseStateError('unsupported fixture or fingerprint')
    return value


def migration_digest() -> str:
    return hashlib.sha256((MIGRATIONS / '001_application.up.sql').read_bytes()).hexdigest()


def migration_sql(direction: str, registered_schema: str):
    if direction not in {'up', 'down'}:
        raise ValueError('invalid migration direction')
    # This low-level renderer accepts only a schema-shaped identifier. Public
    # operations additionally compare it to the trusted, locked registry mapping.
    import re
    if not re.fullmatch(r'r_[0-9a-f]{32}', registered_schema):
        raise ValueError('invalid registered schema')
    source = (MIGRATIONS / f'001_application.{direction}.sql').read_text()
    pieces = source.split('__SCHEMA__')
    rendered = [sql.SQL(pieces[0])]
    for piece in pieces[1:]:
        rendered.extend((sql.Identifier(registered_schema), sql.SQL(piece)))
    return sql.Composed(rendered)


@contextmanager
def _transaction(conn):
    if conn.info.transaction_status != TransactionStatus.IDLE:
        raise DatabaseStateError('idle connection required; nested commit forbidden')
    with conn.transaction():
        # Per-transaction limits, never native PostgreSQL/Ollama configuration.
        conn.execute("SET LOCAL statement_timeout = '4s'")
        conn.execute("SET LOCAL lock_timeout = '1s'")
        conn.execute("SET LOCAL TIME ZONE 'UTC'")
        conn.execute('SET TRANSACTION ISOLATION LEVEL READ COMMITTED')
        if conn.execute('SELECT current_database(), current_user').fetchone() != (
                'mcpbench', 'mcpbench_controller'):
            raise DatabaseStateError('dedicated database/controller connection required')
        yield


def _mapping(conn, run_id: str) -> dict:
    validate('Identifier', run_id)
    row = conn.execute(sql.SQL('SELECT {} FROM bench_control.run_registry WHERE run_id = %s FOR UPDATE').format(
        sql.SQL(',').join(map(sql.Identifier, MAPPING_COLUMNS))), (run_id,)).fetchone()
    if row is None:
        raise DatabaseStateError('unknown registered run')
    value = dict(zip(MAPPING_COLUMNS, row))
    value['not_after'] = _wire(value['not_after'])
    validate('RunMapping', value)
    if value['schema_name'] != schema_name(run_id):
        raise DatabaseStateError('invalid trusted run binding')
    return value


def _initial(mapping):
    # This module initializes or rolls back only before launch. Sealed cleanup is
    # a separate lifecycle operation requiring real fence/artifact evidence.
    if mapping['phase'] != 'prepared' or mapping['generation'] != 0:
        raise DatabaseStateError('operation requires unused prepared run')


def _metadata(conn, mapping, seed):
    row = conn.execute('SELECT version,migration_sha256,fixture_version,tenant_id,seed_hash '
                       'FROM bench_control.schema_migrations WHERE run_id = %s',
                       (mapping['run_id'],)).fetchone()
    expected = (1, migration_digest(), seed['fixture_version'], seed['tenant_id'], seed['seed_hash'])
    if row is not None and row != expected:
        raise DatabaseStateError('incompatible version, migration checksum or seed identity')
    if mapping['tenant_id'] != seed['tenant_id']:
        raise DatabaseStateError('fixture tenant mismatch')
    return row


def _check_shape(conn, name):
    rows = conn.execute(
        'SELECT table_name,column_name FROM information_schema.columns '
        'WHERE table_schema = %s ORDER BY table_name,ordinal_position', (name,)).fetchall()
    observed = {}
    for table, column in rows:
        observed.setdefault(table, []).append(column)
    if {table: tuple(columns) for table, columns in observed.items()} != TABLES:
        raise DatabaseStateError('incompatible existing table/column inventory')


def _migrate(conn, mapping, seed):
    if _metadata(conn, mapping, seed) is not None:
        _check_shape(conn, mapping['schema_name'])
        return
    name = mapping['schema_name']
    exists = conn.execute('SELECT 1 FROM pg_namespace WHERE nspname = %s', (name,)).fetchone()
    if exists is not None:
        raise DatabaseStateError('unversioned existing schema; refusing adoption')
    conn.execute(sql.SQL('CREATE SCHEMA {} AUTHORIZATION mcpbench_controller').format(sql.Identifier(name)))
    conn.execute(sql.SQL('REVOKE ALL ON SCHEMA {} FROM PUBLIC').format(sql.Identifier(name)))
    conn.execute(migration_sql('up', name))
    conn.execute('INSERT INTO bench_control.schema_migrations '
                 '(run_id,version,migration_sha256,fixture_version,tenant_id,seed_hash) '
                 'VALUES (%s,1,%s,%s,%s,%s)',
                 (mapping['run_id'], migration_digest(), seed['fixture_version'], seed['tenant_id'], seed['seed_hash']))


def _wire(value):
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')
    if isinstance(value, date):
        return value.isoformat()
    return value


def _tables(conn, name):
    result = {}
    for table, columns in TABLES.items():
        rows = conn.execute(sql.SQL('SELECT {} FROM {}.{} ORDER BY {}').format(
            sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(name),
            sql.Identifier(table), sql.Identifier(columns[0]))).fetchall()
        result[table] = [dict(zip(columns, map(_wire, row))) for row in rows]
    return result


def _fingerprint(seed, tables):
    return seed_hash({**seed, 'seed': tables})


def _seed(conn, mapping, seed):
    if _metadata(conn, mapping, seed) is None:
        raise DatabaseStateError('migration required before seed')
    name = mapping['schema_name']
    _check_shape(conn, name)
    current = _tables(conn, name)
    if any(current.values()):
        if _fingerprint(seed, current) != seed['seed_hash']:
            raise DatabaseStateError('noncanonical existing state; refusing seed overwrite')
        return seed['seed_hash']
    for table, columns in TABLES.items():
        for row in seed['seed'][table]:
            conn.execute(sql.SQL('INSERT INTO {}.{} ({}) VALUES ({})').format(
                sql.Identifier(name), sql.Identifier(table),
                sql.SQL(',').join(map(sql.Identifier, columns)),
                sql.SQL(',').join(sql.Placeholder() for _ in columns)),
                tuple(row[column] for column in columns))
    if _fingerprint(seed, _tables(conn, name)) != seed['seed_hash']:
        raise DatabaseStateError('seed readback fingerprint mismatch')
    return seed['seed_hash']


def prepare(conn, mapping: dict) -> str:
    """Atomically register a NEW prepared run, migrate and verify canonical seed."""
    validate('RunMapping', mapping)
    _initial(mapping)
    seed = fixture()
    with _transaction(conn):
        values = [Jsonb(mapping[c]) if c == 'verifier_scope' and mapping[c] is not None else mapping[c]
                  for c in MAPPING_COLUMNS]
        conn.execute(sql.SQL('INSERT INTO bench_control.run_registry ({}) VALUES ({})').format(
            sql.SQL(',').join(map(sql.Identifier, MAPPING_COLUMNS)),
            sql.SQL(',').join(sql.Placeholder() for _ in MAPPING_COLUMNS)), values)
        trusted = _mapping(conn, mapping['run_id'])
        _migrate(conn, trusted, seed)
        result = _seed(conn, trusted, seed)
    return result


def migrate(conn, run_id: str) -> None:
    """Upgrade a registered prepared run from no schema (0) to version 1, or no-op."""
    seed = fixture()
    with _transaction(conn):
        mapping = _mapping(conn, run_id)
        _initial(mapping)
        _migrate(conn, mapping, seed)


def seed(conn, run_id: str) -> str:
    """Repeat seed safely; reject partial/changed rows rather than overwrite them."""
    source = fixture()
    with _transaction(conn):
        mapping = _mapping(conn, run_id)
        _initial(mapping)
        return _seed(conn, mapping, source)


def rollback(conn, run_id: str) -> None:
    """Version 1 -> 0, only an unused empty/canonical run; retain registry identity."""
    source = fixture()
    with _transaction(conn):
        mapping = _mapping(conn, run_id)
        _initial(mapping)
        if _metadata(conn, mapping, source) is None:
            # A missing version is only valid when the schema is also absent.
            if conn.execute('SELECT 1 FROM pg_namespace WHERE nspname = %s',
                            (mapping['schema_name'],)).fetchone():
                raise DatabaseStateError('unversioned existing schema')
            return
        tables = _tables(conn, mapping['schema_name'])
        if any(tables.values()) and _fingerprint(source, tables) != source['seed_hash']:
            raise DatabaseStateError('rollback would destroy noncanonical state')
        conn.execute(migration_sql('down', mapping['schema_name']))
        conn.execute(sql.SQL('DROP SCHEMA {}').format(sql.Identifier(mapping['schema_name'])))
        conn.execute('DELETE FROM bench_control.schema_migrations WHERE run_id = %s', (run_id,))
