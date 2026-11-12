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

PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aX1cAAAAASUVORK5CYII=')


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


with tempfile.TemporaryDirectory() as directory, patch.object(delivery_data, 'configured_db_path', return_value=Path(directory) / 'claims.sqlite3'):
    original = manufacture_claims.save_claim(dict(orderDate='2026-10-24', originalOrderNo='663132', replacementOrderNo='700001',
        variantCode='SKU', reason='Others', reasonOther='Custom reason', solution='Refund', sellingShop='B&Q',
        photos=[{'name': 'original.png', 'data': base64.b64encode(PNG).decode()}]))
    server = ThreadingHTTPServer(('127.0.0.1', 0), PreviewHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
            page.goto(f'http://127.0.0.1:{server.server_port}/manufacture-claims.html')
            add = page.locator('[data-mc-add-image]')
            expect(add).to_be_enabled()
            with page.expect_file_chooser() as chooser:
                add.click()
            with page.expect_response(lambda response: response.request.method == 'POST' and response.url.endswith('/photos')):
                chooser.value.set_files({'name': 'added.png', 'mimeType': 'image/png', 'buffer': PNG})
            expect(page.locator('.mc-row-photos button')).to_have_count(2)
            expect(page.locator('.mc-dialog')).not_to_be_visible()
            saved = manufacture_claims.list_claims()['records'][0]
            assert saved['photos'][0] == original['photos'][0]
            assert saved['reason'] == 'Custom reason' and saved['createdAt'] == original['createdAt']
            page.reload()
            expect(page.locator('.mc-row-photos button')).to_have_count(2)
            with page.expect_file_chooser() as chooser:
                add.click()
            chooser.value.set_files([{'name': f'extra-{i}.png', 'mimeType': 'image/png', 'buffer': PNG} for i in range(3)])
            expect(add).to_be_disabled()
            expect(page.locator('.mc-photo-overflow')).to_have_text('+3')
            assert len(manufacture_claims.list_claims()['records'][0]['photos']) == 5
            page.locator('.mc-row-photos button').nth(2).click()
            expect(page.locator('.qd-gallery-viewer')).to_be_visible()
            browser.close()
            print('PASS: inline upload persists, preserves existing pictures/fields, stays out of editor, caps at five and opens gallery')
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
