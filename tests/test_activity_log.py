import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import activity_log


class ActivityLogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = patch.object(activity_log, "DB_PATH", Path(self.temp.name) / "activity.sqlite3")
        self.db.start()
        self.scope = patch.object(activity_log, "account", return_value="test-account")
        self.scope.start()

    def tearDown(self):
        self.scope.stop()
        self.db.stop()
        self.temp.cleanup()

    def test_status_changes_and_completion_are_retained_under_aliases(self):
        record = {
            "id": "internal-1",
            "orderNo": "CUSTOM-1",
            "providerOrderNo": "ORDER-1",
            "status": "scheduled",
            "driver": "Alex",
            "scheduledAt": "2026-10-07 10:00",
        }
        activity_log.archive_records([record, record])
        record.update(
            status="failed",
            completedAt={"unixTimestamp": 1791367200},
            podNote="Customer unavailable",
        )
        activity_log.archive_records([record])
        record.update(status="success", completedAt={"unixTimestamp": 1791453600})
        activity_log.archive_records([record])
        for query in ["internal-1", "CUSTOM-1", "ORDER-1"]:
            entries = activity_log.history(query)["entries"]
            self.assertEqual(
                [e["kind"] for e in entries if e["source"] == "observed"],
                ["scheduled", "failed", "success"],
            )
            self.assertEqual(len(entries), 5)
            self.assertTrue(any("Customer unavailable" in e["detail"] for e in entries))
        with patch.object(activity_log, "account", return_value="other-account"):
            self.assertEqual(activity_log.history("ORDER-1")["entries"], [])

    def test_lookup_internal_id_and_partial_provider_failure(self):
        api = Mock(
            side_effect=[
                {"orders": []},
                {"orders": [{"id": "internal-1", "data": {"orderNo": "ORDER-1"}}]},
                RuntimeError("Completion unavailable"),
                {
                    "events": [
                        {
                            "orderId": "internal-1",
                            "orderNo": "ORDER-1",
                            "event": "failed",
                            "unixTimestamp": 1791367200,
                        }
                    ],
                    "tag": "next",
                },
            ]
        )
        result = activity_log.lookup("internal-1", api)
        self.assertEqual(api.call_args_list[1].args[1]["orders"], [{"id": "internal-1"}])
        self.assertEqual(result["entries"][0]["kind"], "failed")
        self.assertEqual(result["warnings"], ["Completion unavailable"])
        self.assertFalse(any(e["source"] == "observed" for e in result["entries"]))

    def test_invalid_query(self):
        api = Mock()
        for query in ["", " ", "x" * 201]:
            with self.assertRaises(ValueError):
                activity_log.lookup(query, api)
        api.assert_not_called()

    def test_legacy_history_moves_to_shared_database_without_duplicates(self):
        legacy = Path(self.temp.name) / "legacy.sqlite3"
        shared = Path(self.temp.name) / "delivery-desk.sqlite3"
        with patch.object(activity_log, "DB_PATH", legacy):
            activity_log.archive_records(
                [{"id": "internal-1", "orderNo": "ORDER-1", "status": "scheduled"}]
            )
        with (
            patch.object(activity_log, "DB_PATH", shared),
            patch.object(activity_log, "MAIN_DB_PATH", shared),
            patch.object(activity_log, "LEGACY_DB_PATH", legacy),
            patch.object(activity_log, "_legacy_mtime", None),
        ):
            first = activity_log.history("ORDER-1")
            second = activity_log.history("ORDER-1")
            self.assertEqual(len(first["entries"]), 1)
            self.assertEqual(first["entries"], second["entries"])
            with activity_log.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM entries").fetchone()[0], 1)
        self.assertTrue(legacy.exists())
