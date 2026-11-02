import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import delivery_data
import google_sheets
import xdp_sheet


class XdpSheetTests(unittest.TestCase):
    def test_failure_statuses_join_failed_page_and_update_dynamically(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            source = [{'Order no': str(658883 + i), 'Delivery method': 'XDP', 'Status': 'Completed'} for i in range(4)]
            delivery_data.archive(source)
            rows = [{'order': str(658883 + i), 'status': status} for i, status in enumerate(['DAMAGE', 'DELETE', 'NOT RECEIVED', 'IN TRANSIT'])]
            xdp_sheet.archive(rows)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='XDP')['total'], 3)
            saved = delivery_data.detail('658883')
            self.assertEqual((saved['st'], saved['xdpStatus'], saved['statusSource']), ('Failed', 'DAMAGE', 'XDP'))
            delivery_data.archive(source)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='XDP')['total'], 3)
            rows[0]['status'] = 'IN TRANSIT'
            xdp_sheet.archive(rows)
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='XDP')['total'], 2)
            self.assertEqual(delivery_data.detail('658883')['st'], 'Awaiting')
            xdp_sheet.archive([])
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='XDP')['total'], 0)

    def test_xdp_consignments_header_maps_by_order_in_column_a(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ['Order no', 'Tracking ID', 'XDP Consignments'],
            ['123', 'OTHER-TRACKING', 'ZDBJSD020303'],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=spreadsheet):
            rows = google_sheets.read_xdp_statuses()
        self.assertEqual(rows[0]['consignmentNo'], 'ZDBJSD020303')
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': '123', 'Delivery method': 'XDP', 'Tracking No': 'OW-TRACKING'}])
            xdp_sheet.archive(rows)
            self.assertEqual(delivery_data.detail('123')['xdpConsignmentNo'], 'ZDBJSD020303')

    def test_consignment_uses_column_a_and_dedicated_header_with_no_tracking_fallback(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ['External reference', 'Tracking ID', 'Consignment No', 'Order no'],
            ['123', 'TRACK', 'CONSIGN-123', '999'],
            ['123', 'TRACK', 'CONSIGN-123', '999'],
            ['456', 'TRACK-2', 'CONFLICT-A', '456'],
            ['456', 'TRACK-2', 'CONFLICT-B', '456'],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=spreadsheet):
            rows = google_sheets.read_xdp_statuses()
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            source = [{'Order no': order, 'Delivery method': 'XDP', 'Tracking No': 'TRACK'} for order in ['123', '456', '789']]
            delivery_data.archive(source)
            xdp_sheet.archive(rows)
            saved = {row['order']: row for row in delivery_data.snapshot()}
            self.assertEqual(saved['123']['xdpConsignmentNo'], 'CONSIGN-123')
            self.assertNotIn('xdpConsignmentNo', saved['456'])
            self.assertNotIn('xdpConsignmentNo', saved['789'])
            source[0]['Tracking No'] = 'CHANGED-OW-TRACKING'
            delivery_data.archive(source)
            self.assertEqual(delivery_data.detail('123')['xdpConsignmentNo'], 'CONSIGN-123')
            xdp_sheet.archive([])
            self.assertNotIn('xdpConsignmentNo', delivery_data.detail('123'))

    def test_ow_completed_cannot_confirm_xdp_delivery(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            delivery_data.archive([{'Order no': '658505', 'Delivery method': 'XDP', 'Status': 'Completed'}])
            saved = delivery_data.detail('658505')
            self.assertEqual((saved['st'], saved['statusSource']), ('Awaiting', 'XDP fallback'))
            self.assertEqual(saved['rawStatus'], 'Completed')
            self.assertEqual(delivery_data.query_records(status='Delivered')['total'], 0)
            self.assertEqual(delivery_data.query_records(carrier='XDP', status='Awaiting', courier_status=True)['total'], 1)
            xdp_sheet.archive([{'order': '658505', 'status': 'DELIVERED'}])
            self.assertEqual(delivery_data.query_records(carrier='XDP', status='xdp:DELIVERED', courier_status=True)['total'], 1)

    def test_column_t_documents_split_ignore_placeholders_and_survive_source_failure(self):
        one = 'https://xdp.sysx.co.uk/pod/view/1792022400/Zmlyc3QuanBn'
        two = 'https://xdp.sysx.co.uk/pod/view/1792022400/c2Vjb25kLnBuZw=='
        cell = f'https://xdp.sysx.co.uk/pod/view//\n{one}\r\n{two}\n{one}'
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ['Order no', 'Tracking ID'], ['123', 'TRACK'] + [''] * 17 + [cell, '001234567890\nZDBJSD020172-2'],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=spreadsheet):
            rows = google_sheets.read_xdp_statuses()
        self.assertEqual(rows[0]['documents'], cell)
        self.assertEqual(rows[0]['parcelBarcode'], '001234567890\nZDBJSD020172-2')
        self.assertEqual(xdp_sheet.document_urls(cell), [one, two])
        self.assertEqual(xdp_sheet.document_urls('https://xdp.sysx.co.uk/pod/view//'), [])
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            ow = [{'Order no': '123', 'Delivery method': 'XDP', 'Tracking No': 'TRACK'}]
            delivery_data.archive(ow)
            xdp_sheet.archive(rows)
            self.assertEqual(delivery_data.detail('123')['xdpDocuments'], [one, two])
            self.assertEqual(delivery_data.detail('123')['xdpParcelBarcodes'], ['001234567890', 'ZDBJSD020172-2'])
            delivery_data.archive(ow)  # A later failed sheet read retains these documents.
            self.assertEqual(delivery_data.detail('123')['xdpParcelBarcodes'], ['001234567890', 'ZDBJSD020172-2'])
            self.assertEqual(delivery_data.detail('123')['xdpDocuments'], [one, two])
            xdp_sheet.archive([{'order': '123', 'documents': ''}])
            self.assertEqual(delivery_data.detail('123')['xdpDocuments'], [])

    def test_document_download_returns_image_and_rejects_invalid_links(self):
        import io
        from email.message import Message

        handler = Mock()
        handler.wfile = io.BytesIO()
        image = io.BytesIO(b'original-image')
        image.headers = Message()
        image.headers['Content-Type'] = 'image/png'
        record = {'carrier': 'XDP', 'xdpDocuments': ['https://xdp.sysx.co.uk/pod/view/1792022400/aW1hZ2UucG5n']}
        with patch('delivery_data.detail', return_value=record), patch.object(xdp_sheet, 'urlopen', return_value=image):
            xdp_sheet.serve_document(handler, {'order': ['123'], 'download': ['1']})
        self.assertEqual(handler.wfile.getvalue(), b'original-image')
        handler.send_header.assert_any_call('Content-Disposition', 'attachment; filename="xdp-document-1.png"')
        record['xdpDocuments'] = ['https://xdp.sysx.co.uk/pod/view//']
        with patch('delivery_data.detail', return_value=record), patch.object(xdp_sheet, 'urlopen') as network:
            xdp_sheet.serve_document(handler, {'order': ['123']})
            network.assert_not_called()
            self.assertEqual(handler.send_json.call_args.args[0], 404)

    def test_reads_column_i_from_main_workbook_xdp_tab(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ["Order no", "Tracking ID", "C", "D", "E", "F", "G", "H", "Status"],
            ["123", "TRACK", "", "", "", "", "", "", "EXCEPTION", "DriverX Status: Delivered"],
        ]
        with patch.object(google_sheets, "get_spreadsheet", return_value=spreadsheet) as read:
            self.assertEqual(google_sheets.read_xdp_statuses(), [{"order": "123", "trackingId": "TRACK", "consignmentOrder": "123", "consignmentNo": "TRACK", "status": "EXCEPTION", "latestDetail": "DriverX Status: Delivered", "documents": "", "parcelBarcode": ""}])
        read.assert_called_once_with()
        spreadsheet.worksheet.assert_called_once_with("XDP")

    def test_specific_status_and_fallback_do_not_change_shared_categories(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            rows = [{"Order no": order, "Delivery method": "XDP", "Tracking No": order, "Status": "P"} for order in ("123", "456", "789")]
            delivery_data.archive(rows)
            xdp_sheet.archive([{"order": "123", "status": "EXCEPTION"}, {"trackingId": "456", "status": "DELIVERED"}])
            def orders(status):
                return [item["order"] for item in delivery_data.query_records(carrier="XDP", status=status, courier_status=True)["deliveries"]]
            self.assertEqual(orders("xdp:EXCEPTION"), ["123"])
            self.assertEqual(orders("xdp:DELIVERED"), ["456"])
            self.assertEqual(orders("Awaiting"), ["789"])
            self.assertEqual(delivery_data.query_records(status="Awaiting")["total"], 3)
            self.assertTrue(any(item["xdpStatus"] == "EXCEPTION" for item in delivery_data.summary()["filterFacets"]))
            delivery_data.archive(rows)
            self.assertEqual(orders("xdp:EXCEPTION"), ["123"])
            xdp_sheet.archive([{"order": "123", "status": "EXCEPTION"}, {"order": "123", "status": "DELIVERED"}])
            self.assertEqual(len(orders("Awaiting")), 3)
