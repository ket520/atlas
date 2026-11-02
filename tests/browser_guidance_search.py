from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('https://deliverydesk.test/pages/guidance.html')
    expect(page.locator('.guidance-jumps')).to_have_count(0)
    toggle = page.get_by_role('button', name='Search guidance', exact=True)
    field = page.locator('[data-guidance-search]')
    expect(field).to_be_disabled()
    toggle.click()
    expect(field).to_be_focused()
    for query in ['Manufacturing Claims', '15 MB', 'UNDELIVERABLE', '_Sync_Control', '#FFFF00']:
        field.fill(query)
        expect(page.locator('[data-guidance-search-status]')).to_contain_text('matching guidance')
        assert page.locator('mark[data-guidance-match]').count() > 0, query
        assert page.locator('mark mark').count() == 0
    field.fill('[.+?')
    expect(page.locator('[data-guidance-search-status]')).to_contain_text('No guidance found')
    field.fill('UNDELIVERABLE')
    page.evaluate('R()')
    expect(field).to_have_value('UNDELIVERABLE')
    assert page.locator('mark[data-guidance-match]').count() > 0
    field.fill('')
    expect(page.locator('.guidance-workflow:visible')).to_have_count(6)
    expect(page.locator('mark[data-guidance-match]')).to_have_count(0)
    for width in [1440, 760, 390]:
        page.set_viewport_size({'width': width, 'height': 900})
        bounds = page.locator('.guidance-search').bounding_box()
        assert bounds['x'] >= 0 and bounds['x'] + bounds['width'] <= width + 1, (width, bounds)
        assert page.evaluate("getComputedStyle(document.documentElement).overflowX === 'clip'")
        assert page.locator('.guidance-table-scroll').evaluate_all("els=>els.every(el=>getComputedStyle(el).overflowX==='clip'&&el.scrollWidth<=el.clientWidth+1)")
    field.fill('XDP')
    field.press('Escape')
    expect(field).to_be_disabled()
    expect(toggle).to_have_attribute('aria-expanded', 'false')
    expect(page.locator('.guidance-workflow:visible')).to_have_count(6)
    expect(page.locator('mark[data-guidance-match]')).to_have_count(0)
    assert not errors, errors
    browser.close()
    print('PASS: expandable search covers workflows/source tables, highlights safely, retains query on render, resets and fits mobile')
