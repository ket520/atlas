"""Check store labels, filtering, responsive layout and Guidance with local fixtures."""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.get_by_role('button', name='Filter by store', exact=True).wait_for()
    page.evaluate('''() => {
      TrackingVisibility.setEnabled(false);
      TrackingVisibility.setWayfairEnabled(false);
      DeliveryStore.hydrate({deliveries: ['AMAZON','SHOPIFY','WILKO','WAYFAIR'].map((storeCode,i) =>
        ({id:String(i+1), order:String(i+1), storeCode, carrier:'XDP', st:'Scheduled', cust:'Customer',
          date:'2026-10-22', salesActivityDetails:{'Order Type':'Old value'},logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries(); R();
    }''')
    assert page.locator('#tb tr[data-delivery-id]').count() == 4
    for order_type, analysis, image in [('Amazon','','AmaNes.png'), ('B&Q','','BQNes.png'),
        ('Debenhams','Debenhams - Neshome','DeNeshome.png'), ('Ebay','ebay0','EbayBR.png'),
        ('Ebay','ebay1','ebayW.png'), ('Shopify','Shopify - Neshome','ShpfyNes.png'),
        ('Shopify','Bathroom Republic - Website','ShpfyBR.png'), ('Sales','','Hyg.png')]:
        assert page.evaluate('''([orderType,analysis,image]) => purchaseStoreLogo({salesActivityDetails:
          {'Order Type':orderType,'Order Analysis':analysis}}).includes(image)''', [order_type,analysis,image])
    for name, code, image in [('Amazon','AMAZON','AmaNes.png'), ('Wayfair','WAYFAIR','wayfair.jpg'), ('Wilko','WILKO','wilko.png'),
        ('EBay Willesden Bathroom','EBAY_WB','ebayW.png'), ('Ebay Bathroom Republic','EBAY_BR','EbayBR.png')]:
        result = page.evaluate('''([code]) => {
          const delivery={storeCode:code};
          return [purchaseChannel(delivery),purchaseStoreLogo(delivery)];
        }''', [code])
        assert result[0] == name, result
        assert image in result[1] if image else result[1] == '', result
        assert page.evaluate('''filename => new Promise(resolve => {
          const img = new Image();
          img.onload = () => resolve(img.naturalWidth > 0);
          img.onerror = () => resolve(false);
          img.src = '/assets/' + filename;
        })''', image), f'Cannot load store image: {image}'
    page.get_by_role('button', name='Filter by store', exact=True).click()
    page.get_by_role('menuitemcheckbox', name='Wilko', exact=True).click()
    assert page.locator('#tb tr[data-delivery-id]').count() == 1
    assert page.locator('#tb tr[data-delivery-id]').get_attribute('data-delivery-id') == '3'
    for width in [375, 760, 1024, 1440, 1920]:
        page.set_viewport_size({'width': width, 'height': 900})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
        if width >= 1440:
            store = page.get_by_role('button', name='Filter by store', exact=True).bounding_box()
            status = page.get_by_role('button', name='Filter by status', exact=True).bounding_box()
            assert store['x'] < status['x'] and abs(store['y'] - status['y']) < 2, (store, status)
    page.get_by_role('button', name='Clear filters', exact=True).click()
    assert page.locator('#tb tr[data-delivery-id]').count() == 4
    page.evaluate("go('Guidance')")
    captions = page.locator('.guidance-table caption').all_text_contents()
    assert captions[-2:] == ['Stores', 'Data switches'], captions
    assert 'BATHPROF' in page.locator('.guidance-table').filter(has=page.locator('caption', has_text='Stores')).inner_text()
    page.evaluate("go('Settings')")
    assert page.locator('[data-settings-company="wilko"]').is_enabled()
    assert not page.locator('[data-settings-company="wilko"]').is_checked()
    page.locator('[data-settings-company="wilko"]').check()
    page.evaluate("go('Deliveries')")
    assert page.locator('#tb tr[data-delivery-id]').count() == 3
    page.evaluate('''() => {
      TrackingVisibility.setWilkoEnabled(false);
      fstore=''; fsrc=''; fs=''; trackingScope='';
      DeliveryStore.hydrate({deliveries:[['AMAZON','AMZ'],['EBAY_WB','AMZ'],['WILKO','XDP'],['WAYFAIR','Own van']]
        .map(([storeCode,carrier],i)=>({id:String(i+1),order:String(i+1),storeCode,carrier,st:'Scheduled',
          cust:'Customer',date:'2026-10-22',salesActivityDetails:{},logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries(); R();
    }''')
    page.locator('[data-delivery-filter-action="method"][data-value="AMZ"]').click()
    options = page.locator('[data-ui-select-id="dstoreValue"] [data-ui-select-option]').all_text_contents()
    assert [value.strip() for value in options] == ['All stores', 'Amazon', 'EBay Willesden Bathroom'], options
    page.get_by_role('button', name='Filter by store', exact=True).click()
    page.get_by_role('menuitemcheckbox', name='Amazon', exact=True).click()
    # Parent delivery methods remain available when a child store is selected.
    page.locator('[data-delivery-filter-action="method"][data-value="XDP"]').click()
    assert page.locator('#dstoreValue').input_value() == ''
    options = page.locator('[data-ui-select-id="dstoreValue"] [data-ui-select-option]').all_text_contents()
    assert [value.strip() for value in options] == ['All stores', 'Wilko'], options
    assert page.locator('#tb tr[data-delivery-id]').count() == 1
    assert page.locator('#tb tr[data-delivery-id]').get_attribute('data-delivery-id') == '3'
    page.evaluate('''() => {
      fsrc=''; fstore='Wilko';
      TrackingVisibility.setEnabled(false); TrackingVisibility.setWayfairEnabled(false);
      DeliveryStore.hydrate({deliveries:[['WILKO','eBay'],['WAYFAIR','eBay'],['AMAZON','HR_Replacement'],['AMAZON','Amazon']]
        .map(([storeCode,orderType],i)=>({id:String(i+1),order:String(i+1),storeCode,carrier:'AMZ',st:'Scheduled',
          cust:'Customer',date:'2026-10-22',salesActivityDetails:{'Order Type':orderType},logs:[]})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries(); go('Settings');
    }''')
    for company in ['wilko', 'wayfair', 'hygienic']:
        page.locator(f'[data-settings-company="{company}"]').check()
    page.evaluate("go('Deliveries')")
    assert page.locator('#dstoreValue').input_value() == ''
    options = page.locator('[data-ui-select-id="dstoreValue"] [data-ui-select-option]').all_text_contents()
    assert [value.strip() for value in options] == ['All stores', 'Amazon'], options
    assert page.locator('#tb tr[data-delivery-id]').count() == 1
    page.evaluate("go('Settings')")
    for company in ['wilko', 'wayfair', 'hygienic']:
        page.locator(f'[data-settings-company="{company}"]').uncheck()
    page.evaluate("go('Deliveries')")
    options = page.locator('[data-ui-select-id="dstoreValue"] [data-ui-select-option]').all_text_contents()
    assert {value.strip() for value in options} == {'All stores', 'Amazon', 'Wilko', 'Wayfair', 'Hygienic Cleaning Company (UK) LTD'}, options
    assert page.locator('#tb tr[data-delivery-id]').count() == 4
    assert not errors, errors
    page.evaluate('''() => {
      fsrc=''; fstore=''; fs=''; trackingScope='';
      DeliveryStore.hydrate({deliveries:[['B2B','WILKO','Palletways'],['B2C','AMAZON','Palletways'],
        ['','WAYFAIR','Palletways'],['B2B','SHOPIFY','XDP']].map(([classification,storeCode,carrier],i)=>
          ({id:String(i+1),order:String(i+1),storeCode,carrier,st:'Scheduled',cust:'Customer',logs:[],
            palletwaysDetails:{classification},salesActivityDetails:{}})),activity:[],integrations:[]});
      D=DeliveryStore.deliveries(); go('Settings');
    }''')
    page.locator('[data-settings-company="palletways-b2b"]').check()
    page.evaluate("go('Deliveries')")
    assert page.locator('#tb tr[data-delivery-id]').count() == 3
    assert page.locator('#tb tr[data-delivery-id="1"]').count() == 0
    assert page.evaluate("availableTrackingStores().includes('Wilko')") is False
    assert page.evaluate("localStorage.getItem('delivery-desk-hide-palletways-b2b')") == 'true'
    page.evaluate("go('Settings')")
    assert page.locator('[data-settings-company="palletways-b2b"]').is_checked()
    page.locator('[data-settings-company="palletways-b2b"]').uncheck()
    page.evaluate("go('Deliveries')")
    assert page.locator('#tb tr[data-delivery-id]').count() == 4
    assert not errors, errors
    browser.close()
    print('Store labels, logos, filtering, 5 viewport widths, Guidance order and Wilko setting passed.')
