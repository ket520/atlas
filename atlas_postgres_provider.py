"""Test-only Sales Activity provider backed by the Starpark Atlas API.

The provider deliberately returns the same header-keyed row format as
``google_sheets.read_sales_activity``.  It does not connect to PostgreSQL
directly and it never runs unless ``ATLAS_DELIVERY_SOURCE=postgresql``.
"""

import base64
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from atlas_config import setting as _env
from sales_activity import api_store_code
from palletways_shipments import normalize_shipments


DEFAULT_BASE_URL = "https://api.starparkgroup.com"
DEFAULT_PATH = "/atlas/orders"
DEFAULT_TIMEOUT = 20
DEFAULT_PAGE_SIZE = 100
DEFAULT_MAX_PAGES = 1000


class AtlasProviderError(RuntimeError):
    """A safe, user-facing provider failure without credentials in the message."""

    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


def _path(value, path):
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _first(record, names):
    for name in names:
        value = _path(record, name)
        if value is not None and value != "":
            return value
    return ""


def _headers():
    headers = {"Accept": "application/json", "User-Agent": "Atlas-Web-test-provider/1"}
    username = _env("STAR_PARK_API_USERNAME")
    password = _env("STAR_PARK_API_PASSWORD")
    if username or password:
        if not username or not password:
            raise AtlasProviderError("Both Starpark API username and password are required.")
        encoded = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
        headers["Authorization"] = "Basic " + encoded
    else:
        raise AtlasProviderError("Set STAR_PARK_API_USERNAME and STAR_PARK_API_PASSWORD for Starpark Basic Auth.")
    return headers


def _get_json(path, params=None):
    base = _env("STAR_PARK_API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    query = urlencode(params or {})
    url = f"{base}{path}" + (f"?{query}" if query else "")
    request = Request(url, headers=_headers(), method="GET")
    timeout = float(_env("STAR_PARK_API_TIMEOUT_SECONDS", str(DEFAULT_TIMEOUT)))
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except HTTPError as error:
        raise AtlasProviderError(f"Starpark request failed (HTTP {error.code}).", status_code=error.code) from None
    except (URLError, TimeoutError, OSError):
        raise AtlasProviderError("Starpark request failed or timed out.") from None
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise AtlasProviderError("Starpark returned invalid JSON.") from None


def _records(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        raise AtlasProviderError("Starpark returned an unexpected orders response.")
    for key in ("items", "orders", "records", "results"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    for key in ("data", "result"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
        if isinstance(value, dict):
            try:
                return _records(value)
            except AtlasProviderError:
                pass
    raise AtlasProviderError("Starpark orders response contains no record list.")


def _cell_fields(value):
    """Return OrderWise cells as header-keyed fields without discarding values."""
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        fields = {}
        for cell in value:
            if not isinstance(cell, dict):
                continue
            name = cell.get("name") or cell.get("key") or cell.get("field") or cell.get("column")
            if name:
                fields[str(name)] = cell.get("value", cell.get("text", ""))
        return fields
    return {}


def _has_more(payload, count, page, page_size):
    if isinstance(payload, dict):
        for key in ("has_more", "hasMore", "more"):
            if key in payload:
                return bool(payload[key])
        for key in ("next", "next_page", "nextPage"):
            if payload.get(key):
                return True
        total = payload.get("total") or payload.get("total_count") or payload.get("totalCount")
        if isinstance(total, int):
            return page * page_size < total
    return count >= page_size


ALIASES = {
    "Order no": ("Order no", "orderNo", "order_no", "orderNumber", "order_number", "order.number", "order.id", "id"),
    "Order reference": ("Order reference", "orderReference", "order_reference", "reference"),
    "Delivery method": ("Delivery method", "deliveryMethod", "delivery_method", "carrier", "shippingMethod"),
    "Status": ("Status", "status", "orderStatus", "order_status"),
    "Delivery name": ("Delivery name", "deliveryName", "delivery_name", "customer.name", "customerName"),
    "Delivery telephone": ("Delivery telephone", "deliveryTelephone", "delivery_phone", "phone", "customer.phone"),
    "Delivery email": ("Delivery email", "deliveryEmail", "delivery_email", "email", "customer.email"),
    "Delivery postcode": ("Delivery postcode", "deliveryPostcode", "delivery_postcode", "postcode", "address.postcode"),
    "Address": ("Address", "address", "deliveryAddress", "delivery_address", "address.line1"),
    "Special instructions": ("Special instructions", "specialInstructions", "special_instructions", "instructions", "notes"),
    "Tracking No": ("Tracking No", "trackingNo", "tracking_no", "trackingNumber", "tracking_number", "tracking.id"),
    "Order date": ("Order date", "orderDate", "order_date", "createdAt", "created_at"),
    "Despatch Date": ("Despatch Date", "despatchDate", "dispatchDate", "dispatch_date"),
    "eCommerce order number": ("eCommerce order number", "ecommerceOrderNumber", "ecommerce_order_number"),
    "Order Type": ("Order Type", "orderType", "order_type"),
    "Order Analysis": ("Order Analysis", "orderAnalysis", "order_analysis"),
    "Replacement": ("Replacement", "replacement"),
    "Original order Number": ("Original order Number", "originalOrderNumber", "original_order_number"),
    "Original order ID": ("Original order ID", "originalOrderId", "original_order_id"),
    "Gross (base)": ("Gross (base)", "grossBase", "gross_base"),
    "Customer": ("Customer", "customer", "customerName"),
    "EbayUserID": ("EbayUserID", "ebayUserId", "ebay_user_id"),
    "Order Type ID": ("Order Type ID", "orderTypeId", "order_type_id"),
    "Delivery cost": ("Delivery cost", "deliveryCost", "delivery_cost"),
    "Order Category": ("Order Category", "orderCategory", "order_category"),
    "Product SKU": ("Product SKU", "productSku", "product_sku", "sku"),
    "Item Name": ("Item Name", "itemName", "item_name", "productName"),
    "Item Quantity": ("Item Quantity", "itemQuantity", "item_quantity", "quantity"),
}


def _row(record):
    if not isinstance(record, dict):
        raise AtlasProviderError("Starpark returned a non-object order record.")

    nested = {}

    # Starpark PostgreSQL stores the original OrderWise columns in cells.
    nested.update(_cell_fields(record.get("cells")))

    for key in (
        "salesActivity",
        "sales_activity",
        "salesActivityDetails",
        "sales_activity_details",
    ):
        if isinstance(record.get(key), dict):
            nested.update(record[key])

    merged = {**nested, **record}
    row = {}

    for header, aliases in ALIASES.items():
        value = _first(merged, aliases)

        if isinstance(value, (dict, list)):
            value = json.dumps(value, separators=(",", ":"))

        row[header] = str(value).strip() if value is not None else ""

    # Preserve all extra OrderWise columns, including structured cell values.
    for key, value in merged.items():
        if key in row:
            continue
        if key == 'palletways_shipments':
            try:
                row[key] = normalize_shipments(value)
            except (ValueError, TypeError):
                raise AtlasProviderError('Starpark returned invalid Palletways shipments.') from None
        elif isinstance(value, (dict, list)):
            row[key] = json.dumps(value, separators=(",", ":"))
        elif value is not None:
            row[key] = str(value)

    row['Atlas Store Code'] = api_store_code(row)

    if not row["Order no"] or not row["Delivery method"]:
        raise AtlasProviderError(
            "Starpark order records must provide order number and delivery method."
        )

    return row


def read_sales_activity():
    path = _env("STAR_PARK_API_ORDERS_PATH", DEFAULT_PATH)

    page_size = max(
        1,
        min(
            int(_env("STAR_PARK_API_PAGE_SIZE", str(DEFAULT_PAGE_SIZE))),
            500,
        ),
    )

    max_pages = max(
        1,
        int(_env("STAR_PARK_API_MAX_PAGES", str(DEFAULT_MAX_PAGES))),
    )

    rows = []
    offset = 0

    for _ in range(max_pages):
        payload = _get_json(
            path,
            {
                "limit": page_size,
                "offset": offset,
                "include": "palletways_booking",
            },
        )

        page_records = _records(payload)

        rows.extend(_row(record) for record in page_records)

        if not page_records:
            return rows

        if isinstance(payload, dict) and "has_more" in payload:
            has_more = payload["has_more"] is True
        else:
            has_more = len(page_records) >= page_size

        if not has_more:
            return rows

        returned_offset = payload.get("offset", offset) if isinstance(payload, dict) else offset
        returned_count = payload.get("count", len(page_records)) if isinstance(payload, dict) else len(page_records)
        try:
            offset = int(returned_offset) + int(returned_count)
        except (TypeError, ValueError):
            offset += len(page_records)

    raise AtlasProviderError(
        "Starpark orders pagination exceeded the configured page limit."
    )


def connection_test():
    """Read-only connectivity and shape check; returns no credentials or raw headers."""
    health_path = _env("STAR_PARK_API_HEALTH_PATH", "/atlas/health")
    orders_path = _env("STAR_PARK_API_ORDERS_PATH", DEFAULT_PATH)
    health = _get_json(health_path)
    payload = _get_json(orders_path, {"limit": 2})
    sample = [_row(record) for record in _records(payload)]
    return {"health": health, "orderCount": len(sample), "orders": sample}


if __name__ == "__main__":
    if sys.argv[1:] != ["--check"]:
        raise SystemExit("Usage: python -m atlas_postgres_provider --check")
    try:
        result = connection_test()
    except AtlasProviderError as error:
        print(f"Atlas test connection failed: {error}")
        raise SystemExit(1)
    print(f"Atlas health request: OK; orders request: OK; compatible rows: {result['orderCount']}")
