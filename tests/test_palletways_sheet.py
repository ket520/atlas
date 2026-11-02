import unittest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import google_sheets
import palletways_sheet
import delivery_data


class PalletwaysSheetTests(unittest.TestCase):
    def test_reads_a_order_b_tracking_and_c_consignment_from_palletways_tab(self):
        book = Mock()
        book.worksheet.return_value.get_all_values.return_value = [
            ['Any order header', 'Any tracking header', 'Other'],
            [' 123 ', ' 60000000001 ', ' C-123 ', '', '', 'AT THE HUB'] + [''] * 19 + ['Booked value from Z', 'Request value from AA'], ['456'], [''],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=book):
            rows = google_sheets.read_palletways_tracking()
        book.worksheet.assert_called_once_with('Palletways')
        self.assertEqual(rows, [{'order': '123', 'trackingId': '60000000001', 'consignmentNumber': 'C-123', 'status': 'AT THE HUB', 'bookedIn': 'Booked value from Z', 'bookInRequest': 'Request value from AA'}, {'order': '456', 'trackingId': '', 'consignmentNumber': '', 'status': '', 'bookedIn': '', 'bookInRequest': ''}])

    def test_column_f_filters_preserve_general_status_and_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            rows = [{'Order no': order, 'Delivery method': 'Palletways', 'Status': 'P'} for order in ('123', '456')]
            delivery_data.archive(rows)
            palletways_sheet.archive_statuses([{'order': '123.0', 'status': 'AT THE HUB'}])
            def orders(status):
                return [item['order'] for item in delivery_data.query_records(carrier='Palletways', status=status, courier_status=True)['deliveries']]
            self.assertEqual(orders('palletways:AT THE HUB'), ['123'])
            self.assertEqual(orders('Scheduled'), ['456'])
            self.assertEqual(delivery_data.query_records(status='Scheduled')['total'], 2)
            self.assertTrue(any(item['palletwaysSheetStatus'] == 'AT THE HUB' for item in delivery_data.summary()['filterFacets']))
            delivery_data.archive(rows)
            self.assertEqual(orders('palletways:AT THE HUB'), ['123'])
            palletways_sheet.archive_statuses([{'order': '123', 'status': 'A'}, {'order': '123', 'status': 'B'}])
            self.assertEqual(len(orders('Scheduled')), 2)
            palletways_sheet.archive_statuses([{'order': '123', 'status': 'JOB COMPLETE'}])
            palletways_sheet.archive_statuses([])
            self.assertEqual(len(orders('Scheduled')), 2)

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
            no = delivery_data.query_records(carrier='Palletways', booked_in='no')
            self.assertEqual(no['total'], 9)
            self.assertNotIn('39', [item['order'] for item in no['deliveries']])
            self.assertEqual(delivery_data.query_records(booked_in='yes')['total'], 40)
            with self.assertRaises(ValueError):
                delivery_data.query_records(carrier='Palletways', book_in_request='unknown')

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
