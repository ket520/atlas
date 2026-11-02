(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  let routes = [], currentRecords = [], events = [], tag = '', busy = false;
  const date = new Date(); date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  $('op-date').value = date.toISOString().slice(0, 10);
  async function request(action, query = {}) {
    const response = await fetch(`/api/optimoroute/${action}?${new URLSearchParams(query)}`, { headers: { Accept: 'application/json' } });
    const payload = await response.json();
    if (!response.ok) throw new Error(payload.error || `Request failed (${response.status}).`);
    return payload;
  }
  const parsedTime = value => value ? new Date(value.replace(' ', 'T')).getTime() : NaN;
  function flags(r) {
    const scheduled = parsedTime(r.scheduledAt);
    const start = r.startedAt?.unixTimestamp ? r.startedAt.unixTimestamp * 1000 : NaN;
    const active = ['scheduled', 'on_route', 'servicing'].includes(r.status);
    return { late: Number.isFinite(scheduled) && (Number.isFinite(start) ? start > scheduled + 900000 : active && Date.now() > scheduled + 900000), missing: r.status === 'success' && !r.photos?.length && !r.signature && !r.podNote };
  }
  function updateMetrics(records) {
    currentRecords = records;
    $('op-late').textContent = records.filter(r => flags(r).late).length;
    $('op-missing').textContent = records.filter(r => flags(r).missing).length;
    const table = $('pw-records').querySelector('table');
    if (table) {
      const columns = ['Attention', 'Barcode scans', 'Completion GPS', 'Customer feedback'];
      for (const name of columns) { const th = document.createElement('th'); th.textContent = name; table.querySelector('thead tr').append(th); }
      for (const row of table.querySelectorAll('tbody tr')) {
        const r = records.find(item => String(item.id) === row.dataset.id); if (!r) continue;
        const state = flags(r), position = r.completionPosition;
        const gps = position ? `${position.latitude}, ${position.longitude}` : '-';
        const feedback = r.customerFeedback ? `${r.customerFeedback.rating ?? '-'} / 5 ${r.customerFeedback.comment || ''}` : '-';
        for (const value of [[state.late ? 'Late / overdue' : '', state.missing ? 'No POD recorded' : ''].filter(Boolean).join(' | ') || '-', (r.barcodes || []).map(b => b.barcode).join(', ') || '-', gps, feedback]) {
          const td = document.createElement('td'); td.textContent = value; td.title = value; td.className = 'or-nowrap'; row.append(td);
        }
      }
    }
  }
  document.addEventListener('optimoroute-page', event => updateMetrics(event.detail));
  async function liveRefresh() {
    if (busy || document.hidden || !$('op-auto').checked || $('pw-records').getAttribute('aria-busy') === 'true') return;
    busy = true; $('op-live-status').textContent = 'Refreshing statuses and driver events...';
    try {
      const data = await request('refresh', { ids: currentRecords.map(r => r.id).join(',') });
      document.dispatchEvent(new CustomEvent('optimoroute-updated', { detail: data.records }));
      const result = await request('events', { tag });
      tag = result.tag || tag;
      events = [...(result.events || []), ...events].slice(0, 100);
      $('op-event-count').textContent = events.length;
      $('op-events').innerHTML = events.length ? events.map(e => `<p>${esc(e.localTime || e.utcTime)} · ${esc(e.driverName || e.driverSerial)} · ${esc(e.orderNo || '')} · ${esc(e.event)}</p>`).join('') : 'No new driver events.';
      $('op-live-status').textContent = `Live update: ${new Date().toLocaleTimeString()}. Late indicators use a 15-minute grace period.`;
    } catch (error) { $('op-live-status').textContent = error.message; }
    finally { busy = false; }
  }
  $('op-auto').onchange = liveRefresh;
  setInterval(liveRefresh, 30000);
  function decodePolyline(encoded) {
    const points = []; let index = 0, lat = 0, lon = 0;
    while (index < encoded.length) {
      const read = () => { let result = 0, shift = 0, byte; do { if (index >= encoded.length || shift > 30) throw new Error('Invalid route path.'); byte = encoded.charCodeAt(index++) - 63; result |= (byte & 31) << shift; shift += 5; } while (byte >= 32); return result & 1 ? ~(result >> 1) : result >> 1; };
      lat += read(); lon += read(); points.push([lat / 1e5, lon / 1e5]);
    }
    return points;
  }
  function renderRoute() {
    const route = routes[Number($('op-route').value)];
    if (!route) { $('op-route-summary').textContent = 'No routes for this date.'; $('op-stops').replaceChildren(); $('op-map').textContent = 'No route to display.'; return; }
    const stops = route.stops || [];
    $('op-route-summary').innerHTML = `<p><b>${esc(route.driverName)}</b> · ${esc(route.vehicleRegistration || route.vehicleLabel)} · ${stops.length} stops · ${esc(route.distance)} km · ${esc(route.duration)} min</p>`;
    $('op-stops').innerHTML = `<table class="or-table"><thead><tr><th>Stop</th><th>Order</th><th>Address</th><th>Scheduled</th><th>Travel</th></tr></thead><tbody>${stops.map(s => `<tr><td>${esc(s.stopNumber)}</td><td>${esc(s.orderNo)}</td><td>${esc(s.address)}</td><td>${esc(s.scheduledAt)}</td><td>${Math.round((s.travelTime || 0) / 60)} min</td></tr>`).join('')}</tbody></table>`;
    const located = stops.filter(s => Number.isFinite(s.latitude) && Number.isFinite(s.longitude));
    let path = located.map(s => [s.latitude, s.longitude]);
    if (route.routePolyline) { try { path = decodePolyline(route.routePolyline); } catch {} }
    if (!path.length) { $('op-map').textContent = 'No coordinates provided for this route.'; return; }
    const all = [...path, ...located.map(s => [s.latitude, s.longitude])];
    const lats = all.map(p => p[0]), lons = all.map(p => p[1]);
    const minLat = Math.min(...lats), maxLat = Math.max(...lats), minLon = Math.min(...lons), maxLon = Math.max(...lons);
    const point = p => [35 + (p[1] - minLon) / (maxLon - minLon || 1) * 530, 325 - (p[0] - minLat) / (maxLat - minLat || 1) * 290];
    $('op-map').innerHTML = `<svg viewBox="0 0 600 360" role="img" aria-label="Route path and numbered stops"><defs><pattern id="op-grid" width="30" height="30" patternUnits="userSpaceOnUse"><path d="M30 0H0V30" fill="none" stroke="#e4ebf5"/></pattern></defs><rect width="600" height="360" fill="url(#op-grid)"/><polyline points="${path.map(p => point(p).join(',')).join(' ')}" fill="none" stroke="#6192d9" stroke-width="3"/>${located.map(s => { const [x,y] = point([s.latitude,s.longitude]); return `<a href="https://www.google.com/maps/search/?api=1&amp;query=${s.latitude},${s.longitude}" target="_blank" rel="noopener noreferrer"><circle cx="${x}" cy="${y}" r="12" fill="#285dba"/><text x="${x}" y="${y + 4}" text-anchor="middle" fill="white" font-size="10">${esc(s.stopNumber)}</text><title>${esc(s.address)}</title></a>`; }).join('')}</svg><p class="mut">Route overview. Click a numbered stop to open its location in Maps.</p>`;
  }
  $('op-route').onchange = renderRoute;
  async function loadRoutes() {
    $('op-load').disabled = true; $('op-status').textContent = 'Loading routes and dispatch status...';
    try {
      const day = $('op-date').value;
      const [data, dispatch] = await Promise.all([request('routes', { date: day }), request('dispatch', { date: day })]);
      routes = data.routes || []; $('op-route').replaceChildren(); routes.forEach((r, i) => $('op-route').add(new Option(r.driverName || r.driverSerial, i)));
      const changes = dispatch.routes?.changes;
      $('op-dispatch').innerHTML = `<div><b>Routes</b><span>${esc(dispatch.routes?.state || 'Unknown')}</span></div><div><b>Customer notifications</b><span>${esc(dispatch.notifications?.state || 'Unknown')}</span></div><div><b>Changes after sending</b><span>${esc(changes?.totalCnt ?? 0)}</span></div><div><b>Live date</b><span>${dispatch.live ? 'Yes' : 'No'}</span></div>`;
      $('op-status').textContent = `${routes.length} driver routes loaded for ${day}.`; renderRoute();
    } catch (error) { $('op-status').textContent = error.message; }
    finally { $('op-load').disabled = false; }
  }
  $('op-load').onclick = loadRoutes;
})();
