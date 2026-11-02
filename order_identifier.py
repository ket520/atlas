"""Exact identifier lookup using the same saved carrier fields as Tracking."""
import json
import re

from delivery_data import connect, purchase_store


def lookup(value):
    value = str(value).strip()
    if not re.fullmatch(r'(?=.{1,64}$)(?=.*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', value):
        raise ValueError('Enter an exact order ID, tracking ID or consignment number.')
    with connect() as db:
        rows = db.execute('''SELECT order_id, payload FROM deliveries
            WHERE order_id=? OR (json_extract(payload, '$.carrier')='Palletways' AND
            (json_extract(payload, '$.palletwaysSheetTrackingNumber')=? OR
             json_extract(payload, '$.palletwaysSheetConsignmentNumber')=?))
            OR (json_extract(payload, '$.carrier')='AMZ' AND
                upper(trim(json_extract(payload, '$.owTrackingNo')))=upper(?))
            OR (json_extract(payload, '$.carrier')='XDP' AND
                instr(char(10) || upper(replace(json_extract(payload, '$.xdpConsignmentNo'), char(13), '')) || char(10),
                      char(10) || upper(?) || char(10)) > 0)''',
            (value, value, value, value, value)).fetchall()
    if len(rows) > 1:
        return {'found': False, 'ambiguous': True, 'order': value,
                'message': 'This number matches more than one order. Try another identifier.'}
    if not rows:
        return {'found': False, 'order': value}
    delivery = json.loads(rows[0]['payload'])
    result = {'found': True, 'order': rows[0]['order_id'],
              'store': purchase_store(delivery), 'courier': delivery.get('carrier', '')}
    if result['courier'] == 'Palletways':
        result.update(trackingId=delivery.get('palletwaysSheetTrackingNumber', ''),
                      consignmentNumber=delivery.get('palletwaysSheetConsignmentNumber', ''))
    elif result['courier'] == 'AMZ':
        result['trackingId'] = delivery.get('owTrackingNo', '')
    elif result['courier'] == 'XDP':
        result['consignmentNumber'] = delivery.get('xdpConsignmentNo', '')
    return result
