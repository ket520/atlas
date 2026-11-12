import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import atlas_postgres_provider as provider
import delivery_data
from palletways_shipments import normalize_shipments, shipment_statuses, delivery_stage
from status_views import status_view
from tracking_status import global_tracking_status


class PalletwaysShipmentTests(unittest.TestCase):
    def record(self, order='662712', method='Palletways Next Day'):
        return {'order_no': order, 'status': 'Completed', 'cells': {
            'Order no': order, 'Status': 'Completed', 'Delivery method': method, 'Product SKU': 'SKU-A',
        }, 'palletways_shipments': [
            {'palletways_status': 'Delivered', 'carrier_status': 'Delivered', 'tracking_id': '60000000001',
             'consignment_number': 'FIRST-41', 'status_checked_at': '2026-11-12T08:00:00Z'},
            {'palletways_status': 'Unscheduled', 'carrier_status': 'Unscheduled', 'tracking_id': '60000000002',
             'consignment_number': 'SECOND-41', 'status_checked_at': '2026-11-12T08:00:00Z'},
        ]}

    def test_adapter_preserves_array_and_orderwise_status(self):
        row = provider._row(self.record())
        self.assertIsInstance(row['palletways_shipments'], list)
        delivery = delivery_data.row_to_delivery(row)
        self.assertEqual(delivery['rawStatus'], 'Completed')
        self.assertEqual(len(delivery['palletwaysShipments']), 2)
        self.assertEqual(shipment_statuses(delivery), ['Delivered', 'Unscheduled'])
        self.assertNotEqual(delivery_stage(delivery), 'Delivered')
        self.assertNotEqual(global_tracking_status(delivery), 'Delivered')

    def test_not_assigned_is_explicit_and_missing_is_not_orderwise(self):
        record = self.record()
        record['palletways_shipments'] = [{'palletways_status': 'Palletways Not Assigned'}]
        self.assertEqual(status_view(delivery_data.row_to_delivery(provider._row(record)))['carrier'], 'Palletways Not Assigned')
        record['palletways_shipments'] = [{'carrier_status': 'Completed'}]
        self.assertEqual(status_view(delivery_data.row_to_delivery(provider._row(record)))['carrier'], 'Status unavailable')

    def test_other_carriers_do_not_receive_palletways_fields(self):
        delivery = delivery_data.row_to_delivery(provider._row(self.record(method='XDP')))
        self.assertNotIn('palletwaysShipments', delivery)

    def test_invalid_array_is_rejected(self):
        record = self.record()
        record['palletways_shipments'] = {'palletways_status': 'Delivered'}
        with self.assertRaises(provider.AtlasProviderError):
            provider._row(record)

    def test_product_rows_deduplicate_shipments_and_filter_each_status_once(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / '.tmp-tests') as directory, patch.object(
            delivery_data, 'configured_db_path', return_value=Path(directory) / 'isolated.sqlite3'
        ):
            row = provider._row(self.record())
            delivery_data.archive([row, {**row, 'Product SKU': 'SKU-B'}])
            for selected in ('Delivered', 'Unscheduled', ['Delivered', 'Unscheduled']):
                result = delivery_data.query_records(carrier='Palletways', status=selected, status_view_scope='tracking')
                self.assertEqual(result['total'], 1)
                self.assertEqual(len(result['deliveries'][0]['palletwaysShipments']), 2)
            self.assertEqual(delivery_data.query_records(carrier='Palletways', status='Completed', status_view_scope='tracking')['total'], 0)
            facets = delivery_data.summary()['filterFacets']
            self.assertEqual(sum(item['count'] for item in facets), 1)
            self.assertEqual(json.loads(facets[0]['palletwaysStatuses']), ['Delivered', 'Unscheduled'])
            cleared = {**row, 'palletways_shipments': []}
            delivery_data.archive([cleared])
            self.assertEqual(delivery_data.query_records()['deliveries'][0]['palletwaysShipments'], [])
