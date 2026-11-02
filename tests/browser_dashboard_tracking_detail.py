"""Dashboard order clicks reuse Tracking's complete detail UI and interactions."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

SNAPSHOT = """() => [...document.querySelectorAll('.qd-tracking-view .db,.qd-tracking-view .db *')].map(el=>{
 const s=getComputedStyle(el);
 return [el.tagName,el.className?.baseVal ?? el.className,el.children.length ? '' : el.textContent.trim(),s.color,s.backgroundColor,s.borderColor,s.width,s.height,s.fontSize,s.padding,s.display];
})"""
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    for width in (1440,390):
        baseline=None
        for name in ('deliveries','dashboard'):
            context=browser.new_context(viewport={'width':width,'height':900},reduced_motion='reduce',permissions=['clipboard-read','clipboard-write'])
            page=context.new_page()
            page.set_default_timeout(5000)
            page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
            page.route('https://deliverydesk.test/**',serve)
            page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.wait_for_function("typeof R==='function'")
            page.evaluate("""() => {
              DeliveryStore.hydrate({deliveries:[{id:'detail-test',order:'650001',
                cust:'Same customer',addr:'123 Example Street',phone:'0123456789',
                email:'customer@example.com',carrier:'On Hold',st:'Unassigned',
                orderRef:'REF-650001',orderDate:localDateKey(),logs:[]}],activity:[],integrations:[]});
              D=DeliveryStore.deliveries();R();
            }""")
            if name=='dashboard':
                # Use the real dashboard record click, retaining the current page.
                if width > 760:
                    page.locator('[data-dash-order="detail-test"]').first.click()
                else:
                    page.evaluate("op('detail-test')")
                assert page.evaluate('page')=='Dashboard'
            else:
                page.evaluate("op('detail-test')")
            panel=page.locator('.dr.qd.qd-tracking-view')
            expect(panel).to_be_visible()
            expect(panel.locator('.qd-section-tab')).to_have_count(4)
            expect(panel.locator('.qd-purchase-block')).to_be_visible()
            expect(panel.locator('.qd-note-actions')).to_have_count(0)
            expect(panel.locator('.qd-action-section')).to_be_hidden()
            page.mouse.move(0,0)
            snapshot=page.evaluate(SNAPSHOT)
            if baseline is None: baseline=snapshot
            else: assert snapshot==baseline, f'Detail content/styles differ at {width}px'
            for tab in panel.locator('.qd-section-tab').all():
                tab.click()
                expect(tab).to_have_attribute('aria-pressed','true')
            panel.locator('[data-copy-field="phone"]').click()
            page.wait_for_function("navigator.clipboard.readText().then(text=>text==='0123456789')")
            expect(panel.locator('[data-copy-field="phone"]')).to_have_css('background-color','rgb(81, 212, 225)')
            panel.locator('[data-detail-action="close"]').click()
            expect(panel).to_have_count(0)
            context.close()
    browser.close()
    print('PASS: dashboard click opens identical Tracking detail content/styles, tabs, note actions, copy and close on desktop/mobile')
