import unittest
from unittest.mock import patch

import collection_note


class CollectionNoteTests(unittest.TestCase):
    def test_company_uses_order_type_and_shopify_order_analysis(self):
        for order_type, analysis, expected in (("Amazon", "Other", "Amazon"), ("Shopify", "Website", "Website"), (" shopify ", "Retail", "Retail"), ("Shopify", "", "")):
            with self.subTest(order_type=order_type, analysis=analysis):
                note = collection_note.order_note("123", [{"Order no": "123", "Order Type": order_type, "Order Analysis": analysis, "Customer": "Previous company"}])
                self.assertEqual(note["fields"]["company"], expected)

    def test_address_uses_dedicated_columns_and_preserves_commas(self):
        from tests_address_fixture import address_row
        row = address_row(**{"AB": "19, The Crescent", "AC": "Weaverham", "AE": "Northwich", "AG": "UK"})
        note = collection_note.order_note("655497", [row])
        self.assertEqual({key: note["fields"][key] for key in ("street1", "street2", "city", "country", "postcode")}, {
            "street1": "19, The Crescent", "street2": "Weaverham",
            "city": "Northwich", "country": "UK", "postcode": "CW8 3LQ",
        })

    def test_combined_address_is_not_used_as_a_fallback(self):
        note = collection_note.order_note("123", [{"Order no": "123", "Address": "19, Road, Town, CW8 3LQ"}])
        self.assertTrue(all(note["fields"][key] == "" for key in ("street1", "street2", "city", "country", "postcode")))

    def test_conflicting_dedicated_address_is_left_blank(self):
        from tests_address_fixture import address_row
        rows = [address_row(AB="First road", AE="Same city"), address_row(AB="Other road", AE="Same city")]
        note = collection_note.order_note("655497", rows)
        self.assertEqual(note["fields"]["street1"], "")
        self.assertEqual(note["fields"]["city"], "Same city")

    def test_street3_uses_its_column_header_only_when_present(self):
        from tests_address_fixture import address_row
        for header in ("Street 3", "street3", "Delivery address 3", "Delivery address line 3"):
            with self.subTest(header=header):
                row = address_row(AB="Road", AC="Area", AD="Building C")
                row = {header if name == "Street 3" else name: value for name, value in row.items()}
                self.assertEqual(collection_note.order_note("655497", [row])["fields"]["street3"], "Building C")
        self.assertEqual(collection_note.order_note("655497", [address_row()])["fields"]["street3"], "")
        self.assertEqual(collection_note.order_note("123", [{"Order no": "123"}])["fields"]["street3"], "")

    def test_street3_conflicts_are_not_guessed(self):
        from tests_address_fixture import address_row
        note = collection_note.order_note("655497", [address_row(AD="Building A"), address_row(AD="Building B")])
        self.assertEqual(note["fields"]["street3"], "")

    def test_new_sales_activity_address_item_name_and_quantity(self):
        note = collection_note.order_note("655497", [
            {"Order no": "655497", "Address": "10 Example Road, Example Town", "Delivery name": "Recipient",
             "Product SKU": "SKU-ONE", "Item Name": "First item", "Item Quantity": "2", "Customer": "B&Q"},
            {"Order no": "655497", "Address": "10 Example Road, Example Town", "Delivery name": "Recipient",
             "Product SKU": "SKU-TWO", "Item Name": "Second item", "Item Quantity": "0", "Customer": "B&Q"},
        ])
        self.assertEqual(note["fields"]["street1"], "")
        self.assertEqual(note["items"], [
            {"sku": "SKU-ONE", "description": "First item", "quantity": "2"},
            {"sku": "SKU-TWO", "description": "Second item", "quantity": "0"},
        ])
        self.assertEqual(note["fields"]["city"], "")

    def test_exact_order_and_editable_fields_exclude_manual_values(self):
        note = collection_note.order_note("654901", [
            {"Order no": "654901", "Delivery name": "Recipient", "Customer": "B&Q",
             "Product SKU": "NS-5176R-SET+", "Delivery postcode": "AB1 2CD",
             "Order Type": "B&Q", "Delivery telephone": "0123456789", "Order reference": "REF-654901", "Order date": "2020-01-01", "QTY": "8"},
            {"Order no": "6549010", "Delivery name": "Wrong recipient"},
        ])
        self.assertTrue(note["found"])
        self.assertEqual(note["fields"]["customer"], "Recipient")
        self.assertEqual(note["fields"]["company"], "B&Q")
        self.assertEqual(note["fields"]["orderRef"], "REF-654901")
        self.assertEqual(note["fields"]["collectionOrder"], "654901")
        self.assertEqual(note["fields"]["street1"], "")
        self.assertEqual(note["items"], [{"sku": "NS-5176R-SET+", "description": ""}])
        self.assertTrue({"date", "returnDate", "availableDate", "quantity", "condition", "return-reason"}.isdisjoint(note["fields"]))

    def test_multiple_product_rows_and_conflicting_customer_data(self):
        note = collection_note.order_note("123", [
            {"Order no": "123", "Delivery name": "A", "Product SKU": "SKU-1", "Product description": "First item"},
            {"Order no": "123", "Delivery name": "B", "Product SKU": "SKU-2;SKU-3"},
            {"Order no": "123", "Product SKU": "SKU-1", "Product description": "First item"},
        ])
        self.assertEqual(note["fields"]["customer"], "")
        self.assertEqual([item["sku"] for item in note["items"]], ["SKU-1", "SKU-2", "SKU-3"])
        self.assertEqual(note["items"][0]["description"], "First item")

    def test_collection_fields_follow_tracking_sheet_links(self):
        original = {"Order no": "123", "Delivery method": "Next Day (Pallet)"}
        replacement = {"Order no": "456", "Original order Number": "123.0", "Order Category": "Order"}
        credit = {"Order no": "789", "Original order Number": "123", "Order Category": "Credit/Refund"}
        for linked, kind, expected in ((replacement, "Replacement", "456"), (credit, "Refund", "")):
            fields = collection_note.order_note("123", [original, linked])["fields"]
            self.assertEqual(fields["deliveryMethod"], "Next Day (Pallet)")
            self.assertEqual(fields["collectionType"], kind)
            self.assertEqual(fields["replacementOrder"], expected)
        fields = collection_note.order_note("456", [original, replacement])["fields"]
        self.assertEqual((fields["collectionType"], fields["replacementOrder"]), ("Replacement", "123"))
        fields = collection_note.order_note("123", [original])["fields"]
        self.assertEqual((fields["collectionType"], fields["replacementOrder"]), ("", ""))
        fields = collection_note.order_note("123", [original, replacement, credit])["fields"]
        self.assertEqual(fields["collectionType"], "")

    def test_collection_links_do_not_guess_conflicting_or_multiple_replacements(self):
        original = {"Order no": "123"}
        child = {"Order no": "456", "Original order Number": "123", "Order Category": "Order"}
        conflicting = {**child, "Original order Number": "999"}
        fields = collection_note.order_note("123", [original, child, conflicting])["fields"]
        self.assertEqual((fields["collectionType"], fields["replacementOrder"]), ("", ""))
        fields = collection_note.order_note("123", [original, child, {**child, "Order no": "789"}])["fields"]
        self.assertEqual((fields["collectionType"], fields["replacementOrder"]), ("Replacement", ""))

    def test_replacement_order_reads_original_order_number_from_selected_row(self):
        row = {"Order no": "456", "Original order Number": "123.0"}
        fields = collection_note.order_note("456", [row])["fields"]
        self.assertEqual(fields["replacementOrder"], "123")
        self.assertEqual(fields["collectionType"], "")
        row = {"Order no": "456", **{f"Column_{i}": "" for i in range(2, 14)}, "Column_14": "123"}
        self.assertEqual(collection_note.order_note("456", [row])["fields"]["replacementOrder"], "123")
        conflict = {**row, "Column_14": "999"}
        self.assertEqual(collection_note.order_note("456", [row, conflict])["fields"]["replacementOrder"], "")

    def test_missing_and_invalid_orders(self):
        self.assertEqual(collection_note.order_note("123", []), {"found": False, "order": "123"})
        for order in ("", "abc", "123/456"):
            with self.assertRaises(ValueError):
                collection_note.order_note(order, [])

    def test_lookup_caches_sheet_and_does_not_hide_read_failures(self):
        with patch.object(collection_note, "_rows", None), patch.object(collection_note, "_read_at", 0), patch(
            "google_sheets.read_sales_activity", return_value=[{"Order no": "123"}]
        ) as read:
            self.assertTrue(collection_note.lookup("123")["found"])
            self.assertFalse(collection_note.lookup("124")["found"])
            self.assertEqual(read.call_count, 1)
        with patch.object(collection_note, "_rows", None), patch("google_sheets.read_sales_activity", side_effect=RuntimeError("offline")):
            with self.assertRaises(RuntimeError):
                collection_note.lookup("123")


if __name__ == "__main__":
    unittest.main()
