from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['cancelled']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'cancelled':'1x3','cancelled-slot':0,'cancelled-column':0,'cancelled-period':'month'}))")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => {const date=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());const rows=[{id:'fit',order:'12345678901234567890',carrier:'Cancelled',st:'Cancelled',orderDate:date,orderDateTime:date+'T10:15:15+01:00',cust:'Very long customer name and company',orderRef:'LONGREFERENCEWITHOUTBREAKS012345678901234567890123456789',reason:'A long recorded cancellation reason for the delivery',logs:[]}];DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}""")
    for width in [800,1024,1440,1920]:
        page.set_viewport_size({'width':width,'height':900})
        metrics=page.locator('.dash-table-scroll').evaluate('''el=>{const r=el.getBoundingClientRect(),t=el.querySelector('table').getBoundingClientRect();return {viewport:el.clientWidth,scroll:el.scrollWidth,table:t.width,inside:[...el.querySelectorAll('th,td')].every(cell=>{const c=cell.getBoundingClientRect();return c.left>=r.left-1&&c.right<=r.right+1})}}''')
        assert metrics['inside'] and metrics['scroll']<=metrics['viewport']+1 and metrics['table']<=metrics['viewport']+1,(width,metrics)
        expect(page.locator('thead th')).to_have_count(3)
    browser.close()
    print('PASS: all three columns and long content fit within tall widget at 800, 1024, 1440 and 1920 widths; no horizontal overflow')
