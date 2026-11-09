"""Offline adapter behavior only; no sockets, SQL execution or runtime claims."""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from contracts.validate import ContractError, ROOT, load_file, validate
from db import lifecycle as life, manage
from eval.grading import RunScope


class Connection:
    def __init__(self, role, mapping, tables=None, commit_error=None):
        self.info = SimpleNamespace(transaction_status=life.TransactionStatus.IDLE,
                                    dbname='mcpbench', host='db', port=5432,
                                    user='mcpbench_' + role)
        self.mapping = deepcopy(mapping)
        self.tables = deepcopy(tables if tables is not None else manage.fixture()['seed'])
        self.calls = []
        self.closed = False
        self.commit_error = commit_error
        self.commits = 0
        self.ledger = ('INV-001', 'a' * 64)

    @contextmanager
    def transaction(self):
        yield
        self.commits += 1
        if self.commit_error:
            raise self.commit_error

    def execute(self, query, params=None):
        text = query if isinstance(query, str) else query.as_string()
        self.calls.append((text, params))
        one, many = None, []
        if text == 'SELECT current_database(), current_user':
            one = ('mcpbench', self.info.user)
        elif 'FROM information_schema.columns' in text:
            many = [(table, column) for table, columns in manage.TABLES.items() for column in columns]
        elif 'SELECT version,migration_sha256' in text:
            seed = manage.fixture()
            one = (1, manage.migration_digest(), seed['fixture_version'], seed['tenant_id'], seed['seed_hash'])
        elif 'FROM bench_control.run_registry' in text:
            one = tuple(self.mapping[c] for c in manage.MAPPING_COLUMNS) if self.mapping else None
        elif text.startswith('UPDATE bench_control.run_registry'):
            phase, generation, agent, verifier, scope, _ = params
            self.mapping.update(phase=phase, generation=generation, agent_token_sha256=agent,
                                verifier_token_sha256=verifier,
                                verifier_scope=scope.obj if scope else None)
        elif 'WHERE idempotency_key=' in text:
            one = self.ledger
        else:
            for table, columns in manage.TABLES.items():
                if f'."{table}" ORDER BY' in text:
                    many = [tuple(row[c] for c in columns) for row in self.tables[table]]
        return SimpleNamespace(fetchone=lambda: one, fetchall=lambda: many, rowcount=1)

    def close(self):
        self.closed = True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.mapping = load_file(ROOT / 'v1/run-mapping.example.json')
        self.mapping.update(phase='prepared', generation=0, agent_token_sha256=None,
                            verifier_token_sha256=None, verifier_scope=None,
                            not_after=manage._wire(datetime.now(timezone.utc) + timedelta(hours=1)))
        self.scope = RunScope(self.mapping['run_id'], self.mapping['attempt_id'], 'test-key')
        self.connections = []
        self.now = 100.0
        self.backend = life.PostgresBackend(controller_factory=self.factory('controller'),
                                            grader_factory=self.factory('grader'),
                                            monotonic=lambda: self.now)

    def factory(self, role):
        def create(deadline):
            self.assertGreater(deadline, self.now)
            conn = Connection(role, self.mapping)
            self.connections.append(conn)
            return conn
        return create

    def test_constructor_inert_and_timeout_validation(self):
        self.assertFalse(self.connections)
        for bad in (0, 5001, True, 1.5, None):
            with self.assertRaises(ContractError):
                self.backend.set_timeout(bad)
        self.backend.set_timeout(1)
        self.assertEqual(self.backend._timeout_ms, 1)

    def test_prepare_reuses_approved_helper_and_ack_after_commit(self):
        with patch.object(manage, 'prepare') as prepare:
            self.assertIs(self.backend.prepare(self.mapping), True)
            prepare.assert_called_once()
        self.assertTrue(self.connections[-1].closed)

    def test_capture_same_readonly_repeatable_read_connection(self):
        snapshot, mapping = self.backend.capture(self.scope, 'before')
        validate('Snapshot', snapshot)
        self.assertEqual(mapping, self.mapping)
        self.assertEqual(snapshot['tables'], manage.fixture()['seed'])
        self.assertEqual(len(self.connections), 1)
        conn = self.connections[0]
        self.assertEqual(conn.info.user, 'mcpbench_grader')
        self.assertIn(('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY', None), conn.calls)
        self.assertFalse(any('FOR UPDATE' in q for q, _ in conn.calls))
        self.assertEqual(conn.commits, 1)
        self.assertTrue(conn.closed)

    def test_unsettled_snapshot_or_wrong_schema_poison_run(self):
        for args in ((self.scope, 'public', 'before'),
                     (self.scope, self.mapping['schema_name'], 'agent_only')):
            with self.subTest(args=args):
                self.backend._unsafe.clear()
                with self.assertRaisesRegex(ContractError, '^lifecycle backend failed$'):
                    self.backend.snapshot(*args)
                count = len(self.connections)
                with self.assertRaises(ContractError):
                    self.backend.read_mapping(self.scope)
                self.assertEqual(len(self.connections), count)

    def test_scope_and_endpoint_are_checked_before_business_queries(self):
        for changed in ({'attempt_id': 'wrong'}, {'schema_name': 'public'}):
            self.backend._unsafe.clear()
            self.mapping.update(changed)
            with self.assertRaises(ContractError):
                self.backend.capture(self.scope, 'before')
            self.assertFalse(any('LIMIT 1001' in q for q, _ in self.connections[-1].calls))
        self.backend._unsafe.clear()
        self.mapping['schema_name'] = load_file(ROOT / 'v1/run-mapping.example.json')['schema_name']
        conn = Connection('controller', self.mapping)
        conn.info.host = 'localhost'
        self.backend._factories['controller'] = lambda deadline: conn
        with self.assertRaises(ContractError):
            self.backend.prepare(self.mapping)
        self.assertTrue(conn.closed)
        self.assertFalse(conn.calls)

    def test_fence_fresh_locked_revocation_and_positive_receipt(self):
        for fence, phase, generation in (('agent', 'executing', 0), ('verifier', 'verifying', 1)):
            self.backend._unsafe.clear()
            self.mapping.update(phase=phase, generation=generation,
                                agent_token_sha256='a'*64 if fence == 'agent' else None,
                                verifier_token_sha256='b'*64 if fence == 'verifier' else None,
                                verifier_scope={'invoice_id': 'INV-001', 'idempotency_key': 'test-key',
                                                'original_request_hash': 'a'*64} if fence == 'verifier' else None)
            receipt = self.backend.seal(self.scope, fence)
            validate('FenceReceipt', receipt)
            self.assertTrue(receipt['commit_acknowledged'])
            self.assertEqual(receipt['generation'], generation + 1)
            conn = self.connections[-1]
            self.assertTrue(any('FOR UPDATE' in q for q, _ in conn.calls))
            self.assertIsNone(conn.mapping['agent_token_sha256'])
            self.assertIsNone(conn.mapping['verifier_token_sha256'])
            self.assertIsNone(conn.mapping['verifier_scope'])
            self.assertEqual(conn.commits, 1)

    def test_unknown_commit_no_receipt_retry_reset_or_reuse(self):
        self.mapping.update(phase='executing', agent_token_sha256='a'*64)
        conn = Connection('controller', self.mapping, commit_error=OSError('private-password'))
        factory = Mock(return_value=conn)
        self.backend._factories['controller'] = factory
        with self.assertRaisesRegex(ContractError, '^lifecycle backend failed$'):
            self.backend.seal(self.scope, 'agent')
        for call in (lambda: self.backend.seal(self.scope, 'agent'),
                     lambda: self.backend.reset_seed(self.scope, self.mapping['schema_name'], manage.fixture()),
                     lambda: self.backend.read_mapping(self.scope)):
            with self.assertRaises(ContractError):
                call()
        self.assertEqual(factory.call_count, 1)
        self.assertTrue(conn.closed)

    def test_late_commit_is_not_positive_ack(self):
        conn = Connection('controller', self.mapping)
        original = conn.transaction
        @contextmanager
        def late():
            with original():
                yield
            self.now += 6
        conn.transaction = late
        self.backend._factories['controller'] = lambda deadline: conn
        with self.assertRaises(ContractError):
            self.backend.activate(self.scope, 'agent', 'a'*64, None)
        self.assertEqual(conn.commits, 1)
        self.assertIn(self.scope.run_id, self.backend._unsafe)

    def test_interrupt_propagates_and_poisoning_survives(self):
        self.backend._factories['grader'] = Mock(side_effect=KeyboardInterrupt)
        with self.assertRaises(KeyboardInterrupt):
            self.backend.read_mapping(self.scope)
        self.assertIn(self.scope.run_id, self.backend._unsafe)

    def test_reset_locked_bounded_and_preserves_mapping(self):
        source = manage.fixture()
        with patch.object(manage, '_metadata', return_value=(1,)), patch.object(manage, '_check_shape'), \
                patch.object(manage, '_seed', return_value=source['seed_hash']) as seed:
            self.assertTrue(self.backend.reset_seed(self.scope, self.mapping['schema_name'], source))
        conn = self.connections[-1]
        self.assertEqual(conn.mapping, self.mapping)
        queries = [q for q, _ in conn.calls]
        self.assertEqual(sum(' LIMIT ' in q for q in queries), 7)
        deletes = [q for q in queries if q.startswith('DELETE')]
        self.assertEqual(len(deletes), 7)
        self.assertEqual(sum('LIMIT 10001' in q for q in queries), 2)
        self.assertIn('"idempotency_records"', deletes[0])
        self.assertIn('"customers"', deletes[-1])
        self.assertTrue(any('FOR UPDATE' in q for q in queries))
        seed.assert_called_once()

    def test_active_reset_rejected_without_delete(self):
        self.mapping.update(phase='executing', agent_token_sha256='a'*64)
        with self.assertRaises(ContractError):
            self.backend.reset_seed(self.scope, self.mapping['schema_name'], manage.fixture())
        self.assertFalse(any(q.startswith('DELETE') for q, _ in self.connections[-1].calls))

    def test_row_bound_rejects_capture(self):
        conn = Connection('grader', self.mapping)
        conn.tables['customers'] *= 1001
        self.backend._factories['grader'] = lambda deadline: conn
        with self.assertRaises(ContractError):
            self.backend.capture(self.scope, 'before')

    def test_activation_and_cleanup_lifecycle_guards(self):
        self.assertTrue(self.backend.activate(self.scope, 'agent', 'a'*64, None))
        self.assertEqual(self.connections[-1].mapping['phase'], 'executing')
        self.mapping.update(phase='agent_sealed', generation=1)
        self.assertTrue(self.backend.mark_cleaned(self.scope))
        self.assertEqual(self.connections[-1].mapping['phase'], 'cleaned')

    def test_verifier_activation_binds_exact_ledger_and_minimal_scope(self):
        request = load_file(ROOT / 'v1/verification-request.example.json')
        request.update(run_id=self.scope.run_id, attempt_id=self.scope.attempt_id,
                       idempotency_key=self.scope.idempotency_key)
        self.mapping.update(phase='agent_sealed', generation=1)
        conn = Connection('controller', self.mapping)
        conn.ledger = (request['invoice_id'], request['original_request_hash'])
        self.backend._factories['controller'] = lambda deadline: conn
        self.assertTrue(self.backend.activate(self.scope, 'verify', 'b'*64, request))
        self.assertEqual(conn.mapping['phase'], 'verifying')
        self.assertEqual(conn.mapping['verifier_scope'],
                         {key: request[key] for key in ('invoice_id', 'idempotency_key', 'original_request_hash')})
        self.assertIsNone(conn.mapping['agent_token_sha256'])
        conn = Connection('controller', self.mapping)
        self.backend._factories['controller'] = lambda deadline: conn
        with self.assertRaises(ContractError):
            self.backend.activate(self.scope, 'verify', 'b'*64, request)
        self.assertFalse(any(q.startswith('UPDATE') for q, _ in conn.calls))

    def test_fixed_compose_environment_is_accepted_before_connection(self):
        with patch.dict(life.os.environ, {'PGHOST': 'db', 'PGDATABASE': 'mcpbench'}, clear=True), \
                patch.object(life, '_resolve', return_value='192.0.2.1'), \
                patch.object(life._DeadlineConnection, '_connect_gen', return_value='generator'), \
                patch.object(life.waiting, 'wait_conn', return_value=SimpleNamespace()) as wait:
            conn = life._factory('grader', 'synthetic-password')(life.time.monotonic() + 2)
            self.assertGreater(conn.deadline, life.time.monotonic())
            wait.assert_called_once()

    def test_fixed_config_and_private_secret_inventory(self):
        config = dict(schema_version=1, host='db', port=5432, dbname='mcpbench',
                      controller_passfile=str(life.PASSFILES['controller']),
                      grader_passfile=str(life.PASSFILES['grader']))
        import json
        values = {life.CONFIG_PATH: json.dumps(config).encode()}
        for role in life.PASSFILES:
            values[life.PASSFILES[role]] = f'db:5432:mcpbench:mcpbench_{role}:{role}-private-password'.encode()
        directory = SimpleNamespace(st_mode=0o40700, st_uid=life.os.geteuid())
        with patch.object(life, '_private_file', side_effect=lambda path, maximum: values[path]), \
                patch.object(Path, 'stat', return_value=directory):
            backend = life.PostgresBackend.from_private_config()
            self.assertEqual(len(backend.known_secrets), 6)
            self.assertIn('controller-private-password', backend.known_secrets)
            config['host'] = 'localhost'
            values[life.CONFIG_PATH] = json.dumps(config).encode()
            with self.assertRaisesRegex(ContractError, '^lifecycle configuration failed$'):
                life.PostgresBackend.from_private_config()
        with self.assertRaises(ContractError):
            life.PostgresBackend.from_private_config('/tmp/database.json')

    def test_private_file_rejects_symlinks_permissions_and_oversize(self):
        import tempfile
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / 'secret'
            path.write_bytes(b'synthetic-test-secret')
            path.chmod(0o600)
            self.assertEqual(life._private_file(path, 100), b'synthetic-test-secret')
            with self.assertRaises(ValueError):
                life._private_file(path, 3)
            path.chmod(0o644)
            with self.assertRaises(ValueError):
                life._private_file(path, 100)
            path.chmod(0o600)
            link = Path(name) / 'linked'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                life._private_file(link, 100)
            parent = Path(name) / 'parent'
            parent.symlink_to(Path(name), target_is_directory=True)
            with self.assertRaises(OSError):
                life._private_file(parent / 'secret', 100)

    def test_driver_wait_uses_whole_operation_remaining_time_and_closes_on_timeout(self):
        conn = SimpleNamespace(deadline=105.0, pgconn=SimpleNamespace(socket=42), close=Mock())
        with patch.object(life.time, 'monotonic', return_value=102.0), \
                patch.object(life.waiting, 'wait', return_value='ack') as wait:
            self.assertEqual(life._DeadlineConnection.wait(conn, 'generator'), 'ack')
            self.assertEqual(wait.call_args.kwargs['timeout'], 3.0)
        with patch.object(life.time, 'monotonic', return_value=106.0):
            with self.assertRaises(TimeoutError):
                life._DeadlineConnection.wait(conn, 'generator')
        conn.close.assert_called_once()
        conn.close.reset_mock()
        with patch.object(life.time, 'monotonic', return_value=102.0), \
                patch.object(life.waiting, 'wait', side_effect=TimeoutError):
            with self.assertRaises(TimeoutError):
                life._DeadlineConnection.wait(conn, 'generator')
        conn.close.assert_called_once()

    def test_conninfo_omits_service_lookup_keyword(self):
        from psycopg.conninfo import conninfo_to_dict
        for role in ('controller', 'grader'):
            with self.subTest(role=role):
                params = conninfo_to_dict(life._conninfo(role, 'synthetic-password', '192.0.2.1'))
                self.assertNotIn('service', params)
                self.assertEqual(params['host'], 'db')
                self.assertEqual(params['hostaddr'], '192.0.2.1')
                self.assertEqual(params['dbname'], 'mcpbench')
                self.assertEqual(params['user'], 'mcpbench_' + role)

    def test_production_factory_rejects_inherited_libpq_before_dns(self):
        for key, value in (('PGHOSTADDR', '127.0.0.1'), ('PGSERVICE', 'untrusted'),
                           ('PGSERVICE', ''), ('PGSERVICEFILE', '/tmp/untrusted-service')):
            with self.subTest(variable=key, value=value), \
                    patch.dict(life.os.environ, {key: value}, clear=True), \
                    patch.object(life, '_resolve') as resolve:
                with self.assertRaises(ContractError):
                    life._factory('controller', 'fake-password')(life.time.monotonic() + 1)
                resolve.assert_not_called()


if __name__ == '__main__':
    unittest.main()
