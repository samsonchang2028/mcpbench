"""Offline synthetic snapshot adversaries; not database or live-model proof."""
from copy import deepcopy
from pathlib import Path
import unittest

from contracts.validate import canonical_hash, load_file, payload_hash, validate
from eval.grading import RunScope, grade_state, grade_answer, grade_read_trace, grade_replay

ROOT = Path(__file__).resolve().parents[2]


def load(path):
    return load_file(ROOT / path)


def case(task_name='smoke-invoice'):
    fixture = load('eval/fixtures/v1/fixture.json')
    task = load(f'eval/fixtures/v1/tasks/{task_name}.json')
    assertions = load('eval/fixtures/v1/assertions.json')
    snapshot = load('contracts/v1/snapshot.example.json')
    if task['expected_state']['kind'] == 'read_only':
        snapshot['tables'] = deepcopy(fixture['seed'])
    else:
        for table in ('customers', 'items', 'projects', 'timesheets'):
            snapshot['tables'][table] = deepcopy(fixture['seed'][table])
    mapping = load('contracts/v1/run-mapping.example.json')
    mapping.update(phase='agent_sealed', generation=1, agent_token_sha256=None,
                   workflow_kind=task['expected_state']['kind'], principal_id=task['principal_id'],
                   allowed_tools=task['permitted_tools'])
    receipt = load('contracts/v1/fence-receipt.example.json')
    scope = RunScope(mapping['run_id'], mapping['attempt_id'], 'idem-example-001')
    return task, fixture, assertions, snapshot, mapping, receipt, scope


def trace(task, scope):
    table = task['expected_state']['record_table']
    tool = 'billing_get_project' if table == 'projects' else 'billing_get_timesheet'
    key = 'project_id' if table == 'projects' else 'timesheet_id'
    record = next(row for row in load('eval/fixtures/v1/fixture.json')['seed'][table]
                  if row[key] == task['expected_state']['required_record_ids'][0])
    common = dict(schema_version=1, run_id=scope.run_id, attempt_id=scope.attempt_id,
                  source='mcp', timestamp='2026-11-07T23:00:00Z', phase='execution',
                  status='ok', call_id='read-001', elapsed_ms=1)
    return [{**common, 'event_id': 'read-start', 'sequence': 1, 'event_type': 'tool.started',
             'data': {'tool_id': tool, 'arguments': {key: record[key]}, 'retry_index': 0}},
            {**common, 'event_id': 'read-end', 'sequence': 2, 'event_type': 'tool.completed',
             'data': {'tool_id': tool, 'duration_ms': 1, 'tool_result':
                      {'tool_id': tool, 'is_error': False, 'result':
                       {('project' if table == 'projects' else 'timesheet'): record}}}}]


class OracleTests(unittest.TestCase):
    def test_literal_draft_and_baseline(self):
        for name in ('smoke-invoice', 'baseline-invoice'):
            values = case(name)
            self.assertEqual(values[0]['expected_state']['total_cents'], 25000)
            self.assertTrue(grade_state(*values).passed)

    def test_adversarial_rows(self):
        changes = [('invoices', 'customer_id', 'CUST-002'),
                   ('invoices', 'invoice_date', '2026-11-08'),
                   ('invoices', 'due_date', '2026-11-22'),
                   ('invoices', 'status', 'sent'), ('invoices', 'currency', 'EUR'),
                   ('invoices', 'total_cents', 24999), ('invoice_lines', 'quantity', 3),
                   ('invoice_lines', 'unit_price_cents', 17500),
                   ('invoice_lines', 'item_id', 'SVC-ADVISORY'),
                   ('invoice_lines', 'line_number', 2),
                   ('invoice_lines', 'invoice_id', 'INV-WRONG'),
                   ('idempotency_records', 'invoice_id', 'INV-WRONG'),
                   ('idempotency_records', 'idempotency_key', 'wrong-key'),
                   ('idempotency_records', 'request_hash', '0' * 64),
                   ('customers', 'name', 'Changed seed'),
                   ('items', 'unit_price_cents', 1), ('projects', 'name', 'Changed'),
                   ('timesheets', 'minutes', 1)]
        for table, field, value in changes:
            with self.subTest(table=table, field=field):
                values = case()
                values[3]['tables'][table][0][field] = value
                self.assertFalse(grade_state(*values).passed)

    def test_schema_valid_wrong_customer_and_price(self):
        for kind in ('customer', 'price'):
            values = case()
            tables = values[3]['tables']
            invoice, line = tables['invoices'][0], tables['invoice_lines'][0]
            if kind == 'customer':
                invoice['customer_id'] = 'CUST-002'
            else:
                line['unit_price_cents'] = 17500
                line['line_total_cents'] = invoice['subtotal_cents'] = invoice['total_cents'] = 35000
            args = {k: invoice[k] for k in ('customer_id', 'invoice_date', 'due_date')}
            args['lines'] = [{k: line[k] for k in ('item_id', 'quantity')}]
            tables['idempotency_records'][0]['request_hash'] = payload_hash(args)
            validate('Snapshot', values[3])
            self.assertFalse(grade_state(*values).passed)

    def test_extra_missing_or_mutated_records(self):
        for table in case()[3]['tables']:
            for operation in ('extra', 'missing'):
                values = case()
                rows = values[3]['tables'][table]
                if operation == 'extra':
                    rows.append(deepcopy(rows[0]))
                else:
                    rows.pop()
                self.assertFalse(grade_state(*values).passed, (table, operation))

    def test_valid_extra_invoice_is_not_task_success(self):
        values = case()
        tables = values[3]['tables']
        for table, primary in [('invoices', 'invoice_id'), ('invoice_lines', 'line_id'),
                               ('idempotency_records', 'idempotency_key')]:
            row = deepcopy(tables[table][0])
            row[primary] += '-extra' if primary == 'idempotency_key' else '-EXTRA'
            row['invoice_id'] = 'INV-EXTRA'
            tables[table].append(row)
        validate('Snapshot', values[3])
        self.assertFalse(grade_state(*values).passed)

    def test_task_literals_cannot_be_redefined(self):
        values = case()
        values[0]['expected_state']['due_date'] = '2026-11-22'
        self.assertFalse(grade_state(*values).passed)

    def test_trusted_binding_and_stale_snapshot(self):
        for index, field, value in [(3, 'run_id', 'wrong-run'), (3, 'attempt_id', 'wrong-attempt'),
                                    (3, 'stage', 'diagnostic'), (3, 'settlement_generation', 2),
                                    (3, 'captured_at', '2026-11-06T23:00:00Z'),
                                    (4, 'phase', 'executing'), (4, 'schema_name', 'public'),
                                    (4, 'tenant_id', 'OTHER'), (5, 'status', 'unknown')]:
            values = list(case())
            values[index][field] = value
            self.assertFalse(grade_state(*values).passed, (index, field))
        values = list(case())
        values[-1] = RunScope('different-run', values[-1].attempt_id, values[-1].idempotency_key)
        self.assertFalse(grade_state(*values).passed)

    def test_invalid_evidence_and_assertions(self):
        for index in range(6):
            values = list(case())
            values[index] = None
            self.assertFalse(grade_state(*values).passed)
        values = case()
        values[2]['invoice']['original']['line_total_cents'] = 1
        self.assertFalse(grade_state(*values).passed)

    def test_read_workflows_and_row_order(self):
        for name in ('baseline-project', 'baseline-time'):
            values = case(name)
            for rows in values[3]['tables'].values():
                rows.reverse()
            self.assertTrue(grade_state(*values).passed)
            agent = load('contracts/v1/read-agent-result.example.json')
            agent['final_answer']['record_ids'] = values[0]['expected_state']['required_record_ids']
            self.assertTrue(grade_answer(values[0], values[3], agent, values[-1]).passed)
            self.assertTrue(grade_read_trace(values[0], trace(values[0], values[-1]), values[-1]).passed)
            self.assertFalse(grade_read_trace(values[0], [], values[-1]).passed)
            events = trace(values[0], values[-1])
            for event in events:
                event['source'] = 'agent'
            self.assertFalse(grade_read_trace(values[0], events, values[-1]).passed)
            events = trace(values[0], values[-1])
            record_table = values[0]['expected_state']['record_table']
            result_key = 'project' if record_table == 'projects' else 'timesheet'
            primary = 'project_id' if record_table == 'projects' else 'timesheet_id'
            events[1]['data']['tool_result']['result'][result_key][primary] = 'DECOY'
            self.assertFalse(grade_read_trace(values[0], events, values[-1]).passed)
            events = trace(values[0], values[-1])
            events.pop(0)
            self.assertFalse(grade_read_trace(values[0], events, values[-1]).passed)
            agent['final_answer']['record_ids'] = ['WRONG']
            self.assertFalse(grade_answer(values[0], values[3], agent, values[-1]).passed)
            values[3]['tables']['customers'][0]['name'] = 'Mutation'
            self.assertFalse(grade_state(*values).passed)

    def test_answers_do_not_change_db_evidence(self):
        values = case()
        agent = load('contracts/v1/agent-result.example.json')
        self.assertTrue(grade_answer(values[0], values[3], agent, values[-1]).passed)
        for change in ('invoice', 'timeout', 'run'):
            wrong = deepcopy(agent)
            if change == 'invoice':
                wrong['final_answer']['invoice_id'] = 'WRONG'
            elif change == 'timeout':
                wrong['status'] = 'timeout'
            else:
                wrong['run_id'] = 'WRONG'
            self.assertFalse(grade_answer(values[0], values[3], wrong, values[-1]).passed)
            self.assertTrue(grade_state(*values).passed)

    def replay_case(self):
        task, fixture, assertions, snap, mapping, receipt, scope = case()
        final = deepcopy(snap)
        final.update(stage='final', settlement_generation=2)
        final_mapping = {**mapping, 'phase': 'final_sealed', 'generation': 2}
        final_receipt = {**receipt, 'fence': 'verifier', 'phase': 'final_sealed', 'generation': 2}
        request = load('contracts/v1/verification-request.example.json')
        result = load('contracts/v1/verifier-result.example.json')
        for value in (request, result):
            value.update(task_id=task['task_id'], task_hash=canonical_hash(task))
        return [task, fixture, assertions, snap, mapping, receipt, final,
                final_mapping, final_receipt, request, result, scope, request['config_hash']]

    def test_replay_success_and_rejection(self):
        self.assertTrue(grade_replay(*self.replay_case()).passed)
        for index, field, value in [(6, 'settlement_generation', 1),
                                    (8, 'generation', 1), (9, 'run_id', 'WRONG'),
                                    (10, 'invoice_id', 'WRONG'), (10, 'config_hash', '0' * 64),
                                    (10, 'idempotency_key', 'WRONG')]:
            values = self.replay_case()
            values[index][field] = value
            self.assertFalse(grade_replay(*values).passed)
        values = self.replay_case()
        values[6]['tables']['invoices'][0]['created_at'] = '2026-11-07T22:00:00Z'
        self.assertFalse(grade_replay(*values).passed)
        values = self.replay_case()
        values[3]['tables']['invoices'] = []
        self.assertFalse(grade_replay(*values).passed)
        values = self.replay_case()
        values[10]['checks'][0]['tool_result']['result']['invoice']['created_at'] = '2026-11-07T22:00:00Z'
        self.assertFalse(grade_replay(*values).passed)


if __name__ == '__main__':
    unittest.main()
