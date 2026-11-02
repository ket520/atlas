from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser=pw.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':900},reduced_motion='no-preference')
    page.clock.install()
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.evaluate("""() => { const rows=Array.from({length:13},(_,i)=>({id:'preview-'+i,order:'65000'+i,cust:'Customer',carrier:'On Hold',st:'Unassigned',orderDate:'2026-10-24',logs:[]}));DeliveryStore.hydrate({deliveries:rows,activity:[],integrations:[]});D=DeliveryStore.deliveries();R(); }""")
    card=page.locator('[data-dash-widget="hold"]')
    expect(card.locator('[data-dash-view]')).to_have_count(1)
    expect(card.locator('.dash-preview-page')).to_have_count(1)
    expect(card.locator('.dash-preview-page:not([aria-hidden]) .dash-preview-row')).to_have_count(13)
    body=card.locator('.dash-widget-body').bounding_box()
    preview=card.locator('.dash-widget-preview').bounding_box()
    row=card.locator('.dash-preview-row').first.bounding_box()
    assert abs(preview['height']/row['height']-4)<.1,(preview,row,card.locator('.dash-preview-page').first.bounding_box())
    assert .45<preview['width']/body['width']<.55
    assert card.locator('.dash-preview-row').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='15px'
    assert card.locator('.dash-preview-row time').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='15px'
    page.mouse.move(0,0)
    position=lambda:card.locator('.dash-preview-track').evaluate('(el)=>new DOMMatrixReadOnly(getComputedStyle(el).transform).m42')
    page.clock.run_for(2000)
    assert position()==0
    page.clock.run_for(3600)
    card.locator('.dash-preview-track').evaluate('(el)=>el.getAnimations().forEach(a=>a.finish())')
    first=position()
    assert abs(first+preview['height']/4)<1,(first,preview)
    page.clock.run_for(1000)
    assert abs(position()-first)<.01
    page.clock.run_for(4000)
    card.locator('.dash-preview-track').evaluate('(el)=>el.getAnimations().forEach(a=>a.finish())')
    assert abs(position()-2*first)<1
    assert card.locator('[data-dash-order]').evaluate_all("items=>items.every(el=>el.querySelector('.dash-order-view-icon'))")
    # Finish the first pass: the final four orders show, then restart at the top.
    page.clock.run_for(35000)
    card.locator('.dash-preview-track').evaluate('(el)=>el.getAnimations().forEach(a=>a.finish())')
    assert abs(position()-9*first)<1
    page.clock.run_for(5000)
    assert abs(position())<1
    page.emulate_media(reduced_motion='reduce')
    page.evaluate("""async () => {
      const original=ApiClient.get;
      const rows=Array.from({length:13},(_,i)=>({id:'live-'+i,order:'75000'+i,orderDate:'2026-10-24'}));
      window.previewRequests=[];
      ApiClient.get=async path=>{
        previewRequests.push(path);
        if(path.startsWith('/dashboard?')) return {widgets:Object.fromEntries(['cancelled','charge-pending','hold','collect','palletways-next-day','out-of-stock','palletways-unbooked','van-unscheduled','returns'].map(key=>[key,{available:key!=='returns',total:key==='hold'?13:0,preview:key==='hold'?rows.slice(0,3):[]}]))};
        if(path.startsWith('/deliveries?')) return {deliveries:rows};
        return original(path);
      };
      document.body.dataset.live='true';
      await DashboardHome.load(true);
      ApiClient.get=original;
    }""")
    expect(card.locator('.dash-preview-page')).to_have_count(1)
    expect(card.locator('.dash-preview-page:not([aria-hidden]) .dash-preview-row')).to_have_count(13)
    assert page.evaluate("previewRequests.some(path=>path.includes('dashboard_widget=hold') && path.includes('limit=30'))")
    page.clock.run_for(5500)
    assert position()<0
    assert page.evaluate('document.documentElement.scrollHeight<=innerHeight')
    browser.close()
    print('PASS: arrow only, half-width four-row preview, one-row scrolling with pauses, four-row viewport, +1px font, reduced motion, legacy live API fallback and no page scroll')


