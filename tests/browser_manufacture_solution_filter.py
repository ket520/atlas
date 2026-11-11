"""Solution filtering combines with search/dates and limits claims exports."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, accept_downloads=True, reduced_motion='reduce')
    errors, exports = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/manufacture-claims', lambda route: route.fulfill(json={'records': [
        {'id': str(i), 'orderDate': f'2026-11-0{i}', 'originalOrderNo': f'65000{i}', 'replacementOrderNo': f'66000{i}', 'variantCode': 'SKU', 'reason': 'Scratches', 'solution': solution, 'sellingShop': 'Shop', 'photos': []}
        for i, solution in enumerate(('Replacement', 'Refund', 'Repair at customer home'), 1)
    ]}))
    def export(route):
        exports.append(route.request.post_data_json)
        route.fulfill(body=b'export fixture', content_type='application/octet-stream')
    page.route('**/api/manufacture-claims/export', export)
    page.goto('https://deliverydesk.test/pages/manufacture-claims.html')
    rows = page.locator('[data-mc-rows] > tr[data-mc-edit]')
    expect(rows).to_have_count(3)
    page.locator('[data-mc-sort-order-date]').click()
    expect(rows.first).to_have_attribute('data-mc-edit', '3')
    page.locator('[data-mc-sort-order-date]').click()
    expect(rows.first).to_have_attribute('data-mc-edit', '1')
    expect(page.locator('[data-mc-order-date-header]')).to_have_attribute('aria-sort', 'ascending')
    control = page.locator('[data-ui-select-id="mc-solution-filter"]')
    assert control.evaluate('el => el.previousElementSibling.classList.contains("mc-date-select")')
    def choose(value):
        control.locator('[data-ui-select-trigger]').click()
        control.locator(f'[data-ui-select-option][data-value="{value}"]').click()
    for solution, record_id in [('Replacement', '1'), ('Refund', '2'), ('Others', '3')]:
        choose(solution)
        expect(rows).to_have_count(1)
        expect(rows.first).to_have_attribute('data-mc-edit', record_id)
    page.locator('[data-mc-search]').fill('650001')
    expect(rows).to_have_count(0)
    expect(page.locator('.mc-empty')).to_contain_text('No claims match')
    page.locator('[data-mc-search]').fill('')
    choose('Refund')
    for format in ('pdf', 'xlsx'):
        with page.expect_download():
            page.locator(f'[data-mc-download="{format}"]').click()
        assert [row['id'] for row in exports[-1]['rows']] == ['2']
    page.locator('[data-mc-toggle-date]').click()
    page.locator('[data-mc-date="from"]').fill('2026-11-03')
    expect(rows).to_have_count(0)
    page.locator('[data-mc-clear-dates]').click()
    expect(rows).to_have_count(1)
    page.keyboard.press('Escape')
    choose('')
    expect(rows).to_have_count(3)
    for width in (1280, 390):
        page.set_viewport_size({'width': width, 'height': 900})
        choose('Replacement')
        expect(rows).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    assert not errors, errors
    browser.close()
    print('PASS: solution filter placement, custom Others, search/date combinations, filtered exports and mobile menu')
