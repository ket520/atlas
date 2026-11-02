import unittest
from unittest.mock import Mock, patch

import sync_control


class SyncControlTests(unittest.TestCase):
    def test_columns_frequency_latest_run_and_disabled(self):
        values = [['Integration', 'Other', 'Frequency', 'Other', 'Other', 'Status', 'Last Applied'],
                  ['XDP', 'wrong', '10', '', '', 'ACTIVE', '22/10/2026 08:00'],
                  ['Amazon', '', '5', '', '', 'DISABLED', '22/10/2026 08:00'],
                  ['Fallback', '', '15', '', '', 'Installed', '22/10/2026 08:00'],
                  ['Unknown date', '', '5', '', '', 'ACTIVE', 'not a date'],
                  ['Invalid frequency', '', 'bad', '', '', 'ACTIVE', '22/10/2026 08:00'], []]
        logs = [['ID', 'Integration', 'Started At'],
                ['', 'xdp', '22/10/2026 09:00'], ['', 'XDP', '22/10/2026 08:30']]
        rows = sync_control.parse_rows(values, logs, 'Europe/London')
        self.assertEqual(len(rows), 5)
        self.assertEqual(rows[0]['nextRunAt'], '2026-10-22T09:10:00+01:00')
        self.assertEqual(rows[0]['estimateBasis'], 'lastRun')
        self.assertEqual(rows[0]['lastApplied'], '22/10/2026 08:00')
        self.assertTrue(rows[1]['disabled'])
        self.assertIsNone(rows[1]['nextRunAt'])
        self.assertEqual(rows[2]['nextRunAt'], '2026-10-22T08:15:00+01:00')
        self.assertEqual(rows[2]['estimateBasis'], 'lastApplied')
        self.assertIsNone(rows[3]['nextRunAt'])
        self.assertIsNone(rows[4]['nextRunAt'])

    def test_live_read_uses_same_workbook_and_preserves_failed_snapshot(self):
        workbook = Mock()
        workbook.fetch_sheet_metadata.return_value = {'properties': {'timeZone': 'Europe/London'}}
        workbook.worksheet.return_value.get_all_values.return_value = [['header'], ['XDP', '', '10', '', '', 'ACTIVE', '2026-10-22T09:00:00Z']]
        with patch.object(sync_control, '_snapshot', None), patch.object(sync_control, '_checked', 0), \
             patch('google_sheets.get_spreadsheet', return_value=workbook), \
             patch('sync_control.time.monotonic', side_effect=[1000, 1100, 1100]):
            first = sync_control.read_snapshot()
            self.assertFalse(first['unavailable'])
            self.assertEqual(first['rows'][0]['nextRunAt'], '2026-10-22T09:10:00+00:00')
            workbook.worksheet.side_effect = RuntimeError('unavailable')
            second = sync_control.read_snapshot()
            self.assertTrue(second['unavailable'])
            self.assertEqual(first['rows'], second['rows'])
        self.assertIn(('_Sync_Control',), [call.args for call in workbook.worksheet.call_args_list])
