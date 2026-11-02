"""Persistent, editable collection notes in the shared local database."""
import json
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from delivery_data import connect


def database():
    return connect()


def initialize(db):
    db.execute("""CREATE TABLE IF NOT EXISTS collection_notes (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL,
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")


class _ReferenceParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.value = ''

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input' and fields.get('name') == 'orderRef':
            self.value = fields.get('value') or ''


def record_summary(payload):
    data = json.loads(payload)
    summary = data['summary'].copy()
    if 'orderRef' not in summary:
        parser = _ReferenceParser()
        parser.feed(data.get('paper', ''))
        summary['orderRef'] = parser.value
    return summary


def list_notes():
    with database() as db:
        initialize(db)
        rows = db.execute("SELECT id, payload, created_at, updated_at FROM collection_notes ORDER BY updated_at DESC").fetchall()
        return {"records": [{"id": row["id"], **record_summary(row["payload"]),
                             "createdAt": row["created_at"], "updatedAt": row["updated_at"]} for row in rows]}


def get_note(note_id):
    with database() as db:
        initialize(db)
        row = db.execute("SELECT * FROM collection_notes WHERE id=?", (note_id,)).fetchone()
        return {"id": row["id"], **json.loads(row["payload"])} if row else None


def delete_note(note_id):
    with database() as db:
        initialize(db)
        deleted = db.execute("DELETE FROM collection_notes WHERE id=?", (note_id,)).rowcount
        db.commit()
        return bool(deleted)


def latest_note_id(order):
    with database() as db:
        initialize(db)
        row = db.execute(
            "SELECT id FROM collection_notes WHERE trim(json_extract(payload, '$.summary.order'))=? "
            "ORDER BY updated_at DESC, id DESC LIMIT 1", (str(order).strip(),)
        ).fetchone()
        return row["id"] if row else None


def save_note(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("paper"), str) or not 1 <= len(payload["paper"]) <= 2000000:
        raise ValueError("Invalid collection note.")
    summary = payload.get("summary")
    fields = ("order", "collectionOrder", "customer", "postcode", "collectionDate", "items")
    if not isinstance(summary, dict) or any(not isinstance(summary.get(key), str) or len(summary[key]) > 10000 for key in fields):
        raise ValueError("Invalid collection note details.")
    if 'orderRef' in summary:
        if not isinstance(summary['orderRef'], str) or len(summary['orderRef']) > 10000:
            raise ValueError('Invalid order reference.')
        fields = (*fields, 'orderRef')
    if not summary["order"].strip():
        raise ValueError("Enter an order number before saving.")
    note_id = payload.get("id") or uuid.uuid4().hex
    if not isinstance(note_id, str) or len(note_id) > 64:
        raise ValueError("Invalid record ID.")
    now = datetime.now(timezone.utc).isoformat()
    with database() as db:
        initialize(db)
        if payload.get("id") and not db.execute("SELECT 1 FROM collection_notes WHERE id=?", (note_id,)).fetchone():
            raise ValueError("Collection record no longer exists.")
        data = json.dumps({"summary": {key: summary[key] for key in fields}, "paper": payload["paper"]})
        db.execute("""INSERT INTO collection_notes VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""", (note_id, data, now, now))
        db.commit()
    return {"id": note_id, "savedAt": now}
