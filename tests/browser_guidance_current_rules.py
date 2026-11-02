"""Keep visible Guidance aligned with the current failure categories and source fields."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve

import delivery_data
from xdp_sheet import apply_status


assert delivery_data.amazon_status_name('UNDELIVERABLE') == 'Failed'
assert delivery_data.amazon_status_name('LOST') == 'Failed'
for status in ['DAMAGE', 'DELETE', 'NOT RECEIVED']:
    assert apply_status({'carrier': 'XDP', 'xdpStatus': status})['st'] == 'Failed'

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(reduced_motion='reduce')
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/guidance.html')
    page.locator('.guidance-status-map').wait_for()
    table = page.locator('.guidance-status-map')
    failed = table.locator('tbody tr').filter(has=page.locator('th[scope="row"]', has_text='Failed'))
    headings = table.locator('thead tr').nth(1).locator('th').all_text_contents()
    amazon = failed.locator('td').nth(headings.index('Amazon Shipping')).inner_text()
    xdp = failed.locator('td').nth(headings.index('XDP')).inner_text()
    assert 'UNDELIVERABLE' in amazon and 'LOST' in amazon, amazon
    assert all(status in xdp for status in ['DAMAGE', 'DELETE', 'NOT RECEIVED']), xdp
    lost = table.locator('tbody tr').filter(has=page.locator('th[scope="row"]', has_text='Lost'))
    assert 'LOST' not in lost.locator('td').nth(headings.index('Amazon Shipping')).inner_text()
    captions = page.locator('.guidance-table caption').all_text_contents()
    assert captions[-2:] == ['Stores', 'Data switches'], captions
    for group in ['Failed Deliveries · Inclusion and display', 'Failed Deliveries · Filter levels',
                  'Own van · Booking text formatting', 'Tracking · Shipment fields', 'Integration · Data Trafficking']:
        assert group in captions, group
    expect(page.locator('.guidance-workflow')).to_have_count(6)
    expect(page.locator('.guidance-intro')).to_have_css('background-color', 'rgb(23, 28, 53)')
    expect(page.locator('.guidance-table thead th:not([rowspan])').first).to_have_css('background-color', 'rgb(37, 44, 74)')
    expect(page.locator('.guidance-status-map thead th[rowspan]')).to_have_css('color', 'rgb(110, 227, 238)')
    quick = page.locator('.guidance-workflows').inner_text()
    for current in ['Manufacturing Claims', 'Widget guide', 'Others', '15 MB total', 'XLSX and PDF', 'UK London', '75% scale', 'latest recorded sync']:
        assert current in quick, current
    text = page.locator('.guidance-reference').inner_text()
    for expected in ['_Sync_Control', '_Sync_Run_Log', 'NOT RECEIVED', 'zero plus blank',
                     'Current Failed and Rejected', 'current UK year', 'First six digits on each line',
                     'On means hide', 'Amazon LOST is grouped under Failed']:
        assert expected in text, expected
    for width in [390, 760, 1024, 1366, 1920]:
        page.set_viewport_size({'width': width, 'height': 768})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), width
    assert not errors, errors
    print('PASS: Guidance matches Amazon/XDP failure rules, current source/filter/sync definitions, final table order and responsive widths.')
    browser.close()
