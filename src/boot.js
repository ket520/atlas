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
  const modules = ['viewport', 'horizontal-scroll', 'api', 'data', 'services', 'ui', 'dashboard-home', 'dashboard', 'deliveries', 'manufacture-claims', 'admin', 'app'];
  const delay = milliseconds => new Promise(resolve => setTimeout(resolve, milliseconds));

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
      for (const name of modules) await load(name);
    } catch (error) {
      console.error('Atlas startup failed:', error);
      document.dispatchEvent(new CustomEvent('deliverydesk:startup-failed'));
    }
  })();
})();
