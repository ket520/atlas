"""The selection column stays visible after animations and row refreshes."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='no-preference')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id': 'one', 'order': '663132'}, {'id': 'two', 'order': '654171'}
    ]}))
    page.route('**/api/collection-notes/*/status', lambda route: route.fulfill(json={
        'status': route.request.post_data_json['status']
    }))
    page.goto('https://deliverydesk.test/pages/collective-note.html')
    expect(page.locator('#collection-records > tr')).to_have_count(2)
    width = page.locator('thead th').first.bounding_box()['width']
    def check_alignment():
        assert page.evaluate("""() => {
          const header = document.querySelector('thead th:not(.collection-selection-cell)');
          const order = document.querySelector('.collection-order-cell .tracking-order-number');
          return Math.abs(header.getBoundingClientRect().left + parseFloat(getComputedStyle(header).paddingLeft) - order.getBoundingClientRect().left) < 1;
        }""")
    check_alignment()
    for attempt in range(2):
        page.locator('[data-collection-bulk-edit]').click()
        page.wait_for_function('!collectionBulkTransitioning')
        expect(page.locator('[data-collection-bulk-toolbar] > :last-child')).to_have_attribute('data-collection-bulk-edit', '')
        if attempt == 0:
            page.wait_for_timeout(3000)
        all_box = page.locator('[data-collection-bulk-all]')
        expect(all_box).to_be_visible()
        expect(page.locator('thead .collection-selection-cell')).to_have_text('')
        assert page.locator('thead .collection-selection-cell').bounding_box()['width'] <= 50
        check_alignment()
        assert abs(page.locator('thead th').nth(1).bounding_box()['width'] - width) < 1
        for checkbox in page.locator('[data-collection-bulk-note]').all():
            assert checkbox.evaluate("""el => {
              const rect = el.getBoundingClientRect();
              return document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2) === el;
            }""")
        all_box.check()
        expect(page.locator('[data-collection-bulk-count]')).to_have_text('2 selected')
        for status in ('Approved', 'Pending', 'Rejected'):
            page.locator(f'[data-collection-bulk-status="{status}"]').click()
            expect(page.locator('[data-collection-bulk-toolbar]')).not_to_have_attribute('aria-busy', 'true')
            expect(page.locator('[data-collection-bulk-count]')).to_have_text('2 selected')
            for checkbox in page.locator('[data-collection-bulk-note]').all():
                expect(checkbox).to_be_checked()
        page.evaluate('renderCollectionRecords()')
        expect(page.locator('td.collection-selection-cell')).to_have_count(2)
        for checkbox in page.locator('[data-collection-bulk-note]').all():
            expect(checkbox).to_be_checked()
        page.locator('[data-collection-bulk-edit]').click()
        page.wait_for_function('!collectionBulkTransitioning')
        expect(page.locator('.collection-selection-cell')).to_have_count(0)
        expect(page.locator('.collection-actions-heading > [data-collection-bulk-edit]')).to_be_visible()
    page.locator('[data-collection-bulk-edit]').click()
    page.wait_for_function('!collectionBulkTransitioning')
    page.locator('[data-collection-bulk-all]').check()
    expect(page.locator('[data-download-collection-record]').first).to_be_hidden()
    trash = page.locator('[data-delete-collection-record="one"]')
    expect(trash).to_be_visible()
    trash.click()
    page.get_by_role('dialog', name='Heads up').get_by_role('button', name='Cancel').click()
    expect(page.locator('[data-collection-bulk-count]')).to_have_text('2 selected')
    page.route('**/api/collection-notes/one', lambda route: route.fulfill(json={'deleted': True}))
    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id': 'two', 'order': '654171'}
    ]}))
    trash.click()
    page.get_by_role('dialog', name='Heads up').get_by_role('button', name='Delete note', exact=True).click()
    expect(page.locator('#collection-records > tr')).to_have_count(1)
    expect(page.locator('[data-collection-bulk-count]')).to_have_text('1 selected')
    expect(page.locator('[data-collection-bulk-note="two"]')).to_be_checked()
    expect(page.locator('[data-delete-collection-record="two"]')).to_be_visible()
    browser.close()
    print('PASS: checkbox-only header, persistent selection column, unchanged Order ID width and refresh/reopen selection')
