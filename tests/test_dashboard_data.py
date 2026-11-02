import json
import tempfile
import threading
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from http.server import ThreadingHTTPServer
from zoneinfo import ZoneInfo

import dashboard_data
import delivery_data
import server


class DashboardDataTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.patch = patch.object(delivery_data, 'DB_PATH', Path(directory.name) / 'orders.sqlite3')
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.today = datetime.now(ZoneInfo('Europe/London')).date()

    def add(self, order, carrier, present=True, **fields):
        data = {'id': str(order), 'order': str(order), 'carrier': carrier, 'st': 'Unscheduled',
                'orderDate': self.today.isoformat(), 'storeCode': 'AMAZON', **fields}
        with delivery_data.connect() as db:
            db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',
                       (str(order), json.dumps(data), self.today.isoformat(), self.today.isoformat()))
            if present:
                db.execute('INSERT OR IGNORE INTO sales_activity_orders VALUES (?)', (str(order),))
            db.execute('INSERT OR REPLACE INTO sync_metadata VALUES (?,?)',
                       ('sales_activity_orders_snapshot', json.dumps({'observedAt': self.today.isoformat()})))
            db.commit()

    def test_awaiting_dispatch_uses_ow_status_across_carriers_before_paging(self):
        self.add(1, 'AMZ', rawStatus='W', st='Scheduled')
        self.add(2, 'Own van', rawStatus=' w ', st='Unscheduled')
        self.add(3, 'XDP', rawStatus='C', st='Awaiting')
        self.add(4, 'Palletways', rawStatus='K', st='Unscheduled')
        self.add(5, 'Palletways', rawStatus='Awaiting despatch')
        snapshot = dashboard_data.snapshot()['widgets']['awaiting-dispatch']
        self.assertEqual(snapshot['total'], 3)
        first = delivery_data.query_records(dashboard_widget='awaiting-dispatch', limit=1)
        self.assertEqual(first['total'], 3)
        self.assertTrue(first['hasMore'])
        self.assertEqual(delivery_data.query_records(dashboard_widget='awaiting-dispatch', carrier='Own van')['total'], 1)
        self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets('awaiting-dispatch')), 3)

    def test_identifier_reads_exact_order_without_provider_requests(self):
        self.add(123456, 'AMZ', rawStatus='W')
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/order-identifier?order=123456') as response:
                result = json.load(response)
            self.assertEqual(result, {'found': True, 'order': '123456', 'store': 'Amazon', 'courier': 'AMZ', 'trackingId': ''})
            with urlopen(f'http://127.0.0.1:{http.server_port}/api/order-identifier?order=12345') as response:
                self.assertFalse(json.load(response)['found'])
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_cohorts_use_real_status_fields_and_do_not_treat_unknown_booking_as_unbooked(self):
        self.add(1, 'Palletways', deliveryMethodRaw='Palletways Next Day', palletwaysSheetBookedIn='No')
        self.add(2, 'Palletways', deliveryMethodRaw='Palletways Next Day', st='Delivered', palletwaysSheetBookedIn='No')
        self.add(3, 'Palletways', deliveryMethodRaw='Palletways Economy')
        self.add(4, 'Own van', bookingStatus='Out of Stock', st='Scheduled')
        self.add(5, 'On Hold', st='Unassigned')
        self.add(6, 'Collect in Person')
        data = dashboard_data.snapshot()['widgets']
        for key in ['palletways-next-day', 'out-of-stock', 'van-unscheduled', 'hold', 'collect']:
            self.assertEqual(data[key]['total'], 1, key)
        self.assertEqual(data['palletways-unbooked']['total'], 1)
        self.assertEqual({row['order'] for row in data['palletways-unbooked']['preview']}, {'1'})
        self.assertFalse(data['returns']['available'])
        self.assertIsNone(data['returns']['total'])

    def test_cancelled_is_today_only_for_counts_previews_view_all_and_facets(self):
        for order, days in [(1, 0), (2, 1), (3, 29), (4, -1)]:
            self.add(order, 'Cancelled', st='Cancelled', orderDate=(self.today - timedelta(days=days)).isoformat())
        self.add(5, 'Own van', st='Scheduled')
        widget = dashboard_data.snapshot()['widgets']['cancelled']
        self.assertEqual(widget['total'], 1)
        self.assertEqual(widget['scope'], 'today')
        self.assertEqual([row['order'] for row in widget['preview']], ['1'])
        page = delivery_data.query_records(dashboard_widget='cancelled')
        self.assertEqual(page['total'], 1)
        self.assertEqual([row['order'] for row in page['deliveries']], ['1'])
        self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets('cancelled')), 1)

    def test_store_carrier_and_view_all_counts_agree_before_paging(self):
        for order in range(61):
            self.add(order, 'Charge Pending (Remote Postcode)', storeCode='AMAZON' if order < 60 else 'WILKO')
        data = dashboard_data.snapshot(store='Amazon')['widgets']['charge-pending']
        self.assertEqual(data['total'], 60)
        self.assertEqual(len(data['preview']), 3)
        pages = [delivery_data.query_records(dashboard_widget='charge-pending', store='Amazon', offset=offset, limit=25)
                 for offset in (0, 25, 50)]
        self.assertEqual([len(page['deliveries']) for page in pages], [25, 25, 10])
        self.assertTrue(all(page['total'] == data['total'] for page in pages))
        self.assertEqual(dashboard_data.snapshot(carrier='XDP')['widgets']['charge-pending']['total'], 0)
        facets = dashboard_data.widget_facets('charge-pending')
        self.assertEqual(sum(row['count'] for row in facets if row['purchaseStore'] == 'Amazon'), 60)

    def test_cancelled_month_uses_uk_calendar_month_and_matching_facets(self):
        first = self.today.replace(day=1)
        next_month = (first + timedelta(days=32)).replace(day=1)
        self.add(801, 'Cancelled', st='Cancelled', orderDate=self.today.isoformat())
        self.add(802, 'Cancelled', st='Cancelled', orderDate=first.isoformat())
        self.add(803, 'Cancelled', st='Cancelled', orderDate=(first - timedelta(days=1)).isoformat())
        self.add(804, 'Cancelled', st='Cancelled', orderDate=next_month.isoformat())
        self.add(805, 'Own van', st='Scheduled', orderDate=first.isoformat())
        self.add(806, 'Own van', st='Cancelled', orderDate=first.isoformat())
        result = delivery_data.query_records(dashboard_widget='cancelled-month')
        self.assertEqual(result['total'], 3)
        self.assertEqual({row['order'] for row in result['deliveries']}, {'801', '802', '806'})
        self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets('cancelled-month')), 3)
        self.assertEqual(delivery_data.query_records(dashboard_widget='cancelled-month', carrier='Cancelled')['total'], 2)

    def test_unknown_widget_rejected(self):
        with self.assertRaises(ValueError):
            delivery_data.query_records(dashboard_widget='unknown')

    def test_unbooked_reads_palletways_z_not_aa_and_excludes_delivered(self):
        from unittest.mock import Mock
        from google_sheets import read_palletways_tracking
        from palletways_sheet import archive_statuses
        delivery_data.archive([
            {'Order no': '1', 'Delivery method': 'Palletways', 'Status': 'C'},
            {'Order no': '2', 'Delivery method': 'Palletways', 'Status': 'P'},
            {'Order no': '3', 'Delivery method': 'Palletways', 'Status': 'X'},
            {'Order no': '4', 'Delivery method': 'Palletways', 'Status': 'P'},
        ])
        values = [['Customer Ref'] + [''] * 24 + ['Booked In', 'Book In Request']]
        for order, booked, request in [('1', 'no', 'Yes'), ('2', 'yes', 'No'),
                                       ('3', ' NO ', 'Yes'), ('4', '', 'No')]:
            values.append([order] + [''] * 24 + [booked, request])
        workbook = Mock()
        workbook.worksheet.return_value.get_all_values.return_value = values
        with patch('google_sheets.get_spreadsheet', return_value=workbook):
            archive_statuses(read_palletways_tracking())
        workbook.worksheet.assert_called_once_with('Palletways')
        widget = dashboard_data.snapshot()['widgets']['palletways-unbooked']
        self.assertEqual(widget['scope'], 'booked-in-no-current-ow-not-delivered')
        self.assertEqual(widget['total'], 1)
        self.assertEqual({row['order'] for row in widget['preview']}, {'3'})

    def test_unbooked_count_preview_paging_and_facets_exclude_delivered(self):
        statuses = ['Delivered', 'Cancelled', 'Return', 'Unscheduled']
        for order in range(40):
            self.add(order, 'Palletways', st=statuses[order % 4], palletwaysSheetBookedIn='no')
        widget = dashboard_data.snapshot()['widgets']['palletways-unbooked']
        self.assertEqual(widget['total'], 30)
        self.assertEqual(len(widget['preview']), 3)
        first = delivery_data.query_records(dashboard_widget='palletways-unbooked', limit=25)
        second = delivery_data.query_records(dashboard_widget='palletways-unbooked', limit=25, offset=25)
        self.assertEqual((first['total'], second['total']), (30, 30))
        self.assertEqual((len(first['deliveries']), len(second['deliveries'])), (25, 5))
        self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets('palletways-unbooked')), 30)

    def test_unbooked_excludes_delivered_using_sheet_status_then_fallback(self):
        for order, status, sheet_status in [(1, 'Scheduled', ' Delivered '), (2, 'Delivered', ''),
                                             (3, 'Delivered', 'In Transit'), (4, 'Scheduled', '')]:
            self.add(order, 'Palletways', st=status, palletwaysSheetStatus=sheet_status,
                     palletwaysSheetBookedIn='No', palletwaysDetails={'classification':'B2C'})
        for key in ('palletways-unbooked', 'palletways-unbooked-b2c'):
            result = delivery_data.query_records(dashboard_widget=key)
            self.assertEqual({row['order'] for row in result['deliveries']}, {'3', '4'})
            self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets(key)), 2)

    def test_unbooked_requires_exact_id_in_latest_sales_activity_column_a(self):
        from palletways_sheet import archive_statuses
        orders = [{'Order no': value, 'Delivery method': 'Palletways', 'Status': 'P'}
                  for value in ['123', '1234', '999']]
        delivery_data.archive(orders)
        archive_statuses([{'order': value, 'bookedIn': 'No'} for value in ['123', '1234', '999']])
        # A later successful OW snapshot contains 123 twice (two product rows).
        delivery_data.archive([orders[0], {**orders[0], 'Product SKU': 'EXTRA'}])
        widget = dashboard_data.snapshot()['widgets']['palletways-unbooked']
        self.assertEqual(widget['total'], 1)
        self.assertEqual([row['order'] for row in widget['preview']], ['123'])
        self.assertEqual(delivery_data.query_records(dashboard_widget='palletways-unbooked')['total'], 1)
        self.assertEqual(sum(row['count'] for row in dashboard_data.widget_facets('palletways-unbooked')), 1)
        # Missing source IDs stay in delivery history but not this widget.
        self.assertEqual(delivery_data.query_records()['total'], 3)
        delivery_data.archive([])
        self.assertEqual(dashboard_data.snapshot()['widgets']['palletways-unbooked']['total'], 0)
        self.assertEqual(delivery_data.query_records()['total'], 3)

    def test_failed_ow_read_retains_last_successful_membership(self):
        from palletways_sheet import archive_statuses
        delivery_data.archive([{'Order no': '123', 'Delivery method': 'Palletways', 'Status': 'P'}])
        archive_statuses([{'order': '123', 'bookedIn': 'No'}])
        with patch('google_sheets.read_sales_activity', side_effect=RuntimeError('Source unavailable')):
            with self.assertRaises(RuntimeError):
                delivery_data.sync(force=True)
        self.assertEqual(dashboard_data.snapshot()['widgets']['palletways-unbooked']['total'], 1)

    def test_unbooked_waits_for_first_successful_ow_snapshot(self):
        widget = dashboard_data.snapshot()['widgets']['palletways-unbooked']
        self.assertFalse(widget['available'])
        self.assertIsNone(widget['total'])
        self.assertEqual(widget['preview'], [])
        delivery_data.archive([])
        widget = dashboard_data.snapshot()['widgets']['palletways-unbooked']
        self.assertTrue(widget['available'])
        self.assertEqual(widget['total'], 0)

    def test_http_snapshot_and_tracking_cohort(self):
        self.add(1, 'Collect in Person')
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(delivery_data, 'cached_or_schedule_sync', return_value={'syncedAt': '2026-10-23T10:00:00Z'}):
                base = f'http://127.0.0.1:{http.server_port}'
                with urlopen(base + '/api/dashboard?store=Amazon') as response:
                    data = json.load(response)
                    self.assertEqual(data['widgets']['collect']['total'], 1)
                with urlopen(base + '/api/deliveries?dashboard_widget=collect&store=Amazon') as response:
                    data = json.load(response)
                    self.assertEqual(data['total'], 1)
                    self.assertEqual(sum(row['count'] for row in data['filterFacets']), 1)
        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
