import io
import json
import unittest
from unittest.mock import patch

import shopify_products


class ShopifyProductTests(unittest.TestCase):
    def response(self, nodes):
        return io.BytesIO(json.dumps({'data': {'productVariants': {
            'nodes': nodes, 'pageInfo': {'hasNextPage': False},
        }}}).encode())

    def test_exact_sku_returns_real_product_url_and_variant(self):
        settings = {'SHOPIFY_BATHROOM_REPUBLIC_DOMAIN': 'example.myshopify.com',
                    'SHOPIFY_BATHROOM_REPUBLIC_TOKEN': 'test', 'SHOPIFY_BATHROOM_REPUBLIC_API_VERSION': '2026-07'}
        nodes = [{'id': 'gid://shopify/ProductVariant/123', 'sku': 'SKU+A',
                  'product': {'onlineStoreUrl': 'https://bathroomrepublic.co.uk/products/item'}}]
        with patch.object(shopify_products, 'setting', side_effect=lambda key, default='': settings.get(key, default)), patch.object(
            shopify_products, 'urlopen', return_value=self.response(nodes)
        ) as fetch:
            result = shopify_products.configured_product_url('SKU+A', 'https://bathroomrepublic.co.uk')
        self.assertEqual(result, 'https://bathroomrepublic.co.uk/products/item?variant=123')
        self.assertEqual(json.loads(fetch.call_args.args[0].data)['variables']['query'], 'sku:"SKU+A"')

    def test_other_store_url_is_not_used(self):
        nodes = [{'id': 'gid://shopify/ProductVariant/123', 'sku': 'SKU',
                  'product': {'onlineStoreUrl': 'https://bathroomrepublic.co.uk/products/item'}}]
        with patch.object(shopify_products, 'setting', side_effect=lambda key, default='': {
            'SHOPIFY_BATHROOM_REPUBLIC_DOMAIN': 'example.myshopify.com', 'SHOPIFY_BATHROOM_REPUBLIC_TOKEN': 'test',
        }.get(key, default)), patch.object(shopify_products, 'urlopen', return_value=self.response(nodes)):
            self.assertEqual(shopify_products.configured_product_url('SKU', 'https://www.diy.com'), '')
