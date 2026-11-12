import json
import tempfile
import unittest
from datetime import date
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import Mock, patch

import delivery_data
import routine_live


def grid_cell(value, colour=None):
    cell = {'formattedValue': value}
    if colour:
        rgb = {name: int(colour[i:i + 2], 16) / 255
               for name, i in [('red', 1), ('green', 3), ('blue', 5)]}
        cell['effectiveFormat'] = {'backgroundColorStyle': {'rgbColor': rgb}}
    return cell


class RoutineLiveReaderTests(unittest.TestCase):
    def test_booking_shorthand_and_dates(self):
        today = date(2026, 10, 22)
        examples = {
            'Del Fri': 'Delay to 23-Oct-2026',
            'del thurs': 'Delay to 22-Oct-2026',
            'del mon': 'Delay to 26-Oct-2026',
            'o/s': 'Out of Stock',
            'o/s & ND': 'Out of Stock & ND',
            '23-Oct': '23-Oct-2026',
            'partial delivered 5/10': 'Partial delivered 5-Oct-2026',
            'failed 10/1': 'Failed 10-Jan-2026',
            'partial delivered 5/5': 'Partial delivered 5-May-2026',
            '27/10/2025': '27-Oct-2025',
            'failed 31/2': 'Failed 31/2',
            'Awaiting a call': 'Awaiting a call',
            '': '',
        }
        for source, expected in examples.items():
            with self.subTest(source=source):
                self.assertEqual(routine_live.format_booking_status(source, today), expected)
        self.assertEqual(routine_live.format_booking_status('23-Oct', date(2027, 1, 1)), '23-Oct-2027')
        self.assertEqual(routine_live.format_booking_status('del fri', date(2026, 12, 31)), 'Delay to 1-Jan-2027')

    def test_newline_orders_share_status_and_booking_but_same_line_references_do_not(self):
        value = '659669\n659670\r\n659631 - 601216\n650410-59696.remainder\n659669'
        values = [['HYGIENIC ORDERS'], [value, '', '', '', 'Awaiting a call'], ['XDP - Long Parcels']]
        metadata = {'sheets': [{'properties': {'title': routine_live.TAB}, 'data': [{'startRow': 1,
                    'rowData': [{'values': [grid_cell(value, '#FFFF00')]}]}]}]}
        expected = ['659669', '659670', '659631', '650410']
        statuses = routine_live.status_rows(values, metadata)
        bookings = routine_live.booking_rows(values)
        self.assertEqual([row['order'] for row in statuses], expected)
        self.assertTrue(all(row['status'] == 'Failed' and row['cell'] == 'A2' for row in statuses))
        self.assertEqual([row['order'] for row in bookings], expected)
        self.assertTrue(all(row['bookingStatus'] == 'Awaiting a call' for row in bookings))

    def test_booking_values_use_e_and_first_six_digits_without_redefining_values(self):
        values = [['HYGIENIC ORDERS'], ['659631 - 601216', '', '', '', 'Awaiting a call'],
                  ['650410-59696.remainder', '', '', '', '27/10/2026'],
                  ['659783', '', '', '', ''], ['', '', '', '', 'Not an order'], ['XDP - Long Parcels']]
        self.assertEqual(routine_live.booking_rows(values), [
            {'order': '659631', 'bookingStatus': 'Awaiting a call', 'cell': 'E2'},
            {'order': '650410', 'bookingStatus': '27/10/2026', 'cell': 'E3'},
            {'order': '659783', 'bookingStatus': '', 'cell': 'E4'},
        ])

    def test_exact_colours_first_six_digits_and_marker_boundaries(self):
        values = [['111111'], ['HYGIENIC ORDERS'], ['659631 - 601216'],
                  ['650410-59696.remainder'], ['659783'], ['659787'], ['659660'],
                  [''], ['Headings'], ['659999'], ['XDP - Long Parcels'], ['222222']]
        cells = [grid_cell(row[0], colour) for row, colour in zip(values,
                 ['#FFFF00', '#FFFF00', '#FFFF00', '#FFFFFF', '#FFC000', '#FFE598',
                  '#00B0F0', '#FFFFFF', '#FFFFFF', None, '#FFFF00', '#FFFF00'])]
        # Extra-column order numbers and fills must not become order overrides.
        metadata = {'sheets': [{'properties': {'title': routine_live.TAB},
                    'data': [{'startRow': 0, 'rowData': [{'values': [cell, grid_cell('333333', '#FFFF00')]}
                                                       for cell in cells]}]}]}
        result = routine_live.status_rows(values, metadata)
        self.assertEqual([(row['order'], row['status'], row['colour'], row['cell']) for row in result], [
            ('659631', 'Failed', '#FFFF00', 'A3'),
            ('650410', 'Scheduled', '#FFFFFF', 'A4'),
            ('659783', 'Scheduled', '#FFC000', 'A5'),
            ('659999', 'Scheduled', '#FFFFFF', 'A10'),
        ])
        self.assertNotIn('601216', {row['order'] for row in result})

    def test_invalid_range_or_missing_format_data_is_not_an_empty_snapshot(self):
        for values in [[], [['HYGIENIC ORDERS']], [['HYGIENIC ORDERS'], ['XDP - Long Parcels']],
                       [['HYGIENIC ORDERS'], ['HYGIENIC ORDERS'], ['XDP - Long Parcels']]]:
            with self.assertRaises(ValueError):
                routine_live.section_bounds(values)
        values = [['HYGIENIC ORDERS'], ['659631'], ['XDP - Long Parcels']]
        for metadata in [{}, {'sheets': [{'properties': {'title': routine_live.TAB}, 'data': [{}]}]}]:
            with self.assertRaises(ValueError):
                routine_live.status_rows(values, metadata)

    def test_theme_colours_and_fixed_a_range(self):
        values = [['Other section'], ['HYGIENIC ORDERS'], ['659631'], ['XDP - Long Parcels']]
        metadata = {'properties': {'spreadsheetTheme': {'themeColors': [
            {'colorType': 'ACCENT1', 'colorStyle': {'rgbColor': {'red': 1, 'green': 1}}}]}},
            'sheets': [{'properties': {'title': routine_live.TAB}, 'data': [{'startRow': 2,
                'rowData': [{'values': [{'formattedValue': '659631', 'effectiveFormat': {
                    'backgroundColorStyle': {'themeColor': 'ACCENT1'}}}]}]}]}]}
        book = Mock()
        book.worksheet.return_value.get_all_values.return_value = values
        book.fetch_sheet_metadata.return_value = metadata
        with patch('google_sheets.get_spreadsheet', return_value=book):
            result = routine_live.read_status_rows()
        self.assertEqual(result[0]['status'], 'Failed')
        self.assertEqual(book.fetch_sheet_metadata.call_args.kwargs['params']['ranges'],
                         "'Routine Dashboard - Live'!A3:A3")


class RoutineLiveStatusTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.patch_db = patch.object(delivery_data, 'configured_db_path', return_value=Path(self.directory.name) / 'test.sqlite3')
        self.patch_db.start()

    def tearDown(self):
        self.patch_db.stop()
        self.directory.cleanup()

    def record(self, order):
        return next(row for row in delivery_data.snapshot() if row['order'] == order)

    def test_booking_e_updates_clears_and_outranks_legacy_for_own_van_only(self):
        source = [{'Order no': order, 'Delivery method': method, 'Status': 'P'}
                  for order, method in [('659631', 'Own van'), ('659632', 'Self Delivery')]]
        delivery_data.archive(source)
        delivery_data.archive_routine_dashboard([{'Order ID': '659631', 'Status': 'Legacy booking'},
                                               {'Order ID': '659632', 'Status': 'Self booking'}])
        delivery_data.archive_routine_live([], booking_rows=[
            {'order': '659631', 'bookingStatus': 'Awaiting a call'},
            {'order': '659632', 'bookingStatus': 'Not for Self Delivery'}])
        self.assertEqual(self.record('659631')['bookingStatus'], 'Awaiting a call')
        self.assertEqual(self.record('659631')['bookingStatusSource'], routine_live.TAB)
        self.assertEqual(self.record('659632')['bookingStatus'], 'Self booking')
        # Imports from the previous booking source cannot replace the live E value.
        delivery_data.archive(source)
        delivery_data.archive_routine_dashboard([{'Order ID': '659631', 'Status': 'Old source again'}])
        self.assertEqual(self.record('659631')['bookingStatus'], 'Awaiting a call')
        delivery_data.archive_routine_live([], booking_rows=[{'order': '659631', 'bookingStatus': '27/10/2026'}])
        self.assertEqual(self.record('659631')['bookingStatus'], '27-Oct-2026')
        delivery_data.archive_routine_live([], booking_rows=[{'order': '659631', 'bookingStatus': ''}])
        self.assertEqual(self.record('659631')['bookingStatus'], '')
        delivery_data.archive_routine_live([], booking_rows=[{'order': '659631', 'bookingStatus': 'New booking'}])
        delivery_data.archive_routine_live([], booking_rows=[])
        delivery_data.archive_routine_dashboard([{'Order ID': '659631', 'Status': 'Must stay cleared'}])
        self.assertEqual(self.record('659631')['bookingStatus'], '')

    def test_conflicting_duplicate_e_values_are_not_guessed(self):
        delivery_data.archive([{'Order no': '659631', 'Delivery method': 'Own van', 'Status': 'P'}])
        delivery_data.archive_routine_live([], booking_rows=[{'order': '659631', 'bookingStatus': value}
                                                            for value in ['ASAP', 'On hold']])
        self.assertEqual(self.record('659631')['bookingStatus'], '')

    def test_priority_dynamic_change_removal_and_own_van_only(self):
        source = [{'Order no': str(659631 + i), 'Delivery method': method, 'Status': 'P'}
                  for i, method in enumerate(['Own van', 'Self Delivery', 'LOCAL MULTIDROP', 'AMA XL', 'Palletways'])]
        delivery_data.archive(source)
        overlays = [{'order': row['Order no'], 'status': 'Failed', 'colour': '#FFFF00', 'cell': 'A4'} for row in source]
        self.assertEqual(delivery_data.archive_routine_live(overlays), 1)
        self.assertEqual((self.record('659631')['st'], self.record('659631')['statusSource']),
                         ('Failed', routine_live.TAB))
        for order in ['659632', '659633', '659634', '659635']:
            self.assertNotIn('routineLiveStatus', self.record(order))
        self.assertEqual(delivery_data.query_records(carrier='Own van', status='Failed')['total'], 1)
        self.assertEqual(delivery_data.summary()['failedTotal'], 1)
        # A normal OW refresh must not remove the existing override.
        source[0]['Status'] = 'C'
        delivery_data.archive(source)
        self.assertEqual(self.record('659631')['st'], 'Failed')
        delivery_data.archive_routine_live([{'order': '659631', 'status': 'Scheduled', 'colour': '#FFFFFF'}])
        self.assertEqual(self.record('659631')['st'], 'Scheduled')
        delivery_data.archive_routine_live([])
        self.assertEqual((self.record('659631')['st'], self.record('659631')['statusSource']), ('Delivered', 'OW'))
        self.assertNotIn('routineLiveStatus', self.record('659631'))

    def test_optimo_page_detail_restart_and_fallback_keep_priority(self):
        source = [{'Order no': '659631', 'Order reference': 'REF-1', 'Delivery method': 'Own van', 'Status': 'P'}]
        delivery_data.archive(source)
        delivery_data.archive_routine_live([{'order': '659631', 'status': 'Failed', 'colour': '#FFFF00'}])
        def api(method, body):
            if method == 'search_orders':
                return {'orders': [{'id': 'OPT-1', 'data': {'orderNo': 'REF-1', 'date': '2026-10-22'},
                                    'scheduleInformation': {'driverName': 'Driver'}}]}
            return {'orders': [{'id': 'OPT-1', 'data': {'status': 'success'}}]}
        with patch('server.api', side_effect=api), patch('activity_log.archive_records'), patch('activity_log.history', return_value={'entries': []}):
            self.assertEqual(delivery_data.enrich_optimoroute_today(), 1)
            self.assertEqual(self.record('659631')['st'], 'Failed')
            with delivery_data.connect() as db:
                row = self.record('659631')
                row.pop('providerCheckedAt', None)
                db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(row), '659631'))
                db.commit()
            page = delivery_data.query_records(carrier='Own van', refresh_provider=True)
            self.assertEqual(page['deliveries'][0]['st'], 'Failed')
            self.assertEqual(page['deliveries'][0]['providerStatus'], 'success')
            self.assertEqual(delivery_data.detail('659631')['st'], 'Failed')
        with patch.object(delivery_data, '_statuses_refreshed', False), patch.object(delivery_data, 'sync', return_value={}):
            delivery_data.current_or_sync()
        self.assertEqual(self.record('659631')['st'], 'Failed')
        delivery_data.archive_routine_live([])
        self.assertEqual((self.record('659631')['st'], self.record('659631')['statusSource']), ('Delivered', 'OptimoRoute'))

    def test_failed_duplicate_wins_and_unmatched_orders_keep_normal_status(self):
        delivery_data.archive([{'Order no': order, 'Delivery method': 'Own van', 'Status': status}
                               for order, status in [('659631', 'P'), ('659787', 'FAILED')]])
        delivery_data.archive_routine_live([{'order': '659631', 'status': 'Scheduled'},
                                          {'order': '659631', 'status': 'Failed'}])
        self.assertEqual(self.record('659631')['st'], 'Failed')
        self.assertEqual((self.record('659787')['st'], self.record('659787')['statusSource']), ('Failed', 'OW'))

    def test_scheduled_override_holds_over_provider_failure_then_restores_it(self):
        delivery_data.archive([{'Order no': '659631', 'Delivery method': 'Own van', 'Status': 'P'}])
        delivery_data.archive_routine_live([{'order': '659631', 'status': 'Scheduled'}])
        record = self.record('659631')
        record.update(providerStatus='failed', st='Failed', statusSource='OptimoRoute')
        delivery_data.apply_routine_live_status(record)
        with delivery_data.connect() as db:
            db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(record), '659631'))
            db.commit()
        self.assertEqual(delivery_data.query_records(status='Scheduled')['total'], 1)
        self.assertEqual(delivery_data.query_records(issue_cases=True)['total'], 0)
        delivery_data.archive_routine_live([])
        self.assertEqual((self.record('659631')['st'], self.record('659631')['statusSource']), ('Failed', 'OptimoRoute'))

    def test_stale_provider_payload_uses_current_authoritative_snapshot(self):
        delivery_data.archive([{'Order no': '659631', 'Delivery method': 'Own van', 'Status': 'P'}])
        stale = self.record('659631')
        delivery_data.archive_routine_live([{'order': '659631', 'status': 'Failed'}])
        stale.update(providerStatus='success', st='Delivered', statusSource='OptimoRoute')
        with delivery_data.connect() as db:
            delivery_data.apply_routine_live_status(stale, db)
            self.assertEqual(stale['st'], 'Failed')
        stale = self.record('659631')
        delivery_data.archive_routine_live([])
        with delivery_data.connect() as db:
            delivery_data.apply_routine_live_status(stale, db)
            self.assertEqual(stale['st'], 'Scheduled')
            self.assertNotIn('routineLiveStatus', stale)

    def test_successful_empty_read_clears_but_failed_read_retains(self):
        source = [{'Order no': '659631', 'Delivery method': 'Own van', 'Status': 'P'}]
        with ExitStack() as stack:
            for name, result in [('read_sales_activity', source), ('read_stopstart', []),
                ('read_xdp_statuses', []), ('read_xdp_activity', []), ('read_amazon_shipping', []),
                ('read_palletways_tracking', []), ('read_courier_issues', {})]:
                stack.enter_context(patch('google_sheets.' + name, return_value=result))
            stack.enter_context(patch('palletways_live.sync_delta', return_value={'ok': True}))
            stack.enter_context(patch.object(delivery_data, 'apply_palletways_api_data', return_value=0))
            stack.enter_context(patch('routine_dashboard.read_booking_rows', return_value=[]))
            stack.enter_context(patch.object(delivery_data, 'enrich_optimoroute_today', return_value=0))
            stack.enter_context(patch.dict(delivery_data._cache, {'at': None, 'payload': None}))
            with patch('routine_live.read_live_snapshot', return_value={'statuses': [{'order': '659631', 'status': 'Failed'}],
                       'bookings': [{'order': '659631', 'bookingStatus': 'Awaiting a call'}]}):
                result = delivery_data.sync(force=True)
                self.assertEqual(result['routineLiveMatched'], 1)
            with patch('routine_live.read_live_snapshot', side_effect=RuntimeError('unavailable')):
                result = delivery_data.sync(force=True)
                self.assertTrue(result['routineLiveUnavailable'])
                self.assertEqual(self.record('659631')['st'], 'Failed')
                self.assertEqual(self.record('659631')['bookingStatus'], 'Awaiting a call')
            with patch('routine_live.read_live_snapshot', return_value={'statuses': [], 'bookings': []}):
                result = delivery_data.sync(force=True)
                self.assertFalse(result['routineLiveUnavailable'])
                self.assertEqual((self.record('659631')['st'], self.record('659631')['statusSource']), ('Scheduled', 'OW'))
                self.assertEqual(self.record('659631')['bookingStatus'], '')


if __name__ == '__main__':
    unittest.main()
