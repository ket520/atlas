param(
    [string]$PythonPath,
    [ValidatePattern('^(#[0-9A-Fa-f]{6})?$')][string]$YellowHex
)

$ErrorActionPreference = 'Stop'
if (-not $PythonPath) {
    $pythonInstallRoot = Join-Path $env:LOCALAPPDATA 'Python'
    $pythonInstall = Get-ChildItem -LiteralPath $pythonInstallRoot -Directory -Filter 'pythoncore-*' -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending | Where-Object { Test-Path -LiteralPath (Join-Path $_.FullName 'python.exe') } |
        Select-Object -First 1
    if ($pythonInstall) {
        $PythonPath = Join-Path $pythonInstall.FullName 'python.exe'
    } else {
        $PythonPath = (Get-Command python -ErrorAction Stop).Source
    }
}

Push-Location -LiteralPath $PSScriptRoot
try {
    @'
import sys
from collections import Counter
from google_sheets import get_spreadsheet

TAB = 'Routine Dashboard - Live'
START = 'HYGIENIC ORDERS'
END = 'XDP - LONG PARCELS'

def marker(row):
    return ' '.join(str(row[0] if row else '').split()).upper()

try:
    workbook = get_spreadsheet()
    worksheet = workbook.worksheet(TAB)
    rows = worksheet.get_all_values()
except Exception as error:
    print(f'Could not read Google Sheets ({type(error).__name__}).', flush=True)
    print('Check internet access and service-account access to Routine Dashboard - Live.')
    sys.exit(2)

starts = [index for index, row in enumerate(rows) if marker(row) == START]
ends = [index for index, row in enumerate(rows) if marker(row) == END]
if len(starts) != 1:
    print(f'Expected one {START} marker in column A; found {len(starts)} at rows {[i + 1 for i in starts]}.')
    sys.exit(3)
start = starts[0]
following_ends = [index for index in ends if index > start]
if not following_ends:
    print(f'No {END} marker found after {START} at row {start + 1}.')
    sys.exit(3)
end = following_ends[0]
section = rows[start + 1:end]
nonempty = sum(any(str(cell).strip() for cell in row) for row in section)
print(f'Tab: {worksheet.title}')
print(f'Total populated sheet extent: {len(rows)} rows')
print(f'Start marker: A{start + 1} = {START}')
print(f'End marker: A{end + 1} = {END}')
print(f'Rows between markers (markers excluded): {len(section)}')
print(f'Non-empty rows between markers: {nonempty}')
print(f'Blank rows between markers: {len(section) - nonempty}')
if section:
    print(f'Included sheet rows: {start + 2} through {end}')
print('This is a section-row count, including any internal headings or totals; not a confirmed order count.')

def column_name(number):
    result = ''
    while number:
        number, digit = divmod(number - 1, 26)
        result = chr(65 + digit) + result
    return result

if section:
    width = max((len(row) for row in rows), default=1)
    area = f"'{TAB}'!A{start + 2}:{column_name(width)}{end}"
    try:
        metadata = workbook.fetch_sheet_metadata(params={
            'includeGridData': 'true', 'ranges': area,
            'fields': 'properties(spreadsheetTheme(themeColors)),sheets(properties(title),data(startRow,startColumn,rowData(values(formattedValue,effectiveFormat(backgroundColor,backgroundColorStyle)))))',
        })
    except Exception as error:
        print(f'Could not read cell background colours ({type(error).__name__}).')
        sys.exit(4)
    themes = {pair['colorType']: pair.get('colorStyle', {}) for pair in
              metadata.get('properties', {}).get('spreadsheetTheme', {}).get('themeColors', [])}

    def rgb_style(style):
        if 'rgbColor' in style:
            return style['rgbColor']
        return themes.get(style.get('themeColor'), {}).get('rgbColor')

    colours = Counter()
    filled_colours = Counter()
    colour_rows = {}
    first_cells = {}
    for sheet in metadata.get('sheets', []):
        if sheet.get('properties', {}).get('title') != TAB:
            continue
        for grid in sheet.get('data', []):
            for row_offset, row in enumerate(grid.get('rowData', [])):
                actual_row = grid.get('startRow', start + 1) + row_offset
                if not start < actual_row < end:
                    continue
                for column_offset, cell in enumerate(row.get('values', [])):
                    if grid.get('startColumn', 0) + column_offset >= width:
                        continue
                    fmt = cell.get('effectiveFormat', {})
                    rgb = rgb_style(fmt.get('backgroundColorStyle', {}))
                    if rgb is None:
                        rgb = fmt.get('backgroundColor', {'red': 1, 'green': 1, 'blue': 1})
                    if rgb.get('alpha', 1) == 0:
                        continue
                    channels = tuple(max(0, min(255, round(rgb.get(name, 0) * 255))) for name in ('red', 'green', 'blue'))
                    hex_code = '#' + ''.join(f'{channel:02X}' for channel in channels)
                    if hex_code == '#FFFFFF':
                        continue
                    colours[hex_code] += 1
                    filled_colours[hex_code] += bool(str(cell.get('formattedValue', '')).strip())
                    colour_rows.setdefault(hex_code, set()).add(actual_row + 1)
                    position = (actual_row + 1, grid.get('startColumn', 0) + column_offset + 1)
                    if hex_code not in first_cells or position < first_cells[hex_code]:
                        first_cells[hex_code] = position
    exact = sys.argv[1].upper() if len(sys.argv) > 1 and sys.argv[1] else ''
    def yellow_like(hex_code):
        return hex_code in {'#FFFF00', '#FFC000'}
    selected = [exact] if exact else [colour for colour in colours if yellow_like(colour)]
    print(f'Colour-count range: {area}')
    print('Colour rules: effective background fill, including conditional formatting; marker rows excluded.')
    print(f'Yellow matching: {exact}' if exact else 'Yellow matching: #FFFF00 and #FFC000 only; #FFE598 ignored.')
    print(f'Yellow cells (including blank cells): {sum(colours[colour] for colour in selected)}')
    print(f'Yellow cells containing data: {sum(filled_colours[colour] for colour in selected)}')
    affected_rows = set().union(*(colour_rows.get(colour, set()) for colour in selected)) if selected else set()
    print(f'Rows with yellow cells: {len(affected_rows)}')
    print('Background colours found (white/default excluded):')
    for colour, count in colours.most_common():
        if colour == '#FFE598':
            continue
        tag = ' [yellow match]' if colour in selected else ''
        print(f'  {colour}: {count} cells; {filled_colours[colour]} containing data; {len(colour_rows[colour])} rows{tag}')
    print('First encounter for each yellow shade (column A value on the same row):')
    for colour in selected:
        if colour not in first_cells:
            continue
        row_number, column_number = first_cells[colour]
        source_row = rows[row_number - 1] if row_number <= len(rows) else []
        first_value = str(source_row[0]).strip() if source_row else ''
        address = f'{column_name(column_number)}{row_number}'
        print(f'  {colour}: first yellow cell {address}; A{row_number} = {first_value!r}')
    from routine_live import status_rows
    candidates = status_rows(rows, metadata)
    statuses = {}
    for candidate in candidates:
        if candidate['order'] not in statuses or candidate['status'] == 'Failed':
            statuses[candidate['order']] = candidate['status']
    print('Routine status preview: column A only, first six digits per line; sheet candidates before Own van matching.')
    print(f"  Failed (#FFFF00): {sum(status == 'Failed' for status in statuses.values())} unique order numbers")
    print(f"  Scheduled (#FFFFFF / #FFC000): {sum(status == 'Scheduled' for status in statuses.values())} unique order numbers")
    print(f'  Total: {len(statuses)} unique order numbers; duplicate Failed entries take priority.')
print('Read only: no sheet, database or status changes made.')
'@ | & $PythonPath - $YellowHex
    $commandExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $commandExitCode
