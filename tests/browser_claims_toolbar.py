from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True)
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/manufacture-claims', lambda route: route.fulfill(json={'records': [
        {'id': 'one', 'originalOrderNo': '663132', 'replacementOrderNo': '700001', 'orderDate': '2026-10-01', 'variantCode': 'A', 'photos': []},
        {'id': 'two', 'originalOrderNo': '654171', 'replacementOrderNo': '700002', 'orderDate': '2026-09-15', 'variantCode': 'B', 'photos': []}
    ]}))
    exports = []
    def export(route):
        exports.append(route.request.post_data_json)
        route.fulfill(body=b'fixture', content_type='application/octet-stream')
    page.route('**/api/manufacture-claims/export', export)
    page.goto('https://deliverydesk.test/pages/manufacture-claims.html')
    rows = page.locator('[data-mc-rows] tr')
    expect(rows).to_have_count(2)
    search = page.locator('[data-mc-search]')
    search.fill('700002')
    expect(rows).to_have_count(1)
    expect(rows).to_contain_text('654171')
    search.fill('663132')
    expect(rows).to_have_count(1)
    search.fill('')
    date = page.locator('[data-mc-toggle-date]')
    assert page.locator('[data-mc-download="xlsx"]').evaluate('el=>el.previousElementSibling.classList.contains("mc-date-select")')
    for width in [1920, 1440, 1280, 1024]:
        page.set_viewport_size({'width': width, 'height': 900})
        boxes = page.locator('.mc-records-toolbar .delivery-search, .mc-records-toolbar .mc-actions > *').evaluate_all('els=>els.map(el=>{const r=el.getBoundingClientRect();return [r.top,r.bottom]})')
        assert max(box[0] for box in boxes) < min(box[1] for box in boxes), (width, boxes)
    date.click()
    menu = page.get_by_role('dialog', name='Claim order date range')
    assert abs(menu.bounding_box()['width'] - 260) < 1
    page.get_by_label('Claim date from', exact=True).fill('2026-09-01')
    page.get_by_label('Claim date to', exact=True).fill('2026-09-30')
    expect(rows).to_have_count(1)
    expect(rows).to_contain_text('654171')
    page.keyboard.press('Escape')
    for format in ['xlsx', 'pdf']:
        with page.expect_download():
            page.locator(f'[data-mc-download="{format}"]').click()
        assert [row['id'] for row in exports[-1]['rows']] == ['two']
    page.locator('[data-mc-refresh]').click()
    expect(rows).to_have_count(1)
    date.click()
    page.locator('[data-mc-clear-dates]').click()
    expect(rows).to_have_count(2)
    page.keyboard.press('Escape')
    browser.close()
    print('PASS: search original/replacement IDs, order-date range, 260px popup, toolbar row, filtered exports, refresh and clear')
