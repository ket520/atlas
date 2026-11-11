"""Global Tracking groups. Carrier-specific filters and saved statuses stay separate."""
import json

AMAZON_GLOBAL = {
    'READY_FOR_RECEIVE': 'Scheduled', 'IN_TRANSIT': 'Scheduled',
    'OUT_FOR_DELIVERY': 'Out for Delivery', 'DELIVERED': 'Delivered',
    'DELIVERY_ATTEMPTED': 'Failed', 'UNDELIVERABLE': 'Failed',
    'REJECTED': 'Rejected', 'LOST': 'Lost', 'RETURNED_TO_SELLER': 'Cancelled',
    'RETURNED': 'Return', 'AWAITING_CUSTOMER_PICKUP': 'Other Status',
    'PICKUP_CANCELLED': 'Other Status', 'CARRIER_CANCELLED_PICKUP': 'Other Status',
}
PALLETWAYS_GLOBAL = {
    'PALLETWAYS NOT ASSIGNED': 'Unscheduled', 'UNSCHEDULED': 'Unscheduled',
    'CONSIGNMENT CREATED': 'Unscheduled', 'SCHEDULED': 'Scheduled',
    'IN TRANSIT': 'Scheduled', 'OUT FOR DELIVERY': 'Out for Delivery',
    'DELIVERED': 'Delivered', 'RETURN': 'Return',
    'PALLETWAYS LOOK UP FAILED': 'Unassigned',
}
XDP_GLOBAL = {
    'BOOKING': 'Unscheduled', 'UNSCHEDULED': 'Unscheduled',
    'SCHEDULED': 'Scheduled', 'DELIVERY': 'Scheduled',
    'OUT FOR DELIVERY': 'Out for Delivery', 'NEXT STOP': 'Next Stop',
    'DELIVERED': 'Delivered', 'DAMAGE': 'Failed', 'DELETE': 'Failed',
    'NOT RECEIVED': 'Failed', 'FAILED': 'Failed', 'REJECTED': 'Rejected', 'LOST': 'Lost',
    'SMS': 'Other Status', 'EMAIL': 'Other Status', 'CREATE': 'Other Status',
    'AWAITING': 'Other Status',
}
GLOBAL_STATUSES = frozenset(['Other Status', 'Unscheduled', 'Scheduled', 'Out for Delivery',
    'Next Stop', 'Delivered', 'Failed', 'Rejected', 'Lost', 'Cancelled', 'Return', 'Unassigned'])


def canonical_status(value):
    value = str(value or '').strip()
    value = {'Completed': 'Delivered', 'In Transit': 'Scheduled', 'Rescheduled': 'Scheduled',
             'Failed Delivery': 'Failed', 'New': 'Unscheduled', 'Status unverified': 'Unscheduled'}.get(value, value)
    return value if value in GLOBAL_STATUSES else 'Other Status'


def global_tracking_status(delivery):
    if isinstance(delivery, str):
        delivery = json.loads(delivery)
    stored = delivery.get('st') or delivery.get('status')
    carrier = delivery.get('carrier')
    details = delivery.get('salesActivityDetails') or {}
    category = str(details.get('Order Category') or delivery.get('orderCategory') or
                   delivery.get('orderRelationKind') or delivery.get('relatedKind') or '').strip().lower()
    if carrier in {'Palletways', 'XDP'} and category == 'cancelled':
        return 'Cancelled'
    method = str(delivery.get('deliveryMethodRaw') or delivery.get('classification') or '').strip().lower()
    if carrier == 'AMZ':
        raw = str(delivery.get('amazonSheetStatus') or delivery.get('amazonStatus') or '').strip().upper()
        return AMAZON_GLOBAL.get(raw, 'Other Status') if raw else canonical_status(stored)
    if carrier == 'Palletways':
        raw = str(delivery.get('palletwaysSheetStatus') or '').strip().upper()
        if raw in PALLETWAYS_GLOBAL:
            return PALLETWAYS_GLOBAL[raw]
        if method == 'on hold - tbc':
            return 'Unassigned'
        if stored in {'Failed', 'Rejected', 'Lost'}:
            return stored
        if raw or delivery.get('palletwaysSheetMatched'):
            return 'Other Status'
        # Preserve the existing OW fallback grouping for orders absent from the tab.
        from delivery_data import ow_status_name
        return canonical_status(ow_status_name(delivery.get('rawStatus')))
    if carrier == 'XDP':
        raw = ' '.join(str(delivery.get('xdpStatus') or '').strip().upper().replace('_', ' ').split())
        if raw in XDP_GLOBAL:
            return XDP_GLOBAL[raw]
        if method == 'on hold - tbc':
            return 'Unassigned'
        if str(delivery.get('rawStatus') or '').strip().upper() == 'RETURN':
            return 'Return'
        return 'Other Status' if raw else canonical_status(stored)
    return canonical_status(stored)
