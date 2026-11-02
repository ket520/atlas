from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');if(!localStorage.getItem('deliverydesk-dashboard-widgets-v1')){localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['cancelled','hold','collect','out-of-stock','charge-pending']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'cancelled':'1x3','cancelled-slot':0,'cancelled-column':0,'hold-slot':1,'collect-slot':4,'out-of-stock-slot':7,'charge-pending-slot':2}));}""")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    def position(key):return page.locator(f'[data-dash-widget="{key}"]').evaluate('(el)=>[el.style.gridRow,el.style.gridColumn]')
    page.locator('[data-dash-customize]').click()
    page.locator('[data-picker-remove="cancelled"]').click()
    def move(key,row,cancel=False):
        rect=page.locator(f'[data-dash-widget="{key}"]').bounding_box()
        page.mouse.move(rect['x']+10,rect['y']+12);page.mouse.down();page.mouse.move(rect['x']+20,rect['y']+22)
        slot=page.locator(f'[data-widget-slot="empty-{row}-1"]')
        target=slot.bounding_box();ghost=page.locator('.dash-widget-drag-preview').bounding_box()
        page.mouse.move(target['x']+(target['width']-ghost['width'])/2+9.4,target['y']+(target['height']-ghost['height'])/2+11.28)
        expect(slot).to_have_class('dash-widget-slot is-widget-drop-ready')
        expect(slot).to_have_css('border-top-color', 'rgb(98, 103, 233)')
        if cancel:page.keyboard.press('Escape')
        page.mouse.up()
    move('hold',1,True)
    assert position('hold')==['1','2']
    for key,row in [('hold',1),('collect',2),('out-of-stock',3)]:
        others={item:position(item) for item in ['hold','collect','out-of-stock','charge-pending'] if item!=key}
        move(key,row)
        assert position(key)==[str(row),'1']
        for item in others:assert position(item)==others[item]
    page.reload()
    for key,row in [('hold',1),('collect',2),('out-of-stock',3)]:assert position(key)==[str(row),'1']
    assert not errors,errors
    browser.close()
    print('PASS: remove tall widget, move each existing small widget into exact empty cells, leave neighbors fixed, cancel and reload persistence')
