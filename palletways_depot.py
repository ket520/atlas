import json
import logging
import re
import threading
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOGGER = logging.getLogger(__name__)
UK = ZoneInfo("Europe/London")
POLL_SECONDS = 1800


def depot_number(value):
    match = re.fullmatch(r"(?:Depot\s*)?(\d+)", str(value or "").strip(), re.I)
    return str(int(match[1])) if match else ""


def event_time(event):
    try:
        value = datetime.fromisoformat(f"{event.get('date', '')}T{event.get('time', '')}")
        return (value.replace(tzinfo=UK) if value.tzinfo is None else value).astimezone(
            timezone.utc
        )
    except (ValueError, TypeError):
        return None


def depot_stay(consignment, events):
    depot = depot_number(consignment.get("DeliveryDepot"))
    arrival = None
    departed_at = None
    closed_reason = ""
    last_event = ""
    routed_to_destination = False
    if not depot:
        return {"verified": False, "reason": "Delivery depot unavailable"}
    ordered = sorted(
        ((event_time(event), event) for event in events if event_time(event)),
        key=lambda item: item[0],
    )
    for at, event in ordered:
        group, kind, code = (
            str(event.get(key) or "").upper() for key in ("group", "type", "statusCode")
        )
        text = str(event.get("text") or "")
        last_event = text or last_event
        scan_depot = re.search(r"\bdepot\s+(\d+)\b", text, re.I)
        matches = scan_depot and depot_number(scan_depot[1]) == depot
        if group == "JIN" and kind == "GDEP":
            route = re.search(r"\[(\d+)\]\s*$", text)
            routed_to_destination = bool(route and depot_number(route[1]) == depot)
            arrival = None
        elif group == "VU" and kind == "SCN" and code == "700":
            if matches:
                if arrival is None:
                    departed_at = None
                    closed_reason = ""
                arrival = arrival or at
            elif scan_depot:
                arrival = None
        elif group == "BAY" and kind == "SCN" and code == "700":
            if matches or (routed_to_destination and text.strip().lower() == "inbound/receive scan"):
                if arrival is None:
                    departed_at = None
                    closed_reason = ""
                arrival = arrival or at
        elif group == "VL" and kind == "SCN" and code == "800":
            if matches and re.search(r"\bC\s*&\s*D\b", text, re.I):
                arrival = None
                departed_at = departed_at or at
                closed_reason = "Loaded for delivery at destination depot"
        elif group == "VP" and kind == "DAR":
            arrival = None
            closed_reason = closed_reason or "Driver arrival confirms shipment is no longer at depot"
        elif (group == "POD" and kind == "POD") or re.search(
            r"\b(cancelled|canceled|return to sender|returned to sender|job complete)\b", text, re.I
        ):
            arrival = None
            closed_reason = closed_reason or "Shipment completed, cancelled or returned"
    return {
        "verified": bool(arrival),
        "depot": depot,
        "arrivedAt": arrival.isoformat() if arrival else "",
        "lastEvent": last_event,
        "departedAt": departed_at.isoformat() if departed_at else "",
        "reason": "" if arrival else closed_reason or "No confirmed current delivery-depot stay",
    }


def tracking_id(delivery):
    for field in ("palletwaysSheetTrackingNumber", "trk", "owTrackingNo"):
        value = str(delivery.get(field) or "").strip()
        if re.fullmatch(r"\d{11}", value):
            return value
    return ""


def refresh_batch():
    from delivery_data import connect
    from palletways_live import live_tracking

    with connect() as db:
        rows = db.execute("""
            SELECT order_id, payload FROM deliveries
            WHERE json_extract(payload, '$.carrier')='Palletways'
              AND coalesce(json_extract(payload, '$.st'), '') NOT IN ('Delivered','Cancelled','Return')
              AND (length(json_extract(payload, '$.palletwaysSheetTrackingNumber'))=11
                   OR length(json_extract(payload, '$.trk'))=11
                   OR length(json_extract(payload, '$.owTrackingNo'))=11)
            ORDER BY coalesce(json_extract(payload, '$.palletwaysDepotStay.attemptedAt'), '')
            LIMIT 25
        """).fetchall()
    cache = {}
    for row in rows:
        delivery = json.loads(row["payload"])
        tracking = tracking_id(delivery)
        if not tracking:
            continue
        previous = delivery.get("palletwaysDepotStay") or {}
        now = datetime.now(timezone.utc)
        try:
            if (
                now - datetime.fromisoformat(previous["attemptedAt"])
            ).total_seconds() < POLL_SECONDS:
                continue
        except (KeyError, ValueError, TypeError):
            pass
        try:
            if tracking not in cache:
                cache[tracking] = live_tracking(tracking)
            payload = cache[tracking]
            state = depot_stay(payload["consignment"], payload["events"])
            state.update(
                trackingId=tracking,
                checkedAt=payload["fetchedAt"],
                unavailable=False,
                attemptedAt=now.isoformat(),
            )
            if payload["status"]["status"] in ("Delivered", "Cancelled", "Return"):
                state.update(verified=False, arrivedAt="")
        except Exception:
            state = {**previous, "unavailable": True, "attemptedAt": now.isoformat()}
            LOGGER.warning("Palletways depot check failed for tracking %s", tracking)
        with connect() as db:
            current = db.execute(
                "SELECT payload FROM deliveries WHERE order_id=?", (row["order_id"],)
            ).fetchone()
            if current:
                updated = json.loads(current["payload"])
                updated["palletwaysDepotStay"] = state
                db.execute(
                    "UPDATE deliveries SET payload=? WHERE order_id=?",
                    (json.dumps(updated), row["order_id"]),
                )
                db.commit()


def start_depot_monitor():
    from palletways_live import _api_key

    if not _api_key():
        return

    def run():
        while True:
            try:
                refresh_batch()
            except Exception:
                LOGGER.exception("Palletways depot monitor failed")
            threading.Event().wait(60)

    threading.Thread(target=run, name="palletways-depot-monitor", daemon=True).start()
