"""Scripted child/DB evidence only; never opens a DB or launches a child."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import tempfile
import unittest

from contracts.validate import canonical_hash, load_file, payload_hash, validate
from eval.grading.test_oracle import case, trace
from eval.runner import Artifacts, Budget, Evaluator

ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 11, 7, 23, 0, 1, tzinfo=timezone.utc)


def example(name):
    return load_file(ROOT / f'contracts/v1/{name}.example.json')


class ScriptedBackend:
    def __init__(self, name='smoke-invoice'):
        self.task, self.fixture, _, self.saved, self.mapping, self.receipt, self.scope = case(name)
        self.mapping.update(phase='prepared', generation=0, agent_token_sha256=None)
        self.seed = deepcopy(self.fixture['seed'])
        self.tables = deepcopy(self.seed)
        self.calls = []
        self.unknown = None
        self.reset_ok = True
        self.timeouts = []

    def set_timeout(self, timeout):
        self.timeouts.append(timeout)

    def prepare(self, mapping):
        self.calls.append('prepare')
        return mapping == self.mapping

    def read_mapping(self, scope):
        return deepcopy(self.mapping)

    def reset_seed(self, scope, schema, fixture):
        self.calls.append('reset')
        self.tables = deepcopy(self.seed)
        return self.reset_ok

    def snapshot(self, scope, schema, stage):
        return self.capture(scope, stage)[0]

    def capture(self, scope, stage):
        self.calls.append('capture-' + stage)
        snap = deepcopy(self.saved)
        snap.update(stage=stage, tables=deepcopy(self.tables), settlement_generation=self.mapping['generation'])
        return snap, deepcopy(self.mapping)

    def activate(self, scope, mode, digest, verification):
        self.calls.append('activate-' + mode)
        if mode == 'agent':
            self.mapping.update(phase='executing', agent_token_sha256=digest)
        else:
            self.mapping.update(phase='verifying', verifier_token_sha256=digest,
                                verifier_scope={k: verification[k] for k in ('invoice_id', 'original_request_hash')})
        return True

    def seal(self, scope, fence):
        self.calls.append('seal-' + fence)
        if self.unknown == fence:
            raise RuntimeError('password=never-persist-me')
        generation = 1 if fence == 'agent' else 2
        phase = 'agent_sealed' if fence == 'agent' else 'final_sealed'
        self.mapping.update(phase=phase, generation=generation, agent_token_sha256=None,
                            verifier_token_sha256=None, verifier_scope=None)
        return {**self.receipt, 'generation': generation, 'phase': phase, 'fence': fence}

    def mark_cleaned(self, scope):
        self.calls.append('cleaned')
        self.mapping['phase'] = 'cleaned'
        return True


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.chmod(self.tmp.name, 0o700)
        self.files = Artifacts(self.tmp.name)

    def evaluator(self, backend):
        return Evaluator(self.files, backend, monotonic=lambda: 0, wall_clock=lambda: NOW)

    def request(self, phase, backend, prior=None, inputs=None):
        config = dict(mapping=deepcopy(backend.mapping), idempotency_key=backend.scope.idempotency_key,
                      model=example('agent-request')['model'], trace_paths=['events/children.jsonl'])
        common = dict(schema_version=1, run_id=backend.scope.run_id, attempt_id=backend.scope.attempt_id,
                      task_id=backend.task['task_id'], task_hash=canonical_hash(backend.task),
                      config_hash=canonical_hash(config), workflow_kind=backend.task['expected_state']['kind'])
        if phase == 'prepare':
            inputs = {k: self.files.write(f'input/{k}.json', v, private=True) for k, v in
                      [('task', backend.task), ('fixture', backend.fixture), ('config', config)]}
        else:
            common['config_hash'] = prior['config_hash']
            inputs = {'prior_phase_result': self.files.reference(f'control/{prior["phase"]}-result.json'), **(inputs or {})}
        return dict(**common, phase=phase, budget=None if phase == 'prepare' else self.budget(),
                    message_id=phase + '-request', prior_result_id=prior['message_id'] if prior else None, inputs=inputs)

    def budget(self, elapsed=1100):
        return dict(anchor_id='post-example-001', started_at='2026-11-07T23:00:00Z',
                    deadline_at='2026-11-07T23:00:30Z', elapsed_ms=elapsed,
                    remaining_ms=30000-elapsed, operation_timeout_ms=min(5000, 30000-elapsed))

    def prepare(self, backend):
        return self.evaluator(backend).invoke(self.request('prepare', backend))

    def grade(self, backend, prior, *, bad_answer=False, timeout=False, unreaped=False):
        backend.tables = deepcopy(backend.saved['tables'])
        agent = example('agent-result')
        if backend.task['expected_state']['kind'] == 'read_only':
            agent['final_answer'] = {'text': 'Read records', 'invoice_id': None,
                                    'record_ids': backend.task['expected_state']['required_record_ids']}
        if bad_answer:
            agent['final_answer']['invoice_id'] = 'INV-WRONG'
        aref = self.files.write('agent/result.json', agent, contract='AgentResult')
        record = example('agent-exit')
        record.update(task_id=backend.task['task_id'], task_hash=prior['task_hash'], config_hash=prior['config_hash'],
                      result_ref=aref, duration_ms=300001 if timeout else 1000)
        if timeout:
            record['termination'] = 'timed_out'
        if unreaped:
            record.update(termination='terminated', reaped=False, exit_code=None, signal=None)
        eref = self.files.write('agent/exit.json', record, contract='ProcessExit')
        events = trace(backend.task, backend.scope) if backend.task['expected_state']['kind'] == 'read_only' else self.invoice_trace(backend)
        self.files.write_bytes('events/children.jsonl', b''.join(__import__('contracts.validate', fromlist=['canonical_bytes']).canonical_bytes(e)+b'\n' for e in events))
        return self.evaluator(backend).invoke(self.request('settle-grade', backend, prior,
                {'agent_exit': eref, 'agent_result': aref}))

    def invoice_trace(self, backend):
        events = trace(case('baseline-project')[0], backend.scope)
        events[0]['data'] = {'tool_id': 'billing_list_customers', 'arguments': {}, 'retry_index': 0}
        events[1]['data'] = {'tool_id': 'billing_list_customers', 'duration_ms': 1,
                             'tool_result': {'tool_id': 'billing_list_customers', 'is_error': False,
                                             'result': {'customers': backend.fixture['seed']['customers']}}}
        return events

    def finish(self, backend, prior, *, malformed_verifier=False):
        inputs = {}
        if prior['action'] == 'verify':
            v = example('verifier-result')
            v.update(task_id=backend.task['task_id'], task_hash=prior['task_hash'], config_hash=prior['config_hash'], budget=self.budget())
            vref = self.files.write('verifier/result.json', v, contract='VerifierResult')
            record = example('verifier-exit')
            record.update(task_id=backend.task['task_id'], task_hash=prior['task_hash'], config_hash=prior['config_hash'],
                          result_ref=vref, budget=self.budget())
            if malformed_verifier:
                record.update(result_delivery='malformed', result_ref=None)
            inputs['verifier_exit'] = self.files.write('verifier/exit.json', record, contract='ProcessExit')
            if not malformed_verifier:
                inputs['verifier_result'] = vref
        return self.evaluator(backend).invoke(self.request('finalize', backend, prior, inputs))

    def test_positive_fractional_clock_persists_events_and_phase_state(self):
        b = ScriptedBackend()
        p = self.prepare(b)
        ticks = iter(i / 1000000 for i in range(10000))
        self.evaluator = lambda backend: Evaluator(self.files, backend,
                monotonic=lambda: next(ticks), wall_clock=lambda: NOW)
        g = self.grade(b, p)
        self.assertEqual(g['action'], 'verify', g)
        state = self.files.load('private/settle-grade-state.json')
        self.assertTrue(state['events'])
        self.assertTrue(all(type(row['elapsed_ms']) is int for row in state['events']))
        self.assertGreater(state['events'][0]['elapsed_ms'], 0)
        self.files.load('evidence/agent-snapshot.json', 'Snapshot')
        self.assertEqual(len(self.files.read_jsonl('events/evaluator-1.jsonl')), 1)

    def test_event_publication_failure_does_not_contaminate_fallback_state(self):
        from unittest.mock import patch
        from eval.runner.artifacts import ArtifactError
        b = ScriptedBackend()
        p = self.prepare(b)
        write = self.files.write_bytes
        def fail_event(path, raw):
            if path.startswith('events/evaluator-'):
                raise ArtifactError('injected_event_write')
            return write(path, raw)
        with patch.object(self.files, 'write_bytes', side_effect=fail_event):
            g = self.grade(b, p)
        self.assertEqual(g['action'], 'quarantine', g)
        self.assertIn('seal-agent', b.calls)
        self.assertNotIn('capture-agent_only', b.calls)
        state = self.files.load('private/settle-grade-state.json')
        self.assertEqual(state['events'], [])
        self.assertFalse((self.files.root / 'events/evaluator-1.jsonl').exists())
        self.assertEqual(b.calls.count('reset'), 1)
        self.assertNotIn('cleaned', b.calls)

    def test_invoice_three_phases(self):
        b = ScriptedBackend()
        p = self.prepare(b)
        self.assertEqual(p['action'], 'execute_agent', p)
        g = self.grade(b, p)
        self.assertEqual(g['action'], 'verify', g)
        f = self.finish(b, g)
        self.assertEqual(f['action'], 'complete', f)
        result = self.files.read(f['outputs']['evaluation'], 'EvaluationResult')
        self.assertTrue(result['task_success'])
        self.assertTrue(result['replay_pass'])
        self.assertTrue(result['comparison_valid'])
        self.assertEqual(b.calls.count('reset'), 2)
        self.assertTrue(all(0 < t <= 5000 for t in b.timeouts))
        self.assertTrue((Path(self.tmp.name) / 'evidence/manifest.json').exists())

    def test_read_only_skips_verifier(self):
        b = ScriptedBackend('baseline-project')
        p = self.prepare(b)
        g = self.grade(b, p)
        self.assertEqual(g['action'], 'finalize', g)
        self.assertEqual(g['verifier_skip_reason'], 'read_only')
        f = self.finish(b, g)
        self.assertEqual(f['action'], 'complete', f)
        result = self.files.read(f['outputs']['evaluation'], 'EvaluationResult')
        self.assertTrue(result['task_success'])
        self.assertIsNone(result['replay_pass'])
        self.assertNotIn('activate-verify', b.calls)
        self.assertNotIn('seal-verifier', b.calls)

    def test_failed_original_not_repaired(self):
        b = ScriptedBackend()
        g = self.grade(b, self.prepare(b), bad_answer=True)
        self.assertEqual(g['action'], 'finalize', g)
        self.assertFalse(g['original_pass'])
        f = self.finish(b, g)
        self.assertEqual(f['action'], 'complete', f)
        result = self.files.read(f['outputs']['evaluation'], 'EvaluationResult')
        self.assertFalse(result['task_success'])
        self.assertTrue(result['comparison_valid'])
        self.assertNotIn('activate-verify', b.calls)

    def test_unknown_agent_fence_does_not_reset(self):
        b = ScriptedBackend()
        p = self.prepare(b)
        b.unknown = 'agent'
        g = self.grade(b, p)
        self.assertEqual(g['action'], 'quarantine', g)
        self.assertIsNone(g['original_pass'])
        self.assertEqual(b.calls.count('reset'), 1)
        self.assertNotIn('capture-agent_only', b.calls)
        for path in Path(self.tmp.name).rglob('*'):
            if path.is_file():
                self.assertNotIn(b'never-persist-me', path.read_bytes())

    def test_unreaped_child_does_not_seal_or_reset(self):
        b = ScriptedBackend()
        g = self.grade(b, self.prepare(b), unreaped=True)
        self.assertEqual(g['action'], 'quarantine')
        self.assertNotIn('seal-agent', b.calls)
        self.assertEqual(b.calls.count('reset'), 1)

    def test_timeout_is_original_failure_with_safe_cleanup(self):
        b = ScriptedBackend()
        g = self.grade(b, self.prepare(b), timeout=True)
        self.assertEqual(g['action'], 'finalize', g)
        f = self.finish(b, g)
        result = self.files.read(f['outputs']['evaluation'])
        self.assertFalse(result['task_success'])
        self.assertFalse(result['agent_budget_pass'])
        self.assertTrue(result['comparison_valid'])

    def test_malformed_verifier_quarantines_without_cleanup(self):
        b = ScriptedBackend()
        g = self.grade(b, self.prepare(b))
        f = self.finish(b, g, malformed_verifier=True)
        self.assertEqual(f['action'], 'quarantine', f)
        self.assertTrue(f['original_pass'])
        self.assertEqual(b.calls.count('reset'), 1)

    def test_failed_initial_reset_blocks_agent(self):
        b = ScriptedBackend()
        b.reset_ok = False
        p = self.prepare(b)
        self.assertEqual(p['action'], 'blocked', p)
        self.assertNotIn('activate-agent', b.calls)


if __name__ == '__main__':
    unittest.main()
