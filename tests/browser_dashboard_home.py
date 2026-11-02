"""Exercise dashboard filters, personalization, retries and Tracking navigation."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


KEYS = ['cancelled', 'hold', 'out-of-stock', 'charge-pending', 'collect',
        'palletways-next-day', 'palletways-unbooked', 'van-unscheduled', 'returns']


def check_dashboard():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        errors, calls, list_calls = [], [], []
        failing = [False]
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())

        def dashboard(route):
            params = parse_qs(urlparse(route.request.url).query)
            calls.append(params)
            if failing[0]:
                route.fulfill(status=503, json={'error': 'Fixture unavailable'})
                return
            count = 12 if not params.get('carrier') else 4
            route.fulfill(json={'syncedAt': '2026-10-23T10:00:00Z',
                'sourceUpdatedAt': {'ow': '2026-10-23T10:00:00Z'},
                'widgets': {key: {'available': key != 'returns', 'total': count, 'scope': {'cancelled': 'today', 'palletways-unbooked': 'booked-in-no-current-ow'}.get(key, ''),
                    'preview': [] if key == 'returns' else [{'id': '650001', 'order': '650001', 'orderDate': '2026-10-23'}]}
                    for key in KEYS}})

        def tracking(route):
            params = parse_qs(urlparse(route.request.url).query)
            list_calls.append(params)
            route.fulfill(json={'deliveries': [{'id': '650001', 'order': '650001', 'carrier': 'Palletways',
                'st': 'Unscheduled', 'cust': 'Fixture customer', 'date': '', 'logs': []}],
                'total': 4, 'hasMore': False, 'filterFacets': [{'carrier': 'Palletways',
                    'status': 'Unscheduled', 'purchaseStore': 'B&Q', 'count': 4}]})

        page.route('**/api/dashboard?*', dashboard)
        page.route('**/api/deliveries?*', tracking)
        page.route('**/api/deliveries/650001', lambda route: route.fulfill(json={
            'id': '650001', 'order': '650001', 'carrier': 'Palletways', 'st': 'Unscheduled',
            'cust': 'Fixture customer', 'addr': 'Example address', 'logs': [],
        }))
        page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        page.wait_for_selector('.dash-widget')
        page.evaluate("document.body.dataset.live='true'; liveReady=true; liveSummary={syncedAt:'2026-10-23T10:00:00Z',filterFacets:[]};R()")
        count = page.locator('[data-dash-widget="cancelled"] .dash-widget-total strong')
        expect(count).to_have_text('12')
        page.locator('[data-dash-order="650001"]').first.click()
        expect(page.locator('#dr .dr.qd')).to_be_visible()
        page.evaluate('DeliveryDetail.close()')
        expect(page.locator('#dr .dr.qd')).to_have_count(0)
        page.locator('[data-dash-widget="hold"]').drag_to(
            page.locator('[data-dash-widget="cancelled"]'),
            source_position={'x': 10, 'y': 12}, target_position={'x': 10, 'y': 12})
        assert page.locator('.dash-widget').first.get_attribute('data-dash-widget') == 'hold'
        page.locator('[data-dash-reset]').click()
        assert page.locator('[data-dash-filter="store"], [data-dash-select="store"]').count() == 0
        assert 'store' not in calls[-1]
        expect(page.locator('.dash-store-links a')).to_have_count(6)
        page.locator('[data-dash-filter="carrier"][data-value="Palletways"]').click()
        expect(count).to_have_text('4')
        assert calls[-1]['carrier'] == ['Palletways']

        page.locator('[data-dash-customize]').click()
        page.locator('[data-dash-enabled="returns"]').uncheck()
        page.locator('[data-dash-move="hold"][data-direction="-1"]').click()
        page.locator('[data-dash-dialog-save]').click()
        expect(page.locator('.dash-widget')).to_have_count(8)
        assert page.locator('.dash-widget').nth(1).get_attribute('data-dash-widget') == 'hold'
        assert page.evaluate("JSON.parse(localStorage.getItem('deliverydesk-dashboard-widgets-v1')).length") == 8
        page.reload()
        page.wait_for_selector('.dash-widget')
        expect(page.locator('.dash-widget')).to_have_count(8)
        page.locator('[data-dash-reset]').click()
        expect(page.locator('.dash-widget')).to_have_count(9)

        url = page.url
        page.locator('[data-dash-planned="2"]').first.click(force=True)
        assert page.url == url
        expect(page.locator('.toast').last).to_contain_text('Version 2')
        page.evaluate("document.body.dataset.live='true';liveReady=true;liveSummary={syncedAt:'2026-10-23T10:00:00Z',filterFacets:[]};R()")
        expect(count).to_have_text('12')
        page.locator('[data-dash-filter="carrier"][data-value="Palletways"]').click()
        expect(count).to_have_text('4')
        page.locator('[data-dash-widget="palletways-unbooked"] .dash-widget-foot button').click()
        expect(page.locator('.dash-cohort-filter')).to_contain_text('Palletways Unbooked')
        page.wait_for_selector('#tb .tracking-row')
        assert list_calls[-1]['dashboard_widget'] == ['palletways-unbooked']
        assert 'store' not in list_calls[-1]
        assert list_calls[-1]['carrier'] == ['Palletways']
        page.locator('[data-dash-clear-cohort]').click()
        expect(page.locator('.dash-cohort-filter')).to_have_count(0)
        page.locator('[data-page-target="Dashboard"]').click()
        expect(count).to_have_text('4')
        failing[0] = True
        page.evaluate('DashboardHome.load(true)')
        expect(page.locator('#dash-data-message')).to_contain_text('Last loaded counts are shown')
        expect(count).to_have_text('4')
        failing[0] = False
        page.locator('[data-dash-retry]').click()
        expect(page.locator('#dash-data-message')).to_be_hidden()
        assert not errors, errors
        browser.close()
        print('PASS: dashboard filters, order details, drag/reorder, personalization persistence/reset, planned actions, View all, retry and saved data.')


if __name__ == '__main__':
    check_dashboard()
