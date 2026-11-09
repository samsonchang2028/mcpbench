"""Fail-closed lifecycle for the dedicated MCPBench database; inert on import."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from functools import wraps
import json
import os
from pathlib import Path
import stat
import socket
import queue
import threading
import time

import psycopg
from psycopg import sql, waiting
from psycopg.conninfo import make_conninfo
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from contracts.validate import ContractError, canonical_hash, validate
from db import manage
from eval.grading.oracle import RunScope, identity, registration, require

CONFIG_PATH = Path('/run/mcpbench/control/database.json')
PASSFILES = {role: CONFIG_PATH.parent / f'{role}.pgpass' for role in ('controller', 'grader')}
ROW_LIMITS = {table: 10000 if table in {'timesheets', 'invoice_lines'} else 1000
              for table in manage.TABLES}


def _utc():
    return datetime.now(timezone.utc)


def _private_file(path: Path, maximum: int) -> bytes:
    """No symlink components, current owner, regular mode0600, bounded read."""
    require(path.is_absolute(), 'absolute private path required')
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in path.parts[1:-1]:
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or info.st_uid != os.geteuid():
            raise ValueError('private file')
        value = os.read(fd, maximum + 1)
        if len(value) > maximum:
            raise ValueError('private file size')
        return value
    finally:
        os.close(fd)


class _DeadlineConnection(psycopg.Connection):
    """Pin all libpq waits, including COMMIT/ROLLBACK, to one absolute bound.

    Do not use Connection.wait's cancellation grace period: on uncertainty close
    the socket immediately and retain the run for external quarantine.
    """
    deadline: float

    def wait(self, gen, interval=0.05, timeout=None):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            self.close()
            raise TimeoutError('operation deadline')
        try:
            return waiting.wait(gen, self.pgconn.socket, interval=min(interval, 0.05),
                                timeout=min(remaining, timeout) if timeout is not None else remaining)
        except BaseException:
            self.close()
            raise


def _conninfo(role, password, hostaddr=''):
    return make_conninfo(host='db', hostaddr=hostaddr, port=5432, dbname='mcpbench',
                         user=f'mcpbench_{role}', password=password,
                         passfile='/dev/null', sslmode='disable',
                         gssencmode='disable', options='-c search_path=pg_catalog',
                         application_name='mcpbench-lifecycle', connect_timeout=5,
                         target_session_attrs='any', channel_binding='disable')


def _resolve(deadline):
    # libpq hostname resolution can block before yielding its poll generator.
    # Bound that read-only lookup separately and use one resolved address, with
    # no fallback/retry. The daemon can finish DNS after timeout, never SQL.
    result = queue.Queue(maxsize=1)
    def lookup():
        try:
            result.put(socket.getaddrinfo('db', 5432, socket.AF_INET, socket.SOCK_STREAM))
        except Exception:
            result.put(None)
    threading.Thread(target=lookup, daemon=True).start()
    rows = result.get(timeout=max(0, deadline - time.monotonic()))
    require(rows is not None, 'owned database alias unresolved')
    addresses = {row[4][0] for row in rows}
    require(len(addresses) == 1, 'ambiguous database alias')
    return addresses.pop()


def _factory(role, password):
    def connect(deadline):
        # No service files, environment DSNs, plugins, connection retry or fallback
        # hosts. The operator admits the fixed db alias on the owned network.
        allowed_env = {'PGHOST': 'db', 'PGDATABASE': 'mcpbench'}
        require(all(key in allowed_env and value == allowed_env[key]
                    for key, value in os.environ.items() if key.startswith('PG')),
                'fixed libpq environment required')
        conninfo = _conninfo(role, password, _resolve(deadline))
        conn = waiting.wait_conn(_DeadlineConnection._connect_gen(conninfo), interval=0.05,
                                 timeout=max(0, deadline - time.monotonic()))
        conn.deadline = deadline
        return conn
    return connect


def _operation(function):
    @wraps(function)
    def guarded(self, scope, *args, **kwargs):
        run_id = scope.get('run_id') if isinstance(scope, dict) else getattr(scope, 'run_id', None)
        try:
            validate('Identifier', run_id)
            require(run_id not in self._unsafe, 'run unavailable')
            self._deadline = self._clock() + self._timeout_ms / 1000
            result = function(self, scope, *args, **kwargs)
            self._check_deadline()
            return result
        except Exception:
            if isinstance(run_id, str):
                self._unsafe.add(run_id)
            raise ContractError('lifecycle backend failed') from None
        except BaseException:
            if isinstance(run_id, str):
                self._unsafe.add(run_id)
            raise
    return guarded


class PostgresBackend:
    """One trusted serial controller, with independently injected role factories.

    Factories receive an absolute monotonic deadline and return fresh idle tuple-
    row connections. Production factories enforce that deadline in every wait;
    injected factories must do likewise. No connections are opened at creation.
    """
    def __init__(self, *, controller_factory, grader_factory, known_secrets=(),
                 monotonic=time.monotonic):
        require(controller_factory is not grader_factory, 'separate role factories required')
        self._factories = {'controller': controller_factory, 'grader': grader_factory}
        self.known_secrets = tuple(known_secrets)
        self._clock = monotonic
        self._timeout_ms = 5000
        self._deadline = 0.0
        self._unsafe = set()

    @classmethod
    def from_private_config(cls, path=str(CONFIG_PATH)):
        try:
            require(type(path) is str and path == str(CONFIG_PATH), 'fixed private config required')
            def unique(pairs):
                result = {}
                for key, value in pairs:
                    require(key not in result, 'duplicate config key')
                    result[key] = value
                return result
            directory = CONFIG_PATH.parent.stat(follow_symlinks=False)
            require(stat.S_ISDIR(directory.st_mode) and directory.st_uid == os.geteuid() and
                    stat.S_IMODE(directory.st_mode) == 0o700, 'private control directory required')
            config = json.loads(_private_file(CONFIG_PATH, 4096), object_pairs_hook=unique)
            expected = dict(schema_version=1, host='db', port=5432, dbname='mcpbench',
                            controller_passfile=str(PASSFILES['controller']),
                            grader_passfile=str(PASSFILES['grader']))
            require(config == expected and type(config['schema_version']) is int and
                    type(config['port']) is int, 'fixed database configuration required')
            passwords = {}
            secrets = []
            for role, passfile in PASSFILES.items():
                text = _private_file(passfile, 1024).decode('ascii').rstrip('\n')
                prefix = f'db:5432:mcpbench:mcpbench_{role}:'
                require(text.startswith(prefix), 'dedicated role passfile required')
                password = text[len(prefix):]
                require(16 <= len(password) <= 256 and all(c.isalnum() or c in '-_' for c in password),
                        'synthetic password required')
                passwords[role] = password
                secrets.extend((password, text, _conninfo(role, password)))
            require(passwords['controller'] != passwords['grader'], 'distinct credentials required')
            return cls(controller_factory=_factory('controller', passwords['controller']),
                       grader_factory=_factory('grader', passwords['grader']),
                       known_secrets=tuple(secrets))
        except Exception:
            raise ContractError('lifecycle configuration failed') from None

    def set_timeout(self, timeout_ms):
        if type(timeout_ms) is not int or not 1 <= timeout_ms <= 5000:
            raise ContractError('invalid lifecycle timeout')
        self._timeout_ms = timeout_ms

    def _check_deadline(self):
        require(self._clock() < self._deadline, 'operation deadline')

    @contextmanager
    def _connection(self, role):
        self._check_deadline()
        conn = self._factories[role](self._deadline)
        try:
            self._check_deadline()
            require(conn.info.transaction_status == TransactionStatus.IDLE, 'idle connection required')
            require(conn.info.dbname == 'mcpbench' and conn.info.user == f'mcpbench_{role}' and
                    conn.info.host == 'db' and conn.info.port == 5432, 'dedicated endpoint required')
            yield conn
            self._check_deadline()
        finally:
            conn.close()

    @contextmanager
    def _transaction(self, role):
        with self._connection(role) as conn:
            with conn.transaction():
                conn.execute('SET TRANSACTION ISOLATION LEVEL ' +
                             ('REPEATABLE READ, READ ONLY' if role == 'grader' else 'READ COMMITTED'))
                ms = max(1, min(self._timeout_ms, int((self._deadline - self._clock()) * 1000)))
                conn.execute("SELECT set_config('statement_timeout', %s, true), "
                             "set_config('lock_timeout', %s, true)", (f'{ms}ms', f'{ms}ms'))
                conn.execute("SET LOCAL TIME ZONE 'UTC'")
                require(conn.execute('SELECT current_database(), current_user').fetchone() ==
                        ('mcpbench', f'mcpbench_{role}'), 'database role mismatch')
                yield conn
                self._check_deadline()
            self._check_deadline()  # Positive COMMIT ACK, not merely queued COMMIT.

    def _mapping(self, conn, scope, *, lock=False):
        require(isinstance(scope, RunScope), 'trusted scope required')
        for value in (scope.run_id, scope.attempt_id, scope.idempotency_key):
            validate('Identifier', value)
        row = conn.execute(sql.SQL('SELECT {} FROM bench_control.run_registry WHERE run_id=%s' +
                                  (' FOR UPDATE' if lock else '')).format(
            sql.SQL(',').join(map(sql.Identifier, manage.MAPPING_COLUMNS))), (scope.run_id,)).fetchone()
        require(row is not None, 'unknown run')
        value = dict(zip(manage.MAPPING_COLUMNS, row))
        value['not_after'] = manage._wire(value['not_after'])
        validate('RunMapping', value)
        identity(value, scope)
        require(value['phase'] not in {'quarantined', 'cleaned'}, 'terminal run')
        return value

    def _tables(self, conn, name):
        # Bound reads and hence all scoped reset writes. Extra rows fail closed.
        result = {}
        for table, columns in manage.TABLES.items():
            limit = ROW_LIMITS[table]
            rows = conn.execute(sql.SQL('SELECT {} FROM {}.{} ORDER BY {} LIMIT {}').format(
                sql.SQL(',').join(map(sql.Identifier, columns)), sql.Identifier(name),
                sql.Identifier(table), sql.Identifier(columns[0]), sql.Literal(limit + 1))).fetchall()
            require(len(rows) <= limit, 'table row bound')
            result[table] = [dict(zip(columns, map(manage._wire, row))) for row in rows]
        validate('Tables', result)
        return result

    @_operation
    def prepare(self, mapping):
        validate('RunMapping', mapping)
        require(mapping['phase'] == 'prepared' and mapping['generation'] == 0, 'unused run required')
        # Approved helper owns this transaction. Absolute driver deadline still
        # bounds its existing per-statement limits and its COMMIT acknowledgment.
        with self._connection('controller') as conn:
            manage.prepare(conn, deepcopy(mapping))
        return True

    @_operation
    def read_mapping(self, scope):
        with self._transaction('grader') as conn:
            result = self._mapping(conn, scope)
        return result

    def _capture(self, scope, stage, schema=None):
        require(stage in {'before', 'agent_only', 'final', 'after_reset', 'diagnostic'}, 'snapshot stage')
        with self._transaction('grader') as conn:
            mapping = self._mapping(conn, scope)
            require(schema is None or schema == mapping['schema_name'], 'registered schema required')
            expected = {'before': ('prepared', 0), 'agent_only': ('agent_sealed', 1),
                        'final': ('final_sealed', 2)}
            if stage in expected:
                require((mapping['phase'], mapping['generation']) == expected[stage], 'unsettled snapshot')
            if stage == 'after_reset':
                self._resettable(mapping)
            manage._check_shape(conn, mapping['schema_name'])
            snapshot = dict(schema_version=1, run_id=scope.run_id, attempt_id=scope.attempt_id,
                            stage=stage, captured_at=manage._wire(_utc()),
                            settlement_generation=None if stage == 'diagnostic' else mapping['generation'],
                            tables=self._tables(conn, mapping['schema_name']))
            validate('Snapshot', snapshot)
        return snapshot, mapping

    @_operation
    def snapshot(self, scope, schema, stage):
        return self._capture(scope, stage, schema)[0]

    @_operation
    def capture(self, scope, stage):
        return self._capture(scope, stage)

    @staticmethod
    def _resettable(mapping):
        require((mapping['phase'], mapping['generation']) in
                {('prepared', 0), ('agent_sealed', 1), ('final_sealed', 2)} and
                mapping['agent_token_sha256'] is None and mapping['verifier_token_sha256'] is None,
                'acknowledged inactive state required')

    @_operation
    def reset_seed(self, scope, schema, fixture):
        source = manage.fixture()
        require(canonical_hash(source) == canonical_hash(fixture), 'frozen fixture required')
        with self._transaction('controller') as conn:
            mapping = self._mapping(conn, scope, lock=True)
            self._resettable(mapping)
            registration(mapping, scope, source)
            require(schema == mapping['schema_name'], 'registered schema required')
            require(manage._metadata(conn, mapping, source) is not None, 'migration required')
            manage._check_shape(conn, schema)
            self._tables(conn, schema)
            # No CASCADE/TRUNCATE/schema recreation. FK children first, then seed
            # the exact frozen bounded rows in their declared dependency order.
            for table in ('idempotency_records', 'invoice_lines', 'invoices', 'timesheets',
                          'projects', 'items', 'customers'):
                conn.execute(sql.SQL('DELETE FROM {}.{}').format(sql.Identifier(schema), sql.Identifier(table)))
            manage._seed(conn, mapping, source)
        return True

    @_operation
    def activate(self, scope, mode, token_sha256, verification_request):
        validate('SHA256', token_sha256)
        require(mode in {'agent', 'verify'}, 'activation mode')
        with self._transaction('controller') as conn:
            mapping = self._mapping(conn, scope, lock=True)
            require(datetime.fromisoformat(mapping['not_after']) > _utc(), 'expired run')
            if mode == 'agent':
                require(verification_request is None and (mapping['phase'], mapping['generation']) ==
                        ('prepared', 0), 'agent activation state')
                updated = dict(mapping, phase='executing', agent_token_sha256=token_sha256)
            else:
                validate('VerificationRequest', verification_request)
                identity(verification_request, scope)
                require(verification_request['idempotency_key'] == scope.idempotency_key and
                        (mapping['phase'], mapping['generation']) == ('agent_sealed', 1) and
                        mapping['workflow_kind'] == 'draft_invoice', 'verifier activation state')
                verifier = {key: verification_request[key] for key in
                            ('invoice_id', 'idempotency_key', 'original_request_hash')}
                # The trusted request cannot authorize replay against a missing or
                # different ledger binding, even if the caller bypasses the oracle.
                ledger = conn.execute(sql.SQL('SELECT invoice_id,request_hash FROM {}.idempotency_records '
                                              'WHERE idempotency_key=%s').format(
                    sql.Identifier(mapping['schema_name'])), (scope.idempotency_key,)).fetchone()
                require(ledger == (verifier['invoice_id'], verifier['original_request_hash']), 'verifier ledger')
                updated = dict(mapping, phase='verifying', verifier_token_sha256=token_sha256,
                               verifier_scope=verifier)
            self._update(conn, updated)
        return True

    @staticmethod
    def _update(conn, mapping):
        validate('RunMapping', mapping)
        cursor = conn.execute('UPDATE bench_control.run_registry SET phase=%s,generation=%s,'
                              'agent_token_sha256=%s,verifier_token_sha256=%s,verifier_scope=%s WHERE run_id=%s',
                              (mapping['phase'], mapping['generation'], mapping['agent_token_sha256'],
                               mapping['verifier_token_sha256'], Jsonb(mapping['verifier_scope'])
                               if mapping['verifier_scope'] is not None else None, mapping['run_id']))
        require(cursor.rowcount == 1, 'registry acknowledgment')

    @_operation
    def seal(self, scope, fence):
        require(fence in {'agent', 'verifier'}, 'fence kind')
        started = self._clock()
        with self._transaction('controller') as conn:
            mapping = self._mapping(conn, scope, lock=True)
            phase, generation = ('executing', 0) if fence == 'agent' else ('verifying', 1)
            require((mapping['phase'], mapping['generation']) == (phase, generation), 'fresh fence required')
            phase = 'agent_sealed' if fence == 'agent' else 'final_sealed'
            self._update(conn, dict(mapping, phase=phase, generation=generation + 1,
                                    agent_token_sha256=None, verifier_token_sha256=None, verifier_scope=None))
        receipt = dict(schema_version=1, run_id=scope.run_id, attempt_id=scope.attempt_id,
                       fence=fence, status='settled', generation=generation + 1, phase=phase,
                       commit_acknowledged=True, committed_at=manage._wire(_utc()), remaining_inflight=0,
                       elapsed_ms=max(0, (self._clock() - started) * 1000))
        validate('FenceReceipt', receipt)
        return receipt

    @_operation
    def mark_cleaned(self, scope):
        with self._transaction('controller') as conn:
            mapping = self._mapping(conn, scope, lock=True)
            self._resettable(mapping)
            require(mapping['phase'] in {'agent_sealed', 'final_sealed'}, 'cleanup requires seal')
            source = manage.fixture()
            registration(mapping, scope, source)
            require(manage._metadata(conn, mapping, source) is not None, 'migration required')
            manage._check_shape(conn, mapping['schema_name'])
            require(manage._fingerprint(source, self._tables(conn, mapping['schema_name'])) == source['seed_hash'],
                    'cleanup fingerprint')
            self._update(conn, dict(mapping, phase='cleaned'))
        return True
