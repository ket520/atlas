"""Check Tracking copy actions and dashboard cursor behavior."""
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    context = browser.new_context(permissions=['clipboard-read', 'clipboard-write'], viewport={'width': 1440, 'height': 900})
    page = context.new_page()
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/deliveries.html')
    page.wait_for_function("typeof R === 'function'")
    page.evaluate("""() => {
      DeliveryStore.hydrate({deliveries:[{id:'copy-test',order:'650001',
        orderRef:'REF-650001',carrier:'Palletways',st:'Scheduled',logs:[],
        palletwaysSheetConsignmentNumber:'12345678901'}],activity:[],integrations:[]});
      D=DeliveryStore.deliveries();fsrc='Palletways';R();
    }""")
    for attribute, value in [('order-number', '650001'), ('order-reference', 'REF-650001'),
                             ('consignment-number', '12345678901')]:
        page.locator(f'[data-copy-{attribute}]').first.click()
        page.wait_for_function('(value) => navigator.clipboard.readText().then(text => text === value)', arg=value)
    expect(page.locator('#dr .dr')).to_have_count(0)

    # Exercise browsers that expose the API but deny permission.
    page.evaluate("""() => {
      navigator.clipboard.writeText = () => Promise.reject(new Error('Permission denied'));
      window.originalExecCommand = document.execCommand.bind(document);
      document.execCommand = command => {
        window.fallbackValue = document.activeElement.value;
        return window.originalExecCommand(command);
      };
    }""")
    button = page.locator('[data-copy-order-number]').first
    button.click()
    expect(page.locator('.toast').last).to_have_text('Order number copied')
    assert page.evaluate('window.fallbackValue') == '650001'
    expect(button).to_be_focused()
    page.evaluate('document.execCommand = () => false')
    button.click()
    expect(page.locator('.toast').last).to_have_text('Could not copy. Please copy it manually.')

    page.goto('https://deliverydesk.test/pages/dashboard.html')
    card = page.locator('.dash-widget').first
    expect(card).to_be_visible()
    assert card.evaluate('el => getComputedStyle(el).cursor') == 'default'
    rect = card.bounding_box()
    page.mouse.move(rect['x'] + 10, rect['y'] + 12)
    page.mouse.down()
    page.mouse.move(rect['x'] + 30, rect['y'] + 30)
    expect(page.locator('.dash-widget-drag-preview')).to_be_visible()
    assert page.evaluate('getComputedStyle(document.body).cursor') == 'move'
    page.keyboard.press('Escape')
    page.mouse.up()
    assert page.evaluate("document.body.classList.contains('is-dashboard-dragging')") is False
    browser.close()
    print('PASS: Tracking copies, denied-permission fallback, failure feedback and dashboard cursors')
