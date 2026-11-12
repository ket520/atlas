import json


def is_next_day(delivery):
    return str(delivery.get('deliveryMethodRaw') or '').strip().casefold() == 'palletways next day'


def current_shipments(delivery):
    return [shipment for shipment in delivery.get('palletwaysShipments') or []
            if str(shipment.get('mapping_status') or '').strip().casefold() not in {'inactive', 'historical', 'replaced'}]


def state(delivery, shipment, field):
    booking = shipment.get('booking_summary') or {}
    value = booking.get(field)
    if is_next_day(delivery):
        if field == 'booked_in' and value is False:
            return 'not-applicable'
        return 'hidden'
    if value is True:
        return 'yes'
    if value is False:
        return 'not-yet' if field == 'booked_in' else 'no'
    return 'unknown'


def matches_filters(delivery, booked_in, book_in_request):
    shipments = current_shipments(delivery)
    if not shipments:
        return not is_next_day(delivery) and booked_in in {'', 'unknown'} and book_in_request in {'', 'unknown'}
    return any(
        (not booked_in or state(delivery, shipment, 'booked_in') == booked_in)
        and (not book_in_request or state(delivery, shipment, 'book_in_request') == book_in_request)
        for shipment in shipments
    )


def matches_payload(payload, booked_in, book_in_request):
    return int(matches_filters(json.loads(payload), booked_in, book_in_request))
