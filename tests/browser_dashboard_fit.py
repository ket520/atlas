"""Verify desktop dashboard sizing with populated, empty and search states."""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


METRICS = '''() => {
    const box = element => {
        const rect = element.getBoundingClientRect();
        return {left: rect.left, top: rect.top, right: rect.right, bottom: rect.bottom,
                width: rect.width, height: rect.height};
    };
    return {
        width: innerWidth, height: innerHeight,
        pageWidth: document.documentElement.scrollWidth,
        pageHeight: document.documentElement.scrollHeight,
        mainOverflow: document.querySelector('main').scrollHeight - document.querySelector('main').clientHeight,
        lists: [...document.querySelectorAll('.dash-widget')].map(box),
        widgetOverflow: [...document.querySelectorAll('.dash-widget')].filter(e => e.scrollHeight > e.clientHeight + 1 || e.scrollWidth > e.clientWidth + 1).map(e => e.dataset.dashWidget),
        controls: [...document.querySelectorAll('.db-search, .dash-utilities, .dash-filter-row, .dash-workspace-heading')].map(box),
    };
}'''


def check_dashboard():
    sizes = [(761, 480), (800, 600), (960, 540), (1024, 600), (1024, 768),
             (1180, 664), (1280, 600), (1280, 720), (1280, 800), (1366, 768),
             (1440, 810), (1440, 900), (1536, 864), (1600, 900), (1920, 1080),
             (1920, 1200), (2560, 1080), (2560, 1440), (2560, 1600),
             (3440, 1440), (3840, 2160)]
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        page.wait_for_selector('.dash-widget')
        checks = 0
        for populated in (False, True):
            page.evaluate('''populated => {
                const records = populated ? Array.from({length: 30}, (_, i) => ({
                    id: String(i), order: String(650000 + i), orderRef: 'LONG-REFERENCE-123456',
                    cust: 'Example customer with a long company name', carrier: 'Palletways',
                    st: i % 2 ? 'Failed' : 'Scheduled', date: localDateKey(), orderDate: localDateKey(),
                    bookingStatus: 'Out of Stock', deliveryMethodRaw: 'Palletways Next Day', palletwaysSheetBookedIn: 'No',
                    failedAt: localDateKey() + 'T10:30:00', reason: 'Unable to access property', logs: [],
                })) : [];
                DeliveryStore.hydrate({deliveries: records, activity: [], integrations: []});
                D = DeliveryStore.deliveries(); R();
            }''', populated)
            for width, height in sizes:
                page.set_viewport_size({'width': width, 'height': height})
                for collapsed in (False, True):
                    page.evaluate('collapsed => document.querySelector(".app").classList.toggle("cl", collapsed)', collapsed)
                    metrics = page.evaluate(METRICS)
                    context = (populated, collapsed, metrics)
                    assert metrics['pageWidth'] <= width + 1, context
                    assert metrics['pageHeight'] <= height + 1, context
                    assert metrics['mainOverflow'] <= 1, context
                    assert len(metrics['lists']) == 9, context
                    assert not metrics['widgetOverflow'], context
                    assert all(item['height'] >= 45 for item in metrics['lists']), context
                    assert all(item['bottom'] <= height + 1 and item['right'] <= width + 1
                               for item in metrics['controls'] + metrics['lists']), context
                    checks += 1
                    if populated:
                        page.locator('#dq').fill('Example')
                        page.evaluate('dq = "Example"; dres()')
                        assert page.locator('#dres .rc').count() == 6
                        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1')
                        page.locator('#dq').fill('')
                        page.evaluate('dq = ""; dres()')
        assert not errors, errors
        browser.close()
        print(f'PASS: {checks} desktop dashboard layouts, including empty/populated states, sidebar modes and search.')


if __name__ == '__main__':
    check_dashboard()
