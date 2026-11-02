"""Read workbook trigger settings and estimate their next run without changing triggers."""
from datetime import datetime, timedelta, timezone
import re
import threading
import time
from zoneinfo import ZoneInfo

_lock = threading.Lock()
_snapshot = None
_checked = 0


def parse_time(value, zone):
    raw = str(value or '').strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace('Z', '+00:00'))
    except ValueError:
        parsed = None
        for fmt in ('%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%d/%m/%Y %I:%M:%S %p',
                    '%d/%m/%Y %I:%M %p', '%d-%b-%Y %H:%M:%S', '%d-%b-%Y %H:%M'):
            try:
                parsed = datetime.strptime(raw, fmt)
                break
            except ValueError:
                continue
    return parsed.replace(tzinfo=zone) if parsed and parsed.tzinfo is None else parsed


def parse_rows(values, log_values, timezone_name):
    zone = ZoneInfo(timezone_name)
    latest = {}
    for row in log_values[1:]:
        if len(row) > 2:
            key = str(row[1]).strip().casefold()
            at = parse_time(row[2], zone)
            if at and (key not in latest or at > latest[key]):
                latest[key] = at
    result = []
    for row in values[1:]:
        def cell(index):
            return str(row[index]).strip() if len(row) > index and row[index] is not None else ''
        name, frequency, status, applied = cell(0), cell(2), cell(5), cell(6)
        if not name:
            continue
        try:
            minutes = float(frequency)
            if not 0 < minutes <= 525600:
                minutes = None
        except ValueError:
            minutes = None
        disabled = not status or bool(re.search(r'\b(disabled|inactive|off|stopped|paused|deleted|false|not installed|not applied)\b', status, re.I))
        last_run = latest.get(name.casefold())
        base = last_run or parse_time(applied, zone)
        next_run = base + timedelta(minutes=minutes) if base and minutes and not disabled else None
        result.append({'integration': name, 'frequencyMinutes': frequency, 'triggerStatus': status,
                       'lastApplied': applied, 'nextRunAt': next_run.isoformat() if next_run else None,
                       'estimateBasis': 'lastRun' if last_run else 'lastApplied', 'disabled': disabled})
    return result


def read_snapshot():
    global _snapshot, _checked
    with _lock:
        if _snapshot is not None and time.monotonic() - _checked < 60:
            return _snapshot
        try:
            from google_sheets import get_spreadsheet
            workbook = get_spreadsheet()
            zone = workbook.fetch_sheet_metadata(params={'fields': 'properties(timeZone)'})['properties']['timeZone']
            values = workbook.worksheet('_Sync_Control').get_all_values()
            logs = workbook.worksheet('_Sync_Run_Log').get_all_values()
            _snapshot = {'rows': parse_rows(values, logs, zone), 'unavailable': False,
                         'timezone': zone, 'updatedAt': datetime.now(timezone.utc).isoformat()}
        except Exception:
            _snapshot = {**(_snapshot or {'rows': [], 'updatedAt': None}), 'unavailable': True}
        _checked = time.monotonic()
        return _snapshot
