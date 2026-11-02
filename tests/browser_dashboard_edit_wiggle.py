from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='no-preference')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    assert page.locator('.dash-widget').first.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    rect=page.locator('[data-dash-widget="collect"]').bounding_box()
    page.mouse.move(rect['x']+10,rect['y']+12);page.mouse.down();page.mouse.move(rect['x']+25,rect['y']+25)
    expect(page.locator('.dash-editor')).to_have_count(0)
    assert page.locator('[data-dash-widget="hold"]').evaluate('(el)=>getComputedStyle(el).animationName')=='dash-edit-wiggle'
    assert page.locator('.dash-widget-drag-preview').evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    page.keyboard.press('Escape');page.mouse.up()
    expect(page.locator('.dash-widget-drag-preview')).to_have_count(0)
    assert page.locator('[data-dash-widget="hold"]').evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    page.locator('[data-dash-customize]').click()
    for selector in ['.dash-widget','.dash-picker-tile']:
        assert page.locator(selector).first.evaluate('(el)=>getComputedStyle(el).animationName')=='dash-edit-wiggle'
    card=page.locator('[data-dash-widget="collect"]')
    rect=card.bounding_box()
    page.mouse.move(rect['x']+10,rect['y']+12)
    page.mouse.down()
    page.mouse.move(rect['x']+25,rect['y']+25)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    assert card.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    page.keyboard.press('Escape')
    page.mouse.up()
    page.locator('[data-dash-customize]').click()
    expect(page.locator('.dash-editor')).to_have_count(0)
    assert page.locator('.dash-widget').first.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    page.emulate_media(reduced_motion='reduce')
    page.locator('[data-dash-customize]').click()
    for selector in ['.dash-widget','.dash-picker-tile']:
        assert page.locator(selector).first.evaluate('(el)=>getComputedStyle(el).animationName')=='none'
    browser.close()
    print('PASS: widget and tile wiggle only in edit mode, drag pauses wiggle, closing stops it, reduced motion is respected')
