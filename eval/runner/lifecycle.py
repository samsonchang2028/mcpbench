"""Private fixed-phase evaluator. The trusted launcher owns all child execution."""
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import math
import secrets
import time
from typing import Protocol

from contracts.validate import (
    CATALOG, ContractError, canonical_bytes, canonical_hash, payload_hash, validate,
    validate_event_stream, validate_task_fixture,
)
from eval.fixtures.validate import ASSERTIONS
from eval.grading import RunScope, grade_state, grade_answer, grade_read_trace, grade_replay
from eval.grading.oracle import arguments, bind_snapshot, fingerprint, registration, require
from eval.reset import check_seed, reset_and_check
from observability.jsonl import redact


class LifecycleBackend(Protocol):
    """Trusted dedicated DB adapter. Each call has positive ACK or fails closed.

    set_timeout applies local statement/lock/connection deadlines to subsequent
    operation, including every transaction and positive COMMIT acknowledgment.
    capture returns snapshot AND registry from one read-only grader transaction.
    seal holds registry-exclusive lock until capability revocation commits;
    service shared locks must span the whole application transaction.
    """
    def set_timeout(self, timeout_ms: int) -> None: ...
    def prepare(self, mapping: dict) -> bool: ...
    def read_mapping(self, scope: RunScope) -> dict: ...
    def reset_seed(self, scope: RunScope, schema: str, fixture: dict) -> bool: ...
    def snapshot(self, scope: RunScope, schema: str, stage: str) -> dict: ...
    def capture(self, scope: RunScope, stage: str) -> tuple[dict, dict]: ...
    def activate(self, scope: RunScope, mode: str, token_sha256: str,
                 verification_request: dict | None) -> bool: ...
    def seal(self, scope: RunScope, fence: str) -> dict: ...
    def mark_cleaned(self, scope: RunScope) -> bool: ...


class Budget:
    """Continue launcher elapsed observations; never restart a post-agent anchor."""
    def __init__(self, value, *, monotonic=time.monotonic, wall_clock=lambda: datetime.now(timezone.utc)):
        validate('PostAgentBudget', value)
        self.base = deepcopy(value)
        self.mono, self.wall = monotonic, wall_clock
        self.observed_at = monotonic()
        self.elapsed = value['elapsed_ms']
        self.deadline = datetime.fromisoformat(value['deadline_at'].replace('Z', '+00:00'))

    def observation(self):
        now = self.mono()
        # The absolute deadline conservatively charges startup/transport and
        # forward UTC changes. Continue every such floor with this process's
        # monotonic deltas, so a later backward UTC change cannot restore time.
        # This is safety-budget accounting, not cross-producer latency.
        self.elapsed = max(self.elapsed + max(0, (now - self.observed_at) * 1000),
                           30000 - (self.deadline - self.wall()).total_seconds() * 1000)
        self.observed_at = now
        elapsed = math.ceil(self.elapsed)
        remaining = max(0, 30000 - elapsed)
        return {**self.base, 'elapsed_ms': elapsed, 'remaining_ms': remaining,
                'operation_timeout_ms': min(5000, remaining)}

    def check(self):
        value = self.observation()
        require(value['remaining_ms'] > 0, 'post_agent_expired')
        return value['operation_timeout_ms']

    def matches(self, value, *, floor=None):
        validate('PostAgentBudget', value)
        require(all(value[k] == self.base[k] for k in ('anchor_id', 'started_at', 'deadline_at')), 'budget_anchor')
        require(value['elapsed_ms'] >= (self.base['elapsed_ms'] if floor is None else floor), 'budget_regression')
        require(value['elapsed_ms'] <= self.observation()['elapsed_ms'], 'budget_future')


class BoundedBackend:
    """Apply a fresh remaining deadline separately to each reset backend call."""
    def __init__(self, evaluator):
        self.e = evaluator

    def read_mapping(self, *args):
        return self.e.operation('read_mapping', *args)

    def reset_seed(self, *args):
        return self.e.operation('reset_seed', *args)

    def snapshot(self, *args):
        return self.e.operation('snapshot', *args)


def failure(stage, code):
    return dict(stage=stage, code=code, call_id=None, reason=code,
                attribution='observed', disposition='terminal')


def assertion(name, passed, reason='verified'):
    return {'name': name, 'pass': passed, 'reason': reason}


class Evaluator:
    def __init__(self, artifacts, backend: LifecycleBackend, *, monotonic=time.monotonic,
                 wall_clock=lambda: datetime.now(timezone.utc)):
        self.files, self.backend = artifacts, backend
        self.files.secrets += tuple(getattr(backend, 'known_secrets', ()))
        self.mono, self.wall = monotonic, wall_clock
        self.budget = None
        self.state = None
        self.events = []

    def operation(self, name, *args):
        timeout = self.budget.check() if self.budget else 5000
        start = self.mono()
        try:
            self.backend.set_timeout(timeout)
            value = getattr(self.backend, name)(*args)
        except Exception:
            raise ContractError('backend_operation_failed') from None
        require((self.mono() - start) * 1000 <= timeout, 'operation_deadline')
        if self.budget:
            self.budget.check()
        return deepcopy(value)

    def identity(self, value):
        require(all(value[key] == self.request[key] for key in
                    ('run_id', 'attempt_id', 'task_id', 'task_hash', 'config_hash')), 'control_identity')

    def event(self, kind, phase, data):
        rows = self.state.setdefault('events', [])
        if not hasattr(self, '_event_offset'):
            self._event_offset = rows[-1]['elapsed_ms'] if rows else 0
        row = dict(schema_version=1, run_id=self.scope.run_id, attempt_id=self.scope.attempt_id,
                   event_id=f'evaluator-{len(rows) + 1}', sequence=len(rows) + 1, source='evaluator',
                   timestamp=self.wall().isoformat().replace('+00:00', 'Z'), event_type=kind,
                   phase=phase, status='ok', elapsed_ms=self._event_offset + math.ceil(max(0, (self.mono() - self.invoked_at) * 1000)), data=data)
        row = redact(row, self.files.secrets)
        validate('Event', row)
        # Each record is durable immediately; one source sequence spans processes.
        self.files.write_bytes(f'events/evaluator-{len(rows) + 1}.jsonl', canonical_bytes(row) + b'\n')
        rows.append(row)
        self.events.append(row)

    def invoke(self, request):
        """Return and persist one frozen ControlResult; never execute a child."""
        validate('ControlRequest', request)
        self.request = deepcopy(request)
        self.invoked_at = self.mono()
        phase = request['phase']
        # Exclusive invocation marker means replay/restart cannot grant a new budget.
        self.files.write(f'private/{phase}-invoked.json', {'message_id': request['message_id']}, private=True)
        receipt, outputs, original = None, {}, None
        try:
            if phase == 'prepare':
                return self.prepare()
            prior = self.files.read(request['inputs']['prior_phase_result'], 'ControlResult')
            self.identity(prior)
            require(prior['message_id'] == request['prior_result_id'], 'prior_result_id')
            expected = 'prepare' if phase == 'settle-grade' else 'settle-grade'
            require(prior['phase'] == expected and prior['action'] in
                    ({'execute_agent'} if phase == 'settle-grade' else {'verify', 'finalize'}), 'prior_phase')
            self.state = self.files.load(f'private/{expected}-state.json')
            require(self.state['result_ref'] == request['inputs']['prior_phase_result'], 'prior_artifact')
            self.task, self.fixture, self.config = (self.state[k] for k in ('task', 'fixture', 'config'))
            for mode in ('agent', 'verify'):
                auth_path = f'private/{mode}-auth.json'
                if (self.files.root / auth_path).exists():
                    auth = self.files.load(auth_path, 'AuthInput')
                    self.files.secrets += (auth['capability'], hashlib.sha256(auth['capability'].encode()).hexdigest())
            self.scope = RunScope(request['run_id'], request['attempt_id'], self.config['idempotency_key'])
            self.budget = Budget(request['budget'], monotonic=self.mono, wall_clock=self.wall)
            if prior['budget'] is not None:
                self.budget.matches(prior['budget'], floor=0)
            self.budget.check()
            return self.settle_grade(prior) if phase == 'settle-grade' else self.finalize(prior)
        except Exception:
            # Fixed category only; never persist arbitrary adapter/driver exception text.
            code = 'prepare_failed' if phase == 'prepare' else 'settlement_unknown'
            if self.state:
                original = self.state.get('original_pass')
                receipt = self.state.get('receipt')
            self.files.write(f'private/{phase}-quarantine.json', {'reason': code}, private=True)
            if phase != 'prepare' and self.state and hasattr(self, 'fixture'):
                self.state.setdefault('failures', []).append(failure('operations', code))
                settled = True if self.state.get('snapshot') else None
                summary = self.evaluation(bool(original), settled, None, None, None, None,
                                          False, False, True, self.state.get('verifier_calls', 0), [])
                self.files.write(f'evidence/{phase}-quarantine-evaluation.json', summary, contract='EvaluationResult')
            return self.result('quarantine', original=original, receipt=receipt,
                               terminal=failure('prepare' if phase == 'prepare' else 'operations', code))

    def result(self, action, *, original=None, receipt=None, outputs=None, terminal=None, skip=None):
        req = self.request
        row = {k: deepcopy(req[k]) for k in ('schema_version', 'run_id', 'attempt_id', 'task_id',
                                             'task_hash', 'config_hash', 'workflow_kind', 'phase')}
        row.update(budget=self.budget.observation() if self.budget else req['budget'],
                   status='failed' if action in {'quarantine', 'blocked'} else 'completed',
                   action=action, original_pass=original, fence_receipt=receipt, outputs=outputs or {},
                   message_id='result-' + hashlib.sha256(req['message_id'].encode()).hexdigest()[:32], request_id=req['message_id'],
                   failure=terminal, verifier_skip_reason=skip)
        validate('ControlResult', row)
        ref = self.files.write(f'control/{req["phase"]}-result.json', row, contract='ControlResult')
        if self.state is not None:
            self.state['result_ref'] = ref
            self.files.write(f'private/{req["phase"]}-state.json', self.state, private=True)
        return row

    def prepare(self):
        req = self.request
        self.task = self.files.read(req['inputs']['task'], 'Task')
        self.fixture = self.files.read(req['inputs']['fixture'], 'Fixture')
        self.config = self.files.read(req['inputs']['config'])
        require(set(self.config) == {'mapping', 'idempotency_key', 'model', 'trace_paths'}, 'config_fields')
        validate_task_fixture(self.task, self.fixture)
        require(canonical_hash(self.task) == req['task_hash'] and canonical_hash(self.config) == req['config_hash'], 'input_hash')
        require(self.task['task_id'] == req['task_id'] and self.task['expected_state']['kind'] == req['workflow_kind'], 'task_binding')
        self.scope = RunScope(req['run_id'], req['attempt_id'], self.config['idempotency_key'])
        mapping = self.config['mapping']
        registration(mapping, self.scope, self.fixture, self.task)
        require(mapping['phase'] == 'prepared' and mapping['generation'] == 0, 'prepare_phase')
        self.state = {'task': self.task, 'fixture': self.fixture, 'config': self.config, 'events': []}
        require(self.operation('prepare', mapping) is True, 'prepare_ack')
        reset = reset_and_check(BoundedBackend(self), self.scope, self.fixture)
        if not reset.passed:
            return self.result('blocked', terminal=failure('prepare', 'reset_failed'))
        snapshot, current = self.operation('capture', self.scope, 'before')
        require(check_seed(self.fixture, snapshot, current, self.scope, 'before').passed, 'before_seed')
        self.files.write('evidence/before.json', snapshot, contract='Snapshot')
        agent = dict(schema_version=1, run_id=self.scope.run_id, attempt_id=self.scope.attempt_id,
                     task_id=self.task['task_id'], prompt=self.task['prompt'], strategy='full_context',
                     catalog_id='billing-baseline', catalog_hash=canonical_hash(CATALOG),
                     principal_id=self.task['principal_id'], model=self.config['model'], budgets=self.task['budgets'])
        ref = self.files.write('agent/request.json', agent, contract='AgentRequest')
        self.mint('agent', None)
        return self.result('execute_agent', outputs={'agent_request': ref})

    def mint(self, mode, verification):
        capability = secrets.token_hex(32)
        self.files.secrets += (capability, hashlib.sha256(capability.encode()).hexdigest())
        auth = dict(schema_version=1, run_id=self.scope.run_id, attempt_id=self.scope.attempt_id,
                    mode=mode, capability=capability, idempotency_key=self.scope.idempotency_key)
        self.files.write(f'private/{mode}-auth.json', auth, contract='AuthInput', private=True)
        require(self.operation('activate', self.scope, mode, hashlib.sha256(capability.encode()).hexdigest(), verification) is True, 'activation_ack')

    def child(self, kind):
        inputs = self.request['inputs']
        record = self.files.read(inputs[f'{kind}_exit'], 'ProcessExit')
        self.identity(record)
        require(record['child'] == kind, 'child_kind')
        require(record['reaped'], 'unreaped_child')
        result = None
        if record['result_delivery'] == 'complete':
            require(inputs.get(f'{kind}_result') == record['result_ref'], 'child_reference')
            result = self.files.read(record['result_ref'], 'AgentResult' if kind == 'agent' else 'VerifierResult')
            require((result['run_id'], result['attempt_id']) == (self.scope.run_id, self.scope.attempt_id), 'child_scope')
        else:
            require(f'{kind}_result' not in inputs, 'unexpected_child_result')
        success = (record['termination'] == 'exited' and record['exit_code'] == 0 and
                   record['signal'] is None and record['result_delivery'] == 'complete')
        if kind == 'verifier':
            self.budget.matches(record['budget'], floor=self.state['verification']['budget']['elapsed_ms'])
            if result:
                self.identity(result)
                self.budget.matches(result['budget'], floor=self.state['verification']['budget']['elapsed_ms'])
            require(success and result is not None and result['status'] == 'completed', 'verifier_exit')
        return record, result, success

    def seal(self, kind):
        receipt = self.operation('seal', self.scope, kind)
        validate('FenceReceipt', receipt)
        require((receipt['run_id'], receipt['attempt_id'], receipt['fence'], receipt['status']) ==
                (self.scope.run_id, self.scope.attempt_id, kind, 'settled'), 'unknown_seal')
        self.event('fence.completed', 'grading' if kind == 'agent' else 'verification', {'receipt': receipt})
        return receipt

    def traces(self):
        events = []
        paths = self.config['trace_paths']
        require(type(paths) is list and 1 <= len(paths) <= 3 and len(set(paths)) == len(paths), 'trace_paths')
        for path in paths:
            events.extend(self.files.read_jsonl(path))
        validate_event_stream(events)
        require(events and all((v['run_id'], v['attempt_id']) == (self.scope.run_id, self.scope.attempt_id) for v in events), 'trace_scope')
        require(not any(v['source'] == 'evaluator' for v in events), 'trace_authority')
        return events

    def settle_grade(self, prior):
        record, agent, process_ok = self.child('agent')
        self.state.update(exit=record, agent=agent)
        receipt = self.seal('agent')
        snapshot, mapping = self.operation('capture', self.scope, 'agent_only')
        registration(mapping, self.scope, self.fixture, self.task)
        bind_snapshot(snapshot, mapping, receipt, self.scope, 'agent_only')
        ref = self.files.write('evidence/agent-snapshot.json', snapshot, contract='Snapshot')
        db = grade_state(self.task, self.fixture, ASSERTIONS, snapshot, mapping, receipt, self.scope)
        answer = grade_answer(self.task, snapshot, agent, self.scope)
        events, trace_ok = [], True
        try:
            events = self.traces()
        except Exception:
            trace_ok = False
        budget_ok = record['duration_ms'] <= self.task['budgets']['task_timeout_ms']
        if agent:
            counts = agent['counts']
            budget_ok = budget_ok and all(counts[key] <= self.task['budgets'][bound] for key, bound in
                                         (('model_calls', 'model_turns'), ('tool_calls', 'tool_calls'), ('retries', 'transient_retries')))
        read_ok = self.task['expected_state']['kind'] != 'read_only' or grade_read_trace(self.task, events, self.scope).passed
        unauthorized = sum(1 for e in events if e['source'] == 'mcp' and e['event_type'] == 'tool.completed' and
                           (e['phase'] != 'execution' or e['data']['tool_id'] not in self.task['permitted_tools']))
        failures = [deepcopy(e['data']['failure']) for e in events if e['data'].get('failure') is not None]
        if not agent:
            failures.append(failure('agent', 'no_result'))
        if not process_ok or not agent or agent['status'] != 'completed':
            failures.append(failure('agent', 'no_result'))
        if not budget_ok:
            failures.append(failure('agent', 'budget_exhausted'))
        if not db.passed:
            failures.append(failure('grading', 'state_incorrect'))
        if not answer.passed:
            failures.append(failure('grading', 'answer_invalid'))
        if not read_ok:
            failures.append(failure('grading', 'state_incorrect'))
        if unauthorized:
            failures.append(failure('execution', 'unauthorized_execution'))
        original = bool(db.passed and answer.passed and read_ok and process_ok and budget_ok and agent and
                        agent['status'] == 'completed' and not unauthorized and
                        not any(f['disposition'] == 'terminal' and f['stage'] in
                                {'admission', 'prepare', 'retrieval', 'agent', 'execution', 'grading'} for f in failures))
        self.state.update(original_pass=original, receipt=receipt, snapshot=snapshot, mapping=mapping,
                          db_pass=db.passed, answer_pass=answer.passed, budget_pass=budget_ok,
                          agent=agent, exit=record, failures=failures, trace_ok=trace_ok,
                          unauthorized=unauthorized)
        self.files.write('evidence/original.json', {k: self.state[k] for k in
                         ('original_pass', 'db_pass', 'answer_pass', 'budget_pass', 'failures', 'trace_ok')})
        self.event('grading.completed', 'grading', {'workflow_kind': self.request['workflow_kind'], 'task_success': original, 'original_assertions':
                   [assertion('db-oracle', db.passed), assertion('answer', answer.passed)], 'verification_assertions': []})
        if unauthorized:
            return self.result('quarantine', original=original, receipt=receipt,
                               terminal=failure('execution', 'unauthorized_execution'))
        if original and self.task['expected_state']['kind'] == 'draft_invoice':
            args = arguments(self.task['expected_state'])
            conflict = deepcopy(args)
            q = conflict['lines'][0]['quantity']
            conflict['lines'][0]['quantity'] += 1 if q < 1000 else -1
            verification = dict(schema_version=1, run_id=self.scope.run_id, attempt_id=self.scope.attempt_id,
                                task_id=self.task['task_id'], task_hash=self.request['task_hash'],
                                config_hash=self.request['config_hash'], budget=self.budget.observation(),
                                invoice_id=snapshot['tables']['invoices'][0]['invoice_id'],
                                idempotency_key=self.scope.idempotency_key, original_arguments=args,
                                original_request_hash=payload_hash(args), conflict_arguments=conflict,
                                checks=['same_payload_replay', 'changed_payload_conflict'])
            vref = self.files.write('verifier/request.json', verification, contract='VerificationRequest')
            self.state['verification'] = verification
            self.mint('verify', verification)
            return self.result('verify', original=True, receipt=receipt,
                               outputs={'agent_snapshot': ref, 'verification_request': vref})
        skip = 'read_only' if self.task['expected_state']['kind'] == 'read_only' else 'original_failed'
        return self.result('finalize', original=original, receipt=receipt,
                           outputs={'agent_snapshot': ref}, skip=skip)

    def finalize(self, prior):
        original = self.state['original_pass']
        require(original is prior['original_pass'], 'original_changed')
        verification = prior['action'] == 'verify'
        result, replay, verifier_settled, calls = None, None, None, 0
        receipt = self.state['receipt']
        if verification:
            _, result, _ = self.child('verifier')
            calls = result['calls']
            self.state['verifier_calls'] = calls
            receipt = self.seal('verifier')
            verifier_settled = True
        else:
            require(not {'verifier_exit', 'verifier_result'} & self.request['inputs'].keys(), 'unissued_verifier')
        snapshot, mapping = self.operation('capture', self.scope, 'final' if verification else 'agent_only')
        registration(mapping, self.scope, self.fixture, self.task)
        bind_snapshot(snapshot, mapping, receipt, self.scope, 'final' if verification else 'agent_only')
        unchanged = fingerprint(self.fixture, snapshot['tables']) == fingerprint(self.fixture, self.state['snapshot']['tables'])
        ref = self.files.write('evidence/final-snapshot.json', snapshot, contract='Snapshot')
        verification_assertions = [assertion('unchanged-state', unchanged)]
        if verification:
            replay = grade_replay(self.task, self.fixture, ASSERTIONS, self.state['snapshot'],
                                  self.state['mapping'], self.state['receipt'], snapshot, mapping,
                                  receipt, self.state['verification'], result, self.scope,
                                  self.request['config_hash']).passed
            verification_assertions = [assertion('same-payload-replay', replay),
                                       assertion('changed-payload-conflict', replay), *verification_assertions]
            if not replay:
                self.state['failures'].append(failure('verification', 'verification_failed'))
        if not unchanged:
            self.state['failures'].append(failure('verification', 'unexpected_write'))
        artifact_complete = self.state['trace_ok']
        if not artifact_complete:
            self.state['failures'].append(failure('operations', 'artifact_incomplete'))
        # Preserve settled state, original and verification before any reset.
        self.files.write('evidence/verification.json', {'assertions': verification_assertions,
                         'replay_pass': replay, 'verifier_settlement_pass': verifier_settled})
        self.files.manifest('evidence/pre-cleanup-manifest.json')
        self.budget.check()
        cleanup = reset_and_check(BoundedBackend(self), self.scope, self.fixture,
                                  receipt=receipt, evidence_persisted=True)
        cleaned = cleanup.passed
        self.files.write('evidence/reset-check.json', {
            'pass': cleaned, 'seed_hash': self.fixture['seed_hash'] if cleaned else None})
        if cleaned:
            cleaned = self.operation('mark_cleaned', self.scope) is True
        if not cleaned:
            self.state['failures'].append(failure('cleanup', 'cleanup_failed'))
        self.files.write('evidence/cleanup.json', {'pass': cleaned, 'seed_hash': self.fixture['seed_hash'] if cleaned else None})
        self.event('cleanup.completed', 'cleanup', {'pass': cleaned, 'seed_hash': self.fixture['seed_hash']})
        post = self.budget.observation()['elapsed_ms']
        terminal_safety = {'grader_error', 'settlement_unknown', 'verification_failed', 'cleanup_failed',
                           'resource_abort', 'artifact_incomplete', 'unauthorized_execution', 'unexpected_write'}
        comparison = bool(cleaned and artifact_complete and unchanged and post < 30000 and
                          (not verification or replay) and not any(f['code'] in terminal_safety and
                           f['disposition'] == 'terminal' for f in self.state['failures']))
        evaluation = self.evaluation(original, True, verifier_settled, replay, cleaned, unchanged,
                                     artifact_complete, comparison, not cleaned, calls, verification_assertions)
        eref = self.files.write('evidence/evaluation.json', evaluation, contract='EvaluationResult')
        self.files.write('evidence/metrics-availability.json', {
            'cpu_ms': 'not_measured', 'lifecycle_latency_ms': 'launcher_measurement_unavailable',
            'cost_usd': 'no_declared_rate', 'energy_joules': 'not_metered',
            'retrieval_precision': 'not_derived', 'required_tool_recall': 'not_derived',
            'prompt_tokens': 'trace_aggregation_unavailable', 'output_tokens': 'trace_aggregation_unavailable'})
        # Final result publication is part of evidence; the final manifest is saved
        # after the result and excludes only its own bytes, avoiding self hashing.
        row = self.result('complete' if cleaned else 'quarantine', original=original, receipt=receipt,
                          outputs={'evaluation': eref, 'final_snapshot': ref},
                          skip=prior['verifier_skip_reason'] if cleaned else None,
                          terminal=None if cleaned else failure('cleanup', 'cleanup_failed'))
        self.files.manifest()
        return row

    def evaluation(self, original, settled, verifier_settled, replay, cleaned, unchanged,
                   artifacts, comparison, quarantine, calls, verification_assertions):
        agent = self.state.get('agent')
        record = self.state.get('exit')
        status = 'not_started' if not record else 'timeout' if record['termination'] == 'timed_out' else (
            'completed' if agent and agent['status'] == 'completed' and record['termination'] == 'exited' and
            record['exit_code'] == 0 else 'failed')
        skip = 'not_started' if not record else 'read_only' if self.request['workflow_kind'] == 'read_only' else 'original_failed'
        flags = dict(agent_settlement_pass=settled, verifier_settlement_pass=verifier_settled,
                     db_oracle_pass=self.state.get('db_pass') if settled else None,
                     answer_pass=self.state.get('answer_pass') if settled else None,
                     replay_pass=replay, cleanup_pass=cleaned, final_state_unchanged=unchanged)
        reasons = {}
        for key, value in flags.items():
            if value is None:
                reasons[key] = (skip if key in {'verifier_settlement_pass', 'replay_pass'} and
                                (not original or self.request['workflow_kind'] == 'read_only') else
                                'not_started' if not record else 'settlement_unknown')
        post = self.budget.observation()['elapsed_ms'] if self.budget else None
        metrics = dict(task_latency_ms=record['duration_ms'] if record else None,
                       lifecycle_latency_ms=None, post_agent_ms=post, cpu_ms=None,
                       prompt_tokens=None, output_tokens=None, known_prompt_tokens=0,
                       known_output_tokens=0, missing_token_components=2,
                       retrieval_precision=None, required_tool_recall=None,
                       unauthorized_executions=self.state.get('unauthorized', 0), verifier_calls=calls,
                       cost_usd=None, energy_joules=None, cost_basis=None, energy_basis=None)
        row = {k: self.request[k] for k in ('schema_version', 'run_id', 'attempt_id', 'task_id', 'task_hash', 'config_hash', 'workflow_kind')}
        row.update(fixture_hash=canonical_hash(self.fixture),
                   catalog_hash=canonical_hash(CATALOG),
                   setup_pass=True, agent_status=status, agent_budget_pass=self.state.get('budget_pass', False),
                   **flags, null_reasons=reasons, artifact_complete=artifacts, comparison_valid=comparison,
                   task_success=original, overall_status='passed' if original and comparison else
                   'blocked' if not record else 'failed', quarantined=quarantine,
                   failures=self.state.get('failures', []), original_assertions=[
                       assertion('db-oracle', flags['db_oracle_pass']), assertion('answer', flags['answer_pass'])],
                   verification_assertions=verification_assertions, metrics=metrics)
        validate('EvaluationResult', row)
        return row
