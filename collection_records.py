"""Persistent, editable collection notes in the shared local database."""
import json
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from delivery_data import connect, purchase_store


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
        self.values = {}

    def handle_starttag(self, tag, attrs):
        fields = dict(attrs)
        if tag == 'input':
            self.values[fields.get('name')] = fields.get('value') or ''
            if fields.get('name') == 'orderRef':
                self.value = fields.get('value') or ''


def record_summary(payload):
    data = json.loads(payload)
    summary = data['summary'].copy()
    summary['status'] = data.get('status', 'Pending')
    parser = _ReferenceParser()
    parser.feed(data.get('paper', ''))
    method = parser.values.get('collectionType', '').strip()
    summary['collectionMethod'] = 'Refund' if method == 'Credit/Refund' else method
    for key, source in (("orderRef", "orderRef"), ("channel", "company"), ("phone", "phone")):
        if key not in summary:
            summary[key] = parser.values.get(source, '')
    return summary


def list_notes():
    with database() as db:
        initialize(db)
        rows = db.execute("""SELECT n.id, n.payload, n.created_at, n.updated_at,
                                    d.payload AS delivery_payload
            FROM collection_notes n LEFT JOIN deliveries d
              ON d.order_id=trim(json_extract(n.payload, '$.summary.order'))
            ORDER BY n.updated_at DESC""").fetchall()
        records = []
        for row in rows:
            summary = record_summary(row['payload'])
            if row['delivery_payload']:
                summary['channel'] = purchase_store(json.loads(row['delivery_payload']))
            records.append({'id': row['id'], **summary,
                            'createdAt': row['created_at'], 'updatedAt': row['updated_at']})
        return {'records': records}


def get_note(note_id):
    with database() as db:
        initialize(db)
        row = db.execute("SELECT * FROM collection_notes WHERE id=?", (note_id,)).fetchone()
        if not row:
            return None
        data = json.loads(row["payload"])
        return {"id": row["id"], **data, "status": data.get("status", "Pending")}


def set_status(note_id, status):
    if status not in ('Pending', 'Approved', 'Rejected'):
        raise ValueError('Choose Pending, Approved or Rejected.')
    with database() as db:
        initialize(db)
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('SELECT payload FROM collection_notes WHERE id=?', (note_id,)).fetchone()
        if not row:
            raise FileNotFoundError('Collection note not found.')
        data = json.loads(row['payload'])
        data['status'] = status
        db.execute('UPDATE collection_notes SET payload=?, updated_at=? WHERE id=?',
                   (json.dumps(data), datetime.now(timezone.utc).isoformat(), note_id))
        db.commit()
    return {'id': note_id, 'status': status}


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
    for key in ('orderRef', 'channel', 'phone'):
        if key in summary:
            if not isinstance(summary[key], str) or len(summary[key]) > 10000:
                raise ValueError('Invalid collection note details.')
            fields = (*fields, key)
    if not summary["order"].strip():
        raise ValueError("Enter an order number before saving.")
    note_id = payload.get("id") or uuid.uuid4().hex
    if not isinstance(note_id, str) or len(note_id) > 64:
        raise ValueError("Invalid record ID.")
    now = datetime.now(timezone.utc).isoformat()
    with database() as db:
        initialize(db)
        db.execute("BEGIN IMMEDIATE")
        existing = db.execute("SELECT payload FROM collection_notes WHERE id=?", (note_id,)).fetchone()
        if payload.get("id") and not existing:
            raise ValueError("Collection record no longer exists.")
        status = json.loads(existing["payload"]).get("status", "Pending") if existing else "Pending"
        data = json.dumps({"summary": {key: summary[key] for key in fields}, "paper": payload["paper"], "status": status})
        db.execute("""INSERT INTO collection_notes VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at""", (note_id, data, now, now))
        db.commit()
    return {"id": note_id, "savedAt": now, "status": status}
