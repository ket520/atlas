"""Check the seven-link carousel, automatic motion and inactive workflows."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


def check_quick_links():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='no-preference')
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        page.wait_for_selector('.dash-quick-page')
        page.mouse.move(1430, 890)
        page.wait_for_function("document.querySelector('[data-quick-batch]').textContent==='2 / 2'", timeout=7000)
        frames = page.locator('.dash-quick-viewport').evaluate('''element => element.getAnimations({subtree:true})
            .flatMap(animation => animation.effect.getKeyframes()).map(frame => frame.transform)''')
        assert 'translateX(-100%)' in frames, frames
        expect(page.locator('.dash-quick-page')).to_have_count(1)
        expect(page.locator('.dash-quick')).to_have_count(7)
        second = page.locator('.dash-quick-name').all_text_contents()
        assert second == ['Manufacture Claims', 'Logistics Claims', 'Refund',
                          'Integration & Data Trafficking', 'Guidance', 'Settings', 'Dashboard'], second
        page.locator('.dash-quick-links').hover()
        page.wait_for_timeout(5200)
        expect(page.locator('[data-quick-batch]')).to_have_text('2 / 2')
        assert page.locator('[data-quick-action]').count() == 1
        assert page.locator('[data-quick-action="next"]').count() == 1
        page.emulate_media(reduced_motion='reduce')
        page.locator('[data-quick-action="next"]').click()
        expect(page.locator('[data-quick-batch]')).to_have_text('1 / 2')
        expect(page.locator('.dash-quick')).to_have_count(7)
        first = page.locator('.dash-quick-name').all_text_contents()
        assert first == ['Dashboard', 'Tracking', 'Failed Deliveries', 'Replacement',
                         'Collection Notes', 'Return', 'Free Return'], first
        sidebar = page.locator('#side .sidebar-link-label').evaluate_all(
            "elements => elements.map(element => element.childNodes[0].textContent)")
        assert set(first + second) == set(sidebar)
        planned = page.locator('.dash-quick[data-dash-planned="2"]')
        assert planned.get_attribute('aria-disabled') == 'true'
        url = page.url
        planned.click(force=True)
        assert page.url == url
        page.locator('.dash-quick[data-page-target="Deliveries"]').click()
        expect(page.locator('.fx-title')).to_have_text('Tracking')
        page.locator('#side [data-page-target="Dashboard"]').click()
        expect(page.locator('.dash-quick')).to_have_count(7)
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1')
        assert not errors, errors
        browser.close()
        print('PASS: sidebar parity, seven-item batches, automatic left slide, hover, next-only looping, reduced motion and inactive versions.')


if __name__ == '__main__':
    check_quick_links()
