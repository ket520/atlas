"""Exercise the real claims API, picture storage and form in an isolated database."""
import base64
import io
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch
from urllib.request import urlopen
import json
from openpyxl import load_workbook

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delivery_data
from server import Handler, ROOT
from playwright.sync_api import sync_playwright, expect

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')


class PreviewHandler(Handler):
    def do_GET(self):
        if self.path.split('?')[0] == '/manufacture-claims.html':
            content = (ROOT / 'pages/manufacture-claims.html').read_bytes().replace(b'data-live="true"', b'data-live="false"')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return
        super().do_GET()


with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'claims.sqlite3'):
    server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
            page.set_default_timeout(5000)
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
            errors=[]
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(base+'/manufacture-claims.html')
            expect(page.locator('.mc-table th')).to_have_count(9)
            page.locator('[data-mc-new]').click()
            form=page.locator('#mc-form')
            stores=form.locator('[name="sellingShop"] option').all_text_contents()[1:]
            assert stores==page.evaluate('PURCHASE_STORES')
            form.locator('[name="orderDate"]').fill('2026-10-24')
            form.locator('[name="originalOrderNo"]').fill('650001')
            form.locator('[name="replacementOrderNo"]').fill('650002')
            form.locator('[name="variantCode"]').fill('SKU-100')
            form.locator('[name="sellingShop"]').select_option('B&Q')
            form.locator('[name="reason"]').select_option('Others')
            form.locator('[name="solution"]').select_option('Others')
            form.locator('[data-mc-save]').click()
            assert form.locator('[name="reasonOther"]').evaluate('el=>!el.validity.valid')
            form.locator('[name="reasonOther"]').fill('Cracked glaze <test>')
            form.locator('[name="solutionOther"]').fill('Supplier assessment')
            upload={'name':'damage.png','mimeType':'image/png','buffer':PNG}
            form.locator('#mc-pictures').set_input_files([upload])
            expect(form.locator('.mc-photo-previews img')).to_have_count(1)
            assert form.locator('.mc-photo-previews img').evaluate('el=>getComputedStyle(el).width') == '120px'
            # A background refresh must preserve a claim being entered.
            page.evaluate('window.claimForm=document.querySelector("#mc-form");R()')
            assert page.evaluate('claimForm===document.querySelector("#mc-form")')
            # Failure preserves the form and attachments for a safe retry.
            page.route('**/api/manufacture-claims', lambda route: route.fulfill(status=503,json={'error':'Temporary save problem'}))
            form.locator('[data-mc-save]').click()
            expect(form.locator('[data-mc-form-status]')).to_have_text('Temporary save problem')
            expect(form.locator('[name="reasonOther"]')).to_have_value('Cracked glaze <test>')
            expect(form.locator('.mc-photo-previews img')).to_have_count(1)
            page.unroute('**/api/manufacture-claims')
            form.locator('[data-mc-save]').click()
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            expect(page.locator('[data-mc-rows] tr')).to_have_count(1)
            expect(page.locator('[data-mc-rows]')).to_contain_text('Cracked glaze <test>')
            page.wait_for_function('document.querySelector(".mc-row-photos img").naturalWidth>0')
            assert page.locator('.mc-row-photos img').evaluate('el=>getComputedStyle(el).width') == '64px'
            assert page.locator('.mc-row-photos button').evaluate('el=>el.clientHeight >= el.querySelector("img").offsetHeight')
            assert page.locator('.mc-row-photos').evaluate('el=>el.closest("tr").offsetHeight >= el.offsetHeight')
            page.reload()
            expect(page.locator('[data-mc-rows]')).to_contain_text('Supplier assessment')
            with urlopen(base+'/api/manufacture-claims') as response:
                record=json.load(response)['records'][0]
            with urlopen(base+record['photos'][0]['url']) as response:
                assert response.headers['Content-Type']=='image/png' and response.read()==PNG
            # Excel follows the reference layout while retaining the displayed data.
            expected=page.locator('.mc-table').evaluate("el=>({columns:[...el.querySelectorAll('th')].map(e=>e.innerText.trim()),cells:[...el.querySelector('tbody tr').cells].map(e=>e.innerText.trim())})")
            for format in ('xlsx','pdf'):
                with page.expect_download() as pending:
                    page.locator(f'[data-mc-download="{format}"]').click()
                download=pending.value
                assert download.suggested_filename==f'manufacturing-claims.{format}'
                output=Path(directory)/download.suggested_filename
                download.save_as(output)
                if format=='xlsx':
                    book=load_workbook(output)
                    try:
                        assert [cell.value for cell in book.active[1]]==['Order Date', 'Original Order Date', 'Replacement Order Date', 'VariantCode', 'Reason', 'Solution', 'Shop / Selling\nPlatform', 'Photos']
                        assert [cell.value or '' for cell in book.active[2]]==expected['cells'][:8]
                        assert len(book.active._images)==1
                    finally:
                        book.close()
                else:
                    assert output.read_bytes().startswith(b'%PDF-')
            # Clicking the data opens a populated edit form, not a duplicate claim.
            page.locator('[data-mc-edit] td').nth(4).click()
            expect(form.locator('#mc-form-title')).to_have_text('Edit claim')
            expect(form.locator('[name="originalOrderNo"]')).to_have_value('650001')
            expect(form.locator('[name="reason"]')).to_have_value('Others')
            expect(form.locator('[name="reasonOther"]')).to_have_value('Cracked glaze <test>')
            expect(form.locator('.mc-photo-previews img')).to_have_count(1)
            form.locator('[name="variantCode"]').fill('EDITED-SKU')
            page.route('**/api/manufacture-claims/'+record['id'], lambda route: route.fulfill(status=503,json={'error':'Temporary update problem'}))
            form.locator('[data-mc-save]').click()
            expect(form.locator('[data-mc-form-status]')).to_have_text('Temporary update problem')
            expect(form.locator('[name="variantCode"]')).to_have_value('EDITED-SKU')
            expect(form.locator('.mc-photo-previews img')).to_have_count(1)
            page.unroute('**/api/manufacture-claims/'+record['id'])
            form.locator('#mc-pictures').set_input_files([upload])
            form.locator('[data-mc-save]').click()
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            records = page.request.get(base+'/api/manufacture-claims').json()['records']
            assert len(records) == 1 and records[0]['id'] == record['id']
            assert records[0]['createdAt'] == record['createdAt']
            assert records[0]['variantCode'] == 'EDITED-SKU'
            assert records[0]['photos'][0]['id'] == record['photos'][0]['id']
            assert len(records[0]['photos']) == 2
            # Keyboard opening and cancel leave persisted data alone.
            page.locator('[data-mc-edit]').focus()
            page.keyboard.press('Enter')
            form.locator('[name="variantCode"]').fill('DO-NOT-SAVE')
            form.get_by_role('button',name='Cancel',exact=True).click()
            assert page.request.get(base+'/api/manufacture-claims').json()['records'][0]['variantCode'] == 'EDITED-SKU'
            page.locator('[data-mc-edit] td').first.click()
            form.locator('[data-mc-remove-photo]').first.click()
            form.locator('[data-mc-save]').click()
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            assert page.request.get(base+record['photos'][0]['url']).status == 404
            page.reload()
            expect(page.locator('[data-mc-rows]')).to_contain_text('EDITED-SKU')
            # Month changes affect the table and both export requests.
            result = page.request.post(base+'/api/manufacture-claims', data={
                'orderDate':'2026-09-15','originalOrderNo':'SEPT-001','replacementOrderNo':'SEPT-002','variantCode':'SKU-SEP',
                'reason':'Leaking','solution':'Refund','sellingShop':'B&Q',
                'photos':[{'name':f'photo-{i}.png','data':base64.b64encode(PNG).decode()} for i in range(2)]})
            assert result.ok
            september = result.json()
            page.locator('[data-mc-refresh]').click()
            expect(page.locator('[data-mc-rows] tr')).to_have_count(2)
            page.locator('[data-mc-toggle-date]').click()
            page.locator('[data-mc-date="from"]').fill('2026-09-01')
            page.locator('[data-mc-date="to"]').fill('2026-09-30')
            page.keyboard.press('Escape')
            expect(page.locator('[data-mc-rows] tr')).to_have_count(1)
            expect(page.locator('[data-mc-count]')).to_have_text('1 claim')
            for format in ('xlsx', 'pdf'):
                with page.expect_request('**/api/manufacture-claims/export') as sent, page.expect_download() as pending:
                    page.locator(f'[data-mc-download="{format}"]').click()
                payload = sent.value.post_data_json
                assert len(payload['columns']) == 8
                assert [row['id'] for row in payload['rows']] == [september['id']]
                assert payload['rows'][0]['cells'][1] == 'SEPT-001'
                pending.value.save_as(Path(directory)/f'filtered.{format}')
            # Claims reuse gallery controls while omitting original/copy actions.
            page.locator('[data-mc-view-photos]').first.click()
            gallery = page.get_by_role('dialog', name='Claim pictures', exact=True)
            expect(gallery).to_be_visible()
            expect(gallery.locator('.qd-gallery-head span')).to_have_text('1 of 2')
            expect(gallery.get_by_text('Open original')).to_have_count(0)
            expect(gallery.get_by_text('Copy link')).to_have_count(0)
            page.wait_for_function('document.querySelector(".qd-gallery-image").naturalWidth>0')
            gallery.get_by_role('button', name='Zoom in', exact=True).click()
            expect(gallery.get_by_role('button', name='Reset image view')).to_have_text('125%')
            gallery.get_by_role('button', name='Rotate image clockwise').click()
            assert 'rotate(90deg)' in gallery.locator('img').get_attribute('style')
            gallery.get_by_role('button', name='Next image').click()
            expect(gallery.locator('.qd-gallery-head span')).to_have_text('2 of 2')
            page.keyboard.press('ArrowLeft')
            expect(gallery.locator('.qd-gallery-head span')).to_have_text('1 of 2')
            with page.expect_download() as pending:
                gallery.get_by_role('button', name='Download image').click()
            assert pending.value.suggested_filename == 'claim-picture-1.png'
            page.keyboard.press('Escape')
            expect(gallery).to_have_count(0)
            page.locator('[data-mc-delete]').click()
            confirmation = page.get_by_role('dialog', name='Heads up')
            expect(confirmation).to_contain_text('manufacturing claim and its pictures')
            confirmation.get_by_role('button', name='Cancel', exact=True).click()
            expect(page.locator('[data-mc-delete]')).to_have_count(1)
            page.locator('[data-mc-delete]').click()
            confirmation.get_by_role('button', name='Delete claim', exact=True).click()
            expect(page.locator('[data-mc-count]')).to_have_text('0 claims')
            assert page.request.get(base+september['photos'][0]['url']).status == 404
            page.locator('[data-mc-toggle-date]').click()
            page.locator('[data-mc-clear-dates]').click()
            page.keyboard.press('Escape')
            expect(page.locator('[data-mc-count]')).to_have_text('1 claim')
            page.screenshot(path=str(ROOT/'.test-temp/manufacture-claims.png'))
            for width in (1440,390):
                page.set_viewport_size({'width':width,'height':900})
                page.locator('[data-mc-new]').click()
                form.locator('[name="reason"]').select_option('Others')
                form.locator('[name="solution"]').select_option('Others')
                assert page.locator('.mc-dialog').evaluate('el=>el.scrollWidth<=el.clientWidth')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                form.locator('#mc-pictures').set_input_files([upload]*6)
                expect(form.locator('[data-mc-form-status]')).to_have_text('Attach up to 5 pictures.')
                expect(form.locator('.mc-photo-previews img')).to_have_count(0)
                if width==1440:
                    page.locator('.mc-dialog').screenshot(path=str(ROOT/'.test-temp/manufacture-claims-form.png'))
                page.keyboard.press('Escape')
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown(); server.server_close(); thread.join()
    print('PASS: real claims save/reload, pictures, custom choices, shop list, retry without data loss, upload limits and responsive form')
