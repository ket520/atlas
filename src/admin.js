function vManufactureClaims() {
  return ManufactureClaims.render();
}

function collectionNoteNumber(order) {
  const number = String(order || '').trim().replace(/^(?:CN\s*)+/i, '');
  return number ? 'CN' + number : '';
}

let collectionRecordsSearch = '';
let collectionMethodFilter = '', collectionStatusFilter = '';
let collectionBulkMode = false;
const collectionBulkSelection = new Set();
let collectionRecordsData = [];
let collectionCreatedFrom = '', collectionCreatedTo = '';
let collectionCreatedSort = '';

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

function collectionRecordFilters() {
  const select = (key, label, value, options) => UiSelect.render(`collection-${key}-filter`, value,
    [['', label], ...options.map(option => [option, option])], {
      className: 'collection-record-filter', ariaLabel: `Filter by ${label.toLowerCase()}`,
      onChange: value => {
        if (key === 'method') collectionMethodFilter = value;
        else collectionStatusFilter = value;
        renderCollectionRecords();
      },
    });
  return select('method', 'Collection Method', collectionMethodFilter, ['Replacement', 'Refund']) + select('status', 'Status', collectionStatusFilter, ['Pending', 'Approved', 'Rejected']);
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
    <div class="collection-records-toolbar"><label class="delivery-search">${ico('search', 18)}<input type="search" data-collection-records-search placeholder="Search Order No or Order Reference No" aria-label="Search collection notes by order or reference number" value="${esc(collectionRecordsSearch)}"></label>${collectionRecordFilters()}<span id="collection-records-count" role="status" aria-live="polite"></span>${collectionDateFilter()}<a class="collection-note-link" href="./collective-note.html?view=create">${ico('plus', 16)}<span>Create collection note</span></a></div>
    <div class="tracking-table-wrap">
      <table class="tracking-table collection-records-table" aria-label="Collection note records">
        <thead><tr><th>Order No</th><th>Order Reference No</th><th data-collection-created-header aria-sort="${collectionCreatedSort === 'asc' ? 'ascending' : collectionCreatedSort === 'desc' ? 'descending' : 'none'}"><button type="button" class="table-date-sort" data-collection-sort-created aria-label="Sort collection date created">Date Created <span class="table-date-sort-indicator" aria-hidden="true">${dateSortIcon(collectionCreatedSort)}</span></button></th><th>Customer</th><th>Postcode</th><th>Channel</th><th>Tel</th><th>Collection<br>Date</th><th>Collection Method</th><th>Status</th><th><div class="collection-actions-heading"><span>Actions</span><button type="button" class="collection-bulk-edit-trigger" data-collection-bulk-edit aria-label="Bulk edit collection notes" title="Bulk edit collection notes" aria-expanded="false"><span class="collection-edit-icon">${ico('pencil', 16)}</span><span class="collection-edit-done">Done</span></button></div></th></tr></thead>
        <tbody id="collection-records"><tr><td colspan="11" class="tracking-empty" role="status">Loading collection records…</td></tr></tbody>
      </table>
    </div>
    <div class="collection-bulk-toolbar" data-collection-bulk-toolbar popover="manual" hidden><span data-collection-bulk-count>0 selected</span><div class="collection-bulk-status-actions"><button type="button" data-collection-bulk-status="Approved" disabled>Approve</button><button type="button" data-collection-bulk-status="Pending" disabled>On Hold</button><button type="button" data-collection-bulk-status="Rejected" disabled>Reject</button></div><div class="collection-bulk-file-actions"><button type="button" data-collection-bulk-download="pdf" disabled>${ico('download', 14)} PDF</button><button type="button" data-collection-bulk-download="xlsx" disabled>${ico('download', 14)} XLSX</button><button type="button" data-collection-bulk-print disabled>${ico('print', 14)} Print</button></div><div class="collection-bulk-delete-actions"><button type="button" class="collection-bulk-delete" data-collection-bulk-delete disabled>${ico('x', 14)} Delete notes</button></div></div>
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
    body.innerHTML = `<tr><td colspan="11" class="tracking-empty" role="alert">${esc(error.message)} <button type="button" onclick="loadCollectionRecords()">Retry</button></td></tr>`;
  }
}

function collectionStatusSwitch(note) {
  const status = ['Approved', 'Rejected'].includes(note.status) ? note.status : 'Pending';
  const options = [
    ['Approved', 'Approve', 'approve'],
    ['Pending', 'On Hold', 'hold'],
    ['Rejected', 'Reject', 'reject'],
  ];
  return `<span class="collection-approval-action" role="group" aria-label="Collection note status" data-active-status="${status}"><span class="collection-status-slider" aria-hidden="true"></span>${options.map(([value, label, tone]) => `<button type="button" class="collection-${tone}-note" data-approve-collection-record="${esc(note.id)}" data-status="${value}" aria-pressed="${status === value}" ${status === value ? 'disabled' : ''}><span>${label}</span></button>`).join('')}</span>`;
}

function collectionStatusMarker() {
  return '';
}

function renderCollectionRecords() {
    const body = document.getElementById('collection-records');
    if (!body) return;
    const search = collectionRecordsSearch.trim().toLowerCase();
    const preferred = exactOrderMatches(collectionRecordsData.map(note => ({ ...note, noteNumber: collectionNoteNumber(note.order) })), search, ['order', 'noteNumber']);
    const records = sortDeliveriesByDate(preferred.filter(note => {
      const day = collectionCreatedDay(note);
      return (!search || [note.order, collectionNoteNumber(note.order), note.orderRef].some(value => String(value || '').toLowerCase().includes(search)))
        && (!collectionMethodFilter || note.collectionMethod === collectionMethodFilter)
        && (!collectionStatusFilter || (['Approved', 'Rejected'].includes(note.status) ? note.status : 'Pending') === collectionStatusFilter)
        && (!collectionCreatedFrom || day && day >= collectionCreatedFrom)
        && (!collectionCreatedTo || day && day <= collectionCreatedTo);
    }), collectionCreatedSort, note => note.createdAt);
    const copyOrderCell = (value, reference = false) => value ? `<span class="tracking-order-number">${esc(value)}${!reference || canCopyOrderReference(value) ? `<button type="button" class="qd-customer-copy" ${reference ? 'data-copy-order-reference' : 'data-copy-order-number'}="${esc(value)}" aria-label="Copy ${reference ? 'order reference' : 'order number'} ${esc(value)}" title="Copy ${reference ? 'order reference' : 'order number'}">${ico('copy', 13, 1.8)}</button>` : ''}</span>` : '—';
    const createdDate = note => {
      const date = new Date(note.createdAt);
      return note.createdAt && Number.isFinite(date.getTime()) ? `<time datetime="${esc(note.createdAt)}" title="${esc(note.createdAt)}">${esc(date.toLocaleDateString('en-GB', {timeZone: 'Europe/London'}))}</time>` : '—';
    };
    body.innerHTML = records.length ? records.map(note => `<tr data-open-collection-record="${esc(note.id)}" data-note-status="${['Approved', 'Rejected'].includes(note.status) ? note.status : 'Pending'}" tabindex="0" aria-label="Open collection note for order ${esc(note.order)}">
      <td class="collection-order-cell">${collectionBulkMode ? `<input type="checkbox" class="collection-bulk-checkbox" data-collection-bulk-note="${esc(note.id)}" aria-label="Select collection note ${esc(note.order)}" ${collectionBulkSelection.has(note.id) ? 'checked' : ''}>` : collectionStatusMarker(note.status)}${copyOrderCell(collectionNoteNumber(note.order))}</td><td>${copyOrderCell(note.orderRef, true)}</td><td>${createdDate(note)}</td>
      <td>${esc(note.customer || '—')}</td><td>${esc(note.postcode || '—')}</td><td>${esc(note.channel || '\u2014')}</td><td>${esc(note.phone || '\u2014')}</td>
      <td>${esc(note.collectionDate || '—')}</td><td>${esc(note.collectionMethod || '\u2014')}</td><td class="collection-status-cell">${collectionStatusSwitch(note)}</td>
      <td><div class="collection-record-actions">${['pdf', 'xlsx'].map(format => `<button type="button" class="collection-record-download" data-download-collection-record="${esc(note.id)}" data-format="${format}" title="Download ${format.toUpperCase()}" aria-label="Download ${format.toUpperCase()} for order ${esc(note.order)}"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 16v5h14v-5"/></svg>${format.toUpperCase()}</button>`).join('')}<button type="button" class="collection-record-download collection-record-print" data-print-collection-record="${esc(note.id)}" title="Print note" aria-label="Print collection note for order ${esc(note.order)}">${ico('print', 14)}</button><button type="button" class="collection-delete-note" title="Delete note" data-delete-collection-record="${esc(note.id)}" aria-label="Delete collection note for order ${esc(note.order)}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/></svg></button></div></td>
    </tr>`).join('') : `<tr><td colspan="11" class="tracking-empty">${collectionRecordsData.length ? 'No collection notes match the selected search, filters or dates.' : 'No collection records yet. Create a collection note and choose Save note.'}</td></tr>`;
    const count = document.getElementById('collection-records-count');
    if (count) count.textContent = `${records.length} of ${collectionRecordsData.length} notes`;
    syncCollectionBulkControls();
}

function syncCollectionBulkControls() {
  const toolbar = document.querySelector('[data-collection-bulk-toolbar]');
  if (!toolbar) return;
  toolbar.hidden = !collectionBulkMode;
  if (collectionBulkMode && !toolbar.matches(':popover-open')) toolbar.showPopover();
  if (!collectionBulkMode && toolbar.matches(':popover-open')) toolbar.hidePopover();
  const table = document.querySelector('.collection-records-table');
  table?.classList.toggle('is-bulk-edit', collectionBulkMode);
  if (table) {
    const headerRow = table.querySelector('thead tr');
    if (collectionBulkMode && !headerRow.querySelector('.collection-selection-cell')) {
      const header = document.createElement('th');
      header.className = 'collection-selection-cell';
      header.innerHTML = '<input type="checkbox" data-collection-bulk-all aria-label="Select all visible notes">';
      headerRow.prepend(header);
    }
    table.querySelectorAll('tbody tr[data-open-collection-record]').forEach(row => {
      if (!collectionBulkMode) return;
      let cell = row.querySelector('.collection-selection-cell');
      if (!cell) {
        cell = document.createElement('td');
        cell.className = 'collection-selection-cell';
        row.prepend(cell);
      }
      let input = row.querySelector('[data-collection-bulk-note]');
      if (!input) {
        input = document.createElement('input');
        input.type = 'checkbox';
        input.className = 'collection-bulk-checkbox';
        input.dataset.collectionBulkNote = row.dataset.openCollectionRecord;
        input.setAttribute('aria-label', 'Select collection note ' + row.querySelector('.collection-order-cell').textContent.trim());
      }
      input.hidden = false;
      input.checked = collectionBulkSelection.has(row.dataset.openCollectionRecord);
      cell.append(input);
    });
    if (!collectionBulkMode) table.querySelectorAll('.collection-selection-cell').forEach(cell => cell.remove());
  }
  document.querySelectorAll('#collection-records td[colspan]').forEach(cell => { cell.colSpan = collectionBulkMode ? 12 : 11; });
  const editButton = document.querySelector('[data-collection-bulk-edit]');
  if (editButton) {
    const home = document.querySelector('.collection-actions-heading');
    const destination = collectionBulkMode ? toolbar : home;
    if (destination && editButton.parentElement !== destination) destination.append(editButton);
    editButton.setAttribute('aria-expanded', String(collectionBulkMode));
    editButton.setAttribute('aria-label', collectionBulkMode ? 'Done bulk editing' : 'Bulk edit collection notes');
    editButton.title = collectionBulkMode ? 'Done bulk editing' : 'Bulk edit collection notes';
    editButton.disabled = toolbar.getAttribute('aria-busy') === 'true';
    // Keep both faces mounted so CSS can animate the button swap.
  }
  toolbar.querySelector('[data-collection-bulk-count]').textContent = `${collectionBulkSelection.size} selected`;
  toolbar.querySelectorAll('[data-collection-bulk-status], [data-collection-bulk-download], [data-collection-bulk-print], [data-collection-bulk-delete]').forEach(button => { button.disabled = !collectionBulkSelection.size || toolbar.getAttribute('aria-busy') === 'true'; });
  const checkboxes = [...document.querySelectorAll('[data-collection-bulk-note]')];
  const checked = checkboxes.filter(input => input.checked).length;
  const all = document.querySelector('[data-collection-bulk-all]');
  if (!all) return;
  all.checked = checkboxes.length > 0 && checked === checkboxes.length;
  all.indeterminate = checked > 0 && checked < checkboxes.length;
}

let collectionBulkTransitioning = false;
document.addEventListener('click', async event => {
  const trigger = event.target.closest('[data-collection-bulk-edit]');
  if (!trigger || trigger.disabled || collectionBulkTransitioning) return;
  const toolbar = document.querySelector('[data-collection-bulk-toolbar]');
  const table = document.querySelector('.collection-records-table');
  if (!toolbar || !table || toolbar.getAttribute('aria-busy') === 'true') return;
  collectionBulkTransitioning = true;
  const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const opening = !collectionBulkMode;
  const before = new Map([...table.querySelectorAll('thead th')].map(cell => [cell, cell.getBoundingClientRect()]));
  try {
    if (!opening && !reduced) {
      toolbar.inert = true;
      await toolbar.animate([
        {opacity: 1, transform: 'translateY(0)'},
        {opacity: 0, transform: 'translateY(16px)'},
      ], {duration: 260, easing: 'cubic-bezier(.22,1,.36,1)'}).finished;
    }
    const dataHeaders = [...table.querySelectorAll('thead th:not(.collection-selection-cell)')];
    if (opening) dataHeaders.forEach(cell => { cell.dataset.normalWidth = cell.getBoundingClientRect().width; });
    dataHeaders.forEach((cell, index) => {
      const width = Number(cell.dataset.normalWidth);
      cell.style.width = `${index === dataHeaders.length - 1 && opening ? Math.max(78, width - 48) : width}px`;
    });
    collectionBulkMode = opening;
    collectionBulkSelection.clear();
    syncCollectionBulkControls();
    toolbar.inert = false;
    if (!reduced) {
      const headers = [...table.querySelectorAll('thead th')];
      const after = headers.map(cell => cell.getBoundingClientRect());
      const columnAnimations = headers.flatMap((header, index) => [...table.querySelectorAll(`tr > :nth-child(${index + 1}):not([colspan])`)].map(cell => cell.animate([
        {transform: `translateX(${(before.get(header)?.left ?? after[index].left) - after[index].left}px)`},
        {transform: 'translateX(0)'},
      ], {duration: 360, easing: 'cubic-bezier(.22,1,.36,1)'}).finished));
      if (!opening) table.querySelectorAll('.collection-record-download').forEach(button => {
        button.animate([{opacity: 0, transform: 'translateX(12px)'}, {opacity: 1, transform: 'translateX(0)'}],
          {duration: 300, easing: 'cubic-bezier(.22,1,.36,1)'});
      });
      if (opening) {
        await toolbar.animate([
          {opacity: 0, transform: 'translateY(16px)'},
          {opacity: 1, transform: 'translateY(0)'},
        ], {duration: 360, easing: 'cubic-bezier(.22,1,.36,1)'}).finished;
      }
      await Promise.all(columnAnimations);
    }
    if (!opening) {
      table.querySelectorAll('thead th').forEach(cell => { cell.style.width = ''; });
      table.style.marginLeft = '';
      table.style.width = '';
    }
    trigger.focus({preventScroll: true});
  } finally {
    toolbar.inert = false;
    collectionBulkTransitioning = false;
  }
});

document.addEventListener('change', event => {
  if (event.target.matches('[data-collection-bulk-note]')) {
    const id = event.target.dataset.collectionBulkNote;
    if (event.target.checked) collectionBulkSelection.add(id);
    else collectionBulkSelection.delete(id);
  } else if (event.target.matches('[data-collection-bulk-all]')) {
    document.querySelectorAll('[data-collection-bulk-note]').forEach(input => {
      input.checked = event.target.checked;
      if (input.checked) collectionBulkSelection.add(input.dataset.collectionBulkNote);
      else collectionBulkSelection.delete(input.dataset.collectionBulkNote);
    });
  } else return;
  syncCollectionBulkControls();
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-collection-bulk-status]');
  if (!button || button.disabled) return;
  const toolbar = button.closest('[data-collection-bulk-toolbar]');
  const ids = [...collectionBulkSelection];
  const status = button.dataset.collectionBulkStatus;
  toolbar.setAttribute('aria-busy', 'true');
  toolbar.querySelectorAll('button,input').forEach(control => { control.disabled = true; });
  document.querySelectorAll('[data-collection-bulk-note]').forEach(input => { input.disabled = true; });
  document.querySelector('[data-collection-bulk-edit]').disabled = true;
  const failures = [];
  try {
    for (const id of ids) {
      try {
        const response = await fetch(`/api/collection-notes/${encodeURIComponent(id)}/status`, {
          method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({status}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not update note.');
        const note = collectionRecordsData.find(note => note.id === id);
        if (note) note.status = result.status;
      } catch { failures.push(id); }
    }
  } finally {
    toolbar.removeAttribute('aria-busy');
    toolbar.querySelectorAll('button,input').forEach(control => { control.disabled = false; });
    document.querySelector('[data-collection-bulk-edit]').disabled = false;
    renderCollectionRecords();
    toast(failures.length ? `${ids.length - failures.length} updated; ${failures.length} could not be updated. Failed notes remain selected.` : `${ids.length} notes set to ${status.toLowerCase()}`);
  }
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-approve-collection-record]');
  if (!button || button.disabled) return;
  const group = button.closest('.collection-approval-action');
  const previousStatus = group.dataset.activeStatus;
  group.dataset.activeStatus = button.dataset.status;
  decisionsForStatus(group, button.dataset.status);
  group.setAttribute('aria-busy', 'true');
  const decisions = [...group.querySelectorAll('button')];
  const disabledBefore = decisions.map(action => action.disabled);
  decisions.forEach(action => { action.disabled = true; });
  try {
    const response = await fetch(`/api/collection-notes/${encodeURIComponent(button.dataset.approveCollectionRecord)}/status`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({status: button.dataset.status}),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not update note status.');
    const note = collectionRecordsData.find(note => note.id === button.dataset.approveCollectionRecord);
    if (note) note.status = result.status;
    group.closest('tr').dataset.noteStatus = result.status;
    group.dataset.activeStatus = result.status;
    group.removeAttribute('aria-busy');
    decisionsForStatus(group, result.status);
    decisions.forEach(action => { action.disabled = action.dataset.status === result.status; });
    if (collectionStatusFilter && collectionStatusFilter !== result.status) {
      const row = group.closest('tr');
      const motion = matchMedia('(prefers-reduced-motion: reduce)').matches;
      await new Promise(resolve => setTimeout(resolve, motion ? 0 : 420));
      if (row.isConnected && collectionStatusFilter && collectionStatusFilter !== result.status) {
        if (!motion) await row.animate([{opacity: 1}, {opacity: 0, transform: 'translateY(-4px)'}], {duration: 180, fill: 'forwards'}).finished;
        renderCollectionRecords();
      }
    }
    toast(`Note ${result.status.toLowerCase()}`);
  } catch (error) {
    group.dataset.activeStatus = previousStatus;
    decisionsForStatus(group, previousStatus);
    group.removeAttribute('aria-busy');
    decisions.forEach((action, index) => { action.disabled = disabledBefore[index]; });
    toast(error.message || 'Could not update note status.');
  }
});

function decisionsForStatus(group, status) {
  group.querySelectorAll('button').forEach(action => action.setAttribute('aria-pressed', String(action.dataset.status === status)));
}

function openCollectionRecordRow(event) {
  const row = event.target.closest('[data-open-collection-record]');
  if (!row || event.defaultPrevented || event.target.closest('button,a,input,select,textarea')) return;
  if (collectionBulkMode) {
    if (document.querySelector('[data-collection-bulk-toolbar][aria-busy="true"]')) return;
    if (event.type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
    event.preventDefault();
    const checkbox = row.querySelector('[data-collection-bulk-note]');
    checkbox.checked = !checkbox.checked;
    checkbox.dispatchEvent(new Event('change', {bubbles: true}));
    return;
  }
  if (event.target.closest('.collection-status-cell, .collection-record-actions') ||
      event.target.closest('td') === row.lastElementChild) return;
  if (event.type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
  if (event.type === 'click' && (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey)) return;
  if (event.type === 'click' && window.getSelection()?.toString()) return;
  event.preventDefault();
  location.href = './collective-note.html?' + new URLSearchParams({view: 'create', record: row.dataset.openCollectionRecord});
}

document.addEventListener('click', openCollectionRecordRow);
document.addEventListener('keydown', openCollectionRecordRow);

document.addEventListener('input', event => {
  if (!event.target.matches('[data-collection-records-search]')) return;
  collectionRecordsSearch = event.target.value;
  renderCollectionRecords();
});

document.addEventListener('change', event => {
  const filter = event.target.dataset.collectionRecordFilter;
  if (!filter) return;
  if (filter === 'method') collectionMethodFilter = event.target.value;
  if (filter === 'status') collectionStatusFilter = event.target.value;
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

async function printCollectionRecords(ids) {
  const notes = await Promise.all(ids.map(id => ApiClient.get('/collection-notes/' + encodeURIComponent(id))));
  if (notes.some(note => !note.paper)) throw new Error('Could not open all selected notes for printing.');
  const printablePaper = markup => {
    const parsed = new DOMParser().parseFromString(markup, 'text/html');
    const tags = new Set(['TABLE', 'COLGROUP', 'COL', 'TBODY', 'THEAD', 'TFOOT', 'TR', 'TD', 'TH', 'INPUT', 'TEXTAREA', 'LABEL', 'SPAN', 'BR']);
    const attrs = new Set(['class', 'name', 'value', 'type', 'colspan', 'rowspan', 'aria-label', 'scope', 'min', 'max', 'step', 'data-inserted']);
    for (const element of [...parsed.body.querySelectorAll('*')]) {
      if (!tags.has(element.tagName)) { element.remove(); continue; }
      for (const attribute of [...element.attributes]) if (!attrs.has(attribute.name)) element.removeAttribute(attribute.name);
      if (element.tagName === 'INPUT' && !['text', 'date', 'number', 'tel'].includes(element.type)) element.type = 'text';
    }
    return parsed.body.innerHTML;
  };
  const frame = document.createElement('iframe');
  frame.title = 'Print selected collection notes';
  frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
  frame.setAttribute('aria-hidden', 'true');
  frame.tabIndex = -1;
  frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1200px;height:1000px;border:0';
  const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
  frame.srcdoc = '<!doctype html><html><head><title>Collection notes</title><link rel="stylesheet" href="' + location.origin + '/static/css/general.css"><link rel="stylesheet" href="' + location.origin + '/static/css/collection.css"><style>.collection-print-note { break-after: page; } .collection-print-note:last-child { break-after: auto; }</style></head><body data-page="Collective Note"><section id="collection-note-root">' + notes.map(note => '<div class="collection-print-note"><div class="cn-paper">' + printablePaper(note.paper) + '</div></div>').join('') + '</section></body></html>';
  document.body.append(frame);
  try {
    await loaded;
    await frame.contentDocument.fonts.ready;
    frame.contentDocument.querySelectorAll('input, textarea').forEach(field => {
      field.readOnly = true;
      field.tabIndex = -1;
    });
    frame.contentDocument.querySelectorAll('textarea').forEach(field => {
      field.style.height = 'auto';
      field.style.height = `${field.scrollHeight}px`;
    });
    frame.contentWindow.addEventListener('afterprint', () => frame.remove(), {once: true});
    frame.contentWindow.focus();
    frame.contentWindow.print();
    setTimeout(() => frame.remove(), 300000);
  } catch (error) { frame.remove(); throw error; }
}

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-collection-bulk-print]');
  if (!button || button.disabled) return;
  const toolbar = button.closest('[data-collection-bulk-toolbar]');
  toolbar.setAttribute('aria-busy', 'true');
  button.setAttribute('aria-busy', 'true');
  syncCollectionBulkControls();
  try {
    await printCollectionRecords([...collectionBulkSelection]);
  } catch (error) { toast(error.message || 'Could not print the selected notes.'); }
  finally {
    toolbar.removeAttribute('aria-busy');
    button.removeAttribute('aria-busy');
    syncCollectionBulkControls();
    button.focus({preventScroll: true});
  }
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-print-collection-record]');
  if (!button || button.disabled) return;
  button.disabled = true;
  button.setAttribute('aria-busy', 'true');
  try {
    await printCollectionRecords([button.dataset.printCollectionRecord]);
  } catch (error) { toast(error.message || 'Could not print the saved note.'); }
  finally {
    button.disabled = false;
    button.removeAttribute('aria-busy');
    if (button.isConnected) button.focus({preventScroll: true});
  }
});

function downloadCollectionRecord(record, format) {
  return new Promise(resolve => {
    const frame = document.createElement('iframe');
    frame.title = 'Collection note download';
    frame.setAttribute('aria-hidden', 'true');
    frame.tabIndex = -1;
    frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1200px;height:1000px;visibility:hidden;border:0;pointer-events:none';
    const finish = result => {
      clearTimeout(timeout);
      window.removeEventListener('message', complete);
      setTimeout(() => frame.remove(), 1000);
      resolve(result);
    };
    const complete = event => {
      if (event.origin !== location.origin || event.source !== frame.contentWindow
        || event.data?.type !== 'collection-record-download' || event.data.record !== record) return;
      finish({ok: Boolean(event.data.ok), error: event.data.error});
    };
    const timeout = setTimeout(() => finish({ok: false, error: 'Download timed out. Please try again.'}), 90000);
    window.addEventListener('message', complete);
    frame.src = `./collective-note.html?${new URLSearchParams({view: 'create', record, download: format})}`;
    document.body.append(frame);
  });
}

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-download-collection-record]');
  if (!button || button.disabled) return;
  const record = button.dataset.downloadCollectionRecord, format = button.dataset.format;
  const buttons = [...button.closest('.collection-record-actions').querySelectorAll('[data-download-collection-record]')];
  buttons.forEach(node => { node.disabled = true; });
  button.setAttribute('aria-busy', 'true');
  toast(`Preparing ${format.toUpperCase()} download?`);
  const result = await downloadCollectionRecord(record, format);
  buttons.forEach(node => { node.disabled = false; });
  button.removeAttribute('aria-busy');
  toast(result.ok ? `${format.toUpperCase()} downloaded.` : result.error || 'Could not download the saved note.');
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-collection-bulk-download], [data-collection-bulk-delete]');
  if (!button || button.disabled) return;
  const ids = [...collectionBulkSelection];
  const deleting = button.hasAttribute('data-collection-bulk-delete');
  if (deleting && !await confirmSavedRecordDelete('', `${ids.length} selected collection notes`, `Delete ${ids.length} notes`)) return;
  const toolbar = button.closest('[data-collection-bulk-toolbar]');
  toolbar.setAttribute('aria-busy', 'true');
  toolbar.querySelectorAll('button,input').forEach(control => { control.disabled = true; });
  document.querySelectorAll('[data-collection-bulk-note]').forEach(input => { input.disabled = true; });
  document.querySelector('[data-collection-bulk-edit]').disabled = true;
  let completed = 0;
  try {
    for (const id of ids) {
      try {
        if (deleting) {
          const response = await fetch(`/api/collection-notes/${encodeURIComponent(id)}`, {method: 'DELETE'});
          const result = await response.json();
          if (!response.ok) throw new Error(result.error || 'Could not delete note.');
          collectionRecordsData = collectionRecordsData.filter(note => note.id !== id);
          collectionBulkSelection.delete(id);
        } else {
          toolbar.querySelector('[data-collection-bulk-count]').textContent = `Downloading ${completed + 1} of ${ids.length}?`;
          const result = await downloadCollectionRecord(id, button.dataset.collectionBulkDownload);
          if (!result.ok) throw new Error(result.error || 'Could not download note.');
        }
        completed++;
      } catch { /* Keep unsuccessful notes selected for retry. */ }
    }
  } finally {
    toolbar.removeAttribute('aria-busy');
    toolbar.querySelectorAll('button,input').forEach(control => { control.disabled = false; });
    document.querySelector('[data-collection-bulk-edit]').disabled = false;
    renderCollectionRecords();
    toast(`${completed} of ${ids.length} notes ${deleting ? 'deleted' : 'downloaded'}${completed < ids.length ? '. Some notes could not be processed; try again.' : '.'}`);
  }
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
    collectionBulkSelection.delete(button.dataset.deleteCollectionRecord);
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
  if (summary?.disabledSources?.includes(source.key)) return { label: 'Disabled', tone: 'offline' };
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
  const method = source.key === 'ow' && summary?.deliverySource === 'postgresql' ? 'Atlas API' : source.method;
  return `<article class="card integration-card">
    <div><h3>${esc(source.name)}</h3><small class="mut">${esc(method)}</small></div>
    <span class="integration-state" data-state="${state.tone}">${esc(state.label)}</span>
    <div><small class="mut">Last successful update</small><b>${esc(integrationTime(summary?.sourceUpdatedAt?.[source.key]))}</b></div>
  </article>`;
}

function integrationOrderRangeLabel(summary) {
  const orderRange = summary?.orderDateRanges?.All;
  return orderRange?.from && orderRange?.to
    ? `${hd(orderRange.from)} – ${hd(orderRange.to)}`
    : summary ? 'No dated orders' : 'Loading…';
}

function integrationTraffic(summary, unavailable) {
  const orderRangeLabel = integrationOrderRangeLabel(summary);
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
document.documentElement.dataset.theme = 'light';
try { localStorage.setItem('delivery-desk-theme', 'light'); } catch {}

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
let guidanceMethodIndex = 0;
const GUIDANCE_METHOD_LABELS = ['Van', 'Palletways', 'Amazon', 'XDP', 'Stopstart'];
const GUIDANCE_RETIRED_XDP_STATUSES = new Set(['IRISH MANIFEST', 'MISROUTE', 'EXCEPTION', 'EDIT']);

function selectGuidanceMethod(index, instant = false) {
  const track = document.querySelector('.guidance-method-slides');
  if (!track) return;
  const slides = [...track.querySelectorAll('.guidance-method-slide')];
  guidanceMethodIndex = Math.max(0, Math.min(slides.length - 1, index));
  track.scrollTo({left: guidanceMethodIndex * track.clientWidth,
    behavior: instant || window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
  updateGuidanceMethodNavigation();
}

function updateGuidanceMethodNavigation() {
  const nav = document.querySelector('.guidance-method-navigation');
  if (!nav) return;
  const labels = GUIDANCE_METHOD_LABELS;
  nav.querySelector('[data-guidance-method-prev]').disabled = guidanceMethodIndex === 0;
  nav.querySelector('[data-guidance-method-next]').disabled = guidanceMethodIndex === labels.length - 1;
  nav.querySelector('[data-guidance-method-current]').textContent = `${labels[guidanceMethodIndex]} ${guidanceMethodIndex + 1} / ${labels.length}`;
  nav.querySelectorAll('[data-guidance-method-index]').forEach(button => {
    button.setAttribute('aria-pressed', String(Number(button.dataset.guidanceMethodIndex) === guidanceMethodIndex));
  });
}

function guidanceMethodSlides(summary) {
  const ready = Array.isArray(summary?.filterFacets);
  const facets = (summary?.filterFacets || []).filter(item => !item.creditRefund &&
    SELF_DELIVERY_CARRIERS.includes(item.carrier) &&
    TrackingVisibility.includesOrderType(item.orderType) &&
    TrackingVisibility.includesStore(item.purchaseStore));
  const rows = new Map();
  facets.forEach(item => {
    const key = JSON.stringify([item.carrier, item.classification || '']);
    const row = rows.get(key) || {carrier: item.carrier, method: item.classification || '', count: 0};
    row.count += item.count;
    rows.set(key, row);
  });
  const methods = [...rows.values()].sort((a,b) => a.carrier.localeCompare(b.carrier) || a.method.localeCompare(b.method));
  const total = carrier => facets.filter(item => item.carrier === carrier).reduce((sum,item) => sum + item.count, 0);
  const number = count => ready ? count.toLocaleString() : '\u2014';
  const vanStatuses = [
    ['Failed', 'Routine Dashboard - Live: yellow #FFFF00', 'Own van priority. Applies to a matched order in the live section.'],
    ['Scheduled', 'Routine Dashboard - Live: white #FFFFFF or amber #FFC000', 'Own van priority. The cell must contain an order number.'],
    ['Unscheduled', 'OptimoRoute: unscheduled', 'Used when no applicable Routine live override exists.'],
    ['Out for Delivery', 'OptimoRoute: scheduled, on_route, servicing', 'OptimoRoute supplies the shipment progress.'],
    ['Delivered', 'OptimoRoute: success', 'Successful delivery recorded by OptimoRoute.'],
    ['Failed / Rejected / Return', 'OptimoRoute: failed / rejected / returned', 'Each source value maps to the corresponding app status.'],
    ['OW fallback', 'Sales Activity column J: Status', 'Used when there is no applicable live override or mapped OptimoRoute status. Invoice waiting to be printed maps to Unscheduled.'],
  ];
  const palletFacets = (summary?.filterFacets || []).filter(item => item.carrier === 'Palletways' &&
    !item.creditRefund && TrackingVisibility.includesOrderType(item.orderType) &&
    TrackingVisibility.includesStore(item.purchaseStore) &&
    TrackingVisibility.includesPalletwaysClassification(item.carrier, item.palletwaysClassification));
  const palletMethods = new Map();
  palletFacets.forEach(item => palletMethods.set(item.classification || '',
    (palletMethods.get(item.classification || '') || 0) + item.count));
  const palletTotal = palletFacets.reduce((sum,item) => sum + item.count, 0);
  const palletStatuses = [
    ['Unscheduled', 'Palletways tab column F: Palletways Not Assigned or Unscheduled', 'Palletways Not Assigned is displayed as Unscheduled.'],
    ['Consignment Created', 'Palletways tab column F', 'Consignment record created; the label alone does not confirm collection.'],
    ['Scheduled', 'Palletways tab column F', 'Display the workbook status as supplied.'],
    ['In Transit', 'Palletways tab column F', 'Shipment moving through the carrier network.'],
    ['Out for Delivery', 'Palletways tab column F', 'Shipment marked out for delivery.'],
    ['Delivered', 'Palletways tab column F', 'Display the workbook Delivered label.'],
    ['Return', 'Palletways tab column F', 'Display the workbook Return label.'],
    ['Cancelled', 'Self-defined: OW Sales Activity → Order Category = Cancelled', 'Self-defined category label based on OW Order Category; not a carrier tracking event.'],
    ['Credit/Refund (credit note)', 'Self-defined: OW Sales Activity → Order Category = Credit/Refund', 'Self-defined category label based on OW Order Category; credit/refund records are excluded from the normal Tracking delivery total.'],
    ['Palletways Look Up Failed', 'Palletways tab column F', 'Lookup problem; this does not establish the shipment’s physical status.'],
    ['Exact OW fallback', 'OW Sales Activity column J: Status', 'Only when the order is absent from the Palletways tab. Keep the exact text, for example Invoice waiting to be printed; do not rename it Unscheduled.'],
  ];
  const sourceStatusSlide = (carrier, label, field, source, defaults, exceptions, note) => {
    const carrierFacets = (summary?.filterFacets || []).filter(item => item.carrier === carrier &&
      !item.creditRefund && TrackingVisibility.includesOrderType(item.orderType) &&
      TrackingVisibility.includesStore(item.purchaseStore) && TrackingVisibility.includesCarrier(item.carrier));
    const methodCounts = new Map();
    carrierFacets.forEach(item => methodCounts.set(item.classification || '',
      (methodCounts.get(item.classification || '') || 0) + item.count));
    const count = carrierFacets.reduce((sum,item) => sum + item.count, 0);
    const statuses = [...new Set([...defaults, ...(summary?.filterFacets || [])
      .filter(item => item.carrier === carrier).map(item => item[field]).filter(Boolean)])]
      .filter(value => !exceptions.length || !['CANCELLED', 'CREDIT/REFUND'].includes(String(value).trim().toUpperCase()))
      .filter(value => carrier !== 'XDP' || !GUIDANCE_RETIRED_XDP_STATUSES.has(String(value).trim().toUpperCase()))
      .sort((a,b) => a.localeCompare(b));
    const definitions = {
      READY_FOR_RECEIVE: 'Ready to receive; retain the Amazon source label.',
      IN_TRANSIT: 'In transit through the carrier network.',
      OUT_FOR_DELIVERY: 'Marked out for delivery.',
      DELIVERED: 'Marked delivered in the source tab.',
      DELIVERY: 'Retain the XDP DELIVERY label; this alone does not establish delivery to the customer.',
      'NEXT STOP': 'Marked as the next stop.',
      SMS: 'SMS notification event.',
      EMAIL: 'Email notification event.',
      DAMAGE: 'Damage source label; the overall app category groups this as Failed.',
      DELETE: 'Delete source label; the overall app category groups this as Failed.',
      'NOT RECEIVED': 'Not received source label; the overall app category groups this as Failed.',
      LOST: 'Global Lost status; included on Failed Deliveries.',
      UNDELIVERABLE: 'Undeliverable source label; the overall app category groups this as Failed.',
      'Tracking Unavailable': 'The source tab reports tracking unavailable. This does not confirm delivery, failure or cancellation.',
      'Past Expected Date \u2014 Unconfirmed': 'The planned delivery date has passed without confirmation. This is not proof of a failed delivery.',
      'Expected Today': 'The source tab indicates an expected delivery today; this is a plan, not proof of delivery.',
    };
    const index = GUIDANCE_METHOD_LABELS.indexOf(label);
    return `<article class="guidance-method-slide" aria-label="${esc(label)} guide, slide ${index + 1} of ${GUIDANCE_METHOD_LABELS.length}">
      <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="${esc(label)} delivery method totals"><table class="guidance-table guidance-${carrier.toLowerCase()}-methods">
        <caption>${esc(label)} · Delivery methods and totals</caption><thead><tr><th scope="col">Sales Activity column T · Delivery method</th><th scope="col">App group</th><th scope="col">Records</th></tr></thead>
        <tbody>${methodCounts.size ? [...methodCounts].sort(([a],[b]) => a.localeCompare(b)).map(([method,total]) => `<tr><th scope="row">${esc(method || '(Blank delivery method)')}</th><td>${esc(label)}</td><td>${number(total)}</td></tr>`).join('') : '<tr><td colspan="3">Live delivery-method totals are not available yet.</td></tr>'}</tbody>
        <tfoot><tr><th scope="row" colspan="2">${esc(label)} total · sum of the methods above</th><td>${number(count)}</td></tr></tfoot>
      </table><p class="guidance-mapping-note">Credit/refund records are excluded from the Tracking delivery total. Store visibility switches apply. This method total counts app orders, not every historical shipment row in the carrier tab.</p></div>
      <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="${esc(label)} status sources"><table class="guidance-table guidance-${carrier.toLowerCase()}-statuses">
        <caption>${esc(label)} · Status sources and definitions</caption><thead><tr><th scope="col">Status / label</th><th scope="col">Source / condition</th><th scope="col">Definition</th></tr></thead>
        <tbody>${statuses.map(status => `<tr><th scope="row">${esc(status)}</th><td>${esc(source)}</td><td>${esc(definitions[status] || 'Use the source tab status as supplied; this is not a self-defined OW category label.')}</td></tr>`).join('')}${exceptions.map(row => `<tr class="guidance-self-defined"><th scope="row">${esc(row[0])}</th><td>${esc(row[1])}</td><td>${esc(row[2])}</td></tr>`).join('')}</tbody>
      </table><p class="guidance-mapping-note">${esc(note)}</p></div>
    </article>`;
  };
  const amazonSlide = sourceStatusSlide('AMZ', 'Amazon', 'amazonStatus', 'Amazon Shipping tab column G · Order status',
    ['READY_FOR_RECEIVE', 'IN_TRANSIT', 'OUT_FOR_DELIVERY', 'DELIVERED', 'DELIVERY_ATTEMPTED', 'UNDELIVERABLE', 'LOST', 'REJECTED', 'RETURNED', 'RETURNED_TO_SELLER', 'AWAITING_CUSTOMER_PICKUP'], [],
    'Amazon status labels come purely from the Amazon Shipping tab, column G (Order status). Join its column B (TrackingId) to the OW tracking number in Sales Activity column S. Scheduled delivery date/time comes from Amazon column M. No self-defined OW Cancelled or Credit/Refund status is added to this Amazon status table.');
  const xdpSlide = sourceStatusSlide('XDP', 'XDP', 'xdpStatus', 'XDP tab column I · Status',
    ['DELIVERED', 'DELIVERY', 'NEXT STOP', 'SMS', 'EMAIL', 'DAMAGE', 'DELETE', 'NOT RECEIVED'],
    palletStatuses.filter(row => row[1].startsWith('Self-defined:')),
    'XDP status labels come purely from the XDP tab, column I, except the two self-defined OW Order Category labels shown above. Latest status detail is XDP column J, separate from the status. XDP Activity column M supplies history, not the primary status label. Match by the order number, with tracking-number fallback.');
  const stopstartSlide = sourceStatusSlide('Stopstart', 'Stopstart', 'stopstartStatus', 'STOPSTART tab column I · Status',
    ['Tracking Unavailable', 'Past Expected Date \u2014 Unconfirmed'], [],
    'Display the STOPSTART status from column I, joined by the OW order number to STOPSTART column A. Delivery Activity in column J (legacy column H) supplies the expected date, UK delivery window, driver and reference; it is separate from the status. Column N is Fetch Result and column O is Trackability. Open tracking appears only when Trackability is Yes; No, Missing and Time Out do not show the tracking button. If the source status is blank or conflicting, there is no unique STOPSTART status to display; the current app falls back to its saved delivery category.');
  return `<section class="guidance-method-guide" aria-labelledby="guidance-method-guide-heading">
    <div class="guidance-method-guide-head"><div><h3 id="guidance-method-guide-heading">Delivery method guide</h3><p class="mut">Method totals, source fields and status priority.</p></div>
      <nav class="guidance-method-navigation" aria-label="Delivery method slides"><button type="button" data-guidance-method-prev aria-label="Previous delivery method">${ico('left',18)}</button>${GUIDANCE_METHOD_LABELS.map((label,index) => `<button type="button" data-guidance-method-index="${index}" aria-pressed="${guidanceMethodIndex === index}">${esc(label)}</button>`).join('')}<span data-guidance-method-current aria-live="polite"></span><button type="button" data-guidance-method-next aria-label="Next delivery method">${ico('right',18)}</button></nav></div>
    <div class="guidance-method-slides" tabindex="0" role="region" aria-label="Delivery method guide slides">
      <article class="guidance-method-slide" aria-label="Van guide, slide 1 of 5">
        <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="Van delivery method totals"><table class="guidance-table guidance-van-methods">
          <caption>Van \u00b7 Delivery methods and totals</caption><thead><tr><th scope="col">Sales Activity column T \u00b7 Delivery method</th><th scope="col">App group</th><th scope="col">Records</th></tr></thead>
          <tbody>${methods.length ? methods.map(row => `<tr><th scope="row">${esc(row.method || '(Blank delivery method)')}</th><td>${esc(row.carrier)}</td><td>${number(row.count)}</td></tr>`).join('') : '<tr><td colspan="3">Live delivery-method totals are not available yet.</td></tr>'}</tbody>
          <tfoot><tr><th scope="row" colspan="2">Own van (${number(total('Own van'))}) + Self Delivery (${number(total('Self Delivery'))})</th><td>${number(total('Own van') + total('Self Delivery'))}</td></tr></tfoot>
        </table><p class="guidance-mapping-note">Same Own van / Self Delivery group as Tracking. Credit/refund records are excluded; store visibility switches apply. LOCAL MULTIDROP belongs to Other Delivery Method and is excluded from this Van total.</p></div>
        <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="Van status priority"><table class="guidance-table guidance-van-statuses">
          <caption>Van \u00b7 Status sources and priority</caption><thead><tr><th scope="col">Displayed status</th><th scope="col">Source value</th><th scope="col">Rule</th></tr></thead>
          <tbody>${vanStatuses.map(row => `<tr><th scope="row">${esc(row[0])}</th><td>${esc(row[1])}</td><td>${esc(row[2])}</td></tr>`).join('')}</tbody>
        </table><p class="guidance-mapping-note">Routine live colour overrides apply to Own van only. Self Delivery uses OptimoRoute, then OW fallback. Booking text comes from Routine Dashboard - Live column E, joined by the order number in column A; booking text is separate from delivery status.</p></div>
      </article>
      <article class="guidance-method-slide" aria-label="Palletways guide, slide 2 of 5">
        <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="Palletways delivery method totals"><table class="guidance-table guidance-palletways-methods">
          <caption>Palletways · Delivery methods and totals</caption><thead><tr><th scope="col">Sales Activity column T · Delivery method</th><th scope="col">App group</th><th scope="col">Records</th></tr></thead>
          <tbody>${palletMethods.size ? [...palletMethods].sort(([a],[b]) => a.localeCompare(b)).map(([method,count]) => `<tr><th scope="row">${esc(method || '(Blank delivery method)')}</th><td>Palletways</td><td>${number(count)}</td></tr>`).join('') : '<tr><td colspan="3">Live delivery-method totals are not available yet.</td></tr>'}</tbody>
          <tfoot><tr><th scope="row" colspan="2">Palletways total · sum of the methods above</th><td>${number(palletTotal)}</td></tr></tfoot>
        </table><p class="guidance-mapping-note">Credit/refund records are excluded. Store and Palletways B2B visibility switches apply. The app groups OW methods containing Palletways, plus Next Day (Pallet), under Palletways; this does not establish membership in the Palletways tab.</p></div>
        <div class="guidance-table-scroll" role="region" tabindex="0" aria-label="Palletways status sources"><table class="guidance-table guidance-palletways-statuses">
          <caption>Palletways · Status sources and definitions</caption><thead><tr><th scope="col">Status / label</th><th scope="col">Source / condition</th><th scope="col">Definition</th></tr></thead>
          <tbody>${palletStatuses.map(row => `<tr${row[1].startsWith('Self-defined:') ? ' class="guidance-self-defined"' : ''}><th scope="row">${esc(row[0])}</th><td>${esc(row[1])}</td><td>${esc(row[2])}</td></tr>`).join('')}</tbody>
        </table><p class="guidance-mapping-note">Match OW order number to Palletways column A (Customer Ref). For matched orders, display column F; a blank F cell remains blank. Booked In uses Z, Book In Request uses AA, and booking date/time use BT/BU. These booking fields are separate from the status.</p></div>
      </article>
      ${amazonSlide}${xdpSlide}${stopstartSlide}
    </div>
  </section>`;
}

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
    ['Next Stop', [['XDP tab · I', ['NEXT STOP']]]],
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
  const mappingCouriers = ['Own van', 'Amazon Shipping', 'Palletways', 'XDP'];
  const referenceStatuses = {
    XDP: [...new Set(['Awaiting', 'BOOKING', 'CREATE', 'DAMAGE', 'DELETE', 'DELIVERED', 'DELIVERY', 'EMAIL', 'OUT FOR DELIVERY', 'NEXT STOP', 'NOT RECEIVED', 'SMS', ...sourceValues('xdpStatus')])]
      .filter(value => !GUIDANCE_RETIRED_XDP_STATUSES.has(value.trim().toUpperCase())),
    Stopstart: [...new Set(['Past Expected Date \u2014 Unconfirmed', 'Tracking Unavailable', ...sourceValues('stopstartStatus')])],
  };
  const referenceStatusGroup = value => ({
    DELIVERED: 'Delivered', DELIVERY: 'Scheduled', 'NEXT STOP': 'Next Stop',
    SCHEDULED: 'Scheduled', UNSCHEDULED: 'Unscheduled', BOOKING: 'Unscheduled', 'OUT FOR DELIVERY': 'Out for Delivery',
    FAILED: 'Failed', REJECTED: 'Rejected', LOST: 'Lost', CANCELLED: 'Cancelled',
    RETURN: 'Return', UNASSIGNED: 'Unassigned',
  }[value.trim().toUpperCase()] || 'Other Status');
  const palletwaysOverallMapping = {
    Unscheduled: ['Palletways Not Assigned', 'Unscheduled', 'Consignment Created'],
    Scheduled: ['Scheduled', 'In Transit'],
    'Out for Delivery': ['Out for Delivery'],
    Delivered: ['Delivered'],
    Return: ['Return'],
    Unassigned: ['Palletways Look Up Failed'],
  };
  const amazonOverallMapping = {
    'Other Status': ['AWAITING_CUSTOMER_PICKUP', 'PICKUP_CANCELLED', 'CARRIER_CANCELLED_PICKUP'],
    Scheduled: ['READY_FOR_RECEIVE', 'IN_TRANSIT'],
    'Out for Delivery': ['OUT_FOR_DELIVERY'],
    Delivered: ['DELIVERED'],
    Failed: ['DELIVERY_ATTEMPTED', 'UNDELIVERABLE'],
    Rejected: ['REJECTED'],
    Lost: ['LOST'],
    Cancelled: ['RETURNED_TO_SELLER'],
    Return: ['RETURNED'],
  };
  const carrierMappingCell = (status, mappings, courier) => {
    if (status === 'All statuses') return 'All values';
    if (status === 'Next Stop' && courier !== 'XDP') return '\u2014';
    if (courier === 'XDP' && ['Cancelled', 'Return', 'Unassigned'].includes(status)) {
      const [source, value] = {
        Cancelled: ['Self-defined · OW Order Category', 'Cancelled'],
        Return: ['OW Status (J) · fallback', 'RETURN'],
        Unassigned: ['OW Delivery method (T)', 'On hold - TBC'],
      }[status];
      return `<ul class="guidance-source-values"><li><strong>${esc(source)}</strong><div>${esc(value)}</div></li></ul>`;
    }
    if (courier === 'Amazon Shipping' && Object.prototype.hasOwnProperty.call(amazonOverallMapping, status))
      return `<ul class="guidance-source-values"><li><strong>Amazon Shipping tab · G</strong><div>${amazonOverallMapping[status].map(esc).join(' &amp; ')}</div></li></ul>`;
    if (courier === 'Palletways' && status === 'Cancelled')
      return '<ul class="guidance-source-values"><li><strong>Self-defined · OW Order Category</strong><div>Cancelled</div></li></ul>';
    if (courier === 'Palletways' && Object.prototype.hasOwnProperty.call(palletwaysOverallMapping, status)) {
      const sources = [['Palletways tab · F', palletwaysOverallMapping[status]]];
      if (status === 'Unassigned') sources.push(['OW Delivery method (T)', ['On hold - TBC']]);
      else sources.push(...mappings.filter(([source]) => source.startsWith('OW Status (J)') && source.includes('fallback')));
      return `<ul class="guidance-source-values">${sources.map(([source, values]) =>
        `<li><strong>${esc(source)}</strong><div>${values.map(esc).join(' &amp; ')}</div></li>`).join('')}</ul>`;
    }
    if (referenceStatuses[courier]) {
      const values = referenceStatuses[courier].filter(value => {
        if (courier === 'XDP' && ['DAMAGE', 'DELETE', 'NOT RECEIVED'].includes(value.trim().toUpperCase())) return status === 'Failed';
        return referenceStatusGroup(value) === status;
      });
      if (courier === 'XDP') {
        const sheetValues = values.filter(value => value.trim().toUpperCase() !== 'AWAITING');
        const sources = [];
        if (sheetValues.length) sources.push(`<li><strong>XDP tab column I · Status</strong><div>${sheetValues.map(esc).join(' &amp; ')}</div></li>`);
        if (sheetValues.length !== values.length) sources.push('<li><strong>XDP fallback · saved category</strong><div>Awaiting → Other Status</div></li>');
        return sources.length ? `<ul class="guidance-source-values">${sources.join('')}</ul>` : '\u2014';
      }
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
    <p class="guidance-mapping-note">This table defines the global status filter when All methods is selected in Tracking. Each courier keeps its specific status filter. Failed Deliveries includes global Failed, Rejected and Lost records. Saved source categories remain unchanged.</p>
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
      ['Failed', 'Routine Dashboard - Live, mapped carrier status or OW fallback', "Own van: #FFFF00; Amazon: DELIVERY_ATTEMPTED & UNDELIVERABLE; XDP: DAMAGE & DELETE & NOT RECEIVED; Palletways: existing Failed / Damaged mapping"],
      ['Rejected', 'Mapped carrier status or OW fallback', "Rejected & rejected & Refused"],
      ['Lost', 'Amazon Shipping column G / existing Palletways mapping', 'Amazon LOST is grouped under Lost; Lost records are included on Failed Deliveries'],
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
      ['Page inclusion', 'Global status mapping', 'Current global Failed, Rejected and Lost deliveries; credit/refund records are excluded. Original carrier labels can differ from the global group'],
      ['Amazon Shipping failures', 'Amazon Shipping column G; matched from Sales Activity tracking number (S) to Amazon Shipping tracking ID (B)', ['DELIVERY_ATTEMPTED / UNDELIVERABLE: Failed', 'REJECTED: Rejected', 'LOST: Lost', 'All appear on Failed Deliveries with their source labels']],
      ['XDP failures', 'XDP · I', ['DAMAGE → Failed', 'DELETE → Failed', 'NOT RECEIVED → Failed', 'Original labels remain visible in red']],
      ['Own van failures', 'Routine Dashboard - Live · column A fill; otherwise OptimoRoute / OW fallback', '#FFFF00 overrides the usual status; text in booking status alone does not mark the delivery Failed'],
      ['Rejected deliveries', 'OptimoRoute / Palletways API / OW fallback', 'rejected / Refused / REJECTED also appear on Failed Deliveries'],
      ['Dynamic changes', 'Successful source refresh', 'An order appears while its global status is Failed, Rejected or Lost, and leaves when the global status changes outside those three groups'],
      ['Store icons and copy buttons', 'Same store mapping and sidebar as Tracking', 'Store icon in the customer cell; unmapped icon stays blank. Order No and Order Ref have copy buttons'],
      ['Activity timeline', 'Shared Tracking and Failed Deliveries sidebar', 'Saved status and booking updates are shown; sheet colour codes and cell references are hidden. Own van failures use red pulse dots and delivered events use green dots'],
    ]],
    ['Failed Deliveries · Filter levels', [
      ['Level 1 · General scope', 'Same general scopes as Tracking', 'General scope narrows available delivery methods; all levels respect Hide data settings'],
      ['Level 2 · Delivery method', 'Global Failed / Rejected / Lost records within the selected general scope', 'Only methods with matching records appear; Own van and Self Delivery share their method button'],
      ['Level 3 · Store', 'Stores present within the selected scope and delivery method', 'Stores with no matching failed records are omitted. Changing stores resets the status selection'],
      ['Level 3 - Status', 'Global groups for All methods; source statuses for a selected courier', 'All methods offers Failed, Rejected and Lost. A selected courier retains its matching source labels and counts'],
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
      'Save note stores it in Collection Notes. Click a saved row to reopen it; the X deletes a saved note after confirmation.',
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
  queueMicrotask(() => {
    selectGuidanceMethod(guidanceMethodIndex, true);
    applyGuidanceSearch();
  });
  return `<div class="workflow-intro guidance-intro"><div><span class="guidance-eyebrow">ATLAS WORKSPACE</span><h1>Guidance</h1><p>Your guide to orders, widgets, notes and manufacturing claims.</p></div>
      <form class="guidance-search${guidanceSearchOpen ? ' is-open' : ''}" role="search" aria-label="Search guidance"><button type="button" class="guidance-search-toggle" data-guidance-search-toggle aria-label="Search guidance" aria-expanded="${guidanceSearchOpen}" aria-controls="guidance-search-field">${ico('search', 21)}</button><div id="guidance-search-field" class="guidance-search-field"><input type="search" data-guidance-search placeholder="Search all guidance…" aria-label="Search all guidance" autocomplete="off" value="${esc(guidanceSearchTerm)}" ${guidanceSearchOpen ? '' : 'disabled'}><button type="button" data-guidance-search-close aria-label="Clear and close guidance search" ${guidanceSearchOpen ? '' : 'disabled'}>${ico('x', 17)}</button></div></form></div>
    <p class="guidance-search-status" data-guidance-search-status role="status" aria-live="polite" hidden></p>
    <div class="guidance-content" data-guidance-content>
    <section class="guidance-workflows-section" aria-labelledby="guidance-workflows-heading"><h2 id="guidance-workflows-heading">Using Atlas</h2><div class="guidance-workflows">${workflows.map(([title, icon, instructions]) => `<article class="guidance-workflow"><h3><span>${ico(icon, 20)}</span>${esc(title)}</h3><ul>${instructions.map(instruction => `<li>${esc(instruction)}</li>`).join('')}</ul></article>`).join('')}</div></section>
    <section class="card guidance-reference" aria-labelledby="guidance-filters-heading">
      <h2 id="guidance-filters-heading">Filter values &amp; data sources</h2>
      <p class="mut">OW means OrderWise Sales Activity. Column letters refer to the named source tab. Carrier buttons group the OW delivery method; the displayed status can come from a different source.</p>
      ${groups.map(([group, rows]) => `${group === 'Tracking · Status with All methods selected' ? guidanceMethodSlides(summary) + overallStatusTable : ''}<div class="guidance-table-scroll" role="region" aria-label="${esc(group)}" tabindex="0">
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
  const methodSlides = [...reference.querySelectorAll('.guidance-method-slide')];
  const slideMatches = slide => [...slide.querySelectorAll('.guidance-table-scroll')].some(table => !table.hidden);
  if (words.length && !slideMatches(methodSlides[guidanceMethodIndex])) {
    const index = methodSlides.findIndex(slideMatches);
    if (index >= 0) selectGuidanceMethod(index, true);
  }
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
  if (event.target.closest('[data-guidance-method-prev]')) selectGuidanceMethod(guidanceMethodIndex - 1);
  if (event.target.closest('[data-guidance-method-next]')) selectGuidanceMethod(guidanceMethodIndex + 1);
  const methodTab = event.target.closest('[data-guidance-method-index]');
  if (methodTab) selectGuidanceMethod(Number(methodTab.dataset.guidanceMethodIndex));
  if (event.target.closest('[data-guidance-search-toggle]')) toggleGuidanceSearch(!guidanceSearchOpen);
  if (event.target.closest('[data-guidance-search-close]')) toggleGuidanceSearch(false);
});
document.addEventListener('scrollend', event => {
  const track = event.target;
  if (!track.matches?.('.guidance-method-slides') || !track.clientWidth) return;
  guidanceMethodIndex = Math.round(track.scrollLeft / track.clientWidth);
  updateGuidanceMethodNavigation();
}, true);
window.addEventListener('resize', () => {
  if (page === 'Guidance') selectGuidanceMethod(guidanceMethodIndex, true);
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
});

document.addEventListener('pointerover', event => {
  const button = event.target.closest('.collection-record-download');
  if (!button || button.contains(event.relatedTarget)) return;
  const bounds = button.getBoundingClientRect();
  button.style.setProperty('--download-x', ((event.clientX - bounds.left) / bounds.width * 100) + '%');
  button.style.setProperty('--download-y', ((event.clientY - bounds.top) / bounds.height * 100) + '%');
});

document.addEventListener('click', event => {
  if (!event.target.closest('[data-collection-sort-created]')) return;
  collectionCreatedSort = collectionCreatedSort === 'desc' ? 'asc' : 'desc';
  renderCollectionRecords();
  const header = document.querySelector('[data-collection-created-header]');
  header?.setAttribute('aria-sort', collectionCreatedSort === 'asc' ? 'ascending' : 'descending');
  const indicator = header?.querySelector('.table-date-sort-indicator');
  if (indicator) indicator.innerHTML = dateSortIcon(collectionCreatedSort);
});
