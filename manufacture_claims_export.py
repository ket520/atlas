"""Export the displayed manufacturing claims table without changing its data."""
import base64
import io
import math
import re
import textwrap
from html import escape

from collection_export import EXPORT_SLOTS, MIME_TYPES
from manufacture_claims import get_photo


def validate(payload):
    if not isinstance(payload, dict) or payload.get('format') not in MIME_TYPES:
        raise ValueError('Choose XLSX or PDF.')
    columns, widths, rows = (payload.get(key) for key in ('columns', 'widths', 'rows'))
    if not isinstance(columns, list) or len(columns) != 8 or any(not isinstance(value, str) or not value.strip() or len(value) > 200 for value in columns):
        raise ValueError('Refresh the claims table before downloading.')
    if not isinstance(widths, list) or len(widths) != 8 or any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 20 <= value <= 2000 for value in widths):
        raise ValueError('Invalid table column widths.')
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError('Download up to 10,000 claims at a time.')
    for row in rows:
        if not isinstance(row, dict) or not re.fullmatch(r'[a-f0-9]{32}', str(row.get('id', ''))):
            raise ValueError('Invalid claim row.')
        cells, photos = row.get('cells'), row.get('photos')
        if not isinstance(cells, list) or len(cells) != 8 or any(not isinstance(value, str) or len(value) > 10000 for value in cells):
            raise ValueError('Invalid claim values.')
        if not isinstance(photos, list) or len(photos) > 5 or any(not isinstance(value, str) or not re.fullmatch(r'[a-f0-9]{32}', value) for value in photos):
            raise ValueError('Invalid claim pictures.')
    return payload


def thumbnails(table):
    from PIL import Image, ImageOps

    photos = {}
    for index, row in enumerate(table['rows']):
        for photo_id in row['photos']:
            photo = get_photo(row['id'], photo_id)
            if not photo:
                raise ValueError('A picture is no longer available. Refresh the table and retry.')
            try:
                with Image.open(io.BytesIO(photo[0])) as source:
                    source.seek(0)
                    image = ImageOps.pad(ImageOps.exif_transpose(source).convert('RGBA'), (280, 280), color=(255, 255, 255, 0))
                    output = io.BytesIO()
                    image.save(output, format='PNG')
                    photos.setdefault(index, []).append(output.getvalue())
            except (OSError, ValueError):
                raise ValueError('A saved picture could not be exported. Check the picture and retry.') from None
    return photos


def xlsx_file(table, photos):
    from openpyxl import Workbook
    from openpyxl.drawing.image import Image
    from openpyxl.drawing.spreadsheet_drawing import AnchorMarker, OneCellAnchor
    from openpyxl.drawing.xdr import XDRPositiveSize2D
    from openpyxl.styles import Alignment, Border, Font, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.utils.units import pixels_to_EMU

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = 'Manufacturing Claims'
    sheet.sheet_view.showGridLines = True
    border = Side(style='thin', color='D9D9D9')
    headings = ['Order Date', 'Original Order Date', 'Replacement Order Date', 'VariantCode', 'Reason', 'Solution', 'Shop / Selling\nPlatform', 'Photos']
    widths = [190, 216, 307, 285, 190, 101, 157, 320]
    for index, (heading, width) in enumerate(zip(headings, widths), 1):
        sheet.column_dimensions[get_column_letter(index)].width = max(3, (width - 5) / 7)
        cell = sheet.cell(1, index, heading)
        cell.data_type = 's'
        cell.font = Font(name='Arial', size=11, bold=True, color='000000')
        cell.border = Border(left=border, right=border, top=border, bottom=border)
        cell.alignment = Alignment(vertical='top', wrap_text=True)
    sheet.row_dimensions[1].height = 31
    picture_size, picture_gap, picture_padding = 140, 12, 12
    per_line = max(1, int((widths[7] - picture_padding * 2 + picture_gap) // (picture_size + picture_gap)))
    for index, row in enumerate(table['rows']):
        row_index = index + 2
        height = 150
        for column, (value, width) in enumerate(zip(row['cells'], widths), 1):
            cell = sheet.cell(row_index, column, value)
            # Preserve order numbers/leading zeroes and treat formula-like text literally.
            cell.data_type = 's'
            cell.font = Font(name='Arial', size=10, color='000000')
            cell.border = Border(left=border, right=border, top=border, bottom=border)
            cell.alignment = Alignment(vertical='bottom', wrap_text=True)
            lines = sum(max(1, len(textwrap.wrap(line, max(1, int((width - 24) / 6))))) for line in value.split('\n'))
            height = max(height, lines * 16 + 26)
        pictures = photos.get(index, [])
        if pictures:
            height = max(height, math.ceil(len(pictures) / per_line) * (picture_size + picture_gap) - picture_gap + picture_padding * 2)
        sheet.row_dimensions[row_index].height = min(409.5, height * .75)
        for number, content in enumerate(pictures):
            image = Image(io.BytesIO(content))
            image.width = image.height = picture_size
            image.anchor = OneCellAnchor(
                _from=AnchorMarker(col=7, row=row_index - 1,
                                   colOff=pixels_to_EMU(picture_padding + number % per_line * (picture_size + picture_gap)),
                                   rowOff=pixels_to_EMU(picture_padding + number // per_line * (picture_size + picture_gap))),
                ext=XDRPositiveSize2D(pixels_to_EMU(picture_size), pixels_to_EMU(picture_size)))
            sheet.add_image(image)
    sheet.freeze_panes = 'A2'
    sheet.auto_filter.ref = f'A1:H{max(1, len(table["rows"]) + 1)}'
    sheet.print_title_rows = '1:1'
    sheet.print_area = sheet.auto_filter.ref
    sheet.page_setup.orientation = 'landscape'
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def pdf_html(table, photos):
    text_width = sum(table['widths'][:7])
    columns = ''.join(f'<col style="width:{width / text_width * 69:.5f}%">' for width in table['widths'][:7]) + '<col style="width:31%">'
    headers = ''.join(f'<th>{escape(value)}</th>' for value in table['columns'])
    rows = []
    for index, row in enumerate(table['rows']):
        cells = []
        for column, value in enumerate(row['cells']):
            if column == 7 and photos.get(index):
                content = '<div class="pictures">' + ''.join(f'<img alt="Claim picture" src="data:image/png;base64,{base64.b64encode(photo).decode()}">' for photo in photos[index]) + '</div>'
            elif column == 5:
                content = f'<span class="solution">{escape(value)}</span>'
            else:
                content = escape(value)
            cells.append(f'<td>{content}</td>')
        rows.append('<tr>' + ''.join(cells) + '</tr>')
    return '''<!doctype html><html><head><meta charset="utf-8"><title>Manufacturing Claims</title><style>
      @page { size:A4 landscape; margin:10mm; }
      * { box-sizing:border-box; }
      body { margin:0; color:#252C4A; font-family:Arial,sans-serif; font-size:10px; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
      table { width:100%; table-layout:fixed; border-collapse:collapse; border:1px solid #DFE2F1; }
      thead { display:table-header-group; }
      tr { break-inside:avoid; }
      th { padding:12px 9px; text-align:left; background:#252C4A; color:#fff; font-weight:700; white-space:pre-wrap; overflow-wrap:anywhere; }
      td { padding:12px 9px; border-bottom:1px solid #E6E8F3; vertical-align:middle; white-space:pre-wrap; overflow-wrap:anywhere; }
      tbody tr:nth-child(even) td { background:#F3F4FD; }
      td:nth-child(2) { font-weight:700; }
      .solution { display:inline-block; padding:5px 7px; border-radius:7px; color:#4B50C5; background:#E6E7FC; }
      .pictures { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); align-items:start; gap:8px; }
      .pictures img { display:block; width:100%; max-width:144px; height:144px; object-fit:contain; border:1px solid #C9CCF5; border-radius:7px; }
    </style></head><body><table><colgroup>''' + columns + '</colgroup><thead><tr>' + headers + '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></body></html>'


def pdf_file(table, photos):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(pdf_html(table, photos), wait_until='load')
            return page.pdf(format='A4', landscape=True, print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def export_claims(payload):
    table = validate(payload)
    with EXPORT_SLOTS:
        photos = thumbnails(table)
        content = {'xlsx': xlsx_file, 'pdf': pdf_file}[table['format']](table, photos)
    return content, MIME_TYPES[table['format']], 'manufacturing-claims.' + table['format']
