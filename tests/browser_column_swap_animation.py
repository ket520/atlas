"""Column swaps animate only the selected column and preserve table nodes."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='no-preference')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries: Array.from({length: 20}, (_, i) => ({
        id: 'swap-' + i, order: '65000' + i, carrier: 'Palletways', st: 'Scheduled', logs: [],
        palletwaysSheetTrackingNumber: '60000000001', palletwaysSheetConsignmentNumber: 'C-123',
        date: '2026-11-05', dispatchDate: '2026-11-04', orderDate: '2026-11-01', skuItems: 'SKU-ONE'
      })), activity: [], integrations: []});
      D = DeliveryStore.deliveries(); fsrc = 'Palletways'; R();
    }""")
    for selector, label in [
        ('[data-palletways-number-type]', 'Show Consignment No'),
        ('[data-tracking-date-type]', 'Show Scheduled date'),
        ('[data-delivery-item-column]', 'Show SKU of items'),
    ]:
        page.evaluate("""() => {
          window.previousRow = document.querySelector('#tb tr[data-delivery-id]');
          window.previousOrder = previousRow.children[0];
          document.querySelector('#tb').scrollTop = 100;
          window.previousScroll = document.querySelector('#tb').scrollTop;
        }""")
        page.locator(selector).click()
        assert page.evaluate("document.getAnimations().some(a => a.effect.target.closest('th, td'))")
        assert page.evaluate("document.getAnimations().filter(a => a.effect.target.closest('th, td')).every(a => a.effect.target.matches('.delivery-column-swap-word'))")
        expect(page.locator(selector)).to_have_attribute('aria-label', label)
        page.wait_for_function('!deliveryColumnSwapBusy')
        assert page.evaluate("document.querySelector('#tb tr[data-delivery-id]') === previousRow")
        assert page.evaluate("previousRow.children[0] === previousOrder")
        assert page.evaluate("document.querySelector('#tb').scrollTop === previousScroll")
        assert page.evaluate("document.activeElement.matches(" + repr(selector) + ")")
    assert not errors, errors
    browser.close()
    print('PASS: all three column swaps animate, preserve rows, order cells, scroll and focus')
