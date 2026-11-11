"""The Failed Deliveries workspace stays fixed; every row remains scrollable inside it."""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/failed-deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:Array.from({length:100},(_,i)=>({
        id:String(i),order:String(700000+i),carrier:['AMZ','Palletways','Own van','XDP'][i%4],
        st:'Failed',cust:'Example customer',reason:'Delivery failed',logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries();R();
    }""")
    for width,height in [(1920,1080),(1440,900),(1280,600),(1024,600),(390,600)]:
        page.set_viewport_size({'width':width,'height':height})
        for scaled in [False,True]:
            page.evaluate("""scaled=>{document.documentElement.dataset.atlasAutoScale=scaled?'on':'off';
              dispatchEvent(new Event('resize'));window.scrollTo(0,0);}""", scaled)
            metrics = page.evaluate("""() => {
              const body=document.querySelector('#failed-list');
              const wrap=document.querySelector('.failed-table-wrap');
              const head=document.querySelector('.failed-table thead');
              const top=head.getBoundingClientRect().top;
              body.scrollTop=body.scrollHeight;
              window.scrollTo(0,500);
              return {windowY:scrollY,tableBottom:wrap.getBoundingClientRect().bottom,
                height:innerHeight,bodyHeight:body.clientHeight,scrollTop:body.scrollTop,
                maxScroll:body.scrollHeight-body.clientHeight,
                headFixed:Math.abs(head.getBoundingClientRect().top-top)<1,
                lastRowBottom:body.lastElementChild.getBoundingClientRect().bottom,
                bodyBottom:body.getBoundingClientRect().bottom};
            }""")
            assert metrics['windowY']==0, (width,height,scaled,metrics)
            assert metrics['tableBottom']<=metrics['height']+1, (width,height,scaled,metrics)
            assert metrics['bodyHeight']>40 and metrics['maxScroll']>0, (width,height,scaled,metrics)
            assert abs(metrics['scrollTop']-metrics['maxScroll'])<2, metrics
            assert metrics['headFixed'], metrics
            assert metrics['lastRowBottom']<=metrics['bodyBottom']+2, metrics
    browser.close()
    print('PASS: no page scrolling; table header stays fixed and all 100 rows are reachable at desktop/mobile sizes with app scaling on/off')
