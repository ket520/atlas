"""Claims bulk selection keeps filters, selected exports and row actions working."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 900}, reduced_motion='reduce', accept_downloads=True)
    errors, exports = [], []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.route('**/api/manufacture-claims', lambda route: route.fulfill(json={'records': [
        {'id': 'one', 'orderDate': '2026-11-01', 'originalOrderNo': '663132', 'replacementOrderNo': '663133', 'variantCode': 'SKU-ONE', 'reason': 'Scratches', 'solution': 'Replacement', 'sellingShop': 'Shop A', 'photos': []},
        {'id': 'two', 'orderDate': '2026-11-02', 'originalOrderNo': '654171', 'replacementOrderNo': '654172', 'variantCode': 'SKU-TWO', 'reason': 'Broken parts', 'solution': 'Refund', 'sellingShop': 'Shop B', 'photos': []},
    ]}))
    def export(route):
        exports.append(route.request.post_data_json)
        route.fulfill(body=b'export fixture', content_type='application/octet-stream')
    page.route('**/api/manufacture-claims/export', export)
    page.goto('https://deliverydesk.test/pages/manufacture-claims.html')
    expect(page.locator('[data-mc-rows] > tr')).to_have_count(2)
    expect(page.locator('.mc-table th')).to_have_count(9)
    expect(page.locator('.mc-table th:last-child [data-mc-bulk-select]')).to_be_visible()
    page.locator('[data-mc-bulk-select]').click()
    expect(page.locator('.mc-table th')).to_have_count(10)
    toolbar = page.locator('[data-mc-bulk-toolbar]')
    expect(toolbar).to_be_visible()
    expect(toolbar.locator('[data-mc-bulk-download="pdf"]')).to_be_disabled()
    expect(toolbar.locator('[data-mc-bulk-print]')).to_be_disabled()
    page.locator('[data-mc-select="one"]').check()
    expect(page.locator('[data-mc-selected-count]')).to_have_text('1 selected')
    assert page.locator('[data-mc-select-all]').evaluate('el => el.indeterminate')
    expect(page.locator('.mc-dialog')).not_to_be_visible()
    expect(page.locator('[data-mc-delete="one"]')).to_be_visible()
    page.locator('[data-mc-search]').fill('654171')
    expect(page.locator('[data-mc-rows] > tr')).to_have_count(1)
    page.evaluate("""() => {
      window.claimPrintCalls = [];
      const append = Element.prototype.append;
      Element.prototype.append = function(...nodes) {
        for (const node of nodes) if (node.title === 'Print selected manufacturing claims') {
          node.addEventListener('load', () => {
            node.contentWindow.print = () => claimPrintCalls.push({
              text: node.contentDocument.body.textContent,
              headings: node.contentDocument.querySelectorAll('th').length,
              buttons: node.contentDocument.querySelectorAll('button, input').length,
            });
          }, {once: true});
        }
        return append.apply(this, nodes);
      };
    }""")
    toolbar.locator('[data-mc-bulk-print]').click()
    page.wait_for_function('claimPrintCalls.length === 1')
    printed = page.evaluate('claimPrintCalls[0]')
    assert '663132' in printed['text'] and '654171' not in printed['text']
    assert 'Order Date Range: ' + page.evaluate("hd('2026-11-01')") in printed['text']
    assert printed['headings'] == 8 and printed['buttons'] == 0
    expect(page.locator('[data-mc-selected-count]')).to_have_text('1 selected')
    frame = page.locator('iframe[title="Print selected manufacturing claims"]')
    assert frame.evaluate('frame => frame.contentDocument.title.trim()') == ''
    assert frame.evaluate("frame => [...frame.contentDocument.styleSheets[0].cssRules].some(rule => rule.cssText.startsWith('@page') && rule.style.margin === '0px')")
    frame.evaluate("frame => frame.contentWindow.dispatchEvent(new Event('afterprint'))")
    expect(frame).to_have_count(0)
    for format in ('pdf', 'xlsx'):
        with page.expect_download():
            toolbar.locator(f'[data-mc-bulk-download="{format}"]').click()
        expect(toolbar.locator(f'[data-mc-bulk-download="{format}"]')).to_be_enabled()
        assert [row['id'] for row in exports[-1]['rows']] == ['one']
        assert len(exports[-1]['columns']) == 8
        assert exports[-1]['rows'][0]['cells'][1] == '663132'
    page.locator('[data-mc-select-all]').check()
    expect(page.locator('[data-mc-selected-count]')).to_have_text('2 selected')
    page.locator('[data-mc-search]').fill('')
    expect(page.locator('[data-mc-select="one"]')).to_be_checked()
    expect(page.locator('[data-mc-select="two"]')).to_be_checked()
    toolbar.locator('[data-mc-bulk-print]').click()
    page.wait_for_function('claimPrintCalls.length === 2')
    range_text = page.evaluate('claimPrintCalls[1].text')
    assert page.evaluate("hd('2026-11-01')") in range_text
    assert page.evaluate("hd('2026-11-02')") in range_text
    frame.evaluate("frame => frame.contentWindow.dispatchEvent(new Event('afterprint'))")
    page.locator('[data-mc-edit="one"]').press('Space')
    expect(page.locator('[data-mc-select="one"]')).not_to_be_checked()
    for width in (1440, 390):
        page.set_viewport_size({'width': width, 'height': 900})
        box = toolbar.bounding_box()
        assert box and box['x'] >= 0 and box['x'] + box['width'] <= width
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    toolbar.locator('[data-mc-bulk-done]').click()
    expect(toolbar).not_to_be_visible()
    expect(page.locator('.mc-selection-cell')).to_have_count(0)
    expect(page.locator('[data-mc-bulk-select]')).to_be_focused()
    top_print = page.locator('[data-mc-print]')
    expect(top_print).to_be_visible()
    assert top_print.evaluate("el => el.previousElementSibling.dataset.mcDownload === 'pdf' && el.nextElementSibling.hasAttribute('data-mc-refresh')")
    page.locator('[data-mc-search]').fill('654171')
    top_print.click()
    page.wait_for_function('claimPrintCalls.length === 3')
    normal_print = page.evaluate('claimPrintCalls[2].text')
    assert '654171' in normal_print and '663132' not in normal_print
    expect(top_print).to_be_enabled()
    frame.evaluate("frame => frame.contentWindow.dispatchEvent(new Event('afterprint'))")
    assert not errors, errors
    browser.close()
    print('PASS: claims bulk selection, visible select-all, keyboard, selected exports across filters, row actions and mobile toolbar')
