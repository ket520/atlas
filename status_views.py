import json

from palletways_shipments import UNAVAILABLE, delivery_stage, shipment_statuses


SOURCES = {
    'Palletways': 'Atlas API · Palletways',
    'Own van': 'OptimoRoute',
    'Self Delivery': 'OptimoRoute',
    'LOCAL MULTIDROP': 'OptimoRoute',
    'AMZ': 'Amazon Shipping',
    'XDP': 'XDP',
    'Stopstart': 'Stopstart',
    'Yodel': 'Yodel',
}


def sales_status(delivery):
    return str(delivery.get('rawStatus') or '').strip() or UNAVAILABLE


def carrier_status(delivery):
    carrier = delivery.get('carrier')
    if carrier in {'Own van', 'Self Delivery', 'LOCAL MULTIDROP'}:
        raw = str(delivery.get('providerStatus') or '').strip()
        return raw.replace('_', ' ').title() if raw else UNAVAILABLE
    if carrier == 'Palletways':
        return ' · '.join(shipment_statuses(delivery))
    return UNAVAILABLE


def status_view(delivery):
    status = carrier_status(delivery)
    carrier = delivery.get('carrier')
    is_palletways = carrier == 'Palletways'
    return {
        'sales': sales_status(delivery),
        'carrier': status,
        'source': SOURCES.get(carrier, 'Carrier'),
        'available': status != UNAVAILABLE,
        'carrierStatuses': shipment_statuses(delivery) if is_palletways else [status],
        'stage': delivery_stage(delivery) if is_palletways else status,
    }


def status_value(payload, scope):
    delivery = json.loads(payload)
    return carrier_status(delivery) if scope == 'carrier' else sales_status(delivery)
