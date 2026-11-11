import unittest
from unittest.mock import patch

import amazon_shipping_live as live


class AmazonProgressTests(unittest.TestCase):
    def test_progress_tracks_completed_steps_and_finishes_only_when_ready(self):
        tracking_id = "UK1234567890"
        job = {"state": "queued", "viewers": {"test"}, "requested": 1}
        observed = []

        def capture(tracking_id, should_cancel, on_progress):
            for completed in range(1, 7):
                on_progress(completed, f"Step {completed}")
                observed.append(dict(job["progress"]))
                self.assertEqual(job["state"], "loading")
            return {"pdf": False, "excel": False, "raw": {}}

        with patch.dict(live.JOBS, {tracking_id: job}, clear=True), patch.object(
            live, "_capture", side_effect=capture
        ), patch.object(live, "snapshot", return_value={"available": True}), patch.object(
            live, "SCHEDULER_ACTIVE", True
        ), patch.object(live, "BROWSER_IDLE_SECONDS", 0), patch.object(live, "_close_worker_browser"):

            live._queue_loop()
            self.assertEqual([p["completed"] for p in observed], list(range(1, 7)))
            self.assertTrue(all(p["percent"] < 100 for p in observed))
            self.assertEqual(job["state"], "ready")
            self.assertEqual(job["progress"]["percent"], 100)

    def test_superseded_job_cannot_update_replacement_progress(self):
        old = {}
        current = {"progress": {"completed": 0}}
        with patch.dict(live.JOBS, {"UK1234567890": current}, clear=True):
            live._set_progress("UK1234567890", old, 6, "Preparing updates")
            self.assertEqual(current["progress"]["completed"], 0)


if __name__ == "__main__":
    unittest.main()
