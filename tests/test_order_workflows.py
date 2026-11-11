import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import delivery_data


class OrderWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.db = patch.object(delivery_data, 'DB_PATH', Path(self.directory.name) / 'test.sqlite3')
        self.db.start()
        self.addCleanup(self.db.stop)
        delivery_data.archive([
            {'Order no': '100', 'Delivery method': 'XDP'},
            {'Order no': '101', 'Delivery method': 'XDP', 'Order Category': 'Order', 'Original order Number': '100'},
            {'Order no': '102', 'Delivery method': 'Palletways', 'Order Category': 'Order', 'Original order Number': '101'},
            {'Order no': '103', 'Delivery method': '', 'Order Category': 'Credit/Refund', 'Original order Number': '100', 'Order reference': 'CREDIT-REF'},
            {'Order no': '104', 'Delivery method': 'XDP', 'Order Category': 'Credit/Refund', 'Original order Number': '100'},
            {'Order no': '105', 'Delivery method': 'XDP', 'Order Category': 'Order', 'Original order Number': '100'},
            {'Order no': '105', 'Delivery method': 'XDP', 'Order Category': 'Order', 'Original order Number': '999'},
        ])

    def test_only_verified_replacements_including_later_generations(self):
        result = delivery_data.query_records(order_kind='replacement')
        self.assertEqual({row['order'] for row in result['deliveries']}, {'101', '102'})
        self.assertEqual(sum(row['count'] for row in result['filterFacets']), 2)
        self.assertEqual(delivery_data.query_records(order_kind='replacement', carrier='XDP')['total'], 1)

    def test_refunds_include_non_delivery_records_without_duplicates(self):
        result = delivery_data.query_records(order_kind='refund')
        self.assertEqual({row['order'] for row in result['deliveries']}, {'103', '104'})
        self.assertEqual(sum(row['count'] for row in result['filterFacets']), 2)
        record = next(row for row in result['deliveries'] if row['order'] == '103')
        self.assertFalse(record['canOpenDetails'])
        result = delivery_data.query_records(order_kind='refund', search='CREDIT-REF')
        self.assertEqual([row['order'] for row in result['deliveries']], ['103'])

    def test_paging_and_filters_apply_to_entire_workflow(self):
        pages = [delivery_data.query_records(order_kind='refund', limit=1, offset=offset) for offset in (0, 1)]
        self.assertEqual([page['total'] for page in pages], [2, 2])
        self.assertEqual([page['hasMore'] for page in pages], [True, False])
        self.assertNotEqual(pages[0]['deliveries'][0]['order'], pages[1]['deliveries'][0]['order'])
        self.assertEqual(delivery_data.query_records(order_kind='refund', carrier='XDP')['total'], 1)
        self.assertEqual(delivery_data.query_records(order_kind='refund', search='101')['total'], 0)

    def test_refund_filters_use_credit_status_instead_of_delivery_status(self):
        import json
        delivery_data.archive([
            {'Order no': '200', 'Delivery method': 'Self Delivery', 'Order Category': 'Credit/Refund', 'Original order Number': '100', 'Status': 'C'},
            {'Order no': '201', 'Delivery method': 'Self Delivery', 'Order Category': 'Credit/Refund', 'Original order Number': '100', 'Status': 'X'},
        ])
        with delivery_data.connect() as db:
            for order, stale_status in [('200', 'Cancelled'), ('201', 'Delivered')]:
                row = db.execute('SELECT payload FROM deliveries WHERE order_id=?', (order,)).fetchone()
                record = json.loads(row['payload'])
                record.update(st=stale_status, statusSource='OptimoRoute')
                db.execute('UPDATE deliveries SET payload=? WHERE order_id=?', (json.dumps(record), order))
            db.commit()
        with patch.object(delivery_data, 'enrich_optimoroute_page') as enrich:
            complete = delivery_data.query_records(order_kind='refund', status='refund:complete', refresh_provider=True)
            enrich.assert_not_called()
        self.assertEqual([row['order'] for row in complete['deliveries']], ['200'])
        self.assertEqual((complete['deliveries'][0]['st'], complete['deliveries'][0]['statusSource']), ('Delivered', 'OW'))
        cancelled = delivery_data.query_records(order_kind='refund', status='refund:cancelled')
        self.assertEqual([row['order'] for row in cancelled['deliveries']], ['201'])
        self.assertEqual(cancelled['deliveries'][0]['st'], 'Cancelled')
        self.assertTrue(all('rawStatus' in facet for facet in complete['filterFacets']))

    def test_exact_order_hides_unrelated_reference_matches_before_paging(self):
        delivery_data.archive([
            {'Order no': '662101', 'Delivery method': 'XDP'},
            {'Order no': '645854', 'Delivery method': 'XDP', 'Order reference': '202-6621010-2327552'},
        ])
        result = delivery_data.query_records(search='662101', limit=1)
        self.assertEqual(result['total'], 1)
        self.assertEqual([row['order'] for row in result['deliveries']], ['662101'])
        self.assertFalse(result['hasMore'])
        self.assertEqual(delivery_data.query_records(search='662101', offset=1)['deliveries'], [])
        partial = delivery_data.query_records(search='66210')
        self.assertEqual({row['order'] for row in partial['deliveries']}, {'662101', '645854'})

    def test_exact_search_keeps_linked_replacement_and_credit_lookup(self):
        from tracking_relations import lookup
        exact = delivery_data.query_records(search='100')
        self.assertEqual([row['order'] for row in exact['deliveries']], ['100'])
        related = lookup('100')['related']
        self.assertTrue(any(row['order'] == '101' and row['relatedKind'] == 'Replacement' for row in related))
        self.assertTrue(any(row['order'] == '103' and row['relatedKind'] == 'Credit/Refund' for row in related))

    def test_tracking_excludes_credits_even_with_a_delivery_method(self):
        result = delivery_data.query_records(exclude_refunds=True)
        self.assertNotIn('104', {row['order'] for row in result['deliveries']})
        self.assertIn('101', {row['order'] for row in result['deliveries']})
        self.assertEqual(delivery_data.query_records(search='104', exclude_refunds=True)['total'], 0)
        # Global search must still find credits so it can route to Refund.
        self.assertEqual(delivery_data.query_records(search='104')['total'], 1)

    def test_refund_original_order_search_returns_only_its_credits(self):
        result = delivery_data.query_records(order_kind='refund', search='100')
        self.assertEqual({row['order'] for row in result['deliveries']}, {'103', '104'})
        self.assertEqual(result['total'], 2)
        self.assertEqual(delivery_data.query_records(order_kind='refund', search='100', carrier='XDP')['total'], 1)
        page = delivery_data.query_records(order_kind='refund', search='100', limit=1)
        self.assertTrue(page['hasMore'])
        exact = delivery_data.query_records(order_kind='refund', search='104')
        self.assertEqual([row['order'] for row in exact['deliveries']], ['104'])

    def test_tracking_relations_remove_credit_rows_and_flow_nodes(self):
        from tracking_relations import lookup, without_credit_refunds
        related = without_credit_refunds(lookup('100'))
        self.assertTrue(any(row['order'] == '101' for row in related['related']))
        self.assertFalse(any(row['relatedKind'] == 'Credit/Refund' for row in related['related']))
        self.assertFalse(any(node['id'] in {'103', '104'} for node in related['flow']['nodes']))
        self.assertFalse(any(edge['kind'] == 'Credit/Refund' for edge in related['flow']['edges']))
        self.assertIsNone(without_credit_refunds(lookup('104')))
        self.assertIsNone(without_credit_refunds(lookup('103')))

    def test_refund_view_includes_original_and_complete_flow(self):
        from tracking_relations import lookup, refund_order_relations
        result = refund_order_relations(lookup('104'))
        self.assertEqual(result['original']['order'], '104')
        self.assertTrue(any(row['order'] == '100' and row['relatedKind'] == 'Original' for row in result['related']))
        self.assertTrue(any(edge['from'] == '100' and edge['to'] == '104' for edge in result['flow']['edges']))
        by_original = refund_order_relations(lookup('100'))
        self.assertEqual({row['order'] for row in by_original['related']}, {'103', '104'})
        self.assertTrue(by_original['flow']['nodes'])
        self.assertIsNone(refund_order_relations(None))
