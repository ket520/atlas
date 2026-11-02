(() => {
  'use strict';
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
