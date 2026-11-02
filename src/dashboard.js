const vNN = delivery => (
  ['Scheduled', 'Rescheduled', 'Out for Delivery'].includes(delivery.st)
  && Boolean(delivery.date)
  && !delivery.nt
);

const localClockLabel = () => new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' });

function dk(key) {
  if (key === 'fail') {
    go('Failed Deliveries');
    return;
  }
  const status = {
    unscheduled: 'Unscheduled',
    active: 'Scheduled',
    done: 'Delivered',
    fail: 'Failed',
  }[key] || '';
  go('Deliveries', status);
}

function todayDeliveries() {
  const currentDay = localDateKey();
  const deliveries = document.body.dataset.live === 'true' && liveSummary
    ? liveSummary.today || []
    : D;

  return deliveries
    .filter(delivery => (
      delivery.date === currentDay
      && ['Scheduled', 'Out for Delivery'].includes(trackingStatus(delivery.st))
    ))
    .sort((a, b) => (a.deliveryWindowStartAt || a.eta || a.win || '99:99')
      .localeCompare(b.deliveryWindowStartAt || b.eta || b.win || '99:99'));
}

function failedDeliveriesPreview() {
  if (document.body.dataset.live === 'true' && liveSummary) {
    return (liveSummary.failedPreview || []).filter(delivery =>
      ['Failed', 'Rejected'].includes(trackingStatus(delivery.st)));
  }
  return D.filter(delivery => ['Failed', 'Rejected'].includes(trackingStatus(delivery.st)));
}

let dashboardFailedSearch = '';
let dashboardCollectionOrder = '';

function filterDashboardFailedOrders(value) {
  dashboardFailedSearch = value;
  const list = document.querySelector('[data-dashboard-failed-list]');
  if (!list) return;
  DashboardFailedCarousel.search();
}

const dashboardOffsets = { ongoing: 0, failed: 0 };

async function loadDashboardMore(scope, direction = 1) {
  if (!liveSummary || !['ongoing', 'failed'].includes(scope)) return;
  const key = scope === 'ongoing' ? 'today' : 'failedPreview';
  const action = direction < 0 ? 'prev' : 'more';
  const button = document.querySelector(`[data-dashboard-${action}="${scope}"]`);
  if (!button || button.disabled) return;
  button.disabled = true;
  button.textContent = 'Loading…';
  const scrollPositions = [...document.querySelectorAll('.db-list-scroll')]
    .map(list => list.scrollTop);
  try {
    const offset = Math.max(0, dashboardOffsets[scope] + direction * DELIVERY_PAGE_SIZE);
    const result = await DeliveryApi.list({
      dashboard_scope: scope,
      issues: scope === 'failed' ? 1 : '',
      limit: DELIVERY_PAGE_SIZE,
      offset,
    });
    const deliveries = scope === 'failed'
      ? result.deliveries.filter(delivery => ['Failed', 'Rejected'].includes(trackingStatus(delivery.st)))
      : result.deliveries;
    if (scope === 'failed' && !deliveries.length) {
      throw new Error('No failed records were returned.');
    }
    liveSummary[key] = deliveries;
    dashboardOffsets[scope] = offset;
    if (scope === 'ongoing') liveSummary.ongoingTodayTotal = result.total;
    DeliveryStore.hydrate({
      deliveries: [...liveSummary.today, ...liveSummary.failedPreview],
      activity: [],
      integrations: S,
    });
    D = DeliveryStore.deliveries();
    R();
    document.querySelectorAll('.db-list-scroll').forEach((list, index) => {
      list.scrollTop = scrollPositions[index] || 0;
    });
  } catch (error) {
    button.disabled = false;
    button.textContent = direction < 0 ? 'Previous 25' : 'Load next 25';
    toast(error.message);
  }
}

function dashboardListRow(delivery, failed = false) {
  const issueAt = delivery.failedAt || delivery.failedDate || delivery.carrierIssueDate || '';
  const issueDate = issueAt ? hd(String(issueAt).slice(0, 10)) : 'Date unavailable';
  const issueTime = /[T ]\d{2}:\d{2}/.test(String(issueAt)) ? optimoClock(issueAt) : '';
  const reason = deliveryReason(delivery.reason).label || delivery.carrierIssueReason || trackingStatus(delivery.st);
  const searchText = [delivery.order, delivery.cust || '?', delivery.orderRef || delivery.orderReference || '?'].join(' ').toLocaleLowerCase();
  const hidden = failed && !searchText.includes(dashboardFailedSearch.trim().toLocaleLowerCase());
  return `<button ${hidden ? 'hidden' : ''} class="db-list-row" type="button" data-today-delivery="${esc(delivery.id)}">
    ${failed ? '' : `<span class="db-list-tag" title="${esc(deliveryWindow(delivery).full)}">${esc(deliveryWindow(delivery).short)}</span>`}
    <span class="db-list-details"><b>${esc(delivery.order)}</b><small>${esc(delivery.cust || '—')}</small><small>${esc(delivery.orderRef || delivery.orderReference || '—')}</small></span>
    ${failed
      ? `<span class="db-list-reason" title="${esc(reason)}">${esc(reason)}</span><span class="db-list-issue-time"><b>${esc(issueTime || '—')}</b><small>${esc(issueDate)}</small></span>`
      : `<span class="db-list-carrier">${esc(delivery.carrier)}</span>`}
  </button>`;
}

function vDash() {
  return DashboardHome.render();
}

const DashboardFailedCarousel = (() => {
  const size = 6;
  const interval = 5000;
  let card = null, viewport = null, timer = null, searchTimer = null, countdown = null;
  let records = [], total = 0, offset = 0, query = '', revision = null;
  let request = 0, busy = false, disposed = () => {};
  let animations = [], automaticAnimation = false;

  const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
  const paused = () => !card || document.hidden || viewport.matches(':hover')
    || viewport.contains(document.activeElement)
    || card.querySelector('.db-mini-search')?.matches(':hover')
    || document.activeElement?.matches('[data-dashboard-failed-search]')
    || Boolean(dashboardFailedSearch.trim());

  function timerLabel(text) {
    const label = card?.querySelector('[data-failed-slide-timer]');
    if (label) label.textContent = text;
  }

  function clearTimer() {
    clearTimeout(timer);
    clearInterval(countdown);
    timer = null;
    countdown = null;
  }

  function schedule() {
    clearTimer();
    if (!card) return;
    if (total <= size) { timerLabel(''); return; }
    if (busy) { timerLabel('Loading…'); return; }
    if (paused() || reducedMotion()) { timerLabel('Auto paused'); return; }
    const deadline = Date.now() + interval;
    const updateCountdown = () => timerLabel(`Next in ${Math.max(0, Math.ceil((deadline - Date.now()) / 1000))}s`);
    updateCountdown();
    countdown = setInterval(updateCountdown, 250);
    timer = setTimeout(() => {
      if (!paused()) load(offset + size >= total ? 0 : offset + size, 1, true);
    }, interval);
  }

  function controls() {
    if (!card) return;
    const previous = card.querySelector('[data-failed-slide="previous"]');
    const next = card.querySelector('[data-failed-slide="next"]');
    previous.disabled = busy || offset === 0;
    next.disabled = busy || offset + size >= total;
    card.querySelector('[data-failed-slide-count]').textContent = total
      ? `${offset + 1}–${Math.min(offset + records.length, total)} of ${total}` : '0 orders';
  }

  function finishAnimation() {
    animations.forEach(animation => animation.cancel());
    animations = [];
    automaticAnimation = false;
    viewport?.querySelector('[data-failed-outgoing]')?.remove();
  }

  function paint(direction = 0, automatic = false) {
    if (!viewport) return;
    finishAnimation();
    const outgoing = viewport.querySelector('.db-failed-page');
    const incoming = document.createElement('div');
    incoming.className = 'db-failed-page';
    incoming.innerHTML = records.length
      ? records.map(delivery => dashboardListRow(delivery, true)).join('')
      : '<p class="db-list-empty" role="status">No matching failed or rejected orders.</p>';
    viewport.scrollTop = 0;
    if (!direction || !outgoing || reducedMotion() || typeof incoming.animate !== 'function') {
      viewport.replaceChildren(incoming);
      return;
    }
    outgoing.dataset.failedOutgoing = '';
    outgoing.setAttribute('aria-hidden', 'true');
    outgoing.inert = true;
    viewport.append(incoming);
    automaticAnimation = automatic;
    const timing = { duration: 620, easing: 'cubic-bezier(.22,.8,.25,1)', fill: 'both' };
    animations = [
      outgoing.animate([{ transform: 'translateX(0)', opacity: 1 },
        { transform: `translateX(${-direction * 100}%)`, opacity: .25 }], timing),
      incoming.animate([{ transform: `translateX(${direction * 100}%)`, opacity: .45 },
        { transform: 'translateX(0)', opacity: 1 }], timing),
    ];
    const current = animations;
    Promise.all(current.map(animation => animation.finished)).then(() => {
      if (animations !== current) return;
      finishAnimation();
      schedule();
    }, () => {});
  }

  async function load(nextOffset, direction = 0, automatic = false) {
    if (!card || (automatic && paused())) return;
    const version = ++request;
    const nextQuery = dashboardFailedSearch.trim();
    busy = true;
    clearTimer();
    controls();
    try {
      let result;
      if (document.body.dataset.live === 'true') {
        result = await DeliveryApi.list({ issues: 1, dashboard_scope: 'failed',
          limit: size, offset: nextOffset, q: nextQuery });
      } else {
        const matches = failedDeliveriesPreview().filter(delivery =>
          [delivery.order, delivery.cust, delivery.orderRef, delivery.orderReference]
            .some(value => String(value || '').toLocaleLowerCase().includes(nextQuery.toLocaleLowerCase())));
        result = { deliveries: matches.slice(nextOffset, nextOffset + size), total: matches.length };
      }
      if (version !== request || !card || nextQuery !== dashboardFailedSearch.trim()) return;
      // A hover or search that starts during a request must not replace the records being read.
      if (automatic && paused()) return;
      if (nextOffset > 0 && !result.deliveries.length) {
        busy = false;
        return load(0, direction, automatic);
      }
      records = result.deliveries.filter(delivery => ['Failed', 'Rejected'].includes(trackingStatus(delivery.st)));
      total = result.total;
      offset = nextOffset;
      query = nextQuery;
      for (const delivery of records) {
        if (DeliveryStore.find(delivery.id)) DeliveryStore.update(delivery.id, delivery);
        else DeliveryStore.add(delivery);
      }
      D = DeliveryStore.deliveries();
      paint(direction, automatic);
    } catch (error) {
      if (version === request && card) {
        if (nextQuery !== query) {
          viewport.innerHTML = `<p class="db-list-empty" role="status">${esc(error.message)}</p>`;
        } else if (!automatic) toast(error.message);
      }
    } finally {
      if (version === request) {
        busy = false;
        controls();
        if (!animations.length) schedule();
      }
    }
  }

  function search() {
    clearTimer();
    clearTimeout(searchTimer);
    ++request;
    busy = false;
    finishAnimation();
    if (!card) return;
    controls();
    searchTimer = setTimeout(() => load(0), 250);
  }

  function attach() {
    disposed();
    clearTimer();
    clearTimeout(searchTimer);
    finishAnimation();
    ++request;
    busy = false;
    card = document.querySelector('[data-dashboard-failed-card]');
    viewport = card?.querySelector('[data-dashboard-failed-list]') || null;
    if (!card || !viewport) return;
    const nextRevision = document.body.dataset.live === 'true'
      ? `${liveSummary?.syncedAt || ''}|${liveSummary?.failedTotal || 0}` : 'local';
    if (revision !== nextRevision) {
      revision = nextRevision;
      records = failedDeliveriesPreview().slice(0, size);
      total = liveSummary?.failedTotal ?? failedDeliveriesPreview().length;
      offset = 0;
      query = '';
    }
    if (records.length || liveReady) paint();
    const listeners = [];
    const listen = (target, type, callback) => {
      target.addEventListener(type, callback);
      listeners.push(() => target.removeEventListener(type, callback));
    };
    const pause = () => {
      clearTimer();
      timerLabel(total > size ? 'Auto paused' : '');
      if (automaticAnimation) animations.forEach(animation => animation.pause());
    };
    const resume = () => {
      if (paused()) return;
      if (automaticAnimation) animations.forEach(animation => animation.play());
      else schedule();
    };
    for (const area of [viewport, card.querySelector('.db-mini-search')].filter(Boolean)) {
      listen(area, 'pointerenter', pause);
      listen(area, 'pointerleave', resume);
      listen(area, 'focusin', pause);
      listen(area, 'focusout', () => queueMicrotask(resume));
    }
    listen(card, 'click', event => {
      const button = event.target.closest('[data-failed-slide]');
      if (!button || button.disabled) return;
      const direction = button.dataset.failedSlide === 'next' ? 1 : -1;
      load(Math.max(0, offset + direction * size), direction);
    });
    listen(document, 'visibilitychange', () => document.hidden ? pause() : resume());
    disposed = () => listeners.forEach(remove => remove());
    controls();
    if (dashboardFailedSearch.trim() || query) search();
    else schedule();
  }

  return { attach, search };
})();

const DashboardListAutoScroll = (() => {
  let cleanup = () => {};
  function attach() {
    cleanup();
    const lists = [...document.querySelectorAll('.db-list-scroll:not([data-dashboard-failed-list])')];
    if (!lists.length) return;
    const states = lists.map(list => ({ list, pauseUntil: 0, holding: false, hovered: false, position: list.scrollTop, expected: list.scrollTop }));
    const removers = [];
    const listen = (target, type, handler) => {
      target.addEventListener(type, handler, { passive: true });
      removers.push(() => target.removeEventListener(type, handler));
    };
    for (const state of states) {
      const pause = () => {
        state.pauseUntil = performance.now();
        state.position = state.list.scrollTop;
      };
      listen(state.list, 'pointerenter', () => { state.hovered = true; pause(); });
      listen(state.list, 'pointerleave', () => { state.hovered = false; pause(); });
      listen(state.list, 'wheel', pause);
      listen(state.list, 'touchmove', pause);
      listen(state.list, 'keydown', pause);
      listen(state.list, 'pointerdown', () => { state.holding = true; pause(); });
      listen(window, 'pointerup', () => { if (state.holding) { state.holding = false; pause(); } });
      listen(window, 'pointercancel', () => { state.holding = false; pause(); });
      listen(state.list, 'scroll', () => {
        if (Math.abs(state.list.scrollTop - state.expected) > 1) pause();
      });
    }
    let frame;
    let previous = performance.now();
    const tick = now => {
      const elapsed = Math.min(now - previous, 50);
      previous = now;
      if (!document.hidden) for (const state of states) {
        if (state.holding || state.hovered || state.list.matches(':hover') || now < state.pauseUntil) continue;
        const maximum = state.list.scrollHeight - state.list.clientHeight;
        if (maximum <= 0 || state.list.scrollTop >= maximum - 1) continue;
        state.position = Math.min(maximum, state.position + elapsed * 0.012);
        state.list.scrollTop = state.position;
        state.expected = state.list.scrollTop;
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    cleanup = () => { cancelAnimationFrame(frame); removers.forEach(remove => remove()); };
  }
  return { attach };
})();
