"""Collection Notes looks the same on first navigation, direct load and return."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

RECORD_STYLES = """() => [...document.querySelectorAll('.collection-records-table th,.collection-records-table td,.collection-note-link,.collection-delete-note')].map(el=>{
  const s=getComputedStyle(el);return [s.color,s.backgroundColor,s.borderColor,s.width,s.height,s.fontSize,s.padding];
})"""
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    for width in (1440,390):
        page=browser.new_page(viewport={'width':width,'height':1000},reduced_motion='reduce')
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**',serve)
        page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
        page.route('**/api/collection-notes',lambda route:route.fulfill(json={'records':[
            {'id':'note-1','order':'650001','customer':'Example customer','items':'SKU1'},
            {'id':'note-2','order':'650002','customer':'Example customer','items':'SKU2'}]}))

        def assert_records():
            page.mouse.move(0,0)
            expect(page.locator('[data-open-collection-record]')).to_have_count(2)
            expect(page.locator('.collection-records-toolbar > .collection-note-link')).to_have_css('background-color','rgb(98, 103, 233)')
            expect(page.locator('.collection-records-table th').first).to_have_css('background-color','rgb(37, 44, 74)')
            expect(page.locator('[data-open-collection-record]').first).to_have_css('cursor','pointer')
            expect(page.locator('.qd-customer-copy').first).to_have_css('background-color','rgb(110, 227, 238)')
            assert page.locator('link[href="/static/css/collection-records.css"]').count()==1
            return page.evaluate(RECORD_STYLES)

        page.goto('https://deliverydesk.test/pages/collective-note.html')
        direct=assert_records()
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R==='function'")
        page.evaluate("go('Collective Note')")
        assert assert_records()==direct
        assert page.locator('link[href="/static/css/collection.css"]').count()==0
        # Delay editor CSS after its JS loads: never expose an unstyled sheet.
        pending=[]
        page.route('**/static/css/collection.css',lambda route:pending.append(route))
        page.evaluate("history.pushState({page:'Collective Note'},'', './collective-note.html?view=create');R()")
        page.wait_for_function('!!window.CollectionNote')
        assert pending
        expect(page.locator('.cn-workspace')).to_have_count(0)
        pending[0].fulfill(body=(ROOT/'static/css/collection.css').read_bytes(),content_type='text/css')
        page.unroute('**/static/css/collection.css')
        page.wait_for_selector('.cn-workspace')
        expect(page.locator('[data-collection-save]')).to_have_css('background-color','rgb(98, 103, 233)')
        for format in ('pdf','xlsx'):
            button=page.locator(f'[data-collection-download="{format}"]')
            button.hover()
            expect(button).to_have_css('color','rgb(255, 255, 255)')
            assert button.evaluate("el=>getComputedStyle(el,'::before').backgroundColor")==('rgb(98, 103, 233)' if format=='pdf' else 'rgb(37, 44, 74)')
        page.evaluate("go('Deliveries');go('Collective Note')")
        assert assert_records()==direct
        page.reload()
        assert assert_records()==direct
        page.close()
    browser.close()
    print('PASS: first/direct/return/reload styles match; editor waits for CSS; controls work at desktop/mobile sizes')
