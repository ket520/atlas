from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import expressvpn_local as local


class ExpressVpnDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for name, value in [('_cached', None), ('running_clients', []),
                            ('installed_directories', []), ('drive_roots', [self.root])]:
            mock = patch.object(local, name, value) if name == '_cached' else patch.object(local, name, return_value=value)
            mock.start()
            self.addCleanup(mock.stop)
        mock = patch('shutil.which', return_value=None)
        mock.start()
        self.addCleanup(mock.stop)
        mock = patch.dict('os.environ', {'PROGRAMFILES': '', 'PROGRAMFILES(X86)': '', 'LOCALAPPDATA': ''})
        mock.start()
        self.addCleanup(mock.stop)
        mock = patch('expressvpn_local.Path.home', return_value=self.root)
        mock.start()
        self.addCleanup(mock.stop)

    def tool(self, folder):
        path = self.root / folder / 'expressvpnctl.exe'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return path

    def test_finds_moved_app_on_another_drive(self):
        tool = self.tool('arbitrary/nested/tools/VPN')
        self.assertEqual(local.find_cli(), tool)

    def test_downloads_are_checked_before_full_drive_scan(self):
        tool = self.tool('Downloads/my-vpn')
        with patch.object(local, 'search_tree', wraps=local.search_tree) as search:
            self.assertEqual(local.find_cli(), tool)
            self.assertEqual(search.call_count, 1)

    def test_running_installation_takes_priority(self):
        tool = self.tool('custom-install')
        with patch.object(local, 'running_clients', return_value=[tool.parent / 'expressvpn-client.exe']), patch.object(local, 'search_tree') as search:
            self.assertEqual(local.find_cli(), tool)
            search.assert_not_called()

    def test_missing_cached_path_is_rediscovered(self):
        first = self.tool('old')
        self.assertEqual(local.find_cli(), first)
        first.unlink()
        moved = self.tool('new')
        self.assertEqual(local.find_cli(), moved)

    def test_installer_is_not_selected(self):
        (self.root / 'expressvpn-installer.exe').touch()
        with self.assertRaisesRegex(RuntimeError, 'installer alone'):
            local.find_cli()

    def test_opens_desktop_client_next_to_discovered_tool(self):
        tool = self.tool('Downloads/custom-vpn')
        client = tool.parent / 'expressvpn-client.exe'
        client.touch()
        with patch('subprocess.Popen') as launch:
            local.ensure_client(tool)
            self.assertEqual(launch.call_args.args[0], [str(client)])


if __name__ == '__main__':
    unittest.main()
