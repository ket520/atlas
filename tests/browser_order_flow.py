"""A stable complete order map highlights only the searched order."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    positions = None
    for searched in ['648637', '654171', '659494']:
        page.evaluate("""searched => {
          const ids=['648637','654171','659494'];
          const records=ids.map((id,index)=>({id,order:id,carrier:'Palletways',st:['Delivered','Scheduled','Failed'][index],cust:'Customer',logs:[]}));
          DeliveryStore.hydrate({deliveries:records,activity:[],integrations:[]});D=DeliveryStore.deliveries();
          trackingRelations={order:searched,original:records.find(row=>row.id===searched),
            related:records.filter(row=>row.id!==searched).map(row=>({...row,relatedKind:'Replacement',canOpenDetails:true})),
            flow:{nodes:records.map(({id,st,carrier})=>({id,st,carrier})),edges:[
              {from:'648637',to:'654171',kind:'Replacement'},
              {from:'654171',to:'659494',kind:'Replacement'}]}};
          fsrc='Palletways';q=searched;R();rows();
        }""", searched)
        flow = page.locator('#tracking-order-flow')
        expect(flow).to_be_visible()
        expect(flow.locator('.order-flow-node')).to_have_count(3)
        expect(flow.locator('.order-flow-edge')).to_have_count(2)
        for node_id, node_type in [('648637','Order'),('654171','Replacement'),('659494','Replacement')]:
            expect(flow.locator(f'[data-flow-order="{node_id}"] .order-flow-node-label')).to_have_text(node_type)

        for order, status in [('648637', 'Delivered'), ('654171', 'Scheduled'), ('659494', 'Failed')]:
            node = flow.locator(f'[data-flow-order="{order}"]')
            expect(node.locator('.order-flow-status tspan').first).to_have_text(status)
            assert node.locator('.order-flow-status').evaluate("el=>Number(el.getAttribute('y')) > Number(el.parentElement.querySelector('rect').getAttribute('y')) + 62")

        expect(flow.locator('.is-searched')).to_have_count(1)
        expect(flow.locator('.is-searched')).to_have_attribute('data-flow-order', searched)
        assert flow.locator('.is-searched rect').evaluate('el=>getComputedStyle(el).fill') == 'rgb(201, 242, 216)'
        searched_row = page.locator('#tb > tr.tracking-searched-row')
        expect(searched_row).to_have_count(1)
        expect(searched_row).to_have_attribute('data-delivery-id', searched)
        expected_type = 'Order' if searched == '648637' else 'Replacement'
        expect(searched_row.locator('.tracking-order-type')).to_have_text(expected_type)

        page.mouse.move(0, 0)
        assert searched_row.locator('td').first.evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgb(201, 242, 216)'
        for row in page.locator('#tb > tr.tracking-related-row:not(.tracking-searched-row)').all():
            assert row.locator('td').first.evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgb(237, 243, 255)'
        searched_row.hover()
        assert searched_row.locator('td').first.evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgb(201, 242, 216)'
        searched_row.evaluate("el=>el.classList.add('is-selected')")
        assert searched_row.locator('td').first.evaluate('el=>getComputedStyle(el).backgroundColor') == 'rgb(201, 242, 216)'
        current = flow.locator('.order-flow-node').evaluate_all("nodes=>nodes.map(node=>[node.dataset.flowOrder,node.querySelector('rect').getAttribute('x'),node.querySelector('rect').getAttribute('y')])")
        if positions is not None:
            assert current == positions
        positions = current
        assert flow.evaluate("el=>Boolean(document.querySelector('.tracking-table-wrap').compareDocumentPosition(el)&Node.DOCUMENT_POSITION_FOLLOWING)")
    # Use the real row-opening function and assert the actual shared drawer.
    for order, action in [('654171', 'click'), ('648637', 'Enter'), ('659494', 'Space')]:
        node = page.locator(f'.order-flow-node[data-flow-order="{order}"]')
        expect(node).to_have_attribute('role', 'button')
        expect(node).to_have_attribute('tabindex', '0')
        if action == 'click':
            node.locator('rect').click()
        else:
            node.focus()
            node.press(action)
        page.wait_for_function('order => sel === order', arg=order)
        expect(page.locator('#dr .dr')).to_be_visible()
        assert node.evaluate('el=>getComputedStyle(el).outlineStyle') == 'none'
        expect(page.locator('#dr .dr')).to_contain_text(order)
        page.keyboard.press('Escape')
        page.wait_for_function('sel === null')
    # A source-only credit retains the same unavailable-details behavior as its row.
    page.evaluate("""() => {
      const node=trackingRelations.flow.nodes.find(node=>node.id==='648637');
      node.canOpenDetails=false;rows();
    }""")
    expect(page.locator('[data-flow-order="648637"]')).to_have_attribute('role', 'group')
    assert page.locator('[data-flow-order="648637"]').get_attribute('data-flow-open') is None
    page.emulate_media(reduced_motion='no-preference')
    selected_rect = page.locator('.order-flow-node.is-searched rect')
    expect(selected_rect).to_have_css('animation-name', 'order-flow-searched-pulse')
    expect(selected_rect).to_have_css('animation-iteration-count', 'infinite')
    colors = selected_rect.evaluate("""el => {
      const animation=el.getAnimations()[0];animation.pause();animation.currentTime=0;
      const start=getComputedStyle(el).fill;
      animation.currentTime=1800;const faded=getComputedStyle(el).fill;
      return [start,faded];
    }""")
    assert colors == ['rgb(201, 242, 216)', 'rgb(255, 255, 255)'], colors
    expect(page.locator('.order-flow-node:not(.is-searched) rect').first).to_have_css('animation-name', 'none')
    page.emulate_media(reduced_motion='reduce')
    expect(selected_rect).to_have_css('animation-name', 'none')
    expect(selected_rect).to_have_css('fill', 'rgb(201, 242, 216)')
    page.set_viewport_size({'width': 390, 'height': 844})
    page.locator('#tracking-order-flow').scroll_into_view_if_needed()
    expect(page.locator('#tracking-order-flow')).to_be_visible()
    assert page.locator('.order-flow-scroll').evaluate('el=>el.scrollWidth>el.clientWidth')
    page.locator('[data-delivery-search]').fill('no match')
    expect(page.locator('#tracking-order-flow')).to_be_hidden()
    expect(page.locator('#tb > tr.tracking-searched-row')).to_have_count(0)

    page.evaluate("""() => {
      const credit={id:'700001',order:'700001',carrier:'',st:'',cust:'Credit',canOpenDetails:false};
      trackingRelations={order:'700001',original:credit,related:[{id:'654171',order:'654171',carrier:'Palletways',st:'Scheduled',relatedKind:'Original',canOpenDetails:true}],
        flow:{nodes:[{id:'654171'},{id:'700001',category:'credit/refund',canOpenDetails:false}],edges:[{from:'654171',to:'700001',kind:'Credit/Refund'}]}};
      q='700001';R();rows();
    }""")
    expect(page.locator('#tb > tr').first.locator('.tracking-order-type')).to_have_text('Credit/Refund')
    page.evaluate("""() => {
      trackingRelations=null;q='659494';R();rows();
    }""")
    expect(page.locator('.tracking-order-type')).to_have_count(0)
    assert not errors, errors
    browser.close()
    print('PASS: same map for first/middle/last search, directed links, green highlight, map below table, mobile scroll, and cleared searches.')
