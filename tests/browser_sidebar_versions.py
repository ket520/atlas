"""Check planned sidebar entries and the Manufacture Claims page with local fixtures."""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


def check_sidebar():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(reduced_motion='reduce')
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        page.wait_for_selector('.side-main a')
        labels = page.locator('.side-main a').all_text_contents()
        assert [''.join(label.split()) for label in labels] == [
            'Dashboard', 'Tracking', 'FailedDeliveries', 'ReplacementV2',
            'CollectionNotes', 'ReturnV3', 'FreeReturnV3', 'ManufactureClaims',
            'LogisticsClaimsV3', 'RefundV2',
        ], labels
        assert page.locator('.side-main [aria-disabled="true"]').count() == 5
        assert page.locator('.side-main [aria-disabled="true"][href]').count() == 0
        for width, height in [(1440, 900), (1024, 600), (390, 844)]:
            page.set_viewport_size({'width': width, 'height': height})
            for collapsed in ([False, True] if width > 760 else [False]):
                page.evaluate('''collapsed => {
                    document.querySelector('.app').classList.toggle('cl', collapsed);
                    document.querySelector('.app').classList.toggle('mobile-open', innerWidth <= 760);
                }''', collapsed)
                item = page.locator('[data-sidebar-hint^="Replacement"]')
                page.mouse.move(width - 5, height - 5)
                item.scroll_into_view_if_needed()
                page.wait_for_timeout(100)
                item.hover()
                assert page.locator('#sidebar-hint').is_visible()
                assert 'Version 2' in page.locator('#sidebar-hint').inner_text()
                before = page.url
                # Planned links deliberately expose aria-disabled to automation.
                item.click(force=True)
                assert page.url == before
                page.keyboard.press('Escape')
                assert not page.locator('#sidebar-hint').is_visible()
                item.blur()
                item.focus()
                assert page.locator('#sidebar-hint').is_visible()
                page.locator('[data-sidebar-hint^="Refund"]').scroll_into_view_if_needed()
                assert page.locator('[data-sidebar-hint^="Refund"]').is_visible()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                if not collapsed:
                    overflow = page.locator('.side-main a').evaluate_all('''items => items.filter(item =>
                        item.querySelector('.sidebar-link-label').getBoundingClientRect().right
                        > item.getBoundingClientRect().right
                    ).map(item => item.textContent.trim())''')
                    assert not overflow, (width, overflow)
        page.set_viewport_size({'width': 1440, 'height': 900})
        page.evaluate("document.querySelector('.app').classList.remove('cl', 'mobile-open')")
        page.locator('#side [data-page-target="Manufacture Claims"]').click()
        assert page.url.endswith('/manufacture-claims.html')
        assert page.locator('h1').inner_text() == 'Manufacture Claims'
        page.goto('https://deliverydesk.test/pages/manufacture-claims.html')
        page.wait_for_selector('.manufacture-claims-placeholder')
        assert not errors, errors
        browser.close()
        print('PASS: sidebar order, versions, inactive items, hints, responsive fit and claims page.')


if __name__ == '__main__':
    check_sidebar()
