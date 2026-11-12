import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import carrier_issues
import delivery_data
import google_sheets


class CarrierIssueTests(unittest.TestCase):
    def test_read_uses_separate_workbook_and_read_only_scope(self):
        workbook = Mock()
        workbook.worksheet.return_value.get_all_values.return_value = [["Order ID"], ["101"]]
        with patch.object(google_sheets, "get_spreadsheet", return_value=workbook) as get:
            data = google_sheets.read_courier_issues()
        get.assert_called_once_with(google_sheets.COURIER_ISSUES_SHEET_ID)
        self.assertEqual(set(data), set(google_sheets.COURIER_ISSUE_TABS))
        self.assertEqual(data["Van"][0]["Order ID"], "101")
        self.assertEqual(
            google_sheets.SCOPES, ["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )

    def test_exact_carrier_and_reference_join_with_followup_history(self):
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / "issues.sqlite3"),
        ):
            delivery_data.archive(
                [
                    {"Order no": "101", "Order reference": "REF-101", "Delivery method": "Own van"},
                    {"Order no": "102", "Order reference": "REF-102", "Delivery method": "Own van"},
                    {"Order no": "201", "Delivery method": "Palletways"},
                    {"Order no": "301", "Delivery method": "XDP"},
                ]
            )
            sheets = {
                "Van": [
                    {
                        "Order ID": "101",
                        "Order Reference": "REF-101",
                        "Status": "failed 7/10",
                        "Date": "06/10/2026",
                        "Note": "No answer",
                        "Follow up": "Van",
                        "Follow up_2": "local",
                        "Follow up_3": "55",
                        "Follow up_4": "Customer called back",
                        "Messaged Status": "WhatsApp sent",
                    },
                    {"Order ID": "102", "Order Reference": "WRONG", "Status": "failed 7/10"},
                    {"Order ID": "201", "Status": "failed 7/10"},
                    {"Order ID": "101 & 102", "Status": "failed 7/10"},
                ],
                "Palletways": [
                    {
                        "Order number": "201",
                        "Date": "07/10/2026",
                        "Dispatch Date": "06/10/2026",
                        "Status": "Customer unavailable",
                        "Follow up": "Booked 9/10",
                    }
                ],
                "XDP": [
                    {
                        "Order number": "301",
                        "Entry Date": "07/10/2026",
                        "Issue": "Damage",
                        "Issues": "Panel damaged",
                    }
                ],
                "Cancelled Orders": [
                    {"Order No": "101", "Date": "08/10/2026", "Cancelled/Refused": "Cancelled"}
                ],
                "COMPLETED VAN DELIVERIES": [
                    {"Order ID": "101", "Date": "07/10/2026", "Status": "1"}
                ],
            }
            first = carrier_issues.archive_courier_issues(sheets, "2026-10-08T09:00:00+00:00")
            self.assertEqual(first["matchedOrders"], 3)
            records = {item["order"]: item for item in delivery_data.snapshot()}
            self.assertTrue(records["101"]["carrierIssueFailure"])
            self.assertEqual(records["101"]["failedDate"], "2026-10-07")
            self.assertEqual(records["101"]["st"], "Unscheduled")
            self.assertEqual(len(records["101"]["followUps"]), 1)
            self.assertEqual(records["101"]["followUps"][0]["remark"], "Customer called back")
            self.assertEqual(records["101"]["messagedStatus"], "WhatsApp sent")
            self.assertEqual(records["101"]["cancellationRecord"]["status"], "Cancelled")
            self.assertEqual(records["101"]["completedVanRecord"]["date"], "2026-10-07")
            self.assertNotIn("carrierIssueEntries", records["102"])
            self.assertEqual(records["201"]["carrierIssueDispatchDate"], "2026-10-06")
            self.assertFalse(records["201"].get("carrierIssueFailure", False))
            self.assertTrue(records["301"]["carrierIssueFailure"])
            self.assertEqual(delivery_data.query_records(issue_cases=True)["total"], 0)

            carrier_issues.archive_courier_issues(sheets, "2026-10-08T10:00:00+00:00")
            again = {item["order"]: item for item in delivery_data.snapshot()}
            self.assertEqual(len(again["101"]["followUps"]), 1)
            delivery_data.archive(
                [{"Order no": "101", "Order reference": "REF-101", "Delivery method": "Own van"}],
                "2026-10-09T07:00:00+00:00",
            )
            retained = {item["order"]: item for item in delivery_data.snapshot()}
            self.assertEqual(len(retained["101"]["followUps"]), 1)
            delivery_data.archive([], "2026-10-09T08:00:00+00:00")
            self.assertEqual(delivery_data.query_records(issue_cases=True)["total"], 0)


if __name__ == "__main__":
    unittest.main()
