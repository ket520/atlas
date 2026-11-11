"""Credit statuses and filter counts ignore inherited delivery/provider states."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/refund.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries: [
        {id:'200',order:'200',rawStatus:'Completed',st:'Cancelled'},
        {id:'201',order:'201',rawStatus:'W',st:'Delivered'},
        {id:'202',order:'202',rawStatus:'X',st:'Delivered'},
      ].map(record => ({...record,carrier:'Own van',statusSource:'OptimoRoute',orderRelationKind:'Credit/Refund',logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    expect(page.locator('[data-delivery-id="200"] .tracking-status-cell')).to_have_text('Refund completeOW')
    expect(page.locator('[data-delivery-id="201"] .tracking-status-cell')).to_have_text('Not YetOW')
    expect(page.locator('[data-delivery-id="202"] .tracking-status-cell')).to_have_text('CancelledOW')
    select = page.locator('[data-ui-select-id="dstatusValue"]')
    for value, label, order in [('refund:complete', 'Refund complete (1)', '200'), ('refund:not-yet', 'Not Yet (1)', '201'), ('refund:cancelled', 'Cancelled (1)', '202')]:
        if not select.locator('.ui-select-menu').is_visible():
            select.locator('[data-ui-select-trigger]').click()
        select.locator('[data-ui-select-option][data-value=""]').click()
        option = select.locator(f'[data-value="{value}"]')
        expect(option).to_have_text(label)
        option.click()
        expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(1)
        expect(page.locator('#tb tr[data-delivery-id]')).to_have_attribute('data-delivery-id', order)
    browser.close()
    print('PASS: refund-only status labels, OW source, matching filter counts and correct cancelled/complete rows')
