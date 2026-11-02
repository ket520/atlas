"""Exercise small laptop workspaces with navigation expanded/collapsed and long data."""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve, METRICS


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    checks = 0
    for view in ['failed-deliveries', 'integrations']:
        page.goto(f'https://deliverydesk.test/pages/{view}.html')
        page.wait_for_function("typeof DeliveryStore !== 'undefined'")
        page.add_style_tag(content='*,*::before,*::after {transition:none!important;animation:none!important}')
        page.evaluate('''() => {
          TrackingVisibility.setEnabled(false); TrackingVisibility.setWayfairEnabled(false);
          TrackingVisibility.setWilkoEnabled(false);
          DeliveryStore.hydrate({deliveries:Array.from({length:30}, (_,i)=>({
            id:String(i),order:'658883',orderRef:'REFERENCE-LONG-12345',
            cust:'A long customer company name for responsive verification',
            addr:'123 Long Street, Manchester M1 1AA', phone:'01234567890',
            email:'long.email.address@example.com',carrier:'XDP',st:'Failed',xdpStatus:'NOT RECEIVED',
            storeCode:'AMAZON',date:'2026-10-22',skuItems:'LONG-SKU-1234567890',
            salesActivityDetails:{},logs:[]})),activity:[],integrations:[]});
          D=DeliveryStore.deliveries();
          failedCarrier='XDP'; failedStore='Amazon'; failedStatus='xdp:NOT RECEIVED';
          failedDateFrom='2026-10-01';failedDateTo='2026-10-22';
          syncControl={rows:Array.from({length:20},()=>({integration:'A long integration name',
            frequencyMinutes:'10',triggerStatus:'ACTIVE',lastApplied:'22/10/2026 14:30:00',
            nextRunAt:new Date(Date.now()+600000).toISOString()}))};
          syncRunLog={rows:Array.from({length:30},()=>({integration:'Amazon Shipping integration',
            startedAt:'22/10/2026 14:30:00',executionResult:'RETURNED',
            recordsInserted:'123456',recordsUpdated:'1234567'}))};
          liveSummary={orderDateRanges:{All:{from:'2025-01-01',to:'2026-10-22'}}};
          integrationView='traffic'; R();
        }''')
        # Keep rows visible despite the date filter; exercise its longest label.
        if view == 'failed-deliveries':
            page.evaluate("failedDateFrom='';failedDateTo='';failedRows();")
        for width in [1920, 1536, 1440, 1366, 1280, 1180, 1100, 1024, 900, 800, 760, 600, 390]:
            for height in [600, 768, 900]:
                page.set_viewport_size({'width': width, 'height': height})
                for collapsed in [False, True]:
                    page.evaluate('(value)=>document.querySelector(".app").classList.toggle("cl",value)', collapsed)
                    context = (view, width, height, collapsed)
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), context
                    if view == 'failed-deliveries':
                        metrics = page.evaluate(METRICS)
                        assert metrics['aligned'], (context, metrics)
                        assert not metrics['overlaps'], (context, metrics)
                        assert page.evaluate('''() => [...document.querySelectorAll('.delivery-filters > *')]
                          .filter(el=>el.getClientRects().length).every(el=>{
                            const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1;
                          })'''), context
                        if width >= 800:
                            assert page.evaluate('''() => new Set([...document.querySelectorAll('.delivery-filters > *')]
                              .filter(el=>el.getClientRects().length).map(el=>{const r=el.getBoundingClientRect();return Math.round(r.top+r.height/2)})).size===1'''), context
                    else:
                        assert page.evaluate('''() => [...document.querySelectorAll('.integration-flow-card,.integration-sync-scroll')]
                          .every(el=>{const r=el.getBoundingClientRect();return r.left>=0&&r.right<=innerWidth+1;})'''), context
                        assert page.evaluate('''() => [...document.querySelectorAll('.integration-sync-scroll')].every(el=>{
                          el.scrollLeft=el.scrollWidth;const r=el.getBoundingClientRect();
                          const last=el.querySelector('thead th:last-child').getBoundingClientRect();
                          return last.right<=r.right+1&&last.left>=r.left;
                        })'''), context
                    checks += 1
    assert not errors, errors
    print(f'PASS: {checks} responsive checks across Failed Deliveries and Integration, expanded/collapsed navigation, laptop widths and short screens.')
    browser.close()
