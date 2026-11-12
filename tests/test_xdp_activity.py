import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import delivery_data
import google_sheets
import xdp_sheet


def event(identifier, day, clock, kind, text='', order='655824', tracking='ZDBJSD020303'):
    return (f'<consignment><id>{identifier}</id><consigNo>{tracking}</consigNo>'
            f'<barcode>All Barcodes</barcode><references>{order}</references>'
            f'<sdate>{day}</sdate><statusTime>{clock}</statusTime><location>165</location>'
            f'<statusType>{kind}</statusType><statusData>{text}</statusData></consignment>')


class XdpActivityTests(unittest.TestCase):
    def test_adjacent_xml_events_are_sorted_decoded_and_deduplicated(self):
        delivered = event('3', '16-10-2026', '10:41:00', 'DELIVERED', 'ScanX Status: &quot;Delivered&quot;')
        raw = delivered + event('2', '16-10-2026', '8:20:24', 'DELIVERY', 'Scheduled for Delivery - Route 12 - ETA: 12:30pm to 2:30pm')
        raw += event('1', '14-10-2026', '7:54:02', 'CREATE') + delivered
        parsed = xdp_sheet.parse_activity(raw)
        self.assertEqual([item['id'] for item in parsed], ['1', '2', '3'])
        self.assertEqual(parsed[1]['at'], '2026-10-16T08:20:24')
        self.assertEqual(parsed[2]['text'], 'ScanX Status: "Delivered"')
        self.assertEqual(parsed[2]['barcode'], 'All Barcodes')
        self.assertEqual(xdp_sheet.parse_activity(''), [])
        for raw in ('<consignment>', '<!DOCTYPE x [<!ENTITY a "bad">]><consignment/>'):
            with self.assertRaises(ValueError):
                xdp_sheet.parse_activity(raw)

    def test_reads_xml_from_column_m(self):
        raw = event('1', '14-10-2026', '7:54:02', 'CREATE')
        row = ['not-the-order', '655824'] + [''] * 11
        row[12] = raw
        row[8] = 'DELIVERED'
        sheet = Mock()
        sheet.worksheet.return_value.get_all_values.return_value = [['Order no', 'Tracking ID'], row]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=sheet):
            result = google_sheets.read_xdp_activity()[0]
            self.assertEqual(result['activityXml'], raw)
            self.assertEqual(result['order'], '655824')
            self.assertEqual(result['statusType'], 'DELIVERED')
        sheet.worksheet.assert_called_once_with('XDP Activity')

    def test_activity_survives_refresh_and_bad_xml_without_changing_status(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            ow = [{'Order no': '655824', 'Delivery method': 'XDP', 'Tracking No': 'ZDBJSD020303', 'Status': 'P'}]
            delivery_data.archive(ow)
            rows = [{'order': '655824', 'status': 'EXCEPTION', 'activityXml': event('1', '16-10-2026', '10:41:00', 'DELIVERED')}]
            xdp_sheet.archive_activity(rows)
            delivery_data.archive(ow)
            with patch.object(xdp_sheet, 'parse_activity', wraps=xdp_sheet.parse_activity) as parse:
                xdp_sheet.archive_activity(rows)
                parse.assert_not_called()
            saved = delivery_data.detail('655824')
            self.assertEqual(len(saved['xdpEvents']), 1)
            self.assertEqual((saved['st'], saved['statusSource']), ('Awaiting', 'XDP fallback'))
            self.assertEqual(saved['xdpActivitySource'], 'XDP Activity')
            xdp_sheet.archive_activity([{'order': '655824', 'activityXml': '<consignment>'}])
            saved = delivery_data.detail('655824')
            self.assertEqual(len(saved['xdpEvents']), 1)
            self.assertTrue(saved['xdpActivityError'])
            xdp_sheet.archive_activity([{'order': '655824', 'activityXml': event('2', '16-10-2026', '11:00:00', 'SMS', order='WRONG')
                               + event('3', '16-10-2026', '12:00:00', 'SMS', order='', tracking='WRONG')}])
            self.assertEqual(len(delivery_data.detail('655824')['xdpEvents']), 3)

    def test_exact_order_reference_matches_when_ow_tracking_is_marketplace_reference(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'test.sqlite3'):
            ow = [{'Order no': '655824', 'Delivery method': 'XDP', 'Tracking No': 'BQS-59501', 'Status': 'P'}]
            delivery_data.archive(ow)
            xml = event('1438901074', '16-10-2026', '10:41:00', 'DELIVERED', 'ScanX Status: &quot;Delivered&quot;')
            xdp_sheet.archive_activity([{'order': '655824', 'trackingId': 'ZDBJSD020303', 'activityXml': xml}])
            delivery = delivery_data.detail('655824')
            self.assertEqual(len(delivery['xdpEvents']), 1)
            self.assertEqual(delivery['xdpEvents'][0]['consignment'], 'ZDBJSD020303')
            self.assertEqual(delivery['xdpEvents'][0]['reference'], '655824')
            self.assertEqual(delivery['trk'], 'BQS-59501')
            delivery_data.archive(ow)
            self.assertEqual(len(delivery_data.detail('655824')['xdpEvents']), 1)
