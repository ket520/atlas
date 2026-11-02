"""View all exposes matching Tracking controls for both dashboard widget sizes."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

CASES = [
    ('charge-pending', 'Charge Pending (Remote Postcode)', '', 'Charge Pending'),
    ('collect', 'Collect in Person', '', 'Collect in Person'),
    ('hold', 'On Hold', '', 'On Hold'),
    ('cancelled', 'Cancelled', '', 'Order date: today'),
    ('palletways-next-day', '', 'Palletways', 'Next Day'),
    ('palletways-unbooked', '', 'Palletways', 'Booked in: No'),
    ('out-of-stock', '', '', 'Out of Stock'),
    ('van-unscheduled', '', 'Own van / Self Delivery', 'Unscheduled'),
]

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    for size in ('1x1','1x3'):
        for key, scope, carrier, description in CASES:
            page.evaluate("([key,size])=>{localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify([key]));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({[key]:size,[key+'-slot']:0}));}",[key,size])
            page.goto('https://deliverydesk.test/pages/dashboard.html')
            page.locator(f'[data-dash-widget="{key}"] [data-dash-view]').click()
            assert page.evaluate('trackingScope') == scope
            assert page.evaluate('fsrc') == carrier
            expect(page.locator(f'[data-delivery-filter-action="general"][data-value="{scope}"]')).to_have_attribute('aria-selected','true')
            expect(page.locator('.tracking-widget-conditions')).to_contain_text(description)
            if key == 'palletways-unbooked':
                assert page.evaluate('fbookedIn') == 'no'
            page.reload()
            expect(page.locator('.tracking-widget-conditions')).to_contain_text(description)
            assert page.evaluate('trackingScope') == scope
            assert page.evaluate('fsrc') == carrier
            page.locator('[data-dash-clear-cohort]').click()
            expect(page.locator('.tracking-widget-conditions')).to_have_count(0)
            assert page.evaluate("!dashboardWidgetFilter && !trackingScope && !fsrc && !fbookedIn")
    browser.close()
    print('PASS: both widget sizes map visible filter controls, describe compound conditions, survive reload and clear')
