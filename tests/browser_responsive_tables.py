"""Browser regression check using local fixture data, without a running server.

Run with Python and Playwright Chromium installed:
    python tests/browser_responsive_tables.py
"""
from pathlib import Path
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]

def serve(route):
    rel = urlparse(route.request.url).path.lstrip('/')
    if '/src/' in '/' + rel:
        rel = 'src/' + rel.split('/src/')[-1] if '/src/' in rel else rel
    path = ROOT / rel
    if not path.is_file() or not path.resolve().is_relative_to(ROOT):
        route.abort()
        return
    content = path.read_bytes()
    if path.suffix == '.html':
        content = content.replace(b'data-live="true"', b'data-live="false"')
        # Component layout fixtures isolate CSS; viewport zoom has its own integration test.
        content = content.replace(b'<html ', b'<html data-atlas-auto-scale="off" ')
    types = {'.html':'text/html', '.css':'text/css', '.js':'application/javascript', '.svg':'image/svg+xml'}
    route.fulfill(body=content, content_type=types.get(path.suffix, 'application/octet-stream'))

METRICS = '''() => {
  const wrap = document.querySelector('.tracking-records-scroll');
  const table = wrap.querySelector('table');
  const head = [...table.querySelectorAll('thead th')].map(e=>e.getBoundingClientRect());
  const row = table.querySelector('tbody tr');
  const cells = [...row.children].map(e=>e.getBoundingClientRect());
  return {viewport:innerWidth, pageWidth:document.documentElement.scrollWidth,
    wrapWidth:wrap.clientWidth, wrapRight:wrap.getBoundingClientRect().right,
    scrollWidth:wrap.scrollWidth, tableWidth:table.getBoundingClientRect().width,
    columns:head.length, cells:cells.length,
    aligned:head.length===cells.length && head.every((h,i)=>Math.abs(h.x-cells[i].x)<1 && Math.abs(h.width-cells[i].width)<1),
    overlaps:[...table.querySelectorAll('thead th'),...row.children].filter(e=>e.scrollWidth>e.clientWidth+1).map(e=>e.textContent.trim().slice(0,45))};
}'''

if __name__ == '__main__':
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(reduced_motion='reduce')
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        checks = 0
        errors = []
        page.on('pageerror', lambda err: errors.append(str(err)))
        for name in ['deliveries','failed-deliveries']:
            page.goto(f'https://deliverydesk.test/pages/{name}.html')
            page.add_style_tag(content='*,*::before,*::after { transition: none !important; animation: none !important; }')
            page.evaluate('''() => {
              const records = Array.from({length:30},(_,i)=>({id:'test-'+i,order:'12345678'+i,
                orderRef:'REFERENCE-LONG-12345',cust:'Example customer with a long company name',
                addr:'123 Example Street, Manchester M1 1AA',phone:'01234567890',
                email:'long.email.address@example.com',carrier:'Palletways',st:page === 'Deliveries' ? 'Out for Delivery' : 'Failed',date:'2026-10-21',
                skuItems:'LONG-SKU-1234567890;SECOND-SKU-0987654321',
                salesActivityDetails:{'Order Type':['Amazon','HR_Replacement','Debenhams','B&Q','Ebay','Shopify'][i%6],
                  'Order Analysis':i%6===2 ? 'Debenhams - Neshome' : 'Shopify - Neshome'},
                instructions:'Please call before delivery and use the rear entrance.',
                bookingStatus:'Awaiting customer response',deliveryMethodRaw:'Palletways premium service',logs:[]}));
              DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});
              D=DeliveryStore.deliveries(); R();
            }''')
            for carrier in (['','Palletways'] if name=='deliveries' else ['']):
                if name=='deliveries': page.evaluate('(carrier)=>{fsrc=carrier;R();}',carrier)
                for width in [2560,1920,1440,1366,1280,1237,1180,1100,1024,947,833,761,760,600,390,320]:
                    for height in [560,768,900]:
                        page.set_viewport_size({'width':width,'height':height})
                        for collapsed in [False, True]:
                            page.evaluate('(cl)=>document.querySelector(".app").classList.toggle("cl",cl)',collapsed)
                            info = {'page':name,'carrier':carrier,'collapsed':collapsed,'height':height,**page.evaluate(METRICS)}
                            assert info['pageWidth'] <= width + 1, info
                            assert info['wrapRight'] <= width + 1, info
                            assert info['aligned'], info
                            assert not info['overlaps'], info
                            assert page.evaluate('''() => [...document.querySelectorAll('.purchase-store-logo-tracking')].every(logo => {
                              const box=logo.parentElement.getBoundingClientRect();
                              const image=logo.getBoundingClientRect();
                              return image.width>0 && image.width<=56 && image.width<=box.width*.28+1
                                && image.left>=box.left && image.right<=box.right+1
                                && [...logo.parentElement.querySelectorAll('.tracking-cell-line')].every(text => {
                                  const r=text.getBoundingClientRect();
                                  return r.left>=image.right || r.right<=image.left || r.bottom<=image.top || r.top>=image.bottom;
                                });
                            })'''), info
                            # The last column remains reachable inside the table.
                            assert page.evaluate('''() => {
                              const w=document.querySelector('.tracking-records-scroll');
                              w.scrollLeft=w.scrollWidth;
                              const last=w.querySelector('thead th:last-child').getBoundingClientRect();
                              const bounds=w.getBoundingClientRect();
                              const visible=last.right<=bounds.right+1 && last.left>=bounds.left;
                              w.scrollLeft=0;
                              const body=w.querySelector('tbody');
                              body.scrollTop=body.scrollHeight;
                              const vertical=body.scrollTop>0;
                              body.scrollTop=0;
                              return visible && vertical;
                            }'''), info
                            assert page.evaluate('''() => [...document.querySelectorAll('.delivery-filters > *')]
                              .filter(e => e.getClientRects().length)
                              .every(e => {const r=e.getBoundingClientRect();return r.left>=0 && r.right<=innerWidth+1;})'''), info
                            checks += 1
                # Keyboard users can move the table sideways without scrolling the page.
                wrapper=page.locator('.tracking-records-scroll')
                wrapper.focus()
                wrapper.evaluate('(el)=>el.scrollLeft=0')
                page.keyboard.press('ArrowRight')
                page.wait_for_timeout(150)
                assert wrapper.evaluate('(el)=>el.scrollLeft>0'), (name,carrier)
                if name=='deliveries' and not carrier:
                    page.set_viewport_size({'width':1280,'height':720})
                    page.evaluate('document.querySelector(".app").classList.remove("cl")')
                    wrapper.evaluate('(el)=>el.scrollLeft=0')
                    (ROOT/'.tmp-tests').mkdir(exist_ok=True)
                    page.screenshot(path=str(ROOT/'.tmp-tests/responsive-tracking-1280.png'),full_page=True)
        assert not errors, errors
        print(f'PASS: {checks} table/page/viewport/sidebar combinations; column alignment, wrapping, contained overflow, horizontal and vertical scrolling, keyboard access, and no JavaScript errors.')
        browser.close()
