import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

import delivery_data
import server
from tracking_relations import lookup


def source(order, original='', category='Order', method='Palletways', sku='SKU-1'):
    return {'Order no': order, 'Original order Number': original, 'Order Category': category,
            'Delivery method': method, 'Status': 'W', 'Delivery name': 'Test customer',
            'Product SKU': sku, 'Order date': '29/10/2026', 'Gross (base)': '25.00'}


class TrackingRelationsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(delivery_data, 'configured_db_path', return_value=Path(directory.name) / 'test.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_exact_original_order_links_replacement_and_credit_without_carrier(self):
        delivery_data.archive([source('663132'), source('700001', '663132'),
                               source('700002', '663132', 'Credit/Refund', ''),
                               source('700003', '66313'), source('700004', '663132', 'Unknown')])
        result = lookup('663132')
        self.assertEqual(result['original']['order'], '663132')
        self.assertEqual([(item['order'], item['relatedKind']) for item in result['related']],
                         [('700001', 'Replacement'), ('700002', 'Credit/Refund')])
        self.assertTrue(result['related'][0]['canOpenDetails'])
        credit = result['related'][1]
        self.assertFalse(credit['canOpenDetails'])
        self.assertEqual(credit['carrier'], '')
        self.assertEqual(credit['st'], '')
        self.assertEqual(credit['grossAmount'], '25.00')
        self.assertEqual(delivery_data.query_records(search='663132')['total'], 1)
        self.assertEqual(lookup('663')['related'], [])
        self.assertIsNone(lookup('Test customer'))

    def test_product_rows_combine_and_ambiguous_links_are_not_guessed(self):
        delivery_data.archive([source('1'), source('2', '1', sku='A'), source('2', '1', sku='B'),
                               source('3', '1'), source('3', '9'),
                               source('4', '1', 'Order'), source('4', '1', 'Credit/Refund')])
        result = lookup('1')['related']
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['skuItems'], 'A, B')

    def test_replacement_and_credit_reverse_lookup_show_original(self):
        delivery_data.archive([source('663132'), source('700001', '663132'),
                               source('700002', '663132', 'Credit/Refund', '')])
        for order in ('700001', '700002'):
            result = lookup(order)
            self.assertEqual(result['original']['order'], order)
            self.assertEqual([(item['order'], item['relatedKind']) for item in result['related']],
                             [('663132', 'Original')])
            self.assertTrue(result['related'][0]['canOpenDetails'])
        self.assertFalse(lookup('700002')['original']['canOpenDetails'])

    def test_missing_parent_is_not_fabricated(self):
        delivery_data.archive([source('700001', '663132')])
        self.assertEqual(lookup('700001')['related'], [])

    def test_new_snapshots_update_observed_links_and_keep_retained_history(self):
        delivery_data.archive([source('1'), source('2', '1')])
        delivery_data.archive([source('1')])
        self.assertEqual(len(lookup('1')['related']), 1)
        delivery_data.archive([source('2', '9')])
        self.assertEqual(lookup('1')['related'], [])
        self.assertEqual(lookup('9')['related'][0]['order'], '2')
        delivery_data.archive([source('2', '')])
        self.assertEqual(lookup('9')['related'], [])

    def test_metadata_import_and_api_are_opt_in_for_tracking(self):
        delivery_data.archive([source('663132'), source('700001', '663132')])
        self.assertEqual(delivery_data.detail('700001')['salesActivityDetails']['Order Category'], 'Order')
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(delivery_data, 'cached_or_schedule_sync', return_value={}):
                for suffix, included in [('', False), ('&tracking_related=1', True),
                                         ('&tracking_related=1&issues=1', False)]:
                    with urlopen(f'http://127.0.0.1:{http.server_port}/api/deliveries?q=663132{suffix}') as response:
                        data = json.load(response)
                    self.assertEqual('orderRelations' in data, included)
                    if included:
                        self.assertEqual(data['orderRelations']['related'][0]['order'], '700001')
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_original_chain_keeps_each_direct_relationship_and_search_counts(self):
        delivery_data.archive([source('648637'), source('654171', '648637'),
                               source('659494', '654171')])
        result = lookup('659494')
        self.assertEqual(result['parentOrder'], '654171')
        self.assertEqual([(item['order'], item['relatedKind'], item['linkedToOrder'], item['ancestorDepth'])
                          for item in result['related']],
                         [('654171', 'Original', '659494', 1),
                          ('648637', 'Earlier Original', '654171', 2)])
        self.assertEqual(delivery_data.query_records(search='659494')['total'], 1)
        middle = lookup('654171')
        self.assertEqual([(item['order'], item['relatedKind']) for item in middle['related']],
                         [('648637', 'Original'), ('659494', 'Replacement')])

    def test_deeper_original_chains_and_cycles_stop_without_repeating_ancestors(self):
        delivery_data.archive([source('1'), source('2', '1'), source('3', '2'), source('4', '3')])
        self.assertEqual([(item['order'], item['ancestorDepth']) for item in lookup('4')['related']],
                         [('3', 1), ('2', 2), ('1', 3)])
        delivery_data.archive([source('1', '4')])
        ancestors = [item for item in lookup('4')['related'] if item['relatedKind'] != 'Replacement']
        self.assertEqual([item['order'] for item in ancestors], ['3', '2', '1'])

    def test_missing_or_ambiguous_earlier_original_does_not_invent_ancestors(self):
        delivery_data.archive([source('2', '1'), source('3', '2')])
        self.assertEqual([item['order'] for item in lookup('3')['related']], ['2'])
        delivery_data.archive([source('1'), source('2', '1'), source('2', '9')])
        self.assertEqual([item['order'] for item in lookup('3')['related']], ['2'])

    def test_source_only_ancestor_remains_non_openable(self):
        delivery_data.archive([source('1'), source('2', '1', 'Credit/Refund', ''), source('3', '2')])
        result = lookup('3')['related']
        self.assertEqual([item['order'] for item in result], ['2', '1'])
        self.assertFalse(result[0]['canOpenDetails'])
        self.assertTrue(result[1]['canOpenDetails'])

    def test_replacement_chain_includes_every_level_with_its_direct_parent(self):
        delivery_data.archive([source('648637'), source('654171', '648637'),
                               source('659494', '654171'), source('700001', '659494'),
                               source('700002', '700001')])
        result = lookup('648637')
        self.assertEqual([(item['order'], item['relatedKind'], item['linkedToOrder'], item['replacementDepth'])
                          for item in result['related']],
                         [('654171', 'Replacement', '648637', 1),
                          ('659494', 'Later Replacement', '654171', 2),
                          ('700001', 'Later Replacement', '659494', 3),
                          ('700002', 'Later Replacement', '700001', 4)])
        self.assertEqual(delivery_data.query_records(search='648637')['total'], 1)

    def test_replacement_branches_keep_separate_direct_parents(self):
        delivery_data.archive([source('1'), source('2', '1'), source('3', '1'),
                               source('4', '2'), source('5', '3')])
        self.assertEqual([(item['order'], item['linkedToOrder'], item['replacementDepth'])
                          for item in lookup('1')['related']],
                         [('2', '1', 1), ('3', '1', 1), ('4', '2', 2), ('5', '3', 2)])

    def test_replacement_cycle_never_repeats_search_or_ancestors(self):
        delivery_data.archive([source('1', '3'), source('2', '1'), source('3', '2')])
        result = lookup('1')['related']
        self.assertEqual([item['order'] for item in result], ['3', '2'])
        self.assertTrue(all(item['relatedKind'] in {'Original', 'Earlier Original'} for item in result))

    def test_credit_records_do_not_become_replacement_chain_edges(self):
        delivery_data.archive([source('1'), source('2', '1'),
                               source('3', '1', 'Credit/Refund', ''), source('4', '3'),
                               source('5', '2', 'Credit/Refund', '')])
        self.assertEqual([(item['order'], item['relatedKind']) for item in lookup('1')['related']],
                         [('2', 'Replacement'), ('3', 'Credit/Refund')])

    def test_flow_is_identical_when_searching_any_order_in_a_chain(self):
        delivery_data.archive([source('648637'), source('654171', '648637'),
                               source('659494', '654171'), source('700001', '659494')])
        flows = [lookup(order)['flow'] for order in ('648637', '654171', '659494', '700001')]
        self.assertTrue(all(flow == flows[0] for flow in flows))
        self.assertEqual(flows[0]['edges'], [
            {'from': '648637', 'to': '654171', 'kind': 'Replacement'},
            {'from': '654171', 'to': '659494', 'kind': 'Replacement'},
            {'from': '659494', 'to': '700001', 'kind': 'Replacement'}])

    def test_flow_includes_sibling_branches_and_credit_with_correct_edge_types(self):
        delivery_data.archive([source('1'), source('2', '1'), source('3', '1'),
                               source('4', '2'), source('5', '3'),
                               source('6', '1', 'Credit/Refund', ''), source('99')])
        expected = lookup('1')['flow']
        for order in ('2', '3', '4', '5', '6'):
            self.assertEqual(lookup(order)['flow'], expected)
        self.assertEqual([node['id'] for node in expected['nodes']], ['1', '2', '3', '4', '5', '6'])
        self.assertIn({'from': '1', 'to': '6', 'kind': 'Credit/Refund'}, expected['edges'])
        self.assertEqual(lookup('99')['flow'], {'nodes': [], 'edges': []})

    def test_flow_cycle_terminates_and_missing_records_are_not_invented(self):
        delivery_data.archive([source('1', '3'), source('2', '1'), source('3', '2'), source('9', '8')])
        self.assertEqual(lookup('1')['flow'], lookup('2')['flow'])
        self.assertEqual(len(lookup('1')['flow']['edges']), 3)
        self.assertEqual(lookup('9')['flow'], {'nodes': [], 'edges': []})

    def test_flow_nodes_include_saved_statuses_for_all_branches(self):
        delivery_data.archive([source('1'), {**source('2', '1'), 'Status': 'C'},
                               source('3', '1'), source('4', '2'),
                               source('5', '1', 'Credit/Refund', '')])
        from palletways_sheet import archive_statuses
        archive_statuses([{'order': '2', 'status': 'Delivered'},
                          {'order': '3', 'status': 'In Transit'}])
        nodes = {node['id']: node for node in lookup('4')['flow']['nodes']}
        self.assertEqual(nodes['2']['st'], 'Delivered')
        self.assertEqual(nodes['2']['palletwaysSheetStatus'], 'Delivered')
        self.assertEqual(nodes['3']['palletwaysSheetStatus'], 'In Transit')
        self.assertEqual(nodes['5']['category'], 'credit/refund')
        self.assertEqual(nodes['5']['st'], '')
        self.assertTrue(nodes['2']['canOpenDetails'])
        self.assertFalse(nodes['5']['canOpenDetails'])
        self.assertNotIn('cust', nodes['2'])

    def test_dashboard_flow_endpoint_returns_only_graph_and_validates_exact_ids(self):
        delivery_data.archive([source('1'), source('2', '1'), source('3', '2'), source('99')])
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(delivery_data, 'cached_or_schedule_sync', side_effect=AssertionError('No provider sync')):
                graphs = []
                for order in ('1', '2', '3'):
                    with urlopen(f'http://127.0.0.1:{http.server_port}/api/order-flow?order={order}') as response:
                        result = json.load(response)
                    self.assertEqual(set(result), {'found', 'order', 'flow'})
                    self.assertTrue(result['found'])
                    graphs.append(result['flow'])
                self.assertEqual(graphs[0], graphs[1])
                self.assertEqual(graphs[1], graphs[2])
                for order, found in [('99', True), ('999', False)]:
                    with urlopen(f'http://127.0.0.1:{http.server_port}/api/order-flow?order={order}') as response:
                        result = json.load(response)
                    self.assertEqual(result['found'], found)
                    self.assertEqual(result['flow']['edges'], [])
                from urllib.error import HTTPError
                with self.assertRaises(HTTPError) as error:
                    urlopen(f'http://127.0.0.1:{http.server_port}/api/order-flow?order=ABC')
                self.assertEqual(error.exception.code, 400)
                error.exception.close()
        finally:
            http.shutdown()
            http.server_close()
            thread.join()
