"""Palletways summaries show sheet booking facts except for Next Day orders."""
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
    for method, booked, request, expected in [
        ('Palletways', 'Yes', 'Yes', '05/11/2026\n14:30'),
        ('Palletways BQ', 'No', 'No', 'Not Yet'),
        ('Palletways Next Day', 'No', 'Yes', None),
    ]:
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R === 'function'")
        page.evaluate("""facts => {
          const record = {id:'663346',order:'663346',carrier:'Palletways',st:'Scheduled',rawStatus:'P',logs:[],
            deliveryMethodRaw:facts.method,palletwaysSheetBookedIn:facts.booked,
            palletwaysSheetBookInRequest:facts.request,palletwaysSheetBookInDate:'05/11/2026',palletwaysSheetBookInTime:'14:30'};
          DeliveryStore.hydrate({deliveries:[record],activity:[],integrations:[]});D=DeliveryStore.deliveries();R();op(record.id);
        }""", {'method': method, 'booked': booked, 'request': request})
        panel = page.locator('.qd-tracking-view')
        panel.get_by_role('button', name='Details', exact=True).click()
        summary = panel.locator('.qd-summary')
        expect(summary.locator('[data-summary-field="original-delivery-method"]')).to_have_count(0)
        booked_field = summary.locator('[data-summary-field="booked-in"] b')
        request_field = summary.locator('[data-summary-field="book-in-request"] b')
        if expected is None:
            expect(booked_field).to_have_count(0)
            expect(request_field).to_have_count(0)
        else:
            expect(booked_field).to_have_text(expected)
            expect(request_field).to_have_text(request)
            assert booked_field.evaluate('el => getComputedStyle(el).whiteSpace') == 'pre-line'
            expected_colour = 'rgb(35, 122, 73)' if booked == 'Yes' else 'rgb(184, 50, 74)'
            assert booked_field.evaluate('el => getComputedStyle(el.closest(".qd-summary-item")).backgroundColor') == expected_colour
            assert summary.evaluate("""el => {
              const fields = [...el.querySelectorAll('[data-summary-field]')].map(node => node.dataset.summaryField);
              return fields.indexOf('orderwise-status') < fields.indexOf('book-in-request') && fields.indexOf('book-in-request') < fields.indexOf('booked-in');
            }""")
    assert not errors, errors
    browser.close()
    print('PASS: sidebar sheet date/time, Not Yet, request Yes/No and Next Day exclusion')
