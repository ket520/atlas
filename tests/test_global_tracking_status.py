import collections
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import delivery_data
from tracking_status import global_tracking_status
from global_tracking_status_cases import global_status_cases


class GlobalTrackingStatusTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = patch.object(delivery_data, 'configured_db_path', return_value=Path(directory.name) / 'orders.sqlite3')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.cases = global_status_cases()
        with delivery_data.connect() as db:
            for record, _ in self.cases:
                db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',
                    (record['order'], json.dumps(record), '2026-11-06', '2026-11-06'))
            db.commit()

    def test_all_agreed_groups_filter_before_paging_and_reconcile(self):
        expected = collections.defaultdict(set)
        for record, group in self.cases:
            self.assertEqual(global_tracking_status(record), group, record)
            expected[group].add(record['order'])
        for group, orders in expected.items():
            result = delivery_data.query_records(global_status=True, status=group, limit=100)
            self.assertEqual({row['order'] for row in result['deliveries']}, orders, group)
            self.assertTrue(all(row['overallStatus'] == group for row in result['deliveries']))
            if len(orders) > 1:
                page = delivery_data.query_records(global_status=True, status=group, limit=1, offset=1)
                self.assertEqual(page['total'], len(orders))
                self.assertEqual(page['deliveries'][0]['order'], sorted(orders, reverse=True)[1])
        facets = delivery_data.summary()['filterFacets']
        actual = collections.Counter()
        for item in facets:
            actual[item['overallStatus']] += item['count']
            self.assertIn('rawStatus', item)
        self.assertEqual(actual, {group:len(orders) for group,orders in expected.items()})
        self.assertEqual(sum(actual.values()), len(self.cases))
        self.assertNotIn('Awaiting', actual)

    def test_specific_filters_and_saved_categories_are_unchanged(self):
        for carrier, status in [('AMZ','amazon:LOST'), ('XDP','xdp:BOOKING'), ('Palletways','palletways:In Transit')]:
            result = delivery_data.query_records(global_status=True, carrier=carrier, courier_status=True, status=status)
            self.assertEqual(result['total'], 1)
            self.assertEqual(result['deliveries'][0]['st'], 'Delivered')
        # Default non-issue callers keep saved-category semantics.
        self.assertEqual(delivery_data.query_records(status='Lost')['total'], 1)
        with delivery_data.connect() as db:
            actual = {r['order_id']:json.loads(r['payload']) for r in db.execute('SELECT order_id,payload FROM deliveries')}
        self.assertEqual(actual, {record['order']:record for record,_ in self.cases})

    def test_failed_page_includes_all_three_global_groups_and_palletways(self):
        expected = {r['order'] for r,group in self.cases if group in {'Failed','Rejected','Lost'}}
        # A credit/refund must not enter the delivery workflow even if saved as Failed.
        with delivery_data.connect() as db:
            credit = dict(id='999999', order='999999', carrier='Own van', st='Failed', orderRelationKind='Credit/Refund')
            db.execute('INSERT INTO deliveries VALUES (?,?,?,?)', ('999999',json.dumps(credit),'2026-11-06','2026-11-06'))
            db.commit()
        result = delivery_data.query_records(issue_cases=True, limit=100)
        self.assertEqual({r['order'] for r in result['deliveries']}, expected)
        for group in ['Failed','Rejected','Lost']:
            filtered = delivery_data.query_records(issue_cases=True, status=group, limit=100)
            self.assertEqual({r['order'] for r in filtered['deliveries']},
                {r['order'] for r,g in self.cases if g==group})
            self.assertEqual(delivery_data.query_records(issue_cases=True, carrier='Palletways',
                courier_status=True, status=group)['total'], 1)
        summary = delivery_data.summary()
        self.assertEqual(summary['failedTotal'], len(expected))
        self.assertEqual(sum(summary['failedCarriers'].values()), len(expected))
        self.assertEqual(summary['failedCarriers']['Palletways'], 3)
        page = delivery_data.query_records(issue_cases=True, limit=1, offset=1)
        self.assertEqual(page['total'], len(expected))
        self.assertEqual(page['deliveries'][0]['order'], sorted(expected, reverse=True)[1])
