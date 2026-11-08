"""Behavioral Python checks only: these do not validate PostgreSQL semantics."""
from copy import deepcopy
from datetime import date, datetime, timezone
import unittest
from unittest.mock import Mock, patch

from psycopg.pq import TransactionStatus
from db import manage
from contracts.validate import ContractError, load_file, ROOT, schema_name


class OfflineTests(unittest.TestCase):
    def test_frozen_seed(self):
        source = manage.fixture()
        self.assertEqual(source['seed_hash'], '8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78')
        self.assertEqual(set(source['seed']), set(manage.TABLES))
        for table, rows in source['seed'].items():
            for row in rows:
                self.assertEqual(set(row), set(manage.TABLES[table]))

    def test_schema_injection_and_direction_rejected(self):
        for bad in ('public', 'r_' + '0' * 31, 'r_' + 'a' * 32 + ';DROP SCHEMA public'):
            with self.assertRaises(ValueError):
                manage.migration_sql('up', bad)
        with self.assertRaises(ValueError):
            manage.migration_sql('../../bootstrap', schema_name('run-test'))
        rendered = manage.migration_sql('up', schema_name('run-test')).as_string()
        self.assertIn('"' + schema_name('run-test') + '".customers', rendered)
        self.assertNotIn('__SCHEMA__', rendered)

    def test_changed_seed_is_detectable(self):
        source = manage.fixture()
        altered = deepcopy(source['seed'])
        altered['items'][0]['unit_price_cents'] += 1
        self.assertNotEqual(manage._fingerprint(source, altered), source['seed_hash'])
        altered = deepcopy(source['seed'])
        for rows in altered.values():
            rows.reverse()
        self.assertEqual(manage._fingerprint(source, altered), source['seed_hash'])

    def test_wire_dates(self):
        self.assertEqual(manage._wire(date(2026, 11, 7)), '2026-11-07')
        self.assertEqual(manage._wire(datetime(2026, 11, 7, tzinfo=timezone.utc)), '2026-11-07T00:00:00.000000Z')
        self.assertEqual(manage._wire(12500), 12500)

    def test_prepared_only(self):
        mapping = load_file(ROOT / 'v1/run-mapping.example.json')
        with self.assertRaises(manage.DatabaseStateError):
            manage._initial(mapping)
        mapping.update(phase='prepared', generation=0, agent_token_sha256=None)
        manage._initial(mapping)
        for phase in ('agent_sealed', 'cleaned', 'quarantined'):
            with self.assertRaises(manage.DatabaseStateError):
                manage._initial({**mapping, 'phase': phase})

    def test_invalid_mapping_fails_before_database(self):
        conn = Mock()
        mapping = load_file(ROOT / 'v1/run-mapping.example.json')
        mapping['schema_name'] = 'public'
        with self.assertRaises(ContractError):
            manage.prepare(conn, mapping)
        conn.execute.assert_not_called()

    def test_nested_transaction_rejected(self):
        conn = Mock()
        conn.info.transaction_status = TransactionStatus.INTRANS
        with self.assertRaises(manage.DatabaseStateError):
            with manage._transaction(conn):
                self.fail('entered nested transaction')
        conn.execute.assert_not_called()

    def test_noncanonical_seed_never_overwrites(self):
        source = manage.fixture()
        conn = Mock()
        with patch.object(manage, '_metadata', return_value=(1,)), patch.object(
                manage, '_tables', return_value={**source['seed'], 'invoices': [{'invoice_id': 'BAD'}]}):
            with self.assertRaises(manage.DatabaseStateError):
                manage._seed(conn, {'schema_name': schema_name('run-test')}, source)
        conn.execute.assert_not_called()

    def test_canonical_repeat_is_read_only(self):
        source = manage.fixture()
        conn = Mock()
        with patch.object(manage, '_metadata', return_value=(1,)), patch.object(
                manage, '_tables', return_value=source['seed']):
            self.assertEqual(manage._seed(conn, {'schema_name': schema_name('run-test')}, source), source['seed_hash'])
        conn.execute.assert_not_called()

    def test_migration_checksum_is_stable(self):
        self.assertEqual(len(manage.migration_digest()), 64)
        self.assertEqual(manage.migration_digest(), manage.migration_digest())


if __name__ == '__main__':
    unittest.main()
