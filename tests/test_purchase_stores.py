"""AH store identity and server paging must agree with the displayed store."""
import tempfile
import unittest
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.request import urlopen

import delivery_data
import server
from google_sheets import worksheet_to_records
from sales_activity import store_name


class PurchaseStoreTests(unittest.TestCase):
    def test_company_switches_hide_store_even_with_different_carrier(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'stores.sqlite3'):
            with delivery_data.connect() as db:
                for order, code, order_type in [('1', 'WILKO', 'eBay'), ('2', 'WAYFAIR', 'eBay'),
                    ('3', 'AMAZON', 'Sales'), ('4', '', 'HR_Replacement'), ('5', 'AMAZON', 'Amazon')]:
                    delivery = {'id': order, 'order': order, 'carrier': 'AMZ', 'st': 'Scheduled',
                                'storeCode': code, 'salesActivityDetails': {'Order Type': order_type}}
                    db.execute('INSERT INTO deliveries VALUES (?, ?, ?, ?)',
                               (order, json.dumps(delivery), '2026-10-22', '2026-10-22'))
                db.commit()
            result = delivery_data.query_records(hide_wilko=True, hide_wayfair=True, hide_hygienic=True)
            self.assertEqual([row['order'] for row in result['deliveries']], ['5'])

    def test_willesden_filter_uses_ah_even_when_saved_store_label_is_empty(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'stores.sqlite3'):
            delivery = {'id': '648326', 'order': '648326', 'carrier': 'AMZ', 'st': 'Scheduled',
                        'storeCode': 'EBAY_WB', 'purchaseStore': '',
                        'salesActivityDetails': {'Order Type': 'eBay', 'Order Analysis': 'N/A'}}
            with delivery_data.connect() as db:
                db.execute('INSERT INTO deliveries VALUES (?, ?, ?, ?)',
                           ('648326', json.dumps(delivery), '2026-10-22', '2026-10-22'))
                db.commit()
            result = delivery_data.query_records(store='EBay Willesden Bathroom')
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['deliveries'][0]['order'], '648326')
            self.assertEqual(delivery_data.summary()['filterFacets'][0]['purchaseStore'], 'EBay Willesden Bathroom')

    def test_saved_orders_keep_icons_until_ah_is_imported(self):
        cases = [
            ('Amazon', '', 'Amazon'), ('B&Q', '', 'B&Q'),
            ('Debenhams', 'Debenhams - Neshome', 'Debenhams - Neshome'),
            ('Shopify', 'Shopify - Neshome', 'Shopify - Neshome'),
            ('Ebay', 'ebay0', 'Ebay Bathroom Republic'),
            ('Ebay', 'ebay1', 'EBay Willesden Bathroom'),
        ]
        for order_type, analysis, expected in cases:
            delivery = {'salesActivityDetails': {'Order Type': order_type, 'Order Analysis': analysis}}
            self.assertEqual(delivery_data.purchase_store(delivery), expected)
            self.assertEqual(delivery_data.purchase_store({**delivery, 'storeCode': 'WAYFAIR'}), 'Wayfair')
            self.assertEqual(delivery_data.purchase_store({**delivery, 'storeCode': ''}), '')

    def test_http_forwards_store_and_visibility_filters(self):
        with patch.object(delivery_data, 'cached_or_schedule_sync', return_value={}), patch.object(
            delivery_data, 'query_records', return_value={'deliveries': [], 'total': 0}
        ) as query:
            http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
            thread = threading.Thread(target=http.serve_forever, daemon=True)
            thread.start()
            try:
                with urlopen(f'http://127.0.0.1:{http.server_port}/api/deliveries?store=Wilko&hide_wilko=1&hide_palletways_b2b=1') as response:
                    self.assertEqual(json.load(response)['total'], 0)
                self.assertEqual(query.call_args.kwargs['store'], ['Wilko'])
                self.assertTrue(query.call_args.kwargs['hide_wilko'])
                self.assertTrue(query.call_args.kwargs['hide_palletways_b2b'])
                with urlopen(f'http://127.0.0.1:{http.server_port}/api/deliveries?store=Amazon&store=Wilko&status=Scheduled&status=Delivered') as response:
                    self.assertEqual(json.load(response)['total'], 0)
                self.assertEqual(query.call_args.kwargs['store'], ['Amazon', 'Wilko'])
                self.assertEqual(query.call_args.kwargs['status'], ['Scheduled', 'Delivered'])
            finally:
                http.shutdown()
                http.server_close()
                thread.join()

    def test_codes_and_hygienic_priority(self):
        expected = {
            'AMAZON': 'Amazon', 'DEBENHAM': 'Debenhams - Neshome', 'B&Q': 'B&Q',
            'EBAY_BR': 'Ebay Bathroom Republic', 'EBAY_WB': 'EBay Willesden Bathroom', 'SHOPIFY': 'Shopify - Neshome',
            'BATHPROF': 'Bathroom Republic - Website', 'BATHREP': 'Bathroom Republic - Website',
            'BATHROOM': 'Bathroom Republic - Website', 'WILKO': 'Wilko', 'WAYFAIR': 'Wayfair',
        }
        for code, name in expected.items():
            self.assertEqual(store_name(' ' + code.lower() + ' ', 'Amazon'), name)
        self.assertEqual(store_name('EBAY_BR', '', 'ebay1'), 'Ebay Bathroom Republic')
        self.assertEqual(store_name('EBAY_WB', '', 'ebay0'), 'EBay Willesden Bathroom')
        for order_type in ['Sales', 'HR_Replacement']:
            self.assertEqual(store_name('WAYFAIR', order_type), 'Hygienic Cleaning Company (UK) LTD')
        self.assertEqual(store_name('', 'Amazon'), '')
        self.assertEqual(store_name('UNKNOWN', 'Shopify', 'Old store'), '')

    def test_ah_position_and_server_filter_before_paging(self):
        headers = ['Order no', 'Delivery method', 'Status', 'Order Type', 'Order Analysis']
        headers += ['Unused_' + str(i) for i in range(28)] + ['New channel header']
        values = []
        for index, code in enumerate(['AMAZON', 'WILKO', 'AMAZON', 'BATHREP', 'WAYFAIR'], 1):
            values.append([str(index), 'XDP', 'P', 'Old type', ''] + [''] * 28 + [code])
        sheet = Mock()
        sheet.get_all_values.return_value = [headers, *values]
        rows = worksheet_to_records(sheet)
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'stores.sqlite3'):
            delivery_data.archive(rows)
            first = delivery_data.query_records(store='Amazon', limit=1)
            second = delivery_data.query_records(store='Amazon', limit=1, offset=1)
            self.assertEqual(first['total'], 2)
            self.assertTrue(first['hasMore'])
            self.assertNotEqual(first['deliveries'][0]['id'], second['deliveries'][0]['id'])
            self.assertEqual(first['deliveries'][0]['storeCode'], 'AMAZON')
            self.assertEqual(delivery_data.query_records(store='Wilko')['total'], 1)
            self.assertEqual(delivery_data.query_records(hide_wilko=True)['total'], 4)
            facets = delivery_data.summary()['filterFacets']
            self.assertEqual(sum(item['count'] for item in facets if item['purchaseStore'] == 'Amazon'), 2)


if __name__ == '__main__':
    unittest.main()
