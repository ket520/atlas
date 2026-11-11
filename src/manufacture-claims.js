const ManufactureClaims = (() => {
  const reasons = ['Scratches', 'Broken parts', 'Leaking', 'Missing parts', 'Others'];
  const solutions = ['Replacement', 'Refund', 'Others'];
  let records = [], loading = false, loadError = '', request = 0, exporting = false;
  let attachments = [], search = '', dateFrom = '', dateTo = '', editingId = null, editingOpener = null;
  let bulkSelect = false, solutionFilter = '';
  let orderDateSort = ''; 
  const selectedClaims = new Set();
  const deleting = new Set();
  const uploading = new Set();
  let lookupTimer = null, lookupController = null, lookupVersion = 0, autoValues = {};
  const fieldHighlights = new WeakMap();
  function flashAutofill(input) {
    fieldHighlights.get(input)?.cancel();
    const background = getComputedStyle(input).backgroundColor;
    fieldHighlights.set(input, input.animate([
      {backgroundColor: '#fde047', offset: 0},
      {backgroundColor: '#fde047', offset: .2},
      {backgroundColor: background, offset: 1},
    ], {duration: matchMedia('(prefers-reduced-motion: reduce)').matches ? 250 : 1400, easing: 'ease-out'}));
  }
  function cancelLookup() { clearTimeout(lookupTimer); lookupController?.abort(); lookupVersion++; }
  const filteredRecords = () => sortDeliveriesByDate(exactOrderMatches(records, search, ['originalOrderNo', 'replacementOrderNo']).filter(item =>
    (!search.trim() || [item.originalOrderNo, item.replacementOrderNo].some(value => String(value || '').toLowerCase().includes(search.trim().toLowerCase())))
    && (!dateFrom || item.orderDate >= dateFrom) && (!dateTo || item.orderDate <= dateTo)
    && (!solutionFilter || (solutionFilter === 'Others' ? Boolean(item.solution) && !['Replacement', 'Refund'].includes(item.solution) : item.solution === solutionFilter))), orderDateSort, item => item.orderDate);
  document.addEventListener('click', event => {
    if (!event.target.closest('[data-mc-sort-order-date]')) return;
    orderDateSort = orderDateSort === 'desc' ? 'asc' : 'desc';
    paint();
    const header = document.querySelector('[data-mc-order-date-header]');
    header?.setAttribute('aria-sort', orderDateSort === 'asc' ? 'ascending' : 'descending');
    const indicator = header?.querySelector('.table-date-sort-indicator');
    if (indicator) indicator.innerHTML = dateSortIcon(orderDateSort);
  });
  function dateLabel() {
    const display = value => value.split('-').reverse().join('/');
    return dateFrom && dateTo ? `${display(dateFrom)} – ${display(dateTo)}`
      : dateFrom ? `From ${display(dateFrom)}` : dateTo ? `Until ${display(dateTo)}` : 'Order date';
  }
  function solutionFilterControl() {
    return UiSelect.render('mc-solution-filter', solutionFilter, [['', 'All solutions'], ...solutions.map(value => [value, value])], {
      className: 'mc-solution-select', ariaLabel: 'Filter claims by solution',
      onChange: value => { solutionFilter = value; paint(); },
    });
  }
  function dateFilter() {
    return `<div class="ui-select mc-date-select"><button type="button" class="ui-select-trigger" data-mc-toggle-date aria-label="Filter claims by order date" aria-expanded="false" aria-controls="mc-date-menu" aria-haspopup="dialog"><span class="ui-select-label">${esc(dateLabel())}</span><span class="ui-select-chevron">${ico('chevdown', 16, 2)}</span></button><div id="mc-date-menu" class="ui-select-menu ui-date-menu mc-date-menu" popover="auto" role="dialog" aria-label="Claim order date range"><div class="delivery-date-fields"><label><span>From</span><input type="date" aria-label="Claim date from" data-mc-date="from" value="${esc(dateFrom)}" max="${esc(dateTo)}"></label><label><span>To</span><input type="date" aria-label="Claim date to" data-mc-date="to" value="${esc(dateTo)}" min="${esc(dateFrom)}"></label></div><button type="button" class="delivery-date-clear" data-mc-clear-dates>Clear dates</button></div></div>`;
  }
  const maxPicture = 5 * 1024 * 1024, maxTotal = 15 * 1024 * 1024;
  const options = choices => choices.map(value => `<option value="${esc(value)}">${esc(value)}</option>`).join('');

  function photoPreviews(item) {
    const photos = item.photos || [];
    return photos.slice(0, 3).map((photo, index) => {
      const extra = index === 2 && photos.length > 3 ? photos.length - 2 : 0;
      return `<button type="button" data-mc-view-photos="${esc(item.id)}" data-mc-photo-index="${index}" title="${esc(extra ? `View ${extra} more pictures` : photo.name)}" aria-label="${esc(extra ? `View ${extra} more pictures` : `Open picture ${photo.name}`)}"><img src="${esc(photo.url)}" alt="${esc(photo.name)}" loading="lazy">${extra ? `<span class="mc-photo-overflow" aria-hidden="true">+${extra}</span>` : ''}</button>`;
    }).join('') || '—';
  }

  function rows() {
    if (loading && !records.length) return `<tr><td colspan="${bulkSelect ? 10 : 9}" class="mc-empty">Loading claims…</td></tr>`;
    if (!filteredRecords().length) return `<tr><td colspan="${bulkSelect ? 10 : 9}" class="mc-empty">${loadError ? 'Claims could not be loaded.' : search || dateFrom || dateTo || solutionFilter ? 'No claims match the selected search or dates.' : 'No claims yet. Select New claim to add one.'}</td></tr>`;
    return filteredRecords().map(claimRow).join('');
  }

  function claimRow(item) {
    return `<tr data-mc-edit="${esc(item.id)}" tabindex="0" aria-label="Edit claim for order ${esc(item.originalOrderNo)}">
      ${bulkSelect ? `<td class="mc-selection-cell"><input type="checkbox" data-mc-select="${esc(item.id)}" aria-label="Select claim for order ${esc(item.originalOrderNo)}" ${selectedClaims.has(item.id) ? 'checked' : ''}></td>` : ''}<td>${esc(hd(item.orderDate))}</td><td><span class="tracking-order-number"><strong>${esc(item.originalOrderNo)}</strong>${item.originalOrderNo ? `<button type="button" class="qd-customer-copy" data-copy-order-number="${esc(item.originalOrderNo)}" aria-label="Copy original order number ${esc(item.originalOrderNo)}" title="Copy original order number">${ico('copy', 13, 1.8)}</button>` : ''}</span></td>
      <td><span class="tracking-order-number">${esc(item.replacementOrderNo || '—')}${item.replacementOrderNo ? `<button type="button" class="qd-customer-copy" data-copy-order-number="${esc(item.replacementOrderNo)}" aria-label="Copy replacement order number ${esc(item.replacementOrderNo)}" title="Copy replacement order number">${ico('copy', 13, 1.8)}</button>` : ''}</span></td><td>${esc(item.variantCode)}</td>
      <td>${esc(item.reason)}</td><td><span class="mc-solution">${esc(item.solution)}</span></td>
      <td>${esc(item.sellingShop)}</td><td><div class="mc-picture-cell"><div class="mc-row-photos">${photoPreviews(item)}</div><button type="button" class="mc-add-image" data-mc-add-image="${esc(item.id)}" aria-label="Add image to claim for order ${esc(item.originalOrderNo)}" title="${(item.photos || []).length >= 5 ? 'Maximum 5 pictures per claim' : 'Add pictures to this claim'}" ${uploading.has(item.id) || deleting.has(item.id) || (item.photos || []).length >= 5 ? 'disabled' : ''}>${ico('plus', 18)}<span>${uploading.has(item.id) ? 'Adding…' : 'Add image'}</span></button></div></td>
      <td class="mc-delete-cell"><button type="button" class="collection-delete-note" data-mc-delete="${esc(item.id)}" aria-label="Delete claim for order ${esc(item.originalOrderNo)}" title="Delete claim" ${deleting.has(item.id) ? 'disabled' : ''}><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/></svg></button></td>
    </tr>`;
  }

  function render() {
    return `<section id="manufacture-claims-root" class="mc-page" aria-label="Manufacturing claims">
      <div class="delivery-page-head"><div><h1 class="fx-title">Manufacturing Claims</h1><p class="mc-subtitle">Record product issues, resolutions and supporting pictures.</p></div></div>
      <div class="mc-records-toolbar"><label class="delivery-search">${ico('search', 18)}<input type="search" data-mc-search placeholder="Search original or replacement order no" aria-label="Search claims by original or replacement order number" value="${esc(search)}"></label><div class="mc-actions">${dateFilter()}${solutionFilterControl()}<button type="button" class="mc-secondary" data-mc-download="xlsx">${ico('download', 15)}XLSX</button><button type="button" class="mc-secondary" data-mc-download="pdf">${ico('download', 15)}PDF</button><button type="button" class="mc-secondary" data-mc-print>${ico('print', 15)}Print</button><button type="button" class="mc-secondary" data-mc-refresh>Refresh</button><button type="button" class="mc-primary" data-mc-new>${ico('plus', 16)}New claim</button></div></div>
      <p class="mc-list-status" data-mc-error role="alert" ${loadError ? '' : 'hidden'}>${esc(loadError)}</p>
      <input type="file" data-mc-add-files accept="image/jpeg,image/png,image/webp,image/gif" multiple hidden>
      <div class="mc-table-wrap" role="region" aria-label="Manufacturing claims table" tabindex="0"><table class="mc-table">
        <thead><tr><th data-mc-order-date-header aria-sort="${orderDateSort === 'asc' ? 'ascending' : orderDateSort === 'desc' ? 'descending' : 'none'}"><button type="button" class="table-date-sort" data-mc-sort-order-date aria-label="Sort claim order date">Order date <span class="table-date-sort-indicator" aria-hidden="true">${dateSortIcon(orderDateSort)}</span></button></th><th>Order No</th><th>Replacement Order No</th><th>SKU</th><th>Reason</th><th>Solution<br><small>Replacement / Refund</small></th><th>Channel</th><th>Pictures</th><th class="mc-delete-cell" aria-label="Actions"><button type="button" class="collection-bulk-edit-trigger mc-bulk-select-trigger" data-mc-bulk-select aria-label="Bulk select claims" title="Bulk select claims" aria-expanded="${bulkSelect}">${ico('pencil', 16)}</button></th></tr></thead>
        <tbody data-mc-rows>${rows()}</tbody></table></div>
      <div class="collection-bulk-toolbar mc-bulk-toolbar" data-mc-bulk-toolbar popover="manual" hidden><span data-mc-selected-count role="status" aria-live="polite">0 selected</span><div class="collection-bulk-file-actions"><button type="button" data-mc-bulk-download="pdf">${ico('download', 14)} PDF</button><button type="button" data-mc-bulk-download="xlsx">${ico('download', 14)} XLSX</button><button type="button" data-mc-bulk-print>${ico('print', 14)} Print</button></div><button type="button" class="mc-bulk-done" data-mc-bulk-done>Done</button></div>
      <p class="mc-count" data-mc-count>${filteredRecords().length} ${filteredRecords().length === 1 ? 'claim' : 'claims'}</p>
      <dialog class="mc-dialog" aria-labelledby="mc-form-title"><form id="mc-form">
        <header><div><p class="mc-eyebrow">MANUFACTURING CLAIMS</p><h2 id="mc-form-title">New claim</h2></div><button type="button" class="mc-close" data-mc-close aria-label="Close claim form">${ico('x', 20)}</button></header>
        <fieldset class="mc-fields">
          <label>Order No<input name="originalOrderNo" required maxlength="200" autocomplete="off"></label>
          <label>Replacement Order No<input name="replacementOrderNo" required maxlength="200" autocomplete="off" list="mc-replacement-options"><datalist id="mc-replacement-options"></datalist></label>
          <label>Order date<input type="date" name="orderDate" required value="${localDateKey()}"></label>
          <label>Channel<select name="sellingShop" required><option value="">Choose a channel</option>${options(PURCHASE_STORES)}</select></label>
          <label class="mc-full">SKU<input name="variantCode" required maxlength="200" autocomplete="off"></label>
          <p class="mc-full mc-lookup-status" data-mc-lookup-status role="status" aria-live="polite"></p>
          <label>Reason<select name="reason" required><option value="">Choose a reason</option>${options(reasons)}</select></label>
          <label>Solution<select name="solution" required><option value="">Choose a solution</option>${options(solutions)}</select></label>
          <label data-mc-other="reason" hidden>Other reason<input name="reasonOther" maxlength="2000" disabled placeholder="Describe the reason"></label>
          <label data-mc-other="solution" hidden>Other solution<input name="solutionOther" maxlength="2000" disabled placeholder="Describe the solution"></label>
          <div class="mc-full mc-upload"><label for="mc-pictures">Supporting pictures <small>Optional</small></label>
            <p>Drag pictures here or choose files. Up to 5 pictures · JPG, PNG, WebP or GIF · 5 MB each, 15 MB total.</p>
            <input id="mc-pictures" type="file" accept="image/jpeg,image/png,image/webp,image/gif" multiple>
            <div class="mc-photo-previews" data-mc-previews aria-label="Selected pictures"></div></div>
        </fieldset>
        <p class="mc-form-status" role="alert" data-mc-form-status></p>
        <footer><button type="button" class="mc-form-delete" data-mc-form-delete hidden><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/></svg>Delete claim</button><button type="button" class="mc-secondary" data-mc-close>Cancel</button><button type="submit" class="mc-primary" data-mc-save>Save claim</button></footer>
      </form></dialog>
    </section>`;
  }

  function paint() {
    const root = document.getElementById('manufacture-claims-root');
    if (!root) return;
    root.querySelector('[data-mc-rows]').innerHTML = rows();
    root.querySelector('[data-mc-toggle-date] .ui-select-label').textContent = dateLabel();
    root.querySelector('[data-mc-count]').textContent = `${filteredRecords().length} ${filteredRecords().length === 1 ? 'claim' : 'claims'}`;
    const error = root.querySelector('[data-mc-error]');
    error.hidden = !loadError; error.textContent = loadError;
    syncBulkSelection(root);
  }

  function syncBulkSelection(root = document.getElementById('manufacture-claims-root')) {
    if (!root) return;
    const table = root.querySelector('.mc-table');
    table.classList.toggle('is-bulk-select', bulkSelect);
    const headerRow = table.querySelector('thead tr');
    if (bulkSelect && !headerRow.querySelector('.mc-selection-cell')) {
      const header = document.createElement('th');
      header.className = 'mc-selection-cell';
      header.innerHTML = '<input type="checkbox" data-mc-select-all aria-label="Select all visible claims">';
      headerRow.prepend(header);
    }
    if (!bulkSelect) headerRow.querySelector('.mc-selection-cell')?.remove();
    const visible = filteredRecords();
    const checked = visible.filter(item => selectedClaims.has(item.id)).length;
    const all = root.querySelector('[data-mc-select-all]');
    if (all) { all.checked = visible.length > 0 && checked === visible.length; all.indeterminate = checked > 0 && checked < visible.length; all.disabled = loading || exporting || !visible.length; }
    root.querySelectorAll('[data-mc-select]').forEach(input => { input.checked = selectedClaims.has(input.dataset.mcSelect); input.disabled = exporting; });
    root.querySelectorAll('[data-mc-edit]').forEach(row => {
      if (bulkSelect) row.setAttribute('aria-selected', String(selectedClaims.has(row.dataset.mcEdit)));
      else row.removeAttribute('aria-selected');
    });
    const trigger = root.querySelector('[data-mc-bulk-select]');
    trigger.hidden = bulkSelect;
    trigger.setAttribute('aria-expanded', String(bulkSelect));
    trigger.disabled = exporting;
    const toolbar = root.querySelector('[data-mc-bulk-toolbar]');
    toolbar.hidden = !bulkSelect;
    if (bulkSelect && !toolbar.matches(':popover-open')) toolbar.showPopover();
    if (!bulkSelect && toolbar.matches(':popover-open')) toolbar.hidePopover();
    toolbar.querySelector('[data-mc-selected-count]').textContent = selectedClaims.size + ' selected';
    toolbar.querySelector('[data-mc-bulk-done]').disabled = exporting;
    root.querySelectorAll('[data-mc-download], [data-mc-bulk-download], [data-mc-bulk-print], [data-mc-print]').forEach(button => { button.disabled = loading || Boolean(loadError) || exporting || (bulkSelect && !selectedClaims.size) || (button.hasAttribute('data-mc-print') && !visible.length); });
  }
  function toggleClaimSelection(row) {
    const id = row.dataset.mcEdit;
    if (exporting) return;
    if (selectedClaims.has(id)) selectedClaims.delete(id); else selectedClaims.add(id);
    syncBulkSelection();
  }

  async function responseJson(response) {
    if ([404, 405].includes(response.status)) throw new Error('Restart Atlas to enable manufacturing claims, then refresh this page.');
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Could not save the claim. Please try again.');
    return result;
  }

  async function load() {
    if (loading) return;
    const id = ++request;
    loading = true; loadError = ''; paint();
    try {
      const result = await responseJson(await fetch('/api/manufacture-claims'));
      if (request === id) { records = result.records || []; const ids = new Set(records.map(item => item.id)); selectedClaims.forEach(id => { if (!ids.has(id)) selectedClaims.delete(id); }); }
    } catch (error) { if (request === id) loadError = error.message || 'Could not load claims. Please try again.'; }
    finally { loading = false; paint(); }
  }

  async function printSelectedClaims(selectedOnly = true) {
    if (loading || loadError || exporting || (selectedOnly && !selectedClaims.size)) return;
    const root = document.getElementById('manufacture-claims-root');
    if (!root) return;
    const selected = selectedOnly ? records.filter(record => selectedClaims.has(record.id)) : filteredRecords();
    if (!selected.length) return;
    const dates = selected.map(record => String(record.orderDate || '').slice(0, 10)).filter(date => /^\d{4}-\d{2}-\d{2}$/.test(date)).sort();
    const dateRange = dates.length ? esc(hd(dates[0])) + (dates[0] === dates[dates.length - 1] ? '' : ' &ndash; ' + esc(hd(dates[dates.length - 1]))) : 'Not specified';
    const table = document.createElement('table');
    const head = root.querySelector('.mc-table thead').cloneNode(true);
    head.querySelectorAll('.mc-selection-cell, .mc-delete-cell').forEach(cell => cell.remove());
    table.append(head);
    const body = document.createElement('tbody');
    body.innerHTML = selected.map(claimRow).join('');
    [...body.children].forEach((row, index) => {
      row.querySelectorAll('.mc-selection-cell, .mc-delete-cell').forEach(cell => cell.remove());
      row.lastElementChild.innerHTML = (selected[index].photos || []).map(photo => '<img src="' + esc(photo.url) + '" alt="' + esc(photo.name || 'Claim picture') + '">').join('') || '?';
      row.querySelectorAll('button').forEach(button => button.remove());
    });
    table.append(body);
    const frame = document.createElement('iframe');
    frame.title = 'Print selected manufacturing claims';
    frame.setAttribute('sandbox', 'allow-same-origin allow-modals');
    frame.setAttribute('aria-hidden', 'true');
    frame.tabIndex = -1;
    frame.style.cssText = 'position:fixed;left:-10000px;top:0;width:1200px;height:900px;border:0';
    const loaded = new Promise(resolve => frame.addEventListener('load', resolve, {once: true}));
    frame.srcdoc = '<!doctype html><html><head><title> </title><style>@page{size:A4 landscape;margin:0}body{margin:0;padding:10mm;font:11px Arial,sans-serif;color:#171c35}header{display:flex;align-items:baseline;justify-content:space-between;gap:24px;margin:0 0 6px;break-inside:avoid}h1{font-size:20px;margin:0}.print-date-range{font-size:12px;font-weight:600;margin:0;text-align:right;color:#171c35}p{margin:0 0 16px;color:#525a75}table{width:100%;border-collapse:collapse;table-layout:fixed}thead{display:table-header-group}th{background:#252c4a;color:white;text-align:left}th,td{padding:8px;border:1px solid #ccd1de;overflow-wrap:anywhere;vertical-align:top}tr{break-inside:avoid}th:last-child{width:24%}img{max-width:84px;max-height:84px;object-fit:contain;margin:2px}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}</style></head><body><header><h1>Manufacturing Claims</h1><p class="print-date-range">Order Date Range: ' + dateRange + '</p></header><p>' + selected.length + (selectedOnly ? ' selected claim' : ' claim') + (selected.length === 1 ? '' : 's') + '</p>' + table.outerHTML + '</body></html>';
    exporting = true;
    syncBulkSelection(root);
    const button = root.querySelector(selectedOnly ? '[data-mc-bulk-print]' : '[data-mc-print]');
    button.setAttribute('aria-busy', 'true');
    document.body.append(frame);
    try {
      await loaded;
      await frame.contentDocument.fonts.ready;
      frame.contentWindow.addEventListener('afterprint', () => frame.remove(), {once: true});
      frame.contentWindow.focus();
      frame.contentWindow.print();
      setTimeout(() => frame.remove(), 300000);
    } catch (error) { frame.remove(); toast(error.message || 'Could not print the selected claims.'); }
    finally {
      exporting = false;
      button.removeAttribute('aria-busy');
      syncBulkSelection(root);
      if (button.isConnected) button.focus({preventScroll: true});
    }
  }

  async function download(format) {
    if (loading || loadError || exporting) return;
    const root = document.getElementById('manufacture-claims-root');
    if (!root) return;
    const headings = [...root.querySelectorAll('.mc-table th:not(.mc-selection-cell)')].slice(0, 8);
    const exportRecords = bulkSelect ? records.filter(record => selectedClaims.has(record.id)) : filteredRecords();
    if (bulkSelect && !exportRecords.length) return;
    const exportBody = document.createElement('tbody');
    exportBody.innerHTML = exportRecords.map(claimRow).join('');
    const visibleRows = [...exportBody.children];
    const payload = {
      format, columns: headings.map(cell => cell.innerText.trim()),
      widths: headings.map(cell => AtlasViewport.rect(cell).width),
      rows: exportRecords.map((record, index) => ({id: record.id,
        cells: [...visibleRows[index].cells].filter(cell => !cell.classList.contains('mc-selection-cell')).slice(0, 8).map(cell => cell.textContent.trim()),
        photos: (record.photos || []).map(photo => photo.id),
      })),
    };
    exporting = true; paint();
    root.querySelector(bulkSelect ? `[data-mc-bulk-download="${format}"]` : `[data-mc-download="${format}"]`)?.setAttribute('aria-busy', 'true');
    try {
      const response = await fetch('/api/manufacture-claims/export', {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
      });
      if (!response.ok) { await responseJson(response); return; }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url; link.download = `manufacturing-claims.${format}`;
      document.body.append(link); link.click(); link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast(`${format.toUpperCase()} downloaded`);
    } catch (error) { toast(error.message || 'Could not download the claims table. Please try again.'); }
    finally {
      exporting = false; paint();
      root.querySelectorAll('[data-mc-download], [data-mc-bulk-download], [data-mc-bulk-print], [data-mc-print]').forEach(button => button.removeAttribute('aria-busy'));
    }
  }

  function clearPhotos() {
    attachments.forEach(item => { if (item.file) URL.revokeObjectURL(item.url); }); attachments = [];
  }

  function paintPhotos(form) {
    form.querySelector('[data-mc-previews]').innerHTML = attachments.map((item, index) => `<figure><button type="button" class="mc-preview-open" data-mc-preview="${index}" aria-label="Open picture ${esc(item.file?.name || item.name)}"><img src="${esc(item.url)}" alt="${esc(item.file?.name || item.name)}"></button><figcaption>${esc(item.file?.name || item.name)}</figcaption><button type="button" data-mc-remove-photo="${index}" aria-label="Remove picture ${esc(item.file?.name || item.name)}">${ico('x', 14)}</button></figure>`).join('');
  }

  function open(record = null, opener = null) {
    const dialog = document.querySelector('.mc-dialog');
    if (!dialog || dialog.open) return;
    if (record && (uploading.has(record.id) || deleting.has(record.id))) return;
    cancelLookup(); autoValues = {};
    clearPhotos(); dialog.querySelector('form').reset();
    editingId = record?.id || null; editingOpener = opener;
    dialog.querySelector('#mc-form-title').textContent = record ? 'Edit claim' : 'New claim';
    dialog.querySelector('[data-mc-save]').textContent = record ? 'Save changes' : 'Save claim';
    dialog.querySelector('[data-mc-form-status]').textContent = '';
    dialog.querySelector('[data-mc-lookup-status]').textContent = '';
    dialog.querySelector('#mc-replacement-options').innerHTML = '';
    dialog.querySelector('[data-mc-form-delete]').hidden = !record;
    dialog.querySelector('[data-mc-form-delete]').disabled = false;
    dialog.querySelectorAll('[data-mc-other]').forEach(label => { label.hidden = true; label.querySelector('input').disabled = true; label.querySelector('input').required = false; });
    if (record) {
      const form = dialog.querySelector('form');
      for (const key of ['orderDate', 'sellingShop', 'originalOrderNo', 'replacementOrderNo', 'variantCode']) form.elements[key].value = record[key] || '';
      for (const [key, choices] of [['reason', reasons], ['solution', solutions]]) {
        const custom = !choices.includes(record[key]) || record[key] === 'Others';
        form.elements[key].value = custom ? 'Others' : record[key];
        const other = form.querySelector(`[data-mc-other="${key}"]`);
        other.hidden = !custom; other.querySelector('input').disabled = !custom; other.querySelector('input').required = custom;
        other.querySelector('input').value = custom ? record[key] : '';
      }
      attachments = (record.photos || []).map(photo => ({...photo}));
    }
    paintPhotos(dialog.querySelector('form'));
    dialog.onclose = () => { cancelLookup(); clearPhotos(); editingId = null; (editingOpener?.isConnected ? editingOpener : document.querySelector('[data-mc-new]'))?.focus(); editingOpener = null; };
    dialog.oncancel = event => { if (dialog.querySelector('fieldset').disabled) event.preventDefault(); };
    dialog.showModal(); dialog.querySelector('[name="originalOrderNo"]').focus();
  }

  async function deleteClaim(button) {
    const id = button.dataset.mcDelete || editingId;
    if (deleting.has(id) || uploading.has(id)) return;
    if (editingId === id && document.querySelector('#mc-form fieldset')?.disabled) return;
    const claim = records.find(item => item.id === id);
    if (!await confirmSavedRecordDelete(claim?.originalOrderNo, 'manufacturing claim and its pictures', 'Delete claim')) return;
    deleting.add(id); button.disabled = true;
    const form = document.getElementById('mc-form');
    const editing = editingId === id;
    if (editing) { cancelLookup(); form.querySelector('fieldset').disabled = true; form.querySelector('[data-mc-save]').disabled = true; }
    try {
      await responseJson(await fetch(`/api/manufacture-claims/${encodeURIComponent(id)}`, {method:'DELETE'}));
      request++; records = records.filter(item => item.id !== id); selectedClaims.delete(id); paint();
      if (editing) form.closest('dialog').close();
      toast('Claim deleted');
    } catch (error) { toast(error.message || 'Could not delete claim.'); }
    finally {
      deleting.delete(id); button.disabled = false;
      if (editing) { form.querySelector('fieldset').disabled = false; form.querySelector('[data-mc-save]').disabled = false; }
      paint();
    }
  }

  document.addEventListener('keydown', event => {
    const row = event.target.closest('[data-mc-edit]');
    if (row && event.target === row && ['Enter', ' '].includes(event.key)) {
      event.preventDefault();
      if (bulkSelect) toggleClaimSelection(row); else open(records.find(item => item.id === row.dataset.mcEdit), row);
    }
  });

  document.addEventListener('click', event => {
    const bulkButton = event.target.closest('[data-mc-bulk-select], [data-mc-bulk-done]');
    if (bulkButton) {
      if (bulkButton.disabled || exporting) return;
      bulkSelect = !bulkSelect;
      selectedClaims.clear();
      paint();
      const root = document.getElementById('manufacture-claims-root');
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
        root.querySelectorAll('.mc-table tbody td').forEach(cell => cell.animate([{transform: 'translateX(-20px)'}, {transform: 'translateX(0)'}], {duration: 300, easing: 'cubic-bezier(.22,1,.36,1)'}));
        if (bulkSelect) root.querySelector('[data-mc-bulk-toolbar]').animate([{opacity: 0, transform: 'translateY(16px)'}, {opacity: 1, transform: 'translateY(0)'}], {duration: 300, easing: 'ease-out'});
      }
      root.querySelector(bulkSelect ? '[data-mc-bulk-done]' : '[data-mc-bulk-select]')?.focus({preventScroll: true});
      return;
    }
    const preview = event.target.closest('[data-mc-preview]');
    if (preview) DeliveryDetail.openImages(attachments, Number(preview.dataset.mcPreview),
      `Claim ${document.querySelector('#mc-form [name="originalOrderNo"]').value || 'pictures'}`, preview);
    const addImage = event.target.closest('[data-mc-add-image]');
    if (addImage && !addImage.disabled) {
      const input = document.querySelector('[data-mc-add-files]');
      input.dataset.claimId = addImage.dataset.mcAddImage;
      input.value = ''; input.click();
    }
    const dateTrigger = event.target.closest('[data-mc-toggle-date]');
    const dateMenu = document.getElementById('mc-date-menu');
    if (dateTrigger && dateMenu) {
      if (dateMenu.matches(':popover-open')) dateMenu.hidePopover();
      else {
        const rect = AtlasViewport.rect(dateTrigger), width = Math.min(260, AtlasViewport.width - 24);
        Object.assign(dateMenu.style, {width: `${width}px`, left: `${Math.max(12, Math.min(rect.right - width, AtlasViewport.width - width - 12))}px`, top: `${rect.bottom + 6}px`});
        dateMenu.showPopover();
      }
      dateTrigger.setAttribute('aria-expanded', String(dateMenu.matches(':popover-open')));
      dateMenu.ontoggle = () => dateTrigger.setAttribute('aria-expanded', String(dateMenu.matches(':popover-open')));
    }
    if (event.target.closest('[data-mc-clear-dates]') && dateMenu) {
      dateFrom = ''; dateTo = '';
      dateMenu.querySelectorAll('input').forEach(input => { input.value = ''; input.min = ''; input.max = ''; });
      paint();
    }
    const row = event.target.closest('[data-mc-edit]');
    if (row && !uploading.has(row.dataset.mcEdit) && !event.target.closest('button, a, input, select')) { if (bulkSelect) toggleClaimSelection(row); else open(records.find(item => item.id === row.dataset.mcEdit), row); }
    const deleteButton = event.target.closest('[data-mc-delete]');
    if (deleteButton) deleteClaim(deleteButton);
    const formDelete = event.target.closest('[data-mc-form-delete]');
    if (formDelete && !formDelete.disabled) deleteClaim(formDelete);
    const picture = event.target.closest('[data-mc-view-photos]');
    if (picture) {
      const record = records.find(item => item.id === picture.dataset.mcViewPhotos);
      if (record) DeliveryDetail.openImages(record.photos, Number(picture.dataset.mcPhotoIndex), `Claim ${record.originalOrderNo}`, picture);
    }
    const printButton = event.target.closest('[data-mc-bulk-print], [data-mc-print]');
    if (printButton && !printButton.disabled) void printSelectedClaims(printButton.hasAttribute('data-mc-bulk-print'));
    const exportButton = event.target.closest('[data-mc-download], [data-mc-bulk-download]');
    if (exportButton) download(exportButton.dataset.mcDownload || exportButton.dataset.mcBulkDownload);
    if (event.target.closest('[data-mc-new]')) open();
    if (event.target.closest('[data-mc-refresh]')) load();
    if (event.target.closest('[data-mc-close]')) {
      if (!document.querySelector('.mc-dialog fieldset')?.disabled) document.querySelector('.mc-dialog')?.close();
    }
    const remove = event.target.closest('[data-mc-remove-photo]');
    if (remove) {
      const [item] = attachments.splice(Number(remove.dataset.mcRemovePhoto), 1);
      if (item?.file) URL.revokeObjectURL(item.url);
      paintPhotos(remove.closest('form'));
    }
  });

  document.addEventListener('input', event => {
    if (event.target.matches('[data-mc-search]')) { search = event.target.value; paint(); }
    const input = event.target.closest('#mc-form input[name="originalOrderNo"], #mc-form input[name="replacementOrderNo"]');
    if (!input) return;
    cancelLookup();
    const form = input.form;
    form.querySelector('[data-mc-lookup-status]').textContent = '';
    for (const name of ['originalOrderNo', 'replacementOrderNo', 'variantCode', 'sellingShop']) {
      if (name !== input.name && autoValues[name] && form.elements[name].value === autoValues[name]) form.elements[name].value = '';
    }
    const value = input.value.trim();
    if (/^\d{1,20}$/.test(value)) lookupTimer = setTimeout(() => lookupOrderFields(input.name, value), 500);
  });

  async function lookupOrderFields(source, order) {
    const form = document.getElementById('mc-form');
    if (!form?.closest('dialog').open) return;
    const version = ++lookupVersion;
    const controller = new AbortController(); lookupController = controller;
    const names = ['originalOrderNo', 'replacementOrderNo', 'variantCode', 'sellingShop'];
    const before = Object.fromEntries(names.map(name => [name, form.elements[name].value]));
    const status = form.querySelector('[data-mc-lookup-status]');
    status.textContent = 'Looking up order links and Product SKU…';
    const timeout = setTimeout(() => controller.abort(), 30000);
    try {
      const result = await responseJson(await fetch(`/api/manufacture-claims/order-lookup?${new URLSearchParams({order})}`, {signal: controller.signal}));
      if (version !== lookupVersion || !form.closest('dialog').open) return;
      if (!result.found) { status.textContent = 'Order not found in saved Sales Activity. You can fill the fields manually.'; return; }
      const values = {originalOrderNo: result.originalOrderNo, replacementOrderNo: result.replacementOrderNo,
        variantCode: (result.variantCodes || []).join(', '), sellingShop: result.sellingShop};
      names.forEach(name => {
        const input = form.elements[name], value = values[name];
        const manual = name !== source && before[name] && before[name] !== autoValues[name];
        if (name === 'sellingShop' && ![...input.options].some(option => option.value === value)) return;
        if (value && value.length <= 200 && !manual && input.value === before[name]) {
          const changed = input.value !== value;
          input.value = value; autoValues[name] = value;
          if (changed) flashAutofill(input);
        }
      });
      form.querySelector('#mc-replacement-options').innerHTML = (result.replacementOptions || []).map(value => `<option value="${esc(value)}"></option>`).join('');
      status.textContent = result.replacementOptions?.length > 1
        ? 'Multiple replacement orders found. Choose a replacement order from the suggestions.'
        : result.originalUnavailable ? 'The linked original is not saved yet. Check the order fields before saving.'
        : 'Available order links, SKU and channel filled. Check the details before saving.';
      if (!result.variantCodes?.length) status.textContent += ' SKU is not available; enter it manually.';
    } catch (error) {
      if (version === lookupVersion) status.textContent = error.name === 'AbortError' ? 'Order lookup timed out. Try again or fill the fields manually.' : error.message;
    } finally { clearTimeout(timeout); }
  }

  function addFormPictures(files, form) {
    if (form.querySelector('fieldset').disabled) return;
    const combined = [...attachments.map(item => item.file || {size: 0}), ...files];
    let error = '';
    if (combined.length > 5) error = 'Attach up to 5 pictures.';
    else if (files.some(file => !['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type))) error = 'Choose JPG, PNG, WebP or GIF pictures.';
    else if (files.some(file => file.size > maxPicture)) error = 'Each picture must be 5 MB or smaller.';
    else if (combined.reduce((sum, file) => sum + file.size, 0) > maxTotal) error = 'Pictures must total 15 MB or less.';
    form.querySelector('[data-mc-form-status]').textContent = error;
    if (!error) attachments.push(...files.map(file => ({file, url: URL.createObjectURL(file)})));
    paintPhotos(form);
  }
  document.addEventListener('dragover', event => {
    const zone = event.target.closest('.mc-upload');
    if (!zone || zone.closest('fieldset').disabled) return;
    event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; zone.classList.add('is-drag-over');
  });
  document.addEventListener('dragleave', event => {
    const zone = event.target.closest('.mc-upload');
    if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove('is-drag-over');
  });
  document.addEventListener('drop', event => {
    const zone = event.target.closest('.mc-upload');
    if (!zone) return;
    event.preventDefault(); zone.classList.remove('is-drag-over');
    addFormPictures([...event.dataTransfer.files], zone.closest('form'));
  });

  document.addEventListener('change', event => {
    if (event.target.matches('[data-mc-select], [data-mc-select-all]')) {
      if (exporting) return;
      const ids = event.target.matches('[data-mc-select-all]') ? filteredRecords().map(item => item.id) : [event.target.dataset.mcSelect];
      ids.forEach(id => { if (event.target.checked) selectedClaims.add(id); else selectedClaims.delete(id); });
      syncBulkSelection();
      return;
    }
    if (event.target.matches('[data-mc-add-files]')) {
      const files = [...event.target.files], id = event.target.dataset.claimId;
      event.target.value = '';
      if (files.length) void appendPictures(id, files);
      return;
    }
    if (event.target.matches('[data-mc-date]')) {
      if (event.target.dataset.mcDate === 'from') dateFrom = event.target.value;
      else dateTo = event.target.value;
      document.querySelector('[data-mc-date="from"]').max = dateTo;
      document.querySelector('[data-mc-date="to"]').min = dateFrom;
      paint(); return;
    }
    const form = event.target.closest('#mc-form');
    if (!form) return;
    if (['reason', 'solution'].includes(event.target.name)) {
      const other = form.querySelector(`[data-mc-other="${event.target.name}"]`);
      other.hidden = event.target.value !== 'Others';
      other.querySelector('input').disabled = other.hidden;
      other.querySelector('input').required = !other.hidden;
    }
    if (event.target.id === 'mc-pictures') {
      const files = Array.from(event.target.files || []);
      addFormPictures(files, form);
      event.target.value = '';
    }
  });

  const encode = file => new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve({name: file.name, data: String(reader.result).split(',')[1]});
    reader.onerror = () => reject(new Error('Could not read a picture. Please choose it again.'));
    reader.readAsDataURL(file);
  });

  async function appendPictures(id, files) {
    const claim = records.find(item => item.id === id);
    if (!claim || uploading.has(id) || deleting.has(id)) return;
    if ((claim.photos || []).length + files.length > 5) return toast('Attach up to 5 pictures per claim.');
    if (files.some(file => !['image/jpeg', 'image/png', 'image/webp', 'image/gif'].includes(file.type))) return toast('Choose JPG, PNG, WebP or GIF pictures.');
    if (files.some(file => file.size > maxPicture)) return toast('Each picture must be 5 MB or smaller.');
    if (files.reduce((sum, file) => sum + file.size, 0) > maxTotal) return toast('Pictures must total 15 MB or less.');
    uploading.add(id); paint();
    try {
      const photos = await Promise.all(files.map(encode));
      const updated = await responseJson(await fetch(`/api/manufacture-claims/${encodeURIComponent(id)}/photos`, {
        method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({photos}),
      }));
      request++; records = records.map(item => item.id === id ? updated : item);
      toast('Pictures added');
    } catch (error) { toast(error.message || 'Could not add pictures. Please try again.'); }
    finally { uploading.delete(id); paint(); }
  }

  document.addEventListener('submit', async event => {
    if (event.target.id !== 'mc-form') return;
    event.preventDefault();
    const form = event.target;
    if (form.querySelector('fieldset').disabled || !form.reportValidity()) return;
    if (editingId && deleting.has(editingId)) return;
    cancelLookup();
    const payload = Object.fromEntries(new FormData(form).entries());
    const files = attachments.filter(item => item.file).map(item => item.file);
    const claimId = editingId;
    const retainedPhotoIds = attachments.filter(item => item.id).map(item => item.id);
    const save = form.querySelector('[data-mc-save]');
    form.querySelector('fieldset').disabled = true; save.disabled = true; save.textContent = 'Saving…';
    form.querySelector('[data-mc-form-status]').textContent = '';
    try {
      payload.photos = await Promise.all(files.map(encode));
      if (claimId) payload.retainedPhotoIds = retainedPhotoIds;
      const record = await responseJson(await fetch(claimId ? `/api/manufacture-claims/${encodeURIComponent(claimId)}` : '/api/manufacture-claims', {
        method: claimId ? 'PUT' : 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload),
      }));
      request++; loadError = '';
      records = claimId ? records.map(item => item.id === record.id ? record : item) : [record, ...records.filter(item => item.id !== record.id)]; paint();
      form.closest('dialog').close(); toast(claimId ? 'Claim updated' : 'Claim saved');
    } catch (error) { form.querySelector('[data-mc-form-status]').textContent = error.message || 'Could not save the claim. Please try again.'; }
    finally { form.querySelector('fieldset').disabled = false; save.disabled = false; save.textContent = editingId ? 'Save changes' : 'Save claim'; }
  });

  return {render, mount: load};
})();
