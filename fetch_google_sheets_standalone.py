"""Standalone fetch of the Routine Dashboard Google Sheet ONLY.

Place beside Atlas-Admin's database folder. No app imports or PostgreSQL writes.
Install: python -m pip install "gspread>=6.2,<7" "google-auth>=2,<3"
Run: python fetch_google_sheets_standalone.py
Credentials: credentials/google_service_account.json beside this file, or
--credentials PATH (also supports GOOGLE_APPLICATION_CREDENTIALS).
Output: routine_dashboard_export.json, or --output PATH.

Reads only 'Routine Dashboard - Live', between HYGIENIC ORDERS and
XDP - LONG PARCELS. Column A supplies order references and status colours;
column E supplies booking text verbatim. Yellow = Failed; white/orange =
Scheduled. Other colours have no status override. Includes raw section rows
and formatting for the other bot to inspect. No source data is changed.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SHEET_ID = "1F2DnKdPEm-LdxM1Ag6hTcvP7a8glhnESl9m7-UlvNcs"
TAB = "Routine Dashboard - Live"
START = "HYGIENIC ORDERS"
END = "XDP - LONG PARCELS"
COLOUR_STATUS = {"#FFFF00": "Failed", "#FFFFFF": "Scheduled", "#FFC000": "Scheduled"}

def create_client(credentials_path):
    """Authenticate with read-only Sheets access; no app modules are needed."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        from gspread.http_client import BackOffHTTPClient
    except ImportError as exc:
        raise RuntimeError(
            'Install dependencies: python -m pip install "gspread>=6.2,<7" '
            '"google-auth>=2,<3"'
        ) from exc
    credentials = Credentials.from_service_account_file(
        str(credentials_path),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
    )
    client = gspread.authorize(credentials, http_client=BackOffHTTPClient)
    client.set_timeout(60)
    return client


def order_numbers(value):
    """Each line identifies one order; composite references keep only its first six digits."""
    result = []
    for line in str(value or '').splitlines():
        match = re.search(r'\d{6}', line)
        if match and match[0] not in result:
            result.append(match[0])
    return result


def section_bounds(values):
    def marker(row):
        return ' '.join(str(row[0] if row else '').split()).upper()
    starts = [i for i, row in enumerate(values) if marker(row) == START]
    if len(starts) != 1:
        raise ValueError('Routine Dashboard - Live needs exactly one HYGIENIC ORDERS marker in column A.')
    ends = [i for i, row in enumerate(values) if i > starts[0] and marker(row) == END]
    if not ends:
        raise ValueError('Routine Dashboard - Live has no XDP - Long Parcels marker after HYGIENIC ORDERS.')
    if ends[0] == starts[0] + 1:
        raise ValueError('Routine Dashboard - Live section is empty; previous overrides retained.')
    return starts[0], ends[0]


def background_hex(cell, themes):
    fmt = cell.get('effectiveFormat', {})
    style = fmt.get('backgroundColorStyle', {})
    if 'rgbColor' in style:
        rgb = style['rgbColor']
    elif 'themeColor' in style:
        rgb = themes.get(style['themeColor'], {}).get('rgbColor')
        if rgb is None:
            return ''  # An unresolved theme is not evidence of a white cell.
    else:
        rgb = fmt.get('backgroundColor', {'red': 1, 'green': 1, 'blue': 1})
    return '#' + ''.join(f'{max(0, min(255, round(rgb.get(name, 0) * 255))):02X}'
                         for name in ('red', 'green', 'blue'))


def status_rows(values, metadata):
    start, end = section_bounds(values)
    themes = {pair['colorType']: pair.get('colorStyle', {}) for pair in
              metadata.get('properties', {}).get('spreadsheetTheme', {}).get('themeColors', [])}
    sheets = [sheet for sheet in metadata.get('sheets', []) if sheet.get('properties', {}).get('title') == TAB]
    if len(sheets) != 1 or not sheets[0].get('data'):
        raise ValueError('Routine Dashboard - Live formatting data is unavailable; previous overrides retained.')
    cells = {}
    for grid in sheets[0]['data']:
        if grid.get('startColumn', 0) != 0:
            continue
        for offset, row in enumerate(grid.get('rowData', [])):
            index = grid.get('startRow', 0) + offset
            if row.get('values'):
                cells[index] = row['values'][0]
    result = []
    for index in range(start + 1, end):
        cell = cells.get(index, {})
        text = str(cell.get('formattedValue', values[index][0] if values[index] else '')).strip()
        orders = order_numbers(text)
        if not orders:
            continue
        if index not in cells:
            raise ValueError('Routine Dashboard - Live order-cell formatting is incomplete; previous overrides retained.')
        colour = background_hex(cell, themes)
        status = COLOUR_STATUS.get(colour)
        if status:
            result.extend({'order': order, 'status': status, 'colour': colour, 'cell': f'A{index + 1}'}
                          for order in orders)
    return result


def booking_rows(values):
    """Column E is displayed verbatim, independent of the status colour."""
    start, end = section_bounds(values)
    result = []
    for index in range(start + 1, end):
        row = values[index]
        orders = order_numbers(row[0] if row else '')
        if orders:
            value = row[4] if len(row) > 4 and row[4] is not None else ''
            result.extend({'order': order, 'bookingStatus': str(value).strip(), 'cell': f'E{index + 1}'}
                          for order in orders)
    return result


def write_json_atomic(destination, payload):
    """Replace the output only after a complete successful fetch and JSON write."""
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=destination.parent,
            prefix=destination.name + ".", suffix=".tmp", delete=False,
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temporary, destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def fetch_routine_dashboard(client):
    book = client.open_by_key(SHEET_ID)
    values = book.worksheet(TAB).get_all_values(value_render_option="FORMATTED_VALUE")
    start, end = section_bounds(values)
    metadata = book.fetch_sheet_metadata(params={
        "includeGridData": "true",
        "ranges": f"'{TAB}'!A{start + 2}:A{end}",
        "fields": "properties(spreadsheetTheme(themeColors)),sheets(properties(title),data(startRow,startColumn,rowData(values(formattedValue,effectiveFormat(backgroundColor,backgroundColorStyle)))))",
    })
    return {
        "format_version": 1,
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "spreadsheet_id": SHEET_ID,
        "tab": TAB,
        "section": {"start_marker": START, "end_marker": END},
        "statuses": status_rows(values, metadata),
        "bookings": booking_rows(values),
        "source_rows": [
            {"sheet_row": i + 1, "values": values[i]}
            for i in range(start + 1, end)
        ],
        "source_formatting": metadata,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--credentials", type=Path, default=Path(
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or ROOT / "credentials" / "google_service_account.json"
    ))
    parser.add_argument("--output", type=Path, default=ROOT / "routine_dashboard_export.json")
    args = parser.parse_args()
    try:
        payload = fetch_routine_dashboard(create_client(args.credentials))
        write_json_atomic(args.output, payload)
        print(f"Saved {len(payload['bookings'])} booking records and "
              f"{len(payload['statuses'])} status overrides: {args.output.resolve()}")
        return 0
    except Exception as exc:
        print(f"Routine dashboard fetch failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
