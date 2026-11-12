import json


FIELDS = (
    'palletways_status',
    'carrier_status',
    'status_checked_at',
    'tracking_id',
    'consignment_number',
)
BOOKING_FIELDS = ('booked_in', 'book_in_request', 'booking_date', 'booking_time', 'checked_at', 'source')
UNAVAILABLE = 'Status unavailable'
DELIVERY_STAGES = (
    'Failed', 'Rejected', 'Lost', 'Return', 'Out for Delivery', 'In Transit',
    'Consignment Created', 'Unscheduled', 'Palletways Not Assigned',
)


def normalize_shipments(value):
    if isinstance(value, str):
        value = json.loads(value)
    if value is None:
        return []
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError('Palletways shipments must be an array of objects.')
    result = []
    positions = {}
    for item in value:
        shipment = {
            field: str(item[field]).strip() if item.get(field) is not None else None
            for field in FIELDS
        }
        shipment['mapping_status'] = str(item['mapping_status']).strip() if item.get('mapping_status') is not None else None
        booking = item.get('booking_summary')
        if booking is not None:
            if not isinstance(booking, dict):
                raise ValueError('Invalid Palletways booking summary.')
            if any(booking.get(field) is not None and type(booking.get(field)) is not bool
                   for field in BOOKING_FIELDS[:2]):
                raise ValueError('Invalid Palletways booking flag.')
            shipment['booking_summary'] = {
                field: booking.get(field) if field in BOOKING_FIELDS[:2]
                else str(booking[field]).strip() if booking.get(field) is not None else None
                for field in BOOKING_FIELDS
            }
        identity = (shipment['tracking_id'], shipment['consignment_number'], shipment['mapping_status'])
        if not any(identity[:2]):
            identity = (json.dumps(shipment, sort_keys=True), None, None)
        if identity in positions:
            previous = result[positions[identity]]
            if shipment.get('booking_summary') and not previous.get('booking_summary'):
                result[positions[identity]] = shipment
        else:
            positions[identity] = len(result)
            result.append(shipment)
    return result


def shipments(delivery):
    if delivery.get('carrier') != 'Palletways':
        return []
    return delivery.get('palletwaysShipments') or []


def shipment_statuses(delivery):
    statuses = (item.get('palletways_status') or UNAVAILABLE for item in shipments(delivery))
    return list(dict.fromkeys(statuses)) or [UNAVAILABLE]


def delivery_stage(delivery):
    statuses = shipment_statuses(delivery)
    if all(value == 'Delivered' for value in statuses):
        return 'Delivered'
    for value in DELIVERY_STAGES:
        if value in statuses:
            return value
    return UNAVAILABLE
