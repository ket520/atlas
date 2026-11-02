from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.clock.install(time=__import__('datetime').datetime(2026,10,24,12,tzinfo=__import__('datetime').timezone.utc))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['cancelled','cancelled--1x3']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'cancelled-slot':0,'cancelled--1x3-slot':1,'cancelled--1x3':'1x3'}))")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => {const rows=['2026-10-24','2026-10-01','2026-09-30'].map((date,i)=>({id:'c'+i,order:'65000'+i,carrier:'Cancelled',st:'Cancelled',orderDate:date,orderDateTime:date+'T10:15:15+01:00',deliveryMethodRaw:'Own Van Delivery',cust:'Customer '+i,orderRef:'REF-'+i,reason:i===0?'Access restricted':'',carrierIssueReason:i===1?'Customer requested cancellation':'',logs:[]}));DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}""")
    small=page.locator('[data-dash-widget="cancelled"]')
    tall=page.locator('[data-dash-widget="cancelled--1x3"]')
    expect(small.locator('.dash-widget-total')).to_have_text('1')
    small.locator('[data-cancelled-period="month"]').click()
    expect(small.locator('.dash-widget-total')).to_have_text('2')
    expect(small.locator('[data-dash-view]')).to_have_attribute('data-dash-view','cancelled-month')
    expect(tall.locator('[data-cancelled-period="daily"]')).to_have_attribute('aria-pressed','true')
    expect(tall.locator('tbody tr')).to_have_count(1)
    expect(tall.locator('thead th')).to_have_count(3)
    expect(tall.locator('.dash-order-customer')).to_have_text('Customer 0')
    expect(tall.locator('tbody [data-dash-order]')).to_have_text('650000')
    expect(tall.locator('tbody tr').first.locator('td').nth(1)).to_have_text('REF-0')
    expect(tall.locator('.dash-order-time')).to_have_text('10:15')
    expect(tall.locator('.dash-order-date')).to_have_count(0)
    tall.locator('[data-cancelled-period="month"]').click()
    expect(tall.locator('tbody tr')).to_have_count(2)
    expect(tall.locator('.dash-order-date').first).to_have_text('24 Oct 2026')
    expect(tall.locator('tbody tr').nth(1).locator('td').nth(1)).to_have_text('REF-1')
    small.locator('[data-cancelled-period="daily"]').click()
    expect(small.locator('.dash-widget-total')).to_have_text('1')
    expect(tall.locator('[data-cancelled-period="month"]')).to_have_attribute('aria-pressed','true')
    assert page.evaluate("JSON.parse(localStorage.getItem('deliverydesk-dashboard-widgets-v1-sizes'))['cancelled--1x3-period']==='month'")
    page.evaluate("""() => {
      window.monthRequests=[];
      ApiClient.get=async path=>{
        monthRequests.push(path);
        if(!path.includes('general_scope=Cancelled')) throw Error('Unsupported endpoint');
        const offset=Number(new URLSearchParams(path.split('?')[1]).get('offset'));
        return {total:101,deliveries:Array.from({length:offset===0?100:1},(_,i)=>({id:'live-'+(i+offset),order:'live-'+(i+offset),orderDate:offset===0?'2026-10-01':'2026-09-30',orderDateTime:offset===0?'2026-10-01T10:15:15+01:00':'2026-09-30T11:00:00+01:00'}))};
      };
      document.body.dataset.live='true';
    }""")
    tall.locator('[data-cancelled-period="daily"]').click()
    tall.locator('[data-cancelled-period="month"]').click()
    expect(tall.locator('tbody tr')).to_have_count(30)
    small.locator('[data-cancelled-period="month"]').click()
    expect(small.locator('.dash-widget-total')).to_have_text('100')
    assert page.evaluate("monthRequests.length===2 && monthRequests[1].includes('offset=100')")
    browser.close()
    print('PASS: Daily/Month counts, preview/table rows, matching View action, independent widget sizes and saved period')
