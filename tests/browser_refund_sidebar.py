"""Credit/refund sidebars show refund progress and amount across carriers."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/**', lambda route: route.fulfill(json={'available': False}))
    for carrier, width, category, gross, raw_status in [
        ('AMZ', 1440, True, '-125.50', 'C'),
        ('Palletways', 390, True, '-125.50', 'W'),
        ('XDP', 1440, True, '', 'H'),
        ('Own van', 1440, True, '-125.50', 'C'),
        ('Own van', 1440, False, '-125.50', 'C'),
    ]:
        page.set_viewport_size({'width': width, 'height': 1000})
        page.goto('https://deliverydesk.test/pages/refund.html' if category else 'https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R === 'function'")
        page.evaluate("""facts => {
          const record = {id:'663346',order:'663346',carrier:facts.carrier,st:'Delivered',rawStatus:facts.raw,
            cust:'Test customer',logs:[],trk:'TRACK-TEST',orderDate:'2026-11-01',completedAt:'2026-11-02T12:00:00Z',
            podPhotos:[{url:'https://deliverydesk.test/inherited-delivery-photo.jpg',kind:'Photo'}],providerPodNote:'Original delivery note',
            salesActivityDetails: {'Order Category':facts.refund?'Credit/Refund':'Order','Gross (base)':facts.gross},
            ...(facts.refund ? {orderRelationKind:'Credit/Refund'} : {})};
          DeliveryStore.hydrate({deliveries:[record],activity:[],integrations:[]});D=DeliveryStore.deliveries();R();op(record.id);
        }""", {'carrier': carrier, 'refund': category, 'gross': gross, 'raw': raw_status})
        panel = page.locator('.qd-tracking-view')
        expect(panel).to_be_visible()
        if category:
            expect(panel.locator('.qd-progress h3')).to_have_text('Refund progress')
            expect(panel.locator('.qd-tracking h3')).to_have_text('Refund amount')
            expect(panel.locator('.qd-refund-amount')).to_have_text('\u00a3125.50' if gross else 'Amount unavailable')
            expect(panel.locator('.qd-tracking-number, .qd-tracking-actions')).to_have_count(0)
            expect(panel.locator('.qd-progress-bottom > span').last).to_have_text('Completed' if raw_status == 'C' else 'Not completed')
            assert 'Shipment tracking' not in panel.inner_text()
            expect(panel.locator('[data-qd-tab="documents"]')).to_have_count(0)
            expect(panel.locator('.qd-pod, .qd-documents-empty, .qd-pod-image')).to_have_count(0)
            expect(panel.locator('.qd-section-tabs, .qd-activity, .qd-activity-log')).to_have_count(0)
            expect(panel.locator('.qd-summary')).to_have_count(0)
            expect(panel.locator('.qd-action-section')).to_be_visible()
            if raw_status == 'C':
                tick = panel.locator('.qd-refund-complete')
                expect(tick).to_be_visible()
                expect(tick).to_have_attribute('aria-label', 'Refund complete')
                assert tick.bounding_box()['x'] > panel.locator('.qd-refund-amount').bounding_box()['x']
                expect(panel.locator('.qd-refund-pending')).to_have_count(0)
            else:
                expect(panel.locator('.qd-refund-pending')).to_have_text('Not Yet')
                expect(panel.locator('.qd-refund-complete')).to_have_count(0)
            assert panel.evaluate("""el => {
              const pair = el.querySelector('.qd-pair').getBoundingClientRect();
              const actions = el.querySelector('.qd-action-section').getBoundingClientRect();
              return actions.top >= pair.bottom - 1;
            }""")
            assert panel.locator('.db').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgb(23, 28, 53)'
            assert panel.locator('.qd-tracking').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert panel.locator('.qd-customer-block').evaluate('el => getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
            assert panel.evaluate("""el => {
              const luminance = colour => {
                const rgb = colour.match(/[\\d.]+/g).slice(0, 3).map(Number).map(value => {
                  value /= 255; return value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4;
                });
                return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2];
              };
              return [...el.querySelectorAll('.qd-detail-heading-icon, .qd-action-card-icon')].every(tile => {
                const foreground = luminance(getComputedStyle(tile.querySelector('svg')).color);
                const background = luminance(getComputedStyle(tile).backgroundColor);
                return (Math.max(foreground, background) + .05) / (Math.min(foreground, background) + .05) >= 3;
              });
            }""")
        else:
            expect(panel.locator('.qd-progress h3')).to_have_text('Delivery progress')
            expect(panel.locator('.qd-tracking h3')).to_have_text('Shipment tracking')
            expect(panel.locator('.qd-refund-amount')).to_have_count(0)
            panel.get_by_role('button', name='Activity', exact=True).click()
            expect(panel.locator('.qd-event-top b').filter(has_text='Delivered').first).to_be_visible()
    assert not errors, errors
    browser.close()
    print('PASS: refund heading, amount, credit-note completion, missing amount, mobile layout and ordinary delivery preservation')
