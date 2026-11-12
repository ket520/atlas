import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import delivery_data
import sync_control
import sync_run_log


class GoogleSheetsDisconnectTests(unittest.TestCase):
    def test_sync_skips_all_sheet_readers(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1] / '.tmp-tests') as directory:
            with patch.dict(os.environ, {'ATLAS_GOOGLE_SHEETS_ENABLED': 'false'}), patch.object(
                delivery_data, 'configured_db_path', return_value=Path(directory) / 'isolated.sqlite3'
            ), patch.object(delivery_data, '_cache', {'at': None, 'payload': None}), patch.object(
                delivery_data, 'read_sales_activity_source', return_value=[]
            ), patch('google_sheets.get_spreadsheet') as spreadsheet, patch(
                'routine_live.read_live_snapshot'
            ) as routine, patch('palletways_live.sync_delta', return_value={'ok': True}), patch.object(
                delivery_data, 'apply_palletways_api_data', return_value=0
            ), patch.object(delivery_data, 'enrich_optimoroute_today', return_value=0), patch(
                'routine_dashboard.read_booking_rows', return_value=[]
            ):
                result = delivery_data.sync(force=True)
                spreadsheet.assert_not_called()
                routine.assert_not_called()
                self.assertEqual(len(result['disabledSources']), 7)
                self.assertIsNone(result['amazonShippingError'])
                self.assertNotIn('amazonShipping', result['sourceUpdatedAt'])

    def test_sheet_controls_and_logs_are_disconnected_without_reading(self):
        with patch.dict(os.environ, {'ATLAS_GOOGLE_SHEETS_ENABLED': 'false'}), patch(
            'google_sheets.get_spreadsheet'
        ) as spreadsheet:
            self.assertTrue(sync_control.read_snapshot()['disabled'])
            self.assertTrue(sync_run_log.read_snapshot()['disabled'])
            spreadsheet.assert_not_called()
