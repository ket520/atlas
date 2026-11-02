"""Tracking categories share the toolbar dropdown controls and filter saved rows."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate('''() => {
      const carriers = ['Palletways', 'LOCAL MULTIDROP', 'SUPPLIER', 'UK Next Day', 'Collect in Person', 'Cancelled'];
      DeliveryStore.hydrate({deliveries: carriers.flatMap((carrier, i) => [
        {id: String(i * 2 + 1), order: String(i * 2 + 1), carrier, st: 'Scheduled', storeCode: 'AMAZON', logs: []},
        {id: String(i * 2 + 2), order: String(i * 2 + 2), carrier, st: 'Delivered', storeCode: 'B&Q', logs: []}
      ]), activity: [], integrations: []});
      D = DeliveryStore.deliveries(); R();
    }''')
    scope = page.locator('[data-ui-select-id="dscopeValue"]')
    assert page.locator('.tracking-general-section').count() == 0
    assert scope.evaluate("el => el.previousElementSibling.dataset.uiSelectId") == 'dstoreValue'
    scope.locator('[data-ui-select-trigger]').click()
    for value in ['LOCAL MULTIDROP', 'UK Next Day', 'Collect in Person']:
        assert scope.locator(f'[data-value="{value}"]').count() == 0
    scope.locator('[data-value="SUPPLIER"]').click()
    expect(page.locator('.tracking-row')).to_have_count(2)
    scope.locator('[data-value="Cancelled"]').click()
    expect(page.locator('.tracking-row')).to_have_count(4)
    assert page.evaluate('trackingScope') == ['SUPPLIER', 'Cancelled']
    scope.locator('[data-value="Cancelled"]').click()
    expect(page.locator('.tracking-row')).to_have_count(2)
    scope.locator('[data-ui-select-trigger]').click()
    store = page.locator('[data-ui-select-id="dstoreValue"]')
    store.locator('[data-ui-select-trigger]').click()
    store.locator('[data-value="Amazon"]').click()
    expect(page.locator('.tracking-row')).to_have_count(1)
    page.locator('[data-delivery-filter-action="clear-all"]').click()
    expect(page.locator('.tracking-row')).to_have_count(12)
    expect(scope.locator('.ui-select-label')).to_have_text('All categories')
    for width in [1920, 1440, 1280, 1024]:
        page.set_viewport_size({'width': width, 'height': 900})
        bounds = page.locator('.delivery-filters').evaluate('''el => {
          const box = el.getBoundingClientRect();
          return [...el.children].every(child => child.getBoundingClientRect().right <= box.right + 1);
        }''')
        assert bounds, width
    browser.close()
    print('PASS: category dropdown position, special methods, combined store filter, reset and toolbar fit')
