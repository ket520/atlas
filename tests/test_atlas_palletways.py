import unittest
from unittest.mock import patch

import atlas_palletways


class AtlasPalletwaysBridgeTests(unittest.TestCase):
    def test_both_identifiers_are_required_and_route_is_read_only(self):
        with patch.object(atlas_palletways, '_get_json', return_value={'tracking_id': '60000000001',
                'consignment_number': 'FIRST-41', 'status': {'ETA': None},
                'shipment': {'Weight': '25'}, 'raw_payload': 'excluded'}) as request:
            result = atlas_palletways.shipment_details('60000000001', 'FIRST-41')
        request.assert_called_once_with('/atlas/palletways/shipments/60000000001/FIRST-41')
        self.assertNotIn('raw_payload', result)
        self.assertIsNone(result['status']['ETA'])
        self.assertEqual(result['shipment']['Weight'], '25')
        with patch.object(atlas_palletways, '_get_json') as request:
            for tracking, consignment in (('', 'FIRST-41'), ('60000000001', ''), ('60000000001', '../private')):
                with self.assertRaises(ValueError):
                    atlas_palletways.shipment_details(tracking, consignment)
            request.assert_not_called()

    def test_full_order_keeps_inactive_links_and_historical_values_separate(self):
        shipment = {'tracking_id': '60000000001', 'consignment_number': 'FIRST-41',
                    'linked_orders': [{'order_no': '1', 'mapping_status': 'inactive'}],
                    'scheduling': {'DueDate': None}, 'historical_snapshot': {'DueDate': '01/02/2025'}}
        with patch.object(atlas_palletways, '_get_json', return_value={
            'palletways': {'shipments': [shipment]}, 'lines': []
        }):
            result = atlas_palletways.order_shipments('1')
        self.assertTrue(result['details_available'])
        self.assertEqual(result['shipments'][0]['linked_orders'][0]['mapping_status'], 'inactive')
        self.assertIsNone(result['shipments'][0]['scheduling']['DueDate'])
        self.assertEqual(result['shipments'][0]['historical_snapshot']['DueDate'], '01/02/2025')

    def test_not_yet_activated_detail_route_does_not_invent_full_data(self):
        with patch.object(atlas_palletways, '_get_json', return_value={'lines': [
            {'palletways_shipments': [{'palletways_status': 'Palletways Not Assigned'}]}
        ]}):
            result = atlas_palletways.order_shipments('1')
        self.assertFalse(result['details_available'])
        self.assertEqual(result['shipments'], [])
        self.assertEqual(result['summaries'][0]['palletways_status'], 'Palletways Not Assigned')

    def test_events_and_audit_use_both_identifiers_and_pagination(self):
        with patch.object(atlas_palletways, '_get_json', return_value={'items': [], 'has_more': False}) as request:
            atlas_palletways.shipment_records('60000000001', 'FIRST-41', 'events', 25, 50, 'historical')
            request.assert_called_with('/atlas/palletways/shipments/60000000001/FIRST-41/events',
                                       {'limit': 25, 'offset': 50, 'source': 'historical'})
            atlas_palletways.shipment_records('60000000001', 'FIRST-41', 'audit', 50, 0)
            request.assert_called_with('/atlas/palletways/shipments/60000000001/FIRST-41/audit',
                                       {'limit': 50, 'offset': 0})
            for kind, limit, offset, source in [('events', 101, 0, None), ('audit', 50, -1, None),
                                                ('audit', 50, 0, 'historical')]:
                with self.assertRaises(ValueError):
                    atlas_palletways.shipment_records('60000000001', 'FIRST-41', kind, limit, offset, source)
