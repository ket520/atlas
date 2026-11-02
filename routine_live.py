"""Read colour-based Own van status overrides from the live Google workbook."""
import re
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

TAB = 'Routine Dashboard - Live'
START = 'HYGIENIC ORDERS'
END = 'XDP - LONG PARCELS'
COLOUR_STATUS = {'#FFFF00': 'Failed', '#FFFFFF': 'Scheduled', '#FFC000': 'Scheduled'}


def format_booking_status(value, today=None):
    """Expand known shorthand; dates without a year use the current UK year."""
    today = today or datetime.now(ZoneInfo('Europe/London')).date()
    text = str(value or '').strip()
    months = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')

    def display(day, month, year):
        parsed = date(int(year), int(month), int(day))
        return f'{parsed.day}-{months[parsed.month - 1]}-{parsed.year}'

    days = {'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3, 'fri': 4, 'sat': 5, 'sun': 6}

    def delay(match):
        target = today + timedelta(days=(days[match[1][:3].lower()] - today.weekday()) % 7)
        return 'Delay to ' + display(target.day, target.month, target.year)

    text = re.sub(r'\bdel\s+(monday|mon|tuesday|tues|tue|wednesday|weds|wed|thursday|thurs|thur|thu|friday|fri|saturday|sat|sunday|sun)\b',
                  delay, text, flags=re.I)
    text = re.sub(r'\bo\s*/\s*s\b', 'Out of Stock', text, flags=re.I)
    text = re.sub(r'\bnd\b', 'ND', text, flags=re.I)

    def numeric(match):
        try:
            year = match[3] or today.year
            if len(str(year)) == 2:
                year = 2000 + int(year)
            return display(match[1], match[2], year)
        except ValueError:
            return match[0]

    text = re.sub(r'(?<![\d/\-])(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}|\d{2}))?(?![\d/\-])', numeric, text)

    def named(match):
        try:
            month = [m.lower() for m in months].index(match[2][:3].lower()) + 1
            year = int(match[3]) if match[3] else today.year
            if year < 100:
                year += 2000
            return display(match[1], month, year)
        except ValueError:
            return match[0]

    text = re.sub(r'\b(\d{1,2})[- ](Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:[- ](\d{4}|\d{2}))?\b', named, text, flags=re.I)
    return text[:1].upper() + text[1:]


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


def read_live_snapshot():
    from google_sheets import get_spreadsheet
    workbook = get_spreadsheet()
    values = workbook.worksheet(TAB).get_all_values()
    start, end = section_bounds(values)
    metadata = workbook.fetch_sheet_metadata(params={
        'includeGridData': 'true', 'ranges': f"'{TAB}'!A{start + 2}:A{end}",
        'fields': 'properties(spreadsheetTheme(themeColors)),sheets(properties(title),data(startRow,startColumn,rowData(values(formattedValue,effectiveFormat(backgroundColor,backgroundColorStyle)))))',
    })
    return {'statuses': status_rows(values, metadata), 'bookings': booking_rows(values)}


def read_status_rows():
    return read_live_snapshot()['statuses']
