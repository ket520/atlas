"""First-use walkthrough, dismissal persistence, keyboard and motion preferences."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width, motion in [(1440, 'no-preference'), (390, 'reduce')]:
        context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion=motion)
        page = context.new_page()
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        expect(page.locator('.dash-widget-tour')).to_have_count(0)
        page.locator('[data-dash-customize]').click()
        dialog = page.locator('.dash-widget-tour')
        expect(dialog).to_be_visible()
        expect(dialog.locator('h2')).to_have_text('Add a widget')
        assert dialog.evaluate('el => el.matches(":modal")')
        box = dialog.bounding_box()
        assert box['x'] >= 0 and box['x'] + box['width'] <= width
        assert dialog.evaluate('el => el.scrollWidth <= el.clientWidth')
        animation = dialog.locator('.dash-tour-demo-card').evaluate('el => getComputedStyle(el).animationName')
        assert animation == ('none' if motion == 'reduce' else 'dash-tour-add')
        page.keyboard.press('Enter')
        expect(dialog.locator('h2')).to_have_text('Make it your own')
        dialog.locator('[data-tour-back]').click()
        expect(dialog.locator('h2')).to_have_text('Add a widget')
        dialog.locator('[data-tour-next]').click()
        dialog.locator('[data-tour-next]').click()
        expect(dialog.locator('h2')).to_have_text('You’re all set')
        dialog.locator('[data-tour-next]').click()
        expect(dialog).to_have_count(0)
        expect(page.locator('.dash-editor')).to_be_visible()
        assert page.evaluate("localStorage.getItem('deliverydesk-widget-tour-v1')") == 'seen'
        page.reload()
        page.locator('[data-dash-widget-guide]').click()
        expect(dialog).to_be_visible()
        expect(dialog.locator('h2')).to_have_text('Add a widget')
        page.keyboard.press('Escape')
        expect(dialog).to_have_count(0)
        page.locator('[data-dash-customize]').click()
        page.wait_for_selector('.dash-editor', state='detached')
        page.locator('[data-dash-customize]').click()
        expect(dialog).to_have_count(0)
        page.locator('[data-dash-customize]').click()
        page.wait_for_selector('.dash-editor', state='detached')
        # Escape and Skip both persist dismissal without changing any widgets.
        for action in ['escape', 'skip']:
            page.evaluate("localStorage.removeItem('deliverydesk-widget-tour-v1')")
            before = page.locator('[data-dash-widget]').count()
            page.locator('[data-dash-customize]').click()
            expect(dialog).to_be_visible()
            if action == 'escape':
                page.keyboard.press('Escape')
            else:
                dialog.locator('[data-tour-close]').last.click()
            expect(dialog).to_have_count(0)
            assert page.locator('[data-dash-widget]').count() == before
            assert page.evaluate("localStorage.getItem('deliverydesk-widget-tour-v1')") == 'seen'
            page.locator('[data-dash-customize]').click()
            page.wait_for_selector('.dash-editor', state='detached')
        assert not errors, errors
        context.close()
    browser.close()
    print('PASS: first-click tour, three steps, keyboard, skip, persistence, mobile fit and reduced motion')
