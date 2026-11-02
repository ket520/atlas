import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch

import collection_note
import server


class CollectionProgressTests(unittest.TestCase):
    def test_progress_counts_real_scanned_rows_and_marks_uncached_read(self):
        events = []
        rows = [{"Order no": str(i)} for i in range(601)]
        with patch.object(collection_note, "_rows", None), patch.object(collection_note, "_read_at", 0), patch(
            "google_sheets.read_sales_activity", return_value=rows
        ) as read:
            result = collection_note.lookup("600", on_progress=events.append)
            self.assertTrue(result["found"])
            self.assertEqual([event["stage"] for event in events[:2]], ["waiting", "reading"])
            self.assertEqual([event["completed"] for event in events if event["stage"] == "matching"], [0, 250, 500, 601])
            events.clear()
            collection_note.lookup("9999", on_progress=events.append)
            self.assertNotIn("reading", [event["stage"] for event in events])
            self.assertEqual(read.call_count, 1)

    def test_stream_endpoint_sends_progress_then_result_and_errors(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(collection_note, "_rows", None), patch("google_sheets.read_sales_activity", return_value=[{"Order no": "123"}]):
                with urlopen(f"http://127.0.0.1:{http.server_port}/api/collection-note?order=123&progress=1") as response:
                    self.assertIn("application/x-ndjson", response.headers["Content-Type"])
                    events = [json.loads(line) for line in response]
                self.assertEqual(events[0]["stage"], "waiting")
                self.assertEqual(events[-1]["type"], "result")
                self.assertTrue(events[-1]["result"]["found"])
            with patch.object(collection_note, "_rows", None), patch("google_sheets.read_sales_activity", side_effect=RuntimeError("private source error")):
                with urlopen(f"http://127.0.0.1:{http.server_port}/api/collection-note?order=123&progress=1") as response:
                    events = [json.loads(line) for line in response]
                self.assertEqual(events[-1]["type"], "error")
                self.assertNotIn("private source error", events[-1]["error"])
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
