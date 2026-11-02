import json
import io
from email.message import Message
import threading
import re
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from unittest.mock import patch
import server


class ServerTests(unittest.TestCase):
    def test_pod_download_returns_original_image_and_rejects_invalid_selection(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}/api/pod-image?order=A&index="
        image_bytes = b"\xff\xd8\xfforiginal-jpeg"
        upstream = io.BytesIO(image_bytes)
        upstream.headers = Message()
        upstream.headers["Content-Type"] = "image/jpeg"
        delivery = {"podPhotos": [{"url": "https://images.example/photo.jpg"}]}
        try:
            with patch("delivery_data.detail", return_value=delivery), patch.object(server, "urlopen", return_value=upstream) as retrieve:
                with urlopen(base + "0") as response:
                    self.assertEqual(response.read(), image_bytes)
                    self.assertEqual(response.headers["Content-Type"], "image/jpeg")
                    self.assertIn("attachment;", response.headers["Content-Disposition"])
                    self.assertIn("proof-of-delivery-1", response.headers["Content-Disposition"])
                self.assertEqual(retrieve.call_args.args[0].full_url, delivery["podPhotos"][0]["url"])
                retrieve.reset_mock()
                for index in ("-1", "1", "abc"):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(base + index)
                    self.assertIn(error.exception.code, (400, 404))
                    error.exception.close()
                retrieve.assert_not_called()
            upstream = io.BytesIO(b"expired image link")
            upstream.headers = Message()
            upstream.headers["Content-Type"] = "text/html"
            with patch("delivery_data.detail", return_value=delivery), patch.object(server, "urlopen", return_value=upstream):
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + "0")
                self.assertEqual(error.exception.code, 502)
                error.exception.close()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_network_permission_error_is_actionable(self):
        from urllib.error import URLError

        message = server.connection_message(URLError(PermissionError(13, "Access denied")))
        self.assertIn("py server.py", message)
        self.assertIn("Windows blocked", message)

    def test_completion_mapping(self):
        record = server.normalize(
            {
                "id": "A",
                "data": {"notes": "Gate code"},
                "scheduleInformation": {"driverName": "Assigned"},
            },
            {
                "success": True,
                "data": {
                    "status": "failed",
                    "endTime": {"unixTimestamp": 123},
                    "form": {"note": "Absent", "images": [{"url": "https://example.com/photo"}]},
                },
            },
        )
        self.assertEqual(record["status"], "failed")
        self.assertEqual(record["completedAt"]["unixTimestamp"], 123)
        self.assertEqual(record["podNote"], "Absent")
        self.assertEqual(record["instructions"], "Gate code")
        self.assertEqual(record["driver"], "Assigned")
        self.assertEqual(len(record["photos"]), 1)
        self.assertEqual(server.normalize({"id": "B"})["status"], "unscheduled")

    def test_single_date_and_status_filter_are_sent_to_carrier(self):
        with patch.object(server, "api", return_value={"orders": []}) as api:
            status, payload = server.deliveries(
                {"from": ["2026-10-07"], "to": ["2026-10-07"], "status": ["success"]}
            )
            self.assertEqual(status, 200)
            self.assertEqual(
                api.call_args.args[1]["dateRange"], {"from": "2026-10-07", "to": "2026-10-07"}
            )
            self.assertEqual(api.call_args.args[1]["orderStatus"], ["success"])
            self.assertIsNone(payload["next"])

    def test_service_times_and_planned_date(self):
        record = server.normalize(
            {"id": "A", "data": {"date": "2026-10-07", "type": "D", "duration": 10}},
            {"data": {"startTime": {"unixTimestamp": 123}, "endTime": {"unixTimestamp": 456}}},
        )
        self.assertEqual(record["plannedDate"], "2026-10-07")
        self.assertEqual(record["startedAt"]["unixTimestamp"], 123)
        self.assertEqual(record["completedAt"]["unixTimestamp"], 456)
        self.assertEqual(record["orderType"], "D")
        self.assertEqual(record["plannedDuration"], 10)

    def test_date_validation(self):
        for start, end in [("2026-02-30", "2026-03-01"), ("2026-10-07", "2026-10-01"), ("", "")]:
            with patch.object(server, "api") as api:
                self.assertEqual(server.deliveries({"from": [start], "to": [end]})[0], 400)
                api.assert_not_called()

    def test_pagination_is_lazy_and_retryable(self):
        orders = [{"id": str(i), "data": {"orderNo": f"HG-{i:06d}"}} for i in range(60)]

        def mock_api(method, body):
            if method == "search_orders":
                return {"orders": orders}
            return {
                "orders": [
                    {"id": item["id"], "data": {"status": "success"}}
                    for item in reversed(body["orders"])
                ]
            }

        with patch.object(server, "api", side_effect=mock_api) as api:
            status, first = server.deliveries({"from": ["2026-10-07"], "to": ["2026-10-07"]})
            self.assertEqual(status, 200)
            self.assertEqual(len(first["records"]), 25)
            self.assertEqual(first["records"][0]["orderNo"], "HG-000000")
            self.assertEqual(api.call_count, 2)
            self.assertEqual(len(api.call_args.args[1]["orders"]), 25)
            cursor = parse_qs(urlsplit(first["next"]).query)
            _, second = server.deliveries(cursor)
            self.assertEqual(second["records"][0]["id"], "25")
            self.assertEqual(api.call_count, 3)
            self.assertEqual(server.deliveries(cursor)[1], second)
            self.assertEqual(api.call_count, 3)
            _, last = server.deliveries(parse_qs(urlsplit(second["next"]).query))
            self.assertEqual(len(last["records"]), 10)
            self.assertIsNone(last["next"])

    def test_all_scope_and_custom_reference(self):
        with patch.dict(
            server.ENV,
            {"OPTIMOROUTE_HISTORY_FROM": "2026-10-01", "OPTIMOROUTE_HISTORY_TO": "2026-10-07"},
        ):
            with patch.object(server, "api", return_value={"orders": []}) as api:
                status, payload = server.deliveries({"scope": ["all"]})
                self.assertEqual(status, 200)
                self.assertIsNone(payload["next"])
                self.assertEqual(api.call_args.args[1]["dateRange"]["from"], "2026-10-01")
        with patch.dict(server.ENV, {"OPTIMOROUTE_ORDER_ID_FIELD": "sales_order"}):
            record = server.normalize(
                {"id": "A", "data": {"orderNo": "HG", "customFields": {"sales_order": "HG-123456"}}}
            )
            self.assertEqual(record["orderNo"], "HG-123456")
            self.assertEqual(record["providerOrderNo"], "HG")

    def test_http_protects_private_files(self):
        http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{http.server_port}"
        try:
            for route in ["/.env", "/server.py", "/test_server.py", "/%2eenv", "/..%5c.env"]:
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + route)
                self.assertEqual(error.exception.code, 404)
                error.exception.close()
            with urlopen(base + "/optimoroute.html") as response:
                self.assertEqual(response.status, 200)
            for page in (server.ROOT / "pages").glob("*.html"):
                with urlopen(base + "/" + page.name) as response:
                    self.assertEqual(response.status, 200, page.name)
                for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text(encoding="utf-8")):
                    if ref.startswith(("https:", "http:", "#")):
                        continue
                    with urlopen(base + "/" + ref.lstrip("./")) as response:
                        self.assertEqual(response.status, 200, ref)
            for route in [
                "/static/js/optimoroute.js",
                "/static/css/styles.css",
                "/static/images/logo-icon.png",
            ]:
                with urlopen(base + route) as response:
                    self.assertEqual(response.status, 200)
            for page in (server.ROOT / "templates").glob("*.html"):
                for ref in re.findall(r'(?:href|src)="([^"]+)"', page.read_text(encoding="utf-8")):
                    if ref.startswith(("https:", "http:", "#")):
                        continue
                    with urlopen(base + "/" + ref.lstrip("./")) as response:
                        self.assertEqual(response.status, 200, ref)
            for ref in re.findall(
                r'@import url\("\./([^"]+)"\)', (server.ROOT / "static/css/styles.css").read_text()
            ):
                with urlopen(base + "/static/css/" + ref) as response:
                    self.assertEqual(response.status, 200, ref)
            with patch.object(server, "api", return_value={"orders": []}):
                with urlopen(
                    base + "/api/integrations/optimoroute/data?from=2026-10-07&to=2026-10-07"
                ) as response:
                    self.assertEqual(json.load(response)["records"], [])
        finally:
            http.shutdown()
            http.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
