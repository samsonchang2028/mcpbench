"""Fake backend tests only. PostgreSQL reset/privileges/transaction proof UNRUN."""
from copy import deepcopy
import unittest
import psycopg

from eval.grading.test_oracle import case
from eval.reset import check_seed, reset_and_check


class FakeBackend:
    def __init__(self, prepared=True):
        self.task, self.fixture, _, self.capture, self.mapping, self.receipt, self.scope = case()
        if prepared:
            self.mapping.update(phase='prepared', generation=0)
        self.calls = []
        self.ack = True
        self.dirty = False
        self.raise_reset = False

    def read_mapping(self, scope):
        return deepcopy(self.mapping)

    def reset_seed(self, scope, schema, fixture):
        self.calls.append((scope, schema))
        if self.raise_reset:
            raise OSError('simulated disconnected backend')
        self.capture['tables'] = deepcopy(fixture['seed'])
        if self.dirty:
            self.capture['tables']['customers'][0]['name'] = 'not reset'
        return self.ack

    def snapshot(self, scope, schema, stage):
        snapshot = deepcopy(self.capture)
        snapshot.update(stage=stage, settlement_generation=self.mapping['generation'])
        return snapshot


class ResetTests(unittest.TestCase):
    def test_backend_errors_are_sanitized_without_retry_or_reuse(self):
        for prepared in (True, False):
            operations = (['read_mapping', 'reset_seed', 'read_mapping', 'snapshot'] if prepared else
                          ['read_mapping', 'snapshot', 'reset_seed', 'read_mapping', 'snapshot'])
            for error_type in (OSError, psycopg.OperationalError, psycopg.IntegrityError):
                for fail_at in range(1, len(operations) + 1):
                    with self.subTest(prepared=prepared, error=error_type, fail_at=fail_at):
                        class FailingBackend(FakeBackend):
                            def __init__(self):
                                super().__init__(prepared)
                                self.operations = []

                            def invoke(self, method, *args):
                                self.operations.append(method)
                                value = getattr(super(), method)(*args)
                                if len(self.operations) == fail_at:
                                    # Reset may have committed before acknowledgment was lost.
                                    raise error_type('private connection details must not escape')
                                return value

                            def read_mapping(self, *args):
                                return self.invoke('read_mapping', *args)

                            def reset_seed(self, *args):
                                return self.invoke('reset_seed', *args)

                            def snapshot(self, *args):
                                return self.invoke('snapshot', *args)

                        backend = FailingBackend()
                        result = reset_and_check(backend, backend.scope, backend.fixture,
                                                 receipt=backend.receipt, evidence_persisted=True)
                        self.assertFalse(result.passed)
                        self.assertEqual(result.reason, 'reset_and_check_failed')
                        self.assertEqual(backend.operations, operations[:fail_at])

    def test_backend_interrupts_propagate_without_retry(self):
        for error_type in (KeyboardInterrupt, SystemExit):
            class InterruptedBackend(FakeBackend):
                def reset_seed(self, *args):
                    super().reset_seed(*args)
                    raise error_type()
            backend = InterruptedBackend()
            with self.assertRaises(error_type):
                reset_and_check(backend, backend.scope, backend.fixture)
            self.assertEqual(len(backend.calls), 1)

    def test_initial_and_final_reset(self):
        for prepared in (True, False):
            backend = FakeBackend(prepared)
            result = reset_and_check(backend, backend.scope, backend.fixture,
                                     receipt=backend.receipt, evidence_persisted=True)
            self.assertTrue(result.passed)
            self.assertEqual(backend.calls, [(backend.scope, backend.mapping['schema_name'])])

    def test_final_generation_two_cleanup(self):
        backend = FakeBackend(False)
        backend.mapping.update(phase='final_sealed', generation=2)
        backend.receipt.update(fence='verifier', phase='final_sealed', generation=2)
        self.assertTrue(reset_and_check(backend, backend.scope, backend.fixture,
                                       receipt=backend.receipt, evidence_persisted=True).passed)

    def test_registry_drift_after_reset_is_failure(self):
        class DriftingBackend(FakeBackend):
            def reset_seed(self, scope, schema, fixture):
                super().reset_seed(scope, schema, fixture)
                self.mapping['not_after'] = '2026-11-08T23:00:00Z'
                return True
        backend = DriftingBackend()
        self.assertFalse(reset_and_check(backend, backend.scope, backend.fixture).passed)

    def test_reset_failure_ack_and_dirty_seed(self):
        for field, value in [('ack', False), ('ack', None), ('ack', 1), ('dirty', True), ('raise_reset', True)]:
            backend = FakeBackend()
            setattr(backend, field, value)
            self.assertFalse(reset_and_check(backend, backend.scope, backend.fixture).passed)

    def test_no_mutation_on_invalid_scope_or_active_state(self):
        for field, value in [('schema_name', 'public'), ('run_id', 'WRONG'),
                             ('attempt_id', 'WRONG'), ('tenant_id', 'WRONG'),
                             ('phase', 'executing'), ('phase', 'quarantined'),
                             ('agent_token_sha256', '0' * 64)]:
            backend = FakeBackend()
            backend.mapping[field] = value
            self.assertFalse(reset_and_check(backend, backend.scope, backend.fixture).passed)
            self.assertFalse(backend.calls)

    def test_cleanup_requires_fence_and_saved_evidence(self):
        backend = FakeBackend(False)
        for receipt, persisted in [(None, True), (backend.receipt, False)]:
            self.assertFalse(reset_and_check(backend, backend.scope, backend.fixture,
                                             receipt=receipt, evidence_persisted=persisted).passed)
        self.assertFalse(backend.calls)

    def test_row_order_invariant_and_all_field_fingerprint(self):
        backend = FakeBackend()
        snapshot = backend.snapshot(backend.scope, backend.mapping['schema_name'], 'before')
        snapshot['tables'] = deepcopy(backend.fixture['seed'])
        for rows in snapshot['tables'].values():
            rows.reverse()
        self.assertTrue(check_seed(backend.fixture, snapshot, backend.mapping, backend.scope, 'before').passed)
        snapshot['tables']['timesheets'][0]['minutes'] += 1
        self.assertFalse(check_seed(backend.fixture, snapshot, backend.mapping, backend.scope, 'before').passed)

    def test_wrong_stage_generation_and_missing_snapshot(self):
        backend = FakeBackend()
        for field, value in [('stage', 'diagnostic'), ('settlement_generation', 1), ('run_id', 'WRONG')]:
            snapshot = backend.snapshot(backend.scope, backend.mapping['schema_name'], 'before')
            snapshot['tables'] = deepcopy(backend.fixture['seed'])
            snapshot[field] = value
            self.assertFalse(check_seed(backend.fixture, snapshot, backend.mapping, backend.scope, 'before').passed)
        self.assertFalse(check_seed(backend.fixture, None, backend.mapping, backend.scope, 'before').passed)
