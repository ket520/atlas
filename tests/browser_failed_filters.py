"""Failed Deliveries separates courier cards from general status options."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('https://deliverydesk.test/pages/failed-deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      const records = ['AMZ','Palletways','On Hold','SUPPLIER'].map((carrier,i) => ({
        id:String(700000+i),order:String(700000+i),carrier,st:'Failed',storeCode:'AMAZON',
        cust:'Customer '+i,logs:[],reason:'Delivery failed'}));
      DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
    }""")
    expect(page.locator('.tracking-general-section')).to_have_count(0)
    expect(page.locator('[data-failed-method="On Hold"], [data-failed-method="SUPPLIER"]')).to_have_count(0)
    expect(page.locator('.tracking-courier-grid [data-failed-method]')).to_have_count(2)
    status = page.locator('[data-ui-select-id="failed-scope-value"]')
    status.locator('[data-ui-select-trigger]').click()
    status.locator('[data-value="On Hold"]').click()
    expect(page.locator('#failed-list .tracking-row')).to_have_count(1)
    assert page.evaluate('failedScope') == 'On Hold'
    if not status.locator('.ui-select-menu').is_visible():
        status.locator('[data-ui-select-trigger]').click()
    status.locator('[data-value="SUPPLIER"]').click()
    expect(page.locator('#failed-list .tracking-row')).to_have_count(2)
    assert page.evaluate('failedScope') == ['On Hold', 'SUPPLIER']
    if not status.locator('.ui-select-menu').is_visible():
        status.locator('[data-ui-select-trigger]').click()
    status.locator('[data-value=""]').click()
    expect(page.locator('#failed-list .tracking-row')).to_have_count(4)
    page.locator('[data-failed-method="AMZ"]').click()
    expect(page.locator('#failed-list .tracking-row')).to_have_count(1)
    assert page.evaluate('failedCarrier') == 'AMZ'
    for width in [1440, 1280, 1024, 390]:
        page.set_viewport_size({'width':width,'height':900})
        layouts = []
        for name in ['deliveries', 'failed-deliveries']:
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.wait_for_function("typeof R === 'function'")
            layouts.append(page.locator('.bar.delivery-filters').evaluate('''bar => {
              const rect=bar.getBoundingClientRect();
              return [...bar.children].filter(el=>el.matches('.delivery-search,.ui-select') && !el.classList.contains('delivery-other-method-select')).map(el=>{
                const r=el.getBoundingClientRect();const control=el.querySelector('.ui-select-trigger') || el;
                const style=getComputedStyle(control);
                return [Math.round(r.x-rect.x),Math.round(r.y-rect.y),Math.round(r.width),Math.round(r.height),
                  style.backgroundColor,style.borderRadius,style.fontSize];
              });
            }'''))
        # Tracking has an additional Other Delivery Method dropdown, so widths differ.
        # Shared controls retain the same height, colours, radius and font size.
        assert [item[3:] for item in layouts[0]] == [item[3:] for item in layouts[1]], (width, layouts)
        assert len(layouts[1]) == 4, layouts  # Empty category filters are omitted.
        assert len({item[1] for item in layouts[1]}) == 1, layouts
    for width in [1440, 1280, 390]:
        page.set_viewport_size({'width':width,'height':900})
        for name in ['deliveries', 'failed-deliveries']:
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.wait_for_function("typeof R === 'function'")
            page.evaluate("""() => {
              const records = ['Own van','AMZ','XDP'].map((carrier,i)=>({id:String(710000+i),
                order:String(710000+i),carrier,st:'Failed',storeCode:'AMAZON',cust:'Customer',logs:[]}));
              DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
            }""")
            tops=page.locator('.tracking-scope-section:not(.tracking-general-section) [role="tab"]').evaluate_all(
                'nodes=>nodes.map(node=>Math.round(node.getBoundingClientRect().top))')
            assert len(tops) == 4 and max(tops) - min(tops) <= 2, (width,name,tops)
    page.set_viewport_size({'width':1440,'height':900})
    page.goto('https://deliverydesk.test/pages/failed-deliveries.html')
    page.locator('[data-failed-toggle-date]').click()
    page.locator('#failed-date-from').fill('2026-11-01')
    page.locator('#failed-scheduled-from').fill('2026-11-02')
    assert page.evaluate('[failedDateFrom,failedScheduledFrom]') == ['2026-11-01','2026-11-02']
    page.locator('[data-failed-clear-dates=""]').click()
    assert page.evaluate('[failedDateFrom,failedScheduledFrom]') == ['', '2026-11-02']
    page.locator('[data-failed-toggle-date]').click()
    expect(page.locator('#failed-scheduled-from')).to_have_value('2026-11-02')
    page.locator('[data-failed-clear-dates="scheduled"]').click()
    assert page.evaluate('[failedDateFrom,failedScheduledFrom]') == ['', '']
    assert not errors, errors
    browser.close()
    print('PASS: Tracking-matched single-row filters at four widths, multi-select categories and both date ranges')
