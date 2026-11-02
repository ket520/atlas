"""Read captured Amazon Shipping snapshots by tracking ID (demo only).

No Amazon login, scraping, claim submission, or external HTTP requests.
"""

import io
import csv
from xml.etree import ElementTree as ET
import json
import re
from html import escape as html_escape
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape
from zipfile import ZIP_DEFLATED, ZipFile

CAPTURES = Path(__file__).resolve().parent / "amazon_demo_captures"
TRACKING_RE = re.compile(r"UK\d{8,20}", re.IGNORECASE)
ROUTE_RE = re.compile(
    r"/api/amazon-shipping/(UK\d{8,20})(?:/(pod|excel|excel-preview))?/?$",
    re.IGNORECASE,
)
DETAIL_FIELDS = ("reference", "shipping_speed", "package_size", "package_weight", "total_charge")
EVENT_FIELDS = ("date", "time", "timezone_offset", "timestamp", "description", "location", "note")


def snapshot(tracking_id):
    """Read only the snapshot matching this tracking ID, never another order."""
    tracking_id = tracking_id.upper()
    if not TRACKING_RE.fullmatch(tracking_id):
        return None
    path = CAPTURES / f"{tracking_id}_amazon_history.json"
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(raw, dict) or str(raw.get("tracking_id", "")).upper() != tracking_id:
        return None
    events = raw.get("events", [])
    if not isinstance(events, list):
        events = []
    cleaned = [
        {key: str(event.get(key) or "")[:1000] for key in EVENT_FIELDS}
        for event in events[:1000]
        if isinstance(event, dict)
    ]
    pod = CAPTURES / f"{tracking_id}_pod.pdf"
    package_file = _original_excel_file(tracking_id)
    has_pod = pod.is_file() and 0 < pod.stat().st_size <= 20 * 1024 * 1024
    result = {
        "available": True,
        "tracking_id": tracking_id,
        "shipment_status": str(raw.get("shipment_status") or "")[:100],
        "capture_type": "on_demand_browser_capture" if raw.get("source") == "amazon_shipping_live_browser_capture" else "manual_browser_capture",
        "events": cleaned,
        "events_count": len(cleaned),
        "documents": {
            "pod_available": has_pod,
            "pod_view_url": f"/api/amazon-shipping/{tracking_id}/pod" if has_pod else None,
            "pod_download_url": f"/api/amazon-shipping/{tracking_id}/pod?download=1" if has_pod else None,
            "excel_available": package_file is not None,
            "excel_preview_url": f"/api/amazon-shipping/{tracking_id}/excel-preview" if package_file else None,
            "excel_download_url": f"/api/amazon-shipping/{tracking_id}/excel" if package_file else None,
        },
    }
    result.update({field: str(raw.get(field) or "")[:200] for field in DETAIL_FIELDS})
    return result


def _cell_reference(index):
    letters = ""
    while index:
        index, digit = divmod(index - 1, 26)
        letters = chr(65 + digit) + letters
    return letters


def _sheet_xml(rows):
    cells = []
    for row_num, row in enumerate(rows, 1):
        row_cells = []
        for col_num, value in enumerate(row, 1):
            # Excel inline strings are text, never interpreted as formulas.
            value = "" if value is None else str(value)
            value = "".join(ch for ch in value if ord(ch) >= 32 or ch in "\n\t\r")
            value = xml_escape(value)
            row_cells.append(
                f'<c r="{_cell_reference(col_num)}{row_num}" t="inlineStr">'
                f'<is><t xml:space="preserve">{value}</t></is></c>'
            )
        cells.append(f'<row r="{row_num}">{"".join(row_cells)}</row>')
    return ('<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData>' + ''.join(cells) + '</sheetData></worksheet>')


def shipment_excel(data):
    """Make an XLSX report from THIS snapshot, using the Python stdlib."""
    details = [["Field", "Value"], ["Tracking ID", data["tracking_id"]],
               ["Shipment status", data["shipment_status"]]]
    details.extend([[field.replace("_", " ").title(), data.get(field, "")] for field in DETAIL_FIELDS])
    details.append(["Source", "Saved Amazon Shipping browser capture — demo export"])
    columns = ["timestamp", "description", "location", "note"]
    events = [["Timestamp (+ original offset)", "Event", "Location", "Delivery note"]]
    events.extend([[item.get(key, "") for key in columns] for item in data["events"]])

    out = io.BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", '''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
<Override PartName="/xl/worksheets/sheet2.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>''')
        archive.writestr("_rels/.rels", '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
        archive.writestr("xl/workbook.xml", '''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Shipment Details" sheetId="1" r:id="rId1"/>
<sheet name="Tracking Events" sheetId="2" r:id="rId2"/></sheets></workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet2.xml"/>
</Relationships>''')
        archive.writestr("xl/worksheets/sheet1.xml", _sheet_xml(details))
        archive.writestr("xl/worksheets/sheet2.xml", _sheet_xml(events))
    return out.getvalue()


def _html_preview(data):
    rows = "".join(
        f"<tr><td>{html_escape(item['timestamp'])}</td><td>{html_escape(item['description'])}</td>"
        f"<td>{html_escape(item['location'])}</td><td>{html_escape(item['note'])}</td></tr>"
        for item in data["events"]
    )
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Shipment export preview — {data['tracking_id']}</title>
<style>body{{font:14px system-ui;margin:30px;color:#26372b}}
table{{width:100%;border-collapse:collapse}}td,th{{text-align:left;border:1px solid #d8e4dc;padding:10px}}
th{{background:#eaf5ee}}h1{{color:#26774e}}.mut{{color:#65776a}}</style></head><body>
<h1>Shipment export preview</h1><p>Tracking ID: {data['tracking_id']}</p>
<p class="mut">Generated from a saved manual capture — not an official Amazon export.</p>
<table><thead><tr><th>Timestamp</th><th>Event</th><th>Location</th><th>Note</th></tr></thead>
<tbody>{rows}</tbody></table></body></html>'''.encode("utf-8")


def _send_bytes(handler, content, mime, filename=None, inline=False):
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'")
    if filename:
        handler.send_header("Content-Disposition", f'{"inline" if inline else "attachment"}; filename="{filename}"')
    handler.send_header("Content-Length", str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


def _original_excel_file(tracking_id):
    files = [CAPTURES / f"{tracking_id}_package_details{ext}" for ext in (".xlsx", ".xls", ".csv")]
    found = [p for p in files if p.is_file() and 0 < p.stat().st_size <= 20 * 1024 * 1024]
    return max(found, key=lambda p: p.stat().st_mtime) if found else None


def _excel_preview(file, tracking_id):
    """Preview cells of original downloaded Excel; does not rewrite the document."""
    rows = []
    if file.suffix.lower() == ".csv":
        with file.open("r", encoding="utf-8-sig", newline="") as fp:
            rows = [row[:12] for _, row in zip(range(25), csv.reader(fp))]
    elif file.suffix.lower() == ".xlsx":
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        with ZipFile(file) as book:
            shared = []
            if "xl/sharedStrings.xml" in book.namelist():
                ss = ET.fromstring(book.read("xl/sharedStrings.xml"))
                shared = ["".join(el.itertext()) for el in ss.findall(ns + "si")]
            sheets = sorted(n for n in book.namelist() if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
            if sheets:
                root = ET.fromstring(book.read(sheets[0]))
                for row in root.iter(ns + "row"):
                    values = []
                    for cell in row.findall(ns + "c")[:12]:
                        typ = cell.get("t")
                        raw = cell.findtext(ns + "v") or ""
                        if typ == "s":
                            try:
                                raw = shared[int(raw)]
                            except (IndexError, ValueError):
                                raw = ""
                        elif typ == "inlineStr":
                            inside = cell.find(ns + "is")
                            raw = "".join(inside.itertext()) if inside is not None else ""
                        values.append(raw)
                    rows.append(values)
                    if len(rows) >= 25:
                        break
    else:
        rows = [["Excel 97-2003 file", "Download the original file to view it in Excel."]]
    cells = "".join("<tr>" + "".join(f"<td>{html_escape(str(val)[:300])}</td>" for val in row) + "</tr>" for row in rows)
    return ('''<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Package details</title><style>
    body{font:14px system-ui;padding:26px;color:#213c2b}h1{color:#167649}p{color:#657668}
    table{border-collapse:collapse;width:100%}td{padding:9px;border:1px solid #dbe5df;white-space:pre-wrap;max-width:250px;overflow-wrap:anywhere}
    tr:first-child{font-weight:700;background:#e9f4ed}</style></head><body>
    <h1>Amazon Shipping — Package details</h1><p>Original export preview — ''' + tracking_id + '''</p>
    <table>''' + cells + '''</table></body></html>''').encode("utf-8")


def serve_amazon_shipping(handler, path, params):
    match = ROUTE_RE.fullmatch(path)
    if not match:
        return handler.send_json(400, {"error": "Invalid Amazon Shipping ID or route."})
    tracking_id = match.group(1).upper()
    kind = (match.group(2) or "").lower()
    data = snapshot(tracking_id)
    if not data:
        if kind:
            return handler.send_json(404, {"error": "No saved Amazon data for this tracking ID."})
        return handler.send_json(200, {"available": False, "tracking_id": tracking_id})
    if kind == "":
        return handler.send_json(200, data)
    if kind == "pod":
        if not data["documents"]["pod_available"]:
            return handler.send_json(404, {"error": "No PDF saved for this shipment."})
        filename = f"{tracking_id}_pod.pdf"
        content = (CAPTURES / filename).read_bytes()
        return _send_bytes(handler, content, "application/pdf", filename,
                           inline=params.get("download", [""])[0] != "1")
    if kind in ("excel", "excel-preview"):
        file = _original_excel_file(tracking_id)
        if not file:
            return handler.send_json(404, {"error": "Original Amazon Package details Excel has not been captured."})
        if kind == "excel-preview":
            try:
                content = _excel_preview(file, tracking_id)
            except Exception:
                return handler.send_json(422, {"error": "Excel preview unavailable; download the original file instead."})
            return _send_bytes(handler, content, "text/html; charset=utf-8")
        mime = {".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ".xls": "application/vnd.ms-excel", ".csv": "text/csv"}[file.suffix.lower()]
        return _send_bytes(handler, file.read_bytes(), mime, file.name)
