"""Read-only STOPSTART sheet details and planned delivery observations."""

import json
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")


def trackability(row):
    explicit = str(row.get('trackability') or '').strip()
    if explicit:
        return {'yes': 'Yes', 'no': 'No', 'missing': 'Missing', 'time out': 'Time Out'}.get(explicit.lower(), '')
    result = str(row.get('fetchResult') or '').strip()
    if not result:
        return ''
    if result == 'OK':
        return 'Yes'
    if re.match(r'^HTTP 404\b', result, re.I) or re.search(r'EXPIRED TRACKING PAGE \(HTTP 200\)', result, re.I):
        return 'No'
    if re.match(r'^REQUEST ERROR:|^HTTP \d{3}\b', result, re.I):
        return 'Time Out'
    return 'Missing'


def parse_details(value):
    raw = str(value or "").strip()
    def field(label):
        match = re.search(r"^\s*" + label + r"\s*:\s*(.+)$", raw, re.I | re.M)
        return match[1].strip() if match else ""

    expected = field(r"Expected delivery")
    window = field(r"Delivery window")
    date_match = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", expected)
    day = ""
    if date_match:
        try:
            day = datetime(int(date_match[3]), int(date_match[2]), int(date_match[1])).date().isoformat()
        except ValueError:
            pass
    times = re.findall(r"(?<!\d)([0-2]?\d:[0-5]\d)(?!\d)", window)
    start = end = ""
    try:
        if times:
            clock = datetime.strptime(times[0], "%H:%M")
            start = clock.strftime("%H:%M")
            if len(times) > 1:
                end = datetime.strptime(times[1], "%H:%M").strftime("%H:%M")
            else:
                duration = re.search(r"\+\s*(\d+(?:\.\d+)?)\s*(?:hr|hour|h)\b", window, re.I)
                if duration:
                    end = (clock + timedelta(hours=float(duration[1]))).strftime("%H:%M")
    except ValueError:
        start = end = ""
    scheduled = datetime.fromisoformat(f"{day}T{start}").replace(tzinfo=UK).isoformat() if day and start else ""
    return {"raw": raw, "expectedDate": day, "expectedDelivery": expected,
            "window": f"{start} - {end}" if start and end else window,
            "windowStart": start, "windowEnd": end, "scheduledAt": scheduled,
            "driver": field(r"Driver"), "reference": field(r"Stop\s*Start\s*Ref")}


def archive(rows, observed_at=None):
    from delivery_data import connect

    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    by_order = {}
    statuses = {}
    trackabilities = {}
    for row in rows:
        order = str(row.get("order") or "").strip()
        if re.fullmatch(r"\d+\.0", order):
            order = order[:-2]
        raw = str(row.get("details") or "").strip()
        status = str(row.get("status") or "")
        if order.isdigit():
            trackabilities.setdefault(order, set()).add(trackability(row))
        if order.isdigit() and status.strip():
            statuses.setdefault(order, set()).add(status)
        if order.isdigit() and raw:
            details = parse_details(raw)
            if details not in by_order.setdefault(order, []):
                by_order[order].append(details)
    matched = 0
    with connect() as db:
        for row in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='Stopstart'").fetchall():
            details = by_order.get(row["order_id"], [])
            delivery = json.loads(row["payload"])
            source_trackability = trackabilities.get(row['order_id'], set())
            delivery.pop('stopstartTrackability', None)
            if len(source_trackability) == 1:
                delivery['stopstartTrackability'] = next(iter(source_trackability))
            source_statuses = statuses.get(row["order_id"], set())
            delivery.pop("stopstartStatus", None)
            if len(source_statuses) == 1:
                delivery["stopstartStatus"] = next(iter(source_statuses))
            if not details:
                db.execute("UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(delivery), row["order_id"]))
                if source_statuses:
                    matched += 1
                continue
            history = delivery.setdefault("stopstartEvents", [])
            for detail in details:
                if not any(event.get("raw") == detail["raw"] for event in history):
                    event = {**detail, "observedAt": observed_at}
                    history.append(event)
                    db.execute("INSERT OR IGNORE INTO activity VALUES (?,?,?)", (
                        row["order_id"], detail["scheduledAt"] or observed_at,
                        "STOPSTART expected delivery (planned): " + detail["raw"],
                    ))
            # Conflicting duplicate rows remain in history without choosing a current plan.
            delivery["stopstartDetails"] = details[0] if len(details) == 1 else None
            delivery["stopstartAmbiguous"] = len(details) > 1
            delivery["stopstartCheckedAt"] = observed_at
            db.execute("UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(delivery), row["order_id"]))
            matched += 1
        db.commit()
    return matched
