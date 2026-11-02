import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent

BASE_URL = "https://api.palletways.com"

REQUEST_LOCK = threading.Lock()
LAST_REQUEST_AT = 0.0

MIN_REQUEST_GAP = 1.0

RETRY_DELAYS = (2, 5, 10)


def _load_env():
    values = {}

    for env_file in (
        ROOT / ".env",
        ROOT / ".env.local",
    ):
        if not env_file.exists():
            continue

        for line in env_file.read_text(
            encoding="utf-8-sig"
        ).splitlines():

            match = re.match(
                r"^\s*([^#=]+?)\s*=\s*(.*?)\s*$",
                line,
            )

            if not match:
                continue

            value = match.group(2)

            if (
                len(value) >= 2
                and value[0] == value[-1]
                and value[0] in "\"'"
            ):
                value = value[1:-1]

            values[match.group(1)] = value

    return values


ENV = _load_env()


def _api_key():
    return (
        os.environ.get("PALLETWAYS_API_KEY")
        or ENV.get("PALLETWAYS_API_KEY")
        or ""
    ).strip()


def _wait_for_request_slot():
    global LAST_REQUEST_AT

    with REQUEST_LOCK:
        now = time.monotonic()

        wait = MIN_REQUEST_GAP - (
            now - LAST_REQUEST_AT
        )

        if wait > 0:
            time.sleep(wait)

        LAST_REQUEST_AT = time.monotonic()


def _request_json(path):
    key = _api_key()

    if not key:
        raise RuntimeError(
            "PALLETWAYS_API_KEY is not configured."
        )

    query = urlencode({
        "apikey": key,
        "outputformat": "json",
    })

    url = (
        BASE_URL
        + path
        + "?"
        + query
    )

    last_error = None

    for attempt in range(
        len(RETRY_DELAYS) + 1
    ):

        _wait_for_request_slot()

        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent":
                    "DeliveryDesk-Palletways/1.0",
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:

                content_type = (
                    response.headers
                    .get("Content-Type", "")
                    .lower()
                )

                body = response.read()

                if (
                    "json" not in content_type
                    and body.lstrip().startswith(b"<")
                ):
                    raise RuntimeError(
                        "Palletways returned HTML instead of JSON."
                    )

                return json.loads(
                    body.decode("utf-8")
                )

        except HTTPError as error:

            last_error = error

            if (
                error.code == 503
                and attempt < len(RETRY_DELAYS)
            ):
                time.sleep(
                    RETRY_DELAYS[attempt]
                )
                continue

            raise RuntimeError(
                f"Palletways returned HTTP {error.code}."
            ) from None

        except (
            URLError,
            TimeoutError,
            OSError,
            json.JSONDecodeError,
        ) as error:

            last_error = error

            if attempt < len(RETRY_DELAYS):
                time.sleep(
                    RETRY_DELAYS[attempt]
                )
                continue

            raise RuntimeError(
                "Could not contact Palletways."
            ) from None

    raise RuntimeError(
        f"Palletways request failed: {last_error}"
    )





def _request_pdf(path):
    key = _api_key()

    if not key:
        raise RuntimeError(
            "PALLETWAYS_API_KEY is not configured."
        )

    query = urlencode({
        "apikey": key,
    })

    url = (
        BASE_URL
        + path
        + "?"
        + query
    )

    last_error = None

    for attempt in range(
        len(RETRY_DELAYS) + 1
    ):
        _wait_for_request_slot()

        request = Request(
            url,
            headers={
                "Accept": "application/pdf",
                "User-Agent":
                    "DeliveryDesk-Palletways/1.0",
            },
            method="GET",
        )

        try:
            with urlopen(
                request,
                timeout=30,
            ) as response:
                body = response.read(
                    25 * 1024 * 1024 + 1
                )

                if len(body) > 25 * 1024 * 1024:
                    raise RuntimeError(
                        "Palletways PDF is too large."
                    )

                if not body.lstrip().startswith(
                    b"%PDF-"
                ):
                    raise RuntimeError(
                        "Palletways did not return a PDF."
                    )

                return body

        except HTTPError as error:
            last_error = error

            if (
                error.code == 503
                and attempt < len(RETRY_DELAYS)
            ):
                time.sleep(
                    RETRY_DELAYS[attempt]
                )
                continue

            raise RuntimeError(
                f"Palletways returned HTTP {error.code}."
            ) from None

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as error:
            last_error = error

            if attempt < len(RETRY_DELAYS):
                time.sleep(
                    RETRY_DELAYS[attempt]
                )
                continue

            raise RuntimeError(
                "Could not contact Palletways."
            ) from None

    raise RuntimeError(
        f"Palletways PDF request failed: {last_error}"
    )




def _detail_data(payload):
    detail = payload.get("Detail") or {}

    return detail.get("Data")


def _normalise_events(payload):
    data = _detail_data(payload)

    if not data:
        return []

    if isinstance(data, dict):
        data = [data]

    if not isinstance(data, list):
        return []

    events = []

    for item in data:

        if not isinstance(item, dict):
            continue

        event = {
            "delta": str(
                item.get("Delta") or ""
            ),
            "trackingId": str(
                item.get("TrackingID") or ""
            ),
            "consignmentNumber": str(
                item.get("ConNo") or ""
            ),
            "systemNote": str(
                item.get("SysNote") or ""
            ),
            "barcode": str(
                item.get("Barcode") or ""
            ),
            "date": str(
                item.get("NoteDate") or ""
            ),
            "time": str(
                item.get("NoteTime") or ""
            ),
            "podDate": str(
                item.get("PodDate") or ""
            ),
            "podTime": str(
                item.get("PodTime") or ""
            ),
            "podSignature": str(
                item.get("PodSignature") or ""
            ),
            "bookInDate": str(
                item.get("BookInDate") or ""
            ),
            "bookInTime": str(
                item.get("BookInTime") or ""
            ),
            "bookInContact": str(
                item.get("BookInContact") or ""
            ),
            "bookInReference": str(
                item.get("BookInReference") or ""
            ),
            "text": str(
                item.get("NoteText") or ""
            ),
            "statusCode": str(
                item.get("StatusCode") or ""
            ),
            "group": str(
                item.get("NoteGroup") or ""
            ),
            "type": str(
                item.get("NoteType") or ""
            ),
            "codeId": str(
                item.get("NoteCodeID") or ""
            ),
        }

        events.append(event)

    events.sort(
        key=lambda event: (
            event["date"],
            event["time"],
            event["delta"],
        )
    )

    return events


def _find_consignment(payload):
    data = _detail_data(payload)

    if not isinstance(data, dict):
        return data or {}

    manifest = (
        data.get("Manifest")
        or data
    )

    depot = (
        manifest.get("Depot")
        if isinstance(manifest, dict)
        else None
    )

    if not isinstance(depot, dict):
        return {}

    account = depot.get("Account")

    if isinstance(account, list):
        account = (
            account[0]
            if account
            else {}
        )

    if not isinstance(account, dict):
        return {}

    consignment = account.get("Consignment")

    if isinstance(consignment, list):
        consignment = (
            consignment[0]
            if consignment
            else {}
        )

    if not isinstance(consignment, dict):
        return {}

    result = dict(consignment)

    result["_account"] = {
        "name": account.get("Name"),
        "code": account.get("Code"),
    }

    result["_depot"] = {
        "number": depot.get("Number"),
    }

    result["_manifest"] = {
        "date": manifest.get("Date"),
        "time": manifest.get("Time"),
    }

    return result


def _documents_from_events(events):
    delivered = any(
        (
            event["group"].upper() == "POD"
            and event["type"].upper()
            in {"POD", "REF"}
        )
        for event in events
    )

    pod_image_reference = next(
        (
            event["text"]
            for event in reversed(events)
            if (
                event["group"].upper()
                == "POD"
                and event["type"].upper()
                == "IMG"
                and event["text"]
            )
        ),
        "",
    )

    return {
        "podAvailable": delivered,
        "podImageReference":
            pod_image_reference,
        "labelAvailable": True,
    }


def derive_status(events, consignment=None):
    consignment = consignment or {}

    if not events:
        if str(
            consignment.get("BookedIn") or ""
        ).lower() == "yes":
            return {
                "status": "Scheduled",
                "label": "Scheduled",
                "event": None,
            }

        return {
            "status": "Unscheduled",
            "label": "Status unavailable",
            "event": None,
        }

    # Terminal / exception events take priority.
    for event in reversed(events):
        group = str(
            event.get("group") or ""
        ).upper()

        event_type = str(
            event.get("type") or ""
        ).upper()

        code = str(
            event.get("statusCode") or ""
        )

        text = str(
            event.get("text") or ""
        ).strip()

        searchable = text.lower()

        if (
            group == "POD"
            and event_type == "POD"
        ):
            return {
                "status": "Delivered",
                "label": "Delivered",
                "event": event,
            }

        if "lost" in searchable:
            return {
                "status": "Lost",
                "label": "Lost parcel",
                "event": event,
            }

        if "damag" in searchable:
            return {
                "status": "Damaged",
                "label": "Damaged",
                "event": event,
            }

        if "refus" in searchable:
            return {
                "status": "Refused",
                "label": "Delivery refused",
                "event": event,
            }

        if (
            "failed delivery" in searchable
            or "unable to deliver" in searchable
        ):
            return {
                "status": "Failed",
                "label": "Delivery failed",
                "event": event,
            }

        if "return" in searchable:
            return {
                "status": "Return",
                "label": "Returning",
                "event": event,
            }

    # Find the latest shipment-progress event.
    for event in reversed(events):
        group = str(
            event.get("group") or ""
        ).upper()

        event_type = str(
            event.get("type") or ""
        ).upper()

        code = str(
            event.get("statusCode") or ""
        )

        text = str(
            event.get("text") or ""
        ).strip()

        searchable = text.lower()

        # Ignore document-generation records.
        if (
            group == "POD"
            and event_type == "IMG"
        ):
            continue

        # Driver is physically at delivery location.
        if (
            group == "VP"
            and event_type == "DAR"
        ):
            return {
                "status": "Out for Delivery",
                "label": "Driver arrived",
                "event": event,
            }

        # Loaded onto local C&D vehicle.
        if (
            group == "VL"
            and event_type == "SCN"
            and code == "800"
        ):
            return {
                "status": "Out for Delivery",
                "label": "Out for delivery",
                "event": event,
            }

        # Depot/hub movement.
        if group in {
            "BAY",
            "VU",
            "VL",
            "JIN",
            "ARC",
        }:
            return {
                "status": "In Transit",
                "label": "In transit",
                "event": event,
            }

        # Booking activity.
        if (
            group == "BIN"
            and event_type == "BIN"
        ):
            if (
                "tried ringing" in searchable
                or "left vm" in searchable
                or "voicemail" in searchable
                or "message left" in searchable
            ):
                return {
                    "status": "Scheduled",
                    "label": "Awaiting customer booking",
                    "event": event,
                }

            return {
                "status": "Scheduled",
                "label": "Delivery booked",
                "event": event,
            }

        if group == "POC":
            return {
                "status": "Scheduled",
                "label": "Consignment created",
                "event": event,
            }

    return {
        "status": "Scheduled",
        "label": "Scheduled",
        "event": events[-1],
    }


def live_tracking(tracking_id):
    tracking_id = str(
        tracking_id or ""
    ).strip()

    if not re.fullmatch(
        r"\d{11}",
        tracking_id,
    ):
        raise ValueError(
            "Invalid Palletways tracking ID."
        )

    consignment_response = _request_json(
        f"/getconsignment/{tracking_id}"
    )

    notes_response = _request_json(
        f"/getnotes/trackingid/{tracking_id}"
    )

    events = _normalise_events(
        notes_response
    )

    consignment = _find_consignment(
        consignment_response
    )

    latest_event = (
        events[-1]
        if events
        else None
    )

    status = derive_status(
        events,
        consignment,
    )

    payload = {
        "ok": True,
        "trackingId": tracking_id,
        "fetchedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "consignment": consignment,
        "events": events,
        "latestEvent": latest_event,
        "status": status,
        "documents":
            _documents_from_events(events),
    }

    from palletways_store import save_live_payload

    save_live_payload(payload)

    return payload





def sync_delta(max_batches=10):
    from palletways_store import (
        get_latest_delta,
        save_events,
        set_latest_delta,
    )

    starting_delta = get_latest_delta()

    if not starting_delta:
        return {
            "ok": False,
            "reason": "No starting delta stored yet.",
            "events": 0,
        }

    cursor = int(starting_delta)

    total_received = 0
    total_inserted = 0
    batches = 0
    complete = False
    stalled = False

    while batches < max_batches:
        response = _request_json(
            f"/getnotes/delta/{cursor}"
        )

        events = _normalise_events(
            response
        )

        batches += 1

        if not events:
            complete = True
            break

        inserted = save_events(
            events
        )

        total_received += len(events)
        total_inserted += inserted

        deltas = [
            int(event["delta"])
            for event in events
            if str(
                event.get("delta") or ""
            ).isdigit()
        ]

        if not deltas:
            break

        max_delta = max(deltas)

        if len(events) < 1000:
            set_latest_delta(
                max_delta
            )

            cursor = max_delta
            complete = True
            break

        # 1000 means we may have hit the API response ceiling.
        #
        # Re-query one second before the highest delta so
        # multiple events sharing the same Delta are not lost.
        safe_cursor = max(
            cursor,
            max_delta - 1,
        )

        if safe_cursor <= cursor:
            stalled = True
            break

        set_latest_delta(
            safe_cursor
        )

        cursor = safe_cursor

    return {
        "ok": True,
        "fromDelta": starting_delta,
        "latestDelta": str(cursor),
        "batches": batches,
        "events": total_received,
        "inserted": total_inserted,
        "complete": complete,
        "stalled": stalled,
        "hitBatchLimit": (
            not complete
            and not stalled
            and batches >= max_batches
        ),
    }


def serve_document(
    handler,
    path,
    query=None,
):
    query = query or {}

    download = (
        query.get(
            "download",
            [""],
        )[0]
        == "1"
    )

    pod_prefix = "/api/palletways/pod/"
    label_prefix = "/api/palletways/label/"

    if path.startswith(pod_prefix):
        document_type = "pod"

        identifier = path[
            len(pod_prefix):
        ].strip()

        if not re.fullmatch(
            r"\d{11}",
            identifier,
        ):
            return handler.send_json(
                400,
                {
                    "error":
                        "Invalid Palletways tracking ID."
                },
            )

        upstream_path = (
            "/getPodByTrackingId/"
            + quote(
                identifier,
                safe="",
            )
        )

        filename = (
            f"palletways-pod-{identifier}.pdf"
        )

    elif path.startswith(label_prefix):
        document_type = "label"

        identifier = path[
            len(label_prefix):
        ].strip()

        if not re.fullmatch(
            r"[A-Za-z0-9._-]{1,80}",
            identifier,
        ):
            return handler.send_json(
                400,
                {
                    "error":
                        "Invalid Palletways consignment number."
                },
            )

        upstream_path = (
            "/getLabelsByConNo/"
            + quote(
                identifier,
                safe="",
            )
        )

        filename = (
            f"palletways-label-{identifier}.pdf"
        )

    else:
        return handler.send_json(
            404,
            {
                "error":
                    "Unknown Palletways document."
            },
        )

    try:
        content = _request_pdf(
            upstream_path
        )

    except RuntimeError as error:
        return handler.send_json(
            502,
            {
                "error": str(error),
                "document": document_type,
            },
        )

    except Exception:
        return handler.send_json(
            500,
            {
                "error":
                    "Unexpected Palletways document error.",
                "document": document_type,
            },
        )

    disposition = (
        "attachment"
        if download
        else "inline"
    )

    handler.send_response(200)

    handler.send_header(
        "Content-Type",
        "application/pdf",
    )

    handler.send_header(
        "Content-Disposition",
        f'{disposition}; filename="{filename}"',
    )

    handler.send_header(
        "Cache-Control",
        "no-store",
    )

    handler.send_header(
        "X-Content-Type-Options",
        "nosniff",
    )

    handler.send_header(
        "Content-Length",
        str(len(content)),
    )

    handler.end_headers()
    handler.wfile.write(content)

    return


def serve_live(
    handler,
    path,
    query=None,
):
    prefix = "/api/palletways/live/"

    tracking_id = (
        path[len(prefix):]
        if path.startswith(prefix)
        else ""
    )

    try:
        payload = live_tracking(
            tracking_id
        )

    except ValueError as error:
        return handler.send_json(
            400,
            {
                "error": str(error),
            },
        )

    except RuntimeError as error:
        return handler.send_json(
            502,
            {
                "error": str(error),
            },
        )

    except Exception:
        return handler.send_json(
            500,
            {
                "error":
                    "Unexpected Palletways error.",
            },
        )

    return handler.send_json(
        200,
        payload,
    )