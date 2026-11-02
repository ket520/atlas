import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "delivery-desk.sqlite3"

def _event_key(event):
    raw = json.dumps(
        event,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hashlib.sha256(
        raw.encode("utf-8")
    ).hexdigest()



def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DB_PATH)

    connection.row_factory = sqlite3.Row

    connection.execute(
        """
        PRAGMA journal_mode = WAL
        """
    )

    connection.execute(
        """
        PRAGMA foreign_keys = ON
        """
    )

    return connection


def ensure_schema():
    with _connect() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS palletways_shipments (
                tracking_id TEXT PRIMARY KEY,
                consignment_number TEXT,
                order_reference TEXT,
                classification TEXT,
                weight TEXT,
                lifts TEXT,
                collection_depot TEXT,
                delivery_depot TEXT,
                due_date TEXT,
                due_time TEXT,
                booked_in TEXT,
                book_in_request TEXT,
                book_in_contact TEXT,
                book_in_reference TEXT,
                manifest_note TEXT,
                service_json TEXT,
                bill_unit_json TEXT,
                pallet_json TEXT,
                address_json TEXT,
                raw_json TEXT,
                first_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS palletways_events (
                event_key TEXT PRIMARY KEY,
                tracking_id TEXT NOT NULL,
                delta TEXT NOT NULL,
                consignment_number TEXT,
                system_note TEXT,
                barcode TEXT,
                note_date TEXT,
                note_time TEXT,
                pod_date TEXT,
                pod_time TEXT,
                pod_signature TEXT,
                book_in_date TEXT,
                book_in_time TEXT,
                book_in_contact TEXT,
                book_in_reference TEXT,
                note_text TEXT,
                status_code TEXT,
                note_group TEXT,
                note_type TEXT,
                note_code_id TEXT,
                raw_json TEXT,
                saved_at TEXT NOT NULL
            )
            """
        )

        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS
                idx_palletways_events_tracking_time
            ON palletways_events (
                tracking_id,
                note_date,
                note_time
            )
            """
        )

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS palletways_sync_state (
                sync_key TEXT PRIMARY KEY,
                sync_value TEXT,
                updated_at TEXT NOT NULL
            )
            """
        )


def save_live_payload(payload):
    ensure_schema()

    tracking_id = str(
        payload.get("trackingId") or ""
    ).strip()

    if not tracking_id:
        return

    now = datetime.now(
        timezone.utc
    ).isoformat()

    consignment = (
        payload.get("consignment")
        or {}
    )

    with _connect() as connection:

        existing = connection.execute(
            """
            SELECT first_seen_at
            FROM palletways_shipments
            WHERE tracking_id = ?
            """,
            (tracking_id,),
        ).fetchone()

        first_seen_at = (
            existing["first_seen_at"]
            if existing
            else now
        )

        connection.execute(
            """
            INSERT INTO palletways_shipments (
                tracking_id,
                consignment_number,
                order_reference,
                classification,
                weight,
                lifts,
                collection_depot,
                delivery_depot,
                due_date,
                due_time,
                booked_in,
                book_in_request,
                book_in_contact,
                book_in_reference,
                manifest_note,
                service_json,
                bill_unit_json,
                pallet_json,
                address_json,
                raw_json,
                first_seen_at,
                updated_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )

            ON CONFLICT(tracking_id)
            DO UPDATE SET
                consignment_number =
                    excluded.consignment_number,
                order_reference =
                    excluded.order_reference,
                classification =
                    excluded.classification,
                weight =
                    excluded.weight,
                lifts =
                    excluded.lifts,
                collection_depot =
                    excluded.collection_depot,
                delivery_depot =
                    excluded.delivery_depot,
                due_date =
                    excluded.due_date,
                due_time =
                    excluded.due_time,
                booked_in =
                    excluded.booked_in,
                book_in_request =
                    excluded.book_in_request,
                book_in_contact =
                    excluded.book_in_contact,
                book_in_reference =
                    excluded.book_in_reference,
                manifest_note =
                    excluded.manifest_note,
                service_json =
                    excluded.service_json,
                bill_unit_json =
                    excluded.bill_unit_json,
                pallet_json =
                    excluded.pallet_json,
                address_json =
                    excluded.address_json,
                raw_json =
                    excluded.raw_json,
                updated_at =
                    excluded.updated_at
            """,
            (
                tracking_id,
                str(
                    consignment.get("Number")
                    or ""
                ),
                str(
                    consignment.get("Reference")
                    or ""
                ),
                str(
                    consignment.get(
                        "Classification"
                    )
                    or ""
                ),
                str(
                    consignment.get("Weight")
                    or ""
                ),
                str(
                    consignment.get("Lifts")
                    or ""
                ),
                str(
                    consignment.get(
                        "CollectionDepot"
                    )
                    or ""
                ),
                str(
                    consignment.get(
                        "DeliveryDepot"
                    )
                    or ""
                ),
                str(
                    consignment.get("DueDate")
                    or ""
                ),
                str(
                    consignment.get("DueTime")
                    or ""
                ),
                str(
                    consignment.get("BookedIn")
                    or ""
                ),
                str(
                    consignment.get(
                        "BookInRequest"
                    )
                    or ""
                ),
                str(
                    consignment.get(
                        "BookInContactName"
                    )
                    or ""
                ),
                str(
                    consignment.get(
                        "BookInReference"
                    )
                    or ""
                ),
                str(
                    consignment.get(
                        "ManifestNote"
                    )
                    or ""
                ),
                json.dumps(
                    consignment.get("Service")
                    or [],
                    ensure_ascii=False,
                ),
                json.dumps(
                    consignment.get("BillUnit")
                    or [],
                    ensure_ascii=False,
                ),
                json.dumps(
                    consignment.get("Pallet")
                    or [],
                    ensure_ascii=False,
                ),
                json.dumps(
                    consignment.get("Address")
                    or [],
                    ensure_ascii=False,
                ),
                json.dumps(
                    consignment,
                    ensure_ascii=False,
                ),
                first_seen_at,
                now,
            ),
        )

        for event in (
            payload.get("events")
            or []
        ):

            delta = str(
                event.get("delta")
                or ""
            ).strip()

            if not delta:
                continue

            connection.execute(
                """
                INSERT OR IGNORE INTO palletways_events (
                    event_key,
                    tracking_id,
                    delta,
                    consignment_number,
                    system_note,
                    barcode,
                    note_date,
                    note_time,
                    pod_date,
                    pod_time,
                    pod_signature,
                    book_in_date,
                    book_in_time,
                    book_in_contact,
                    book_in_reference,
                    note_text,
                    status_code,
                    note_group,
                    note_type,
                    note_code_id,
                    raw_json,
                    saved_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    _event_key(event),
                    tracking_id,
                    delta,
                    str(
                        event.get(
                            "consignmentNumber"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "systemNote"
                        )
                        or ""
                    ),
                    str(
                        event.get("barcode")
                        or ""
                    ),
                    str(
                        event.get("date")
                        or ""
                    ),
                    str(
                        event.get("time")
                        or ""
                    ),
                    str(
                        event.get("podDate")
                        or ""
                    ),
                    str(
                        event.get("podTime")
                        or ""
                    ),
                    str(
                        event.get(
                            "podSignature"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInDate"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInTime"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInContact"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInReference"
                        )
                        or ""
                    ),
                    str(
                        event.get("text")
                        or ""
                    ),
                    str(
                        event.get(
                            "statusCode"
                        )
                        or ""
                    ),
                    str(
                        event.get("group")
                        or ""
                    ),
                    str(
                        event.get("type")
                        or ""
                    ),
                    str(
                        event.get("codeId")
                        or ""
                    ),
                    json.dumps(
                        event,
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )

        deltas = [
            str(
                event.get("delta")
                or ""
            )
            for event in (
                payload.get("events")
                or []
            )
            if str(
                event.get("delta")
                or ""
            ).isdigit()
        ]



        if deltas:
            incoming_delta = max(
                int(value)
                for value in deltas
            )

            existing = connection.execute(
                """
                SELECT sync_value
                FROM palletways_sync_state
                WHERE sync_key = 'latest_delta'
                """
            ).fetchone()

            existing_delta = 0

            if existing:
                try:
                    existing_delta = int(
                        existing["sync_value"] or 0
                    )
                except (TypeError, ValueError):
                    existing_delta = 0

            latest_delta = str(
                max(
                    existing_delta,
                    incoming_delta,
                )
            )

            connection.execute(
                """
                INSERT INTO palletways_sync_state (
                    sync_key,
                    sync_value,
                    updated_at
                )
                VALUES (
                    'latest_delta',
                    ?,
                    ?
                )

                ON CONFLICT(sync_key)
                DO UPDATE SET
                    sync_value =
                        excluded.sync_value,
                    updated_at =
                        excluded.updated_at
                """,
                (
                    latest_delta,
                    now,
                ),
            )


def get_events(tracking_id):
    ensure_schema()

    with _connect() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM palletways_events
            WHERE tracking_id = ?
            ORDER BY
                note_date,
                note_time,
                CAST(delta AS INTEGER)
            """,
            (
                str(tracking_id),
            ),
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]


def get_shipment(tracking_id):
    ensure_schema()

    with _connect() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM palletways_shipments
            WHERE tracking_id = ?
            """,
            (
                str(tracking_id),
            ),
        ).fetchone()

    return (
        dict(row)
        if row
        else None
    )


def get_latest_delta():
    ensure_schema()

    with _connect() as connection:

        row = connection.execute(
            """
            SELECT sync_value
            FROM palletways_sync_state
            WHERE sync_key = 'latest_delta'
            """
        ).fetchone()

    return (
        row["sync_value"]
        if row
        else ""
    )




def save_events(events):
    ensure_schema()

    if not events:
        return 0

    now = datetime.now(
        timezone.utc
    ).isoformat()

    inserted = 0

    with _connect() as connection:

        for event in events:
            tracking_id = str(
                event.get("trackingId")
                or ""
            ).strip()

            delta = str(
                event.get("delta")
                or ""
            ).strip()

            if not tracking_id or not delta:
                continue

            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO palletways_events (
                    event_key,
                    tracking_id,
                    delta,
                    consignment_number,
                    system_note,
                    barcode,
                    note_date,
                    note_time,
                    pod_date,
                    pod_time,
                    pod_signature,
                    book_in_date,
                    book_in_time,
                    book_in_contact,
                    book_in_reference,
                    note_text,
                    status_code,
                    note_group,
                    note_type,
                    note_code_id,
                    raw_json,
                    saved_at
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?
                )
                """,
                (
                    _event_key(event),
                    tracking_id,
                    delta,
                    str(
                        event.get(
                            "consignmentNumber"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "systemNote"
                        )
                        or ""
                    ),
                    str(
                        event.get("barcode")
                        or ""
                    ),
                    str(
                        event.get("date")
                        or ""
                    ),
                    str(
                        event.get("time")
                        or ""
                    ),
                    str(
                        event.get("podDate")
                        or ""
                    ),
                    str(
                        event.get("podTime")
                        or ""
                    ),
                    str(
                        event.get(
                            "podSignature"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInDate"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInTime"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInContact"
                        )
                        or ""
                    ),
                    str(
                        event.get(
                            "bookInReference"
                        )
                        or ""
                    ),
                    str(
                        event.get("text")
                        or ""
                    ),
                    str(
                        event.get(
                            "statusCode"
                        )
                        or ""
                    ),
                    str(
                        event.get("group")
                        or ""
                    ),
                    str(
                        event.get("type")
                        or ""
                    ),
                    str(
                        event.get("codeId")
                        or ""
                    ),
                    json.dumps(
                        event,
                        ensure_ascii=False,
                    ),
                    now,
                ),
            )

            inserted += cursor.rowcount

    return inserted


def set_latest_delta(value):
    ensure_schema()

    try:
        incoming = int(value)
    except (TypeError, ValueError):
        return

    now = datetime.now(
        timezone.utc
    ).isoformat()

    with _connect() as connection:

        row = connection.execute(
            """
            SELECT sync_value
            FROM palletways_sync_state
            WHERE sync_key = 'latest_delta'
            """
        ).fetchone()

        current = 0

        if row:
            try:
                current = int(
                    row["sync_value"] or 0
                )
            except (TypeError, ValueError):
                current = 0

        final_value = str(
            max(
                current,
                incoming,
            )
        )

        connection.execute(
            """
            INSERT INTO palletways_sync_state (
                sync_key,
                sync_value,
                updated_at
            )
            VALUES (
                'latest_delta',
                ?,
                ?
            )

            ON CONFLICT(sync_key)
            DO UPDATE SET
                sync_value =
                    excluded.sync_value,
                updated_at =
                    excluded.updated_at
            """,
            (
                final_value,
                now,
            ),
        )