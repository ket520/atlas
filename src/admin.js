function vManufactureClaims() {
  return ManufactureClaims.render();
}

let collectionRecordsSearch = '';
let collectionRecordsData = [];
let collectionCreatedFrom = '', collectionCreatedTo = '';

function collectionCreatedDay(note) {
  const date = new Date(note.createdAt);
  return note.createdAt && Number.isFinite(date.getTime())
    ? new Intl.DateTimeFormat('en-CA', {timeZone: 'Europe/London', year: 'numeric', month: '2-digit', day: '2-digit'}).format(date) : '';
}

function collectionDateLabel() {
  const display = value => value.split('-').reverse().join('/');
  if (collectionCreatedFrom && collectionCreatedTo) return `${display(collectionCreatedFrom)} – ${display(collectionCreatedTo)}`;
  return collectionCreatedFrom ? `From ${display(collectionCreatedFrom)}` : collectionCreatedTo ? `Until ${display(collectionCreatedTo)}` : 'Date created';
}

function collectionDateFilter() {
  return `<div class="ui-select collection-date-select"><button type="button" class="ui-select-trigger" data-collection-toggle-date aria-label="Filter by date created" aria-expanded="false" aria-haspopup="dialog" aria-controls="collection-created-menu"><span class="ui-select-label">${esc(collectionDateLabel())}</span><span class="ui-select-chevron">${ico('chevdown', 16, 2)}</span></button><div id="collection-created-menu" class="ui-select-menu ui-date-menu collection-date-menu" popover="auto" role="dialog" aria-label="Date created range"><div class="delivery-date-fields"><label><span>From</span><input type="date" aria-label="Created from" data-collection-created="from" value="${esc(collectionCreatedFrom)}" max="${esc(collectionCreatedTo)}"></label><label><span>To</span><input type="date" aria-label="Created to" data-collection-created="to" value="${esc(collectionCreatedTo)}" min="${esc(collectionCreatedFrom)}"></label></div><button type="button" class="delivery-date-clear" data-collection-clear-dates>Clear dates</button></div></div>`;
}

function confirmSavedRecordDelete(order, recordType = 'collection note', buttonLabel = 'Delete note') {
  if (document.querySelector('.collection-delete-confirm')) return Promise.resolve(false);
  return new Promise(resolve => {
    const dialog = document.createElement('dialog');
    dialog.className = 'collection-delete-confirm';
    dialog.setAttribute('aria-labelledby', 'collection-delete-title');
    dialog.setAttribute('aria-describedby', 'collection-delete-description');
    dialog.innerHTML = `<form method="dialog"><span class="collection-delete-warning" aria-hidden="true">${ico('alert', 25)}</span><h2 id="collection-delete-title">Heads up</h2><p id="collection-delete-description">You're about to permanently delete ${order ? `the ${esc(recordType)} for order <strong>${esc(order)}</strong>` : `this ${esc(recordType)}`}. This action can't be undone.</p><div class="collection-delete-confirm-actions"><button type="submit" value="cancel" autofocus>Cancel</button><button type="submit" value="delete" class="collection-confirm-delete">${esc(buttonLabel)}</button></div></form>`;
    dialog.addEventListener('close', () => {
      const confirmed = dialog.returnValue === 'delete';
      dialog.remove();
      resolve(confirmed);
    }, {once: true});
    document.body.append(dialog);
    dialog.showModal();
  });
}

function vCollectiveNote() {
  const params = new URLSearchParams(location.search);
  if (params.get('view') === 'create' || params.has('order')) {
    return '<div class="delivery-page-head"><a class="collection-note-link" style="margin-left:0" href="./collective-note.html">Back to records</a></div><section id="collection-note-root" aria-label="Collection note generator"><p role="status">Loading collection note…</p></section>';
  }
  return `<section aria-label="Collection note records">
    <div class="delivery-page-head">
      <h2 class="fx-title">Collection Note</h2>
    </div>
    <div class="collection-records-toolbar"><label class="delivery-search">${ico('search', 18)}<input type="search" data-collection-records-search placeholder="Search Order No or Order Reference No" aria-label="Search collection notes by order or reference number" value="${esc(collectionRecordsSearch)}"></label><span id="collection-records-count" role="status" aria-live="polite"></span>${collectionDateFilter()}<a class="collection-note-link" href="./collective-note.html?view=create">${ico('plus', 16)}<span>Create collection note</span></a></div>
    <div class="tracking-table-wrap">
      <table class="tracking-table collection-records-table" aria-label="Collection note records">
        <thead><tr><th>Order No</th><th>Order Reference No</th><th>Date Created</th><th>Customer</th><th>Postcode</th><th>Collection Date</th><th>Items</th><th>Actions</th></tr></thead>
        <tbody id="collection-records"><tr><td colspan="8" class="tracking-empty" role="status">Loading collection records…</td></tr></tbody>
      </table>
    </div>
  </section>`;
}

async function loadCollectionRecords() {
  const body = document.getElementById('collection-records');
  if (!body) return;
  try {
    const result = await ApiClient.get('/collection-notes');
    if (!body.isConnected) return;
    collectionRecordsData = result.records;
    renderCollectionRecords();
  } catch (error) {
    body.innerHTML = `<tr><td colspan="8" class="tracking-empty" role="alert">${esc(error.message)} <button type="button" onclick="loadCollectionRecords()">Retry</button></td></tr>`;
  }
}

function renderCollectionRecords() {
    const body = document.getElementById('collection-records');
    if (!body) return;
    const search = collectionRecordsSearch.trim().toLowerCase();
    const records = collectionRecordsData.filter(note => {
      const day = collectionCreatedDay(note);
      return (!search || [note.order, note.orderRef].some(value => String(value || '').toLowerCase().includes(search)))
        && (!collectionCreatedFrom || day && day >= collectionCreatedFrom)
        && (!collectionCreatedTo || day && day <= collectionCreatedTo);
    });
    const copyOrderCell = (value, reference = false) => value ? `<span class="tracking-order-number">${esc(value)}<button type="button" class="qd-customer-copy" ${reference ? 'data-copy-order-reference' : 'data-copy-order-number'}="${esc(value)}" aria-label="Copy ${reference ? 'order reference' : 'order number'} ${esc(value)}" title="Copy ${reference ? 'order reference' : 'order number'}">${ico('copy', 13, 1.8)}</button></span>` : '—';
    const createdDate = note => {
      const date = new Date(note.createdAt);
      return note.createdAt && Number.isFinite(date.getTime()) ? `<time datetime="${esc(note.createdAt)}" title="${esc(note.createdAt)}">${esc(date.toLocaleDateString('en-GB', {timeZone: 'Europe/London'}))}</time>` : '—';
    };
    body.innerHTML = records.length ? records.map(note => `<tr>
      <td>${copyOrderCell(note.order)}</td><td>${copyOrderCell(note.orderRef, true)}</td><td>${createdDate(note)}</td>
      <td>${esc(note.customer || '—')}</td><td>${esc(note.postcode || '—')}</td>
      <td>${esc(note.collectionDate || '—')}</td><td>${esc(note.items || '—')}</td>
      <td><div class="collection-record-actions"><a class="collection-note-link collection-open-note" href="./collective-note.html?view=create&record=${encodeURIComponent(note.id)}">${ico('note', 15)}Open note</a>${['pdf', 'xlsx'].map(format => `<button type="button" class="collection-record-download" data-download-collection-record="${esc(note.id)}" data-format="${format}" title="Download ${format.toUpperCase()}" aria-label="Download ${format.toUpperCase()} for order ${esc(note.order)}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 16v5h14v-5"/></svg>${format.toUpperCase()}</button>`).join('')}<button type="button" class="collection-delete-note" title="Delete note" data-delete-collection-record="${esc(note.id)}" aria-label="Delete collection note for order ${esc(note.order)}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/></svg></button></div></td>
    </tr>`).join('') : `<tr><td colspan="8" class="tracking-empty">${collectionRecordsData.length ? 'No collection notes match the selected search or dates.' : 'No collection records yet. Create a collection note and choose Save note.'}</td></tr>`;
    const count = document.getElementById('collection-records-count');
    if (count) count.textContent = `${records.length} of ${collectionRecordsData.length} notes`;
}

document.addEventListener('input', event => {
  if (!event.target.matches('[data-collection-records-search]')) return;
  collectionRecordsSearch = event.target.value;
  renderCollectionRecords();
});

document.addEventListener('click', event => {
  const trigger = event.target.closest('[data-collection-toggle-date]');
  const menu = document.getElementById('collection-created-menu');
  if (trigger && menu) {
    if (menu.matches(':popover-open')) menu.hidePopover();
    else {
      const rect = AtlasViewport.rect(trigger);
      const width = Math.min(260, AtlasViewport.width - 24);
      Object.assign(menu.style, {width: `${width}px`, left: `${Math.max(12, Math.min(rect.right - width, AtlasViewport.width - width - 12))}px`, top: `${rect.bottom + 6}px`});
      menu.showPopover();
    }
    trigger.setAttribute('aria-expanded', String(menu.matches(':popover-open')));
    menu.ontoggle = () => trigger.setAttribute('aria-expanded', String(menu.matches(':popover-open')));
  }
  if (event.target.closest('[data-collection-clear-dates]') && menu) {
    collectionCreatedFrom = ''; collectionCreatedTo = '';
    menu.querySelectorAll('input').forEach(input => { input.value = ''; input.min = ''; input.max = ''; });
    document.querySelector('[data-collection-toggle-date] .ui-select-label').textContent = collectionDateLabel();
    renderCollectionRecords();
  }
});

document.addEventListener('change', event => {
  const input = event.target.closest('[data-collection-created]');
  if (!input) return;
  if (input.dataset.collectionCreated === 'from') collectionCreatedFrom = input.value;
  else collectionCreatedTo = input.value;
  document.querySelector('[data-collection-created="from"]').max = collectionCreatedTo;
  document.querySelector('[data-collection-created="to"]').min = collectionCreatedFrom;
  document.querySelector('[data-collection-toggle-date] .ui-select-label').textContent = collectionDateLabel();
  renderCollectionRecords();
});

document.addEventListener('click', event => {
  const button = event.target.closest('[data-download-collection-record]');
  if (!button || button.disabled) return;
  const record = button.dataset.downloadCollectionRecord, format = button.dataset.format;
  const buttons = [...button.closest('.collection-record-actions').querySelectorAll('[data-download-collection-record]')];
  buttons.forEach(node => { node.disabled = true; });
  button.setAttribute('aria-busy', 'true');
  toast(`Preparing ${format.toUpperCase()} download…`);
  const frame = document.createElement('iframe');
  frame.title = 'Collection note download';
  frame.setAttribute('aria-hidden', 'true');
  frame.tabIndex = -1;
  frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1200px;height:1000px;visibility:hidden;border:0;pointer-events:none';
  const finish = message => {
    clearTimeout(timeout);
    window.removeEventListener('message', complete);
    setTimeout(() => frame.remove(), 1000);
    buttons.forEach(node => { node.disabled = false; });
    button.removeAttribute('aria-busy');
    toast(message);
  };
  const complete = event => {
    if (event.origin !== location.origin || event.source !== frame.contentWindow
      || event.data?.type !== 'collection-record-download' || event.data.record !== record) return;
    finish(event.data.ok ? `${format.toUpperCase()} downloaded.` : event.data.error || 'Could not download the saved note.');
  };
  const timeout = setTimeout(() => finish('Download timed out. Please try again.'), 90000);
  window.addEventListener('message', complete);
  frame.src = `./collective-note.html?${new URLSearchParams({view: 'create', record, download: format})}`;
  document.body.append(frame);
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-delete-collection-record]');
  if (!button || button.disabled) return;
  const note = collectionRecordsData.find(note => note.id === button.dataset.deleteCollectionRecord);
  if (!await confirmSavedRecordDelete(note?.order)) return;
  button.disabled = true;
  try {
    const response = await fetch(`/api/collection-notes/${encodeURIComponent(button.dataset.deleteCollectionRecord)}`, { method: 'DELETE' });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not delete collection note.');
    await loadCollectionRecords();
    toast('Collection note deleted');
  } catch (error) {
    button.disabled = false;
    toast(error.message || 'Could not delete collection note.');
  }
});

let integrationView = 'integration';
let syncControl = null;
let syncControlLoading = false;
let syncControlCheckedAt = 0;

function syncCountdown(row, now = Date.now()) {
  if (row.disabled) return 'Not scheduled';
  const at = row.nextRunAt && new Date(row.nextRunAt).getTime();
  if (!at || !Number.isFinite(at)) return 'Time unavailable';
  const seconds = Math.ceil((at - now) / 1000);
  if (seconds <= 0) return 'Due · awaiting run';
  return `${Math.floor(seconds / 60)}m ${String(seconds % 60).padStart(2, '0')}s`;
}

function syncControlMarkup() {
  if (!syncControl) return '<p class="mut" role="status">Loading sync schedule…</p>';
  return `${syncControl.unavailable ? '<p class="integration-warning" role="alert">Schedule read unavailable. Last loaded settings are shown.</p>' : ''}
    <div class="integration-sync-scroll sync-control-scroll" tabindex="0" role="region" aria-label="Sync Schedule">
      <table class="integration-sync-table sync-control-table" aria-label="Workbook sync schedule">
        <thead><tr><th>Integration</th><th>Frequency (Minutes)</th><th>Trigger Status</th><th>Last Applied</th><th>Estimated next run</th></tr></thead>
        <tbody>${(syncControl.rows || []).map((row, index) => `<tr>
          <td><strong>${esc(row.integration)}</strong></td><td>${esc(row.frequencyMinutes)}</td>
          <td><span class="sync-result ${row.disabled ? 'sync-result-warning' : 'sync-result-info'}">${ico(row.disabled ? 'alert' : 'clock', 13)}${esc(row.triggerStatus || 'Not recorded')}</span></td>
          <td>${esc(row.lastApplied || 'Not recorded')}</td>
          <td><span class="sync-countdown" data-sync-countdown="${index}">${esc(syncCountdown(row))}</span></td>
        </tr>`).join('') || '<tr><td colspan="5">No sync settings recorded.</td></tr>'}</tbody>
      </table>
    </div><p class="integration-traffic-note">Estimated from the latest logged run and frequency; Last Applied is used when no run is recorded. Trigger timing may vary.</p>`;
}

async function loadSyncControl() {
  if (document.body.dataset.live !== 'true' || syncControlLoading || Date.now() - syncControlCheckedAt < 60000) return;
  syncControlLoading = true;
  const startedAt = Date.now();
  try {
    const result = await ApiClient.get('/sync-control');
    if (!Array.isArray(result.rows)) throw new Error('Invalid schedule response');
    syncControl = result;
  } catch (_) {
    syncControl = { ...(syncControl || {rows: []}), unavailable: true };
  } finally {
    syncControlLoading = false;
    syncControlCheckedAt = startedAt;
    const target = document.getElementById('sync-control');
    if (target) target.innerHTML = syncControlMarkup();
  }
}

setInterval(() => {
  if (page !== 'Integrations' || integrationView !== 'traffic') return;
  document.querySelectorAll('[data-sync-countdown]').forEach(element => {
    const row = syncControl?.rows?.[Number(element.dataset.syncCountdown)];
    if (row) element.textContent = syncCountdown(row);
  });
  loadSyncControl();
}, 1000);

let syncRunLog = null;
let syncRunLogLoading = false;
let syncRunLogCheckedAt = 0;

function syncResultStyle(value) {
  const text = String(value || '').trim();
  if (/\b(fail(?:ed|ure)?|error|exception|timeout|timed out)\b/i.test(text)) return ['error', 'alert'];
  if (/\b(partial|warning|skipped|cancelled|canceled)\b/i.test(text)) return ['warning', 'alert'];
  if (/^(success(?:ful)?|ok|completed|complete|succeeded)$/i.test(text)) return ['success', 'check'];
  if (/^(running|started|pending|in progress)$/i.test(text)) return ['pending', 'clock'];
  return ['info', 'right'];
}

function syncCountMarkup(value, kind) {
  const raw = String(value ?? '').trim();
  const numeric = /^\d[\d,]*$/.test(raw) ? Number(raw.replace(/,/g, '')) : null;
  return raw ? `<span class="sync-count sync-count-${kind}${numeric === 0 ? ' is-zero' : ''}">${ico(kind === 'inserted' ? 'plus' : 'clipboardcheck', 13)}${esc(numeric === null ? raw : numeric.toLocaleString('en-GB'))}</span>` : '<span class="sync-count-empty" aria-label="Not recorded">—</span>';
}

function syncRunLogMarkup() {
  if (!syncRunLog) return '<p class="mut" role="status">Loading sync activity…</p>';
  const warning = syncRunLog.unavailable
    ? '<p class="integration-warning" role="alert">Sync activity is unavailable. Any last loaded entries are shown below.</p>' : '';
  const rows = (syncRunLog.rows || []).filter(row => {
    const counts = [row.recordsInserted, row.recordsUpdated].map(value => String(value ?? '').trim());
    return !counts.every(value => !value || Number(value.replace(/,/g, '')) === 0);
  });
  const total = field => rows.reduce((sum, row) => {
    const raw = String(row[field] ?? '').trim();
    return sum + (/^\d[\d,]*$/.test(raw) ? Number(raw.replace(/,/g, '')) : 0);
  }, 0).toLocaleString('en-GB');
  return `${warning}<div class="sync-log-stats" aria-label="Totals for displayed sync runs">
      <div class="sync-log-stat sync-log-stat-runs">${ico('clock', 18)}<span><strong>${rows.length.toLocaleString('en-GB')}</strong><small>Sync runs</small></span></div>
      <div class="sync-log-stat sync-log-stat-inserted">${ico('plus', 18)}<span><strong>${total('recordsInserted')}</strong><small>Records inserted</small></span></div>
      <div class="sync-log-stat sync-log-stat-updated">${ico('clipboardcheck', 18)}<span><strong>${total('recordsUpdated')}</strong><small>Records updated</small></span></div>
    </div><p class="sync-log-read">${ico('clock', 13)} Last read: ${esc(integrationTime(syncRunLog.updatedAt))}</p>
    <div class="integration-sync-scroll" tabindex="0" role="region" aria-label="Data Sync Activity">
      <table class="integration-sync-table" aria-label="Workbook sync activity">
        <thead><tr><th>Integration</th><th>Started At</th><th>Execution Result</th><th>Records Inserted</th><th>Records Updated</th></tr></thead>
        <tbody>${rows.length ? rows.map(row => {
          const [tone, icon] = syncResultStyle(row.executionResult);
          return `<tr data-sync-result="${tone}">
          <td><span class="sync-integration"><span class="sync-integration-icon" aria-hidden="true">${ico('link', 15)}</span><strong>${esc(row.integration)}</strong></span></td>
          <td><span class="sync-started">${ico('clock', 13)}<span>${esc(row.startedAt)}</span></span></td>
          <td>${row.executionResult ? `<span class="sync-result sync-result-${tone}">${ico(icon, 13)}<span>${esc(row.executionResult)}</span></span>` : '<span class="sync-count-empty">—</span>'}</td>
          <td>${syncCountMarkup(row.recordsInserted, 'inserted')}</td><td>${syncCountMarkup(row.recordsUpdated, 'updated')}</td>
        </tr>`;
        }).join('') : `<tr><td colspan="5">${syncRunLog.unavailable ? 'No saved sync activity available.' : 'No sync runs with recorded insert or update counts.'}</td></tr>`}</tbody>
      </table>
    </div>`;
}

async function loadSyncRunLog() {
  if (document.body.dataset.live !== 'true' || syncRunLogLoading || Date.now() - syncRunLogCheckedAt < 300000) return;
  syncRunLogLoading = true;
  try {
    const result = await ApiClient.get('/sync-run-log');
    if (!Array.isArray(result.rows)) throw new Error('Invalid sync log response');
    syncRunLog = result;
  } catch (_) {
    syncRunLog = { ...(syncRunLog || {rows: [], updatedAt: null}), unavailable: true };
  } finally {
    syncRunLogLoading = false;
    syncRunLogCheckedAt = Date.now();
    const target = document.getElementById('sync-run-log');
    if (target) target.innerHTML = syncRunLogMarkup();
    document.dispatchEvent(new CustomEvent('deliverydesk:sync-run-log'));
  }
}

const INTEGRATION_SOURCES = [
  { name: 'OrderWise', key: 'ow', method: 'Google Sheets · Sales Activity', count: 'imported', unit: 'source rows read', data: 'Orders, customers, addresses and items' },
  { name: 'Amazon Shipping', key: 'amazonShipping', error: 'amazonShippingUnavailable', method: 'Google Sheets · Amazon Shipping', count: 'amazonShippingMatched', unit: 'orders matched', data: 'Shipment status and scheduled dates' },
  { name: 'Palletways', key: 'palletways', error: 'palletwaysUnavailable', method: 'Palletways API', count: 'palletwaysMatched', unit: 'orders matched', data: 'Shipment events, status and delivery details' },
  { name: 'OptimoRoute', key: 'optimoroute', error: 'optimorouteUnavailable', method: 'OptimoRoute API', count: 'optimorouteMatched', unit: 'orders matched', data: 'Own van schedules, tracking and proof of delivery' },
  { name: 'Courier Issues', key: 'courierIssues', error: 'courierIssuesUnavailable', method: 'Google Sheets · Courier Issues', count: 'courierIssuesMatched', unit: 'orders matched', data: 'Issues, notes and follow-ups' },
  { name: 'Routine Dashboard', key: 'routineDashboard', error: 'bookingUnavailable', method: 'Local workbook', count: 'bookingMatched', unit: 'orders matched', data: 'Booking status' },
  { name: 'Routine Dashboard - Live', key: 'routineLive', error: 'routineLiveUnavailable', method: 'Google Sheets', count: 'routineLiveMatched', unit: 'Own van orders overridden', data: 'Priority Failed / Scheduled statuses from order-cell colours; booking status from column E' },
  { name: 'STOPSTART', key: 'stopstart', error: 'stopstartUnavailable', method: 'Google Sheets · STOPSTART', count: 'stopstartMatched', unit: 'orders matched', data: 'Expected delivery dates, UK windows, driver and reference' },
  { name: 'XDP', key: 'xdp', error: 'xdpUnavailable', method: 'Google Sheets · XDP', count: 'xdpMatched', unit: 'orders matched', data: 'Shipment status, latest details, parcel barcodes and proof of delivery' },
];

function integrationTime(value) {
  const instant = value && new Date(value);
  return instant && !Number.isNaN(instant.getTime())
    ? instant.toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : 'Not recorded';
}

function integrationState(source, summary, unavailable) {
  if (source.disconnected) return { label: 'Not connected', tone: 'offline' };
  if (unavailable) return { label: 'Check unavailable', tone: 'warning' };
  if (!summary) return { label: 'Checking', tone: 'waiting' };
  if ((source.key === 'ow' && summary.stale) || summary[source.error]) return { label: 'Connection error', tone: 'error' };
  if (summary.stale) return { label: 'Not checked', tone: 'warning' };
  if (!summary.sourceUpdatedAt?.[source.key]) return { label: 'Not checked', tone: 'waiting' };
  return { label: 'Connected', tone: 'connected' };
}

function integrationCard(source, summary, unavailable) {
  const state = integrationState(source, summary, unavailable);
  return `<article class="card integration-card">
    <div><h3>${esc(source.name)}</h3><small class="mut">${esc(source.method)}</small></div>
    <span class="integration-state" data-state="${state.tone}">${esc(state.label)}</span>
    <div><small class="mut">Last successful update</small><b>${esc(integrationTime(summary?.sourceUpdatedAt?.[source.key]))}</b></div>
  </article>`;
}

function integrationTraffic(summary, unavailable) {
  const orderRange = summary?.orderDateRanges?.All;
  const orderRangeLabel = orderRange?.from && orderRange?.to
    ? `${hd(orderRange.from)} – ${hd(orderRange.to)}`
    : summary ? 'No dated orders' : 'Loading…';
  return `<section class="integration-traffic" aria-labelledby="traffic-title">
    <div class="integration-traffic-heading">
      <div class="integration-section-heading"><h2 id="traffic-title">Data Trafficking</h2><p>Follow incoming data and workbook sync activity.</p></div>

    </div>
    <div class="integration-flow-overview" aria-label="API to Google Sheets for processing, then Atlas">
      <div><small>Source</small><strong>API</strong></div><span aria-hidden="true">→</span>
      <div><small>Processing</small><strong>Google Sheets</strong></div><span aria-hidden="true">→</span>
      <div><small>Display</small><strong>Atlas</strong></div>
    </div>
    <div class="integration-traffic-grid">
      <div class="integration-incoming-stack">
        <section class="card integration-flow-card integration-range-card"><h3>Order date range</h3>
          <p class="mut">Orders currently available in Atlas.</p>
      <div class="integration-order-range" role="status" aria-label="Order date range">
        <span>Order date range</span><strong>${esc(orderRangeLabel)}</strong>
        <small>Sales Activity · Order date (B)</small>
      </div>
        </section>
        <section class="card integration-flow-card"><h3>Sync Schedule</h3>
          <p class="mut">Integration frequency and trigger settings.</p>
          <div id="sync-control">${syncControlMarkup()}</div>
        </section>
      </div>
      <section class="card integration-flow-card integration-sync-card"><h3>Data Sync Activity</h3>
        <p class="mut">Workbook sync runs with recorded insert or update counts.</p>
        <div id="sync-run-log">${syncRunLogMarkup()}</div>
      </section>
    </div>
    <p class="integration-traffic-note">Activity counts describe the displayed workbook sync runs; repeated updates can affect the same order more than once.</p>
  </section>`;
}

function vIntegrations() {
  const summary = typeof liveSummary !== 'undefined' ? liveSummary : null;
  const unavailable = typeof liveSummaryError !== 'undefined' && liveSummaryError;
  return `<div class="workflow-intro"><div><h1>Integration &amp; Data Trafficking</h1></div></div>
    <nav class="integration-view-switch" aria-label="Integration page views">
      <button type="button" data-integration-view="integration" aria-pressed="${integrationView === 'integration'}">${ico('Integrations', 18)}Integration</button>
      <button type="button" data-integration-view="traffic" aria-pressed="${integrationView === 'traffic'}">${ico('right', 18)}Data Trafficking</button>
    </nav>
    ${unavailable ? '<p class="integration-warning" role="alert">Connection checks are unavailable. Last recorded updates are shown below.</p>' : ''}
    ${integrationView === 'traffic' ? integrationTraffic(summary, unavailable) : `
      <section aria-labelledby="integration-title">
        <div class="integration-section-heading"><h2 id="integration-title">Integration</h2><p>Check whether each platform is connected. Status is based on the latest synchronization; checks refresh automatically every five minutes.</p></div>
        <div class="integration-list">${INTEGRATION_SOURCES.map(source => integrationCard(source, summary, unavailable)).join('')}</div>
      </section>`}`;
}

document.addEventListener('click', event => {
  const button = event.target.closest('[data-integration-view]');
  if (!button) return;
  integrationView = button.dataset.integrationView;
  R();
  document.querySelector(`[data-integration-view="${integrationView}"]`)?.focus();
});

// This app always uses the light palette, regardless of saved or device preferences.
let themeChoice = 'light';
document.documentElement.dataset.theme = 'light';
try { localStorage.setItem('delivery-desk-theme', 'light'); } catch {}

function setTheme() {
  themeChoice = 'light';
  document.documentElement.dataset.theme = 'light';
  R();
}

function themeOptions() {
  return '<span class="mut">Light mode is enabled for this application.</span>';
}

function vSettings() {
  return `<div class="workflow-intro">
    <div>
      <h1>Settings</h1>
    </div>
  </div>
  <section class="card settings-card settings-data" aria-labelledby="settings-data-heading">
    <h2 id="settings-data-heading">Hide data</h2>
    <div class="settings-data-list">
      ${[['hygienic', 'Hygienic Cleaning Company (UK) LTD'], ['wayfair', 'Wayfair'], ['wilko', 'Wilko']].map(([key, label]) => `<label class="settings-data-row">
        <span>${esc(label)}</span>
        <input class="settings-data-switch" type="checkbox" role="switch" data-settings-company="${key}" ${(key === 'hygienic' ? TrackingVisibility.enabled() : key === 'wilko' ? TrackingVisibility.wilkoEnabled() : TrackingVisibility.wayfairEnabled()) ? 'checked' : ''}>
      </label>`).join('')}
      <label class="settings-data-row">
        <span>Palletways B2B</span>
        <input class="settings-data-switch" type="checkbox" role="switch" data-settings-company="palletways-b2b" ${TrackingVisibility.palletwaysB2bEnabled() ? 'checked' : ''}>
      </label>
    </div>
  </section>`;
}

let guidanceSearchTerm = '', guidanceSearchOpen = false;

function vGuidance() {
  const summary = typeof liveSummary !== 'undefined' ? liveSummary : null;
  const sourceValues = field => [...new Set((summary?.filterFacets || []).map(item => item[field]).filter(Boolean))]
    .sort((a, b) => a.localeCompare(b));
  const knownDeliveryMethods = {
    'Own van': ['Next Day Van Delivery', 'Standard Van Delivery'],
    'Self Delivery': ['Self Delivery', 'Self Delivery BQ'],
    AMZ: ['AMA Large', 'AMA Letter', 'AMA Medium', 'AMA Standard', 'AMA XL', 'Amazon Shipping One-Day Tracked'],
    Palletways: ['Next Day (Pallet)', 'Palletways', 'Palletways BQ', 'Palletways Next Day'],
    XDP: ['XDP', 'XDP (Next Day)', 'XDP BQ'],
    Yodel: ['Yodel - XPECT 48 XL POD', 'Yodel - XPECT MON - SAT 24', 'Yodel - XPRESS MINI 48 NON POD'],
    Stopstart: ['STOPSTART', 'Stopstart BQ'],
    'LOCAL MULTIDROP': ['LOCAL MULTIDROP'],
    'UK Next Day': ['UK Next Day Delivery'],
    Wayfair: ['Wayfair UPS'],
  };
  const methodValues = (...carriers) => [...new Set(carriers.flatMap(carrier => [
    ...(knownDeliveryMethods[carrier] || []),
    ...(summary?.deliveryMethodClassifications?.[carrier] || []),
    ...(summary?.filterFacets || []).filter(item => item.carrier === carrier).map(item => item.classification).filter(Boolean),
  ]))].sort((a, b) => a.localeCompare(b));
  const statusMappings = [
    ['All statuses', [['All carriers', ['All values']]]],
    ['Other Status', [['XDP fallback', ['Awaiting']]]],
    ['Unscheduled', [
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['unscheduled']],
      ['Palletways API', ['Unscheduled']],
      ['Amazon Shipping · OW Tracking No (S)', ['Empty tracking number']],
      ['OW Status (J) · fallback', ['W', 'K', 'H', 'I', 'A', 'U', 'Y', 'UNSCHEDULED', 'Empty / unmapped status']],
    ]],
    ['Scheduled', [
      ['Routine Dashboard - Live · Own van priority', ['#FFFFFF with an order number', '#FFC000']],
      ['Amazon Shipping tab · G', ['IN_TRANSIT', 'READY_FOR_RECEIVE']],
      ['Palletways API', ['In Transit', 'Scheduled']],
      ['OW Status (J) · fallback', ['P', 'S', 'SCHEDULED']],
    ]],
    ['Out for Delivery', [
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['scheduled', 'on_route', 'servicing']],
      ['Amazon Shipping tab · G', ['OUT_FOR_DELIVERY']],
      ['Palletways API', ['Out for Delivery']],
      ['OW Status (J) · fallback', ['OUT FOR DELIVERY']],
    ]],
    ['Delivered', [
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['success']],
      ['Amazon Shipping tab · G', ['DELIVERED']],
      ['Palletways API', ['Delivered']],
      ['OW Status (J) · fallback', ['C', 'DELIVERED', 'COMPLETE', 'COMPLETED']],
    ]],
    ['Failed', [
      ['Routine Dashboard - Live · Own van priority', ['#FFFF00']],
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['failed']],
      ['Amazon Shipping tab · G', ['UNDELIVERABLE', 'LOST']],
      ['XDP tab · I', ['DAMAGE', 'DELETE', 'NOT RECEIVED']],
      ['Palletways API', ['Failed', 'Damaged']],
      ['OW Status (J) · fallback', ['FAILED DELIVERY', 'FAILED']],
    ]],
    ['Rejected', [
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['rejected']],
      ['Palletways API', ['Refused']],
      ['OW Status (J) · fallback', ['REJECTED']],
    ]],
    ['Lost', [
      ['Palletways API', ['Lost']],
    ]],
    ['Cancelled', [
      ['OW Status (J)', ['X']],
      ['OW Delivery method (T)', ['To be cancelled']],
    ]],
    ['Return', [
      ['Own van / Self Delivery / LOCAL MULTIDROP · OptimoRoute', ['returned']],
      ['Palletways API', ['Return']],
      ['OW Status (J) · fallback', ['RETURN']],
    ]],
    ['Unassigned', [['OW Delivery method (T)', ['On hold - TBC']]]],
  ];
  const mappingCouriers = ['Own van', 'Self Delivery', 'LOCAL MULTIDROP', 'Amazon Shipping', 'Palletways', 'XDP', 'Yodel', 'Stopstart', 'UK Next Day', 'Wayfair'];
  const referenceStatuses = {
    XDP: [...new Set(['Awaiting', 'DAMAGE', 'DELETE', 'DELIVERED', 'DELIVERY', 'EDIT', 'EMAIL', 'EXCEPTION', 'IRISH MANIFEST', 'MISROUTE', 'NEXT STOP', 'NOT RECEIVED', 'SMS', ...sourceValues('xdpStatus')])],
    Stopstart: [...new Set(['Past Expected Date \u2014 Unconfirmed', 'Tracking Unavailable', ...sourceValues('stopstartStatus')])],
  };
  const referenceStatusGroup = value => ({
    DELIVERED: 'Delivered', DELIVERY: 'Scheduled', 'NEXT STOP': 'Out for Delivery',
    SCHEDULED: 'Scheduled', UNSCHEDULED: 'Unscheduled', 'OUT FOR DELIVERY': 'Out for Delivery',
    FAILED: 'Failed', REJECTED: 'Rejected', LOST: 'Lost', CANCELLED: 'Cancelled',
    RETURN: 'Return', UNASSIGNED: 'Unassigned',
  }[value.trim().toUpperCase()] || 'Other Status');
  const carrierMappingCell = (status, mappings, courier) => {
    if (status === 'All statuses') return 'All values';
    if (referenceStatuses[courier]) {
      const values = referenceStatuses[courier].filter(value => {
        if (courier === 'XDP' && ['DAMAGE', 'DELETE', 'NOT RECEIVED'].includes(value.trim().toUpperCase())) return status === 'Failed';
        return referenceStatusGroup(value) === status;
      });
      return values.length
        ? `<ul class="guidance-source-values">${values.map(value => `<li>${esc(value)}</li>`).join('')}</ul>`
        : '\u2014';
    }
    const ownVan = ['Own van', 'Self Delivery', 'LOCAL MULTIDROP'].includes(courier);
    const applicable = mappings.filter(([source]) => source.startsWith('OW ')
      || (courier === 'Own van' && source.startsWith('Routine Dashboard - Live'))
      || (ownVan && source.includes('OptimoRoute'))
      || (courier === 'Amazon Shipping' && source.startsWith('Amazon Shipping'))
      || (courier === 'Palletways' && source === 'Palletways API'));
    if (!applicable.length) return '—';
    return `<ul class="guidance-source-values">${applicable.map(([source, values]) => {
      const label = source.includes('OptimoRoute') ? 'OptimoRoute' : source;
      return `<li><strong>${esc(label)}</strong><div>${values.map(esc).join(' &amp; ')}</div></li>`;
    }).join('')}</ul>`;
  };
  const overallStatusTable = `<div class="guidance-table-scroll" role="region" aria-label="Overall status mapping" tabindex="0">
    <table class="guidance-table guidance-status-map">
      <caption>Overall status mapping</caption>
      <colgroup><col class="guidance-status-column">${mappingCouriers.map(() => '<col class="guidance-carrier-column">').join('')}</colgroup>
      <thead><tr><th scope="col" rowspan="2">All methods status filter</th><th scope="colgroup" colspan="${mappingCouriers.length}">Carrier mapping</th></tr>
        <tr>${mappingCouriers.map(courier => `<th scope="col">${esc(courier)}</th>`).join('')}</tr></thead>
      <tbody>
      ${statusMappings.map(([status, mappings]) => `<tr><th scope="row">${esc(status)}</th>
        ${mappingCouriers.map(courier => `<td data-guidance-carrier="${esc(courier)}">${carrierMappingCell(status, mappings, courier)}</td>`).join('')}
      </tr>`).join('')}</tbody>
    </table>
    <p class="guidance-mapping-note">XDP DAMAGE, DELETE and NOT RECEIVED count as Failed. Amazon UNDELIVERABLE and LOST also count as Failed. Other XDP and STOPSTART entries show reference groupings; their source labels remain separate from the saved delivery category. Failed Deliveries uses the saved Failed or Rejected category.</p>
  </div>`;
  const groups = [
    ['Tracking · General & non-delivery', [
      ['All', 'OW Sales Activity · all saved orders', "\u2014"],
      ['Today Deliveries', 'Current UK date and carrier-specific delivery evidence', 'STOPSTART: Expected Today; XDP: NEXT STOP; Palletways sheet: Out for Delivery. Also includes eligible deliveries dated today, including STOPSTART expected date or Palletways due date. Failed, Rejected, Lost, Cancelled and Return are excluded'],
      ['Charge Pending (Remote Postcode)', 'OW Sales Activity · Delivery method (T)', "Charge Pending (Remote Postcode)"],
      ['Collect in Person', 'OW Sales Activity · Delivery method (T)', "Collect in Person"],
      ['Do Not Pick Yet', 'OW Sales Activity · Delivery method (T)', "Do Not Pick Yet"],
      ['Cancelled', 'OW Sales Activity · Delivery method (T) / Status (J)', "To be cancelled & X & Cancelled"],
      ['On Hold', 'OW Sales Activity · Delivery method (T)', "On hold - TBC"],
      ['Unassigned', 'OW Sales Activity · Delivery method (T)', "Unassigned"],
      ['Hygienic LTD', 'OW Sales Activity · Order Type (K)', "Sales"],
    ]],
    ['Tracking · Delivery methods', [
      ['All methods', 'OW Sales Activity · Delivery method (T)', 'All delivery-method values'],
      ['Own van / Self Delivery', 'OW Sales Activity · Delivery method (T)', methodValues('Own van', 'Self Delivery')],
      ['LOCAL MULTIDROP', 'OW Sales Activity · Delivery method (T)', methodValues('LOCAL MULTIDROP')],
      ['Amazon Shipping', 'OW Sales Activity · Delivery method (T)', methodValues('AMZ')],
      ['Palletways', 'OW Sales Activity · Delivery method (T)', methodValues('Palletways')],
      ['XDP', 'OW Sales Activity · Delivery method (T)', methodValues('XDP')],
      ['Yodel', 'OW Sales Activity · Delivery method (T)', methodValues('Yodel')],
      ['Stopstart', 'OW Sales Activity · Delivery method (T)', methodValues('Stopstart')],
      ['UK Next Day', 'OW Sales Activity · Delivery method (T)', methodValues('UK Next Day')],
      ['Wayfair', 'OW Sales Activity · Delivery method (T)', methodValues('Wayfair')],
    ]],
    ['Tracking · Status with All methods selected', [
      ['All statuses', 'Saved current delivery status', "\u2014"],
      ['Other Status', 'XDP fallback', 'Awaiting'],
      ['Unscheduled', 'OW Status (J) or mapped carrier status', "W & K & H & I & A & U & Y & Unscheduled & unscheduled"],
      ['Scheduled', 'Routine Dashboard - Live Own van override; otherwise mapped carrier or OW status', "#FFFFFF with an order number & #FFC000 & P & S & Scheduled & IN_TRANSIT & READY_FOR_RECEIVE & In Transit"],
      ['Out for Delivery', 'Mapped carrier status or OW fallback', "Out for Delivery & scheduled & on_route & servicing & OUT_FOR_DELIVERY & VL/SCN/800 & VP/DAR"],
      ['Delivered', 'Mapped carrier status or OW fallback', "C & Complete & Completed & Delivered & success & DELIVERED & POD/POD"],
      ['Failed', 'Routine Dashboard - Live, mapped carrier status or OW fallback', "Own van: #FFFF00; Amazon: UNDELIVERABLE & LOST; XDP: DAMAGE & DELETE & NOT RECEIVED; other mapped values: Failed & Failed Delivery & failed & Damaged"],
      ['Rejected', 'Mapped carrier status or OW fallback', "Rejected & rejected & Refused"],
      ['Lost', 'Palletways API', 'Lost; Amazon LOST is grouped under Failed'],
      ['Cancelled', 'OW Status (J) or Delivery method (T)', "To be cancelled & X & Cancelled"],
      ['Return', 'Mapped carrier status or OW fallback', "Return & returned"],
      ['Unassigned', 'OW Sales Activity · Delivery method (T)', "On hold - TBC"],
    ]],
    ['Tracking · Courier-specific status dropdown', [
      ['Amazon Shipping statuses', 'Sales Activity workbook → Amazon Shipping tab · G', [...new Set(['IN_TRANSIT', 'READY_FOR_RECEIVE', 'OUT_FOR_DELIVERY', 'DELIVERED', 'UNDELIVERABLE', 'LOST', ...sourceValues('amazonStatus')])]],
      ['Palletways statuses', 'Sales Activity workbook → Palletways tab · F', sourceValues('palletwaysSheetStatus').length ? sourceValues('palletwaysSheetStatus') : 'Shown from saved source values when available'],
      ['XDP · own statuses', 'Sales Activity workbook → XDP tab · I', [...new Set(['DAMAGE', 'DELETE', 'NOT RECEIVED', ...sourceValues('xdpStatus')])]],
      ['STOPSTART · own statuses', 'Sales Activity workbook → STOPSTART tab · I', sourceValues('stopstartStatus')],
      ['Shared status shown among courier options', 'Saved carrier / fallback status', ['Awaiting', 'Unscheduled', 'Scheduled', 'Out for Delivery', 'Delivered', 'Failed', 'Rejected', 'Lost', 'Cancelled', 'Return', 'Unassigned']],
    ]],
    ['Own van status priority', [
      ['Failed (highest priority)', 'Routine Dashboard - Live · order cell in column A', '#FFFF00'],
      ['Scheduled (highest priority)', 'Routine Dashboard - Live · order cell in column A', ['#FFFFFF with an order number', '#FFC000']],
      ['Order matching', 'Between HYGIENIC ORDERS and XDP - Long Parcels; markers excluded', 'First six digits on each line; multiple lines identify separate orders; extra numbers on the same line are ignored'],
      ['Booking status', 'Routine Dashboard - Live · E on the matching order row', 'Expands Del weekday and o/s; dates use day-Mon-year, with the current UK year when absent. Changed values update and blank or missing rows clear on successful sync'],
      ['Ignored fill', 'Routine Dashboard - Live', '#FFE598; other colours do not override'],
      ['Normal fallback', 'OptimoRoute, then OW status', 'Used when no matching Routine override remains; a failed source read retains the last saved override'],
      ['Scope', 'Sales Activity · Delivery method', 'Own van only; Self Delivery and LOCAL MULTIDROP retain their usual statuses'],
    ]],
    ['Failed Deliveries · Inclusion and display', [
      ['Page inclusion', 'Saved delivery category', 'Current Failed and Rejected deliveries; original carrier labels can differ from the category'],
      ['Amazon Shipping failures', 'Amazon Shipping · G; matched from Sales Activity tracking number (S) to Amazon Shipping tracking ID (B)', ['UNDELIVERABLE → Failed', 'LOST → Failed', 'Original labels remain visible in red']],
      ['XDP failures', 'XDP · I', ['DAMAGE → Failed', 'DELETE → Failed', 'NOT RECEIVED → Failed', 'Original labels remain visible in red']],
      ['Own van failures', 'Routine Dashboard - Live · column A fill; otherwise OptimoRoute / OW fallback', '#FFFF00 overrides the usual status; text in booking status alone does not mark the delivery Failed'],
      ['Rejected deliveries', 'OptimoRoute / Palletways API / OW fallback', 'rejected / Refused / REJECTED also appear on Failed Deliveries'],
      ['Dynamic changes', 'Successful source refresh', 'New carrier statuses update the category; an order leaves this page when it is no longer Failed or Rejected'],
      ['Store icons and copy buttons', 'Same store mapping and sidebar as Tracking', 'Store icon in the customer cell; unmapped icon stays blank. Order No and Order Ref have copy buttons'],
      ['Activity timeline', 'Shared Tracking and Failed Deliveries sidebar', 'Saved status and booking updates are shown; sheet colour codes and cell references are hidden. Own van failures use red pulse dots and delivered events use green dots'],
    ]],
    ['Failed Deliveries · Filter levels', [
      ['Level 1 · General scope', 'Same general scopes as Tracking', 'General scope narrows available delivery methods; all levels respect Hide data settings'],
      ['Level 2 · Delivery method', 'Failed / Rejected records within the selected general scope', 'Only methods with matching records appear; Own van and Self Delivery share their method button'],
      ['Level 3 · Store', 'Stores present within the selected scope and delivery method', 'Stores with no matching failed records are omitted. Changing stores resets the status selection'],
      ['Level 3 · Status', 'Carrier-specific statuses within the selected scope, method and store', 'Only matching status labels and counts appear: for example Damage, Delete, Not Received, Undeliverable or Lost'],
      ['Parent selections', 'General scope → delivery method → store/status', 'Changing scope resets method, store and status; changing method resets store and status. A store selection does not remove the other method buttons'],
      ['Search and dates', 'Order/customer/contact search, failed or issue date, scheduled date', 'Date filters require a matching saved date. A Failed order with no recorded failure date is excluded by a failed-date range'],
    ]],
    ['Own van · Booking text formatting', [
      ['Delay weekday', 'Routine Dashboard - Live · E', 'Del Fri → Delay to the next Friday date, including today when Friday. Other weekdays work too'],
      ['Stock shorthand', 'Routine Dashboard - Live · E', 'o/s → Out of Stock; o/s & ND → Out of Stock & ND'],
      ['Date format', 'UK day/month order; current UK year when absent', '23-Oct gains the current year. partial delivered 5/10 → Partial delivered 5-Oct-YYYY; failed 10/1 → Failed 10-Jan-YYYY'],
      ['Explicit year and unknown text', 'Original column E text', 'Existing years are retained; invalid dates and unfamiliar text are preserved, with the first letter capitalized'],
      ['Booking versus delivery status', 'Booking text and colour-based delivery category are separate', 'A booking note starting with Failed does not by itself add the order to Failed Deliveries'],
    ]],
    ['Tracking · Shipment fields', [
      ['Amazon Tracking ID', 'Sales Activity · A order number and S tracking number', 'Shown before SKU with a copy button; this displayed tracking number is not taken from the Amazon Shipping tab'],
      ['Amazon scheduled time', 'Amazon Shipping · M, matched by tracking ID in B', 'Source timestamp is UTC and converted to UK time; this is separate from Inducted Date and Time'],
      ['Palletways number switch', 'Palletways tab · A order number; B Tracking ID; C consignment number', 'Click the cyan switch icon beside the number heading to switch between Tracking ID and Consignment No. The copy button copies the selected value; the choice is remembered in this browser. Conflicting or empty matches remain blank'],
      ['XDP Consignment No', 'XDP · A order number and XDP Consignments header', 'Shown before SKU with a copy button; ambiguous consignment matches remain blank'],
      ['XDP status and detail', 'XDP · I status / J latest detail / T document links / U parcel barcode', 'Source status labels remain visible; failure categories follow the Failed Deliveries rules above'],
      ['Special instructions', 'Saved order instructions', 'The general and STOPSTART tracking tables display these in a dedicated column. Amazon, XDP and Palletways display these in the sidebar Details'],
      ['SKU of items', 'Saved order product items', 'Displayed beneath the store icon in the sidebar for every store'],
      ['STOPSTART tracking button', 'STOPSTART · O Trackability', 'Open tracking appears only for Yes. No, Missing or Time Out do not show the button; saved delivery history is retained'],
      ['STOPSTART source fields', 'STOPSTART · A / I / J / N / O', 'A order, I source status, J Delivery Activity (legacy H), N Fetch Result, O Trackability'],
    ]],
    ['Integration · Data Trafficking', [
      ['Data flow overview', 'API → Google Sheets → Atlas', 'Google Sheets processes source data before display in Atlas'],
      ['Order date range', 'Sales Activity · B Order date', 'First section on the left; earliest through latest saved order date available in the app'],
      ['Sync Schedule', '_Sync_Control in the Sales Activity workbook', 'A Integration; C Frequency (Minutes); F Trigger Status; G Last Applied'],
      ['Estimated next run', 'Latest _Sync_Run_Log start time for the integration + frequency', 'Falls back to Last Applied when no run is logged. Uses the workbook time zone. This estimates the next run, not the exact Google trigger firing time'],
      ['Countdown refresh', 'Schedule reread every minute; countdown updates every second while this view is open', 'Disabled triggers show Not scheduled. An overdue estimate shows Due · awaiting run; missing date/frequency shows Time unavailable'],
      ['Data Sync Activity', '_Sync_Run_Log in the Sales Activity workbook', 'B Integration; C Started At; F Execution Result; H Records Inserted; I Records Updated'],
      ['Activity row visibility', '_Sync_Run_Log · H and I', 'Rows with no insert/update activity are hidden: both blank, both zero, or zero plus blank. Displayed totals use the visible rows'],
      ['Activity refresh and results', 'Read on opening Data Trafficking, then on its five-minute refresh cycle', 'Result text is preserved; RETURNED has a neutral blue badge, not an assumed success. Read failures retain last loaded data with a warning'],
      ['Smaller screens', 'Available workspace width, including navigation', 'Panels stack when needed; wide tables scroll within their own panels'],
    ]],
    ['Stores', [
      ['Amazon', 'Sales Activity · AH', 'AMAZON'],
      ['Hygienic Cleaning Company (UK) LTD', 'Sales Activity · Order Type (K)', 'Sales or HR_Replacement (takes priority over AH)'],
      ['Debenhams - Neshome', 'Sales Activity · AH', 'DEBENHAM'],
      ['B&Q', 'Sales Activity · AH', 'B&Q'],
      ['Ebay Bathroom Republic', 'Sales Activity · AH', 'EBAY_BR'],
      ['EBay Willesden Bathroom', 'Sales Activity · AH', 'EBAY_WB'],
      ['Shopify - Neshome', 'Sales Activity · AH', 'SHOPIFY'],
      ['Bathroom Republic - Website', 'Sales Activity · AH', ['BATHPROF', 'BATHREP', 'BATHROOM']],
      ['Wilko', 'Sales Activity · AH', 'WILKO'],
      ['Wayfair', 'Sales Activity · AH', 'WAYFAIR'],
    ]],
    ['Data switches', [
      ['Switch behaviour', 'Settings · Hide data', 'On means hide. Applies to Tracking and Failed Deliveries records, counts and relevant filter options'],
      ['Settings · Hygienic switch', 'OW Sales Activity · Order Type (K) / mapped store', 'Sales & HR_Replacement; legacy HG_Replacement is also hidden'],
      ['Settings · Wayfair switch', 'OW Sales Activity · AH or Delivery method (T)', 'WAYFAIR or Wayfair / Wayfair UPS'],
      ['Settings · Wilko switch', 'OW Sales Activity · AH', 'WILKO'],
      ['Settings · Palletways B2B switch', 'Palletways · Classification', 'B2B'],
    ]],
  ];
  const workflows = [
    ['Dashboard', 'Dashboard', [
      'Click an order number or preview record to open the same right-hand order details panel used in Tracking.',
      'Customize Widgets lets you drag cards into slots, rearrange them and remove them with the X. Changes save automatically; select Complete when finished.',
      'Widget guide replays the walkthrough at any time. Reset to Default restores the dashboard layout without deleting orders.',
    ]],
    ['Tracking & order details', 'Deliveries', [
      'Choose a general scope, delivery method, store and status, then narrow the results with search or dates. Filter options and counts follow the selected scope.',
      'Open an order to view its customer information, shipment tracking, progress, Activity, Details and Documents. Cyan copy buttons copy the labelled value or link.',
      'Palletways portal photos load using a visible browser window and the saved sign-in. Use Refresh photos to retry; renew the portal sign-in if requested.',
    ]],
    ['Collection Notes', 'note', [
      'Create a collection note, enter the order number and review the customer and item details. The sheet can be edited before saving.',
      'Save note stores it in Collection Notes. Open note reopens it; the X deletes a saved note after confirmation.',
      'Use the formatting toolbar, Print note, Download PDF or Download XLSX. Generating a note does not save it automatically.',
    ]],
    ['Manufacturing Claims', 'Manufacture Claims', [
      'Select New claim and enter the order date, original Order No and VariantCode. The replacement Order No is optional. Selling Shop uses the existing Tracking shop choices.',
      'Click a saved claim row to reopen its form. Edit the details, keep or change pictures, then select Save changes to update the same claim. Cancel leaves the saved claim unchanged.',
      'Reason options are Scratches, Broken parts, Leaking, Missing parts and Others. Solution options are Replacement, Refund and Others. Choosing Others reveals a field for your own text.',
      'Attach up to 5 JPG, PNG, WebP or GIF pictures: 5 MB each and 15 MB total. Preview or remove pictures before saving.',
      'Filter by Order month to narrow the table; XLSX and PDF export only those rows. Excel uses the reference spreadsheet layout. Click a picture for the zoomable gallery, or use the far-right X to delete a claim after confirmation. Saved claims and pictures remain after refresh.',
    ]],
    ['Store shortcuts & B&Q', 'pkg', [
      'The six dashboard store shortcuts also appear to the left of Data sources on operational pages. Their labels automatically slide to reveal the store logos.',
      'B&Q NesHome connects the installed, signed-in ExpressVPN app to UK London and opens the seller page in a dedicated browser window.',
      'Close all windows belonging to that B&Q session to disconnect the VPN. Keep Atlas running until the session closes. The other store shortcuts open normally.',
    ]],
    ['Sync information & screen sizing', 'Settings', [
      'Data sources shows the latest recorded sync time for each source. Open Integration & Data Trafficking for the full schedule and activity log.',
      'Desktop Atlas scales down automatically from a 1920 × 1080 reference workspace. For example, a 1440 × 810 browser viewport uses 75% scale.',
      'Mobile layouts and printed documents keep their own sizing. Hide data switches in Settings affect Tracking and Failed Deliveries records, counts and relevant filter options.',
    ]],
  ];
  queueMicrotask(applyGuidanceSearch);
  return `<div class="workflow-intro guidance-intro"><div><span class="guidance-eyebrow">ATLAS WORKSPACE</span><h1>Guidance</h1><p>Your guide to orders, widgets, notes and manufacturing claims.</p></div>
      <form class="guidance-search${guidanceSearchOpen ? ' is-open' : ''}" role="search" aria-label="Search guidance"><button type="button" class="guidance-search-toggle" data-guidance-search-toggle aria-label="Search guidance" aria-expanded="${guidanceSearchOpen}" aria-controls="guidance-search-field">${ico('search', 21)}</button><div id="guidance-search-field" class="guidance-search-field"><input type="search" data-guidance-search placeholder="Search all guidance…" aria-label="Search all guidance" autocomplete="off" value="${esc(guidanceSearchTerm)}" ${guidanceSearchOpen ? '' : 'disabled'}><button type="button" data-guidance-search-close aria-label="Clear and close guidance search" ${guidanceSearchOpen ? '' : 'disabled'}>${ico('x', 17)}</button></div></form></div>
    <p class="guidance-search-status" data-guidance-search-status role="status" aria-live="polite" hidden></p>
    <div class="guidance-content" data-guidance-content>
    <section class="guidance-workflows-section" aria-labelledby="guidance-workflows-heading"><h2 id="guidance-workflows-heading">Using Atlas</h2><div class="guidance-workflows">${workflows.map(([title, icon, instructions]) => `<article class="guidance-workflow"><h3><span>${ico(icon, 20)}</span>${esc(title)}</h3><ul>${instructions.map(instruction => `<li>${esc(instruction)}</li>`).join('')}</ul></article>`).join('')}</div></section>
    <section class="card guidance-reference" aria-labelledby="guidance-filters-heading">
      <h2 id="guidance-filters-heading">Filter values &amp; data sources</h2>
      <p class="mut">OW means OrderWise Sales Activity. Column letters refer to the named source tab. Carrier buttons group the OW delivery method; the displayed status can come from a different source.</p>
      ${groups.map(([group, rows]) => `${group === 'Tracking · Status with All methods selected' ? overallStatusTable : ''}<div class="guidance-table-scroll" role="region" aria-label="${esc(group)}" tabindex="0">
        <table class="guidance-table">
          <caption>${esc(group)}</caption>
          <thead><tr><th scope="col">Filter value</th><th scope="col">Data source / field</th><th scope="col">Specific source value</th></tr></thead>
          <tbody>${rows.map(([value, source, rule]) => `<tr>
            <th scope="row">${esc(value)}</th><td>${esc(source)}</td><td>${Array.isArray(rule)
              ? rule.length ? `<ul class="guidance-source-values">${rule.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : '—'
              : esc(rule)}</td>
          </tr>`).join('')}</tbody>
        </table>
      </div>`).join('')}
    </section></div>`;
}

function applyGuidanceSearch() {
  const root = document.querySelector('[data-guidance-content]');
  if (!root) return;
  root.querySelectorAll('mark[data-guidance-match]').forEach(mark => {
    const parent = mark.parentNode;
    mark.replaceWith(document.createTextNode(mark.textContent));
    parent.normalize();
  });
  const words = [...new Set(guidanceSearchTerm.trim().toLowerCase().split(/\s+/).filter(Boolean))];
  const matches = text => words.every(word => text.toLowerCase().includes(word));
  let count = 0;
  const workflows = root.querySelector('.guidance-workflows-section');
  const allWorkflows = matches(workflows.querySelector('h2').textContent);
  workflows.querySelectorAll('.guidance-workflow').forEach(article => {
    article.hidden = !allWorkflows && !matches(article.textContent);
    if (!article.hidden) count++;
  });
  workflows.hidden = ![...workflows.querySelectorAll('.guidance-workflow')].some(article => !article.hidden);
  const reference = root.querySelector('.guidance-reference');
  const allReference = matches([...reference.children].filter(node => node.matches('h2,p')).map(node => node.textContent).join(' '));
  reference.querySelectorAll('.guidance-table-scroll').forEach(group => {
    const context = [...group.querySelectorAll('caption,thead,.guidance-mapping-note')].map(node => node.textContent).join(' ');
    const allRows = allReference || matches(context);
    let visible = 0;
    group.querySelectorAll('tbody tr').forEach(row => {
      row.hidden = !allRows && !matches(row.textContent);
      if (!row.hidden) visible++;
    });
    group.hidden = !visible;
    count += visible;
  });
  reference.hidden = ![...reference.querySelectorAll('.guidance-table-scroll')].some(group => !group.hidden);
  const status = document.querySelector('[data-guidance-search-status]');
  status.hidden = !words.length;
  status.textContent = count ? `${count} matching guidance ${count === 1 ? 'item' : 'items'}` : `No guidance found for “${guidanceSearchTerm.trim()}”. Try another word.`;
  if (!words.length) return;
  const escaped = words.map(word => word.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
  const pattern = new RegExp(escaped.join('|'), 'gi');
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode: node =>
    node.parentElement.closest('[hidden],svg,button,input,select,textarea') || !node.textContent.trim() ? NodeFilter.FILTER_REJECT : NodeFilter.FILTER_ACCEPT});
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) {
    const text = node.textContent;
    pattern.lastIndex = 0;
    const hits = [...text.matchAll(pattern)];
    if (!hits.length) continue;
    const fragment = document.createDocumentFragment();
    let start = 0;
    hits.forEach(hit => {
      fragment.append(document.createTextNode(text.slice(start, hit.index)));
      const mark = document.createElement('mark'); mark.dataset.guidanceMatch = ''; mark.textContent = hit[0]; fragment.append(mark);
      start = hit.index + hit[0].length;
    });
    fragment.append(document.createTextNode(text.slice(start)));
    node.replaceWith(fragment);
  }
}

function toggleGuidanceSearch(open) {
  const shell = document.querySelector('.guidance-search');
  if (!shell) return;
  guidanceSearchOpen = open;
  shell.classList.toggle('is-open', open);
  shell.querySelector('[data-guidance-search-toggle]').setAttribute('aria-expanded', String(open));
  shell.querySelectorAll('input,[data-guidance-search-close]').forEach(node => { node.disabled = !open; });
  if (open) shell.querySelector('input').focus();
  else {
    guidanceSearchTerm = ''; shell.querySelector('input').value = ''; applyGuidanceSearch();
    shell.querySelector('[data-guidance-search-toggle]').focus();
  }
}

document.addEventListener('click', event => {
  if (event.target.closest('[data-guidance-search-toggle]')) toggleGuidanceSearch(!guidanceSearchOpen);
  if (event.target.closest('[data-guidance-search-close]')) toggleGuidanceSearch(false);
});
document.addEventListener('input', event => {
  if (!event.target.matches('[data-guidance-search]')) return;
  guidanceSearchTerm = event.target.value;
  applyGuidanceSearch();
});
document.addEventListener('submit', event => { if (event.target.matches('.guidance-search')) event.preventDefault(); });
document.addEventListener('keydown', event => {
  if (event.key === 'Escape' && event.target.closest('.guidance-search')) { event.preventDefault(); toggleGuidanceSearch(false); }
});


document.addEventListener('change', event => {
  const key = event.target.dataset.settingsCompany;
  if (!['hygienic', 'wayfair', 'wilko', 'palletways-b2b'].includes(key)) return;
  if (key === 'hygienic') {
    TrackingVisibility.setEnabled(event.target.checked);
    hygienicFilterAnimated = false;
    if (event.target.checked && trackingScope === 'hygienic') trackingScope = '';
  } else if (key === 'wilko') {
    TrackingVisibility.setWilkoEnabled(event.target.checked);
  } else if (key === 'palletways-b2b') {
    TrackingVisibility.setPalletwaysB2bEnabled(event.target.checked);
  } else {
    TrackingVisibility.setWayfairEnabled(event.target.checked);
    if (event.target.checked && fsrc === 'Wayfair') { fsrc = ''; fclassification = []; fs = ''; }
  }
  fstore = compactFilter(filterValues(fstore).filter(value => TrackingVisibility.includesStore(value)));
  trackingRequest++;
  trackingLoaded = [];
  trackingOffset = 0;
  dashboardSelectedId = null;
});
