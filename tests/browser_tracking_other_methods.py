"""Every method contributes once; secondary methods live in the Other dropdown."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      localStorage.setItem('delivery-desk-hide-hygienic-tracking','false');
      localStorage.setItem('delivery-desk-hide-wayfair-tracking','false');""")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      const carriers=['Own van','Self Delivery','Palletways','AMZ','XDP','Stopstart','Yodel','Wayfair',
        'Cancelled','On Hold','Do Not Pick Yet','Collect in Person','Charge Pending (Remote Postcode)',
        'LOCAL MULTIDROP','Standard Pallet Delivery','SUPPLIER','UK Next Day'];
      DeliveryStore.hydrate({deliveries:carriers.map((carrier,i)=>({id:String(i+1),order:String(i+1),
        carrier,st:'Scheduled',rawStatus:'P',deliveryMethodRaw:carrier,logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    expect(page.locator('[data-delivery-filter-action="method"]')).to_have_count(8)
    expect(page.locator('[data-delivery-filter-action="method"][data-value="Cancelled"]')).to_have_count(0)
    expect(page.locator('.tracking-method-totals')).to_have_text(
        'Main delivery methods (8) + Other Delivery Method (9) = All methods (17)')
    assert page.evaluate('Object.values(trackingLevelCounts().carriers).reduce((a,b)=>a+b,0)') == 17
    assert page.evaluate("""(() => {
      const other=document.querySelector('[data-ui-select-id="dotherMethodValue"]');
      return other.nextElementSibling.dataset.uiSelectId==='dstoreValue';
    })()""")
    other = page.locator('[data-ui-select-id="dotherMethodValue"]')
    other.locator('[data-ui-select-trigger]').click()
    expect(other.locator('[data-value="Cancelled"]')).to_have_text('Cancelled (1)')
    other.locator('[data-value="Cancelled"]').click()
    assert page.evaluate('fsrc') == 'Cancelled'
    expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(1)
    page.locator('[data-delivery-filter-action="method"][data-value="AMZ"]').click()
    assert page.evaluate('fsrc') == 'AMZ'
    expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(1)
    for carrier in ['Own van / Self Delivery', 'Palletways', 'AMZ', 'XDP', 'Stopstart', 'Yodel', 'Wayfair']:
        if page.evaluate('fsrc') != carrier:
            page.locator(f'[data-delivery-filter-action="method"][data-value="{carrier}"]').click()
        expect(page.locator('[data-ui-select-id="dotherMethodValue"]')).to_have_count(0)
    page.locator('[data-delivery-filter-action="method"][data-value=""]').click()
    expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(17)
    expect(page.locator('[data-ui-select-id="dotherMethodValue"]')).to_be_visible()
    category = page.locator('[data-ui-select-id="dscopeValue"]')
    expect(category.locator('[data-value="Cancelled"]')).to_have_count(0)
    expect(category.locator('[data-value="SUPPLIER"]')).to_have_count(0)
    browser.close()
    print('PASS: all methods reconcile, other dropdown filters correctly, categories do not duplicate methods')
