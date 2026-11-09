"""UNRUN until T018. Run only inside the admitted, isolated MCPBench network.

Opt-in never authorizes startup or bootstrap. Fixed host=db/database=mcpbench;
passwords use private PGPASSFILE (not DSNs or argv). No host port is contacted.
"""
import os
import secrets
import unittest
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg import sql
from contracts.validate import ROOT, load_file, schema_name
from db import manage

LIVE = os.environ.get('MCPBENCH_LIVE_DB') == 'dedicated-container'


def connect(role):
    # Explicit parameters override inherited PGHOST/PGPORT/PGDATABASE/PGUSER.
    return psycopg.connect(host='db', port=5432, dbname='mcpbench', user=role,
                           connect_timeout=3, autocommit=True)


@unittest.skipUnless(LIVE, 'UNRUN: requires T018 dedicated-container admission')
class PostgreSQLTests(unittest.TestCase):
    def setUp(self):
        self.controller = connect('mcpbench_controller')
        self.mapping = load_file(ROOT / 'v1/run-mapping.example.json')
        suffix = secrets.token_hex(12)
        self.run = 'run-dbtest-' + suffix
        self.mapping.update(run_id=self.run, attempt_id='attempt-dbtest-' + suffix,
                            schema_name=schema_name(self.run), phase='prepared', generation=0,
                            agent_token_sha256=None,
                            not_after=(datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace('+00:00', 'Z'))
        self.name = self.mapping['schema_name']
        self.addCleanup(self.controller.close)
        manage.prepare(self.controller, self.mapping)
        self.addCleanup(self.cleanup_run)

    def cleanup_run(self):
        # Test-owned prepared runs only. This is not a production cleanup API.
        with self.controller.transaction():
            mapping = manage._mapping(self.controller, self.run)
            manage._initial(mapping)
            for table in reversed(manage.TABLES):
                self.controller.execute(sql.SQL('DELETE FROM {}.{}').format(
                    sql.Identifier(self.name), sql.Identifier(table)))
        manage.rollback(self.controller, self.run)
        self.controller.execute('DELETE FROM bench_control.run_registry WHERE run_id=%s', (self.run,))

    def q(self, source):
        return sql.SQL(source).format(s=sql.Identifier(self.name))

    def invoice(self, conn, *, quantity=2, price=12500, total=25000, ledger=True, lines=True):
        conn.execute(self.q("INSERT INTO {s}.invoices VALUES ('INV-TEST','CUST-001','2026-11-07','2026-11-21','USD','draft',%s,0,%s,'2026-11-07T23:00:00Z')"), (total, total))
        if lines:
            conn.execute(self.q("INSERT INTO {s}.invoice_lines VALUES ('LINE-TEST','INV-TEST','SVC-CONSULT',%s,%s,%s,1)"), (quantity, price, total))
        if ledger:
            conn.execute(self.q("INSERT INTO {s}.idempotency_records VALUES ('key-test',%s,'INV-TEST')"), ('1' * 64,))

    def test_runtime_roles_connect_only_to_benchmark_database(self):
        for role in ('mcpbench_controller', 'mcpbench_service', 'mcpbench_grader'):
            for database in ('postgres', 'template0', 'template1'):
                with self.subTest(role=role, database=database):
                    self.assertFalse(self.controller.execute(
                        "SELECT has_database_privilege(%s,%s,'CONNECT')",
                        (role, database)).fetchone()[0])
            self.assertTrue(self.controller.execute(
                "SELECT has_database_privilege(%s,'mcpbench','CONNECT')",
                (role,)).fetchone()[0])

    def test_seed_twice_and_existing_volume_migration(self):
        expected = manage.fixture()['seed_hash']
        self.assertEqual(manage.seed(self.controller, self.run), expected)
        manage.migrate(self.controller, self.run)
        self.assertEqual(manage.seed(self.controller, self.run), expected)
        with connect('mcpbench_controller') as reconnected:
            manage.migrate(reconnected, self.run)
            self.assertEqual(manage.seed(reconnected, self.run), expected)

    def test_rollback_upgrade_and_repeat_rollback(self):
        manage.rollback(self.controller, self.run)
        manage.rollback(self.controller, self.run)
        manage.migrate(self.controller, self.run)
        self.assertEqual(manage.seed(self.controller, self.run), manage.fixture()['seed_hash'])

    def test_seed_rejects_extra_table_and_column(self):
        alterations = (
            ('CREATE TABLE {s}.extra_table(extra_column integer)', 'DROP TABLE {s}.extra_table'),
            ('ALTER TABLE {s}.customers ADD COLUMN extra_column text',
             'ALTER TABLE {s}.customers DROP COLUMN extra_column'),
        )
        for create, restore in alterations:
            with self.subTest(alteration=create):
                self.controller.execute(self.q(create))
                try:
                    with self.assertRaisesRegex(manage.DatabaseStateError, 'inventory'):
                        manage.seed(self.controller, self.run)
                finally:
                    self.controller.execute(self.q(restore))
                self.assertEqual(manage.seed(self.controller, self.run), manage.fixture()['seed_hash'])

    def test_version_checksum_rejection(self):
        self.controller.execute('UPDATE bench_control.schema_migrations SET migration_sha256=%s WHERE run_id=%s', ('0' * 64, self.run))
        try:
            with self.assertRaises(manage.DatabaseStateError):
                manage.migrate(self.controller, self.run)
        finally:
            self.controller.execute('UPDATE bench_control.schema_migrations SET migration_sha256=%s WHERE run_id=%s', (manage.migration_digest(), self.run))

    def test_foreign_key_quantity_money_and_atomic_rollback(self):
        for quantity, price, total in ((0,12500,0),(1001,12500,12512500),(2,-1,-2),
                                        (2,12500,24999),(1000,9007199254740991,9007199254740991)):
            with self.subTest(quantity=quantity, price=price, total=total):
                with self.assertRaises(psycopg.IntegrityError):
                    with self.controller.transaction():
                        self.invoice(self.controller, quantity=quantity, price=price, total=total)
                self.assertEqual(self.controller.execute(self.q('SELECT count(*) FROM {s}.invoices')).fetchone()[0], 0)
        with self.assertRaises(psycopg.errors.ForeignKeyViolation):
            with self.controller.transaction():
                self.controller.execute(self.q("INSERT INTO {s}.projects VALUES ('PRJ-INVALID','CUST-MISSING','Missing',true)"))

    def test_commit_requires_lines_and_ledger(self):
        for ledger, lines in ((False,True),(True,False),(False,False)):
            with self.assertRaises(psycopg.errors.CheckViolation):
                with self.controller.transaction():
                    self.invoice(self.controller, ledger=ledger, lines=lines)
        self.assertEqual(self.controller.execute(self.q('SELECT count(*) FROM {s}.invoices')).fetchone()[0], 0)

    def test_valid_service_invoice_and_unique_idempotency(self):
        with connect('mcpbench_service') as service:
            with service.transaction():
                service.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR SHARE', (self.run,))
                self.invoice(service)
            with self.assertRaises(psycopg.errors.UniqueViolation):
                with service.transaction():
                    service.execute(self.q("INSERT INTO {s}.idempotency_records VALUES ('key-test',%s,'INV-TEST')"), ('2' * 64,))
        with self.assertRaises(manage.DatabaseStateError):
            manage.seed(self.controller, self.run)
        with self.assertRaises(manage.DatabaseStateError):
            manage.rollback(self.controller, self.run)

    def test_least_privilege_and_read_only_grader(self):
        with connect('mcpbench_service') as service:
            for statement, params in (
                ('UPDATE bench_control.run_registry SET generation=1 WHERE run_id=%s', (self.run,)),
                ('UPDATE bench_control.run_registry SET agent_token_sha256=NULL WHERE run_id=%s', (self.run,)),
                ('UPDATE bench_control.run_registry SET schema_name=schema_name WHERE run_id=%s', (self.run,)),
                (self.q('UPDATE {s}.customers SET active=false'), None),
                (self.q('DELETE FROM {s}.items'), None),
                (self.q('CREATE TABLE {s}.forbidden(x integer)'), None)):
                with self.subTest(statement=str(statement)):
                    with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                        service.execute(statement, params)
        with connect('mcpbench_grader') as grader:
            self.assertEqual(grader.execute(self.q('SELECT count(*) FROM {s}.customers')).fetchone()[0], 2)
            with self.assertRaises(psycopg.errors.ReadOnlySqlTransaction):
                grader.execute(self.q('DELETE FROM {s}.customers'))
            grader.execute('SET default_transaction_read_only=off')
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                grader.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR SHARE', (self.run,))
            with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                grader.execute(self.q('DELETE FROM {s}.customers'))

    def test_shared_lock_blocks_controller_and_exclusive_blocks_service(self):
        with connect('mcpbench_service') as service:
            with service.transaction():
                service.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR SHARE', (self.run,))
                with self.assertRaises(psycopg.errors.LockNotAvailable):
                    with self.controller.transaction():
                        self.controller.execute("SET LOCAL lock_timeout='100ms'")
                        self.controller.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR UPDATE', (self.run,))
            with self.controller.transaction():
                self.controller.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR UPDATE', (self.run,))
                with self.assertRaises(psycopg.errors.LockNotAvailable):
                    with service.transaction():
                        service.execute("SET LOCAL lock_timeout='100ms'")
                        service.execute('SELECT run_id FROM bench_control.run_registry WHERE run_id=%s FOR SHARE', (self.run,))


if __name__ == '__main__':
    unittest.main()
