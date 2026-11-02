"""Read dashboard cohorts from the retained order index; never invent workflow counts."""
from datetime import datetime
from zoneinfo import ZoneInfo


WIDGET_KEYS = ('cancelled', 'hold', 'out-of-stock', 'charge-pending', 'collect',
               'palletways-next-day', 'palletways-unbooked', 'van-unscheduled', 'returns', 'awaiting-dispatch')


def widget_condition(key):
    if key in ('palletways-unbooked-b2b', 'palletways-unbooked-b2c'):
        clause, values = widget_condition('palletways-unbooked')
        return (clause + " AND json_extract(payload, '$.carrier')='Palletways' AND palletways_classification(payload)=?", values + [key[-3:].upper()])
    status = "coalesce(json_extract(payload, '$.st'), '')"
    carrier = "coalesce(json_extract(payload, '$.carrier'), '')"
    booking = "lower(trim(coalesce(json_extract(payload, '$.bookingStatus'), '')))"
    uk_day = datetime.now(ZoneInfo('Europe/London')).date()
    conditions = {
        'awaiting-dispatch': ("upper(trim(coalesce(json_extract(payload, '$.rawStatus'), ''))) IN ('W', 'AWAITING DESPATCH', 'AWAITING DISPATCH')", []),
        'cancelled': (f"({carrier}='Cancelled' OR {status}='Cancelled') AND substr(json_extract(payload, '$.orderDate'),1,10)=?",
                      [uk_day.isoformat()]),
        'cancelled-month': (f"({carrier}='Cancelled' OR {status}='Cancelled') AND substr(json_extract(payload, '$.orderDate'),1,7)=?",
                            [uk_day.strftime('%Y-%m')]),
        'hold': (f"({carrier}='On Hold' OR {status}='Unassigned')", []),
        'out-of-stock': (f"({booking} LIKE '%out of stock%' OR {booking}='o/s') AND {status} NOT IN ('Delivered','Cancelled','Return')", []),
        'charge-pending': (f"{carrier}='Charge Pending (Remote Postcode)'", []),
        'collect': (f"{carrier}='Collect in Person'", []),
        'palletways-next-day': (f"{carrier}='Palletways' AND lower(json_extract(payload, '$.deliveryMethodRaw')) LIKE '%next day%' AND {status} NOT IN ('Delivered','Cancelled','Return')", []),
        'palletways-unbooked': (f"{carrier}='Palletways' AND lower(trim(coalesce(json_extract(payload, '$.palletwaysSheetBookedIn'), '')))='no' AND lower(trim(coalesce(nullif(trim(json_extract(payload, '$.palletwaysSheetStatus')), ''), json_extract(payload, '$.st'), '')))!='delivered' AND EXISTS (SELECT 1 FROM sales_activity_orders AS ow WHERE ow.order_id=deliveries.order_id)", []),
        'van-unscheduled': (f"{carrier} IN ('Own van','Self Delivery','LOCAL MULTIDROP') AND ({status}='Unscheduled' OR {booking} IN ('o/s','out of stock','on hold','open')) AND {status} NOT IN ('Delivered','Cancelled','Return')", []),
        # Processing state belongs to the planned Returns workflow, not shipment status.
        'returns': ('0', []),
    }
    if key not in conditions:
        raise ValueError('Unknown dashboard widget.')
    return conditions[key]


def snapshot(store='', carrier='', **visibility):
    from delivery_data import query_records, connect
    with connect() as db:
        ow_snapshot_ready = bool(db.execute(
            "SELECT 1 FROM sync_metadata WHERE key='sales_activity_orders_snapshot'").fetchone())
    widgets = {}
    for key in WIDGET_KEYS:
        if key == 'returns':
            widgets[key] = {'available': False, 'total': None, 'preview': []}
            continue
        if key == 'palletways-unbooked' and not ow_snapshot_ready:
            widgets[key] = {'available': False, 'total': None, 'preview': [],
                            'scope': 'booked-in-no-current-ow-not-delivered',
                            'reason': 'Waiting for Sales Activity sync'}
            continue
        result = query_records(store=store, carrier=carrier, dashboard_widget=key, limit=30, **visibility)
        widgets[key] = {'available': True, 'total': result['total'], 'preview': [
            {name: row.get(name, '') for name in ('id', 'order', 'orderDate', 'date', 'cust', 'st')}
            for row in result['deliveries'][:3]
        ]}
        widgets[key]['rows'] = [{name: row.get(name, '') for name in ('id', 'order', 'orderDate', 'orderDateTime', 'cust', 'orderRef', 'deliveryMethodRaw', 'carrier', 'postcode', 'palletwaysSheetStatus', 'st')}
                                for row in result['deliveries']]
        if key == 'cancelled':
            widgets[key]['scope'] = 'today'
        elif key == 'palletways-unbooked':
            widgets[key]['scope'] = 'booked-in-no-current-ow-not-delivered'
    return {'widgets': widgets}


def widget_facets(key):
    """Tracking's counts follow the same cohort as a widget's View all action."""
    from delivery_data import connect
    clause, values = widget_condition(key)
    with connect() as db:
        return [dict(row) for row in db.execute(
            "SELECT json_extract(payload, '$.carrier') AS carrier, "
            "json_extract(payload, '$.st') AS status, "
            "json_extract(payload, '$.deliveryMethodRaw') AS classification, "
            "coalesce(nullif(json_extract(payload, '$.amazonSheetStatus'), ''), json_extract(payload, '$.amazonStatus')) AS amazonStatus, "
            "json_extract(payload, '$.stopstartStatus') AS stopstartStatus, "
            "json_extract(payload, '$.xdpStatus') AS xdpStatus, "
            "json_extract(payload, '$.palletwaysSheetStatus') AS palletwaysSheetStatus, "
            "tracking_today(payload, ?) AS today, "
            "json_extract(payload, '$.salesActivityDetails.\"Order Type\"') AS orderType, "
            "purchase_store(payload) AS purchaseStore, palletways_classification(payload) AS palletwaysClassification, COUNT(*) AS count "
            "FROM deliveries WHERE " + clause + " GROUP BY 1,2,3,4,5,6,7,8,9,10,11",
            [datetime.now(ZoneInfo('Europe/London')).date().isoformat(), *values])]
