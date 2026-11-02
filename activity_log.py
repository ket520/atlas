"""Local archive of read-only OptimoRoute events and observed status changes."""

import hashlib
import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
MAIN_DB_PATH = DATA_DIR / "delivery-desk.sqlite3"
LEGACY_DB_PATH = DATA_DIR / "optimoroute-activity.sqlite3"
DB_PATH = MAIN_DB_PATH
SYNC_LOCK = threading.Lock()
_legacy_mtime = None


def migrate_legacy(db):
    """Copy historical OptimoRoute rows into the shared database without deleting the old file."""
    global _legacy_mtime
    if DB_PATH != MAIN_DB_PATH or not LEGACY_DB_PATH.is_file():
        return
    modified = LEGACY_DB_PATH.stat().st_mtime_ns
    if modified == _legacy_mtime:
        return
    legacy = sqlite3.connect(LEGACY_DB_PATH.as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("BEGIN IMMEDIATE")
        for table, columns in (
            ("orders", "account,id,reference,last_status"),
            ("aliases", "account,alias,order_id"),
            ("entries", "account,fingerprint,order_id,reference,kind,timestamp,driver,source,detail"),
            ("sync_state", "account,tag,synced_at"),
        ):
            fields = columns.split(",")
            placeholders = ",".join("?" for _ in fields)
            for row in legacy.execute(f"SELECT {columns} FROM {table}"):
                db.execute(
                    f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})",
                    row,
                )
        db.commit()
        _legacy_mtime = modified
    except Exception:
        db.rollback()
        raise
    finally:
        legacy.close()


def account():
    from server import KEY

    return hashlib.sha256((KEY or "unconfigured").encode()).hexdigest()


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=15)
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            account TEXT, id TEXT, reference TEXT, last_status TEXT,
            PRIMARY KEY(account, id));
        CREATE TABLE IF NOT EXISTS aliases (
            account TEXT, alias TEXT, order_id TEXT,
            PRIMARY KEY(account, alias, order_id));
        CREATE TABLE IF NOT EXISTS entries (
            account TEXT, fingerprint TEXT, order_id TEXT, reference TEXT,
            kind TEXT, timestamp REAL, driver TEXT, source TEXT, detail TEXT,
            PRIMARY KEY(account, fingerprint));
        CREATE INDEX IF NOT EXISTS history_by_order ON entries(account, order_id, timestamp);
        CREATE TABLE IF NOT EXISTS sync_state (
            account TEXT PRIMARY KEY, tag TEXT, synced_at TEXT);
    """)
    try:
        migrate_legacy(db)
        with db:
            yield db
    finally:
        db.close()


def insert(db, scope, order_id, reference, kind, timestamp, driver, source, detail=""):
    fingerprint = hashlib.sha256(
        json.dumps(
            [order_id, reference if not order_id else "", kind, timestamp, driver, source],
            sort_keys=True,
        ).encode()
    ).hexdigest()
    db.execute(
        "INSERT OR IGNORE INTO entries VALUES (?,?,?,?,?,?,?,?,?)",
        (scope, fingerprint, order_id, reference, kind, timestamp, driver, source, detail),
    )


def timestamp(value):
    if isinstance(value, (int, float)):
        return value
    if value:
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return (instant if instant.tzinfo else instant.replace(tzinfo=timezone.utc)).timestamp()
        except ValueError:
            pass
    return None


def archive_records(records):
    scope = account()
    with connect() as db:
        for record in records:
            order_id = record.get("id")
            if not order_id:
                continue
            reference = record.get("providerOrderNo") or record.get("orderNo") or ""
            aliases = {reference, record.get("orderNo"), order_id} - {None, ""}
            for alias in aliases:
                db.execute(
                    "INSERT OR IGNORE INTO aliases VALUES (?,?,?)", (scope, str(alias), order_id)
                )
            previous = db.execute(
                "SELECT last_status FROM orders WHERE account=? AND id=?", (scope, order_id)
            ).fetchone()
            status = record.get("status")
            if not record.get("completionError") and status:
                if previous is None or previous["last_status"] != status:
                    detail = (
                        "First observed in this app; original change time is unknown."
                        if previous is None
                        else f"Status changed from {previous['last_status']} to {status}; original change time is unknown."
                    )
                    context = [
                        f"{name}: {record[field]}"
                        for field, name in [
                            ("scheduledAt", "Scheduled arrival"),
                            ("date", "Delivery date"),
                            ("vehicle", "Vehicle"),
                            ("podNote", "Delivery note"),
                        ]
                        if record.get(field)
                    ]
                    insert(
                        db,
                        scope,
                        order_id,
                        reference,
                        status,
                        datetime.now(timezone.utc).timestamp(),
                        record.get("driver") or "",
                        "observed",
                        " ".join([detail] + context),
                    )
                db.execute(
                    "INSERT OR REPLACE INTO orders VALUES (?,?,?,?)",
                    (scope, order_id, reference, status),
                )
            for field, kind in [("startedAt", "start_service"), ("completedAt", status)]:
                value = record.get(field) or {}
                instant = timestamp(
                    value.get("unixTimestamp")
                    if value.get("unixTimestamp") is not None
                    else value.get("utcTime")
                )
                if instant is not None and kind in {"start_service", "success", "failed"}:
                    insert(
                        db,
                        scope,
                        order_id,
                        reference,
                        kind,
                        instant,
                        record.get("driver") or "",
                        "completion",
                        "Timestamp supplied in order completion details."
                        + (f" Delivery note: {record['podNote']}" if record.get("podNote") else ""),
                    )


def sync_events(api, max_pages=5):
    scope = account()
    with SYNC_LOCK, connect() as db:
        state = db.execute("SELECT * FROM sync_state WHERE account=?", (scope,)).fetchone()
        tag = state["tag"] if state else ""
        events = []
        remaining = 0
        for _ in range(max_pages):
            result = api("get_events", {"after_tag": tag}, "GET")
            batch = result.get("events") or []
            for event in batch:
                order_id = event.get("orderId") or event.get("id") or ""
                reference = event.get("orderNo") or ""
                instant = timestamp(
                    event.get("unixTimestamp")
                    if event.get("unixTimestamp") is not None
                    else event.get("utcTime")
                )
                if not (order_id or reference) or instant is None:
                    continue
                insert(
                    db,
                    scope,
                    order_id,
                    reference,
                    event.get("event", "unknown"),
                    instant,
                    event.get("driverName") or event.get("driverSerial") or "",
                    "mobile",
                    "Driver app event.",
                )
                if order_id and reference:
                    db.execute(
                        "INSERT OR IGNORE INTO aliases VALUES (?,?,?)", (scope, reference, order_id)
                    )
            events.extend(batch)
            next_tag = result.get("tag") or tag
            remaining = result.get("remainingEvents") or 0
            synced = datetime.now(timezone.utc).isoformat()
            db.execute(
                "INSERT OR REPLACE INTO sync_state VALUES (?,?,?)", (scope, next_tag, synced)
            )
            db.commit()  # Preserve both events and cursor even if a later page fails.
            if not remaining or next_tag == tag:
                tag = next_tag
                break
            tag = next_tag
        return {"events": events, "tag": tag, "remainingEvents": remaining, "syncedAt": synced}


def history(query):
    scope = account()
    with connect() as db:
        ids = [
            row["order_id"]
            for row in db.execute(
                "SELECT order_id FROM aliases WHERE account=? AND alias=?", (scope, query)
            )
        ]
        clauses = ["reference=?", "order_id=?"]
        values = [scope, query, query]
        if ids:
            clauses.append("order_id IN (" + ",".join("?" for _ in ids) + ")")
            values.extend(ids)
        entries = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM entries WHERE account=? AND ("
                + " OR ".join(clauses)
                + ") ORDER BY timestamp, fingerprint",
                values,
            )
        ]
        mobile = {
            (item["order_id"], item["kind"], item["timestamp"])
            for item in entries
            if item["source"] == "mobile"
        }
        entries = [
            item
            for item in entries
            if item["source"] != "completion"
            or (item["order_id"], item["kind"], item["timestamp"]) not in mobile
        ]
        for item in entries:
            item.pop("account", None)
            item.pop("fingerprint", None)
        state = db.execute("SELECT synced_at FROM sync_state WHERE account=?", (scope,)).fetchone()
        return {
            "orderNo": query,
            "entries": entries,
            "syncedAt": state["synced_at"] if state else None,
            "notice": "History includes collected live-route events and observed statuses. Earlier changes may be unavailable. Observed times are when this app saw the status, not when it originally changed.",
        }


def lookup(query, api):
    query = query.strip()
    if not query or len(query) > 200:
        raise ValueError("Enter an Order ID of up to 200 characters.")
    warnings = []
    try:
        orders = api(
            "search_orders",
            {
                "orders": [{"orderNo": query}],
                "includeOrderData": True,
                "includeScheduleInformation": True,
            },
        )
        found = orders["orders"]
        if not found:
            orders = api(
                "search_orders",
                {
                    "orders": [{"id": query}],
                    "includeOrderData": True,
                    "includeScheduleInformation": True,
                },
            )
            found = orders["orders"]
        if found:
            try:
                done = api(
                    "get_completion_details", {"orders": [{"id": item["id"]} for item in found]}
                )
                by_id = {item.get("id"): item for item in done["orders"]}
            except Exception as error:
                from server import KEY

                warnings.append(str(error).replace(KEY, "[redacted]") if KEY else str(error))
                by_id = {
                    item["id"]: {"success": False, "code": "Completion details unavailable"}
                    for item in found
                }
            from server import normalize

            archive_records([normalize(item, by_id.get(item.get("id"))) for item in found])
    except Exception as error:
        from server import KEY

        warnings.append(str(error).replace(KEY, "[redacted]") if KEY else str(error))
    try:
        synced = sync_events(api)
        if synced["remainingEvents"]:
            warnings.append("More live events remain. Search again to continue collecting them.")
    except Exception as error:
        from server import KEY

        warnings.append(str(error).replace(KEY, "[redacted]") if KEY else str(error))
    result = history(query)
    result["warnings"] = warnings
    return result
