/* Load dependencies in order and retry interrupted requests before starting the app. */
(() => {
  'use strict';
  const view = document.getElementById('v');
  if (view && !view.children.length) {
    const loading = document.createElement('p');
    loading.dataset.startupLoading = '';
    loading.setAttribute('role', 'status');
    loading.textContent = 'Opening your workspace\u2026';
    view.append(loading);
  }
  const modules = [
    'viewport', 'horizontal-scroll', 'api', 'data', 'services',
    'status-views', 'palletways-shipments', 'product-links', 'ui',
    'dashboard-home', 'dashboard', 'deliveries', 'manufacture-claims', 'admin', 'app',
  ];
  const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

  async function ensureStyles(link) {
    const url = new URL(link.href, location.href);
    if (url.origin !== location.origin || !url.pathname.startsWith('/static/css/')) return;
    try {
      if (link.sheet && link.sheet.cssRules.length) return;
    } catch (_) {
      // Failed stylesheet downloads can expose an unreadable sheet in Chromium.
    }
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => finish(new Error(`Could not load ${url.pathname}`)), 15000);
          function finish(error) {
            clearTimeout(timeout);
            link.onload = link.onerror = null;
            error ? reject(error) : resolve();
          }
          link.onload = () => finish();
          link.onerror = () => finish(new Error(`Could not load ${url.pathname}`));
          url.searchParams.set('retry', `${Date.now()}-${attempt}`);
          link.href = url.href;
        });
        return;
      } catch (error) {
        if (attempt === 1) throw error;
        await delay(500);
      }
    }
  }

  async function load(name) {
    const path = `/src/${name}.js`;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        await new Promise((resolve, reject) => {
          const script = document.createElement('script');
          script.src = attempt ? `${path}?retry=${Date.now()}-${attempt}` : path;
          script.async = false;
          script.onload = resolve;
          script.onerror = () => {
            script.remove();
            reject(new Error(`Could not load ${path}`));
          };
          document.head.append(script);
        });
        return;
      } catch (error) {
        if (attempt === 2) throw error;
        await delay(500 * (attempt + 1));
      }
    }
  }

  (async () => {
    try {
      await Promise.all([...document.querySelectorAll('link[rel="stylesheet"]')].map(ensureStyles));
      for (const name of modules) await load(name);
    } catch (error) {
      console.error('Atlas startup failed:', error);
      document.dispatchEvent(new CustomEvent('deliverydesk:startup-failed'));
    }
  })();
})();
