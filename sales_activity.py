"""Header-based product mapping for current and earlier Sales Activity exports."""

import re


STORE_CODES = {
    'EBAY_BR': 'Ebay Bathroom Republic',
    'EBAY_WB': 'EBay Willesden Bathroom',
    'AMAZON': 'Amazon',
    'DEBENHAM': 'Debenhams - Neshome',
    'B&Q': 'B&Q',
    'SHOPIFY': 'Shopify - Neshome',
    'BATHPROF': 'Bathroom Republic - Website',
    'BATHREP': 'Bathroom Republic - Website',
    'BATHROOM': 'Bathroom Republic - Website',
    'WILKO': 'Wilko',
    'WAYFAIR': 'Wayfair',
}

API_STORE_CHANNELS = {name.casefold(): code for code, name in STORE_CODES.items()}
API_STORE_CHANNELS.update({
    'b&q - neshome': 'B&Q',
    'b&q': 'B&Q',
    'amazon': 'AMAZON',
    'ebay0': 'EBAY_BR',
    'ebay1': 'EBAY_WB',
})

MARKETPLACE_ID_FIELDS = {
    'asin': ('ASIN', 'Amazon ASIN', 'amazon_asin', 'asin'),
    'ebayItemId': ('eBay Item ID', 'Ebay Item ID', 'ebay_item_id', 'ebayItemId'),
}


def store_name(code, order_type='', analysis=''):
    """AH supplies store identity; retain the existing Hygienic rule."""
    if text(order_type).lower() in {'sales', 'hr_replacement'}:
        return 'Hygienic Cleaning Company (UK) LTD'
    code = text(code).upper()
    return STORE_CODES.get(code, '')


def store_code(row):
    if 'Atlas Store Code' in row:
        return text(row['Atlas Store Code']).upper()
    # worksheet_to_records preserves source positions, including unnamed columns.
    values = list(row.values())
    return text(values[33]).upper() if len(values) > 33 else ''


def api_store_code(row):
    for name in ('Store Code', 'storeCode', 'store_code', 'Channel Code', 'channel_code'):
        value = text(row.get(name)).upper()
        if value in STORE_CODES:
            return value
    for name in ('Order Analysis', 'Order Type'):
        value = text(row.get(name)).casefold()
        if value in API_STORE_CHANNELS:
            return API_STORE_CHANNELS[value]
    return ''


def text(value):
    return "" if value is None else str(value).strip()


def sku_value(row):
    fields = {re.sub(r"[^a-z0-9]", "", str(key).lower()): value for key, value in row.items()}
    for name in ("parentsku", "parentskus", "productsku", "skuofitems", "sku"):
        value = text(fields.get(name))
        if value:
            return value
    return ""


def product_items(rows):
    items = []
    for row in rows:
        description = text(row.get("Item Name") or row.get("Product description") or row.get("Item description"))
        quantity = text(row.get("Item Quantity"))
        codes = [code.strip() for code in re.split(r"[,;|\r\n]+", sku_value(row)) if code.strip()]
        for code in codes:
            item = {"sku": code, "description": description if len(codes) == 1 else ""}
            if len(codes) == 1:
                for field, names in MARKETPLACE_ID_FIELDS.items():
                    identifiers = {text(row.get(name)) for name in names if text(row.get(name))}
                    if len(identifiers) == 1:
                        item[field] = next(iter(identifiers))
            if len(codes) == 1 and re.fullmatch(r"\d+(?:\.\d+)?", quantity):
                item["quantity"] = quantity
            if item not in items:
                items.append(item)
    return items
