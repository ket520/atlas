"""Read Sales Activity facts for an editable collection note."""

import re
import threading
import time
from sales_activity import product_items

_lock = threading.Lock()
_rows = None
_read_at = 0


def order_note(order, rows, on_progress=None):
    order = str(order).strip()
    if not re.fullmatch(r"\d{1,20}", order):
        raise ValueError("Enter a numeric order number.")
    matches = []
    total = len(rows)
    if on_progress:
        on_progress({"stage": "matching", "completed": 0, "total": total})
    for index, row in enumerate(rows, 1):
        if str(row.get("Order no") or "").strip() == order:
            matches.append(row)
        if on_progress and (index % 250 == 0 or index == total):
            on_progress({"stage": "matching", "completed": index, "total": total})
    if not matches:
        return {"found": False, "order": order}

    def value(*names):
        for name in names:
            values = {str(row.get(name) or "").strip() for row in matches}
            values.discard("")
            if len(values) == 1:
                return values.pop()
            if len(values) > 1:
                return ""
        return ""

    def column_value(index):
        # worksheet_to_records preserves source column order, including blank headers.
        # These dedicated address columns are explicitly mapped by sheet position.
        values = {str(list(row.values())[index] or "").strip()
                  for row in matches if len(row) > index}
        values.discard("")
        return values.pop() if len(values) == 1 else ""

    def street3_value():
        headers = {"street3", "address3", "addressline3", "deliveryaddress3", "deliveryaddressline3", "deliverystreet3"}
        values = {str(field or "").strip()
                  for row in matches for name, field in row.items()
                  if re.sub(r"[^a-z0-9]", "", str(name).lower()) in headers}
        values.discard("")
        return values.pop() if len(values) == 1 else ""

    items = product_items(matches)
    order_type = value("Order Type")
    company = value("Order Analysis") if order_type.casefold() == "shopify" else order_type
    if order_type.casefold() == "sales":
        company = "Hygienic Orders"
    return {
        "found": True,
        "order": order,
        "fields": {
            "orderRef": value("Order reference"),
            "company": company,
            "customer": value("Delivery name"),
            "street1": column_value(27),  # AB
            "street2": column_value(28),  # AC
            "street3": street3_value(),
            "city": column_value(30),  # AE
            "country": column_value(32),  # AG
            "postcode": value("Delivery postcode"),
            "phone": value("Delivery telephone"),
            "collectionOrder": order,
        },
        "items": items,
    }


def lookup(order, on_progress=None):
    global _rows, _read_at
    if not re.fullmatch(r"\d{1,20}", str(order).strip()):
        raise ValueError("Enter a numeric order number.")
    if on_progress:
        on_progress({"stage": "waiting"})
    with _lock:
        if _rows is None or time.monotonic() - _read_at >= 300:
            from google_sheets import read_sales_activity

            if on_progress:
                on_progress({"stage": "reading"})
            rows = read_sales_activity()
            _rows, _read_at = rows, time.monotonic()
        return order_note(order, _rows, on_progress)
