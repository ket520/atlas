import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import atlas_postgres_provider as provider
import delivery_data
from palletways_booking import matches_filters
from palletways_shipments import normalize_shipments


class PalletwaysBookingApiTests(unittest.TestCase):
    def shipment(self, number, booked=None, requested=None, mapping=None, date=None):
        return {
            'tracking_id': f'6000000000{number}',
            'consignment_number': f'CON-{number}',
            'mapping_status': mapping,
            'booking_summary': {
                'booked_in': booked,
                'book_in_request': requested,
                'booking_date': date,
                'booking_time': None,
                'checked_at': '2026-11-12T08:00:00Z',
                'source': 'carrier',
            },
        }

    def record(self, order, method, shipments):
        return provider._row({
            'order_no': order,
            'cells': {'Order no': order, 'Delivery method': method, 'Status': 'Pending'},
            'palletways_shipments': shipments,
        })

    def test_normalization_preserves_nullable_flags_and_distinct_consignments(self):
        shipments = normalize_shipments([
            self.shipment(1, False, True), self.shipment(2, True, None, date='12/11/2026')
        ])
        self.assertEqual(len(shipments), 2)
        self.assertIs(shipments[0]['booking_summary']['booked_in'], False)
        self.assertIsNone(shipments[1]['booking_summary']['book_in_request'])
        with self.assertRaises(ValueError):
            normalize_shipments([self.shipment(1, 'No', True)])

    def test_next_day_and_inactive_mappings(self):
        ordinary = delivery_data.row_to_delivery(self.record('100', 'Palletways', [
            self.shipment(1, False, True), self.shipment(2, True, False, mapping='inactive')
        ]))
        self.assertTrue(matches_filters(ordinary, 'not-yet', ''))
        self.assertFalse(matches_filters(ordinary, 'yes', ''))
        self.assertTrue(matches_filters(ordinary, '', 'yes'))
        next_day = delivery_data.row_to_delivery(self.record('101', 'Palletways Next Day', [
            self.shipment(3, False, True)
        ]))
        self.assertTrue(matches_filters(next_day, 'not-applicable', ''))
        self.assertFalse(matches_filters(next_day, '', 'yes'))

    def test_server_filter_counts_order_once_across_consignments(self):
        Path('.tmp-tests').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir='.tmp-tests') as directory, patch.object(
            delivery_data, 'configured_db_path', return_value=Path(directory) / 'booking.sqlite3'
        ):
            delivery_data.archive([
                self.record('100', 'Palletways', [self.shipment(1, True, False), self.shipment(2, True, True)]),
                self.record('101', 'Palletways Next Day', [self.shipment(3, False, None)]),
                self.record('102', 'Palletways', [self.shipment(4)]),
            ])
            self.assertEqual(delivery_data.query_records(carrier='Palletways', booked_in='yes')['total'], 1)
            self.assertEqual(delivery_data.query_records(carrier='Palletways', booked_in='not-applicable')['total'], 1)
            self.assertEqual(delivery_data.query_records(carrier='Palletways', booked_in='unknown')['total'], 1)
            self.assertEqual(delivery_data.query_records(carrier='Palletways', book_in_request='yes')['total'], 1)
            self.assertEqual(delivery_data.query_records(
                carrier='Palletways', booked_in='not-yet', book_in_request='yes'
            )['total'], 0)

    def test_orders_request_opts_in_to_booking_summary(self):
        payload = {'items': [], 'has_more': False}
        with patch.object(provider, '_get_json', return_value=payload) as request:
            self.assertEqual(provider.read_sales_activity(), [])
        self.assertEqual(request.call_args.args[1]['include'], 'palletways_booking')


if __name__ == '__main__':
    unittest.main()
