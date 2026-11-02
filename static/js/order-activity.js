(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const labels = {scheduled:'Scheduled', unscheduled:'Unscheduled', on_route:'On route', servicing:'Servicing', start_service:'Service started', success:'Completed', failed:'Failed', rejected:'Rejected', cancelled:'Cancelled'};
  const label = kind => labels[kind] || String(kind || 'Unknown').replace(/_/g, ' ');
  const sources = {observed:'Status observed by Atlas', mobile:'Driver app event', completion:'Recorded completion details'};
  const time = value => Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : 'Time unavailable';
  let entries = [], searchedOrder = '';
  function render() {
    const shown = entries.filter(e => !$('activity-filter').value || e.kind === $('activity-filter').value);
    shown.sort((a, b) => $('activity-sort').value === 'oldest' ? a.timestamp - b.timestamp : b.timestamp - a.timestamp);
    $('activity-count').textContent = `${shown.length} of ${entries.length} activities shown. Times use your browser's local timezone.`;
    $('activity-timeline').innerHTML = shown.length ? shown.map(e => `<li><div class="or-activity-head"><span class="or-badge" data-status="${esc(e.kind)}">${esc(label(e.kind))}</span><time datetime="${esc(Number.isFinite(e.timestamp) ? new Date(e.timestamp * 1000).toISOString() : '')}">${esc(time(e.timestamp))}</time></div><p>${esc(e.driver ? `Driver: ${e.driver}` : 'Driver not provided')} &middot; Order: ${esc(e.reference || searchedOrder)}${e.order_id ? ` &middot; Internal ID: ${esc(e.order_id)}` : ''}</p><small>${esc(sources[e.source] || e.source)}${e.detail ? ` — ${esc(e.detail)}` : ''}</small></li>`).join('') : '<li>No activity matches this filter.</li>';
  }
  $('activity-filter').onchange = render;
  $('activity-sort').onchange = render;
  $('activity-form').onsubmit = async event => {
    event.preventDefault();
    const query = $('activity-order').value.trim();
    if (!query) { $('activity-status').textContent = 'Enter an Order ID.'; return; }
    $('activity-search').disabled = true;
    $('activity-export').disabled = true;
    $('activity-results').hidden = true;
    $('activity-warnings').hidden = true;
    $('activity-status').textContent = `Collecting delivery activity for ${query}…`;
    $('activity-form').setAttribute('aria-busy', 'true');
    try {
      const response = await fetch(`/api/optimoroute/activity?${new URLSearchParams({orderNo:query})}`, {headers:{Accept:'application/json'}});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || `Request failed (${response.status}).`);
      entries = data.entries || []; searchedOrder = query;
      $('activity-filter').replaceChildren(new Option('All activity', ''));
      [...new Set(entries.map(e => e.kind))].sort().forEach(kind => $('activity-filter').add(new Option(label(kind), kind)));
      const observed = entries.filter(e => e.source === 'observed').sort((a,b) => b.timestamp - a.timestamp);
      $('activity-summary').innerHTML = [['Order ID', query], ['Recorded activities', entries.length], ['Last observed status', observed.length ? label(observed[0].kind) : 'Unavailable'], ['Last activity', entries.length ? time(Math.max(...entries.map(e => e.timestamp))) : 'Unavailable']].map(([name,value]) => `<div><span>${esc(name)}</span><b>${esc(value)}</b></div>`).join('');
      $('activity-notice').textContent = `${data.notice || ''}${data.syncedAt ? ` Events last synced: ${new Date(data.syncedAt).toLocaleString()}.` : ''}`;
      const warnings = data.warnings || [];
      $('activity-warnings').textContent = warnings.join(' ');
      $('activity-warnings').hidden = !warnings.length;
      $('activity-status').textContent = entries.length ? `Delivery log for ${query}${warnings.length ? ' — some provider data could not be collected.' : '.'}` : `No recorded activity found for ${query}. Check the ID or try again after deliveries have synced.`;
      $('activity-results').hidden = false;
      $('activity-export').disabled = !entries.length;
      render();
    } catch (error) { entries = []; $('activity-status').textContent = `Unable to load the delivery log: ${error.message}`; }
    finally { $('activity-search').disabled = false; $('activity-form').removeAttribute('aria-busy'); }
  };
  $('activity-export').onclick = () => {
    const cell = value => `"${String(value ?? '').replace(/^[=+@-]/, "'$&").replace(/"/g, '""')}"`;
    const rows = [['Order ID','Internal ID','Activity','Timestamp (UTC)','Driver','Source','Details'], ...entries.map(e => [e.reference || searchedOrder,e.order_id,label(e.kind),new Date(e.timestamp * 1000).toISOString(),e.driver,sources[e.source] || e.source,e.detail])];
    const url = URL.createObjectURL(new Blob(['\uFEFF' + rows.map(row => row.map(cell).join(',')).join('\r\n')], {type:'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `delivery-log-${searchedOrder.replace(/[^a-z0-9_-]/gi, '_')}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
})();
