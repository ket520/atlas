from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='no-preference')
    page.clock.install()
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['hold']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'hold':'1x3','hold-slot':0}))")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => {const rows=Array.from({length:30},(_,i)=>({id:'h'+i,order:'6500'+i,carrier:'On Hold',st:'Unassigned',cust:'Customer '+i,orderDate:'2026-10-24',logs:[]}));DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}""")
    table=page.locator('.dash-table-scroll')
    page.mouse.move(0,0)
    page.clock.run_for(1000)
    first=table.evaluate('el=>el.scrollTop')
    assert 5<=first<=10,first
    rect=table.bounding_box()
    page.mouse.move(rect['x']+rect['width']/2,rect['y']+50)
    page.clock.run_for(50)
    paused=table.evaluate('el=>el.scrollTop')
    page.clock.run_for(1000)
    assert table.evaluate('el=>el.scrollTop')==paused
    page.mouse.move(0,0)
    page.clock.run_for(1000)
    assert table.evaluate('el=>el.scrollTop')>first+5
    assert page.locator('[data-dash-order]').evaluate_all("items=>items.every(el=>el.querySelector('.dash-order-view-icon'))")
    table.evaluate('el=>el.scrollTop=el.scrollHeight-el.clientHeight')
    page.clock.run_for(1000)
    assert table.evaluate('el=>el.scrollTop')>0
    page.clock.run_for(1200)
    assert table.evaluate('el=>el.scrollTop')<3
    page.clock.run_for(1000)
    assert table.evaluate('el=>el.scrollTop')>5
    assert page.locator('.dash-filter-chips button').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='13px'
    assert page.locator('.dash-store-name').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='11px'
    assert page.evaluate('document.documentElement.scrollHeight<=innerHeight')
    browser.close()
    print('PASS: slow table auto-scroll, exact hover pause, resume on leave, smaller filter/store text and no page scroll')
