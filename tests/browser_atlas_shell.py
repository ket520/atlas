"""Compare protected content before/after the scoped Atlas shell palette."""
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

MARKER = '/* Atlas shell palette'
original = (ROOT / 'static/css/general.css').read_text(encoding='utf-8').split(MARKER)[0]
# Dashboard controls now consume the brand tokens independently of shell styling.
original += ':root { --atlas-space:#171C35; --atlas-indigo:#6267E9; --atlas-cyan:#6EE3EE; --atlas-slate:#252C4A; }'
COLORS = """selector => [...document.querySelectorAll(selector)].map(el => {
  const s = getComputedStyle(el);
  return [s.color, s.backgroundColor, s.borderTopColor, s.borderRightColor,
    s.borderBottomColor, s.borderLeftColor, s.fill, s.stroke,
    s.width, s.height, s.fontSize];
})"""

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    baseline = {}
    for themed in (False, True):
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
        page = context.new_page()
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        if not themed:
            page.route('**/static/css/general.css', lambda route: route.fulfill(body=original, content_type='text/css'))
        for name in ('dashboard', 'deliveries', 'failed-deliveries', 'settings', 'integrations'):
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.wait_for_function("typeof R === 'function'")
            if name in ('deliveries', 'failed-deliveries'):
                page.evaluate("""() => {
                  DeliveryStore.hydrate({deliveries:[{id:'atlas-test',order:'650001',
                    orderRef:'REF-650001',carrier:'Palletways',cust:'Test customer',
                    st:page === 'Deliveries' ? 'Scheduled' : 'Failed',logs:[]}],activity:[],integrations:[]});
                  D=DeliveryStore.deliveries();R();
                }""")
                page.wait_for_selector('.tracking-row')
            protected = '.dashboard-home, .dashboard-home *' if name == 'dashboard' else 'table, table *'
            colors = page.evaluate(COLORS, protected)
            if not themed:
                baseline[name] = colors
                if name == 'dashboard':
                    page.locator('.mn').click()
                    baseline['dashboard-toggled'] = page.evaluate(COLORS, protected)
                continue
            assert colors == baseline[name], f'Protected content changed on {name}'
            expect(page.locator('.sd')).to_have_css('background-color', 'rgb(23, 28, 53)')
            expect(page.locator('.sd a.on')).to_have_css('background-color', 'rgb(98, 103, 233)')
            expect(page.locator('.hd .av')).to_have_css('background-color', 'rgb(110, 227, 238)')
            page.evaluate("toast('Atlas interface check')")
            expect(page.locator('.toast').last).to_have_css('background-color', 'rgb(37, 44, 74)')
            if name == 'dashboard':
                page.screenshot(path=str(ROOT / '.test-temp/atlas-dashboard.png'))
                page.locator('.mn').click()
                expect(page.locator('.sd')).to_have_css('background-color', 'rgb(23, 28, 53)')
                assert page.evaluate(COLORS, protected) == baseline['dashboard-toggled']
                page.screenshot(path=str(ROOT / '.test-temp/atlas-collapsed.png'))
        context.close()
    context = browser.new_context(viewport={'width': 390, 'height': 844}, reduced_motion='reduce')
    page = context.new_page()
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.locator('.mn').click()
    expect(page.locator('.sd')).to_be_visible()
    expect(page.locator('.sd')).to_have_css('background-color', 'rgb(23, 28, 53)')
    expect(page.locator('.sd a.on')).to_have_css('background-color', 'rgb(98, 103, 233)')
    page.locator('.sidebar-close').click()
    expect(page.locator('.app')).not_to_have_class('app mobile-open')
    context.close()
    browser.close()
    print('PASS: Atlas shell on five pages; dashboard and table colours and dimensions unchanged')
