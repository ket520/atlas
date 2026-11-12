import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data


class DeliveryMethodFilterTests(unittest.TestCase):
    def test_multiple_methods_filter_before_paging_with_no_twelve_option_limit(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            methods = [f'Palletways service {index}' for index in range(15)]
            delivery_data.archive([
                {'Order no': str(index), 'Delivery method': method, 'Status': 'P'}
                for index, method in enumerate(methods * 3)
            ] + [{'Order no': 'van', 'Delivery method': 'Own van', 'Status': 'P'}])
            selected = methods[:13]
            first = delivery_data.query_records(classification=selected, limit=25)
            second = delivery_data.query_records(classification=selected, limit=25, offset=25)
            self.assertEqual((first['total'], len(first['deliveries']), len(second['deliveries'])), (39, 25, 14))
            self.assertTrue(first['hasMore'])
            self.assertFalse(second['hasMore'])
            self.assertEqual({item['deliveryMethodRaw'] for item in first['deliveries'] + second['deliveries']}, set(selected))
            self.assertEqual(delivery_data.query_records(carrier='Own van', classification=selected)['total'], 0)
            self.assertEqual(delivery_data.query_records(classification=[methods[0], 'Own van'])['total'], 4)
            self.assertEqual(delivery_data.query_records(classification=methods[0])['total'], 3)
            self.assertEqual(delivery_data.query_records(classification=[])['total'], 46)

    def test_method_labels_containing_commas_are_kept_intact(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            delivery_data.archive([
                {'Order no': '1', 'Delivery method': 'Palletways, special', 'Status': 'P'},
                {'Order no': '2', 'Delivery method': 'Palletways', 'Status': 'P'},
            ])
            result = delivery_data.query_records(classification=['Palletways, special'])
            self.assertEqual([item['order'] for item in result['deliveries']], ['1'])
