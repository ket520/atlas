"""Palletways B/C display switch preserves filters/scroll and copies the right value."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser=pw.chromium.launch()
    context=browser.new_context(viewport={'width':1440,'height':900},reduced_motion='reduce',permissions=['clipboard-read','clipboard-write'])
    page=context.new_page()
    page.set_default_timeout(5000)
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R==='function'")
    hydrate="""() => {
      DeliveryStore.hydrate({deliveries:Array.from({length:30},(_,i)=>({
        id:'number-'+i,order:'65000'+i,carrier:'Palletways',st:'Scheduled',logs:[],
        palletwaysSheetTrackingNumber:'60000000001',palletwaysSheetConsignmentNumber:'C-123',
      })),activity:[],integrations:[]});D=DeliveryStore.deliveries();fsrc='Palletways';R();
    }"""
    page.evaluate(hydrate)
    switch=page.locator('[data-palletways-number-type]')
    expect(switch).to_have_attribute('aria-label','Show Tracking ID')
    expect(page.locator('.tracking-palletways-number').first).to_contain_text('C-123')
    page.locator('[data-copy-consignment-number]').first.click()
    page.wait_for_function("navigator.clipboard.readText().then(text=>text==='C-123')")
    page.evaluate("document.querySelector('#tb').scrollTop=120;window.previousScroll=document.querySelector('#tb').scrollTop")
    switch.click()
    assert page.evaluate("document.querySelector('#tb').scrollTop===previousScroll")
    assert page.evaluate("fsrc==='Palletways'")
    expect(page.locator('.tracking-palletways-number').first).to_contain_text('60000000001')
    page.evaluate("document.querySelector('#tb').scrollTop=0")
    page.locator('[data-copy-palletways-tracking]').first.click()
    page.wait_for_function("navigator.clipboard.readText().then(text=>text==='60000000001')")
    expect(page.locator('.toast').last).to_have_text('Tracking number copied')
    expect(page.locator('#dr .dr')).to_have_count(0)
    page.reload();page.wait_for_function("typeof R==='function'");page.evaluate(hydrate)
    expect(switch).to_have_attribute('aria-label','Show Consignment No')
    switch.click()
    expect(page.locator('.tracking-palletways-number').first).to_contain_text('C-123')
    page.evaluate("D[0].palletwaysSheetTrackingNumber='';rows()")
    switch.click()
    expect(page.locator('.tracking-palletways-number').first).to_have_text('—')
    expect(page.locator('.tracking-palletways-number').first.locator('button')).to_have_count(0)
    for width in (1024,390):
        page.set_viewport_size({'width':width,'height':900})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    browser.close()
    print('PASS: Palletways B/C switch, correct copy values, preserved filters/scroll, remembered preference and blank handling')
