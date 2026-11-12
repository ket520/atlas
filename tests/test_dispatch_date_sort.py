import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data


class DispatchDateSortTests(unittest.TestCase):
    def test_depot_widget_respects_explicit_created_sort(self):
        from datetime import datetime, timedelta, timezone
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': str(i), 'Delivery method': 'Palletways', 'Status': 'P'} for i in (1, 2)])
            with delivery_data.connect() as db:
                for order, days, created in [('1', 8, '2026-11-02'), ('2', 5, '2026-11-01')]:
                    row = db.execute('SELECT payload FROM deliveries WHERE order_id=?', (order,)).fetchone()
                    payload = json.loads(row['payload'])
                    payload.update(orderDate=created, orderDateTime='', palletwaysDepotStay={
                        'verified': True, 'arrivedAt': (datetime.now(timezone.utc)-timedelta(days=days)).isoformat()})
                    db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(payload), order))
                db.commit()
            self.assertEqual([r['order'] for r in delivery_data.query_records(dashboard_widget='palletways-depot-3days')['deliveries']], ['1', '2'])
            self.assertEqual([r['order'] for r in delivery_data.query_records(dashboard_widget='palletways-depot-3days', date_sort='created_asc', limit=1)['deliveries']], ['2'])

    def test_created_date_sorts_before_paging_and_keeps_missing_dates_last(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': str(i), 'Delivery method': 'Palletways', 'Status': 'P'} for i in range(1, 5)])
            with delivery_data.connect() as db:
                for order, day, timestamp in [('1', '2026-11-02', '2026-11-02T08:00:00'),
                                               ('2', '2026-11-01', ''), ('3', '', ''),
                                               ('4', '2026-11-02', '2026-11-02T16:00:00')]:
                    db.execute("UPDATE deliveries SET payload=json_set(payload,'$.orderDate',?,'$.orderDateTime',?) WHERE order_id=?", (day, timestamp, order))
                db.commit()
            def orders(direction, **paging):
                return [row['order'] for row in delivery_data.query_records(date_sort='created_' + direction, **paging)['deliveries']]
            self.assertEqual(orders('asc'), ['2', '1', '4', '3'])
            self.assertEqual(orders('desc'), ['4', '1', '2', '3'])
            self.assertEqual(orders('asc', limit=1, offset=1), ['1'])
            self.assertEqual(orders('desc', limit=2), ['4', '1'])

    def test_dispatch_sort_uses_fallback_and_pages_with_missing_dates_last(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'
        ):
            delivery_data.archive([
                {'Order no': order, 'Delivery method': 'XDP', 'Despatch Date': value}
                for order, value in [('1', '03/11/2026'), ('2', ''), ('3', ''), ('4', '')]
            ])
            with delivery_data.connect() as db:
                for order, value in [('1', '2026-11-01'), ('2', '2026-11-02')]:
                    row = db.execute('SELECT payload FROM deliveries WHERE order_id=?', (order,)).fetchone()
                    payload = json.loads(row['payload'])
                    payload['carrierIssueDispatchDate'] = value
                    db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(payload), order))
                db.commit()
            def orders(direction, **paging):
                return [item['order'] for item in delivery_data.query_records(
                    date_sort='dispatch_' + direction, **paging
                )['deliveries']]
            self.assertEqual(orders('asc'), ['2', '1', '4', '3'])
            self.assertEqual(orders('desc'), ['1', '2', '4', '3'])
            self.assertEqual(orders('asc', limit=1, offset=1), ['1'])
