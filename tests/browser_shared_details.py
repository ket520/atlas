"""Shared Details layout preserves fields and controls across couriers."""
import json
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


capture = '--capture-baseline' in sys.argv
baseline_path = Path('.tmp-tests/detail-fields-before.json')
snapshots = {}
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width in [1440, 390]:
        context = browser.new_context(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
        context.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        context.route('https://deliverydesk.test/**', serve)
        context.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        context.route('**/api/**', lambda route: route.fulfill(json={'available': False, 'error': 'Fixture offline'}))
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R === 'function'")
        for carrier in ['Own van', 'AMZ', 'XDP', 'Palletways', 'Stopstart']:
            page.evaluate("""carrier => {
              const record = {id:'662105',order:'662105',carrier,cust:'Clare Shields',
                addr:'18 Crescent Road, London, DL4 1AP',phone:'07858650888',email:'clare@example.com',
                st:'Scheduled',orderRef:'1070370360-A',date:'2026-11-05',orderDate:'2026-11-03',
                deliveryMethodRaw:carrier+' delivery',bookingStatus:'Confirmed',rawStatus:'W',
                specialInstructions:'Please call before arrival. Leave with reception if unavailable.',
                storeCode:'B&Q',skuItems:'NS-5176R-SET+',logs:[],
                xdpLatestDetail:'Awaiting delivery confirmation',xdpParcelBarcodes:['XDP123456789'],
                palletwaysDetails:carrier==='Palletways'?{deliveryPostcode:'DL4 1AP',
                  deliveryAddress:'18 Crescent Road',deliveryTelephone:'07858650888',
                  deliveryContact:'Clare Shields',consignmentNumber:'PW123456',
                  collectionDepot:'Central depot',tailLift:'Yes',handBall:'Yes',dueAt:'2026-11-05T17:00:00'}:null};
              DeliveryStore.hydrate({deliveries:[record],activity:[],integrations:[]});
              D=DeliveryStore.deliveries();R();op(record.id);
            }""", carrier)
            panel = page.locator('.dr.qd.qd-tracking-view')
            expect(panel).to_be_visible()
            panel.get_by_role('button', name='Details', exact=True).click()
            expect(panel.locator('.qd-summary')).to_be_visible()
            expect(panel.locator('.qd-summary')).to_contain_text('1070370360-A')
            expect(panel.locator('.qd-summary')).to_contain_text('Confirmed')
            expect(panel.locator('.qd-summary')).to_contain_text('Scheduled')
            if carrier != 'Own van':
                expect(panel.locator('.qd-summary')).to_contain_text('Please call before arrival.')
            if carrier == 'Palletways':
                expect(panel.locator('.qd-provider')).not_to_contain_text('Tail lift requested')
                expect(panel.locator('.qd-provider')).not_to_contain_text('Hand-ball requested')
            fields = panel.locator('.qd-summary-item, .qd-provider .qd-facts > div').evaluate_all(
                "nodes=>nodes.map(node=>node.textContent.replace(/\\s+/g,' ').trim())")
            snapshots[f'{width}:{carrier}'] = fields
            assert panel.evaluate('el=>el.scrollWidth<=el.clientWidth+1'), (width, carrier)
            if not capture:
                expect(panel.locator('.qd-detail-heading')).to_be_visible()
                expect(panel.locator('[data-summary-field="scheduled"]')).to_be_visible()
                expect(panel.locator('[data-summary-field="scheduled"] b')).to_have_css('color', 'rgb(244, 246, 255)')
                expect(panel.locator('.qd-section-tabs')).to_be_in_viewport()
            if width == 1440 and carrier == 'Palletways':
                Path('.tmp-tests').mkdir(exist_ok=True)
                panel.screenshot(path=f'.tmp-tests/detail-{"before" if capture else "after"}.png')
        assert not errors, errors
        context.close()
    browser.close()
if capture:
    baseline_path.write_text(json.dumps(snapshots), encoding='utf-8')
elif baseline_path.exists():
    assert snapshots == json.loads(baseline_path.read_text(encoding='utf-8')), 'A detail field was removed or changed'
print('PASS: five couriers at desktop/mobile widths, visible detail fields preserved and no panel overflow')
