import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data
from order_exclusions import exclude


class OrderExclusionTests(unittest.TestCase):
    def test_deleted_orders_cannot_return_from_sync_or_direct_insert(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            rows = [
                {'Order no': '640477', 'Delivery method': 'Palletways', 'Status': 'P'},
                {'Order no': '640318', 'Delivery method': 'Palletways', 'Order Category': 'Credit/Refund', 'Original order Number': '100', 'Status': 'C'},
                {'Order no': '100', 'Delivery method': 'Palletways', 'Status': 'P'},
            ]
            delivery_data.archive(rows)
            with delivery_data.connect() as db:
                removed = exclude(db, ['640477', '640318', '639501', '639004'])
                db.commit()
            self.assertEqual(removed['deliveries'], 2)
            delivery_data.archive(rows)
            self.assertEqual([row['order'] for row in delivery_data.snapshot()], ['100'])
            with delivery_data.connect() as db:
                self.assertEqual(db.execute('SELECT count(*) FROM excluded_orders').fetchone()[0], 4)
                self.assertFalse(db.execute("SELECT 1 FROM tracking_related_orders WHERE order_id='640318'").fetchone())
                self.assertFalse(db.execute("SELECT 1 FROM sales_activity_orders WHERE order_id='640477'").fetchone())
                db.execute("INSERT INTO activity VALUES ('640477', '2026-11-05', 'Should stay excluded')")
                self.assertFalse(db.execute("SELECT 1 FROM activity WHERE order_id='640477'").fetchone())
                db.execute("UPDATE deliveries SET order_id='640477' WHERE order_id='100'")
                self.assertTrue(db.execute("SELECT 1 FROM deliveries WHERE order_id='100'").fetchone())
                self.assertFalse(db.execute("SELECT 1 FROM deliveries WHERE order_id='640477'").fetchone())

    def test_invalid_id_does_not_delete_records(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': '100', 'Delivery method': 'Palletways'}])
            with delivery_data.connect() as db:
                with self.assertRaises(ValueError):
                    exclude(db, ['100', 'invalid'])
            self.assertEqual([row['order'] for row in delivery_data.snapshot()], ['100'])
