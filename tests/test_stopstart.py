import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import delivery_data
import google_sheets
import stopstart

SAMPLE = "Expected delivery: 16/10/2026\nDelivery window: 09:27 (+2hr window)\nDriver: bluelion2\nStop Start Ref: 202787"


class StopstartTests(unittest.TestCase):
    def test_modern_sheet_reads_activity_j_and_trackability_o(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ['Order ID', 'Delivery Method', 'Customer Order Number', 'Expected Delivery Date',
             'Expected Delivery Time', 'Window (hours)', 'Driver', 'Stop Start Order #',
             'Calculated Status', 'Delivery Activity', 'Last Checked', 'Last Changed',
             'Activity Log', 'Fetch Result', 'Trackability'],
            ['655955', 'STOPSTART', '655955', '16/10/2026', '09:27', '2', 'bluelion2',
             '202787', 'Scheduled', SAMPLE, '', '', '', 'OK', 'Yes'],
        ]
        with patch.object(google_sheets, 'get_spreadsheet', return_value=spreadsheet):
            rows = google_sheets.read_stopstart()
        self.assertEqual(rows[0]['details'], SAMPLE)
        self.assertEqual(rows[0]['trackability'], 'Yes')
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
            source = [{'Order no': '655955', 'Delivery method': 'STOPSTART', 'Status': 'P'}]
            delivery_data.archive(source)
            stopstart.archive(rows)
            record = delivery_data.detail('655955')
            self.assertEqual(record['stopstartTrackability'], 'Yes')
            self.assertEqual(record['stopstartDetails']['reference'], '202787')
            stopstart.archive([{'order': '655955', 'trackability': 'No', 'fetchResult': 'HTTP 404 | LOG ENDED'}])
            record = delivery_data.detail('655955')
            self.assertEqual(record['stopstartTrackability'], 'No')
            self.assertEqual(record['stopstartDetails']['reference'], '202787')
            delivery_data.archive(source)
            self.assertEqual(delivery_data.detail('655955')['stopstartTrackability'], 'No')

    def test_trackability_uses_o_then_legacy_saved_fetch_result_without_new_requests(self):
        for result, expected in [('OK', 'Yes'), ('HTTP 404 | LOG ENDED', 'No'),
            ('EXPIRED TRACKING PAGE (HTTP 200)', 'No'), ('HTTP 503', 'Time Out'),
            ('REQUEST ERROR: timeout', 'Time Out'), ('INCOMPLETE TRACKING PAGE', 'Missing'), ('', '')]:
            self.assertEqual(stopstart.trackability({'fetchResult': result}), expected)
        self.assertEqual(stopstart.trackability({'trackability': ' No ', 'fetchResult': 'OK'}), 'No')

    def test_uk_window_is_duration_not_timezone_adjustment(self):
        parsed = stopstart.parse_details(SAMPLE)
        self.assertEqual(parsed["window"], "09:27 - 11:27")
        self.assertEqual(parsed["scheduledAt"], "2026-10-16T09:27:00+01:00")
        self.assertEqual(parsed["driver"], "bluelion2")
        self.assertEqual(parsed["reference"], "202787")
        winter = stopstart.parse_details(SAMPLE.replace("16/10/2026", "16/12/2026"))
        self.assertEqual(winter["scheduledAt"], "2026-12-16T09:27:00+00:00")

    def test_explicit_window_and_missing_or_invalid_dates(self):
        self.assertEqual(stopstart.parse_details(SAMPLE.replace("09:27 (+2hr window)", "09:27 - 11:27"))["window"], "09:27 - 11:27")
        self.assertEqual(stopstart.parse_details("Driver: Someone")["scheduledAt"], "")
        self.assertEqual(stopstart.parse_details(SAMPLE.replace("16/10/2026", "31/02/2026"))["scheduledAt"], "")
        self.assertEqual(stopstart.parse_details(SAMPLE.replace("09:27", "23:27"))["window"], "23:27 - 01:27")

    def test_sheet_uses_a_and_h_not_header_names(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ["Order", "B", "C", "D", "E", "F", "G", "Details"],
            [" 123 ", "wrong", "", "", "", "", "", SAMPLE, "Delivered_OK"], ["456"], [""],
        ]
        with patch.object(google_sheets, "get_spreadsheet", return_value=spreadsheet):
            rows = google_sheets.read_stopstart()
        spreadsheet.worksheet.assert_called_once_with("STOPSTART")
        self.assertEqual(rows, [{"order": "123", "details": SAMPLE, "status": "Delivered_OK", "fetchResult": "", "trackability": ""}, {"order": "456", "details": "", "status": "", "fetchResult": "", "trackability": ""}])

    def test_column_i_status_filters_verbatim_without_changing_general_status(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            rows = [{"Order no": order, "Delivery method": "Stopstart", "Status": "P"} for order in ("123", "456")]
            delivery_data.archive(rows)
            stopstart.archive([{"order": "123", "status": " Ready_FOR Delivery "}])
            def results(status):
                return delivery_data.query_records(carrier="Stopstart", status=status, courier_status=True)["deliveries"]
            self.assertEqual([item["order"] for item in results("stopstart: Ready_FOR Delivery ")], ["123"])
            self.assertEqual([item["order"] for item in results("Scheduled")], ["456"])
            self.assertEqual(delivery_data.query_records(status="Scheduled")["total"], 2)
            self.assertTrue(any(item["stopstartStatus"] == " Ready_FOR Delivery " for item in delivery_data.summary()["filterFacets"]))
            delivery_data.archive(rows)
            self.assertEqual(len(results("stopstart: Ready_FOR Delivery ")), 1)
            stopstart.archive([{"order": "123", "status": "A"}, {"order": "123", "status": "B"}])
            self.assertEqual(len(results("Scheduled")), 2)
            stopstart.archive([{"order": "123", "status": "Delivered"}])
            stopstart.archive([])
            self.assertEqual(len(results("Scheduled")), 2)

    def test_exact_matching_preserves_ow_status_and_merges_history(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            delivery_data.archive([
                {"Order no": "123", "Delivery method": "Stopstart", "Status": "P", "Order date": "15/10/2026"},
                {"Order no": "1234", "Delivery method": "Stopstart", "Status": "C"},
                {"Order no": "456", "Delivery method": "XDP", "Status": "P"},
            ], "2026-10-15T10:00:00+00:00")
            rows = [{"order": "123.0", "details": SAMPLE}, {"order": "456", "details": SAMPLE}]
            self.assertEqual(stopstart.archive(rows, "2026-10-15T12:00:00+00:00"), 1)
            stopstart.archive(rows, "2026-10-15T13:00:00+00:00")
            with delivery_data.connect() as db:
                saved = {row["order_id"]: json.loads(row["payload"]) for row in db.execute("SELECT * FROM deliveries")}
                logs = [dict(row) for row in db.execute("SELECT * FROM activity WHERE order_id='123'")]
            self.assertEqual(len(saved["123"]["stopstartEvents"]), 1)
            self.assertEqual(saved["123"]["stopstartDetails"]["window"], "09:27 - 11:27")
            self.assertEqual((saved["123"]["st"], saved["123"]["statusSource"]), ("Scheduled", "OW"))
            self.assertNotIn("stopstartDetails", saved["1234"])
            self.assertNotIn("stopstartDetails", saved["456"])
            self.assertTrue(any("Order received from OW" in row["text"] for row in logs))
            self.assertEqual(sum(row["text"].startswith("STOPSTART") for row in logs), 1)
            # Later OW refreshes retain the carrier observations.
            delivery_data.archive([{"Order no": "123", "Delivery method": "Stopstart", "Status": "C"}])
            with delivery_data.connect() as db:
                saved = json.loads(db.execute("SELECT payload FROM deliveries WHERE order_id='123'").fetchone()[0])
            self.assertEqual(len(saved["stopstartEvents"]), 1)
            self.assertEqual(saved["st"], "Delivered")

    def test_conflicting_plans_remain_in_history_without_picking_current(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, "DB_PATH", Path(directory) / "test.sqlite3"):
            delivery_data.archive([{"Order no": "123", "Delivery method": "Stopstart", "Status": "P"}])
            stopstart.archive([{"order": "123", "details": SAMPLE}, {"order": "123", "details": SAMPLE.replace("09:27", "10:27")}])
            with delivery_data.connect() as db:
                delivery = json.loads(db.execute("SELECT payload FROM deliveries WHERE order_id='123'").fetchone()[0])
            self.assertTrue(delivery["stopstartAmbiguous"])
            self.assertIsNone(delivery["stopstartDetails"])
            self.assertEqual(len(delivery["stopstartEvents"]), 2)
