import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from unittest.mock import Mock, patch
import operations
import server


class ReadOnlyTests(unittest.TestCase):
    def test_removed_write_endpoints_cannot_call_provider(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}"
        try:
            with patch.object(server, "api") as api:
                for action in [
                    "send",
                    "schedule-send",
                    "cancel-send",
                    "plan",
                    "stop-planning",
                    "order",
                    "driver",
                    "completion",
                    "refresh",
                ]:
                    request = Request(
                        base + "/api/optimoroute/" + action,
                        data=json.dumps({"confirmed": True}).encode(),
                        headers={"Content-Type": "application/json"},
                    )
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request)
                    self.assertEqual(error.exception.code, 405)
                    error.exception.close()
                api.assert_not_called()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_provider_client_blocks_all_mutations(self):
        for method in [
            "send_routes",
            "start_planning",
            "stop_planning",
            "create_order",
            "delete_order",
            "update_drivers_parameters",
            "update_completion_details",
        ]:
            with patch.object(server, "urlopen") as network:
                with self.assertRaisesRegex(ValueError, "read-only"):
                    server.api(method, {})
                network.assert_not_called()

    def test_route_and_dispatch_reads(self):
        api = Mock(return_value={"success": True})
        operations.read_operation("routes", {"date": ["2026-10-07"]}, api)
        self.assertEqual(api.call_args.args[0], "get_routes")
        self.assertEqual(api.call_args.args[2], "GET")
        operations.read_operation("dispatch", {"date": ["2026-10-07"]}, api)
        self.assertEqual(api.call_args.args[0], "get_dispatch_status")
        for action in ["send", "plan", "order", "jobs"]:
            with self.assertRaises(ValueError):
                operations.read_operation(action, {}, api)

    def test_live_refresh_only_reads_current_page(self):
        api = Mock(
            side_effect=[
                {"orders": [{"id": "A", "data": {"orderNo": "HG"}}]},
                {"orders": [{"id": "A", "data": {"status": "success"}}]},
            ]
        )
        result = operations.read_operation("refresh", {"ids": ["A"]}, api)
        self.assertEqual(result["records"][0]["status"], "success")
        self.assertEqual(
            [call.args[0] for call in api.call_args_list],
            ["search_orders", "get_completion_details"],
        )
        with self.assertRaises(ValueError):
            operations.read_operation("refresh", {"ids": [",".join(["A"] * 26)]}, api)
