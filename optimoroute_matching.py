"""Exact, one-to-one OptimoRoute identity matching; never match by address alone."""
import re


def identifiers(delivery):
    return {
        'orderRef': str(delivery.get('orderRef') or '').strip(),
        'eCommerce order number': str((delivery.get('salesActivityDetails') or {}).get('eCommerce order number') or '').strip(),
    }


def resolve(deliveries, orders, complete=True):
    """Preserve primary matching; require unique ownership and postcode for fallback."""
    owners = {}
    for delivery in deliveries:
        for value in set(identifiers(delivery).values()) - {''}:
            owners.setdefault(value, set()).add(delivery['order'])
    by_reference = {}
    for order in orders:
        reference = str((order.get('data') or {}).get('orderNo') or '').strip()
        by_reference.setdefault(reference, {})[order['id']] = order
    matched, warnings = {}, {}
    if not complete:
        return matched, {d['order']: 'OptimoRoute search was incomplete; no automatic match was made.' for d in deliveries}
    for delivery in deliveries:
        if delivery.get('carrier') not in {'Own van', 'Self Delivery', 'LOCAL MULTIDROP'}:
            continue
        category = str((delivery.get('salesActivityDetails') or {}).get('Order Category') or '').strip().casefold()
        if category == 'credit/refund' or delivery.get('orderRelationKind') == 'Credit/Refund':
            continue
        keys = identifiers(delivery)
        for field, value in keys.items():
            candidates = list(by_reference.get(value, {}).values()) if value else []
            if not candidates:
                continue
            if len(candidates) != 1 or owners.get(value) != {delivery['order']}:
                warnings[delivery['order']] = 'OptimoRoute reference is ambiguous; no automatic match was made.'
                break
            item = candidates[0]
            if field != 'orderRef':
                postcode = str(delivery.get('postcode') or '').strip()
                address = str(((item.get('data') or {}).get('location') or {}).get('address') or '')
                compact = re.sub(r'\s+', '', postcode)
                pattern = r'\b' + r'\s*'.join(re.escape(c) for c in compact) + r'\b'
                if not compact or not re.search(pattern, address, re.I):
                    warnings[delivery['order']] = 'OptimoRoute eCommerce reference requires a matching delivery postcode; no automatic match was made.'
                    break
            matched[delivery['order']] = (item, field, value)
            break
    # A primary reference and a fallback reference must not claim the same stop.
    claims = {}
    for order_id, (item, _, _) in matched.items():
        claims.setdefault(item['id'], []).append(order_id)
    for claimants in claims.values():
        if len(claimants) > 1:
            for order_id in claimants:
                matched.pop(order_id)
                warnings[order_id] = 'Multiple OW orders claim this OptimoRoute stop; no automatic match was made.'
    return matched, warnings


def search(candidates, api):
    """Read all exact identifier results, in bounded batches; never guess on truncation."""
    references = sorted({v for d in candidates for v in identifiers(d).values() if v})
    orders = {}
    for start in range(0, len(references), 25):
        query = {'orders': [{'orderNo': v} for v in references[start:start + 25]],
                 'includeOrderData': True, 'includeScheduleInformation': True}
        for _ in range(20):
            result = api('search_orders', query)
            orders.update({o['id']: o for o in result['orders']})
            if not result.get('after_tag'):
                break
            query['after_tag'] = result['after_tag']
        else:
            return list(orders.values()), False
    return list(orders.values()), True
