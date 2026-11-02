import base64
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import delivery_data
import manufacture_claims
from server import Handler, ROOT
from playwright.sync_api import sync_playwright, expect

PNG64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII='


class PreviewHandler(Handler):
    def do_GET(self):
        if self.path == '/manufacture-claims.html':
            content = (ROOT / 'pages/manufacture-claims.html').read_bytes().replace(b'data-live="true"', b'data-live="false"')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        else:
            super().do_GET()


with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'DB_PATH', Path(directory) / 'test.sqlite3'):
    delivery_data.archive([{'Order no': order, 'Original order Number': original, 'Order Category': 'Order',
        'Delivery method': 'Palletways', 'Product SKU': sku, 'Parent SKU': 'WRONG-PARENT',
        **{f'Extra{i}': '' for i in range(27)}, 'Store code': 'B&Q'}
        for order, original, sku in [('100', '', 'PRODUCT-SKU'), ('200', '100', 'REPLACEMENT-SKU'),
            ('300', '', 'MULTI-SKU'), ('400', '300', 'OTHER'), ('500', '300', 'OTHER')]])
    manufacture_claims.save_claim(dict(orderDate='2026-10-24', originalOrderNo='553641',
        replacementOrderNo='653099', variantCode='TAP2203B', reason='Leaking', solution='Replacement',
        sellingShop='B&Q', photos=[{'name': 'picture.png', 'data': PNG64}] * 4))
    server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
            page.goto(f'http://127.0.0.1:{server.server_port}/manufacture-claims.html')
            expect(page.locator('.mc-solution')).to_have_text('Replacement')
            for width in [1920, 1440]:
                page.set_viewport_size({'width': width, 'height': 1080})
                assert page.locator('.mc-solution').evaluate('''el => {
                  const range=document.createRange();range.selectNodeContents(el);
                  return range.getClientRects().length === 1;
                }''')
            page.locator('[data-mc-new]').click()
            form = page.locator('#mc-form')
            assert form.locator('.mc-fields > label').evaluate_all('els=>els.slice(0,4).map(el=>el.querySelector("input,select").name)') == ['originalOrderNo', 'replacementOrderNo', 'orderDate', 'sellingShop']
            assert form.locator('[name="replacementOrderNo"]').evaluate('(el)=>el.required')
            page.evaluate('''() => {
              window.autofilled=[];
              const animate=Element.prototype.animate;
              Element.prototype.animate=function(frames,options){
                if (this.closest('#mc-form') && frames[0]?.backgroundColor === '#fde047') autofilled.push(this.name);
                return animate.call(this,frames,options);
              };
            }''')
            expect(form.locator('[data-mc-form-delete]')).to_be_hidden()
            form.locator('[name="originalOrderNo"]').fill('100')
            expect(form.locator('[name="replacementOrderNo"]')).to_have_value('200')
            expect(form.locator('[name="variantCode"]')).to_have_value('PRODUCT-SKU')
            expect(form.locator('[name="sellingShop"]')).to_have_value('B&Q')
            assert {'replacementOrderNo', 'variantCode', 'sellingShop'} <= set(page.evaluate('window.autofilled'))
            form.locator('[name="variantCode"]').fill('MANUAL-SKU')
            form.locator('[name="originalOrderNo"]').fill('300')
            expect(form.locator('#mc-replacement-options option')).to_have_count(2)
            expect(form.locator('[name="replacementOrderNo"]')).to_have_value('')
            expect(form.locator('[name="variantCode"]')).to_have_value('MANUAL-SKU')
            form.locator('[name="replacementOrderNo"]').fill('500')
            expect(form.locator('[name="originalOrderNo"]')).to_have_value('300')
            expect(form.locator('[data-mc-lookup-status]')).to_contain_text('Check the details')
            transfer = page.evaluate_handle('''encoded => {
              const transfer=new DataTransfer();
              transfer.items.add(new File([Uint8Array.from(atob(encoded), c=>c.charCodeAt(0))], 'dropped.png', {type:'image/png'}));
              return transfer;
            }''', PNG64)
            zone = form.locator('.mc-upload')
            zone.dispatch_event('dragover', {'dataTransfer': transfer})
            expect(zone).to_have_class('mc-full mc-upload is-drag-over')
            zone.dispatch_event('drop', {'dataTransfer': transfer})
            expect(form.locator('[data-mc-previews] figure')).to_have_count(1)
            expect(zone).not_to_have_class('mc-full mc-upload is-drag-over')
            form.locator('[data-mc-preview]').click()
            gallery = page.get_by_role('dialog', name='Claim pictures')
            expect(gallery).to_be_visible()
            assert page.locator('.mc-dialog #dr').count() == 1
            page.wait_for_function('document.querySelector(".qd-gallery-image").naturalWidth > 0')
            gallery.get_by_role('button', name='Zoom in', exact=True).click()
            expect(gallery.get_by_role('button', name='Reset image view')).not_to_have_text('100%')
            page.keyboard.press('Escape')
            expect(gallery).to_have_count(0)
            expect(page.locator('.mc-dialog')).to_be_visible()
            assert page.locator('.mc-dialog #dr').count() == 0
            form.locator('[name="sellingShop"]').select_option('B&Q')
            form.locator('[name="reason"]').select_option('Leaking')
            form.locator('[name="solution"]').select_option('Replacement')
            with page.expect_response(lambda response: response.url.endswith('/api/manufacture-claims') and response.request.method == 'POST') as saved:
                form.locator('[data-mc-save]').click()
            record = saved.value.json()
            assert len(record['photos']) == 1
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            page.locator(f'[data-mc-edit="{record["id"]}"]').click()
            form.locator('[data-mc-preview]').click()
            expect(gallery).to_be_visible()
            gallery.get_by_role('button', name='Close image viewer').click()
            expect(gallery).to_have_count(0)
            expect(page.locator('.mc-dialog')).to_be_visible()
            delete = form.locator('[data-mc-form-delete]')
            expect(delete).to_be_visible()
            assert delete.bounding_box()['x'] < form.locator('[data-mc-close]').last.bounding_box()['x']
            delete.click()
            confirm = page.get_by_role('dialog', name='Heads up')
            confirm.get_by_role('button', name='Cancel', exact=True).click()
            assert len(manufacture_claims.list_claims()['records']) == 2
            delete.click()
            confirm.get_by_role('button', name='Delete claim', exact=True).click()
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            expect(page.locator('[data-mc-edit]')).to_have_count(1)
            assert len(manufacture_claims.list_claims()['records']) == 1
            browser.close()
            print('PASS: readable table, bidirectional autofill, exact Product SKU, multiple choices, manual preservation, dropped image saves and footer deletion confirms')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
