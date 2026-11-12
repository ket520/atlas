import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data


class TrackingVisibilityTests(unittest.TestCase):
    def test_tracking_counts_and_rows_share_the_same_credit_exclusion(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            delivery_data.archive([
                {'Order no': '100', 'Delivery method': 'Palletways', 'Status': 'W'},
                {'Order no': '101', 'Delivery method': 'Palletways', 'Status': 'W', 'Order Category': 'Credit/Refund', 'Original order Number': '100'},
                {'Order no': '102', 'Delivery method': 'Palletways', 'Status': 'W', 'Order Category': 'Credit/Refund'},
            ])
            facets = delivery_data.summary()['filterFacets']
            self.assertEqual(sum(item['count'] for item in facets if item['creditRefund']), 2)
            visible_count = sum(item['count'] for item in facets if not item['creditRefund'])
            page = delivery_data.query_records(carrier='Palletways', exclude_refunds=True)
            self.assertEqual(visible_count, page['total'])
            self.assertEqual(visible_count, 1)

    def test_palletways_b2b_hidden_before_paging_using_details_or_shipment_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            with delivery_data.connect() as db:
                db.execute('CREATE TABLE palletways_shipments (tracking_id TEXT, order_reference TEXT, classification TEXT)')
                db.executemany('INSERT INTO palletways_shipments VALUES (?,?,?)',
                               [('12345678901', '2', ' B2B '), ('12345678902', '3', 'B2B')])
                for order, carrier, classification, tracking in [
                    ('1', 'Palletways', ' b2b ', ''), ('2', 'Palletways', 'B2C', '12345678901'),
                    ('3', 'Palletways', '', ''), ('4', 'Palletways', 'B2C', ''),
                    ('5', 'Palletways', '', ''), ('6', 'XDP', 'B2B', '')]:
                    delivery = {'order': order, 'carrier': carrier, 'st': 'Scheduled', 'trk': tracking,
                                'palletwaysDetails': {'classification': classification}}
                    db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',
                               (order, json.dumps(delivery), '2026-10-22', '2026-10-22'))
                db.commit()
            first = delivery_data.query_records(hide_palletways_b2b=True, limit=2)
            second = delivery_data.query_records(hide_palletways_b2b=True, limit=2, offset=2)
            self.assertEqual(first['total'], 3)
            self.assertTrue(first['hasMore'])
            self.assertEqual({row['order'] for row in first['deliveries'] + second['deliveries']}, {'4', '5', '6'})
            self.assertEqual(delivery_data.query_records()['total'], 6)
            self.assertEqual(delivery_data.query_records(search='2')['deliveries'][0]['palletwaysDetails']['classification'], 'B2B')
            facets = delivery_data.summary()['filterFacets']
            self.assertEqual(sum(row['count'] for row in facets if row['palletwaysClassification'] == 'B2B'), 3)

    def test_wayfair_switch_filters_delivery_method_not_order_type(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'
        ):
            delivery_data.archive([
                {'Order no': '1', 'Delivery method': 'Wayfair', 'Status': 'FAILED'},
                {'Order no': '2', 'Delivery method': 'Wayfair UPS', 'Status': 'FAILED'},
                {'Order no': '3', 'Delivery method': 'XDP', 'Order Type': 'Wayfair', 'Status': 'FAILED'},
                {'Order no': '4', 'Delivery method': 'XDP', 'Order Type': 'Sales', 'Status': 'FAILED'},
            ])
            page = delivery_data.query_records(hide_wayfair=True, limit=1)
            self.assertEqual(page['total'], 2)
            self.assertTrue(page['hasMore'])
            self.assertEqual({row['order'] for row in delivery_data.query_records(hide_wayfair=True)['deliveries']}, {'3', '4'})
            self.assertEqual(delivery_data.query_records(hide_wayfair=True, hide_hygienic=True)['total'], 1)
            self.assertEqual(delivery_data.query_records()['total'], 4)
            self.assertEqual(delivery_data.query_records(issue_cases=True)['total'], 2)

    def test_hides_hygienic_order_types_and_store_before_paging(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'
        ):
            types = ['Sales', 'HG_Replacement', ' sales ', 'HR_Replacement', 'Wayfair', 'Weiko', '']
            delivery_data.archive([
                {'Order no': str(index), 'Delivery method': 'XDP', 'Status': 'FAILED', 'Order Type': order_type}
                for index, order_type in enumerate(types)
            ])
            first = delivery_data.query_records(hide_hygienic=True, limit=2)
            second = delivery_data.query_records(hide_hygienic=True, limit=2, offset=2)
            self.assertEqual(first['total'], 3)
            self.assertTrue(first['hasMore'])
            self.assertFalse(second['hasMore'])
            self.assertEqual({row['order'] for row in first['deliveries'] + second['deliveries']}, {'4', '5', '6'})
            self.assertEqual(delivery_data.query_records(hide_hygienic=True, search='0')['total'], 0)
            self.assertEqual(delivery_data.query_records()['total'], 7)
            sales = delivery_data.query_records(general_scope='hygienic', limit=1)
            self.assertEqual(sales['total'], 2)
            self.assertTrue(sales['hasMore'])
            self.assertTrue(all(row['salesActivityDetails']['Order Type'].lower() == 'sales' for row in sales['deliveries']))
            self.assertEqual(delivery_data.query_records(general_scope='hygienic', hide_hygienic=True)['total'], 0)
            self.assertEqual(delivery_data.query_records(issue_cases=True)['total'], 0)
            summary = delivery_data.summary()
            self.assertEqual(summary['total'], 7)
            self.assertEqual(sum(item['count'] for item in summary['filterFacets']), 7)
            self.assertEqual({item['orderType'] for item in summary['filterFacets']}, {value.strip() for value in types})
