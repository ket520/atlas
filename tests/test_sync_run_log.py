import unittest
from unittest.mock import Mock, patch

import sync_run_log


class SyncRunLogTests(unittest.TestCase):
    def test_fixed_columns_blank_counts_excluded_but_zero_retained(self):
        values = [['ID', 'Integration', 'Started At', 'Other', 'Other', 'Execution Result', 'Other', 'Records Inserted', 'Records Updated'],
                  ['1', 'Amazon', '22/10/2026 10:00', 'wrong', 'wrong', 'Success', 'wrong', '12', ''],
                  ['2', 'XDP', '22/10/2026 11:00', '', '', 'Success', '', '', '0'],
                  ['3', 'Skip', '22/10/2026 12:00', '', '', 'Failed', '', '  ', ''],
                  [], ['4', 'Skip short row'],
                  ['5', 'Skip zero counts', '', '', '', 'RETURNED', '', '0', '0'],
                  ['6', 'Skip zero and blank', '', '', '', 'RETURNED', '', '0', '']]
        self.assertEqual(sync_run_log.parse_rows(values), [
            {'integration': 'Amazon', 'startedAt': '22/10/2026 10:00', 'executionResult': 'Success', 'recordsInserted': '12', 'recordsUpdated': ''}])

    def test_cache_and_failure_keep_last_success_and_successful_empty_clears(self):
        workbook = Mock()
        sheet = workbook.worksheet.return_value
        sheet.get_all_values.return_value = [['header'], ['', 'Amazon', 'Today', '', '', 'OK', '', '0', 2]]
        with patch.object(sync_run_log, '_snapshot', None), patch.object(sync_run_log, '_checked', 0), \
             patch('google_sheets.get_spreadsheet', return_value=workbook), patch('sync_run_log.time.monotonic', side_effect=[1000, 1001, 1400, 1400, 1800, 1800]):
            first = sync_run_log.read_snapshot()
            self.assertFalse(first['unavailable'])
            self.assertEqual(sync_run_log.read_snapshot(), first)
            self.assertEqual(sheet.get_all_values.call_count, 1)
            sheet.get_all_values.side_effect = RuntimeError('unavailable')
            failed = sync_run_log.read_snapshot()
            self.assertTrue(failed['unavailable'])
            self.assertEqual(failed['rows'], first['rows'])
            sheet.get_all_values.side_effect = None
            sheet.get_all_values.return_value = []
            self.assertEqual(sync_run_log.read_snapshot()['rows'], [])
        workbook.worksheet.assert_called_with('_Sync_Run_Log')
