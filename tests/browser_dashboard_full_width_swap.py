"""Drag a 3x2 card past three 1x1 cards without leaving gaps or overlaps."""
import sys
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':1000}, reduced_motion='no-preference' if '--animated' in sys.argv else 'reduce')
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      if (!localStorage.getItem('deliverydesk-dashboard-widgets-v1')) {
        localStorage.setItem('deliverydesk-dashboard-widgets-v1',JSON.stringify(['hold','awaiting-dispatch','out-of-stock','charge-pending']));
        localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes',JSON.stringify({
          hold:'3x2','hold-slot':0,'awaiting-dispatch-slot':6,'out-of-stock-slot':7,'charge-pending-slot':8}));
      }""")
    page.route('https://deliverydesk.test/**',serve)
    page.route('https://fonts.googleapis.com/**',lambda route:route.abort())
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.locator('[data-dash-widget="hold"]').wait_for()

    def positions():
        return page.locator('#dash-widget-grid [data-dash-widget]').evaluate_all(
            'cards=>Object.fromEntries(cards.map(card=>[card.dataset.dashWidget,[card.style.gridRow,card.style.gridColumn]]))')

    original=positions()
    expected={'hold':['2 / span 2','1 / span 3'], 'awaiting-dispatch':['1','1'],
              'out-of-stock':['1','2'], 'charge-pending':['1','3']}

    def drag(source,target,cancel=False,preview=None):
        card=page.locator(f'[data-dash-widget="{source}"]').bounding_box()
        page.mouse.move(card['x']+10,card['y']+12)
        page.mouse.down()
        page.mouse.move(card['x']+20,card['y']+22)
        ghost=page.locator('.dash-widget-drag-preview')
        expect(ghost).to_be_visible()
        slot=page.locator(f'[data-widget-slot="{target}"]').bounding_box()
        floating=ghost.bounding_box()
        page.mouse.move(slot['x']+(slot['width']-floating['width'])/2+9.4,
                        slot['y']+(slot['height']-floating['height'])/2+11.28)
        expect(page.locator('.dash-widget.is-widget-drop-ready')).to_have_count(1)
        if preview is not None:
            assert positions()==preview,positions()
        if cancel:
            page.keyboard.press('Escape')
        page.mouse.up()
        expect(page.locator('.dash-widget-drag-preview')).to_have_count(0)

    drag('hold','out-of-stock',cancel=True,preview=expected)
    assert positions()==original,positions()
    drag('hold','out-of-stock',preview=expected)
    assert positions()==expected,positions()
    page.reload()
    page.locator('[data-dash-widget="hold"]').wait_for()
    assert positions()==expected,positions()
    drag('out-of-stock','hold',preview=original)
    assert positions()==original,positions()
    assert not errors,errors
    browser.close()
    print('PASS: full-width drag preview, upward packing, cancellation, persisted layout and reverse swap')
