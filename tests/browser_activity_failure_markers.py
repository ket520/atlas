"""Explicit courier failure events use the existing red animated timeline marker."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='no-preference')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    checks = [
        ['xdp','NOT RECEIVED Manual Confirm, Consignment Not Received','failed'],
        ['xdp','NOT_RECEIVED','failed'], ['xdp','DAMAGE','failed'], ['xdp','DELETE','failed'],
        ['xdp','Delivered but not received','failed'], ['amazon','DELIVERY_ATTEMPTED','failed'],
        ['palletways','Delivery refused','failed'], ['xdp','DELIVERED','delivered'],
        ['xdp','DELIVERY Scheduled for Delivery','neutral'], ['xdp','SMS notification','neutral'],
        ['ow','Failed order update','ow'], ['amazon','LOST','lost'],
    ]
    for source,title,expected in checks:
        assert page.evaluate('([source,title])=>activityMarkerKind(source,title)',[source,title]) == expected
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:[{id:'650001',order:'650001',carrier:'XDP',st:'Failed',
        xdpStatus:'NOT RECEIVED',logs:[],xdpEvents:[{type:'NOT RECEIVED',text:'Manual Confirm, Consignment Not Received',
          at:'2026-09-23T19:27:46',location:'460',consignment:'ZDBJSD019763',barcode:'ZDBJSD019763001'}]}],activity:[],integrations:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    page.locator('[data-delivery-id="650001"]').click()
    event = page.locator('.qd-merged-event-xdp').filter(has_text='NOT RECEIVED')
    expect(event).to_have_attribute('data-activity-marker','failed')
    marker = event.locator('.qd-event-marker')
    expect(marker).to_have_css('border-top-color','rgb(217, 54, 70)')
    expect(marker).to_have_css('animation-name','activity-point-pulse')
    assert marker.evaluate("e=>getComputedStyle(e,'::before').animationName") == 'activity-point-ring'
    page.emulate_media(reduced_motion='reduce')
    expect(marker).to_have_css('animation-name','none')
    expect(marker).to_have_css('border-top-color','rgb(217, 54, 70)')
    browser.close()
    print('PASS: screenshot NOT RECEIVED event gets red pulse/rings; other failures classified; delivered/OW/neutral retained; reduced motion respected')
