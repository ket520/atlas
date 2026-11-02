"""Download the current editable collection note without changing source data."""

import io
import math
import re
import threading
from copy import copy
from html import escape

EXPORT_SLOTS = threading.BoundedSemaphore(2)
MIME_TYPES = {
    "pdf": "application/pdf",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def number(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("Invalid note layout.")
    return value


def color(value, fallback="FFFFFF"):
    match = re.fullmatch(r"#?([0-9a-fA-F]{6})", str(value or ""))
    return match[1].upper() if match else fallback


def validate(payload):
    if not isinstance(payload, dict) or payload.get("format") not in MIME_TYPES:
        raise ValueError("Choose PDF or XLSX.")
    width = number(payload.get("width"), 100, 2000)
    rows = payload.get("rows")
    if not isinstance(rows, list) or not 1 <= len(rows) <= 2000:
        raise ValueError("The note must contain between 1 and 2,000 rows.")
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("cells"), list) or not 1 <= len(row["cells"]) <= 30:
            raise ValueError("Invalid note row.")
        number(row.get("height"), 1, 2000)
        for cell in row["cells"]:
            if not isinstance(cell, dict) or not isinstance(cell.get("text"), str) or len(cell["text"]) > 50000:
                raise ValueError("Invalid note cell.")
            x = number(cell.get("x"), 0, width)
            if x + number(cell.get("width"), 1, width) > width + 1:
                raise ValueError("Invalid note cell width.")
            number(cell.get("fontSize"), 1, 100)
            number(cell.get("paddingLeft", 0), 0, 100)
            number(cell.get("paddingRight", 0), 0, 100)
            borders = cell.get("borders", {})
            if not isinstance(borders, dict):
                raise ValueError("Invalid note borders.")
            for side in ("top", "right", "bottom", "left"):
                border = borders.get(side, {})
                if not isinstance(border, dict):
                    raise ValueError("Invalid note border.")
                number(border.get("width", 0), 0, 10)
    return payload


def xlsx_file(note):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Collection Note"
    # A common column grid preserves both the four-column address table and
    # the five-column item table on the same printable worksheet.
    edges = {0.0, round(note["width"], 2)}
    for row in note["rows"]:
        for cell in row["cells"]:
            edges.update((round(cell["x"], 2), round(cell["x"] + cell["width"], 2)))
    ordered = []
    for edge in sorted(edges):
        if not ordered or edge - ordered[-1] > 0.5:
            ordered.append(edge)
    from openpyxl.utils import get_column_letter

    for column, (start, end) in enumerate(zip(ordered, ordered[1:]), 1):
        sheet.column_dimensions[get_column_letter(column)].width = max(0.1, (end - start) / 7)
    for row_index, row in enumerate(note["rows"], 1):
        sheet.row_dimensions[row_index].height = row["height"] * 0.75
        for cell in row["cells"]:
            start = min(range(len(ordered)), key=lambda i: abs(ordered[i] - cell["x"])) + 1
            end = min(range(len(ordered)), key=lambda i: abs(ordered[i] - cell["x"] - cell["width"]))
            target = sheet.cell(row_index, start, cell["text"])
            target.data_type = "s"
            target.font = Font(name="Arial", size=cell["fontSize"] * 0.75,
                               bold=bool(cell.get("bold")), italic=bool(cell.get("italic")),
                               underline="single" if cell.get("underline") else None,
                               color=color(cell.get("color"), "090909"))
            target.fill = PatternFill("solid", fgColor=color(cell.get("background")))
            target.alignment = Alignment(horizontal=cell.get("align") if cell.get("align") in {"left", "center", "right"} else "left",
                                         vertical="center", wrap_text=True)
            sides = {}
            for side in ("top", "right", "bottom", "left"):
                border = cell.get("borders", {}).get(side, {})
                sides[side] = Side(style="thin" if border.get("width", 0) else None,
                                   color=color(border.get("color"), "E2E4E8"))
            target.border = Border(**sides)
            if end > start:
                sheet.merge_cells(start_row=row_index, start_column=start, end_row=row_index, end_column=end)
                for column in range(start, end + 1):
                    sheet.cell(row_index, column).fill = copy(target.fill)
    sheet.sheet_view.showGridLines = False
    sheet.print_area = f"A1:{get_column_letter(len(ordered) - 1)}{len(note['rows'])}"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A4
    sheet.page_setup.orientation = "portrait"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True
    sheet.page_margins.left = sheet.page_margins.right = 10 / 25.4
    sheet.page_margins.top = sheet.page_margins.bottom = 10 / 25.4
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def pdf_html(note):
    rows = []
    for row in note["rows"]:
        cells = []
        for cell in row["cells"]:
            align = cell.get("align") if cell.get("align") in {"left", "center", "right"} else "left"
            rules = [f"left:{cell['x']}px", f"width:{cell['width']}px", f"font-size:{cell['fontSize']}px",
                     f"background:#{color(cell.get('background'))}", f"color:#{color(cell.get('color'), '090909')}",
                     f"padding-left:{cell.get('paddingLeft', 0)}px", f"padding-right:{cell.get('paddingRight', 0)}px",
                     f"font-weight:{'bold' if cell.get('bold') else 'normal'}", f"font-style:{'italic' if cell.get('italic') else 'normal'}",
                     f"text-decoration:{'underline' if cell.get('underline') else 'none'}", f"text-align:{align}"]
            for side in ("top", "right", "bottom", "left"):
                border = cell.get("borders", {}).get(side, {})
                rules.append(f"border-{side}:{border.get('width', 0)}px solid #{color(border.get('color'), 'E2E4E8')}")
            cells.append(f'<div class="cell" style="{";".join(rules)}"><span>{escape(cell["text"])}</span></div>')
        rows.append(f'<div class="row" style="height:{row["height"]}px">{"".join(cells)}</div>')
    html = '<!doctype html><meta charset="utf-8"><style>@page{size:A4;margin:10mm}*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif}.row{position:relative;break-inside:avoid}.cell{position:absolute;top:0;height:100%;display:flex;align-items:center;line-height:1.25;overflow:hidden}.cell span{width:100%;white-space:pre-wrap;overflow-wrap:anywhere}</style>'
    html += f'<main style="width:{note["width"]}px">{"".join(rows)}</main>'
    return html


def pdf_file(note):
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.set_content(pdf_html(note), wait_until="load")
            return page.pdf(format="A4", print_background=True, prefer_css_page_size=True)
        finally:
            browser.close()


def export_note(payload):
    note = validate(payload)
    with EXPORT_SLOTS:
        content = {"pdf": pdf_file, "xlsx": xlsx_file}[note["format"]](note)
    order = re.sub(r"[^A-Za-z0-9_-]", "", str(note.get("order") or ""))[:40]
    filename = f"collection-note{'-' + order if order else ''}.{note['format']}"
    return content, MIME_TYPES[note["format"]], filename
