"""Local Delivery Desk server. Run with Python 3.10+: python server.py."""

import json
import mimetypes
import os
import re
import socket
import ssl
import secrets
import time
import threading
from datetime import date, datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlencode, urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent
ENV = {}
for env_file in (ROOT / ".env", ROOT / ".env.local"):
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8-sig").splitlines():
            match = re.match(r"^\s*([^#=]+?)\s*=\s*(.*?)\s*$", line)
            if match:
                value = match[2]
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                ENV[match[1]] = value
KEY = (
    os.environ.get("OPTIMOROUTE_API_KEY") or ENV.get("OPTIMOROUTE_API_KEY") or ENV.get("OPTIMO API")
)
API_SLOTS = threading.BoundedSemaphore(4)


def connection_message(error):
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, PermissionError) or getattr(reason, "winerror", None) == 10013:
        return (
            "Windows blocked the server network connection. Stop this server and run "
            "py server.py in your own PowerShell window, then try Sync deliveries again. "
            "If it still fails, check whether your firewall permits Python internet access."
        )
    if isinstance(reason, ssl.SSLCertVerificationError):
        return "Python could not verify the OptimoRoute HTTPS certificate. Check your system clock and trusted certificates."
    if isinstance(reason, socket.gaierror):
        return (
            "Cannot resolve api.optimoroute.com. Check your internet connection and DNS settings."
        )
    if isinstance(reason, TimeoutError):
        return "OptimoRoute connection timed out. Try syncing again."
    return "Cannot connect to OptimoRoute. Check your internet connection and API access."


def api(method, body, verb="POST"):
    allowed = {
        "search_orders",
        "get_orders",
        "get_completion_details",
        "get_routes",
        "get_dispatch_status",
        "get_events",
    }
    if method not in allowed:
        raise ValueError("This app is read-only. OptimoRoute writes are disabled.")
    if not KEY:
        raise RuntimeError("Set OPTIMOROUTE_API_KEY in .env and restart the server.")
    query = {"key": KEY}
    if verb == "GET":
        query.update(body)
    request = Request(
        "https://api.optimoroute.com/v1/" + method + "?" + urlencode(query),
        data=json.dumps(body).encode() if verb == "POST" else None,
        headers={"Content-Type": "application/json"},
        method=verb,
    )
    try:
        with API_SLOTS, urlopen(request, timeout=25) as response:
            data = json.load(response)
    except HTTPError as error:
        raise RuntimeError(f"OptimoRoute returned HTTP {error.code}.") from None
    except (URLError, TimeoutError, OSError) as error:
        raise RuntimeError(connection_message(error)) from None
    if data.get("success") is False:
        raise RuntimeError(f"OptimoRoute request failed ({data.get('code', 'unknown error')}).")
    if method in {"search_orders", "get_orders", "get_completion_details"} and not isinstance(
        data.get("orders"), list
    ):
        raise RuntimeError("OptimoRoute returned an unexpected response.")
    return data


def order_reference(data):
    field = os.environ.get("OPTIMOROUTE_ORDER_ID_FIELD") or ENV.get("OPTIMOROUTE_ORDER_ID_FIELD")
    if field:
        value = (data.get("customFields") or {}).get(field, data.get(field))
        if value is not None and str(value).strip():
            return str(value).strip()
    return str(data.get("orderNo") or "").strip() or None


def normalize(order, completion=None):
    data = order.get("data") or {}
    schedule = order.get("scheduleInformation") or {}
    done = (completion or {}).get("data") or {}
    form = done.get("form") or {}
    location = data.get("location") or {}
    return {
        "id": order.get("id") or data.get("id"),
        "orderNo": order_reference(data),
        "providerOrderNo": data.get("orderNo"),
        "address": location.get("address"),
        "customer": location.get("locationName"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "date": data.get("date"),
        "orderType": data.get("type"),
        "plannedDuration": data.get("duration"),
        "status": done.get("status")
        or ("scheduled" if order.get("scheduleInformation") else "unscheduled"),
        "startedAt": done.get("startTime"),
        "completedAt": done.get("endTime"),
        "plannedDate": data.get("date"),
        "trackingUrl": done.get("tracking_url"),
        "photos": form.get("images") or [],
        "podNote": form.get("note") or "",
        "signature": form.get("signature"),
        "barcodes": form.get("barcode") or [],
        "completionPosition": done.get("endPosition"),
        "customerFeedback": done.get("customerFeedback"),
        "driver": schedule.get("driverName") or "",
        "vehicle": schedule.get("vehicleRegistration") or schedule.get("vehicleLabel") or "",
        "eta": (schedule.get("liveEstimate") or {}).get("arrivalTimeDt") or "",
        "scheduledAt": schedule.get("scheduledAtDt") or "",
        "stopNumber": schedule.get("stopNumber"),
        "instructions": data.get("notes") or "",
        "locationNotes": location.get("notes") or "",
        "phone": data.get("phone") or "",
        "email": data.get("email") or "",
        "timeWindows": data.get("timeWindows") or [],
        "completionError": (
            (completion.get("code") or "Unavailable")
            if completion and completion.get("success") is False
            else None
        ),
        "raw": {"order": order, "completion": completion},
    }


SESSIONS = {}
SESSION_LOCK = threading.Lock()
SESSION_TTL = 1800


def deliveries(params):
    cursor = params.get("cursor", [""])[0]
    now = time.monotonic()
    with SESSION_LOCK:
        for token in list(SESSIONS):
            if now - SESSIONS[token]["touched"] > SESSION_TTL:
                del SESSIONS[token]
        state = SESSIONS.get(cursor) if cursor else None
    if cursor and state is None:
        return 410, {"error": "This browsing session expired. Click Refresh deliveries."}
    if state is None:
        start, end = params.get("from", [""])[0], params.get("to", [""])[0]
        if params.get("scope", [""])[0] == "all":
            start = os.environ.get("OPTIMOROUTE_HISTORY_FROM") or ENV.get(
                "OPTIMOROUTE_HISTORY_FROM", "2000-01-01"
            )
            end = (
                os.environ.get("OPTIMOROUTE_HISTORY_TO")
                or ENV.get("OPTIMOROUTE_HISTORY_TO")
                or (date.today() + timedelta(days=365)).isoformat()
            )
        try:
            if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", item) for item in (start, end)):
                raise ValueError()
            first, last = date.fromisoformat(start), date.fromisoformat(end)
            if first > last:
                raise ValueError()
        except ValueError:
            return 400, {"error": "Choose valid start and end dates."}
        token = secrets.token_urlsafe(24)
        status = params.get("status", [""])[0]
        if status and status not in {
            "unscheduled",
            "scheduled",
            "on_route",
            "servicing",
            "success",
            "failed",
            "rejected",
            "cancelled",
        }:
            return 400, {"error": "Invalid delivery status."}
        state = {
            "first": first,
            "last": last,
            "window_end": last,
            "tag": None,
            "pending": [],
            "pages": [],
            "done": False,
            "touched": now,
            "lock": threading.Lock(),
            "token": token,
            "status": status,
        }
        with SESSION_LOCK:
            if len(SESSIONS) >= 100:
                oldest = min(SESSIONS, key=lambda item: SESSIONS[item]["touched"])
                del SESSIONS[oldest]
            SESSIONS[token] = state
    try:
        page = int(params.get("page", ["1"])[0])
        if page < 1:
            raise ValueError()
    except ValueError:
        return 400, {"error": "Invalid page number."}
    with state["lock"]:
        state["touched"] = now
        if page <= len(state["pages"]):
            return 200, state["pages"][page - 1]
        if page != len(state["pages"]) + 1:
            return 400, {"error": "Load pages in order."}
        attempts = 0
        while len(state["pending"]) < 25 and not state["done"] and attempts < 16:
            window_end = state["window_end"]
            window_start = max(state["first"], window_end - timedelta(days=34))
            query = {
                "dateRange": {"from": window_start.isoformat(), "to": window_end.isoformat()},
                "includeOrderData": True,
                "includeScheduleInformation": True,
            }
            if state["tag"]:
                query["after_tag"] = state["tag"]
            if state["status"]:
                query["orderStatus"] = [state["status"]]
            result = api("search_orders", query)
            state["pending"].extend(result["orders"])
            state["tag"] = result.get("after_tag")
            if not state["tag"]:
                if window_start == state["first"]:
                    state["done"] = True
                else:
                    state["window_end"] = window_start - timedelta(days=1)
            attempts += 1
        batch = state["pending"][:25]
        completions = (
            api(
                "get_completion_details",
                {
                    "orders": [{"id": order["id"]} for order in batch],
                    "includeCustomerFeedback": True,
                },
            )["orders"]
            if batch
            else []
        )
        by_id = {item.get("id"): item for item in completions}
        del state["pending"][: len(batch)]
        next_page = (
            None
            if state["done"] and not state["pending"]
            else "/api/integrations/optimoroute/data?"
            + urlencode({"cursor": state["token"], "page": page + 1})
        )
        payload = {
            "records": [normalize(order, by_id.get(order.get("id"))) for order in batch],
            "next": next_page,
            "page": page,
            "pageSize": 25,
            "coverage": {"from": state["first"].isoformat(), "to": state["last"].isoformat()},
            "syncedAt": datetime.now(timezone.utc).isoformat(),
        }
        from activity_log import archive_records

        archive_records(payload["records"])
        state["pages"].append(payload)
        return 200, payload


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, status, payload):
        content = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        try:
            url = urlsplit(self.path)

            if url.path == '/api/order-flow':
                from tracking_relations import flow_lookup
                try:
                    return self.send_json(200, flow_lookup(parse_qs(url.query).get('order', [''])[0]))
                except ValueError as error:
                    return self.send_json(400, {'error': str(error)})

            if url.path == '/api/order-identifier':
                from order_identifier import lookup
                order = parse_qs(url.query).get('order', [''])[0].strip()
                try:
                    return self.send_json(200, lookup(order))
                except ValueError as error:
                    return self.send_json(400, {'error': str(error)})

            if url.path == '/api/manufacture-claims/order-lookup':
                from claim_order_lookup import order_fields
                try:
                    return self.send_json(200, order_fields(parse_qs(url.query).get('order', [''])[0]))
                except ValueError as error:
                    return self.send_json(400, {'error': str(error)})

            if url.path == '/api/manufacture-claims':
                from manufacture_claims import list_claims
                return self.send_json(200, list_claims())
            photo = re.fullmatch(r'/api/manufacture-claims/([a-f0-9]{32})/photos/([a-f0-9]{32})', url.path)
            if photo:
                from manufacture_claims import get_photo
                result = get_photo(*photo.groups())
                if not result:
                    return self.send_json(404, {'error': 'Picture not found.'})
                content, mime = result
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('X-Content-Type-Options', 'nosniff')
                self.send_header('Cache-Control', 'private, no-store')
                self.send_header('Content-Length', str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return

            if url.path == "/api/collection-notes":
                from collection_records import list_notes
                return self.send_json(200, list_notes())
            if url.path.startswith("/api/collection-notes/"):
                from collection_records import get_note
                note = get_note(unquote(url.path.rsplit("/", 1)[-1]))
                return self.send_json(200 if note else 404, note or {"error": "Collection record not found."})

            if url.path == "/api/collection-note":
                from collection_note import lookup

                order = parse_qs(url.query).get("order", [""])[0]
                if parse_qs(url.query).get("progress", [""])[0] == "1":
                    self.send_response(200)
                    self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Accel-Buffering", "no")
                    self.send_header("Connection", "close")
                    self.end_headers()
                    self.close_connection = True

                    def emit(event):
                        self.wfile.write((json.dumps(event) + "\n").encode("utf-8"))
                        self.wfile.flush()

                    try:
                        result = lookup(order, on_progress=lambda event: emit({"type": "progress", **event}))
                        emit({"type": "result", "result": result})
                    except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                        pass
                    except ValueError as error:
                        emit({"type": "error", "error": str(error)})
                    except Exception:
                        emit({"type": "error", "error": "Could not read the order from the sheet. Try again; you can still fill the note manually."})
                    return
                try:
                    return self.send_json(200, lookup(order))
                except ValueError as error:
                    return self.send_json(400, {"error": str(error)})
                except Exception:
                    return self.send_json(502, {"error": "Could not read the order from the sheet. Try again; you can still fill the note manually."})

            # Amazon Shipping — dynamic lookup by tracking ID
            if url.path.startswith("/api/amazon-shipping/live/"):
                from amazon_shipping_live import serve_live
                return serve_live(self, url.path, parse_qs(url.query))
            # Palletways portal — richer shipment data
            if url.path.startswith("/api/palletways/order-tracking/"):
                from palletways_sheet import tracking_for_order
                try:
                    return self.send_json(200, tracking_for_order(
                        unquote(url.path.rsplit("/", 1)[-1]),
                        force=parse_qs(url.query).get("refresh", [""])[0] == "1",
                    ))
                except ValueError as error:
                    return self.send_json(400, {"error": str(error)})
                except Exception:
                    return self.send_json(502, {"error": "Could not read tracking IDs from columns A/B of the Palletways tab."})

            if url.path.startswith(
                "/api/palletways/portal/"
            ):
                from palletways_portal import (
                    portal_details,
                )

                tracking_id = unquote(
                    url.path[
                        len(
                            "/api/palletways/portal/"
                        ):
                    ]
                )

                try:
                    return self.send_json(
                        200,
                        portal_details(
                            tracking_id,
                            force=parse_qs(url.query).get("refresh", [""])[0] == "1",
                        ),
                    )

                except ValueError as error:
                    return self.send_json(
                        400,
                        {
                            "error": str(error),
                        },
                    )

                except RuntimeError as error:
                    return self.send_json(
                        502,
                        {
                            "error": str(error),
                        },
                    )


            # Palletways portal — actual JPG/TIFF media
            if url.path.startswith(
                "/api/palletways/media/"
            ):
                from palletways_portal import (
                    portal_media,
                )

                filename = unquote(
                    url.path[
                        len(
                            "/api/palletways/media/"
                        ):
                    ]
                )

                try:
                    content, content_type = (
                        portal_media(
                            filename
                        )
                    )

                except ValueError as error:
                    return self.send_json(
                        400,
                        {
                            "error": str(error),
                        },
                    )

                except RuntimeError as error:
                    return self.send_json(
                        502,
                        {
                            "error": str(error),
                        },
                    )

                self.send_response(200)

                self.send_header(
                    "Content-Type",
                    content_type,
                )

                if parse_qs(url.query).get("download", [""])[0] == "1":
                    self.send_header("Content-Disposition", f'attachment; filename="{filename}"')

                self.send_header(
                    "Cache-Control",
                    "private, max-age=300",
                )

                self.send_header(
                    "Content-Length",
                    str(len(content)),
                )

                self.end_headers()

                self.wfile.write(
                    content
                )

                return
            # Palletways — live tracking by Tracking ID
            if url.path.startswith("/api/palletways/live/"):
                from palletways_live import serve_live
                return serve_live(
                    self,
                    url.path,
                    parse_qs(url.query),
                )

            # Palletways — POD and label PDFs
            if (
                url.path.startswith(
                    "/api/palletways/pod/"
                )
                or url.path.startswith(
                    "/api/palletways/label/"
                )
            ):
                from palletways_live import (
                    serve_document,
                )

                return serve_document(
                    self,
                    url.path,
                    parse_qs(url.query),
                )



            if url.path.startswith("/api/amazon-shipping/"):
                from amazon_shipping_demo import serve_amazon_shipping

                return serve_amazon_shipping(
                    self,
                    url.path,
                    parse_qs(url.query),
                )

            if url.path == "/api/xdp/document":
                from xdp_sheet import serve_document

                return serve_document(self, parse_qs(url.query))
            if url.path == "/api/pod-image":
                from delivery_data import detail

                params = parse_qs(url.query)
                order_id = params.get("order", [""])[0]
                try:
                    index = int(params.get("index", ["0"])[0])
                except ValueError:
                    return self.send_json(400, {"error": "Invalid image index."})
                delivery = detail(order_id)
                if delivery.get("error"):
                    return self.send_json(404, {"error": "Order not found."})
                photos = [item for item in delivery.get("podPhotos", []) if item and item.get("url")]
                if not photos:
                    source = delivery.get("podUrl") or delivery.get("proofUrl")
                    photos = [{"url": source, "imageUrl": delivery.get("podImageUrl")}] if source else []
                if index < 0 or index >= len(photos):
                    return self.send_json(404, {"error": "Image not found."})
                image_url = photos[index].get("imageUrl") or photos[index]["url"]
                if urlsplit(image_url).scheme != "https":
                    return self.send_json(400, {"error": "Unsupported image source."})
                try:
                    with API_SLOTS, urlopen(Request(image_url, headers={"Accept": "image/*"}), timeout=25) as response:
                        content_type = response.headers.get_content_type()
                        if not content_type.startswith("image/"):
                            return self.send_json(502, {"error": "The image provider did not return an image."})
                        content = response.read(25 * 1024 * 1024 + 1)
                    if len(content) > 25 * 1024 * 1024:
                        return self.send_json(502, {"error": "Image is too large to download."})
                except (HTTPError, URLError, TimeoutError, OSError):
                    return self.send_json(502, {"error": "Could not retrieve the image. Please try again."})
                extension = mimetypes.guess_extension(content_type) or ".img"
                if extension == ".jpe":
                    extension = ".jpg"
                self.send_response(200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Disposition", f'attachment; filename="proof-of-delivery-{index + 1}{extension}"')
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            if url.path == "/api/sync-run-log":
                from sync_run_log import read_snapshot
                return self.send_json(200, read_snapshot())
            if url.path == "/api/sync-control":
                from sync_control import read_snapshot
                return self.send_json(200, read_snapshot())
            if url.path == "/api/dashboard":
                from dashboard_data import snapshot
                from delivery_data import cached_or_schedule_sync
                params = parse_qs(url.query)
                return self.send_json(200, {**cached_or_schedule_sync(), **snapshot(
                    store=params.get('store', [''])[0], carrier=params.get('carrier', [''])[0],
                    **{key: params.get(key, [''])[0] == '1' for key in
                       ('hide_hygienic', 'hide_wayfair', 'hide_wilko', 'hide_palletways_b2b')})})
            if url.path == "/api/deliveries":
                from delivery_data import cached_or_schedule_sync, query_records

                params = parse_qs(url.query)
                force = params.get("refresh", [""])[0] == "1"
                sync_state = cached_or_schedule_sync(force)
                try:
                    page = query_records(
                        search=params.get("q", [""])[0],
                        carrier=params.get("carrier", [""])[0],
                        store=params.get("store", []),
                        general_scope=params.get("general_scope", []),
                        classification=params.get("delivery_method", []),
                        status=params.get("status", []),
                        courier_status=params.get("courier_status", [""])[0] == "1",
                        date_from=params.get("from", [""])[0],
                        date_to=params.get("to", [""])[0],
                        scheduled_from=params.get("scheduled_from", [""])[0],
                        scheduled_to=params.get("scheduled_to", [""])[0],
                        today=params.get("today", [""])[0] == "1",
                        ongoing_today=params.get("dashboard_scope", [""])[0] == "ongoing",
                        limit=params.get("limit", ["25"])[0],
                        offset=params.get("offset", ["0"])[0],
                        refresh_provider=params.get("refresh_provider", [""])[0] == "1",
                        issue_cases=params.get("issues", [""])[0] == "1" or params.get("dashboard_scope", [""])[0] == "failed",
                        date_sort=params.get("date_sort", [""])[0],
                        hide_hygienic=params.get("hide_hygienic", [""])[0] == "1",
                        hide_wayfair=params.get("hide_wayfair", [""])[0] == "1",
                        hide_wilko=params.get("hide_wilko", [""])[0] == "1",
                        hide_palletways_b2b=params.get("hide_palletways_b2b", [""])[0] == "1",
                        booked_in=params.get("booked_in", [""])[0],
                        book_in_request=params.get("book_in_request", [""])[0],
                        dashboard_widget=params.get('dashboard_widget', [''])[0],
                    )
                    if params.get('dashboard_widget', [''])[0]:
                        from dashboard_data import widget_facets
                        page['filterFacets'] = widget_facets(params['dashboard_widget'][0])
                    if params.get('tracking_related', [''])[0] == '1' and not params.get('issues', [''])[0]:
                        from tracking_relations import lookup
                        page['orderRelations'] = lookup(params.get('q', [''])[0])
                except ValueError:
                    return self.send_json(400, {"error": "Invalid page size or offset."})
                return self.send_json(200, {**sync_state, **page})
            if url.path == "/api/deliveries/summary":
                from delivery_data import cached_or_schedule_sync, summary

                return self.send_json(200, {**cached_or_schedule_sync(), **summary()})
            if url.path.startswith("/api/deliveries/"):
                from delivery_data import detail

                return self.send_json(200, detail(unquote(url.path[len("/api/deliveries/") :])))
            if url.path == "/api/integrations/optimoroute/data":
                status, payload = deliveries(parse_qs(url.query, keep_blank_values=True))
                return self.send_json(status, payload)
            if url.path == "/api/google-sheets/data":
                from google_sheets import read_sheet_data

                tab = parse_qs(url.query).get("tab", [None])[0]
                if tab not in {None, "sales_activity", "palletways"}:
                    return self.send_json(400, {"error": "Unknown spreadsheet tab."})
                try:
                    return self.send_json(200, read_sheet_data(tab))
                except Exception:
                    return self.send_json(
                        502,
                        {
                            "error": "Could not read Google Sheets. Check the service account credentials, sheet sharing and internet connection."
                        },
                    )
            if url.path.startswith("/api/optimoroute/"):
                from operations import read_operation

                return self.send_json(
                    200, read_operation(url.path.rsplit("/", 1)[1], parse_qs(url.query), api)
                )
            if url.path == "/today-deliveries.html":
                self.send_response(302)
                self.send_header("Location", "/deliveries.html?view=today")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            relative = unquote(url.path).lstrip("/") or "index.html"
            parts = relative.replace("\\", "/").split("/")
            if relative.startswith("src/") or relative.startswith("assets/"):
                public_root = ROOT
                file = (ROOT / relative).resolve()
            elif relative.startswith("static/"):
                public_root = ROOT / "static"
                file = (ROOT / relative).resolve()
            elif "/" not in relative and "\\" not in relative and relative.endswith(".html"):
                if relative in {
                    "index.html",
                    "dashboard.html",
                    "deliveries.html",
                    "failed-deliveries.html",
                    "collective-note.html",
                    "manufacture-claims.html",
                    "integrations.html",
                    "settings.html",
                    "guidance.html",
                    "van-deliveries.html",
                }:
                    public_root = ROOT / "pages"
                else:
                    public_root = ROOT / "templates"
                file = (public_root / relative).resolve()
            else:
                return self.send_json(404, {"error": "Not found."})
            allowed = {".html", ".js", ".css", ".svg", ".png", ".jpg", ".jpeg", ".webp", ".woff2", ".ico"}
            if (
                any(part.startswith(".") for part in parts)
                or file.suffix not in allowed
                or not file.is_relative_to(public_root)
                or not file.is_file()
            ):
                return self.send_json(404, {"error": "Not found."})
            content = file.read_bytes()
            self.send_response(200)
            self.send_header(
                "Content-Type", mimetypes.guess_type(file.name)[0] or "application/octet-stream"
            )
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # Client disconnected before the response finished.
            # No second response should be attempted.
            pass
        except Exception as error:
            message = str(error).replace(KEY, "[redacted]") if KEY else str(error)
            self.send_json(502, {"error": message})

    def do_POST(self):
        photo_upload = re.fullmatch(r'/api/manufacture-claims/([a-f0-9]{32})/photos', urlsplit(self.path).path)
        if photo_upload:
            from manufacture_claims import add_photos, MAX_REQUEST
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST:
                    return self.send_json(413, {'error': 'Pictures are too large. Attach up to 5 pictures, 5 MB each and 15 MB total.'})
                return self.send_json(200, add_photos(photo_upload[1], json.loads(self.rfile.read(length))))
            except FileNotFoundError as error:
                return self.send_json(404, {'error': str(error)})
            except (ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error) or 'Check the pictures and retry.'})
            except Exception:
                return self.send_json(500, {'error': 'Could not add pictures. Please try again.'})
        if urlsplit(self.path).path == '/api/manufacture-claims/export':
            from manufacture_claims_export import export_claims
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 12 * 1024 * 1024:
                    return self.send_json(413, {'error': 'The claims table is too large to export.'})
                content, mime, filename = export_claims(json.loads(self.rfile.read(length)))
            except (ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error) or 'Could not export this table.'})
            except Exception:
                return self.send_json(502, {'error': 'Could not export claims. Check that OpenPyXL, Pillow and Playwright Chromium are installed, then retry.'})
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        if urlsplit(self.path).path == '/api/manufacture-claims':
            from manufacture_claims import save_claim, MAX_REQUEST
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST:
                    return self.send_json(413, {'error': 'Claim is too large. Attach up to 5 pictures, 5 MB each and 15 MB total.'})
                return self.send_json(201, save_claim(json.loads(self.rfile.read(length))))
            except (ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error) or 'Check the claim details.'})
            except Exception:
                return self.send_json(500, {'error': 'Could not save the claim. Please try again.'})
        if urlsplit(self.path).path == '/api/bq/open':
            # Only the local dashboard may trigger desktop/VPN commands.
            origin = urlsplit(self.headers.get('Origin', ''))
            if (self.client_address[0] not in {'127.0.0.1', '::1'}
                or origin.scheme != 'http'
                or origin.netloc != self.headers.get('Host')
                or origin.hostname not in {'127.0.0.1', 'localhost', '::1'}
                or self.headers.get('X-DeliveryDesk-Action') != 'open-bq'):
                return self.send_json(403, {'error': 'Open B&Q from the local Delivery Desk dashboard.'})
            from bq_vpn import open_bq
            try:
                return self.send_json(200, open_bq())
            except Exception as error:
                return self.send_json(502, {'error': str(error)})
        if urlsplit(self.path).path == "/api/collection-notes":
            from collection_records import save_note
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 5 * 1024 * 1024:
                    return self.send_json(413, {"error": "Collection note is too large."})
                return self.send_json(200, save_note(json.loads(self.rfile.read(length))))
            except (ValueError, TypeError):
                return self.send_json(400, {"error": "Could not save. Enter an order number and check the note data."})
            except Exception:
                return self.send_json(500, {"error": "Could not save the collection note. Please try again."})
        if urlsplit(self.path).path == "/api/collection-note/export":
            from collection_export import export_note

            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 5 * 1024 * 1024:
                    return self.send_json(413, {"error": "The note is too large to export."})
                payload = json.loads(self.rfile.read(length))
                content, mime, filename = export_note(payload)
            except (ValueError, TypeError, KeyError):
                return self.send_json(400, {"error": "Could not export this note. Check the note data and try again."})
            except Exception:
                return self.send_json(502, {"error": "Export unavailable. Check that openpyxl and Playwright with Chromium are installed on the server."})
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            try:
                self.wfile.write(content)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            return
        self.send_json(405, {"error": "This app is read-only. Write actions are disabled."})

    def do_PUT(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/manufacture-claims/'):
            from manufacture_claims import save_claim, MAX_REQUEST
            claim_id = path.removeprefix('/api/manufacture-claims/')
            if not re.fullmatch(r'[a-f0-9]{32}', claim_id):
                return self.send_json(400, {'error': 'Invalid claim ID.'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= MAX_REQUEST:
                    return self.send_json(413, {'error': 'Claim is too large. Attach up to 5 pictures, 5 MB each and 15 MB total.'})
                return self.send_json(200, save_claim(json.loads(self.rfile.read(length)), claim_id))
            except FileNotFoundError as error:
                return self.send_json(404, {'error': str(error)})
            except (ValueError, TypeError) as error:
                return self.send_json(400, {'error': str(error) or 'Check the claim details.'})
            except Exception:
                return self.send_json(500, {'error': 'Could not update the claim. Please try again.'})
        self.send_json(405, {"error": "Method not supported."})

    def do_DELETE(self):
        path = urlsplit(self.path).path
        if path.startswith('/api/manufacture-claims/'):
            from manufacture_claims import delete_claim
            claim_id = path.removeprefix('/api/manufacture-claims/')
            if not re.fullmatch(r'[a-f0-9]{32}', claim_id):
                return self.send_json(400, {'error': 'Invalid claim ID.'})
            if not delete_claim(claim_id):
                return self.send_json(404, {'error': 'Claim not found.'})
            return self.send_json(200, {'deleted': True})
        prefix = "/api/collection-notes/"
        if path.startswith(prefix):
            from collection_records import delete_note

            note_id = unquote(path[len(prefix):])
            if not note_id or len(note_id) > 64 or "/" in note_id:
                return self.send_json(400, {"error": "Invalid collection record ID."})
            if not delete_note(note_id):
                return self.send_json(404, {"error": "Collection record not found."})
            return self.send_json(200, {"deleted": True})
        self.send_json(405, {"error": "Method not supported."})

    do_PATCH = do_PUT


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "3000"))

    with ThreadingHTTPServer(("127.0.0.1", port), Handler) as server:
        print(
            f"Delivery Desk: http://127.0.0.1:{port}/dashboard.html",
            flush=True
        )

        from amazon_background_prefetch import start_amazon_prefetch
        start_amazon_prefetch()

        from palletways_depot import start_depot_monitor

        start_depot_monitor()

        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
