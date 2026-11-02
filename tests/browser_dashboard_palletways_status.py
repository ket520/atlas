from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['palletways-next-day','palletways-unbooked']));localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({'palletways-next-day':'1x3','palletways-next-day-slot':0,'palletways-unbooked':'1x3','palletways-unbooked-slot':1}))")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => {const rows=['COLLECTED',''].map((status,i)=>({id:'p'+i,order:'6500'+i,carrier:'Palletways',st:'Scheduled',deliveryMethodRaw:'Palletways Next Day',salesActivityPresent:true,palletwaysSheetBookedIn:'No',palletwaysDetails:{classification:'B2C'},palletwaysSheetStatus:status,logs:[]}));DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}""")
    for key in ['palletways-next-day','palletways-unbooked']:
        card=page.locator(f'[data-dash-widget="{key}"]')
        expect(card.locator('th').nth(2)).to_have_text('Status')
        expect(card.locator('tbody tr').first.locator('td').nth(2)).to_have_text('COLLECTED')
        expect(card.locator('tbody tr').nth(1).locator('td').nth(2)).to_have_text('-')
    browser.close()
    print('PASS: Palletways Next Day and Unbooked tables show Palletways sheet status, never OW status; Next Day heading restored to Status')
