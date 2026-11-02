from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    for width in [1440, 390]:
        page = browser.new_page(viewport={'width': width, 'height': 900}, reduced_motion='reduce')
        page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
        page.route('https://deliverydesk.test/**', serve)
        page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
        page.goto('https://deliverydesk.test/pages/deliveries.html')
        page.wait_for_function("typeof R === 'function'")
        page.evaluate('''() => {
          DeliveryStore.hydrate({deliveries:[
            {id:'action-amz', order:'650001', carrier:'AMZ', st:'Scheduled', collectionNoteId:'saved-note', logs:[]},
            {id:'action-van', order:'650002', carrier:'Own van', st:'Scheduled', logs:[]}
          ],activity:[],integrations:[]}); D=DeliveryStore.deliveries();R();op('action-amz');
        }''')
        panel = page.locator('.qd-tracking-view')
        expect(panel.locator('.qd-section-tab')).to_have_count(4)
        expect(panel.locator('.qd-section-tab').last).to_have_text('Action')
        expect(panel.locator('.qd-action-section')).to_be_hidden()
        expect(panel.locator('.qd-purchase-block .qd-note-actions')).to_have_count(0)
        expect(panel.locator('.qd-badges .qd-amazon-claim-button')).to_have_count(0)
        panel.locator('[data-qd-tab="action"]').click()
        actions = panel.get_by_role('region', name='Order actions')
        expect(actions).to_be_visible()
        expect(actions.locator('.qd-action-button')).to_have_count(4)
        expect(actions.locator('h3')).to_have_count(0)
        expect(actions.get_by_role('button', name='Generate Manufacture Claims', exact=True)).to_be_disabled()
        cards = actions.locator('.qd-action-button').evaluate_all('els=>els.map(el=>el.getBoundingClientRect().toJSON())')
        assert cards[1]['x'] > cards[0]['x'] and abs(cards[1]['y'] - cards[0]['y']) < 1
        assert cards[2]['y'] > cards[0]['y']
        assert all(card['width'] > 0 for card in cards)
        expect(actions.get_by_role('link', name='Generate collection note for order 650001')).to_have_attribute('href', './collective-note.html?order=650001')
        expect(actions.get_by_role('link', name='View collection note for order 650001')).to_have_attribute('href', './collective-note.html?view=create&record=saved-note')
        expect(actions.get_by_role('button', name='File Claim', exact=True)).to_be_disabled()
        expect(actions.locator('.qd-action-claim')).to_contain_text('COMING SOON')
        expect(actions.locator('.qd-action-claim')).to_have_css('filter', 'grayscale(1)')
        expect(actions.locator('.qd-action-manufacture')).to_have_css('filter', 'grayscale(1)')
        expect(panel.locator('.qd-amazon-claim-panel')).to_have_count(0)
        panel.locator('[data-qd-tab="details"]').click()
        expect(actions).to_be_hidden()
        panel.locator('[data-qd-tab="action"]').click()
        expect(actions).to_be_visible()
        page.evaluate("op('action-van')")
        panel.locator('[data-qd-tab="action"]').click()
        expect(panel.get_by_role('button', name='View Collection Note', exact=True)).to_be_disabled()
        expect(panel.locator('.qd-action-view')).to_have_css('filter', 'grayscale(1)')
        expect(panel.locator('.qd-amazon-claim-button')).to_have_count(0)
        bounds = panel.locator('.qd-section-tabs').evaluate('''el => {
          const box=el.getBoundingClientRect();
          return [...el.children].every(tab=>tab.getBoundingClientRect().right<=box.right+1);
        }''')
        assert bounds
        page.close()
    browser.close()
    print('PASS: action cards, saved-note links, disabled greyscale coming-soon/missing-note cards and mobile layout')
