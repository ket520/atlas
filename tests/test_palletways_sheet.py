import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import google_sheets
import palletways_sheet
import delivery_data


class PalletwaysSheetTests(unittest.TestCase):
    def test_invoice_waiting_uses_ow_only_for_absent_sheet_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            rows = [{'Order no': order, 'Delivery method': 'Next Day (Pallet)',
                     'Status': 'Invoice waiting to be printed'} for order in ('123', '456')]
            delivery_data.archive(rows)
            palletways_sheet.archive_statuses([{'order': '456', 'status': ''}])
            delivery_data.archive(rows)
            with delivery_data.connect() as db:
                db.execute("UPDATE deliveries SET payload=json_set(payload,'$.st','Delivered')")
            result = delivery_data.query_records(carrier='Palletways', status='Invoice waiting to be printed', courier_status=True)
            self.assertEqual([row['order'] for row in result['deliveries']], ['123'])
            facets = delivery_data.summary()['filterFacets']
            self.assertEqual({row['palletwaysSheetMatched'] for row in facets}, {0, 1})

    def test_not_assigned_maps_to_specific_unscheduled_without_changing_global_status(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([
                {'Order no': '123', 'Delivery method': 'Palletways', 'Status': 'C'},
                {'Order no': '456', 'Delivery method': 'Palletways', 'Status': 'W'},
            ])
            palletways_sheet.archive_statuses([{'order': order, 'status': 'Palletways Not Assigned'} for order in ('123', '456')])
            result = delivery_data.query_records(carrier='Palletways', status='Unscheduled', courier_status=True)
            self.assertEqual({row['order'] for row in result['deliveries']}, {'123', '456'})
            self.assertEqual(delivery_data.query_records(carrier='Palletways', status='Delivered', courier_status=True)['total'], 0)
            self.assertEqual(delivery_data.query_records(status='Delivered')['total'], 1)
            self.assertEqual(delivery_data.query_records(status='Unscheduled')['total'], 1)

    def test_reads_a_order_b_tracking_and_c_consignment_from_palletways_tab(self):
        book = Mock()
        book.worksheet.return_value.get_all_values.return_value = [
            ['Any order header', 'Any tracking header', 'Other'],
            [' 123 ', ' 60000000001 ', ' C-123 ', '', '', 'AT THE HUB'] + [''] * 19 + ['Booked value from Z', 'Request value from AA'] + [''] * 44 + [' 05/11/2026 ', ' 14:30 '], ['456'], [''],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=book):
            rows = google_sheets.read_palletways_tracking()
        book.worksheet.assert_called_once_with('Palletways')
        self.assertEqual(rows, [{'order': '123', 'trackingId': '60000000001', 'consignmentNumber': 'C-123', 'status': 'AT THE HUB', 'bookedIn': 'Booked value from Z', 'bookInRequest': 'Request value from AA', 'bookInDate': '05/11/2026', 'bookInTime': '14:30'}, {'order': '456', 'trackingId': '', 'consignmentNumber': '', 'status': '', 'bookedIn': '', 'bookInRequest': '', 'bookInDate': '', 'bookInTime': ''}])

    def test_booking_date_time_join_survives_refresh_and_clears_conflicts(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            orders = [{'Order no': order, 'Delivery method': 'Palletways', 'Status': 'P'} for order in ('123', '1234')]
            delivery_data.archive(orders)
            palletways_sheet.archive_statuses([
                {'order': '123.0', 'bookedIn': 'Yes', 'bookInDate': '05/11/2026', 'bookInTime': '14:30'},
                {'order': '1234', 'bookedIn': 'Yes', 'bookInDate': '06/11/2026', 'bookInTime': '09:00'},
            ])
            delivery_data.archive(orders)
            saved = {item['order']: item for item in delivery_data.snapshot()}
            self.assertEqual((saved['123']['palletwaysSheetBookInDate'], saved['123']['palletwaysSheetBookInTime']), ('05/11/2026', '14:30'))
            self.assertEqual((saved['1234']['palletwaysSheetBookInDate'], saved['1234']['palletwaysSheetBookInTime']), ('06/11/2026', '09:00'))
            palletways_sheet.archive_statuses([
                {'order': '123', 'bookedIn': 'Yes', 'bookInDate': '05/11/2026', 'bookInTime': '14:30'},
                {'order': '123', 'bookedIn': 'Yes', 'bookInDate': '06/11/2026', 'bookInTime': '15:30'},
            ])
            saved = {item['order']: item for item in delivery_data.snapshot()}
            self.assertNotIn('palletwaysSheetBookInDate', saved['123'])
            self.assertNotIn('palletwaysSheetBookInTime', saved['123'])
            self.assertNotIn('palletwaysSheetBookInDate', saved['1234'])
            self.assertNotIn('palletwaysSheetBookInTime', saved['1234'])

    def test_column_f_filters_fall_back_to_ow_only_when_order_absent(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            rows = [{'Order no': order, 'Delivery method': 'Palletways', 'Status': 'P'} for order in ('123', '456')]
            delivery_data.archive(rows)
            palletways_sheet.archive_statuses([{'order': '123.0', 'status': 'AT THE HUB'}])
            def orders(status):
                return [item['order'] for item in delivery_data.query_records(carrier='Palletways', status=status, courier_status=True)['deliveries']]
            self.assertEqual(orders('palletways:AT THE HUB'), ['123'])
            self.assertEqual(orders('P'), ['456'])
            self.assertEqual(orders('palletways:Status unavailable'), [])
            self.assertEqual(delivery_data.query_records(status='Scheduled')['total'], 2)
            self.assertTrue(any(item['palletwaysSheetStatus'] == 'AT THE HUB' for item in delivery_data.summary()['filterFacets']))
            delivery_data.archive(rows)
            self.assertEqual(orders('palletways:AT THE HUB'), ['123'])
            palletways_sheet.archive_statuses([{'order': '123', 'status': 'A'}, {'order': '123', 'status': 'B'}])
            self.assertEqual(orders('P'), ['456'])
            palletways_sheet.archive_statuses([{'order': '123', 'status': 'JOB COMPLETE'}])
            palletways_sheet.archive_statuses([])
            self.assertEqual(set(orders('P')), {'123', '456'})

    def test_matches_exact_order_reuses_cache_and_can_refresh(self):
        with patch.object(palletways_sheet, '_rows', None), patch.object(palletways_sheet, '_read_at', 0), patch(
            'google_sheets.read_palletways_tracking', return_value=[
                {'order': '123.0', 'trackingId': '60000000001'},
                {'order': '1234', 'trackingId': '60000000002'},
            ]
        ) as read:
            self.assertEqual(palletways_sheet.tracking_for_order('123')['trackingId'], '60000000001')
            self.assertEqual(palletways_sheet.tracking_for_order('1234')['trackingId'], '60000000002')
            self.assertEqual(read.call_count, 1)
            palletways_sheet.tracking_for_order('123', force=True)
            self.assertEqual(read.call_count, 2)

    def test_consignment_column_c_is_separate_from_tracking_and_retained(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            rows = [{'Order no': '123', 'Delivery method': 'Palletways', 'Status': 'P'}]
            delivery_data.archive(rows)
            palletways_sheet.archive_statuses([{'order': '123.0', 'trackingId': '60000000001', 'consignmentNumber': 'C-123', 'status': 'AT THE HUB'}])
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetConsignmentNumber'], 'C-123')
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetTrackingNumber'], '60000000001')
            delivery_data.archive(rows)
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetConsignmentNumber'], 'C-123')
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetTrackingNumber'], '60000000001')
            palletways_sheet.archive_statuses([{'order': '123', 'trackingId': '60000000001', 'consignmentNumber': '1'}, {'order': '123', 'trackingId': '60000000001', 'consignmentNumber': '2'}])
            self.assertNotIn('palletwaysSheetConsignmentNumber', delivery_data.snapshot()[0])
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetTrackingNumber'], '60000000001')
            palletways_sheet.archive_statuses([{'order': '123', 'trackingId': '60000000001', 'consignmentNumber': ''}])
            self.assertNotIn('palletwaysSheetConsignmentNumber', delivery_data.snapshot()[0])
            palletways_sheet.archive_statuses([{'order':'123','trackingId':'60000000001','consignmentNumber':'C-123'},
                                               {'order':'123','trackingId':'60000000002','consignmentNumber':'C-123'}])
            self.assertNotIn('palletwaysSheetTrackingNumber', delivery_data.snapshot()[0])
            self.assertEqual(delivery_data.snapshot()[0]['palletwaysSheetConsignmentNumber'], 'C-123')

    def test_missing_and_conflicting_tracking_are_not_guessed(self):
        for rows in [[], [{'order': '123', 'trackingId': 'wrong'}],
                     [{'order': '123', 'trackingId': '60000000001'}, {'order': '123', 'trackingId': '60000000002'}]]:
            with patch.object(palletways_sheet, '_rows', None), patch('google_sheets.read_palletways_tracking', return_value=rows):
                with self.assertRaises(ValueError):
                    palletways_sheet.tracking_for_order('123')

    def test_booking_filters_apply_before_paging_and_combine(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': str(order), 'Delivery method': 'Palletways', 'Status': 'P'} for order in range(40)])
            palletways_sheet.archive_statuses([
                {'order': str(order), 'bookedIn': ' YES ' if order < 30 else 'no',
                 'bookInRequest': 'No' if order % 2 else 'Yes'} for order in range(39)
            ])
            page = delivery_data.query_records(carrier='Palletways', booked_in='yes', limit=25)
            self.assertEqual((page['total'], len(page['deliveries']), page['hasMore']), (30, 25, True))
            second = delivery_data.query_records(carrier='Palletways', booked_in='yes', limit=25, offset=25)
            self.assertEqual(len(second['deliveries']), 5)
            self.assertFalse({item['order'] for item in page['deliveries']} & {item['order'] for item in second['deliveries']})
            combined = delivery_data.query_records(carrier='Palletways', booked_in='yes', book_in_request='no')
            self.assertEqual(combined['total'], 15)
            self.assertTrue(all(int(item['order']) < 30 and int(item['order']) % 2 for item in combined['deliveries']))
            no = delivery_data.query_records(carrier='Palletways', booked_in='not-yet')
            self.assertEqual(no['total'], 9)
            self.assertNotIn('39', [item['order'] for item in no['deliveries']])
            self.assertEqual(delivery_data.query_records(booked_in='yes')['total'], 40)
            with self.assertRaises(ValueError):
                delivery_data.query_records(carrier='Palletways', book_in_request='unknown')

    def test_booked_in_no_is_next_day_and_not_yet_is_other_services(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([
                {'Order no': '123', 'Delivery method': 'Palletways Next Day', 'Status': 'P'},
                {'Order no': '456', 'Delivery method': 'Palletways', 'Status': 'P'},
                {'Order no': '789', 'Delivery method': 'Palletways BQ', 'Status': 'P'},
            ])
            palletways_sheet.archive_statuses([
                {'order': '123', 'bookedIn': 'No'},
                {'order': '456', 'bookedIn': 'No'},
                {'order': '789', 'bookedIn': 'Yes'},
            ])
            for selected, expected in [('no', ['123']), ('not-yet', ['456']), ('yes', ['789'])]:
                result = delivery_data.query_records(carrier='Palletways', booked_in=selected)
                self.assertEqual([row['order'] for row in result['deliveries']], expected)
                self.assertEqual(result['total'], 1)
            with self.assertRaises(ValueError):
                delivery_data.query_records(carrier='Palletways', book_in_request='not-yet')

    def test_sheet_booking_matches_exact_order_and_survives_ow_refresh(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            orders = [{'Order no': order, 'Delivery method': 'Palletways', 'Status': 'P'} for order in ('123', '1234')]
            delivery_data.archive(orders)
            palletways_sheet.archive_statuses([
                {'order': '123.0', 'bookedIn': 'Yes', 'bookInRequest': 'No'},
                {'order': '1234', 'bookedIn': 'No', 'bookInRequest': 'Yes'},
            ])
            delivery_data.archive(orders)
            saved = {item['order']: item for item in delivery_data.snapshot()}
            self.assertEqual((saved['123']['palletwaysSheetBookedIn'], saved['123']['palletwaysSheetBookInRequest']), ('Yes', 'No'))
            self.assertEqual((saved['1234']['palletwaysSheetBookedIn'], saved['1234']['palletwaysSheetBookInRequest']), ('No', 'Yes'))
            palletways_sheet.archive_statuses([
                {'order': '123', 'bookedIn': 'Yes', 'bookInRequest': ''},
                {'order': '123', 'bookedIn': 'No', 'bookInRequest': ''},
            ])
            saved = {item['order']: item for item in delivery_data.snapshot()}
            self.assertNotIn('palletwaysSheetBookedIn', saved['123'])
            self.assertEqual(saved['123']['palletwaysSheetBookInRequest'], '')
