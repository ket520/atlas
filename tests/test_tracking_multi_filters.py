import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data as data
from palletways_sheet import archive_statuses


class TrackingMultiFilterTests(unittest.TestCase):
    def test_palletways_delivered_uses_only_column_f(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            data.archive([{'Order no': str(i), 'Delivery method': 'Palletways', 'Status': 'P'} for i in range(4)])
            archive_statuses([{'order': '0', 'status': 'Delivered'}, {'order': '2', 'status': 'In Transit'}])
            with data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload,'$.st','Delivered') WHERE order_id IN ('1','2')")
                db.execute("UPDATE deliveries SET payload=json_set(payload,'$.st','Rejected') WHERE order_id='0'")
                db.commit()
            filters = dict(carrier='Palletways', courier_status=True)
            result = data.query_records(**filters, status='Delivered')
            self.assertEqual({item['order'] for item in result['deliveries']}, {'0'})
            self.assertEqual(data.query_records(**filters, status='palletways:Delivered')['total'], 1)
            self.assertEqual(data.query_records(**filters, status=['Delivered', 'palletways:In Transit'])['total'], 2)

    def test_status_store_union_and_intersection_apply_before_paging(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            data.archive([{'Order no': str(i), 'Delivery method': 'Palletways', 'Status': 'P'} for i in range(60)])
            archive_statuses([{'order': str(i), 'status': 'READY' if i % 2 else 'IN TRANSIT'} for i in range(60)])
            with data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload,'$.storeCode',CASE WHEN CAST(order_id AS INTEGER)%3=0 THEN 'AMAZON' WHEN CAST(order_id AS INTEGER)%3=1 THEN 'B&Q' ELSE 'WILKO' END)")
                db.commit()
            filters = dict(carrier='Palletways', courier_status=True)
            result = data.query_records(**filters, status=['palletways:READY', 'palletways:IN TRANSIT'], store=['Amazon', 'B&Q'], limit=25)
            self.assertEqual(result['total'], 40)
            self.assertEqual(len(result['deliveries']), 25)
            self.assertTrue(result['hasMore'])
            self.assertEqual(data.query_records(**filters, status=['palletways:READY'], store=['Amazon', 'B&Q'])['total'], 20)
            self.assertEqual(data.query_records(**filters, status='palletways:READY', store='Amazon')['total'], 10)
            self.assertEqual(data.query_records(status=[], store=[])['total'], 60)

    def test_categories_union_before_paging_and_status_intersection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            data.archive([{'Order no': str(i), 'Delivery method': 'Palletways', 'Status': 'P'} for i in range(6)])
            with data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload,'$.carrier',CASE WHEN CAST(order_id AS INTEGER)<2 THEN 'SUPPLIER' WHEN CAST(order_id AS INTEGER)<4 THEN 'Cancelled' ELSE 'Palletways' END,'$.st','Scheduled')")
                db.commit()
            result = data.query_records(general_scope=['SUPPLIER', 'Cancelled'], limit=1)
            self.assertEqual(result['total'], 4)
            self.assertEqual(len(result['deliveries']), 1)
            self.assertEqual(data.query_records(general_scope='SUPPLIER')['total'], 2)
            self.assertEqual(data.query_records(general_scope=['SUPPLIER', 'Cancelled'], status='Delivered')['total'], 0)
            self.assertEqual(data.query_records(general_scope=['today', 'Cancelled'])['total'], 2)
            self.assertEqual(data.query_records(general_scope=[])['total'], 6)
