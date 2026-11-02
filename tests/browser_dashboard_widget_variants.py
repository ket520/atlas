from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.locator('[data-dash-customize]').click()
    tile=page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')
    rect=tile.bounding_box()
    page.mouse.move(rect['x']+rect['width']/2,rect['y']+rect['height']/2)
    page.mouse.down()
    page.mouse.move(rect['x']+rect['width']/2+10,rect['y']+rect['height']/2+10)
    grid=page.locator('#dash-widget-grid').bounding_box()
    page.mouse.move(grid['x']+grid['width']/2,grid['y']+grid['height']/2)
    page.mouse.up()
    expect(page.locator('[data-dash-widget="cancelled"]')).to_have_count(1)
    expect(page.locator('[data-dash-widget="cancelled--1x3"]')).to_have_count(1)
    expect(page.locator('[data-picker-key="cancelled"]')).to_have_count(0)
    assert page.locator('[data-dash-widget="cancelled"]').evaluate('(el)=>el.style.gridColumn')=='1'
    assert page.locator('[data-dash-widget="cancelled--1x3"]').evaluate('(el)=>el.style.gridColumn')=='2'
    assert page.locator('[id^="dash-title-cancelled"]').evaluate_all('els=>new Set(els.map(el=>el.id)).size')==2
    expect(page.locator('[data-dash-widget="cancelled--1x3"] [data-dash-view="cancelled"]')).to_have_count(1)
    page.reload()
    expect(page.locator('[data-dash-widget="cancelled"]')).to_have_count(1)
    expect(page.locator('[data-dash-widget="cancelled--1x3"]')).to_have_count(1)
    page.locator('[data-dash-customize]').click()
    page.locator('[data-picker-remove="cancelled"]').click()
    expect(page.locator('[data-dash-widget="cancelled--1x3"]')).to_have_count(1)
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x1"]')).to_have_count(1)
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')).to_have_count(0)
    page.locator('[data-picker-remove="cancelled--1x3"]').click()
    expect(page.locator('[data-picker-key="cancelled"]')).to_have_count(2)
    assert not errors,errors
    browser.close()
    print('PASS: summary and table of same widget coexist, keep distinct positions and titles, persist, use same cohort, and remove independently')

