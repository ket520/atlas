"""Exercise cold startup and interrupted JS downloads with local browser fixtures.

Run: python tests/browser_startup.py (requires Playwright Chromium).
"""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


def check_startup():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        checks = 0
        for returning in [False, True]:
            context = browser.new_context(reduced_motion='reduce')
            if returning:
                context.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            for name in ['index','dashboard','deliveries','failed-deliveries','integrations','settings','guidance','collective-note','manufacture-claims']:
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('https://deliverydesk.test/**', serve)
                page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
                page.route('**/api/**', lambda r: r.fulfill(json={'records': [], 'deliveries': [], 'total': 0}))
                page.goto(f'https://deliverydesk.test/pages/{name}.html')
                page.wait_for_function('''() => {
                    const view=document.getElementById('v');
                    return view.textContent.trim().length>30 && !view.querySelector('[data-startup-loading]');
                }''')
                assert not errors, (name, errors)
                assert page.locator('.startup-load-error').count() == 0, name
                page.close()
                checks += 1
            for module in ['horizontal-scroll','api','data','services','ui','dashboard-home','dashboard','deliveries','admin','app']:
                page = context.new_page()
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.route('https://deliverydesk.test/**', serve)
                page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
                requests = []

                def interrupt_once(route):
                    requests.append(route.request.url)
                    if len(requests) == 1:
                        route.abort()
                    else:
                        serve(route)

                page.route(f'**/src/{module}.js*', interrupt_once)
                page.goto('https://deliverydesk.test/pages/dashboard.html')
                page.locator('.dashboard-home').wait_for(state='attached', timeout=10000)
                assert len(requests) == 2, (module, requests)
                assert not errors, (module, errors)
                assert page.locator('#side a').count() == 13
                assert page.locator('.startup-load-error').count() == 0
                page.close()
                checks += 1

            for failed_file in ['admin', 'boot']:
                page = context.new_page()
                page.route('https://deliverydesk.test/**', serve)
                page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
                attempts = []

                def unavailable(route):
                    attempts.append(route.request.url)
                    route.abort()

                page.route(f'**/src/{failed_file}.js*', unavailable)
                page.goto('https://deliverydesk.test/pages/dashboard.html')
                page.get_by_role('button', name='Reload page', exact=True).wait_for(timeout=10000)
                assert len(attempts) == (3 if failed_file == 'admin' else 1), attempts
                assert page.locator('.desk-startup').count() == 0
                assert page.locator('.startup-load-error').is_visible()
                assert not page.locator('html').evaluate('(el)=>el.classList.contains("desk-starting")')
                page.close()
                checks += 1
            page = context.new_page()
            page.route('https://deliverydesk.test/**', serve)
            page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
            page.route('**/src/dashboard.js', lambda r: r.fulfill(
                body="throw new Error('Fixture runtime failure')", content_type='application/javascript'))
            page.goto('https://deliverydesk.test/pages/dashboard.html')
            page.get_by_role('button', name='Reload page', exact=True).wait_for(timeout=10000)
            assert page.locator('.startup-load-error').is_visible()
            page.close()
            checks += 1
            context.close()
        browser.close()
        print(f'PASS: {checks} first-visit/returning-visit startup checks; interrupted modules recover in order and persistent failures show a visible reload action.')


if __name__ == '__main__':
    check_startup()
