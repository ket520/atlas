"""Real automatic desktop zoom: fit, dragging, details, resize, and mobile opt-out."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1920,'height':1080},reduced_motion='reduce')
    page.set_default_timeout(5000)
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    def html(route):
        name=route.request.url.split('/pages/')[1].split('?')[0]
        route.fulfill(body=(ROOT/'pages'/name).read_bytes().replace(b'data-live="true"',b'data-live="false"'),content_type='text/html')
    page.route('**/pages/*.html',html)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.wait_for_selector('.dash-widget')
    for width,height in [(1920,1080),(1440,810),(1366,768),(1280,720),(1280,600),(1024,600),(1920,750),(800,600)]:
        page.set_viewport_size({'width':width,'height':height})
        scale=min(1,width/1920,height/1080)
        page.wait_for_function('(scale)=>Math.abs(AtlasViewport.scale-scale)<.00001',arg=scale)
        for collapsed in (False,True):
            page.evaluate('(value)=>setSidebarCollapsed(value)',collapsed)
            sidebar=page.locator('.sd')
            assert sidebar.evaluate('el=>el.scrollHeight<=el.clientHeight+1'),(width,height,collapsed)
            assert sidebar.locator('a').evaluate_all('items=>items.every(el=>{const r=el.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight})'),(width,height,collapsed)
            assert page.locator('.dash-widget').evaluate_all('items=>items.every(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.top>=0&&r.right<=innerWidth+1&&r.bottom<=innerHeight+1})'),(width,height)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1&&document.documentElement.scrollHeight<=innerHeight+1')
    # Pointer coordinates and fixed drag previews stay aligned at 75%.
    page.set_viewport_size({'width':1440,'height':810})
    page.wait_for_function('AtlasViewport.scale===.75')
    page.evaluate('setSidebarCollapsed(false)')
    card=page.locator('[data-dash-widget="hold"]')
    box=card.bounding_box()
    page.mouse.move(box['x']+8,box['y']+8);page.mouse.down()
    page.mouse.move(box['x']+32,box['y']+27)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    ghost=page.locator('.dash-widget-drag-preview').bounding_box()
    assert abs(ghost['x']-(box['x']+24))<10,(box,ghost)
    page.keyboard.press('Escape');page.mouse.up()
    target=page.locator('[data-dash-widget="charge-pending"]').bounding_box()
    page.mouse.move(box['x']+8,box['y']+8);page.mouse.down()
    page.mouse.move(target['x']+8,target['y']+8)
    expect(page.locator('.dash-widget-slot.is-widget-drop-ready')).to_have_count(1)
    page.mouse.up()
    assert card.evaluate('el=>el.style.gridColumn')=='2'
    page.locator('[data-dash-customize]').click()
    tile=page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')
    source=tile.bounding_box();grid=page.locator('#dash-widget-grid').bounding_box()
    page.mouse.move(source['x']+source['width']/2,source['y']+source['height']/2)
    page.mouse.down();page.mouse.move(source['x']+source['width']/2+10,source['y']+source['height']/2+10)
    page.mouse.move(grid['x']+grid['width']/6,grid['y']+grid['height']/2)
    expect(page.locator('.dash-picker-slots .is-widget-drop-ready')).to_have_count(1)
    page.mouse.up()
    expect(page.locator('.dash-widget-tall')).to_have_count(1)
    page.locator('[data-dash-customize]').click()
    page.screenshot(path=str(ROOT/'.test-temp/atlas-auto-scale.png'))
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R==='function'")
    page.evaluate("DeliveryStore.hydrate({deliveries:[{id:'zoom-test',order:'650001',cust:'Zoom test customer',carrier:'Own van',st:'Scheduled',logs:[]}],activity:[],integrations:[]});D=DeliveryStore.deliveries();R();op('zoom-test')")
    panel=page.locator('.dr.qd.qd-tracking-view')
    expect(panel).to_be_visible()
    box=panel.bounding_box()
    assert box['x']+box['width']<=1441
    assert box['y']>=0 and box['y']+box['height']<=811
    panel.locator('[data-detail-action="close"]').click()
    expect(panel).to_have_count(0)
    page.set_viewport_size({'width':390,'height':844})
    page.wait_for_function('AtlasViewport.scale===1')
    assert page.evaluate('!document.documentElement.classList.contains("atlas-scaled")')
    assert not errors,errors
    browser.close()
    print('PASS: automatic zoom at eight laptop sizes, no sidebar scrolling, scaled widget dragging/gallery, details and mobile opt-out')
