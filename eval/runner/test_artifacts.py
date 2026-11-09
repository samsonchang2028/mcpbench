"""Local artifact and deadline adversaries; no application services."""
from datetime import datetime, timezone
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
        from unittest.mock import Mock
        module.PostgresBackend = Mock()
        module.PostgresBackend.from_private_config.return_value = b
        with patch.dict('sys.modules', {'db.lifecycle': module}):
            self.assertEqual(main(['prepare'], root=self.files.root, control=control), 0)
        module.PostgresBackend.from_private_config.assert_called_once_with(CONTROL / 'database.json')
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


if __name__ == '__main__':
    unittest.main()
