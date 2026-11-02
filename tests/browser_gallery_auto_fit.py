"""Small portrait/landscape images grow to canvas edges; rotation/zoom still work."""
import base64
import io
from PIL import Image
from playwright.sync_api import sync_playwright, expect
from browser_responsive_tables import serve


def picture(size):
    output = io.BytesIO()
    Image.new('RGB', size, '#6267e9').save(output, format='PNG')
    return 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode()


MEASURE = '''() => {
  const canvas=document.querySelector('.qd-gallery-canvas').getBoundingClientRect();
  const image=document.querySelector('.qd-gallery-image').getBoundingClientRect();
  return {width:image.width,height:image.height,cw:canvas.width,ch:canvas.height,
    inside:image.left>=canvas.left-1 && image.right<=canvas.right+1 && image.top>=canvas.top-1 && image.bottom<=canvas.bottom+1};
}'''

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page(viewport={'width':1440,'height':900})
    page.add_init_script("sessionStorage.setItem('deliverydesk-started','1')")
    page.route('https://deliverydesk.test/**', serve)
    page.route('https://fonts.googleapis.com/**', lambda route: route.abort())
    page.goto('https://deliverydesk.test/pages/dashboard.html')
    page.wait_for_function("typeof DeliveryDetail==='object'")
    photos = [{'url':picture((80,240))},{'url':picture((240,80))}]
    for width in (1440,390):
        page.set_viewport_size({'width':width,'height':900})
        page.evaluate("photos=>DeliveryDetail.openImages(photos,0,'Claim images')",photos)
        page.wait_for_function("document.querySelector('.qd-gallery-image').naturalWidth>0 && document.querySelector('.qd-gallery-image').style.width!==''")
        portrait = page.evaluate(MEASURE)
        assert portrait['inside'] and abs(portrait['height']-portrait['ch'])<2, portrait
        page.get_by_role('button',name='Zoom in',exact=True).click()
        expect(page.get_by_role('button',name='Reset image view')).to_have_text('125%')
        assert page.evaluate(MEASURE)['height'] > portrait['height'] * 1.2
        page.get_by_role('button',name='Reset image view').click()
        page.get_by_role('button',name='Rotate image clockwise').click()
        rotated = page.evaluate(MEASURE)
        assert rotated['inside'] and abs(rotated['width']-rotated['cw'])<2, rotated
        page.get_by_role('button',name='Next image').click()
        page.wait_for_function("document.querySelector('.qd-gallery-image').naturalWidth===240 && document.querySelector('.qd-gallery-image').style.width!==''")
        landscape = page.evaluate(MEASURE)
        assert landscape['inside'] and abs(landscape['width']-landscape['cw'])<2, landscape
        page.keyboard.press('Escape')
    browser.close()
    print('PASS: portrait/landscape auto enlargement, full image fit, zoom, reset and rotation on desktop/mobile')
