"""Tracking colours change while table geometry and status colours stay intact."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve, ROOT

original = (ROOT / 'static/css/tracking.css').read_text(encoding='utf-8').split('/* Atlas Tracking surfaces')[0]
MEASURE = """() => ({
  cells: [...document.querySelectorAll('.current-table th,.current-table td')].map(el => {
    const r=el.getBoundingClientRect(); return [r.width,r.height];
  }),
  status: [...document.querySelectorAll('.tracking-status-cell .stx')].map(el => getComputedStyle(el).color)
})"""
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    baseline = {}
    for themed in (False, True):
        context = browser.new_context(viewport={'width': 1440, 'height': 900}, reduced_motion='no-preference')
        page = context.new_page()
        page.set_default_timeout(5000)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        if not themed:
            page.route('**/static/css/tracking.css', lambda route: route.fulfill(body=original, content_type='text/css'))
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R === 'function'")
        page.evaluate("""() => {
          DeliveryStore.hydrate({deliveries:Array.from({length:6}, (_,i) => ({
            id:'atlas-'+i,order:'65000'+i,carrier:'Palletways',cust:'Example customer',
            st:i % 2 ? 'Scheduled' : 'Delivered',date:'2026-10-24',logs:[]
          })),activity:[],integrations:[]});
          D=DeliveryStore.deliveries();R();
        }""")
        for carrier in ('', 'Palletways', 'AMZ', 'XDP', 'Stopstart'):
            page.evaluate('(carrier) => {fsrc=carrier;R()}', carrier)
            if not themed:
                baseline[carrier] = page.evaluate(MEASURE)
                continue
            assert page.evaluate(MEASURE) == baseline[carrier], carrier
            expect(page.locator('.current-table th').first).to_have_css('background-color', 'rgb(37, 44, 74)')
            expect(page.locator('.current-table th').first).to_have_css('color', 'rgb(255, 255, 255)')
        if themed:
            page.evaluate("fsrc='';R()")
            row = page.locator('.tracking-row').first
            row.evaluate("el => el.classList.add('is-selected')")
            expect(row.locator('td').first).to_have_css('background-color', 'rgb(230, 231, 252)')
            page.evaluate("""() => {
              const animate=Element.prototype.animate;
              Element.prototype.animate=function(...args) {
                if(this.classList.contains('scope-liquid')) {
                  const s=getComputedStyle(this); window.liquidColors=[s.borderTopColor,s.backgroundImage];
                }
                return animate.apply(this,args);
              };
            }""")
            page.locator('[data-delivery-filter-action="method"][data-value="Palletways"]').click()
            page.wait_for_function('window.liquidColors')
            colors=page.evaluate('window.liquidColors')
            assert colors[0] == 'rgb(98, 103, 233)', colors
            assert '98, 103, 233' in colors[1] and '110, 227, 238' in colors[1], colors
            page.wait_for_selector('.scope-liquid', state='detached')
            page.mouse.move(0,0)
            page.screenshot(path=str(ROOT / '.test-temp/atlas-tracking.png'))
        context.close()
    browser.close()
    print('PASS: Tracking Atlas backgrounds, unchanged geometry/status colours, Indigo/Cyan liquid animation')
