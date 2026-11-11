"""Agreed examples, including contradictory saved categories and blank source statuses."""
def global_status_cases():
    cases = []
    def add(carrier, expected, **fields):
        order = str(700000 + len(cases))
        cases.append((dict(id=order, order=order, carrier=carrier, st='Delivered',
            rawStatus='P', deliveryMethodRaw=carrier, logs=[], **fields), expected))
    for source, expected in [
        ('READY_FOR_RECEIVE','Scheduled'), ('IN_TRANSIT','Scheduled'),
        ('OUT_FOR_DELIVERY','Out for Delivery'), ('DELIVERED','Delivered'),
        ('DELIVERY_ATTEMPTED','Failed'), ('UNDELIVERABLE','Failed'),
        ('REJECTED','Rejected'), ('LOST','Lost'), ('RETURNED_TO_SELLER','Cancelled'),
        ('RETURNED','Return'), ('AWAITING_CUSTOMER_PICKUP','Other Status'),
        ('PICKUP_CANCELLED','Other Status'), ('CARRIER_CANCELLED_PICKUP','Other Status')]:
        add('AMZ', expected, amazonSheetStatus=source)
    for source, expected in [
        ('Palletways Not Assigned','Unscheduled'), ('Unscheduled','Unscheduled'),
        ('Consignment Created','Unscheduled'), ('Scheduled','Scheduled'),
        ('In Transit','Scheduled'), ('Out for Delivery','Out for Delivery'),
        ('Delivered','Delivered'), ('Return','Return'), ('Palletways Look Up Failed','Unassigned')]:
        add('Palletways', expected, palletwaysSheetStatus=source, palletwaysSheetMatched=True)
    for source, expected in [
        ('BOOKING','Unscheduled'), ('DELIVERY','Scheduled'), ('OUT FOR DELIVERY','Out for Delivery'),
        ('NEXT STOP','Next Stop'), ('DELIVERED','Delivered'), ('DAMAGE','Failed'),
        ('DELETE','Failed'), ('NOT RECEIVED','Failed'), ('SMS','Other Status'),
        ('EMAIL','Other Status'), ('CREATE','Other Status')]:
        add('XDP', expected, xdpStatus=source)
    for carrier in ['Palletways', 'XDP']:
        add(carrier, 'Cancelled', salesActivityDetails={'Order Category':'Cancelled'})
    add('XDP', 'Return')
    cases[-1][0]['rawStatus'] = 'RETURN'
    add('XDP', 'Unassigned')
    cases[-1][0]['deliveryMethodRaw'] = 'On hold - TBC'
    add('XDP', 'Other Status')
    cases[-1][0]['st'] = 'Awaiting'
    add('Palletways', 'Unscheduled', palletwaysSheetMatched=False)
    cases[-1][0]['rawStatus'] = 'Invoice waiting to be printed'
    add('Palletways', 'Other Status', palletwaysSheetMatched=True)
    for expected in ['Delivered', 'Failed', 'Scheduled']:
        add('Own van', expected, statusSource='Routine Dashboard - Live')
        cases[-1][0]['st'] = expected
    for expected in ['Failed', 'Rejected', 'Lost']:
        add('Palletways', expected, palletwaysSheetMatched=True, statusSource='Palletways',
            palletwaysStatusLabel=expected)
        cases[-1][0]['st'] = expected
    add('Palletways', 'Delivered', palletwaysSheetStatus='Delivered', palletwaysSheetMatched=True)
    cases[-1][0]['st'] = 'Failed'
    return cases
