import io
import unittest

from openpyxl import load_workbook

from collection_export import export_note, validate


def cell(text, x=0, width=100, **styles):
    return {"text": text, "x": x, "width": width, "fontSize": 12,
            "borders": {side: {"width": 1, "color": "#171717"} for side in ("top", "right", "bottom", "left")}, **styles}


class CollectionExportTests(unittest.TestCase):
    def note(self, format):
        return {"format": format, "order": "123456", "width": 100, "rows": [
            {"height": 38, "cells": [cell("COLLECTION NOTE", bold=True, fontSize=25)]},
            {"height": 27, "cells": [cell("Item Code", width=25, background="#f8d7be"), cell("Description", x=25, width=75, background="#f8d7be")]},
            {"height": 56, "cells": [cell("=SKU-123", width=25), cell('Edited description, with "quotes"\nand another line', x=25, width=75, italic=True, underline=True)]},
        ]}

    def test_xlsx_preserves_merged_layout_colors_formatting_and_text(self):
        data, mime, filename = export_note(self.note("xlsx"))
        workbook = load_workbook(io.BytesIO(data))
        try:
            sheet = workbook.active
            self.assertIn("A1:B1", {str(merge) for merge in sheet.merged_cells.ranges})
            self.assertEqual(sheet["A3"].value, "=SKU-123")
            self.assertEqual(sheet["A3"].data_type, "s")
            self.assertTrue(sheet["A1"].font.bold)
            self.assertTrue(sheet["B3"].font.italic)
            self.assertEqual(sheet["B3"].font.underline, "single")
            self.assertEqual(sheet["B2"].fill.fgColor.rgb, "00F8D7BE")
            self.assertEqual(sheet.row_dimensions[3].height, 42)
            self.assertEqual(sheet.page_setup.fitToWidth, 1)
        finally:
            workbook.close()

    def test_rejects_invalid_format_and_unbounded_layout(self):
        for key, value in (("format", "html"), ("format", "csv"), ("width", float("nan")), ("rows", [])):
            note = self.note("xlsx")
            note[key] = value
            with self.assertRaises(ValueError):
                validate(note)
        note = self.note("pdf")
        note["rows"][0]["cells"][0]["width"] = 10000
        with self.assertRaises(ValueError):
            validate(note)
