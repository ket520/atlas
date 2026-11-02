import threading
import unittest
from unittest.mock import MagicMock, patch

import bq_vpn
from server import Handler


class BqVpnTests(unittest.TestCase):
    def test_vpn_connects_before_browser_and_disconnects_after_exit(self):
        calls = []
        process = MagicMock()
        process.poll.return_value = None
        process.wait.side_effect = lambda: calls.append('close')
        def vpn(*args):
            calls.append(args[0])
            return 'Connected'
        def launch(command):
            calls.append('launch')
            return process
        ready = threading.Event()
        with patch.object(bq_vpn, 'vpn', side_effect=vpn), patch.object(bq_vpn, 'browser_command', return_value=['chrome']), patch('subprocess.Popen', side_effect=launch), patch('time.sleep'):
            bq_vpn._session(ready)
        self.assertEqual(calls, ['connect', 'get', 'launch', 'close', 'disconnect'])
        self.assertTrue(ready.is_set())
        self.assertFalse(bq_vpn._active)

    def test_launch_failure_disconnects_vpn(self):
        with patch.object(bq_vpn, 'vpn', return_value='Connected') as vpn, patch.object(bq_vpn, 'browser_command', return_value=['chrome']), patch('subprocess.Popen', side_effect=OSError('Browser unavailable')), patch('logging.exception'):
            bq_vpn._session(threading.Event())
        self.assertEqual(vpn.call_args_list[-1].args, ('disconnect',))
        self.assertEqual(bq_vpn._error, 'Browser unavailable')

    def test_browser_exits_immediately_reports_error(self):
        process = MagicMock()
        process.poll.return_value = 1
        with patch.object(bq_vpn, 'vpn', return_value='Connected') as vpn, patch.object(bq_vpn, 'browser_command', return_value=['chrome']), patch('subprocess.Popen', return_value=process), patch('time.sleep'), patch('logging.exception'):
            bq_vpn._session(threading.Event())
        self.assertIn('could not stay open', bq_vpn._error)
        self.assertEqual(vpn.call_args_list[-1].args, ('disconnect',))

    def test_repeated_click_does_not_start_another_session(self):
        with patch.object(bq_vpn, '_active', True), patch('threading.Thread') as thread:
            self.assertIn('Connecting', bq_vpn.open_bq()['message'])
            thread.assert_not_called()

    def test_remote_origin_cannot_control_vpn(self):
        handler = MagicMock()
        handler.path = '/api/bq/open'
        handler.client_address = ('127.0.0.1', 12345)
        handler.headers = {'Origin': 'https://example.com', 'Host': '127.0.0.1:3000',
                           'X-DeliveryDesk-Action': 'open-bq'}
        with patch.object(bq_vpn, 'open_bq') as open_bq:
            Handler.do_POST(handler)
            open_bq.assert_not_called()
        self.assertEqual(handler.send_json.call_args.args[0], 403)

    def test_existing_session_opens_visible_window_without_reconnecting(self):
        browser = MagicMock()
        browser.poll.return_value = None
        with patch.object(bq_vpn, '_active', True), patch.object(bq_vpn, '_browser', browser), patch.object(bq_vpn, 'browser_command', return_value=['chrome']), patch('subprocess.Popen') as launch, patch.object(bq_vpn, 'vpn') as vpn:
            self.assertIn('dedicated Chrome', bq_vpn.open_bq()['message'])
            launch.assert_called_once_with(['chrome'])
            vpn.assert_not_called()

    def test_local_button_opens_session(self):
        handler = MagicMock()
        handler.path = '/api/bq/open'
        handler.client_address = ('127.0.0.1', 12345)
        handler.headers = {'Origin': 'http://127.0.0.1:3000', 'Host': '127.0.0.1:3000',
                           'X-DeliveryDesk-Action': 'open-bq'}
        with patch.object(bq_vpn, 'open_bq', return_value={'message': 'opened'}) as open_bq:
            Handler.do_POST(handler)
            open_bq.assert_called_once()
        self.assertEqual(handler.send_json.call_args.args[0], 200)


if __name__ == '__main__':
    unittest.main()
