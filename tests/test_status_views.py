import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import delivery_data
from status_views import UNAVAILABLE, status_view


class StatusViewTests(unittest.TestCase):
    def test_sales_and_carrier_statuses_are_independent(self):
        view = status_view({'carrier': 'Palletways', 'rawStatus': 'Completed',
                            'palletwaysShipments': [{'palletways_status': 'Out for Delivery'}]})
        self.assertEqual(view['sales'], 'Completed')
        self.assertEqual(view['carrier'], 'Out for Delivery')
        self.assertEqual(view['source'], 'Atlas API · Palletways')

    def test_missing_carrier_status_never_uses_order_or_sheet_status(self):
        for carrier in ('Palletways', 'AMZ', 'XDP', 'Stopstart', 'Yodel', 'Own van'):
            view = status_view({'carrier': carrier, 'rawStatus': 'Completed', 'st': 'Delivered',
                                'palletwaysSheetStatus': 'Delivered', 'amazonStatus': 'DELIVERED',
                                'xdpStatus': 'Delivered', 'stopstartStatus': 'Delivered'})
            self.assertEqual(view['carrier'], UNAVAILABLE)
            self.assertFalse(view['available'])

    def test_optimoroute_status_is_not_replaced_by_routine_or_sales(self):
        view = status_view({'carrier': 'Self Delivery', 'rawStatus': 'Completed', 'st': 'Failed',
                            'statusSource': 'Routine Dashboard - Live', 'providerStatus': 'on_route'})
        self.assertEqual(view['carrier'], 'On Route')
        self.assertEqual(view['source'], 'OptimoRoute')

    def test_sql_filters_and_facets_use_same_status_as_list(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / '.tmp-tests') as directory, patch.object(
            delivery_data, 'configured_db_path', return_value=Path(directory) / 'isolated.sqlite3'
        ):
            delivery_data.archive([{'Order no': '1', 'Delivery method': 'Palletways', 'Status': 'Completed'},
                                   {'Order no': '2', 'Delivery method': 'Own van', 'Status': 'Open'}])
            with delivery_data.connect() as db:
                db.execute("update deliveries set payload=json_set(payload,'$.palletwaysShipments',json(?)) where order_id='1'", (json.dumps([{'palletways_status': 'Out for Delivery'}]),))
                db.commit()
            sales = delivery_data.query_records(status='Completed', status_view_scope='tracking')
            carrier = delivery_data.query_records(carrier='Palletways', status='Out for Delivery', status_view_scope='tracking')
            self.assertEqual(sales['total'], 1)
            self.assertEqual(carrier['total'], 1)
            self.assertEqual(carrier['deliveries'][0]['statusView']['carrier'], 'Out for Delivery')
            self.assertEqual(delivery_data.query_records(carrier='Palletways', status='Completed', status_view_scope='tracking')['total'], 0)
            facets = delivery_data.summary()['filterFacets']
            palletways = next(item for item in facets if item['carrier'] == 'Palletways')
            self.assertEqual(palletways['salesStatus'], 'Completed')
            self.assertEqual(palletways['carrierStatus'], 'Out for Delivery')
