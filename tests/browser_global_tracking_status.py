"""All methods uses global groups; courier-specific source filters remain intact."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
from global_tracking_status_cases import global_status_cases

cases = global_status_cases()
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    records = [record for record,_ in cases]
    page.evaluate("""records=>{
      DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});
      D=DeliveryStore.deliveries();fsrc='';R();
    }""", records)
    assert page.evaluate('records=>records.map(overallTrackingStatus)', records) == [group for _,group in cases]
    counts = page.evaluate('trackingLevelCounts().statuses')
    assert sum(counts.values()) == len(records)
    assert 'Awaiting' not in counts
    awaiting_id = next(record['id'] for record,_ in cases if record['st']=='Awaiting')
    expect(page.locator(f'[data-delivery-id="{awaiting_id}"] .stx')).to_have_text('Other Status')
    expect(page.locator('[data-ui-select-id="dstatusValue"] [data-value="Awaiting"]')).to_have_count(0)
    expect(page.locator('[data-ui-select-id="dstatusValue"] [data-value="Next Stop"]')).to_have_count(1)
    for group in counts:
        page.evaluate('group=>{fs=group;rows()}', group)
        actual = set(page.locator('#tb tr[data-delivery-id]').evaluate_all('es=>es.map(e=>e.dataset.deliveryId)'))
        assert actual == {record['id'] for record,expected in cases if expected==group}, (group,actual)
    for carrier, specific in [('AMZ','amazon:LOST'), ('XDP','xdp:BOOKING'), ('Palletways','palletways:In Transit')]:
        page.evaluate("carrier=>{fs='';fsrc=carrier;R()}", carrier)
        assert specific in page.evaluate('trackingLevelCounts().statuses')
        page.evaluate('specific=>{fs=specific;rows()}', specific)
        expect(page.locator('#tb tr[data-delivery-id]')).to_have_count(1)
    requests = page.evaluate("""async () => {
      const requests=[];
      ApiClient.get=async path=>{requests.push(path);return {deliveries:[],total:0,hasMore:false};};
      document.body.dataset.live='true';liveReady=true;
      fsrc='';fs='Lost';await loadTrackingPage(true);
      fsrc='AMZ';fs='amazon:LOST';await loadTrackingPage(true);
      return requests.map(path=>Object.fromEntries(new URL(path,'https://test').searchParams));
    }""")
    assert requests[0]['global_status']=='1' and requests[0]['status']=='Lost', requests
    assert not requests[1].get('global_status') and requests[1]['courier_status']=='1', requests
    assert not errors, errors
    browser.close()
    print('PASS: backend/frontend mapping parity, all global filters reconcile, no Awaiting, raw courier filters preserved, API flag scoped to All methods')
