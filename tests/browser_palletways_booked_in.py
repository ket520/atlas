"""Booked In presents BT/BU on two lines while filters retain Z's Yes/No facts."""
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
        {deliveryMethodRaw: 'Palletways Next Day', palletwaysSheetBookedIn: 'No'},
        {deliveryMethodRaw: 'Palletways', palletwaysSheetBookedIn: 'No'},
        {deliveryMethodRaw: 'Palletways BQ', palletwaysSheetBookedIn: ' no '},
        {deliveryMethodRaw: 'Palletways Next Day', palletwaysSheetBookedIn: ' YES ', palletwaysSheetBookInDate: '05/11/2026', palletwaysSheetBookInTime: '14:30'},
        {deliveryMethodRaw: 'Palletways', palletwaysSheetBookedIn: 'Yes'},
        {deliveryMethodRaw: 'Palletways', palletwaysSheetBookedIn: ''},
      ];
      DeliveryStore.hydrate({deliveries: facts.map((row, i) => ({id: 'booking-' + i, order: '65000' + i, carrier: 'Palletways', st: 'Scheduled', logs: [], ...row})), activity: [], integrations: []});
      D = DeliveryStore.deliveries(); fsrc = 'Palletways'; R();
    }""")
    cells = page.locator('.tracking-booked-in-cell')
    expect(cells).to_have_count(6)
    expect(cells.nth(0)).to_have_text('N/A')
    expect(cells.nth(1)).to_have_text('Not Yet')
    expect(cells.nth(2)).to_have_text('Not Yet')
    expect(cells.nth(3)).to_contain_text('05/11/2026')
    expect(cells.nth(3)).to_contain_text('14:30')
    assert cells.nth(3).evaluate("el => el.children[1].getBoundingClientRect().top >= el.children[0].getBoundingClientRect().bottom")
    expect(cells.nth(4)).to_have_text('\u2014')
    expect(cells.nth(5)).to_have_text('\u2014')
    page.evaluate("fbookedIn = 'yes'; rows()")
    expect(cells).to_have_count(2)
    page.evaluate("fbookedIn = 'no'; rows()")
    expect(cells).to_have_count(1)
    expect(cells.nth(0)).to_have_text('N/A')
    page.evaluate("fbookedIn = 'not-yet'; rows()")
    expect(cells).to_have_count(2)
    expect(cells.nth(0)).to_have_text('Not Yet')
    page.locator('[data-booking-field="booked_in"][data-delivery-filter-action="toggle-booking"]').click()
    expect(page.locator('#tracking-booked_in-menu [data-value="yes"]')).to_have_text('Yes')
    expect(page.locator('#tracking-booked_in-menu [data-value="no"]')).to_have_text('N/A')
    expect(page.locator('#tracking-booked_in-menu [data-value="not-yet"]')).to_have_text('Not Yet')
    assert not errors, errors
    browser.close()
    print('PASS: Next Day No, other services Not Yet, sheet date/time on two lines, blank fallback and unchanged booking filters')
