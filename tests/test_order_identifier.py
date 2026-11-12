import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data
from order_identifier import lookup


class OrderIdentifierTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(delivery_data, 'configured_db_path', return_value=Path(directory.name) / 'test.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.add('123456', '12345678901', '987654')

    def add(self, order, tracking, consignment):
        payload = {'order': order, 'carrier': 'Palletways', 'storeCode': 'B&Q',
                   'palletwaysSheetTrackingNumber': tracking,
                   'palletwaysSheetConsignmentNumber': consignment,
                   'trk': '99999999999'}
        with delivery_data.connect() as db:
            db.execute('INSERT INTO deliveries VALUES (?,?,?,?)', (order, json.dumps(payload), '', ''))
            db.commit()

    def test_all_three_identifiers_return_same_sheet_mapping(self):
        expected = {'found': True, 'order': '123456', 'store': 'B&Q', 'courier': 'Palletways',
                    'trackingId': '12345678901', 'consignmentNumber': '987654'}
        for identifier in ('123456', '12345678901', '987654'):
            self.assertEqual(lookup(identifier), expected)
        self.assertFalse(lookup('99999999999')['found'])
        self.assertFalse(lookup('12345')['found'])

    def test_duplicate_and_cross_field_matches_are_ambiguous(self):
        self.add('987654', '12345678901', '111111')
        for identifier in ('12345678901', '987654'):
            result = lookup(identifier)
            self.assertFalse(result['found'])
            self.assertTrue(result['ambiguous'])

    def test_missing_fields_and_invalid_input(self):
        self.add('222222', '', '')
        self.assertEqual(lookup('222222')['trackingId'], '')
        for value in ('', 'abc', '123 OR 1=1', '1' * 65):
            with self.assertRaises(ValueError):
                lookup(value)

    def test_hyphenated_palletways_consignment_number(self):
        self.add('333333', '33333333333', '7590123-41')
        result = lookup('7590123-41')
        self.assertTrue(result['found'])
        self.assertEqual(result['order'], '333333')
        self.assertEqual(result['consignmentNumber'], '7590123-41')

    def add_carrier(self, order, carrier, **fields):
        with delivery_data.connect() as db:
            db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',
                       (order, json.dumps({'carrier': carrier, 'storeCode': 'AMAZON', **fields}), '', ''))
            db.commit()

    def test_amazon_uses_tracking_table_field_in_both_directions(self):
        self.add_carrier('444444', 'AMZ', owTrackingNo='UK4818227623', trk='UK9999999999', amazonTrackingId='UK8888888888')
        expected = {'found': True, 'order': '444444', 'store': 'Amazon', 'courier': 'AMZ', 'trackingId': 'UK4818227623'}
        for value in ('444444', 'UK4818227623', 'uk4818227623'):
            self.assertEqual(lookup(value), expected)
        for value in ('UK481822', 'UK9999999999', 'UK8888888888'):
            self.assertFalse(lookup(value)['found'])

    def test_each_xdp_consignment_resolves_same_order(self):
        numbers = 'ZDBJSD019771\nZDBJSD019745'
        self.add_carrier('555555', 'XDP', xdpConsignmentNo=numbers, owTrackingNo='OTHER123')
        for value in ('555555', 'ZDBJSD019771', 'ZDBJSD019745', 'zdbjsd019745'):
            result = lookup(value)
            self.assertEqual(result['order'], '555555')
            self.assertEqual(result['consignmentNumber'], numbers)
        for value in ('ZDBJSD0197', 'OTHER123'):
            self.assertFalse(lookup(value)['found'])

    def test_cross_carrier_duplicate_is_ambiguous(self):
        self.add_carrier('444444', 'AMZ', owTrackingNo='UK4818227623')
        self.add_carrier('555555', 'XDP', xdpConsignmentNo='UK4818227623')
        self.assertTrue(lookup('UK4818227623')['ambiguous'])
