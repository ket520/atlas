import html
import json
import re
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen


STORES = {
    "Shopify - Neshome": "https://neshome.co.uk",
    "Bathroom Republic - Website": "https://bathroomrepublic.co.uk",
    "B&Q": "https://www.diy.com",
    "Amazon": "https://www.amazon.co.uk",
    "Ebay Bathroom Republic": "https://www.ebay.co.uk",
    "EBay Willesden Bathroom": "https://www.ebay.co.uk",
}


class ProductLookupError(RuntimeError):
    pass


def official_url(base, value):
    url = urljoin(base, value)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc != urlsplit(base).netloc:
        return ""
    return url


def marketplace_product_url(store, platform_id):
    if store == 'Amazon' and re.fullmatch(r'[A-Z0-9]{10}', platform_id):
        return f'https://www.amazon.co.uk/gp/product/{platform_id}'
    if store in {'Ebay Bathroom Republic', 'EBay Willesden Bathroom'} and re.fullmatch(r'\d{9,15}', platform_id):
        return f'https://www.ebay.co.uk/itm/{platform_id}?' + urlencode({'ViewItem': '', 'item': platform_id})
    return ''


def read_url(url):
    request = Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json,text/html"})
    with urlopen(request, timeout=10) as response:
        return response.read(4_000_000).decode("utf-8")


def shopify_product(base, sku):
    query = urlencode({"q": sku, "resources[type]": "product", "resources[limit]": 10})
    payload = json.loads(read_url(f"{base}/search/suggest.json?{query}"))
    products = payload.get("resources", {}).get("results", {}).get("products", [])
    matches = set()
    for product in products[:10]:
        handle = product.get("handle", "")
        if not re.fullmatch(r"[a-zA-Z0-9_-]+", handle):
            continue
        detail = json.loads(read_url(f"{base}/products/{handle}.js"))
        for variant in detail.get("variants", []):
            if str(variant.get("sku", "")).strip().casefold() == sku.casefold():
                variant_id = str(variant.get("id", ""))
                if variant_id.isdigit():
                    matches.add(f"{base}/products/{handle}?variant={variant_id}")
    return matches


class ProductPageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = set()
        self.documents = []
        self.script = None
        self.canonical = ''

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if tag == 'link' and attributes.get('rel') == 'canonical':
            self.canonical = attributes.get('href', '')
        if tag == "a" and "/departments/" in attributes.get("href", ""):
            self.links.add(attributes["href"])
        if tag == "script" and attributes.get("type") == "application/ld+json":
            self.script = ""

    def handle_data(self, data):
        if self.script is not None:
            self.script += data

    def handle_endtag(self, tag):
        if tag == "script" and self.script is not None:
            try:
                self.documents.append(json.loads(self.script))
            except ValueError:
                pass
            self.script = None


def product_matches(value, sku):
    if isinstance(value, list):
        return any(product_matches(item, sku) for item in value)
    if not isinstance(value, dict):
        return False
    types = value.get("@type", [])
    if isinstance(types, str):
        types = [types]
    if "Product" in types and any(
        str(value.get(key, "")).strip().casefold() == sku.casefold() for key in ("sku", "mpn")
    ):
        return True
    return any(product_matches(item, sku) for item in value.values() if isinstance(item, (dict, list)))


def bq_product(base, sku):
    search = ProductPageParser()
    search.feed(read_url(f"{base}/search?{urlencode({'term': sku})}"))
    matches = set()
    for link in sorted(search.links)[:8]:
        url = official_url(base, link)
        if not url or not urlsplit(url).path.endswith(".prd"):
            continue
        product = ProductPageParser()
        product.feed(read_url(url))
        if product_matches(product.documents, sku):
            matches.add(url)
    return matches


@lru_cache(maxsize=2048)
def resolve_product(store, sku, platform_id=''):
    base = STORES.get(store)
    sku = sku.strip()
    if not base or not sku or len(sku) > 200:
        raise ValueError("A supported store and SKU are required.")
    if store in {'Amazon', 'Ebay Bathroom Republic', 'EBay Willesden Bathroom'}:
        target = marketplace_product_url(store, platform_id.strip())
        if target:
            return target
        raise ProductLookupError('No verified marketplace product ID is saved for this SKU.')
    try:
        if store == 'Bathroom Republic - Website':
            from shopify_products import configured_product_url
            target = configured_product_url(sku, base)
            if target:
                return target
        matches = bq_product(base, sku) if store == "B&Q" else shopify_product(base, sku)
    except Exception as error:
        raise ProductLookupError("The store could not be reached. Please try again.") from error
    if len(matches) != 1:
        raise ProductLookupError("No unique product page was found for this SKU.")
    return next(iter(matches))


def verified_product_url(store, sku, platform_id=''):
    try:
        target = resolve_product(store, sku, platform_id)
        if store == 'Amazon':
            content = read_url(target)
            if 'productTitle' not in content or platform_id not in content:
                return None
        elif store in {'Ebay Bathroom Republic', 'EBay Willesden Bathroom'}:
            content = read_url(target)
            page = ProductPageParser()
            page.feed(content)
            canonical = official_url(STORES[store], page.canonical) if page.canonical else ''
            if not canonical or not re.search(r'/itm/(?:[^/]+/)?' + re.escape(platform_id) + r'(?:[/?#]|$)', canonical):
                return None
        return target
    except (ValueError, ProductLookupError, OSError):
        return None


def lookup_page(store, sku, message):
    return f'''<!doctype html>
<html lang="en">
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Product lookup</title>
  <style>
    body {{
      font: 16px/1.6 system-ui;
      color: #12223d;
      max-width: 520px;
      margin: 12vh auto;
      padding: 24px;
    }}
  </style>
  <h1>Product lookup</h1>
  <p>{html.escape(store)} · {html.escape(sku)}</p>
  <p>{html.escape(message)}</p>
</html>'''.encode()
