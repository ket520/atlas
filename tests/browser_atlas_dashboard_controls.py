"""Check themed dashboard controls without altering widget palettes or heights."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

original = (ROOT / 'static/css/dashboard-home.css').read_text(encoding='utf-8').split('/* Atlas dashboard controls;')[0]
MEASURE = """() => ({
  heights: [...document.querySelectorAll('.dash-workspace-actions button, .dash-collection form button, .db-search-button')].map(el => el.getBoundingClientRect().height),
  widgets: [...document.querySelectorAll('.dash-widget, .dash-widget *')].map(el => {
    const s=getComputedStyle(el);
    return [s.color,s.backgroundColor,s.borderTopColor,s.borderLeftColor,s.width,s.height];
  })
})"""
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width in (1440, 390):
        before = None
        for themed in (False, True):
            context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
            page = context.new_page()
            page.set_default_timeout(5000)
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
            page.route('https://deliverydesk.test/**', serve)
            page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
            if not themed:
                page.route('**/static/css/dashboard-home.css', lambda route: route.fulfill(body=original, content_type='text/css'))
            page.goto('https://deliverydesk.test/pages/dashboard.html')
            page.wait_for_selector('.dash-widget')
            if not themed:
                before = page.evaluate(MEASURE)
                context.close()
                continue
            assert page.evaluate(MEASURE) == before, (width, 'Widget palettes or control heights changed')
            expect(page).to_have_title('Dashboard · Atlas')
            expect(page.locator('.side-logo-wordmark')).to_have_text('Atlas')
            expect(page.locator('.sidebar-app-icon img')).to_have_attribute('src', '/assets/atlas-sidebar.svg')
            page.wait_for_function("document.querySelector('.sidebar-app-icon img').naturalWidth > 0")
            expect(page.locator('.dash-searchbar')).to_have_css('background-color', 'rgb(23, 28, 53)')
            expect(page.locator('.db-search-button')).to_have_css('background-color', 'rgb(98, 103, 233)')
            expect(page.locator('.dash-collection form button')).to_have_css('background-color', 'rgb(98, 103, 233)')
            expect(page.locator('[data-dash-widget-guide]')).to_have_css('background-color', 'rgb(37, 44, 74)')
            if width == 1440:
                expect(page.locator('.dash-filter-chips button.is-active')).to_have_css('background-color', 'rgb(98, 103, 233)')
                page.locator('[data-dash-filter][data-value="Palletways"]').click()
                expect(page.locator('[data-dash-filter][data-value="Palletways"]')).to_have_attribute('aria-pressed', 'true')
                page.mouse.move(0, 0)
                page.screenshot(path=str(ROOT / '.test-temp/atlas-dashboard-controls.png'))
            page.locator('[data-dash-customize]').click()
            expect(page.locator('[data-dash-customize]')).to_have_css('color', 'rgb(110, 227, 238)')
            assert page.locator('[data-dash-customize]').bounding_box()['height'] == before['heights'][2]
            context.close()
    browser.close()
    print('PASS: Atlas branding and controls, unchanged heights and widget palettes at desktop/mobile widths')
