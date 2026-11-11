"""Bulk print groups selected saved notes into one print document."""
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
    page.route('**/api/collection-notes', lambda route: route.fulfill(json={'records': [
        {'id': 'one', 'order': '663132'}, {'id': 'two', 'order': '654171'}
    ]}))
    for note_id in ('one', 'two'):
        page.route('**/api/collection-notes/' + note_id, lambda route, request, note_id=note_id: route.fulfill(json={
            'id': note_id,
            'paper': '<table class="cn-sheet"><tbody><tr><td><input name="customer" value="Customer ' + note_id + '"></td></tr></tbody></table>'
                     '<script>parent.unwantedScript = true</script>'
        }))
    page.goto('https://deliverydesk.test/pages/collective-note.html')
    expect(page.locator('#collection-records > tr')).to_have_count(2)
    page.locator('[data-collection-bulk-edit]').click()
    toolbar = page.locator('[data-collection-bulk-toolbar]')
    expect(toolbar.locator('.collection-bulk-file-actions > button')).to_have_count(3)
    expect(toolbar.locator('.collection-bulk-delete-actions > button')).to_have_count(1)
    print_button = toolbar.locator('[data-collection-bulk-print]')
    expect(print_button).to_be_disabled()
    page.locator('[data-collection-bulk-all]').check()
    expect(print_button).to_be_enabled()
    page.evaluate("""() => {
      window.printCalls = [];
      const append = Element.prototype.append;
      Element.prototype.append = function(...nodes) {
        for (const node of nodes) if (node.title === 'Print selected collection notes') {
          node.addEventListener('load', () => {
            node.contentWindow.print = () => {
              printCalls.push([...node.contentDocument.querySelectorAll('input')].map(input => input.value));
            };
          }, {once: true});
        }
        return append.apply(this, nodes);
      };
    }""")
    compact_height = toolbar.bounding_box()['height']
    print_button.click()
    page.wait_for_function('printCalls.length === 1')
    assert page.evaluate('printCalls[0]') == ['Customer one', 'Customer two']
    assert page.evaluate('!window.unwantedScript')
    expect(print_button).to_be_enabled()
    expect(page.locator('.collection-print-preview')).to_have_count(0)
    assert abs(toolbar.bounding_box()['height'] - compact_height) < 1
    frame = page.locator('iframe[title="Print selected collection notes"]')
    assert frame.evaluate("frame => frame.contentDocument.querySelectorAll('.collection-print-note').length") == 2
    assert frame.evaluate("frame => frame.contentDocument.querySelectorAll('script').length") == 0
    frame.evaluate("frame => frame.contentWindow.dispatchEvent(new Event('afterprint'))")
    expect(frame).to_have_count(0)
    expect(page.locator('[data-collection-bulk-count]')).to_have_text('2 selected')
    page.route('**/api/collection-notes/two', lambda route: route.fulfill(status=500, json={'error': 'Could not load selected note.'}))
    print_button.click()
    expect(page.locator('.toast').last).to_contain_text('Could not load selected note.')
    expect(print_button).to_be_enabled()
    assert page.evaluate('printCalls.length') == 1
    page.unroute('**/api/collection-notes/two')
    page.locator('[data-collection-bulk-edit]').click()
    page.wait_for_function('!collectionBulkTransitioning')
    row_print = page.locator('[data-print-collection-record="one"]')
    expect(row_print).to_be_visible()
    assert row_print.evaluate("el => el.previousElementSibling.dataset.format === 'xlsx' && el.nextElementSibling.hasAttribute('data-delete-collection-record')")
    row_print.click()
    page.wait_for_function('printCalls.length === 2')
    assert page.evaluate('printCalls[1]') == ['Customer one']
    expect(row_print).to_be_enabled()
    frame.evaluate("frame => frame.contentWindow.dispatchEvent(new Event('afterprint'))")
    expect(frame).to_have_count(0)
    assert not errors, errors
    browser.close()
    print('PASS: direct print dialog, no custom preview, preserved selections, cleanup and error recovery')

