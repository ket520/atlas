import tempfile
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.request import Request, urlopen
from pathlib import Path
from unittest.mock import patch

import collection_records
import delivery_data
import server


class CollectionRecordsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db_patch = patch.object(delivery_data, 'DB_PATH', Path(self.temp.name) / 'notes.sqlite3')
        self.db_patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.db_patch.stop)

    def note(self):
        return {'summary': dict(order='123', collectionOrder='456', customer='Alice', postcode='AB1',
                                collectionDate='2026-10-15', items='SKU1'),
                'paper': '<table><tbody><tr><td><input name="order" value="123"></td></tr></tbody></table>'}

    def test_approval_toggle_survives_note_edits_and_defaults_for_legacy(self):
        note = self.note()
        saved = collection_records.save_note(note)
        note_id = saved['id']
        self.assertEqual(collection_records.get_note(note_id)['status'], 'Pending')
        collection_records.set_status(note_id, 'Approved')
        note['id'] = note_id
        note['summary']['customer'] = 'Edited'
        collection_records.save_note(note)
        self.assertEqual(collection_records.get_note(note_id)['status'], 'Approved')
        self.assertEqual(collection_records.list_notes()['records'][0]['status'], 'Approved')
        collection_records.set_status(note_id, 'Pending')
        self.assertEqual(collection_records.get_note(note_id)['status'], 'Pending')
        with self.assertRaises(ValueError):
            collection_records.set_status(note_id, 'Other')
        with self.assertRaises(FileNotFoundError):
            collection_records.set_status('missing', 'Approved')
        self.assertEqual(collection_records.record_summary(json.dumps(self.note()))['status'], 'Pending')

    def test_channel_and_phone_are_saved_and_recovered_from_older_notes(self):
        note = self.note()
        note['paper'] = '<input name="company" value="Shopify"><input name="phone" value="0123456789">'
        saved = collection_records.save_note(note)
        record = collection_records.list_notes()['records'][0]
        self.assertEqual((record['channel'], record['phone']), ('Shopify', '0123456789'))
        note['id'] = saved['id']
        note['summary'].update(channel='Amazon', phone='0987654321')
        collection_records.save_note(note)
        record = collection_records.list_notes()['records'][0]
        self.assertEqual((record['channel'], record['phone']), ('Amazon', '0987654321'))

    def test_save_reopen_and_update_without_duplicate_records(self):
        self.assertEqual(collection_records.list_notes(), {'records': []})
        note = self.note()
        saved = collection_records.save_note(note)
        restored = collection_records.get_note(saved['id'])
        self.assertEqual(restored['paper'], note['paper'])
        self.assertEqual(restored['summary'], note['summary'])
        note['id'] = saved['id']
        note['summary']['customer'] = 'Bob'
        collection_records.save_note(note)
        records = collection_records.list_notes()['records']
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['customer'], 'Bob')
        self.assertNotIn('paper', records[0])
        self.assertIsNone(collection_records.get_note('missing'))

    def test_new_notes_for_same_order_remain_separate(self):
        for _ in range(2):
            collection_records.save_note(self.note())
        self.assertEqual(len(collection_records.list_notes()['records']), 2)

    def test_reference_is_saved_and_original_creation_time_survives_updates(self):
        note = self.note()
        note['summary']['orderRef'] = 'REF-123'
        saved = collection_records.save_note(note)
        first = collection_records.list_notes()['records'][0]
        self.assertEqual(first['orderRef'], 'REF-123')
        note['id'] = saved['id']
        note['summary']['orderRef'] = 'REF-UPDATED'
        collection_records.save_note(note)
        updated = collection_records.list_notes()['records'][0]
        self.assertEqual(updated['orderRef'], 'REF-UPDATED')
        self.assertEqual(updated['createdAt'], first['createdAt'])

    def test_older_notes_recover_reference_from_saved_form_not_collection_number(self):
        note = self.note()
        note['paper'] += '<input name="orderRef" value="REF&amp;123">'
        collection_records.save_note(note)
        record = collection_records.list_notes()['records'][0]
        self.assertEqual(record['orderRef'], 'REF&123')
        self.assertEqual(record['collectionOrder'], '456')

    def test_invalid_data_and_unknown_updates_rejected(self):
        for payload in (None, {}, {'paper': '<table></table>'}):
            with self.assertRaises(ValueError):
                collection_records.save_note(payload)
        note = self.note()
        note['summary']['order'] = ' '
        with self.assertRaises(ValueError):
            collection_records.save_note(note)
        note = self.note()
        note['id'] = 'missing'
        with self.assertRaises(ValueError):
            collection_records.save_note(note)

    def test_tracking_detail_links_latest_note_for_exact_order(self):
        delivery_data.archive([{'Order no': '123', 'Delivery method': 'Palletways'}])
        self.assertIsNone(delivery_data.detail('123')['collectionNoteId'])
        note = self.note()
        first = collection_records.save_note(note)['id']
        self.assertEqual(delivery_data.detail('123')['collectionNoteId'], first)
        second = collection_records.save_note(note)['id']
        self.assertEqual(delivery_data.detail('123')['collectionNoteId'], second)
        other = self.note()
        other['summary']['order'] = '1234'
        collection_records.save_note(other)
        self.assertEqual(delivery_data.detail('123')['collectionNoteId'], second)
        note['id'] = first
        collection_records.save_note(note)
        self.assertEqual(delivery_data.detail('123')['collectionNoteId'], first)

    def test_http_save_list_and_open(self):
        http = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        base = f'http://127.0.0.1:{http.server_port}/api/collection-notes'
        try:
            request = Request(base, data=json.dumps(self.note()).encode(),
                              headers={'Content-Type': 'application/json'}, method='POST')
            with urlopen(request, timeout=5) as response:
                saved = json.load(response)
            with urlopen(base, timeout=5) as response:
                self.assertEqual(json.load(response)['records'][0]['id'], saved['id'])
            with urlopen(base + '/' + saved['id'], timeout=5) as response:
                self.assertEqual(json.load(response)['paper'], self.note()['paper'])
            for status in ('Approved', 'Pending'):
                request = Request(base + '/' + saved['id'] + '/status',
                                  data=json.dumps({'status': status}).encode(),
                                  headers={'Content-Type': 'application/json'}, method='POST')
                with urlopen(request, timeout=5) as response:
                    self.assertEqual(json.load(response)['status'], status)
                with urlopen(base + '/' + saved['id'], timeout=5) as response:
                    self.assertEqual(json.load(response)['status'], status)
            other = collection_records.save_note(self.note())
            with urlopen(Request(base + '/' + saved['id'], method='DELETE'), timeout=5) as response:
                self.assertTrue(json.load(response)['deleted'])
            self.assertIsNone(collection_records.get_note(saved['id']))
            self.assertIsNotNone(collection_records.get_note(other['id']))
        finally:
            http.shutdown()
            http.server_close()
            thread.join()

    def test_channel_uses_tracking_store_classification_for_saved_notes(self):
        note = self.note()
        note['summary']['channel'] = 'Website'
        saved = collection_records.save_note(note)
        mappings = [('SHOPIFY', 'Shopify - Neshome'), ('BATHPROF', 'Bathroom Republic - Website'),
                    ('BATHROOM', 'Bathroom Republic - Website'), ('AMAZON', 'Amazon'), ('', '')]
        for code, expected in mappings:
            with self.subTest(code=code):
                payload = {'storeCode': code, 'salesActivityDetails': {'Order Type': 'Shopify', 'Order Analysis': 'Website'}}
                with delivery_data.connect() as db:
                    db.execute('INSERT OR REPLACE INTO deliveries VALUES (?,?,?,?)',
                               ('123', json.dumps(payload), '2026-01-01', '2026-01-01'))
                    db.commit()
                record = next(row for row in collection_records.list_notes()['records'] if row['id'] == saved['id'])
                self.assertEqual(record['channel'], expected)
                self.assertEqual(collection_records.get_note(saved['id'])['summary']['channel'], 'Website')

    def test_rejection_persists_and_can_be_changed_to_approval(self):
        note = self.note()
        note_id = collection_records.save_note(note)['id']
        collection_records.set_status(note_id, 'Rejected')
        note['id'] = note_id
        collection_records.save_note(note)
        self.assertEqual(collection_records.get_note(note_id)['status'], 'Rejected')
        self.assertEqual(collection_records.list_notes()['records'][0]['status'], 'Rejected')
        collection_records.set_status(note_id, 'Approved')
        self.assertEqual(collection_records.get_note(note_id)['status'], 'Approved')
