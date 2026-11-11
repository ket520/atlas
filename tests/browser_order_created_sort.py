"""Created-date sorting works across courier tables, failures and dashboard tables."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      localStorage.setItem('atlas-delivery-item-column','order-date');
      localStorage.setItem('delivery-desk-hide-wayfair-tracking','false');
      localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['hold','cancelled']));
      localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'hold':'1x3','hold-slot':0,'cancelled':'1x3','cancelled-slot':1}));""")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    for filename in ['deliveries', 'failed-deliveries']:
        page.goto(f'https://deliverydesk.test/pages/{filename}.html')
        page.wait_for_function("typeof R === 'function'")
        page.evaluate("""() => {
          const rows=['Palletways','AMZ','XDP','Stopstart','Yodel','Wayfair','Own van'].flatMap((carrier,c)=>
            ['2026-11-02','2026-11-01',''].map((date,i)=>({id:String(c*10+i+1),order:String(c*10+i+1),
              carrier,st:'Failed',orderDate:date,orderDateTime:date?date+'T12:00:00':'',logs:[]})));
          DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
        }""")
        if filename == 'deliveries':
            for carrier in ['Palletways', 'AMZ', 'XDP', 'Stopstart', 'Yodel', 'Wayfair', 'Own van / Self Delivery']:
                page.evaluate("carrier=>{fsrc=carrier;trackingDateSort='';R();}", carrier)
                button = page.get_by_role('button', name='Sort order date created', exact=True)
                button.click()
                dates = page.locator('#tb .delivery-item-cell').all_text_contents()
                assert dates[0] == '2 Nov 2026' and dates[1] == '1 Nov 2026', dates
                button.click()
                dates = page.locator('#tb .delivery-item-cell').all_text_contents()
                assert dates[0] == '1 Nov 2026' and dates[1] == '2 Nov 2026', dates
        else:
            button = page.get_by_role('button', name='Sort order date created', exact=True)
            button.click()
            assert page.locator('#failed-list .delivery-item-cell').first.inner_text() == '2 Nov 2026'
            button.click()
            assert page.locator('#failed-list .delivery-item-cell').first.inner_text() == '1 Nov 2026'
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      const day=new Intl.DateTimeFormat('en-CA',{timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
      const rows=['On Hold','Cancelled'].flatMap((carrier,c)=>['08:00:00','16:00:00'].map((time,i)=>({
        id:String(c*10+i+1),order:String(c*10+i+1),carrier,st:c?'Cancelled':'Unassigned',orderDate:day,deliveryMethodRaw:carrier==='Cancelled'?'TO BE CANCELLED':'On hold - TBC',cancelledFromDeliveryMethod:carrier==='Cancelled'?'Standard Van Delivery':'',
        orderDateTime:day+'T'+time,logs:[]})));
      DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
    }""")
    for key, newest, oldest in [('hold', '2', '1'), ('cancelled', '12', '11')]:
        card = page.locator(f'[data-dash-widget="{key}"]')
        card.locator('[data-dash-sort-created]').click()
        expect(card.locator('tbody [data-dash-order]').first).to_contain_text(newest)
        card.locator('[data-dash-sort-created]').click()
        expect(card.locator('tbody [data-dash-order]').first).to_contain_text(oldest)
    assert not errors, errors
    browser.close()
    print('PASS: created dates sort in both directions across all courier tables, failures and dashboard widgets')
