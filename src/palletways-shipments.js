const palletwaysApiShipments = delivery => (
  delivery?.carrier === 'Palletways' && Array.isArray(delivery.palletwaysShipments)
    ? delivery.palletwaysShipments
    : []
);

const palletwaysInactiveMappings = new Set(['inactive', 'historical', 'replaced']);

const palletwaysBookingShipments = delivery => palletwaysApiShipments(delivery).filter(shipment => {
  const mapping = String(shipment.mapping_status || '').trim().toLowerCase();
  return !palletwaysInactiveMappings.has(mapping);
});

const palletwaysNextDay = delivery =>
  String(delivery.deliveryMethodRaw || '').trim().toLowerCase() === 'palletways next day';

function palletwaysBookingState(delivery, shipment, field) {
  const value = shipment.booking_summary?.[field];
  if (palletwaysNextDay(delivery)) {
    return field === 'booked_in' && value === false ? 'not-applicable' : 'hidden';
  }
  if (value === true) return 'yes';
  if (value === false) return field === 'booked_in' ? 'not-yet' : 'no';
  return 'unknown';
}

function palletwaysBookingText(delivery, shipment, field) {
  const state = palletwaysBookingState(delivery, shipment, field);
  if (field === 'book_in_request') {
    if (state === 'yes') return 'Yes';
    if (state === 'no') return 'No';
    return '—';
  }
  if (state === 'not-applicable') return 'Not Applicable';
  if (state === 'not-yet') return 'Not Yet';
  if (state !== 'yes') return '—';
  const booking = shipment.booking_summary;
  const date = String(booking?.booking_date || '').trim();
  const time = String(booking?.booking_time || '').trim();
  return date ? [date, time].filter(Boolean).join(' · ') : 'Booked · Date unavailable';
}

function palletwaysBookingRows(delivery, field) {
  const shipments = palletwaysBookingShipments(delivery);
  if (!shipments.length) return [{identity: '', state: 'unknown', text: '—'}];
  return shipments.map(shipment => ({
    identity: shipments.length > 1 ? shipment.consignment_number || shipment.tracking_id || '—' : '',
    state: palletwaysBookingState(delivery, shipment, field),
    text: palletwaysBookingText(delivery, shipment, field),
  }));
}

function palletwaysBookingCell(delivery, field) {
  return palletwaysBookingRows(delivery, field).map(row =>
    `<span class="tracking-cell-line">${esc(row.text)}</span>${row.identity ? `<small class="tracking-cell-line mut">${esc(row.identity)}</small>` : ''}`
  ).join('');
}

function palletwaysBookingMatchesFilters(delivery, bookedIn, bookInRequest) {
  const shipments = palletwaysBookingShipments(delivery);
  if (!shipments.length) return !palletwaysNextDay(delivery) &&
    (!bookedIn || bookedIn === 'unknown') && (!bookInRequest || bookInRequest === 'unknown');
  return shipments.some(shipment =>
    (!bookedIn || palletwaysBookingState(delivery, shipment, 'booked_in') === bookedIn) &&
    (!bookInRequest || palletwaysBookingState(delivery, shipment, 'book_in_request') === bookInRequest)
  );
}

const palletwaysFacetStatuses = item => {
  if (Array.isArray(item.statusView?.carrierStatuses)) return item.statusView.carrierStatuses;
  try {
    const values = JSON.parse(item.palletwaysStatuses || '[]');
    if (Array.isArray(values) && values.length) return values;
  } catch {}
  return ['Status unavailable'];
};

function palletwaysFactMarkup(label, value) {
  return `<div><dt>${esc(label)}</dt><dd>${esc(value || '—')}</dd></div>`;
}

function palletwaysPortalDetailsMarkup(delivery, copyButton = () => '') {
  if (delivery.carrier !== 'Palletways') return '';
  const records = delivery.palletwaysDocumentRecords || [];
  const details = records.filter(record => record.details);
  if (!details.length) return palletwaysDetails(delivery, copyButton);
  return details.map(record => palletwaysDetails({
    ...delivery,
    trk: record.trackingId,
    palletwaysDetails: record.details,
  }, copyButton)).join('');
}

function trackingStatusMarkup(delivery) {
  const shipments = palletwaysApiShipments(delivery);
  if (usesSourceTrackingStatus() && fsrc === 'Palletways' && shipments.length) {
    return shipments.map(shipment => {
      const identity = shipments.length > 1
        ? `<small class="tracking-cell-line mut">${esc(shipment.consignment_number || shipment.tracking_id || '—')}</small>`
        : '';
      return `<div class="tracking-shipment-status">
        ${stat(shipment.palletways_status, shipment.palletways_status || 'Status unavailable')}
        ${identity}
      </div>`;
    }).join('');
  }
  return stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery));
}

function palletwaysStructuredValue(value) {
  if (value == null || value === '') return '<span class="mut">Not available</span>';
  if (Array.isArray(value)) {
    return value.length
      ? value.map(item => `<div class="qd-palletways-record">${palletwaysStructuredValue(item)}</div>`).join('')
      : '<span class="mut">None</span>';
  }
  if (typeof value === 'object') {
    const facts = Object.entries(value).map(([key, item]) =>
      `<div><dt>${esc(key.replace(/_/g, ' '))}</dt><dd>${palletwaysStructuredValue(item)}</dd></div>`);
    return `<dl>${facts.join('')}</dl>`;
  }
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  return esc(String(value));
}

function palletwaysFullDetailsMarkup(shipment) {
  const identity = shipment.tracking_id && shipment.consignment_number
    ? `data-tracking-id="${esc(shipment.tracking_id)}" data-consignment-number="${esc(shipment.consignment_number)}"`
    : '';
  const sections = Object.entries(shipment).filter(([key]) => key !== 'events').map(([key, value]) => {
    const label = key === 'historical_snapshot' ? 'Historical snapshot · separate from current data'
      : key.replace(/_/g, ' ');
    return `<details class="qd-palletways-api-section"><summary>${esc(label)}</summary>${palletwaysStructuredValue(value)}</details>`;
  }).join('');
  if (!identity) return sections;
  const records = [['events', 'Tracking notes'], ['events:historical', 'Historical tracking notes'], ['audit', 'Sync audit']]
    .map(([kind, label]) => `<details class="qd-palletways-api-section" ${identity} data-palletways-records="${kind}">
      <summary>${label}</summary>
      <button type="button" class="qd-text" data-palletways-load-records data-offset="0">Load ${label.toLowerCase()}</button>
      <div data-palletways-record-list></div>
    </details>`).join('');
  return sections + records;
}

document.addEventListener('click', async event => {
  const recordsButton = event.target.closest('[data-palletways-load-records]');
  if (recordsButton && !recordsButton.disabled) {
    const section = recordsButton.closest('[data-palletways-records]');
    const list = section?.querySelector('[data-palletways-record-list]');
    if (!section || !list) return;
    const [kind, source] = section.dataset.palletwaysRecords.split(':');
    const offset = Number(recordsButton.dataset.offset || 0);
    const base = `shipments/${encodeURIComponent(section.dataset.trackingId)}/${encodeURIComponent(section.dataset.consignmentNumber)}/${kind}`;
    const params = new URLSearchParams({limit: '50', offset: String(offset)});
    if (source) params.set('source', source);
    recordsButton.disabled = true;
    recordsButton.textContent = 'Loading…';
    try {
      const response = await fetch(`/api/atlas-palletways/${base}?${params}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || 'Records unavailable.');
      if (!list.isConnected) return;
      const items = Array.isArray(data.items) ? data.items : [];
      const markup = items.map(item => `<div class="qd-palletways-record">${palletwaysStructuredValue(item)}</div>`).join('');
      list.insertAdjacentHTML('beforeend', markup || (offset ? '' : '<p class="mut">No records available.</p>'));
      const nextOffset = offset + items.length;
      if (data.has_more && items.length) {
        recordsButton.dataset.offset = String(nextOffset);
        recordsButton.textContent = `Load more (${nextOffset}${Number.isInteger(data.total) ? ` of ${data.total}` : ''})`;
        recordsButton.disabled = false;
      } else recordsButton.remove();
    } catch (error) {
      recordsButton.textContent = error.message || 'Records unavailable.';
      recordsButton.disabled = false;
    }
    return;
  }
});
