"""Check automatic 25-row batches with local APIs: python tests/browser_scroll_batches.py."""
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


def records(offset, count, query=''):
    return [dict(id=f'{query}-{i}', order=str(i), carrier='Palletways', st='Failed',
                 cust='Example customer', date='2026-10-21', logs=[])
            for i in range(offset, offset + count)]


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for name, body_id in [('deliveries', 'tb'), ('failed-deliveries', 'failed-list')]:
        page = browser.new_page(reduced_motion='reduce')
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
        calls, held = [], []
        state = {'hold': True, 'fail': False}

        def api(route):
            params = parse_qs(urlparse(route.request.url).query)
            offset = int(params.get('offset', ['0'])[0])
            query = params.get('q', [''])[0]
            calls.append((query, offset))
            result = dict(deliveries=records(offset, min(25, 60-offset), query), total=60, hasMore=offset+25<60)
            if offset == 25 and state['hold']:
                held.append((route, result))
            elif offset == 25 and state['fail']:
                state['fail'] = False
                route.fulfill(status=503, json={'error': 'Fixture unavailable'})
            else:
                route.fulfill(json=result)

        page.route('**/api/deliveries?*', api)
        page.goto(f'https://deliverydesk.test/pages/{name}.html')
        page.locator('.tracking-records-scroll').wait_for()
        page.evaluate('''() => {document.body.dataset.live='true';liveReady=true;
            liveSummary={failedPreview:[],failedTotal:60};R();}''')
        rows = page.locator(f'#{body_id} .tracking-row')
        page.wait_for_function('(id)=>document.getElementById(id).querySelectorAll(".tracking-row").length===25', arg=body_id)
        assert calls == [('', 0)], calls
        assert page.locator('[data-tracking-more],[data-failed-more]').count() == 0

        def bottom():
            page.locator(f'#{body_id}').evaluate('''el=>{el.scrollTop=el.scrollHeight;el.dispatchEvent(new Event('scroll'));}''')

        def wait_rows(count):
            page.wait_for_function('([id,n])=>document.getElementById(id).querySelectorAll(".tracking-row").length===n', arg=[body_id,count])

        first_id = rows.first.get_attribute('data-delivery-id')
        bottom()
        page.wait_for_timeout(50)
        for _ in range(5): bottom()
        assert calls == [('', 0), ('', 25)], calls
        assert len(held) == 1
        previous_top = page.locator(f'#{body_id}').evaluate('(el)=>el.scrollTop')
        state['hold'] = False
        route, result = held.pop()
        route.fulfill(json=result)
        wait_rows(50)
        assert rows.first.get_attribute('data-delivery-id') == first_id
        assert page.locator(f'#{body_id}').evaluate('(el)=>el.scrollTop') == previous_top
        bottom()
        wait_rows(60)
        for _ in range(5): bottom()
        page.wait_for_timeout(100)
        assert calls == [('',0),('',25),('',50)], calls
        assert len(set(rows.evaluate_all('(els)=>els.map(el=>el.dataset.deliveryId)'))) == 60

        # A failed batch retains rows and offset, and does not retry in a loop.
        state['fail'] = True
        page.evaluate('''() => {if(page==='Deliveries'){q='retry';loadTrackingPage(true);}
            else {failedSearch='retry';loadFailedPage(true);}}''')
        wait_rows(25)
        bottom()
        page.wait_for_function('''() => document.querySelector('.tracking-list-footer').textContent.includes('Could not load')''')
        attempts = len(calls)
        page.wait_for_timeout(100)
        assert rows.count() == 25 and len(calls) == attempts
        page.locator(f'#{body_id}').evaluate('''el=>{el.scrollTop=0;el.dispatchEvent(new Event('scroll'));}''')
        bottom()
        wait_rows(50)
        assert calls[-2:] == [('retry',25),('retry',25)], calls

        # A response for the old filter must not append to a new result set.
        state['hold'] = True
        page.evaluate('''() => {if(page==='Deliveries'){q='old';loadTrackingPage(true);}
            else {failedSearch='old';loadFailedPage(true);}}''')
        wait_rows(25)
        bottom()
        page.wait_for_timeout(50)
        assert len(held) == 1
        page.evaluate('''() => {if(page==='Deliveries'){q='new';loadTrackingPage(true);}
            else {failedSearch='new';loadFailedPage(true);}}''')
        wait_rows(25)
        route, result = held.pop()
        route.fulfill(json=result)
        page.wait_for_timeout(100)
        assert rows.count() == 25
        assert all(value.startswith('new-') for value in rows.evaluate_all('(els)=>els.map(el=>el.dataset.deliveryId)'))

        if name == 'failed-deliveries':
            state['hold'] = False
            attempts = len(calls)
            page.evaluate('''preview => {failedSearch='';liveSummary={failedPreview:preview,failedTotal:60};loadFailedPage(true);}''', records(0,25))
            wait_rows(25)
            assert len(calls) == attempts
            bottom()
            wait_rows(50)
            assert calls[-1] == ('',25)
        page.close()
    browser.close()
    print('PASS: both tables load 25, 50, then 60 rows on scroll; no buttons, duplicates, concurrent requests, or extra end requests; scroll position and rows survive appends/errors, and retry uses the same offset.')
