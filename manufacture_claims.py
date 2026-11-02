"""Local manufacturing claims and their uploaded pictures."""
import base64
import binascii
import json
import uuid
from datetime import date, datetime, timezone

from delivery_data import connect
from sales_activity import STORE_CODES

REASONS = ('Scratches', 'Broken parts', 'Leaking', 'Missing parts', 'Others')
SOLUTIONS = ('Replacement', 'Refund', 'Others')
STORES = set(STORE_CODES.values()) | {'Hygienic Cleaning Company (UK) LTD'}
MAX_PICTURE = 5 * 1024 * 1024
MAX_TOTAL = 15 * 1024 * 1024
MAX_REQUEST = 22 * 1024 * 1024


def initialize(db):
    db.execute('''CREATE TABLE IF NOT EXISTS manufacture_claims (
        id TEXT PRIMARY KEY, payload TEXT NOT NULL, created_at TEXT NOT NULL)''')
    db.execute('''CREATE TABLE IF NOT EXISTS manufacture_claim_photos (
        id TEXT PRIMARY KEY, claim_id TEXT NOT NULL, name TEXT NOT NULL,
        mime TEXT NOT NULL, content BLOB NOT NULL)''')
    db.execute('CREATE INDEX IF NOT EXISTS manufacture_claim_photos_claim ON manufacture_claim_photos(claim_id)')


def text(payload, key, limit=200, required=True):
    value = payload.get(key, '')
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Invalid {key}.')
    value = value.strip()
    if required and not value:
        raise ValueError(f'Enter {key}.')
    return value


def choice(payload, key, options):
    selected = text(payload, key)
    if selected not in options:
        raise ValueError(f'Choose a valid {key}.')
    return text(payload, key + 'Other', 2000) if selected == 'Others' else selected


def picture(upload):
    if not isinstance(upload, dict):
        raise ValueError('Invalid picture.')
    name = text(upload, 'name', 250).replace('\\', '/').rsplit('/', 1)[-1]
    encoded = upload.get('data')
    if not isinstance(encoded, str) or len(encoded) > (MAX_PICTURE + 2) // 3 * 4:
        raise ValueError('Each picture must be 5 MB or smaller.')
    try:
        content = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError('Invalid picture data.') from None
    if not content or len(content) > MAX_PICTURE:
        raise ValueError('Each picture must be 5 MB or smaller.')
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif content.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif content[:6] in (b'GIF87a', b'GIF89a'):
        mime = 'image/gif'
    elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        mime = 'image/webp'
    else:
        raise ValueError('Upload JPG, PNG, WebP or GIF pictures.')
    return name, mime, content


def save_claim(payload, claim_id=None):
    if not isinstance(payload, dict):
        raise ValueError('Invalid claim.')
    order_date = text(payload, 'orderDate', 10)
    try:
        if date.fromisoformat(order_date).isoformat() != order_date:
            raise ValueError()
    except ValueError:
        raise ValueError('Choose a valid order date.') from None
    store = text(payload, 'sellingShop')
    if store not in STORES:
        raise ValueError('Choose an existing selling shop from the list.')
    record = dict(orderDate=order_date,
                  originalOrderNo=text(payload, 'originalOrderNo'),
                  replacementOrderNo=text(payload, 'replacementOrderNo'),
                  variantCode=text(payload, 'variantCode'),
                  reason=choice(payload, 'reason', REASONS),
                  solution=choice(payload, 'solution', SOLUTIONS), sellingShop=store)
    uploads = payload.get('photos', [])
    if not isinstance(uploads, list) or len(uploads) > 5:
        raise ValueError('Attach up to 5 pictures.')
    photos = [picture(upload) for upload in uploads]
    if sum(len(item[2]) for item in photos) > MAX_TOTAL:
        raise ValueError('Pictures must total 15 MB or less.')
    updating = claim_id is not None
    claim_id = claim_id or uuid.uuid4().hex
    now = datetime.now(timezone.utc).isoformat()
    with connect() as db:
        initialize(db)
        retained = []
        if updating:
            existing = db.execute('SELECT created_at FROM manufacture_claims WHERE id=?', (claim_id,)).fetchone()
            if not existing:
                raise FileNotFoundError('This claim no longer exists. Refresh the list.')
            now = existing['created_at']
            saved = db.execute('SELECT id, name, length(content) AS size FROM manufacture_claim_photos WHERE claim_id=? ORDER BY rowid', (claim_id,)).fetchall()
            keep = payload.get('retainedPhotoIds', [row['id'] for row in saved])
            if not isinstance(keep, list) or any(not isinstance(value, str) for value in keep) or len(set(keep)) != len(keep):
                raise ValueError('Invalid saved pictures.')
            owned = {row['id'] for row in saved}
            if not set(keep).issubset(owned):
                raise ValueError('A saved picture does not belong to this claim. Refresh and retry.')
            retained = [row for row in saved if row['id'] in keep]
            if len(retained) + len(photos) > 5:
                raise ValueError('Attach up to 5 pictures.')
            if sum(row['size'] for row in retained) + sum(len(item[2]) for item in photos) > MAX_TOTAL:
                raise ValueError('Pictures must total 15 MB or less.')
            db.execute('UPDATE manufacture_claims SET payload=? WHERE id=?', (json.dumps(record), claim_id))
            for row in saved:
                if row['id'] not in keep:
                    db.execute('DELETE FROM manufacture_claim_photos WHERE claim_id=? AND id=?', (claim_id, row['id']))
        else:
            db.execute('INSERT INTO manufacture_claims VALUES (?, ?, ?)', (claim_id, json.dumps(record), now))
        attached = [photo_info(claim_id, row['id'], row['name']) for row in retained]
        for name, mime, content in photos:
            photo_id = uuid.uuid4().hex
            db.execute('INSERT INTO manufacture_claim_photos VALUES (?, ?, ?, ?, ?)',
                       (photo_id, claim_id, name, mime, content))
            attached.append(photo_info(claim_id, photo_id, name))
        db.commit()
    return {'id': claim_id, **record, 'createdAt': now, 'photos': attached}



def photo_info(claim_id, photo_id, name):
    return {'id': photo_id, 'name': name, 'url': f'/api/manufacture-claims/{claim_id}/photos/{photo_id}'}


def add_photos(claim_id, payload):
    """Append pictures atomically without replacing claim fields or existing pictures."""
    uploads = payload.get('photos') if isinstance(payload, dict) else None
    if not isinstance(uploads, list) or not 1 <= len(uploads) <= 5:
        raise ValueError('Choose between 1 and 5 pictures.')
    photos = [picture(upload) for upload in uploads]
    with connect() as db:
        initialize(db)
        db.execute('BEGIN IMMEDIATE')
        claim = db.execute('SELECT payload, created_at FROM manufacture_claims WHERE id=?', (claim_id,)).fetchone()
        if not claim:
            raise FileNotFoundError('This claim no longer exists. Refresh the list.')
        saved = db.execute('SELECT id, name, length(content) AS size FROM manufacture_claim_photos WHERE claim_id=? ORDER BY rowid', (claim_id,)).fetchall()
        if len(saved) + len(photos) > 5:
            raise ValueError('Attach up to 5 pictures.')
        if sum(row['size'] for row in saved) + sum(len(item[2]) for item in photos) > MAX_TOTAL:
            raise ValueError('Pictures must total 15 MB or less.')
        attached = [photo_info(claim_id, row['id'], row['name']) for row in saved]
        for name, mime, content in photos:
            photo_id = uuid.uuid4().hex
            db.execute('INSERT INTO manufacture_claim_photos VALUES (?,?,?,?,?)',
                       (photo_id, claim_id, name, mime, content))
            attached.append(photo_info(claim_id, photo_id, name))
        db.commit()
        return {'id': claim_id, **json.loads(claim['payload']), 'createdAt': claim['created_at'], 'photos': attached}


def list_claims():
    with connect() as db:
        initialize(db)
        attached = {}
        for row in db.execute('SELECT id, claim_id, name FROM manufacture_claim_photos ORDER BY rowid'):
            attached.setdefault(row['claim_id'], []).append(photo_info(row['claim_id'], row['id'], row['name']))
        return {'records': [{'id': row['id'], **json.loads(row['payload']),
                             'createdAt': row['created_at'], 'photos': attached.get(row['id'], [])}
                            for row in db.execute('SELECT * FROM manufacture_claims ORDER BY created_at DESC, id DESC')]}


def get_photo(claim_id, photo_id):
    with connect() as db:
        initialize(db)
        row = db.execute('SELECT content, mime FROM manufacture_claim_photos WHERE claim_id=? AND id=?',
                         (claim_id, photo_id)).fetchone()
        return (bytes(row['content']), row['mime']) if row else None


def delete_claim(claim_id):
    with connect() as db:
        initialize(db)
        deleted = db.execute('DELETE FROM manufacture_claims WHERE id=?', (claim_id,)).rowcount
        if deleted:
            db.execute('DELETE FROM manufacture_claim_photos WHERE claim_id=?', (claim_id,))
        db.commit()
    return bool(deleted)
