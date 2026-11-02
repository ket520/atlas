"""Check live animated widget swaps before release, persistence, and cancellation."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


def check_drag():
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='no-preference')
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('https://deliverydesk.test/pages/dashboard.html')
        page.wait_for_selector('.dash-widget')
        card = lambda key: page.locator(f'[data-dash-widget="{key}"]')
        slot = lambda key: page.locator(f'[data-widget-slot="{key}"]')
        keys = lambda: page.locator('.dash-widget').evaluate_all('items => items.map(item => item.dataset.dashWidget)')
        original = keys()

        def begin(key):
            rect = card(key).bounding_box()
            page.mouse.move(rect['x'] + 10, rect['y'] + 12)
            page.mouse.down()
            page.mouse.move(rect['x'] + 22, rect['y'] + 24)

        def move(rect):
            floating = page.locator('.dash-widget-drag-preview').bounding_box()
            x = rect['x'] + (rect['width'] - floating['width']) / 2 + 10 * .94
            y = rect['y'] + (rect['height'] - floating['height']) / 2 + 12 * .94
            page.mouse.move(x, y)
            page.mouse.move(x + 1, y + 1)
            return x + 1, y + 1

        def overlap(rect, fraction):
            floating = page.locator('.dash-widget-drag-preview').bounding_box()
            x = rect['x'] + rect['width'] - floating['width'] * fraction + 10 * .94
            y = rect['y'] + (rect['height'] - floating['height']) / 2 + 12 * .94
            page.mouse.move(x, y)

        source_before = card('collect').bounding_box()
        target_before = card('hold').bounding_box()
        begin('collect')
        floating = page.locator('.dash-widget-drag-preview')
        expect(floating).to_be_visible()
        pickup = floating.bounding_box()
        assert abs(pickup['width'] - source_before['width'] * .94) < 1
        assert abs(pickup['x'] + 10 * .94 - (source_before['x'] + 22)) < 1
        assert abs(pickup['y'] + 12 * .94 - (source_before['y'] + 24)) < 1
        assert floating.evaluate('(item) => getComputedStyle(item).opacity') == '1'
        assert card('collect').evaluate('(item) => getComputedStyle(item).opacity') == '0'
        assert slot('collect').evaluate('(item) => getComputedStyle(item, "::after").content') == '"+"'
        assert slot('collect').evaluate('(item) => getComputedStyle(item).borderTopColor') == 'rgb(183, 189, 199)'
        source_slot_before = slot('collect').bounding_box()
        target_slot_before = slot('hold').bounding_box()
        assert card('collect').locator('.dash-widget-head').evaluate('(item) => getComputedStyle(item).visibility') == 'hidden'
        overlap(target_before, .79)
        assert not card('collect').evaluate('(item) => item.classList.contains("is-widget-drop-ready")')
        assert slot('hold').evaluate('(item) => getComputedStyle(item).borderTopStyle') == 'dashed'
        assert card('hold').evaluate('(item) => item.style.order') == ''
        overlap(target_before, .81)
        assert card('collect').evaluate('(item) => item.classList.contains("is-widget-drop-ready")')
        assert slot('hold').evaluate('(item) => getComputedStyle(item).borderTopStyle') == 'solid'
        assert slot('hold').evaluate('(item) => getComputedStyle(item).borderTopColor') == page.locator('#side').evaluate('(item) => getComputedStyle(item).backgroundColor')
        cursor = move(target_before)
        following = floating.bounding_box()
        assert abs(following['x'] + 10 * .94 - cursor[0]) < 1
        assert abs(following['y'] + 12 * .94 - cursor[1]) < 1
        assert card('collect').evaluate('(item) => item.classList.contains("is-widget-dragging")')
        assert card('hold').evaluate('(item) => item.style.order') == str(original.index('collect'))
        assert card('hold').evaluate('(item) => item.getAnimations().length') > 0
        page.wait_for_timeout(350)
        hold_now = card('hold').bounding_box()
        assert abs(hold_now['x'] - source_before['x']) < 1
        assert abs(hold_now['y'] - source_before['y']) < 1
        assert slot('collect').bounding_box() == source_slot_before
        assert slot('hold').bounding_box() == target_slot_before
        assert page.locator('.dash-widget-slot').evaluate_all('(items) => items.every(item => item.getAnimations().length === 0)')
        assert page.evaluate("localStorage.getItem('deliverydesk-dashboard-widgets-v1')") is None
        page.mouse.up()
        swapped = original[:]
        first, second = swapped.index('collect'), swapped.index('hold')
        swapped[first], swapped[second] = swapped[second], swapped[first]
        assert keys() == swapped, (keys(), swapped)
        assert page.evaluate("JSON.parse(localStorage.getItem('deliverydesk-dashboard-widgets-v1'))") == swapped

        # Passing another slot first must not permanently shift intermediate tiles.
        page.wait_for_timeout(350)
        middle = card('palletways-next-day').bounding_box()
        destination = card('charge-pending').bounding_box()
        begin('returns')
        move(middle)
        page.wait_for_timeout(350)
        move(destination)
        page.wait_for_timeout(350)
        page.mouse.up()
        expected = swapped[:]
        first, second = expected.index('returns'), expected.index('charge-pending')
        expected[first], expected[second] = expected[second], expected[first]
        assert keys() == expected, keys()

        # An outside drop restores the current saved order, rather than saving a preview.
        page.wait_for_timeout(350)
        destination = card('hold').bounding_box()
        begin('collect')
        move(destination)
        page.mouse.move(1400, 30)
        page.mouse.up()
        page.wait_for_timeout(350)
        assert keys() == expected
        assert page.evaluate("JSON.parse(localStorage.getItem('deliverydesk-dashboard-widgets-v1'))") == expected
        assert page.locator('.is-widget-dragging, .is-widget-lifted, .is-widget-reordering').count() == 0
        expect(floating).to_have_count(0)
        # Leaving a valid slot below 80% resets its border and rejects the drop.
        destination = card('hold').bounding_box()
        begin('collect')
        move(destination)
        assert card('collect').evaluate('(item) => item.classList.contains("is-widget-drop-ready")')
        overlap(destination, .79)
        assert not card('collect').evaluate('(item) => item.classList.contains("is-widget-drop-ready")')
        assert slot('hold').evaluate('(item) => getComputedStyle(item).borderTopStyle') == 'dashed'
        page.mouse.up()
        page.wait_for_timeout(350)
        assert keys() == expected
        destination = card('collect').bounding_box()
        begin('hold')
        move(destination)
        page.keyboard.press('Escape')
        page.mouse.up()
        page.wait_for_timeout(350)
        assert keys() == expected
        expect(floating).to_have_count(0)
        assert not page.locator('body').evaluate('(item) => item.classList.contains("is-dashboard-dragging")')
        expect(page.locator('.dash-widget-slots')).to_have_count(0)
        page.reload()
        page.wait_for_selector('.dash-widget')
        assert keys() == expected
        assert page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1')
        assert not errors, errors
        browser.close()
        print('PASS: stationary grey slot layer, opaque floating card, animated real-card swaps, 80% green border, cancellation, cleanup and persistence.')


if __name__ == '__main__':
    check_drag()
