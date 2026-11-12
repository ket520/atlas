import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data
from optimoroute_matching import resolve, search


def delivery(order='660755', ref='424099', ecommerce='02-15349-33171', postcode='AB1 2CD'):
    return {'order': order, 'orderRef': ref, 'carrier': 'Own van', 'postcode': postcode,
            'salesActivityDetails': {'eCommerce order number': ecommerce}}


def stop(reference='02-15349-33171', postcode='AB1 2CD', identifier='stop-1'):
    return {'id': identifier, 'data': {'orderNo': reference, 'date': '2026-10-28',
                                     'location': {'address': 'Example Road, ' + postcode}}}


class MatchingTests(unittest.TestCase):
    def test_exact_ecommerce_requires_postcode_and_retains_evidence(self):
        found, warnings = resolve([delivery()], [stop(postcode='AB12CD')])
        self.assertEqual(found['660755'][1:], ('eCommerce order number', '02-15349-33171'))
        self.assertFalse(warnings)

    def test_primary_reference_still_wins(self):
        found, _ = resolve([delivery()], [stop(), stop('424099', identifier='primary')])
        self.assertEqual(found['660755'][0]['id'], 'primary')

    def test_wrong_missing_or_partial_postcode_cannot_attach_photos(self):
        for postcode in ['ZZ1 2CD', '', 'XAB1 2CD9']:
            with self.subTest(postcode=postcode):
                found, _ = resolve([delivery()], [stop(postcode=postcode)])
                self.assertFalse(found)
        self.assertFalse(resolve([delivery(postcode='')], [stop()])[0])

    def test_shared_ecommerce_and_cross_field_collisions_are_blocked(self):
        for other in [delivery('other'), delivery('other', ref='02-15349-33171', ecommerce='different')]:
            self.assertFalse(resolve([delivery(), other], [stop()])[0])

    def test_duplicate_provider_reference_blocks_fallback(self):
        self.assertFalse(resolve([delivery()], [stop(), stop(identifier='second')])[0])
        found, warnings = resolve([delivery()], [stop('424099'), stop('424099', identifier='second'), stop()])
        self.assertFalse(found)
        self.assertIn('660755', warnings)

    def test_address_alone_and_incomplete_results_never_match(self):
        self.assertFalse(resolve([delivery()], [stop('unrelated')])[0])
        self.assertFalse(resolve([delivery()], [stop()], complete=False)[0])

    def test_conflicting_product_row_identifiers_are_not_chosen(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(delivery_data, 'configured_db_path', return_value=Path(folder) / 'test.sqlite3'):
            row = {'Order no': '660755', 'Delivery method': 'Own van',
                   'eCommerce order number': '02-15349-33171'}
            delivery_data.archive([row, {**row, 'eCommerce order number': 'different'}])
            self.assertEqual(delivery_data.snapshot()[0]['salesActivityDetails']['eCommerce order number'], '')

    def test_credit_records_do_not_receive_delivery_documents(self):
        record = delivery()
        record['salesActivityDetails']['Order Category'] = 'Credit/Refund'
        self.assertFalse(resolve([record], [stop()])[0])

    def test_exact_search_reads_all_pages(self):
        calls = []
        def api(method, body):
            calls.append(dict(body))
            return {'orders': [stop()], 'after_tag': 'next'} if len(calls) == 1 else {'orders': []}
        orders, complete = search([delivery()], api)
        self.assertTrue(complete)
        self.assertEqual(len(orders), 1)
        self.assertEqual(calls[1]['after_tag'], 'next')

    def test_fallback_works_for_detail_page_and_today_without_changing_ow_reference(self):
        row = {'Order no': '660755', 'Order reference': '424099', 'Delivery method': 'Own van',
               'eCommerce order number': '02-15349-33171', 'Delivery postcode': 'AB1 2CD'}
        def api(method, body):
            if method == 'search_orders':
                return {'orders': [stop()]}
            return {'orders': [{'id': 'stop-1', 'data': {'status': 'success', 'form': {
                'images': [{'url': 'https://example.com/photo.jpg'}],
                'signature': {'url': 'https://example.com/signature.png'}}}}]}
        for mode in ['detail', 'page', 'today']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as folder, \
                 patch.object(delivery_data, 'configured_db_path', return_value=Path(folder) / 'test.sqlite3'), \
                 patch('server.api', side_effect=api), patch('activity_log.archive_records'), \
                 patch('activity_log.history', return_value={'entries': []}):
                delivery_data.archive([row])
                if mode == 'detail':
                    result = delivery_data.detail('660755')
                elif mode == 'page':
                    result = delivery_data.query_records(refresh_provider=True)['deliveries'][0]
                else:
                    self.assertEqual(delivery_data.enrich_optimoroute_today(), 1)
                    result = delivery_data.snapshot()[0]
                self.assertEqual(result['orderRef'], '424099')
                self.assertEqual(result['providerMatchField'], 'eCommerce order number')
                self.assertEqual(len(result['podPhotos']), 2)
                delivery_data.archive([row])
                self.assertEqual(delivery_data.snapshot()[0]['providerMatchValue'], '02-15349-33171')


if __name__ == '__main__':
    unittest.main()
