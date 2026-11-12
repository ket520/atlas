import unittest
import threading
from unittest.mock import Mock, patch

import palletways_portal as portal


class PalletwaysMediaTests(unittest.TestCase):
    def test_browser_is_reused_on_one_worker_for_different_orders_and_media(self):
        context, manager = Mock(), Mock()
        context.browser.is_connected.return_value = True
        context.pages = [Mock()]
        context.request.get.return_value.ok = True
        context.request.get.return_value.body.return_value = b'image'
        context.request.get.return_value.headers = {'content-type': 'image/jpeg'}
        threads = []
        def source(current, url):
            self.assertIs(current, context)
            threads.append(threading.get_ident())
            return 'Consignment Notes'
        with patch.object(portal, '_browser_context', None), patch.object(portal, '_browser_playwright', None), patch.dict(
            portal.CACHE, {}, clear=True
        ), patch.object(portal, 'sync_playwright', return_value=manager), patch.object(
            portal, '_open_context', return_value=context
        ) as launch, patch.object(portal, '_tracking_source', side_effect=source):
            portal.portal_details('60000000001')
            portal.portal_details('60000000002')
            self.assertEqual(portal.portal_media('photo.jpg'), (b'image', 'image/jpeg'))
            launch.assert_called_once_with(manager.start.return_value, headless=False)
            context.close.assert_not_called()
            self.assertEqual(len(set(threads)), 1)
            self.assertNotEqual(threads[0], threading.get_ident())

    def test_expired_session_opens_login_tab_and_waits_for_sign_in(self):
        context = Mock()
        page = Mock()
        context.pages = [page]
        page.is_closed.return_value = False
        page.content.return_value = '<form>Sign in</form>'
        login, authenticated = Mock(), Mock()
        login.ok = authenticated.ok = True
        login.text.return_value = '<form>Sign in</form>'
        authenticated.text.return_value = '<h2>Consignment Notes</h2>'
        context.request.get.side_effect = [login, login, authenticated]
        with patch.object(portal, '_submit_saved_login', return_value=True) as submit:
            source = portal._tracking_source(context, 'https://portal.palletways.com/cwp/tt.php?dc_syscon=60000000001')
        submit.assert_called_once_with(page)
        self.assertIn('Consignment Notes', source)
        page.goto.assert_called_once()
        self.assertEqual(page.wait_for_timeout.call_count, 2)
        context.close.assert_not_called()

    def test_authenticated_session_does_not_prompt_for_login(self):
        context = Mock()
        context.request.get.return_value.ok = True
        context.pages = [Mock()]
        context.request.get.return_value.text.return_value = 'Palletways Tracking ID'
        self.assertEqual(portal._tracking_source(context, 'tracking-url'), 'Palletways Tracking ID')
        context.new_page.assert_not_called()
        context.pages[0].goto.assert_called_once_with('tracking-url', wait_until='domcontentloaded', timeout=30000)

    def test_closed_login_window_reports_retry(self):
        context = Mock()
        page = Mock()
        context.pages = [page]
        page.is_closed.return_value = True
        context.request.get.return_value.text.return_value = 'Sign in'
        with self.assertRaisesRegex(RuntimeError, 'closed before sign-in'):
            portal._tracking_source(context, 'tracking-url')

    def test_discovers_photos_outside_six_column_notes(self):
        source = '''<table><tr><td><a href="show_pod.php?fullsize=true&amp;file=shipment-one.jpg">Photo</a></td></tr></table>
          <img src="show_pod.php?file=shipment-two%2Epng&amp;fullsize=true">
          <a href="show_pod.php?file=signature.tiff">Signature</a>
          <a href="show_pod.php?file=../../invalid.jpg">invalid</a>'''
        media = portal._extract_media(portal._extract_notes(source), source)
        self.assertEqual([item['filename'] for item in media], ['shipment-one.jpg', 'shipment-two.png', 'signature.tiff'])

    def test_note_metadata_is_retained_and_files_are_deduplicated(self):
        notes = [{'type': 'POD', 'files': ['one.jpg', 'one.jpg'], 'date': '2026-10-20', 'time': '10:00', 'number': '17'}]
        media = portal._extract_media(notes, '<a href="show_pod.php?file=one.jpg">Photo</a>')
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]['noteNumber'], '17')

    def test_normal_lookup_uses_cache_but_explicit_refresh_bypasses_it(self):
        with patch.dict(portal.CACHE, {'60050728153': {'time': 100, 'data': {'ok': True, 'media': []}}}, clear=True), patch(
            'palletways_portal.time.time', return_value=101
        ), patch('palletways_portal._browser_call', side_effect=RuntimeError('browser attempted')):
            self.assertEqual(portal.portal_details('60050728153')['media'], [])
            with self.assertRaisesRegex(RuntimeError, 'browser attempted'):
                portal.portal_details('60050728153', force=True)
