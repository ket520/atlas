"""Hide switches invalidate Dashboard data immediately without a document reload."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      localStorage.setItem('deliverydesk-widget-tour-v1','seen');
      localStorage.setItem('delivery-desk-hide-hygienic-tracking','false');
      localStorage.setItem('delivery-desk-hide-wayfair-tracking','false');
      localStorage.setItem('delivery-desk-hide-wilko-tracking','false');
      localStorage.setItem('delivery-desk-hide-palletways-b2b','false');
      localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['hold']));""")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      window.visibilityCalls=[];window.holdDashboard=false;window.releaseDashboard=null;
      const keys=['palletways-depot-3days','cancelled','hold','out-of-stock','charge-pending','collect',
        'palletways-next-day','palletways-unbooked','van-unscheduled','returns','awaiting-dispatch'];
      ApiClient.get=async path=>{
        if (!path.startsWith('/dashboard?')) return {deliveries:[],total:0,hasMore:false};
        const params=Object.fromEntries(new URL(path,'https://test').searchParams);
        visibilityCalls.push(params);
        const count=100-(params.hide_hygienic==='1'?10:0)-(params.hide_wayfair==='1'?20:0)
          -(params.hide_wilko==='1'?30:0)-(params.hide_palletways_b2b==='1'?5:0);
        const row={id:'1',order:'1',carrier:'Own van',st:'Unassigned',bookingStatus:''};
        const result={syncedAt:'fixed',widgets:Object.fromEntries(keys.map(key=>[key,{
          available:key!=='returns',total:count,rows:Array.from({length:30},()=>row),preview:[],
          scope:key==='cancelled'?'today':key==='palletways-unbooked'?'booked-in-no-current-ow-not-delivered':''}]))};
        if (holdDashboard) {holdDashboard=false;await new Promise(resolve=>releaseDashboard=resolve);}
        return result;
      };
      document.body.dataset.live='true';liveReady=true;liveSummary={syncedAt:'fixed',filterFacets:[]};R();
    }""")
    count = page.locator('[data-dash-widget="hold"] .dash-widget-total strong')
    expect(count).to_have_text('100')
    for key, difference in [('hygienic',10),('wayfair',20),('wilko',30),('palletways-b2b',5)]:
        page.evaluate("go('Settings')")
        page.locator(f'[data-settings-company="{key}"]').check(force=True)
        page.evaluate("go('Dashboard')")
        expect(count).to_have_text(str(100-difference))
        page.evaluate("go('Settings')")
        page.locator(f'[data-settings-company="{key}"]').uncheck(force=True)
        page.evaluate("go('Dashboard')")
        expect(count).to_have_text('100')
    assert len(page.evaluate('visibilityCalls')) == 9
    # Reusing a prior combination must still fetch after a settings change.
    page.evaluate("go('Settings')")
    page.locator('[data-settings-company="hygienic"]').check(force=True)
    page.locator('[data-settings-company="hygienic"]').uncheck(force=True)
    page.evaluate("go('Dashboard')")
    expect(count).to_have_text('100')
    assert len(page.evaluate('visibilityCalls')) == 10
    # A delayed old response must not restore counts for the previous hide settings.
    page.evaluate('holdDashboard=true;void DashboardHome.load(true)')
    page.wait_for_function('releaseDashboard !== null')
    page.evaluate("go('Settings')")
    page.locator('[data-settings-company="wilko"]').check(force=True)
    page.evaluate("go('Dashboard')")
    expect(count).to_have_text('70')
    page.evaluate('releaseDashboard()')
    page.wait_for_timeout(100)
    expect(count).to_have_text('70')
    # Returning to a tab re-reads settings changed by another app tab.
    page.evaluate("""() => {
      localStorage.setItem('delivery-desk-hide-wilko-tracking','false');
      dispatchEvent(new StorageEvent('storage',{key:'delivery-desk-hide-wilko-tracking',newValue:'false'}));
    }""")
    expect(count).to_have_text('100')
    assert page.evaluate("performance.getEntriesByType('navigation').length") == 1
    assert not errors, errors
    browser.close()
    print('PASS: all four hide/unhide switches refresh Dashboard without reload, old responses cannot overwrite counts, prior combinations and cross-tab changes refresh')
