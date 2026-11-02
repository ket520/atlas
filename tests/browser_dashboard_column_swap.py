from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');if(!localStorage.getItem('deliverydesk-dashboard-widgets-v1')){localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['hold','collect','out-of-stock','cancelled','charge-pending']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'hold-slot':0,'collect-slot':3,'out-of-stock-slot':6,'cancelled':'1x3','cancelled-slot':1,'cancelled-column':1,'charge-pending-slot':2}));}""")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    def position(key):return page.locator(f'[data-dash-widget="{key}"]').evaluate('(el)=>[el.style.gridRow,el.style.gridColumn]')
    original={key:position(key) for key in ['hold','collect','out-of-stock','cancelled','charge-pending']}
    def move(source,target,cancel=False):
        rect=page.locator(f'[data-dash-widget="{source}"]').bounding_box()
        page.mouse.move(rect['x']+10,rect['y']+12);page.mouse.down();page.mouse.move(rect['x']+20,rect['y']+22)
        slot=page.locator(f'[data-widget-slot="{target}"]').bounding_box()
        ghost=page.locator('.dash-widget-drag-preview').bounding_box()
        page.mouse.move(slot['x']+(slot['width']-ghost['width'])/2+9.4,slot['y']+(slot['height']-ghost['height'])/2+11.28)
        tall_column=position('cancelled')[1]
        small_column=position('hold')[1]
        expect(page.locator(f'[data-column-preview="{tall_column}"]')).to_have_count(1)
        expect(page.locator(f'[data-column-preview="{small_column}"]')).to_have_count(3)
        tall_slot=page.locator(f'[data-column-preview="{tall_column}"]').bounding_box()
        assert abs(tall_slot['height']-page.locator('#dash-widget-grid').bounding_box()['height'])<1
        if cancel:page.keyboard.press('Escape')
        page.mouse.up()
    move('cancelled','collect',True)
    for key in original:assert position(key)==original[key]
    move('cancelled','collect')
    for key in ['hold','collect','out-of-stock']:assert position(key)==[original[key][0],'2']
    assert position('cancelled')==['1 / span 3','1']
    assert position('charge-pending')==original['charge-pending']
    move('collect','cancelled')
    for key in original:assert position(key)==original[key]
    page.reload()
    for key in original:assert position(key)==original[key]
    browser.close()
    print('PASS: grey outlines match tall/small column layouts, whole-column swaps in both directions preserve row order and third column, cancel cleanly and persist')
