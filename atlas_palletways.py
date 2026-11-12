import re
from urllib.parse import quote

from atlas_postgres_provider import _get_json
from palletways_shipments import normalize_shipments


SECTIONS = (
    'tracking_id', 'consignment_number', 'linked_orders', 'status', 'booking',
    'scheduling', 'shipment', 'addresses', 'pallets', 'services', 'bill_units',
    'routing', 'account', 'manifest', 'delivery_confirmation',
    'collection_information', 'documents', 'events', 'sync', 'provenance',
    'historical_snapshot',
)


def structured_shipment(shipment):
    if not isinstance(shipment, dict):
        raise ValueError('Unexpected shipment details response.')
    return {key: shipment.get(key) for key in SECTIONS}


def shipment_details(tracking_id, consignment_number):
    path = shipment_path(tracking_id, consignment_number)
    payload = _get_json(path)
    details = payload if 'tracking_id' in payload else payload.get('shipment', payload)
    return structured_shipment(details)


def shipment_path(tracking_id, consignment_number):
    valid_tracking = re.fullmatch(r'\d{1,32}', tracking_id)
    valid_consignment = re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', consignment_number)
    if not valid_tracking or not valid_consignment:
        raise ValueError('Both valid shipment identifiers are required.')
    return '/atlas/palletways/shipments/{}/{}'.format(
        quote(tracking_id, safe=''), quote(consignment_number, safe='')
    )


def shipment_records(tracking_id, consignment_number, kind, limit=50, offset=0, source=None):
    if kind not in {'events', 'audit'}:
        raise ValueError('Unknown Palletways resource.')
    if not 1 <= limit <= 100 or not 0 <= offset <= 1000000:
        raise ValueError('Invalid pagination values.')
    if source not in (None, 'live', 'historical') or kind == 'audit' and source is not None:
        raise ValueError('Invalid event source.')
    params = {'limit': limit, 'offset': offset}
    if source is not None:
        params['source'] = source
    return _get_json(shipment_path(tracking_id, consignment_number) + '/' + kind, params)


def order_shipments(order):
    if not re.fullmatch(r'\d{1,20}', order):
        raise ValueError('A valid order number is required.')
    payload = _get_json('/atlas/orders/' + quote(order, safe=''))
    section = payload.get('palletways') or {}
    full = section.get('shipments')
    summaries = normalize_shipments([
        shipment
        for line in payload.get('lines', [])
        for shipment in normalize_shipments(line.get('palletways_shipments'))
    ])
    return {
        'details_available': isinstance(full, list),
        'summaries': summaries,
        'shipments': [structured_shipment(item) for item in full] if isinstance(full, list) else [],
    }
