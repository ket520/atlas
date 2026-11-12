from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


def product_lookup(route):
    sku = parse_qs(urlsplit(route.request.url).query)['sku'][0]
    target = {
        'FOUND': 'https://neshome.co.uk/products/verified-product',
        'SEARCH': 'https://neshome.co.uk/search?q=SEARCH',
        'WRONG-STORE': 'https://other.test/products/item',
    }.get(sku)
    route.fulfill(json={'url': target})


with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    for width in (1440, 390):
        page = browser.new_page(viewport={'width': width, 'height': 1000}, reduced_motion='reduce')
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('https://deliverydesk.test/**', serve)
        page.route('**/api/**', lambda route: route.fulfill(json={'available': False}))
        page.route('**/api/product-link?**', product_lookup)
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function('typeof R === "function"')
        page.evaluate('''() => {
          const record={id:'fixture',order:'fixture',storeCode:'SHOPIFY',carrier:'XDP',
            st:'Scheduled',rawStatus:'Open',cust:'Fixture',logs:[],items:[
              {sku:'FOUND',quantity:'1.0000'}, {sku:'MISSING',quantity:'2.5000'},
              {sku:'SEARCH',quantity:'0.0000'}, {sku:'WRONG-STORE'}
            ]};
          TrackingVisibility.setEnabled(false);TrackingVisibility.setWayfairEnabled(false);
          DeliveryStore.hydrate({deliveries:[record],activity:[],integrations:[]});
          D=DeliveryStore.deliveries();R();op(record.id);
        }''')
        table = page.locator('.qd-purchase-items')
        table.locator('a').wait_for()
        assert table.locator('a').count() == 1
        assert table.locator('a').inner_text() == 'FOUND'
        assert table.locator('a').get_attribute('target') == '_blank'
        assert table.locator('tbody tr td:last-child').all_inner_texts() == ['1', '2.5', '0', '—']
        assert page.evaluate("itemQuantityLabel('100')") == '100'
        assert page.evaluate("verifiedProductUrl('not a URL', 'Amazon')") == ''
        assert page.locator('.qd-purchase-block').evaluate('''element => {
          const bounds=element.getBoundingClientRect();
          return [...element.querySelectorAll('th:last-child,td:last-child')].every(cell => {
            const rect=cell.getBoundingClientRect();
            return rect.right<=bounds.right+1 && rect.right<=innerWidth;
          });
        }''')
        assert not errors, errors
        print('SKU quantity and verified-only links checked:', width)
        page.close()
    browser.close()
