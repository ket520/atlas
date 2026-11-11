"""Failed Deliveries reconciles global Failed/Rejected/Lost, including Palletways."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
from global_tracking_status_cases import global_status_cases

cases = global_status_cases()
expected = {r['id'] for r,group in cases if group in {'Failed','Rejected','Lost'}}
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/failed-deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("records=>{DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});D=DeliveryStore.deliveries();R();}",
        [r for r,_ in cases])
    visible_ids = lambda: set(page.locator('#failed-list tr[data-delivery-id]').evaluate_all('es=>es.map(e=>e.dataset.deliveryId)'))
    assert visible_ids() == expected
    expect(page.locator('[data-failed-method="Palletways"] .tracking-courier-count')).to_have_text('3')
    status_counts = page.evaluate('Object.fromEntries(availableFailedStatuses())')
    assert set(status_counts) == {'Failed','Rejected','Lost'}
    for group in ['Failed','Rejected','Lost']:
        page.evaluate('group=>{failedStatus=group;failedRows()}', group)
        assert visible_ids() == {r['id'] for r,g in cases if g==group}, group
    page.evaluate("failedStatus='';R()")
    page.locator('[data-failed-method="Palletways"]').click()
    assert len(visible_ids()) == 3
    assert page.locator('#failed-list .tracking-status-cell .stx.bad').count() == 3
    page.evaluate("failedCarrier='';failedStatus='';R()")
    for width in [1440,390]:
        page.set_viewport_size({'width':width,'height':1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert not errors, errors
    browser.close()
    print('PASS: global Failed/Rejected/Lost included, Palletways visible, no stale-category false positives, filters and mobile layout reconcile')
