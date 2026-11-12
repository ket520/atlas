"""Read-only, short-lived cache of the Sales Activity workbook's sync log."""
from datetime import datetime, timezone
import threading
import time
from atlas_config import google_sheets_enabled

TAB = '_Sync_Run_Log'
_lock = threading.Lock()
_snapshot = None
_checked = 0


def parse_rows(values):
    rows = []
    for row in values[1:]:
        def cell(index):
            return str(row[index]).strip() if len(row) > index and row[index] is not None else ''
        inserted, updated = cell(7), cell(8)
        if not inserted and not updated:
            continue
        def zero_or_blank(value):
            try:
                return not value or float(value.replace(',', '')) == 0
            except ValueError:
                return False
        if zero_or_blank(inserted) and zero_or_blank(updated):
            continue
        rows.append({'integration': cell(1), 'startedAt': cell(2),
                     'executionResult': cell(5), 'recordsInserted': inserted,
                     'recordsUpdated': updated})
    return list(reversed(rows))


def read_snapshot():
    global _snapshot, _checked
    if not google_sheets_enabled():
        return {'rows': [], 'updatedAt': None, 'unavailable': False, 'disabled': True}
    with _lock:
        if _snapshot is not None and time.monotonic() - _checked < 300:
            return _snapshot
        try:
            from google_sheets import get_spreadsheet
            values = get_spreadsheet().worksheet(TAB).get_all_values()
            _snapshot = {'rows': parse_rows(values), 'unavailable': False,
                         'updatedAt': datetime.now(timezone.utc).isoformat()}
        except Exception:
            # A failed read must not replace a last good log with an empty table.
            _snapshot = {**(_snapshot or {'rows': [], 'updatedAt': None}), 'unavailable': True}
        _checked = time.monotonic()
        return _snapshot
