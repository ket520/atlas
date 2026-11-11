window.CollectionNote = (() => {
  let savedPaper = null;
  let undoStack = [];
  let redoStack = [];
  const minimumItemRows = 4;
  let sequence = minimumItemRows;
  let dispose = () => {};
  let messages = [];
  let foundSkus = [];
  let foundItems = [];
  let shortcutOrderApplied = false;
  let pendingOrder = '';
  function mount(root) {
    if (!root || root.dataset.mounted === 'true') return;
    root.dataset.mounted = 'true';
    dispose();
    const input = (name, label, type = 'text') => `<input type="${type}" name="${name}" aria-label="${label}">`;
    const addressField = (label, name, type = 'text') => `<tr class="cn-address-row"><td class="cn-label${name === 'phone' ? ' cn-emph cn-phone-label' : name === 'collectionOrder' ? ' cn-emph cn-collection-order-label' : ''}">${label}</td><td>${input(name, label, type)}</td><td class="cn-address-unused"></td><td class="cn-address-unused"></td></tr>`;
    const inlineField = (label, name, type = 'text') => `<tr class="cn-address-row"><td><label class="cn-inline-field"><span>${label}</span>${input(name, label, type)}</label></td><td></td><td></td><td></td></tr>`;
    const blankRows = count => Array.from({length: count}, () => '<tr class="cn-blank"><td></td><td></td><td></td><td></td></tr>').join('');
    const itemRow = i => `<tr class="cn-item-row${i >= 3 ? ' cn-item-tall' : ''}"><td>${input(`sku-${i}`, `Item ${i + 1} code`)}</td><td><textarea name="description-${i}" aria-label="Item ${i + 1} description" rows="1"></textarea></td><td>${input(`quantity-${i}`, `Item ${i + 1} quantity`, 'number')}</td><td>${input(`condition-${i}`, `Item ${i + 1} condition`)}</td><td>${input(`return-reason-${i}`, `Item ${i + 1} reason of return`)}</td></tr>`;
    root.innerHTML = `<form class="cn-form">
      <div class="cn-toolbar">
        <div><h1 class="cn-heading">Collection Note</h1><p class="cn-subheading">Collection note <span class="collection-status" data-collection-note-status>Pending</span></p></div>
        <div class="cn-actions"><button type="button" class="cn-button cn-button-primary" data-collection-save>Save note</button><button type="button" class="cn-button" data-collection-add-item>Add item row</button><button type="reset" class="cn-button">Clear note</button><button type="button" class="cn-button cn-button-primary" data-collection-print>Print note</button></div>
      </div>
      <div class="cn-format-toolbar" role="toolbar" aria-label="Cell formatting">
        <button type="button" class="cn-button" data-cell-format="bold" aria-label="Bold" aria-pressed="false"><b>B</b></button>
        <button type="button" class="cn-button" data-cell-format="italic" aria-label="Italic" aria-pressed="false"><i>I</i></button>
        <button type="button" class="cn-button" data-cell-format="underline" aria-label="Underline" aria-pressed="false"><u>U</u></button>
        <button type="button" class="cn-button" data-collection-undo disabled>Undo</button>
        <button type="button" class="cn-button" data-collection-redo disabled>Redo</button>
        <button type="button" class="cn-button" data-clear-format>Clear formatting</button>
        <span class="cn-selected-cell" role="status">Select a cell to format</span>
        <div class="cn-download-actions" role="group" aria-label="Download collection note">
          ${['pdf', 'xlsx'].map(format => `<button type="button" class="cn-button cn-download-button" data-collection-download="${format}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M5 16v5h14v-5"/></svg><span>Download ${format.toUpperCase()}</span></button>`).join('')}
        </div>
      </div>
      <div class="cn-workspace">
      <aside class="cn-status-panel" aria-label="Collection note messages">
        <h2>Messages</h2>
        <p data-collection-lookup-status role="status" aria-live="polite">Enter an order number to fill details from the sheet.</p>
        <progress data-collection-progress max="100" value="0" aria-label="Order lookup progress"></progress>
        <span class="cn-progress-label" data-collection-progress-label aria-live="polite">Ready</span>
        <button type="button" class="cn-button" data-collection-lookup>Look up order</button>
        <ol data-collection-messages aria-label="Activity messages"></ol>
        <h3>Product SKUs found <span data-collection-sku-count>0</span></h3>
        <ul data-collection-skus></ul>
      </aside>
      <div class="cn-sheet-scroll"><div class="cn-paper">
        <table class="cn-sheet" aria-label="Collection note">
          <colgroup><col class="cn-col-a"><col class="cn-col-b"><col class="cn-col-c"><col class="cn-col-d"></colgroup>
          <tbody>
            <tr class="cn-title-row"><th class="cn-title-cell" colspan="4">COLLECTION NOTE</th></tr>
            ${blankRows(2)}
          </tbody>
          <tbody class="cn-table-section">
            <tr class="cn-hdr-row cn-peach">
              <th scope="col" class="cn-small-head">Order Number:</th>
              <th scope="col" class="cn-small-head">Document date</th>
              <th scope="col" class="cn-small-head">Order reference number</th>
              <th scope="col" class="cn-small-head">Company</th>
            </tr>
            <tr class="cn-data-row">
              <td class="cn-value-cell">${input('order', 'Order number')}</td>
              <td class="cn-value-cell">${input('date', 'Document date', 'date')}</td>
              <td class="cn-value-cell">${input('orderRef', 'Order reference')}</td>
              <td class="cn-value-cell">${input('company', 'Company')}</td>
            </tr>
          </tbody>
          <tbody>
            ${blankRows(2)}
          </tbody>
          <tbody class="cn-table-section cn-address-section">
            <tr class="cn-address-head cn-peach"><th class="cn-section-label">Address</th><td></td><td class="cn-address-unused"></td><td class="cn-address-unused"></td></tr>
            ${addressField('Name', 'customer')}
            ${addressField('Street 1', 'street1')}
            ${addressField('Street 2', 'street2')}
            ${addressField('City', 'city')}
            ${addressField('Country', 'country')}
            ${addressField('Post Code', 'postcode')}
            ${addressField('Telephone', 'phone', 'tel')}
            ${addressField('Order Number to be Collected', 'collectionOrder')}
          </tbody>
          <tbody>
            ${blankRows(1)}
          </tbody>
        </table>
        <table class="cn-sheet cn-items-table" aria-label="Collection items">
          <colgroup><col class="cn-item-code-col"><col class="cn-item-description-col"><col class="cn-item-qty-col"><col class="cn-item-condition-col"><col class="cn-item-reason-col"></colgroup>
          <tbody class="cn-table-section">
            <tr class="cn-item-head cn-peach"><th class="cn-small-head">Item Code</th><th class="cn-small-head">Item description</th><th class="cn-qty-head">QTY</th><th class="cn-cond-head">Condition</th><th class="cn-small-head">Reason of Return</th></tr>
            ${Array.from({length: minimumItemRows}, (_, i) => itemRow(i)).join('')}
          </tbody>
        </table>
        <table class="cn-sheet" aria-label="Collection availability">
          <colgroup><col class="cn-col-a"><col class="cn-col-b"><col class="cn-col-c"><col class="cn-col-d"></colgroup>
          <tbody>
            ${inlineField('Collection Date:', 'availableDate')}
            ${inlineField('Collection Method:', 'collectionType')}
            ${inlineField('Refund Amount:', 'refundAmount')}
            ${inlineField('Replacement Order:', 'replacementOrder')}
            ${inlineField('Collection Fee:', 'collectionFee')}
            ${blankRows(3)}
          </tbody>
        </table>
      </div></div></div>
    </form>`;
    const form = root.querySelector('form');
    const paper = root.querySelector('.cn-paper');
    const showNoteStatus = status => {
      const badge = root.querySelector('[data-collection-note-status]');
      badge.textContent = ['Approved', 'Rejected'].includes(status) ? status : 'Pending';
      badge.classList.toggle('is-approved', status === 'Approved');
      badge.classList.toggle('is-rejected', status === 'Rejected');
    };
    const events = new AbortController();
    const on = (target, name, handler, options = {}) => target.addEventListener(name, handler, { ...options, signal: events.signal });
    root.querySelectorAll('[data-collection-download]').forEach(button => {
      const liquidOrigin = event => {
        const bounds = AtlasViewport.rect(button);
        const x = Math.max(0, Math.min(bounds.width, AtlasViewport.x(event) - bounds.left));
        const y = Math.max(0, Math.min(bounds.height, AtlasViewport.y(event) - bounds.top));
        button.style.setProperty('--liquid-x', `${x}px`);
        button.style.setProperty('--liquid-y', `${y}px`);
        button.style.setProperty('--liquid-size', `${Math.hypot(Math.max(x, bounds.width - x), Math.max(y, bounds.height - y)) * 2.3}px`);
      };
      on(button, 'pointerenter', liquidOrigin);
      on(button, 'pointermove', liquidOrigin);
      on(button, 'pointerleave', liquidOrigin);
    });
    let selectedCell = null;
    let selectedCells = new Set();
    let dragAnchor = null;
    let dragging = false;
    let lookupTimer = null;
    let lookupVersion = 0;
    let lookupController = null;
    let pendingInput = null;
    let recordId = new URLSearchParams(location.search).get('record') || '';
    let recordLoading = Boolean(recordId);
    let recordLoadFailed = false;
    const deleteButton = document.createElement('button');
    deleteButton.type = 'button';
    deleteButton.className = 'cn-button cn-button-danger';
    deleteButton.dataset.collectionDelete = '';
    deleteButton.setAttribute('aria-label', 'Delete note');
    deleteButton.title = 'Delete note';
    const deleteIcon = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 6h18M9 6V4h6v2M5 6l1 14h12l1-14M10 10v6M14 10v6"/></svg>';
    deleteButton.innerHTML = deleteIcon;
    deleteButton.hidden = !recordId;
    deleteButton.disabled = recordLoading;
    root.querySelector('.cn-actions').append(deleteButton);
    on(paper, 'input', () => {
      const saveButton = root.querySelector('[data-collection-save]');
      if (!saveButton.disabled) saveButton.textContent = 'Save note';
    });
    const lookupStatus = root.querySelector('[data-collection-lookup-status]');
    const progress = root.querySelector('[data-collection-progress]');
    const progressLabel = root.querySelector('[data-collection-progress-label]');
    const reportProgress = (completed, total, label) => {
      if (total == null) {
        progress.removeAttribute('value');
      } else {
        progress.max = total > 0 ? total : 1;
        progress.value = completed;
      }
      progressLabel.textContent = label;
      progress.setAttribute('aria-valuetext', label);
    };
    const paintProgress = () => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
    const control = name => form.elements.namedItem(name);
    const rawOrder = () => control('order').value.trim().replace(/^CN\s*/i, '');
    const displayOrder = () => {
      const field = control('order');
      const value = rawOrder();
      if (/^\d+$/.test(value)) {
        const position = field.selectionStart;
        const previous = field.value;
        field.value = `CN${value}`;
        if (document.activeElement === field && position !== null) {
          const offset = field.value.length - previous.length;
          field.setSelectionRange(Math.max(2, position + offset), Math.max(2, position + offset));
        }
      }
    };
    const resizeDescriptions = () => {
      const fields = [...paper.querySelectorAll('textarea[name^="description-"]')];
      fields.forEach(field => { field.style.height = 'auto'; });
      const heights = fields.map(field => Math.max(41, field.scrollHeight + 2));
      fields.forEach((field, index) => { field.style.height = `${heights[index]}px`; });
    };
    const cellHighlights = new WeakMap();
    const flashCells = fields => {
      const cells = new Set(fields.map(field => field?.closest('td,th')).filter(Boolean));
      // Offscreen rows need no composited highlight layers during a large lookup.
      const visible = [...cells].filter(cell => {
        const bounds = AtlasViewport.rect(cell);
        return bounds.bottom >= 0 && bounds.top <= AtlasViewport.height;
      });
      const targets = visible.flatMap(cell => [cell, ...cell.querySelectorAll('input,textarea')]);
      for (const target of targets) {
        if (typeof target.animate !== 'function') continue;
        cellHighlights.get(target)?.cancel();
        const background = window.getComputedStyle(target).backgroundColor;
        cellHighlights.set(target, target.animate([
          { backgroundColor: '#fde047', offset: 0 },
          { backgroundColor: '#fde047', offset: 0.2 },
          { backgroundColor: background, offset: 1 },
        ], { duration: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 250 : 1400, easing: 'ease-out' }));
      }
    };
    const today = () => {
      const now = new Date();
      return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
    };
    const editableCells = () => [...paper.querySelectorAll('td:not(.cn-address-unused),th')];
    const syncCollectionMethod = () => {
      control('deliveryMethod')?.closest('tr')?.remove();
      const method = control('collectionType');
      if (method?.value === 'Credit/Refund') method.value = 'Refund';
      const row = control('replacementOrder')?.closest('tr');
      if (row) row.hidden = method?.value.trim().toLowerCase() !== 'replacement';
      if (!control('refundAmount') && method) {
        method.closest('tr').insertAdjacentHTML('afterend', inlineField('Refund Amount:', 'refundAmount'));
      }
      const refund = control('refundAmount');
      if (refund) {
        refund.closest('tr').hidden = method?.value.trim().toLowerCase() !== 'refund';
        const raw = refund.value.trim().replace(/[£,\s]/g, '').replace(/^\((.*)\)$/, '-$1');
        if (raw && /^-?\d+(?:\.\d+)?$/.test(raw) && Number.isFinite(Number(raw))) {
          refund.value = new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(Math.abs(Number(raw)));
        }
      }
    };
    const snapshot = () => {
      const copy = paper.cloneNode(true);
      const originals = paper.querySelectorAll('input,textarea');
      copy.querySelectorAll('input,textarea').forEach((field, index) => {
        if (field.tagName === 'TEXTAREA') field.textContent = originals[index].value;
        else field.setAttribute('value', originals[index].value);
      });
      copy.querySelectorAll('.cn-cell-selected').forEach(cell => cell.classList.remove('cn-cell-selected'));
      return copy.innerHTML;
    };
    const remember = () => { savedPaper = snapshot(); };
    const syncToolbar = () => {
      root.querySelector('[data-collection-undo]').disabled = !undoStack.length;
      root.querySelector('[data-collection-redo]').disabled = !redoStack.length;
      root.querySelectorAll('[data-cell-format]').forEach(button => {
        button.setAttribute('aria-pressed', String(Boolean(selectedCell?.classList.contains(`cn-cell-${button.dataset.cellFormat}`))));
      });
      root.querySelector('.cn-selected-cell').textContent = selectedCells.size > 1
        ? `${selectedCells.size} cells selected ? Delete clears their contents`
        : selectedCell ? `Selected cell ${String.fromCharCode(65 + selectedCell.cellIndex)}${selectedCell.parentElement.rowIndex + 1}` : 'Select a cell to format';
    };
    const paintSkus = () => {
      const present = new Set([...paper.querySelectorAll('.cn-item-row [name^="sku-"]')]
        .map(field => field.value.trim().toUpperCase()).filter(Boolean));
      root.querySelector('[data-collection-sku-count]').textContent = foundSkus.length;
      root.querySelector('[data-collection-skus]').replaceChildren(...foundSkus.map(sku => {
        const included = present.has(sku.trim().toUpperCase());
        const entry = document.createElement('li');
        entry.className = `cn-sku-box ${included ? 'cn-sku-present' : 'cn-sku-removed'}`;
        const code = document.createElement('strong');
        code.textContent = sku;
        entry.append(code);
        if (!included) {
          entry.dataset.collectionRestoreSku = sku;
          const restore = document.createElement('button');
          restore.type = 'button';
          restore.className = 'cn-sku-restore';
          restore.dataset.collectionRestoreSku = sku;
          restore.setAttribute('aria-label', `Restore ${sku} to collection items`);
          restore.title = 'Restore to collection items';
          restore.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 10h11a6 6 0 0 1 0 12"/><path d="m7 6-4 4 4 4"/></svg>';
          entry.append(restore);
        }
        return entry;
      }));
    };
    const paintMessages = () => {
      const list = root.querySelector('[data-collection-messages]');
      list.replaceChildren(...messages.filter(text => !/^(?:Item row(?: .*)? deleted\.|Looking up order \d+ in the sheet|Order \d+ (?:found\. Loading|filled with)|Missing address details and item descriptions)/.test(text)).map(message => {
        const entry = document.createElement('li');
        entry.textContent = message;
        return entry;
      }));
      paintSkus();
    };
    const message = text => {
      lookupStatus.textContent = text;
      messages.push(text);
      paintMessages();
    };
    const select = (cell, range = null) => {
      selectedCells.forEach(previous => previous.classList.remove('cn-cell-selected'));
      selectedCell = cell;
      selectedCells = new Set(range || (cell ? [cell] : []));
      selectedCells.forEach(current => current.classList.add('cn-cell-selected'));
      syncToolbar();
    };
    const record = before => {
      const after = snapshot();
      if (after !== before) {
        undoStack.push(before);
        if (undoStack.length > 100) undoStack.shift();
        redoStack = [];
      }
      savedPaper = after;
      syncToolbar();
      paintSkus();
    };
    const cancelLookup = (keepPending = false) => {
      ++lookupVersion;
      clearTimeout(lookupTimer);
      lookupController?.abort();
      if (!keepPending) pendingOrder = '';
      reportProgress(0, 1, 'Ready');
    };
    const prepare = () => {
      syncCollectionMethod();
      // Saved notes retain their original table markup; upgrade the old date label.
      paper.querySelectorAll('th, .cn-small-head').forEach(heading => {
        if (/^order\s+date$/i.test(heading.textContent.trim())) heading.textContent = 'Document date';
      });
      control('date')?.setAttribute('aria-label', 'Document date');
      paper.querySelectorAll('input[name^="description-"]').forEach(field => {
        const textarea = document.createElement('textarea');
        textarea.name = field.name;
        textarea.setAttribute('aria-label', field.getAttribute('aria-label') || 'Item description');
        textarea.rows = 1;
        textarea.value = field.value;
        field.replaceWith(textarea);
      });
      displayOrder();
      editableCells().forEach(cell => {
        if (cell.tagName === 'TD' && !cell.firstChild) cell.innerHTML = input(`extra-${sequence++}`, 'Editable cell');
        cell.tabIndex = -1;
      });
      paper.querySelectorAll('input[type="number"]').forEach(field => { field.min = '0'; });
      for (const name of ['order', 'collectionOrder']) {
        const cell = control(name).closest('td');
        cell.classList.add('cn-copy-cell');
        cell.querySelector('[data-collection-copy]')?.remove();
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'cn-copy-button';
        button.dataset.collectionCopy = name;
        button.setAttribute('aria-label', name === 'order' ? 'Copy note order number' : 'Copy customer order number');
        button.title = button.getAttribute('aria-label');
        button.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>';
        cell.append(button);
      }
      resizeDescriptions();
      paper.querySelectorAll('.cn-item-row').forEach(row => {
        const cell = row.firstElementChild;
        row.querySelector('[data-collection-delete-item]')?.remove();
        if (!cell.querySelector('[data-collection-delete-item]')) {
          const button = document.createElement('button');
          button.type = 'button';
          button.className = 'cn-delete-item';
          button.dataset.collectionDeleteItem = '';
          button.setAttribute('aria-label', 'Delete item row');
          button.title = 'Delete item row';
          button.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M18 6 6 18M6 6l12 12"/></svg>';
          cell.append(button);
        }
      });
    };
    if (savedPaper) paper.innerHTML = savedPaper;
    else {
      control('date').value = today();
    }
    normalizeItemRows();
    prepare();
    if (!savedPaper) flashCells([control('date')]);
    remember();
    paintMessages();
    syncToolbar();
    const undoRedo = redo => {
      cancelLookup();
      pendingInput = null;
      const source = redo ? redoStack : undoStack;
      const target = redo ? undoStack : redoStack;
      if (!source.length) return;
      target.push(snapshot());
      paper.innerHTML = source.pop();
      selectedCell = null;
      selectedCells = new Set();
      prepare();
      remember();
      syncToolbar();
      message(redo ? 'Change redone.' : 'Change undone.');
    };
    const addItem = afterRow => {
      const holder = document.createElement('tbody');
      holder.innerHTML = itemRow(sequence++);
      const row = holder.firstElementChild;
      if (afterRow) afterRow.after(row);
      else paper.querySelector('.cn-items-table tbody').append(row);
      prepare();
      return row;
    };
    function normalizeItemRows() {
      const rows = [...paper.querySelectorAll('.cn-item-row')];
      const empty = rows.filter(row => [...row.querySelectorAll('input,textarea')].every(field => !field.value.trim()));
      const blanksToKeep = Math.max(0, minimumItemRows - (rows.length - empty.length));
      empty.slice(blanksToKeep).forEach(row => {
        if (selectedCell?.closest('tr') === row) select(null);
        row.remove();
      });
      let added = false;
      while (paper.querySelectorAll('.cn-item-row').length < minimumItemRows) {
        while (control(`sku-${sequence}`)) sequence++;
        const holder = document.createElement('tbody');
        holder.innerHTML = itemRow(sequence++);
        paper.querySelector('.cn-items-table tbody').append(holder.firstElementChild);
        added = true;
      }
      if (added) prepare();
    }
    const autoNames = () => ['orderRef', 'company', 'customer', 'street1', 'street2',
      ...(control('street3') ? ['street3'] : []), 'city', 'country', 'postcode', 'phone', 'collectionOrder',
      ...['collectionType', 'replacementOrder', 'refundAmount'].filter(name => control(name)),
      ...[...paper.querySelectorAll('.cn-item-row input,.cn-item-row textarea')].filter(field => /^(sku|description|quantity)-/.test(field.name)).map(field => field.name)];
    const exportColor = value => {
      const parts = String(value).match(/[\d.]+/g);
      if (!parts || (parts.length > 3 && Number(parts[3]) === 0)) return null;
      return '#' + parts.slice(0, 3).map(part => Math.round(Number(part)).toString(16).padStart(2, '0')).join('');
    };
    function exportLayout(format) {
      resizeDescriptions();
      const clone = paper.cloneNode(true);
      clone.style.cssText = 'position:fixed;left:-10000px;top:0;width:711px;max-width:none;pointer-events:none;visibility:hidden';
      clone.querySelectorAll('button').forEach(button => button.remove());
      clone.querySelectorAll('.cn-cell-selected').forEach(cell => cell.classList.remove('cn-cell-selected'));
      root.append(clone);
      try {
        const originals = [...paper.querySelectorAll('input,textarea')];
        clone.querySelectorAll('input,textarea').forEach((field, index) => {
          const source = originals[index];
          const style = window.getComputedStyle(field);
          const value = document.createElement('span');
          value.dataset.cnExportValue = '';
          value.textContent = source.type === 'date' && source.value
            ? new Date(`${source.value}T12:00:00`).toLocaleDateString('en-GB') : source.value;
          for (const property of ['display', 'width', 'minWidth', 'minHeight', 'paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft', 'fontFamily', 'fontSize', 'fontWeight', 'fontStyle', 'textDecorationLine', 'textAlign', 'color', 'lineHeight', 'flex']) {
            value.style[property] = style[property];
          }
          value.style.height = `${AtlasViewport.rect(field).height}px`;
          value.style.whiteSpace = 'pre-wrap';
          value.style.overflowWrap = 'anywhere';
          field.replaceWith(value);
        });
        const tables = [...clone.querySelectorAll('.cn-sheet')];
        const width = AtlasViewport.rect(tables[0]).width;
        const round = value => Math.round(value * 100) / 100;
        const rows = tables.flatMap(table => {
          const bounds = AtlasViewport.rect(table);
          return [...table.rows].filter(row => !row.hidden).map(row => ({
            height: round(AtlasViewport.rect(row).height),
            cells: [...row.cells].map(cell => {
              const rect = AtlasViewport.rect(cell);
              const style = window.getComputedStyle(cell);
              const value = cell.querySelector('[data-cn-export-value]');
              const textStyle = value ? window.getComputedStyle(value) : style;
              let background = null;
              for (let ancestor = cell; ancestor && !background; ancestor = ancestor.parentElement) {
                background = exportColor(window.getComputedStyle(ancestor).backgroundColor);
              }
              const inline = cell.querySelector('.cn-inline-field');
              const text = inline ? [...inline.children].map(part => part.textContent.trim()).join(' ') : cell.textContent.trim();
              const x = Math.max(0, round(rect.left - bounds.left));
              return {
                x, width: Math.min(round(rect.width), round(width - x)), text,
                fontSize: parseFloat(textStyle.fontSize), bold: Number(textStyle.fontWeight) >= 600 || textStyle.fontWeight === 'bold',
                italic: textStyle.fontStyle === 'italic', underline: textStyle.textDecorationLine.includes('underline'),
                align: ['left', 'center', 'right'].includes(textStyle.textAlign) ? textStyle.textAlign : 'left',
                color: exportColor(textStyle.color), background: background || '#ffffff',
                paddingLeft: parseFloat(style.paddingLeft) + (value ? parseFloat(textStyle.paddingLeft) : 0),
                paddingRight: parseFloat(style.paddingRight) + (value ? parseFloat(textStyle.paddingRight) : 0),
                borders: Object.fromEntries(['Top', 'Right', 'Bottom', 'Left'].map(side => [side.toLowerCase(), {
                  width: parseFloat(style[`border${side}Width`]), color: exportColor(style[`border${side}Color`]),
                }])),
              };
            }),
          }));
        });
        return { format, order: rawOrder(), width: round(width), rows };
      } finally {
        clone.remove();
      }
    }
    let exportInFlight = false;
    async function downloadNote(format) {
      if (exportInFlight) return;
      exportInFlight = true;
      const buttons = [...root.querySelectorAll('[data-collection-download]')];
      buttons.forEach(button => { button.disabled = true; });
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 60000);
      message(`Preparing ${format.toUpperCase()} download...`);
      try {
        const response = await fetch('/api/collection-note/export', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(exportLayout(format)), signal: controller.signal,
        });
        if (!response.ok) {
          const error = await response.json();
          throw new Error(error.error || 'Could not download the note.');
        }
        const url = URL.createObjectURL(await response.blob());
        const link = document.createElement('a');
        link.href = url;
        link.download = response.headers.get('Content-Disposition')?.match(/filename="([^"]+)"/)?.[1] || `collection-note.${format}`;
        document.body.append(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 60000);
        message(`${format.toUpperCase()} downloaded.`);
        return {ok: true};
      } catch (error) {
        const detail = error.name === 'AbortError' ? 'Download timed out. Please try again.' : error.message;
        message(detail);
        return {ok: false, error: detail};
      } finally {
        clearTimeout(timeout);
        exportInFlight = false;
        buttons.forEach(button => { button.disabled = false; });
      }
    }
    async function lookupOrder() {
      cancelLookup();
      displayOrder();
      const order = rawOrder();
      if (!/^\d{1,20}$/.test(order)) {
        message('Enter a numeric order number. You can also fill the note manually.');
        return;
      }
      const version = lookupVersion;
      pendingOrder = order;
      const beforeValues = Object.fromEntries(autoNames().map(name => [name, control(name).value]));
      lookupController = new AbortController();
      const controller = lookupController;
      const timeout = setTimeout(() => controller.abort(), 60000);
      foundSkus = [];
      reportProgress(0, null, 'Connecting to order lookup…');
      lookupStatus.textContent = '';
      try {
        const response = await fetch(`/api/collection-note?${new URLSearchParams({ order, progress: '1' })}`, { signal: controller.signal, cache: 'no-store' });
        if (version !== lookupVersion || !root.isConnected) return;
        const totalBytes = Number(response.headers.get('Content-Length')) || 0;
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let received = 0;
        let body = '';
        let result;
        const streaming = response.headers.get('Content-Type')?.includes('application/x-ndjson');
        const handleEvent = line => {
          if (!line.trim()) return;
          const event = JSON.parse(line);
          if (event.type === 'error') throw new Error(event.error || 'Order lookup failed.');
          if (event.type === 'result') { result = event.result; return; }
          if (event.type !== 'progress') return;
          if (event.stage === 'waiting') reportProgress(0, null, 'Waiting for access to the sheet…');
          else if (event.stage === 'reading') reportProgress(0, null, 'Reading Sales Activity from Google Sheets…');
          else if (event.stage === 'matching') {
            const total = Number(event.total) || 0;
            const completed = Number(event.completed) || 0;
            reportProgress(completed, total, `Searching orders: ${completed.toLocaleString()} / ${total.toLocaleString()} rows`);
          }
        };
        while (true) {
          const { done, value } = await reader.read();
          if (version !== lookupVersion || !root.isConnected) { await reader.cancel(); return; }
          if (done) break;
          received += value.byteLength;
          body += decoder.decode(value, { stream: true });
          if (streaming) {
            let newline;
            while ((newline = body.indexOf('\n')) !== -1) {
              handleEvent(body.slice(0, newline));
              body = body.slice(newline + 1);
            }
          } else {
            reportProgress(received, totalBytes || null, totalBytes
              ? `Receiving order data: ${received.toLocaleString()} / ${totalBytes.toLocaleString()} bytes`
              : `Receiving order data: ${received.toLocaleString()} bytes`);
          }
        }
        body += decoder.decode();
        if (streaming) {
          handleEvent(body);
          if (!result) throw new Error('The lookup ended before returning order details. Try again.');
        } else result = JSON.parse(body);
        if (version !== lookupVersion || !root.isConnected || rawOrder() !== order) return;
        if (!response.ok) throw new Error(result.error || 'Order lookup failed.');
        if (!result.found) {
          pendingOrder = '';
          message(`Order ${order} was not found in the sheet. You can fill the note manually.`);
          reportProgress(1, 1, 'Lookup complete - order not found');
          return;
        }
        reportProgress(0, null, 'Preparing collection note fields…');
        await paintProgress();
        if (version !== lookupVersion || !root.isConnected || rawOrder() !== order) return;
        const before = snapshot();
        const highlightedFields = [];
        const street3 = control('street3');
        if (!street3 || street3.value === (beforeValues.street3 ?? '')) {
          if (result.fields.street3?.trim()) {
            if (!street3) {
              control('street2').closest('tr').insertAdjacentHTML('afterend', addressField('Street 3', 'street3'));
              prepare();
            }
          } else {
            street3?.closest('tr').remove();
          }
        }
        const missingRows = result.items.length - paper.querySelectorAll('.cn-item-row').length;
        if (missingRows > 0) {
          const holder = document.createElement('tbody');
          holder.innerHTML = Array.from({ length: missingRows }, () => itemRow(sequence++)).join('');
          const addedFields = [...holder.querySelectorAll('input,textarea')];
          paper.querySelector('.cn-items-table tbody').append(...holder.children);
          prepare();
          highlightedFields.push(...addedFields);
        }
        const values = { ...result.fields };
        paper.querySelectorAll('.cn-item-row').forEach((row, index) => {
          values[row.querySelector('[name^="sku-"]').name] = result.items[index]?.sku || '';
          values[row.querySelector('[name^="description-"]').name] = result.items[index]?.description || '';
          values[row.querySelector('[name^="quantity-"]').name] = result.items[index]?.quantity ?? '';
        });
        const names = autoNames();
        let filled = 0;
        reportProgress(0, names.length, `Filling cells: 0 / ${names.length}`);
        for (const name of names) {
          const field = control(name);
          if (field.value === (beforeValues[name] ?? '')) {
            const value = values[name] || '';
            if (value || field.value !== value) highlightedFields.push(field);
            field.value = value;
          }
          reportProgress(++filled, names.length, `Cells processed: ${filled} / ${names.length}`);
        }
        syncCollectionMethod();
        normalizeItemRows();
        resizeDescriptions();
        foundSkus = result.items.map(item => item.sku);
        foundItems = result.items.map(item => ({ ...item }));
        pendingOrder = '';
        record(before);
        flashCells(highlightedFields);
        await paintProgress();
        if (version !== lookupVersion || !root.isConnected || rawOrder() !== order) return;
        reportProgress(1, 1, `Complete - ${result.items.length} product SKUs found`);
      } catch (error) {
        if (version !== lookupVersion || !root.isConnected) return;
        pendingOrder = '';
        reportProgress(0, 1, 'Lookup failed');
        message(error.name === 'AbortError' ? 'Order lookup timed out. Try again or fill the note manually.' : error.message);
      } finally {
        clearTimeout(timeout);
      }
    }
    async function saveRecord(button) {
      if (recordLoading || recordLoadFailed) return message('Reload the saved note before saving changes.');
      displayOrder();
      if (!rawOrder()) return message('Enter an order number before saving.');
      if (lookupController) cancelLookup();
      const summary = Object.fromEntries(['order', 'orderRef', 'collectionOrder', 'customer', 'postcode'].map(key => [key, control(key).value.trim()]));
      summary.channel = control('company')?.value.trim() || '';
      summary.phone = control('phone')?.value.trim() || '';
      summary.order = rawOrder();
      summary.collectionDate = control('availableDate')?.value || '';
      summary.items = [...paper.querySelectorAll('[name^="sku-"]')].map(field => field.value.trim()).filter(Boolean).join(', ');
      button.disabled = true;
      button.textContent = 'Saving…';
      deleteButton.disabled = true;
      try {
        const response = await fetch('/api/collection-notes', {
          method: 'POST', headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({id: recordId || undefined, summary, paper: snapshot()}),
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not save collection note.');
        recordId = result.id;
        showNoteStatus(result.status);
        const url = new URL(location.href);
        url.search = new URLSearchParams({view: 'create', record: recordId}).toString();
        history.replaceState(history.state, '', url);
        remember();
        message('Collection note saved. It is available in Collection Note records.');
        button.textContent = 'Saved';
      } catch (error) {
        message(error.message || 'Could not save collection note. Please try again.');
        button.textContent = 'Save note';
      } finally {
        button.disabled = false;
        deleteButton.hidden = !recordId;
        deleteButton.disabled = false;
      }
    }

    async function deleteRecord() {
      if (!recordId || recordLoading || recordLoadFailed || deleteButton.disabled) return;
      if (!await confirmSavedRecordDelete(rawOrder())) return;
      deleteButton.disabled = true;
      root.querySelector('[data-collection-save]').disabled = true;
      deleteButton.textContent = 'Deleting…';
      try {
        const response = await fetch(`/api/collection-notes/${encodeURIComponent(recordId)}`, {method: 'DELETE'});
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not delete collection note.');
        savedPaper = null;
        undoStack = [];
        redoStack = [];
        pendingOrder = '';
        window.location.assign('./collective-note.html');
      } catch (error) {
        message(error.message || 'Could not delete collection note. Please try again.');
        deleteButton.disabled = false;
        root.querySelector('[data-collection-save]').disabled = false;
        deleteButton.innerHTML = deleteIcon;
      }
    }

    async function loadRecord() {
      paper.inert = true;
      root.querySelector('[data-collection-save]').disabled = true;
      try {
        const response = await fetch(`/api/collection-notes/${encodeURIComponent(recordId)}`);
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || 'Could not open collection note.');
        if (!root.isConnected) return;
        showNoteStatus(result.status);
        // Restore only note table elements and safe attributes from stored markup.
        const parsed = new DOMParser().parseFromString(result.paper, 'text/html');
        const tags = new Set(['TABLE', 'COLGROUP', 'COL', 'TBODY', 'THEAD', 'TFOOT', 'TR', 'TD', 'TH', 'INPUT', 'TEXTAREA', 'LABEL', 'SPAN', 'BR']);
        const attrs = new Set(['class', 'name', 'value', 'type', 'colspan', 'rowspan', 'aria-label', 'scope', 'min', 'max', 'step', 'data-inserted']);
        for (const element of [...parsed.body.querySelectorAll('*')]) {
          if (!tags.has(element.tagName)) { element.remove(); continue; }
          for (const attribute of [...element.attributes]) if (!attrs.has(attribute.name)) element.removeAttribute(attribute.name);
          if (element.tagName === 'INPUT' && !['text', 'date', 'number', 'tel'].includes(element.type)) element.type = 'text';
        }
        paper.replaceChildren(...parsed.body.childNodes);
        const collectionMethod = paper.querySelector('[name="collectionType"]');
        const collectionMethodLabel = collectionMethod?.closest('label')?.querySelector('span');
        if (collectionMethodLabel) collectionMethodLabel.textContent = 'Collection Method:';
        if (collectionMethod) collectionMethod.setAttribute('aria-label', 'Collection Method:');
        if (collectionMethod?.value === 'Credit/Refund') collectionMethod.value = 'Refund';
        normalizeItemRows();
        prepare();
        undoStack = [];
        redoStack = [];
        remember();
        syncToolbar();
        message('Saved collection note opened. Edit it and choose Save note to update this record.');
      } catch (error) {
        recordLoadFailed = true;
        message(error.message || 'Could not open collection note. Reload to retry.');
      } finally {
        recordLoading = false;
        paper.inert = recordLoadFailed;
        root.querySelector('[data-collection-save]').disabled = recordLoadFailed;
        deleteButton.disabled = recordLoadFailed;
      }
    }

    on(root, 'click', event => {
      const button = event.target.closest('[data-collection-restore-sku]') || event.target.closest('button');
      if (!button) return;
      if (button.hasAttribute('data-collection-copy')) {
        const value = control(button.dataset.collectionCopy).value;
        if (value) writeClipboard(value).then(() => message('Order number copied.')).catch(() => message('Could not copy the order number.'));
        return;
      }
      if (button.hasAttribute('data-collection-save')) return void saveRecord(button);
      if (button.hasAttribute('data-collection-delete')) return void deleteRecord();
      if (button.hasAttribute('data-collection-download')) return void downloadNote(button.dataset.collectionDownload);
      if (button.hasAttribute('data-collection-restore-sku')) {
        const sku = button.dataset.collectionRestoreSku;
        const rows = [...paper.querySelectorAll('.cn-item-row')];
        if (rows.some(row => row.querySelector('[name^="sku-"]').value.trim().toUpperCase() === sku.trim().toUpperCase())) return;
        const before = snapshot();
        const row = rows.find(item => [...item.querySelectorAll('input,textarea')].every(field => !field.value.trim())) || addItem();
        const field = row.querySelector('[name^="sku-"]');
        field.value = sku;
        row.querySelector('[name^="description-"]').value = foundItems.find(item => item.sku === sku)?.description || '';
        row.querySelector('[name^="quantity-"]').value = foundItems.find(item => item.sku === sku)?.quantity ?? '';
        resizeDescriptions();
        record(before);
        field.focus();
        flashCells([...row.querySelectorAll('input,textarea')]);
        return;
      }
      if (button.hasAttribute('data-collection-lookup')) return void lookupOrder();
      if (button.hasAttribute('data-collection-undo')) return undoRedo(false);
      if (button.hasAttribute('data-collection-redo')) return undoRedo(true);
      if (button.hasAttribute('data-collection-print')) return window.print();
      if (button.hasAttribute('data-collection-add-item')) {
        const before = snapshot();
        const row = addItem();
        record(before);
        row.querySelector('input').focus();
        flashCells([...row.querySelectorAll('input,textarea')]);
        message('Item row added.');
      } else if (button.hasAttribute('data-collection-delete-item')) {
        const before = snapshot();
        const row = button.closest('tr');
        if (selectedCell?.closest('tr') === row) select(null);
        row.remove();
        normalizeItemRows();
        record(before);
      } else if (button.closest('.cn-format-toolbar') && selectedCells.size) {
        const before = snapshot();
        selectedCells.forEach(cell => {
          if (button.hasAttribute('data-clear-format')) ['bold', 'italic', 'underline', 'border', 'line'].forEach(style => cell.classList.remove(`cn-cell-${style}`));
          else if (button.dataset.cellFormat) cell.classList.toggle(`cn-cell-${button.dataset.cellFormat}`);
        });
        record(before);
      }
    });
    on(paper, 'focusin', event => {
      const cell = event.target.closest('td,th');
      if (!dragging && cell && !cell.classList.contains('cn-address-unused')) select(cell);
    });
    on(paper, 'pointerdown', event => {
      if (event.button !== 0 || event.target.closest('button')) return;
      const cell = event.target.closest('td,th');
      if (!cell || cell.classList.contains('cn-address-unused')) return;
      dragAnchor = cell;
      dragging = false;
      select(cell);
      if (event.target === cell) cell.querySelector('input,textarea')?.focus();
    });
    on(document, 'pointermove', event => {
      if (!dragAnchor || !root.isConnected) return;
      const cell = document.elementFromPoint(event.clientX, event.clientY)?.closest('td,th');
      if (!cell || cell.closest('table') !== dragAnchor.closest('table') || (cell === dragAnchor && !dragging)) return;
      dragging = true;
      paper.classList.add('cn-selecting');
      event.preventDefault();
      const rows = [dragAnchor.parentElement.rowIndex, cell.parentElement.rowIndex].sort((a, b) => a - b);
      const cols = [dragAnchor.cellIndex, cell.cellIndex].sort((a, b) => a - b);
      const range = [...cell.closest('table').rows].slice(rows[0], rows[1] + 1)
        .flatMap(row => [...row.cells].filter(current => current.cellIndex >= cols[0] && current.cellIndex <= cols[1] && !current.classList.contains('cn-address-unused')));
      select(dragAnchor, range);
    });
    on(document, 'pointerup', () => {
      if (dragging) {
        window.getSelection()?.removeAllRanges();
        selectedCell?.focus();
      }
      dragAnchor = null;
      dragging = false;
      paper.classList.remove('cn-selecting');
    });
    on(document, 'pointercancel', () => { dragAnchor = null; dragging = false; paper.classList.remove('cn-selecting'); });
    on(form, 'keydown', event => {
      if (event.isComposing) return;
      if ((event.ctrlKey || event.metaKey) && ['z', 'y'].includes(event.key.toLowerCase())) {
        event.preventDefault();
        undoRedo(event.key.toLowerCase() === 'y' || event.shiftKey);
        return;
      }
      if (event.target.closest('button')) return;
      if (['Delete', 'Backspace'].includes(event.key) && event.target === control('order')) return;
      if (['Delete', 'Backspace'].includes(event.key) && (
        (event.target.matches('td,th') && event.target.contains(control('order')))
        || (selectedCells.size > 1 && [...selectedCells].some(cell => cell.contains(control('order'))))
      )) {
        event.preventDefault();
        clearNote(true);
        control('order').focus();
        return;
      }
      if (event.key === 'Enter' && selectedCell && event.target.closest('.cn-sheet')) {
        event.preventDefault();
        cancelLookup();
        const before = snapshot();
        const currentRow = selectedCell.parentElement;
        let row;
        if (currentRow.closest('.cn-items-table')) row = addItem(currentRow);
        else {
          row = document.createElement('tr');
          row.className = 'cn-address-row';
          row.dataset.inserted = 'true';
          row.innerHTML = Array.from({ length: currentRow.closest('table').querySelector('colgroup').children.length }, () => `<td>${input(`extra-${sequence++}`, 'Editable cell')}</td>`).join('');
          currentRow.after(row);
          prepare();
        }
        const column = Math.min(selectedCell.cellIndex, row.cells.length - 1);
        record(before);
        row.cells[column].querySelector('input').focus();
        message('New row inserted below the selected cell.');
      } else if (['Delete', 'Backspace'].includes(event.key) && (selectedCells.size > 1 || event.target.matches('td,th'))) {
        event.preventDefault();
        const before = snapshot();
        let count = 0;
        selectedCells.forEach(cell => cell.querySelectorAll('input,textarea').forEach(field => { field.value = ''; count++; }));
        if ([...selectedCells].some(cell => cell.contains(control('order')))) cancelLookup();
        record(before);
        message(`Cleared ${count} editable cells.`);
      }
    });
    on(form, 'submit', event => event.preventDefault());
    on(form, 'beforeinput', event => {
      pendingInput = snapshot();
    });
    on(form, 'input', event => {
      if (event.target.name === 'collectionType') syncCollectionMethod();
      if (event.target.name === 'order') displayOrder();
      if (event.target.matches('textarea[name^="description-"]')) resizeDescriptions();
      if (event.target === control('order') && event.inputType?.startsWith('delete')) {
        clearNote(true, pendingInput ?? savedPaper);
        return;
      }
      record(pendingInput ?? savedPaper);
      pendingInput = null;
      if (event.target.name === 'order') {
        cancelLookup();
        foundSkus = [];
        paintMessages();
        if (/^\d{1,20}$/.test(rawOrder())) lookupTimer = setTimeout(lookupOrder, 600);
      }
    });
    function clearNote(keepOrder = false, before = snapshot()) {
      cancelLookup();
      pendingInput = null;
      paper.querySelectorAll('input,textarea').forEach(field => {
        if (!keepOrder || field !== control('order')) field.value = '';
      });
      control('street3')?.closest('tr').remove();
      normalizeItemRows();
      paper.querySelectorAll('[name^="extra-"]').forEach(field => {
        const row = field.closest('tr');
        if (row.dataset.inserted) row.remove();
      });
      editableCells().forEach(cell => ['bold', 'italic', 'underline', 'border', 'line'].forEach(style => cell.classList.remove(`cn-cell-${style}`)));
      control('date').value = today();
      syncCollectionMethod();
      select(null);
      foundSkus = [];
      foundItems = [];
      record(before);
      message(keepOrder ? 'Note cleared. Order number kept; document date reset to today.' : 'Note cleared. Document date reset to today.');
    }
    on(form, 'reset', event => {
      event.preventDefault();
      clearNote();
    });
    dispose = () => { cancelLookup(true); events.abort(); remember(); };
    const shortcutOrder = new URLSearchParams(window.location.search).get('order') || '';
    const orderToLoad = pendingOrder || (!shortcutOrderApplied ? shortcutOrder : '');
    if (recordId) {
      void loadRecord().then(async () => {
        const format = new URLSearchParams(location.search).get('download');
        if (window.parent === window || !['pdf', 'xlsx'].includes(format)) return;
        const result = recordLoadFailed ? {ok: false, error: 'Could not open the saved collection note.'} : await downloadNote(format);
        window.parent.postMessage({type: 'collection-record-download', record: recordId, ...result}, location.origin);
      });
    } else if (/^\d{1,20}$/.test(orderToLoad)) {
      if (orderToLoad === shortcutOrder) shortcutOrderApplied = true;
      control('order').value = orderToLoad;
      void lookupOrder();
    }
  }
  return { mount };
})();

(() => {
  'use strict';
  if (!document.getElementById('sheet-refresh')) return;
  const $ = id => document.getElementById(`sheet-${id}`);
  let values = [], page = 1;
  const status = (message, error = false) => { $('status').textContent = message; $('status').dataset.error = String(error); };
  function render() {
    const query = $('search').value.trim().toLowerCase();
    const rows = values.slice(1).map((cells, index) => ({cells, number:index + 2})).filter(row => row.cells.some(cell => String(cell).toLowerCase().includes(query)));
    const size = $('size').value === 'all' ? Math.max(rows.length, 1) : Number($('size').value);
    const pages = Math.max(1, Math.ceil(rows.length / size));
    page = Math.min(page, pages);
    $('count').textContent = `${rows.length} / ${Math.max(0, values.length - 1)} rows · ${values[0]?.length || 0} columns`;
    $('table').replaceChildren();
    if (rows.length) {
      const table = document.createElement('table'); table.className = 'sheet-table';
      const caption = table.createCaption(); caption.textContent = `${document.body.dataset.sheet} — spreadsheet values`;
      const header = table.createTHead().insertRow();
      ['Sheet row', ...values[0]].forEach((value, index) => { const th = document.createElement('th'); th.scope = 'col'; th.textContent = index ? (value || `Column ${index}`) : value; header.append(th); });
      const body = table.createTBody();
      for (const row of rows.slice((page - 1) * size, page * size)) {
        const tr = body.insertRow();
        const th = document.createElement('th'); th.scope = 'row'; th.textContent = row.number; tr.append(th);
        row.cells.forEach(value => { const td = tr.insertCell(); td.textContent = value; });
      }
      $('table').append(table);
    } else { $('table').textContent = values.length > 1 ? 'No rows match your search.' : 'This tab has no data rows.'; }
    $('page').textContent = `Page ${page} of ${pages}`;
    $('prev').disabled = page <= 1; $('next').disabled = page >= pages;
    $('export').disabled = !values.length; $('search').disabled = !values.length;
  }
  async function load() {
    $('refresh').disabled = true; $('export').disabled = true;
    $('table').setAttribute('aria-busy', 'true');
    status('Loading all spreadsheet rows and columns…');
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 60000);
    try {
      const response = await fetch(`/api/google-sheets/data?${new URLSearchParams({tab:document.body.dataset.sheet})}`, {headers:{Accept:'application/json'}, signal:controller.signal});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
      if (!Array.isArray(data.values) || data.values.some(row => !Array.isArray(row))) throw new Error('The server returned an invalid spreadsheet response.');
      values = data.values; page = 1; render();
      status(`Loaded ${Math.max(values.length - 1, 0)} rows from ${data.tab}. All returned columns are available; scroll horizontally to see more.`);
      $('synced').textContent = `Last refreshed: ${new Date(data.syncedAt).toLocaleString()}. Values are read-only.`;
    } catch (error) { status(`${error.name === 'AbortError' ? 'The sheet request timed out. Try refreshing again.' : error.message}${values.length ? ' Previously loaded values remain visible.' : ''}`, true); $('export').disabled = !values.length; }
    finally { clearTimeout(timer); $('refresh').disabled = false; $('table').removeAttribute('aria-busy'); }
  }
  $('refresh').onclick = load;
  $('search').oninput = () => { page = 1; render(); };
  $('size').onchange = () => { page = 1; render(); };
  $('prev').onclick = () => { page--; render(); };
  $('next').onclick = () => { page++; render(); };
  $('export').onclick = () => {
    const cell = value => `"${String(value ?? '').replace(/^[\s]*[=+@-]/, "'$&").replace(/"/g, '""')}"`;
    const url = URL.createObjectURL(new Blob(['\uFEFF' + values.map(row => row.map(cell).join(',')).join('\r\n')], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `${document.body.dataset.sheet}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  load();
})();
