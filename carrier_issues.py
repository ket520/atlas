"""Read-only Courier Issues sheet rows matched to archived OW orders."""

import json
import re
from datetime import datetime, timezone

TAB_CARRIERS = {
    "Van": "Own van",
    "Palletways": "Palletways",
    "XDP": "XDP",
    "Cancelled Orders": "Own van",
    "COMPLETED VAN DELIVERIES": "Own van",
}


def _value(row, name):
    return str(row.get(name) or "").strip()


def _order(value):
    text = str(value or "").strip()
    if re.fullmatch(r"\d+(?:\.0)?", text):
        return text[:-2] if text.endswith(".0") else text
    return ""


def _source_date(row, tab):
    from delivery_data import date_value

    name = "Entry Date" if tab == "XDP" else "Date"
    return date_value(row.get(name))


def _failed_date(text, source_date):
    match = re.search(
        r"\bfailed(?:\s+delivery)?\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", text, re.I
    )
    if not match:
        return ""
    year = match.group(3) or (source_date[:4] if source_date else "")
    if not year:
        return ""
    year = int(year)
    if year < 100:
        year += 2000
    try:
        return datetime(year, int(match.group(2)), int(match.group(1))).date().isoformat()
    except ValueError:
        return ""


def _entry(row, tab):
    from delivery_data import date_value

    source_date = _source_date(row, tab)
    if tab == "Van":
        status, note = _value(row, "Status"), _value(row, "Note")
        details = {
            "messageStatus": _value(row, "Messaged Status"),
            "scheduledStatus": _value(row, "Scheduled Status"),
            "deliveredStatus": _value(row, "Delivered Status"),
        }
    elif tab == "Palletways":
        status, note = _value(row, "Status"), ""
        details = {"dispatchDate": date_value(row.get("Dispatch Date"))}
    elif tab == "XDP":
        status, note = _value(row, "Issue"), _value(row, "Issues")
        details = {
            "dispatchDate": date_value(row.get("Dispatch Date")),
            "item": _value(row, "Item"),
        }
    elif tab == "Cancelled Orders":
        status, note = _value(row, "Cancelled/Refused"), _value(row, "Remarks")
        details = {
            "backToStockDate": date_value(row.get("Date Back to Stock")),
            "staffComment": _value(row, "Chris Comments"),
        }
    else:
        status, note = "", ""
        details = {}
    return {
        "source": f"Courier Issues · {tab}",
        "date": source_date,
        "status": status,
        "note": note,
        **{key: value for key, value in details.items() if value},
    }


def _followups(row, tab, observed_at):
    if tab == "Van":
        names = ("Follow up_4",)
    elif tab in {"Palletways", "XDP"}:
        names = tuple(name for name in row if name == "Follow up" or name.startswith("Follow up_"))
    else:
        names = ()
    result = []
    for name in names:
        remark = _value(row, name)
        if remark:
            result.append(
                {
                    "at": observed_at,
                    "status": f"Courier Issues · {tab}",
                    "remark": remark,
                    "sourceColumn": name,
                }
            )
    return result


def _has_failed_issue(entry):
    source = entry["source"]
    status = entry["status"].lower()
    note = entry["note"].lower()
    if source.endswith("Van"):
        return bool(re.search(r"\bfailed\b|\brefused\b", status + " " + note))
    if source.endswith("Palletways"):
        return bool(re.search(r"\bfailed\b|\brefused\b|\bdamaged\b", status))
    if source.endswith("XDP"):
        return status in {"failed", "refused", "damage", "lost"}
    return False


def archive_courier_issues(tabs, observed_at=None):
    """Store matched source facts locally; never update the Google workbook."""
    from delivery_data import connect, clean

    observed_at = observed_at or datetime.now(timezone.utc).isoformat()
    matched_rows = 0
    with connect() as db:
        saved = {
            row["order_id"]: json.loads(row["payload"])
            for row in db.execute("SELECT order_id, payload FROM deliveries")
        }
        changed = set()
        for tab, required_carrier in TAB_CARRIERS.items():
            for row in tabs.get(tab, []):
                key = (
                    "Order ID"
                    if tab in {"Van", "COMPLETED VAN DELIVERIES"}
                    else "Order No" if tab == "Cancelled Orders" else "Order number"
                )
                order = _order(row.get(key))
                delivery = saved.get(order)
                if not delivery or delivery.get("carrier") != required_carrier:
                    continue
                if tab == "Van":
                    source_ref, ow_ref = clean(row.get("Order Reference")), clean(
                        delivery.get("orderRef")
                    )
                    if source_ref and ow_ref and source_ref.casefold() != ow_ref.casefold():
                        continue
                matched_rows += 1
                changed.add(order)
                entry = _entry(row, tab)
                entries = delivery.setdefault("carrierIssueEntries", [])
                if entry not in entries:
                    entries.append(entry)
                followups = delivery.setdefault("followUps", [])
                for followup in _followups(row, tab, observed_at):
                    if not any(
                        item.get("status") == followup["status"]
                        and item.get("sourceColumn") == followup["sourceColumn"]
                        and item.get("remark") == followup["remark"]
                        for item in followups
                    ):
                        followups.append(followup)
                if tab == "Van":
                    delivery["messagedStatus"] = entry.get("messageStatus") or delivery.get(
                        "messagedStatus", ""
                    )
                    delivery["scheduledStatus"] = entry.get("scheduledStatus") or delivery.get(
                        "scheduledStatus", ""
                    )
                    delivery["deliveredStatus"] = entry.get("deliveredStatus") or delivery.get(
                        "deliveredStatus", ""
                    )
                elif tab in {"Palletways", "XDP"} and entry.get("dispatchDate"):
                    delivery["carrierIssueDispatchDate"] = entry["dispatchDate"]
                    delivery["carrierIssueDispatchDateTime"] = clean(row.get("Dispatch Date"))
                elif tab == "Cancelled Orders":
                    delivery["cancellationRecord"] = entry
                elif tab == "COMPLETED VAN DELIVERIES":
                    delivery["completedVanRecord"] = entry
                if tab in {"Van", "Palletways", "XDP"} and (entry["status"] or entry["note"]):
                    failure = _has_failed_issue(entry)
                    reason = entry["status"] or entry["note"]
                    if (
                        tab == "Van"
                        and not re.search(r"\bfailed\b|\brefused\b", entry["status"], re.I)
                        and failure
                    ):
                        reason = entry["note"]
                    if failure or not delivery.get("carrierIssueReason"):
                        delivery["carrierIssueReason"] = reason
                    delivery["carrierIssueNote"] = entry["note"]
                    delivery["carrierIssueDate"] = entry["date"] or delivery.get(
                        "carrierIssueDate", ""
                    )
                    if failure:
                        delivery["carrierIssueFailure"] = True
                        failure_date = _failed_date(
                            entry["status"] + " " + entry["note"], entry["date"]
                        )
                        if failure_date:
                            delivery["failedDate"] = failure_date
                if tab == "COMPLETED VAN DELIVERIES":
                    event = "Courier Issues · COMPLETED VAN DELIVERIES: order listed in sheet (not independent delivery proof)"
                elif entry["status"] or entry["note"]:
                    event = f"{entry['source']}: {entry['status'] or entry['note']}"
                    if entry["note"] and entry["status"]:
                        event += f" · {entry['note']}"
                else:
                    event = ""
                if event:
                    if not db.execute(
                        "SELECT 1 FROM activity WHERE order_id=? AND text=? LIMIT 1", (order, event)
                    ).fetchone():
                        event_date = (
                            _failed_date(entry["status"] + " " + entry["note"], entry["date"])
                            or entry["date"]
                            or observed_at
                        )
                        db.execute(
                            "INSERT OR IGNORE INTO activity VALUES (?,?,?)",
                            (order, event_date, event),
                        )
        for order in changed:
            db.execute(
                "UPDATE deliveries SET payload=? WHERE order_id=?",
                (json.dumps(saved[order]), order),
            )
        db.commit()
    return {"matchedRows": matched_rows, "matchedOrders": len(changed)}
