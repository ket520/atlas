(() => {
  'use strict';
  // Install recovery before the session check: returning visitors need it too.
  function showStartupFailure() {
    const view = document.getElementById('v');
    if (!view || (view.children.length && !view.querySelector('[data-startup-loading]'))) return;
    const panel = document.createElement('section');
    panel.className = 'card startup-load-error';
    panel.setAttribute('role', 'alert');
    const title = document.createElement('h2');
    title.textContent = 'The workspace could not finish loading';
    const message = document.createElement('p');
    message.textContent = 'A required page file could not be loaded. Check your connection and reload the page.';
    const reload = document.createElement('button');
    reload.type = 'button';
    reload.className = 'btn';
    reload.textContent = 'Reload page';
    reload.addEventListener('click', () => location.reload());
    panel.append(title, message, reload);
    view.replaceChildren(panel);
    document.documentElement.classList.remove('desk-starting');
    document.querySelector('.desk-startup')?.remove();
  }
  document.addEventListener('deliverydesk:startup-failed', showStartupFailure);
  window.addEventListener('error', event => {
    const failedBoot = event.target instanceof HTMLScriptElement
      && new URL(event.target.src, location.href).pathname === '/src/boot.js';
    if (!failedBoot && !event.message) return;
    // Wait for the HTML shell if the failure happened while parsing scripts.
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', showStartupFailure, {once: true});
    } else {
      setTimeout(showStartupFailure, 0);
    }
  }, true);
  const sessionKey = 'deliverydesk-started';
  try { if (sessionStorage.getItem(sessionKey)) return; } catch {}

  const startedAt = performance.now();
  const root = document.documentElement;
  root.classList.add('desk-starting');
  const splash = document.createElement('section');
  splash.className = 'desk-startup';
  splash.setAttribute('aria-label', 'Starting Atlas');
  splash.innerHTML = `
    <div class="desk-startup-grain" aria-hidden="true"></div>
    <div class="desk-startup-top"><span class="desk-startup-brand"><img src="/assets/atlas-sidebar.svg" width="30" height="30" alt="">Atlas</span><span class="desk-startup-edition">YOUR OPERATIONS WORKSPACE</span></div>
    <div class="desk-startup-center">
      <div class="desk-startup-route" aria-hidden="true">
        <svg viewBox="0 0 440 180" fill="none"><path class="desk-startup-track" d="M30 135H105Q145 135 145 95V75Q145 35 185 35H255Q295 35 295 75V95Q295 135 335 135H410"/><path class="desk-startup-trail" d="M30 135H105Q145 135 145 95V75Q145 35 185 35H255Q295 35 295 75V95Q295 135 335 135H410"/></svg>
        <div class="desk-startup-icon"><img src="/assets/atlas-sidebar.svg" width="160" height="160" alt=""></div>
        <span class="desk-startup-stop desk-startup-stop-first"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 13v-2a8 8 0 0 1 16 0v2M4 12H3a1 1 0 0 0-1 1v4a1 1 0 0 0 1 1h3v-6zM20 12h1a1 1 0 0 1 1 1v4a1 1 0 0 1-1 1h-3v-6zM20 18v1a2 2 0 0 1-2 2h-4"/><path d="M10 20h4v2h-4z"/></svg></span><span class="desk-startup-stop desk-startup-stop-last"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3 9 5v8l-9 5-9-5V8z"/><path d="m3 8 9 5 9-5M12 13v8M7.5 5.5l9 5v4"/></svg></span>
      </div>
      <p class="desk-startup-eyebrow">ALL YOUR TRACKING. ONE PLACE.</p>
      <h1>Atlas<span class="desk-startup-period">.</span></h1>
      <p class="desk-startup-tagline">Your deliveries, in motion.</p>
      <div class="desk-startup-status" role="status" aria-live="polite"><span class="desk-startup-spinner" aria-hidden="true"></span><span data-startup-status>Opening your workspace…</span></div>
      <button class="desk-startup-continue" type="button" hidden>Continue to workspace <span aria-hidden="true">→</span></button>
    </div>
    <div class="desk-startup-bottom"><span><i aria-hidden="true"></i> by Starparkgroup</span><span>ORDERS. TRACKING. DELIVERED.</span></div>`;
  document.body.append(splash);
  const status = splash.querySelector('[data-startup-status]');
  const continueButton = splash.querySelector('button');
  let closing = false;
  let readyTimer;
  const skipTimer = setTimeout(() => {
    continueButton.hidden = false;
    status.textContent = 'Still loading. You can open the workspace now.';
  }, 4500);
  const fallbackTimer = setTimeout(dismiss, 12000);

  function dismiss() {
    if (closing) return;
    closing = true;
    clearTimeout(skipTimer);
    clearTimeout(fallbackTimer);
    clearTimeout(readyTimer);
    document.removeEventListener('deliverydesk:ready', ready);
    try { sessionStorage.setItem(sessionKey, '1'); } catch {}
    root.classList.remove('desk-starting');
    splash.classList.add('desk-startup-leaving');
    if (splash.contains(document.activeElement)) {
      const main = document.querySelector('main');
      if (main) { main.tabIndex = -1; main.focus({preventScroll: true}); }
    }
    setTimeout(() => splash.remove(), matchMedia('(prefers-reduced-motion: reduce)').matches ? 0 : 650);
  }
  function ready(event) {
    if (closing) return;
    clearTimeout(skipTimer);
    splash.classList.add('desk-startup-ready');
    status.textContent = event.detail?.unavailable ? 'Opening workspace. Data sources need attention.'
      : event.detail?.syncing ? 'Saved workspace ready. Updates continue in the background.' : 'Your workspace is ready.';
    readyTimer = setTimeout(dismiss, Math.max(0, 4000 - (performance.now() - startedAt)));
  }
  continueButton.addEventListener('click', dismiss);
  document.addEventListener('deliverydesk:ready', ready);
  document.addEventListener('DOMContentLoaded', () => {
    if (document.body.dataset.live !== 'true') ready({detail: {}});
    else if (!closing && !readyTimer) status.textContent = 'Loading your delivery overview…';
  }, {once: true});
})();
