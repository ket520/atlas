"""Read saved Sales Activity order links and explicit Product SKU values for claims."""
import re
from tracking_relations import lookup
from delivery_data import purchase_store


def order_fields(order):
    order = str(order or '').strip()
    if not re.fullmatch(r'\d{1,20}', order):
        raise ValueError('Enter an exact numeric order number.')
    links = lookup(order)
    searched = links['original']
    if not searched:
        return {'found': False, 'order': order}
    parents = [item for item in links['related'] if item['relatedKind'] == 'Original']
    parent_id = links['parentOrder']
    is_replacement = bool(parent_id) and (searched.get('salesActivityDetails') or {}).get('Order Category', 'Order').casefold() == 'order'
    original = parents[0] if parents else searched
    replacements = [item['order'] for item in links['related'] if item['relatedKind'] == 'Replacement']
    if is_replacement:
        replacements = [order]
    # Prefer the defective original's Product SKU; never substitute Parent SKU.
    return {'found': True, 'order': order, 'originalOrderNo': parent_id or original['order'],
            'replacementOrderNo': replacements[0] if len(replacements) == 1 else '',
            'replacementOptions': replacements, 'variantCodes': [] if parent_id and not parents else original.get('productSkuItems') or [],
            'sellingShop': '' if parent_id and not parents else purchase_store(original),
            'originalUnavailable': bool(parent_id and not parents)}
