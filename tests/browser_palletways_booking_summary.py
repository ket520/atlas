from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/**', lambda route: route.fulfill(json={'available': False}))
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")

    cases = [
        ('Palletways', True, False, '05/11/2026 · 14:30', 'No'),
        ('Palletways BQ', False, True, 'Not Yet', 'Yes'),
        ('Palletways', None, None, '—', '—'),
        ('Palletways Next Day', False, True, 'Not Applicable', '—'),
        ('Palletways Next Day', True, False, '—', '—'),
    ]
    for method, booked, requested, expected_booked, expected_request in cases:
        page.evaluate("""facts => {
          const record = {id:'663346',order:'663346',carrier:'Palletways',st:'Scheduled',rawStatus:'P',logs:[],
            deliveryMethodRaw:facts.method,palletwaysShipments:[{
              tracking_id:'60000000001',consignment_number:'CON-1',booking_summary:{
                booked_in:facts.booked,book_in_request:facts.requested,
                booking_date:'05/11/2026',booking_time:'14:30'
              }
            }]};
          DeliveryStore.hydrate({deliveries:[record],activity:[],integrations:[]});
          D=DeliveryStore.deliveries();fsrc='Palletways';R();op(record.id);
        }""", {'method': method, 'booked': booked, 'requested': requested})
        assert page.evaluate("""() => {
          const record=get('663346');
          return [palletwaysBookingRows(record,'booked_in')[0].text,
            palletwaysBookingRows(record,'book_in_request')[0].text];
        }""") == [expected_booked, expected_request]
        panel = page.locator('.qd-tracking-view')
        panel.get_by_role('button', name='Details', exact=True).click()
        summary = panel.locator('.qd-summary')
        if method == 'Palletways Next Day':
            expect(summary.locator('[data-summary-field="booked-in"]')).to_have_count(0)
        else:
            expect(summary.locator('[data-summary-field="booked-in"] b')).to_have_text(expected_booked)
            expect(summary.locator('[data-summary-field="book-in-request"] b')).to_have_text(expected_request)

    page.evaluate("""() => {
      const record=get('663346');
      record.deliveryMethodRaw='Palletways';
      record.palletwaysShipments[0].booking_summary.booking_date=null;
      R();
    }""")
    assert page.evaluate("""() => palletwaysBookingRows(get('663346'),'booked_in')[0].text""") == 'Booked · Date unavailable'

    page.evaluate("""() => {
      const record=get('663346');
      record.palletwaysShipments=[
        {tracking_id:'60000000001',consignment_number:'CON-1',booking_summary:{booked_in:true,book_in_request:false,booking_date:'05/11/2026'}},
        {tracking_id:'60000000002',consignment_number:'CON-2',booking_summary:{booked_in:false,book_in_request:true}}
      ];
      R();
    }""")
    assert page.evaluate("""() => {
      const record=get('663346');
      return palletwaysBookingMatchesFilters(record,'yes','') &&
        palletwaysBookingMatchesFilters(record,'not-yet','') &&
        palletwaysBookingCell(record,'booked_in').includes('CON-2');
    }""")
    assert not errors, errors
    browser.close()
    print('PASS: API booking summary, Next Day rules, unknown values and multiple consignments')
