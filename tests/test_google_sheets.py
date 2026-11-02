import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import urlopen
from unittest.mock import Mock, patch

import google_sheets
import server


class GoogleSheetsTests(unittest.TestCase):
    def test_reuses_connection_within_sync_and_reloads_changed_credentials(self):
        from types import SimpleNamespace
        client = Mock()
        fake_file = Mock()
        fake_file.stat.return_value = SimpleNamespace(st_mtime_ns=1)
        with patch.object(google_sheets, 'gspread', Mock()), patch.object(
            google_sheets, 'Credentials', Mock()
        ) as credentials, patch.object(google_sheets, 'CREDENTIALS_FILE', fake_file), patch.object(
            google_sheets._sheets_local, 'books', {}, create=True
        ), patch.object(google_sheets.gspread, 'authorize', return_value=client):
            first = google_sheets.get_spreadsheet()
            self.assertIs(google_sheets.get_spreadsheet(), first)
            credentials.from_service_account_file.assert_called_once()
            client.open_by_key.assert_called_once()
            fake_file.stat.return_value = SimpleNamespace(st_mtime_ns=2)
            google_sheets.get_spreadsheet()
            self.assertEqual(client.open_by_key.call_count, 2)

    @unittest.skipIf(google_sheets.gspread is None, "gspread is not installed")
    def test_amazon_tab_accepts_case_and_spacing_variations(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.side_effect = google_sheets.gspread.WorksheetNotFound("Amazon Shipping")
        sheet = Mock()
        sheet.title = "Amazon shipping "
        sheet.get_all_values.return_value = [
            ["", "Tracking ID", "", "", "", "", "Order status"],
            ["", "UK4954910337", "", "", "", "", "IN_TRANSIT"],
        ]
        spreadsheet.worksheets.return_value = [sheet]
        with patch.object(google_sheets, "get_spreadsheet", return_value=spreadsheet):
            self.assertEqual(google_sheets.read_amazon_shipping(), [{"trackingId": "UK4954910337", "status": "IN_TRANSIT", "scheduledAt": ""}])

    def test_amazon_tab_reads_columns_b_and_g_from_sales_workbook(self):
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value.get_all_values.return_value = [
            ["A", "Tracking ID", "C", "D", "E", "F", "Order status"],
            ["Ignored", " UK1234567890 ", "", "", "", "", " IN_TRANSIT ", "", "", "", "", "", "13/10/2026 19:00 (UTC)"],
            ["Ignored", "UK9999999999"],
            ["Ignored", "", "", "", "", "", "DELIVERED"],
        ]
        with patch.object(google_sheets, "get_spreadsheet", return_value=spreadsheet) as open_book:
            rows = google_sheets.read_amazon_shipping()
        open_book.assert_called_once_with()
        spreadsheet.worksheet.assert_called_once_with("Amazon Shipping")
        self.assertEqual(rows, [
            {"trackingId": "UK1234567890", "status": "IN_TRANSIT", "scheduledAt": "13/10/2026 19:00 (UTC)"},
            {"trackingId": "UK9999999999", "status": "", "scheduledAt": ""},
        ])

    def test_records_preserve_extra_columns_and_unique_headers(self):
        sheet = Mock()
        sheet.get_all_values.return_value = [
            ["Order", "Order", "Order_2", ""],
            ["A", "B", "C", "D", "Extra"],
        ]
        records = google_sheets.worksheet_to_records(sheet)
        self.assertEqual(len(records[0]), 5)
        self.assertEqual(list(records[0].values()), ["A", "B", "C", "D", "Extra"])

    def test_sheet_values_preserve_duplicates_blank_cells_and_rows(self):
        sheet = Mock(title="Sales Activity")
        sheet.get_all_values.return_value = [["Order", "Order"], ["A", "", "Extra"], []]
        spreadsheet = Mock()
        spreadsheet.worksheet.return_value = sheet
        with patch.object(google_sheets, "get_spreadsheet", return_value=spreadsheet):
            data = google_sheets.read_sheet_data("sales_activity")
        spreadsheet.worksheet.assert_called_once_with("Sales Activity")
        self.assertEqual(data["values"], [["Order", "Order", ""], ["A", "", "Extra"], ["", "", ""]])

    def test_page_endpoint_selects_tab_and_protects_credentials(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}"
        try:
            with patch.object(
                google_sheets, "read_sheet_data", return_value={"values": [["Order"], ["A"]]}
            ) as read:
                for tab in ["sales_activity", "palletways"]:
                    with urlopen(base + "/api/google-sheets/data?tab=" + tab) as response:
                        self.assertEqual(json.load(response)["values"][1], ["A"])
                    read.assert_called_with(tab)
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/api/google-sheets/data?tab=unknown")
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
            with patch.object(
                google_sheets,
                "read_sheet_data",
                side_effect=RuntimeError("private credential content"),
            ):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "/api/google-sheets/data?tab=palletways")
                self.assertNotIn("private credential", error.exception.read().decode())
                error.exception.close()
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/credentials/google_service_account.json")
            self.assertEqual(error.exception.code, 404)
            error.exception.close()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
