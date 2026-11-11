"""Column F alone controls status when the Palletways filter is selected."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1920, 'height': 1080}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries: [
        {id:'663346',order:'663346',carrier:'Palletways',st:'Rejected',palletwaysStatusLabel:'Delivery refused',statusSource:'Palletways',palletwaysSheetStatus:'Delivered',logs:[]},
        {id:'663347',order:'663347',carrier:'Palletways',st:'Scheduled',palletwaysSheetStatus:'Delivered',logs:[]},
        {id:'663348',order:'663348',carrier:'Palletways',st:'Delivered',palletwaysSheetStatus:'Palletways Not Assigned',logs:[]},
        {id:'663349',order:'663349',carrier:'Palletways',st:'Unscheduled',palletwaysSheetStatus:'Palletways Not Assigned',logs:[]},
        {id:'663350',order:'663350',carrier:'Palletways',st:'Unscheduled',rawStatus:'Completed',orderRelationKind:'Credit/Refund',palletwaysSheetStatus:'Palletways Not Assigned',logs:[]},
      ],activity:[],integrations:[]}); D=DeliveryStore.deliveries(); R();
    }""")
    row = page.locator('[data-delivery-id="663346"]')
    expect(row.locator('.tracking-status-cell .stx')).to_have_text('Delivery refused')
    expect(page.locator('[data-delivery-id="663348"] .tracking-status-cell .stx')).to_have_text('Delivered')
    page.evaluate("fsrc='Palletways';R()")
    expect(row.locator('.tracking-status-cell .stx.ok')).to_have_text('Delivered')
    expect(row.locator('.tracking-status-cell')).to_contain_text('Palletways')
    assert 'Palletways sheet' in row.locator('.tracking-status-cell').inner_text()
    expect(page.locator('[data-delivery-id="663347"] .tracking-status-cell .stx.ok')).to_have_text('Delivered')
    for order in ('663348', '663349'):
        badge = page.locator(f'[data-delivery-id="{order}"] .tracking-status-cell .stx')
        expect(badge).to_have_text('Unscheduled')
        assert badge.evaluate('el => getComputedStyle(el).color') == 'rgb(134, 85, 200)'
    page.evaluate("fs='Unscheduled';rows()")
    expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(2)
    assert page.evaluate('trackingLevelCounts().statuses.Unscheduled') == 2
    assert page.evaluate("D.find(row => row.order === '663348').st") == 'Delivered'
    page.evaluate("fs='Delivered';rows()")
    expect(row).to_have_count(1)
    page.evaluate("fs='palletways:Status unavailable';rows()")
    expect(row).to_have_count(0)
    browser.close()
    print('PASS: Palletways filter uses column F and maps Not Assigned to Unscheduled')
