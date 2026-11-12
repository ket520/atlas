from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import collection_note
import delivery_data
from google_sheets import worksheet_to_records


HEADERS = ["Order no", "Order date", "Delivery name", "eCommerce order number", "Order reference", "Product SKU",
           "Item Name", "Item Quantity", "Special instructions", "Status", "Order Type", "Order Analysis", "Replacement",
           "Original order Number", "Original order ID", "Address", "Delivery postcode", "Gross (base)", "Tracking No",
           "Delivery method", "Customer", "Delivery telephone", "Delivery email", "Despatch Date", "EbayUserID", "Order Type ID", "Delivery cost"]


class SalesActivityMappingTests(unittest.TestCase):
    def setUp(self):
        source = patch.object(delivery_data, 'configured_delivery_source', return_value='google_sheets')
        source.start()
        self.addCleanup(source.stop)

    def test_marketplace_product_ids_stay_attached_to_single_sku(self):
        from sales_activity import product_items
        row = {'Product SKU': 'SKU', 'Item Quantity': '2', 'ASIN': 'B012345678',
               'eBay Item ID': '123456789012', 'EbayUserID': 'buyer-account'}
        item = product_items([row])[0]
        self.assertEqual(item['asin'], 'B012345678')
        self.assertEqual(item['ebayItemId'], '123456789012')
        row['Product SKU'] = 'SKU,OTHER'
        self.assertTrue(all('asin' not in item and 'ebayItemId' not in item for item in product_items([row])))
        self.assertNotIn('ebayItemId', product_items([{'Product SKU': 'SKU', 'EbayUserID': 'buyer-account'}])[0])

    def rows(self, headers=HEADERS):
        base = {"Order no": "655497", "Order date": "14/10/2026", "Delivery name": "Recipient", "eCommerce order number": "EC-123",
                "Order reference": "REF-123", "Product SKU": "SKU-ONE", "Item Name": "First item", "Item Quantity": "2",
                "Special instructions": "Ring bell", "Status": "P", "Order Type": "B&Q", "Address": "10 Example Road, Example Town",
                "Delivery postcode": "AB1 2CD", "Tracking No": "TRACK-123", "Delivery method": "XDP", "Customer": "B&Q",
                "Delivery telephone": "0123456789", "Delivery email": "test@example.test", "Despatch Date": "15/10/2026"}
        second = {**base, "Product SKU": "SKU-TWO", "Item Name": "Second item", "Item Quantity": "3"}
        worksheet = Mock()
        worksheet.get_all_values.return_value = [headers, *[[row.get(header, "") for header in headers] for row in (base, second)]]
        return worksheet_to_records(worksheet)

    def test_inserted_or_reordered_columns_do_not_shift_order_or_carrier_fields(self):
        for headers in (HEADERS, list(reversed(HEADERS))):
            delivery = delivery_data.row_to_delivery(self.rows(headers)[0])
            self.assertEqual(delivery["orderRef"], "REF-123")
            self.assertEqual(delivery["trk"], "TRACK-123")
            self.assertEqual(delivery["carrier"], "XDP")
            self.assertEqual(delivery["postcode"], "AB1 2CD")
            self.assertEqual(delivery["phone"], "0123456789")
            self.assertEqual(delivery["dispatchDate"], "2026-10-15")
            self.assertEqual(delivery["salesActivityDetails"]["eCommerce order number"], "EC-123")

    def test_tracking_retains_all_product_rows_under_one_order(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / "test.sqlite3"):
            self.assertEqual(delivery_data.archive(self.rows()), 2)
            deliveries = delivery_data.snapshot()
            self.assertEqual(len(deliveries), 1)
            self.assertEqual(deliveries[0]["skuItems"], "SKU-ONE, SKU-TWO")
            self.assertEqual(deliveries[0]["items"], [
                {"sku": "SKU-ONE", "description": "First item", "quantity": "2"},
                {"sku": "SKU-TWO", "description": "Second item", "quantity": "3"},
            ])
            self.assertEqual(deliveries[0]["addr"], "10 Example Road, Example Town, AB1 2CD")

    def test_collection_note_does_not_split_the_old_27_column_address(self):
        note = collection_note.order_note("655497", self.rows())
        self.assertEqual(note["fields"]["street1"], "")
        self.assertEqual(note["fields"]["company"], "B&Q")
        self.assertEqual([item["quantity"] for item in note["items"]], ["2", "3"])
        self.assertEqual([item["description"] for item in note["items"]], ["First item", "Second item"])

    def test_address_does_not_repeat_its_postcode(self):
        row = self.rows()[0]
        row["Address"] = "10 Example Road, AB12CD"
        self.assertEqual(delivery_data.row_to_delivery(row)["addr"], row["Address"])
