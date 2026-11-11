"""Atlas colours in the right-hand Tracking details panel, including its tabs."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

original = (ROOT / 'static/css/tracking.css').read_text(encoding='utf-8').split('/* Shared Atlas order details')[0]
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width in (1440, 390):
        dimensions = None
        for themed in (False, True):
            context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
            page = context.new_page()
            page.set_default_timeout(5000)
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            page.route('https://deliverydesk.test/**', serve)
            page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
            if not themed:
                page.route('**/static/css/tracking.css', lambda route: route.fulfill(body=original, content_type='text/css'))
            page.goto('https://deliverydesk.test/pages/deliveries.html')
            page.wait_for_function("typeof R === 'function'")
            page.evaluate("""() => {
              DeliveryStore.hydrate({deliveries:[{id:'atlas-detail',order:'650001',
                cust:'Atlas customer',addr:'123 Example Street',phone:'0123456789',
                email:'customer@example.com',carrier:'Own van',st:'Scheduled',
                date:'2026-10-24',logs:[]}],activity:[],integrations:[]});
              D=DeliveryStore.deliveries();R();op('atlas-detail');
            }""")
            panel = page.locator('.dr.qd.qd-tracking-view')
            expect(panel).to_be_visible()
            sizes = panel.evaluate("el => [...el.querySelectorAll('.qd-head,.qd-progress,.qd-section-tabs,.qd-customer-block')].map(e=>[e.getBoundingClientRect().width,e.getBoundingClientRect().height])")
            if not themed:
                dimensions = sizes
                context.close()
                continue
            assert all(width > 0 and height > 0 for width, height in sizes), sizes
            expect(panel.locator('.qd-detail-heading')).to_be_visible()
            assert len(panel.locator('.qd-summary').evaluate('el=>getComputedStyle(el).gridTemplateColumns').split()) == 2
            expect(panel).to_have_css('background-color', 'rgb(243, 246, 243)')
            expect(panel.locator('.db')).to_have_css('background-color', 'rgb(255, 255, 255)')
            expect(panel.locator('.qd-head-icon')).to_have_css('background-color', 'rgb(98, 103, 233)')
            expect(panel.locator('.qd-progress')).to_have_css('background-color', 'rgb(234, 250, 253)')
            for tab in panel.locator('.qd-section-tab').all():
                tab.click()
                expect(tab).to_have_css('color', 'rgb(110, 227, 238)')
                expect(tab).to_have_css('background-color', 'rgb(37, 44, 74)')
            panel.locator('.qd-section-tab').first.click()
            expect(page.locator('.sd')).to_have_css('background-color', 'rgb(23, 28, 53)')
            if width == 1440:
                panel.screenshot(path=str(ROOT / '.test-temp/atlas-order-detail.png'))
            context.close()
    browser.close()
    print('PASS: right-hand Tracking panel uses Atlas colours, tabs work, shared details grid and dark left sidebar preserved')
