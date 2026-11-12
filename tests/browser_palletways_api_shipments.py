import sys
from pathlib import Path

from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from atlas_postgres_provider import _row
from delivery_data import row_to_delivery
from status_views import status_view


records = []
for order, statuses in [('672088', ['In Transit']), ('660098', ['Consignment Created']),
                        ('662712', ['Delivered', 'Unscheduled'])]:
    delivery = row_to_delivery(_row({'order_no': order, 'status': 'Completed',
        'cells': {'Delivery method': 'Palletways Next Day'}, 'palletways_shipments': [
            {'palletways_status': status, 'carrier_status': status, 'tracking_id': f'6000000000{index}',
             'consignment_number': f'{order}-{index}', 'status_checked_at': '2026-11-12T08:00:00Z'}
            for index, status in enumerate(statuses)
        ]}))
    delivery['statusView'] = status_view(delivery)
    records.append(delivery)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width in (1440, 390):
        page = browser.new_page(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        portal_requests = []
        page.on('request', lambda request: portal_requests.append(request.url) if '/api/palletways/' in request.url else None)
        page.route('https://deliverydesk.test/**', serve)
        page.route('**/api/**', lambda route: route.fulfill(json={'available': False}))
        page.route('**/api/palletways/portal/**', lambda route: route.fulfill(json={'trackingId': route.request.url.rsplit('/', 1)[-1], 'media': [], 'details': [{'title': 'Consignment details', 'fields': [{'label': 'Units', 'value': '1 @ 200kg'}]}], 'notes': [{'text': '<script>unsafe</script>'}]}))
        page.route('**/api/palletways/live/**', lambda route: route.fulfill(json={
            'ok': True, 'trackingId': route.request.url.rsplit('/', 1)[-1],
            'consignment': {'Number': '662712-0', 'Weight': '200', 'Reference': 'TEST'}, 'events': [], 'documents': {'podAvailable': True, 'labelAvailable': True},
            'status': {'status': 'Failed'},
        }))
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function('typeof R === "function"')
        page.evaluate('''records => {
          TrackingVisibility.setEnabled(false);TrackingVisibility.setWayfairEnabled(false);
          DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});
          D=DeliveryStore.deliveries();fsrc='Palletways';fs='';R();
        }''', records)
        assert page.locator('#tb tr[data-delivery-id]').count() == 3
        mixed = page.locator('#tb tr[data-delivery-id="662712"]')
        assert 'Delivered' in mixed.locator('.tracking-status-cell').inner_text()
        assert 'Unscheduled' in mixed.locator('.tracking-status-cell').inner_text()
        assert mixed.locator('.tracking-shipment-number').count() == 2
        counts = page.evaluate('trackingLevelCounts()')
        assert counts['statusTotal'] == 3
        assert counts['statuses']['Delivered'] == counts['statuses']['Unscheduled'] == 1
        for status in ('Delivered', 'Unscheduled', ['Delivered', 'Unscheduled']):
            page.evaluate('status=>{fs=status;R();}', status)
            assert page.locator('#tb tr[data-delivery-id]').count() == 1
        page.evaluate("fs='';R();op('662712')")
        page.locator('[aria-label="Palletways consignment details"]').first.wait_for(state='attached')
        page.wait_for_function("DeliveryStore.deliveries().find(item=>String(item.id) === '662712').palletwaysDocumentRecords?.length === 2")
        assert any('/api/palletways/portal/60000000000' in url for url in portal_requests)
        assert any('/api/palletways/portal/60000000001' in url for url in portal_requests)
        assert not any('/api/palletways/order-tracking/' in url for url in portal_requests)
        assert page.locator('.qd-palletways-shipments').count() == 0
        page.wait_for_function("document.querySelectorAll('.qd-palletways-documents iframe').length === 4")
        sources = page.locator('.qd-palletways-documents iframe').evaluate_all('(frames)=>frames.map(frame=>frame.getAttribute("src"))')
        assert any('/pod/60000000000' in url for url in sources)
        assert any('/pod/60000000001' in url for url in sources)
        assert any('/label/662712-0' in url for url in sources)
        assert any('/label/662712-1' in url for url in sources)
        assert 'Failed' not in page.locator('#tb tr[data-delivery-id="662712"] .tracking-status-cell').inner_text()

        assert page.locator('.qd-progress .is-active').count() < 4
        assert 'Not all consignments delivered' in page.locator('.qd-progress').inner_text()
        details = page.locator('[aria-label="Palletways consignment details"]')
        assert details.count() == 2
        assert details.first.locator('dt').all_inner_texts()[:3] == ['Consignment number', 'Tracking ID', 'Customer reference']
        assert page.locator('[data-detail-action="refresh-palletways-photos"]').count() == 1
        assert page.locator('.qd-palletways-portal-consignment').count() == 0
        details.first.screenshot(path=f'.tmp-tests/palletways-shipments-{width}.png')
        safe_markup = page.evaluate('''()=>palletwaysFullDetailsMarkup({
          tracking_id:'60000000000',consignment_number:'662712-0',
          status:{ETA:null,physical_collection_confirmed:null},
          historical_snapshot:{DueDate:'01/02/2025 10:00',text:'<img src=x onerror=alert(1)>'},
          documents:[{download_available:false,url:'https://invalid.test/unverified'}],
          linked_orders:[{order_no:'662712',mapping_status:'inactive'}]
        })''')
        assert '&lt;img' in safe_markup and '<img' not in safe_markup
        assert '<a ' not in safe_markup
        assert '01/02/2025 10:00' in safe_markup and 'inactive' in safe_markup
        assert 'Historical snapshot' in safe_markup
        assert 'Tracking notes' in safe_markup and 'Sync audit' in safe_markup
        page.route('**/api/atlas-palletways/**', lambda route: route.fulfill(json={
            'items': [{'NoteText': '<script>unsafe</script>'}], 'has_more': False,
            'source': 'live', 'offset': 0, 'limit': 50, 'total': 1,
        }))
        page.evaluate('''()=>{
          const panel=document.createElement('div');
          panel.id='palletways-record-test';
          panel.innerHTML=palletwaysFullDetailsMarkup({tracking_id:'60000000000',consignment_number:'662712-0'});
          document.body.append(panel);
        }''')
        page.locator('#palletways-record-test [data-palletways-records="events"] summary').dispatch_event('click')
        page.locator('#palletways-record-test [data-palletways-records="events"] button').dispatch_event('click')
        page.wait_for_function("document.querySelector('#palletways-record-test [data-palletways-record-list]').textContent.includes('unsafe')")
        assert '<script>' not in page.locator('#palletways-record-test').inner_html()
        assert page.locator('#palletways-record-test [data-palletways-records="events"] button').count() == 0
        page.evaluate("DeliveryDetail.close();fsrc='';fs='';R()")
        assert all('Completed' in text for text in page.locator('#tb .tracking-status-cell').all_inner_texts())
        assert not errors, errors
        print('Palletways multi-consignment UI verified:', width)
        page.close()
    browser.close()
