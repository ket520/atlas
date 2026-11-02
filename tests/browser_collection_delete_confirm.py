from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/collective-note.html?view=create')
    page.locator('.cn-paper input[name="order"]').wait_for()
    paper = page.locator('.cn-paper').evaluate('''el => {
      el.querySelector('[name="order"]').setAttribute('value', '663132');
      return el.innerHTML;
    }''')
    deleted = []
    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id': 'saved', 'order': '663132', 'orderRef': 'REF-123'}
    ]}))
    def record(route):
        if route.request.method == 'DELETE':
            deleted.append(route.request.url)
            route.fulfill(json={'deleted': True})
        else:
            route.fulfill(json={'id': 'saved', 'paper': paper})
    page.route('**/api/collection-notes/saved', record)
    for path, selector in [('collective-note.html', '[data-delete-collection-record]'),
                           ('collective-note.html?view=create&record=saved', '[data-collection-delete]')]:
        page.goto('https://deliverydesk.test/pages/' + path)
        button = page.locator(selector)
        expect(button).to_be_enabled()
        before = len(deleted)
        button.click()
        dialog = page.get_by_role('dialog', name='Heads up')
        expect(dialog).to_contain_text('663132')
        expect(dialog).to_contain_text("can't be undone")
        expect(dialog.get_by_role('button', name='Cancel')).to_be_focused()
        dialog.get_by_role('button', name='Cancel').click()
        expect(dialog).to_have_count(0)
        assert len(deleted) == before
        button.click()
        page.keyboard.press('Escape')
        expect(dialog).to_have_count(0)
        assert len(deleted) == before
        button.click()
        with page.expect_response(lambda response: response.request.method == 'DELETE'):
            dialog.get_by_role('button', name='Delete note', exact=True).click()
        assert len(deleted) == before + 1
    browser.close()
    print('PASS: records/editor confirmation identifies order; Cancel and Escape preserve note; Delete sends one request')
