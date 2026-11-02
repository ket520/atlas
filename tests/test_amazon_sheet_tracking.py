import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data


class AmazonSheetTrackingTests(unittest.TestCase):
    def test_lost_and_undeliverable_are_failed_and_recover_dynamically(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            source = [{'Order no': str(658386 + i), 'Delivery method': 'AMA XL', 'Tracking No': f'TRACK-{i}', 'Status': 'P'} for i in range(3)]
            delivery_data.archive(source)
            rows = [{'trackingId': f'TRACK-{i}', 'status': status} for i, status in enumerate(['UNDELIVERABLE', 'LOST', 'IN_TRANSIT'])]
            delivery_data.archive_amazon_shipping(rows)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='AMZ')['total'], 2)
            self.assertEqual(delivery_data.detail('658387')['amazonSheetStatus'], 'LOST')
            delivery_data.archive(source)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='AMZ')['total'], 2)
            rows[1]['status'] = 'DELIVERED'
            delivery_data.archive_amazon_shipping(rows)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='AMZ')['total'], 1)
            self.assertEqual(delivery_data.detail('658387')['st'], 'Delivered')

    def test_sales_activity_tracking_stays_with_its_order_and_is_not_replaced_by_amazon_tab(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            source = [
                {'Order no': '658386', 'Delivery method': 'AMA XL', 'Tracking No': 'SALES-TRACKING-1', 'Status': 'P'},
                {'Order no': '658387', 'Delivery method': 'AMA XL', 'Tracking No': 'SALES-TRACKING-2', 'Status': 'P'},
                {'Order no': '658388', 'Delivery method': 'AMA XL', 'Tracking No': '', 'Status': 'P'},
            ]
            delivery_data.archive(source)
            delivery_data.archive_amazon_shipping([
                {'orderId': '658386', 'trackingId': 'AMAZON-TAB-DIFFERENT', 'status': 'DELIVERED'},
            ])
            saved = {row['order']: row for row in delivery_data.snapshot()}
            self.assertEqual(saved['658386']['owTrackingNo'], 'SALES-TRACKING-1')
            self.assertEqual(saved['658387']['owTrackingNo'], 'SALES-TRACKING-2')
            self.assertEqual(saved['658388']['owTrackingNo'], '')
            source[0]['Tracking No'] = 'SALES-UPDATED'
            delivery_data.archive(source)
            self.assertEqual(delivery_data.detail('658386')['owTrackingNo'], 'SALES-UPDATED')
