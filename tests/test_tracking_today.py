import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

import delivery_data


class TrackingTodayTests(unittest.TestCase):
    def test_source_statuses_work_without_shared_date(self):
        for carrier, field, value in [('Stopstart', 'stopstartStatus', 'Expected Today'),
                                      ('XDP', 'xdpStatus', 'NEXT STOP'),
                                      ('Palletways', 'palletwaysSheetStatus', 'Out for Delivery')]:
            with self.subTest(carrier=carrier):
                self.assertTrue(delivery_data.tracking_today({'carrier': carrier, 'st': 'Unscheduled', field: value}, '2026-10-22'))
                self.assertFalse(delivery_data.tracking_today({'carrier': carrier, 'st': 'Failed', field: value}, '2026-10-22'))

    def test_dates_for_all_carriers_and_no_order_or_dispatch_date_guess(self):
        for carrier in ['Own van', 'Self Delivery', 'LOCAL MULTIDROP', 'AMZ', 'Palletways', 'XDP', 'Yodel', 'UK Next Day', 'Wayfair']:
            with self.subTest(carrier=carrier):
                self.assertTrue(delivery_data.tracking_today({'carrier': carrier, 'st': 'Scheduled', 'date': '2026-10-22'}, '2026-10-22'))
                self.assertFalse(delivery_data.tracking_today({'carrier': carrier, 'st': 'Scheduled', 'date': '2026-10-23'}, '2026-10-22'))
                self.assertFalse(delivery_data.tracking_today({'carrier': carrier, 'st': 'Scheduled', 'orderDate': '2026-10-22', 'dispatchDate': '2026-10-22'}, '2026-10-22'))
        self.assertTrue(delivery_data.tracking_today({'carrier': 'Stopstart', 'st': 'Unscheduled', 'stopstartDetails': {'expectedDate': '2026-10-22'}}, '2026-10-22'))
        self.assertTrue(delivery_data.tracking_today({'carrier': 'Palletways', 'st': 'Scheduled', 'palletwaysDetails': {'dueAt': '2026-10-22T14:00:00+01:00'}}, '2026-10-22'))
        for status in ['DAMAGE', 'DELETE', 'NOT RECEIVED']:
            self.assertFalse(delivery_data.tracking_today({'carrier': 'XDP', 'st': 'Awaiting', 'xdpStatus': status, 'date': '2026-10-22'}, '2026-10-22'))

    def test_sql_query_facets_counts_and_pagination_agree(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.db'):
            day = datetime.now(ZoneInfo('Europe/London')).date().isoformat()
            rows = [{'carrier': 'Stopstart', 'st': 'Unscheduled', 'stopstartStatus': 'Expected Today'},
                    {'carrier': 'XDP', 'st': 'Awaiting', 'xdpStatus': 'NEXT STOP'},
                    {'carrier': 'Palletways', 'st': 'Scheduled', 'palletwaysSheetStatus': 'Out for Delivery'},
                    {'carrier': 'Yodel', 'st': 'Scheduled', 'date': day},
                    {'carrier': 'Stopstart', 'st': 'Unscheduled', 'stopstartStatus': 'Tracking Unavailable'},
                    {'carrier': 'XDP', 'st': 'Failed', 'xdpStatus': 'DAMAGE', 'date': day}]
            with delivery_data.connect() as db:
                for i, row in enumerate(rows):
                    row.update(id=str(i), order=str(i))
                    db.execute('INSERT INTO deliveries VALUES (?,?,?,?)', (str(i), json.dumps(row), day, day))
                db.commit()
            result = delivery_data.query_records(general_scope='today', limit=2)
            self.assertEqual(result['total'], 4)
            self.assertTrue(result['hasMore'])
            self.assertEqual(delivery_data.query_records(general_scope='today', carrier='Stopstart')['total'], 1)
            summary = delivery_data.summary()
            self.assertEqual(summary['todayTotal'], 4)
            self.assertEqual(sum(item['count'] for item in summary['filterFacets'] if item['today']), 4)
