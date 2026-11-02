"""Safely add Amazon-only, on-demand Playwright lookup to an existing Delivery Desk.

Run once in the CustomerServiceDeliveryInterface folder: py install_amazon_on_demand.py
Makes timestamped backups. Refuses to patch if expected code is missing/ambiguous.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
STAMP = datetime.now().strftime('%Y%m%d-%H%M%S')

LIVE_LOADER = '''  function loadAmazonShipping(trackingId) {
    if (!/^UK\\d{8,20}$/.test(trackingId)) return;
    if (amazonShippingPending.has(trackingId)) return;

    amazonShippingPending.add(trackingId);
    const endpoint = `/api/amazon-shipping/live/${encodeURIComponent(trackingId)}`;

    async function checkAmazon(attempt = 0) {
      const response = await fetch(
        endpoint + (attempt === 0 ? '?refresh=1' : ''),
        { cache: 'no-store' }
      );
      const result = await response.json();

      if (!response.ok) {
        throw new Error(result.error || `Amazon lookup HTTP ${response.status}`);
      }

      if (result.state === 'queued' || result.state === 'loading') {
        if (attempt >= 80) {
          throw new Error('Amazon lookup timed out. Reopen this order to retry.');
        }
        await new Promise(resolve => setTimeout(resolve, 2500));
        return checkAmazon(attempt + 1);
      }

      if (result.state === 'error') {
        throw new Error(result.error || 'Amazon lookup failed.');
      }

      if (
        result.state !== 'ready'
        || !result.data?.available
        || result.data.tracking_id !== trackingId
      ) {
        throw new Error('No matching Amazon shipment was returned.');
      }

      return result.data;
    }

    checkAmazon()
      .then(data => {
        amazonShippingCache.set(trackingId, data);
      })
      .catch(error => {
        amazonShippingCache.set(trackingId, {
          available: false,
          tracking_id: trackingId,
          error: error.message || 'Amazon Shipping could not load.',
        });
      })
      .finally(() => {
        amazonShippingPending.delete(trackingId);
        const current = sel ? get(sel) : null;
        const panel = container()?.querySelector('.qd-tracking-view');
        if (
          page === 'Deliveries'
          && current
          && isAmazonShippingDelivery(current)
          && panel
          && !panel.classList.contains('qd-closing')
          && amazonShippingId(current) === trackingId
        ) {
          render();
        }
      });
  }
'''

STRICT_AMAZON = '''  function isAmazonShippingDelivery(delivery) {
    if (!delivery) return false;
    const carrier = String(delivery.carrier || '').trim().toLowerCase();
    return ['amz', 'amazon', 'amazon shipping'].includes(carrier);
  }
'''

NEW_API = '''            if url.path.startswith("/api/amazon-shipping/live/"):
                from amazon_shipping_live import serve_live
                return serve_live(self, url.path, parse_qs(url.query))

'''

CSS_RULE = '''
/* On-demand Amazon loading — Tracking page, Amazon carrier only */
.dr.qd.qd-tracking-view .qd-amazon-live-loading {
  margin: 18px 0 24px;
  padding: 16px 18px;
  border: 1px solid #d8e6db;
  border-radius: 12px;
  background: #f3f8f4;
  color: #476d54;
  font-size: 13px;
}
'''


def once_replace(data, old, new, label):
    count = data.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one matching block, found {count}. File was NOT changed.')
    return data.replace(old, new, 1)


def patch_js(source):
    a = source.find('  function loadAmazonShipping(trackingId) {')
    b = source.find('  function amazonShippingActivity(data) {', a)
    if a < 0 or b <= a:
        raise RuntimeError('JS: could not locate Amazon loader block. No files changed.')
    source = source[:a] + LIVE_LOADER + '\n' + source[b:]

    a = source.find('  function isAmazonShippingDelivery(delivery) {')
    b = source.find('  function loadAmazonShipping(trackingId) {', a)
    if a < 0 or b <= a:
        raise RuntimeError('JS: could not locate Amazon carrier check. No files changed.')
    source = source[:a] + STRICT_AMAZON + '\n' + source[b:]

    old = '''    if (validId && !data) {
      loadAmazonShipping(trackingId);
    }
'''
    new = '''    if (validId && !data) {
      loadAmazonShipping(trackingId);
      panel.querySelector('.qd-section-tabs')?.insertAdjacentHTML(
        'afterend',
        '<p class="qd-amazon-live-loading" role="status">Fetching Amazon shipment history, proof of delivery and Package details Excel…</p>'
      );
      return;
    }
'''
    source = once_replace(source, old, new, 'JS: loading placeholder')

    original_open = '''  function open(id, section = '') {
    if (detailCloseTimer !== null) {
      clearTimeout(detailCloseTimer);
      detailCloseTimer = null;
    }

    sel = id;
'''
    new_open = '''  function open(id, section = '') {
    if (detailCloseTimer !== null) {
      clearTimeout(detailCloseTimer);
      detailCloseTimer = null;
    }

    // A fresh Amazon lookup is requested each time an AMZ order is opened.
    const amazonDelivery = get(id);
    if (page === 'Deliveries' && isAmazonShippingDelivery(amazonDelivery)) {
      const trackingId = amazonShippingId(amazonDelivery);
      if (/^UK\\d{8,20}$/.test(trackingId)) amazonShippingCache.delete(trackingId);
    }

    sel = id;
'''
    source = once_replace(source, original_open, new_open, 'JS: open() function')
    source = source.replace('Saved Amazon browser capture · Not live', 'Amazon Shipping · Retrieved on demand')
    if 'renderAmazonShippingContent(delivery);' not in source:
        raise RuntimeError('JS: Amazon render integration missing. No files changed.')
    return source


def patch_server(source):
    if 'url.path.startswith("/api/amazon-shipping/live/")' in source:
        raise RuntimeError('server.py: live route is already present. Installer will not apply twice.')
    anchor = '''            if url.path.startswith("/api/amazon-shipping/"):
'''
    if anchor in source:
        return once_replace(source, anchor, NEW_API + anchor, 'server.py Amazon route')
    anchor = '''            url = urlsplit(self.path)
'''
    addition = '''            url = urlsplit(self.path)

            if url.path.startswith("/api/amazon-shipping/live/"):
                from amazon_shipping_live import serve_live
                return serve_live(self, url.path, parse_qs(url.query))

            if url.path.startswith("/api/amazon-shipping/"):
                from amazon_shipping_demo import serve_amazon_shipping
                return serve_amazon_shipping(self, url.path, parse_qs(url.query))
'''
    return once_replace(source, anchor, addition, 'server.py do_GET')


def locate_js():
    js = ROOT / "src" / "ui.js"

    if not js.is_file():
        raise RuntimeError(
            f"JavaScript file not found: {js}"
        )

    if 'const DeliveryDetail = (() => {' not in js.read_text(encoding="utf-8-sig"):
        raise RuntimeError(
            "src/ui.js does not contain DeliveryDetail."
        )

    return js

def main():
    server = ROOT / 'server.py'
    js = locate_js()
    css = ROOT / 'src' / 'styles' / 'delivery-detail.css'
    live_mod = ROOT / 'amazon_shipping_live.py'
    demo_mod = ROOT / 'amazon_shipping_demo.py'
    demo_new = ROOT / 'amazon_shipping_demo_live.py'

    if not server.is_file() or not live_mod.is_file() or not demo_mod.is_file() or not demo_new.is_file():
        raise RuntimeError('Place ZIP contents in the same folder as server.py before running.')

    old_js = js.read_text(encoding='utf-8-sig')
    old_server = server.read_text(encoding='utf-8-sig')
    candidate_js = patch_js(old_js)
    candidate_server = patch_server(old_server)
    compile(candidate_server, str(server), 'exec')
    compile(live_mod.read_text(encoding='utf-8'), str(live_mod), 'exec')
    compile(demo_new.read_text(encoding='utf-8'), str(demo_new), 'exec')
    node = shutil.which('node')
    if node:
        probe = ROOT / f'.amazon-js-check-{STAMP}.js'
        try:
            probe.write_text(candidate_js, encoding='utf-8')
            checked = subprocess.run([node, '--check', str(probe)], capture_output=True, text=True)
            if checked.returncode:
                raise RuntimeError('JavaScript syntax check failed:\n' + checked.stderr)
        finally:
            probe.unlink(missing_ok=True)

    to_write = [(server, candidate_server), (js, candidate_js)]
    if css.is_file():
        old_css = css.read_text(encoding='utf-8-sig')
        if '.qd-amazon-live-loading' not in old_css:
            to_write.append((css, old_css + '\n' + CSS_RULE))

    demo_backup = demo_mod.with_name(demo_mod.name + '.before-amazon-live-' + STAMP)
    shutil.copy2(demo_mod, demo_backup)
    print('Backup:', demo_backup.relative_to(ROOT))
    shutil.copy2(demo_new, demo_mod)
    print('Updated:', demo_mod.relative_to(ROOT))

    for path, changed in to_write:
        backup = path.with_name(path.name + '.before-amazon-live-' + STAMP)
        shutil.copy2(path, backup)
        print('Backup:', backup.relative_to(ROOT))
        path.write_text(changed, encoding='utf-8')
        print('Updated:', path.relative_to(ROOT))
    print('\nDONE: Amazon-only on-demand integration installed.')
    print('Restart: py server.py')
    print('Ensure Amazon credentials are configured in .env.local on this PC.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('NOT INSTALLED:', exc)
        sys.exit(1)
