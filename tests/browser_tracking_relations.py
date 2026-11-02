"""Exact-order search shows linked source records below the original, only in Tracking."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate('''() => {
      const original = {id:'663132', order:'663132', carrier:'Palletways', st:'Scheduled', storeCode:'AMAZON', cust:'Original customer', logs:[]};
      const replacement = {id:'700001', order:'700001', carrier:'Own van', st:'Scheduled', storeCode:'AMAZON', cust:'Replacement customer', skuItems:'SKU-1', relatedKind:'Replacement', originalOrder:'663132', canOpenDetails:true, logs:[]};
      const credit = {id:'700002', order:'700002', carrier:'', st:'', cust:'Credit customer', relatedKind:'Credit/Refund', originalOrder:'663132', grossAmount:'25.00', rawStatus:'W', canOpenDetails:false};
      DeliveryStore.hydrate({deliveries:[replacement,original],activity:[],integrations:[]});D=DeliveryStore.deliveries();
      trackingRelations={order:'663132', original, related:[replacement,credit]};fsrc='Palletways';R();
    }''')
    page.locator('[data-delivery-search]').fill('663132')
    expect(page.locator('#tb > tr').first).to_have_attribute('data-delivery-id', '663132')
    expect(page.locator('#tb > tr').nth(1)).to_have_class('tracking-related-heading')
    expect(page.locator('.tracking-related-row')).to_have_count(2)
    expect(page.locator('.tracking-related-heading').first).to_contain_text('Replacement Order Found')
    expect(page.locator('.tracking-related-heading').last).to_contain_text('Credit/Refund Found')
    expect(page.locator('.tracking-related-row td:first-child small')).to_have_count(0)
    colors = page.locator('.tracking-related-row').evaluate_all('rows => rows.map(row => getComputedStyle(row.cells[0]).backgroundColor)')
    assert colors == ['rgb(237, 243, 255)', 'rgb(255, 244, 220)'], colors
    for carrier in ['', 'Palletways', 'AMZ', 'XDP', 'Stopstart']:
        page.evaluate('(carrier) => { fsrc=carrier; R(); }', carrier)
        headers = page.locator('.current-table thead th').count()
        for row in page.locator('.tracking-related-row').all():
            assert row.locator(':scope > td').count() == headers
            assert row.evaluate('''el => {
              const headers=[...document.querySelectorAll('.current-table thead th')];
              return [...el.children].every((cell,i)=>Math.abs(cell.getBoundingClientRect().x-headers[i].getBoundingClientRect().x)<1);
            }''')
    assert page.locator('.tracking-related-row').last.get_attribute('data-delivery-id') is None
    page.evaluate('window.opened=null;op=(id)=>window.opened=id')
    page.locator('.tracking-related-row').first.click()
    assert page.evaluate('window.opened') == '700001'
    page.evaluate('window.forwardRelations=trackingRelations')
    for order in ['700001', '700002']:
        page.evaluate('''order => {
          const searched=forwardRelations.related.find(item=>item.order===order);
          trackingRelations={order, original:searched,
            related:[{...forwardRelations.original, relatedKind:'Original', canOpenDetails:true}]};
        }''', order)
        page.locator('[data-delivery-search]').fill(order)
        expect(page.locator('#tb > tr').first.locator('td').first).to_contain_text(order)
        expect(page.locator('.tracking-related-heading')).to_contain_text('Original ID Found')
        expect(page.locator('[data-related-kind="Original"][data-delivery-id="663132"]')).to_have_count(1)
        if order == '700002':
            assert page.locator('#tb > tr').first.get_attribute('data-delivery-id') is None
    page.evaluate('trackingRelations=forwardRelations')
    page.locator('[data-delivery-search]').fill('66313')
    expect(page.locator('.tracking-related-heading')).to_have_count(0)
    page.locator('[data-delivery-search]').fill('')
    expect(page.locator('.tracking-related-row')).to_have_count(0)
    page.evaluate('''() => {
      const searched={id:'659494',order:'659494',carrier:'Palletways',st:'Scheduled',cust:'Current',logs:[]};
      trackingRelations={order:'659494',original:searched,related:[
        {...searched,id:'654171',order:'654171',relatedKind:'Original',linkedToOrder:'659494',ancestorDepth:1,canOpenDetails:true},
        {...searched,id:'648637',order:'648637',relatedKind:'Earlier Original',linkedToOrder:'654171',ancestorDepth:2,canOpenDetails:true}
      ]};fsrc='Palletways';R();
    }''')
    page.locator('[data-delivery-search]').fill('659494')
    expect(page.locator('.tracking-related-heading')).to_have_count(2)
    expect(page.locator('.tracking-related-heading').first).to_contain_text('Original ID Found')
    expect(page.locator('.tracking-related-heading').first.locator('small')).to_have_text('Original order of 659494')
    expect(page.locator('.tracking-related-heading').last).to_contain_text('2nd Original ID Found')
    expect(page.locator('.tracking-related-heading').last.locator('small')).to_have_text('Original order of 654171')
    expect(page.locator('[data-related-kind="Earlier Original"][data-delivery-id="648637"]')).to_have_count(1)
    page.evaluate('''() => {
      const searched={id:'648637',order:'648637',carrier:'Palletways',st:'Scheduled',cust:'Current',logs:[]};
      const ids=['654171','659494','700001','700002'];
      trackingRelations={order:'648637',original:searched,related:ids.map((id,index)=>({
        ...searched,id,order:id,relatedKind:index?'Later Replacement':'Replacement',
        linkedToOrder:index?ids[index-1]:'648637',replacementDepth:index+1,canOpenDetails:true
      }))};R();
    }''')
    page.locator('[data-delivery-search]').fill('648637')
    expect(page.locator('.tracking-related-heading')).to_have_count(4)
    for index, label in enumerate(['Replacement Order Found','2nd Replacement Order Found','3rd Replacement Order Found','4th Replacement Order Found']):
        expect(page.locator('.tracking-related-heading').nth(index)).to_contain_text(label)
    expect(page.locator('.tracking-related-heading').nth(1).locator('small')).to_have_text('Replacement for order 654171')
    expect(page.locator('.tracking-related-heading').nth(2).locator('small')).to_have_text('Replacement for order 659494')
    page.evaluate('''() => {
      const searched={id:'700002',order:'700002',carrier:'Palletways',st:'Scheduled',cust:'Current',logs:[]};
      const ids=['700001','659494','654171','648637'];
      trackingRelations={order:'700002',original:searched,related:ids.map((id,index)=>({
        ...searched,id,order:id,relatedKind:index?'Earlier Original':'Original',
        linkedToOrder:index?ids[index-1]:'700002',ancestorDepth:index+1,canOpenDetails:true
      }))};R();
    }''')
    page.locator('[data-delivery-search]').fill('700002')
    for index, label in enumerate(['Original ID Found','2nd Original ID Found','3rd Original ID Found','4th Original ID Found']):
        expect(page.locator('.tracking-related-heading').nth(index)).to_contain_text(label)
    browser.close()
    print('PASS: forward/reverse order links, column alignment, type colours/headings, details, credits without courier and exact-search-only display')
