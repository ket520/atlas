from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => {const rows=Array.from({length:13},(_,i)=>({id:'drag-'+i,order:'65000'+i,carrier:'On Hold',st:'Unassigned',orderDate:'2026-10-24',logs:[]}));DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}""")
    def metrics(selector):
        return page.locator(selector).evaluate('''el=>{const root=el.getBoundingClientRect(),body=el.querySelector('.dash-widget-body').getBoundingClientRect(),total=el.querySelector('.dash-widget-total').getBoundingClientRect(),preview=el.querySelector('.dash-widget-preview'),p=preview.getBoundingClientRect();return {ratio:p.width/body.width,totalX:(total.left-root.left)/root.width,totalY:(total.top-root.top)/root.height,clipped:getComputedStyle(preview).overflow==='hidden',inside:p.right<=root.right+1&&p.bottom<=root.bottom+1,rows:p.height/el.querySelector('.dash-preview-row').getBoundingClientRect().height}}''')
    source=metrics('[data-dash-widget="hold"]')
    rect=page.locator('[data-dash-widget="hold"]').bounding_box()
    page.mouse.move(rect['x']+10,rect['y']+12)
    page.mouse.down()
    page.mouse.move(rect['x']+25,rect['y']+25)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    ghost=metrics('.dash-widget-drag-preview')
    assert ghost['clipped'] and ghost['inside'] and abs(ghost['rows']-4)<.1,ghost
    for key in ['ratio','totalX','totalY']:assert abs(ghost[key]-source[key])<.01,(key,source,ghost)
    page.keyboard.press('Escape');page.mouse.up()
    page.locator('[data-dash-customize]').click()
    page.wait_for_timeout(310)
    page.locator('[data-picker-remove="hold"]').click()
    tile=page.locator('[data-picker-key="hold"][data-picker-size="1x1"]')
    rect=tile.bounding_box()
    page.mouse.move(rect['x']+rect['width']/2,rect['y']+rect['height']/2)
    page.mouse.down()
    page.mouse.move(rect['x']+rect['width']/2+10,rect['y']+rect['height']/2+10)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    ghost=metrics('.dash-widget-drag-preview')
    assert ghost['clipped'] and ghost['inside'] and abs(ghost['rows']-4)<.1 and .45<ghost['ratio']<.55,ghost
    page.keyboard.press('Escape');page.mouse.up()
    browser.close()
    print('PASS: populated reorder and gallery previews retain half-width clipped four-row list and original total alignment')

