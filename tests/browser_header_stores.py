"""Store shortcuts: exclusions, SPA updates, layout, animation and B&Q action."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width, motion in [(1440, 'no-preference'), (1024, 'reduce'), (390, 'reduce')]:
        context = browser.new_context(viewport={'width': width, 'height': 900}, reduced_motion=motion)
        page = context.new_page()
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        for name in ('deliveries', 'failed-deliveries', 'collective-note', 'manufacture-claims'):
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            links = page.locator('.header-store-links .dash-store-website')
            expect(links).to_have_count(6)
            assert page.locator('.header-store-links').evaluate("el => {const r=el.getBoundingClientRect(); return r.left>=0 && r.right<=innerWidth+1}")
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (name, width)
            expect(links.last).to_have_attribute('href', 'https://www.diy.com/verified-sellers/seller/3038/products')
            animation=links.first.locator('img').evaluate('el => getComputedStyle(el).animationName')
            assert animation == ('header-store-icon' if motion == 'no-preference' else 'none')
            assert links.locator('img').evaluate_all("items => items.every(el => getComputedStyle(el).animationDelay === '0s')")
            page.wait_for_function("[...document.querySelectorAll('.header-store-links img')].every(el=>el.complete && el.naturalWidth>0)")
            if motion == 'no-preference':
                for index in (0, 3, 5):
                    links.nth(index).hover()
                    assert links.locator('img').evaluate_all("items => items.every(el => getComputedStyle(el).animationName === 'header-store-icon' && getComputedStyle(el).animationPlayState === 'running')")
                page.mouse.move(0, 0)
                page.wait_for_timeout(100)
                times = links.locator('img').evaluate_all("items => items.map(el => el.getAnimations()[0].currentTime)")
                assert max(times)-min(times)<2, times
        for name in ('dashboard', 'integrations', 'guidance', 'settings'):
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.wait_for_function("typeof R === 'function'")
            expect(page.locator('.header-store-links')).to_have_count(0)
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        expect(page.locator('.header-store-links')).to_be_visible()
        page.evaluate("window.originalStores=document.querySelector('.header-store-links');R()")
        assert page.evaluate("originalStores===document.querySelector('.header-store-links')")
        page.evaluate("go('Dashboard')")
        expect(page.locator('.header-store-links')).to_have_count(0)
        page.evaluate("go('Deliveries')")
        expect(page.locator('.header-store-links .dash-store-website')).to_have_count(6)
        requests=[]
        page.route('**/api/bq/open', lambda route: (requests.append(route.request), route.fulfill(json={'message':'B&Q opened'})))
        page.locator('.header-store-links [data-bq-vpn]').click()
        expect(page.locator('.toast').last).to_contain_text('Check your taskbar or press Alt+Tab for the separate B&Q window')
        assert len(requests)==1 and requests[0].method=='POST'
        assert len(context.pages)==1
        context.close()

    # Confirm actual placement beside the existing Data sources control.
    page=browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.route('**/pages/deliveries.html',lambda route:route.fulfill(body=(ROOT/'pages/deliveries.html').read_bytes(),content_type='text/html'))
    page.route('**/api/**',lambda route:route.fulfill(json={'deliveries':[],'records':[],'rows':[],'integrations':[],'total':0,'failedTotal':0,'failedPreview':[],'filterFacets':[],'sourceUpdatedAt':{}}))
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    expect(page.locator('.source-info-button')).to_be_visible()
    assert page.locator('.header-store-links').evaluate("el => el.nextElementSibling.classList.contains('live-data-status')")
    source=page.locator('.source-info-button').bounding_box()
    links=page.locator('.header-store-links').bounding_box()
    assert abs(source['y']-links['y'])<=4, (source,links)
    assert links['x'] + links['width'] <= source['x'], (source,links)
    page.screenshot(path=str(ROOT/'.test-temp/header-stores.png'))
    browser.close()
    print('PASS: six header stores, excluded pages, responsive layout, slide animation, SPA updates and B&Q VPN action')
