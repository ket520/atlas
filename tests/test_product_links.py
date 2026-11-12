import json
import unittest
from unittest.mock import patch

import product_links


class ProductLinksTests(unittest.TestCase):
    def test_marketplace_links_use_only_explicit_valid_identifiers(self):
        self.assertEqual(product_links.resolve_product('Amazon', 'SKU', 'B012345678'),
                         'https://www.amazon.co.uk/gp/product/B012345678')
        self.assertEqual(product_links.resolve_product('Ebay Bathroom Republic', 'SKU', '123456789012'),
                         'https://www.ebay.co.uk/itm/123456789012?ViewItem=&item=123456789012')
        with self.assertRaises(product_links.ProductLookupError):
            product_links.resolve_product('Amazon', 'B012345678')
        with self.assertRaises(product_links.ProductLookupError):
            product_links.resolve_product('Ebay Bathroom Republic', 'SKU', 'https://other.test')

    def test_missing_or_unavailable_product_has_no_link(self):
        self.assertIsNone(product_links.verified_product_url('Amazon', 'SKU+A'))
        with patch.object(product_links, 'read_url', side_effect=OSError('Unavailable')):
            self.assertIsNone(product_links.verified_product_url('Amazon', 'SKU', 'B012345678'))

    def test_marketplace_page_must_confirm_product_identity(self):
        with patch.object(product_links, 'read_url', return_value='<p>Search results B012345678</p>'):
            self.assertIsNone(product_links.verified_product_url('Amazon', 'SKU', 'B012345678'))
        content = '<link rel="canonical" href="https://www.ebay.co.uk/itm/123456789012">'
        with patch.object(product_links, 'read_url', return_value=content):
            self.assertIsNotNone(product_links.verified_product_url('Ebay Bathroom Republic', 'SKU', '123456789012'))
    def setUp(self):
        product_links.resolve_product.cache_clear()

    def test_shopify_verifies_exact_sku_and_opens_variant(self):
        suggestions = {"resources": {"results": {"products": [{"handle": "cabinet"}]}}}
        product = {"variants": [{"sku": "PS320-SG", "id": 123}]}
        with patch.object(product_links, "read_url", side_effect=[json.dumps(suggestions), json.dumps(product)]):
            url = product_links.resolve_product("Shopify - Neshome", "PS320-SG")
        self.assertEqual(url, "https://neshome.co.uk/products/cabinet?variant=123")

    def test_partial_sku_is_not_a_match(self):
        suggestions = {"resources": {"results": {"products": [{"handle": "cabinet"}]}}}
        product = {"variants": [{"sku": "PS320-SG-OTHER", "id": 123}]}
        with patch.object(product_links, "read_url", side_effect=[json.dumps(suggestions), json.dumps(product)]):
            with self.assertRaises(product_links.ProductLookupError):
                product_links.resolve_product("Shopify - Neshome", "PS320-SG")

    def test_bq_verifies_product_schema(self):
        search = '<a href="/departments/shower/123.prd">Shower</a><a href="https://other.test/departments/1.prd">Other</a>'
        product = '<script type="application/ld+json">{"@type":"Product","mpn":"TSVW11+A101"}</script>'
        with patch.object(product_links, "read_url", side_effect=[search, product]) as read:
            url = product_links.resolve_product("B&Q", "TSVW11+A101")
        self.assertEqual(url, "https://www.diy.com/departments/shower/123.prd")
        self.assertEqual(read.call_count, 2)

    def test_ambiguous_variants_do_not_redirect(self):
        suggestions = {"resources": {"results": {"products": [{"handle": "cabinet"}]}}}
        product = {"variants": [{"sku": "SKU", "id": 1}, {"sku": "SKU", "id": 2}]}
        with patch.object(product_links, "read_url", side_effect=[json.dumps(suggestions), json.dumps(product)]):
            with self.assertRaises(product_links.ProductLookupError):
                product_links.resolve_product("Shopify - Neshome", "SKU")

    def test_error_page_escapes_sku_without_search_links(self):
        page = product_links.lookup_page("B&Q", '<SKU>+A', "Unavailable").decode()
        self.assertIn("&lt;SKU&gt;+A", page)
        self.assertNotIn('<a ', page)

    def test_unsupported_store_never_connects(self):
        with patch.object(product_links, "read_url") as read:
            with self.assertRaises(ValueError):
                product_links.resolve_product("Unknown", "SKU")
            read.assert_not_called()
