from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      const facts = [
        {method:'Palletways Next Day',booked:false},
        {method:'Palletways',booked:false},
        {method:'Palletways BQ',booked:false},
        {method:'Palletways Next Day',booked:true},
        {method:'Palletways',booked:true,date:'05/11/2026'},
        {method:'Palletways',booked:null},
      ];
      DeliveryStore.hydrate({deliveries:facts.map((fact,i)=>({
        id:'booking-'+i,order:'65000'+i,carrier:'Palletways',st:'Scheduled',logs:[],
        deliveryMethodRaw:fact.method,palletwaysShipments:[{
          tracking_id:'6000000000'+i,consignment_number:'CON-'+i,
          booking_summary:{booked_in:fact.booked,book_in_request:null,booking_date:fact.date||null}
        }]
      })),activity:[],integrations:[]});
      D=DeliveryStore.deliveries();fsrc='Palletways';R();
    }""")
    cells = page.locator('.tracking-booked-in-cell')
    expect(cells).to_have_count(6)
    expect(cells.nth(0)).to_have_text('Not Applicable')
    expect(cells.nth(1)).to_have_text('Not Yet')
    expect(cells.nth(2)).to_have_text('Not Yet')
    expect(cells.nth(3)).to_have_text('—')
    expect(cells.nth(4)).to_have_text('05/11/2026')
    expect(cells.nth(5)).to_have_text('—')
    for value, count in [('yes', 1), ('not-applicable', 1), ('not-yet', 2), ('unknown', 1)]:
        page.evaluate('(value) => {fbookedIn=value;rows()}', value)
        expect(cells).to_have_count(count)
    page.locator('[data-booking-field="booked_in"][data-delivery-filter-action="toggle-booking"]').click()
    for value in ('yes', 'not-yet', 'not-applicable', 'unknown'):
        expect(page.locator(f'#tracking-booked_in-menu [data-value="{value}"]')).to_have_count(1)
    assert not errors, errors
    browser.close()
    print('PASS: API Booked In values and filters')
