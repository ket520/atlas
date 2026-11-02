from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve
with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900}, reduced_motion='no-preference')
    page.add_init_script("""sessionStorage.setItem('deliverydesk-started','1');
      localStorage.setItem('deliverydesk-dashboard-widgets-v1', JSON.stringify(['hold','collect','cancelled']));
      localStorage.setItem('deliverydesk-dashboard-widgets-v1-sizes', JSON.stringify({'hold-slot':0,'collect-slot':7,'cancelled':'1x3','cancelled-slot':2,'cancelled-column':2}));""")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    errors=[]
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.add_init_script("localStorage.setItem('deliverydesk-widget-tour-v1','seen')")
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    placement=lambda key: page.locator(f'[data-dash-widget="{key}"]').evaluate('(el)=>[el.style.gridRow,el.style.gridColumn]')
    before={key:placement(key) for key in ['hold','collect']}
    page.locator('[data-dash-customize]').click()
    tile=page.locator('[data-picker-key="charge-pending"][data-picker-size="1x1"]')
    tile.wait_for(state='visible')
    tile.evaluate('(el)=>el.closest(".dash-editor").getAnimations().forEach(a=>a.finish())')
    page.evaluate("window.heldCard=document.querySelector('[data-dash-widget=hold]');window.heldTile=document.querySelector('[data-picker-key=returns][data-picker-size=\"1x3\"]')")
    def no_page_scroll():
        assert page.evaluate("document.documentElement.scrollHeight<=innerHeight && document.documentElement.scrollWidth<=innerWidth")
        assert page.evaluate("getComputedStyle(document.body).overflowY === 'hidden'")
    no_page_scroll()
    rect=tile.bounding_box()
    page.mouse.move(rect['x']+rect['width']/2, rect['y']+rect['height']/2)
    page.mouse.down()
    page.mouse.move(rect['x']+rect['width']/2+8, rect['y']+rect['height']/2+8)
    page.mouse.move(1435, 895)
    no_page_scroll()
    grid=page.locator('#dash-widget-grid').bounding_box()
    page.mouse.move(grid['x']+grid['width']*5/6,grid['y']+grid['height']/2)
    expect(page.locator('.dash-picker-slots .is-widget-drop-ready')).to_have_count(1)
    page.evaluate("() => { window.enteredTiles=[]; const animate=Element.prototype.animate; Element.prototype.animate=function(...args){if(this.dataset.pickerKey)enteredTiles.push(this.dataset.pickerKey+':'+this.dataset.pickerSize);return animate.apply(this,args)}; }")
    page.mouse.up()
    expect(page.locator('[data-dash-widget="cancelled"]')).to_have_count(0)
    assert placement('charge-pending')==['2','3'],placement('charge-pending')
    for key in before: assert placement(key)==before[key]
    no_page_scroll()
    assert page.evaluate("heldCard===document.querySelector('[data-dash-widget=hold]') && heldTile===document.querySelector('[data-picker-key=returns][data-picker-size=\"1x3\"]')")
    assert page.evaluate("enteredTiles.includes('cancelled:1x3')")
    assert page.locator('.dash-add-slot').evaluate_all("items=>items.filter(el=>el.style.gridColumn==='3').length")==2
    expect(page.locator('[data-picker-key="cancelled"][data-picker-size="1x3"]')).to_have_count(1)
    page.locator('[data-dash-customize]').click()
    expect(page.locator('.dash-editor.is-closing')).to_have_count(1)
    expect(page.locator('.dash-editor')).to_have_count(0)
    expect(page.locator('.app')).not_to_have_class('app cl')
    page.locator('.mn[data-app-action="toggle-sidebar"]').click()
    expect(page.locator('.app')).to_have_class('app cl')
    page.locator('[data-dash-customize]').click()
    page.locator('[data-dash-customize]').click()
    expect(page.locator('.dash-editor')).to_have_count(0)
    expect(page.locator('.app')).to_have_class('app cl')
    assert not errors, errors
    print('PASS: exact row/column replacement, tall removal leaves two holes, neighbors stay fixed, displaced version returns, exit animation, sidebar state restored')
    browser.close()

