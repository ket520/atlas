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
    page.locator('[data-dash-customize]').click()
    for key in ['cancelled','returns']:
        tile=page.locator(f'[data-picker-key="{key}"][data-picker-size="1x3"]')
        page.evaluate('document.getAnimations().filter(a=>a.effect.getTiming().iterations!==Infinity).forEach(a=>a.finish())')
        icon=tile.locator('.dash-picker-icon').bounding_box()
        rect=tile.bounding_box()
        page.mouse.move(rect['x']+rect['width']/2,rect['y']+rect['height']/2)
        page.mouse.down()
        page.mouse.move(rect['x']+rect['width']/2+8,rect['y']+rect['height']/2+8)
        preview=page.locator('.dash-widget-drag-preview')
        preview.evaluate('(el)=>el.getAnimations().forEach(a=>{a.pause();a.currentTime=0})')
        start=preview.bounding_box()
        for prop in ['x','y','width','height']:
            assert abs(start[prop]-icon[prop])<1,(key,prop,start,icon)
        page.keyboard.press('Escape')
        page.mouse.up()
        expect(page.locator('.dash-picker-drag-shell')).to_have_count(0)
    browser.close()
    print('PASS: left and right menu icons are the exact pickup origins; cancellation cleans up preview')

