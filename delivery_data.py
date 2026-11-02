"""Read-only OW delivery snapshot with a persistent, order-keyed local history."""

import json
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from sales_activity import product_items, sku_value, store_code, store_name

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "delivery-desk.sqlite3"
SYNC_LOCK = threading.Lock()
CACHE_SECONDS = 300
INDEX_VERSION = 39
ROUTINE_LIVE_SOURCE = 'Routine Dashboard - Live'
OWN_VAN_CARRIERS = {"Own van", "Self Delivery", "LOCAL MULTIDROP"}
_cache = {"at": None, "payload": None}
_statuses_refreshed = False
_background_lock = threading.Lock()
_background_thread = None
_background_status = {"error": None, "checked_at": None}


def clean(value):
    return str(value or "").strip()


def date_value(value):
    value = clean(value)
    if not value:
        return ""
    for pattern in (
        "%Y-%m-%d",
        "%d/%m/%Y",
        "%d-%m-%Y",
        "%d/%m/%y",
        "%A, %d %B, %Y %I:%M:%S %p",
        "%A, %d %B, %Y",
        "%d %B %Y %I:%M:%S %p",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        pass
    return ""


def carrier_name(value):
    raw = clean(value)
    label = raw.lower()
    if not raw:
        return ""
    if label.startswith("ama ") or label.startswith("amazon shipping"):
        return "AMZ"
    if "palletways" in label or label == "next day (pallet)":
        return "Palletways"
    if "xdp" in label:
        return "XDP"
    if label.startswith("yodel"):
        return "Yodel"
    if label in {"standard van delivery", "next day van delivery", "own van", "own delivery"}:
        return "Own van"
    if label.startswith("self delivery"):
        return "Self Delivery"
    if label.startswith("stopstart"):
        return "Stopstart"
    return {
        "charge pending (remote postcode)": "Charge Pending (Remote Postcode)",
        "collect in person": "Collect in Person",
        "do not pick yet": "Do Not Pick Yet",
        "local multidrop": "LOCAL MULTIDROP",
        "on hold - tbc": "On Hold",
        "to be cancelled": "Cancelled",
        "uk next day delivery": "UK Next Day",
        "wayfair ups": "Wayfair",
    }.get(label, raw)


def delivery_status(raw_status, delivery_method, tracking=None):
    if carrier_name(delivery_method) == 'XDP':
        return 'Awaiting'
    if carrier_name(delivery_method) == "AMZ" and tracking is not None and not clean(tracking):
        return "Unscheduled"
    method = clean(delivery_method).lower()
    if method == "to be cancelled":
        return "Cancelled"
    if method == "on hold - tbc":
        return "Unassigned"
    return ow_status_name(raw_status)


def optimoroute_status_name(value):
    return {
        "unscheduled": "Unscheduled",
        "scheduled": "Out for Delivery",
        "on_route": "Out for Delivery",
        "servicing": "Out for Delivery",
        "success": "Delivered",
        "failed": "Failed",
        "rejected": "Rejected",
        "returned": "Return",
    }.get(clean(value).lower())


def tracking_today(delivery, day=None):
    """Tracking's Today scope uses delivery evidence, never order/despatch dates."""
    day = day or datetime.now(ZoneInfo('Europe/London')).date().isoformat()
    status = clean(delivery.get('st')).lower()
    if status in {'failed', 'rejected', 'lost', 'cancelled', 'return'}:
        return False
    carrier = delivery.get('carrier')
    source = clean(delivery.get('xdpStatus') if carrier == 'XDP' else
                   delivery.get('stopstartStatus') if carrier == 'Stopstart' else
                   delivery.get('palletwaysSheetStatus') if carrier == 'Palletways' else
                   delivery.get('amazonSheetStatus') or delivery.get('amazonStatus')).upper().replace('_', ' ')
    if source in {'DAMAGE', 'DELETE', 'NOT RECEIVED', 'FAILED', 'REJECTED', 'LOST', 'UNDELIVERABLE', 'CANCELLED', 'RETURN'}:
        return False
    if carrier == 'Stopstart' and source == 'EXPECTED TODAY':
        return True
    if carrier == 'XDP' and source == 'NEXT STOP':
        return True
    if carrier == 'Palletways' and source == 'OUT FOR DELIVERY':
        return True
    details = delivery.get('palletwaysDetails') or {}
    stopstart = delivery.get('stopstartDetails') or {}
    dates = [delivery.get('date'), delivery.get('amazonScheduledAt'), delivery.get('providerPlannedDate'),
             details.get('dueAt'), stopstart.get('expectedDate')]
    has_today = any(clean(value)[:10] == day for value in dates)
    return has_today and (status in {'scheduled', 'out for delivery', 'delivered'} or carrier in {'XDP', 'Stopstart'})


def apply_routine_live_status(delivery, db=None):
    """Keep Routine's latest snapshot above normal statuses for Own van only."""
    if delivery.get('carrier') == 'XDP':
        from xdp_sheet import apply_status
        return apply_status(delivery)
    if delivery.get('carrier') != 'Own van':
        return delivery
    if db is not None:
        if not db.in_transaction:
            db.execute('BEGIN IMMEDIATE')
        saved = db.execute('SELECT * FROM routine_live_overrides WHERE order_id=?',
                           (clean(delivery.get('order') or delivery.get('id')),)).fetchone()
        for field in ('routineLiveStatus', 'routineLiveColour', 'routineLiveCell', 'routineLiveObservedAt'):
            delivery.pop(field, None)
        if saved:
            delivery.update(routineLiveStatus=saved['status'], routineLiveColour=saved['colour'],
                            routineLiveCell=saved['cell'], routineLiveObservedAt=saved['observed_at'])
        if db.execute("SELECT 1 FROM sync_metadata WHERE key='routine_live_bookings_snapshot'").fetchone():
            booking = db.execute('SELECT value FROM routine_live_bookings WHERE order_id=?',
                                 (clean(delivery.get('order') or delivery.get('id')),)).fetchone()
            from routine_live import format_booking_status
            delivery['bookingStatus'] = format_booking_status(booking['value'] if booking else '')
            delivery['bookingStatusSource'] = ROUTINE_LIVE_SOURCE
    override = delivery.get('routineLiveStatus')
    if override in {'Failed', 'Scheduled'}:
        delivery['st'] = override
        delivery['statusSource'] = ROUTINE_LIVE_SOURCE
    elif delivery.get('statusSource') == ROUTINE_LIVE_SOURCE:
        provider_status = optimoroute_status_name(delivery.get('providerStatus'))
        delivery['st'] = provider_status or ow_status_name(delivery.get('rawStatus'))
        delivery['statusSource'] = 'OptimoRoute' if provider_status else 'OW'
    return delivery


def amazon_status_name(value):
    return {
        "OUT_FOR_DELIVERY": "Out for Delivery",
        "DELIVERED": "Delivered",
        "IN_TRANSIT": "Scheduled",
        "READY_FOR_RECEIVE": "Scheduled",
        "LOST": "Failed",
        "UNDELIVERABLE": "Failed",
    }.get(clean(value).upper())


def amazon_scheduled_time(value):
    """Convert Amazon's explicitly UTC schedule to UK local time, including BST."""
    raw = clean(value)
    try:
        moment = datetime.strptime(raw, "%d/%m/%Y %H:%M (UTC)").replace(tzinfo=timezone.utc)
    except ValueError:
        return ""
    return moment.astimezone(ZoneInfo("Europe/London")).isoformat()


def palletways_status_name(value, completed=""):
    raw = clean(value).upper()
    if raw == "JOB COMPLETE":
        return "Delivered"
    if raw in {"OUT FOR DELIVERY", "ON DELIVERY VEHICLE"}:
        return "Out for Delivery"
    if raw in {
        "IN COLLECTION DEPOT",
        "AT COLLECTION DEPOT",
        "AT THE HUB",
        "TRUNKED TO HUB",
        "DEPARTED HUB",
        "AT DELIVERY DEPOT",
    }:
        return "Scheduled"
    if re.search(r"\bfailed delivery\b", raw):
        return "Failed"
    if "REJECT" in raw or raw == "DELETED":
        return "Rejected"
    if "RETURN" in raw:
        return "Return"
    return None





def palletways_app_status(value):
    return {
        "Delivered": "Delivered",
        "Out for Delivery": "Out for Delivery",
        "In Transit": "Scheduled",
        "Scheduled": "Scheduled",
        "Unscheduled": "Unscheduled",
        "Failed": "Failed",
        "Damaged": "Failed",
        "Refused": "Rejected",
        "Lost": "Lost",
        "Return": "Return",
    }.get(clean(value))



def palletways_tracking_id(delivery):
    candidates = (
        delivery.get("trk"),
        delivery.get("owTrackingNo"),
    )

    for value in candidates:
        value = clean(value)

        if re.fullmatch(r"\d{11}", value):
            return value

    return ""

def apply_palletways_api_data():
    """
    Apply Palletways API history stored in SQLite to OrderWise deliveries.

    OrderWise supplies the order/tracking relationship.
    Palletways supplies the physical shipment status.
    """
    from palletways_live import derive_status
    from palletways_store import ensure_schema

    ensure_schema()

    events_by_tracking = {}
    shipments_by_tracking = {}
    shipments_by_reference = {}

    with connect() as db:

        for row in db.execute(
            """
            SELECT
                tracking_id,
                raw_json
            FROM palletways_events
            ORDER BY
                CAST(delta AS INTEGER),
                note_date,
                note_time
            """
        ):
            try:
                event = json.loads(
                    row["raw_json"]
                )
            except (TypeError, ValueError):
                continue

            tracking = clean(
                row["tracking_id"]
            )

            if not tracking:
                continue

            events_by_tracking.setdefault(
                tracking,
                [],
            ).append(event)

        for row in db.execute(
            """
            SELECT
                tracking_id,
                order_reference,
                raw_json
            FROM palletways_shipments
            """
        ):
            tracking = clean(
                row["tracking_id"]
            )

            reference = clean(
                row["order_reference"]
            )

            if not tracking:
                continue

            try:
                consignment = json.loads(
                    row["raw_json"]
                )
            except (TypeError, ValueError):
                consignment = {}

            shipments_by_tracking[
                tracking
            ] = consignment

            if reference:
                shipments_by_reference[
                    reference
                ] = {
                    "trackingId": tracking,
                    "consignment": consignment,
                }

        matched = 0

        rows = list(
            db.execute(
                """
                SELECT
                    order_id,
                    payload
                FROM deliveries
                WHERE json_extract(
                    payload,
                    '$.carrier'
                ) = 'Palletways'
                """
            )
        )

        for row in rows:

            order_id = row["order_id"]

            delivery = json.loads(
                row["payload"]
            )

            tracking = palletways_tracking_id(
                delivery
            )

            consignment = {}

            if tracking:
                consignment = (
                    shipments_by_tracking.get(
                        tracking,
                        {},
                    )
                )

            if not tracking:
                order_key = clean(
                    delivery.get("order")
                    or order_id
                )

                linked_shipment = (
                    shipments_by_reference.get(
                        order_key
                    )
                )

                if linked_shipment:
                    tracking = clean(
                        linked_shipment.get(
                            "trackingId"
                        )
                    )

                    consignment = (
                        linked_shipment.get(
                            "consignment"
                        )
                        or {}
                    )

            # Kill old Google-Sheet Palletways state.
            delivery.pop(
                "palletwaysStatus",
                None,
            )

            delivery.pop(
                "palletwaysVerification",
                None,
            )

            delivery.pop(
                "palletwaysDetails",
                None,
            )

            if not tracking:
                delivery["palletwaysLookup"] = (
                    "no_tracking"
                )

                delivery["st"] = ow_status_name(
                    delivery.get("rawStatus")
                )

                delivery["statusSource"] = "OW"

                db.execute(
                    """
                    UPDATE deliveries
                    SET payload=?
                    WHERE order_id=?
                    """,
                    (
                        json.dumps(apply_routine_live_status(delivery, db)),
                        order_id,
                    ),
                )

                continue

            delivery["trk"] = tracking

            delivery["trackingUrl"] = (
                palletways_tracking_url(
                    tracking
                )
            )

            events = events_by_tracking.get(
                tracking,
                [],
            )

            if not events and not consignment:

                delivery[
                    "palletwaysLookup"
                ] = "not_found"

                delivery["st"] = ow_status_name(
                    delivery.get("rawStatus")
                )

                delivery[
                    "statusSource"
                ] = "OW"

                db.execute(
                    """
                    UPDATE deliveries
                    SET payload=?
                    WHERE order_id=?
                    """,
                    (
                        json.dumps(apply_routine_live_status(delivery, db)),
                        order_id,
                    ),
                )

                continue



            delivery[
                "palletwaysLookup"
            ] = "matched"

            result = derive_status(
                events,
                consignment,
            )

            live_status = clean(
                result.get("status")
            )

            live_label = clean(
                result.get("label")
            )

            mapped = palletways_app_status(
                live_status
            )

            if mapped:
                delivery["st"] = mapped

                delivery[
                    "statusSource"
                ] = "Palletways"

            else:
                delivery["st"] = ow_status_name(
                    delivery.get("rawStatus")
                )

                delivery[
                    "statusSource"
                ] = "OW"

            delivery[
                "palletwaysStatusLabel"
            ] = (
                live_label
                or live_status
                or delivery["st"]
            )

            status_event = (
                result.get("event")
                or {}
            )

            if delivery["st"] == "Delivered":

                completed_date = clean(
                    status_event.get(
                        "podDate"
                    )
                    or status_event.get(
                        "date"
                    )
                )

                completed_time = clean(
                    status_event.get(
                        "podTime"
                    )
                    or status_event.get(
                        "time"
                    )
                )

                if completed_date:

                    delivery[
                        "completedAt"
                    ] = (
                        f"{completed_date}"
                        f"T{completed_time}"
                        if completed_time
                        else completed_date
                    )

            else:
                # Do not retain completion
                # dates from the old sheet.
                delivery.pop(
                    "completedAt",
                    None,
                )

            booking_event = next(
                (
                    event
                    for event
                    in reversed(events)
                    if clean(
                        event.get(
                            "bookInDate"
                        )
                    )
                ),
                None,
            )

            due_date = clean(
                consignment.get("DueDate")
            )

            if not due_date and booking_event:
                due_date = clean(
                    booking_event.get(
                        "bookInDate"
                    )
                )

            if due_date:
                delivery["date"] = date_value(
                    due_date
                )

            services = (
                consignment.get("Service")
                or []
            )

            service_text = []

            for service in services:
                if not isinstance(
                    service,
                    dict,
                ):
                    continue

                parts = [
                    clean(
                        service.get("Type")
                    ),
                    clean(
                        service.get("Code")
                    ),
                ]

                parts = [
                    part
                    for part in parts
                    if part
                ]

                if parts:
                    service_text.append(
                        " ".join(parts)
                    )

            addresses = (
                consignment.get("Address")
                or []
            )

            delivery_address = next(
                (
                    address
                    for address in addresses
                    if isinstance(
                        address,
                        dict,
                    )
                    and clean(
                        address.get("Type")
                    ).lower()
                    == "delivery"
                ),
                {},
            )

            address_lines = (
                delivery_address.get("Line")
                or []
            )

            if not address_lines:
                address_lines = [
                    delivery_address.get(
                        "Addr1"
                    ),
                    delivery_address.get(
                        "Addr2"
                    ),
                    delivery_address.get(
                        "Town2"
                    ),
                    delivery_address.get(
                        "Town"
                    ),
                    delivery_address.get(
                        "County"
                    ),
                ]

            address_text = ", ".join(
                clean(value)
                for value in address_lines
                if clean(value)
            )

            delivery[
                "palletwaysDetails"
            ] = {
                "consignmentNumber":
                    clean(
                        consignment.get(
                            "Number"
                        )
                    ),
                "customerRef":
                    clean(
                        consignment.get(
                            "Reference"
                        )
                    ),
                "trackingId":
                    tracking,
                "type":
                    clean(
                        consignment.get(
                            "Type"
                        )
                    ),
                "classification":
                    clean(
                        consignment.get(
                            "Classification"
                        )
                    ),
                "weight":
                    clean(
                        consignment.get(
                            "Weight"
                        )
                    ),
                "lifts":
                    clean(
                        consignment.get(
                            "Lifts"
                        )
                    ),
                "collectionDepot":
                    clean(
                        consignment.get(
                            "CollectionDepot"
                        )
                    ),
                "deliveryDepot":
                    clean(
                        consignment.get(
                            "DeliveryDepot"
                        )
                    ),
                "dueDate":
                    date_value(
                        consignment.get(
                            "DueDate"
                        )
                    ),
                "dueTime":
                    clean(
                        consignment.get(
                            "DueTime"
                        )
                    ),
                "bookedIn":
                    clean(
                        consignment.get(
                            "BookedIn"
                        )
                    ),
                "bookInRequest":
                    clean(
                        consignment.get(
                            "BookInRequest"
                        )
                    ),
                "bookInContactName":
                    clean(
                        consignment.get(
                            "BookInContactName"
                        )
                    ),
                "bookInReference":
                    clean(
                        consignment.get(
                            "BookInReference"
                        )
                    ),
                "manifestNote":
                    clean(
                        consignment.get(
                            "ManifestNote"
                        )
                    ),
                "pallets":
                    consignment.get(
                        "Pallet"
                    )
                    or [],
                "billUnits":
                    consignment.get(
                        "BillUnit"
                    )
                    or [],
                "services":
                    services,
                "deliveryService":
                    " · ".join(
                        service_text
                    ),
                "deliveryAddress":
                    address_text,
                "deliveryPostcode":
                    clean(
                        delivery_address.get(
                            "PostCode"
                        )
                    ),
                "deliveryTelephone":
                    clean(
                        delivery_address.get(
                            "Telephone"
                        )
                    ),
                "status":
                    live_status,
                "statusLabel":
                    live_label,
            }

            if mapped in {
                "Failed",
                "Rejected",
                "Lost",
                "Return",
            }:
                delivery["reason"] = (
                    clean(
                        status_event.get(
                            "text"
                        )
                    )
                    or live_label
                )
            elif delivery.get(
                "statusSource"
            ) == "Palletways":
                delivery["reason"] = ""

            db.execute(
                """
                UPDATE deliveries
                SET payload=?
                WHERE order_id=?
                """,
                (
                    json.dumps(apply_routine_live_status(delivery, db)),
                    order_id,
                ),
            )

        db.commit()

    return matched





def ow_status_name(value):
    """Group OW order statuses into the delivery table's existing categories."""
    raw = clean(value).upper()
    return {
        "W": "Unscheduled",
        "K": "Unscheduled",
        "H": "Unscheduled",
        "P": "Scheduled",
        "I": "Unscheduled",
        "C": "Delivered",
        "X": "Cancelled",
        "S": "Scheduled",
        "A": "Unscheduled",
        "U": "Unscheduled",
        "Y": "Unscheduled",
        "SCHEDULED": "Scheduled",
        "UNSCHEDULED": "Unscheduled",
        "DELIVERED": "Delivered",
        "COMPLETE": "Delivered",
        "COMPLETED": "Delivered",
        "FAILED DELIVERY": "Failed",
        "FAILED": "Failed",
        "OUT FOR DELIVERY": "Out for Delivery",
        "REJECTED": "Rejected",
        "RETURN": "Return",
    }.get(raw, "Unscheduled")




def apply_optimoroute_fields(delivery, source):
    """Keep useful provider fields without copying the complete API response."""
    previous_schedule = delivery.get("providerScheduledAt") or delivery.get("providerPlannedDate")
    incoming_schedule = source.get("scheduledAt") or source.get("plannedDate")
    if (
        previous_schedule and incoming_schedule and previous_schedule != incoming_schedule
        and (len(str(previous_schedule)) > 10 or str(previous_schedule)[:10] != str(incoming_schedule)[:10])
    ):
        history = delivery.setdefault("scheduleHistory", [])
        if previous_schedule not in history:
            history.append(previous_schedule)
    completion = source.get("completedAt") or {}
    status = clean(source.get("status")).lower()
    if isinstance(completion, dict) and status in {"failed", "success"}:
        completed_at = completion.get("utcTime") or completion.get("localTime")
        if completion.get("unixTimestamp") is not None:
            completed_at = datetime.fromtimestamp(completion["unixTimestamp"], timezone.utc).isoformat()
        if completed_at:
            attempts = delivery.setdefault("providerAttemptHistory", [])
            attempt = {"status": status, "at": completed_at, "note": clean(source.get("podNote"))}
            if not any(item.get("status") == status and item.get("at") == completed_at for item in attempts):
                attempts.append(attempt)
            if status == "failed":
                delivery["failedAt"] = completed_at
    fields = {
        "providerOrderId": source.get("id"),
        "providerOrderNo": source.get("providerOrderNo"),
        "providerLocation": source.get("customer"),
        "providerAddress": source.get("address"),
        "providerLatitude": source.get("latitude"),
        "providerLongitude": source.get("longitude"),
        "providerOrderType": source.get("orderType"),
        "providerDriver": source.get("driver"),
        "providerVehicle": source.get("vehicle"),
        "providerStopNumber": source.get("stopNumber"),
        "providerPlannedDate": source.get("plannedDate"),
        "providerScheduledAt": source.get("scheduledAt"),
        "providerStartedAt": source.get("startedAt"),
        "providerEndedAt": source.get("completedAt"),
        "providerPlannedDuration": source.get("plannedDuration"),
        "providerTimeWindows": source.get("timeWindows"),
        "providerInstructions": source.get("instructions"),
        "providerLocationNotes": source.get("locationNotes"),
        "providerPodNote": source.get("podNote"),
        "providerPhone": source.get("phone"),
        "providerEmail": source.get("email"),
        "providerCompletionPosition": source.get("completionPosition"),
        "providerCompletionError": source.get("completionError"),
        "providerCustomerFeedback": source.get("customerFeedback"),
        "providerBarcodes": source.get("barcodes"),
    }
    for key, value in fields.items():
        if value not in (None, "", [], {}):
            delivery[key] = value
    photos = []
    seen = set()
    for photo in source.get("photos") or []:
        url = clean(photo.get("url")) if isinstance(photo, dict) else ""
        if url and url not in seen:
            photos.append({"url": url, "kind": "Photo"})
            seen.add(url)
    signature = source.get("signature")
    signature_url = clean(signature.get("url")) if isinstance(signature, dict) else ""
    if signature_url and signature_url not in seen:
        photos.append({"url": signature_url, "kind": "Signature"})
    if photos:
        delivery["podPhotos"] = photos
        delivery["podUrl"] = photos[0]["url"]
        delivery["podImageUrl"] = photos[0]["url"]


def palletways_tracking_url(value):
    tracking_id = clean(value)
    if re.fullmatch(r"\d{11}", tracking_id):
        return f"https://track2.palletways.com/?dc_syscon={tracking_id}"
    return ""


def apply_verified_palletways(delivery):
    """Apply individually checked public tracking facts over a stale sheet row."""
    if delivery.get("carrier") != "Palletways":
        return False
    path = ROOT / "data" / "palletways_verified.json"
    if not path.exists():
        return False
    facts = json.loads(path.read_text(encoding="utf-8"))
    tracking = clean(delivery.get("trk"))
    fact = facts.get(tracking)
    if not fact or clean(fact.get("order")) != clean(delivery.get("order")):
        return False
    due_at = clean(fact.get("scheduledDueAt"))
    if due_at:
        delivery["date"] = date_value(due_at)
        delivery.setdefault("palletwaysDetails", {})["dueAt"] = due_at
    completed_at = clean(fact.get("completedAt"))
    if completed_at and (delivery.get("st") != "Delivered" or not delivery.get("completedAt")):
        delivery["completedAt"] = completed_at
        delivery["palletwaysStatus"] = "JOB COMPLETE"
        delivery["palletwaysDetails"]["status"] = "JOB COMPLETE"
        delivery["palletwaysDetails"]["dateCompleted"] = datetime.fromisoformat(completed_at).strftime("%d/%m/%Y - %H:%M")
        delivery["st"] = "Delivered"
        delivery["statusSource"] = "Palletways"
    delivery["palletwaysVerification"] = fact.get("evidence", "")
    return True


def row_sku_items(row):
    """Read item SKUs, accepting the parent-SKU header used by OW exports."""
    return sku_value(row)


def row_to_delivery(row):
    order = clean(row.get("Order no"))
    carrier = carrier_name(row.get("Delivery method"))
    if not order or not carrier:
        return None
    tracking = clean(row.get("Tracking No"))
    postcode = clean(row.get("Delivery postcode"))
    address = clean(row.get("Address"))
    full_address = address
    if postcode and re.sub(r"\s+", "", postcode).casefold() not in re.sub(r"\s+", "", address).casefold():
        full_address = ", ".join(part for part in (address, postcode) if part)
    raw_status = clean(row.get("Status"))
    return {
        "id": order,
        "order": order,
        "orderRef": clean(row.get("Order reference")),
        "cust": clean(row.get("Delivery name")) or order,
        "phone": clean(row.get("Delivery telephone")),
        "email": clean(row.get("Delivery email")),
        "addr": full_address or postcode,
        "address": address,
        "postcode": postcode,
        "specialInstructions": clean(row.get("Special instructions")),
        "skuItems": row_sku_items(row),
        "items": product_items([row]),
        "productSkuItems": [item['sku'] for item in product_items([{'Product SKU': row.get('Product SKU')}])],
        "salesActivityDetails": {name: clean(row.get(name)) for name in (
            "eCommerce order number", "Order Type", "Order Analysis", "Replacement",
            "Original order Number", "Original order ID", "Gross (base)", "Customer",
            "EbayUserID", "Order Type ID", "Delivery cost", "Order Category",
        )},
        "storeCode": store_code(row),
        "purchaseStore": store_name(store_code(row), row.get('Order Type'), row.get('Order Analysis')),
        "carrier": carrier,
        "type": "Van" if carrier in OWN_VAN_CARRIERS else "External",
        "trk": tracking,
        "owTrackingNo": tracking,
        "st": delivery_status(raw_status, row.get("Delivery method"), tracking),
        "statusSource": "XDP fallback" if carrier == 'XDP' else "OW",
        "rawStatus": raw_status,
        "deliveryMethodRaw": clean(row.get("Delivery method")),
        "orderDate": date_value(row.get("Order date")),
        "orderDateTime": clean(row.get("Order date")),
        "dispatchDate": date_value(row.get("Despatch Date")),
        "date": "",
        "win": "",
        "eta": "",
        "trackingUrl": "",
        "podUrl": "",
        "fu": "",
        "reason": "",
        "src": "OW",
        "logs": [],
    }


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=20)
    db.row_factory = sqlite3.Row
    db.create_function('purchase_store', 1, lambda payload: purchase_store(json.loads(payload)), deterministic=True)
    db.create_function('tracking_today', 2, lambda payload, day: int(tracking_today(json.loads(payload), day)), deterministic=True)
    shipment_classes, reference_classes = {}, {}
    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='palletways_shipments'").fetchone():
        for shipment in db.execute('SELECT tracking_id, order_reference, classification FROM palletways_shipments'):
            shipment_classes[clean(shipment['tracking_id'])] = clean(shipment['classification']).upper()
            reference = clean(shipment['order_reference'])
            if reference:
                reference_classes.setdefault(reference, []).append(clean(shipment['classification']).upper())

    def palletways_classification(payload):
        delivery = json.loads(payload)
        if delivery.get('carrier') != 'Palletways':
            return ''
        details = delivery.get('palletwaysDetails') or {}
        for tracking in (details.get('trackingId'), delivery.get('trk'), delivery.get('owTrackingNo')):
            classification = shipment_classes.get(clean(tracking))
            if classification:
                return classification
        matches = reference_classes.get(clean(delivery.get('order') or delivery.get('id')), [])
        if len(matches) == 1 and matches[0]:
            return matches[0]
        return clean(details.get('classification')).upper()

    db.create_function('palletways_classification', 1, palletways_classification, deterministic=True)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS deliveries (
            order_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
            first_seen TEXT NOT NULL, last_seen TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS activity (
            order_id TEXT NOT NULL, at TEXT NOT NULL, text TEXT NOT NULL,
            PRIMARY KEY(order_id, at, text));
        CREATE TABLE IF NOT EXISTS sync_metadata (
            key TEXT PRIMARY KEY, payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sales_activity_orders (
            order_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS routine_live_overrides (
            order_id TEXT PRIMARY KEY, status TEXT NOT NULL, colour TEXT NOT NULL,
            cell TEXT NOT NULL, observed_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS routine_live_bookings (
            order_id TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TRIGGER IF NOT EXISTS keep_self_delivery_on_insert
        AFTER INSERT ON deliveries
        WHEN json_extract(NEW.payload, '$.deliveryMethodRaw') IN ('Self Delivery', 'Self Delivery BQ')
             AND json_extract(NEW.payload, '$.carrier') != 'Self Delivery'
        BEGIN
            UPDATE deliveries SET payload=json_set(NEW.payload, '$.carrier', 'Self Delivery', '$.type', 'Van')
            WHERE order_id=NEW.order_id;
        END;
        CREATE TRIGGER IF NOT EXISTS keep_self_delivery_on_update
        AFTER UPDATE ON deliveries
        WHEN json_extract(NEW.payload, '$.deliveryMethodRaw') IN ('Self Delivery', 'Self Delivery BQ')
             AND json_extract(NEW.payload, '$.carrier') != 'Self Delivery'
        BEGIN
            UPDATE deliveries SET payload=json_set(NEW.payload, '$.carrier', 'Self Delivery', '$.type', 'Van')
            WHERE order_id=NEW.order_id;
        END;
    """)
    try:
        yield db
    finally:
        db.close()


def archive(rows, observed_at=None):
    rows = list(rows)
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    normalized = []
    grouped = {}
    source_orders = set()
    for row in rows:
        # worksheet_to_records preserves physical column order: A is the OW ID.
        source_order = clean(next(iter(row.values()), ''))
        if source_order:
            source_orders.add(source_order)
        delivery = row_to_delivery(row)
        if delivery:
            normalized.append(delivery)
            group = grouped.setdefault(delivery["order"], {"rows": []})
            group["rows"].append(row)
            group["delivery"] = delivery
    for group in grouped.values():
        delivery = group["delivery"]
        delivery["items"] = product_items(group["rows"])
        delivery['productSkuItems'] = list(dict.fromkeys(item['sku'] for row in group['rows']
            for item in product_items([{'Product SKU': row.get('Product SKU')}])) )
        delivery["skuItems"] = ", ".join(dict.fromkeys(item["sku"] for item in delivery["items"]))
    with connect() as db:
        # Replace source membership in the same transaction as the OW import.
        # Retained delivery history is deliberately not deleted.
        db.execute('BEGIN IMMEDIATE')
        from tracking_relations import archive as archive_relations
        archive_relations(db, rows)
        db.execute('DELETE FROM sales_activity_orders')
        db.executemany('INSERT INTO sales_activity_orders VALUES (?)',
                       [(order,) for order in source_orders])
        for group in grouped.values():
            delivery = group["delivery"]
            order = delivery["order"]
            previous = db.execute(
                "SELECT payload, first_seen FROM deliveries WHERE order_id=?", (order,)
            ).fetchone()
            first_seen = previous["first_seen"] if previous else observed_at
            if not previous:
                event_at = (
                    delivery["orderDate"] + "T00:00:00" if delivery["orderDate"] else observed_at
                )
                db.execute(
                    "INSERT OR IGNORE INTO activity VALUES (?,?,?)",
                    (order, event_at, "Order received from OW"),
                )
            else:
                old = json.loads(previous["payload"])
                if delivery['carrier'] == 'Own van' and old.get('carrier') == 'Own van':
                    for field in ('routineLiveStatus', 'routineLiveColour', 'routineLiveCell', 'routineLiveObservedAt'):
                        if old.get(field):
                            delivery[field] = old[field]
                for field in (
                    "date",
                    "win",
                    "eta",
                    "trackingUrl",
                    "podUrl",
                    "podImageUrl",
                    "podPhotos",
                    "bookingStatus",
                    "skuItems",
                    "completedAt",
                    "failedAt",
                    "reason",
                    "fu",
                    "providerCheckedAt",
                    "carrierIssueEntries",
                    "followUps",
                    "carrierIssueReason",
                    "carrierIssueNote",
                    "carrierIssueDate",
                    "carrierIssueDispatchDate",
                    "carrierIssueFailure",
                    "failedDate",
                    "messagedStatus",
                    "scheduledStatus",
                    "scheduleHistory",
                    "providerAttemptHistory",
                    "deliveredStatus",
                    "cancellationRecord",
                    "completedVanRecord",
                    "palletwaysDetails",
                    "palletwaysDetails",
                    "palletwaysVerification",
                    "stopstartDetails",
                    "stopstartEvents",
                    "stopstartCheckedAt",
                    "stopstartAmbiguous",
                    "stopstartTrackability",
                ):
                    if field == 'bookingStatus' and delivery['carrier'] != 'Own van' and old.get('bookingStatusSource') == ROUTINE_LIVE_SOURCE:
                        continue
                    if old.get(field) and not delivery.get(field):
                        delivery[field] = old[field]
                if (delivery["carrier"] == "AMZ" and delivery["trk"]
                    and clean(old.get("owTrackingNo") or old.get("trk")).upper() == delivery["trk"].upper()
                    and old.get("amazonSheetStatus")):
                    delivery["amazonSheetStatus"] = old["amazonSheetStatus"]
                if delivery["carrier"] == "Stopstart" and old.get("carrier") == "Stopstart" and old.get("stopstartStatus"):
                    delivery["stopstartStatus"] = old["stopstartStatus"]
                if delivery["carrier"] == "Palletways" and old.get("carrier") == "Palletways" and old.get("palletwaysSheetStatus"):
                    delivery["palletwaysSheetStatus"] = old["palletwaysSheetStatus"]
                if delivery["carrier"] == "Palletways" and old.get("carrier") == "Palletways" and old.get("palletwaysSheetConsignmentNumber"):
                    delivery["palletwaysSheetConsignmentNumber"] = old["palletwaysSheetConsignmentNumber"]
                if delivery["carrier"] == "Palletways" and old.get("carrier") == "Palletways":
                    for field in ("palletwaysSheetTrackingNumber", "palletwaysSheetBookedIn", "palletwaysSheetBookInRequest"):
                        if field in old:
                            delivery[field] = old[field]
                if delivery['carrier'] == 'XDP' and old.get('carrier') == 'XDP' and old.get('xdpConsignmentNo'):
                    delivery['xdpConsignmentNo'] = old['xdpConsignmentNo']
                if (delivery["carrier"] == "XDP" and old.get("carrier") == "XDP"
                    and clean(old.get("owTrackingNo") or old.get("trk")) == delivery["trk"]):
                    if old.get("xdpDocuments"):
                        delivery["xdpDocuments"] = old["xdpDocuments"]
                    if old.get("xdpParcelBarcodes"):
                        delivery["xdpParcelBarcodes"] = old["xdpParcelBarcodes"]
                    if old.get("xdpLatestDetail"):
                        delivery["xdpLatestDetail"] = old["xdpLatestDetail"]
                    if old.get("xdpEvents"):
                        delivery["xdpEvents"] = old["xdpEvents"]
                    if old.get("xdpActivityError"):
                        delivery["xdpActivityError"] = old["xdpActivityError"]
                    for field in ('xdpActivitySource', 'xdpActivityStatus', 'xdpActivityFingerprint'):
                        if old.get(field):
                            delivery[field] = old[field]
                if (delivery["carrier"] == "XDP" and old.get("carrier") == "XDP"
                    and clean(old.get("owTrackingNo") or old.get("trk")) == delivery["trk"]
                    and old.get("xdpStatus")):
                    delivery["xdpStatus"] = old["xdpStatus"]
                if (delivery["carrier"] == "AMZ"
                    and delivery["trk"]
                    and clean(old.get("amazonTrackingId")).upper() == clean(delivery["trk"]).upper()
                    and amazon_status_name(old.get("amazonStatus"))):
                    delivery["amazonTrackingId"] = old["amazonTrackingId"]
                    delivery["amazonStatus"] = old["amazonStatus"]
                    if old.get("amazonScheduledAt"):
                        delivery["amazonScheduledAt"] = old["amazonScheduledAt"]
                    delivery["st"] = amazon_status_name(old["amazonStatus"])
                    delivery["statusSource"] = "Amazon Shipping"
                elif delivery["carrier"] in OWN_VAN_CARRIERS and old.get("providerStatus"):
                    delivery["providerStatus"] = old["providerStatus"]
                    mapped = optimoroute_status_name(old["providerStatus"])
                    delivery["st"] = mapped or delivery["st"]
                    delivery["statusSource"] = "OptimoRoute" if mapped else "OW"
                elif delivery["carrier"] in OWN_VAN_CARRIERS and old.get("providerLookup") == "not_found":
                    delivery["providerLookup"] = "not_found"
                    delivery["st"] = ow_status_name(delivery.get("rawStatus"))
                    delivery["statusSource"] = "OW"

                if (delivery["carrier"] == "AMZ" and old.get("amazonScheduledAt")
                    and clean(old.get("owTrackingNo") or old.get("trk")).upper() != clean(delivery["trk"]).upper()):
                    delivery["date"] = ""
                elif delivery["carrier"] == "AMZ" and old.get("amazonScheduledAt"):
                    delivery["amazonScheduledAt"] = old["amazonScheduledAt"]
            db.execute(
                "INSERT OR REPLACE INTO deliveries VALUES (?,?,?,?)",
                (order, json.dumps(apply_routine_live_status(delivery, db)), first_seen, observed_at),
            )
        db.execute('INSERT OR REPLACE INTO sync_metadata VALUES (?,?)',
                   ('sales_activity_orders_snapshot', json.dumps({'observedAt': observed_at})))
        db.commit()
    return len(normalized)


def archive_amazon_shipping(rows, observed_at=None):
    """Use Amazon statuses only for AMZ orders matched by their OW tracking ID."""
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    statuses = {}
    schedules = {}
    ambiguous = set()
    for row in rows:
        tracking = clean(row.get("trackingId")).upper()
        raw = clean(row.get("status")).upper()
        if not tracking:
            continue
        if tracking in statuses and statuses[tracking] != raw:
            ambiguous.add(tracking)
        statuses[tracking] = raw
        schedules[tracking] = amazon_scheduled_time(row.get("scheduledAt"))
    matched = 0
    with connect() as db:
        for row in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='AMZ'"):
            delivery = json.loads(row["payload"])
            tracking = clean(delivery.get("owTrackingNo") or delivery.get("trk")).upper()
            raw = statuses.get(tracking) if tracking not in ambiguous else None
            mapped = amazon_status_name(raw)
            delivery.pop("amazonSheetStatus", None)
            if raw:
                delivery["amazonSheetStatus"] = raw
            previous = (delivery.get("st"), delivery.get("statusSource"))
            delivery.pop("amazonStatus", None)
            delivery.pop("amazonTrackingId", None)
            if delivery.pop("amazonScheduledAt", None):
                delivery["date"] = ""
            scheduled = schedules.get(tracking) if tracking not in ambiguous else None
            if scheduled:
                delivery["amazonScheduledAt"] = scheduled
                delivery["date"] = scheduled[:10]
            if mapped:
                delivery.update(amazonStatus=raw, amazonTrackingId=tracking, st=mapped, statusSource="Amazon Shipping")
                matched += 1
            else:
                delivery["st"] = delivery_status(delivery.get("rawStatus"), delivery.get("deliveryMethodRaw"), tracking)
                delivery["statusSource"] = "OW"
            if previous != (delivery["st"], delivery["statusSource"]):
                text = f"Amazon Shipping status observed: {raw}" if mapped else "Amazon Shipping match unavailable; using OW status"
                db.execute("INSERT OR IGNORE INTO activity VALUES (?,?,?)", (row["order_id"], observed_at, text))
            db.execute("UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(apply_routine_live_status(delivery, db)), row["order_id"]))
        db.commit()
    return matched


def archive_routine_live(rows, observed_at=None, booking_rows=None):
    """Replace the previous live override snapshot, restoring fallback for absent orders."""
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    by_order = {}
    for row in rows:
        order = clean(row.get('order'))
        if not re.fullmatch(r'\d{6}', order) or row.get('status') not in {'Failed', 'Scheduled'}:
            continue
        # If an order occurs more than once, a yellow Failed entry takes priority.
        if order not in by_order or row['status'] == 'Failed':
            by_order[order] = row
    matched = 0
    with connect() as db:
        db.execute('BEGIN IMMEDIATE')
        db.execute('DELETE FROM routine_live_overrides')
        db.executemany('INSERT INTO routine_live_overrides VALUES (?,?,?,?,?)',
                       [(order, entry['status'], entry.get('colour', ''), entry.get('cell', ''), observed_at)
                        for order, entry in by_order.items()])
        if booking_rows is not None:
            booking_values = {}
            for entry in booking_rows:
                order = clean(entry.get('order'))
                if re.fullmatch(r'\d{6}', order):
                    booking_values.setdefault(order, set()).add(clean(entry.get('bookingStatus')))
            db.execute('DELETE FROM routine_live_bookings')
            db.executemany('INSERT INTO routine_live_bookings VALUES (?,?)',
                           [(order, next(iter(values)) if len(values) == 1 else '')
                            for order, values in booking_values.items()])
            db.execute('INSERT OR REPLACE INTO sync_metadata VALUES (?,?)',
                       ('routine_live_bookings_snapshot', json.dumps({'observedAt': observed_at})))
        for saved in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='Own van'").fetchall():
            delivery = json.loads(saved['payload'])
            previous = (delivery.get('st'), delivery.get('statusSource'))
            previous_booking = clean(delivery.get('bookingStatus'))
            current = by_order.get(saved['order_id'])
            for field in ('routineLiveStatus', 'routineLiveColour', 'routineLiveCell', 'routineLiveObservedAt'):
                delivery.pop(field, None)
            if current:
                delivery.update(routineLiveStatus=current['status'], routineLiveColour=current.get('colour', ''),
                                routineLiveCell=current.get('cell', ''), routineLiveObservedAt=observed_at)
                matched += 1
            apply_routine_live_status(delivery, db)
            if previous_booking != clean(delivery.get('bookingStatus')):
                text = f"{ROUTINE_LIVE_SOURCE} booking status: {delivery.get('bookingStatus') or '(cleared)'}"
                db.execute('INSERT OR IGNORE INTO activity VALUES (?,?,?)', (saved['order_id'], observed_at, text))
            if previous != (delivery.get('st'), delivery.get('statusSource')):
                text = (f"{ROUTINE_LIVE_SOURCE}: {delivery['st']} ({current.get('colour', '')}, {current.get('cell', '')})"
                        if current else f"{ROUTINE_LIVE_SOURCE}: override removed; using {delivery.get('statusSource')} status {delivery.get('st')}")
                db.execute('INSERT OR IGNORE INTO activity VALUES (?,?,?)', (saved['order_id'], observed_at, text))
            db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(apply_routine_live_status(delivery, db)), saved['order_id']))
        db.commit()
    return matched


def archive_routine_dashboard(rows):
    """Attach Routine DASHBOARD statuses to orders identified in its Order ID field."""
    allowed = {
        "on hold": "On Hold",
        "onhold": "On Hold",
        "hold": "On Hold",
        "asap": "ASAP",
        "open": "Open",
        "out of stock": "Out of Stock",
        "o/s": "Out of Stock",
    }
    by_order = {}
    ambiguous = set()
    for row in rows:
        order_cell = clean(row.get("Order ID"))
        if re.fullmatch(r"\d+\.0", order_cell):
            order_cell = order_cell[:-2]
        orders = (
            [order_cell]
            if order_cell.isdigit()
            else re.findall(r"(?<!\d)\d{6}(?!\d)", order_cell)
        )
        raw_status = row.get("Status")
        status = (
            raw_status.strftime("%d/%m/%Y")
            if isinstance(raw_status, (date, datetime))
            else allowed.get(re.sub(r"\s+", " ", clean(raw_status).lower()), clean(raw_status))
        )
        if not status:
            continue
        for order in set(orders):
            if order in by_order and by_order[order] != status:
                ambiguous.add(order)
            by_order[order] = status
    updated = 0
    with connect() as db:
        for order, status in by_order.items():
            if order in ambiguous:
                continue
            existing = db.execute(
                "SELECT payload FROM deliveries WHERE order_id=?", (order,)
            ).fetchone()
            if not existing:
                continue
            delivery = json.loads(existing["payload"])
            delivery["bookingStatus"] = status
            db.execute(
                "UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(apply_routine_live_status(delivery, db)), order)
            )
            updated += 1
        db.commit()
    return updated


def archive_palletways(rows, observed_at=None):
    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    matched = 0
    matched_orders = set()
    with connect() as db:
        for row in rows:
            order = clean(row.get("Customer Ref") or row.get("Order number") or row.get("Order No"))
            if not order:
                continue
            existing = db.execute(
                "SELECT payload FROM deliveries WHERE order_id=?", (order,)
            ).fetchone()
            if not existing:
                continue
            delivery = json.loads(existing["payload"])
            if delivery["carrier"] != "Palletways":
                continue
            matched += 1
            matched_orders.add(order)
            delivery["palletwaysLookup"] = "matched"
            delivery["palletwaysDetails"] = {
                "dateEntered": date_value(row.get("Date Entered")),
                "dueDate": date_value(row.get("Due Date")),
                "consignmentNumber": clean(row.get("Consignment Number")),
                "customerRef": clean(row.get("Customer Ref")),
                "trackingId": clean(row.get("Tracking ID")),
                "type": clean(row.get("Type")),
                "deliveryAddress": clean(row.get("Delivery Address")),
                "status": clean(row.get("Status")),
                "dateCompleted": clean(row.get("Date Completed")),
                "collectionPostcode": clean(row.get("Col Postcode")),
                "deliveryPostcode": clean(row.get("Del Postcode")),
                "deliveryService": clean(row.get("Del Service")),
            }
            dispatch = date_value(row.get("Dispatch Date"))
            if dispatch:
                delivery["dispatchDate"] = dispatch
            note = clean(row.get("Status"))
            if note:
                previous_status = delivery.get("palletwaysStatus")
                delivery["palletwaysStatus"] = note
                mapped = palletways_status_name(note, row.get("Date Completed"))
                delivery["st"] = mapped or ow_status_name(delivery.get("rawStatus"))
                delivery["statusSource"] = "Palletways" if mapped else "OW"
                if delivery["st"] == "Failed":
                    delivery["reason"] = note
                if note != previous_status and not (
                    delivery.get("palletwaysVerification") and delivery.get("completedAt")
                ):
                    db.execute(
                        "INSERT OR IGNORE INTO activity VALUES (?,?,?)",
                        (order, observed_at, f"Palletways status observed: {note}"),
                    )
            tracking = clean(row.get("Tracking ID"))
            if tracking:
                delivery["trk"] = tracking
                delivery["trackingUrl"] = palletways_tracking_url(tracking)
            delivery["date"] = date_value(row.get("Due Date"))
            completed = clean(row.get("Date Completed"))
            if note.upper() == "JOB COMPLETE" and completed:
                try:
                    delivery["completedAt"] = datetime.strptime(
                        completed, "%d/%m/%Y - %H:%M"
                    ).isoformat()
                except ValueError:
                    pass
            apply_verified_palletways(delivery)
            for key, value in row.items():
                if not key.lower().startswith("follow up") or not clean(value):
                    continue
                text = f"Palletways follow-up remark: {clean(value)}"
                found = db.execute(
                    "SELECT 1 FROM activity WHERE order_id=? AND text=? LIMIT 1", (order, text)
                ).fetchone()
                if not found:
                    db.execute(
                        "INSERT OR IGNORE INTO activity VALUES (?,?,?)", (order, observed_at, text)
                    )
            db.execute(
                "UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(apply_routine_live_status(delivery, db)), order)
            )
        for row in db.execute(
            "SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='Palletways'"
        ):
            if row["order_id"] in matched_orders:
                continue
            delivery = json.loads(row["payload"])
            if delivery.get("palletwaysStatus"):
                continue
            delivery["palletwaysLookup"] = "not_found"
            delivery["st"] = ow_status_name(delivery.get("rawStatus"))
            delivery["statusSource"] = "OW"
            db.execute(
                "UPDATE deliveries SET payload=? WHERE order_id=?",
                (json.dumps(apply_routine_live_status(delivery, db)), row["order_id"]),
            )
        db.commit()
    return matched


def enrich_optimoroute_today():
    """Fetch a bounded set of today's stops; ambiguous references remain untouched."""
    from server import api, normalize

    day = date.today().isoformat()
    tag = None
    orders = []
    for _ in range(3):
        query = {
            "dateRange": {"from": day, "to": day},
            "includeOrderData": True,
            "includeScheduleInformation": True,
        }
        if tag:
            query["after_tag"] = tag
        response = api("search_orders", query)
        orders.extend(response["orders"])
        tag = response.get("after_tag")
        if not tag:
            break
    if not orders:
        return 0
    refs = {}
    for item in orders:
        reference = clean((item.get("data") or {}).get("orderNo"))
        if reference:
            refs.setdefault(reference, []).append(item)
    with connect() as db:
        own_van = {}
        for row in db.execute("SELECT order_id, payload FROM deliveries"):
            delivery = json.loads(row["payload"])
            if delivery["carrier"] in OWN_VAN_CARRIERS and delivery.get("orderRef"):
                own_van.setdefault(delivery["orderRef"], []).append((row["order_id"], delivery))
        matched = [
            (items[0], own_van[reference][0])
            for reference, items in refs.items()
            if len(items) == 1 and len(own_van.get(reference, [])) == 1
        ]
    enriched = 0
    for start in range(0, len(matched), 25):
        chunk = matched[start : start + 25]
        details = api(
            "get_completion_details", {"orders": [{"id": item["id"]} for item, _ in chunk]}
        )
        by_id = {item.get("id"): item for item in details["orders"]}
        with connect() as db:
            for item, (order_id, delivery) in chunk:
                source = normalize(item, by_id.get(item.get("id")))
                apply_optimoroute_fields(delivery, source)
                previous_status = delivery.get("providerStatus")
                delivery["providerStatus"] = source.get("status")
                delivery["statusSource"] = "OptimoRoute"
                delivery["providerCheckedAt"] = datetime.now(timezone.utc).isoformat()
                delivery["date"] = date_value(source.get("plannedDate")) or delivery.get("date", "")
                delivery["trackingUrl"] = source.get("trackingUrl") or delivery.get(
                    "trackingUrl", ""
                )
                delivery["st"] = optimoroute_status_name(source.get("status")) or ow_status_name(
                    delivery.get("rawStatus")
                )
                delivery["statusSource"] = (
                    "OptimoRoute" if optimoroute_status_name(source.get("status")) else "OW"
                )
                if source.get("status") == "failed":
                    delivery["reason"] = source.get("podNote") or delivery.get("reason", "")
                if source.get("eta"):
                    delivery["eta"] = source["eta"]
                if source.get("status") and source["status"] != previous_status:
                    db.execute(
                        "INSERT OR IGNORE INTO activity VALUES (?,?,?)",
                        (
                            order_id,
                            datetime.now(timezone.utc).isoformat(),
                            f"OptimoRoute status observed: {source['status']}",
                        ),
                    )
                db.execute(
                    "UPDATE deliveries SET payload=? WHERE order_id=?",
                    (json.dumps(apply_routine_live_status(delivery, db)), order_id),
                )
                enriched += 1
            db.commit()
    return enriched


def enrich_optimoroute_page(deliveries):
    """Check only visible own-van rows, including older orders, against exact references."""
    now = datetime.now(timezone.utc)
    candidates = []
    for delivery in deliveries:
        if delivery["carrier"] not in OWN_VAN_CARRIERS or not delivery.get("orderRef"):
            continue
        checked = delivery.get("providerCheckedAt")
        if checked:
            try:
                if (now - datetime.fromisoformat(checked)).total_seconds() < CACHE_SECONDS:
                    continue
            except (ValueError, TypeError):
                pass
        candidates.append(delivery)
    if not candidates:
        return
    from server import api, normalize

    refs = {delivery["orderRef"] for delivery in candidates}
    with connect() as db:
        counts = {}
        for row in db.execute("SELECT payload FROM deliveries"):
            saved = json.loads(row["payload"])
            reference = saved.get("orderRef")
            if saved.get("carrier") in OWN_VAN_CARRIERS and reference in refs:
                counts[reference] = counts.get(reference, 0) + 1
    refs = {reference for reference in refs if counts.get(reference) == 1}
    if not refs:
        return
    response = api(
        "search_orders",
        {
            "orders": [{"orderNo": reference} for reference in refs],
            "includeOrderData": True,
            "includeScheduleInformation": True,
        },
    )
    found = {}
    for item in response["orders"]:
        reference = clean((item.get("data") or {}).get("orderNo"))
        if reference in refs:
            found.setdefault(reference, []).append(item)
    unique = [items[0] for reference, items in found.items() if len(items) == 1]
    details = (
        api("get_completion_details", {"orders": [{"id": item["id"]} for item in unique]})
        if unique
        else {"orders": []}
    )
    completions = {item.get("id"): item for item in details["orders"]}
    matched = {
        reference: normalize(items[0], completions.get(items[0].get("id")))
        for reference, items in found.items()
        if len(items) == 1
    }
    with connect() as db:
        for delivery in candidates:
            source = matched.get(delivery["orderRef"])
            delivery["providerCheckedAt"] = now.isoformat()
            if source:
                apply_optimoroute_fields(delivery, source)
                prior = delivery.get("providerStatus")
                delivery["providerStatus"] = source.get("status")
                delivery["providerLookup"] = "matched"
                delivery["statusSource"] = "OptimoRoute"
                delivery["st"] = optimoroute_status_name(source.get("status")) or ow_status_name(
                    delivery.get("rawStatus")
                )
                delivery["statusSource"] = (
                    "OptimoRoute" if optimoroute_status_name(source.get("status")) else "OW"
                )
                delivery["date"] = date_value(source.get("plannedDate")) or delivery.get("date", "")
                delivery["trackingUrl"] = source.get("trackingUrl") or delivery.get(
                    "trackingUrl", ""
                )
                if source.get("status") == "failed":
                    delivery["reason"] = source.get("podNote") or delivery.get("reason", "")
                if source.get("status") and source["status"] != prior:
                    db.execute(
                        "INSERT OR IGNORE INTO activity VALUES (?,?,?)",
                        (
                            delivery["order"],
                            now.isoformat(),
                            f"OptimoRoute status observed: {source['status']}",
                        ),
                    )
            elif (
                not found.get(delivery["orderRef"])
                and not response.get("after_tag")
                and not delivery.get("providerStatus")
            ):
                delivery["providerLookup"] = "not_found"
                delivery["statusSource"] = "OW"
                delivery["st"] = ow_status_name(delivery.get("rawStatus"))
                delivery["statusSource"] = "OW"
            elif len(found.get(delivery["orderRef"], [])) > 1 and not delivery.get(
                "providerStatus"
            ):
                delivery["providerLookup"] = "ambiguous"
                delivery["st"] = ow_status_name(delivery.get("rawStatus"))
                delivery["statusSource"] = "OW"
            apply_routine_live_status(delivery, db)
            db.execute(
                "UPDATE deliveries SET payload=? WHERE order_id=?",
                (
                    json.dumps(
                        {
                            key: value
                            for key, value in delivery.items()
                            if key not in {"logs", "lastSeenAt", "updatedAt", "firstSeenAt"}
                        }
                    ),
                    delivery["order"],
                ),
            )
        db.commit()


def snapshot():
    with connect() as db:
        logs = {}
        for entry in db.execute("SELECT order_id, at, text FROM activity ORDER BY at"):
            logs.setdefault(entry["order_id"], []).append(
                {"at": entry["at"], "text": entry["text"]}
            )
        records = []
        for row in db.execute("SELECT * FROM deliveries ORDER BY last_seen DESC, order_id DESC"):
            delivery = json.loads(row["payload"])
            delivery["lastSeenAt"] = row["last_seen"][:10]
            delivery["updatedAt"] = row["last_seen"]
            delivery["firstSeenAt"] = row["first_seen"]
            delivery["logs"] = logs.get(row["order_id"], [])
            records.append(delivery)
        return records


def sync(force=False):
    now = datetime.now(timezone.utc)
    with SYNC_LOCK:
        cached = _cache["payload"]
        if not force and cached and (now - _cache["at"]).total_seconds() < CACHE_SECONDS:
            return cached
        from google_sheets import read_sales_activity

        count = archive(read_sales_activity(), now.isoformat())
        source_updated_at = dict((cached or {}).get("sourceUpdatedAt", {}))
        source_updated_at["ow"] = datetime.now(timezone.utc).isoformat()
        try:
            from google_sheets import read_stopstart
            from stopstart import archive as archive_stopstart

            stopstart_count = archive_stopstart(read_stopstart(), now.isoformat())
            source_updated_at["stopstart"] = datetime.now(timezone.utc).isoformat()
            stopstart_error = False
        except Exception:
            stopstart_count = 0
            stopstart_error = True
        try:
            from google_sheets import read_xdp_statuses
            from xdp_sheet import archive as archive_xdp

            xdp_count = archive_xdp(read_xdp_statuses())
            source_updated_at["xdp"] = datetime.now(timezone.utc).isoformat()
            xdp_error = False
        except Exception:
            xdp_count, xdp_error = 0, True
        try:
            from google_sheets import read_xdp_activity
            from xdp_sheet import archive_activity

            xdp_activity_count = archive_activity(read_xdp_activity())
            source_updated_at['xdpActivity'] = datetime.now(timezone.utc).isoformat()
            xdp_activity_error = False
        except Exception:
            xdp_activity_count, xdp_activity_error = 0, True
        amazon_error_message = None
        try:
            from google_sheets import read_amazon_shipping

            amazon_count = archive_amazon_shipping(read_amazon_shipping(), now.isoformat())
            source_updated_at["amazonShipping"] = datetime.now(timezone.utc).isoformat()
            amazon_error = False
        except Exception as error:
            amazon_count = 0
            amazon_error = True
            kind = type(error).__name__
            if kind == "ImportError":
                amazon_error_message = "Restart the server to load the Amazon Shipping sheet reader."
            elif kind in {"WorksheetNotFound", "RuntimeError"}:
                amazon_error_message = "Amazon Shipping tab was not found in the Sales Activity workbook. Check the tab name."
            else:
                amazon_error_message = f"Amazon Shipping sheet read failed ({kind}). Check Google Sheets access and the server's internet connection."
        try:
            from google_sheets import read_palletways_tracking
            from palletways_sheet import archive_statuses

            palletways_sheet_count = archive_statuses(read_palletways_tracking())
            source_updated_at["palletwaysSheet"] = datetime.now(timezone.utc).isoformat()
            palletways_sheet_error = False
        except Exception:
            palletways_sheet_count, palletways_sheet_error = 0, True
        palletways_error = False

        try:
            from palletways_live import sync_delta

            palletways_sync = sync_delta()

            if not palletways_sync.get(
                "ok",
                False,
            ):
                palletways_error = True

        except Exception:
            palletways_error = True

        try:
            palletways_count = (
                apply_palletways_api_data()
            )

            source_updated_at[
                "palletways"
            ] = datetime.now(
                timezone.utc
            ).isoformat()

        except Exception:
            palletways_count = 0
            palletways_error = True
        try:
            from google_sheets import read_courier_issues
            from carrier_issues import archive_courier_issues

            issue_counts = archive_courier_issues(read_courier_issues(), now.isoformat())
            source_updated_at["courierIssues"] = datetime.now(timezone.utc).isoformat()
            courier_issues_error = False
        except Exception:
            issue_counts = {"matchedRows": 0, "matchedOrders": 0}
            courier_issues_error = True
        try:
            from routine_dashboard import read_booking_rows

            booking_count = archive_routine_dashboard(read_booking_rows())
            source_updated_at["routineDashboard"] = datetime.now(timezone.utc).isoformat()
            booking_error = False
        except Exception:
            booking_count = 0
            booking_error = True
        try:
            optimoroute_count = enrich_optimoroute_today()
            source_updated_at["optimoroute"] = datetime.now(timezone.utc).isoformat()
            optimoroute_error = False
        except Exception:
            optimoroute_count = 0
            optimoroute_error = True
        try:
            from routine_live import read_live_snapshot
            routine_snapshot = read_live_snapshot()
            routine_live_count = archive_routine_live(routine_snapshot['statuses'], datetime.now(timezone.utc).isoformat(),
                                                     booking_rows=routine_snapshot['bookings'])
            source_updated_at['routineLive'] = datetime.now(timezone.utc).isoformat()
            routine_live_error = False
        except Exception:
            # A failed read is not a successful empty snapshot: retain saved overrides.
            routine_live_count, routine_live_error = 0, True
        payload = {
            "indexVersion": INDEX_VERSION,
            "syncedAt": now.isoformat(),
            "sourceUpdatedAt": source_updated_at,
            "imported": count,
            "stopstartMatched": stopstart_count,
            "stopstartUnavailable": stopstart_error,
            "xdpMatched": xdp_count,
            "xdpUnavailable": xdp_error,
            "xdpActivityMatched": xdp_activity_count,
            "xdpActivityUnavailable": xdp_activity_error,
            "amazonShippingMatched": amazon_count,
            "amazonShippingUnavailable": amazon_error,
            "amazonShippingError": amazon_error_message,
            "palletwaysMatched": palletways_count,
            "palletwaysSheetMatched": palletways_sheet_count,
            "palletwaysSheetUnavailable": palletways_sheet_error,
            "palletwaysUnavailable": palletways_error,
            "courierIssuesMatched": issue_counts["matchedOrders"],
            "courierIssuesUnavailable": courier_issues_error,
            "bookingMatched": booking_count,
            "bookingUnavailable": booking_error,
            "optimorouteMatched": optimoroute_count,
            "optimorouteUnavailable": optimoroute_error,
            "routineLiveMatched": routine_live_count,
            "routineLiveUnavailable": routine_live_error,
        }
        _cache.update(at=now, payload=payload)
        with connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO sync_metadata VALUES (?, ?)",
                ("latest", json.dumps(payload)),
            )
            db.commit()
        return payload


def _refresh_background(force):
    try:
        result = current_or_sync(force)
        error = result.get("message") if result.get("stale") else None
    except Exception as exc:
        error = str(exc)
    with _background_lock:
        _background_status.update(error=error, checked_at=datetime.now(timezone.utc))


def cached_or_schedule_sync(force=False):
    """Serve the saved index immediately while one background refresh runs."""
    global _background_thread
    now = datetime.now(timezone.utc)
    with _background_lock:
        cached = _cache["payload"]
        if cached is None:
            with connect() as db:
                row = db.execute(
                    "SELECT payload FROM sync_metadata WHERE key='latest'"
                ).fetchone()
            if row:
                cached = json.loads(row["payload"])
                _cache.update(at=datetime.fromisoformat(cached["syncedAt"]), payload=cached)
        running = _background_thread is not None and _background_thread.is_alive()
        needs_reindex = bool(cached and cached.get("indexVersion") != INDEX_VERSION)
        stale = force or needs_reindex or not cached or (now - _cache["at"]).total_seconds() >= CACHE_SECONDS
        checked_at = _background_status["checked_at"]
        retry_paused = bool(
            _background_status["error"] and checked_at
            and (now - checked_at).total_seconds() < CACHE_SECONDS
        )
        if stale and not running and (force or not retry_paused):
            _background_thread = threading.Thread(
                target=_refresh_background, args=(force or needs_reindex,), daemon=True,
                name="delivery-background-sync",
            )
            _background_thread.start()
            running = True
        error = _background_status["error"]
    return {**(cached or {}), "syncing": running, "stale": bool(error), "message": error}


def current_or_sync(force=False):
    global _statuses_refreshed
    if not _statuses_refreshed:
        with connect() as db:
            for row in db.execute("SELECT order_id, payload FROM deliveries"):
                delivery = json.loads(row["payload"])
                remapped_hold = clean(delivery.get("deliveryMethodRaw")).lower() == "on hold - tbc"
                if remapped_hold:
                    delivery["carrier"] = "On Hold"
                    delivery["type"] = "External"

                source = 'XDP fallback' if delivery.get('carrier') == 'XDP' else 'OW'
                status = delivery_status(delivery.get("rawStatus"), delivery.get("deliveryMethodRaw"), clean(delivery.get("owTrackingNo") or delivery.get("trk")))
                if (delivery.get("carrier") == "AMZ"
                    and clean(delivery.get("owTrackingNo") or delivery.get("trk"))
                    and clean(delivery.get("amazonTrackingId")).upper() == clean(delivery.get("owTrackingNo") or delivery.get("trk")).upper()
                    and amazon_status_name(delivery.get("amazonStatus"))):
                    status, source = amazon_status_name(delivery["amazonStatus"]), "Amazon Shipping"
                elif delivery.get("carrier") in OWN_VAN_CARRIERS and delivery.get("providerStatus"):
                    mapped = optimoroute_status_name(delivery["providerStatus"])
                    if mapped:
                        status, source = mapped, "OptimoRoute"

                elif delivery.get("carrier") == "XDP" and clean(delivery.get("xdpStatus")):
                    status = clean(delivery["xdpStatus"])
                    source = "XDP"

                if remapped_hold or (delivery.get("st"), delivery.get("statusSource")) != (status, source):
                    delivery["st"], delivery["statusSource"] = status, source
                    db.execute(
                        "UPDATE deliveries SET payload=? WHERE order_id=?",
                        (json.dumps(apply_routine_live_status(delivery, db)), row["order_id"]),
                    )
            db.commit()
        _statuses_refreshed = True
    try:
        return sync(force)
    except Exception:
        with connect() as db:
            retained = db.execute("SELECT 1 FROM deliveries LIMIT 1").fetchone()
        if retained:
            return {
                "syncedAt": None,
                "sourceUpdatedAt": (_cache["payload"] or {}).get("sourceUpdatedAt", {}),
                "stale": True,
                "message": "Live sheet unavailable; showing retained orders.",
            }
        raise


def purchase_store(delivery):
    details = delivery.get('salesActivityDetails') or {}
    if 'storeCode' not in delivery:
        order_type = clean(details.get('Order Type'))
        analysis = clean(details.get('Order Analysis'))
        if order_type.lower() in {'sales', 'hr_replacement'}:
            return 'Hygienic Cleaning Company (UK) LTD'
        if analysis.lower() == 'ebay0':
            return 'Ebay Bathroom Republic'
        if analysis.lower() == 'ebay1':
            return 'EBay Willesden Bathroom'
        if order_type.lower() == 'shopify':
            return analysis
        if order_type.lower() == 'debenhams' and analysis.lower() == 'debenhams - neshome':
            return 'Debenhams - Neshome'
        return order_type
    return store_name(delivery.get('storeCode'), details.get('Order Type'), details.get('Order Analysis'))


def query_records(
    search="",
    carrier="",
    status="",
    date_from="",
    date_to="",
    scheduled_from="",
    scheduled_to="",
    today=False,
    ongoing_today=False,
    limit=25,
    offset=0,
    refresh_provider=False,
    issue_cases=False,
    date_sort="",
    classification="",
    general_scope="",
    courier_status=False,
    hide_hygienic=False,
    hide_wayfair=False,
    booked_in="",
    book_in_request="",
    store="",
    hide_wilko=False,
    hide_palletways_b2b=False,
    dashboard_widget='',
):
    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))
    clauses = []
    values = []
    if dashboard_widget:
        from dashboard_data import widget_condition
        clause, widget_values = widget_condition(dashboard_widget)
        clauses.append(clause)
        values.extend(widget_values)
    if hide_palletways_b2b:
        clauses.append("palletways_classification(payload)!='B2B'")
    stores = list(dict.fromkeys(value for value in (store if isinstance(store, (list, tuple)) else [store]) if value))
    if stores:
        clauses.append('purchase_store(payload) IN (' + ','.join('?' for _ in stores) + ')')
        values.extend(stores)
    if hide_wilko:
        clauses.append("purchase_store(payload)!='Wilko'")
    if hide_wayfair:
        clauses.append("lower(trim(coalesce(json_extract(payload, '$.carrier'), '')))!='wayfair'")
        clauses.append("purchase_store(payload)!='Wayfair'")
    if hide_hygienic:
        clauses.append("purchase_store(payload)!='Hygienic Cleaning Company (UK) LTD'")
        clauses.append("lower(trim(coalesce(json_extract(payload, '$.salesActivityDetails.\"Order Type\"'), ''))) NOT IN ('sales', 'hg_replacement')")
    scopes = list(dict.fromkeys(value for value in (general_scope if isinstance(general_scope, (list, tuple)) else [general_scope]) if value))
    scope_clauses = []
    for scope in scopes:
        if scope == "hygienic":
            scope_clauses.append("lower(trim(coalesce(json_extract(payload, '$.salesActivityDetails.\"Order Type\"'), '')))='sales'")
        elif scope == "Cancelled":
            scope_clauses.append("(json_extract(payload, '$.carrier')='Cancelled' OR json_extract(payload, '$.st')='Cancelled')")
        elif scope == "On Hold":
            scope_clauses.append("(json_extract(payload, '$.carrier')='On Hold' OR json_extract(payload, '$.st')='Unassigned')")
        elif scope == "today":
            scope_clauses.append('tracking_today(payload, ?)=1')
            values.append(datetime.now(ZoneInfo('Europe/London')).date().isoformat())
        else:
            scope_clauses.append("json_extract(payload, '$.carrier')=?")
            values.append(scope)
    if scope_clauses:
        clauses.append('(' + ' OR '.join(scope_clauses) + ')')
    if search:
        pattern = (
            "%"
            + clean(search).lower().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            + "%"
        )
        fields = ("order", "orderRef", "trk", "palletwaysSheetConsignmentNumber", "cust", "phone", "email", "postcode")
        clauses.append(
            "("
            + " OR ".join(
                f"lower(coalesce(json_extract(payload, '$.{field}'), '')) LIKE ? ESCAPE '\\'"
                for field in fields
            )
            + ")"
        )
        values.extend([pattern] * len(fields))
    if carrier == "Own van / Self Delivery":
        clauses.append("json_extract(payload, '$.carrier') IN (?, ?)")
        values.extend(["Own van", "Self Delivery"])
    elif carrier:
        clauses.append("json_extract(payload, '$.carrier')=?")
        values.append(carrier)
    if classification:
        methods = list(dict.fromkeys(classification if isinstance(classification, (list, tuple)) else [classification]))
        clauses.append("json_extract(payload, '$.deliveryMethodRaw') IN (" + ",".join("?" for _ in methods) + ")")
        values.extend(methods)
    if carrier == "Palletways":
        for field, selected in (("palletwaysSheetBookedIn", booked_in),
                                ("palletwaysSheetBookInRequest", book_in_request)):
            selected = clean(selected).lower()
            if selected:
                if selected not in {"yes", "no"}:
                    raise ValueError("Choose Yes or No for Palletways booking filters.")
                clauses.append(f"lower(trim(coalesce(json_extract(payload, '$.{field}'), '')))=?")
                values.append(selected)
    statuses = list(dict.fromkeys(value for value in (status if isinstance(status, (list, tuple)) else [status]) if value))
    if statuses:
        if issue_cases and courier_status:
            status_expression = ("CASE "
                "WHEN json_extract(payload, '$.carrier')='AMZ' AND coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), nullif(json_extract(payload, '$.amazonStatus'), '')) IS NOT NULL THEN 'amazon:' || coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), json_extract(payload, '$.amazonStatus')) "
                "WHEN json_extract(payload, '$.carrier')='XDP' AND nullif(json_extract(payload, '$.xdpStatus'), '') IS NOT NULL THEN 'xdp:' || json_extract(payload, '$.xdpStatus') "
                "WHEN json_extract(payload, '$.carrier')='Palletways' AND nullif(json_extract(payload, '$.palletwaysSheetStatus'), '') IS NOT NULL THEN 'palletways:' || json_extract(payload, '$.palletwaysSheetStatus') "
                "WHEN json_extract(payload, '$.carrier')='Stopstart' AND nullif(json_extract(payload, '$.stopstartStatus'), '') IS NOT NULL THEN 'stopstart:' || json_extract(payload, '$.stopstartStatus') "
                "ELSE json_extract(payload, '$.st') END")
        elif carrier == "AMZ" and courier_status:
            status_expression = ("CASE WHEN coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), nullif(json_extract(payload, '$.amazonStatus'), '')) IS NOT NULL THEN 'amazon:' || coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), json_extract(payload, '$.amazonStatus')) ELSE json_extract(payload, '$.st') END")
        elif carrier == "Stopstart" and courier_status:
            status_expression = ("CASE WHEN nullif(trim(json_extract(payload, '$.stopstartStatus')), '') IS NOT NULL THEN 'stopstart:' || json_extract(payload, '$.stopstartStatus') ELSE json_extract(payload, '$.st') END")
        elif carrier == "XDP" and courier_status:
            status_expression = ("CASE WHEN nullif(json_extract(payload, '$.xdpStatus'), '') IS NOT NULL THEN 'xdp:' || json_extract(payload, '$.xdpStatus') ELSE json_extract(payload, '$.st') END")
        elif carrier == "Palletways" and courier_status:
            statuses = list(dict.fromkeys('Delivered' if value == 'palletways:Delivered' else value for value in statuses))
            status_expression = ("CASE WHEN lower(trim(coalesce(nullif(trim(json_extract(payload, '$.palletwaysSheetStatus')), ''), json_extract(payload, '$.st'))))='delivered' THEN 'Delivered' "
                "WHEN nullif(trim(json_extract(payload, '$.palletwaysSheetStatus')), '') IS NOT NULL THEN 'palletways:' || trim(json_extract(payload, '$.palletwaysSheetStatus')) ELSE json_extract(payload, '$.st') END")
        else:
            status_expression = ("json_extract(payload, '$.st')")
        clauses.append(status_expression + " IN (" + ",".join("?" for _ in statuses) + ")")
        values.extend(statuses)
    if issue_cases:
        clauses.append(
            "json_extract(payload, '$.st') IN ('Failed', 'Rejected')"
        )
    issue_date = "COALESCE(NULLIF(json_extract(payload, '$.failedAt'), ''), NULLIF(json_extract(payload, '$.failedDate'), ''), NULLIF(json_extract(payload, '$.carrierIssueDate'), ''))"
    filter_date = issue_date if issue_cases else "json_extract(payload, '$.date')"
    if date_from:
        clauses.append(f"{filter_date}>=?")
        values.append(date_from)
    if date_to:
        clauses.append(f"substr({filter_date}, 1, 10)<=?")
        values.append(date_to)
    if scheduled_from:
        clauses.append("json_extract(payload, '$.date')>=?")
        values.append(scheduled_from)
    if scheduled_to:
        clauses.append("substr(json_extract(payload, '$.date'), 1, 10)<=?")
        values.append(scheduled_to)
    if today:
        clauses.append('tracking_today(payload, ?)=1')
        values.append(datetime.now(ZoneInfo('Europe/London')).date().isoformat())
    if ongoing_today:
        clauses.append("json_extract(payload, '$.date')=?")
        values.append(date.today().isoformat())
        clauses.append("json_extract(payload, '$.st') IN ('Scheduled', 'Out for Delivery')")
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    sort_fields = {
        "scheduled": "json_extract(payload, '$.date')",
        "issue": issue_date,
    }
    sort_column, _, sort_direction = date_sort.partition("_")
    if sort_column in sort_fields and sort_direction in {"asc", "desc"}:
        expression = sort_fields[sort_column]
        order_by = f" ORDER BY CASE WHEN {expression} IS NULL OR {expression}='' THEN 1 ELSE 0 END, {expression} {sort_direction.upper()}, order_id DESC"
    else:
        order_by = " ORDER BY last_seen DESC, order_id DESC"
    def load_page():
        with connect() as db:
            total = db.execute("SELECT COUNT(*) FROM deliveries" + where, values).fetchone()[0]
            rows = db.execute(
                "SELECT order_id, payload, first_seen, last_seen, palletways_classification(payload) AS palletways_classification FROM deliveries"
                + where
                + order_by + " LIMIT ? OFFSET ?",
                values + [limit, offset],
            )
            deliveries = []
            for row in rows:
                delivery = json.loads(row["payload"])
                if row['palletways_classification']:
                    delivery['palletwaysDetails'] = {**(delivery.get('palletwaysDetails') or {}),
                                                    'classification': row['palletways_classification']}
                delivery["lastSeenAt"] = row["last_seen"][:10]
                delivery["updatedAt"] = row["last_seen"]
                delivery["firstSeenAt"] = row["first_seen"]
                delivery["logs"] = [
                    dict(entry)
                    for entry in db.execute(
                        "SELECT at, text FROM activity WHERE order_id=? ORDER BY at",
                        (row["order_id"],),
                    )
                ]
                deliveries.append(delivery)
        return total, deliveries

    total, deliveries = load_page()
    provider_unavailable = False
    if refresh_provider:
        try:
            enrich_optimoroute_page(deliveries)
            if status or date_from or date_to or scheduled_from or scheduled_to or today or ongoing_today or issue_cases or date_sort:
                total, deliveries = load_page()
        except Exception:
            provider_unavailable = True
    return {
        "deliveries": deliveries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "hasMore": offset + len(deliveries) < total,
        "providerUnavailable": provider_unavailable,
    }


def summary():
    with connect() as db:
        filter_facets = [dict(row) for row in db.execute(
            "SELECT json_extract(payload, '$.carrier') AS carrier, "
            "json_extract(payload, '$.st') AS status, "
            "json_extract(payload, '$.deliveryMethodRaw') AS classification, "
            "coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), json_extract(payload, '$.amazonStatus')) AS amazonStatus, "
            "json_extract(payload, '$.stopstartStatus') AS stopstartStatus, "
            "json_extract(payload, '$.xdpStatus') AS xdpStatus, "
            "json_extract(payload, '$.palletwaysSheetStatus') AS palletwaysSheetStatus, "
            "tracking_today(payload, ?) AS today, "
            "json_extract(payload, '$.salesActivityDetails.\"Order Type\"') AS orderType, "
            "purchase_store(payload) AS purchaseStore, palletways_classification(payload) AS palletwaysClassification, COUNT(*) AS count "
            "FROM deliveries GROUP BY 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11", (datetime.now(ZoneInfo('Europe/London')).date().isoformat(),)
        )]
        all_count = db.execute("SELECT COUNT(*) FROM deliveries").fetchone()[0]
        order_date_ranges = {
            row[0]: {"from": row[1], "to": row[2]}
            for row in db.execute(
                "SELECT json_extract(payload, '$.st'), "
                "MIN(NULLIF(json_extract(payload, '$.orderDate'), '')), "
                "MAX(NULLIF(json_extract(payload, '$.orderDate'), '')) "
                "FROM deliveries GROUP BY 1"
            )
        }
        all_order_dates = db.execute(
            "SELECT MIN(NULLIF(json_extract(payload, '$.orderDate'), '')), "
            "MAX(NULLIF(json_extract(payload, '$.orderDate'), '')) FROM deliveries"
        ).fetchone()
        order_date_ranges["All"] = {"from": all_order_dates[0], "to": all_order_dates[1]}
        statuses = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT json_extract(payload, '$.st'), COUNT(*) FROM deliveries GROUP BY 1"
            )
        }
        carriers = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT json_extract(payload, '$.carrier'), COUNT(*) FROM deliveries GROUP BY 1"
            )
        }
        classifications = {}
        for row in db.execute(
            "SELECT DISTINCT json_extract(payload, '$.carrier'), "
            "json_extract(payload, '$.deliveryMethodRaw') FROM deliveries "
            "WHERE coalesce(json_extract(payload, '$.deliveryMethodRaw'), '') != '' "
            "ORDER BY 2 COLLATE NOCASE"
        ):
            classifications.setdefault(row[0], []).append(row[1])
        failed_carriers = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT json_extract(payload, '$.carrier'), COUNT(*) FROM deliveries "
                "WHERE json_extract(payload, '$.st') IN ('Failed', 'Rejected') GROUP BY 1"
            )
        }
        failed_total = sum(failed_carriers.values())
        unverified_carriers = {
            row[0]: row[1]
            for row in db.execute(
                "SELECT json_extract(payload, '$.carrier'), COUNT(*) FROM deliveries "
                "WHERE json_extract(payload, '$.statusSource')='OW' GROUP BY 1"
            )
        }
    due = query_records(ongoing_today=True, limit=25)
    failed_due = query_records(issue_cases=True, limit=25)
    today_total = sum(item['count'] for item in filter_facets if item['today'])
    return {
        "total": all_count,
        "filterFacets": filter_facets,
        "statuses": statuses,
        "orderDateRanges": order_date_ranges,
        "carriers": carriers,
        "deliveryMethodClassifications": classifications,
        "failedTotal": failed_total,
        "failedCarriers": failed_carriers,
        "unverifiedCarriers": unverified_carriers,
        "today": due["deliveries"],
        "ongoingTodayTotal": due["total"],
        "failedPreview": failed_due["deliveries"],
        "todayTotal": today_total,
    }


def detail(order_id):
    with connect() as db:
        row = db.execute(
            "SELECT payload, last_seen FROM deliveries WHERE order_id=?", (order_id,)
        ).fetchone()
    if not row:
        return {"error": "Order not found."}
    delivery = json.loads(row["payload"])
    if delivery["carrier"] in OWN_VAN_CARRIERS and delivery.get("orderRef"):
        try:
            from server import api, normalize

            result = api(
                "search_orders",
                {
                    "orders": [{"orderNo": delivery["orderRef"]}],
                    "includeOrderData": True,
                    "includeScheduleInformation": True,
                },
            )
            matches = [
                item
                for item in result["orders"]
                if clean((item.get("data") or {}).get("orderNo")) == delivery["orderRef"]
            ]
            if len(matches) == 1:
                item = matches[0]
                completion = api("get_completion_details", {"orders": [{"id": item["id"]}]})
                matched = normalize(
                    item,
                    next(
                        (entry for entry in completion["orders"] if entry.get("id") == item["id"]),
                        None,
                    ),
                )
                apply_optimoroute_fields(delivery, matched)
                from activity_log import archive_records

                archive_records([matched])
                delivery["date"] = date_value(matched.get("plannedDate")) or delivery.get(
                    "date", ""
                )
                delivery["trackingUrl"] = matched.get("trackingUrl") or delivery.get(
                    "trackingUrl", ""
                )
                delivery["providerStatus"] = matched.get("status")
                delivery["providerLookup"] = "matched"
                delivery["statusSource"] = "OptimoRoute"
                delivery["st"] = optimoroute_status_name(matched.get("status")) or ow_status_name(
                    delivery.get("rawStatus")
                )
                delivery["statusSource"] = (
                    "OptimoRoute" if optimoroute_status_name(matched.get("status")) else "OW"
                )
                if matched.get("status") == "failed":
                    delivery["reason"] = matched.get("podNote") or delivery.get("reason", "")
                if matched.get("completedAt"):
                    moment = matched["completedAt"]
                    if moment.get("unixTimestamp") is not None:
                        delivery["completedAt"] = datetime.fromtimestamp(
                            moment["unixTimestamp"], timezone.utc
                        ).isoformat()
                with connect() as db:
                    db.execute(
                        "UPDATE deliveries SET payload=? WHERE order_id=?",
                        (json.dumps(apply_routine_live_status(delivery, db)), order_id),
                    )
                    db.commit()
            elif len(matches) > 1:
                delivery["matchWarning"] = (
                    "Multiple OptimoRoute orders use this reference; no automatic match was made."
                )
                if not delivery.get("providerStatus"):
                    delivery["providerLookup"] = "ambiguous"
                    delivery["st"] = ow_status_name(delivery.get("rawStatus"))
                    delivery["statusSource"] = "OW"
                    with connect() as db:
                        db.execute(
                            "UPDATE deliveries SET payload=? WHERE order_id=?",
                            (json.dumps(apply_routine_live_status(delivery, db)), order_id),
                        )
                        db.commit()
            elif not result.get("after_tag") and not delivery.get("providerStatus"):
                delivery["providerLookup"] = "not_found"
                delivery["statusSource"] = "OW"
                delivery["st"] = ow_status_name(delivery.get("rawStatus"))
                delivery["statusSource"] = "OW"
                delivery["providerCheckedAt"] = datetime.now(timezone.utc).isoformat()
                with connect() as db:
                    db.execute(
                        "UPDATE deliveries SET payload=? WHERE order_id=?",
                        (json.dumps(apply_routine_live_status(delivery, db)), order_id),
                    )
                    db.commit()
        except Exception:
            delivery["matchWarning"] = "OptimoRoute details are temporarily unavailable."
    from collection_records import latest_note_id

    delivery["collectionNoteId"] = latest_note_id(delivery.get("order") or order_id)
    delivery["lastSeenAt"] = row["last_seen"][:10]
    delivery["updatedAt"] = row["last_seen"]
    with connect() as db:
        delivery["logs"] = [
            dict(item)
            for item in db.execute(
                "SELECT at, text FROM activity WHERE order_id=? ORDER BY at", (order_id,)
            )
        ]


    delivery["palletwaysEvents"] = []

    if delivery.get("carrier") == "Palletways":
        tracking = palletways_tracking_id(
            delivery
        )

        if tracking:
            photo_references = ROOT / "data" / "palletways_verified.json"
            delivery["palletwaysPhotos"] = []
            if photo_references.exists():
                facts = json.loads(photo_references.read_text(encoding="utf-8"))
                delivery["palletwaysPhotos"] = facts.get(tracking, {}).get("photos", [])
            try:
                from palletways_store import get_events

                carrier_events = []

                for event in get_events(tracking):
                    event_date = clean(
                        event.get("note_date")
                    )

                    event_time = clean(
                        event.get("note_time")
                    )

                    if not event_date:
                        continue

                    event_at = (
                        f"{event_date}T{event_time}"
                        if event_time
                        else event_date
                    )

                    carrier_events.append({
                        "at": event_at,
                        "group": clean(
                            event.get("note_group")
                        ),
                        "type": clean(
                            event.get("note_type")
                        ),
                        "statusCode": clean(
                            event.get("status_code")
                        ),
                        "codeId": clean(
                            event.get("note_code_id")
                        ),
                        "text": clean(
                            event.get("note_text")
                        ),
                        "barcode": clean(
                            event.get("barcode")
                        ),
                        "podSignature": clean(
                            event.get("pod_signature")
                        ),
                        "bookInContact": clean(
                            event.get("book_in_contact")
                        ),
                        "bookInReference": clean(
                            event.get(
                                "book_in_reference"
                            )
                        ),
                    })

                delivery[
                    "palletwaysEvents"
                ] = carrier_events

            except Exception:
                delivery[
                    "palletwaysEvents"
                ] = []


    if delivery.get("carrier") in OWN_VAN_CARRIERS and delivery.get("orderRef"):
        try:
            from activity_log import history

            provider_entries = history(delivery["orderRef"]).get("entries", [])
            for entry in provider_entries:
                at = datetime.fromtimestamp(entry["timestamp"], timezone.utc).isoformat()
                text = "OptimoRoute: " + clean(entry.get("kind")).replace("_", " ").capitalize()
                if entry.get("detail"):
                    text += " — " + clean(entry["detail"])
                delivery["logs"].append({"at": at, "text": text})
            delivery["logs"].sort(key=lambda event: event["at"])
        except Exception:
            pass
    return apply_routine_live_status(delivery)
