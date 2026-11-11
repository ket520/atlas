"""Exact OW cancellation fields, restricted to confirmed Own van orders."""
import json

VAN_METHODS = {'own van', 'own delivery', 'standard van delivery', 'next day van delivery'}


def ow_cancelled_van(delivery):
    if isinstance(delivery, str):
        delivery = json.loads(delivery)
    category = str((delivery.get('salesActivityDetails') or {}).get('Order Category') or '').strip().lower()
    if category == 'credit/refund' or str(delivery.get('orderRelationKind') or delivery.get('relatedKind') or '').strip().lower() == 'credit/refund':
        return False
    method = str(delivery.get('deliveryMethodRaw') or '').strip().lower()
    if method != 'to be cancelled' and category != 'cancelled':
        return False
    if method in VAN_METHODS or (not method and delivery.get('carrier') == 'Own van'):
        return True
    return method == 'to be cancelled' and str(delivery.get('cancelledFromDeliveryMethod') or '').strip().lower() in VAN_METHODS
