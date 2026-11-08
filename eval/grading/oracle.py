"""Independent deterministic state/answer/replay evidence; no lifecycle success claim."""
from dataclasses import dataclass
from datetime import datetime
from functools import wraps

from contracts.validate import (
    ContractError, TABLE_KEYS, canonical_bytes, canonical_hash, payload_hash,
    seed_hash, validate, validate_task_fixture, load_file,
)
from eval.fixtures.validate import ASSERTIONS, ROOT as FIXTURE_ROOT, validate_corpus


@dataclass(frozen=True)
class Evidence:
    passed: bool
    reason: str


@dataclass(frozen=True)
class RunScope:
    """Controller-owned identity, never inferred from a supplied snapshot."""
    run_id: str
    attempt_id: str
    idempotency_key: str


def require(ok, reason):
    if not ok:
        raise ContractError(reason)


def evidence(function):
    @wraps(function)
    def checked(*args, **kwargs):
        try:
            function(*args, **kwargs)
            return Evidence(True, 'verified')
        except (ContractError, KeyError, TypeError, ValueError, AttributeError, IndexError, OSError, RuntimeError):
            # Invalid evidence must fail without leaking raw data or exceptions.
            return Evidence(False, function.__name__ + '_failed')
    return checked


def identity(value, scope):
    for field in ('run_id', 'attempt_id', 'idempotency_key'):
        validate('Identifier', getattr(scope, field))
    require((value['run_id'], value['attempt_id']) == (scope.run_id, scope.attempt_id),
            'wrong trusted scope')


def registration(mapping, scope, fixture, task=None):
    validate('RunMapping', mapping)
    validate('Fixture', fixture)
    validate_corpus()
    require(canonical_hash(fixture) == canonical_hash(load_file(FIXTURE_ROOT / 'fixture.json')),
            'unregistered fixture')
    identity(mapping, scope)
    require(mapping['tenant_id'] == fixture['tenant_id'], 'wrong tenant')
    if task is not None:
        validate_task_fixture(task, fixture)
        require(task['task_id'] in {'smoke-invoice', 'baseline-invoice', 'baseline-project', 'baseline-time'},
                'unregistered task')
        require(canonical_hash(task) == canonical_hash(load_file(
            FIXTURE_ROOT / 'tasks' / (task['task_id'] + '.json'))), 'task differs from frozen corpus')
        require(mapping['principal_id'] == task['principal_id'] and
                set(mapping['allowed_tools']) == set(task['permitted_tools']) and
                mapping['workflow_kind'] == task['expected_state']['kind'], 'wrong permissions')


def bind_snapshot(snapshot, mapping, receipt, scope, stage):
    """Mapping and receipt must come from trusted read-only/control channels."""
    validate('Snapshot', snapshot)
    validate('FenceReceipt', receipt)
    identity(snapshot, scope)
    identity(receipt, scope)
    generation, phase, fence = {'agent_only': (1, 'agent_sealed', 'agent'),
                               'final': (2, 'final_sealed', 'verifier')}[stage]
    require((snapshot['stage'], snapshot['settlement_generation']) == (stage, generation),
            'wrong snapshot stage/generation')
    require((mapping['phase'], mapping['generation']) == (phase, generation), 'unsealed registry')
    require(receipt['status'] == 'settled' and receipt['fence'] == fence and
            receipt['generation'] == generation and receipt['phase'] == phase, 'unsettled receipt')
    require(datetime.fromisoformat(snapshot['captured_at']) >= datetime.fromisoformat(receipt['committed_at']), 'stale capture')


def fingerprint(fixture, tables):
    validate('Tables', tables)
    return seed_hash({**fixture, 'seed': tables})


def ordered(rows, table):
    return sorted(rows, key=lambda row: row[TABLE_KEYS[table]])


def arguments(expected):
    return {**{k: expected[k] for k in ('customer_id', 'invoice_date', 'due_date')},
            'lines': [{k: row[k] for k in ('item_id', 'quantity')} for row in expected['lines']]}


@evidence
def grade_state(task, fixture, assertions, snapshot, mapping, receipt, scope):
    """DB correctness only. Neither agent answer nor lifecycle outcome is consumed."""
    registration(mapping, scope, fixture, task)
    require(canonical_bytes(assertions) == canonical_bytes(ASSERTIONS), 'unsupported assertions')
    bind_snapshot(snapshot, mapping, receipt, scope, 'agent_only')
    expected, tables = task['expected_state'], snapshot['tables']
    if expected['kind'] == 'read_only':
        require(fingerprint(fixture, tables) == fixture['seed_hash'], 'read changed seed')
        return
    original = assertions['invoice']['original']
    for table in assertions['invoice']['unchanged_seed_tables']:
        require(ordered(tables[table], table) == ordered(fixture['seed'][table], table), 'seed mutation')
    # T009 declares empty write tables. Preserve seed rows even if later extended.
    additions = {}
    for table, count in [('invoices', original['invoice_count_delta']),
                         ('invoice_lines', original['invoice_line_count_delta']),
                         ('idempotency_records', original['idempotency_count_delta'])]:
        seed = fixture['seed'][table]
        key = TABLE_KEYS[table]
        old = {row[key]: row for row in seed}
        current = {row[key]: row for row in tables[table]}
        require(all(current.get(k) == row for k, row in old.items()), 'changed existing write row')
        additions[table] = [row for k, row in current.items() if k not in old]
        require(len(additions[table]) == count, 'extra or missing writes')
    invoice, line, ledger = (additions[t][0] for t in ('invoices', 'invoice_lines', 'idempotency_records'))
    for key in ('customer_id', 'invoice_date', 'due_date', 'currency',
                'subtotal_cents', 'tax_cents', 'total_cents'):
        require(invoice[key] == expected[key], 'invoice differs from literal')
    require(invoice['status'] == original['status'] and
            datetime.fromisoformat(invoice['created_at']) <= datetime.fromisoformat(snapshot['captured_at']), 'status or creation time')
    require(len(expected['lines']) == 1, 'unsupported fixture line count')
    require(all(line[k] == v for k, v in expected['lines'][0].items()), 'line differs from literal')
    require(line['line_number'] == original['line_number'] and
            line['line_total_cents'] == original['line_total_cents'], 'line number/total')
    require(line['invoice_id'] == ledger['invoice_id'] == invoice['invoice_id'], 'generated ID relationship')
    require(ledger['idempotency_key'] == scope.idempotency_key and
            ledger['request_hash'] == payload_hash(arguments(expected)), 'ledger binding')


@evidence
def grade_answer(task, snapshot, agent, scope):
    """Structured answer only; original state and lifecycle must pass separately."""
    validate('Task', task)
    validate('Snapshot', snapshot)
    validate('AgentResult', agent)
    identity(snapshot, scope)
    identity(agent, scope)
    require(agent['status'] == 'completed', 'agent did not complete')
    answer = agent['final_answer']
    if task['expected_state']['kind'] == 'read_only':
        require(answer['invoice_id'] is None and
                set(answer['record_ids']) == set(task['expected_state']['required_record_ids']), 'wrong record set')
    else:
        require(len(snapshot['tables']['invoices']) == 1 and answer['record_ids'] == [] and
                answer['invoice_id'] == snapshot['tables']['invoices'][0]['invoice_id'], 'wrong saved ID')


@evidence
def grade_read_trace(task, events, scope):
    """Trusted captured trace, never agent counts; does not prove server ACLs."""
    validate('Task', task)
    require(task['expected_state']['kind'] == 'read_only', 'not read workflow')
    validate('EventStream', events)
    successful = False
    observed = set()
    primary = TABLE_KEYS[task['expected_state']['record_table']]

    def collect(value):
        if isinstance(value, dict):
            if primary in value:
                observed.add(value[primary])
            for child in value.values():
                collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)

    for event in events:
        identity(event, scope)
        if event['event_type'].startswith('tool.'):
            tool = event['data']['tool_id']
            require(tool in task['permitted_tools'] and tool != 'billing_create_draft_invoice', 'unauthorized tool')
            require(event['phase'] == 'execution', 'read verifier forbidden')
            if (event['event_type'] == 'tool.completed' and event['source'] == 'mcp'
                    and tool in task['relevant_tool_ids']):
                successful = True
                collect(event['data']['tool_result']['result'])
    require(successful and set(task['expected_state']['required_record_ids']) <= observed,
            'missing successful authorized relevant read of expected IDs')


@evidence
def grade_replay(task, fixture, assertions, agent_snapshot, agent_mapping, agent_receipt,
                 final_snapshot, final_mapping, final_receipt, request, result,
                 scope, config_hash):
    """Replay consistency only; T016 must gate calls on original state/answer/budget PASS."""
    require(grade_state(task, fixture, assertions, agent_snapshot, agent_mapping,
                        agent_receipt, scope).passed, 'original state failed')
    require(task['expected_state']['kind'] == 'draft_invoice', 'read verifier forbidden')
    registration(final_mapping, scope, fixture, task)
    bind_snapshot(final_snapshot, final_mapping, final_receipt, scope, 'final')
    require(fingerprint(fixture, agent_snapshot['tables']) ==
            fingerprint(fixture, final_snapshot['tables']), 'replay changed state')
    validate('VerificationRequest', request)
    validate('VerifierResult', result)
    validate('SHA256', config_hash)
    for value in (request, result):
        identity(value, scope)
        require(value['task_id'] == task['task_id'] and value['task_hash'] == canonical_hash(task)
                and value['config_hash'] == config_hash and value['idempotency_key'] == scope.idempotency_key,
                'wrong verification binding')
        require(value['invoice_id'] == agent_snapshot['tables']['invoices'][0]['invoice_id'] and
                value['original_request_hash'] == payload_hash(arguments(task['expected_state'])),
                'wrong original request')
    require(request['original_arguments'] == arguments(task['expected_state']), 'wrong arguments')
    require(result['status'] == 'completed', 'verification incomplete')
    require(request['budget']['anchor_id'] == result['budget']['anchor_id'] and
            request['budget']['started_at'] == result['budget']['started_at'] and
            request['budget']['deadline_at'] == result['budget']['deadline_at'] and
            result['budget']['elapsed_ms'] >= request['budget']['elapsed_ms'], 'budget binding')
    replay = result['checks'][0]['tool_result']['result']
    require(replay['invoice'] == agent_snapshot['tables']['invoices'][0] and
            ordered(replay['lines'], 'invoice_lines') == ordered(agent_snapshot['tables']['invoice_lines'], 'invoice_lines'),
            'replay response differs from saved rows')
