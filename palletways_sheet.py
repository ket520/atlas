"""Resolve Palletways tracking IDs from the workbook's explicit A/B columns."""
import re
import threading
import time
import json

_lock = threading.Lock()
_rows = None
_read_at = 0


def archive_statuses(rows):
    """Join sheet facts by column A, keeping booking values separate from API facts."""
    from delivery_data import connect

    statuses = {}
    consignments = {}
    tracking_numbers = {}
    booking_fields = {"bookedIn": {}, "bookInRequest": {}}
    for row in rows:
        order = str(row.get("order") or "").strip()
        if re.fullmatch(r"\d+\.0", order):
            order = order[:-2]
        status = str(row.get("status") or "")
        if order:
            statuses.setdefault(order, set()).add(status if status.strip() else "")
            number = str(row.get("consignmentNumber") or "").strip()
            if re.fullmatch(r"\d+\.0", number):
                number = number[:-2]
            consignments.setdefault(order, set()).add(number)
            tracking = str(row.get("trackingId") or "").strip()
            if re.fullmatch(r"\d+\.0", tracking):
                tracking = tracking[:-2]
            tracking_numbers.setdefault(order, set()).add(tracking)
            for field, values in booking_fields.items():
                values.setdefault(order, set()).add(str(row.get(field) or ""))
    matched = 0
    with connect() as db:
        for row in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='Palletways'").fetchall():
            delivery = json.loads(row["payload"])
            candidates = statuses.get(row["order_id"], set())
            delivery.pop("palletwaysSheetStatus", None)
            delivery.pop("palletwaysSheetConsignmentNumber", None)
            delivery.pop("palletwaysSheetTrackingNumber", None)
            numbers = consignments.get(row["order_id"], set())
            if len(numbers) == 1 and next(iter(numbers)):
                delivery["palletwaysSheetConsignmentNumber"] = next(iter(numbers))
            tracking = tracking_numbers.get(row["order_id"], set())
            if len(tracking) == 1 and next(iter(tracking)):
                delivery["palletwaysSheetTrackingNumber"] = next(iter(tracking))
            for source, target in (("bookedIn", "palletwaysSheetBookedIn"),
                                   ("bookInRequest", "palletwaysSheetBookInRequest")):
                delivery.pop(target, None)
                values = booking_fields[source].get(row["order_id"], set())
                if len(values) == 1:
                    delivery[target] = next(iter(values))
            if len(candidates) == 1 and next(iter(candidates)):
                delivery["palletwaysSheetStatus"] = next(iter(candidates))
                matched += 1
            db.execute("UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(delivery), row["order_id"]))
        db.commit()
    return matched


def tracking_for_order(order, force=False):
    global _rows, _read_at
    order = str(order).strip()
    if not re.fullmatch(r"\d{1,20}", order):
        raise ValueError("Invalid order number.")
    with _lock:
        if force or _rows is None or time.monotonic() - _read_at >= 300:
            from google_sheets import read_palletways_tracking
            _rows = read_palletways_tracking()
            _read_at = time.monotonic()
        candidates = set()
        for row in _rows:
            source_order = str(row.get("order") or "").strip()
            if re.fullmatch(r"\d+\.0", source_order):
                source_order = source_order[:-2]
            if source_order == order:
                tracking = str(row.get("trackingId") or "").strip()
                if re.fullmatch(r"\d+\.0", tracking):
                    tracking = tracking[:-2]
                if tracking:
                    candidates.add(tracking)
        if len(candidates) > 1:
            raise ValueError("Multiple tracking IDs in column B match this order in column A of the Palletways tab.")
        tracking = next(iter(candidates), "")
        if not re.fullmatch(r"\d{11}", tracking):
            raise ValueError("No valid tracking ID in column B for this order in column A of the Palletways tab.")
        return {"order": order, "trackingId": tracking}
