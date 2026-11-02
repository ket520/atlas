import base64
import io
import re
import unittest
from unittest.mock import patch

from openpyxl import load_workbook
import manufacture_claims_export as exports

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')
XLSX_HEADERS = ['Order Date', 'Original Order Date', 'Replacement Order Date', 'VariantCode', 'Reason', 'Solution', 'Shop / Selling\nPlatform', 'Photos']
HEADERS = ['Order date', 'Original Order No', 'Replacement Order No', 'VariantCode', 'Reason',
           'Solution\nReplacement / Refund', 'Selling shop', 'Pictures']


class ManufactureClaimsExportTests(unittest.TestCase):
    def table(self, format='xlsx'):
        return {'format': format, 'columns': HEADERS.copy(), 'widths': [120,150,150,120,200,160,170,130],
                'rows': [{'id':'a'*32, 'cells':['24 Oct 2026','000123','—','=SKU-1','Scratches <test>', 'Refund','B&Q',''], 'photos':['b'*32]},
                         {'id':'c'*32, 'cells':['23 Oct 2026','000124','R-1','SKU-2','Custom reason\nsecond line','Supplier inspection','Amazon','—'], 'photos':[]}]}

    def test_xlsx_has_exact_headers_order_values_and_embedded_pictures(self):
        table = self.table()
        with patch.object(exports, 'get_photo', return_value=(PNG, 'image/png')):
            content, mime, filename = exports.export_claims(table)
        self.assertEqual(filename, 'manufacturing-claims.xlsx')
        self.assertIn('spreadsheetml', mime)
        book=load_workbook(io.BytesIO(content))
        try:
            sheet=book.active
            self.assertEqual(sheet.max_column, 8)
            self.assertEqual(sheet.max_row, 3)
            self.assertEqual([cell.value for cell in sheet[1]], XLSX_HEADERS)
            for index, row in enumerate(table['rows'], 2):
                self.assertEqual([cell.value or '' for cell in sheet[index]], row['cells'])
            self.assertEqual(sheet['B2'].value, '000123')
            self.assertEqual(sheet['D2'].data_type, 's')
            self.assertEqual(sheet['A1'].font.color.rgb, '00000000')
            self.assertEqual(sheet['A1'].fill.patternType, None)
            self.assertTrue(sheet.sheet_view.showGridLines)
            self.assertEqual(sheet['A2'].alignment.vertical, 'bottom')
            self.assertGreaterEqual(sheet.row_dimensions[2].height, 123)
            self.assertEqual(sheet._images[0].anchor.ext.cx, 140 * 9525)
            self.assertEqual(len(sheet._images), 1)
            self.assertEqual(sheet._images[0].anchor._from.col, 7)
            self.assertEqual(sheet.print_title_rows, '$1:$1')
        finally:
            book.close()

    def test_pdf_html_preserves_headers_text_and_pictures_without_html_injection(self):
        table=self.table('pdf')
        with patch.object(exports,'get_photo',return_value=(PNG,'image/png')):
            html=exports.pdf_html(table,exports.thumbnails(table))
        for heading in HEADERS:
            self.assertIn(heading, html)
        self.assertIn('Scratches &lt;test&gt;', html)
        self.assertIn('B&amp;Q', html)
        self.assertNotIn('<test>', html)
        self.assertIn('data:image/png;base64,', html)
        self.assertIn('table-header-group', html)

    def test_five_large_photos_fit_inside_the_excel_row(self):
        table = self.table()
        table['rows'] = [table['rows'][0]]
        table['rows'][0]['photos'] = ['b' * 32] * 5
        with patch.object(exports, 'get_photo', return_value=(PNG, 'image/png')):
            content, _, _ = exports.export_claims(table)
        book = load_workbook(io.BytesIO(content))
        try:
            sheet = book.active
            self.assertEqual(len(sheet._images), 5)
            for image in sheet._images:
                anchor = image.anchor
                self.assertLessEqual((anchor._from.colOff + anchor.ext.cx) / 9525, 320)
                self.assertLessEqual((anchor._from.rowOff + anchor.ext.cy) / 9525, sheet.row_dimensions[2].height / .75)
        finally:
            book.close()

    def test_pdf_is_valid_and_spans_multiple_pages(self):
        table=self.table('pdf')
        table['rows']=[table['rows'][1]]*90
        content,mime,filename=exports.export_claims(table)
        self.assertTrue(content.startswith(b'%PDF-'))
        self.assertEqual(mime,'application/pdf')
        self.assertEqual(filename,'manufacturing-claims.pdf')
        self.assertGreater(len(re.findall(rb'/Type /Page\b',content)),1)

    def test_pdf_five_large_photos_fit_the_row_and_printable_page(self):
        from playwright.sync_api import sync_playwright
        table = self.table('pdf')
        table['rows'] = [table['rows'][0]]
        table['rows'][0]['photos'] = ['b' * 32] * 5
        with patch.object(exports, 'get_photo', return_value=(PNG, 'image/png')):
            html = exports.pdf_html(table, exports.thumbnails(table))
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            try:
                page = browser.new_page(viewport={'width': 1047, 'height': 718})
                page.set_content(html, wait_until='load')
                result = page.evaluate('''() => {
                  const cell = document.querySelector('tbody tr td:last-child').getBoundingClientRect();
                  const images = [...document.querySelectorAll('.pictures img')];
                  return {count:images.length, fits:images.every(img => {
                    const r=img.getBoundingClientRect();
                    return r.width>=140 && r.height>=140 && r.left>=cell.left && r.right<=cell.right && r.top>=cell.top && r.bottom<=cell.bottom && getComputedStyle(img).objectFit==='contain';
                  }), height:document.querySelector('table').getBoundingClientRect().height};
                }''')
                self.assertEqual(result['count'], 5)
                self.assertTrue(result['fits'])
                self.assertLess(result['height'], 718)
            finally:
                browser.close()

    def test_empty_table_downloads_just_the_headers(self):
        table=self.table()
        table['rows']=[]
        content,_,_=exports.export_claims(table)
        book=load_workbook(io.BytesIO(content))
        try:
            self.assertEqual(book.active.max_row,1)
            self.assertEqual([cell.value for cell in book.active[1]],XLSX_HEADERS)
        finally:
            book.close()

    def test_missing_picture_does_not_silently_drop_data(self):
        with patch.object(exports,'get_photo',return_value=None), self.assertRaisesRegex(ValueError,'no longer available'):
            exports.export_claims(self.table())

    def test_bad_export_requests_are_rejected(self):
        for key,value in [('format','csv'),('columns',['Wrong']),('widths',[0]*8),('rows',[{}])]:
            with self.subTest(key=key),self.assertRaises(ValueError):
                exports.validate({**self.table(),key:value})


if __name__=='__main__':
    unittest.main()
