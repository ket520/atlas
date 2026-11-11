"""Zero-count categories are omitted; controls disappear when no categories remain."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    expect(page.locator('[data-ui-select-id="dscopeValue"]')).to_have_count(0)
    page.evaluate("""() => {
      const today=localDateKey();
      DeliveryStore.hydrate({deliveries:[
        {id:'1',order:'1',carrier:'Own van',st:'Scheduled',date:today,logs:[]},
        {id:'2',order:'2',carrier:'AMZ',st:'Scheduled',date:'2020-01-01',logs:[]},
        {id:'3',order:'3',carrier:'Palletways',st:'Scheduled',palletwaysSheetStatus:'In Transit',
          palletwaysDepotStay:{verified:true,arrivedAt:new Date(Date.now()-96*3600000).toISOString()},logs:[]}
      ],activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
    }""")
    category = page.locator('[data-ui-select-id="dscopeValue"]')
    expect(category.locator('[data-value="today"]')).to_have_text('Today Deliveries (1)')
    expect(category.locator('[data-value="hygienic"]')).to_have_count(0)
    page.locator('[data-delivery-filter-action="method"][data-value="AMZ"]').click()
    expect(category).to_have_count(0)
    page.locator('[data-delivery-filter-action="method"][data-value="Palletways"]').click()
    expect(category.locator('[data-value="palletways-depot-3days"]')).to_have_text('At Depot 3> Days (1)')
    page.goto('https://deliverydesk.test/pages/failed-deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:[{id:'4',order:'4',carrier:'AMZ',st:'Failed',logs:[]}],activity:[],integrations:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    failed = page.locator('[data-ui-select-id="failed-scope-value"]')
    expect(failed).to_have_count(0)
    page.evaluate("""() => {
      DeliveryStore.add({id:'5',order:'5',carrier:'On Hold',st:'Failed',logs:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    expect(failed.locator('[data-value="On Hold"]')).to_have_text('On Hold (1)')
    expect(failed.locator('[data-value="Cancelled"]')).to_have_count(0)
    expect(failed.locator('[data-value="SUPPLIER"]')).to_have_count(0)
    page.locator('[data-failed-method="AMZ"]').click()
    expect(failed).to_have_count(0)
    assert not errors, errors
    browser.close()
    print('PASS: empty category options and controls hidden; positive categories and depot counts retained; scoped to selected carrier')
