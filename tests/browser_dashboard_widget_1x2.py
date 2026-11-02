from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    page.route("https://deliverydesk.test/**", serve)
    page.route("https://fonts.googleapis.com/**", lambda route: route.abort())
    page.add_init_script(
        "sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-widget-tour-v1','seen')"
    )
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("https://deliverydesk.test/pages/dashboard.html")
    page.locator("[data-dash-customize]").click()
    page.locator('[data-picker-filter="1x2"]').click()
    keys = []
    while True:
        keys.extend(
            page.locator("[data-picker-key]").evaluate_all(
                "tiles => tiles.map(tile => tile.dataset.pickerKey)"
            )
        )
        next_page = page.locator('[data-picker-page="1"]')
        if next_page.is_disabled():
            break
        next_page.click()
    assert len(set(keys)) == 13, keys
    for key in keys:
        page.evaluate(
            """key => {
            localStorage.setItem('deliverydesk-dashboard-widgets-v1', JSON.stringify([key + '--1x2', 'hold']));
            localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes', JSON.stringify({[key + '--1x2-slot']: 3, 'hold-slot': 0}));
        }""",
            key,
        )
        page.reload()
        card = page.locator('[data-dash-widget="' + key + '--1x2"]')
        expect(card).to_have_count(1)
        assert card.evaluate("el => el.style.gridRow") == "2 / span 2"
        assert (
            card.bounding_box()["height"]
            > page.locator('[data-dash-widget="hold"]').bounding_box()["height"] * 1.9
        )
    page.locator("[data-dash-customize]").click()
    page.locator('[data-picker-filter="1x2"]').click()
    (
        page.locator('[data-picker-page="-1"]').click()
        if not page.locator('[data-picker-page="-1"]').is_disabled()
        else None
    )
    tile = page.locator('[data-picker-key="cancelled"][data-picker-size="1x2"]')
    rect = tile.bounding_box()
    page.mouse.move(rect["x"] + rect["width"] / 2, rect["y"] + rect["height"] / 2)
    page.mouse.down()
    page.mouse.move(rect["x"] + rect["width"] / 2 + 12, rect["y"] + rect["height"] / 2 + 12)
    slot = page.locator(".dash-picker-slots .dash-widget-slot").nth(4).bounding_box()
    page.mouse.move(slot["x"] + slot["width"] * 0.47, slot["y"] + slot["height"] * 0.47)
    page.mouse.up()
    card = page.locator('[data-dash-widget="cancelled"]')
    expect(card).to_have_count(1)
    assert card.evaluate("el => el.style.gridRow") == "2 / span 2"
    page.reload()
    expect(page.locator('[data-dash-widget="cancelled"]')).to_have_count(1)
    assert not errors, errors
    browser.close()
    print(
        "PASS: every widget supports 1x2, gallery filtering, lower-row placement, drag insertion and persistence"
    )
