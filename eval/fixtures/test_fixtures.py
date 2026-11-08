"""Static corpus negatives use deep copies or isolated temporary directories."""
from copy import deepcopy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from contracts.validate import ContractError, load_file, seed_hash, validate
from .validate import ROOT, ROLES, file_hash, validate_corpus, validate_records


class FixtureTests(unittest.TestCase):
    def setUp(self):
        self.fixture = load_file(ROOT / 'fixture.json')
        self.tasks = [load_file(ROOT / f'tasks/{name}.json') for name in ROLES]
        self.assertions = load_file(ROOT / 'assertions.json')

    def check(self):
        self.fixture['seed_hash'] = seed_hash(self.fixture)
        validate_records(self.fixture, self.tasks, self.assertions)

    def test_corpus_repeatability(self):
        self.assertEqual(validate_corpus(), validate_corpus())
        original = self.fixture['seed_hash']
        shuffled = deepcopy(self.fixture)
        for rows in shuffled['seed'].values():
            rows.reverse()
        self.assertEqual(seed_hash(shuffled), original)
        shuffled['seed']['items'][0]['unit_price_cents'] += 1
        self.assertNotEqual(seed_hash(shuffled), original)

    def test_run_metadata_not_seed_business_state(self):
        altered = deepcopy(self.fixture)
        altered['run_id'] = 'run-generated-example'
        altered['control'] = {'attempt_id': 'attempt-generated-example'}
        self.assertEqual(seed_hash(altered), self.fixture['seed_hash'])
        # Seed hash exclusion is not permission to place control data in a Fixture.
        with self.assertRaises(ContractError):
            validate('Fixture', altered)

    def test_missing_duplicate_and_broken_records(self):
        for table, operation in [
            ('customers', lambda rows: rows.pop()),
            ('items', lambda rows: rows.append(deepcopy(rows[0]))),
            ('projects', lambda rows: rows[0].update(customer_id='CUST-404')),
            ('timesheets', lambda rows: rows[0].update(project_id='PRJ-404')),
        ]:
            with self.subTest(table=table):
                original = deepcopy(self.fixture)
                operation(self.fixture['seed'][table])
                with self.assertRaises(ContractError):
                    self.check()
                self.fixture = original

    def test_strict_types_and_dates(self):
        for field, value in [('minutes', True), ('minutes', 120.0),
                             ('work_date', '2026-11-31')]:
            with self.subTest(field=field, value=value):
                original = deepcopy(self.fixture)
                self.fixture['seed']['timesheets'][0][field] = value
                with self.assertRaises(ContractError):
                    self.check()
                self.fixture = original

    def test_independent_price_even_if_expected_and_seed_agree(self):
        self.fixture['seed']['items'][0]['unit_price_cents'] = 12600
        for task in self.tasks[:2]:
            task['expected_state']['lines'][0]['unit_price_cents'] = 12600
            task['expected_state']['subtotal_cents'] = 25200
            task['expected_state']['total_cents'] = 25200
        with self.assertRaises(ContractError):
            self.check()

    def test_independent_invoice_specification(self):
        for field, value in [('customer_id', 'CUST-002'), ('total_cents', 25001),
                             ('invoice_date', '2026-11-08'), ('due_date', '2026-11-22')]:
            with self.subTest(field=field):
                original = deepcopy(self.tasks)
                self.tasks[0]['expected_state'][field] = value
                with self.assertRaises(ContractError):
                    self.check()
                self.tasks = original

    def test_expected_replay_and_unchanged_assertions(self):
        self.assertions['invoice']['replay']['may_create_missing_invoice'] = True
        with self.assertRaises(ContractError):
            self.check()
        self.assertions = load_file(ROOT / 'assertions.json')
        self.assertions['invoice']['unchanged_seed_tables'].remove('items')
        with self.assertRaises(ContractError):
            self.check()

    def test_permission_and_full_context_scopes(self):
        for index in (1, 2, 3):
            with self.subTest(index=index):
                original = deepcopy(self.tasks)
                self.tasks[index]['permitted_tools'].remove('billing_list_invoices')
                with self.assertRaises(ContractError):
                    self.check()
                self.tasks = original
        self.tasks[2]['permitted_tools'].append('billing_create_draft_invoice')
        with self.assertRaises(ContractError):
            self.check()

    def test_read_existence_exact_predicate_and_no_leakage(self):
        for record_id in ('PRJ-404', 'PRJ-9C2E'):
            self.tasks[2]['expected_state']['required_record_ids'] = [record_id]
            with self.assertRaises(ContractError):
                self.check()
        self.tasks[2] = load_file(ROOT / 'tasks/baseline-project.json')
        self.tasks[2]['prompt'] += ' PRJ-7F3A'
        with self.assertRaises(ContractError):
            self.check()
        self.tasks[2] = load_file(ROOT / 'tasks/baseline-project.json')
        self.tasks[3]['expected_state']['required_record_ids'] = ['TS-2E9A']
        with self.assertRaises(ContractError):
            self.check()

    def test_missing_duplicate_tasks_and_versions(self):
        original = deepcopy(self.tasks)
        for replacement in (original[:3], [original[0]] * 4):
            self.tasks = replacement
            with self.assertRaises(ContractError):
                self.check()
        self.tasks = original
        self.tasks[0]['task_version'] = '2'
        with self.assertRaises(ContractError):
            self.check()

    def test_prompt_and_relevance_consistency(self):
        for field, value in [('prompt', 'Find timesheets dated 2026-11-07.'),
                             ('relevant_tool_ids', ['billing_list_timesheets'])]:
            with self.subTest(field=field):
                original = deepcopy(self.tasks)
                self.tasks[3][field] = value
                with self.assertRaises(ContractError):
                    self.check()
                self.tasks = original

    def test_missing_empty_seed_table(self):
        del self.fixture['seed']['invoices']
        with self.assertRaises(ContractError):
            validate('Fixture', self.fixture)

    def test_manifest_staleness(self):
        # Never change committed data, even transiently.
        for change in ('file', 'contract', 'version', 'seed', 'inventory', 'role', 'unregistered'):
            with self.subTest(change=change), tempfile.TemporaryDirectory(prefix='mcpbench-t009-') as tmp:
                root = Path(tmp) / 'v1'
                shutil.copytree(ROOT, root)
                manifest = load_file(root / 'manifest.json')
                if change == 'file':
                    with (root / 'fixture.json').open('a') as stream:
                        stream.write(' ')
                elif change == 'contract':
                    manifest['contracts']['schema_sha256'] = '0' * 64
                elif change == 'version':
                    manifest['dataset_version'] = '2'
                elif change == 'seed':
                    manifest['seed_hash'] = '0' * 64
                elif change == 'inventory':
                    del manifest['files']['assertions.json']
                elif change == 'role':
                    manifest['tasks']['baseline-invoice'] = 'smoke3'
                else:
                    (root / 'extra.json').write_text('{}')
                (root / 'manifest.json').write_text(json.dumps(manifest))
                with self.assertRaises(ContractError):
                    validate_corpus(root)

    def test_rehashed_corruption_still_rejected(self):
        with tempfile.TemporaryDirectory(prefix='mcpbench-t009-') as tmp:
            root = Path(tmp) / 'v1'
            shutil.copytree(ROOT, root)
            path = root / 'tasks/smoke-invoice.json'
            task = load_file(path)
            task['expected_state']['due_date'] = '2026-11-22'
            path.write_text(json.dumps(task))
            manifest = load_file(root / 'manifest.json')
            manifest['files']['tasks/smoke-invoice.json'] = file_hash(path)
            (root / 'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaises(ContractError):
                validate_corpus(root)


if __name__ == '__main__':
    unittest.main()
