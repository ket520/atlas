"""Method slides preserve totals, source definitions and navigation."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1440, 'height': 1000}, reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1');localStorage.setItem('delivery-desk-hide-hygienic-tracking','false')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/guidance.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      liveSummary={filterFacets:[
        {carrier:'Own van',classification:'Standard Van Delivery',count:6},
        {carrier:'Self Delivery',classification:'Self Delivery',count:2},
        {carrier:'Palletways',classification:'Palletways',count:5},
        {carrier:'Palletways',classification:'Palletways Next Day',count:3},
        {carrier:'Palletways',classification:'Palletways',count:9,creditRefund:1},
        {carrier:'AMZ',classification:'AMA XL',count:7,amazonStatus:'IN_TRANSIT'},
        {carrier:'AMZ',classification:'AMA Letter',count:2,amazonStatus:'DELIVERED'},
        {carrier:'XDP',classification:'XDP BQ',count:4,xdpStatus:'DELIVERY'},
        {carrier:'XDP',classification:'XDP',count:1,xdpStatus:'DAMAGE'}]};R();
    }""")
    expect(page.locator('.guidance-method-slide')).to_have_count(5)
    expect(page.locator('[data-guidance-method-prev]')).to_be_disabled()
    expect(page.locator('.guidance-van-methods tfoot td')).to_have_text('8')
    page.get_by_role('button', name='Next delivery method', exact=True).click()
    expect(page.locator('[data-guidance-method-current]')).to_have_text('Palletways 2 / 5')
    expect(page.locator('[data-guidance-method-next]')).to_be_enabled()
    expect(page.locator('.guidance-palletways-methods tfoot td')).to_have_text('8')
    statuses = page.locator('.guidance-palletways-statuses')
    cancelled = statuses.locator('tr.guidance-self-defined').filter(has=page.get_by_role('rowheader', name='Cancelled', exact=True))
    expect(cancelled).to_contain_text('Order Category = Cancelled')
    credit = statuses.locator('tr.guidance-self-defined').filter(has=page.get_by_role('rowheader', name='Credit/Refund (credit note)', exact=True))
    expect(credit).to_contain_text('Order Category = Credit/Refund')
    expect(statuses).to_contain_text('Keep the exact text')
    page.get_by_role('button', name='Next delivery method', exact=True).click()
    expect(page.locator('[data-guidance-method-current]')).to_have_text('Amazon 3 / 5')
    expect(page.locator('.guidance-amz-methods tfoot td')).to_have_text('9')
    expect(page.locator('.guidance-amz-statuses .guidance-self-defined')).to_have_count(0)
    for cell in page.locator('.guidance-amz-statuses tbody tr td:nth-child(2)').all_text_contents():
        assert cell == 'Amazon Shipping tab column G · Order status'
    page.get_by_role('button', name='Next delivery method', exact=True).click()
    expect(page.locator('[data-guidance-method-current]')).to_have_text('XDP 4 / 5')
    expect(page.locator('[data-guidance-method-next]')).to_be_enabled()
    expect(page.locator('.guidance-xdp-methods tfoot td')).to_have_text('5')
    expect(page.locator('.guidance-xdp-statuses .guidance-self-defined')).to_have_count(2)
    expect(page.locator('.guidance-xdp-statuses')).to_contain_text('Order Category = Cancelled')
    expect(page.locator('.guidance-xdp-statuses')).to_contain_text('Order Category = Credit/Refund')
    xdp_labels = page.locator('.guidance-xdp-statuses tbody th').all_text_contents()
    assert not {'IRISH MANIFEST', 'MISROUTE', 'EXCEPTION', 'EDIT'}.intersection(xdp_labels)
    page.get_by_role('button', name='Next delivery method', exact=True).click()
    expect(page.locator('[data-guidance-method-current]')).to_have_text('Stopstart 5 / 5')
    expect(page.locator('[data-guidance-method-next]')).to_be_disabled()
    expect(page.locator('.guidance-stopstart-statuses')).to_contain_text('STOPSTART tab column I')
    expect(page.locator('.guidance-method-slides')).to_have_css('scrollbar-width', 'none')
    page.locator('[data-guidance-method-index="1"]').click()
    page.get_by_role('button', name='Previous delivery method', exact=True).click()
    expect(page.locator('[data-guidance-method-current]')).to_have_text('Van 1 / 5')
    page.get_by_role('button', name='Search guidance', exact=True).click()
    page.locator('[data-guidance-search]').fill('self-defined')
    expect(page.locator('[data-guidance-method-current]')).to_have_text('Palletways 2 / 5')
    page.get_by_role('button', name='Clear and close guidance search', exact=True).click()
    for width in [1440, 390]:
        page.set_viewport_size({'width': width, 'height': 1000})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert not errors, errors
    browser.close()
    print('PASS: five method slides, source rules, hidden scrollbar, navigation, search and mobile layout')
