import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import delivery_data
import manufacture_claims as claims

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')


class ManufactureClaimsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.patch = patch.object(delivery_data, 'configured_db_path', return_value=Path(directory.name) / 'claims.sqlite3')
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def payload(self):
        return dict(orderDate='2026-10-24', originalOrderNo='650001', replacementOrderNo='650002',
                    variantCode='SKU-1', reason='Scratches', solution='Refund', sellingShop='B&Q',
                    photos=[{'name': 'damage.png', 'data': base64.b64encode(PNG).decode()}])

    def test_save_reload_and_retrieve_original_picture(self):
        self.assertEqual(claims.list_claims(), {'records': []})
        record = claims.save_claim(self.payload())
        self.assertEqual(claims.list_claims()['records'], [record])
        photo = record['photos'][0]
        self.assertEqual(claims.get_photo(record['id'], photo['id']), (PNG, 'image/png'))
        self.assertIsNone(claims.get_photo('other-claim', photo['id']))
        self.assertNotIn('data', photo)
        self.assertEqual(record['replacementOrderNo'], '650002')

    def test_custom_reason_and_solution_are_stored(self):
        payload = self.payload()
        payload.update(reason='Others', reasonOther='Cracked glaze', solution='Others', solutionOther='Supplier assessment')
        record = claims.save_claim(payload)
        self.assertEqual(record['reason'], 'Cracked glaze')
        self.assertEqual(record['solution'], 'Supplier assessment')

    def test_inline_photo_append_preserves_fields_date_and_original_pictures(self):
        payload = self.payload()
        payload.update(reason='Others', reasonOther='Custom reason')
        original = claims.save_claim(payload)
        updated = claims.add_photos(original['id'], {'photos': payload['photos']})
        self.assertEqual(len(updated['photos']), 2)
        self.assertEqual(updated['photos'][0], original['photos'][0])
        self.assertEqual(updated['reason'], 'Custom reason')
        for field in ('createdAt', 'originalOrderNo', 'replacementOrderNo', 'variantCode', 'solution', 'sellingShop'):
            self.assertEqual(updated[field], original[field])
        self.assertEqual(claims.list_claims()['records'][0], updated)

    def test_inline_photo_limits_and_failures_do_not_change_saved_claim(self):
        payload = self.payload()
        original = claims.save_claim(payload)
        for data in ({'photos': payload['photos'] * 5}, {'photos': []}, {'photos': [{'name': 'bad.txt', 'data': 'YWJj'}]}):
            with self.assertRaises(ValueError):
                claims.add_photos(original['id'], data)
            self.assertEqual(claims.list_claims()['records'][0], original)
        with self.assertRaises(FileNotFoundError):
            claims.add_photos('missing', {'photos': payload['photos']})

    def test_update_preserves_identity_and_photos_and_replaces_fields(self):
        original = claims.save_claim(self.payload())
        payload = {**self.payload(), 'photos': [], 'variantCode': 'UPDATED', 'reason': 'Others', 'reasonOther': 'Custom issue'}
        updated = claims.save_claim(payload, original['id'])
        self.assertEqual(updated['id'], original['id'])
        self.assertEqual(updated['createdAt'], original['createdAt'])
        self.assertEqual(updated['photos'], original['photos'])
        self.assertEqual(updated['reason'], 'Custom issue')
        self.assertEqual(claims.list_claims()['records'], [updated])

    def test_update_can_remove_and_add_photos_without_touching_other_claims(self):
        original = claims.save_claim(self.payload())
        other = claims.save_claim(self.payload())
        updated = claims.save_claim({**self.payload(), 'retainedPhotoIds': []}, original['id'])
        self.assertEqual(len(updated['photos']), 1)
        self.assertNotEqual(updated['photos'][0]['id'], original['photos'][0]['id'])
        self.assertIsNone(claims.get_photo(original['id'], original['photos'][0]['id']))
        self.assertIsNotNone(claims.get_photo(other['id'], other['photos'][0]['id']))
        before = claims.list_claims()
        with self.assertRaises(ValueError):
            claims.save_claim({**self.payload(), 'retainedPhotoIds': [other['photos'][0]['id']]}, original['id'])
        with self.assertRaises(ValueError):
            claims.save_claim({**self.payload(), 'photos': self.payload()['photos'] * 5}, original['id'])
        self.assertEqual(claims.list_claims(), before)
        with self.assertRaises(FileNotFoundError):
            claims.save_claim(self.payload(), 'a' * 32)

    def test_delete_removes_only_selected_claim_and_its_photos(self):
        first = claims.save_claim(self.payload())
        second = claims.save_claim(self.payload())
        self.assertTrue(claims.delete_claim(first['id']))
        self.assertFalse(claims.delete_claim(first['id']))
        self.assertIsNone(claims.get_photo(first['id'], first['photos'][0]['id']))
        self.assertEqual(claims.list_claims()['records'], [second])
        self.assertIsNotNone(claims.get_photo(second['id'], second['photos'][0]['id']))

    def test_invalid_fields_and_unknown_shops_do_not_create_records(self):
        for changes in ({'orderDate':'2026-02-30'}, {'originalOrderNo':' '}, {'replacementOrderNo':' '}, {'variantCode':''},
                        {'reason':'Other shop'}, {'reason':'Others','reasonOther':''},
                        {'solution':'Others','solutionOther':''}, {'sellingShop':'Made up shop'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                claims.save_claim({**self.payload(), **changes})
        self.assertEqual(claims.list_claims()['records'], [])

    def test_non_image_and_excess_uploads_are_rejected_atomically(self):
        photo = self.payload()['photos'][0]
        for photos in ([{'name':'fake.png','data':base64.b64encode(b'<script>alert(1)</script>').decode()}],
                       [{'name':'bad.jpg','data':'not-base64!'}], [photo] * 6):
            with self.subTest(photos=len(photos)), self.assertRaises(ValueError):
                claims.save_claim({**self.payload(), 'photos': photos})
        with patch.object(claims, 'MAX_PICTURE', len(PNG)-1), self.assertRaises(ValueError):
            claims.save_claim(self.payload())
        with patch.object(claims, 'MAX_TOTAL', len(PNG)-1), self.assertRaises(ValueError):
            claims.save_claim(self.payload())
        self.assertEqual(claims.list_claims()['records'], [])

    def test_optional_photos_and_replacement_number(self):
        payload = self.payload()
        payload.update(photos=[], solution='Replacement', replacementOrderNo='R-650001')
        result = claims.save_claim(payload)
        self.assertEqual(result['photos'], [])
        self.assertEqual(result['replacementOrderNo'], 'R-650001')

    def test_shop_allowlist_matches_tracking(self):
        import re
        source = (Path(__file__).resolve().parents[1] / 'src/ui.js').read_text(encoding='utf-8')
        stores = re.search(r'const PURCHASE_STORES = (\[[\s\S]*?\]);', source)[1]
        import ast
        self.assertEqual(set(ast.literal_eval(stores)), claims.STORES)


if __name__ == '__main__':
    unittest.main()
