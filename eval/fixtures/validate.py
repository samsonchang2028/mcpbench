"""Read-only corpus checks. This is neither a database oracle nor a grader."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from contracts.validate import (
    CATALOG, ROOT as CONTRACT_ROOT, ContractError, load_file, seed_hash,
    canonical_bytes, validate, validate_task_fixture,
)

ROOT = Path(__file__).resolve().parent / 'v1'
ROLES = {'smoke-invoice': 'smoke3', 'baseline-invoice': 'baseline10',
         'baseline-project': 'baseline9-reader', 'baseline-time': 'baseline9-reader'}
FILES = {'fixture.json', 'assertions.json'} | {f'tasks/{name}.json' for name in ROLES}
SMOKE_PROMPT = ('Create a draft invoice for customer CUST-001 for two hours of '
                'SVC-CONSULT, dated 2026-11-07, due 2026-11-21. Do not send it.')
# Independent task specification literals, never imported from a server or computed
# from seed prices. Arithmetic and seed agreement are checked separately.
INVOICE_EXPECTED = {
    'kind': 'draft_invoice', 'customer_id': 'CUST-001',
    'invoice_date': '2026-11-07', 'due_date': '2026-11-21', 'currency': 'USD',
    'lines': [{'item_id': 'SVC-CONSULT', 'quantity': 2, 'unit_price_cents': 12500}],
    'subtotal_cents': 25000, 'tax_cents': 0, 'total_cents': 25000,
    'invoice_count_delta': 1,
    'allowed_changed_tables': ['invoices', 'invoice_lines', 'idempotency_records'],
}
ASSERTIONS = {
    'schema_version': 1, 'fixture_version': '1',
    'invoice': {
        'original': {'status': 'draft', 'invoice_count_delta': 1,
                     'invoice_line_count_delta': 1, 'idempotency_count_delta': 1,
                     'line_number': 1, 'line_total_cents': 25000,
                     'answer': 'same_saved_invoice_id'},
        'unchanged_seed_tables': ['customers', 'items', 'projects', 'timesheets'],
        'replay': {'same_payload': 'same_saved_invoice_id',
                   'changed_payload': 'idempotency_conflict', 'changed_quantity': 3,
                   'application_state': 'equal_agent_only_snapshot',
                   'may_create_missing_invoice': False}},
    'read_only': {'application_state': 'equal_seed',
                  'answer': 'exact_required_record_ids',
                  'evidence': 'successful_authorized_read_trace', 'verifier_calls': 0},
}


READ_PROMPTS = {
    'baseline-project': 'Find the ID of the active project named Lantern Launch for Juniper Lantern Studio. Return only the matching project ID; make no changes.',
    'baseline-time': 'Find the IDs of billable timesheets dated 2026-11-06 for the Lantern Launch project of Juniper Lantern Studio. Return only the matching timesheet IDs; make no changes.',
}
RELEVANT = {
    'smoke-invoice': ['billing_list_customers', 'billing_list_items', 'billing_create_draft_invoice'],
    'baseline-invoice': ['billing_list_customers', 'billing_list_items', 'billing_create_draft_invoice', 'billing_get_customer'],
    'baseline-project': ['billing_list_customers', 'billing_get_customer', 'billing_list_projects', 'billing_get_project', 'billing_list_timesheets'],
    'baseline-time': ['billing_list_customers', 'billing_get_customer', 'billing_list_projects', 'billing_get_project', 'billing_list_timesheets', 'billing_get_timesheet'],
}


def require(condition: bool, category: str) -> None:
    if not condition:
        raise ContractError(category)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_records(fixture: dict, tasks: list[dict], assertions: dict) -> None:
    """Check in-memory records without rewriting data or evaluating run results."""
    validate('Fixture', fixture)
    require((fixture['fixture_id'], fixture['fixture_version'], fixture['migration_version'])
            == ('fictional-billing-dev', '1', '1'), 'fixture version/identity')
    seed = fixture['seed']
    require(all(len(seed[t]) == 2 for t in ('customers', 'items', 'projects', 'timesheets')),
            'development seed cardinality')
    require(all(not seed[t] for t in ('invoices', 'invoice_lines', 'idempotency_records')),
            'nonempty initial write tables')
    require(all(row['active'] for t in ('customers', 'items', 'projects') for row in seed[t]),
            'inactive target or decoy')
    items = {row['item_id']: row for row in seed['items']}
    require(items.get('SVC-CONSULT', {}).get('unit_price_cents') == 12500
            and items.get('SVC-ADVISORY', {}).get('unit_price_cents') == 17500,
            'independent seed prices')
    require(canonical_bytes(assertions) == canonical_bytes(ASSERTIONS),
            'assertion specification changed')
    require(len(tasks) == 4 and {t['task_id'] for t in tasks} == set(ROLES),
            'missing or duplicate task')
    require(all(task['budgets'] == tasks[0]['budgets'] for task in tasks),
            'unequal task budgets')
    for task in tasks:
        validate_task_fixture(task, fixture)
        require(task['task_version'] == '1' and task['split'] == 'development',
                'task version/split')
        role = ROLES[task['task_id']]
        reader = role == 'baseline9-reader'
        permitted = (CATALOG['smoke_tool_ids'] if role == 'smoke3' else
                     [t['name'] for t in CATALOG['tools']
                      if not reader or t['permission'] == 'billing:read'])
        require(task['permitted_tools'] == permitted, 'full authorized catalog required')
        require(task['principal_id'] == ('billing-reader' if reader else 'billing-drafter'),
                'principal mismatch')
        require(task['relevant_tool_ids'] == RELEVANT[task['task_id']],
                'development relevance annotation changed')
        if not reader:
            require(task['prompt'] == SMOKE_PROMPT and task['expected_state'] == INVOICE_EXPECTED,
                    'independent invoice specification')
            require(task['required_tool_ids'] == ['billing_create_draft_invoice'],
                    'invoice required tools')
        else:
            require(task['prompt'] == READ_PROMPTS[task['task_id']], 'read prompt specification')
            require(task['required_tool_ids'] == [], 'conservative read required set')
            expected = task['expected_state']
            require(all(record_id.casefold() not in (task['prompt'] + task['task_id']).casefold()
                        for record_id in expected['required_record_ids']), 'literal read answer leakage')
            # Independent natural-language predicates; verify exact sets, not existence alone.
            projects = {p['project_id'] for p in seed['projects']
                        if p['name'] == 'Lantern Launch' and p['active']
                        and any(c['customer_id'] == p['customer_id']
                                and c['name'] == 'Juniper Lantern Studio' for c in seed['customers'])}
            if task['task_id'] == 'baseline-project':
                table, ids = 'projects', projects
            else:
                table = 'timesheets'
                ids = {t['timesheet_id'] for t in seed[table]
                       if t['project_id'] in projects and t['billable']
                       and t['work_date'] == '2026-11-06'}
            require(len(ids) == 1 and expected['record_table'] == table
                    and set(expected['required_record_ids']) == ids, 'read oracle predicate mismatch')


def validate_corpus(root: Path = ROOT) -> dict:
    manifest = load_file(root / 'manifest.json')
    require(set(manifest) == {'schema_version', 'dataset_id', 'dataset_version', 'split',
                             'contracts', 'seed_hash', 'files', 'tasks'}, 'manifest fields')
    require(type(manifest['schema_version']) is int and manifest['schema_version'] == 1
            and manifest['dataset_id'] == 'fictional-billing-dev'
            and manifest['dataset_version'] == '1' and manifest['split'] == 'development',
            'manifest version/split')
    require(canonical_bytes(manifest['contracts']) == canonical_bytes({
        'schema_version': 1, 'catalog_version': CATALOG['catalog_version'],
        'schema_sha256': file_hash(CONTRACT_ROOT / 'v1/schema.json'),
        'catalog_sha256': file_hash(CONTRACT_ROOT / 'v1/catalog.json')}), 'stale contract hashes/version')
    require(set(manifest['files']) == FILES, 'manifest file inventory')
    require({p.relative_to(root).as_posix() for p in root.rglob('*.json')}
            == FILES | {'manifest.json'}, 'unregistered corpus JSON')
    for name in sorted(FILES):
        path = root / name
        require(not path.is_symlink() and path.is_file(), 'invalid corpus file')
        require(file_hash(path) == manifest['files'][name], 'stale file hash')
    require(manifest['tasks'] == ROLES, 'task role inventory')
    fixture = load_file(root / 'fixture.json')
    tasks = [load_file(root / f'tasks/{name}.json') for name in ROLES]
    validate_records(fixture, tasks, load_file(root / 'assertions.json'))
    require(manifest['seed_hash'] == fixture['seed_hash'] == seed_hash(fixture), 'seed fingerprint')
    return {'dataset_id': manifest['dataset_id'], 'tasks': len(tasks),
            'seed_hash': manifest['seed_hash']}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        result = validate_corpus(args.root)
    except (ContractError, OSError, KeyError, TypeError, ValueError):
        print('FAIL: invalid static corpus')
        return 1
    print(f"PASS: {result['dataset_id']} ({result['tasks']} tasks); seed={result['seed_hash']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
