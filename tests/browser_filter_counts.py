"""Check filter labels/counts at narrow widths using local fixtures.

Run: python tests/browser_filter_counts.py (requires Playwright Chromium).
"""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
    checks = 0
    for name in ['deliveries', 'failed-deliveries']:
        page.goto(f'https://deliverydesk.test/pages/{name}.html')
        page.locator('.tracking-scope-sections').wait_for()
        page.add_style_tag(content='*,*::before,*::after{animation:none!important;transition:none!important}')
        page.evaluate('''() => {
            const carriers=['Own van','Self Delivery','Palletways','AMZ','XDP','Stopstart','Yodel','Wayfair',
                'Charge Pending (Remote Postcode)','Collect in Person','Do Not Pick Yet','UK Next Day'];
            TrackingVisibility.setWayfairEnabled(false);
            DeliveryStore.hydrate({deliveries:carriers.map((carrier,i)=>({id:String(i),order:String(i),carrier,
                st:'Failed',cust:'Customer',date:'2026-10-21',logs:[]})),activity:[],integrations:[]});
            D=DeliveryStore.deliveries(); R();
        }''')
        for large in [False, True]:
            if large:
                page.evaluate('''() => document.querySelectorAll('.tracking-scope-sections .fx-tab')
                    .forEach(button=>button.lastElementChild.textContent='1234567')''')
            for width in [320,375,390,600,760,761,800,900,1024,1180,1280,1440,1920,2560]:
                page.set_viewport_size({'width': width, 'height': 768})
                for collapsed in [False, True]:
                    page.evaluate('(cl)=>document.querySelector(".app").classList.toggle("cl",cl)', collapsed)
                    failures = page.evaluate('''() => [...document.querySelectorAll('.tracking-scope-sections .fx-tab')]
                        .flatMap(button=>{
                            const label=button.querySelector('.tracking-courier-self-label') || button.firstElementChild;
                            const count=button.lastElementChild;
                            const b=button.getBoundingClientRect(),l=label.getBoundingClientRect(),c=count.getBoundingClientRect();
                            const clipped=button.scrollWidth>button.clientWidth+1 || c.right>b.right
                                || c.bottom>b.bottom || c.top<b.top || b.height>80;
                            return l.right>c.left+.5 || clipped || b.right>innerWidth+1
                                ? [button.textContent.trim()] : [];
                        })''')
                    assert not failures, (name, large, width, collapsed, failures)
                    checks += 1
        page.set_viewport_size({'width': 1024, 'height': 768})
        page.evaluate('document.querySelector(".app").classList.remove("cl")')
        page.locator('.tracking-scope-sections').screenshot(path=f'.tmp-tests/{name}-filters.png')
    browser.close()
    print(f'PASS: {checks} page/viewport/sidebar/count combinations, including seven-digit counts; labels precede counts without clipping or excessive wrapping.')
