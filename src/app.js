const pageRenderers = () => ({
  Dashboard: vDash,
  Deliveries: vDel,
  Replacement: vDel,
  Refund: vDel,
  'Failed Deliveries': vFail,
  'Collective Note': vCollectiveNote,
  'Manufacture Claims': vManufactureClaims,
  Integrations: vIntegrations,
  Guidance: vGuidance,
  Settings: vSettings,
});

const sidebarLink = (target, version = null) => `
  <a
    ${version ? 'role="link" tabindex="0" aria-disabled="true"' : `href="${PAGE_URL[target]}" data-page-target="${target}"`}
    class="${target === page ? 'on' : ''}${version ? ' sidebar-planned' : ''}"
    aria-label="${PAGE_LABELS[target] || target}${version ? ` — Version ${version}, not available yet` : ''}"
    ${version ? `data-sidebar-hint="${PAGE_LABELS[target] || target} — Planned for Version ${version}. Not available yet."` : ''}
    ${target === page ? 'aria-current="page"' : ''}
  >
    ${ico(target, 20)}<span class="sidebar-link-label">${PAGE_LABELS[target] || target}${version ? `<span class="sidebar-version">V${version}</span>` : ''}</span>
  </a>`;

function renderSidebar() {
  $('#side').innerHTML = `
    <div class="sidebar-app-icon" aria-label="Atlas"><img src="/assets/atlas-sidebar.svg" alt="" width="56" height="56"><span class="side-logo-wordmark">Atlas</span></div>
    <button class="sidebar-close" data-app-action="toggle-sidebar" aria-label="Close navigation">
      ${ico('x', 22)}
    </button>
    <div class="side-main">
      ${SIDEBAR_ITEMS.filter(item => !item.bottom).map(item => sidebarLink(item.target, item.version)).join('')}
    </div>
    <div class="side-bottom">
      ${SIDEBAR_ITEMS.filter(item => item.bottom).map(item => sidebarLink(item.target, item.version)).join('')}
    </div>
    <button class="sidebar-expand" type="button" tabindex="${$('.app').classList.contains('cl') ? '0' : '-1'}" data-app-action="toggle-sidebar" aria-label="Expand navigation" title="Expand navigation">${ico('right', 22)}</button>`;
}

// Render outside the scrolling sidebar so hints also fit beside collapsed icons.
const sidebarHint = document.createElement('div');
sidebarHint.id = 'sidebar-hint';
sidebarHint.className = 'sidebar-hint';
sidebarHint.setAttribute('role', 'tooltip');
sidebarHint.hidden = true;
document.body.append(sidebarHint);
let sidebarHintTarget = null;
function hideSidebarHint() {
  sidebarHintTarget?.removeAttribute('aria-describedby');
  sidebarHintTarget = null;
  sidebarHint.hidden = true;
}
function showSidebarHint(target) {
  hideSidebarHint();
  sidebarHintTarget = target;
  sidebarHint.textContent = target.dataset.sidebarHint;
  target.setAttribute('aria-describedby', sidebarHint.id);
  sidebarHint.hidden = false;
  const bounds = AtlasViewport.rect(target);
  const width = sidebarHint.offsetWidth;
  const height = sidebarHint.offsetHeight;
  sidebarHint.style.left = `${Math.max(8, Math.min(bounds.right + 12, AtlasViewport.width - width - 8))}px`;
  sidebarHint.style.top = `${Math.max(8, Math.min(bounds.top + (bounds.height - height) / 2, AtlasViewport.height - height - 8))}px`;
}
document.addEventListener('pointerover', event => {
  const target = event.target.closest('[data-sidebar-hint]');
  if (target && target !== sidebarHintTarget) showSidebarHint(target);
});
document.addEventListener('pointerout', event => {
  if (sidebarHintTarget?.contains(event.target) && !sidebarHintTarget.contains(event.relatedTarget)) hideSidebarHint();
});
document.addEventListener('focusin', event => {
  const target = event.target.closest('[data-sidebar-hint]');
  if (target) showSidebarHint(target);
});
document.addEventListener('focusout', hideSidebarHint);
document.addEventListener('scroll', hideSidebarHint, true);
window.addEventListener('resize', hideSidebarHint);
document.addEventListener('keydown', event => { if (event.key === 'Escape') hideSidebarHint(); });
document.addEventListener('click', event => {
  const target = event.target.closest('[aria-disabled="true"][data-sidebar-hint]');
  if (target) { event.preventDefault(); showSidebarHint(target); }
});

let renderedPage = null;
let pageTransition = null;
let collectionNoteReady = null;

function loadCollectionNote() {
  if (!collectionNoteReady) {
    const styles = new Promise((resolve, reject) => {
      const existing = document.querySelector('link[href="/static/css/collection.css"]');
      if (existing?.sheet) { resolve(); return; }
      existing?.remove();
      const stylesheet = document.createElement('link');
      stylesheet.rel = 'stylesheet';
      stylesheet.href = '/static/css/collection.css';
      stylesheet.addEventListener('load', resolve, {once: true});
      stylesheet.addEventListener('error', () => {
        stylesheet.remove();
        reject(new Error('Could not load the collection note styles. Refresh to retry.'));
      }, {once: true});
      document.head.insertBefore(stylesheet, document.querySelector('link[href="/static/css/startup.css"]'));
    });
    const scriptReady = window.CollectionNote ? Promise.resolve() : new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = '/static/js/collection.js';
      script.onload = resolve;
      script.onerror = () => { script.remove(); reject(new Error('Could not load the collection note. Refresh to retry.')); };
      document.head.append(script);
    });
    collectionNoteReady = Promise.all([styles, scriptReady]);
  }
  collectionNoteReady.then(() => {
    const root = document.getElementById('collection-note-root');
    if (page === 'Collective Note' && root && root.dataset.mounted !== 'true') window.CollectionNote.mount(root);
  }).catch(error => {
    collectionNoteReady = null;
    const root = document.getElementById('collection-note-root');
    if (root) root.textContent = error.message;
  });
}

function renderHeaderStores() {
  const excluded = ['Dashboard', 'Integrations', 'Guidance', 'Settings'].includes(page);
  const existing = document.querySelector('.header-store-links');
  if (excluded) { existing?.remove(); return; }
  if (existing) return;
  const actions = document.querySelector('.hd .hr');
  if (!actions) return;
  const stores = document.createElement('nav');
  stores.className = 'header-store-links';
  stores.setAttribute('aria-label', 'Store websites');
  stores.innerHTML = DashboardHome.storeLinksMarkup();
  actions.insertBefore(stores, actions.querySelector('.live-data-status, [aria-label="Profile"]'));
}

function R() {
  hideSidebarHint();
  const switchingPage = renderedPage !== null && renderedPage !== page;
  renderedPage = page;
  document.title = `${PAGE_LABELS[page] || page} · Atlas`;
  document.body.dataset.page = isTrackingPage() ? 'Deliveries' : page;
  document.body.dataset.orderKind = trackingOrderKind();
  renderSidebar();
  renderHeaderStores();

  const app = $('.app');
  const mobile = matchMedia('(max-width:760px)').matches;
  $('.mn')?.setAttribute(
    'aria-expanded',
    String(mobile ? app.classList.contains('mobile-open') : !app.classList.contains('cl')),
  );

  const renderer = pageRenderers()[page];
  const keepCollectionNote = page === 'Collective Note'
    && (new URLSearchParams(location.search).get('view') === 'create' || new URLSearchParams(location.search).has('order'))
    && document.querySelector('#collection-note-root[data-mounted="true"]');
  const keepClaims = page === 'Manufacture Claims' && document.getElementById('manufacture-claims-root');
  const keepDashboardEditor = page === 'Dashboard' && !switchingPage && DashboardHome.preserveEditor();
  if (!keepCollectionNote && !keepClaims && !keepDashboardEditor) {
    $('#v').innerHTML = renderer();
    if (page === 'Collective Note' && document.getElementById('collection-note-root')) loadCollectionNote();
    if (page === 'Collective Note' && document.getElementById('collection-records')) loadCollectionRecords();
    if (page === 'Manufacture Claims') ManufactureClaims.mount();
  }
  if (switchingPage) {
    pageTransition?.cancel();
    const view = $('#v');
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches && typeof view.animate === 'function') {
      pageTransition = view.animate([
        { opacity: 0, transform: 'translateY(8px)' },
        { opacity: 1, transform: 'translateY(0)' },
      ], { duration: 260, easing: 'cubic-bezier(.2,.8,.2,1)' });
    }
  }
  DashboardListAutoScroll.attach();
  DashboardFailedCarousel.attach();
  DashboardHome.attachQuickLinks();

  if (isTrackingPage()) {
    animateHygienicFilter();
    if (document.body.dataset.live === 'true') loadTrackingPage(true);
    else rows();
  }
  if (page === 'Failed Deliveries') {
    if (document.body.dataset.live === 'true' && liveReady) loadFailedPage(true);
    else failedRows();
  }
  if (page === 'Dashboard') {
    if (dashboardSearchVisible) dres();
    DashboardHome.load();
  }

  if (page === 'Integrations' && integrationView === 'traffic') {
    loadSyncRunLog();
    loadSyncControl();
  }
  drawer();
  fitBrand();
}

function fitBrand() {
  const brand = $('.sd .brand');
  if (!brand) return;

  let size = 24;
  brand.style.fontSize = `${size}px`;
  while (brand.scrollWidth > brand.clientWidth && size > 12) {
    size -= 0.5;
    brand.style.fontSize = `${size}px`;
  }
}

function toggleSidebar() {
  const app = $('.app');
  const mobile = matchMedia('(max-width:760px)').matches;
  if (mobile) app.classList.toggle('mobile-open');
  else setSidebarCollapsed(!app.classList.contains('cl'));
  $('.mn')?.setAttribute(
    'aria-expanded',
    String(mobile ? app.classList.contains('mobile-open') : !app.classList.contains('cl')),
  );
}

document.addEventListener('click', event => {
  const app = $('.app');
  if (!app.classList.contains('detail-open')
    || event.target.closest('#dr, [data-app-action="toggle-sidebar"], [data-copy-special-instructions], [data-copy-order-number], [data-copy-order-reference], [data-copy-consignment-number], [data-copy-amazon-tracking], [data-copy-palletways-tracking]')) return;
  setSidebarCollapsed(true);
  app.classList.remove('mobile-open');
  $('.mn')?.setAttribute('aria-expanded', 'false');
}, true);

document.addEventListener('click', event => {
  const refundLink = event.target.closest('[data-view-credit-refund]');
  if (refundLink) {
    const id = refundLink.dataset.viewCreditRefund;
    const record = trackingCreditRefundMatch;
    if (record && String(record.id || record.order) === id && !get(id)) DeliveryStore.add({ ...record, id });
    go('Refund', '', '', { search: String(record?.order || id) });
    op(id);
    rows();
    return;
  }
  if (event.target.closest('[data-dashboard-search]')) {
    const input = $('#dq');
    if (input) { dq = input.value; input.focus(); dres(); }
    return;
  }
  const dashboardMore = event.target.closest('[data-dashboard-more]');
  if (dashboardMore) {
    loadDashboardMore(dashboardMore.dataset.dashboardMore);
    return;
  }
  const dashboardPrev = event.target.closest('[data-dashboard-prev]');
  if (dashboardPrev) {
    loadDashboardMore(dashboardPrev.dataset.dashboardPrev, -1);
    return;
  }
  if (event.target.closest('[data-tracking-today]')) {
    go('Deliveries', '', 'today');
    return;
  }
  const navLink = event.target.closest('[data-page-target]');
  if (navLink) {
    event.preventDefault();
    go(navLink.dataset.pageTarget);
    return;
  }

  if (event.target.closest('[data-app-action="toggle-sidebar"]')) {
    toggleSidebar();
  }
});

if (document.fonts?.ready) document.fonts.ready.then(fitBrand);

document.addEventListener('click', event => {
  const copyAmazonTracking = event.target.closest('[data-copy-amazon-tracking]');
  const copyPalletwaysTracking = event.target.closest('[data-copy-palletways-tracking]');
  if (copyPalletwaysTracking) {
    event.preventDefault();
    copyText(copyPalletwaysTracking.dataset.copyPalletwaysTracking, 'Tracking number copied');
    return;
  }
  if (copyAmazonTracking) {
    event.preventDefault();
    copyText(copyAmazonTracking.dataset.copyAmazonTracking, 'Tracking ID copied');
    return;
  }
  const copyConsignment = event.target.closest('[data-copy-consignment-number]');
  if (copyConsignment) {
    event.preventDefault();
    copyText(copyConsignment.dataset.copyConsignmentNumber, 'Consignment number copied');
    return;
  }
  const copyInstructions = event.target.closest('[data-copy-special-instructions]');
  if (copyInstructions) {
    event.preventDefault();
    copyText(copyInstructions.dataset.copySpecialInstructions, 'Special instructions copied');
    return;
  }
  const copyOrder = event.target.closest('[data-copy-order-number], [data-copy-order-reference]');
  if (copyOrder) {
    event.preventDefault();
    const reference = copyOrder.hasAttribute('data-copy-order-reference');
    copyText(reference ? copyOrder.dataset.copyOrderReference : copyOrder.dataset.copyOrderNumber,
      reference ? 'Order reference copied' : 'Order number copied');
    return;
  }
  const dateSort = event.target.closest('[data-table-date-sort]');
  if (dateSort) {
    toggleTableDateSort(dateSort.dataset.tableDateSort);
    return;
  }
  const todayRow = event.target.closest('[data-today-delivery]');
  if (todayRow) {
    const id = todayRow.dataset.todayDelivery;
    todayRow.classList.add('is-opening');
    todayRow.setAttribute('aria-busy', 'true');
    requestAnimationFrame(() => setTimeout(() => {
      const failed = Boolean(todayRow.closest('.db-list-card:last-child'));
      go(failed ? 'Failed Deliveries' : 'Deliveries', '', failed ? '' : 'today');
      dashboardSelectedId = id;
      op(id);
      if (failed) failedRows();
      else rows();
    }, 0));
    return;
  }
  const podButton = event.target.closest('[data-view-pod]');
  if (podButton) {
    op(podButton.dataset.viewPod);
    return;
  }
  if (event.target.closest('[data-failed-clear-filters]')) {
    fadeClearFilter(event.target.closest('[data-failed-clear-filters]'));
    failedCarrier = '';
    failedScope = '';
    failedStore = '';
    failedStatus = '';
    failedDateFrom = '';
    failedDateTo = '';
    failedScheduledFrom = '';
    failedScheduledTo = '';
    closeFailedDateFilter();
    R();
    return;
  }
  const clearFailedDates = event.target.closest('[data-failed-clear-dates]');
  if (clearFailedDates) {
    const scheduled = clearFailedDates.dataset.failedClearDates === 'scheduled';
    if (scheduled) {
      failedScheduledFrom = '';
      failedScheduledTo = '';
    } else {
      failedDateFrom = '';
      failedDateTo = '';
    }
    const menu = clearFailedDates.closest('[data-failed-date-filter]');
    menu.querySelectorAll('input[type="date"]').forEach(input => {
      if (input.id.startsWith(scheduled ? 'failed-scheduled-' : 'failed-date-')) input.value = '';
    });
    const label = menu.querySelector('.ui-select-label');
    if (label) label.textContent = failedCombinedDateLabel();
    closeFailedDateFilter();
    syncFailedClearButton();
    if (document.body.dataset.live === 'true') loadFailedPage(true);
    else failedRows();
    return;
  }
  const failedDateTrigger = event.target.closest('[data-failed-toggle-date]');
  if (failedDateTrigger) {
    const menu = failedDateTrigger.closest('[data-failed-date-filter]').querySelector('.ui-date-menu');
    const opening = menu.hidden;
    DeliveryFilters.closeAll();
    UiSelect.closeAll();
    closeFailedDateFilter();
    menu.hidden = !opening;
    failedDateTrigger.setAttribute('aria-expanded', String(opening));
    return;
  }
  const failedTab = event.target.closest('[data-failed-method]');
  if (failedTab) {
    const from = ScopeLiquid.capture();
    failedCarrier = failedTab.dataset.failedMethod;
    failedStore = '';
    failedStatus = '';
    dashboardSelectedId = null;
    R();
    ScopeLiquid.move(from);
    return;
  }
  if (DeliveryFilters.handleClick(event)) return;
  if (UiSelect.handleClick(event)) return;

  if (!event.target.closest('[data-ui-select-id]')) UiSelect.closeAll();
  if (!event.target.closest('[data-date-filter]')) DeliveryFilters.closeAll();
  if (!event.target.closest('[data-failed-date-filter]')) closeFailedDateFilter();

  if (!event.target.closest('.fx-menu')) {
    document.querySelectorAll('.fx-menu').forEach(menu => {
      menu.hidden = true;
    });
  }

  const deliveryRow = event.target.closest('.delivery-list-row[data-delivery-id]');
  if (deliveryRow && !event.target.closest('button, a, input, select, textarea')) {
    op(deliveryRow.dataset.deliveryId);
  }
  const trackingRow = event.target.closest('.tracking-row[data-delivery-id]');
  if (trackingRow && !event.target.closest('button, a, input, select, textarea')) {
    openLinkedOrderRow(trackingRow.dataset.deliveryId);
  }
});

document.addEventListener('input', event => {
  if (event.target.matches('[data-dashboard-failed-search]')) filterDashboardFailedOrders(event.target.value);
  if (event.target.matches('#failed-search')) {
    failedSearch = event.target.value;
    if (document.body.dataset.live === 'true') {
      clearTimeout(failedSearchTimer);
      failedSearchTimer = setTimeout(() => loadFailedPage(true), 250);
    } else failedRows();
  }
  DeliveryFilters.handleInput(event);
});

document.addEventListener('change', event => {
  if (event.target.closest('[data-failed-date-filter] input[type="date"]')) {
    const menu = event.target.closest('[data-failed-date-filter]');
    const scheduled = event.target.id.startsWith('failed-scheduled-');
    if (scheduled) {
      failedScheduledFrom = document.querySelector('#failed-scheduled-from')?.value || '';
      failedScheduledTo = document.querySelector('#failed-scheduled-to')?.value || '';
    } else {
      failedDateFrom = document.querySelector('#failed-date-from')?.value || '';
      failedDateTo = document.querySelector('#failed-date-to')?.value || '';
    }
    const label = menu.querySelector('.ui-select-label');
    if (label) label.textContent = failedCombinedDateLabel();
    syncFailedClearButton();
    if (document.body.dataset.live === 'true') loadFailedPage(true);
    else failedRows();
    return;
  }
  DeliveryFilters.handleChange(event);
});

window.addEventListener('tracking-visibility-change', () => {
  DashboardHome.invalidateVisibility();
  hygienicFilterAnimated = false;
  if (TrackingVisibility.enabled()) {
    trackingScope = compactFilter(filterValues(trackingScope).filter(value => value !== 'hygienic'));
    failedScope = compactFilter(filterValues(failedScope).filter(value => value !== 'hygienic'));
  }
  if (TrackingVisibility.wayfairEnabled() && fsrc === 'Wayfair') {
    fsrc = ''; fclassification = []; fs = '';
  }
  fstore = compactFilter(filterValues(fstore).filter(value => TrackingVisibility.includesStore(value)));
  failedStore = compactFilter(filterValues(failedStore).filter(value => TrackingVisibility.includesStore(value)));
  trackingRequest++;
  trackingLoaded = [];
  trackingOffset = 0;
  trackingTotal = 0;
  trackingHasMore = false;
  trackingLoadedQuery = '';
  trackingWidgetFacets = null;
  failedRequest++;
  failedLoaded = [];
  failedOffset = 0;
  failedTotal = 0;
  failedHasMore = false;
  dashboardSelectedId = null;
  if (page === 'Dashboard' || isTrackingPage() || page === 'Failed Deliveries' || page === 'Guidance') R();
});

window.addEventListener('popstate', event => {
  page = PAGE_URL[event.state?.page] ? event.state.page : Object.entries(PAGE_URL)
    .find(([, url]) => location.pathname.endsWith(url))?.[0] || 'Dashboard';
  trackingScope = isTrackingPage() && new URLSearchParams(location.search).get('view') === 'today'
    ? 'today' : '';
  dashboardWidgetFilter = isTrackingPage() ? new URLSearchParams(location.search).get('dashboard_widget') || '' : '';
  trackingWidgetFacets = null;
  fsrc = dashboardWidgetFilter ? new URLSearchParams(location.search).get('carrier') || '' : '';
  fstore = dashboardWidgetFilter ? compactFilter(new URLSearchParams(location.search).getAll('store')) : '';
  fbookedIn = '';
  applyDashboardWidgetControls();
  sel = null;
  dashboardSelectedId = null;
  R();
});

document.addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    const trackingRow = event.target.closest('.tracking-row[data-delivery-id]');
    if (trackingRow && event.target === trackingRow) {
      openLinkedOrderRow(trackingRow.dataset.deliveryId);
      return;
    }
    const deliveryRow = event.target.closest('.delivery-list-row[data-delivery-id]');
    if (deliveryRow) {
      op(deliveryRow.dataset.deliveryId);
      return;
    }
  }

  if (event.key !== 'Escape') return;

  if (UiSelect.hasOpenMenu() || DeliveryFilters.hasOpenMenu()) {
    UiSelect.closeAll();
    DeliveryFilters.closeAll();
    closeFailedDateFilter();
    return;
  }
  if (document.querySelector('[data-failed-date-filter] .ui-date-menu:not([hidden])')) {
    closeFailedDateFilter();
    return;
  }

  if (sel) {
    sel = null;
    drawer();
    return;
  }

});

applyDashboardWidgetControls();
R();
if (document.body.dataset.live === 'true') {
  const status = document.createElement('div');
  status.className = 'live-data-status';
  const sourceButton = document.createElement('button');
  sourceButton.type = 'button';
  sourceButton.className = 'source-info-button';
  sourceButton.textContent = 'Data sources';
  sourceButton.setAttribute('aria-expanded', 'false');
  sourceButton.setAttribute('aria-controls', 'source-info-panel');
  const sourcePanel = document.createElement('div');
  sourcePanel.id = 'source-info-panel';
  sourcePanel.className = 'source-info-panel';
  sourcePanel.hidden = true;
  sourceButton.addEventListener('click', () => {
    sourcePanel.hidden = !sourcePanel.hidden;
    sourceButton.setAttribute('aria-expanded', String(!sourcePanel.hidden));
    if (!sourcePanel.hidden) { renderSourceInfo(); loadSyncRunLog(); }
  });
  const dismissSourceInfo = () => {
    sourcePanel.hidden = true;
    sourceButton.setAttribute('aria-expanded', 'false');
  };
  document.addEventListener('click', event => {
    if (!status.contains(event.target)) dismissSourceInfo();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !sourcePanel.hidden) {
      dismissSourceInfo();
      sourceButton.focus();
    }
  });
  const showSourceInfo = entries => {
    const heading = document.createElement('h2');
    heading.textContent = 'Last sync';
    const header = document.createElement('header');
    header.className = 'source-info-heading';
    const range = document.createElement('div');
    range.className = 'source-info-range';
    range.setAttribute('role', 'status');
    range.setAttribute('aria-label', 'Order date range');
    const rangeLabel = document.createElement('span');
    rangeLabel.textContent = 'Order date range';
    const rangeValue = document.createElement('strong');
    rangeValue.textContent = integrationOrderRangeLabel(liveSummary);
    range.append(rangeLabel, rangeValue);
    header.append(heading, range);
    const sections = entries.map(([label, description]) => {
      const section = document.createElement('section');
      section.className = 'source-info-entry';
      const title = document.createElement('strong');
      title.textContent = label;
      const detail = document.createElement('p');
      detail.textContent = description;
      section.append(title, detail);
      return section;
    });
    sourcePanel.replaceChildren(header, ...sections);
  };
  const renderSourceInfo = () => {
    sourceButton.textContent = 'Data sources';
    if (!syncRunLog) {
      showSourceInfo([['Last sync', 'Loading…']]);
      return;
    }
    const entries = [];
    const latest = new Map();
    // The shared activity endpoint returns newest runs first.
    for (const row of syncRunLog.rows || []) {
      const name = String(row.integration || '').trim() || 'Unknown integration';
      if (!latest.has(name)) latest.set(name, row);
    }
    for (const [name, row] of latest) {
      entries.push([name, row.startedAt || 'Not recorded']);
    }
    if (!latest.size) entries.push(['Last sync', syncRunLog.unavailable ? 'Unavailable' : 'Not recorded']);
    showSourceInfo(entries);
  };
  document.addEventListener('deliverydesk:sync-run-log', renderSourceInfo);
  document.addEventListener('deliverydesk:ready', renderSourceInfo);
  renderSourceInfo();
  loadSyncRunLog();
  setInterval(loadSyncRunLog, 5 * 60 * 1000);
  status.append(sourceButton, sourcePanel);
  const headerActions = document.querySelector('.hd .hr');
  headerActions?.insertBefore(status, headerActions.querySelector('[aria-label="Profile"]'));
  const refreshLive = async () => {
    if (refreshLive.inFlight) return;
    refreshLive.inFlight = true;
    liveSummaryError = false;
    try {
      const result = await DeliveryApi.summary();
      if ((result.failedTotal || 0) > 0 && !(result.failedPreview || []).length) {
        try {
          const failedPage = await DeliveryApi.list({ issues: 1, dashboard_scope: 'failed', limit: DELIVERY_PAGE_SIZE });
          result.failedPreview = (failedPage.deliveries || []).filter(delivery =>
            isGlobalException(delivery) && !isCreditRefundRecord(delivery));
          if (!result.failedPreview.length) result.failedPreviewError = 'The failed-delivery request returned no failed records.';
        } catch (previewError) {
          result.failedPreviewError = previewError.message;
        }
      }
      const sourceTimes = result.sourceUpdatedAt || {};
      const formatTime = value => value
        ? new Date(value).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' })
        : result.syncing ? 'Refreshing…' : 'Not recorded';
      const selectedDelivery = sel ? get(sel) : null;
      const visiblePageRecords = isTrackingPage() ? trackingLoaded
        : page === 'Failed Deliveries' ? failedLoaded : [];
      DeliveryStore.hydrate({ deliveries: [...(result.today || []), ...(result.failedPreview || []), ...visiblePageRecords], activity: [], integrations: [
        ['OptimoRoute', formatTime(sourceTimes.optimoroute), result.stale ? 'wn' : result.optimorouteUnavailable ? 'er' : 'ok', 'Tracking unavailable'],
        ['Palletways', formatTime(sourceTimes.palletways), result.stale ? 'wn' : result.palletwaysUnavailable ? 'er' : 'ok', 'Updates unavailable'],
        ['Courier Issues', formatTime(sourceTimes.courierIssues), result.stale ? 'wn' : result.courierIssuesUnavailable ? 'er' : 'ok', 'Updates unavailable'],
        ['XDP', 'Not connected', 'er', 'Not connected'],
      ] });
      if (selectedDelivery) {
        const refreshedSelection = get(sel);
        if (refreshedSelection) {
          Object.assign(refreshedSelection, { ...selectedDelivery, ...refreshedSelection });
        } else {
          DeliveryStore.add(selectedDelivery);
        }
      }
      D = DeliveryStore.deliveries();
      S = DeliveryStore.integrations();
      const previousSync = liveSummary?.syncedAt;
      const previousTotal = liveSummary?.total;
      const previousFailedTotal = liveSummary?.failedTotal;
      const previousTodayTotal = liveSummary?.todayTotal;
      const previousFilterFacets = JSON.stringify(liveSummary?.filterFacets);
      const wasReady = liveReady;
      liveSummary = result;
      dashboardOffsets.ongoing = 0;
      dashboardOffsets.failed = 0;
      liveReady = true;
      if (page === 'Integrations' || !wasReady || result.syncedAt !== previousSync || result.total !== previousTotal
        || result.failedTotal !== previousFailedTotal || result.todayTotal !== previousTodayTotal
        || JSON.stringify(result.filterFacets) !== previousFilterFacets) R();
      if (result.syncing) setTimeout(refreshLive, 5000);
    } catch (error) {
      liveSummaryError = true;
      if (page === 'Dashboard' || page === 'Integrations') R();
      // Tracking has its own request and error state; an overview failure must
      // not erase a working table or interrupt its independent load.
      if (page === 'Failed Deliveries') {
        const list = $('#failed-list');
        if (list) list.innerHTML = `<tr><td colspan="10" class="tracking-empty">${esc(`Delivery data unavailable: ${error.message}`)}</td></tr>`;
      }
    } finally {
      refreshLive.inFlight = false;
      document.dispatchEvent(new CustomEvent('deliverydesk:ready', {
        detail: { unavailable: liveSummaryError, syncing: Boolean(liveSummary?.syncing) },
      }));
    }
  };
  refreshLive();
  setInterval(refreshLive, 5 * 60 * 1000);
}
setInterval(() => {
  if (page !== 'Dashboard') return;
  const dateLabel = document.querySelector('#db-current-date');
  if (!dateLabel) return;
  if (dateLabel.dateTime !== localDateKey()) {
    R();
    return;
  }
  const clock = document.querySelector('#db-current-time');
  if (clock) clock.textContent = localClockLabel();
}, 30000);


document.addEventListener('keydown', event => {
  if (!['Enter', ' '].includes(event.key)) return;
  const card = event.target.closest('.refund-discovery[data-view-credit-refund]');
  if (!card) return;
  event.preventDefault();
  card.click();
});
