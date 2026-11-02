"""Keep XDP column-I statuses separate from shared delivery categories."""
import json
import re
import hashlib
from datetime import datetime
from xml.etree import ElementTree as ET
from functools import lru_cache
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


def apply_status(delivery):
    """Keep the source label while grouping explicit XDP failures as Failed."""
    if delivery.get('carrier') == 'XDP':
        status = re.sub(r'[_\s]+', ' ', str(delivery.get('xdpStatus') or '').strip().upper())
        if status in {'DAMAGE', 'DELETE', 'NOT RECEIVED'}:
            delivery['st'] = 'Failed'
            delivery['statusSource'] = 'XDP'
        elif delivery.get('statusSource') == 'XDP' and delivery.get('st') == 'Failed':
            delivery['st'] = 'Awaiting'
            delivery['statusSource'] = 'XDP fallback'
    return delivery


def document_urls(value):
    """One complete XDP image URL per line; incomplete placeholder URLs are ignored."""
    return list(dict.fromkeys(
        line.strip() for line in str(value or '').splitlines()
        if re.fullmatch(r'https://xdp\.sysx\.co\.uk/pod/view/\d+/[A-Za-z0-9_+=%-]+', line.strip())
    ))


def parse_activity(value):
    raw = str(value or '').strip()
    # Bound cache memory; unusually large cells are parsed without retaining XML.
    if len(raw) > 65536:
        return _parse_activity(raw)
    return [dict(event) for event in _cached_activity(raw)]


@lru_cache(maxsize=128)
def _cached_activity(raw):
    return _parse_activity(raw)


def _parse_activity(value):
    """Parse adjacent consignment elements without guessing a source timezone."""
    raw = str(value or '').strip()
    if not raw:
        return []
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    if len(raw) > 5 * 1024 * 1024 or re.search(r'<!DOCTYPE|<!ENTITY', raw, re.I):
        raise ValueError('Invalid XDP activity XML.')
    raw = re.sub(r'<\?xml[^>]*\?>', '', raw)
    try:
        root = ET.fromstring('<events>' + raw + '</events>')
    except ET.ParseError:
        raise ValueError('Could not parse XDP activity XML from column M.') from None
    events = {}
    for node in root.iter():
        if node.tag.rsplit('}', 1)[-1] != 'consignment':
            continue
        fields = {child.tag.rsplit('}', 1)[-1]: ''.join(child.itertext()).strip() for child in node}
        try:
            at = datetime.strptime(fields.get('sdate', '') + ' ' + fields.get('statusTime', ''), '%d-%m-%Y %H:%M:%S').isoformat()
        except ValueError:
            continue
        event = {
            'id': fields.get('id', ''), 'consignment': fields.get('consigNo', ''),
            'reference': fields.get('references', ''), 'barcode': fields.get('barcode', ''),
            'at': at, 'type': fields.get('statusType', ''),
            'text': fields.get('statusData', ''), 'location': fields.get('location', ''),
        }
        key = event['id'] or hashlib.sha256(json.dumps(event, sort_keys=True).encode()).hexdigest()
        event['key'] = event['consignment'] + ':' + key
        events[event['key']] = event
    return sorted(events.values(), key=lambda event: (event['at'], event['key']))


def serve_document(handler, params):
    from delivery_data import detail

    delivery = detail(params.get('order', [''])[0])
    if delivery.get('carrier') != 'XDP':
        return handler.send_json(404, {'error': 'XDP order not found.'})
    try:
        index = int(params.get('index', ['0'])[0])
    except ValueError:
        return handler.send_json(400, {'error': 'Invalid document index.'})
    documents = delivery.get('xdpDocuments') or []
    if index < 0 or index >= len(documents) or not document_urls(documents[index]):
        return handler.send_json(404, {'error': 'Document not found.'})
    try:
        with urlopen(Request(documents[index], headers={'Accept': 'image/*'}), timeout=25) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith('image/'):
                return handler.send_json(502, {'error': 'XDP did not return an image.'})
            content = response.read(25 * 1024 * 1024 + 1)
        if len(content) > 25 * 1024 * 1024:
            return handler.send_json(502, {'error': 'XDP image is too large.'})
    except (HTTPError, URLError, TimeoutError, OSError):
        return handler.send_json(502, {'error': 'Could not retrieve the XDP image. Please try again.'})
    extension = {'image/jpeg': 'jpg', 'image/png': 'png', 'image/webp': 'webp',
                 'image/gif': 'gif', 'image/tiff': 'tiff'}.get(content_type, 'img')
    handler.send_response(200)
    handler.send_header('Content-Type', content_type)
    disposition = 'attachment' if params.get('download', [''])[0] == '1' else 'inline'
    handler.send_header('Content-Disposition', f'{disposition}; filename="xdp-document-{index + 1}.{extension}"')
    handler.send_header('Cache-Control', 'private, max-age=300')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Content-Length', str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def archive_activity(rows):
    """Join XDP Activity column B to OW order number only."""
    from delivery_data import connect

    by_order, statuses = {}, {}
    for row in rows:
        order = str(row.get('order') or '').strip()
        if re.fullmatch(r'\d+\.0', order):
            order = order[:-2]
        if not order:
            continue
        by_order.setdefault(order, []).append(str(row.get('activityXml') or ''))
        status = str(row.get('statusType') or '').strip()
        if status:
            statuses.setdefault(order, set()).add(status)
    matched = 0
    with connect() as db:
        for row in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='XDP'").fetchall():
            order = row['order_id']
            if order not in by_order:
                continue
            delivery = json.loads(row['payload'])
            source_statuses = statuses.get(order, set())
            fingerprint = hashlib.sha256(json.dumps(
                [by_order[order], sorted(source_statuses)], ensure_ascii=False
            ).encode()).hexdigest()
            if delivery.get('xdpActivityFingerprint') == fingerprint:
                matched += 1
                continue
            events = {item['key']: item for item in delivery.get('xdpEvents', []) if item.get('key')}
            activity_error = ''
            for raw in by_order[order]:
                try:
                    events.update({item['key']: item for item in parse_activity(raw)})
                except ValueError as error:
                    activity_error = str(error)
            delivery['xdpEvents'] = sorted(events.values(), key=lambda item: (item['at'], item['key']))
            delivery['xdpActivityError'] = activity_error
            delivery['xdpActivityFingerprint'] = fingerprint
            delivery['xdpActivitySource'] = 'XDP Activity'
            delivery['xdpActivityStatus'] = next(iter(source_statuses)) if len(source_statuses) == 1 else ''
            payload = json.dumps(delivery)
            if payload != row['payload']:
                db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (payload, order))
            matched += 1
        db.commit()
    return matched


def archive(rows):
    from delivery_data import connect

    by_order, by_tracking = {}, {}
    documents_by_order, documents_by_tracking = {}, {}
    barcodes_by_order, barcodes_by_tracking = {}, {}
    details_by_order, details_by_tracking = {}, {}
    consignments_by_order = {}
    for row in rows:
        order = str(row.get("order") or "").strip()
        if re.fullmatch(r"\d+\.0", order):
            order = order[:-2]
        tracking = str(row.get("trackingId") or "").strip().upper()
        consignment_order = str(row.get('consignmentOrder', order) or '').strip()
        if re.fullmatch(r'\d+\.0', consignment_order):
            consignment_order = consignment_order[:-2]
        consignment = str(row.get('consignmentNo', tracking) or '').strip()
        if consignment_order and consignment:
            consignments_by_order.setdefault(consignment_order, set()).add(consignment)
        status = str(row.get("status") or "").strip().upper()
        latest_detail = str(row.get('latestDetail') or '').strip()
        barcodes = [value.strip() for value in str(row.get('parcelBarcode') or '').splitlines() if value.strip()]
        if order:
            by_order.setdefault(order, set()).add(status)
            documents_by_order.setdefault(order, []).extend(document_urls(row.get('documents')))
            barcodes_by_order.setdefault(order, []).extend(barcodes)
            details_by_order.setdefault(order, []).append(latest_detail)
        elif tracking:
            by_tracking.setdefault(tracking, set()).add(status)
            documents_by_tracking.setdefault(tracking, []).extend(document_urls(row.get('documents')))
            barcodes_by_tracking.setdefault(tracking, []).extend(barcodes)
            details_by_tracking.setdefault(tracking, []).append(latest_detail)
    matched = 0
    with connect() as db:
        for row in db.execute("SELECT order_id, payload FROM deliveries WHERE json_extract(payload, '$.carrier')='XDP'").fetchall():
            delivery = json.loads(row["payload"])
            consignments = consignments_by_order.get(row['order_id'], set())
            delivery.pop('xdpConsignmentNo', None)
            if len(consignments) == 1:
                delivery['xdpConsignmentNo'] = next(iter(consignments))
            tracking = str(delivery.get("owTrackingNo") or delivery.get("trk") or "").strip().upper()
            delivery['xdpLatestDetail'] = '\n'.join(dict.fromkeys(value for value in details_by_order.get(
                row['order_id'], details_by_tracking.get(tracking, [])
            ) if value))
            delivery['xdpParcelBarcodes'] = list(dict.fromkeys(barcodes_by_order.get(
                row['order_id'], barcodes_by_tracking.get(tracking, [])
            )))
            delivery['xdpDocuments'] = list(dict.fromkeys(documents_by_order.get(
                row['order_id'], documents_by_tracking.get(tracking, [])
            )))
            statuses = by_order.get(row["order_id"], by_tracking.get(str(delivery.get("owTrackingNo") or delivery.get("trk") or "").strip().upper(), set()))
            delivery.pop("xdpStatus", None)
            if len(statuses) == 1 and next(iter(statuses)):
                delivery["xdpStatus"] = next(iter(statuses))
                matched += 1
            db.execute("UPDATE deliveries SET payload=? WHERE order_id=?", (json.dumps(apply_status(delivery)), row["order_id"]))
        db.commit()
    return matched
