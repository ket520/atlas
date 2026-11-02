"""Saved-note downloads reuse the editor's measured layout without leaving records."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/collective-note.html?view=create')
    page.locator('.cn-paper input[name="order"]').wait_for()
    paper = page.locator('.cn-paper').evaluate('''el => {
      el.querySelector('[name="order"]').setAttribute('value', '663132');
      el.querySelector('[name="customer"]').setAttribute('value', 'Saved customer');
      el.querySelector('[name="orderRef"]').setAttribute('value', 'REF-123');
      return el.innerHTML;
    }''')
    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id': 'saved', 'order': '663132', 'orderRef': 'REF-123', 'customer': 'Saved customer'}
    ]}))
    page.route('**/api/collection-notes/saved', lambda route: route.fulfill(json={'id': 'saved', 'paper': paper}))
    exports = []
    def export(route):
        payload = route.request.post_data_json
        exports.append(payload)
        route.fulfill(body=b'export fixture', content_type='application/octet-stream',
                      headers={'Content-Disposition': f'attachment; filename="collection-note.{payload["format"]}"'})
    page.route('**/api/collection-note/export', export)
    page.goto('https://deliverydesk.test/pages/collective-note.html')
    expect(page.locator('[data-download-collection-record]')).to_have_count(2)
    for width in [1920, 1440, 1280, 390]:
        page.set_viewport_size({'width': width, 'height': 900})
        boxes = page.locator('.collection-record-actions').evaluate('''el =>
          [...el.children].map(child=>{const r=child.getBoundingClientRect();return [r.top,r.bottom]})''')
        assert max(box[0] for box in boxes) < min(box[1] for box in boxes), (width, boxes)
        contained = page.locator('.collection-record-actions').evaluate('''el => {
          const cell=el.closest('td').getBoundingClientRect();
          return [...el.children].every(child=>child.getBoundingClientRect().right <= cell.right - 2);
        }''')
        assert contained, f'Actions overflow their cell at {width}px'
    page.set_viewport_size({'width': 1440, 'height': 900})
    for format in ['pdf', 'xlsx']:
        button = page.locator(f'[data-download-collection-record][data-format="{format}"]')
        with page.expect_download() as download:
            button.click()
        assert download.value.suggested_filename == f'collection-note.{format}'
        expect(button).to_be_enabled()
        assert page.url.endswith('/pages/collective-note.html')
        cells = [cell['text'] for row in exports[-1]['rows'] for cell in row['cells']]
        assert 'Saved customer' in cells, cells
        assert 'REF-123' in cells, cells
        assert 100 <= exports[-1]['width'] <= 2000
    browser.close()
    print('PASS: actions stay in one row; PDF/XLSX download saved note layout and leave records open')
