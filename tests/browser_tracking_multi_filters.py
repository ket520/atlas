"""Checkbox filter selection, combined results, deselection and reset."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R==='function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:Array.from({length:6},(_,i)=>({
        id:'multi-'+i,order:'70000'+i,carrier:'Palletways',st:i%2?'Scheduled':'Delivered',logs:[],
        storeCode:['AMAZON','B&Q','WILKO'][Math.floor(i/2)],
      })),activity:[],integrations:[]});D=DeliveryStore.deliveries();R();
    }""")
    status = page.locator('[data-ui-select-id="dstatusValue"]')
    store = page.locator('[data-ui-select-id="dstoreValue"]')
    status.locator('[data-ui-select-trigger]').click()
    status.locator('[data-value="Scheduled"]').click()
    expect(page.locator('.tracking-row')).to_have_count(3)
    status.locator('[data-value="Delivered"]').click()
    expect(status.locator('[role="menuitemcheckbox"][aria-checked="true"]')).to_have_count(2)
    expect(status.locator('.ui-select-menu')).to_be_visible()
    expect(status.locator('.ui-select-label')).to_have_text('2 statuses selected')
    expect(page.locator('.tracking-row')).to_have_count(6)
    store.locator('[data-ui-select-trigger]').click()
    store.locator('[data-value="Amazon"]').click()
    store.locator('[data-value="B&Q"]').click()
    expect(store.locator('[role="menuitemcheckbox"][aria-checked="true"]')).to_have_count(2)
    expect(page.locator('.tracking-row')).to_have_count(4)
    store.locator('[data-value="Amazon"]').click()
    expect(page.locator('.tracking-row')).to_have_count(2)
    store.locator('[data-value=""]').click()
    expect(page.locator('.tracking-row')).to_have_count(6)
    page.locator('[data-delivery-filter-action="clear-all"]').click()
    expect(page.locator('.tracking-row')).to_have_count(6)
    assert page.evaluate("!fs && !fstore")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:[
        {id:'sheet',order:'80001',carrier:'Palletways',st:'Unscheduled',palletwaysSheetStatus:'Delivered',logs:[]},
        {id:'fallback',order:'80002',carrier:'Palletways',st:'Delivered',logs:[]},
        {id:'transit',order:'80003',carrier:'Palletways',st:'Delivered',palletwaysSheetStatus:'In Transit',logs:[]}
      ],activity:[],integrations:[]});D=DeliveryStore.deliveries();fsrc='Palletways';R();
    }""")
    expect(status.locator('[data-value="palletways:Delivered"]')).to_have_count(0)
    expect(status.locator('[data-value="Delivered"]')).to_have_text('Delivered (2)')
    status.locator('[data-ui-select-trigger]').click()
    status.locator('[data-value="Delivered"]').click()
    expect(page.locator('.tracking-row')).to_have_count(2)
    browser.close()
    print('PASS: status/store checkboxes, combined selections, open menus, deselection and clear')
