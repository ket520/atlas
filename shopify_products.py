import json
import re
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from atlas_config import setting


PRODUCT_QUERY = """
query ProductLink($query: String!) {
  productVariants(first: 100, query: $query) {
    nodes { id sku product { onlineStoreUrl } }
    pageInfo { hasNextPage }
  }
}
"""


def configured_product_url(sku, base):
    domain = setting('SHOPIFY_BATHROOM_REPUBLIC_DOMAIN')
    token = setting('SHOPIFY_BATHROOM_REPUBLIC_TOKEN')
    version = setting('SHOPIFY_BATHROOM_REPUBLIC_API_VERSION', '2026-07')
    if not domain or not token:
        return ''
    if not re.fullmatch(r'[a-zA-Z0-9-]+\.myshopify\.com', domain) or not re.fullmatch(r'\d{4}-\d{2}', version):
        raise ValueError('Invalid Shopify API configuration.')
    escaped = re.sub(r'([\\":()])', r'\\\1', sku)
    request = Request(
        f'https://{domain}/admin/api/{version}/graphql.json',
        data=json.dumps({'query': PRODUCT_QUERY, 'variables': {'query': f'sku:"{escaped}"'}}).encode(),
        headers={'Content-Type': 'application/json', 'X-Shopify-Access-Token': token},
        method='POST',
    )
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if payload.get('errors'):
        raise ValueError('Shopify product lookup failed.')
    variants = (payload.get('data') or {}).get('productVariants') or {}
    if variants.get('pageInfo', {}).get('hasNextPage'):
        return ''
    matches = set()
    for variant in variants.get('nodes', []):
        if str(variant.get('sku', '')).strip().casefold() != sku.casefold():
            continue
        url = (variant.get('product') or {}).get('onlineStoreUrl') or ''
        parsed = urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc != urlsplit(base).netloc or not parsed.path.startswith('/products/'):
            continue
        variant_id = str(variant.get('id', '')).rsplit('/', 1)[-1]
        if variant_id.isdigit():
            matches.add(url + ('&' if parsed.query else '?') + urlencode({'variant': variant_id}))
    return next(iter(matches)) if len(matches) == 1 else ''
