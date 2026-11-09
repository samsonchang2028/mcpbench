"""Local artifact and deadline adversaries; no application services."""
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from contracts.validate import ContractError
from eval.runner import Artifacts, Budget
from eval.runner.__main__ import CONTROL, main, read_request
from eval.runner.test_lifecycle import LifecycleTests, ScriptedBackend
from eval.runner.lifecycle import BoundedBackend
from eval.reset import reset_and_check


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.files = Artifacts(self.root)

    def test_exclusive_atomic_publish_and_hash(self):
        ref = self.files.write('control/result.json', {'status': 'saved'})
        with self.assertRaises(ValueError):
            self.files.write('control/result.json', {'status': 'overwritten'})
        self.assertEqual(self.files.read(ref), {'status': 'saved'})
        (self.root / ref['path']).write_bytes(b'{}\n')
        with self.assertRaises(ValueError):
            self.files.read(ref)
        self.assertFalse(list(self.root.rglob('.publish-*')))

    def test_no_symlink_or_path_escape(self):
        (self.root / 'link').symlink_to(self.root, target_is_directory=True)
        for path in ('link/result.json', '../escape.json', '/absolute/result.json', 'control/../bad.json'):
            with self.subTest(path=path), self.assertRaises((ValueError, OSError)):
                self.files.write(path, {'x': 1})

    def test_reject_symlink_ancestor(self):
        other = self.root / 'real'
        other.mkdir(mode=0o700)
        (self.root / 'alias').symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError):
            Artifacts(self.root / 'alias')

    def test_caps_and_secrets(self):
        self.files.secrets = ('unique-private-literal',)
        ref = self.files.write('evidence/reason.json', {'reason': 'contains unique-private-literal'})
        self.assertNotIn('unique-private-literal', self.files.read(ref)['reason'])
        with self.assertRaises(ValueError):
            self.files.write('evidence/large.json', {'x': 'x' * 1024**2})
        limited = Artifacts(self.root, max_bytes=self.files.size()+1)
        with self.assertRaises(ValueError):
            limited.write('evidence/second.json', {'x': 1})

    def test_mode_and_symlink_transport(self):
        path = self.root / 'request.json'
        path.write_text('{}')
        os.chmod(path, 0o644)
        with self.assertRaises(ValueError):
            read_request(self.root)
        path.unlink()
        path.symlink_to('/dev/null')
        with self.assertRaises(OSError):
            read_request(self.root)

    def test_fixed_cli_rejects_arbitrary_command(self):
        self.assertEqual(main(['shell', 'anything'], root=self.root), 2)

    def test_transport_size_and_nonregular_files_are_rejected(self):
        path = self.root / 'request.json'
        path.write_bytes(b' ' * (1024**2 + 1))
        os.chmod(path, 0o600)
        with self.assertRaises(ValueError):
            read_request(self.root)
        path.unlink()
        os.mkfifo(path, 0o600)
        with self.assertRaises(ValueError):
            read_request(self.root)

    def test_nonregular_artifact_never_blocks_waiting_for_writer(self):
        directory = self.root / 'input'
        directory.mkdir(mode=0o700)
        os.mkfifo(directory / 'task.json', 0o600)
        with self.assertRaises(ValueError):
            self.files.reference('input/task.json')


class DeadlineTests(unittest.TestCase):
    def test_normal_budget_preserves_anchor_and_operation_cap(self):
        current = [900000.0]
        supplied = LifecycleTests().budget()
        budget = Budget(supplied, monotonic=lambda: current[0],
                        wall_clock=lambda: datetime(2026, 11, 7, 23, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(budget.check(), 5000)
        self.assertEqual(budget.observation(), supplied)
        current[0] += 0.125
        observed = budget.observation()
        self.assertEqual(observed['elapsed_ms'], 1225)
        self.assertEqual(observed['remaining_ms'], 28775)
        for key in ('anchor_id', 'started_at', 'deadline_at'):
            self.assertEqual(observed[key], supplied[key])

    def test_budget_does_not_restart_and_preserves_overrun(self):
        current = [0.0]
        budget = Budget(LifecycleTests().budget(29900), monotonic=lambda: current[0],
                        wall_clock=lambda: datetime(2026, 11, 7, 23, 0, 1, tzinfo=timezone.utc))
        self.assertEqual(budget.check(), 100)
        current[0] = 0.25
        self.assertEqual(budget.observation()['elapsed_ms'], 30150)
        with self.assertRaises(ContractError):
            budget.check()

    def test_expired_absolute_deadline_cannot_be_restarted(self):
        budget = Budget(LifecycleTests().budget(), monotonic=lambda: 0,
                        wall_clock=lambda: datetime(2026, 11, 7, 23, 1, tzinfo=timezone.utc))
        with self.assertRaises(ContractError):
            budget.check()

    def test_stale_observation_is_capped_before_absolute_expiry(self):
        budget = Budget(LifecycleTests().budget(0), monotonic=lambda: 900000,
                        wall_clock=lambda: datetime(2026, 11, 7, 23, 0, 29, tzinfo=timezone.utc))
        self.assertEqual(budget.check(), 1000)
        observation = budget.observation()
        self.assertEqual(observation['elapsed_ms'], 29000)
        self.assertEqual(observation['remaining_ms'], 1000)
        from contracts.validate import validate
        validate('PostAgentBudget', observation)

    def test_wall_clock_changes_cannot_extend_monotonic_budget(self):
        current, wall = [0.0], [datetime(2026, 11, 7, 23, 0, 29, tzinfo=timezone.utc)]
        budget = Budget(LifecycleTests().budget(0), monotonic=lambda: current[0], wall_clock=lambda: wall[0])
        self.assertEqual(budget.check(), 1000)
        current[0], wall[0] = 0.25, wall[0] - timedelta(seconds=10)
        self.assertEqual(budget.check(), 750)
        wall[0] = datetime(2026, 11, 7, 23, 0, 29, 500000, tzinfo=timezone.utc)
        self.assertEqual(budget.check(), 500)
        current[0], wall[0] = 0.5, wall[0] - timedelta(seconds=20)
        self.assertEqual(budget.check(), 250)
        current[0] = 0.8
        with self.assertRaises(ContractError):
            budget.check()
        self.assertEqual(budget.observation()['elapsed_ms'], 30050)


class LifecycleAdversaries(LifecycleTests):
    # Inherited base cases also run against exactly the same public lifecycle API.
    def test_repeated_phase_refuses_reuse(self):
        b = ScriptedBackend()
        request = self.request('prepare', b)
        self.evaluator(b).invoke(request)
        with self.assertRaises(ValueError):
            self.evaluator(b).invoke(request)
        self.assertEqual(b.calls.count('prepare'), 1)

    def test_unknown_verifier_fence_preserves_original_and_no_reset(self):
        b = ScriptedBackend()
        grade = self.grade(b, self.prepare(b))
        b.unknown = 'verifier'
        final = self.finish(b, grade)
        self.assertEqual(final['action'], 'quarantine')
        self.assertTrue(final['original_pass'])
        summary = self.files.load('evidence/finalize-quarantine-evaluation.json', 'EvaluationResult')
        self.assertTrue(summary['task_success'])
        self.assertIsNone(summary['verifier_settlement_pass'])
        self.assertFalse(summary['comparison_valid'])
        self.assertEqual(b.calls.count('reset'), 1)

    def test_cleanup_failure_does_not_reuse(self):
        b = ScriptedBackend()
        grade = self.grade(b, self.prepare(b))
        b.reset_ok = False
        final = self.finish(b, grade)
        self.assertEqual(final['action'], 'quarantine', final)
        summary = self.files.read(final['outputs']['evaluation'], 'EvaluationResult')
        self.assertTrue(summary['task_success'])
        self.assertFalse(summary['cleanup_pass'])
        self.assertFalse(summary['comparison_valid'])
        self.assertNotIn('cleaned', b.calls)

    def test_stale_prior_hash_quarantines_before_seal(self):
        b = ScriptedBackend()
        prepare = self.prepare(b)
        path = self.files.root / 'control/prepare-result.json'
        path.write_bytes(path.read_bytes()+b' ')
        grade = self.grade(b, prepare)
        # Request helper captures the altered hash, but private phase state binds
        # the original reference and prevents substitution of otherwise valid JSON.
        self.assertEqual(grade['action'], 'quarantine')
        self.assertNotIn('seal-agent', b.calls)

    def test_cli_runs_fixed_phase_with_injected_backend(self):
        b = ScriptedBackend()
        request = self.request('prepare', b)
        control = self.files.root / 'transport'
        control.mkdir(mode=0o700)
        from contracts.validate import canonical_bytes
        (control / 'request.json').write_bytes(canonical_bytes(request))
        os.chmod(control / 'request.json', 0o600)
        self.assertEqual(main(['prepare'], backend=b, root=self.files.root, control=control), 0)
        self.assertEqual(self.files.load('control/prepare-result.json')['action'], 'execute_agent')

    def test_cli_loads_fixed_backend_without_injection(self):
        b = ScriptedBackend()
        request = self.request('prepare', b)
        control = self.files.root / 'transport'
        control.mkdir(mode=0o700)
        from contracts.validate import canonical_bytes
        (control / 'request.json').write_bytes(canonical_bytes(request))
        os.chmod(control / 'request.json', 0o600)
        module = ModuleType('db.lifecycle')
        calls = []

        class StrictBackendFactory:
            @staticmethod
            def from_private_config(path):
                # Match the real T018 factory's exact-type and fixed-path guard.
                if type(path) is not str or path != '/run/mcpbench/control/database.json':
                    raise ValueError('private_config_path')
                calls.append(path)
                return b

        module.PostgresBackend = StrictBackendFactory
        with patch.dict('sys.modules', {'db.lifecycle': module}):
            self.assertEqual(main(['prepare'], root=self.files.root, control=control), 0)
        self.assertEqual(calls, [str(CONTROL / 'database.json')])
        self.assertEqual(self.files.load('control/prepare-result.json')['action'], 'execute_agent')

    def test_missing_trace_preserves_original_but_invalidates_comparison(self):
        b = ScriptedBackend()
        prior = self.prepare(b)
        events = self.invoice_trace(b)
        with patch.object(self, 'invoice_trace', return_value=events[:1]):
            grade = self.grade(b, prior)
        self.assertTrue(grade['original_pass'])
        final = self.finish(b, grade)
        summary = self.files.read(final['outputs']['evaluation'], 'EvaluationResult')
        self.assertTrue(summary['task_success'])
        self.assertFalse(summary['artifact_complete'])
        self.assertFalse(summary['comparison_valid'])
        self.assertIn('artifact_incomplete', [row['code'] for row in summary['failures']])

    def test_changed_final_state_cannot_change_original_verdict(self):
        b = ScriptedBackend()
        grade = self.grade(b, self.prepare(b))
        b.tables['customers'][0]['name'] = 'Unexpected synthetic customer mutation'
        final = self.finish(b, grade)
        summary = self.files.read(final['outputs']['evaluation'], 'EvaluationResult')
        self.assertTrue(summary['task_success'])
        self.assertFalse(summary['final_state_unchanged'])
        self.assertFalse(summary['comparison_valid'])
        self.assertIn('unexpected_write', [row['code'] for row in summary['failures']])

    def test_seed_check_is_durable_before_cleaned_transition(self):
        b = ScriptedBackend()
        grade = self.grade(b, self.prepare(b))
        transition = b.mark_cleaned

        def checked_transition(scope):
            proof = self.files.load('evidence/reset-check.json')
            self.assertEqual(proof, {'pass': True, 'seed_hash': b.fixture['seed_hash']})
            return transition(scope)

        with patch.object(b, 'mark_cleaned', side_effect=checked_transition):
            self.assertEqual(self.finish(b, grade)['action'], 'complete')

    def test_expiry_during_backend_operation_rejects_ack_and_next_operation(self):
        b = ScriptedBackend()
        wall = [datetime(2026, 11, 7, 23, 0, 29, tzinfo=timezone.utc)]
        e = self.evaluator(b)
        e.budget = Budget(self.budget(0), monotonic=lambda: 0, wall_clock=lambda: wall[0])
        read_mapping = b.read_mapping

        def expire(scope):
            wall[0] += timedelta(seconds=1)
            return read_mapping(scope)

        with patch.object(b, 'read_mapping', side_effect=expire):
            with self.assertRaises(ContractError):
                e.operation('read_mapping', b.scope)
        self.assertEqual(b.timeouts, [1000])
        with self.assertRaises(ContractError):
            e.operation('reset_seed', b.scope, b.mapping['schema_name'], b.fixture)
        self.assertNotIn('reset', b.calls)
        self.assertEqual(b.timeouts, [1000])

    def test_reset_backend_refreshes_absolute_bound_for_every_call(self):
        b = ScriptedBackend()
        current = [0.0]
        initial = datetime(2026, 11, 7, 23, 0, 29, tzinfo=timezone.utc)
        e = self.evaluator(b)
        e.mono = lambda: current[0]
        e.budget = Budget(self.budget(0), monotonic=e.mono,
                          wall_clock=lambda: initial + timedelta(seconds=current[0]))

        def advance(operation):
            def wrapped(*args):
                result = operation(*args)
                current[0] += 0.125
                return result
            return wrapped

        with patch.object(b, 'read_mapping', side_effect=advance(b.read_mapping)), \
             patch.object(b, 'reset_seed', side_effect=advance(b.reset_seed)), \
             patch.object(b, 'snapshot', side_effect=advance(b.snapshot)):
            result = reset_and_check(BoundedBackend(e), b.scope, b.fixture)
        self.assertTrue(result.passed)
        self.assertEqual(b.timeouts, [1000, 875, 750, 625])

    def test_expired_budget_blocks_reset_before_backend_io(self):
        b = ScriptedBackend()
        e = self.evaluator(b)
        e.budget = Budget(self.budget(0), monotonic=lambda: 0,
                          wall_clock=lambda: datetime(2026, 11, 7, 23, 0, 30, tzinfo=timezone.utc))
        result = reset_and_check(BoundedBackend(e), b.scope, b.fixture)
        self.assertFalse(result.passed)
        self.assertEqual(b.timeouts, [])
        self.assertEqual(b.calls, [])


if __name__ == '__main__':
    unittest.main()
