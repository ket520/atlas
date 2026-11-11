import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import delivery_data
import amazon_background_prefetch as prefetch


class AmazonPrefetchPriorityTests(unittest.TestCase):
    def test_background_pass_finishes_delivered_candidates_before_other_statuses(self):
        class PassFinished(Exception):
            pass
        def sleep(seconds):
            if seconds == 60:
                raise PassFinished()
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data,'DB_PATH',Path(directory)/'test.sqlite3'):
            with delivery_data.connect() as db:
                for order,tracking,status in [('1','CACHED','DELIVERED'),('2','PENDING','DELIVERED'),('3','OTHER','IN_TRANSIT')]:
                    payload={'carrier':'AMZ','trk':tracking,'amazonSheetStatus':status,'date':'2026-11-06'}
                    db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',(order,json.dumps(payload),'2026-11-06','2026-11-06'))
                db.commit()
            with patch.object(delivery_data,'cached_or_schedule_sync'), \
                 patch.object(prefetch,'snapshot',side_effect=lambda tracking: {'saved':True} if tracking=='CACHED' else None), \
                 patch.object(prefetch,'JOBS',{}), \
                 patch.object(prefetch,'_call',return_value=(200,{'state':'ready'})) as lookup, \
                 patch.object(prefetch.time,'sleep',side_effect=sleep):
                with self.assertRaises(PassFinished):
                    prefetch._loop()
                self.assertEqual([call.args[0] for call in lookup.call_args_list],['PENDING','OTHER'])

    def test_amazon_delivered_first_then_other_statuses_newest_first(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data,'DB_PATH',Path(directory)/'test.sqlite3'):
            records = [
                # A future non-delivered record must not overtake an older Delivered one.
                dict(order='1',trk='TRANSIT',amazonSheetStatus='IN_TRANSIT',date='2026-12-01'),
                dict(order='2',trk='DELIVERED-OLD',amazonSheetStatus='DELIVERED',date='2026-09-01'),
                dict(order='3',trk='DELIVERED-NEW',amazonSheetStatus=' delivered ',date='2026-11-06'),
                # OW Completed alone is not Amazon Delivered.
                dict(order='4',trk='CANCELLED',amazonSheetStatus='CARRIER_CANCELLED_PICKUP',st='Delivered',date='2026-11-01'),
                dict(order='5',trk='WRONG-ID',owTrackingNo='OW-ID',amazonSheetStatus='DELIVERED',dispatchDate='2026-10-01'),
                dict(order='6',trk='NO-DATE',amazonSheetStatus='DELIVERED'),
                # Deduplicate an ID across both phases, keeping its Delivered position.
                dict(order='7',trk='DELIVERED-NEW',amazonSheetStatus='IN_TRANSIT',date='2026-12-02'),
                dict(order='8',trk='BAD ID',amazonSheetStatus='DELIVERED',date='2026-11-07'),
                dict(order='9',trk='NON-AMAZON',carrier='XDP',amazonSheetStatus='DELIVERED',date='2026-11-07'),
            ]
            with delivery_data.connect() as db:
                for record in records:
                    payload={'carrier':'AMZ','st':'Scheduled',**record}
                    db.execute('INSERT INTO deliveries VALUES (?,?,?,?)',
                        (record['order'],json.dumps(payload),'2026-11-06','2026-11-06'))
                db.commit()
            self.assertEqual(list(prefetch._ordered_ids()),
                ['DELIVERED-NEW','OW-ID','DELIVERED-OLD','NO-DATE','TRANSIT','CANCELLED'])
