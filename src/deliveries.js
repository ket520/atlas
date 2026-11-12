// Animate column switches without replacing unaffected rows or cells.
let deliveryColumnSwapBusy = false;
let deliveryColumnSwapUpdating = false;
function renderDeliveryRows(list, markup) {
  if (!deliveryColumnSwapUpdating) { list.innerHTML = markup; return; }
  const next = list.cloneNode(false);
  next.innerHTML = markup;
  if (next.children.length !== list.children.length || [...next.children].some((row, i) => row.children.length !== list.children[i].children.length)) {
    list.innerHTML = markup; return;
  }
  [...next.children].forEach((row, i) => {
    const current = list.children[i];
    [...current.attributes].forEach(attr => { if (!row.hasAttribute(attr.name)) current.removeAttribute(attr.name); });
    [...row.attributes].forEach(attr => current.setAttribute(attr.name, attr.value));
    [...row.children].forEach((cell, column) => {
      const existing = current.children[column];
      if (existing.innerHTML !== cell.innerHTML) existing.innerHTML = cell.innerHTML;
      [...cell.attributes].forEach(attr => existing.setAttribute(attr.name, attr.value));
    });
  });
}
async function swapDeliveryColumn(selector, update) {
  if (deliveryColumnSwapBusy) return;
  deliveryColumnSwapBusy = true;
  const headers = [...document.querySelectorAll(selector)].map(button => button.closest('th'));
  const cells = () => headers.flatMap(header => [header, ...header.closest('table').querySelectorAll('tbody tr > td:nth-child(' + (header.cellIndex + 1) + '):not([colspan])')]);
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  let outgoing = [];
  let wordWrappers = [];
  const unwrapWords = () => {
    wordWrappers.forEach(word => word.replaceWith(...word.childNodes));
    wordWrappers = [];
  };
  const words = () => {
    cells().forEach(cell => {
      const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
      const textNodes = [];
      while (walker.nextNode()) {
        const node = walker.currentNode;
        if (node.textContent.trim() && !node.parentElement.closest('svg, .tracking-number-switch, .delivery-item-switch, .qd-customer-copy')) textNodes.push(node);
      }
      textNodes.forEach(node => {
        const word = document.createElement('span');
        word.className = 'delivery-column-swap-word';
        word.style.display = 'inline-block';
        node.replaceWith(word);
        word.append(node);
        wordWrappers.push(word);
      });
    });
    return wordWrappers;
  };
  try {
    if (!reduced) {
      outgoing = words().map(word => word.animate([{transform: 'translateX(0)'}, {transform: 'translateX(-24px)'}], {duration: 180, easing: 'ease-in', fill: 'forwards'}));
      await Promise.all(outgoing.map(animation => animation.finished.catch(() => {})));
    }
    unwrapWords();
    deliveryColumnSwapUpdating = true;
    update();
    deliveryColumnSwapUpdating = false;
    outgoing.forEach(animation => animation.cancel());
    if (!reduced) await Promise.all(words().map(word => word.animate([{transform: 'translateX(24px)'}, {transform: 'translateX(0)'}], {duration: 260, easing: 'cubic-bezier(.22,1,.36,1)'}).finished.catch(() => {})));
    document.querySelector(selector)?.focus({preventScroll: true});
  } finally {
    outgoing.forEach(animation => animation.cancel());
    unwrapWords();
    deliveryColumnSwapUpdating = false;
    deliveryColumnSwapBusy = false;
  }
}

function splitDeliveryAddress(address) {
  const text = String(address || '').trim();
  const postcode = text.match(/\b([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$/i);

  if (!postcode) {
    return {
      primary: text || 'Address not available',
      secondary: '',
    };
  }

  return {
    primary: text.slice(0, postcode.index).replace(/[\s,]+$/, '') || text,
    secondary: postcode[1].toUpperCase().replace(/\s+/, ' '),
  };
}

let palletwaysNumberType = 'consignment';
try {
  if (localStorage.getItem('atlas-palletways-number-type') === 'tracking')
    palletwaysNumberType = 'tracking';
} catch {}

function palletwaysNumberCell(delivery) {
  const tracking = palletwaysNumberType === 'tracking';
  const value = tracking
    ? delivery.palletwaysSheetTrackingNumber
    : delivery.palletwaysSheetConsignmentNumber;
  return `<span class="tracking-order-number"><span>${esc(value || '\u2014')}</span>${value ? `<button type="button" class="qd-customer-copy" ${tracking ? 'data-copy-palletways-tracking' : 'data-copy-consignment-number'}="${esc(value)}" aria-label="Copy ${tracking ? 'tracking' : 'consignment'} number ${esc(value)}" title="Copy ${tracking ? 'tracking' : 'consignment'} number">${ico('copy', 13, 1.8)}</button>` : ''}</span>`;
}

function palletwaysBookedInFilterValue(delivery) {
  const booked = String(delivery.palletwaysSheetBookedIn || '').trim().toLowerCase();
  if (booked !== 'no') return booked;
  return String(delivery.deliveryMethodRaw || '').trim().toLowerCase() === 'palletways next day' ? 'no' : 'not-yet';
}

function palletwaysBookedInCell(delivery) {
  const booked = String(delivery.palletwaysSheetBookedIn || '').trim().toLowerCase();
  if (booked === 'no') {
    return palletwaysBookedInFilterValue(delivery) === 'no' ? 'N/A' : 'Not Yet';
  }
  if (booked !== 'yes') return '\u2014';
  const date = String(delivery.palletwaysSheetBookInDate || '').trim();
  const time = String(delivery.palletwaysSheetBookInTime || '').trim();
  return `<span class="tracking-cell-line">${esc(date || '\u2014')}</span>${time ? `<small class="tracking-cell-line mut">${esc(time)}</small>` : ''}`;
}

function palletwaysNumberHeading() {
  const tracking = palletwaysNumberType === 'tracking';
  const next = tracking ? 'Consignment No' : 'Tracking ID';
  return `<div class="tracking-number-heading"><span>${tracking ? 'Tracking ID' : 'Consignment No'}</span><button type="button" class="tracking-number-switch" data-palletways-number-type aria-label="Show ${next}" title="Switch to ${next}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/></svg></button></div>`;
}
document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-palletways-number-type]');
  if (!button) return;
  event.preventDefault();
  void swapDeliveryColumn('[data-palletways-number-type]', () => {
  palletwaysNumberType = palletwaysNumberType === 'tracking' ? 'consignment' : 'tracking';
  try {
    localStorage.setItem('atlas-palletways-number-type', palletwaysNumberType);
  } catch {}
  button.closest('th').innerHTML = palletwaysNumberHeading();
  rows();
  });
});

let trackingDateType = 'scheduled';
try {
  if (localStorage.getItem('atlas-tracking-date-type') === 'dispatch') trackingDateType = 'dispatch';
} catch {}

function trackingDateValue(delivery) {
  return trackingDateType === 'dispatch'
    ? delivery.dispatchDate || delivery.carrierIssueDispatchDate || ''
    : delivery.date;
}

function trackingDateSortDirection() {
  return trackingDateSortType === trackingDateType ? trackingDateSort : '';
}

function trackingDateHeading() {
  const label = trackingDateType === 'dispatch' ? 'Dispatch' : 'Scheduled';
  const next = trackingDateType === 'dispatch' ? 'Scheduled date' : 'Dispatch date';
  return `<div class="tracking-number-heading"><button class="table-date-sort" type="button" data-table-date-sort="tracking" aria-label="Sort ${label.toLowerCase()} date"><span>${label}<br>date</span><span class="table-date-sort-indicator" aria-hidden="true">${dateSortIcon(trackingDateSortDirection())}</span></button><button type="button" class="tracking-number-switch" data-tracking-date-type aria-label="Show ${next}" title="Switch to ${next}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/></svg></button></div>`;
}

function trackingDateCell(delivery) {
  const value = trackingDateValue(delivery);
  const date = esc(value ? hd(value) : '\u2014');
  if (trackingDateType === 'dispatch') {
    const timestamp = delivery.dispatchDate
      ? delivery.dispatchDateTime
      : delivery.carrierIssueDispatchDateTime;
    const time = /[T ](\d{2}:\d{2}(?::\d{2})?)/.exec(timestamp || '')?.[1];
    return `${date}${time ? `<small class="tracking-cell-line mut">${esc(time)}</small>` : ''}`;
  }
  return `${date}${delivery.amazonScheduledAt ? `<small class="tracking-cell-line mut">Scheduled ${esc(optimoClock(delivery.amazonScheduledAt))} UK time</small>` : delivery.providerScheduledAt ? `<small class="tracking-cell-line mut">Scheduled ${esc(optimoClock(delivery.providerScheduledAt) || optimoTime(delivery.providerScheduledAt))}</small>` : ''}${delivery.eta ? `<small class="tracking-cell-line mut">ETA ${esc(optimoClock(delivery.eta) || optimoTime(delivery.eta))}</small>` : ''}`;
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-tracking-date-type]');
  if (!button) return;
  event.preventDefault();
  void swapDeliveryColumn('[data-tracking-date-type]', () => {
  trackingDateType = trackingDateType === 'scheduled' ? 'dispatch' : 'scheduled';
  try { localStorage.setItem('atlas-tracking-date-type', trackingDateType); } catch {}
  const header = button.closest('th');
  header.innerHTML = trackingDateHeading();
  header.setAttribute('aria-sort', trackingDateSortDirection() === 'asc' ? 'ascending' : trackingDateSortDirection() === 'desc' ? 'descending' : 'none');
  rows();
  });
});

let trackingLoaded = [];
let trackingRelations = null;
let trackingCreditRefundMatch = null;
let trackingOffset = 0;
let trackingTotal = 0;
let trackingHasMore = false;
let trackingRequest = 0;
let trackingLoadedQuery = '';
let trackingSearchTimer = null;
let trackingLoading = document.body.dataset.live === 'true';
let trackingLoadError = false;
let dashboardSelectedId = null;
let liveSummary = null;
let liveReady = false;
let liveSummaryError = false;
let trackingDateSort = 'desc';
let trackingDateSortType = 'scheduled';
let failedDateSort = '';
let failedDateSortType = 'issue';
const orderCreatedDate = delivery => delivery.orderDateTime || delivery.orderDate || '';

function dateSortIcon(direction) {
  const up = '<path d="m4 7 3-3 3 3"/><path d="M7 4v9"/>';
  const down = '<path d="m4 10 3 3 3-3"/><path d="M7 4v9"/>';
  const both = '<path d="m4 6 3-3 3 3"/><path d="m4 12 3 3 3-3"/><path d="M7 3v12"/>';
  return `<svg viewBox="0 0 14 18" width="14" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${direction === 'asc' ? up : direction === 'desc' ? down : both}</svg>`;
}

function sortDeliveriesByDate(deliveries, direction, dateOf) {
  if (!direction) return deliveries;
  return [...deliveries].sort((a, b) => {
    const first = String(dateOf(a) || '');
    const second = String(dateOf(b) || '');
    if (!first || !second) return first ? -1 : second ? 1 : 0;
    return (direction === 'asc' ? 1 : -1) * first.localeCompare(second);
  });
}

function toggleTableDateSort(table) {
  const failed = table === 'failed' || table === 'failed-created';
  const type = table.endsWith('-created') ? 'created' : failed ? 'issue' : trackingDateType;
  if (failed) {
    failedDateSort = failedDateSortType === type && failedDateSort === 'desc' ? 'asc' : 'desc';
    failedDateSortType = type;
    if (document.body.dataset.live === 'true') loadFailedPage(true);
    else failedRows();
  } else {
    trackingDateSort = trackingDateSortType === type && trackingDateSort === 'desc' ? 'asc' : 'desc';
    trackingDateSortType = type;
    if (document.body.dataset.live === 'true') loadTrackingPage(true);
    else rows();
  }
  document.querySelectorAll('[data-table-date-sort]').forEach(button => {
    const target = button.dataset.tableDateSort;
    const direction = target === 'tracking' ? trackingDateSortDirection()
      : target === 'failed' ? (failedDateSortType === 'issue' ? failedDateSort : '')
      : target === 'failed-created' ? (failedDateSortType === 'created' ? failedDateSort : '')
      : trackingDateSortType === 'created' ? trackingDateSort : '';
    button.closest('th')?.setAttribute('aria-sort', direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none');
    const indicator = button.querySelector('.table-date-sort-indicator');
    if (indicator) indicator.innerHTML = dateSortIcon(direction);
  });
}

const courierAssets = {
  Palletways: ['palletways.jpg', '#164b87'],
  AMZ: ['amz.png', '#159bb9'],
  XDP: ['xdp.jpg', '#00a9dc'],
  Yodel: ['yodel.jpg', '#83b900'],
  Stopstart: ['stopstart.jpg', '#d5542d'],
  Wayfair: ['wayfair.jpg', '#8515a5'],
};

const isMainTrackingMethod = (value) =>
  value === SELF_DELIVERY_GROUP || Object.prototype.hasOwnProperty.call(courierAssets, value);

function selfDeliveryCourierCard(count, active, failed = false) {
  return `<button class="tracking-courier-card tracking-courier-self fx-tab ${active ? 'on' : ''}" type="button" role="tab" aria-selected="${active}" aria-label="${esc(SELF_DELIVERY_GROUP)}, ${count} deliveries" title="${esc(SELF_DELIVERY_GROUP)}" ${failed ? `data-failed-method="${esc(SELF_DELIVERY_GROUP)}"` : `data-delivery-filter-action="method" data-value="${esc(SELF_DELIVERY_GROUP)}"`} style="--courier-brand-color:var(--gr)">
    <span class="tracking-courier-logo">${ico('truck', 24)}<span class="tracking-courier-self-label">${esc(SELF_DELIVERY_GROUP)}</span></span>
    <span class="tracking-courier-count">${count}</span>
  </button>`;
}

const TRACKING_GENERAL_OPTIONS = [
  ['', 'All'],
  ['today', 'Today Deliveries'],
  ...[
    'Charge Pending (Remote Postcode)',
    'Collect in Person',
    'Do Not Pick Yet',
    'Cancelled',
    'On Hold',
    'Unassigned',
  ].map((value) => [value, value]),
  ['hygienic', 'Hygienic LTD'],
];
const TRACKING_SCOPE_OPTIONS = [
  ...TRACKING_GENERAL_OPTIONS.filter(([value]) => value !== 'Collect in Person'),
  ['SUPPLIER', 'Supplier'],
];

function trackingMatchesScope(item, scope = trackingScope) {
  if (Array.isArray(scope))
    return !scope.length || scope.some((value) => trackingMatchesScope(item, value));
  if (!scope) return true;
  if (scope === 'hygienic')
    return (
      String(item.orderType || '')
        .trim()
        .toLowerCase() === 'sales'
    );
  if (scope === 'today') return Boolean(item.today);
  if (scope === 'Cancelled') return item.carrier === 'Cancelled' || item.status === 'Cancelled';
  if (scope === 'On Hold') return item.carrier === 'On Hold' || item.status === 'Unassigned';
  return item.carrier === scope;
}

function trackingFilterFacets() {
  if (document.body.dataset.live === 'true')
    return (
      ((dashboardWidgetFilter || trackingOrderKind()) ? trackingWidgetFacets : null) ||
      liveSummary?.filterFacets ||
      []
    ).filter(
      (item) =>
        (page !== 'Deliveries' || !(item.creditRefund || item.orderRelationKind === 'Credit/Refund' || item.relatedKind === 'Credit/Refund')) &&
        TrackingVisibility.includesOrderType(item.orderType) &&
        TrackingVisibility.includesCarrier(item.carrier) &&
        TrackingVisibility.includesStore(item.purchaseStore) &&
        TrackingVisibility.includesPalletwaysClassification(
          item.carrier,
          item.palletwaysClassification,
        ),
    );
  return D.filter(
    (delivery) =>
      (page !== 'Deliveries' || !isCreditRefundRecord(delivery)) &&
      TrackingVisibility.includesOrderType(delivery.salesActivityDetails?.['Order Type']) &&
      TrackingVisibility.includesCarrier(delivery.carrier) &&
      TrackingVisibility.includesStore(purchaseChannel(delivery)) &&
      TrackingVisibility.includesPalletwaysClassification(
        delivery.carrier,
        delivery.palletwaysDetails?.classification,
      ),
  ).map((delivery) => ({
    carrier: delivery.carrier,
    status: trackingStatus(delivery.st),
    overallStatus: overallTrackingStatus(delivery),
    creditRefund: isCreditRefundRecord(delivery),
    palletwaysDepotCount: palletwaysDepotEligible(delivery) ? 1 : 0,
    rawStatus: delivery.rawStatus,
    orderType: delivery.salesActivityDetails?.['Order Type'],
    purchaseStore: purchaseChannel(delivery),
    palletwaysClassification: delivery.palletwaysDetails?.classification,
    classification: delivery.deliveryMethodRaw,
    amazonStatus: delivery.amazonSheetStatus || delivery.amazonStatus,
    stopstartStatus: delivery.stopstartStatus,
    xdpStatus: delivery.xdpStatus,
    palletwaysSheetStatus: delivery.palletwaysSheetStatus,
    palletwaysSheetMatched: delivery.palletwaysSheetMatched,
    count: 1,
    today: deliveryIsToday(delivery),
  }));
}

function deliveryIsToday(delivery) {
  const day = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/London',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date());
  const status = String(delivery.st || '').toLowerCase();
  if (['failed', 'rejected', 'lost', 'cancelled', 'return'].includes(status)) return false;
  const carrier = delivery.carrier;
  const source = String(
    carrier === 'XDP'
      ? delivery.xdpStatus || ''
      : carrier === 'Stopstart'
        ? delivery.stopstartStatus || ''
        : carrier === 'Palletways'
          ? delivery.palletwaysSheetStatus || ''
          : delivery.amazonSheetStatus || delivery.amazonStatus || '',
  )
    .trim()
    .toUpperCase()
    .replace(/_/g, ' ');
  if (
    [
      'DAMAGE',
      'DELETE',
      'NOT RECEIVED',
      'FAILED',
      'REJECTED',
      'LOST',
      'UNDELIVERABLE',
      'CANCELLED',
      'RETURN',
    ].includes(source)
  )
    return false;
  if (
    (carrier === 'Stopstart' && source === 'EXPECTED TODAY') ||
    (carrier === 'XDP' && source === 'NEXT STOP') ||
    (carrier === 'Palletways' && source === 'OUT FOR DELIVERY')
  )
    return true;
  const dates = [
    delivery.date,
    delivery.amazonScheduledAt,
    delivery.providerPlannedDate,
    delivery.palletwaysDetails?.dueAt,
    delivery.stopstartDetails?.expectedDate,
  ];
  return (
    dates.some(
      (value) =>
        String(value || '')
          .trim()
          .slice(0, 10) === day,
    ) &&
    (['scheduled', 'out for delivery', 'delivered'].includes(status) ||
      ['XDP', 'Stopstart'].includes(carrier))
  );
}

function availableTrackingStores() {
  const present = new Set(
    trackingFilterFacets()
      .filter(
        (item) =>
          item.count > 0 &&
          trackingMatchesScope(item) &&
          matchesDeliveryCarrier(item.carrier, fsrc) &&
          (!fclassification.length || fclassification.includes(item.classification)),
      )
      .map((item) => item.purchaseStore)
      .filter(Boolean),
  );
  return PURCHASE_STORES.filter((store) => present.has(store));
}

function palletwaysFilterStatus(sheetStatus, fallbackStatus) {
  const sheet = palletwaysSpecificStatus(sheetStatus);
  if (sheet === 'Unscheduled') return 'Unscheduled';
  const value = sheet;
  return String(value || '')
    .trim()
    .toLowerCase() === 'delivered'
    ? 'Delivered'
    : sheet
      ? `palletways:${sheet}`
      : fallbackStatus || '';
}

function trackingLevelCounts() {
  const facets = trackingFilterFacets();
  const scoped = facets.filter((item) => trackingMatchesScope(item));
  const carriers = {};
  scoped.forEach((item) => {
    const carrier = SELF_DELIVERY_CARRIERS.includes(item.carrier)
      ? SELF_DELIVERY_GROUP
      : item.carrier;
    carriers[carrier] = (carriers[carrier] || 0) + item.count;
  });
  const statuses = {};
  scoped
    .filter(
      (item) =>
        matchesDeliveryCarrier(item.carrier, fsrc) &&
        filterIncludes(fstore, item.purchaseStore) &&
        (!fclassification.length || fclassification.includes(item.classification)),
    )
    .forEach((item) => {
      const status =
        trackingOrderKind() === 'refund' ? refundStatusValue(item) : fsrc === 'AMZ' && item.amazonStatus
          ? `amazon:${item.amazonStatus}`
          : fsrc === 'Stopstart' && item.stopstartStatus
            ? `stopstart:${item.stopstartStatus}`
            : fsrc === 'XDP' && item.xdpStatus
              ? `xdp:${item.xdpStatus}`
              : fsrc === 'Palletways'
                ? palletwaysFilterStatus(item.palletwaysSheetStatus, palletwaysOwFallback(item))
                : usesGlobalTrackingStatus() ? overallTrackingStatus(item) : item.status;
      if (status) statuses[status] = (statuses[status] || 0) + item.count;
    });
  return {
    facets,
    carriers,
    statuses,
    scopeTotal: scoped.reduce((sum, item) => sum + item.count, 0),
  };
}

let hygienicFilterAnimated = false;

function animateHygienicFilter() {
  const filter = document.querySelector(
    '[data-delivery-filter-action="general"][data-value="hygienic"]',
  );
  if (!filter || hygienicFilterAnimated) return;
  hygienicFilterAnimated = true;
  if (
    matchMedia('(prefers-reduced-motion: reduce)').matches ||
    typeof filter.animate !== 'function'
  )
    return;
  filter.animate(
    [
      {
        opacity: 0,
        transform: 'translateY(8px) scale(.75)',
      },
      {
        opacity: 1,
        transform: 'translateY(-3px) scale(1.08)',
        offset: 0.65,
      },
      {
        opacity: 1,
        transform: 'translateY(0) scale(1)',
      },
    ],
    {
      duration: 500,
      easing: 'cubic-bezier(.2,.8,.3,1)',
    },
  );
}

function vDel() {
  const sections = [['Delivery methods', []]];
  const levelCounts = trackingLevelCounts();
  const scopedMethods = Object.entries(levelCounts.carriers)
    .filter(([, count]) => count > 0)
    .map(([value, count]) => [value, value === 'AMZ' ? 'Amazon Shipping' : value, count]);
  const methodTabs = [
    ['', 'All methods', levelCounts.scopeTotal],
  ];
  const courierOrder = ['Palletways', 'AMZ', 'XDP', 'Stopstart', 'Yodel', 'Wayfair'];
  const courierTabs = scopedMethods
    .filter(([value]) => courierAssets[value])
    .sort(([first], [second]) => courierOrder.indexOf(first) - courierOrder.indexOf(second));
  const mainMethodTotal = scopedMethods.reduce((sum, [value, , count]) =>
    sum + (isMainTrackingMethod(value) ? count : 0), 0);
  const renderScopeTab = ([value, label, count], level = 'general') => {
    const active = value === (level === 'general' ? trackingScope : fsrc);
    return `<button class="fx-tab ${active ? 'on' : ''}" type="button" role="tab" aria-selected="${active}" data-delivery-filter-action="${level}" data-value="${esc(value)}"><span class="scope-option-label">${esc(label)}</span><span>${count}</span></button>`;
  };
  return `<div class="delivery-page-head"><h2 class="fx-title">${esc(trackingOrderKind() ? page : 'Tracking')}</h2>${dashboardWidgetFilter && dashboardWidgetFilter !== 'palletways-depot-3days' ? `<button class="dash-cohort-filter" type="button" data-dash-clear-cohort>${esc(DashboardHome.title(dashboardWidgetFilter))} ${ico('x', 13)}</button>` : ''}</div>
    ${dashboardWidgetFilter && dashboardWidgetFilter !== 'palletways-depot-3days' && dashboardWidgetControls().conditions ? `<p class="tracking-widget-conditions" role="status"><strong>Active filters:</strong> ${esc(dashboardWidgetControls().conditions)}</p>` : ''}
    <div class="delivery-scope-row tracking-scope-sections">
      ${sections
        .map(
          ([
            heading,
            options,
          ]) => `<section class="tracking-scope-section ${heading === 'General & non-delivery' ? 'tracking-general-section' : ''}" aria-label="${heading}">
        <h3 class="tracking-scope-heading">${heading}</h3>
        <div class="fx-tabs" role="tablist" aria-label="${heading}">
          ${(heading === 'Delivery methods' ? methodTabs : options).map((option) => renderScopeTab(option, heading === 'Delivery methods' ? 'method' : 'general')).join('')}
        </div>
        ${
          heading === 'Delivery methods'
            ? `<div class="tracking-courier-grid" role="tablist" aria-label="Courier delivery methods">
          ${levelCounts.carriers[SELF_DELIVERY_GROUP] ? selfDeliveryCourierCard(levelCounts.carriers[SELF_DELIVERY_GROUP], fsrc === SELF_DELIVERY_GROUP) : ''}
          ${courierTabs
            .map(
              ([
                value,
                label,
                count,
              ]) => `<button class="tracking-courier-card fx-tab ${value === fsrc ? 'on' : ''}" type="button" role="tab" aria-selected="${value === fsrc}" aria-label="${esc(label)}, ${count} deliveries" title="${esc(label)} · ${count} deliveries" data-delivery-filter-action="method" data-value="${esc(value)}" style="--courier-brand-color:${courierAssets[value][1]}">
            <span class="tracking-courier-logo"><img src="/assets/${courierAssets[value][0]}" alt="" width="110" height="35" decoding="async"></span>
            <span class="tracking-courier-count">${count}</span>
          </button>`,
            )
            .join('')}
        </div>`
            : ''
        }
      </section>`,
        )
        .join('')}
    </div>
    <p class="tracking-method-totals" aria-label="Delivery method count reconciliation">Main delivery methods (${mainMethodTotal.toLocaleString()}) + Other Delivery Method (${(levelCounts.scopeTotal - mainMethodTotal).toLocaleString()}) = All methods (${levelCounts.scopeTotal.toLocaleString()})</p>
    ${DeliveryFilters.render()}
    <div class="tracking-table-wrap tracking-records-scroll" tabindex="0" role="region" aria-label="Tracking table, scroll horizontally to view all columns">
      <table class="tracking-table current-table" data-tracking-carrier="${esc(fsrc)}"><thead><tr>
        <th>Order No</th>${trackingOrderKind() === 'replacement' ? '<th title="Sales Activity column N: Original order Number">Original Order Number</th>' : '<th>Order Ref No</th>'}${trackingOrderKind() === 'refund' ? '<th title="Sales Activity column R: Gross (base)">Refund Amount</th>' : ''}<th>Customer &amp; contact</th>${fsrc === 'Palletways' ? `<th>${palletwaysNumberHeading()}</th><th ${deliveryItemColumnSortAttributes()}>${deliveryItemColumnHeading()}</th><th>Postcode</th><th data-date-sort-header="tracking" aria-sort="${trackingDateSortDirection() === 'asc' ? 'ascending' : trackingDateSortDirection() === 'desc' ? 'descending' : 'none'}">${trackingDateHeading()}</th>` : `${fsrc === 'AMZ' ? '<th>Tracking ID</th>' : fsrc === 'XDP' ? '<th>Consignment No</th>' : ''}<th ${deliveryItemColumnSortAttributes()}>${deliveryItemColumnHeading()}</th><th>Postcode</th><th data-date-sort-header="tracking" aria-sort="${trackingDateSortDirection() === 'asc' ? 'ascending' : trackingDateSortDirection() === 'desc' ? 'descending' : 'none'}">${trackingDateHeading()}</th>${!['AMZ', 'XDP', 'Stopstart'].includes(fsrc) ? '<th>Special instructions</th>' : ''}`}<th><div class="tracking-method-heading"><span>Delivery<br>method</span><button class="tracking-method-filter ${fclassification.length ? 'on' : ''}" type="button" data-delivery-filter-action="toggle-classification" aria-label="Filter delivery-method classification" aria-haspopup="menu" aria-expanded="false" aria-controls="tracking-classification-menu" title="${esc(fclassification.length ? fclassification.join(', ') : 'Filter delivery-method classification')}">${ico('filter', 16)}</button></div></th>
        <th>Status</th>${trackingOrderKind() === 'refund' ? (fsrc === 'Stopstart' ? '<th>Special instructions</th>' : '') : fsrc === 'Palletways' ? `<th>${DeliveryFilters.renderBookingHeading('booked_in')}</th><th>${DeliveryFilters.renderBookingHeading('book_in_request')}</th>` : fsrc === 'Stopstart' ? '<th>Special instructions</th>' : '<th>Booking status</th>'}${fsrc === 'Stopstart' ? '<th>Tracking</th>' : ''}
      </tr></thead><tbody id="tb" tabindex="0" role="rowgroup" aria-label="Tracking records, scroll to view more deliveries"></tbody></table>
      <div class="tracking-scroll-overlay" role="scrollbar" tabindex="0" aria-label="Scroll tracking records" aria-controls="tb" aria-orientation="vertical" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0" hidden><span class="tracking-scroll-thumb"></span></div>
    </div>
    <div class="tracking-list-footer" id="tracking-list-footer" role="status" aria-live="polite" hidden></div>
    <section id="tracking-order-flow" class="order-flow" aria-label="Order link flow map" hidden></section>
    ${DeliveryFilters.renderClassificationMenu()}${DeliveryFilters.renderBookingMenus()}`;
}

function palletwaysDepotEligible(delivery) {
  return delivery.carrier === 'Palletways' && !['Delivered', 'Cancelled', 'Return'].includes(delivery.st) &&
    delivery.palletwaysDepotStay?.verified &&
    Date.now() - Date.parse(delivery.palletwaysDepotStay.arrivedAt) > 72 * 3600000;
}

function deliveryMatchesFilters(delivery) {
  if (dashboardWidgetFilter === 'palletways-depot-3days' && !palletwaysDepotEligible(delivery)) return false;
  if (!filterIncludes(fstore, purchaseChannel(delivery))) return false;
  if (
    !(
      TrackingVisibility.includesOrderType(delivery.salesActivityDetails?.['Order Type']) &&
      TrackingVisibility.includesCarrier(delivery.carrier) &&
      TrackingVisibility.includesStore(purchaseChannel(delivery)) &&
      TrackingVisibility.includesPalletwaysClassification(
        delivery.carrier,
        delivery.palletwaysDetails?.classification,
      )
    )
  )
    return false;
  const search = q.toLowerCase();
  const searchable = [
    delivery.id,
    delivery.trk,
    delivery.palletwaysSheetConsignmentNumber,
    delivery.order,
    delivery.orderRef,
    delivery.cust,
    delivery.addr,
    delivery.phone,
  ];
  const status =
    trackingOrderKind() === 'refund' && isCreditRefundRecord(delivery) ? refundStatusValue(delivery) : fsrc === 'AMZ' && (delivery.amazonSheetStatus || delivery.amazonStatus)
      ? `amazon:${delivery.amazonSheetStatus || delivery.amazonStatus}`
      : fsrc === 'Stopstart' && delivery.stopstartStatus
        ? `stopstart:${delivery.stopstartStatus}`
        : fsrc === 'XDP' && delivery.xdpStatus
          ? `xdp:${delivery.xdpStatus}`
          : fsrc === 'Palletways'
            ? palletwaysFilterStatus(delivery.palletwaysSheetStatus, palletwaysOwFallback(delivery))
            : usesGlobalTrackingStatus() ? overallTrackingStatus(delivery) : trackingStatus(delivery.st);
  return (
    filterIncludes(fs, status) &&
    trackingMatchesScope({
      carrier: delivery.carrier,
      status: trackingStatus(delivery.st),
      orderType: delivery.salesActivityDetails?.['Order Type'],
      today: deliveryIsToday(delivery),
    }) &&
    (!fmethod || delivery.type === fmethod) &&
    matchesDeliveryCarrier(delivery.carrier, fsrc) &&
    (!fclassification.length || fclassification.includes(delivery.deliveryMethodRaw)) &&
    (fsrc !== 'Palletways' ||
      !fbookedIn ||
      palletwaysBookedInFilterValue(delivery) === fbookedIn) &&
    (fsrc !== 'Palletways' ||
      !fbookInRequest ||
      String(delivery.palletwaysSheetBookInRequest || '')
        .trim()
        .toLowerCase() === fbookInRequest) &&
    (!fd || (delivery.date && delivery.date >= fd)) &&
    (!ft || (delivery.date && delivery.date <= ft)) &&
    (!search ||
      searchable.some((value) =>
        String(value || '')
          .toLowerCase()
          .includes(search),
      ))
  );
}

async function loadTrackingPage(reset = true) {
  if (document.body.dataset.live !== 'true' || !isTrackingPage()) return;
  if (!reset && (trackingLoading || !trackingHasMore)) return;
  const request = ++trackingRequest;
  if (reset) {
    trackingCreditRefundMatch = null;
    trackingLoadError = false;
    if ($('#tb')) $('#tb').scrollTop = 0;
    trackingOffset = 0;
    trackingLoading = true;
  }
  const offset = reset ? 0 : trackingOffset + DELIVERY_PAGE_SIZE;
  trackingLoading = true;
  const params = {
    limit: DELIVERY_PAGE_SIZE,
    offset,
    hide_hygienic: TrackingVisibility.enabled() ? 1 : '',
    hide_wayfair: TrackingVisibility.wayfairEnabled() ? 1 : '',
    hide_wilko: TrackingVisibility.wilkoEnabled() ? 1 : '',
    hide_palletways_b2b: TrackingVisibility.palletwaysB2bEnabled() ? 1 : '',
    tracking_related: trackingOrderKind() ? '' : 1,
    order_kind: trackingOrderKind(),
    exclude_refunds: page === 'Deliveries' ? 1 : '',
    dashboard_widget: dashboardWidgetFilter,
    q: q.trim(),
    store: fstore,
    carrier: fsrc,
    delivery_method: fclassification,
    status: fs,
    courier_status: ['AMZ', 'Stopstart', 'XDP', 'Palletways'].includes(fsrc) ? 1 : '',
    from: fd,
    to: ft,
    general_scope: trackingScope,
    global_status: usesGlobalTrackingStatus() ? 1 : '',
    today: trackingScope === 'today' ? 1 : '',
    date_sort: trackingDateSort ? `${trackingDateSortType}_${trackingDateSort}` : '',
    booked_in: fsrc === 'Palletways' ? fbookedIn : '',
    book_in_request: fsrc === 'Palletways' ? fbookInRequest : '',
  };
  const queryKey = JSON.stringify({
    ...params,
    offset: 0,
  });
  if (reset) {
    if (queryKey !== trackingLoadedQuery) {
      trackingLoaded = [];
      trackingRelations = null;
      trackingHasMore = false;
    }
  }
  rows();
  try {
    const result = await DeliveryApi.list(params);
    if (request !== trackingRequest || !isTrackingPage()) return;
    if (['refund', 'replacement'].includes(trackingOrderKind()) && /^\d+$/.test(params.q) && !result.orderRelations) {
      try {
        const linkedResult = await DeliveryApi.list({ q: params.q, tracking_related: 1, limit: 1 });
        if (request !== trackingRequest || !isTrackingPage()) return;
        if (linkedResult.orderRelations) {
          const allowed = ['Original', 'Secondary Original', 'Earlier Original', ...(trackingOrderKind() === 'refund' ? ['Credit/Refund'] : ['Replacement', 'Later Replacement'])];
          result.orderRelations = {
            ...linkedResult.orderRelations,
            related: (linkedResult.orderRelations.related || []).filter(record => allowed.includes(record.relatedKind)),
          };
        }
      } catch (error) {
        if (request !== trackingRequest || !isTrackingPage()) return;
        toast('Linked orders could not be loaded. Search again to retry.');
      }
    }
    // A search result without records under its courier falls back to All methods.
    if (reset && result.total === 0 && !q.trim() && fsrc &&
        dashboardSearchHighlight?.page === page &&
        dashboardSearchHighlight.carrier === fsrc && !dashboardSearchHighlight.fallbackApplied) {
      dashboardSearchHighlight.fallbackApplied = true;
      fsrc = '';
      trackingWidgetFacets = result.filterFacets || null;
      $('#v').innerHTML = vDel();
      return loadTrackingPage(true);
    }

    trackingLoaded = reset
      ? result.deliveries
      : [
          ...new Map(
            [...trackingLoaded, ...result.deliveries].map((delivery) => [delivery.id, delivery]),
          ).values(),
        ];
    trackingLoadedQuery = queryKey;
    trackingRelations = result.orderRelations || null;
    trackingCreditRefundMatch = result.creditRefundMatch || null;
    trackingOffset = offset;
    trackingTotal = result.total;
    trackingHasMore = result.hasMore;
    trackingLoadError = false;
    trackingLoading = false;
    // A new PostgreSQL test cache is populated asynchronously. Retry the
    // initial empty page after the background sync completes, without
    // changing normal cached Google Sheets behavior.
    if (reset && result.deliverySource === 'postgresql' && result.syncing && result.total === 0 && !result.message) {
      setTimeout(() => {
        if (isTrackingPage() && !trackingLoaded.length) loadTrackingPage(true);
      }, 5000);
    }
    const selectedDelivery = sel ? get(sel) : null;
    DeliveryStore.hydrate({
      deliveries: trackingLoaded,
      activity: [],
      integrations: S,
    });
    for (const linked of [trackingRelations?.original, ...(trackingRelations?.related || [])]) {
      if (linked?.carrier && linked.st && !get(linked.id)) DeliveryStore.add(linked);
    }
    if (selectedDelivery && !get(sel)) DeliveryStore.add(selectedDelivery);
    D = DeliveryStore.deliveries();
    if (
      (dashboardWidgetFilter || trackingOrderKind()) &&
      result.filterFacets &&
      JSON.stringify(trackingWidgetFacets) !== JSON.stringify(result.filterFacets)
    ) {
      trackingWidgetFacets = result.filterFacets;
      $('#v').innerHTML = vDel();
    }
    rows();
  } catch (error) {
    if (request !== trackingRequest) return;
    trackingLoading = false;
    trackingLoadError = true;
    if (trackingLoaded.length) {
      rows();
      toast(error.message);
      return;
    }
    const list = $('#tb');
    if (list) {
      list.setAttribute('aria-busy', 'false');
      list.innerHTML = `<tr><td colspan="10" class="tracking-empty">${esc(error.message)}</td></tr>`;
    }
    if ($('#tracking-list-footer')) $('#tracking-list-footer').hidden = true;
  }
}
let deliveryItemColumn = 'sku';
try {
  if (localStorage.getItem('atlas-delivery-item-column') === 'order-date')
    deliveryItemColumn = 'order-date';
} catch {}

function deliveryItemColumnLabel() {
  return deliveryItemColumn === 'order-date' ? 'Order date created' : 'SKU of items';
}

function deliveryItemColumnSortAttributes() {
  if (deliveryItemColumn !== 'order-date') return '';
  const failed = page === 'Failed Deliveries';
  const direction = failed ? (failedDateSortType === 'created' ? failedDateSort : '')
    : trackingDateSortType === 'created' ? trackingDateSort : '';
  return `aria-sort="${direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none'}"`;
}

function deliveryItemColumnHeading() {
  const next = deliveryItemColumn === 'order-date' ? 'SKU of items' : 'Order date created';
  const failed = page === 'Failed Deliveries';
  const direction = failed ? (failedDateSortType === 'created' ? failedDateSort : '')
    : trackingDateSortType === 'created' ? trackingDateSort : '';
  const label = deliveryItemColumn === 'order-date'
    ? `<button class="table-date-sort" type="button" data-table-date-sort="${failed ? 'failed-created' : 'tracking-created'}" aria-label="Sort order date created"><span>${deliveryItemColumnLabel()}</span><span class="table-date-sort-indicator" aria-hidden="true">${dateSortIcon(direction)}</span></button>`
    : `<span>${deliveryItemColumnLabel()}</span>`;
  return `<div class="delivery-item-heading">${label}<button type="button" class="delivery-item-switch" data-delivery-item-column aria-label="Show ${next}" title="Switch to ${next}"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 7h16m-4-4 4 4-4 4M20 17H4m4-4-4 4 4 4"/></svg></button></div>`;
}

function deliveryItemColumnCell(delivery) {
  const value =
    deliveryItemColumn === 'order-date'
      ? esc(delivery.orderDate ? hd(delivery.orderDate) : '\u2014')
      : deliverySkuMarkup(delivery);
  return `<td class="delivery-item-cell" data-column-label="${deliveryItemColumnLabel()}">${value}</td>`;
}

document.addEventListener('click', (event) => {
  const button = event.target.closest('[data-delivery-item-column]');
  if (!button) return;
  event.preventDefault();
  void swapDeliveryColumn('[data-delivery-item-column]', () => {
  deliveryItemColumn = deliveryItemColumn === 'sku' ? 'order-date' : 'sku';
  try {
    localStorage.setItem('atlas-delivery-item-column', deliveryItemColumn);
  } catch {}
  document.querySelectorAll('[data-delivery-item-column]').forEach((control) => {
    const header = control.closest('th');
    header.innerHTML = deliveryItemColumnHeading();
    if (deliveryItemColumn === 'sku') header.removeAttribute('aria-sort');
    else {
      const direction = page === 'Failed Deliveries'
        ? (failedDateSortType === 'created' ? failedDateSort : '')
        : trackingDateSortType === 'created' ? trackingDateSort : '';
      header.setAttribute('aria-sort', direction === 'asc' ? 'ascending' : direction === 'desc' ? 'descending' : 'none');
    }
  });
  rows();
  failedRows();
  });
});

function deliverySkuMarkup(delivery) {
  const skus = String(delivery.skuItems || '')
    .split(/[,;|\r\n]+/)
    .map((sku) => sku.trim())
    .filter(Boolean);
  if (skus.length < 2) return esc(skus[0] || '—');
  return `<ul class="tracking-sku-list">${skus.map((sku) => `<li>${esc(sku)}</li>`).join('')}</ul>`;
}

function trackingOrderFlowMarkup(relations, options = {}) {
  const flow = relations?.flow;
  const markerId = options.markerId || 'order-flow-arrow';
  const nodeWidth = options.compact ? 120 : 164;
  const columnGap = options.compact ? 78 : 112;
  if (!flow?.edges?.length || !flow.nodes?.length) return '';
  const ids = [...new Set(flow.nodes.map((node) => String(node.id)))].sort();
  const records = new Map(
    [relations.original, ...(relations.related || [])]
      .filter(Boolean)
      .map((delivery) => [String(delivery.order || delivery.id), delivery]),
  );
  flow.nodes.forEach((node) =>
    records.set(String(node.id), {
      ...records.get(String(node.id)),
      ...node,
    }),
  );
  const known = new Set(ids);
  const edges = flow.edges
    .filter((edge) => known.has(String(edge.from)) && known.has(String(edge.to)))
    .slice()
    .sort(
      (a, b) =>
        String(a.from).localeCompare(String(b.from)) || String(a.to).localeCompare(String(b.to)),
    );
  if (!edges.length) return '';
  const incoming = new Set(edges.map((edge) => String(edge.to)));
  const children = new Map(ids.map((id) => [id, []]));
  edges.forEach((edge) => children.get(String(edge.from)).push(String(edge.to)));
  const levels = new Map();
  const roots = ids.filter((id) => !incoming.has(id));
  const queue = roots.length ? [...roots] : [ids[0]];
  queue.forEach((id) => levels.set(id, 0));
  for (let index = 0; index < queue.length; index++) {
    const id = queue[index];
    for (const child of children.get(id)) {
      if (levels.has(child)) continue;
      levels.set(child, levels.get(id) + 1);
      queue.push(child);
    }
  }
  ids.forEach((id) => {
    if (!levels.has(id)) levels.set(id, 0);
  });
  const columns = new Map();
  ids.forEach((id) => {
    const level = levels.get(id);
    if (!columns.has(level)) columns.set(level, []);
    columns.get(level).push(id);
  });
  const columnCount = Math.max(...levels.values()) + 1;
  const rowCount = Math.max(...[...columns.values()].map((column) => column.length));
  const width = 44 + columnCount * nodeWidth + (columnCount - 1) * columnGap;
  const height = options.compact ? 102 : 40 + rowCount * 114;
  const positions = new Map();
  for (const [level, column] of columns) {
    column.forEach((id, index) =>
      positions.set(id, {
        x: 22 + level * (nodeWidth + columnGap),
        y: 20 + (height - 40 - column.length * 114) / 2 + index * 114,
      }),
    );
  }
  const compactOrder = options.compact
    ? ids.slice().sort((a, b) => levels.get(a) - levels.get(b) || a.localeCompare(b))
    : [];
  if (options.compact)
    compactOrder.forEach((id, index) =>
      positions.set(id, {
        x: 12 + index * (nodeWidth + columnGap),
        y: 18,
      }),
    );
  const diagramWidth = options.compact
    ? 24 + ids.length * nodeWidth + (ids.length - 1) * columnGap
    : width;
  const boxHeight = options.compact ? 44 : 62;
  const centerY = options.compact ? 22 : 31;
  const connections = edges
    .map((edge) => {
      const from = positions.get(String(edge.from)),
        to = positions.get(String(edge.to));
      const x1 = from.x + nodeWidth,
        y1 = from.y + centerY,
        x2 = to.x,
        y2 = to.y + centerY;
      const middle = (x1 + x2) / 2;
      const skipsNode =
        options.compact &&
        Math.abs(compactOrder.indexOf(String(edge.to)) - compactOrder.indexOf(String(edge.from))) >
          1;
      const path = skipsNode
        ? `M${x1},${y1} H${x1 + 12} V6 H${x2 - 12} V${y2} H${x2 - 7}`
        : x2 > x1
          ? `M${x1},${y1} H${middle} V${y2} H${x2 - 7}`
          : `M${x1},${y1} H${x1 + 16} V${Math.min(from.y, to.y) - 10} H${x2 - 16} V${y2} H${x2 - 7}`;
      return `<g class="order-flow-edge" data-flow-from="${esc(edge.from)}" data-flow-to="${esc(edge.to)}"><title>${esc(edge.from)} &#8594; ${esc(edge.to)}: ${esc(edge.kind)}</title><path d="${path}" marker-end="url(#${esc(markerId)})"/>${options.compact ? '' : `<text x="${x2 > x1 ? middle : x1 + 8}" y="${y1 - 10}" text-anchor="middle">${esc(edge.kind)}</text>`}</g>`;
    })
    .join('');
  const nodes = ids
    .map((id) => {
      const { x, y } = positions.get(id);
      const searched = id === String(relations.order);
      const delivery = records.get(id) || {};
      const incomingLink = edges.find((edge) => String(edge.to) === id);
      const orderType = incomingLink
        ? incomingLink.kind === 'Credit/Refund'
          ? 'Credit/Refund'
          : 'Replacement'
        : 'Order';
      const canOpenDetails = options.dashboardOrders || delivery.canOpenDetails !== false;
      const status =
        delivery.st ||
        delivery.palletwaysSheetStatus ||
        delivery.xdpStatus ||
        delivery.stopstartStatus ||
        delivery.amazonSheetStatus ||
        delivery.amazonStatus
          ? carrierStatusLabel(delivery)
          : delivery.category === 'credit/refund'
            ? 'Credit/Refund'
            : 'Status unavailable';
      const statusLineLength = options.compact ? 18 : 24;
      const statusLines = [''];
      for (const word of String(status).split(/\s+/)) {
        const last = statusLines.length - 1;
        if (statusLines[last] && statusLines[last].length + word.length + 1 > statusLineLength)
          statusLines.push(word);
        else statusLines[last] += (statusLines[last] ? ' ' : '') + word;
      }
      const visibleLines = statusLines.slice(0, 2).map((line, index) => {
        const shortened = line.length > statusLineLength || (index === 1 && statusLines.length > 2);
        return shortened ? line.slice(0, statusLineLength - 3) + '\u2026' : line;
      });
      const statusMarkup = `<text class="order-flow-status" x="${x + nodeWidth / 2}" y="${y + (options.compact ? 61 : 82)}" text-anchor="middle"><title>${esc(status)}</title>${visibleLines.map((line, index) => `<tspan x="${x + nodeWidth / 2}" dy="${index ? 15 : 0}">${esc(line)}</tspan>`).join('')}</text>`;
      return `<g class="order-flow-node${searched ? ' is-searched' : ''}" data-flow-order="${esc(id)}" data-flow-kind="${esc(orderType)}" data-flow-searched="${searched}" ${canOpenDetails ? `role="button" tabindex="0" ${options.dashboardOrders ? 'data-dash-order' : 'data-flow-open'}="${esc(id)}"` : 'role="group"'} aria-label="${canOpenDetails ? 'Open details for order' : 'Order'} ${esc(id)}, ${esc(status)}${searched ? ', searched order' : ''}${canOpenDetails ? '' : ', delivery details unavailable'}"><rect x="${x}" y="${y}" width="${nodeWidth}" height="${boxHeight}" rx="${options.compact ? 8 : 11}"/><text class="order-flow-id" x="${x + nodeWidth / 2}" y="${y + (options.compact ? 18 : 26)}" text-anchor="middle">${esc(id)}</text><text class="order-flow-node-label" x="${x + nodeWidth / 2}" y="${y + (options.compact ? 34 : 46)}" text-anchor="middle">${esc(orderType)}</text>${statusMarkup}</g>`;
    })
    .join('');
  const header = `<div class="order-flow-heading"><h3>Order link flow</h3><span><i aria-hidden="true"></i> Searched order</span></div><p>Follow the arrows from the original order to its replacement or credit/refund.</p>`;
  return `${options.compact ? '' : header}<div class="order-flow-scroll" tabindex="0" role="region" aria-label="Order links, scroll horizontally to see the full chain"><svg class="order-flow-diagram" ${options.compact ? `style="--flow-node-count:${Math.max(3, ids.length)}"` : ''} width="${diagramWidth}" height="${height}" viewBox="0 0 ${diagramWidth} ${height}" role="group" aria-label="Connected orders and their direct links"><defs><marker id="${esc(markerId)}" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 Z"/></marker></defs>${connections}${nodes}</svg></div>`;
}

document.addEventListener('click', (event) => {
  const node = event.target.closest('[data-flow-open]');
  if (!node) return;
  event.preventDefault();
  op(node.dataset.flowOpen);
});

document.addEventListener('keydown', (event) => {
  if (event.key !== 'Enter' && event.key !== ' ') return;
  const node = event.target.closest('[data-flow-open]');
  if (!node) return;
  event.preventDefault();
  op(node.dataset.flowOpen);
});

function trackingRelatedMarkup(relations) {
  const ordinal = (level) => {
    const lastTwo = level % 100;
    const suffix =
      lastTwo >= 11 && lastTwo <= 13
        ? 'th'
        : {
            1: 'st',
            2: 'nd',
            3: 'rd',
          }[level % 10] || 'th';
    return `${level}${suffix}`;
  };
  const section = (kind, title, description, records) => {
    if (page === 'Deliveries' && kind === 'Credit/Refund') return '';
    if (!records.length) return '';
    const heading = `<tr class="tracking-related-heading" data-related-kind="${esc(kind)}"><td colspan="20"><span>${ico('note', 18)}${esc(title)} <strong>${records.length}</strong></span><small>${esc(description)}</small></td></tr>`;
    return heading + records.map((delivery) => deliveryListRow(delivery, true)).join('');
  };
  const originals = relations.related.filter((delivery) =>
    ['Original', 'Secondary Original', 'Earlier Original'].includes(delivery.relatedKind),
  );
  const originalMarkup = originals
    .map((delivery) => {
      const depth = delivery.ancestorDepth || (delivery.relatedKind === 'Original' ? 1 : 2);
      return section(
        delivery.relatedKind,
        `${depth > 1 ? ordinal(depth) + ' ' : ''}Original ID Found`,
        `Original order of ${delivery.linkedToOrder || relations.order}`,
        [delivery],
      );
    })
    .join('');
  const replacements = new Map();
  relations.related
    .filter((delivery) => ['Replacement', 'Later Replacement'].includes(delivery.relatedKind))
    .forEach((delivery) => {
      const depth = delivery.replacementDepth || 1;
      const parent = delivery.linkedToOrder || delivery.originalOrder || relations.order;
      const key = `${depth}:${parent}`;
      if (!replacements.has(key))
        replacements.set(key, {
          depth,
          parent,
          kind: delivery.relatedKind,
          records: [],
        });
      replacements.get(key).records.push(delivery);
    });
  return (
    originalMarkup +
    [...replacements.values()]
      .map(({ depth, parent, kind, records }) =>
        section(
          kind,
          `${depth > 1 ? ordinal(depth) + ' ' : ''}Replacement Order Found`,
          `Replacement for order ${parent}`,
          records,
        ),
      )
      .join('') +
    section(
      'Credit/Refund',
      'Credit/Refund Found',
      `Credit/refund for order ${relations.order}`,
      relations.related.filter((delivery) => delivery.relatedKind === 'Credit/Refund'),
    )
  );
}

function trackingOrderTypeMarkup(delivery) {
  const relations = trackingRelations;
  if (!relations || relations.order !== q.trim() || !relations.flow?.edges?.length) return '';
  const order = String(delivery.order || delivery.id);
  if (!relations.flow.nodes.some((node) => String(node.id) === order)) return '';
  const parent = relations.flow.edges.find((edge) => String(edge.to) === order);
  const type = parent
    ? parent.kind === 'Credit/Refund'
      ? 'Credit/Refund'
      : 'Replacement'
    : 'Order';
  return `<small class="tracking-order-type" data-order-link-type="${esc(type)}">${esc(type)}</small>`;
}

function deliveryListRow(delivery, related = false) {
  related = related === true;
  const canOpen = (trackingOrderKind() === 'refund' && isCreditRefundRecord(delivery)) ||
    (delivery.canOpenDetails !== false && (!related || delivery.canOpenDetails));
  const stopstartUrl =
    delivery.carrier === 'Stopstart' &&
    String(delivery.stopstartTrackability || '')
      .trim()
      .toLowerCase() === 'yes' &&
    /^\d+$/.test(String(delivery.order || '').trim())
      ? `https://track-my-order.co.uk/track_my_delivery/${encodeURIComponent(String(delivery.order).trim())}/`
      : '';
  const postcode =
    delivery.palletwaysDetails?.deliveryPostcode || splitDeliveryAddress(delivery.addr).secondary;
  const contact = [delivery.phone, delivery.email].filter(Boolean);
  const followUpNotice = courierIssueFollowUpNotice(delivery);
  const storeLogo = purchaseStoreLogo(delivery, 'purchase-store-logo-tracking');
  const isSearchedOrder =
    /^\d{1,20}$/.test(q.trim()) && String(delivery.order || delivery.id) === q.trim() &&
    !(page === 'Deliveries' && dashboardSearchHighlight?.order === q.trim());
  return `<tr class="${canOpen ? 'tracking-row' : ''}${related ? ' tracking-related-row' : ''}${isSearchedOrder ? ' tracking-searched-row' : ''}" ${related ? `data-related-kind="${esc(delivery.relatedKind)}"` : ''} ${canOpen ? `tabindex="0" data-delivery-id="${esc(delivery.id)}" aria-label="Open details for ${esc(delivery.order)}"` : ''} data-status="${esc(trackingStatus(carrierBadgeStatus(delivery)))}">
    <td><span class="tracking-order-number"><strong>${esc(delivery.order || '—')}</strong>${delivery.order ? `<button type="button" class="qd-customer-copy" data-copy-order-number="${esc(delivery.order)}" aria-label="Copy order number ${esc(delivery.order)}" title="Copy order number">${ico('copy', 13, 1.8)}</button>` : ''}</span>${trackingOrderTypeMarkup(delivery)}${trackingOrderKind() === 'replacement' ? `<div class="replacement-order-reference">${replacementBadge(delivery)}</div>` : trackingOrderKind() === 'refund' ? `<div class="replacement-order-reference">${creditRefundBadge(delivery)}${delivery.originalOrder ? `<small class="refund-original-order">Original order <strong>${esc(delivery.originalOrder)}</strong></small>` : ''}</div>` : ''}</td>
    ${trackingOrderKind() === 'replacement' ? `<td title="Sales Activity column N: Original order Number"><span class="tracking-order-number"><span>${esc(delivery.originalOrder || '\u2014')}</span>${delivery.originalOrder ? `<button type="button" class="qd-customer-copy" data-copy-order-number="${esc(delivery.originalOrder)}" aria-label="Copy original order number ${esc(delivery.originalOrder)}" title="Copy original order number">${ico('copy', 13, 1.8)}</button>` : ''}</span></td>` : `<td><span class="tracking-order-number tracking-order-reference"><span class="tracking-order-value">${esc(delivery.orderRef || delivery.orderReference || '—')}</span>${canCopyOrderReference(delivery.orderRef || delivery.orderReference) ? `<button type="button" class="qd-customer-copy" data-copy-order-reference="${esc(delivery.orderRef || delivery.orderReference)}" aria-label="Copy order reference ${esc(delivery.orderRef || delivery.orderReference)}" title="Copy order reference">${ico('copy', 13, 1.8)}</button>` : ''}</span>${replacementBadge(delivery)}</td>`}
    ${trackingOrderKind() === 'refund' ? `<td class="tracking-refund-amount" title="Sales Activity column R: Gross (base)">${isCreditRefundRecord(delivery) ? esc(refundAmountLabel(delivery)) : '\u2014'}</td>` : ''}
    <td><div class="tracking-customer-box${storeLogo ? ' has-store-logo' : ''}">${storeLogo}<strong class="tracking-cell-line">${esc(delivery.cust || '—')}</strong>${contact.length ? contact.map((value) => `<span class="tracking-cell-line tracking-customer-contact">${esc(value)}</span>`).join('') : ''}</div></td>
    ${
      fsrc === 'Palletways'
        ? `
    <td class="tracking-palletways-number">${palletwaysNumberCell(delivery)}</td>
    ${deliveryItemColumnCell(delivery)}
    <td>${esc(postcode || '—')}</td>
    <td>${trackingDateCell(delivery)}</td>
    `
        : `
    ${fsrc === 'XDP' ? `<td><span class="tracking-order-number"><span>${esc(delivery.xdpConsignmentNo || '\u2014')}</span>${delivery.xdpConsignmentNo ? `<button type="button" class="qd-customer-copy" data-copy-consignment-number="${esc(delivery.xdpConsignmentNo)}" aria-label="Copy consignment number ${esc(delivery.xdpConsignmentNo)}" title="Copy consignment number">${ico('copy', 13, 1.8)}</button>` : ''}</span></td>` : ''}
    ${fsrc === 'AMZ' ? `<td><span class="tracking-order-number"><span>${esc(delivery.owTrackingNo || '\u2014')}</span>${delivery.owTrackingNo ? `<button type="button" class="qd-customer-copy" data-copy-amazon-tracking="${esc(delivery.owTrackingNo)}" aria-label="Copy tracking ID ${esc(delivery.owTrackingNo)}" title="Copy tracking ID">${ico('copy', 13, 1.8)}</button>` : ''}</span></td>` : ''}
    ${deliveryItemColumnCell(delivery)}
    <td>${esc(postcode || '—')}</td>
    <td>${trackingDateCell(delivery)}</td>
    ${!['AMZ', 'XDP', 'Stopstart'].includes(fsrc) ? `<td>${specialInstructionsMarkup(delivery.specialInstructions || delivery.instructions)}</td>` : ''}
    `
    }
    <td>${esc(delivery.carrier ? carName(delivery.carrier) : '\u2014')}${delivery.deliveryMethodRaw ? `<small class="tracking-cell-line mut">${esc(delivery.deliveryMethodRaw)}</small>` : ''}</td>
    <td class="tracking-status-cell" ${delivery.carrier === 'XDP' && !isCreditRefundRecord(delivery) ? `data-xdp-status="${esc(String(delivery.xdpStatus || '').trim().toUpperCase().replace(/[_\s]+/g, ' '))}"` : ''} ${delivery.carrier === 'AMZ' && !isCreditRefundRecord(delivery) ? `data-amazon-status="${esc(String(delivery.amazonSheetStatus || delivery.amazonStatus || '').trim().toUpperCase())}"` : ''} title="Status source: ${esc(statusSourceDisplay(delivery))}">${related && !delivery.st && !isCreditRefundRecord(delivery) ? '\u2014' : stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery))}<small class="tracking-cell-line mut">${esc(statusSourceDisplay(delivery))}</small>${depotDelayLabel(delivery) ? `<small class="tracking-cell-line status-followup-warning">${esc(depotDelayLabel(delivery))}</small>` : ''}${followUpNotice?.kind === 'missing-row' ? `<small class="tracking-cell-line status-followup-warning">${esc(followUpNotice.text)}</small>` : ''}</td>
    ${
      trackingOrderKind() === 'refund'
        ? (fsrc === 'Stopstart' ? `<td>${specialInstructionsMarkup(delivery.specialInstructions || delivery.instructions)}</td>` : '')
        : fsrc === 'Palletways'
        ? `
    <td class="tracking-booked-in-cell" title="Palletways sheet: Z (Booked In), BT (Book In Date), BU (Book In Time)">${palletwaysBookedInCell(delivery)}</td>
    <td title="Palletways sheet column AA">${esc(delivery.palletwaysSheetBookInRequest || '\u2014')}</td>
    `
        : fsrc === 'Stopstart'
          ? `<td>${specialInstructionsMarkup(delivery.specialInstructions || delivery.instructions)}</td>`
          : `<td title="${delivery.bookingStatusSource === 'Routine Dashboard - Live' ? 'Routine Dashboard - Live · E' : 'Routine Dashboard · Status'}">${esc(delivery.bookingStatus || '—')}</td>`
    }
    ${fsrc === 'Stopstart' ? `<td>${stopstartUrl ? `<a class="stopstart-tracking-link" href="${esc(stopstartUrl)}" target="_blank" rel="noopener noreferrer" aria-label="Open Stopstart tracking for order ${esc(delivery.order)}">Open tracking ${ico('right', 14)}</a>` : '\u2014'}</td>` : ''}
  </tr>`;
}

const TrackingScrollbar = (() => {
  let body = null;
  let observer = null;
  let dispose = () => {};
  let update = () => {};

  function attach() {
    const next = document.getElementById('tb') || document.getElementById('failed-list');
    if (!next) return;
    if (body === next) {
      update();
      return;
    }
    dispose();
    observer?.disconnect();
    body = next;
    const wrapper = body.closest('.tracking-records-scroll');
    const track = wrapper.querySelector('.tracking-scroll-overlay');
    const thumb = track.querySelector('.tracking-scroll-thumb');
    let thumbHeight = 0;
    let dragOffset = null;
    update = () => {
      const range = Math.max(0, body.scrollHeight - body.clientHeight);
      track.hidden = range <= 0;
      track.style.top = `${body.offsetTop + 4}px`;
      track.style.left = `${wrapper.scrollLeft + wrapper.clientWidth - 12}px`;
      const height = Math.max(0, body.clientHeight - 8);
      track.style.height = `${height}px`;
      thumbHeight = Math.min(
        height,
        Math.max(32, (height * body.clientHeight) / Math.max(1, body.scrollHeight)),
      );
      thumb.style.height = `${thumbHeight}px`;
      thumb.style.top = `${range ? (body.scrollTop / range) * (height - thumbHeight) : 0}px`;
      track.setAttribute('aria-valuemax', String(range));
      track.setAttribute('aria-valuenow', String(Math.round(body.scrollTop)));
    };
    const seek = (event) => {
      const bounds = AtlasViewport.rect(track);
      const travel = bounds.height - thumbHeight;
      if (travel <= 0) return;
      const fraction = Math.max(
        0,
        Math.min(1, (AtlasViewport.y(event) - bounds.top - dragOffset) / travel),
      );
      body.scrollTop = fraction * (body.scrollHeight - body.clientHeight);
      update();
    };
    track.addEventListener('pointerdown', (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      const bounds = AtlasViewport.rect(thumb);
      dragOffset =
        AtlasViewport.y(event) >= bounds.top && AtlasViewport.y(event) <= bounds.bottom
          ? AtlasViewport.y(event) - bounds.top
          : thumbHeight / 2;
      track.setPointerCapture(event.pointerId);
      seek(event);
    });
    track.addEventListener('pointermove', (event) => {
      if (dragOffset !== null) seek(event);
    });
    track.addEventListener('pointerup', () => {
      dragOffset = null;
    });
    track.addEventListener('pointercancel', () => {
      dragOffset = null;
    });
    track.addEventListener('keydown', (event) => {
      const steps = {
        ArrowDown: 48,
        ArrowUp: -48,
        PageDown: body.clientHeight,
        PageUp: -body.clientHeight,
      };
      if (!(event.key in steps) && !['Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      body.scrollTop =
        event.key === 'Home'
          ? 0
          : event.key === 'End'
            ? body.scrollHeight
            : body.scrollTop + steps[event.key];
      update();
    });
    const onScroll = () => {
      update();
      if (document.body.dataset.live !== 'true') return;
      const atBottom =
        body.scrollTop > 0 && body.scrollHeight - body.clientHeight - body.scrollTop <= 24;
      if (body.id === 'tb') {
        if (!atBottom) {
          trackingLoadError = false;
          return;
        }
        if (!trackingLoading && trackingHasMore && !trackingLoadError) loadTrackingPage(false);
      } else {
        if (!atBottom) {
          failedLoadError = false;
          return;
        }
        if (!failedLoading && failedHasMore && !failedLoadError) loadFailedPage(false);
      }
    };
    body.addEventListener('scroll', onScroll, {
      passive: true,
    });
    wrapper.addEventListener('scroll', update, {
      passive: true,
    });
    const wrapperUpdate = update;
    const previousBody = body;
    dispose = () => {
      previousBody.removeEventListener('scroll', onScroll);
      wrapper.removeEventListener('scroll', wrapperUpdate);
    };
    if (typeof ResizeObserver !== 'undefined') {
      observer = new ResizeObserver(update);
      observer.observe(body);
      observer.observe(wrapper);
    }
    update();
  }

  return {
    attach,
  };
})();

let linkedOrderFocusRequest = 0;
async function openLinkedOrderRow(id) {
  const record = get(id);
  const kind = trackingOrderKind();
  const linkedRecord = kind === 'refund' ? isCreditRefundRecord(record)
    : kind === 'replacement' && orderRecordType(record) === 'Replacement';
  if (!linkedRecord) { op(id); return; }
  const order = String(record.order || id);
  if (q.trim() === order && trackingRelations?.order === order) { op(id); return; }
  const request = ++linkedOrderFocusRequest;
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  op(id);
  const others = [...document.querySelectorAll('#tb > tr')].filter(row => row.dataset.deliveryId !== String(id));
  if (!reducedMotion) {
    await Promise.allSettled(others.map(row => row.animate(
      [{ opacity: 1 }, { opacity: 0, transform: 'translateY(4px)' }],
      { duration: 200, easing: 'ease-out', fill: 'forwards' },
    ).finished));
  }
  if (request !== linkedOrderFocusRequest || trackingOrderKind() !== kind) return;
  q = order;
  dashboardSelectedId = id;
  const input = document.getElementById('q');
  if (input) input.value = order;
  if (document.body.dataset.live === 'true') await loadTrackingPage(true);
  else rows();
  if (request !== linkedOrderFocusRequest || trackingOrderKind() !== kind || q !== order) return;
  if (!reducedMotion) document.querySelectorAll('#tb [data-related-kind]').forEach(row => {
    row.animate([{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }],
      { duration: 320, easing: 'ease-out' });
  });
}

function trackingCreditRefundNotice() {
  const match = trackingCreditRefundMatch;
  if (page !== 'Deliveries' || trackingLoading || !match || String(match.order || match.id) !== q.trim()) return '';
  return `<tr><td colspan="20" class="tracking-empty tracking-refund-notice">
    <section class="refund-discovery" role="link" tabindex="0" data-view-credit-refund="${esc(match.id || match.order)}" aria-label="View credit/refund order ${esc(match.order || match.id)}">
      <div class="refund-discovery-glow" aria-hidden="true"></div>
      <div class="refund-discovery-symbol" aria-hidden="true">
        <svg viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle class="refund-discovery-orbit" cx="32" cy="32" r="27" stroke-dasharray="3 7"/><circle cx="32" cy="32" r="18"/><path class="refund-discovery-currency" d="M38 24h-9a4 4 0 0 0 0 8h6a4 4 0 0 1 0 8h-9m6-20v24"/><path d="m7 15 1-8 8 1M8 8l6 6"/></svg>
      </div>
      <div class="refund-discovery-copy">
        <div class="refund-discovery-eyebrow"><span class="refund-discovery-dot"></span>Credit / Refund found<span class="refund-discovery-order">#${esc(match.order || match.id)}</span></div>
        <h3>It looks like this is a credit/refund order.</h3>
        <p>Click anywhere here to view it on the Credit/Refund page.</p>
      </div>
      <span class="refund-discovery-link-arrow" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14m-6-6 6 6-6 6"/></svg></span>
    </section>
  </td></tr>`;

}

function rows() {
  const live = document.body.dataset.live === 'true';
  const deliveries = live
    ? trackingLoaded.filter(
        (delivery) =>
          (page !== 'Deliveries' || !isCreditRefundRecord(delivery)) &&
          TrackingVisibility.includesOrderType(delivery.salesActivityDetails?.['Order Type']) &&
          TrackingVisibility.includesCarrier(delivery.carrier) &&
          TrackingVisibility.includesStore(purchaseChannel(delivery)) &&
          TrackingVisibility.includesPalletwaysClassification(
            delivery.carrier,
            delivery.palletwaysDetails?.classification,
          ),
      )
    : sortDeliveriesByDate(
        exactOrderMatches(D, q).filter(delivery => (page !== 'Deliveries' || !isCreditRefundRecord(delivery)) && (!trackingOrderKind() || (delivery.orderRelationKind || delivery.relatedKind) === (trackingOrderKind() === 'replacement' ? 'Replacement' : 'Credit/Refund')) && deliveryMatchesFilters(delivery)),
        trackingDateSort,
        (delivery) => trackingDateSortType === 'created' ? orderCreatedDate(delivery) : trackingDateSortType === 'dispatch'
          ? delivery.dispatchDate || delivery.carrierIssueDispatchDate || ''
          : delivery.date,
      );
  const selectedDelivery =
    sel &&
    dashboardSelectedId === sel &&
    (page !== 'Deliveries' || !isCreditRefundRecord(get(sel))) &&
    TrackingVisibility.includesOrderType(get(sel)?.salesActivityDetails?.['Order Type']) &&
    TrackingVisibility.includesCarrier(get(sel)?.carrier) &&
    TrackingVisibility.includesStore(purchaseChannel(get(sel))) &&
    TrackingVisibility.includesPalletwaysClassification(
      get(sel)?.carrier,
      get(sel)?.palletwaysDetails?.classification,
    )
      ? get(sel)
      : null;
  const visibleDeliveries = selectedDelivery
    ? [selectedDelivery, ...deliveries.filter((delivery) => delivery.id !== sel)]
    : deliveries;
  const list = $('#tb');
  if (!list) return;
  const emptyMessage =
    trackingScope === 'today' && !q && !fs && !fsrc && !fclassification.length && !fd && !ft
      ? 'No tracked deliveries due today.'
      : 'No matching deliveries.';

  const scrollTop = list.scrollTop;
  const relations =
    trackingRelations?.order === q.trim() &&
    (trackingRelations.related?.length || trackingRelations.flow?.edges?.length)
      ? trackingRelations
      : null;
  const linkedIds = new Set(
    relations ? [relations.order, ...relations.related.map((delivery) => delivery.id)] : [],
  );
  const refundOriginalSearch = !relations && trackingOrderKind() === 'refund' && /^\d+$/.test(q.trim()) &&
    visibleDeliveries.some(delivery => String(delivery.originalOrder || '') === q.trim()) &&
    !visibleDeliveries.some(delivery => String(delivery.order || delivery.id) === q.trim());
  const content = refundOriginalSearch
    ? trackingRelatedMarkup({ order: q.trim(), related: visibleDeliveries.map(delivery => ({ ...delivery, relatedKind: 'Credit/Refund' })) })
    : relations
    ? (relations.original
        ? deliveryListRow(relations.original, relations.original.canOpenDetails === false)
        : '') +
      trackingRelatedMarkup(relations) +
      visibleDeliveries
        .filter((delivery) => !linkedIds.has(delivery.id))
        .map(deliveryListRow)
        .join('')
    : visibleDeliveries.map(deliveryListRow).join('');
  const displayedContent = trackingCreditRefundNotice() || content;
  renderDeliveryRows(list, displayedContent
    ? displayedContent
    : `<tr><td colspan="10" class="tracking-empty" ${live && (trackingLoading || !liveReady) ? 'role="status"' : ''}>${live && (trackingLoading || !liveReady) ? 'Loading deliveries…' : emptyMessage}</td></tr>`);
  const flowContainer = $('#tracking-order-flow');
  if (flowContainer) {
    const flowMarkup = trackingOrderFlowMarkup(relations);
    if (flowContainer.innerHTML !== flowMarkup) flowContainer.innerHTML = flowMarkup;
    flowContainer.hidden = !flowMarkup;
  }
  list.scrollTop = scrollTop;
  syncSelectedTrackingRow();
  if (dashboardSearchHighlight?.page === page && !q.trim() && dashboardSearchHighlight.id === String(sel)) {
    const elapsed = performance.now() - dashboardSearchHighlight.startedAt;
    const row = [...list.querySelectorAll('[data-delivery-id]')].find(
      node => node.dataset.deliveryId === dashboardSearchHighlight.id,
    );
    if (row && elapsed < 2600) {
      row.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
        row.querySelectorAll('td').forEach(cell => {
          const animation = cell.animate(
            [{ backgroundColor: '#a8e8bd' }, { backgroundColor: getComputedStyle(cell).backgroundColor }],
            { duration: 2600, easing: 'ease-out' },
          );
          animation.currentTime = elapsed;
        });
      }
    }
  }
  TrackingScrollbar.attach();
  list.setAttribute('aria-busy', String(live && trackingLoading));
  const footer = $('#tracking-list-footer');
  if (footer) {
    footer.hidden = !live || !visibleDeliveries.length || (!trackingLoading && !trackingLoadError);
    footer.textContent = trackingLoadError
      ? 'Could not load more deliveries. Scroll up and back down to retry.'
      : 'Loading deliveries\u2026';
  }
}

let failedSearch = '';
let failedCarrier = '';
let failedScope = '';
let failedStore = '';
let failedStatus = '';
let failedDateFrom = '';
let failedDateTo = '';
let failedScheduledFrom = '';
let failedScheduledTo = '';
let failedLoaded = [];
let failedOffset = 0;
let failedTotal = 0;
let failedHasMore = false;
let failedLoadError = false;
let failedRequest = 0;
let failedSearchTimer = null;
let failedLoading = document.body.dataset.live === 'true';

function hasFailedFilters() {
  return Boolean(
    failedScope ||
      failedStore ||
      failedStatus ||
      failedCarrier ||
      failedDateFrom ||
      failedDateTo ||
      failedScheduledFrom ||
      failedScheduledTo,
  );
}

function syncFailedClearButton() {
  const button = document.querySelector('[data-failed-clear-filters]');
  if (button) button.hidden = !hasFailedFilters();
}

function failedDateLabel() {
  if (!failedDateFrom && !failedDateTo) return 'Failed / issue date';
  if (failedDateFrom && failedDateTo) return `${hd(failedDateFrom)} – ${hd(failedDateTo)}`;
  return failedDateFrom ? `From ${hd(failedDateFrom)}` : `To ${hd(failedDateTo)}`;
}

function failedScheduledLabel() {
  if (!failedScheduledFrom && !failedScheduledTo) return 'Scheduled date';
  if (failedScheduledFrom && failedScheduledTo)
    return `${hd(failedScheduledFrom)} – ${hd(failedScheduledTo)}`;
  return failedScheduledFrom ? `From ${hd(failedScheduledFrom)}` : `To ${hd(failedScheduledTo)}`;
}

function failedCombinedDateLabel() {
  const failed = Boolean(failedDateFrom || failedDateTo);
  const scheduled = Boolean(failedScheduledFrom || failedScheduledTo);
  if (failed && scheduled) return '2 date ranges';
  return failed ? failedDateLabel() : scheduled ? failedScheduledLabel() : 'Delivery date';
}

function closeFailedDateFilter() {
  const menu = $('#fdpn'), trigger = $('#fdbtn');
  if (menu) menu.hidden = true;
  if (trigger) trigger.setAttribute('aria-expanded', 'false');
}

function failedDeliveryVisible(delivery) {
  return (
    Boolean(delivery) &&
    !isCreditRefundRecord(delivery) && isGlobalException(delivery) &&
    TrackingVisibility.includesOrderType(delivery.salesActivityDetails?.['Order Type']) &&
    TrackingVisibility.includesCarrier(delivery.carrier) &&
    TrackingVisibility.includesStore(purchaseChannel(delivery)) &&
    TrackingVisibility.includesPalletwaysClassification(
      delivery.carrier,
      delivery.palletwaysDetails?.classification,
    )
  );
}

function failedVisibilityParams() {
  return {
    hide_hygienic: TrackingVisibility.enabled() ? 1 : '',
    hide_wayfair: TrackingVisibility.wayfairEnabled() ? 1 : '',
    hide_wilko: TrackingVisibility.wilkoEnabled() ? 1 : '',
    hide_palletways_b2b: TrackingVisibility.palletwaysB2bEnabled() ? 1 : '',
  };
}

async function loadFailedPage(reset = true) {
  if (document.body.dataset.live !== 'true' || !liveReady || page !== 'Failed Deliveries') return;
  if (!reset && (failedLoading || !failedHasMore)) return;
  const request = ++failedRequest;
  if (reset) {
    failedLoadError = false;
    if ($('#failed-list')) $('#failed-list').scrollTop = 0;
    failedOffset = 0;
    const canUsePreview =
      !Object.values(failedVisibilityParams()).some(Boolean) &&
      !failedScope &&
      !failedStore &&
      !failedStatus &&
      !failedCarrier &&
      !failedSearch.trim() &&
      !failedDateFrom &&
      !failedDateTo &&
      !failedScheduledFrom &&
      !failedScheduledTo &&
      !failedDateSort;
    failedLoaded = canUsePreview
      ? (liveSummary?.failedPreview || []).filter(
          (delivery) =>
            isGlobalException(delivery) &&
            failedDeliveryVisible(delivery),
        )
      : [];
    failedTotal = canUsePreview ? liveSummary?.failedTotal || failedLoaded.length : 0;
    failedHasMore = failedLoaded.length < failedTotal;
    failedLoading = !failedLoaded.length;
    failedRows();
    if (
      canUsePreview &&
      failedLoaded.length &&
      (!failedHasMore || failedLoaded.length === DELIVERY_PAGE_SIZE)
    )
      return;
  }
  try {
    const offset = reset ? 0 : failedOffset + DELIVERY_PAGE_SIZE;
    failedLoading = true;
    failedRows();
    const result = await DeliveryApi.list({
      limit: DELIVERY_PAGE_SIZE,
      offset,
      ...failedVisibilityParams(),
      issues: 1,
      general_scope: failedScope,
      store: failedStore,
      status: failedStatus,
      courier_status: failedCarrier ? 1 : '',
      carrier: failedCarrier,
      q: failedSearch.trim(),
      from: failedDateFrom,
      to: failedDateTo,
      scheduled_from: failedScheduledFrom,
      scheduled_to: failedScheduledTo,
      date_sort: failedDateSort ? `${failedDateSortType}_${failedDateSort}` : '',
    });
    if (request !== failedRequest || page !== 'Failed Deliveries') return;
    failedLoaded = reset
      ? result.deliveries
      : [
          ...new Map(
            [...failedLoaded, ...result.deliveries].map((delivery) => [delivery.id, delivery]),
          ).values(),
        ];
    failedOffset = offset;
    failedTotal = result.total;
    failedHasMore = result.hasMore;
    failedLoadError = false;
    failedLoading = false;
    const selectedDelivery = sel ? get(sel) : null;
    DeliveryStore.hydrate({
      deliveries: failedLoaded,
      activity: [],
      integrations: S,
    });
    if (selectedDelivery && !get(sel)) DeliveryStore.add(selectedDelivery);
    D = DeliveryStore.deliveries();
    failedRows();
  } catch (error) {
    if (request !== failedRequest) return;
    failedLoading = false;
    failedLoadError = true;
    if (failedLoaded.length) {
      failedRows();
      toast(error.message);
      return;
    }
    const list = $('#failed-list');
    if (list) {
      list.setAttribute('aria-busy', 'false');
      list.innerHTML = `<tr><td colspan="10" class="tracking-empty">${esc(error.message)}</td></tr>`;
    }
    if ($('#failed-list-footer')) $('#failed-list-footer').hidden = true;
  }
}

function failedFilterFacets() {
  return trackingFilterFacets().filter((item) =>
    !item.creditRefund && isGlobalException(item),
  );
}

function failedStatusKey(item) {
  if (!failedCarrier) return overallTrackingStatus(item);
  if (item.carrier === 'AMZ' && (item.amazonSheetStatus || item.amazonStatus))
    return `amazon:${item.amazonSheetStatus || item.amazonStatus}`;
  if (item.carrier === 'XDP' && item.xdpStatus) return `xdp:${item.xdpStatus}`;
  if (item.carrier === 'Palletways' && item.palletwaysSheetStatus)
    return `palletways:${item.palletwaysSheetStatus}`;
  if (item.carrier === 'Stopstart' && item.stopstartStatus)
    return `stopstart:${item.stopstartStatus}`;
  return overallTrackingStatus(item);
}

function availableFailedStatuses() {
  const counts = new Map();
  failedFilterFacets()
    .filter(
      (item) =>
        trackingMatchesScope(item, failedScope) &&
        matchesDeliveryCarrier(item.carrier, failedCarrier) &&
        filterIncludes(failedStore, item.purchaseStore),
    )
    .forEach((item) => {
      const key = failedStatusKey(item);
      counts.set(key, (counts.get(key) || 0) + item.count);
    });
  return [...counts]
    .filter(([key]) => key)
    .map(([key, count]) => [
      key,
      `${amazonStatusLabel(key.includes(':') ? key.split(':').slice(1).join(':') : key)} (${count})`,
    ]);
}

function failedMatchesScope(delivery) {
  return trackingMatchesScope(
    {
      carrier: delivery.carrier,
      status: trackingStatus(delivery.st),
      orderType: delivery.salesActivityDetails?.['Order Type'],
      today: delivery.date === localDateKey(),
    },
    failedScope,
  );
}

function availableFailedStores() {
  const present = new Set(
    failedFilterFacets()
      .filter(
        (item) =>
          trackingMatchesScope(item, failedScope) &&
          matchesDeliveryCarrier(item.carrier, failedCarrier),
      )
      .map((item) => item.purchaseStore),
  );
  return PURCHASE_STORES.filter((store) => present.has(store));
}

function failedCategoryOptions() {
  const facets = failedFilterFacets().filter(item => matchesDeliveryCarrier(item.carrier, failedCarrier) &&
    filterIncludes(failedStore, item.purchaseStore));
  return TRACKING_SCOPE_OPTIONS.filter(([value]) => value !== 'hygienic' || !TrackingVisibility.enabled())
    .map(([value, label]) => [value, label, facets.filter(item => trackingMatchesScope(item, value)).reduce((sum, item) => sum + item.count, 0)])
    .filter(([value, , count]) => !value || count > 0 || filterValues(failedScope).includes(value))
    .map(([value, label, count]) => [value, value ? `${label} (${count})` : 'All categories']);
}

function failedScopeMarkup() {
  const facets = failedFilterFacets().filter(item => trackingMatchesScope(item, failedScope));
  const nonDelivery = new Set([...TRACKING_GENERAL_OPTIONS, ...TRACKING_SCOPE_OPTIONS].map(([value]) => value).filter(value => value && value !== 'today' && value !== 'hygienic'));
  const counts = {};
  facets.forEach(item => {
    if (!item.carrier || nonDelivery.has(item.carrier)) return;
    const carrier = SELF_DELIVERY_CARRIERS.includes(item.carrier) ? SELF_DELIVERY_GROUP : item.carrier;
    counts[carrier] = (counts[carrier] || 0) + item.count;
  });
  const courierOrder = [SELF_DELIVERY_GROUP, 'Palletways', 'AMZ', 'XDP', 'Stopstart', 'Yodel', 'Wayfair'];
  const methods = Object.entries(counts).filter(([, count]) => count > 0)
    .sort(([first], [second]) => (courierOrder.indexOf(first) < 0 ? 99 : courierOrder.indexOf(first)) - (courierOrder.indexOf(second) < 0 ? 99 : courierOrder.indexOf(second)));
  return `<div class="delivery-scope-row tracking-scope-sections failed-scope-sections">
    <section class="tracking-scope-section" aria-label="Delivery methods">
      <h3 class="tracking-scope-heading">Delivery methods</h3>
      <div class="fx-tabs" role="tablist" aria-label="Delivery methods"><button class="fx-tab ${!failedCarrier ? 'on' : ''}" type="button" role="tab" aria-selected="${!failedCarrier}" data-failed-method=""><span class="scope-option-label">All methods</span><span>${facets.reduce((sum, item) => sum + item.count, 0)}</span></button></div>
      <div class="tracking-courier-grid" role="tablist" aria-label="Courier delivery methods">${methods.map(([value, count]) => {
        if (value === SELF_DELIVERY_GROUP) return selfDeliveryCourierCard(count, failedCarrier === value, true);
        const asset = courierAssets[value];
        const label = value === 'AMZ' ? 'Amazon Shipping' : value;
        return `<button class="tracking-courier-card fx-tab ${value === failedCarrier ? 'on' : ''}" type="button" role="tab" aria-selected="${value === failedCarrier}" aria-label="${esc(label)}, ${count} deliveries" data-failed-method="${esc(value)}" style="--courier-brand-color:${asset?.[1] || 'var(--atlas-indigo)'}"><span class="tracking-courier-logo">${asset ? `<img src="/assets/${asset[0]}" alt="" width="110" height="35" decoding="async">` : `${ico('truck', 24)}<span>${esc(label)}</span>`}</span><span class="tracking-courier-count">${count}</span></button>`;
      }).join('')}</div>
    </section>
  </div>`;
}

function vFail() {
  const stores = availableFailedStores();
  failedStore = compactFilter(filterValues(failedStore).filter(value => stores.includes(value)));
  const statuses = availableFailedStatuses();
  const categories = failedCategoryOptions();
  failedStatus = compactFilter(filterValues(failedStatus).filter(value => statuses.some(([status]) => status === value)));
  return `<div class="delivery-page-head"><h2 class="fx-title">Failed Deliveries</h2></div>
    <p class="failed-page-note">Current global Failed, Rejected and Lost deliveries.</p>
    ${failedScopeMarkup()}
    <div class="bar delivery-filters">
      <label class="delivery-search">
        ${ico('search', 18)}
        <input id="failed-search" type="search" aria-label="Search failed deliveries" placeholder="Search delivery" value="${esc(failedSearch)}">
      </label>
      ${UiSelect.render(
        'failed-store-value',
        failedStore,
        [['', 'All stores'], ...stores.map((store) => [store, store])],
        {
          ariaLabel: 'Filter by store',
          className: 'delivery-store-select',
          multiple: true,
          selectionLabel: 'stores selected',
          onChange: (value) => {
            failedStore = value;
            failedStatus = '';
            R();
          },
        },
      )}
      ${categories.length > 1 ? UiSelect.render('failed-scope-value', failedScope, categories, {
        ariaLabel: 'Filter categories', className: 'delivery-scope-select', multiple: true,
        selectionLabel: 'categories selected',
        onChange: value => { failedScope = value; failedStatus = ''; dashboardSelectedId = null; R(); },
      }) : ''}
      ${UiSelect.render('failed-status-value', failedStatus, [['', 'All statuses'], ...statuses], {
        ariaLabel: 'Filter by status', className: 'delivery-select', multiple: true,
        selectionLabel: 'statuses selected',
        onChange: value => { failedStatus = value; dashboardSelectedId = null; R(); },
      })}
      <div class="ui-select delivery-date-select" data-failed-date-filter>
        <button class="ui-select-trigger" id="fdbtn" type="button" aria-expanded="false" aria-label="Filter by delivery date" data-failed-toggle-date>
          <span class="ui-select-label">${esc(failedCombinedDateLabel())}</span><span class="ui-select-chevron">${ico('chevdown', 16, 2)}</span>
        </button>
        <div class="ui-select-menu ui-date-menu" id="fdpn" hidden>
          <span class="failed-date-heading">Failed / issue date</span>
          <div class="delivery-date-fields">
            <label><span>From</span><input id="failed-date-from" type="date" aria-label="Failed or issue date from" value="${esc(failedDateFrom)}"></label>
            <label><span>To</span><input id="failed-date-to" type="date" aria-label="Failed or issue date to" value="${esc(failedDateTo)}"></label>
          </div>
          <button class="delivery-date-clear" type="button" data-failed-clear-dates>Clear failed dates</button>
          <span class="failed-date-heading">Scheduled date</span>
          <div class="delivery-date-fields">
            <label><span>From</span><input id="failed-scheduled-from" type="date" aria-label="Scheduled date from" value="${esc(failedScheduledFrom)}"></label>
            <label><span>To</span><input id="failed-scheduled-to" type="date" aria-label="Scheduled date to" value="${esc(failedScheduledTo)}"></label>
          </div>
          <button class="delivery-date-clear" type="button" data-failed-clear-dates="scheduled">Clear scheduled dates</button>
        </div>
      </div>
      <button class="delivery-clear" type="button" data-failed-clear-filters ${hasFailedFilters() ? '' : 'hidden'}>Clear filters</button>
    </div>
    <div class="tracking-table-wrap failed-table-wrap tracking-records-scroll" tabindex="0" role="region" aria-label="Failed deliveries table, scroll horizontally to view all columns">
      <table class="tracking-table failed-table current-table">
        <thead><tr><th>Order No</th><th>Order Ref No</th><th>Customer &amp; contact</th><th ${deliveryItemColumnSortAttributes()}>${deliveryItemColumnHeading()}</th><th>Postcode</th><th>Scheduled date</th><th data-date-sort-header="failed" aria-sort="${failedDateSortType !== 'issue' ? 'none' : failedDateSort === 'asc' ? 'ascending' : failedDateSort === 'desc' ? 'descending' : 'none'}"><button class="table-date-sort" type="button" data-table-date-sort="failed" aria-label="Sort failed or issue date">Failed / issue date <span class="table-date-sort-indicator" aria-hidden="true">${dateSortIcon(failedDateSortType === 'issue' ? failedDateSort : '')}</span></button></th><th>Failed reason / issue</th><th>Delivery method</th><th>Status</th></tr></thead>
        <tbody id="failed-list" tabindex="0" aria-label="Failed delivery records"></tbody>
      </table>
      <div class="tracking-scroll-overlay" role="scrollbar" tabindex="0" aria-label="Scroll failed deliveries" aria-controls="failed-list" aria-orientation="vertical" aria-valuemin="0" aria-valuemax="0" aria-valuenow="0" hidden><span class="tracking-scroll-thumb"></span></div>
    </div><div class="tracking-list-footer" id="failed-list-footer" role="status" aria-live="polite" hidden></div>`;
}

function failedRows() {
  const list = $('#failed-list');
  if (!list) return;
  const search = failedSearch.trim().toLowerCase();
  const failed =
    document.body.dataset.live === 'true'
      ? failedLoaded.filter(
          (delivery) =>
            failedDeliveryVisible(delivery) &&
            failedMatchesScope(delivery) &&
            matchesDeliveryCarrier(delivery.carrier, failedCarrier) &&
            filterIncludes(failedStore, purchaseChannel(delivery)) &&
            filterIncludes(failedStatus, failedStatusKey(delivery)),
        )
      : sortDeliveriesByDate(
          exactOrderMatches(D, search).filter(
            (delivery) =>
              failedDeliveryVisible(delivery) &&
              isGlobalException(delivery) &&
              failedMatchesScope(delivery) &&
              filterIncludes(failedStore, purchaseChannel(delivery)) &&
              filterIncludes(failedStatus, failedStatusKey(delivery)) &&
              matchesDeliveryCarrier(delivery.carrier, failedCarrier) &&
              (!failedDateFrom ||
                String(
                  delivery.failedAt || delivery.failedDate || delivery.carrierIssueDate || '',
                ).slice(0, 10) >= failedDateFrom) &&
              (!failedDateTo ||
                String(
                  delivery.failedAt || delivery.failedDate || delivery.carrierIssueDate || '',
                ).slice(0, 10) <= failedDateTo) &&
              (!failedScheduledFrom ||
                String(delivery.date || '').slice(0, 10) >= failedScheduledFrom) &&
              (!failedScheduledTo ||
                (delivery.date && String(delivery.date).slice(0, 10) <= failedScheduledTo)) &&
              (!search ||
                [
                  delivery.order,
                  delivery.orderRef,
                  delivery.orderReference,
                  delivery.addr,
                  delivery.trk,
                  delivery.palletwaysSheetConsignmentNumber,
                  delivery.cust,
                  delivery.phone,
                  delivery.email,
                ].some((value) =>
                  String(value || '')
                    .toLowerCase()
                    .includes(search),
                )),
          ),
          failedDateSort,
          (delivery) => failedDateSortType === 'created' ? orderCreatedDate(delivery) : delivery.failedAt || delivery.failedDate || delivery.carrierIssueDate,
        );
  const selectedDelivery =
    sel && dashboardSelectedId === sel && !hasFailedFilters() && failedDeliveryVisible(get(sel))
      ? get(sel)
      : null;
  const visibleFailed = selectedDelivery
    ? [selectedDelivery, ...failed.filter((delivery) => delivery.id !== sel)]
    : failed;

  const scrollTop = list.scrollTop;
  renderDeliveryRows(list, visibleFailed.length
    ? visibleFailed
        .map((delivery) => {
          const storeLogo = purchaseStoreLogo(delivery, 'purchase-store-logo-tracking');
          const failedDate = delivery.failedAt || delivery.failedDate || delivery.carrierIssueDate;
          const followUpNotice = courierIssueFollowUpNotice(delivery);
          return `
    <tr class="tracking-row failed-table-row" tabindex="0" data-delivery-id="${esc(delivery.id)}" aria-label="Open failed delivery details for ${esc(delivery.order)}">
    <td><span class="tracking-order-number"><strong>${esc(delivery.order || '—')}</strong>${delivery.order ? `<button type="button" class="qd-customer-copy" data-copy-order-number="${esc(delivery.order)}" aria-label="Copy order number ${esc(delivery.order)}" title="Copy order number">${ico('copy', 13, 1.8)}</button>` : ''}</span></td>
    <td><span class="tracking-order-number tracking-order-reference"><span class="tracking-order-value">${esc(delivery.orderRef || delivery.orderReference || '—')}</span>${canCopyOrderReference(delivery.orderRef || delivery.orderReference) ? `<button type="button" class="qd-customer-copy" data-copy-order-reference="${esc(delivery.orderRef || delivery.orderReference)}" aria-label="Copy order reference ${esc(delivery.orderRef || delivery.orderReference)}" title="Copy order reference">${ico('copy', 13, 1.8)}</button>` : ''}</span>${replacementBadge(delivery)}</td>
    <td><div class="tracking-customer-box${storeLogo ? ' has-store-logo' : ''}">${storeLogo}<strong class="tracking-cell-line">${esc(delivery.cust || '—')}</strong>${[
      delivery.phone,
      delivery.email,
    ]
      .filter(Boolean)
      .map(
        (value) =>
          `<span class="tracking-cell-line tracking-customer-contact">${esc(value)}</span>`,
      )
      .join('')}</div></td>
      ${deliveryItemColumnCell(delivery)}
      <td>${esc(splitDeliveryAddress(delivery.addr).secondary || '—')}</td>
      <td>${esc(delivery.date ? hd(delivery.date) : '—')}</td>
      <td>${esc(failedDate ? hd(String(failedDate).slice(0, 10)) : '—')}</td>
      <td>${esc(deliveryReason(delivery.reason).label || delivery.carrierIssueReason || '—')}${!delivery.reason && delivery.carrierIssueReason ? `<small class="tracking-cell-line mut">Source: Courier Issues · ${esc(delivery.carrier === 'Own van' ? 'Van' : delivery.carrier)}</small>` : ''}</td>
      <td>${esc(carName(delivery.carrier))}${delivery.deliveryMethodRaw ? `<small class="tracking-cell-line mut">${esc(delivery.deliveryMethodRaw)}</small>` : ''}</td>
      <td class="tracking-status-cell" ${delivery.carrier === 'XDP' && !isCreditRefundRecord(delivery) ? `data-xdp-status="${esc(String(delivery.xdpStatus || '').trim().toUpperCase().replace(/[_\s]+/g, ' '))}"` : ''} ${delivery.carrier === 'AMZ' && !isCreditRefundRecord(delivery) ? `data-amazon-status="${esc(String(delivery.amazonSheetStatus || delivery.amazonStatus || '').trim().toUpperCase())}"` : ''}>${stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery))}<small class="tracking-cell-line failed-history-note">${esc(statusSourceDisplay(delivery))}</small>${followUpNotice?.kind === 'missing-row' ? `<small class="tracking-cell-line status-followup-warning">${esc(followUpNotice.text)}</small>` : ''}</td>
    </tr>`;
        })
        .join('')
    : `<tr><td colspan="10" class="tracking-empty" ${document.body.dataset.live === 'true' && (failedLoading || !liveReady) ? 'role="status"' : ''}>${document.body.dataset.live === 'true' && (failedLoading || !liveReady) ? 'Loading failed deliveries…' : 'No matching deliveries.'}</td></tr>`);
  list.scrollTop = scrollTop;
  syncSelectedTrackingRow();
  TrackingScrollbar.attach();
  list.setAttribute('aria-busy', String(document.body.dataset.live === 'true' && failedLoading));
  const footer = $('#failed-list-footer');
  if (footer) {
    footer.hidden =
      document.body.dataset.live !== 'true' ||
      !visibleFailed.length ||
      (!failedLoading && !failedLoadError);
    footer.textContent = failedLoadError
      ? 'Could not load more deliveries. Scroll up and back down to retry.'
      : 'Loading deliveries\u2026';
  }
}
