import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import delivery_data
from claim_order_lookup import order_fields


class ClaimOrderLookupTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(delivery_data, 'configured_db_path', return_value=Path(directory.name) / 'test.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)

    def row(self, order, original='', sku='PRODUCT-SKU', **extra):
        row = {'Order no': order, 'Original order Number': original, 'Order Category': 'Order',
                'Delivery method': 'Palletways', 'Product SKU': sku, 'Parent SKU': 'WRONG-PARENT-SKU', **extra}
        while len(row) < 33:
            row[f'Column_{len(row)}'] = ''
        row['Store code'] = 'B&Q'
        return row

    def test_original_and_replacement_resolve_both_directions_with_product_sku(self):
        delivery_data.archive([self.row('100'), self.row('200', '100', 'REPLACEMENT-SKU')])
        for order in ('100', '200'):
            result = order_fields(order)
            self.assertEqual(result['originalOrderNo'], '100')
            self.assertEqual(result['replacementOrderNo'], '200')
            self.assertEqual(result['variantCodes'], ['PRODUCT-SKU'])
            self.assertEqual(result['sellingShop'], 'B&Q')

    def test_multiple_replacements_are_choices_and_product_rows_combine(self):
        delivery_data.archive([self.row('100', sku='A'), self.row('100', sku='B'),
                               self.row('200', '100'), self.row('300', '100'),
                               self.row('400', '100', **{'Order Category': 'Credit/Refund'})])
        result = order_fields('100')
        self.assertEqual(result['replacementOrderNo'], '')
        self.assertEqual(result['replacementOptions'], ['200', '300'])
        self.assertEqual(result['variantCodes'], ['A', 'B'])

    def test_missing_product_sku_does_not_substitute_parent_sku(self):
        delivery_data.archive([self.row('100', sku='')])
        self.assertEqual(order_fields('100')['variantCodes'], [])
        self.assertFalse(order_fields('999')['found'])

    def test_missing_parent_uses_explicit_link_without_guessing_its_sku(self):
        delivery_data.archive([self.row('200', '100')])
        result = order_fields('200')
        self.assertEqual(result['originalOrderNo'], '100')
        self.assertEqual(result['replacementOrderNo'], '200')
        self.assertEqual(result['variantCodes'], [])
        self.assertTrue(result['originalUnavailable'])

    def test_descendant_replacements_do_not_change_direct_claim_lookup(self):
        delivery_data.archive([self.row('100'), self.row('200', '100'), self.row('300', '200')])
        result = order_fields('100')
        self.assertEqual(result['replacementOptions'], ['200'])
        self.assertEqual(result['replacementOrderNo'], '200')
        result = order_fields('300')
        self.assertEqual(result['originalOrderNo'], '200')
        self.assertEqual(result['replacementOrderNo'], '300')
