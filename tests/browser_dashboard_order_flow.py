"""The 1x1 family tracker uses system utility styling and renders only its graph."""
from urllib.parse import parse_qs, urlparse
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='reduce')
    page.set_default_timeout(8000)
    errors, calls = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      localStorage.setItem('deliverydesk-widget-tour-v1','seen');
      localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['order-flow-tracker','order-identifier','collection-generator']));""")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    flow = {'nodes': [
        {'id':'648637','st':'Delivered','carrier':'Palletways','canOpenDetails':True},
        {'id':'654171','st':'Scheduled','carrier':'Palletways','canOpenDetails':True},
        {'id':'659494','st':'Failed','carrier':'Palletways','canOpenDetails':True},
        {'id':'700000','st':'','category':'credit/refund','canOpenDetails':False}],
        'edges':[
        {'from':'648637','to':'654171','kind':'Replacement'},
        {'from':'654171','to':'659494','kind':'Replacement'},
        {'from':'654171','to':'700000','kind':'Credit/Refund'}]}
    def respond(route):
        order=parse_qs(urlparse(route.request.url).query)['order'][0]
        calls.append(order)
        if order=='888888':
            route.fulfill(status=503,json={'error':'Lookup unavailable. Try again.'})
            return
        found=order!='999999'
        graph=flow if order in ('648637','654171','659494') else {'nodes':[],'edges':[]}
        if order == '777777':
            graph = {'nodes': flow['nodes'][:3], 'edges': flow['edges'][:2]}
        route.fulfill(json={'found':found,'order':order,'flow':graph})
    page.route('**/api/order-flow?*', respond)
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    widget=page.locator('[data-dash-widget="order-flow-tracker"]')
    expect(widget).to_be_visible()
    expect(widget.locator('h3')).to_have_text('Replacement / Credit Refund Tracker')
    assert 'dash-widget-tall' not in widget.get_attribute('class')
    assert widget.evaluate("el=>getComputedStyle(el).getPropertyValue('--tone').trim()") == page.locator('[data-dash-widget="order-identifier"]').evaluate("el=>getComputedStyle(el).getPropertyValue('--tone').trim()")
    field=widget.locator('[data-utility-order]')
    generator_input = page.locator('[data-dash-widget="collection-generator"] [data-utility-order]')
    assert abs(field.bounding_box()['height'] - generator_input.bounding_box()['height']) < 1
    assert abs(field.bounding_box()['width'] - generator_input.bounding_box()['width']) < 1
    for order in ('659494','648637','654171'):
        field.fill(order)
        field.press('Enter')
        expect(widget.locator('.order-flow-node')).to_have_count(4)
        expect(widget.locator('.is-searched')).to_have_attribute('data-flow-order',order)
        expect(widget.locator('.order-flow-edge')).to_have_count(3)
        expect(widget.locator('.dash-identifier-ids')).to_have_count(0)
        expect(widget.locator('.dash-utility-guide')).to_be_hidden()
        expect(widget.locator('[data-flow-order="700000"] .order-flow-status tspan')).to_have_text('Credit/Refund')
        assert widget.locator('.order-flow-edge path').first.get_attribute('marker-end') == 'url(#utility-flow-arrow-order-flow-tracker)'
        scroller=widget.locator('.order-flow-scroll')
        assert scroller.evaluate('el=>el.scrollHeight<=el.clientHeight+1')
        assert scroller.evaluate('el=>el.scrollWidth>el.clientWidth+1')
        expect(scroller).to_have_css('overflow-y','hidden')
        expect(scroller).to_have_css('background-color','rgba(0, 0, 0, 0)')
        for node_id, node_type in [('648637','Order'),('654171','Replacement'),('659494','Replacement'),('700000','Credit/Refund')]:
            expect(widget.locator(f'[data-flow-order="{node_id}"] .order-flow-node-label')).to_have_text(node_type)
        for node in widget.locator('.order-flow-node').all():
            assert node.evaluate("el=>{const bounds=el.getBoundingClientRect(),area=el.closest('.order-flow-scroll').getBoundingClientRect();return bounds.top>=area.top-1&&bounds.bottom<=area.bottom+1;}")
        assert widget.locator('.dash-utility-form').evaluate('el=>el.scrollHeight<=el.clientHeight+1')
    field.fill('777777');field.press('Enter')
    expect(widget.locator('.order-flow-node')).to_have_count(3)
    for width, height in [(1920,1080), (1440,900), (1280,720)]:
        page.set_viewport_size({'width':width,'height':height})
        assert widget.locator('.order-flow-scroll').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
    page.set_viewport_size({'width':1440,'height':900})
    field.fill('654171');field.press('Enter')
    expect(widget.locator('.order-flow-node')).to_have_count(4)
    page.emulate_media(reduced_motion='no-preference')
    rect=widget.locator('.order-flow-node.is-searched rect')
    expect(rect).to_have_css('animation-name','utility-order-flow-searched-pulse')
    assert rect.evaluate("""el=>{const animation=el.getAnimations()[0];animation.pause();animation.currentTime=1800;return getComputedStyle(el).fill;}""") == 'rgba(0, 0, 0, 0)'
    page.emulate_media(reduced_motion='reduce')
    from pathlib import Path
    Path('.test-temp').mkdir(exist_ok=True)
    widget.screenshot(path='.test-temp/order-flow-widget-compact.png')
    field.fill('123456');field.press('Enter')
    expect(widget.locator('.dash-utility-result')).to_contain_text('No replacement or credit/refund links found')
    field.fill('999999');field.press('Enter')
    expect(widget.locator('.dash-utility-result')).to_contain_text('Order not found')
    count=len(calls)
    field.fill('ABC');field.press('Enter')
    expect(widget.locator('.dash-utility-result')).to_contain_text('Enter a numeric order ID')
    assert len(calls)==count
    field.fill('888888');field.press('Enter')
    expect(widget.locator('.dash-utility-result')).to_contain_text('Lookup unavailable')
    page.locator('[data-dash-customize]').click()
    page.locator('[data-picker-remove="order-flow-tracker"]').click()
    page.locator('[data-picker-filter="1x1"]').click()
    for _ in range(5):
        if page.locator('[data-picker-key="order-flow-tracker"][data-picker-size="1x1"]').count():
            break
        next_page=page.locator('[data-picker-page="1"]')
        if next_page.is_disabled():
            break
        next_page.click()
    expect(page.locator('[data-picker-key="order-flow-tracker"][data-picker-size="1x1"]')).to_have_count(1)
    expect(page.locator('[data-picker-key="order-flow-tracker"][data-picker-size="1x3"]')).to_have_count(0)
    assert not errors, errors
    browser.close()
    print('PASS: 1x1 utility styling, graph-only results, any-chain search, statuses, marker IDs, empty/invalid/error handling, and picker availability.')
