"""Dashboard search keeps its layout, dismissal and pointer-driven controls."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.locator('#dq').wait_for()
    page.evaluate("""() => {
      const record = {id:'662105', order:'662105', cust:'Search customer',
        carrier:'AMZ', st:'Unscheduled', storeCode:'SHOPIFY', logs:[]};
      DeliveryStore.hydrate({deliveries:[record], activity:[], integrations:[]});
      D = DeliveryStore.deliveries();
      dq = '662105'; document.getElementById('dq').value = dq; dres();
    }""")
    expect(page.locator('#dres .rc')).to_have_count(1)
    expect(page.locator('#dres')).to_be_visible()
    metrics = page.evaluate("""() => {
      const bar = document.querySelector('.dash-searchbar');
      const dropdown = document.getElementById('dres');
      return {bar:bar.getBoundingClientRect().width, dropdown:dropdown.getBoundingClientRect().width,
        top:getComputedStyle(dropdown).borderTopLeftRadius,
        bottom:getComputedStyle(bar).borderBottomLeftRadius,
        status:getComputedStyle(dropdown.querySelector('.stx')).color};
    }""")
    assert abs(metrics['bar'] - metrics['dropdown']) < 1, metrics
    assert metrics['top'] == metrics['bottom'] == '0px', metrics
    assert metrics['status'] == 'rgb(255, 218, 128)', metrics
    page.locator('.dash-workspace-heading h1').click()
    expect(page.locator('#dres')).to_be_hidden()
    page.locator('#dq').click()
    expect(page.locator('#dres')).to_be_visible()
    page.evaluate("window.savedResult=document.querySelector('#dres .rc')")
    page.locator('#dq').click()
    assert page.evaluate("savedResult===document.querySelector('#dres .rc')")

    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id':'saved', 'order':'662105', 'customer':'Example', 'status':'Rejected'}
    ]}))
    page.goto('https://deliverydesk.test/pages/collective-note.html')
    expect(page.locator('.collection-status')).to_have_text('Rejected')
    expect(page.locator('.collection-reject-note')).to_be_disabled()
    button = page.locator('.collection-record-download').first
    box = button.bounding_box()
    page.mouse.move(box['x'] - 8, box['y'] + box['height'] / 2)
    page.mouse.move(box['x'] + 2, box['y'] + box['height'] / 2)
    origin = button.evaluate("el=>parseFloat(el.style.getPropertyValue('--download-x'))")
    assert 0 <= origin < 20, origin
    assert not errors, errors
    browser.close()
    print('PASS: dropdown geometry, status contrast, outside dismissal, stable reopening and download hover origin')
