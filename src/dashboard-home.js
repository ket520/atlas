/* Personalized dashboard over the retained order index. */
const DashboardHome = (() => {
  const definitions = [
    ['cancelled', "Today's OW Cancelled Orders", 'Today only · UK order date', 'x', 'red', 'ow', 'OrderWise'],
    ['charge-pending', 'All Charge Pending OW', 'Remote postcode charges · all dates', 'clipboardcheck', 'blue', 'ow', 'OrderWise'],
    ['hold', 'On Hold OW', 'Currently on hold', 'circ', 'amber', 'ow', 'OrderWise'],
    ['palletways-next-day', 'Palletway Next Day List', 'Excluding delivered', 'truck', 'sky', 'palletways', 'Palletways'],
    ['out-of-stock', 'Out of Stock Orders', 'Orders marked out of stock', 'pkg', 'purple', 'routineLive', 'Routine Dashboard'],
    ['palletways-unbooked', 'Palletways Unbooked', 'Deliveries not booked', 'cal', 'orange', 'palletwaysSheet', 'Palletways sheet'],
    ['van-unscheduled', 'Van Unscheduled', 'Unscheduled, O/S, on hold or open', 'truck', 'teal', 'routineLive', 'Routine Dashboard'],
    ['awaiting-dispatch', 'Awaiting Dispatch', 'OW orders awaiting despatch', 'pkg', 'blue', 'ow', 'OrderWise'],
    ['collection-generator', 'Generate Collection Note', 'Enter an order ID to generate a note', 'note', 'utility', '', 'Utility'],
    ['order-identifier', 'Order Identifier', 'Find the store and courier', 'search', 'utility', '', 'Utility'],
    ['order-flow-tracker', 'Replacement / Credit Refund Tracker', 'Trace linked orders and their statuses', 'note', 'utility', '', 'Utility'],
    ['returns', 'Returns Unprocessed', 'Returns processing · Version 3', 'pkg', 'rose', '', 'Returns'],
  ].map(([key, title, subtitle, icon, tone, source, sourceLabel]) => ({key, title, subtitle, icon, tone, source, sourceLabel}));
  const preferenceKey = 'deliverydesk-dashboard-widgets-v1';
  const defaults = () => definitions.filter(item => !['collection-generator', 'order-flow-tracker', 'returns'].includes(item.key)).map(item => item.key);
  const widgetType = key => key.replace(/--1x[13]$/, '');
  const previousDefaultOrder = ['cancelled', 'hold', 'out-of-stock', 'charge-pending', 'collect',
    'palletways-next-day', 'palletways-unbooked', 'van-unscheduled', 'returns'];
  let order = defaults();
  try {
    const saved = JSON.parse(localStorage.getItem(preferenceKey));
    if (Array.isArray(saved)) {
      const valid = [...new Set(saved.filter(key => definitions.some(item => item.key === widgetType(key))))];
      if ((valid.length || saved.length === 0) && JSON.stringify(valid) !== JSON.stringify(previousDefaultOrder)) order = valid;
    }
  } catch {}
  let sizes = {}, editing = false, pickerFilter = 'all', frozenRows = '', sidebarWasCollapsed = true, closingPicker = false, landingKey = ''; 
  try { sizes = JSON.parse(localStorage.getItem(preferenceKey + '-sizes')) || {}; } catch {}
  const units = key => key.endsWith('--1x3') || (!key.endsWith('--1x1') && sizes[key] === '1x3') ? 3 : 1;
  const widgetInstance = (type, size) => order.find(key => widgetType(key) === type && units(key) === (size === '1x3' ? 3 : 1)) || (order.includes(type) ? type + '--' + size : type);
  const used = () => order.reduce((n, key) => n + units(key), 0);
  let carrier = '', result = null, loading = false, error = false;
  let checkedAt = 0, loadedKey = '', request = 0;
  let widgetDrag = null, widgetPaintPending = false;
  let pendingWidgetPointer = null, suppressWidgetClickUntil = 0;
  const widgetMotions = new Map();
  const methods = [['', 'All methods'], ['Own van / Self Delivery', 'Van'], ['Palletways', 'Palletways'], ['XDP', 'XDP'], ['Stopstart', 'StopStart'], ['AMZ', 'AMZ'], ['Yodel', 'Yodel']];
  const quickBatchSize = 7;
  const quickBatchCount = Math.ceil(SIDEBAR_ITEMS.length / quickBatchSize);
  let quickBatch = 0;
  let disposeQuickLinks = () => {};
  function quickPageMarkup(batch) {
    return Array.from({length: quickBatchSize}, (_, offset) => {
      const index = (batch * quickBatchSize + offset) % SIDEBAR_ITEMS.length;
      const {target, version} = SIDEBAR_ITEMS[index];
      const label = PAGE_LABELS[target] || target;
      const content = `<span class="dash-quick-name">${label}</span>${version ? `<small>V${version}</small>` : ''}`;
      return version
        ? `<button type="button" class="dash-quick dash-quick-${index % 7}" aria-disabled="true" aria-label="${label}, planned for Version ${version}" title="Planned for Version ${version}. Not available yet." data-dash-planned="${version}">${content}</button>`
        : `<a class="dash-quick dash-quick-${index % 7}" href="${PAGE_URL[target]}" data-page-target="${target}" title="${label}">${content}</a>`;
    }).join('');
  }
  function quickLinksMarkup() {
    return `<section class="dash-quick-links" aria-label="Quick Links carousel"><header class="dash-quick-heading"><h2>${ico('link', 18)}Quick Links</h2><div class="dash-quick-controls"><span data-quick-batch>${quickBatch + 1} / ${quickBatchCount}</span><button type="button" data-quick-action="next" aria-label="Next seven quick links" aria-controls="dash-quick-viewport">${ico('next', 12)}</button></div></header><div class="dash-quick-viewport" id="dash-quick-viewport"><div class="dash-quick-page" role="group" aria-label="Quick links batch ${quickBatch + 1}">${quickPageMarkup(quickBatch)}</div></div></section>`;
  }
  function attachQuickLinks() {
    disposeQuickLinks();
    const root = document.querySelector('.dash-quick-links');
    if (!root) return;
    const viewport = root.querySelector('.dash-quick-viewport');
    const events = new AbortController();
    const motionPreference = matchMedia('(prefers-reduced-motion: reduce)');
    let timer = null, motions = [], disposed = false, moving = false;
    const on = (element, name, handler) => element.addEventListener(name, handler, {signal: events.signal});
    const stop = () => { clearTimeout(timer); timer = null; };
    function schedule() {
      stop();
      if (disposed || motionPreference.matches || document.hidden || moving
        || root.matches(':hover') || root.contains(document.activeElement)) return;
      timer = setTimeout(() => advance(1), 5000);
    }
    async function advance(direction) {
      if (disposed || moving) return;
      stop(); moving = true;
      quickBatch = (quickBatch + direction + quickBatchCount) % quickBatchCount;
      const outgoing = viewport.querySelector('.dash-quick-page');
      const incoming = document.createElement('div');
      incoming.className = 'dash-quick-page';
      incoming.setAttribute('role', 'group');
      incoming.setAttribute('aria-label', `Quick links batch ${quickBatch + 1}`);
      incoming.innerHTML = quickPageMarkup(quickBatch);
      incoming.inert = true; outgoing.inert = true;
      viewport.append(incoming);
      root.querySelector('[data-quick-batch]').textContent = `${quickBatch + 1} / ${quickBatchCount}`;
      if (!motionPreference.matches && typeof incoming.animate === 'function') {
        const options = {duration: 550, easing: 'cubic-bezier(.22,.7,.25,1)', fill: 'both'};
        motions = [outgoing.animate([{transform: 'translateX(0)'}, {transform: `translateX(${-direction * 100}%)`}], options),
          incoming.animate([{transform: `translateX(${direction * 100}%)`}, {transform: 'translateX(0)'}], options)];
        await Promise.allSettled(motions.map(animation => animation.finished));
      }
      if (disposed) return;
      outgoing.remove(); incoming.inert = false;
      motions.forEach(animation => animation.cancel()); motions = []; moving = false;
      schedule();
    }
    on(root, 'click', event => {
      const control = event.target.closest('[data-quick-action]');
      if (!control) return;
      if (control.dataset.quickAction === 'next') advance(1);
    });
    on(root, 'mouseenter', stop); on(root, 'mouseleave', schedule);
    on(root, 'focusin', stop);
    on(root, 'focusout', () => queueMicrotask(schedule));
    on(document, 'visibilitychange', schedule);
    on(motionPreference, 'change', schedule);
    disposeQuickLinks = () => {
      disposed = true; stop(); events.abort();
      motions.forEach(animation => animation.cancel());
    };
    schedule();
  }
  const storeWebsites = {
    'Ebay Bathroom Republic': ['eBay Bathroom Republic', 'https://www.ebay.co.uk/str/bathroomrepublicoutlet?_trksid=p4429486.m168239.l149086'],
    'Shopify - Neshome': ['NesHome', 'https://neshome.co.uk/'],
    Amazon: ['NesHome Amazon', 'https://www.amazon.co.uk/stores/NesHome/page/EFEAF2DB-270D-470A-BCA7-DC4AD9BAC87A?lp_asin=B09HTXFQ94&ref_=ast_bln&store_ref=bl_ast_dp_brandlogo_sto&bl_grd_status=override'],
    'Bathroom Republic - Website': ['Bathroom Republic', 'https://bathroomrepublic.co.uk/'],
    'EBay Willesden Bathroom': ['eBay Willesden Bathrooms', 'https://www.ebay.co.uk/str/willesdenbathrooms?_trksid=p2334524.m570.l113337'],
    'B&Q': ['B&Q NesHome', 'https://www.diy.com/verified-sellers/seller/3038/products'],
  };
  const websiteLink = value => {
    const website = storeWebsites[value];
    const logo = {'Ebay Bathroom Republic': 'EbayBR.png', 'Shopify - Neshome': 'ShpfyNes.png',
      Amazon: 'AmaNes.png', 'Bathroom Republic - Website': 'ShpfyBR.png',
      'EBay Willesden Bathroom': 'ebayW.png', 'B&Q': 'BQNes.png'}[value];
    const label = {'Ebay Bathroom Republic': 'eBay BR', 'EBay Willesden Bathroom': 'eBay Willesden'}[value] || website[0];
    return `<a class="dash-store-website" ${value === 'B&Q' ? 'data-bq-vpn' : ''} href="${esc(website[1])}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(website[0])}${value === 'B&Q' ? ' with UK VPN' : ' store in a new tab'}" title="Open ${esc(website[0])}${value === 'B&Q' ? ' with UK VPN' : ' store in a new tab'}"><span class="dash-store-name" aria-hidden="true">${esc(label)}</span><img src="/assets/${logo}" alt="" aria-hidden="true" width="120" height="38" decoding="async"></a>`;
  };
  let openingBq = false;
  document.addEventListener('click', async event => {
    const link = event.target.closest('[data-bq-vpn]');
    if (!link) return;
    event.preventDefault();
    if (openingBq) return;
    openingBq = true;
    link.setAttribute('aria-busy', 'true');
    toast('Connecting UK VPN and opening B&Q…');
    try {
      const response = await fetch('/api/bq/open', {
        method: 'POST', headers: {'X-DeliveryDesk-Action': 'open-bq'},
      });
      if (response.status === 405 || response.status === 404) {
        throw new Error('Restart Atlas to enable the B&Q VPN button, then refresh this page.');
      }
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Could not open B&Q.');
      toast(`${result.message} Check your taskbar or press Alt+Tab for the separate B&Q window, rather than a tab beside Atlas.`, 10000);
    } catch (error) {
      toast(error.message || 'Could not open B&Q. Check Atlas is running.');
    } finally {
      openingBq = false;
      link.removeAttribute('aria-busy');
    }
  });
  const storeLinks = () => `<section class="dash-filter-panel dash-stores-panel" aria-label="Stores"><h2>${ico('pkg', 17)}Stores</h2><nav class="dash-store-links" aria-label="Store websites">${Object.keys(storeWebsites).map(websiteLink).join('')}</nav></section>`;
  const selectedDefinition = key => definitions.find(item => item.key === (key === 'cancelled-month' ? 'cancelled' : /^palletways-unbooked-b2[bc]$/.test(key) ? 'palletways-unbooked' : widgetType(key)));
  const live = () => document.body.dataset.live === 'true';
  const visibility = () => ({hide_hygienic: TrackingVisibility.enabled() ? '1' : '',
    hide_wayfair: TrackingVisibility.wayfairEnabled() ? '1' : '',
    hide_wilko: TrackingVisibility.wilkoEnabled() ? '1' : '',
    hide_palletways_b2b: TrackingVisibility.palletwaysB2bEnabled() ? '1' : ''});
  function save() {
    try { localStorage.setItem(preferenceKey, JSON.stringify(order)); localStorage.setItem(preferenceKey + '-sizes', JSON.stringify(sizes)); } catch {}
  }
  function localData(period = 'daily', unbookedClass = '') {
    const scoped = D.filter(item => matchesDeliveryCarrier(item.carrier, carrier)
      && TrackingVisibility.includesOrderType(item.salesActivityDetails?.['Order Type'])
      && TrackingVisibility.includesCarrier(item.carrier) && TrackingVisibility.includesStore(purchaseChannel(item))
      && TrackingVisibility.includesPalletwaysClassification(item.carrier, item.palletwaysDetails?.classification));
    const ukToday = new Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
    const match = (item, key) => {
      const booking = String(item.bookingStatus || '').trim().toLowerCase();
      const active = !['Delivered', 'Cancelled', 'Return'].includes(item.st);
      if (key === 'cancelled') return (item.st === 'Cancelled' || item.carrier === 'Cancelled') && (period === 'month' ? String(item.orderDate || '').slice(0, 7) === ukToday.slice(0, 7) : String(item.orderDate || '').slice(0, 10) === ukToday);
      if (key === 'awaiting-dispatch') return ['W', 'AWAITING DESPATCH', 'AWAITING DISPATCH'].includes(String(item.rawStatus || '').trim().toUpperCase());
      if (key === 'hold') return item.carrier === 'On Hold' || item.st === 'Unassigned';
      if (key === 'out-of-stock') return active && (booking.includes('out of stock') || booking === 'o/s');
      if (key === 'charge-pending') return item.carrier === 'Charge Pending (Remote Postcode)';
      if (key === 'collect') return item.carrier === 'Collect in Person';
      if (key === 'palletways-next-day') return active && item.carrier === 'Palletways' && /next day/i.test(item.deliveryMethodRaw || '');
      if (key === 'palletways-unbooked') return item.salesActivityPresent === true && String(String(item.palletwaysSheetStatus || '').trim() || item.st || '').trim().toLowerCase() !== 'delivered' && item.carrier === 'Palletways' && String(item.palletwaysSheetBookedIn || '').trim().toLowerCase() === 'no' && (!unbookedClass || String(item.palletwaysDetails?.classification || '').trim().toUpperCase() === unbookedClass);
      if (key === 'van-unscheduled') return active && ['Own van', 'Self Delivery', 'LOCAL MULTIDROP'].includes(item.carrier) && (item.st === 'Unscheduled' || ['o/s', 'out of stock', 'on hold', 'open'].includes(booking));
      return false;
    };
    return {widgets: Object.fromEntries(definitions.map(definition => {
      const rows = scoped.filter(item => match(item, definition.key));
      return [definition.key, {available: definition.key !== 'returns', total: rows.length, preview: rows.slice(0, 3), rows: rows.slice(0, 30)}];
    }))};
  }
  const data = () => live() ? result : localData();
  function legacyWidgetPositions(keys = order) {
    const occupied = Array(9).fill(false), positions = {};
    keys.filter(key => units(key) === 3).forEach(key => {
      let column = Number(sizes[key + '-column'] ?? keys.indexOf(key) % 3);
      while (occupied[column]) column = (column + 1) % 3;
      [0, 3, 6].forEach(row => { occupied[row + column] = true; });
      positions[key] = {row: '1 / span 3', column: String(column + 1)};
    });
    keys.filter(key => units(key) === 1).forEach(key => {
      const slot = occupied.indexOf(false); occupied[slot] = true;
      positions[key] = {row: String(Math.floor(slot / 3) + 1), column: String(slot % 3 + 1)};
    });
    return positions;
  }
  function widgetPositions(keys = order) {
    const fallback = legacyWidgetPositions(keys), result = {};
    keys.forEach(key => {
      const slot = sizes[key + '-slot'];
      result[key] = Number.isInteger(slot) && slot >= 0 && slot < 9
        ? {row: units(key) === 3 ? '1 / span 3' : String(Math.floor(slot / 3) + 1), column: String(slot % 3 + 1)}
        : fallback[key];
    });
    return result;
  }
  function pinWidgetPositions() {
    const positions = widgetPositions();
    order.forEach(key => { const pos = positions[key]; sizes[key + '-slot'] = (parseInt(pos.row, 10) - 1) * 3 + Number(pos.column) - 1; });
  }
  function emptySlotsMarkup() {
    const positions = widgetPositions(), occupied = new Set();
    order.forEach(key => {
      const pos = positions[key], start = (parseInt(pos.row, 10) - 1) * 3 + Number(pos.column) - 1;
      for (let i = 0; i < units(key); i++) occupied.add(start + i * 3);
    });
    return Array.from({length: 9}, (_, slot) => occupied.has(slot) ? '' : `<div class="dash-add-slot" style="grid-row:${Math.floor(slot / 3) + 1};grid-column:${slot % 3 + 1}" aria-label="Drop a widget here">+<span>Drop widget here</span></div>`).join('');
  }
  const monthlyCache = new Map();
  function monthlyCancelledData() {
    const key = JSON.stringify([carrier, visibility(), liveSummary?.syncedAt, new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/London',year:'numeric',month:'2-digit'}).format(new Date())]);
    let state = monthlyCache.get(key);
    if (!state || Date.now() - state.checkedAt > 300000) {
      state = {loading: true, checkedAt: Date.now()}; monthlyCache.set(key, state);
      (async () => {
        // Activity A is the order ID; Activity B is retained as orderDate/orderDateTime.
        // Use the established cancelled cohort so an already-running server works too.
        const rows = [], scopeCarrier = carrier, scopeVisibility = visibility();
        let offset = 0, total = Infinity;
        while (offset < total) {
          const payload = await ApiClient.get(`/deliveries?${new URLSearchParams({general_scope:'Cancelled',carrier:scopeCarrier,limit:'100',offset:String(offset),...scopeVisibility})}`);
          if (!Array.isArray(payload.deliveries)) throw Error('Invalid cancelled orders');
          total = Number(payload.total);
          if (!Number.isFinite(total) || (!payload.deliveries.length && offset < total)) throw Error('Incomplete cancelled orders');
          rows.push(...payload.deliveries); offset += payload.deliveries.length;
          if (!payload.deliveries.length) break;
        }
        const month = new Intl.DateTimeFormat('en-CA', {timeZone:'Europe/London',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date()).slice(0,7);
        const matches = rows.filter(row => String(row.orderDate || row.orderDateTime || '').slice(0,7) === month);
        Object.assign(state, {loading:false, available:true, total:matches.length, rows:matches.slice(0,30), preview:matches.slice(0,3)});
      })().catch(() => { Object.assign(state, {loading:false,error:true}); }).finally(() => { if (page === 'Dashboard') paint(); });
    }
    return state;
  }
  const tableSearch = new Map();
  function tableOrderHeading(instance) {
    const search = tableSearch.get(instance);
    const label = 'Order';
    const searchLabel = 'Search order ID';
    return search?.open
      ? `<div class="dash-order-search"><input type="search" data-table-order-search="${instance}" value="${esc(search.query)}" placeholder="Order ID" aria-label="${searchLabel}"></div>`
      : `<div class="dash-order-heading"><span>${label}</span><button type="button" data-table-search-open="${instance}" aria-label="${searchLabel}">${ico('search', 12)}</button></div>`;
  }
  function tableRows(state, instance) {
    const query = (tableSearch.get(instance)?.query || '').trim().toLowerCase();
    return (state?.rows || state?.preview || []).filter(row => !query || String(row.order || row.id || '').toLowerCase().includes(query));
  }
  function updateTableSearch(instance) {
    const card = document.querySelector(`#dash-widget-grid [data-dash-widget="${instance}"]`);
    if (!card) return;
    const template = document.createElement('template'); template.innerHTML = widgetMarkup(selectedDefinition(instance), instance);
    card.querySelector('tbody').replaceChildren(...template.content.querySelector('tbody').childNodes);
  }
  document.addEventListener('input', event => {
    const instance = event.target.dataset.tableOrderSearch;
    if (!instance) return;
    tableSearch.set(instance, {open:true, query:event.target.value}); updateTableSearch(instance);
  });
  function closeTableSearch(instance, focus = false) {
    tableSearch.set(instance, {open:false, query:''});
    const card = document.querySelector(`#dash-widget-grid [data-dash-widget="${instance}"]`);
    if (!card) return;
    card.querySelector('thead th').innerHTML = tableOrderHeading(instance); updateTableSearch(instance);
    if (focus) card.querySelector('[data-table-search-open]')?.focus();
  }
  document.addEventListener('click', event => {
    const open = event.target.closest('[data-table-search-open]');
    for (const [instance, search] of tableSearch) {
      if (search.open && event.target.closest('[data-table-order-search]')?.dataset.tableOrderSearch !== instance) closeTableSearch(instance);
    }
    if (!open) return;
    const instance = open.dataset.tableSearchOpen;
    tableSearch.set(instance, {open:true, query:''});
    const card = open.closest('[data-dash-widget]');
    card.querySelector('thead th').innerHTML = tableOrderHeading(instance); updateTableSearch(instance);
    card.querySelector('[data-table-order-search]')?.focus();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && event.target.matches('[data-table-order-search]')) {
      event.preventDefault(); closeTableSearch(event.target.dataset.tableOrderSearch, true);
    }
  });
  const orderViewIcon = () => '<svg class="dash-order-view-icon" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg>';
  const orderLabel = item => `<span class="dash-order-id-value">${esc(item.order)}</span>${orderViewIcon()}`;
  function cancelledTableMarkup(state, month, detail, instance) {
    const rows = tableRows(state, instance);
    return `<div class="dash-table-scroll"><table class="dash-cancelled-table"><colgroup><col style="width:44%"><col style="width:31%"><col style="width:25%"></colgroup><thead><tr><th>${tableOrderHeading(instance)}</th><th>Reference No.</th><th>Time &amp; Date</th></tr></thead><tbody>${rows.map(item => {
      const raw = String(item.orderDateTime || ''), timestamp = raw ? new Date(raw) : null;
      const valid = timestamp && !Number.isNaN(timestamp.getTime());
      const time = valid ? timestamp.toLocaleTimeString('en-GB', {timeZone:'Europe/London',hour:'2-digit',minute:'2-digit',hour12:false}) : '-';
      const orderDay = item.orderDate ? new Date(`${item.orderDate}T12:00:00`) : timestamp;
      const date = orderDay && !Number.isNaN(orderDay.getTime()) ? orderDay.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'}) : '-';
      const reference = item.orderRef || item.orderReference || '-';
      return `<tr><td><button type="button" data-dash-order="${esc(item.id || item.order)}">${orderLabel(item)}</button><span class="dash-order-customer">${esc(item.cust || '-')}</span></td><td>${esc(reference)}</td><td>${month ? `<span class="dash-order-date">${esc(date)}</span>` : ''}<time class="dash-order-time" ${valid ? `datetime="${esc(raw)}"` : ''}>${esc(time)}</time></td></tr>`;
    }).join('') || `<tr><td colspan="3">${esc(tableSearch.get(instance)?.query ? 'No matching order IDs' : detail)}</td></tr>`}</tbody></table></div>`;
  }
  const unbookedCache = new Map();
  function unbookedWidgetData(classification) {
    if (!live()) return localData('daily', classification).widgets['palletways-unbooked'];
    if (carrier && carrier !== 'Palletways') return {total:0, rows:[], preview:[],scope:'booked-in-no-current-ow-not-delivered'};
    const key = JSON.stringify([visibility(), liveSummary?.syncedAt]);
    let state = unbookedCache.get(key);
    if (!state || Date.now() - state.checkedAt > 300000) {
      state = {loading:true, checkedAt:Date.now(),scope:'booked-in-no-current-ow-not-delivered'}; unbookedCache.set(key,state);
      (async () => {
        const rows = [], filters = visibility(); let offset = 0, total = Infinity;
        while (offset < total) {
          const payload = await ApiClient.get(`/deliveries?${new URLSearchParams({dashboard_widget:'palletways-unbooked',carrier:'Palletways',limit:'100',offset:String(offset),...filters})}`);
          if (!Array.isArray(payload.deliveries) || !Number.isFinite(Number(payload.total))) throw Error('Invalid stock orders');
          total = Number(payload.total);
          if (!payload.deliveries.length && offset < total) throw Error('Incomplete stock orders');
          rows.push(...payload.deliveries); offset += payload.deliveries.length;
          if (!payload.deliveries.length) break;
        }
        Object.assign(state,{loading:false,allRows:rows});
      })().catch(() => Object.assign(state,{loading:false,error:true})).finally(() => { if (page === 'Dashboard') paint(); });
    }
    if (state.loading || state.error) return state;
    const rows = state.allRows.filter(row => row.carrier === 'Palletways' && String(row.palletwaysDetails?.classification || '').trim().toUpperCase() === classification);
    return {available:true,total:rows.length,rows:rows.slice(0,30),preview:rows.slice(0,3),scope:'booked-in-no-current-ow-not-delivered'};
  }
  const utilityKeys = new Set(['collection-generator', 'order-identifier', 'order-flow-tracker']);
  const utilityStates = new Map();
  function utilityState(instance) {
    if (!utilityStates.has(instance)) utilityStates.set(instance, {order: '', message: '', result: null, version: 0});
    return utilityStates.get(instance);
  }
  function utilityResultMarkup(state, instance) {
    if (!state.result) return `<span>${esc(state.message)}</span>`;
    const result = state.result;
    if (result.flow) {
      const map = trackingOrderFlowMarkup({order: result.order, flow: result.flow},
        {compact: true, markerId: `utility-flow-arrow-${instance}`});
      return map ? `<div class="dash-order-flow">${map}</div>`
        : '<span>No replacement or credit/refund links found for this order.</span>';
    }

    const logo = purchaseStoreLogo({salesActivityDetails: {'Order Type': result.store}}, 'dash-identifier-store');
    const identifier = (label, value, attribute) => `<div><dt>${label}</dt><dd>${String(value || '').split(/\r?\n/).map(number => `<span class="dash-identifier-value"><span>${esc(number || 'Not recorded')}</span>${number ? `<button type="button" class="qd-customer-copy dash-identifier-copy" ${attribute}="${esc(number)}" aria-label="Copy ${label} ${esc(number)}" title="Copy ${label}">${ico('copy', 13, 1.8)}</button>` : ''}</span>`).join('')}</dd></div>`;
    const carrierIcon = {Palletways: 'palletwayicon.png', AMZ: 'amazonicon.webp', XDP: 'XDPiocn.png'}[result.courier];
    const fields = [identifier('Order ID', result.order, 'data-copy-order-number')];
    if (['Palletways', 'AMZ'].includes(result.courier)) fields.push(identifier('Tracking ID', result.trackingId, result.courier === 'AMZ' ? 'data-copy-amazon-tracking' : 'data-copy-palletways-tracking'));
    if (['Palletways', 'XDP'].includes(result.courier)) fields.push(identifier('Consignment No', result.consignmentNumber, 'data-copy-consignment-number'));
    return `<div class="dash-identifier-brands">${carrierIcon ? `<img src="/assets/${carrierIcon}" alt="" class="dash-identifier-carrier">` : ''}<strong>${esc(result.courier === 'AMZ' ? 'Amazon Shipping' : result.courier || 'Courier not recorded')}</strong>${logo || '<span class="dash-identifier-unknown">Store not recorded</span>'}</div>
      <dl class="dash-identifier-ids" style="--identifier-count:${fields.length}">${fields.join('')}</dl><button type="button" class="dash-widget-open dash-identifier-open" data-dash-order="${esc(result.order)}" aria-label="View Order Detail" title="View Order Detail"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg></button>`;
  }
  function utilityMarkup(definition, instance) {
    const state = utilityState(instance), position = widgetPositions()[instance];
    const collection = definition.key === 'collection-generator';
    const tracker = definition.key === 'order-flow-tracker';
    const numeric = collection || tracker;
    const steps = collection
      ? [['search', 'Enter order ID'], ['note', 'Note fills for you'], ['clipboardcheck', 'Review & save']]
      : tracker ? [['search', 'Enter order ID'], ['note', 'Follow the links'], ['pkg', 'See order statuses']]
      : [['search', 'Enter any ID'], ['pkg', 'Find the store'], ['truck', 'See linked IDs']];
    return `<article class="dash-widget dash-utility-widget dash-tone-${definition.tone}" style="grid-row:${position.row};grid-column:${position.column}" data-dash-widget="${instance}" data-dash-utility="${definition.key}" data-utility-editing="${editing}" draggable="false" aria-labelledby="dash-title-${instance}">
      <div class="dash-widget-head">${editing ? `<button class="dash-remove-widget" data-picker-remove="${instance}" aria-label="Remove ${definition.title}">&times;</button>` : ''}<span class="dash-widget-icon">${ico(definition.icon, 20)}</span><h3 id="dash-title-${instance}">${definition.title}</h3></div>
      <form class="dash-utility-form" data-utility-form="${instance}" ${editing ? 'inert' : ''}>
        <label for="utility-order-${instance}">${numeric ? 'Order ID' : 'Order ID / tracking ID / consignment no'}</label><div class="dash-utility-controls"><input id="utility-order-${instance}" name="order" type="text" inputmode="${numeric ? 'numeric' : 'text'}" ${numeric ? 'pattern="[0-9]{1,20}"' : ''} maxlength="${numeric ? 20 : 64}" autocomplete="off" required placeholder="${numeric ? 'Enter order ID' : 'Enter order, tracking or consignment ID'}" value="${esc(state.order)}" data-utility-order="${instance}"><button type="submit">${collection ? 'Generate' : tracker ? 'Track' : 'Verify'}</button></div>
        <div class="dash-utility-result" data-utility-result="${instance}" role="status" aria-live="polite">${utilityResultMarkup(state, instance)}</div>
        <div class="dash-utility-guide" aria-label="How it works" ${state.result ? 'hidden' : ''}>
          <div class="dash-utility-steps">${steps.map(([icon, label], index) => `<div class="dash-utility-step" style="--step:${index}"><span class="dash-utility-step-icon" aria-hidden="true">${ico(icon, 18)}</span><span>${label}</span></div>`).join('')}</div>
          <p>${collection ? 'Type an exact order ID to open a filled note. Check the details, then save it in the editor.' : tracker ? 'Enter an order ID to see its replacement and credit/refund flow. The searched order is green.' : 'Enter an order ID, Palletways or Amazon tracking ID, or Palletways or XDP consignment number.'}</p>
        </div>
      </form></article>`;
  }
  function paintUtilityResult(instance) {
    const node = document.querySelector(`[data-utility-result="${instance}"]`);
    if (node) node.innerHTML = utilityResultMarkup(utilityState(instance), instance);
    const guide = node?.parentElement.querySelector('.dash-utility-guide');
    if (guide) guide.hidden = Boolean(utilityState(instance).result);
  }
  async function lookupUtility(instance) {
    const state = utilityState(instance), orderId = state.order.trim();
    clearTimeout(state.timer);
    state.controller?.abort();
    const version = ++state.version;
    state.result = null;
    const collection = widgetType(instance) === 'collection-generator';
    const tracker = widgetType(instance) === 'order-flow-tracker';
    const numeric = collection || tracker;
    if (!(numeric ? /^\d{1,20}$/ : /^(?=.{1,64}$)(?=.*\d)[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$/).test(orderId)) {
      state.message = orderId ? (numeric ? 'Enter a numeric order ID.' : 'Enter an exact order, tracking or consignment number.') : '';
      paintUtilityResult(instance);
      return;
    }
    const controller = new AbortController();
    state.controller = controller;
    const timeout = setTimeout(() => controller.abort(), 60000);
    state.message = collection ? 'Generating collection note…' : 'Looking up order…';
    paintUtilityResult(instance);
    try {
      const response = await fetch(`/api/${collection ? 'collection-note' : tracker ? 'order-flow' : 'order-identifier'}?${new URLSearchParams({order: orderId})}`, {signal: controller.signal, cache: 'no-store'});
      const result = await response.json();
      if (version !== state.version) return;
      if (!response.ok) throw new Error(result.error || 'Order lookup failed. Try again.');
      if (!result.found) state.message = result.message || (numeric ? 'Order not found. Check the exact order ID.' : 'No match found. Check the exact order, tracking or consignment number.');
      else if (collection) {
        // The existing editor automatically fills the note from this exact order.
        if (page === 'Dashboard' && !editing && document.querySelector(`[data-utility-order="${instance}"]`)) {
          location.assign(`./collective-note.html?${new URLSearchParams({view: 'create', order: orderId})}`);
        }
      } else state.result = result;
    } catch (error) {
      if (version !== state.version) return;
      state.message = error.name === 'AbortError' ? 'Lookup timed out. Press Enter to retry.' : error.message;
    } finally {
      clearTimeout(timeout);
      if (version === state.version) paintUtilityResult(instance);
    }
  }
  document.addEventListener('input', event => {
    const input = event.target.closest('[data-utility-order]');
    if (!input || editing) return;
    const instance = input.dataset.utilityOrder, state = utilityState(instance);
    clearTimeout(state.timer);
    state.controller?.abort();
    state.version++;
    state.order = input.value;
    state.result = null;
    state.message = '';
    paintUtilityResult(instance);
    if (state.order.trim()) state.timer = setTimeout(() => {
      if (input.isConnected && page === 'Dashboard' && !editing) lookupUtility(instance);
    }, 800);
  });
  document.addEventListener('submit', event => {
    const form = event.target.closest('[data-utility-form]');
    if (!form) return;
    event.preventDefault();
    if (!editing) lookupUtility(form.dataset.utilityForm);
  });
  function widgetMarkup(definition, instance = definition.key) {
    if (utilityKeys.has(definition.key)) return utilityMarkup(definition, instance);
    const month = definition.key === 'cancelled' && sizes[instance + '-period'] === 'month';
    const hideB2b = TrackingVisibility.palletwaysB2bEnabled();
    const unbookedClass = !hideB2b && sizes[instance + '-class'] === 'B2B' ? 'B2B' : 'B2C';
    const cohort = month ? 'cancelled-month' : definition.key === 'palletways-unbooked' ? 'palletways-unbooked-' + unbookedClass.toLowerCase() : definition.key;
    const title = month ? "This Month's OW Cancelled Orders" : definition.title;
    const savedState = definition.key === 'palletways-unbooked' ? unbookedWidgetData(unbookedClass) : month ? (live() ? monthlyCancelledData() : localData('month').widgets.cancelled) : data()?.widgets?.[definition.key];
    const expectedScope = {cancelled: 'today', 'palletways-unbooked': 'booked-in-no-current-ow-not-delivered'}[definition.key];
    const needsServerUpdate = live() && !month && expectedScope && savedState && savedState.scope !== expectedScope;
    const sourceUnavailable = definition.key !== 'returns' && savedState?.available === false;
    const state = needsServerUpdate || sourceUnavailable ? null : savedState;
    const unavailable = definition.key === 'returns';
    const count = unavailable || needsServerUpdate || sourceUnavailable || savedState?.error ? '—' : state?.loading ? '...' : state ? Number(state.total).toLocaleString('en-GB') : loading ? '…' : '—';
    const detail = savedState?.loading ? (definition.key === 'palletways-unbooked' ? 'Loading orders...' : 'Loading monthly orders...') : savedState?.error ? 'Orders unavailable' : definition.key === 'palletways-unbooked' ? 'Palletways ' + unbookedClass + ' - not booked in' : month ? 'Current month - UK order date' : needsServerUpdate ? (definition.key === 'cancelled' ? 'Restart server to apply today-only filter' : 'Restart server to apply Sales Activity matching') : sourceUnavailable ? savedState.reason || 'Waiting for source data' : unavailable ? 'Planned for Version 3' : !state && error ? 'Data unavailable — retry below' : !state ? 'Loading saved orders…' : definition.subtitle;
    const previewRows = state?.rows || state?.preview || [];
    const previewRow = item => `<button type="button" class="dash-preview-row" data-dash-order="${esc(item.id || item.order)}" aria-label="Open order ${esc(item.order)}"><span class="dash-order-id">${orderLabel(item)}</span><time title="Order date">${esc(item.orderDate ? new Date(`${item.orderDate}T12:00:00`).toLocaleDateString('en-GB', {day: 'numeric', month: 'short'}) : '-')}</time></button>`;
    const preview = previewRows.length ? `<div class="dash-preview-page" style="--preview-count:${Math.max(4, previewRows.length)}">${previewRows.map(item => previewRow(item)).join('')}</div>` : '';
    const periodSwitch = definition.key === 'palletways-unbooked' ? hideB2b ? '<span class="dash-unbooked-class-label">B2C</span>' : `<div class="dash-period-switch" role="group" aria-label="Palletways classification">${['B2C','B2B'].map(value => `<button type="button" data-unbooked-class="${value}" data-widget-instance="${instance}" aria-pressed="${unbookedClass === value}">${value}</button>`).join('<span aria-hidden="true">|</span>')}</div>` : definition.key === 'cancelled' ? `<div class="dash-period-switch" role="group" aria-label="Cancelled orders period">${[['daily','Daily'],['month','Month']].map(([value,label]) => `<button type="button" data-cancelled-period="${value}" data-widget-instance="${instance}" aria-pressed="${(month ? 'month' : 'daily') === value}">${label}</button>`).join('<span aria-hidden="true">|</span>')}</div>` : '';
    return `<article class="dash-widget dash-tone-${definition.tone}${units(instance) === 3 ? ' dash-widget-tall' : ''}" style="grid-row:${widgetPositions()[instance].row};grid-column:${widgetPositions()[instance].column}" data-dash-widget="${instance}" draggable="false" aria-labelledby="dash-title-${instance}">
      <div class="dash-widget-head">${editing ? `<button class="dash-remove-widget" data-picker-remove="${instance}" aria-label="Remove ${title}">&times;</button>` : ''}<span class="dash-widget-icon">${ico(definition.icon, 20)}</span><h3 id="dash-title-${instance}">${title}</h3>
        ${units(instance) === 1 ? periodSwitch : ''}
        ${unavailable ? '<span class="dash-coming">V3</span>' : `<button type="button" class="dash-widget-open" data-dash-view="${cohort}" ${needsServerUpdate || sourceUnavailable ? 'disabled' : ''} aria-label="View all ${title}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 17 17 7M7 7h10v10"/></svg></button>`}</div>
      ${units(instance) === 1 ? `<div class="dash-widget-body"><div class="dash-widget-total" style="--dash-count-digits:${String(count).length}"><strong>${count}</strong></div>
        <div class="dash-widget-preview">${preview ? `<div class="dash-preview-track" data-preview-rows="${previewRows.length}">${preview}</div>` : `<span class="dash-preview-empty">${unavailable ? 'Workflow coming soon' : state ? 'No matching orders' : ''}</span>`}</div></div>` : ''}
      ${units(instance) === 3 ? `<span class="dash-table-record-total" aria-label="${count} total records">${count} records</span>` : ''}
      ${units(instance) === 3 ? definition.key === 'cancelled' ? cancelledTableMarkup(state, month, detail, instance) : `<div class="dash-table-scroll"><table${definition.key === 'hold' ? ' class="dash-hold-table"' : ''}><thead><tr><th>${tableOrderHeading(instance)}</th><th>Customer</th>${['hold', 'out-of-stock'].includes(definition.key) ? '' : '<th>Status</th>'}<th>Date</th></tr></thead><tbody>${tableRows(state, instance).map(item => `<tr><td><button type="button" data-dash-order="${esc(item.id || item.order)}">${orderLabel(item)}</button></td><td>${esc(item.cust || '-' )}</td>${['hold', 'out-of-stock'].includes(definition.key) ? '' : `<td>${esc((['palletways-next-day', 'palletways-unbooked'].includes(definition.key) ? item.palletwaysSheetStatus : item.st) || '-')}</td>`}<td>${esc(item.orderDate || '-' )}</td></tr>`).join('') || `<tr><td colspan="${['hold', 'out-of-stock'].includes(definition.key) ? 3 : 4}">${esc(tableSearch.get(instance)?.query ? 'No matching order IDs' : detail)}</td></tr>`}</tbody></table></div>` : ''}
      <div class="dash-widget-foot"><span>${esc(detail)}</span>${units(instance) === 3 ? periodSwitch : ''}</div>
    </article>`;
  }
  const previewOffsets = new WeakMap();
  setInterval(() => {
    if (document.hidden || editing || widgetDrag || pickerDrag) return;
    document.querySelectorAll('#dash-widget-grid .dash-widget:not(.dash-widget-tall) .dash-preview-track').forEach(track => {
      const card = track.closest('.dash-widget'), count = Number(track.dataset.previewRows);
      if (count <= 4 || card.matches(':hover') || card.contains(document.activeElement)) return;
      const row = (previewOffsets.get(track) || 0) >= count - 4 ? 0 : (previewOffsets.get(track) || 0) + 1;
      previewOffsets.set(track, row);
      if (row === 0) track.style.transition = 'none';
      track.style.transform = `translateY(-${row * 100 / 4}%)`;
      if (row === 0) { void track.offsetHeight; track.style.removeProperty('transition'); }
    });
  }, 5000);
  const tableScrollPositions = new WeakMap();
  let lastTableScrollFrame = 0;
  function scrollTallTables(now) {
    const elapsed = lastTableScrollFrame ? Math.min(now - lastTableScrollFrame, 50) : 0;
    lastTableScrollFrame = now;
    if (!document.hidden && !editing && !widgetDrag && !pickerDrag && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      document.querySelectorAll('#dash-widget-grid .dash-widget-tall .dash-table-scroll').forEach(table => {
        if (table.matches(':hover') || table.contains(document.activeElement)) return;
        const maximum = table.scrollHeight - table.clientHeight;
        if (maximum <= 0) return;
        let state = tableScrollPositions.get(table);
        if (!state || Math.abs(table.scrollTop - state.expected) > 1) state = {position:table.scrollTop, expected:table.scrollTop};
        if (state.wait > 0) {
          state.wait -= elapsed;
          if (state.wait <= 0) state.position = 0;
        } else {
          state.position = Math.min(maximum, state.position + elapsed * .008);
          if (state.position >= maximum) state.wait = 2000;
        }
        table.scrollTop = state.position; state.expected = table.scrollTop;
        tableScrollPositions.set(table,state);
      });
    }
    requestAnimationFrame(scrollTallTables);
  }
  requestAnimationFrame(scrollTallTables);
  function transitionChildren(container, markup, keyFor) {
    const template = document.createElement('template'); template.innerHTML = markup;
    const old = new Map([...container.children].map(node => [keyFor(node), node]));
    const before = new Map([...old.values()].map(node => [node, AtlasViewport.rect(node)]));
    const animate = !matchMedia('(prefers-reduced-motion: reduce)').matches;
    const kept = [];
    for (const fresh of template.content.children) {
      const key = keyFor(fresh); let node = old.get(key);
      if (node && node.classList.contains('dash-widget-tall') !== fresh.classList.contains('dash-widget-tall')) node = null;
      if (node) {
        old.delete(key);
        if (node.innerHTML !== fresh.innerHTML && (!node.dataset.dashUtility || node.dataset.utilityEditing !== fresh.dataset.utilityEditing)) {
          node.innerHTML = fresh.innerHTML;
          if (fresh.dataset.dashUtility) node.dataset.utilityEditing = fresh.dataset.utilityEditing;
        }
        if (fresh.dataset.dashWidget || fresh.classList.contains('dash-add-slot')) { node.style.gridRow = fresh.style.gridRow; node.style.gridColumn = fresh.style.gridColumn; }
        node.classList.remove('is-picker-target');
      } else node = fresh.cloneNode(true);
      container.append(node); kept.push(node);
    }
    old.forEach(node => {
      if (animate && !node.classList.contains('dash-add-slot')) {
        const rect = before.get(node), clone = node.cloneNode(true);
        clone.querySelectorAll('[id]').forEach(item => item.removeAttribute('id'));
        clone.removeAttribute('id'); clone.inert = true; clone.setAttribute('aria-hidden','true');
        const opacity = getComputedStyle(node).opacity;
        Object.assign(clone.style, {position:'fixed', left:rect.left+'px', top:rect.top+'px', width:rect.width+'px', height:rect.height+'px', margin:'0', zIndex:'40', pointerEvents:'none', font:getComputedStyle(node).font});
        document.body.append(clone);
        clone.animate([{opacity,transform:'scale(1)'},{opacity:0,transform:'scale(.96)'}],{duration:160,easing:'ease-out',fill:'forwards'}).finished.catch(()=>{}).then(()=>clone.remove());
      }
      node.remove();
    });
    if (!animate) return;
    kept.forEach(node => {
      const from = before.get(node), to = AtlasViewport.rect(node);
      if (from) {
        const x=from.left-to.left, y=from.top-to.top;
        if (Math.abs(x)+Math.abs(y) > 1) node.animate([{transform:`translate(${x}px,${y}px)`},{transform:'translate(0,0)'}],{duration:220,easing:'cubic-bezier(.2,.8,.25,1)'});
      } else if (node.dataset.dashWidget !== landingKey && !node.classList.contains('dash-add-slot')) {
        node.animate([{opacity:0,transform:'translateY(5px) scale(.97)'},{opacity:1,transform:'translateY(0) scale(1)'}],{duration:200,easing:'ease-out'});
      }
    });
  }
  function paint() {
    if (widgetDrag || pickerDrag) { widgetPaintPending = true; return; }
    const grid = document.getElementById('dash-widget-grid');
    if (!grid) return;
    grid.style.setProperty('--dash-widget-rows', 3);
    transitionChildren(grid, order.map(key => widgetMarkup(selectedDefinition(key), key)).join('') + (editing ? emptySlotsMarkup() : ''), node => node.dataset.dashWidget || 'slot-' + node.style.gridRow + '-' + node.style.gridColumn);
    const message = document.getElementById('dash-data-message');
    if (message) {
      message.hidden = !error;
      message.innerHTML = `Dashboard refresh unavailable.${result ? ' Last loaded counts are shown.' : ''} <button type="button" data-dash-retry>Retry</button>`;
    }
    const updated = document.getElementById('dash-last-update');
    if (updated) updated.textContent = result?.syncedAt ? `Last update: ${integrationTime(result.syncedAt)}` : liveSummary?.syncedAt ? `Last update: ${integrationTime(liveSummary.syncedAt)}` : 'Saved order index';
  }
  async function load(force = false) {
    if (!live() || page !== 'Dashboard') return;
    const key = JSON.stringify([carrier, liveSummary?.syncedAt, visibility()]);
    if (!force && key === loadedKey && (loading || Date.now() - checkedAt < 300000)) { paint(); return; }
    const serial = ++request;
    loadedKey = key; loading = true; error = false;
    paint();
    try {
      const payload = await ApiClient.get(`/dashboard?${new URLSearchParams({carrier, ...visibility()})}`);
      if (!payload.widgets || !definitions.filter(item => !utilityKeys.has(item.key)).every(item => payload.widgets[item.key])) throw new Error('Invalid dashboard response');
      if (serial !== request) return;
      await Promise.allSettled(definitions.map(async definition => {
        if (utilityKeys.has(definition.key)) return;
        const state = payload.widgets[definition.key];
        const needsActivityFields = state.rows?.some(row => definition.key === 'cancelled' ? !Object.prototype.hasOwnProperty.call(row, 'orderDateTime') || !Object.prototype.hasOwnProperty.call(row, 'deliveryMethodRaw') : ['palletways-next-day', 'palletways-unbooked'].includes(definition.key) && !Object.prototype.hasOwnProperty.call(row, 'palletwaysSheetStatus'));
        if (definition.key === 'returns' || state.available === false || (!needsActivityFields && (state.rows?.length || 0) >= Math.min(30, Number(state.total)))) return;
        const rows = await ApiClient.get(`/deliveries?${new URLSearchParams({dashboard_widget: definition.key, carrier, limit: '30', ...visibility()})}`);
        if (Array.isArray(rows.deliveries)) state.rows = rows.deliveries;
      }));
      if (serial !== request) return;
      result = payload;
    } catch (_) {
      if (serial !== request) return;
      error = true;
    } finally {
      if (serial === request) { loading = false; checkedAt = Date.now(); if (page === 'Dashboard') paint(); }
    }
  }
  function filters(label, icon, options, selected, kind) {
    const chips = options.map(([value, text]) => `<button type="button" data-dash-filter="${kind}" data-value="${esc(value)}" aria-pressed="${value === selected}" class="${value === selected ? 'is-active' : ''}">${text}</button>`).join('');
    return `<section class="dash-filter-panel" aria-label="${label}"><h2>${ico(icon, 17)}${label}</h2><div class="dash-filter-chips" role="group" aria-label="${label}">${chips}</div><select class="dash-filter-select" aria-label="${label}" data-dash-select="${kind}">${options.map(([value, text]) => `<option value="${esc(value)}" ${value === selected ? 'selected' : ''}>${text}</option>`).join('')}</select></section>`;
  }
  function render() {
    finishWidgetDrag(false, false);
    return `<div class="dashboard-home${editing ? ' is-customizing' : ''}" ${editing ? `style="grid-template-rows:${frozenRows}"` : ''}>
      <section class="dash-searchbar" ${editing ? 'inert' : ''}><div class="dash-search-wrap"><label class="db-search">${ico('search', 21)}<input id="dq" type="search" value="${esc(dq)}" placeholder="Search tracking, order, customer, phone or postcode" aria-label="Search a delivery" oninput="dq=this.value;scheduleDashboardSearch()"><span class="dash-search-updated" id="dash-last-update">${liveSummary?.syncedAt ? `Last update: ${esc(integrationTime(liveSummary.syncedAt))}` : 'Saved order index'}</span><button type="button" class="db-search-button" data-dashboard-search>Search</button></label><div id="dres"></div></div></section>
      ${editing ? editorMarkup() : ''}
      <div class="dash-filter-row" ${editing ? 'inert' : ''}>${storeLinks()}${filters('Filter by Delivery Method', 'truck', methods, carrier, 'carrier')}</div>
      <div class="dash-workspace-heading"><div><h1>${ico('Dashboard', 23)}My Dashboard</h1><p>Choose and arrange your widgets to create a personalized dashboard.</p></div><div class="dash-workspace-actions"><button type="button" data-dash-customize aria-expanded="${editing}">${editing ? 'Complete' : `${ico('Settings', 15)}Customize Widgets`}</button><button type="button" data-dash-widget-guide aria-label="Replay the widget walkthrough">${ico('alert', 15)}Widget guide</button><button type="button" data-dash-reset>${ico('back', 15)}Reset to Default</button></div><p id="dash-data-message" role="status" hidden></p></div>
      <div class="dash-widget-grid" id="dash-widget-grid" style="--dash-widget-rows:${3}">${order.map(key => widgetMarkup(selectedDefinition(key), key)).join('')}${editing ? emptySlotsMarkup() : ''}</div>
    </div>`;
  }
  function setCarrier(value) {
    carrier = value;
    result = null; checkedAt = 0; R();
  }
  let pickerPage = 0;
  let pickerPageCount = 1, pickerAutoTimer = null;
  const pickerPageSize = 8;
  function schedulePickerAutoSlide() {
    clearTimeout(pickerAutoTimer);
    if (!editing || closingPicker || page !== 'Dashboard') return;
    pickerAutoTimer = setTimeout(() => {
      if (!document.querySelector('.dash-editor') || !editing || closingPicker || page !== 'Dashboard') return;
      if (document.hidden || pickerDrag || pendingPicker || widgetDrag || pendingWidgetPointer
        || document.querySelector('.dash-widget-tour')) {
        schedulePickerAutoSlide();
        return;
      }
      if (pickerPageCount > 1) {
        pickerPage = (pickerPage + 1) % pickerPageCount;
        refreshPicker(false, 1);
      } else schedulePickerAutoSlide();
    }, 5000);
  }
  function editorMarkup() {
    const available = definitions.flatMap(def => (utilityKeys.has(def.key) ? ['1x1'] : ['1x1', '1x3']).filter(size => (pickerFilter === 'all' || size === pickerFilter) && !order.some(key => widgetType(key) === def.key && units(key) === (size === '1x3' ? 3 : 1))).map(size => ({def, size})));
    const pageCount = Math.max(1, Math.ceil(available.length / pickerPageSize));
    pickerPageCount = pageCount;
    pickerPage = Math.max(0, Math.min(pickerPage, pageCount - 1));
    const visible = available.slice(pickerPage * pickerPageSize, (pickerPage + 1) * pickerPageSize);
    return `<section class="dash-editor" aria-label="Widget gallery"><nav aria-label="Filter widget sizes">${['all','1x1','1x3'].map(size => `<button type="button" data-picker-filter="${size}" aria-pressed="${pickerFilter === size}">${size === 'all' ? 'All' : size.replace('x', '&times;')}</button>`).join('')}</nav><div class="dash-picker-row"><button type="button" class="dash-picker-arrow" data-picker-page="-1" aria-label="Previous widget page" ${pickerPage === 0 ? 'disabled' : ''}>${ico('back', 20)}</button><div class="dash-picker-track">${visible.map(({def, size}) => `<button type="button" draggable="true" class="dash-picker-tile dash-tone-${def.tone}" data-picker-key="${def.key}" data-picker-size="${size}" aria-label="Drag ${def.title}, ${size}"><span class="dash-picker-icon">${ico(def.icon, 25)}${size === '1x3' ? '<span class="dash-picker-table-lines"></span>' : ''}</span><strong>${def.title}</strong><small>(${size.replace('x', '&times;')})</small></button>`).join('')}</div><button type="button" class="dash-picker-arrow" data-picker-page="1" aria-label="Next widget page" ${pickerPage === pageCount - 1 ? 'disabled' : ''}>${ico('right', 20)}</button></div><span class="dash-picker-pagination" aria-live="polite">${pickerPage + 1} / ${pageCount}</span><span id="dash-editor-message" class="dash-picker-status" role="status"></span></section>`;
  }
  function customize() {
    if (closingPicker) return;
    if (editing) {
      clearTimeout(pickerAutoTimer);
      finishPicker(false); closingPicker = true;
      const editor = document.querySelector('.dash-editor');
      const close = () => { editing = false; closingPicker = false; R(); if (!sidebarWasCollapsed) setSidebarCollapsed(false); };
      if (editor && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        editor.classList.add('is-closing');
        const motion = editor.animate([{opacity: 1, transform: 'translateY(0)'}, {opacity: 0, transform: 'translateY(-6px)'}], {duration: 180, easing: 'ease-in', fill: 'forwards'});
        motion.finished.catch(() => {}).then(close);
      } else close();
      return;
    }
    const home = document.querySelector('.dashboard-home');
    frozenRows = getComputedStyle(home).gridTemplateRows;
    pinWidgetPositions();
    sidebarWasCollapsed = document.querySelector('.app').classList.contains('cl');
    setSidebarCollapsed(true); document.querySelector('.app')?.classList.remove('mobile-open');
    editing = true; pickerFilter = 'all'; pickerPage = 0; R();
    schedulePickerAutoSlide();
    let seen = false;
    try { seen = localStorage.getItem('deliverydesk-widget-tour-v1') === 'seen'; } catch {}
    if (!seen) showWidgetTour();
  }
  function showWidgetTour() {
    if (document.querySelector('.dash-widget-tour')) return;
    const steps = [
      ['Add a widget', 'Drag a widget from the gallery into a dashboard slot. Choose a compact card or a tall table.'],
      ['Make it your own', 'Drag your dashboard cards to rearrange them. Use the × on a card to remove it and return it to the gallery.'],
      ['You’re all set', 'Changes save automatically. Select Complete when you’re finished. Reset to Default restores the original layout.'],
    ];
    const dialog = document.createElement('dialog');
    dialog.className = 'dash-widget-tour';
    dialog.setAttribute('aria-labelledby', 'dash-widget-tour-title');
    dialog.setAttribute('aria-describedby', 'dash-widget-tour-text');
    let step = 0;
    const paintTour = () => {
      dialog.dataset.step = step;
      dialog.innerHTML = `<button type="button" class="dash-tour-close" data-tour-close aria-label="Close widget walkthrough">${ico('x', 18)}</button>
        <div class="dash-tour-scene" aria-hidden="true"><div class="dash-tour-gallery"><span>${ico('pkg', 22)}</span><span>${ico('truck', 22)}</span><span>${ico('cal', 22)}</span></div><div class="dash-tour-board"><div><b>12</b><i></i></div><div><b>8</b><i></i></div><div class="dash-tour-slot">+</div></div><div class="dash-tour-demo-card">${ico('pkg', 22)}<b>24</b><span>×</span></div><div class="dash-tour-pointer">${ico('right', 22)}</div><span class="dash-tour-saved">${ico('check', 14)} Saved automatically</span></div>
        <div class="dash-tour-copy" aria-live="polite"><small>WIDGET WALKTHROUGH · ${step + 1} OF 3</small><h2 id="dash-widget-tour-title">${steps[step][0]}</h2><p id="dash-widget-tour-text">${steps[step][1]}</p></div>
        <footer><button type="button" class="dash-tour-secondary" ${step ? 'data-tour-back' : 'data-tour-close'}>${step ? 'Back' : 'Skip tour'}</button><div class="dash-tour-dots" aria-hidden="true">${steps.map((_, index) => `<i class="${index === step ? 'is-current' : ''}"></i>`).join('')}</div><button type="button" class="dash-tour-next" data-tour-next>${step === 2 ? 'Start customizing' : 'Next'} ${ico('right', 14)}</button></footer>`;
    };
    const dismiss = () => dialog.close();
    dialog.addEventListener('click', event => {
      if (event.target.closest('[data-tour-close]')) dismiss();
      if (event.target.closest('[data-tour-back]')) { step--; paintTour(); dialog.querySelector('[data-tour-next]').focus(); }
      if (event.target.closest('[data-tour-next]')) {
        if (step === steps.length - 1) dismiss();
        else { step++; paintTour(); dialog.querySelector('[data-tour-next]').focus(); }
      }
    });
    dialog.addEventListener('close', () => {
      try { localStorage.setItem('deliverydesk-widget-tour-v1', 'seen'); } catch {}
      dialog.remove();
      document.querySelector('.dash-editor [data-picker-filter]')?.focus();
    }, {once: true});
    paintTour(); document.body.append(dialog); dialog.showModal();
    dialog.querySelector('[data-tour-next]').focus();
  }
  let finishPickerSlide = () => {};
  let pickerSliding = false;
  function refreshPicker(updateGrid = true, direction = 0) {
    schedulePickerAutoSlide();
    finishPickerSlide();
    const editor = document.querySelector('.dash-editor');
    if (editor) {
      const template = document.createElement('template'); template.innerHTML = editorMarkup(); const fresh = template.content.firstElementChild;
      editor.querySelectorAll('[data-picker-filter]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.pickerFilter === pickerFilter)));
      editor.querySelector('.dash-picker-pagination').replaceWith(fresh.querySelector('.dash-picker-pagination'));
      editor.querySelectorAll('[data-picker-page]').forEach(button => {
        button.disabled = fresh.querySelector(`[data-picker-page="${button.dataset.pickerPage}"]`).disabled;
      });
      const track = editor.querySelector('.dash-picker-track');
      const markup = fresh.querySelector('.dash-picker-track').innerHTML;
      if (direction && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        const outgoing = track.cloneNode(true);
        outgoing.inert = true;
        outgoing.setAttribute('aria-hidden', 'true');
        Object.assign(outgoing.style, {position: 'absolute', inset: '0', pointerEvents: 'none'});
        const distance = track.clientWidth * direction;
        pickerSliding = true;
        track.innerHTML = markup;
        const incoming = [...track.children];
        track.append(outgoing);
        const options = {duration: 320, easing: 'cubic-bezier(.22,.7,.25,1)', fill: 'both'};
        const motions = [outgoing.animate([
          {transform: 'translateX(0)'}, {transform: `translateX(${-distance}px)`},
        ], options), ...incoming.map(tile => tile.animate([
          {transform: `translateX(${distance}px)`}, {transform: 'translateX(0)'},
        ], options))];
        const cleanup = () => { motions.forEach(motion => motion.cancel()); outgoing.remove(); };
        finishPickerSlide = cleanup;
        Promise.allSettled(motions.map(motion => motion.finished)).then(() => {
          cleanup();
          if (finishPickerSlide === cleanup) { pickerSliding = false; finishPickerSlide = () => {}; }
        });
      } else {
        pickerSliding = false;
        finishPickerSlide = () => {};
        const existing = new Map([...track.children].map(node => [node.dataset.pickerKey + ':' + node.dataset.pickerSize, node]));
        const tiles = [...fresh.querySelector('.dash-picker-track').children].map(node => existing.get(node.dataset.pickerKey + ':' + node.dataset.pickerSize) || node);
        track.replaceChildren(...tiles);
      }
    }
    if (!updateGrid) return;
    paint();

  }
  function addPickerWidget(key, size, target, dropColumn, dropRow = 1) {
    pinWidgetPositions();
    const positions = widgetPositions();
    const column = dropColumn || Number(positions[target]?.column || 1);
    const row = size === '1x3' ? 1 : dropRow;
    order = order.filter(item => {
      if (item === key) return false;
      const pos = positions[item];
      return !(Number(pos.column) === column && (size === '1x3' || units(item) === 3 || parseInt(pos.row, 10) === row));
    });
    sizes[key] = size; sizes[key + '-column'] = column - 1;
    sizes[key + '-slot'] = (row - 1) * 3 + column - 1;
    order.push(key); save(); refreshPicker();
  }
  document.addEventListener('click', event => {
    const filter = event.target.closest('[data-picker-filter]');
    if (filter) { pickerFilter = filter.dataset.pickerFilter; pickerPage = 0; refreshPicker(false); }
    const pager = event.target.closest('[data-picker-page]');
    if (pager && !pager.disabled && !pickerSliding && !pickerDrag && !pendingPicker) { const direction = Number(pager.dataset.pickerPage); pickerPage += direction; refreshPicker(false, direction); }
    const remove = event.target.closest('[data-picker-remove]');
    if (remove) { pinWidgetPositions(); order = order.filter(key => key !== remove.dataset.pickerRemove); save(); refreshPicker(); }
  });
  let pickerDrag = null, pendingPicker = null;
  function movePicker(x, y) {
    if (!pickerDrag) return;
    const drag = pickerDrag;
    drag.ghost.style.transform = `translate3d(${x - drag.width * .47}px, ${y - drag.height * .47}px, 0) scale(.94)`;
    // Hit testing uses the final card size while the pickup reveal animates.
    const floating = {left:x-drag.width*.47, top:y-drag.height*.47, right:x+drag.width*.47, bottom:y+drag.height*.47, width:drag.width*.94, height:drag.height*.94};
    let best = -1, overlap = 0;
    drag.slots.forEach((slot, index) => {
      const w = Math.max(0, Math.min(floating.right, slot.right) - Math.max(floating.left, slot.left));
      const h = Math.max(0, Math.min(floating.bottom, slot.bottom) - Math.max(floating.top, slot.top));
      const fraction = w * h / (floating.width * floating.height);
      if (fraction >= .8 && fraction > overlap) { best = index; overlap = fraction; }
    });
    drag.ready = best;
    drag.slotElements.forEach((slot, index) => slot.classList.toggle('is-widget-drop-ready', index === best));
    drag.grid.querySelectorAll('[data-dash-widget]').forEach(card => {
      const column = Number(card.style.gridColumn);
      const row = parseInt(card.style.gridRow, 10);
      const slot = drag.slots[best];
      const affected = slot && column === slot.column && (drag.size === '1x3' || row === slot.row || card.classList.contains('dash-widget-tall'));
      card.classList.toggle('is-picker-target', !!affected);
    });
  }
  function beginPicker(pointer, event) {
    const grid = document.getElementById('dash-widget-grid'), rect = AtlasViewport.rect(grid);
    const style = getComputedStyle(grid), gap = parseFloat(style.columnGap), rowGap = parseFloat(style.rowGap);
    const width = (rect.width - gap * 2) / 3, cellHeight = (rect.height - rowGap * 2) / 3;
    const height = pointer.size === '1x3' ? rect.height : cellHeight;
    const priorOrder = order, priorSizes = sizes;
    order = [pointer.key]; sizes = {...sizes, [pointer.key]: pointer.size};
    const template = document.createElement('template'); template.innerHTML = widgetMarkup(selectedDefinition(pointer.key), pointer.key);
    order = priorOrder; sizes = priorSizes;
    const ghost = template.content.firstElementChild;
    ghost.classList.remove('dash-widget'); ghost.classList.add('dash-widget-drag-preview');
    ghost.removeAttribute('data-dash-widget'); ghost.removeAttribute('aria-labelledby');
    ghost.querySelectorAll('[id]').forEach(node => node.removeAttribute('id'));
    ghost.querySelector('[data-picker-remove]')?.remove();
    ghost.inert = true; ghost.setAttribute('aria-hidden', 'true');
    Object.assign(ghost.style, {width: width + 'px', height: height + 'px', font: getComputedStyle(grid.querySelector('.dash-widget') || grid).font});
    // Move the shell with the cursor; reveal the card inside it independently.
    // Scaling the moving shell would also scale its viewport translation.
    const shell = document.createElement('div');
    shell.className = 'dash-picker-drag-shell';
    Object.assign(shell.style, {width: width + 'px', height: height + 'px'});
    ghost.style.position = 'absolute';
    shell.append(ghost); document.body.append(shell);
    const layer = document.createElement('div'); layer.className = 'dash-widget-slots dash-picker-slots'; layer.inert = true;
    const slots = [], slotElements = [];
    for (let row = 0; row < (pointer.size === '1x3' ? 1 : 3); row++) for (let col = 0; col < 3; col++) {
      const left = col * (width + gap), top = row * (cellHeight + rowGap);
      slots.push({left: rect.left + left, right: rect.left + left + width, top: rect.top + top, bottom: rect.top + top + height, column: col + 1, row: row + 1});
      const slot = document.createElement('div'); slot.className = 'dash-widget-slot';
      Object.assign(slot.style, {left: left + 'px', top: top + 'px', width: width + 'px', height: height + 'px'});
      layer.append(slot); slotElements.push(slot);
    }
    grid.append(layer); grid.classList.add('is-widget-reordering');
    pickerDrag = {...pointer, grid, ghost: shell, layer, slots, slotElements, width, height, ready: -1};
    pointer.tile.classList.add('is-picker-dragging'); pointer.tile.setPointerCapture(pointer.pointerId);
    document.body.classList.add('is-dashboard-dragging'); movePicker(AtlasViewport.x(event), AtlasViewport.y(event));
    if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const icon = AtlasViewport.rect(pointer.tile.querySelector('.dash-picker-icon'));
      const left = AtlasViewport.x(event) - width * .47, top = AtlasViewport.y(event) - height * .47;
      const fromX = (icon.left - left) / .94, fromY = (icon.top - top) / .94;
      const scaleX = icon.width / (width * .94), scaleY = icon.height / (height * .94);
      pickerDrag.pickupMotion = ghost.animate([
        {opacity: 0, transform: `translate(${fromX}px, ${fromY}px) scale(${scaleX}, ${scaleY})`},
        {opacity: 1, transform: 'translate(0px, 0px) scale(1)'},
      ], {duration: 200, easing: 'cubic-bezier(.2,.8,.25,1)'});
      layer.animate([{opacity:0},{opacity:1}], {duration:180,easing:'ease-out'});
    }
  }
  function finishPicker(commit) {
    pendingPicker = null;
    if (!pickerDrag) return;
    const drag = pickerDrag; pickerDrag = null;
    drag.pickupMotion?.cancel();
    if (drag.tile.hasPointerCapture(drag.pointerId)) drag.tile.releasePointerCapture(drag.pointerId);
    drag.tile.classList.remove('is-picker-dragging'); drag.layer.remove();
    drag.grid.classList.remove('is-widget-reordering');
    if (!commit || drag.ready < 0) drag.grid.querySelectorAll('.is-picker-target').forEach(card => card.classList.remove('is-picker-target'));
    document.body.classList.remove('is-dashboard-dragging');
    if (commit && drag.ready >= 0) {
      const slot = drag.slots[drag.ready];
      const target = [...drag.grid.querySelectorAll('[data-dash-widget]')].find(card => Number(card.style.gridColumn) === slot.column && (parseInt(card.style.gridRow, 10) === slot.row || card.classList.contains('dash-widget-tall')));
      landingKey = drag.key;
      addPickerWidget(drag.key, drag.size, target?.dataset.dashWidget, slot.column, slot.row);
      landingKey = '';
      const destination = document.querySelector(`[data-dash-widget="${drag.key}"]`);
      if (destination && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
        const bounds = AtlasViewport.rect(destination); destination.style.opacity = '0';
        const motion = drag.ghost.animate([{transform: drag.ghost.style.transform}, {transform: `translate3d(${bounds.left}px, ${bounds.top}px, 0) scale(1)`}], {duration: 180, easing: 'cubic-bezier(.2,.8,.25,1)', fill: 'forwards'});
        motion.finished.catch(() => {}).then(() => { drag.ghost.remove(); destination.style.removeProperty('opacity'); });
        return;
      }
    }
    if (!commit && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      drag.ghost.animate([{opacity:1},{opacity:0}], {duration:140, easing:'ease-out', fill:'forwards'}).finished.catch(()=>{}).then(()=>drag.ghost.remove());
    } else drag.ghost.remove();
    if (widgetPaintPending) { widgetPaintPending = false; refreshPicker(); }
  }
  document.addEventListener('pointerdown', event => {
    const tile = event.target.closest('[data-picker-key]');
    if (!tile || event.button !== 0 || pickerDrag || widgetDrag) return;
    event.preventDefault(); pendingPicker = {tile, key: widgetInstance(tile.dataset.pickerKey, tile.dataset.pickerSize), size: tile.dataset.pickerSize, pointerId: event.pointerId, x: AtlasViewport.x(event), y: AtlasViewport.y(event)};
  });
  document.addEventListener('pointermove', event => {
    if (pendingPicker?.pointerId === event.pointerId && !pickerDrag && Math.hypot(AtlasViewport.x(event) - pendingPicker.x, AtlasViewport.y(event) - pendingPicker.y) >= 4) beginPicker(pendingPicker, event);
    if (pickerDrag?.pointerId === event.pointerId) { event.preventDefault(); movePicker(AtlasViewport.x(event), AtlasViewport.y(event)); }
  }, {passive: false});
  document.addEventListener('pointerup', event => {
    if (pickerDrag?.pointerId === event.pointerId) { movePicker(AtlasViewport.x(event), AtlasViewport.y(event)); finishPicker(true); }
    if (pendingPicker?.pointerId === event.pointerId) pendingPicker = null;
  });
  document.addEventListener('pointercancel', () => finishPicker(false));
  document.addEventListener('lostpointercapture', event => { if (pickerDrag?.pointerId === event.pointerId) finishPicker(false); });
  document.addEventListener('keydown', event => { if (event.key === 'Escape') finishPicker(false); });
  document.addEventListener('dragstart', event => { if (event.target.closest('[data-picker-key]')) event.preventDefault(); });
  window.addEventListener('blur', () => finishPicker(false));
  window.addEventListener('resize', () => finishPicker(false));
  function positionCollectionHelp(help) {
    const button = document.querySelector('.dash-collection-help');
    if (!button) return;
    const bounds = AtlasViewport.rect(button);
    help.style.left = `${Math.max(12, Math.min(bounds.right - help.offsetWidth, AtlasViewport.width - help.offsetWidth - 12))}px`;
    help.style.top = `${Math.max(12, Math.min(bounds.bottom + 8, AtlasViewport.height - help.offsetHeight - 12))}px`;
  }
  document.addEventListener('toggle', event => {
    if (event.target.id === 'dash-collection-help' && event.newState === 'open') positionCollectionHelp(event.target);
  }, true);
  window.addEventListener('resize', () => {
    const help = document.querySelector('#dash-collection-help:popover-open');
    if (help) positionCollectionHelp(help);
  });
  document.addEventListener('click', event => {
    if (event.target.closest('.dash-collection-help')) {
      event.preventDefault();
      const help = document.getElementById('dash-collection-help');
      if (help.matches(':popover-open')) help.hidePopover();
      else { help.showPopover(); positionCollectionHelp(help); }
    }
    if (event.target.closest('[data-dash-help-start]')) {
      document.getElementById('dash-collection-help')?.hidePopover();
      document.querySelector('.dash-collection input[name="order"]')?.focus();
    }
    if (event.target.closest('[data-dash-clear-cohort]')) {
      go('Deliveries');
    }
    const filter = event.target.closest('[data-dash-filter]');
    if (filter) setCarrier(filter.dataset.value);
    const unbooked = event.target.closest('[data-unbooked-class]');
    if (unbooked && !TrackingVisibility.palletwaysB2bEnabled()) { sizes[unbooked.dataset.widgetInstance + '-class'] = unbooked.dataset.unbookedClass; save(); paint(); }
    const period = event.target.closest('[data-cancelled-period]');
    if (period) {
      sizes[period.dataset.widgetInstance + '-period'] = period.dataset.cancelledPeriod;
      if (period.dataset.cancelledPeriod === 'month') for (const [key,state] of monthlyCache) if (state.error) monthlyCache.delete(key);
      save(); paint();
    }
    const view = event.target.closest('[data-dash-view]');
    if (view) go('Deliveries', '', '', {widget: view.dataset.dashView, carrier});
    const preview = event.target.closest('[data-dash-order]');
    if (preview) op(preview.dataset.dashOrder);
    const planned = event.target.closest('[data-dash-planned]');
    if (planned) toast(`Planned for Version ${planned.dataset.dashPlanned}. Not available yet.`);
    if (event.target.closest('[data-dash-customize]')) customize();
    if (event.target.closest('[data-dash-widget-guide]') && !closingPicker) {
      if (!editing) customize();
      showWidgetTour();
    }
    if (event.target.closest('[data-dash-reset]')) {
      finishPicker(false); finishWidgetDrag(false, false);
      order = defaults(); sizes = {}; pinWidgetPositions(); save(); refreshPicker();
    }
    if (event.target.closest('[data-dash-retry]')) load(true);
  });
  document.addEventListener('pointerover', event => {
    const button = event.target.closest('.dash-filter-chips button');
    if (!button || button.contains(event.relatedTarget)) return;
    const bounds = AtlasViewport.rect(button);
    button.style.setProperty('--chip-x', `${AtlasViewport.x(event) - bounds.left}px`);
    button.style.setProperty('--chip-y', `${AtlasViewport.y(event) - bounds.top}px`);
    button.classList.remove('is-pointer-hover');
    // Establish the collapsed circle at the entry point before expanding it.
    void getComputedStyle(button, '::before').clipPath;
    button.classList.add('is-pointer-hover');
  });
  document.addEventListener('pointerout', event => {
    const button = event.target.closest('.dash-filter-chips button');
    if (button && !button.contains(event.relatedTarget)) button.classList.remove('is-pointer-hover');
  });
  document.addEventListener('change', event => {
    if (event.target.matches('[data-dash-select]')) setCarrier(event.target.value);
  });
  function positionWidgets(grid, nextOrder, fixedPositions = null) {
    const cards = [...grid.querySelectorAll('[data-dash-widget]')];
    // Capture the current visual positions, including any unfinished movement.
    const before = new Map(cards.map(card => [card, AtlasViewport.rect(card)]));
    const placements = widgetDrag?.originalPositions || widgetPositions();
    cards.forEach(card => {
      widgetMotions.get(card)?.cancel();
      widgetMotions.delete(card);
      card.style.order = nextOrder.indexOf(card.dataset.dashWidget);
      const position = fixedPositions?.[card.dataset.dashWidget] || (widgetDrag ? placements[widgetDrag.original[nextOrder.indexOf(card.dataset.dashWidget)]] : placements[card.dataset.dashWidget]);
      card.style.gridRow = position.row; card.style.gridColumn = position.column;
    });
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    cards.forEach(card => {
      const after = AtlasViewport.rect(card), from = before.get(card);
      const x = from.left - after.left, y = from.top - after.top;
      if (Math.abs(x) < .5 && Math.abs(y) < .5) return;
      const motion = card.animate([
        {transform: `translate(${x}px, ${y}px)`}, {transform: 'translate(0, 0)'},
      ], {duration: 300, easing: 'cubic-bezier(.2,.8,.25,1)'});
      widgetMotions.set(card, motion);
      motion.finished.then(() => {
        if (widgetMotions.get(card) === motion) widgetMotions.delete(card);
      }, () => {});
    });
  }
  function clearColumnSlots(drag) {
    drag.slotLayer.querySelectorAll('[data-column-preview]').forEach(slot => slot.remove());
    drag.slotElements.forEach(slot => { slot.style.removeProperty('visibility'); });
  }
  function previewColumnSlots(drag, positions, sourceColumn, targetColumn) {
    clearColumnSlots(drag);
    const bounds = AtlasViewport.rect(drag.grid), style = getComputedStyle(drag.grid);
    const gapX = parseFloat(style.columnGap), gapY = parseFloat(style.rowGap);
    const width = (bounds.width - gapX * 2) / 3, rowHeight = (bounds.height - gapY * 2) / 3;
    drag.slotElements.forEach((slot, index) => {
      const column = drag.originalPositions[drag.original[index]]?.column || drag.slots[index].emptyPosition?.column;
      if (column === sourceColumn || column === targetColumn) slot.style.visibility = 'hidden';
    });
    const occupied = new Set();
    drag.original.forEach(key => {
      const pos = positions[key];
      if (pos.column !== sourceColumn && pos.column !== targetColumn) return;
      const row = parseInt(pos.row, 10) - 1, column = Number(pos.column) - 1;
      const slot = document.createElement('div');
      slot.className = 'dash-widget-slot' + (pos.column === targetColumn ? ' is-widget-drop-ready' : '');
      slot.dataset.columnPreview = pos.column; slot.dataset.previewWidget = key;
      Object.assign(slot.style, {left: column * (width + gapX) + 'px', top: row * (rowHeight + gapY) + 'px', width: width + 'px', height: (units(key) === 3 ? bounds.height : rowHeight) + 'px'});
      drag.slotLayer.append(slot);
      for (let i = 0; i < units(key); i++) occupied.add((row + i) * 3 + column);
    });
    // Preserve empty-cell outlines in partially populated columns too.
    for (const column of [Number(sourceColumn) - 1, Number(targetColumn) - 1]) for (let row = 0; row < 3; row++) {
      if (occupied.has(row * 3 + column)) continue;
      const slot = document.createElement('div'); slot.className = 'dash-widget-slot'; slot.dataset.columnPreview = String(column + 1);
      Object.assign(slot.style, {left: column * (width + gapX) + 'px', top: row * (rowHeight + gapY) + 'px', width: width + 'px', height: rowHeight + 'px'});
      drag.slotLayer.append(slot);
    }
  }
  function previewWidgetSwap() {
    if (!widgetDrag) return;
    const {slots, slotElements, preview, original, key, grid, ghost, card} = widgetDrag;
    const floating = AtlasViewport.rect(ghost);
    const area = floating.width * floating.height;
    let next = -1, bestOverlap = 0;
    slots.forEach((slot, index) => {
      const width = Math.max(0, Math.min(floating.right, slot.right) - Math.max(floating.left, slot.left));
      const height = Math.max(0, Math.min(floating.bottom, slot.bottom) - Math.max(floating.top, slot.top));
      const overlap = area ? width * height / area : 0;
      if ((order.some(item => units(item) === 3) ? floating.left < slot.right && floating.right > slot.left && floating.top + floating.height / 2 >= slot.top && floating.top + floating.height / 2 <= slot.bottom : overlap >= .8) && overlap > bestOverlap) { next = index; bestOverlap = overlap; }
    });
    widgetDrag.readySlot = next;
    card.classList.toggle('is-widget-drop-ready', next >= 0 && next !== original.indexOf(key));
    slotElements.forEach((slot, index) => {
      slot.classList.toggle('is-widget-drop-ready', index === next && next !== original.indexOf(key));
    });
    const placements = widgetDrag.originalPositions;
    const targetKey = original[next];
    const sourceColumn = placements[key].column;
    const targetColumn = targetKey ? placements[targetKey].column : null;
    if (targetKey && sourceColumn !== targetColumn && (units(key) === 3 || units(targetKey) === 3)) {
      slotElements.forEach((slot, index) => slot.classList.toggle('is-widget-drop-ready', original[index] ? placements[original[index]].column === targetColumn : false));
      if (widgetDrag.columnTarget === targetColumn) return;
      widgetDrag.columnTarget = targetColumn; widgetDrag.emptyTarget = null;
      preview.splice(0, preview.length, ...original);
      const moved = Object.fromEntries(original.map(item => {
        const pos = placements[item];
        return [item, {row: pos.row, column: pos.column === sourceColumn ? targetColumn : pos.column === targetColumn ? sourceColumn : pos.column}];
      }));
      previewColumnSlots(widgetDrag, moved, sourceColumn, targetColumn);
      positionWidgets(grid, preview, moved);
      return;
    }
    if (widgetDrag.columnTarget) {
      clearColumnSlots(widgetDrag);
      widgetDrag.columnTarget = null;
      preview.splice(0, preview.length, ...original);
      positionWidgets(grid, preview, placements);
    }
    if (slots[next]?.emptyPosition) {
      if (widgetDrag.emptyTarget === next) return;
      widgetDrag.emptyTarget = next;
      preview.splice(0, preview.length, ...original);
      positionWidgets(grid, preview, {...widgetDrag.originalPositions, [key]: slots[next].emptyPosition});
      return;
    }
    if (widgetDrag.emptyTarget != null) {
      widgetDrag.emptyTarget = null;
      preview.splice(0, preview.length, ...original);
      positionWidgets(grid, preview, widgetDrag.originalPositions);
    }
    if (next < 0 || next === preview.indexOf(key)) return;
    const previous = original.indexOf(key);
    // Reject swaps that would overlap another widget or extend outside the grid.
    const candidate = [...original]; [candidate[previous], candidate[next]] = [candidate[next], candidate[previous]];
    const occupied = new Set();
    const fits = candidate.every((item, index) => {
      const pos = widgetDrag.originalPositions[original[index]];
      const row = parseInt(pos.row, 10) - 1, column = Number(pos.column) - 1;
      if (row + units(item) > 3) return false;
      for (let r = row; r < row + units(item); r++) { const cell = r * 3 + column; if (occupied.has(cell)) return false; occupied.add(cell); }
      return true;
    });
    if (!fits) { widgetDrag.readySlot = -1; return; }
    // Swap the two tiles; intermediate widgets keep their own positions.
    preview.splice(0, preview.length, ...original);
    [preview[previous], preview[next]] = [preview[next], preview[previous]];
    positionWidgets(grid, preview);
  }
  function finishWidgetDrag(commit, animate = true) {
    pendingWidgetPointer = null;
    if (!widgetDrag) return;
    const {grid, preview, original, card, ghost, pointerId, slots, slotLayer} = widgetDrag;
    widgetDrag = null;
    if (card.hasPointerCapture(pointerId)) card.releasePointerCapture(pointerId);
    document.body.classList.remove('is-dashboard-dragging');
    suppressWidgetClickUntil = performance.now() + 300;
    const finalOrder = commit ? preview : original;
    if (!commit) positionWidgets(grid, finalOrder);
    else {
      finalOrder.forEach(key => { const tile = grid.querySelector(`[data-dash-widget="${key}"]`); sizes[key + '-slot'] = (parseInt(tile.style.gridRow, 10) - 1) * 3 + Number(tile.style.gridColumn) - 1; });
      order = [...finalOrder]; save();
    }
    const cards = new Map([...grid.querySelectorAll('[data-dash-widget]')].map(tile => [tile.dataset.dashWidget, tile]));
    finalOrder.forEach(key => {
      const tile = cards.get(key);
      if (tile) { grid.append(tile); tile.style.removeProperty('order'); }
    });
    const finish = () => {
      ghost.remove();
      slotLayer.remove();
      card.classList.remove('is-widget-dragging', 'is-widget-drop-ready');
      if (widgetDrag?.grid !== grid) grid.classList.remove('is-widget-reordering');
      if (editing && grid.isConnected) { grid.querySelectorAll('.dash-add-slot').forEach(slot => slot.remove()); grid.insertAdjacentHTML('beforeend', emptySlotsMarkup()); }
    };
    let settling = Promise.resolve();
    if (animate && grid.isConnected && !matchMedia('(prefers-reduced-motion: reduce)').matches) {
      const destination = AtlasViewport.rect(card);
      const motion = ghost.animate([
        {transform: ghost.style.transform},
        {transform: `translate3d(${destination.left}px, ${destination.top}px, 0) scale(1)`},
      ], {duration: 180, easing: 'cubic-bezier(.2,.8,.25,1)', fill: 'forwards'});
      settling = motion.finished.catch(() => {});
      settling.then(finish);
    } else finish();
    if (widgetPaintPending) {
      widgetPaintPending = false;
      Promise.allSettled([settling, ...[...widgetMotions.values()].map(motion => motion.finished)]).then(() => {
        if (!widgetDrag && grid.isConnected) paint();
      });
    }
  }
  function moveWidgetCard(x, y) {
    if (!widgetDrag) return;
    const {ghost, offsetX, offsetY, scale} = widgetDrag;
    // No easing on cursor movement: the card stays attached to the grab point.
    ghost.style.transform = `translate3d(${x - offsetX * scale}px, ${y - offsetY * scale}px, 0) scale(${scale})`;
  }
  function pickUpWidget(pointer, event) {
    const {card, grid, x, y, pointerId} = pointer;
    widgetMotions.forEach(motion => motion.cancel());
    widgetMotions.clear();
    const tiles = [...grid.querySelectorAll('[data-dash-widget]')];
    const bounds = AtlasViewport.rect(card);
    const gridBounds = AtlasViewport.rect(grid);
    const slots = tiles.map(tile => AtlasViewport.rect(tile));
    const placements = widgetPositions(), occupied = new Set();
    order.forEach(key => {
      const pos = placements[key], start = (parseInt(pos.row, 10) - 1) * 3 + Number(pos.column) - 1;
      for (let row = 0; row < units(key); row++) occupied.add(start + row * 3);
    });
    const gridStyle = getComputedStyle(grid), gapX = parseFloat(gridStyle.columnGap), gapY = parseFloat(gridStyle.rowGap);
    const cellWidth = (gridBounds.width - gapX * 2) / 3, cellHeight = (gridBounds.height - gapY * 2) / 3;
    for (let cell = 0; cell < 9; cell++) {
      const row = Math.floor(cell / 3), column = cell % 3, tall = units(card.dataset.dashWidget) === 3;
      if (occupied.has(cell) || (tall && (row !== 0 || occupied.has(cell + 3) || occupied.has(cell + 6)))) continue;
      const left = gridBounds.left + column * (cellWidth + gapX), top = gridBounds.top + row * (cellHeight + gapY);
      const height = tall ? gridBounds.height : cellHeight;
      slots.push({left, top, right: left + cellWidth, bottom: top + height, width: cellWidth, height,
        emptyPosition: {row: tall ? '1 / span 3' : String(row + 1), column: String(column + 1)}});
    }
    // Empty slots form an independent, stationary layer below the moving cards.
    const slotLayer = document.createElement('div');
    slotLayer.className = 'dash-widget-slots';
    slotLayer.setAttribute('aria-hidden', 'true');
    slotLayer.inert = true;
    const slotElements = slots.map((slot, index) => {
      const empty = document.createElement('div');
      empty.className = 'dash-widget-slot';
      empty.dataset.widgetSlot = tiles[index]?.dataset.dashWidget || 'empty-' + slot.emptyPosition.row.replaceAll(' ', '') + '-' + slot.emptyPosition.column;
      Object.assign(empty.style, {left: `${slot.left - gridBounds.left}px`,
        top: `${slot.top - gridBounds.top}px`, width: `${slot.width}px`, height: `${slot.height}px`});
      slotLayer.append(empty);
      return empty;
    });
    grid.append(slotLayer);
    const ghost = card.cloneNode(true);
    ghost.classList.remove('dash-widget', 'is-widget-dragging', 'is-widget-drop-ready');
    ghost.classList.add('dash-widget-drag-preview');
    ghost.removeAttribute('data-dash-widget');
    ghost.removeAttribute('aria-labelledby');
    ghost.setAttribute('aria-hidden', 'true');
    ghost.inert = true;
    ghost.querySelectorAll('[id]').forEach(element => element.removeAttribute('id'));
    ghost.style.width = `${bounds.width}px`;
    ghost.style.height = `${bounds.height}px`;
    ghost.style.padding = getComputedStyle(card).padding;
    ghost.style.font = getComputedStyle(card).font;
    document.body.append(ghost);
    widgetDrag = {key: card.dataset.dashWidget, card, grid, original: [...order], preview: [...order],
      slots, slotElements, slotLayer, ghost, pointerId, originalPositions: widgetPositions(), readySlot: -1,
      offsetX: x - bounds.left, offsetY: y - bounds.top, scale: .94};
    card.setPointerCapture(pointerId);
    grid.classList.add('is-widget-reordering');
    card.classList.add('is-widget-dragging');
    document.body.classList.add('is-dashboard-dragging');
    moveWidgetCard(AtlasViewport.x(event), AtlasViewport.y(event));
  }
  document.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.isPrimary === false || widgetDrag) return;
    const card = event.target.closest('#dash-widget-grid [data-dash-widget]');
    if (!card || event.target.closest('button, a, input, select, textarea, [data-flow-open], .order-flow-scroll')) return;
    // Touch users can still scroll the cards' bodies; their headings are handles.
    if (event.pointerType === 'touch' && !event.target.closest('.dash-widget-head')) return;
    event.preventDefault();
    pendingWidgetPointer = {card, grid: card.closest('#dash-widget-grid'),
      pointerId: event.pointerId, x: AtlasViewport.x(event), y: AtlasViewport.y(event)};
  });
  document.addEventListener('pointermove', event => {
    if (!widgetDrag && pendingWidgetPointer?.pointerId === event.pointerId
      && Math.hypot(AtlasViewport.x(event) - pendingWidgetPointer.x, AtlasViewport.y(event) - pendingWidgetPointer.y) >= 4) {
      pickUpWidget(pendingWidgetPointer, event);
    }
    if (!widgetDrag || event.pointerId !== widgetDrag.pointerId) return;
    event.preventDefault();
    moveWidgetCard(AtlasViewport.x(event), AtlasViewport.y(event));
    previewWidgetSwap();
  }, {passive: false});
  document.addEventListener('pointerup', event => {
    if (pendingWidgetPointer?.pointerId === event.pointerId) pendingWidgetPointer = null;
    if (!widgetDrag || event.pointerId !== widgetDrag.pointerId) return;
    moveWidgetCard(AtlasViewport.x(event), AtlasViewport.y(event));
    previewWidgetSwap();
    finishWidgetDrag(widgetDrag.readySlot >= 0);
  });
  document.addEventListener('pointercancel', event => {
    if (pendingWidgetPointer?.pointerId === event.pointerId) pendingWidgetPointer = null;
    if (widgetDrag?.pointerId === event.pointerId) finishWidgetDrag(false);
  });
  document.addEventListener('lostpointercapture', event => {
    if (widgetDrag?.pointerId === event.pointerId) finishWidgetDrag(false);
  });
  document.addEventListener('dragstart', event => {
    if (event.target.closest('#dash-widget-grid')) event.preventDefault();
  });
  document.addEventListener('click', event => {
    if (performance.now() < suppressWidgetClickUntil && event.target.closest('#dash-widget-grid')) {
      event.preventDefault(); event.stopImmediatePropagation();
    }
  }, true);
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && (widgetDrag || pendingWidgetPointer)) {
      event.preventDefault(); event.stopImmediatePropagation(); finishWidgetDrag(false);
    }
  }, true);
  window.addEventListener('resize', () => finishWidgetDrag(false, false));
  window.addEventListener('blur', () => finishWidgetDrag(false, false));
  return {render, load, attachQuickLinks,
    preserveEditor: () => editing && !closingPicker && Boolean(document.querySelector('.dashboard-home.is-customizing .dash-editor')),
    storeLinksMarkup: () => Object.keys(storeWebsites).map(websiteLink).join(''),
    title: key => key === 'cancelled-month' ? "This Month's OW Cancelled Orders" : selectedDefinition(key)?.title || ''};
})();
