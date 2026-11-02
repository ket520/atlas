"""Exercise horizontal input on real pages and nested scroll areas.

Run: python tests/browser_horizontal_scroll.py (requires Playwright Chromium).
"""
from playwright.sync_api import sync_playwright
from browser_responsive_tables import serve


with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width': 1024, 'height': 768}, reduced_motion='reduce')
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda r: r.abort())
    page.route('**/api/**', lambda r: r.fulfill(json={'records': []}))
    for name, selector in [('deliveries.html', '.tracking-records-scroll'),
                           ('failed-deliveries.html', '.tracking-records-scroll'),
                           ('collective-note.html?view=create', '.cn-format-toolbar'),
                           ('guidance.html', '.guidance-table-scroll')]:
        page.goto('https://deliverydesk.test/pages/' + name)
        area = page.locator(selector).first
        area.wait_for()
        area.evaluate('''el=>{el.tabIndex=0;el.scrollLeft=0;el.focus();}''')
        page.keyboard.press('ArrowRight')
        assert area.evaluate('(el)=>el.scrollLeft>0'), name
        page.keyboard.press('ArrowLeft')
        assert area.evaluate('(el)=>el.scrollLeft===0'), name
        area.evaluate('''el=>el.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaX:100}))''')
        right = area.evaluate('(el)=>el.scrollLeft')
        assert right == area.evaluate('(el)=>Math.min(100,el.scrollWidth-el.clientWidth)'), name
        area.evaluate('''el=>el.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:-60,shiftKey:true}))''')
        assert area.evaluate('(el)=>el.scrollLeft') == max(0, right-60), name
        # Normal vertical wheels remain available to the table/page.
        assert area.evaluate('''el=>el.dispatchEvent(new WheelEvent('wheel',{bubbles:true,cancelable:true,deltaY:60}))'''), name

    # Delegation also works for scroll areas inserted after the page has loaded.
    page.evaluate('''() => {
      const fixture=document.createElement('section');
      fixture.innerHTML=`<div id="outer" tabindex="0" style="width:300px;overflow-x:auto">
        <div style="width:900px"><div id="inner" tabindex="0" style="width:200px;overflow-x:auto">
          <div style="width:600px"><span id="scroll-text">Scroll area</span><input id="caret" value="abcdef"></div>
        </div></div></div>`;
      document.body.append(fixture);
    }''')
    inner, outer = page.locator('#inner'), page.locator('#outer')
    inner.focus()
    page.keyboard.press('ArrowRight')
    assert inner.evaluate('(el)=>el.scrollLeft') == 80
    assert outer.evaluate('(el)=>el.scrollLeft') == 0
    inner.evaluate('(el)=>el.scrollLeft=el.scrollWidth')
    page.keyboard.press('ArrowRight')
    assert outer.evaluate('(el)=>el.scrollLeft') == 80
    inner.evaluate('(el)=>el.scrollLeft=0')
    outer.evaluate('(el)=>el.scrollLeft=0')
    page.locator('#caret').focus()
    page.locator('#caret').evaluate('(el)=>el.setSelectionRange(2,2)')
    before_inner = inner.evaluate('(el)=>el.scrollLeft')
    before_outer = outer.evaluate('(el)=>el.scrollLeft')
    page.keyboard.press('ArrowRight')
    assert page.locator('#caret').evaluate('(el)=>el.selectionStart') == 3
    assert inner.evaluate('(el)=>el.scrollLeft') == before_inner
    assert outer.evaluate('(el)=>el.scrollLeft') == before_outer
    # An existing widget's prevented arrow key must not also scroll its parent.
    inner.evaluate('''el=>el.addEventListener('keydown',event=>event.preventDefault())''')
    inner.focus()
    inner.evaluate('(el)=>el.scrollLeft=0')
    page.keyboard.press('ArrowRight')
    assert inner.evaluate('(el)=>el.scrollLeft') == 0
    browser.close()
    print('PASS: arrows, horizontal gestures and Shift+wheel on both tables, formatting toolbar and Guidance; dynamic nested areas chain at edges, while vertical scrolling, text editing and widget keys retain their behavior.')
