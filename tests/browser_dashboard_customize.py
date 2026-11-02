from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    before = page.locator('#dash-widget-grid').bounding_box()
    page.locator('[data-dash-customize]').click()
    expect(page.locator('.app')).to_have_class('app cl')
    assert abs(before['y'] - page.locator('#dash-widget-grid').bounding_box()['y']) < 1
    expect(page.locator('.dash-editor header, .dash-editor footer')).to_have_count(0)
    expect(page.locator('.dash-picker-tile')).to_have_count(9)
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x1"]')).to_have_count(0)
    metrics=page.locator('.dash-picker-track').evaluate('(el)=>({cols:getComputedStyle(el).gridTemplateColumns.split(" ").length,rows:getComputedStyle(el).gridTemplateRows.split(" ").length,w:el.clientWidth,sw:el.scrollWidth,h:el.clientHeight,sh:el.scrollHeight})')
    assert metrics['cols']==9 and metrics['rows']==2 and metrics['sw']==metrics['w'] and metrics['sh']==metrics['h'],metrics
    page.evaluate("window.pickerNode=document.querySelector('.dash-editor');window.cardNode=document.querySelector('.dash-widget')")
    page.locator('[data-picker-filter="1x1"]').click()
    assert page.evaluate("pickerNode===document.querySelector('.dash-editor') && cardNode===document.querySelector('.dash-widget')")
    expect(page.locator('.dash-picker-tile')).to_have_count(0)
    page.locator('[data-picker-filter="all"]').click()
    tile=page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')
    tile.click()
    expect(page.locator('.dash-widget-tall')).to_have_count(0)
    source=tile.bounding_box()
    page.mouse.move(source['x']+source['width']/2, source['y']+source['height']/2)
    page.mouse.down()
    page.mouse.move(source['x']+source['width']/2+10, source['y']+source['height']/2+10)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    expect(page.locator('.dash-widget-drag-preview .dash-widget-head')).to_be_visible()
    expect(page.locator('.dash-widget-drag-preview .dash-table-scroll')).to_be_visible()
    grid=page.locator('#dash-widget-grid').bounding_box()
    page.mouse.move(grid['x']+grid['width']/6, grid['y']+grid['height']/2)
    expect(page.locator('.dash-picker-slots .is-widget-drop-ready')).to_have_count(1)
    floating=page.locator('.dash-widget-drag-preview').bounding_box()
    assert abs(floating['x']+floating['width']/2-(grid['x']+grid['width']/6)) < 1
    assert abs(floating['y']+floating['height']/2-(grid['y']+grid['height']/2)) < 1
    page.mouse.up()
    expect(page.locator('.dash-widget-tall')).to_have_count(1)
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')).to_have_count(0)
    for key in ['cancelled','collect','palletways-unbooked']:
        expect(page.locator(f'[data-picker-key="{key}"][data-picker-size="1x1"]')).to_have_count(1)
    expect(page.locator('[data-dash-widget="collect"]')).to_have_count(0)
    expect(page.locator('[data-dash-widget="palletways-unbooked"]')).to_have_count(0)
    assert abs(before['y'] - page.locator('#dash-widget-grid').bounding_box()['y']) < 1
    tall=page.locator('.dash-widget-tall').bounding_box()
    assert abs(tall['height'] - page.locator('#dash-widget-grid').bounding_box()['height'])<2
    page.screenshot(path='tests/dashboard-widget-gallery.png')
    page.reload()
    expect(page.locator('.dash-widget-tall')).to_have_count(1)
    page.locator('[data-dash-customize]').click()
    page.locator('[data-picker-remove="cancelled--1x3"]').click()
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')).to_have_count(1)
    page.locator('[data-dash-customize]').click()
    expect(page.locator('.dash-editor')).to_have_count(0)
    assert not errors,errors
    print('PASS: fixed 9-column/2-row picker, no scrolling/header, drag-only addition, three-widget replacement, available versions, auto-save and close')
    browser.close()

