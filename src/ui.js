const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

const esc = (value) =>
  String(value).replace(
    /[&<>"]/g,
    (char) =>
      ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
      })[char],
  );

function specialInstructionsMarkup(value) {
  const text = String(value || '');
  if (!text.trim()) return '\u2014';
  return `<button type="button" class="special-instructions-copy" data-copy-special-instructions="${esc(text)}" title="Copy special instructions" aria-label="Copy special instructions">${esc(text)}</button>`;
}

function canCopyOrderReference(value) {
  const reference = String(value || '').trim();
  return Boolean(reference) && !/^(?:replacements?|replacementorders?)$/.test(
    reference.toLowerCase().replace(/[^a-z0-9]/g, ''),
  );
}

function replacementBadge(delivery) {
  const kind = delivery.orderRelationKind || delivery.relatedKind;
  const reference = delivery.orderRef || delivery.orderReference;
  const replacementReference = Boolean(String(reference || '').trim()) && !canCopyOrderReference(reference);
  if (!replacementReference && !['Replacement', 'Later Replacement'].includes(kind)) return '';
  return `<span class="replacement-badge" aria-label="Replacement order"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 9a8 8 0 0 1 13-3l3 3M20 4v5h-5M20 15a8 8 0 0 1-13 3l-3-3M4 20v-5h5"/></svg><span>Replacement</span></span>`;
}

function creditRefundBadge(delivery) {
  if (!isCreditRefundRecord(delivery)) return '';
  return '<span class="replacement-badge credit-refund-badge" aria-label="Credit/Refund order"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><g class="refund-coin"><circle cx="12" cy="12" r="7"/><path d="M14 9h-3a1.5 1.5 0 0 0 0 3h2a1.5 1.5 0 0 1 0 3h-3M12 7.5v9"/></g><path class="refund-return-arrow" d="M20.5 8A9.5 9.5 0 0 0 5 4.5L2.5 7m0-4v4h4"/></svg><span>Credit/Refund</span></span>';
}

function toast(message, duration = 2200) {
  const element = document.createElement('div');
  element.className = 'toast';
  element.textContent = message;
  document.body.append(element);
  setTimeout(() => element.remove(), duration);
}

async function writeClipboard(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch (_) {
      // Clipboard permissions can be denied even when the API is available.
    }
  }

  return new Promise((resolve, reject) => {
    const focused = document.activeElement;
    const selection = window.getSelection();
    const ranges = selection
      ? Array.from({ length: selection.rangeCount }, (_, index) =>
          selection.getRangeAt(index).cloneRange(),
        )
      : [];
    const element = document.createElement('textarea');
    element.value = text;
    element.readOnly = true;
    element.style.cssText =
      'position:fixed;top:0;left:0;width:1px;height:1px;opacity:0;pointer-events:none;';
    (document.querySelector('dialog[open]') || document.body).append(element);

    try {
      element.focus({ preventScroll: true });
      element.select();
      if (!document.execCommand('copy')) throw new Error('Clipboard copy failed');
      resolve();
    } catch (error) {
      reject(error);
    } finally {
      element.remove();
      if (focused?.isConnected) focused.focus({ preventScroll: true });
      if (selection) {
        selection.removeAllRanges();
        ranges.forEach((range) => selection.addRange(range));
      }
    }
  });
}

function copyText(text, message = 'Copied') {
  writeClipboard(text)
    .then(() => toast(message))
    .catch(() => toast('Could not copy. Please copy it manually.'));
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const hd = (value) =>
  value
    ? new Date(`${value}T12:00:00`).toLocaleDateString('en-GB', {
        day: 'numeric',
        month: 'short',
        year: 'numeric',
      })
    : '';

const fmtMD = (value) => {
  const [monthDay, time] = value.split(' ');
  const [month, day] = monthDay.split('-');
  return `${+day} ${MONTHS[+month - 1]}${time ? ` · ${time}` : ''}`;
};

const yesterdayKey = () => {
  const date = new Date(`${T}T12:00:00`);
  date.setDate(date.getDate() - 1);
  return date.toISOString().slice(5, 10);
};

const dayLabel = (value) => {
  const key = value.slice(0, 5);
  if (key === T.slice(5)) return 'Today';
  if (key === yesterdayKey()) return 'Yesterday';
  return key;
};

const fmtDay = (value) => {
  const label = dayLabel(value);
  const date = /^\d\d-\d\d$/.test(label) ? fmtMD(label) : label;
  return `${date} · ${value.slice(6)}`;
};

const fmtLogTime = (value) =>
  /^\d{4}-\d{2}-\d{2}$/.test(String(value))
    ? hd(value)
    : /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(String(value))
      ? new Date(value).toLocaleString('en-GB', {
          day: 'numeric',
          month: 'short',
          year: 'numeric',
          hour: '2-digit',
          minute: '2-digit',
        })
      : fmtDay(value);

const clockAmPm = (value) => {
  const match = String(value || '').match(/^(\d{2}):(\d{2})$/);
  if (!match) return String(value || '');
  const hour = Number(match[1]);
  if (hour > 23) return String(value);
  return `${String(hour % 12 || 12).padStart(2, '0')}:${match[2]} ${hour < 12 ? 'AM' : 'PM'}`;
};

const optimoTime = (value) => {
  const raw =
    typeof value === 'object' && value
      ? value.localTime ||
        value.utcTime ||
        (Number.isFinite(value.unixTimestamp)
          ? new Date(value.unixTimestamp * 1000).toISOString()
          : '')
      : String(value || '');
  const match = raw.match(/^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})/);
  return match ? `${hd(match[1])}, ${clockAmPm(match[2])}` : raw || '—';
};

const optimoClock = (value) => {
  const raw =
    typeof value === 'object' && value
      ? value.localTime || value.utcTime || ''
      : String(value || '');
  const clock = raw.match(/[T ](\d{2}:\d{2})/)?.[1];
  return clock ? clockAmPm(clock) : '';
};

const detailDateTime = (value) => {
  if (!value) return '';
  const raw = typeof value === 'object' ? value.localTime || value.utcTime || '' : String(value);
  if (!raw && typeof value === 'object') return optimoTime(value);
  if (/^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(raw)) return optimoTime(value);
  if (/^\d{4}-\d{2}-\d{2}$/.test(raw)) return hd(raw);
  return raw;
};

function palletwaysDetails(delivery, copyButton = () => '') {
  const details = delivery.carrier === 'Palletways' ? delivery.palletwaysDetails : null;

  if (!details) return '';

  const list = (value) => {
    if (Array.isArray(value)) {
      return value;
    }

    return value ? [value] : [];
  };

  const palletText = list(details.pallets)
    .map((item) => {
      if (item && typeof item === 'object') {
        return item.Barcode || item.barcode || item.ID || item.id || '';
      }

      return String(item || '');
    })
    .filter(Boolean)
    .join(', ');

  const billUnitText = list(details.billUnits)
    .map((item) => {
      if (!item || typeof item !== 'object') {
        return String(item || '');
      }

      const type = item.Type || item.type || '';

      const amount = item.Amount || item.amount || '';

      return [type, amount ? `× ${amount}` : ''].filter(Boolean).join(' ');
    })
    .filter(Boolean)
    .join(', ');

  const dueText = [
    details.dueDate ? hd(details.dueDate) : '',
    details.dueTime ? clockAmPm(String(details.dueTime).slice(0, 5)) : '',
  ]
    .filter(Boolean)
    .join(' · ');

  const fact = (label, value, field = '') => {
    const text = String(value ?? '').trim();

    if (!text) return '';

    return `
      <div>
        <dt>${esc(label)}</dt>
        <dd>
          ${esc(text)}
          ${field ? copyButton(field, text, label.toLowerCase()) : ''}
        </dd>
      </div>
    `;
  };

  const facts = [
    fact('Consignment number', details.consignmentNumber, 'consignmentNumber'),

    fact('Tracking ID', details.trackingId || delivery.trk, 'trackingNumber'),

    fact('Customer reference', details.customerRef),

    fact('Delivery service', details.deliveryService, 'deliveryService'),

    fact('Classification', details.classification),

    fact('Weight', details.weight),

    fact('Lifts', details.lifts),

    fact('Collection depot', details.collectionDepot),

    fact('Delivery depot', details.deliveryDepot),

    fact('Due', dueText),

    fact('Booked in', details.bookedIn),

    fact('Book-in request', details.bookInRequest),

    fact('Insurance', details.insurance),

    fact('Booking contact', details.bookInContactName),

    fact('Booking reference', details.bookInReference),

    fact('Pallet', palletText),

    fact('Bill units', billUnitText),

    fact('Collection address', details.collectionAddress),

    fact('Collection postcode', details.collectionPostcode),

    fact('Collection contact', details.collectionContact),

    fact('Collection telephone', details.collectionTelephone),

    fact('Delivery address', details.deliveryAddress),

    fact('Delivery postcode', details.deliveryPostcode),

    fact('Telephone', details.deliveryTelephone),
    fact('Delivery contact', details.deliveryContact),
    fact('Instructions', details.manifestNote),
  ].filter(Boolean);
  const portal = delivery.palletwaysPortal || {};

  const invoiceText = Array.isArray(portal.invoices)
    ? portal.invoices
        .map((item) => [item.number, item.date, item.type, item.value].filter(Boolean).join(' · '))
        .join(', ')
    : '';

  if (invoiceText) {
    facts.push(fact('Palletways invoice', invoiceText));
  }
  if (!facts.length) {
    return '';
  }

  return `
    <section
      class="qd-block qd-order-facts qd-provider"
      aria-label="Palletways consignment details"
    >
      <div class="qd-title-row">
        <div class="qd-title">
          ${ico('truck', 18, 1.9)}
          <h3>
            Palletways consignment details
          </h3>
        </div>
      </div>

      <dl class="qd-facts">
        ${facts.join('')}
      </dl>
    </section>
  `;
}

function palletwaysDocumentInfo(delivery) {
  if (delivery?.carrier !== 'Palletways') {
    return {
      tracking: '',
      consignment: '',
      podEvent: null,
      hasPod: false,
      hasLabel: false,
      hasAny: false,
    };
  }

  const details = delivery.palletwaysDetails || {};

  const tracking = String(details.trackingId || delivery.trk || '').trim();

  const consignment = String(details.consignmentNumber || '').trim();

  const events = Array.isArray(delivery.palletwaysEvents) ? delivery.palletwaysEvents : [];

  const podEvent =
    [...events]
      .reverse()
      .find(
        (item) =>
          String(item.group || '').toUpperCase() === 'POD' &&
          String(item.type || '').toUpperCase() === 'POD',
      ) || null;

  const hasPod = Boolean(
    (podEvent || delivery.palletwaysDocuments?.podAvailable) && /^\d{11}$/.test(tracking),
  );

  const hasLabel = Boolean(consignment);

  return {
    tracking,
    consignment,
    podEvent,
    hasPod,
    hasLabel,
    hasAny: hasPod || hasLabel,
  };
}

function documentViewButton(url, title) {
  return `<a class="qd-document-open" href="${esc(url)}" target="_blank" rel="noopener noreferrer" title="View online" aria-label="View ${esc(title)} online"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 3h6v6M10 14 21 3"/><path d="M21 14v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h6"/></svg></a>`;
}

const unavailablePalletwaysPhotos = new Set();

function settlePalletwaysPreview(event) {
  const preview = event.target;
  if (!preview.matches?.('[data-palletways-preview], [data-document-preview]')) return;
  const container = preview.closest('[data-preview-state]');
  if (!container) return;
  const failed = event.type === 'error' || (preview.tagName === 'IMG' && !preview.naturalWidth);
  if (failed && preview.dataset.palletwaysFilename) {
    unavailablePalletwaysPhotos.add(preview.dataset.palletwaysFilename);
    const documents = preview.closest('.qd-palletways-documents');
    preview.closest('.qd-amazon-doc-card')?.remove();
    if (documents && !documents.querySelector('[data-palletways-filename]')) {
      const empty = documents.querySelector('[data-palletways-photo-empty]');
      if (empty) empty.hidden = false;
    }
    return;
  }
  container.dataset.previewState = failed ? 'error' : 'ready';
  container.setAttribute('aria-busy', 'false');
}

function shipmentDocumentCard(title, url, preview, description, downloadUrl = `${url}?download=1`) {
  return `
    <article class="qd-amazon-doc-card">
      <h4><a href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(title)}">${esc(title)}</a>${documentViewButton(url, title)}</h4>
      <a class="qd-amazon-doc-preview" data-preview-state="${/<(?:img|iframe)\b/.test(preview) ? 'loading' : 'ready'}" aria-busy="${/<(?:img|iframe)\b/.test(preview)}" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open ${esc(title)}">
        <span class="qd-document-loading" role="status" aria-label="Loading ${esc(title)}"><span class="qd-document-donut" aria-hidden="true"></span></span>
        <span class="qd-document-error" role="status">Preview unavailable. Click to open.</span>
        ${preview}
      </a>
      <div class="qd-amazon-doc-footer">
        <span>${esc(description)}</span>
        <a class="qd-amazon-doc-download" href="${esc(downloadUrl)}" aria-label="Download ${esc(title)}">
          ${ico('download', 15)} Download
        </a>
      </div>
    </article>`;
}

function xdpDocuments(delivery) {
  if (delivery?.carrier !== 'XDP') return '';
  const documents = [
    ...new Set(
      (delivery.xdpDocuments || []).filter((url) =>
        /^https:\/\/xdp\.sysx\.co\.uk\/pod\/view\/\d+\/[A-Za-z0-9_+=%-]+$/.test(url),
      ),
    ),
  ];
  if (!documents.length)
    return '<section class="qd-documents-empty" role="status">No document found</section>';
  return `<section class="qd-block qd-pod qd-palletways-documents qd-xdp-documents" aria-label="Proof of delivery">
    <div class="qd-title-row"><div class="qd-title">${ico('note', 18, 1.9)}<h3>Proof of delivery</h3></div></div>
    <div class="qd-amazon-doc-grid">${documents
      .map((url, index) => {
        const title = documents.length > 1 ? `Shipment photo ${index + 1}` : 'Shipment photo';
        const proxy = `/api/xdp/document?${new URLSearchParams({ order: delivery.order || delivery.id, index })}`;
        return shipmentDocumentCard(
          title,
          url,
          `<img class="qd-palletways-photo-image" data-document-preview src="${esc(proxy)}" loading="lazy" alt="${esc(title)}">`,
          'XDP image',
          `${proxy}&download=1`,
        );
      })
      .join('')}</div>
  </section>`;
}

function palletwaysDocuments(delivery) {
  if (delivery?.carrier !== 'Palletways') return '';
  const info = palletwaysDocumentInfo(delivery);
  const portal = delivery.palletwaysPortal || {};
  const media = [
    ...new Map(
      [
        ...(Array.isArray(delivery.palletwaysPhotos) ? delivery.palletwaysPhotos : []),
        ...(Array.isArray(portal.media) ? portal.media : []),
      ]
        .filter((item) => item?.filename)
        .map((item) => [item.filename, item]),
    ).values(),
  ];
  const cards = [];
  const card = shipmentDocumentCard;

  const photos = media.filter(
    (item) =>
      !/\.(tif|tiff)$/i.test(item.filename) && !unavailablePalletwaysPhotos.has(item.filename),
  );
  photos.forEach((item, index) => {
    const url = `/api/palletways/media/${encodeURIComponent(item.filename)}`;
    const title = photos.length > 1 ? `Shipment photo ${index + 1}` : 'Shipment photo';
    const preview = `<img class="qd-palletways-photo-image" data-palletways-preview data-palletways-filename="${esc(item.filename)}" src="${esc(url)}" loading="lazy" alt="${esc(title)}">`;
    cards.push(card(title, url, preview, 'Palletways image'));
  });

  if (info.hasPod) {
    const url = `/api/palletways/pod/${encodeURIComponent(info.tracking)}`;
    cards.push(
      card(
        'Delivery note',
        url,
        `<iframe title="Delivery note preview" data-palletways-preview src="${esc(url)}#page=1&toolbar=0&navpanes=0" loading="lazy" tabindex="0"></iframe>`,
        'PDF document',
      ),
    );
  }
  if (info.hasLabel) {
    const url = `/api/palletways/label/${encodeURIComponent(info.consignment)}`;
    cards.push(
      card(
        'Shipping label',
        url,
        `<iframe title="Shipping label preview" data-palletways-preview src="${esc(url)}#page=1&toolbar=0&navpanes=0" loading="lazy" tabindex="0"></iframe>`,
        `Consignment ${info.consignment}`,
      ),
    );
  }
  const photoState = delivery.palletwaysPortalLoading
    ? '<p class="mut" role="status">Loading shipment photos from Palletways…</p>'
    : delivery.palletwaysPortalError
      ? `<p class="mut" role="alert">${esc(delivery.palletwaysPortalError)}</p>`
      : '';
  const retry = `<button class="qd-text" type="button" data-detail-action="refresh-palletways-photos" ${delivery.palletwaysPortalLoading ? 'disabled' : ''}>Refresh photos</button>`;
  return `<section class="qd-block qd-pod qd-palletways-documents" aria-label="Palletways documents">
    <div class="qd-title-row"><div class="qd-title">${ico('note', 18, 1.9)}<h3>Palletways documents</h3></div></div>
    ${photoState}${retry}
    <p class="mut" data-palletways-photo-empty ${photos.length || delivery.palletwaysPortalLoading ? 'hidden' : ''}>No shipment photos available for this tracking ID.</p>
    <div class="qd-amazon-doc-grid">${cards.join('')}</div>
  </section>`;
}

function deliveryWindow(delivery) {
  const start = String(delivery.deliveryWindowStartAt || '');
  const end = String(delivery.deliveryWindowEndAt || '');
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(start) && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(end)) {
    const startDate = start.slice(0, 10);
    const endDate = end.slice(0, 10);
    const startTime = start.slice(11, 16);
    const endTime = end.slice(11, 16);
    return {
      short: `${clockAmPm(startTime)}–${clockAmPm(endTime)}`,
      full: `${hd(startDate)}, ${clockAmPm(startTime)} – ${startDate === endDate ? '' : `${hd(endDate)}, `}${clockAmPm(endTime)}`,
    };
  }
  if (/^\d{2}:\d{2}\s*[-–]\s*\d{2}:\d{2}$/.test(String(delivery.win || ''))) {
    const short = delivery.win
      .replace(/\s*[-–]\s*/, '–')
      .split('–')
      .map(clockAmPm)
      .join('–');
    return { short, full: `${delivery.date ? `${hd(delivery.date)}, ` : ''}${short}` };
  }
  if (delivery.eta) {
    const eta = String(delivery.eta);
    const match = eta.match(/^(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2})/);
    return {
      short: `ETA ${match ? clockAmPm(match[2]) : clockAmPm(eta)}`,
      full: match ? `ETA ${hd(match[1])}, ${clockAmPm(match[2])}` : `ETA ${clockAmPm(eta)}`,
    };
  }
  return { short: 'TBD', full: 'Not provided' };
}

const initialState = { today: localDateKey(), deliveries: [], activity: [], integrations: [] };
DeliveryStore.hydrate(initialState);

const T = initialState.today;
let D = DeliveryStore.deliveries();
let S = DeliveryStore.integrations();
const EXTERNAL_CARRIERS = APP_CONFIG.carriers.external;

const DELIVERY_REASON_COPY = {
  'Access restricted': {
    label: 'Unable to access property',
    detail: 'Driver could not enter the property or delivery area.',
  },
};

const deliveryReason = (reason) =>
  DELIVERY_REASON_COPY[reason] || {
    label: reason || '',
    detail: '',
  };

const get = (id) => DeliveryStore.find(id);
const carName = (carrier) =>
  carrier === 'Own van' ? 'Own van' : EXTERNAL_CARRIERS[carrier] || carrier;
const SELF_DELIVERY_GROUP = 'Own van / Self Delivery';
const SELF_DELIVERY_CARRIERS = ['Own van', 'Self Delivery'];
const matchesDeliveryCarrier = (carrier, filter) =>
  !filter ||
  (filter === SELF_DELIVERY_GROUP ? SELF_DELIVERY_CARRIERS.includes(carrier) : carrier === filter);

const isTrackingPage = () => ['Deliveries', 'Replacement', 'Refund'].includes(page);
const trackingOrderKind = () => page === 'Replacement' ? 'replacement' : page === 'Refund' ? 'refund' : '';

const PAGE_LABELS = {
  Deliveries: 'Tracking',
  'Collective Note': 'Collection Notes',
  Integrations: 'Integration & Data Trafficking',
};
const PAGE_URL = APP_CONFIG.routes;
let page = PAGE_URL[document.body.dataset.page] ? document.body.dataset.page : 'Deliveries';
let trackingScope =
  isTrackingPage() && new URLSearchParams(location.search).get('view') === 'today'
    ? 'today'
    : '';
// Give the initial page (including / and index.html) an explicit history identity.
try {
  history.replaceState({ ...history.state, page }, '', location.href);
} catch {}
let sel = null;
let q = '';
let fs = '';
let fstore = '';
let fsrc = '';
let dashboardWidgetFilter =
  page === 'Deliveries' ? new URLSearchParams(location.search).get('dashboard_widget') || '' : '';
let trackingWidgetFacets = null;
if (dashboardWidgetFilter) {
  fsrc = new URLSearchParams(location.search).get('carrier') || '';
  fstore = compactFilter(new URLSearchParams(location.search).getAll('store'));
}
let fmethod = '';
let fclassification = [];
let fbookedIn = '';
let fbookInRequest = '';
let fd = '';
let ft = '';
let dq = '';
let dashboardSearchTimer = null;

function syncSelectedTrackingRow() {
  document.querySelectorAll('.tracking-row[data-delivery-id]').forEach((row) => {
    const selected = Boolean(sel) && row.dataset.deliveryId === sel;
    row.classList.toggle('is-selected', selected);
    if (selected) row.setAttribute('aria-current', 'true');
    else row.removeAttribute('aria-current');
  });
}

const ICON = {
  Replacement: '<path d="M20 7H4m0 0 4-4M4 7l4 4M4 17h16m0 0-4-4m4 4-4 4"/>',
  Return: '<path d="M9 10 4 5l5-5M4 5h10a7 7 0 0 1 0 14h-3" transform="translate(0 2)"/>',
  'Free Return': '<path d="m8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12h-3"/><path d="m14 5 2 2 4-4"/>',
  'Manufacture Claims': '<path d="M3 21V9l6 3V7l6 3V3h4l2 18ZM7 17h1m4 0h1m4 0h1"/>',
  'Logistics Claims':
    '<path d="M3 17V5h12v12M15 9h4l3 4v4h-3M7 17h8"/><circle cx="5" cy="18" r="2"/><circle cx="17" cy="18" r="2"/><path d="M9 8v4m0 2h.01"/>',
  Refund:
    '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 9h20m-8 4-3 3 3 3m-3-3h7"/>',
  Guidance:
    '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 3H20v19H6.5A2.5 2.5 0 0 1 4 19.5v-14A2.5 2.5 0 0 1 6.5 3Z"/><path d="M8 7h8M8 11h6"/>',
  'Collective Note':
    '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z"/><path d="M14 2v6h6M8 13h8M8 17h6"/>',
  Dashboard:
    '<rect width="7" height="9" x="3" y="3" rx="1"/><rect width="7" height="5" x="14" y="3" rx="1"/><rect width="7" height="9" x="14" y="12" rx="1"/><rect width="7" height="5" x="3" y="16" rx="1"/>',
  Deliveries:
    '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
  'Van Deliveries':
    '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
  'Failed Deliveries':
    '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
  Integrations:
    '<path d="M12 22v-5"/><path d="M9 8V2"/><path d="M15 8V2"/><path d="M18 8v5a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4V8Z"/>',
  Settings:
    '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
  search: '<circle cx="10.5" cy="10.5" r="7.5"/><path d="M16 16l5 5"/>',
  filter:
    '<line x1="21" x2="14" y1="4" y2="4"/><line x1="10" x2="3" y1="4" y2="4"/><line x1="21" x2="12" y1="12" y2="12"/><line x1="8" x2="3" y1="12" y2="12"/><line x1="21" x2="16" y1="20" y2="20"/><line x1="12" x2="3" y1="20" y2="20"/><line x1="14" x2="14" y1="2" y2="6"/><line x1="8" x2="8" y1="10" y2="14"/><line x1="16" x2="16" y1="18" y2="22"/>',
  sort: '<path d="m21 16-4 4-4-4"/><path d="M17 20V4"/><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/>',
  more: '<circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>',
  chevdown: 'm6 9 6 6 6-6',
  clipboardcheck:
    '<rect width="14" height="18" x="5" y="3" rx="2"/><path d="M9 5h6"/><path d="m9 14 2 2 4-4"/>',
  right: 'm9 18 6-6-6-6',
  back: '<path d="m12 19-7-7 7-7"/><path d="M19 12H5"/>',
  next: '<path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>',
  alert:
    '<circle cx="12" cy="12" r="10"/><line x1="12" x2="12" y1="8" y2="12"/><line x1="12" x2="12.01" y1="16" y2="16"/>',
  pin: '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0"/><circle cx="12" cy="10" r="3"/>',
  phone:
    '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z"/>',
  cal: '<path d="M8 2v4"/><path d="M16 2v4"/><rect width="18" height="18" x="3" y="4" rx="2"/><path d="M3 10h18"/><path d="M8 14h.01"/><path d="M12 14h.01"/><path d="M16 14h.01"/><path d="M8 18h.01"/><path d="M12 18h.01"/><path d="M16 18h.01"/>',
  clock: '<circle cx="12" cy="12" r="10"/><path d="M12 6v6h4"/>',
  bell: '<path d="M10.268 21a2 2 0 0 0 3.464 0"/><path d="M3.262 15.326A1 1 0 0 0 4 17h16a1 1 0 0 0 .74-1.673C19.41 13.956 18 12.499 18 8A6 6 0 0 0 6 8c0 4.499-1.411 5.956-2.738 7.326"/>',
  check: '<path d="M20 6 9 17l-5-5"/>',
  ok: '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
  chat: '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
  send: '<path d="M14.536 21.686a.5.5 0 0 0 .937-.024l6.5-19a.496.496 0 0 0-.635-.635l-19 6.5a.5.5 0 0 0-.024.937l7.93 3.18a2 2 0 0 1 1.112 1.11z"/><path d="m21.854 2.147-10.94 10.939"/>',
  truck:
    '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/><path d="M15 18H9"/><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/><circle cx="17" cy="18" r="2"/><circle cx="7" cy="18" r="2"/>',
  pkg: '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/>',
  pkgx: '<path d="M11 21.73a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73z"/><path d="M12 22V12"/><path d="m3.3 7 7.703 4.734a2 2 0 0 0 1.994 0L20.7 7"/><path d="m7.5 4.27 9 5.15"/><path d="m9 15 6 6"/><path d="m15 15-6 6"/>',
  mail: '<rect width="20" height="16" x="2" y="4" rx="2"/><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7"/>',
  note: '<path d="M15 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6"/><path d="M9 17h6"/>',
  plus: '<path d="M5 12h14"/><path d="M12 5v14"/>',
  download:
    '<path d="M12 15V3"/><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/>',
  print:
    '<path d="M6 9V3h12v6"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="7" rx="1"/><path d="M18 12h.01"/>',
  pencil:
    '<path d="M21.174 6.812a1 1 0 0 0-3.986-3.987L3.842 16.174a2 2 0 0 0-.5.83l-1.321 4.352a.5.5 0 0 0 .623.622l4.353-1.32a2 2 0 0 0 .83-.497z"/><path d="m15 5 4 4"/>',
  image:
    '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/>',
  circ: '<circle cx="12" cy="12" r="10"/>',
  x: '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
  user: '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  calplus:
    '<path d="M8 2v4"/><path d="M16 2v4"/><path d="M21 13V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h8"/><path d="M3 10h18"/><path d="M16 19h6"/><path d="M19 16v6"/>',
  copy: '<rect width="14" height="14" x="8" y="8" rx="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  link: '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>',
};

const ANIMATED_TRUCK_BODY = `
  <g class="ai-truck-speed" aria-hidden="true">
    <line x1="0" y1="8" x2="5" y2="8"/>
    <line x1="-1" y1="11" x2="6" y2="11"/>
    <line x1="0" y1="14" x2="4" y2="14"/>
  </g>
  <g class="ai-truck-body">
    <path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2"/>
    <path d="M15 18H9"/>
    <path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14"/>
  </g>
  <g class="ai-truck-wheel ai-truck-wheel-left">
    <circle cx="7" cy="18" r="2"/>
    <line x1="7" y1="16.5" x2="7" y2="19.5" stroke-width="1.45"/>
    <line x1="5.5" y1="18" x2="8.5" y2="18" stroke-width="1.45"/>
  </g>
  <g class="ai-truck-wheel ai-truck-wheel-right">
    <circle cx="17" cy="18" r="2"/>
    <line x1="17" y1="16.5" x2="17" y2="19.5" stroke-width="1.45"/>
    <line x1="15.5" y1="18" x2="18.5" y2="18" stroke-width="1.45"/>
  </g>`;

const ANIMATED_ICON_BODY = {
  search:
    '<circle class="ai-search-ring" cx="10.5" cy="10.5" r="7.5"/><path class="ai-search-handle" d="M16 16l5 5"/>',
  copy: '<rect class="ai-copy-front" width="14" height="14" x="8" y="8" rx="2"/><path class="ai-copy-back" d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/>',
  truck: ANIMATED_TRUCK_BODY,
  'Van Deliveries': ANIMATED_TRUCK_BODY,
};

const iconToken = (name) =>
  String(name)
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/(^-|-$)/g, '');

const ico = (name, size = 20, strokeWidth = 1.75) => {
  const shape = (ANIMATED_ICON_BODY[name] || ICON[name] || '').trim();
  const body = shape.startsWith('<') ? shape : `<path d="${shape}"/>`;
  const token = iconToken(name);
  return `<svg class="ic2 ai-icon ai-icon-${token}" data-ai-icon="${token}" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
};

const STATUS_STYLE = {
  'Other Status': ['cn', 'circ'],
  'Next Stop': ['am', 'truck'],
  Awaiting: ['uns', 'circ'],
  'Status unverified': ['cn', 'circ'],
  Unscheduled: ['uns', 'circ'],
  Unassigned: ['cn', 'circ'],
  Scheduled: ['sc', 'clock'],
  'Out for Delivery': ['sc', 'truck'],
  Delivered: ['ok', 'check'],
  Failed: ['bad', 'Failed Deliveries'],
  Rejected: ['bad', 'alert'],
  Lost: ['bad', 'alert'],
  Cancelled: ['cn', 'x'],
  Return: ['am', 'alert'],
  'Follow-up Required': ['bad', 'alert'],
  Contacted: ['am', 'phone'],
  Closed: ['cn', 'x'],
  Connected: ['ok', 'check'],
  Error: ['bad', 'alert'],
  Stale: ['am', 'alert'],
};

const chip = (className, _icon, label) => `<span class="stx ${className}">${esc(label)}</span>`;

const stat = (status, label) => {
  const displayStatus = trackingStatus(status) || status;
  const [className, icon] = STATUS_STYLE[displayStatus] || ['sc', 'clock'];
  return chip(className, icon, label || displayStatus);
};

const OW_STATUS_DESCRIPTION = Object.freeze({
  W: 'Awaiting despatch',
  K: 'Picking note printed but not picked',
  H: 'On hold',
  P: 'Partially despatched',
  I: 'Invoice waiting to be printed',
  C: 'Completed',
  X: 'Cancelled',
  S: 'Scheduled',
  A: 'Awaiting conversion',
  U: 'Paused',
  Y: 'Pre-auth pending',
});

const owStatusDescription = (raw) =>
  OW_STATUS_DESCRIPTION[
    String(raw || '')
      .trim()
      .toUpperCase()
  ] || String(raw || '').trim();

const amazonStatusLabel = (value) =>
  String(value).toUpperCase() === 'READY_FOR_RECEIVE'
    ? 'Ready To Receive'
    : String(value)
        .toLowerCase()
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (letter) => letter.toUpperCase());

const depotDelayLabel = (delivery) => {
  const stay = delivery?.palletwaysDepotStay;
  const active = !['Delivered', 'Cancelled', 'Return'].includes(delivery?.st);
  const overdue = Date.now() - Date.parse(stay?.arrivedAt) > 72 * 3600000;
  return delivery?.carrier === 'Palletways' && stay?.verified && active && overdue
    ? 'At Depot 3> Days'
    : '';
};

const palletwaysDeliveryConflict = (delivery) =>
  delivery?.carrier === 'Palletways' &&
  String(delivery.palletwaysSheetStatus || '').trim().toLowerCase() === 'delivered' &&
  ['Failed', 'Rejected', 'Lost'].includes(trackingStatus(delivery.st));

const palletwaysSpecificStatus = (value) => {
  const status = String(value || '').trim();
  return status.toLowerCase() === 'palletways not assigned' ? 'Unscheduled' : status;
};

const usesGlobalTrackingStatus = () => page === 'Deliveries' && !fsrc;
const isOwCancelledVan = delivery => {
  const category = String(delivery.salesActivityDetails?.['Order Category'] || '').trim().toLowerCase();
  if (category === 'credit/refund' || String(delivery.orderRelationKind || delivery.relatedKind || '').trim().toLowerCase() === 'credit/refund') return false;
  const method = String(delivery.deliveryMethodRaw || '').trim().toLowerCase();
  if (method !== 'to be cancelled' && category !== 'cancelled') return false;
  const methods = ['own van', 'own delivery', 'standard van delivery', 'next day van delivery'];
  return methods.includes(method) || (!method && delivery.carrier === 'Own van') ||
    (method === 'to be cancelled' && methods.includes(String(delivery.cancelledFromDeliveryMethod || '').trim().toLowerCase()));
};
const GLOBAL_TRACKING_STATUSES = new Set(['Other Status', 'Unscheduled', 'Scheduled', 'Out for Delivery',
  'Next Stop', 'Delivered', 'Failed', 'Rejected', 'Lost', 'Cancelled', 'Return', 'Unassigned']);
const globalStatusCategory = value => {
  const normalized = trackingStatus(String(value || '').trim());
  return GLOBAL_TRACKING_STATUSES.has(normalized) ? normalized : 'Other Status';
};
const globalOwStatus = value => ({P:'Scheduled', S:'Scheduled', C:'Delivered', X:'Cancelled',
  SCHEDULED:'Scheduled', DELIVERED:'Delivered', COMPLETE:'Delivered', COMPLETED:'Delivered',
  FAILED:'Failed', 'FAILED DELIVERY':'Failed', 'OUT FOR DELIVERY':'Out for Delivery',
  REJECTED:'Rejected', RETURN:'Return'})[String(value || '').trim().toUpperCase()] || 'Unscheduled';
const overallTrackingStatus = delivery => {
  if (delivery.overallStatus) return globalStatusCategory(delivery.overallStatus);
  const stored = delivery.st || delivery.status;
  const category = String(delivery.salesActivityDetails?.['Order Category'] || delivery.orderCategory ||
    delivery.orderRelationKind || delivery.relatedKind || '').trim().toLowerCase();
  if (['Palletways', 'XDP'].includes(delivery.carrier) && category === 'cancelled') return 'Cancelled';
  const method = String(delivery.deliveryMethodRaw || delivery.classification || '').trim().toLowerCase();
  if (delivery.carrier === 'AMZ') {
    const raw = String(delivery.amazonSheetStatus || delivery.amazonStatus || '').trim().toUpperCase();
    return raw ? ({READY_FOR_RECEIVE:'Scheduled', IN_TRANSIT:'Scheduled', OUT_FOR_DELIVERY:'Out for Delivery',
      DELIVERED:'Delivered', DELIVERY_ATTEMPTED:'Failed', UNDELIVERABLE:'Failed', REJECTED:'Rejected',
      LOST:'Lost', RETURNED_TO_SELLER:'Cancelled', RETURNED:'Return', AWAITING_CUSTOMER_PICKUP:'Other Status',
      PICKUP_CANCELLED:'Other Status', CARRIER_CANCELLED_PICKUP:'Other Status'})[raw] || 'Other Status'
      : globalStatusCategory(stored);
  }
  if (delivery.carrier === 'Palletways') {
    const raw = String(delivery.palletwaysSheetStatus || '').trim().toUpperCase();
    const mapped = ({'PALLETWAYS NOT ASSIGNED':'Unscheduled', UNSCHEDULED:'Unscheduled',
      'CONSIGNMENT CREATED':'Unscheduled', SCHEDULED:'Scheduled', 'IN TRANSIT':'Scheduled',
      'OUT FOR DELIVERY':'Out for Delivery', DELIVERED:'Delivered', RETURN:'Return',
      'PALLETWAYS LOOK UP FAILED':'Unassigned'})[raw];
    if (mapped) return mapped;
    if (method === 'on hold - tbc') return 'Unassigned';
    if (['Failed', 'Rejected', 'Lost'].includes(stored)) return stored;
    if (raw || delivery.palletwaysSheetMatched) return 'Other Status';
    return globalOwStatus(delivery.rawStatus);
  }
  if (delivery.carrier === 'XDP') {
    const raw = String(delivery.xdpStatus || '').trim().toUpperCase().replace(/[_\s]+/g, ' ');
    const mapped = ({BOOKING:'Unscheduled', UNSCHEDULED:'Unscheduled', SCHEDULED:'Scheduled', DELIVERY:'Scheduled',
      'OUT FOR DELIVERY':'Out for Delivery', 'NEXT STOP':'Next Stop', DELIVERED:'Delivered', DAMAGE:'Failed',
      DELETE:'Failed', 'NOT RECEIVED':'Failed', FAILED:'Failed', REJECTED:'Rejected', LOST:'Lost',
      SMS:'Other Status', EMAIL:'Other Status', CREATE:'Other Status', AWAITING:'Other Status'})[raw];
    if (mapped) return mapped;
    if (method === 'on hold - tbc') return 'Unassigned';
    if (String(delivery.rawStatus || '').trim().toUpperCase() === 'RETURN') return 'Return';
    return raw ? 'Other Status' : globalStatusCategory(stored);
  }
  return globalStatusCategory(stored);
};
const isGlobalException = delivery => Boolean(delivery) &&
  ['Failed', 'Rejected', 'Lost'].includes(overallTrackingStatus(delivery));

const palletwaysOwFallback = (delivery) => {
  if (delivery.palletwaysSheetMatched || palletwaysSpecificStatus(delivery.palletwaysSheetStatus)) return '';
  return String(delivery.rawStatus || '').trim();
};

const carrierBadgeStatus = (delivery) => {
  if (isCreditRefundRecord(delivery)) return {'refund:complete': 'Delivered', 'refund:cancelled': 'Cancelled', 'refund:not-yet': 'Scheduled'}[refundStatusValue(delivery)];
  if (page === 'Failed Deliveries') return overallTrackingStatus(delivery);
  if (usesGlobalTrackingStatus()) return overallTrackingStatus(delivery);
  if (isTrackingPage() && fsrc === 'Palletways' && delivery?.carrier === 'Palletways') {
    const sheetStatus = palletwaysSpecificStatus(delivery.palletwaysSheetStatus);
    return trackingStatus(sheetStatus) || palletwaysOwFallback(delivery);
  }
  return delivery.st;
};

const carrierStatusLabel = (delivery) => {
  if (isCreditRefundRecord(delivery)) return refundStatusLabel(refundStatusValue(delivery));
  if (usesGlobalTrackingStatus() && ['Palletways', 'XDP'].includes(delivery.carrier) &&
      String(delivery.salesActivityDetails?.['Order Category'] || delivery.orderRelationKind || '').trim().toLowerCase() === 'cancelled') return 'Cancelled';
  if (usesGlobalTrackingStatus() && delivery.carrier === 'Palletways')
    return palletwaysSpecificStatus(delivery.palletwaysSheetStatus) || palletwaysOwFallback(delivery) || overallTrackingStatus(delivery);
  if (isTrackingPage() && fsrc === 'Palletways' && delivery?.carrier === 'Palletways')
    return palletwaysSpecificStatus(delivery.palletwaysSheetStatus) || palletwaysOwFallback(delivery);
  if (palletwaysDeliveryConflict(delivery)) return delivery.palletwaysStatusLabel || delivery.palletwaysDetails?.statusLabel || trackingStatus(delivery.st);
  if (
    isTrackingPage() &&
    fsrc === 'Palletways' &&
    delivery?.carrier === 'Palletways' &&
    delivery.palletwaysSheetStatus && !palletwaysDeliveryConflict(delivery)
  ) {
    return palletwaysSpecificStatus(delivery.palletwaysSheetStatus);
  }
  if (delivery?.carrier === 'XDP' && delivery.xdpStatus) {
    return amazonStatusLabel(delivery.xdpStatus);
  }
  if (
    isTrackingPage() &&
    fsrc === 'Stopstart' &&
    delivery?.carrier === 'Stopstart' &&
    delivery.stopstartStatus
  ) {
    return delivery.stopstartStatus;
  }
  if (delivery?.carrier === 'AMZ' && (delivery.amazonSheetStatus || delivery.amazonStatus)) {
    return amazonStatusLabel(delivery.amazonSheetStatus || delivery.amazonStatus);
  }
  if (delivery?.carrier === 'Palletways' && delivery?.palletwaysStatusLabel) {
    return delivery.palletwaysStatusLabel;
  }

  return usesGlobalTrackingStatus() ? overallTrackingStatus(delivery)
    : trackingStatus(delivery?.st) || delivery?.st || 'Unscheduled';
};

const statusSourceLabel = (delivery) => {
  if (isCreditRefundRecord(delivery)) return 'OW';
  if (usesGlobalTrackingStatus() && ['Palletways', 'XDP'].includes(delivery.carrier) &&
      String(delivery.salesActivityDetails?.['Order Category'] || delivery.orderRelationKind || '').trim().toLowerCase() === 'cancelled') return 'OW Order Category';
  if (usesGlobalTrackingStatus() && delivery.carrier === 'Palletways')
    return delivery.palletwaysSheetStatus || delivery.palletwaysSheetMatched ? 'Palletways sheet' :
      ['Failed', 'Rejected', 'Lost'].includes(delivery.st) ? delivery.statusSource || 'OW' : 'OW';
  if (isTrackingPage() && fsrc === 'Palletways' && delivery?.carrier === 'Palletways')
    return palletwaysOwFallback(delivery) ? 'OW' : 'Palletways sheet';
  if (delivery?.carrier === 'AMZ' && (delivery.amazonSheetStatus || delivery.amazonStatus))
    return 'Amazon Shipping';
  if (
    isTrackingPage() &&
    fsrc === 'Palletways' &&
    delivery?.carrier === 'Palletways' &&
    delivery.palletwaysSheetStatus && !palletwaysDeliveryConflict(delivery)
  )
    return 'Palletways sheet';
  if (delivery?.carrier === 'XDP' && delivery.xdpStatus) return 'XDP sheet';
  if (
    isTrackingPage() &&
    fsrc === 'Stopstart' &&
    delivery?.carrier === 'Stopstart' &&
    delivery.stopstartStatus
  )
    return 'STOPSTART sheet';
  return [
    'Palletways',
    'OptimoRoute',
    'Amazon Shipping',
    'XDP fallback',
    'Routine Dashboard - Live',
  ].includes(delivery?.statusSource)
    ? delivery.statusSource
    : 'OW';
};

const statusSourceDisplay = (delivery) => {
  return statusSourceLabel(delivery);
};

function courierIssueFollowUpNotice(delivery) {
  if (!(page === 'Failed Deliveries' ? isGlobalException(delivery) : ['Failed', 'Rejected'].includes(trackingStatus(delivery?.st)))) return null;
  if (
    document.body.dataset.live === 'true' &&
    (liveSummary?.courierIssuesUnavailable || liveSummary?.stale)
  )
    return null;

  const tab = ['Own van', 'Self Delivery', 'LOCAL MULTIDROP'].includes(delivery.carrier)
    ? 'Van'
    : ['Palletways', 'XDP'].includes(delivery.carrier)
      ? delivery.carrier
      : '';
  if (!tab) return null;

  const source = `Courier Issues · ${tab}`;
  const hasIssueRecord = (delivery.carrierIssueEntries || []).some(
    (item) => item.source === source,
  );
  if (!hasIssueRecord) {
    return {
      kind: 'missing-row',
      text: 'No matching row in Courier Issues Excel. Check the carrier platform and follow up.',
    };
  }

  if (tab !== 'Van' || String(delivery.providerStatus || '').toLowerCase() !== 'failed') {
    return null;
  }
  const hasRemark = (delivery.followUps || []).some(
    (item) => item.status === source && String(item.remark || '').trim(),
  );
  const hasRecordedAction = (delivery.carrierIssueEntries || []).some(
    (item) =>
      item.source === source &&
      [item.messageStatus, item.scheduledStatus, item.deliveredStatus].some((value) =>
        String(value || '').trim(),
      ),
  );
  return hasRemark || hasRecordedAction
    ? null
    : {
        kind: 'missing-remark',
        text: 'Courier Issues Excel: no follow-up remark recorded.',
      };
}

const pill = (status) => (status ? stat(status) : '');

function activityMarkerKind(source, title) {
  if (source === 'ow') return 'ow';
  const text = String(title || '')
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();
  if (/\blost\b/.test(text)) return 'lost';
  if (/\bfailed\b|\bundeliverable\b|\bnot (?:received|delivered)\b|\bdelivery (?:unsuccessful|attempted)\b|\bunable to deliver\b|\bdamag(?:e|ed)\b|\brefused\b|\brejected\b/.test(text) ||
      (source === 'xdp' && /^delete\b/.test(text)))
    return 'failed';
  if (/\bdelivered\b/.test(text) && !/\bnot\b|\bunable\b/.test(text)) return 'delivered';
  return 'neutral';
}

function filterValues(value) {
  return (Array.isArray(value) ? value : [value]).filter(Boolean);
}
function compactFilter(values) {
  return values.length > 1 ? values : values[0] || '';
}
function filterIncludes(value, candidate) {
  const values = filterValues(value);
  return !values.length || values.includes(candidate);
}

const UiSelect = (() => {
  const callbacks = new Map();

  function render(id, value, options, config = {}) {
    callbacks.set(id, typeof config.onChange === 'function' ? config.onChange : null);

    const multiple = Boolean(config.multiple);
    const values = filterValues(value);
    const selected = options.find(([optionValue]) => String(optionValue) === String(value));
    const label =
      multiple && values.length > 1
        ? `${values.length} ${config.selectionLabel || 'selected'}`
        : (selected?.[1] ?? config.placeholder ?? 'Select');
    const classes = ['ui-select', config.className || ''].filter(Boolean).join(' ');
    const disabled = Boolean(config.disabled);

    return `<div class="${classes}" data-ui-select-id="${esc(id)}"${multiple ? ' data-ui-select-multiple="true"' : ''}>
      <input class="ui-select-value" type="hidden" id="${esc(id)}" value="${esc(value ?? '')}">
      <button class="ui-select-trigger" type="button" aria-label="${esc(config.ariaLabel || config.label || label)}" aria-expanded="false" ${disabled ? 'disabled' : ''} data-ui-select-trigger>
        <span class="ui-select-label">${esc(label)}</span>
        <span class="ui-select-chevron">${ico('chevdown', 16, 2)}</span>
      </button>
      <div class="ui-select-menu" role="menu" hidden>
        ${options
          .map(([optionValue, optionLabel]) => {
            const active = multiple
              ? optionValue
                ? values.includes(optionValue)
                : !values.length
              : String(optionValue) === String(value);
            return `<button class="ui-select-option${active ? ' on' : ''}" type="button" role="${multiple ? 'menuitemcheckbox' : 'menuitemradio'}" aria-checked="${active}" data-ui-select-option data-value="${esc(optionValue)}" data-label="${esc(optionLabel)}">
            <span>${esc(optionLabel)}</span>
            ${multiple ? `<span class="ui-select-checkbox" aria-hidden="true">${active ? ico('check', 13, 2) : ''}</span>` : active ? ico('check', 17, 2) : '<span class="ui-select-check" aria-hidden="true"></span>'}
          </button>`;
          })
          .join('')}
      </div>
    </div>`;
  }

  function closeAll(exceptId = '') {
    document.querySelectorAll('[data-ui-select-id]').forEach((select) => {
      if (select.dataset.uiSelectId === exceptId) return;
      const menu = select.querySelector('.ui-select-menu');
      const trigger = select.querySelector('.ui-select-trigger');
      if (menu) menu.hidden = true;
      if (trigger) trigger.setAttribute('aria-expanded', 'false');
    });
  }

  function hasOpenMenu() {
    return Boolean(document.querySelector('.ui-select-menu:not([hidden])'));
  }

  function selectRoot(id) {
    return document.getElementById(id)?.closest('[data-ui-select-id]') || null;
  }

  function toggle(id) {
    const select = selectRoot(id);
    if (!select) return;

    const menu = select.querySelector('.ui-select-menu');
    const trigger = select.querySelector('.ui-select-trigger');
    if (!menu || !trigger || trigger.disabled) return;

    const opening = menu.hidden;
    closeAll(id);
    if (typeof DeliveryFilters !== 'undefined') DeliveryFilters.closeAll();
    menu.hidden = !opening;
    trigger.setAttribute('aria-expanded', String(opening));
  }

  function choose(id, option) {
    const select = selectRoot(id);
    if (!select) return;

    const input = select.querySelector('.ui-select-value');
    const label = select.querySelector('.ui-select-label');
    const menu = select.querySelector('.ui-select-menu');
    const trigger = select.querySelector('.ui-select-trigger');
    const value = option.dataset.value ?? '';
    const text = option.dataset.label ?? option.textContent.trim();
    if (select.dataset.uiSelectMultiple === 'true') {
      const values = [...select.querySelectorAll('[data-ui-select-option][aria-checked="true"]')]
        .map((item) => item.dataset.value)
        .filter(Boolean);
      const next = !value
        ? []
        : values.includes(value)
          ? values.filter((item) => item !== value)
          : [...values, value];
      const scroll = menu.scrollTop;
      callbacks.get(id)?.(compactFilter(next), input);
      const updated = selectRoot(id);
      if (updated) {
        updated.querySelector('.ui-select-menu').hidden = false;
        updated.querySelector('.ui-select-menu').scrollTop = scroll;
        updated.querySelector('.ui-select-trigger').setAttribute('aria-expanded', 'true');
        [...updated.querySelectorAll('[data-ui-select-option]')]
          .find((item) => item.dataset.value === value)
          ?.focus({ preventScroll: true });
      }
      return;
    }

    if (input) input.value = value;
    if (label) label.textContent = text;
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');

    select.querySelectorAll('.ui-select-option').forEach((item) => {
      const active = item === option;
      item.classList.toggle('on', active);
      item.setAttribute('aria-checked', String(active));
      const marker = item.querySelector('svg, .ui-select-check');
      if (marker) marker.remove();
      item.insertAdjacentHTML(
        'beforeend',
        active ? ico('check', 17, 2) : '<span class="ui-select-check" aria-hidden="true"></span>',
      );
    });

    input?.dispatchEvent(new Event('change', { bubbles: true }));
    callbacks.get(id)?.(value, input);
  }

  function handleClick(event) {
    const option = event.target.closest('[data-ui-select-option]');
    if (option) {
      const select = option.closest('[data-ui-select-id]');
      event.stopPropagation();
      choose(select.dataset.uiSelectId, option);
      return true;
    }

    const trigger = event.target.closest('[data-ui-select-trigger]');
    if (!trigger) return false;

    const select = trigger.closest('[data-ui-select-id]');
    event.stopPropagation();
    toggle(select.dataset.uiSelectId);
    return true;
  }

  return {
    closeAll,
    handleClick,
    hasOpenMenu,
    render,
  };
})();

const tlink = (delivery) => {
  return delivery?.trackingUrl || '';
};

function purchaseChannel(delivery) {
  const details = delivery?.salesActivityDetails || {};
  const orderType = String(details['Order Type'] || '').trim();
  if (['sales', 'hr_replacement'].includes(orderType.toLowerCase()))
    return 'Hygienic Cleaning Company (UK) LTD';
  // Orders saved before AH was imported retain their existing store identity.
  // A present but blank/unknown AH value must still use the new mapping.
  if (!Object.prototype.hasOwnProperty.call(delivery || {}, 'storeCode')) {
    const analysis = String(details['Order Analysis'] || '').trim();
    if (analysis.toLowerCase() === 'ebay0') return 'Ebay Bathroom Republic';
    if (analysis.toLowerCase() === 'ebay1') return 'EBay Willesden Bathroom';
    if (orderType.toLowerCase() === 'shopify') return analysis;
    if (orderType.toLowerCase() === 'debenhams' && analysis.toLowerCase() === 'debenhams - neshome')
      return 'Debenhams - Neshome';
    return orderType;
  }
  const code = String(delivery?.storeCode || '')
    .trim()
    .toUpperCase();
  return (
    {
      EBAY_BR: 'Ebay Bathroom Republic',
      EBAY_WB: 'EBay Willesden Bathroom',
      AMAZON: 'Amazon',
      DEBENHAM: 'Debenhams - Neshome',
      'B&Q': 'B&Q',
      SHOPIFY: 'Shopify - Neshome',
      BATHPROF: 'Bathroom Republic - Website',
      BATHREP: 'Bathroom Republic - Website',
      BATHROOM: 'Bathroom Republic - Website',
      WILKO: 'Wilko',
      WAYFAIR: 'Wayfair',
    }[code] || ''
  );
}

const PURCHASE_STORES = [
  'Amazon',
  'Hygienic Cleaning Company (UK) LTD',
  'Debenhams - Neshome',
  'B&Q',
  'Ebay Bathroom Republic',
  'EBay Willesden Bathroom',
  'Shopify - Neshome',
  'Bathroom Republic - Website',
  'Wilko',
  'Wayfair',
];

function purchaseStoreLogo(delivery, className = '') {
  const channel = purchaseChannel(delivery).toLowerCase().replace(/\s+/g, ' ').trim();
  let filename = '';
  if (channel === 'amazon') filename = 'AmaNes.png';
  else if (channel === 'hygienic cleaning company (uk) ltd') filename = 'Hyg.png';
  else if (channel === 'debenhams - neshome') filename = 'DeNeshome.png';
  else if (channel === 'b&q' || channel.startsWith('b&q - ')) filename = 'BQNes.png';
  else if (channel === 'ebay') filename = 'ebay.png';
  else if (channel === 'ebay bathroom republic') filename = 'EbayBR.png';
  else if (channel === 'ebay willesden bathroom') filename = 'ebayW.png';
  else if (channel === 'shopify - neshome') filename = 'ShpfyNes.png';
  else if (channel === 'bathroom republic - website') filename = 'ShpfyBR.png';
  else if (channel === 'wayfair') filename = 'wayfair.jpg';
  else if (channel === 'wilko' || channel === 'weiko') filename = 'wilko.png';
  return filename
    ? `<img class="purchase-store-logo ${esc(className)}" src="/assets/${filename}" width="130" height="40" alt="${esc(purchaseChannel(delivery))}" title="${esc(purchaseChannel(delivery))}">`
    : '';
}

function exactOrderMatches(records, query, keys = ['order', 'id']) {
  const term = String(query || '').trim().toLowerCase();
  if (!term) return records;
  const exact = records.filter(record => keys.some(key => String(record[key] || '').trim().toLowerCase() === term));
  return exact.length ? exact : records;
}

function orderRecordType(delivery = {}) {
  const kind = delivery?.orderRelationKind || delivery?.relatedKind;
  if (kind === 'Credit/Refund' ||
      String(delivery?.salesActivityDetails?.['Order Category'] || '').toLowerCase() === 'credit/refund') return 'Credit/Refund';
  return ['Replacement', 'Later Replacement'].includes(kind) ? 'Replacement' : 'Order';
}

function isCreditRefundRecord(delivery) {
  return orderRecordType(delivery) === 'Credit/Refund';
}

function refundStatusValue(delivery) {
  const raw = String(delivery?.rawStatus || '').trim().toUpperCase();
  return ['C', 'COMPLETED'].includes(raw) ? 'refund:complete'
    : ['X', 'CANCELLED'].includes(raw) ? 'refund:cancelled' : 'refund:not-yet';
}

function refundStatusLabel(value) {
  return {'refund:complete': 'Refund complete', 'refund:cancelled': 'Cancelled', 'refund:not-yet': 'Not Yet'}[value] || value;
}

function refundAmountLabel(delivery) {
  const raw = String(delivery.salesActivityDetails?.['Gross (base)'] ?? '').trim();
  const normalized = raw.replace(/[£,\s]/g, '').replace(/^\((.*)\)$/, '-$1');
  const amount = normalized && /^-?\d+(?:\.\d+)?$/.test(normalized) ? Number(normalized) : NaN;
  return Number.isFinite(amount)
    ? new Intl.NumberFormat('en-GB', { style: 'currency', currency: 'GBP' }).format(Math.abs(amount))
    : 'Amount unavailable';
}

function searchRefundAmountMarkup(delivery) {
  if (!isCreditRefundRecord(delivery)) return '';
  return `<span class="search-result-refund-amount"><small>Refund amount</small><strong>${esc(refundAmountLabel(delivery))}</strong></span>`;
}

function searchOrderTypeMarkup(delivery) {
  const type = orderRecordType(delivery);
  const tone = type === 'Credit/Refund' ? 'refund' : type === 'Replacement' ? 'replacement' : 'order';
  return `<span class="search-result-type is-${tone}">${type}</span>`;
}

function dashboardSearchDestination(delivery = {}) {
  const type = orderRecordType(delivery);
  const target = type === 'Credit/Refund' ? 'Refund' : type === 'Replacement' ? 'Replacement' : 'Deliveries';
  const carrier = SELF_DELIVERY_CARRIERS.includes(delivery.carrier)
    ? SELF_DELIVERY_GROUP : delivery.carrier || '';
  const supported = new Set([...APP_CONFIG.carriers.supported, ...Object.keys(courierAssets), SELF_DELIVERY_GROUP]);
  return { target, carrier: supported.has(carrier) ? carrier : '' };
}

let dashboardSearchHighlight = null;
function openDashboardSearchOrder(id) {
  const delivery = get(id);
  const order = String(delivery?.order || id);
  const destination = dashboardSearchDestination(delivery);
  dashboardSearchHighlight = {
    id: String(id), order, page: destination.target, carrier: destination.carrier,
    startedAt: performance.now(), fallbackApplied: false,
  };
  go(destination.target, '', '', { carrier: destination.carrier });
  dashboardSelectedId = id;
  op(id);
  rows();
}

let dashboardSearchRequest = 0;
let dashboardSearchVisible = false;
let dashboardSearchCache = null;
function closeDashboardSearch() {
  clearTimeout(dashboardSearchTimer);
  dashboardSearchRequest++;
  dashboardSearchVisible = false;
  const dropdown = $('#dres');
  if (dropdown) dropdown.hidden = true;
}
function reopenDashboardSearch(input) {
  dq = input.value;
  if (!dq.trim()) return;
  const dropdown = $('#dres');
  if (dropdown && (dropdown.hidden || !dropdown.childNodes.length)) dres();
}
document.addEventListener('click', event => {
  const input = event.target.closest('#dq');
  if (input) { reopenDashboardSearch(input); return; }
  if (!event.target.closest('#dres, [data-dashboard-search]')) closeDashboardSearch();
}, true);
document.addEventListener('focusin', event => {
  if (event.target.matches('#dq')) reopenDashboardSearch(event.target);
});

async function dres() {
  const request = ++dashboardSearchRequest;
  const container = $('#dres');
  if (!container) return;

  const term = dq.trim().toLowerCase().replace(/\s+/g, ' ');
  if (!term) {
    container.replaceChildren();
    closeDashboardSearch();
    return;
  }
  dashboardSearchVisible = true;
  if (dashboardSearchCache?.term === term && !container.childNodes.length) {
    container.innerHTML = dashboardSearchCache.markup;
  }
  container.hidden = false;

  let candidates = D;
  const linkedOrderIds = new Set();
  if (document.body.dataset.live === 'true') {
    try {
      const result = await DeliveryApi.list({ q: term, limit: 6, tracking_related: 1 });
      if (request !== dashboardSearchRequest || !container.isConnected || dq.trim().toLowerCase().replace(/\s+/g, ' ') !== term) return;
      const relations = result.orderRelations;
      const related = (relations?.related || []).filter(record =>
        ['Replacement', 'Later Replacement', 'Credit/Refund'].includes(record.relatedKind),
      );
      related.forEach(record => linkedOrderIds.add(String(record.id || record.order)));
      candidates = [...new Map([
        ...(relations?.original ? [relations.original] : []), ...result.deliveries, ...related,
      ].map(record => [String(record.id || record.order), record])).values()];
      for (const delivery of candidates)
        if (!DeliveryStore.find(delivery.id)) DeliveryStore.add(delivery);
    } catch (error) {
      if (request !== dashboardSearchRequest || !container.isConnected) return;
      container.textContent = error.message;
      return;
    }
  }
  const phoneTerm = term.replace(/\s/g, '');
  const preferred = exactOrderMatches(candidates, term);
  const searchCandidates = preferred !== candidates
    ? [...preferred, ...candidates.filter(record => linkedOrderIds.has(String(record.id || record.order)) && !preferred.includes(record))]
    : candidates;
  const matches = searchCandidates
    .filter((delivery) => {
      const fields = [
        delivery.trk,
        delivery.palletwaysSheetTrackingNumber,
        delivery.palletwaysSheetConsignmentNumber,
        delivery.order,
        delivery.orderRef,
        delivery.orderReference,
        delivery.cust,
        delivery.addr,
        delivery.phone,
      ]
        .join(' ')
        .toLowerCase();
      return (
        linkedOrderIds.has(String(delivery.id || delivery.order)) || fields.includes(term) ||
        (phoneTerm.length > 3 &&
          String(delivery.phone || '')
            .replace(/\s/g, '')
            .includes(phoneTerm))
      );
    })
    .slice(0, 6);

  const markup = matches.length
    ? matches
        .map(
          (
            delivery,
          ) => `<div class="rc${isCreditRefundRecord(delivery) ? ' is-credit-refund' : ''}" style="--search-brand:${esc(courierAssets[delivery.carrier]?.[1] || '#6267e9')}" tabindex="0" role="button" onclick="openDashboardSearchOrder('${delivery.id}')" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openDashboardSearchOrder('${delivery.id}')}">
        <span class="search-result-backdrop" aria-hidden="true">${courierAssets[delivery.carrier] ? `<img class="search-result-background-logo" src="/assets/${esc(courierAssets[delivery.carrier][0])}" alt="">` : `<span class="search-result-background-name">${esc(delivery.deliveryMethodRaw || delivery.carrier || 'Delivery')}</span>`}</span>
        <div class="search-result-store" aria-hidden="true">${purchaseStoreLogo(delivery, 'search-result-store-logo') || ico('pkg', 24)}</div><div class="search-result-customer"><span class="search-result-order">Order ${esc(delivery.order || delivery.id)}</span><b>${esc(delivery.cust)}</b><br><span class="mut">${esc(delivery.addr)}</span><br><span class="mut">${esc(delivery.phone)} · ${delivery.trk ? esc(delivery.trk) : 'No tracking no.'}</span></div>
        <div class="rcm">${stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery))}<br><span class="mut">${delivery.reason ? esc(deliveryReason(delivery.reason).label) : delivery.date ? `${hd(delivery.date)}${delivery.win ? ` · ${delivery.win.replace('-', '–')}` : ''}` : 'Date unavailable'} · ${esc(delivery.carrier === 'Own van' ? 'Own van' : delivery.carrier)}</span></div>
        <div class="search-result-type-slot">${searchOrderTypeMarkup(delivery)}${searchRefundAmountMarkup(delivery)}</div>
      </div>`,
        )
        .join('')
    : '<div class="rc0">No match. Check the spelling, or try the order ID.</div>';
  dashboardSearchCache = { term, markup };
  if (container.innerHTML !== markup) container.innerHTML = markup;
}

function scheduleDashboardSearch() {
  clearTimeout(dashboardSearchTimer);
  dashboardSearchRequest++;
  if (!dq.trim()) {
    dres();
    return;
  }
  dashboardSearchTimer = setTimeout(dres, 200);
}

const stale = (delivery) => {
  const source = S.find(
    (item) =>
      item[0] === delivery.carrier || (delivery.carrier === 'Own van' && item[0] === 'OptimoRoute'),
  );
  if (!source || source[2] === 'ok') return '';
  return `<div class="card" style="box-shadow:none;background:var(--k2);margin:10px 0">Data from ${source[0]} may be out of date: ${esc(source[3])}</div>`;
};

function dashboardWidgetControls(key = dashboardWidgetFilter) {
  if (key === 'palletways-depot-3days')
    return {
      carrier: 'Palletways',
      conditions: 'Confirmed delivery depot arrival · Over 72 hours · No recorded departure',
    };
  if (key === 'charge-pending')
    return {
      scope: 'Charge Pending (Remote Postcode)',
      conditions: 'Charge Pending (Remote Postcode) ? All order dates',
    };
  if (key === 'collect')
    return { scope: 'Collect in Person', conditions: 'Collect in Person ? All order dates' };
  if (key === 'hold') return { scope: 'On Hold', conditions: 'On Hold or Unassigned' };
  if (key === 'cancelled' || key === 'cancelled-month')
    return {
      conditions: `Confirmed Own van only; OW T = TO BE CANCELLED or OW AI Order Category = Cancelled; excludes Credit/Refund; Order date: ${key === 'cancelled-month' ? 'this month' : 'today'} (UK)`,
    };
  if (key === 'palletways-next-day')
    return {
      carrier: 'Palletways',
      conditions: 'Palletways ? Next Day ? Excludes Delivered, Cancelled and Return',
    };
  if (key.startsWith('palletways-unbooked'))
    return {
      carrier: 'Palletways',
      bookedIn: 'no',
      conditions: `Palletways${key.endsWith('-b2c') ? ' B2C' : key.endsWith('-b2b') ? ' B2B' : ''} ? Booked in: No ? Excludes Delivered and Next Day ? Current Sales Activity orders`,
    };
  if (key === 'out-of-stock')
    return {
      conditions: 'Booking status: Out of Stock or O/S ? Excludes Delivered, Cancelled and Return',
    };
  if (key === 'van-unscheduled')
    return {
      carrier: SELF_DELIVERY_GROUP,
      conditions:
        'Own van / Self Delivery ? Unscheduled, O/S, Out of Stock, On Hold or Open ? Excludes Delivered, Cancelled and Return',
    };
  return {};
}
function applyDashboardWidgetControls() {
  if (!dashboardWidgetFilter) return;
  const controls = dashboardWidgetControls();
  trackingScope = controls.scope || '';
  if (controls.carrier && !fsrc) fsrc = controls.carrier;
  fbookedIn = controls.bookedIn || '';
}

function go(target, statusFilter = '', scope = '', filters = {}) {
  page = target;
  trackingScope = target === 'Deliveries' ? scope : '';
  sel = null;
  q = filters.search || '';
  fs = statusFilter;
  fsrc = filters.carrier || '';
  fstore = filters.store || '';
  dashboardWidgetFilter = target === 'Deliveries' ? filters.widget || '' : '';
  trackingWidgetFacets = null;
  fmethod = '';
  fclassification = [];
  fbookedIn = '';
  fbookInRequest = '';
  fd = '';
  ft = '';
  applyDashboardWidgetControls();
  $('.app').classList.remove('mobile-open');
  $('.mn')?.setAttribute('aria-expanded', 'false');

  try {
    let url =
      target === 'Deliveries' && trackingScope === 'today'
        ? `${PAGE_URL[target]}?view=today`
        : PAGE_URL[target];
    if (dashboardWidgetFilter) {
      const query = new URLSearchParams({ dashboard_widget: dashboardWidgetFilter });
      if (fsrc) query.set('carrier', fsrc);
      filterValues(fstore).forEach((value) => query.append('store', value));
      url += `?${query}`;
    }
    history.pushState({ page: target }, '', url);
  } catch (error) {
    void error;
  }

  R();
}

const ScopeLiquid = (() => {
  let fluid = null;
  let destination = null;
  let motion = null;

  function clear() {
    const settled = destination;
    if (settled) {
      // Paint the selected background before removing the travelling overlay.
      // Otherwise its CSS transition starts from transparent and briefly flashes.
      settled.classList.add('liquid-settling');
      settled.classList.remove('liquid-arriving');
      AtlasViewport.rect(settled);
    }
    motion?.cancel();
    fluid?.remove();
    fluid = destination = motion = null;
    if (settled) requestAnimationFrame(() => settled.classList.remove('liquid-settling'));
  }

  function capture(level = '') {
    const selected =
      fluid ||
      document.querySelector(
        `.tracking-scope-sections .fx-tab.on${level ? `[data-delivery-filter-action="${level}"]` : ''}`,
      );
    const bounds = AtlasViewport.rect(selected);
    clear();
    return bounds;
  }

  function move(from, level = '') {
    const target = document.querySelector(
      `.tracking-scope-sections .fx-tab.on${level ? `[data-delivery-filter-action="${level}"]` : ''}`,
    );
    if (
      !from ||
      !target ||
      matchMedia('(prefers-reduced-motion: reduce)').matches ||
      typeof target.animate !== 'function'
    )
      return;
    const to = AtlasViewport.rect(target);
    if (Math.abs(from.left - to.left) < 1 && Math.abs(from.top - to.top) < 1) return;
    const sameRow =
      Math.abs(from.top + from.height / 2 - (to.top + to.height / 2)) <
      Math.min(from.height, to.height) / 2;
    if (!sameRow) {
      // Enter on the destination row instead of crossing intervening controls.
      from = {
        left: to.left + Math.max(0, Math.min(80, AtlasViewport.width - to.right - 8)),
        top: to.top,
        width: to.width,
        height: to.height,
      };
    }
    destination = target;
    target.classList.add('liquid-arriving');
    const host = target.closest('.tracking-scope-sections');
    const origin = AtlasViewport.rect(host);
    fluid = document.createElement('div');
    fluid.className = 'scope-liquid';
    fluid.setAttribute('aria-hidden', 'true');
    host.append(fluid);
    const direction = to.left >= from.left ? 1 : -1;
    const frame = (progress, width, height, radius, rotate = 0) => ({
      left: `${from.left + (to.left - from.left) * progress + (from.width + (to.width - from.width) * progress - width) / 2 - origin.left}px`,
      top: `${to.top + (to.height - height) / 2 - origin.top}px`,
      width: `${width}px`,
      height: `${height}px`,
      borderRadius: radius,
      transform: `rotate(${rotate * direction}deg)`,
    });
    const travellingWidth = Math.min(180, Math.max(from.width, to.width) * 0.85);
    motion = fluid.animate(
      [
        { ...frame(0, from.width, from.height, '12px'), opacity: sameRow ? 1 : 0, offset: 0 },
        {
          ...frame(
            0.12,
            from.width * 0.8,
            from.height * 0.85,
            '36% 64% 58% 42% / 48% 39% 61% 52%',
            -5,
          ),
          opacity: 1,
          offset: 0.18,
        },
        {
          ...frame(0.5, travellingWidth, from.height * 0.6, '65% 35% 38% 62% / 50% 65% 35% 50%', 4),
          offset: 0.48,
        },
        {
          ...frame(
            0.86,
            to.width * 0.82,
            to.height * 1.12,
            '38% 62% 63% 37% / 62% 43% 57% 38%',
            -3,
          ),
          offset: 0.76,
        },
        { ...frame(1, to.width, to.height, '12px'), offset: 1 },
      ],
      { duration: sameRow ? 680 : 520, easing: 'cubic-bezier(.22,.68,.22,1)', fill: 'forwards' },
    );
    motion.onfinish = clear;
  }

  return { capture, move };
})();

function fadeClearFilter(button) {
  if (
    !button ||
    matchMedia('(prefers-reduced-motion: reduce)').matches ||
    typeof button.animate !== 'function'
  )
    return;
  const bounds = AtlasViewport.rect(button);
  const appearance = getComputedStyle(button);
  // Joined orange pieces soften into droplets as they separate.
  const pieces = [
    [0, 34, -15, -5, -8],
    [34, 68, 1, 9, 4],
    [68, 100, 15, -4, 8],
  ];
  for (const [left, right, x, y, angle] of pieces) {
    const fragment = button.cloneNode(true);
    fragment.classList.add('clear-filter-exit');
    fragment.removeAttribute('id');
    fragment.setAttribute('aria-hidden', 'true');
    fragment.tabIndex = -1;
    const middle = (left + right) / 2;
    const joined = `polygon(${left}% 0%, ${middle}% 0%, ${right}% 0%, ${right}% 50%, ${right}% 100%, ${middle}% 100%, ${left}% 100%, ${left}% 50%)`;
    const liquid = `polygon(${left + 4}% 20%, ${middle}% 6%, ${right - 3}% 19%, ${right - 1}% 48%, ${right - 5}% 78%, ${middle - 2}% 94%, ${left + 2}% 79%, ${left}% 48%)`;
    Object.assign(fragment.style, {
      left: `${bounds.left}px`,
      top: `${bounds.top}px`,
      width: `${bounds.width}px`,
      height: `${bounds.height}px`,
      background: appearance.background,
      color: appearance.color,
      border: appearance.border,
      boxShadow: appearance.boxShadow,
      transformOrigin: `${middle}% 50%`,
      filter: 'blur(0.4px)',
    });
    document.body.append(fragment);
    fragment
      .animate(
        [
          { opacity: 1, clipPath: joined, transform: 'translate(0, 0) scale(1) rotate(0)' },
          {
            opacity: 0.85,
            clipPath: liquid,
            transform: `translate(${x * 0.55}px, ${y * 0.55}px) scale(.98, 1.08) rotate(${angle * 0.4}deg)`,
            offset: 0.45,
          },
          {
            opacity: 0,
            clipPath: liquid,
            transform: `translate(${x}px, ${y}px) scale(.68, .8) rotate(${angle}deg)`,
          },
        ],
        { duration: 380, easing: 'cubic-bezier(.2,.65,.3,1)', fill: 'forwards' },
      )
      .finished.then(
        () => fragment.remove(),
        () => fragment.remove(),
      );
  }
}

const DeliveryFilters = (() => {
  function widgetDateLabel() {
    if (dashboardWidgetFilter === 'cancelled-month') return 'This month (order created)';
    if (dashboardWidgetFilter === 'cancelled') return 'Today (order created)';
    return '';
  }

  function dateLabel() {
    const widgetDate = widgetDateLabel();
    if (widgetDate) return widgetDate + (fd || ft ? ' + delivery dates' : '');
    if (!fd && !ft) return 'Delivery date';
    if (fd && ft) return `${hd(fd)} – ${hd(ft)}`;
    return fd ? `From ${hd(fd)}` : `To ${hd(ft)}`;
  }

  function closeAll() {
    const menu = $('#dpn');
    const trigger = $('#dbtn');
    if (menu) menu.hidden = true;
    if (trigger) trigger.setAttribute('aria-expanded', 'false');
    const classifications = $('#tracking-classification-menu');
    if (classifications?.matches(':popover-open')) classifications.hidePopover();
    $('[data-delivery-filter-action="toggle-classification"]')?.setAttribute(
      'aria-expanded',
      'false',
    );
    document.querySelectorAll('[data-booking-menu]').forEach((menu) => {
      if (menu.matches(':popover-open')) menu.hidePopover();
    });
    document
      .querySelectorAll('[data-delivery-filter-action="toggle-booking"]')
      .forEach((trigger) => trigger.setAttribute('aria-expanded', 'false'));
  }

  function hasOpenMenu() {
    return Boolean(
      $('#dpn:not([hidden])') ||
        $('#tracking-classification-menu:popover-open') ||
        $('[data-booking-menu]:popover-open'),
    );
  }

  const bookingFields = {
    booked_in: ['Booked In', () => fbookedIn],
    book_in_request: ['Book In Request', () => fbookInRequest],
  };

  function renderBookingHeading(field) {
    const [label, selected] = bookingFields[field];
    return `<div class="tracking-method-heading"><span>${label}</span><button class="tracking-method-filter ${selected() ? 'on' : ''}" type="button" data-delivery-filter-action="toggle-booking" data-booking-field="${field}" aria-label="Filter ${label}" aria-haspopup="menu" aria-expanded="false" aria-controls="tracking-${field}-menu" title="Filter ${label}">${ico('filter', 16)}</button></div>`;
  }

  function renderBookingMenus() {
    if (fsrc !== 'Palletways') return '';
    return Object.entries(bookingFields)
      .map(
        ([
          field,
          [label, selected],
        ]) => `<div class="tracking-classification-menu" id="tracking-${field}-menu" data-booking-menu popover="manual" role="menu" aria-label="Filter ${label}">
      ${[
        ['', 'All'],
        ['yes', 'Yes'],
        ['no', field === 'booked_in' ? 'N/A' : 'No'],
        ...(field === 'booked_in' ? [['not-yet', 'Not Yet']] : []),
      ]
        .map(
          ([value, text]) =>
            `<button class="tracking-classification-option ${value === selected() ? 'on' : ''}" type="button" role="menuitemradio" aria-checked="${value === selected()}" data-delivery-filter-action="booking" data-booking-field="${field}" data-value="${value}">${text}</button>`,
        )
        .join('')}
    </div>`,
      )
      .join('');
  }

  function toggleBooking(trigger) {
    const menu = document.getElementById(`tracking-${trigger.dataset.bookingField}-menu`);
    if (!menu) return;
    const opening = !menu.matches(':popover-open');
    closeAll();
    UiSelect.closeAll();
    if (!opening) return;
    const bounds = AtlasViewport.rect(trigger);
    const width = Math.min(180, AtlasViewport.width - 16);
    menu.style.width = `${width}px`;
    menu.style.left = `${Math.max(8, Math.min(bounds.right - width, AtlasViewport.width - width - 8))}px`;
    menu.style.top = `${bounds.bottom + 6}px`;
    menu.style.maxHeight = `${Math.max(80, AtlasViewport.height - bounds.bottom - 14)}px`;
    menu.showPopover();
    trigger.setAttribute('aria-expanded', 'true');
    menu.querySelector('.on, button')?.focus();
  }

  function renderClassificationMenu() {
    const classifications = trackingFilterFacets()
      .filter((item) => trackingMatchesScope(item) && matchesDeliveryCarrier(item.carrier, fsrc))
      .map((item) => item.classification);
    const options = [...new Set(classifications.filter(Boolean))].sort((a, b) =>
      a.localeCompare(b),
    );
    return `<div class="tracking-classification-menu" id="tracking-classification-menu" popover="manual" role="menu" aria-label="${esc(fsrc || 'Delivery method')} classifications">
      ${[['', 'All classifications'], ...options.map((value) => [value, value])]
        .map(([value, label]) => {
          const selected = value ? fclassification.includes(value) : !fclassification.length;
          return `<button class="tracking-classification-option tracking-classification-multi ${selected ? 'on' : ''}" type="button" role="menuitemcheckbox" aria-checked="${selected}" data-delivery-filter-action="classification" data-value="${esc(value)}"><span class="tracking-classification-check" aria-hidden="true">${selected ? ico('check', 14) : ''}</span><span>${esc(label)}</span></button>`;
        })
        .join('')}
    </div>`;
  }

  function toggleClassification(trigger) {
    const menu = $('#tracking-classification-menu');
    if (!menu) return;
    const opening = !menu.matches(':popover-open');
    closeAll();
    UiSelect.closeAll();
    if (!opening) return;
    const bounds = AtlasViewport.rect(trigger);
    const width = Math.min(300, AtlasViewport.width - 16);
    menu.style.width = `${width}px`;
    menu.style.left = `${Math.max(8, Math.min(bounds.right - width, AtlasViewport.width - width - 8))}px`;
    menu.style.top = `${bounds.bottom + 6}px`;
    menu.style.maxHeight = `${Math.max(80, Math.min(320, AtlasViewport.height - bounds.bottom - 14))}px`;
    menu.showPopover();
    trigger.setAttribute('aria-expanded', 'true');
    menu.querySelector('.on, button')?.focus();
  }

  function syncClassificationFilter() {
    const menu = $('#tracking-classification-menu');
    menu?.querySelectorAll('[data-delivery-filter-action="classification"]').forEach((option) => {
      const selected = option.dataset.value
        ? fclassification.includes(option.dataset.value)
        : !fclassification.length;
      option.classList.toggle('on', selected);
      option.setAttribute('aria-checked', String(selected));
      option.querySelector('.tracking-classification-check').innerHTML = selected
        ? ico('check', 14)
        : '';
    });
    const trigger = $('[data-delivery-filter-action="toggle-classification"]');
    trigger?.classList.toggle('on', Boolean(fclassification.length));
    if (trigger)
      trigger.title = fclassification.length
        ? fclassification.join(', ')
        : 'Filter delivery-method classification';
  }

  function toggleDate() {
    const menu = $('#dpn');
    const trigger = $('#dbtn');
    if (!menu || !trigger) return;

    const opening = menu.hidden;
    closeAll();
    UiSelect.closeAll();
    menu.hidden = !opening;
    trigger.setAttribute('aria-expanded', String(opening));
  }

  function updateDateLabel() {
    const label = $('#dbtn .ui-select-label');
    if (label) label.textContent = dateLabel();
  }

  function popSelection(level, value) {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const target = [...document.querySelectorAll(`[data-delivery-filter-action="${level}"]`)].find(
      (button) => button.dataset.value === value,
    );
    // Keep the button out of a transform stacking context so its content
    // stays above the travelling liquid throughout the pop.
    target
      ?.querySelectorAll(':scope > span')
      .forEach((content) =>
        content.animate?.(
          [
            { transform: 'scale(1)' },
            { transform: 'scale(1.06, .92)', offset: 0.3 },
            { transform: 'scale(.98, 1.04)', offset: 0.65 },
            { transform: 'scale(1)' },
          ],
          { duration: 360, easing: 'cubic-bezier(.22,.8,.3,1)' },
        ),
      );
  }

  function setScope(value, level = 'general', toggle = true) {
    const previousCarrier = fsrc;
    const previousBubble = ScopeLiquid.capture(level);
    closeAll();
    UiSelect.closeAll();
    if (level === 'general') {
      trackingScope = toggle && trackingScope === value ? '' : value;
      if (
        !trackingLevelCounts().carriers[fsrc] &&
        dashboardWidgetFilter !== 'palletways-depot-3days'
      )
        fsrc = '';
    } else {
      fsrc = fsrc === value ? '' : value;
    }
    fmethod = '';
    fclassification = [];
    if (previousCarrier !== fsrc) {
      fbookedIn = '';
      fbookInRequest = '';
      if (fsrc !== 'Palletways' && dashboardWidgetFilter === 'palletways-depot-3days') {
        dashboardWidgetFilter = '';
        trackingWidgetFacets = null;
      }
    }
    if (
      previousCarrier !== fsrc &&
      [previousCarrier, fsrc].some((carrier) =>
        ['AMZ', 'Stopstart', 'XDP', 'Palletways'].includes(carrier),
      )
    )
      fs = '';
    fs = compactFilter(filterValues(fs).filter((value) => trackingLevelCounts().statuses[value]));
    history.replaceState(
      { page },
      '',
      trackingScope === 'today' ? `${PAGE_URL[page]}?view=today` : PAGE_URL[page],
    );
    R();
    ScopeLiquid.move(previousBubble, level);
    popSelection(level, value);
  }

  function render() {
    const stores = availableTrackingStores();
    if (dashboardWidgetFilter)
      filterValues(fstore).forEach((value) => {
        if (!stores.includes(value)) stores.push(value);
      });
    if (document.body.dataset.live !== 'true' || liveReady)
      fstore = compactFilter(filterValues(fstore).filter((value) => stores.includes(value)));
    const levelCounts = trackingLevelCounts();
    const counts = levelCounts.statuses;
    const otherMethods = Object.entries(levelCounts.carriers)
      .filter(([value, count]) => value && count > 0 && !isMainTrackingMethod(value))
      .sort(([a], [b]) => a.localeCompare(b));
    const otherMethodTotal = otherMethods.reduce((sum, [, count]) => sum + count, 0);
    const categoryFacets = levelCounts.facets.filter(item => matchesDeliveryCarrier(item.carrier, fsrc) &&
      filterIncludes(fstore, item.purchaseStore) &&
      (!fclassification.length || fclassification.includes(item.classification)));
    const categoryOptions = TRACKING_SCOPE_OPTIONS
      .filter(([value]) => ['', 'today', 'hygienic'].includes(value) &&
        (value !== 'hygienic' || !TrackingVisibility.enabled()))
      .map(([value, label]) => [value, label, categoryFacets.filter(item => trackingMatchesScope(item, value))
        .reduce((sum,item) => sum + item.count, 0)])
      .filter(([value, , count]) => !value || count > 0 || filterValues(trackingScope).includes(value))
      .map(([value, label, count]) => [value, value ? `${label} (${count})` : 'All categories']);
    const depotCount = categoryFacets.reduce((sum,item) => sum + Number(item.palletwaysDepotCount || 0), 0);
    if (fsrc === 'Palletways' && (depotCount > 0 || dashboardWidgetFilter === 'palletways-depot-3days'))
      categoryOptions.push(['palletways-depot-3days', `At Depot 3> Days (${depotCount})`]);
    const statusOptions = [
      ['', `All statuses (${Object.values(counts).reduce((sum, count) => sum + count, 0)})`],
      ...(trackingOrderKind() === 'refund' ? ['refund:complete', 'refund:not-yet', 'refund:cancelled'] : ['AMZ', 'Stopstart', 'XDP', 'Palletways'].includes(fsrc)
        ? Object.keys(counts).sort((a, b) => a.localeCompare(b))
        : [
            ...(usesGlobalTrackingStatus() ? ['Other Status'] : ['Awaiting']),
            'Unscheduled',
            'Scheduled',
            'Out for Delivery',
            'Next Stop',
            'Delivered',
            'Failed',
            'Rejected',
            'Lost',
            'Cancelled',
            'Return',
            'Unassigned',
          ]
      )
        .filter((status) => counts[status] || filterValues(fs).includes(status))
        .map((status) => [
          status,
          `${status.startsWith('refund:') ? refundStatusLabel(status) : status.startsWith('amazon:') ? amazonStatusLabel(status.slice(7)) : status.startsWith('stopstart:') ? status.slice(10) : status.startsWith('xdp:') ? amazonStatusLabel(status.slice(4)) : status.startsWith('palletways:') ? status.slice(11) : status} (${counts[status] || 0})`,
        ]),
    ];
    const hasFilters = Boolean(
      fstore ||
        fs ||
        fsrc ||
        fclassification.length ||
        fbookedIn ||
        fbookInRequest ||
        fd ||
        ft ||
        trackingScope,
    );

    return `<div class="bar delivery-filters">
      <label class="delivery-search">
        ${ico('search', 18)}
        <input type="search" id="q" data-delivery-search placeholder="Search delivery" value="${esc(q)}" aria-label="Search deliveries">
      </label>

      ${!isMainTrackingMethod(fsrc) ? UiSelect.render(
        'dotherMethodValue',
        isMainTrackingMethod(fsrc) ? '' : fsrc,
        [['', `Other Delivery Method (${otherMethodTotal})`],
          ...otherMethods.map(([value, count]) => [value, `${value === 'SUPPLIER' ? 'Supplier' : value} (${count})`])],
        {
          ariaLabel: 'Filter other delivery methods',
          className: 'delivery-other-method-select',
          onChange: (value) => setScope(value, 'method'),
        },
      ) : ''}
      ${UiSelect.render(
        'dstoreValue',
        fstore,
        [['', 'All stores'], ...stores.map((store) => [store, store])],
        {
          ariaLabel: 'Filter by store',
          className: 'delivery-store-select',
          multiple: true,
          selectionLabel: 'stores selected',
          onChange: (value) => {
            fstore = value;
            R();
          },
        },
      )}
      ${categoryOptions.length > 1 ? UiSelect.render(
        'dscopeValue',
        compactFilter([
          ...filterValues(trackingScope),
          ...(fsrc === 'Palletways' && dashboardWidgetFilter === 'palletways-depot-3days'
            ? ['palletways-depot-3days']
            : []),
        ]),
        categoryOptions,
        {
          ariaLabel: 'Filter categories',
          className: 'delivery-scope-select',
          multiple: true,
          selectionLabel: 'categories selected',
          onChange: (value) => {
            const selected = filterValues(value);
            if (fsrc === 'Palletways' && selected.includes('palletways-depot-3days')) {
              dashboardWidgetFilter = 'palletways-depot-3days';
            } else if (dashboardWidgetFilter === 'palletways-depot-3days') {
              dashboardWidgetFilter = '';
            }
            trackingWidgetFacets = null;
            setScope(
              compactFilter(selected.filter((item) => item !== 'palletways-depot-3days')),
              'general',
              false,
            );
          },
        },
      ) : ''}
      ${UiSelect.render('dstatusValue', fs, statusOptions, {
        ariaLabel: 'Filter by status',
        className: 'delivery-select',
        multiple: true,
        selectionLabel: 'statuses selected',
        onChange: (value) => {
          fs = value;
          R();
        },
      })}

      <div class="ui-select delivery-date-select" data-date-filter>
        <button class="ui-select-trigger" id="dbtn" type="button" aria-expanded="false" aria-label="${widgetDateLabel() ? esc(dateLabel()) : 'Filter by delivery date'}" data-delivery-filter-action="toggle-date">
          <span class="ui-select-label">${esc(dateLabel())}</span>
          <span class="ui-select-chevron">${ico('chevdown', 16, 2)}</span>
        </button>
        <div class="ui-select-menu ui-date-menu" id="dpn" hidden>
          ${widgetDateLabel() ? `<p class="tracking-widget-date-scope" role="status">${esc(widgetDateLabel())} (UK). Applied by the dashboard widget. Use Clear filters to remove it.</p><p>Additional delivery date range:</p>` : ''}
          <div class="delivery-date-fields">
            <label><span>From</span><input type="date" data-delivery-date="from" value="${esc(fd)}"></label>
            <label><span>To</span><input type="date" data-delivery-date="to" value="${esc(ft)}"></label>
          </div>
          <button class="delivery-date-clear" type="button" data-delivery-filter-action="clear-dates">Clear dates</button>
        </div>
      </div>

      ${hasFilters ? '<button class="delivery-clear" type="button" title="Clear filters" data-delivery-filter-action="clear-all">Clear filters</button>' : ''}
    </div>`;
  }

  function handleClick(event) {
    const actionButton = event.target.closest('[data-delivery-filter-action]');
    if (!actionButton) return false;

    event.stopPropagation();
    const action = actionButton.dataset.deliveryFilterAction;

    if (action === 'toggle-booking') {
      toggleBooking(actionButton);
      return true;
    }

    if (action === 'booking') {
      const field = actionButton.dataset.bookingField;
      if (field === 'booked_in') fbookedIn = actionButton.dataset.value;
      else if (field === 'book_in_request') fbookInRequest = actionButton.dataset.value;
      closeAll();
      R();
      $(`[data-delivery-filter-action="toggle-booking"][data-booking-field="${field}"]`)?.focus();
      return true;
    }

    if (action === 'toggle-date') {
      toggleDate();
      return true;
    }

    if (action === 'toggle-classification') {
      toggleClassification(actionButton);
      return true;
    }

    if (action === 'classification') {
      const value = actionButton.dataset.value || '';
      if (!value) fclassification = [];
      else if (fclassification.includes(value))
        fclassification = fclassification.filter((item) => item !== value);
      else fclassification = [...fclassification, value];
      fs = compactFilter(filterValues(fs).filter((value) => trackingLevelCounts().statuses[value]));
      syncClassificationFilter();
      const filters = document.querySelector('.delivery-filters');
      if (filters) filters.outerHTML = render();
      if (document.body.dataset.live === 'true' && liveReady) loadTrackingPage(true);
      else rows();
      return true;
    }

    if (action === 'method' || action === 'general') {
      setScope(actionButton.dataset.value || '', action);
      return true;
    }

    if (action === 'clear-dates') {
      fd = '';
      ft = '';
      closeAll();
      R();
      return true;
    }

    if (action === 'clear-all') {
      fadeClearFilter(actionButton);
      fstore = '';
      fs = '';
      fmethod = '';
      fclassification = [];
      fbookedIn = '';
      fbookInRequest = '';
      fsrc = '';
      fd = '';
      ft = '';
      trackingScope = '';
      dashboardWidgetFilter = '';
      trackingWidgetFacets = null;
      history.replaceState({ page }, '', PAGE_URL[page]);
      closeAll();
      UiSelect.closeAll();
      R();
      return true;
    }

    return false;
  }

  function handleInput(event) {
    const search = event.target.closest('[data-delivery-search]');
    if (!search) return false;

    q = search.value;
    if (document.body.dataset.live === 'true') {
      clearTimeout(trackingSearchTimer);
      trackingSearchTimer = setTimeout(() => loadTrackingPage(true), 250);
    } else rows();
    return true;
  }

  function handleChange(event) {
    const input = event.target.closest('[data-delivery-date]');
    if (!input) return false;

    if (input.dataset.deliveryDate === 'from') fd = input.value;
    if (input.dataset.deliveryDate === 'to') ft = input.value;
    if (document.body.dataset.live === 'true') loadTrackingPage(true);
    else rows();
    updateDateLabel();
    return true;
  }

  return {
    closeAll,
    handleChange,
    handleClick,
    handleInput,
    hasOpenMenu,
    renderClassificationMenu,
    renderBookingHeading,
    renderBookingMenus,
    render,
  };
})();

let sidebarMotion = null;
let sidebarContentMotions = [];
let sidebarWaterCleanup = () => {};
let sidebarWaterId = 0;

function sidebarWaterBounds(from, to, progress, collapsed) {
  const eased = 1 - Math.pow(1 - progress, 4);
  const pulse = Math.sin(Math.PI * progress) * Math.exp(-progress * 2);
  const mix = (key) => from[key] + (to[key] - from[key]) * eased;
  return {
    left: mix('left'),
    top: mix('top'),
    width: mix('width') + pulse * (collapsed ? -12 : 18),
    height: mix('height'),
    pulse,
  };
}

function animateSidebarWater(sidebar, from, to, collapsed, duration, startedAt) {
  const id = `sidebar-water-${++sidebarWaterId}`;
  const color = getComputedStyle(sidebar).backgroundColor;
  const origin = { x: Math.min(from.left, to.left) - 44, y: Math.min(from.top, to.top) - 44 };
  const width = Math.max(from.right, to.right) - origin.x + 56;
  const height = Math.max(from.bottom, to.bottom) - origin.y + 56;
  const layer = document.createElement('div');
  layer.className = 'sidebar-water-layer';
  layer.setAttribute('aria-hidden', 'true');
  Object.assign(layer.style, {
    left: `${origin.x}px`,
    top: `${origin.y}px`,
    width: `${width}px`,
    height: `${height}px`,
  });
  layer.innerHTML = `<svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
      <filter id="${id}-merge" x="-25%" y="-10%" width="150%" height="120%" color-interpolation-filters="sRGB">
        <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="soft"/>
        <feColorMatrix in="soft" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 18 -7" result="merged"/>
        <feTurbulence type="fractalNoise" baseFrequency=".014 .028" numOctaves="2" seed="8" result="water"/>
        <feDisplacementMap in="merged" in2="water" scale="0" xChannelSelector="R" yChannelSelector="G"/>
      </filter>
      <linearGradient id="${id}-glass" x1="0" y1="0" x2="1" y2=".8">
        <stop stop-color="#fff" stop-opacity=".32"/><stop offset=".18" stop-color="#fff" stop-opacity=".02"/>
        <stop offset=".65" stop-color="#c9f8ee" stop-opacity=".08"/><stop offset="1" stop-color="#fff" stop-opacity=".24"/>
      </linearGradient>
      <clipPath id="${id}-clip"><path data-water-clip/></clipPath>
    </defs>
    <g filter="url(#${id}-merge)" fill="${esc(color)}"><path data-water-body/>${Array.from({ length: 4 }, () => '<ellipse data-water-drop/>').join('')}</g>
    <g clip-path="url(#${id}-clip)">
      <path data-water-glass fill="url(#${id}-glass)"/>
      <g fill="none" stroke="#f0fff9" stroke-linecap="round">
        <path data-water-ribbon stroke-width="2" opacity=".28"/>
        <path data-water-ribbon stroke-width="1" opacity=".18"/>
        <path data-water-ribbon stroke-width="1.5" opacity=".12"/>
      </g>
    </g>
    <path data-water-rim fill="none" stroke="#edfff6" stroke-width="1.2"/>
  </svg>`;
  document.body.append(layer);
  sidebar.classList.add('sidebar-water-active');
  const paths = ['body', 'clip', 'glass', 'rim'].map((name) =>
    layer.querySelector(`[data-water-${name}]`),
  );
  const drops = [...layer.querySelectorAll('[data-water-drop]')];
  const ribbons = [...layer.querySelectorAll('[data-water-ribbon]')];
  const displacement = layer.querySelector('feDisplacementMap');
  let request;
  let disposed = false;
  const cleanup = () => {
    disposed = true;
    cancelAnimationFrame(request);
    layer.remove();
    sidebar.classList.remove('sidebar-water-active');
  };
  const tick = (now) => {
    if (disposed) return;
    const t = Math.min(1, Math.max(0, (now - startedAt) / duration));
    const bounds = sidebarWaterBounds(from, to, t, collapsed);
    const x = bounds.left - origin.x,
      y = bounds.top - origin.y;
    const w = bounds.width,
      h = bounds.height;
    const r = Math.min(24, w / 3);
    const energy = Math.sin(Math.PI * t) * (1 - t);
    const wave = Math.sin(t * Math.PI * 3.5) * energy * 24;
    // The long edge bows, then releases a travelling wave as the surface settles.
    const d = `M ${x + r} ${y} Q ${x + w / 2} ${y} ${x + w - r} ${y}
      Q ${x + w} ${y} ${x + w} ${y + r}
      C ${x + w + wave} ${y + h * 0.25} ${x + w - wave * 0.7} ${y + h * 0.4} ${x + w} ${y + h * 0.5}
      C ${x + w + wave * 0.6} ${y + h * 0.64} ${x + w - wave * 0.45} ${y + h * 0.82} ${x + w} ${y + h - r}
      Q ${x + w} ${y + h} ${x + w - r} ${y + h}
      Q ${x + w / 2} ${y + h} ${x + r} ${y + h}
      Q ${x} ${y + h} ${x} ${y + h - r}
      C ${x - wave * 0.3} ${y + h * 0.7} ${x + wave * 0.3} ${y + h * 0.3} ${x} ${y + r}
      Q ${x} ${y} ${x + r} ${y} Z`;
    paths.forEach((path) => path.setAttribute('d', d));
    paths[2].setAttribute('opacity', String(energy * 1.8));
    paths[3].setAttribute('opacity', String(energy * 0.8));
    displacement.setAttribute('scale', String(energy * 16));
    drops.forEach((drop, index) => {
      const phase = Math.max(0, Math.min(1, (t - 0.08 - index * 0.035) / 0.72));
      const lift = Math.sin(Math.PI * phase);
      const radius = lift * (5 + index * 1.3) * (1 - t);
      drop.setAttribute('cx', String(x + w + lift * (12 + index * 5)));
      drop.setAttribute(
        'cy',
        String(y + h * (0.2 + index * 0.19) + Math.sin(phase * Math.PI * 2) * 18),
      );
      drop.setAttribute('rx', String(radius));
      drop.setAttribute('ry', String(radius * (1.4 - lift * 0.5)));
    });
    ribbons.forEach((ribbon, index) => {
      const center = y + h * (0.18 + index * 0.27) + t * 34;
      ribbon.setAttribute(
        'd',
        `M ${x - 10} ${center} C ${x + w * 0.3} ${center - 30 * energy} ${x + w * 0.65} ${center + 50 * energy} ${x + w + 10} ${center - 12} M ${x + w - 9 - index * 4} ${y + r} Q ${x + w - 26 - wave} ${y + h * 0.5} ${x + w - 10 - index * 4} ${y + h - r}`,
      );
      ribbon.setAttribute('opacity', String(energy * (0.42 - index * 0.1)));
    });
    if (t < 1) request = requestAnimationFrame(tick);
    else cleanup();
  };
  tick(startedAt);
  return cleanup;
}

function setSidebarCollapsed(collapsed) {
  const app = $('.app');
  const sidebar = $('#side');
  if (app.classList.contains('cl') === collapsed) return;
  const desktop = matchMedia('(min-width:761px)').matches;
  const animate =
    desktop &&
    !matchMedia('(prefers-reduced-motion: reduce)').matches &&
    typeof sidebar.animate === 'function';
  const from = animate ? AtlasViewport.rect(sidebar) : null;
  const fromRadius = animate ? getComputedStyle(sidebar).borderRadius : '';
  const content = animate
    ? [
        ...sidebar.querySelectorAll(
          '.sidebar-app-icon img, .side-main a, .side-main a svg, .side-bottom a, .side-bottom a svg, .sidebar-expand',
        ),
      ]
    : [];
  const contentBefore = content.map((element) => ({
    bounds: AtlasViewport.rect(element),
    opacity: getComputedStyle(element).opacity,
  }));
  sidebarMotion?.cancel();
  sidebarContentMotions.forEach((motion) => motion.cancel());
  sidebarContentMotions = [];
  sidebarWaterCleanup();
  sidebar.style.transition = 'none';
  app.classList.toggle('cl', collapsed);
  sidebar.querySelector('.sidebar-expand')?.setAttribute('tabindex', collapsed ? '0' : '-1');
  $('.mn')?.setAttribute('aria-expanded', String(!collapsed && desktop));
  if (!animate) {
    sidebar.style.removeProperty('transition');
    return;
  }
  const to = AtlasViewport.rect(sidebar);
  const frame = (bounds, radius) => ({
    left: `${bounds.left}px`,
    top: `${bounds.top}px`,
    width: `${bounds.width}px`,
    height: `${bounds.height}px`,
    transform: 'none',
    borderRadius: radius,
  });
  const duration = collapsed ? 650 : 750;
  const contentAfter = content.map((element) => AtlasViewport.rect(element));
  sidebarContentMotions = content.map((element, index) => {
    const before = contentBefore[index];
    const after = contentAfter[index];
    const parentIndex = element.matches('a svg') ? content.indexOf(element.closest('a')) : -1;
    const parentAfter = parentIndex >= 0 ? contentAfter[parentIndex] : null;
    const parentBefore = parentIndex >= 0 ? contentBefore[parentIndex].bounds : null;
    const dx =
      before.bounds.left - after.left - (parentBefore ? parentBefore.left - parentAfter.left : 0);
    const dy =
      before.bounds.top - after.top - (parentBefore ? parentBefore.top - parentAfter.top : 0);
    const motion = element.animate(
      [
        { transform: `translate(${dx}px, ${dy}px)`, opacity: before.opacity },
        { transform: 'translate(0, 0)', opacity: getComputedStyle(element).opacity },
      ],
      {
        duration: duration - 100,
        easing: 'cubic-bezier(.22, .8, .24, 1)',
      },
    );
    motion.finished.then(
      () => {
        sidebarContentMotions = sidebarContentMotions.filter((item) => item !== motion);
      },
      () => {},
    );
    return motion;
  });
  const toRadius = getComputedStyle(sidebar).borderRadius;
  const frames = Array.from({ length: 61 }, (_, index) => {
    const t = index / 60;
    const bounds = sidebarWaterBounds(from, to, t, collapsed);
    return {
      ...frame(
        bounds,
        index === 0
          ? fromRadius
          : index === 60
            ? toRadius
            : `${24 + bounds.pulse * 24}px ${24 + bounds.pulse * 38}px ${24 + bounds.pulse * 18}px ${24 + bounds.pulse * 30}px`,
      ),
      offset: t,
    };
  });
  const startedAt = performance.now();
  const motion = sidebar.animate(frames, { duration, easing: 'linear' });
  sidebarWaterCleanup = animateSidebarWater(sidebar, from, to, collapsed, duration, startedAt);
  sidebarMotion = motion;
  motion.finished.then(
    () => {
      if (sidebarMotion !== motion) return;
      sidebarMotion = null;
      sidebarWaterCleanup();
      sidebar.style.removeProperty('transition');
    },
    () => {},
  );
}

const isOrderDetailPage = () => ['Dashboard', 'Deliveries', 'Replacement', 'Refund', 'Failed Deliveries'].includes(page);

const DeliveryDetail = (() => {
  const container = () => $('#dr');
  let galleryIndex = null;
  let externalGallery = null,
    galleryOpener = null;
  let galleryPortal = null;
  let galleryTransform = { scale: 1, rotation: 0, x: 0, y: 0 };
  let galleryDrag = null;
  let focusedSection = '';
  let trackingTab = 'details';
  let sidebarCollapsedBeforeOpen = null;
  let detailCloseTimer = null;

  function podItemsFor(delivery) {
    if (isCreditRefundRecord(delivery)) return [];
    const podUrl = delivery?.podUrl || delivery?.proofUrl || '';
    const podImageUrl =
      delivery?.podImageUrl ||
      (/\.(?:png|jpe?g|webp|gif|svg)(?:[?#]|$)/i.test(podUrl) ? podUrl : '');
    return Array.isArray(delivery?.podPhotos) && delivery.podPhotos.length
      ? delivery.podPhotos.filter((item) => item && item.url)
      : podUrl
        ? [{ url: podUrl, kind: 'Photo', imageUrl: podImageUrl }]
        : [];
  }

  function podPreviewMarkup(delivery, item, index, extraCount = 0) {
    const label = item.kind === 'Signature' ? 'Signature' : `Photo ${index + 1}`;
    const imageUrl = item.imageUrl || (Array.isArray(delivery.podPhotos) ? item.url : '');
    if (!imageUrl)
      return `<a class="qd-track-link" href="${esc(item.url)}" target="_blank" rel="noopener">Open proof of delivery ${ico('right', 14, 2)}</a>`;
    const preview = `<img class="qd-pod-image" data-pod-index="${index}" src="${esc(imageUrl)}" alt="${esc(label)}" loading="lazy" decoding="async">`;

    return `<button class="qd-pod-thumb" type="button" data-detail-action="open-pod-gallery" data-pod-index="${index}" aria-label="${extraCount ? `View ${extraCount} more images` : `View ${esc(label)}`}">
      <span class="qd-pod-thumb-image">${preview}</span>
      ${extraCount ? `<span class="qd-pod-overflow" aria-hidden="true">+${extraCount}</span>` : ''}
    </button>`;
  }

  function closeGallery() {
    endGalleryDrag();
    galleryIndex = null;
    container()?.querySelector('.qd-gallery-viewer')?.remove();
    if (galleryPortal) {
      const { parent, next } = galleryPortal;
      parent.insertBefore(container(), next?.parentNode === parent ? next : null);
      galleryPortal = null;
    }
    externalGallery = null;
    if (galleryOpener?.isConnected) galleryOpener.focus({ preventScroll: true });
    galleryOpener = null;
  }

  function endGalleryDrag() {
    const drag = galleryDrag;
    galleryDrag = null;
    if (!drag) return;
    drag.image.classList.remove('is-dragging');
    if (drag.image.hasPointerCapture(drag.pointerId))
      drag.image.releasePointerCapture(drag.pointerId);
  }

  function applyGalleryTransform() {
    const image = container().querySelector('.qd-gallery-image');
    const canvas = image?.closest('.qd-gallery-canvas');
    if (!image || !canvas) return;
    const rotated = galleryTransform.rotation % 180 !== 0;
    if (image.naturalWidth && image.naturalHeight && canvas.clientWidth && canvas.clientHeight) {
      const fit = Math.min(
        canvas.clientWidth / (rotated ? image.naturalHeight : image.naturalWidth),
        canvas.clientHeight / (rotated ? image.naturalWidth : image.naturalHeight),
      );
      image.style.width = `${image.naturalWidth * fit}px`;
      image.style.height = `${image.naturalHeight * fit}px`;
    }
    const { scale, rotation, x, y } = galleryTransform;
    if (scale <= 1) endGalleryDrag();
    image.classList.toggle('is-zoomed', scale > 1);
    image.style.transform = `translate(${x}px, ${y}px) rotate(${rotation}deg) scale(${scale})`;
    const reset = container().querySelector('[data-detail-action="reset-pod-view"]');
    if (reset) reset.textContent = `${Math.round(scale * 100)}%`;
    const zoomIn = container().querySelector('[data-detail-action="zoom-pod-in"]');
    const zoomOut = container().querySelector('[data-detail-action="zoom-pod-out"]');
    if (zoomIn) zoomIn.disabled = scale >= 8;
    if (zoomOut) zoomOut.disabled = scale <= 1;
  }

  function zoomGallery(factor, clientX, clientY) {
    const image = container().querySelector('.qd-gallery-image');
    const canvas = image?.closest('.qd-gallery-canvas');
    if (!image?.complete || !image.naturalWidth || !canvas) return;
    const bounds = AtlasViewport.rect(canvas);
    const x = (clientX ?? bounds.left + bounds.width / 2) - bounds.left - bounds.width / 2;
    const y = (clientY ?? bounds.top + bounds.height / 2) - bounds.top - bounds.height / 2;
    const scale = Math.max(1, Math.min(8, galleryTransform.scale * factor));
    const ratio = scale / galleryTransform.scale;
    galleryTransform.x = scale === 1 ? 0 : x - (x - galleryTransform.x) * ratio;
    galleryTransform.y = scale === 1 ? 0 : y - (y - galleryTransform.y) * ratio;
    galleryTransform.scale = scale;
    applyGalleryTransform();
  }

  function showGallery(index, preserveView = false) {
    const delivery = externalGallery || (sel ? get(sel) : null);
    const items = podItemsFor(delivery);
    if (!items.length) return;
    endGalleryDrag();
    galleryIndex = (index + items.length) % items.length;
    if (!preserveView) galleryTransform = { scale: 1, rotation: 0, x: 0, y: 0 };
    const item = items[galleryIndex];
    const label = externalGallery
      ? delivery.order
      : item.kind === 'Signature'
        ? 'Signature'
        : 'Proof of delivery photo';
    const imageUrl = item.imageUrl || (Array.isArray(delivery.podPhotos) ? item.url : '');
    container().querySelector('.qd-gallery-viewer')?.remove();
    container().insertAdjacentHTML(
      'beforeend',
      `<div class="qd-gallery-viewer" role="dialog" aria-modal="true" aria-label="${externalGallery ? 'Claim pictures' : 'Proof of delivery images'}">
      <div class="qd-gallery-backdrop" data-detail-action="close-gallery"></div>
      <div class="qd-gallery-panel">
        <div class="qd-gallery-head"><div><b>${esc(label)}</b><span>${galleryIndex + 1} of ${items.length}</span></div>
          ${
            imageUrl
              ? `<div class="qd-gallery-tools" role="toolbar" aria-label="Image controls">
            <button type="button" data-detail-action="rotate-pod" aria-label="Rotate image clockwise" title="Rotate 90 degrees">&#8635;</button>
            <button type="button" data-detail-action="zoom-pod-out" aria-label="Zoom out" title="Zoom out">&#8722;</button>
            <button type="button" class="qd-gallery-zoom-value" data-detail-action="reset-pod-view" aria-label="Reset image view" title="Reset image view">100%</button>
            <button type="button" data-detail-action="zoom-pod-in" aria-label="Zoom in" title="Zoom in">+</button>
          </div>`
              : '<div></div>'
          }
          <button type="button" class="qd-gallery-close" data-detail-action="close-gallery" aria-label="Close image viewer">${ico('x', 20)}</button></div>
        <div class="qd-gallery-stage">
          ${items.length > 1 ? `<button type="button" class="qd-gallery-arrow" data-detail-action="previous-pod" aria-label="Previous image">&#8249;</button>` : ''}
          ${imageUrl ? `<div class="qd-gallery-canvas"><img class="qd-gallery-image" src="${esc(imageUrl)}" alt="${esc(`${label} ${galleryIndex + 1} for ${delivery.order}`)}" data-gallery-image="${galleryIndex}" decoding="async" draggable="false"></div>` : `<a href="${esc(item.url)}" target="_blank" rel="noopener">Open proof of delivery</a>`}
          ${items.length > 1 ? `<button type="button" class="qd-gallery-arrow" data-detail-action="next-pod" aria-label="Next image">&#8250;</button>` : ''}
        </div>
        <div class="qd-gallery-actions">${externalGallery ? '' : `<a class="qd-track-link" href="${esc(item.url)}" target="_blank" rel="noopener">Open original ${ico('right', 14, 2)}</a><button class="qd-text" type="button" data-detail-action="copy-pod-link" data-pod-index="${galleryIndex}">${ico('copy', 15, 1.8)} Copy link</button>`}${imageUrl ? `<button class="qd-text" type="button" data-detail-action="download-pod-image" data-pod-index="${galleryIndex}">${ico('download', 15, 1.8)} Download image</button>` : ''}</div>
      </div>
    </div>`,
    );
    const image = container().querySelector('.qd-gallery-image');
    image?.addEventListener('load', applyGalleryTransform, { once: true });
    applyGalleryTransform();
    container().querySelector('.qd-gallery-close')?.focus();
  }

  async function downloadPodImage(index) {
    const image =
      container().querySelector(`[data-gallery-image="${index}"]`) ||
      container().querySelector(`.qd-pod-image[data-pod-index="${index}"]`);
    if (!image || (!sel && !externalGallery)) return;
    try {
      const source = new URL(image.currentSrc || image.src, location.href);
      const endpoint =
        source.origin === location.origin || ['data:', 'blob:'].includes(source.protocol)
          ? source.href
          : `/api/pod-image?${new URLSearchParams({ order: sel, index: String(index) })}`;
      const response = await fetch(endpoint);
      if (!response.ok) throw new Error('Image retrieval failed');
      const blob = await response.blob();
      if (!blob.type.startsWith('image/')) throw new Error('Invalid image response');
      const extension =
        {
          'image/jpeg': 'jpg',
          'image/png': 'png',
          'image/webp': 'webp',
          'image/gif': 'gif',
          'image/svg+xml': 'svg',
          'image/avif': 'avif',
        }[blob.type] || 'img';
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${externalGallery ? 'claim-picture' : 'proof-of-delivery'}-${index + 1}.${extension}`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 60000);
      toast(externalGallery ? 'Claim picture download started' : 'PoD image download started');
    } catch (error) {
      toast('Image download failed. Please try again.');
    }
  }

  function activityDescription(text) {
    const raw = String(text || '').trim();
    if (raw === 'Order created in OW') {
      return { title: 'Order created', detail: '', observed: false };
    }
    const ow = raw.match(/^OW status observed:\s*(.*)$/i);
    if (ow)
      return { title: 'OW status observed', detail: owStatusDescription(ow[1]), observed: true };
    const carrier = raw.match(/^(Palletways|OptimoRoute) status observed:\s*(.*)$/i);
    if (carrier) {
      const status = carrier[2].trim().toLowerCase();
      const names = {
        success: 'Delivered',
        failed: 'Delivery failed',
        on_route: 'Out for delivery',
        scheduled: 'Scheduled',
      };
      return {
        title: `${carrier[1]} · ${names[status] || carrier[2].replace(/_/g, ' ')}`,
        detail: '',
        observed: true,
      };
    }
    const provider = raw.match(/^OptimoRoute:\s*([^—]+?)(?:\s*—\s*([\s\S]*))?$/i);
    if (provider) {
      const status = provider[1].trim().toLowerCase();
      const names = {
        failed: 'Delivery failed',
        success: 'Delivered',
        start_service: 'Delivery started',
        'start service': 'Delivery started',
      };
      const note = provider[2]?.match(/Delivery note:\s*([\s\S]*)$/i)?.[1]?.trim() || '';
      return {
        title: `${names[status] || provider[1].trim()} · OptimoRoute`,
        detail: note && !/^fail(?:ed)?$/i.test(note) ? note : '',
        observed: /first observed|status changed|original change time is unknown/i.test(
          provider[2] || '',
        ),
      };
    }
    const issue = raw.match(/^Courier Issues\s*[·�-]\s*([^:]+):\s*([\s\S]*)$/i);
    if (issue)
      return {
        title: `Delivery issue · ${issue[1].trim()}`,
        detail: issue[2].trim(),
        observed: false,
      };
    return { title: raw, detail: '', observed: false };
  }
  function toggleCarrierScans(button) {
    const activity = button.closest('.qd-activity-log');

    if (!activity) return;

    const expanded = activity.dataset.carrierExpanded === 'true';

    const technicalEvents = activity.querySelectorAll('.qd-event[data-technical="true"]');

    technicalEvents.forEach((event) => {
      const shouldHide = expanded;

      event.hidden = shouldHide;
      event.style.display = shouldHide ? 'none' : '';
    });

    activity.dataset.carrierExpanded = String(!expanded);

    activity.querySelectorAll('.qd-carrier-more').forEach((toggle) => {
      toggle.hidden = toggle.dataset.carrierToggle === 'more' ? !expanded : expanded;
      toggle.setAttribute('aria-expanded', String(!expanded));
    });
    activity
      .querySelector(`.qd-carrier-more[data-carrier-toggle="${expanded ? 'more' : 'less'}"]`)
      ?.focus({ preventScroll: true });

    const count = activity.querySelector('.qd-log-count');

    if (count) {
      count.textContent = expanded ? activity.dataset.visibleCount : activity.dataset.totalCount;
    }
  }
  function logMarkup(delivery, collect = null) {
    const timestamp = (value) => {
      const utc = typeof value === 'object' && value ? value.utcTime : '';
      const raw =
        utc || (typeof value === 'object' && value ? value.localTime || '' : String(value || ''));
      const normalized = raw.replace(' ', 'T');
      return /^\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2})?/.test(normalized)
        ? utc && !/[Z+-]\d{0,2}:?\d{0,2}$/.test(normalized)
          ? `${normalized}Z`
          : normalized
        : '';
    };
    const day = (value) => timestamp(value).slice(0, 10);
    const events = [];
    const add = (
      kind,
      at,
      detail = '',
      observed = false,
      title = '',
      technical = false,
      source = 'ow',
    ) => {
      const date = timestamp(at);

      if (date) {
        events.push({
          kind,
          at: date,
          detail: String(detail || '').trim(),
          observed,
          title,
          technical,
          source,
        });
      }
    };
    add('created', delivery.orderDateTime || delivery.orderDate);
    const schedules = [
      ...(Array.isArray(delivery.scheduleHistory) ? delivery.scheduleHistory : []),
      delivery.providerScheduledAt ||
        delivery.providerPlannedDate ||
        delivery.palletwaysDetails?.dueAt ||
        delivery.date,
    ].filter(Boolean);
    schedules.forEach((schedule, index) => add(index ? 'rescheduled' : 'scheduled', schedule));
    if (!events.some((item) => item.kind === 'scheduled')) {
      const booking = String(delivery.bookingStatus || '');
      const match = booking.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/);
      if (match)
        add('scheduled', `${match[3]}-${match[2].padStart(2, '0')}-${match[1].padStart(2, '0')}`);
      const named = booking.match(/^(?:Delay to\s+)?(\d{1,2})-([A-Za-z]{3})-(\d{4})$/i);
      const month = named
        ? [
            'jan',
            'feb',
            'mar',
            'apr',
            'may',
            'jun',
            'jul',
            'aug',
            'sep',
            'oct',
            'nov',
            'dec',
          ].indexOf(named[2].toLowerCase()) + 1
        : 0;
      if (month)
        add(
          'scheduled',
          `${named[3]}-${String(month).padStart(2, '0')}-${named[1].padStart(2, '0')}`,
        );
    }
    add('dispatch', delivery.dispatchDate || delivery.carrierIssueDispatchDate);
    const palletwaysEvents = Array.isArray(delivery.palletwaysEvents)
      ? delivery.palletwaysEvents
      : [];
    palletwaysEvents.forEach((item) => {
      const group = String(item.group || '').toUpperCase();

      const type = String(item.type || '').toUpperCase();

      const statusCode = String(item.statusCode || '');

      let kind = 'palletways';
      let title = 'Palletways update';

      if (group === 'POD' && type === 'POD') {
        kind = 'delivered';
        title = 'Delivered · Palletways';
      } else if (group === 'POD' && type === 'IMG') {
        title = 'Proof of delivery image · Palletways';
      } else if (group === 'VP' && type === 'DAR') {
        title = 'Driver arrived · Palletways';
      } else if (group === 'VL' && type === 'SCN' && statusCode === '800') {
        kind = 'out';
        title = 'Out for delivery · Palletways';
      } else if (group === 'BIN' && type === 'BIN') {
        title = 'Delivery booking update · Palletways';
      } else if (group === 'JIN' && type === 'GDEP') {
        title = 'Departed hub · Palletways';
      } else if (group === 'BAY' && type === 'SCN') {
        title = 'Depot scan · Palletways';
      } else if (group === 'VU' && type === 'SCN') {
        title = 'Depot scan · Palletways';
      } else if (group === 'POC') {
        title = 'Consignment created · Palletways';
      } else if (group || type) {
        title = [group, type].filter(Boolean).join(' / ') + ' · Palletways';
      }

      const meta = [
        group || type ? [group, type].filter(Boolean).join('/') : '',
        statusCode ? `Status ${statusCode}` : '',
        item.codeId ? `Code ${item.codeId}` : '',
      ]
        .filter(Boolean)
        .join(' · ');

      const signature = item.podSignature ? `Signed by ${item.podSignature}` : '';

      const detail = [item.text, signature, meta].filter(Boolean).join(' — ');

      const technical =
        (group === 'VL' && type === 'SCN' && statusCode !== '800') ||
        (group === 'VU' && type === 'SCN') ||
        (group === 'BAY' && type === 'SCN') ||
        (group === 'POD' && type === 'IMG') ||
        (group === 'BIN' && type === 'BIN') ||
        group === 'POC';

      add(kind, item.at, detail, false, title, technical, 'palletways');
    });
    // Starting service proves an attempt began; it does not prove an earlier van departure.
    add('attempt', delivery.providerStartedAt);
    const issues = (
      Array.isArray(delivery.carrierIssueEntries) ? delivery.carrierIssueEntries : []
    ).filter((item) => !String(item.source || '').includes('COMPLETED VAN DELIVERIES'));
    issues.forEach((item) => {
      const combined = `${item.status || ''} ${item.note || ''}`.trim();
      const failure = /\bfailed\b|\brefused\b|\bdamaged\b|\blost\b/i.test(combined);
      if (failure) {
        const attempt = combined.match(
          /\bfailed(?:\s+delivery)?\s+(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?/i,
        );
        const year = attempt ? Number(attempt[3] || day(item.date).slice(0, 4)) : 0;
        const failedAt =
          attempt && year
            ? `${year < 100 ? year + 2000 : year}-${attempt[2].padStart(2, '0')}-${attempt[1].padStart(2, '0')}`
            : item.date;
        const reason = String(item.note || item.status || '')
          .replace(/^(?:\+?\d[\d\s]{8,}\s*[-:]\s*)?/i, '')
          .replace(/^failed\s+\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\s*[-:]?\s*/i, '')
          .trim();
        add('failed', failedAt, reason || item.status);
      }
      const message = String(item.messageStatus || '').trim();
      const messageDate = message.match(/\b(?:on\s+)?(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/i);
      if (message && messageDate) {
        const year = Number(messageDate[3] || day(item.date).slice(0, 4));
        if (year)
          add(
            'followup',
            `${year < 100 ? year + 2000 : year}-${messageDate[2].padStart(2, '0')}-${messageDate[1].padStart(2, '0')}`,
            message,
          );
      }
      const schedule = String(item.scheduledStatus || '').trim();
      const reschedule = schedule.match(/\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/);
      if (reschedule) {
        const year = Number(reschedule[3] || day(item.date).slice(0, 4));
        if (year)
          add(
            'rescheduled',
            `${year < 100 ? year + 2000 : year}-${reschedule[2].padStart(2, '0')}-${reschedule[1].padStart(2, '0')}`,
            schedule,
          );
      }
    });
    (delivery.followUps || []).forEach((item) => {
      const remark = String(item.remark || '').trim();
      const dated = remark.match(/\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b/);
      const year = dated ? Number(dated[3] || day(item.at).slice(0, 4)) : 0;
      const at =
        dated && year
          ? `${year < 100 ? year + 2000 : year}-${dated[2].padStart(2, '0')}-${dated[1].padStart(2, '0')}`
          : item.at;
      if (
        /^delivered\b/i.test(remark) &&
        /delivered/i.test(String(delivery.st || '')) &&
        String(delivery.completedAt || '').slice(0, 10) === String(at).slice(0, 10)
      )
        return;
      add('followup', at, remark, !dated);
    });
    (delivery.providerAttemptHistory || []).forEach((item) => {
      if (item.status === 'failed') add('failed', item.at, item.note);
      if (item.status === 'success') add('delivered', item.at, item.note);
    });
    if (String(delivery.providerStatus || '').toLowerCase() === 'failed') {
      add(
        'failed',
        delivery.providerEndedAt ||
          delivery.failedAt ||
          delivery.completedAt ||
          delivery.failedDate,
        delivery.providerPodNote || delivery.reason,
      );
    } else if (!events.some((item) => item.kind === 'failed')) {
      add(
        'failed',
        delivery.failedAt || delivery.failedDate,
        delivery.carrierIssueReason || delivery.reason,
      );
    }
    const delivered = /delivered|success|completed/i.test(String(delivery.st || ''));

    const hasPalletwaysDelivered = palletwaysEvents.some(
      (item) =>
        String(item.group || '').toUpperCase() === 'POD' &&
        String(item.type || '').toUpperCase() === 'POD',
    );

    if (delivered && !hasPalletwaysDelivered) {
      add(
        'delivered',
        delivery.providerEndedAt ||
          delivery.completedAt ||
          delivery.palletwaysDetails?.dateCompleted,
        '',
        false,
        '',
        false,
        delivery.statusSource === 'Palletways' ? 'palletways' : 'ow',
      );
    }
    (delivery.logs || []).forEach((item) => {
      const label = String(item.text || '');
      if (/^Routine Dashboard - Live(?: booking status)?:/i.test(label)) {
        const bookingUpdate = /^Routine Dashboard - Live booking status:/i.test(label);
        const detail = label
          .replace(/^Routine Dashboard - Live(?: booking status)?:\s*/i, '')
          .replace(/\s*\(#[0-9a-f]{6}\s*,\s*[A-Z]+\d+\)\s*$/i, '')
          .trim();
        const isFailed = !bookingUpdate && /^Failed\b/i.test(detail);
        add(
          bookingUpdate ? 'booking-update' : isFailed ? 'routine-failed' : 'routine-update',
          item.at,
          isFailed ? '' : detail,
          true,
          bookingUpdate
            ? 'Booking status updated'
            : isFailed
              ? 'Delivery failed'
              : 'Delivery status updated',
          false,
          'routine',
        );
      }
      const exact = /Timestamp supplied in order completion details/i.test(label);
      const owStatus = label.match(/^OW status observed:\s*(.+)$/i);
      if (owStatus) add('ow-status', item.at, owStatusDescription(owStatus[1]), true);
      if (
        exact &&
        /^OptimoRoute:\s*Failed/i.test(label) &&
        !events.some((event) => event.kind === 'failed' && day(event.at) === day(item.at))
      )
        add('failed', item.at, delivery.providerPodNote);
      if (
        exact &&
        /^OptimoRoute:\s*Success/i.test(label) &&
        !events.some((event) => event.kind === 'delivered')
      )
        add('delivered', item.at);
      if (
        /^OptimoRoute status observed:\s*on_route$/i.test(label) &&
        !events.some((event) => event.kind === 'out')
      )
        add('out', item.at, '', true);
      if (
        /^Palletways status observed:\s*out[_ ]for[_ ]delivery$/i.test(label) &&
        !events.some((event) => event.kind === 'out')
      )
        add('out', item.at, '', true, '', false, 'palletways');
    });
    if (
      delivery.statusSource === 'Routine Dashboard - Live' &&
      !events.some((item) => ['routine-update', 'routine-failed'].includes(item.kind))
    ) {
      const isFailed = (delivery.routineLiveStatus || delivery.st) === 'Failed';
      add(
        isFailed ? 'routine-failed' : 'routine-update',
        delivery.routineLiveObservedAt,
        isFailed ? '' : delivery.routineLiveStatus || delivery.st,
        true,
        isFailed ? 'Delivery failed' : 'Delivery status observed',
        false,
        'routine',
      );
    }
    if (statusSourceLabel(delivery) === 'OW' && delivery.rawStatus) {
      const currentOwStatus = owStatusDescription(delivery.rawStatus);
      if (!events.some((item) => item.kind === 'ow-status' && item.detail === currentOwStatus)) {
        add('ow-status', delivery.updatedAt || delivery.firstSeenAt, currentOwStatus, true);
      }
    }
    const unique = [];
    const sameDetail = (a, b) => {
      const first = a.toLowerCase().replace(/\s+/g, ' ').trim();
      const second = b.toLowerCase().replace(/\s+/g, ' ').trim();
      return !first || !second || first === second;
    };
    events.forEach((item) => {
      const timed = item.at.includes('T');
      const index = unique.findIndex(
        (previous) =>
          previous.kind === item.kind &&
          day(previous.at) === day(item.at) &&
          sameDetail(previous.detail, item.detail) &&
          (!timed ||
            !previous.at.includes('T') ||
            previous.at.slice(0, 16) === item.at.slice(0, 16)),
      );
      if (index < 0) unique.push(item);
      else {
        const previous = unique[index];
        const preferred =
          (timed && !previous.at.includes('T')) || (previous.observed && !item.observed)
            ? item
            : previous;
        unique[index] = {
          ...preferred,
          detail: previous.detail.length > item.detail.length ? previous.detail : item.detail,
        };
      }
    });
    const sequence = {
      created: 0,
      scheduled: 1,
      rescheduled: 1,
      dispatch: 2,
      palletways: 3,
      out: 4,
      attempt: 5,
      'ow-status': 6,
      failed: 7,
      followup: 8,
      delivered: 9,
    };
    const ordered = unique.sort((a, b) => {
      const first = new Date(timestamp(a.at)).getTime();
      const second = new Date(timestamp(b.at)).getTime();

      if (Number.isFinite(first) && Number.isFinite(second) && first !== second) {
        return first - second;
      }

      return (sequence[a.kind] ?? 99) - (sequence[b.kind] ?? 99);
    });

    const visibleEvents = ordered.filter((item) => !item.technical);

    const technicalEvents = ordered.filter((item) => item.technical);
    const titles = {
      created: 'Order created',
      scheduled: 'Scheduled delivery',
      dispatch: 'Despatched',
      out: 'Out for delivery',
      attempt: 'Delivery attempt started',
      'ow-status': 'OW status observed',
      failed: 'Delivery failed',
      followup: 'Customer service follow-up',
      rescheduled: 'Rescheduled',
      delivered: 'Delivered',
    };

    if (Array.isArray(collect)) {
      collect.push(
        ...visibleEvents.map((item) => ({
          title: item.title || titles[item.kind] || item.kind,
          detail: item.detail,
          timeLabel: `${item.observed ? 'Recorded ' : ''}${fmtLogTime(item.at)}`,
          recordedAt: /^\d{4}-\d{2}-\d{2}$/.test(item.at) ? `${item.at}T23:59:59` : item.at,
        })),
      );
    }

    const tones = {
      'routine-failed': 'failed',
      scheduled: 'scheduled',
      rescheduled: 'scheduled',
      dispatch: 'progress',
      palletways: 'progress',
      out: 'progress',
      attempt: 'progress',
      failed: 'failed',
      followup: 'followup',
      delivered: 'success',
    };

    const renderEvent = (item) => `
      <div
        class="qd-event qd-event-${tones[item.kind] || 'neutral'}"
        data-activity-source="${item.source}"
        ${
          ['Own van', 'Self Delivery', 'LOCAL MULTIDROP'].includes(delivery.carrier)
            ? `data-activity-marker="${['failed', 'routine-failed'].includes(item.kind) ? 'failed' : item.kind === 'delivered' ? 'delivered' : ['created', 'ow-status'].includes(item.kind) ? 'ow' : 'neutral'}"`
            : delivery.carrier === 'Palletways'
              ? `data-activity-marker="${item.source === 'ow' ? 'ow' : item.kind === 'delivered' ? 'delivered' : 'neutral'}"`
              : ''
        }
        data-technical="${item.technical ? 'true' : 'false'}"
        ${item.technical ? 'hidden' : ''}
        style="${item.technical ? 'display:none;' : ''}"
      >
        <span
          class="qd-event-marker"
          aria-hidden="true">
        </span>

        <div class="qd-event-card">
          <div class="qd-event-top">
            <b>
              ${esc(item.title || titles[item.kind] || item.kind)}
            </b>

            <time>
              ${item.observed ? 'Recorded ' : ''}
              ${esc(fmtLogTime(item.at))}
            </time>
          </div>

          ${item.detail ? `<p class="qd-event-detail">${esc(item.detail)}</p>` : ''}
        </div>
      </div>
    `;

    const markup = ordered.length
      ? ordered.map(renderEvent).join('')
      : '<p class="mut">No activity yet.</p>';

    const carrierToggle = (expanded = false) =>
      technicalEvents.length
        ? `
        <button
          type="button"
          class="qd-carrier-more"
          aria-expanded="false"
          data-detail-action="toggle-carrier-scans"
          data-carrier-toggle="${expanded ? 'less' : 'more'}"
          ${expanded ? 'hidden' : ''}
        >
          ${expanded ? 'Show less' : 'Show more information'}
        </button>
      `
        : '';

    return `
      <div
        class="qd-activity-log ${delivery.carrier === 'Palletways' ? 'qd-palletways-activity' : ''}"
        data-carrier-expanded="false"
        data-visible-count="${visibleEvents.length}"
        data-total-count="${ordered.length}"
      >
        <div class="qd-title-row">
          <div class="qd-title">
            ${ico('clock', 18, 1.9)}
            <h3>Activity log</h3>
            <span class="qd-log-count">
              ${visibleEvents.length}
            </span>
          </div>
          ${carrierToggle()}
        </div>

        <div class="qd-events">
          ${markup}
        </div>

        ${carrierToggle(true)}
      </div>
    `;
  }

  function detailActionsMarkup(delivery, showHeading = false) {
    const actionCard = (icon, title, description, label) =>
      `<span class="qd-action-card-top"><span class="qd-action-card-icon" aria-hidden="true">${ico(icon, 23)}</span><span class="qd-action-card-label">${label}</span></span><strong>${title}</strong><span class="qd-action-card-description">${description}</span><span class="qd-action-card-arrow" aria-hidden="true">${ico('right', 17)}</span>`;
    return `
      <section class="qd-block qd-action-section" aria-label="Order actions">
        ${showHeading ? `<div class="qd-title-row"><div class="qd-title">${ico('clipboardcheck', 18)}<h3>Actions</h3></div></div>` : ''}
        <div class="qd-action-buttons">
          <a class="qd-action-button qd-action-create" href="./collective-note.html?order=${encodeURIComponent(delivery.order || delivery.id)}" aria-label="Generate collection note for order ${esc(delivery.order || delivery.id)}">${actionCard('plus', 'Generate Collection Note', 'Start a note with this order’s details.', 'CREATE')}</a>
          ${delivery.collectionNoteId ? `<a class="qd-action-button qd-action-view" href="./collective-note.html?view=create&amp;record=${encodeURIComponent(delivery.collectionNoteId)}" aria-label="View collection note for order ${esc(delivery.order || delivery.id)}">${actionCard('note', 'View Collection Note', 'Pick up your latest saved note.', 'SAVED')}</a>` : `<button type="button" class="qd-action-button qd-action-view" disabled aria-label="View Collection Note" title="No saved collection note for this order">${actionCard('note', 'View Collection Note', 'No saved note for this order yet.', 'NO NOTE')}</button>`}
          <button type="button" class="qd-action-button qd-action-claim" disabled aria-label="File Claim">${actionCard('clipboardcheck', 'File Claim', 'Carrier claim tools are on the way.', 'COMING SOON')}</button>
          <button type="button" class="qd-action-button qd-action-manufacture" disabled aria-label="Generate Manufacture Claims">${actionCard('pkg', 'Generate Manufacture Claims', 'Manufacturing claim tools are on the way.', 'COMING SOON')}</button>
        </div>
      </section>
    `;
  }

  function decorateRefundPanel(panel, delivery) {
    panel.classList.add('qd-tracking-view', 'qd-refund-view');
    panel.dataset.qdTab = 'refund';
    panel.setAttribute('aria-label', 'Credit and refund details');
    const status = String(delivery.rawStatus || '').trim().toUpperCase();
    const complete = ['C', 'COMPLETED'].includes(status);
    const cancelled = ['X', 'CANCELLED'].includes(status);
    const progressLabel = complete ? 'Credit note completed' : cancelled ? 'Cancelled'
      : ['H', 'ON HOLD'].includes(status) ? 'On hold' : 'Refund in progress';
    const progressStep = complete ? 4 : ['P', 'PARTIALLY DESPATCHED', 'S', 'SCHEDULED'].includes(status) ? 2 : 1;
    const created = detailDateTime(delivery.orderDateTime || delivery.orderDate) || 'Date unavailable';
    const headIcon = panel.querySelector('.qd-head-icon');
    if (headIcon) headIcon.innerHTML = ico('Refund', 26);
    const customerTitle = panel.querySelector('.qd-customer-block .qd-title h3');
    if (customerTitle) customerTitle.textContent = 'Customer information';
    panel.querySelector('.qd-head').insertAdjacentHTML('afterend', `
      <div class="qd-badges" aria-label="Refund status and source">
        <span class="qd-badge qd-badge-status">${stat(complete ? 'Delivered' : cancelled ? 'Cancelled' : 'Scheduled', owStatusDescription(delivery.rawStatus) || 'In progress')}</span>
        <span class="qd-badge">Credit / Refund</span><span class="qd-badge">OrderWise</span>
      </div>
      <section class="qd-progress" aria-label="Refund progress">
        <div class="qd-progress-top"><h3>Refund progress</h3><span>${esc(progressLabel)}</span></div>
        <div class="qd-progress-steps" aria-hidden="true">${Array.from({length: 4}, (_, index) => '<span class="' + (index < progressStep ? 'is-active' : '') + '"></span>').join('')}</div>
        <div class="qd-progress-bottom"><span>Order created &middot; ${esc(created)}</span><span>${complete ? 'Completed' : 'Not completed'}</span></div>
      </section>
    `);
    panel.querySelector('.qd-tracking').innerHTML = `
      <div class="qd-title-row"><div class="qd-title">${ico('Refund', 18)}<h3>Refund amount</h3></div></div>
      <div class="qd-refund-amount-row"><strong class="qd-refund-amount">${esc(refundAmountLabel(delivery))}</strong>
        ${complete ? '<span class="qd-refund-complete" role="status" aria-label="Refund complete" title="Refund complete">' + ico('check', 36, 3) + '</span>' : '<span class="qd-refund-pending" role="status">Not Yet</span>'}
      </div><span class="qd-refund-caption">Credit / Refund</span>
    `;
    panel.querySelector('.qd-pair').insertAdjacentHTML('afterend', detailActionsMarkup(delivery, true));
  }

  function decorateTrackingPanel(delivery, provider, podItems) {
    if (!isOrderDetailPage()) return;

    const panel = container().querySelector('.dr.qd');
    const head = panel?.querySelector('.qd-head');
    const summary = panel?.querySelector('.qd-summary');
    const customerTracking = panel?.querySelector('.qd-pair');

    if (!head || !customerTracking) return;
    if (isCreditRefundRecord(delivery)) { decorateRefundPanel(panel, delivery); return; }
    if (!summary) return;

    panel.classList.add('qd-tracking-view');
    panel.dataset.qdTab = trackingTab;

    const customerTitle = panel.querySelector('.qd-customer-block .qd-title h3');

    const trackingTitle = panel.querySelector('.qd-tracking .qd-title h3');

    if (customerTitle) {
      customerTitle.textContent = 'Customer information';
    }

    if (trackingTitle) {
      trackingTitle.textContent = 'Shipment tracking';
    }

    const trackingText = panel.querySelector('.qd-tracking-number');

    if (trackingText && !delivery.trk && !delivery.owTrackingNo) {
      trackingText.textContent = 'Tracking number not available';
    }

    const status = trackingStatus(delivery.st);
    const source =
      statusSourceLabel(delivery) === 'OW' ? 'OrderWise' : statusSourceDisplay(delivery);

    const isDelivered = status === 'Delivered';

    const hasSchedule = Boolean(
      delivery.date ||
        delivery.providerScheduledAt ||
        delivery.providerPlannedDate ||
        delivery.palletwaysDetails?.dueAt,
    );

    const hasDispatch =
      Boolean(
        delivery.dispatchDate || delivery.carrierIssueDispatchDate || delivery.providerStartedAt,
      ) || ['Out for Delivery', 'Delivered'].includes(status);

    const progressStep = isDelivered
      ? 4
      : hasDispatch
        ? 3
        : hasSchedule || status === 'Scheduled'
          ? 2
          : 1;

    const progressLabel = {
        Awaiting: 'Awaiting XDP status',
        Unscheduled: 'Awaiting despatch',
        Unassigned: 'On hold',
        Scheduled: 'Delivery scheduled',
        'Out for Delivery': 'Out for delivery',
        Delivered: 'Delivered',
        Failed: 'Delivery issue',
        Rejected: 'Delivery rejected',
        Lost: 'Shipment lost',
        Cancelled: 'Cancelled',
        Return: 'Return in progress',
      }[status] ||
      (hasDispatch ? 'In transit' : hasSchedule ? 'Delivery scheduled' : 'Awaiting despatch');

    const createdAt =
      detailDateTime(delivery.orderDateTime || delivery.orderDate) || 'Date unavailable';

    head.insertAdjacentHTML(
      'afterend',
      `
      <div class="qd-badges" aria-label="Order status and source">
        <span class="qd-badge qd-badge-status">
          ${stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery))}
        </span>

        <span class="qd-badge">
          ${esc(provider)}
        </span>

        <span class="qd-badge">
          ${esc(source)}
        </span>

      </div>

      <section class="qd-progress" aria-label="Delivery progress">
        <div class="qd-progress-top">
          <h3>Delivery progress</h3>
          <span>${esc(progressLabel)}</span>
        </div>

        <div class="qd-progress-steps" aria-hidden="true">
          ${Array.from(
            { length: 4 },
            (_, index) => `<span class="${index < progressStep ? 'is-active' : ''}"></span>`,
          ).join('')}
        </div>

        <div class="qd-progress-bottom">
          <span>Order created · ${esc(createdAt)}</span>
          <span>${isDelivered ? 'Completed' : 'Not completed'}</span>
        </div>
      </section>
    `,
    );

    summary.insertAdjacentHTML('afterbegin', `<header class="qd-detail-heading"><span class="qd-detail-heading-icon" aria-hidden="true">${ico('clipboardcheck', 19)}</span><div><h3>Order details</h3><p>Schedule, references &amp; delivery information</p></div></header>`);
    const detailIcons = {
      'Delivery method': 'truck', Source: 'link', 'Original delivery method': 'truck',
      'Order reference': 'note', 'Booking status': 'clock', 'Special instructions': 'note',
      'OrderWise status': 'pkg', 'Delivery issue': 'alert',
      'Booked In': 'clock', 'Book In Request': 'note',
    };
    const factRow = (label, value, copyInstructions = false) =>
      value
        ? `<div class="qd-summary-item" data-summary-field="${esc(label.toLowerCase().replace(/[^a-z0-9]+/g, '-'))}">
          <div>
            <span>${ico(detailIcons[label] || 'pkg', 13)}${esc(label)}</span>
            <b>${copyInstructions ? specialInstructionsMarkup(value) : esc(value)}</b>
          </div>
        </div>`
        : '';

    const showPalletwaysBooking = isPalletwaysDelivery(delivery) &&
      String(delivery.deliveryMethodRaw || '').trim().toLowerCase() !== 'palletways next day';
    const sheetBookedIn = String(delivery.palletwaysSheetBookedIn || '').trim().toLowerCase();
    const bookingDateTime = [delivery.palletwaysSheetBookInDate, delivery.palletwaysSheetBookInTime]
      .map(value => String(value || '').trim()).filter(Boolean).join('\n');
    const sheetRequest = String(delivery.palletwaysSheetBookInRequest || '').trim().toLowerCase();
    const bookingState = sheetBookedIn !== 'yes' ? 'not-yet'
      : String(delivery.palletwaysSheetBookInDate || '').trim() && String(delivery.palletwaysSheetBookInTime || '').trim() ? 'booked' : 'unknown';
    const bookedInRow = showPalletwaysBooking
      ? factRow('Booked In', sheetBookedIn === 'yes' ? bookingDateTime || '\u2014' : 'Not Yet')
          .replace('data-summary-field="booked-in"', `data-summary-field="booked-in" data-booking-state="${bookingState}"`)
      : '';
    const orderWiseRow = delivery.rawStatus ? factRow('OrderWise status', owStatusDescription(delivery.rawStatus)) : '';

    summary.insertAdjacentHTML(
      'beforeend',
      [
        factRow('Delivery method', provider),
        factRow('Source', source),

        !isPalletwaysDelivery(delivery) && delivery.carrier !== 'AMZ' && delivery.deliveryMethodRaw && delivery.deliveryMethodRaw !== provider
          ? factRow('Original delivery method', delivery.deliveryMethodRaw)
          : '',

        factRow('Order reference', delivery.orderRef || delivery.orderReference).replace('</b>', `</b>${replacementBadge(delivery)}`),
        factRow('Booking status', delivery.bookingStatus),
        showPalletwaysBooking ? orderWiseRow : '',
        showPalletwaysBooking ? factRow('Book In Request', sheetRequest === 'yes' ? 'Yes' : sheetRequest === 'no' ? 'No' : '\u2014') : '',
        ['AMZ', 'XDP', 'Stopstart'].includes(delivery.carrier) || isPalletwaysDelivery(delivery)
          ? factRow('Special instructions', delivery.specialInstructions || delivery.instructions, true)
          : '',

        showPalletwaysBooking ? bookedInRow : orderWiseRow,

        factRow('Delivery issue', delivery.reason),
      ].join(''),
    );

    const tabs = [
      ['activity', 'Activity'],
      ['details', 'Details'],
      ['documents', 'Documents'],
      ['action', 'Action'],
    ];
    customerTracking.insertAdjacentHTML(
      'afterend',
      `
      <div class="qd-section-tabs"
           role="group"
           aria-label="Order detail sections">

        ${tabs
          .map(
            ([key, label]) => `
          <button
            type="button"
            class="qd-section-tab"
            data-detail-action="tracking-tab"
            data-qd-tab="${key}"
            aria-pressed="${trackingTab === key}">
            ${label}
          </button>
        `,
          )
          .join('')}
      </div>
      ${detailActionsMarkup(delivery)}
    `,
    );


    if (
      !isPalletwaysDelivery(delivery) &&
      delivery.carrier !== 'XDP' &&
      !podItems.length &&
      !palletwaysDocumentInfo(delivery).hasAny &&
      !delivery.palletwaysPhotos?.length &&
      !delivery.palletwaysPortal?.media?.length
    ) {
      panel
        .querySelector('.qd-section-tabs')
        .insertAdjacentHTML(
          'afterend',
          '<section class="qd-documents-empty" role="status">No document found</section>',
        );
    }
  }

  // Palletways live data is loaded on demand for whichever
  // Palletways order the user opens.
  const palletwaysLiveCache = new Map();
  const palletwaysLivePending = new Set();

  function isPalletwaysDelivery(delivery) {
    return (
      String(delivery?.carrier || '')
        .trim()
        .toLowerCase() === 'palletways'
    );
  }

  function palletwaysTrackingId(delivery) {
    return String(
      delivery?.palletwaysDetails?.trackingId || delivery?.trk || delivery?.owTrackingNo || '',
    ).trim();
  }

  function palletwaysAddressText(address) {
    if (!address || typeof address !== 'object') {
      return '';
    }

    const lines = Array.isArray(address.Line) ? address.Line : address.Line ? [address.Line] : [];

    return [
      address.CompanyName,
      ...lines,
      address.Town,
      address.County,
      address.PostCode,
      address.Country,
    ]
      .map((value) => String(value || '').trim())
      .filter(Boolean)
      .join(', ');
  }

  function palletwaysAddress(addresses, type) {
    const list = Array.isArray(addresses) ? addresses : addresses ? [addresses] : [];

    return (
      list.find(
        (address) =>
          String(address?.Type || '')
            .trim()
            .toLowerCase() === String(type).toLowerCase(),
      ) || {}
    );
  }

  function palletwaysServiceText(service) {
    if (!service) return '';

    const item = Array.isArray(service) ? service[0] || {} : service;

    if (typeof item !== 'object') {
      return String(item || '');
    }

    return [item.Type, item.Code]
      .map((value) => String(value || '').trim())
      .filter(Boolean)
      .join(' ');
  }

  function applyPalletwaysLive(delivery, payload) {
    if (!delivery || !payload?.ok) {
      return;
    }

    const consignment = payload.consignment || {};

    const addresses = consignment.Address || [];

    const deliveryAddress = palletwaysAddress(addresses, 'Delivery');

    const collectionAddress = palletwaysAddress(addresses, 'Collection');

    const trackingId = String(
      payload.trackingId || consignment.TrackingID || palletwaysTrackingId(delivery) || '',
    ).trim();

    const dueDate = String(consignment.DueDate || '').trim();

    const dueTime = String(consignment.DueTime || '').trim();

    delivery.trk = trackingId || delivery.trk;

    delivery.palletwaysDetails = {
      ...(delivery.palletwaysDetails || {}),

      trackingId,

      consignmentNumber: consignment.Number || '',

      customerRef: consignment.Reference || '',

      deliveryService: palletwaysServiceText(consignment.Service),

      classification: consignment.Classification || '',

      weight: consignment.Weight || '',

      lifts: consignment.Lifts || '',

      collectionDepot: consignment.CollectionDepot || '',

      deliveryDepot: consignment.DeliveryDepot || '',

      dueDate,
      dueTime,

      dueAt: dueDate ? `${dueDate}${dueTime ? `T${String(dueTime).slice(0, 8)}` : ''}` : '',

      bookedIn: consignment.BookedIn || '',

      bookInRequest: consignment.BookInRequest || '',

      bookInContactName: consignment.BookInContactName || '',

      bookInReference: consignment.BookInReference || '',

      handBall: consignment.HandBall ?? consignment.Handball ?? '',

      tailLift: consignment.TailLift ?? '',

      insurance: consignment.Insurance ?? '',

      manifestNote: consignment.ManifestNote || '',

      pallets: consignment.Pallet || [],

      billUnits: consignment.BillUnit || [],

      collectionAddress: palletwaysAddressText(collectionAddress),

      collectionPostcode: collectionAddress.PostCode || '',

      collectionTelephone: collectionAddress.Telephone || '',

      collectionContact: collectionAddress.ContactName || '',

      deliveryAddress: palletwaysAddressText(deliveryAddress),

      deliveryPostcode: deliveryAddress.PostCode || '',

      deliveryTelephone: deliveryAddress.Telephone || '',

      deliveryContact: deliveryAddress.ContactName || '',

      accountName: consignment._account?.name || '',

      accountCode: consignment._account?.code || '',
    };

    delivery.palletwaysEvents = (Array.isArray(payload.events) ? payload.events : []).map(
      (item) => ({
        ...item,

        at: item.at || (item.date ? `${item.date}${item.time ? `T${item.time}` : ''}` : ''),
      }),
    );

    delivery.palletwaysDocuments = payload.documents || {};

    if (payload.status?.status) {
      delivery.st = payload.status.status;
    }

    if (payload.status?.label) {
      delivery.palletwaysStatusLabel = payload.status.label;
    }

    delivery.statusSource = 'Palletways';
  }

  async function loadPalletwaysLive(deliveryId) {
    const delivery = get(deliveryId);

    if (!delivery || !isPalletwaysDelivery(delivery)) {
      return;
    }

    const trackingId = palletwaysTrackingId(delivery);

    if (!/^\d{11}$/.test(trackingId)) {
      console.warn('Palletways order has no valid tracking ID:', delivery.order, trackingId);

      return;
    }

    if (palletwaysLivePending.has(trackingId)) {
      return;
    }

    const cached = palletwaysLiveCache.get(trackingId);

    if (cached?.ok) {
      applyPalletwaysLive(delivery, cached);

      return;
    }

    palletwaysLivePending.add(trackingId);
    delivery.palletwaysLiveLoading = true;
    delivery.palletwaysLiveError = '';
    if (String(sel) === String(deliveryId)) render();

    try {
      const response = await fetch(`/api/palletways/live/${encodeURIComponent(trackingId)}`, {
        cache: 'no-store',
      });

      const payload = await response.json();

      if (!response.ok) {
        throw new Error(payload.error || `Palletways HTTP ${response.status}`);
      }

      palletwaysLiveCache.set(trackingId, payload);

      applyPalletwaysLive(delivery, payload);
    } catch (error) {
      console.error('Palletways live lookup failed:', trackingId, error);
      delivery.palletwaysLiveError = error.message || 'Could not load Palletways activity.';
    } finally {
      palletwaysLivePending.delete(trackingId);
      delivery.palletwaysLiveLoading = false;
      const record = get(deliveryId);
      if (record && record !== delivery) {
        record.palletwaysLiveLoading = false;
        record.palletwaysLiveError = delivery.palletwaysLiveError;
      }

      const current = sel ? get(sel) : null;

      if (current && String(current.id) === String(deliveryId) && isPalletwaysDelivery(current)) {
        render();
      }
    }
  }

  const palletwaysCache = new Map();
  const palletwaysLoading = new Set();

  function isPalletwaysDelivery(delivery) {
    return (
      String(delivery?.carrier || '')
        .trim()
        .toLowerCase() === 'palletways'
    );
  }

  function palletwaysTrackingId(delivery) {
    return String(
      delivery?.palletwaysDetails?.trackingId || delivery?.trk || delivery?.owTrackingNo || '',
    ).trim();
  }

  async function loadPalletways(deliveryId) {
    const delivery = get(deliveryId);

    if (!delivery || !isPalletwaysDelivery(delivery)) {
      return;
    }

    const trackingId = palletwaysTrackingId(delivery);

    if (!/^\d{11}$/.test(trackingId)) {
      console.warn('No valid Palletways tracking ID', delivery.order);

      return;
    }

    if (palletwaysLoading.has(trackingId)) {
      return;
    }

    const cached = palletwaysCache.get(trackingId);

    if (cached) {
      applyPalletwaysData(delivery, cached);

      return;
    }

    palletwaysLoading.add(trackingId);

    try {
      const [apiResponse, portalResponse] = await Promise.all([
        fetch(`/api/palletways/live/${encodeURIComponent(trackingId)}`, {
          cache: 'no-store',
        }),

        fetch(`/api/palletways/portal/${encodeURIComponent(trackingId)}`, {
          cache: 'no-store',
        }),
      ]);

      const api = await apiResponse.json();

      const portal = await portalResponse.json();

      if (!apiResponse.ok) {
        throw new Error(api.error || 'Palletways API failed');
      }

      const result = {
        api,
        portal: portalResponse.ok ? portal : null,
      };

      palletwaysCache.set(trackingId, result);

      applyPalletwaysData(delivery, result);
    } catch (error) {
      console.error('Palletways lookup failed', error);
    } finally {
      palletwaysLoading.delete(trackingId);

      if (String(sel) === String(deliveryId)) {
        render();
      }
    }
  }

  function applyPalletwaysData(delivery, result) {
    const api = result.api || {};
    const portal = result.portal || {};

    const consignment = api.consignment || {};

    delivery.palletwaysEvents = Array.isArray(api.events)
      ? api.events.map((item) => ({
          ...item,

          at: item.at || (item.date ? `${item.date}${item.time ? `T${item.time}` : ''}` : ''),
        }))
      : [];

    delivery.palletwaysPortal = portal;

    delivery.palletwaysDetails = {
      ...(delivery.palletwaysDetails || {}),

      trackingId: api.trackingId || '',

      consignmentNumber: consignment.Number || '',

      customerRef: consignment.Reference || '',

      classification: consignment.Classification || '',

      weight: consignment.Weight || '',

      lifts: consignment.Lifts || '',

      collectionDepot: consignment.CollectionDepot || '',

      deliveryDepot: consignment.DeliveryDepot || '',

      dueDate: consignment.DueDate || '',

      dueTime: consignment.DueTime || '',

      bookedIn: consignment.BookedIn || '',

      bookInRequest: consignment.BookInRequest || '',

      bookInContactName: consignment.BookInContactName || '',

      bookInReference: consignment.BookInReference || '',

      manifestNote: consignment.ManifestNote || '',

      tailLift: portal.tailLiftRequested || consignment.TailLift || '',

      handBall: portal.handBallRequested || consignment.HandBall || '',

      pallets: consignment.Pallet || [],

      billUnits: consignment.BillUnit || [],
    };

    if (api.status?.status) {
      delivery.st = api.status.status;
    }

    if (api.status?.label) {
      delivery.palletwaysStatusLabel = api.status.label;
    }

    delivery.statusSource = 'Palletways';
  }

  const palletwaysPortalCache = new Map();
  const palletwaysPortalPending = new Set();

  async function loadPalletwaysPortal(deliveryId, force = false) {
    const delivery = get(deliveryId);
    if (!delivery || !isPalletwaysDelivery(delivery)) return;
    const order = String(delivery.order || deliveryId).trim();
    if (force) {
      for (const item of delivery.palletwaysPortal?.media || [])
        unavailablePalletwaysPhotos.delete(item.filename);
      for (const item of delivery.palletwaysPhotos || [])
        unavailablePalletwaysPhotos.delete(item.filename);
    }
    const pendingKey = `order:${order}`;
    if (palletwaysPortalPending.has(pendingKey)) return;
    palletwaysPortalPending.add(pendingKey);
    delivery.palletwaysPortalLoading = true;
    delivery.palletwaysLookupMatched = false;
    delivery.palletwaysPortalError = '';
    if (String(sel) === String(deliveryId)) render();
    let trackingId = '';
    try {
      const query = force ? '?refresh=1' : '';
      const matched = await fetch(
        `/api/palletways/order-tracking/${encodeURIComponent(order)}${query}`,
        { cache: 'no-store' },
      );
      const mapping = await matched.json();
      if (!matched.ok)
        throw new Error(mapping.error || 'Could not match this order in the Palletways tab.');
      trackingId = String(mapping.trackingId || '').trim();
      if (!/^\d{11}$/.test(trackingId))
        throw new Error('The matched column B value is not a valid Palletways tracking ID.');
      delivery.trk = trackingId;
      delivery.palletwaysLookupMatched = true;
      delivery.palletwaysDetails = { ...(delivery.palletwaysDetails || {}), trackingId };
      const current = get(deliveryId);
      if (current && current !== delivery) {
        current.trk = trackingId;
        current.palletwaysDetails = { ...(current.palletwaysDetails || {}), trackingId };
      }
      loadPalletwaysLive(deliveryId);
      const cached = palletwaysPortalCache.get(trackingId);
      if (!force && cached && Date.now() - cached.fetchedAt < 120000) {
        delivery.palletwaysPortal = cached.data;
      } else {
        const response = await fetch(
          `/api/palletways/portal/${encodeURIComponent(trackingId)}${query}`,
          { cache: 'no-store' },
        );
        const data = await response.json();
        if (!response.ok)
          throw new Error(data.error || `Palletways portal HTTP ${response.status}`);
        palletwaysPortalCache.set(trackingId, { data, fetchedAt: Date.now() });
        delivery.palletwaysPortal = data;
      }
    } catch (error) {
      delivery.palletwaysPortalError =
        error.message || 'Could not load Palletways shipment photos.';
    } finally {
      palletwaysPortalPending.delete(pendingKey);
      delivery.palletwaysPortalLoading = false;
      const current = get(deliveryId);
      if (current && current !== delivery) {
        Object.assign(current, {
          palletwaysPortal: delivery.palletwaysPortal,
          palletwaysPortalLoading: false,
          palletwaysPortalError: delivery.palletwaysPortalError,
        });
        if (trackingId) {
          current.trk = trackingId;
          current.palletwaysDetails = { ...(current.palletwaysDetails || {}), trackingId };
        }
      }
      if (String(sel) === String(deliveryId)) render();
    }
  }

  function renderPalletwaysProgress(delivery) {
    if (!isPalletwaysDelivery(delivery)) return;
    const live = palletwaysLivePending.has(palletwaysTrackingId(delivery));
    const portal = delivery.palletwaysPortalLoading;
    const panel = container().querySelector('.qd-tracking-view');
    const tabs = panel?.querySelector('.qd-section-tabs');
    if (!tabs) return;
    if (live || portal) {
      const matched = delivery.palletwaysLookupMatched;
      const completed = !matched ? 0 : 1 + Number(!live) + Number(!portal);
      const percent = Math.round(completed * 100 / 3);
      const label = !matched ? 'Matching Palletways tracking number' :
        live && portal ? 'Loading activity and documents' : live ? 'Loading tracking activity' : 'Loading shipment documents';
      tabs.insertAdjacentHTML('afterend', `<div class="qd-amazon-fetching qd-amazon-loading qd-palletways-loading" role="status" aria-live="polite"><div class="qd-amazon-progress"><span class="qd-amazon-spinner" role="progressbar" aria-label="Palletways lookup steps completed" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}" aria-valuetext="${completed} of 3 steps completed" style="--qd-amazon-progress:${percent}%"></span><small>${percent}% · ${completed}/3 steps completed · ${esc(label)}</small></div></div>`);
    } else if (delivery.palletwaysLiveError) {
      tabs.insertAdjacentHTML('afterend', `<p class="qd-amazon-empty" role="alert">${esc(delivery.palletwaysLiveError)}</p>`);
    }
  }

  // Amazon data is indexed by the real tracking number.
  const amazonShippingCache = new Map();
  const amazonShippingPending = new Set();
  const amazonShippingCacheTime = new Map();

  const amazonShippingViewer = `amz-${Math.random().toString(36).slice(2)}-${Date.now().toString(36)}`;

  let amazonShippingSelectionSerial = 0;
  const amazonShippingStarts = new Map();
  let amazonClaimOpenFor = '';

  function amazonShippingId(delivery) {
    return String(delivery?.trk || delivery?.owTrackingNo || '')
      .trim()
      .toUpperCase();
  }

  function isAmazonShippingDelivery(delivery) {
    if (!delivery) return false;
    const carrier = String(delivery.carrier || '')
      .trim()
      .toLowerCase();
    return ['amz', 'amazon', 'amazon shipping'].includes(carrier);
  }

  function amazonProgressMarkup(delivery) {
    const progress = amazonShippingStarts.get(amazonShippingId(delivery))?.progress;
    const completed = Math.max(0, Math.min(7, Number(progress?.completed) || 0));
    const percent = Math.round((completed * 100) / 7);
    const label = progress?.label || 'Waiting for Amazon lookup';
    return `<div class="qd-amazon-progress">
      <span class="qd-amazon-spinner" role="progressbar" aria-label="Amazon lookup steps completed" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${percent}" aria-valuetext="${completed} of 7 steps completed" style="--qd-amazon-progress: ${percent}%"></span>
      <small class="qd-amazon-progress-label">${percent}% · ${completed}/7 steps completed · ${esc(label)}</small>
    </div>`;
  }

  function updateAmazonProgress(trackingId, progress) {
    const job = amazonShippingStarts.get(trackingId);
    if (!job || !progress) return;
    job.progress = progress;
    const selected = sel ? get(sel) : null;
    if (amazonShippingId(selected) !== trackingId) return;
    const completed = Math.max(0, Math.min(7, Number(progress.completed) || 0));
    const percent = Math.round((completed * 100) / 7);
    container()
      .querySelectorAll('.qd-amazon-spinner')
      .forEach((bar) => {
        bar.style.setProperty('--qd-amazon-progress', `${percent}%`);
        bar.setAttribute('aria-valuenow', String(percent));
        bar.setAttribute('aria-valuetext', `${completed} of 7 steps completed`);
      });
    container()
      .querySelectorAll('.qd-amazon-progress-label')
      .forEach((label) => {
        label.textContent = `${percent}% · ${completed}/7 steps completed · ${progress.label || 'Loading Amazon updates'}`;
      });
  }

  function loadAmazonShipping(trackingId) {
    if (!/^[A-Z0-9-]{1,64}$/.test(trackingId)) return;

    const prior = amazonShippingStarts.get(trackingId);

    if (prior?.phase === 'active') return;

    if (prior?.phase === 'scheduled' && prior.serial === amazonShippingSelectionSerial) {
      return;
    }

    const serial = ++amazonShippingSelectionSerial;

    amazonShippingStarts.set(trackingId, {
      serial,
      phase: 'scheduled',
    });

    amazonShippingPending.add(trackingId);

    window.setTimeout(async () => {
      if (amazonShippingStarts.get(trackingId)?.serial !== serial) {
        return;
      }

      const selected = sel ? get(sel) : null;

      if (
        !isOrderDetailPage() ||
        !isAmazonShippingDelivery(selected) ||
        amazonShippingId(selected) !== trackingId ||
        serial !== amazonShippingSelectionSerial
      ) {
        amazonShippingPending.delete(trackingId);
        amazonShippingStarts.delete(trackingId);
        return;
      }

      amazonShippingStarts.get(trackingId).phase = 'active';

      const endpoint = `/api/amazon-shipping/live/${encodeURIComponent(trackingId)}`;

      const viewerParam = `viewer=${encodeURIComponent(amazonShippingViewer)}`;

      async function readSavedAmazon() {
        try {
          const response = await fetch(`/api/amazon-shipping/${encodeURIComponent(trackingId)}`, {
            cache: 'no-store',
          });

          if (!response.ok) return null;

          const result = await response.json();

          return result?.available === true && result.tracking_id === trackingId ? result : null;
        } catch (_) {
          return null;
        }
      }

      async function checkAmazon(attempt = 0) {
        const selectedOrder = sel ? get(sel) : null;

        if (
          !isOrderDetailPage() ||
          !isAmazonShippingDelivery(selectedOrder) ||
          amazonShippingId(selectedOrder) !== trackingId
        ) {
          return null;
        }

        const query = '?' + viewerParam;

        const response = await fetch(endpoint + query, {
          cache: 'no-store',
        });

        const result = await response.json();

        updateAmazonProgress(trackingId, result.progress);

        if (!response.ok) {
          throw new Error(result.error || `Amazon lookup HTTP ${response.status}`);
        }

        if (result.state === 'queued' || result.state === 'loading') {
          if (attempt >= 320) {
            throw new Error('Amazon lookup timed out. Please retry.');
          }

          await new Promise((resolve) => setTimeout(resolve, 750));

          return checkAmazon(attempt + 1);
        }

        if (result.state === 'cancelled') return null;

        if (result.state === 'error') {
          throw new Error(result.error || 'Amazon lookup failed.');
        }

        if (
          result.state !== 'ready' ||
          !result.data?.available ||
          result.data.tracking_id !== trackingId
        ) {
          throw new Error('No matching Amazon shipment was returned.');
        }

        return result.data;
      }

      try {
        const data = (await readSavedAmazon()) || (await checkAmazon());

        if (data) {
          amazonShippingCache.set(trackingId, data);
          amazonShippingCacheTime.set(trackingId, Date.now());
        }
      } catch (error) {
        amazonShippingCache.set(trackingId, {
          available: false,
          tracking_id: trackingId,
          error: error.message || 'Amazon Shipping could not load.',
        });

        amazonShippingCacheTime.set(trackingId, Date.now());
      } finally {
        if (amazonShippingStarts.get(trackingId)?.serial === serial) {
          amazonShippingPending.delete(trackingId);
          amazonShippingStarts.delete(trackingId);
        }

        const current = sel ? get(sel) : null;

        const panel = container()?.querySelector('.qd-tracking-view');

        if (
          isOrderDetailPage() &&
          current &&
          isAmazonShippingDelivery(current) &&
          panel &&
          !panel.classList.contains('qd-closing') &&
          amazonShippingId(current) === trackingId
        ) {
          render();
        }
      }
    }, 100);
  }

  function parseAmazonEventTimestamp(item) {
    const direct = String(item?.timestamp || '').trim();

    if (direct) {
      const ms = Date.parse(direct);
      if (!Number.isNaN(ms)) return ms;
    }

    const date = String(item?.date || '').trim();
    const time = String(item?.time || '').trim();
    const offset = String(item?.timezone_offset || '').trim();

    if (!date) return 0;

    const composed = `${date}T${time || '00:00'}:00${offset || ''}`;
    const ms = Date.parse(composed);

    return Number.isNaN(ms) ? 0 : ms;
  }

  function parseOwEventTimestamp(item, index = 0) {
    const recorded = String(item?.recordedAt || '').trim();
    if (recorded) {
      const ms = Date.parse(recorded);
      if (!Number.isNaN(ms)) return ms;
    }

    const date = String(item?.date || '').trim();
    const time = String(item?.time || '').trim();

    if (date) {
      const composed = `${date}T${time || '23:59'}:00`;
      const ms = Date.parse(composed);
      if (!Number.isNaN(ms)) return ms;
    }

    /*
      fallback so items without a clean datetime
      still remain in their original OW order
    */
    return 8640000000000000 + index;
  }

  function stopstartDetailText(details) {
    return (
      [
        details.expectedDelivery ? `Expected delivery: ${details.expectedDelivery}` : '',
        details.window ? `Delivery window: ${details.window} (UK time)` : '',
        details.driver ? `Driver: ${details.driver}` : '',
        details.reference ? `Stop Start Ref: ${details.reference}` : '',
      ]
        .filter(Boolean)
        .join('\n') ||
      details.raw ||
      ''
    );
  }

  function stopstartDetailsMarkup(delivery) {
    if (delivery.carrier !== 'Stopstart') return '';
    const details = delivery.stopstartDetails;
    const unavailable = typeof liveSummary !== 'undefined' && liveSummary?.stopstartUnavailable;
    return `<section class="qd-block qd-stopstart-details" aria-label="STOPSTART delivery details">
      <div class="qd-title-row"><div class="qd-title">${ico('truck', 18)}<h3>STOPSTART</h3></div></div>
      ${unavailable ? '<p class="mut">STOPSTART sheet unavailable; showing saved details when available.</p>' : ''}
      ${delivery.stopstartAmbiguous ? '<p class="mut">Multiple STOPSTART plans match this order. See the activity log for all plans.</p>' : ''}
      ${
        details
          ? `<p class="qd-event-detail">${esc(stopstartDetailText(details)).replace(/\n/g, '<br>')}</p><small class="mut">Expected delivery window, not delivery confirmation. Times are UK local time (GMT/BST).</small>`
          : !delivery.stopstartAmbiguous
            ? '<p class="mut">No matched STOPSTART details available.</p>'
            : ''
      }
    </section>`;
  }

  function mergedTrackingActivity(delivery, amazonData) {
    const owRaw = [];
    logMarkup(delivery, owRaw);

    const amazonRaw =
      amazonData?.available && Array.isArray(amazonData.events) ? amazonData.events : [];

    const owItems = owRaw.map((item, index) => {
      const title = String(item?.title || item?.label || '').trim() || 'OrderWise update';

      const detail = String(item?.detail || item?.value || '').trim();

      let timeLabel =
        String(item?.timeLabel || item?.recordedLabel || '').trim() ||
        [item?.date ? hd(item.date) : '', item?.time || ''].filter(Boolean).join(', ');

      if (
        delivery.carrier === 'Stopstart' &&
        /(?:Z|[+-]\d{2}:\d{2})$/i.test(item.recordedAt || '')
      ) {
        const instant = Date.parse(item.recordedAt);
        if (!Number.isNaN(instant))
          timeLabel = `${timeLabel.startsWith('Recorded ') ? 'Recorded ' : ''}${new Intl.DateTimeFormat(
            'en-GB',
            {
              timeZone: 'Europe/London',
              dateStyle: 'medium',
              timeStyle: 'short',
            },
          ).format(new Date(instant))} UK`;
      }

      return {
        source: 'ow',
        sourceLabel: 'OrderWise',
        sourceShort: 'OW',
        title,
        detail,
        timeLabel,
        sortTime: parseOwEventTimestamp(item, index),
      };
    });

    const amazonItems = amazonRaw.map((item) => ({
      source: 'amazon',
      sourceLabel: 'Amazon Shipping',
      sourceShort: 'AMZ',
      title: String(item?.description || 'Amazon Shipping update').trim(),
      detail: [String(item?.location || '').trim(), String(item?.note || '').trim()]
        .filter(Boolean)
        .join('\n'),
      timeLabel: [item?.date ? hd(item.date) : '', item?.time || '', item?.timezone_offset || '']
        .filter(Boolean)
        .join(' · '),
      sortTime: parseAmazonEventTimestamp(item),
    }));

    const stopstartItems = (
      delivery.carrier === 'Stopstart' && Array.isArray(delivery.stopstartEvents)
        ? delivery.stopstartEvents
        : []
    ).map((item) => {
      const instant = item.scheduledAt || item.observedAt;
      const parsed = Date.parse(instant);
      const label = Number.isNaN(parsed)
        ? ''
        : new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Europe/London',
            dateStyle: 'medium',
            timeStyle: 'short',
          }).format(new Date(parsed));
      return {
        source: 'stopstart',
        sourceLabel: 'STOPSTART',
        sourceShort: 'STOPSTART',
        title: item.scheduledAt ? 'Expected delivery (planned)' : 'STOPSTART details observed',
        detail: stopstartDetailText(item),
        timeLabel: `${item.scheduledAt ? '' : 'Recorded '}${label} UK`,
        sortTime: Number.isNaN(parsed) ? 8640000000000000 : parsed,
      };
    });

    const xdpItems = (
      delivery.carrier === 'XDP' && Array.isArray(delivery.xdpEvents) ? delivery.xdpEvents : []
    ).map((item) => {
      const labels = {
        CREATE: 'Shipment created',
        PRINT: 'Print event',
        COLLECT: 'Collection update',
        DELIVERY: 'Delivery update',
        SMS: 'SMS notification',
        'NEXT STOP': 'Next stop',
        DELIVERED: 'Delivered',
      };
      return {
        source: 'xdp',
        sourceLabel: 'XDP Activity · column M',
        sourceShort: 'XDP',
        title: labels[String(item.type || '').toUpperCase()] || item.type || 'XDP update',
        markerTitle: `${item.type || ''} ${item.text || ''}`,
        detail: [
          item.text,
          item.location ? `Location: ${item.location}` : '',
          item.barcode ? `Barcode: ${item.barcode}` : '',
          item.consignment ? `Consignment: ${item.consignment}` : '',
        ]
          .filter(Boolean)
          .join('\n'),
        timeLabel: `${hd(String(item.at || '').slice(0, 10))} · ${String(item.at || '').slice(11, 19)}`,
        sortTime: Date.parse(item.at) || 0,
      };
    });

    return [...owItems, ...amazonItems, ...stopstartItems, ...xdpItems].sort(
      (a, b) => a.sortTime - b.sortTime,
    );
  }

  function mergedTrackingActivityMarkup(delivery, amazonData) {
    const items = mergedTrackingActivity(delivery, amazonData);

    const isLoadingAmazon = !amazonData && isAmazonShippingDelivery(delivery);

    return `
      <section class="qd-block qd-activity qd-merged-activity" tabindex="-1">
        <div class="qd-title-row">
          <div class="qd-title">
            ${ico('clock', 18, 1.9)}
            <h3>Activity log</h3>
            <span class="qd-log-count">${items.length}</span>
          </div>
        </div>

        ${
          isLoadingAmazon
            ? `
          <div class="qd-amazon-fetching qd-merged-fetching"
               role="status"
               aria-live="polite">
            ${amazonProgressMarkup(delivery)}

            <div>
              <p><strong>Loading additional Amazon Shipping updates…</strong></p>
              <small>
                OrderWise activity is shown first. More events will be merged in automatically.
              </small>
            </div>
          </div>
        `
            : ''
        }

        ${
          amazonData?.error
            ? `
          <p class="qd-amazon-empty" role="alert">
            ${esc(amazonData.error)}
          </p>
        `
            : ''
        }

        ${
          delivery.carrier === 'XDP' && delivery.xdpActivityError
            ? `<p class="mut" role="alert">${esc(delivery.xdpActivityError)} Saved activity is shown below.</p>`
            : ''
        }
        ${
          delivery.carrier === 'XDP' && !delivery.xdpEvents?.length && !delivery.xdpActivityError
            ? '<p class="mut" role="status">No XDP Activity history has been loaded for this order yet.</p>'
            : ''
        }

        <div class="qd-events">
          ${items
            .map(
              (item) => `
            <div class="qd-event qd-event-neutral qd-merged-event qd-merged-event-${esc(item.source)}" data-activity-marker="${activityMarkerKind(item.source, item.markerTitle || item.title)}">
              <span class="qd-event-marker" aria-hidden="true"></span>

              <div
                class="qd-event-card"
                title="Source: ${esc(item.sourceLabel)}">

                <div class="qd-event-top">
                  <b>${esc(item.title)}</b>
                  <time>${esc(item.timeLabel || '')}</time>
                </div>

                <div class="qd-merged-source-row">
                  <span class="qd-merged-source-pill qd-merged-source-pill-${esc(item.source)}">
                    ${esc(item.sourceShort)}
                  </span>
                  <span class="qd-merged-source-text">
                    ${esc(item.sourceLabel)}
                  </span>
                </div>

                ${
                  item.detail
                    ? `<p class="qd-event-detail">${esc(item.detail).replace(/\n/g, '<br>')}</p>`
                    : ''
                }
              </div>
            </div>
          `,
            )
            .join('')}
        </div>
      </section>
    `;
  }

  function amazonClaimDraftMarkup(delivery) {
    if (!isAmazonShippingDelivery(delivery)) return '';

    const key = `dd-amazon-claim-demo:${encodeURIComponent(
      String(delivery.id || delivery.order || amazonShippingId(delivery)),
    )}`;

    let draft = {};

    try {
      draft = JSON.parse(localStorage.getItem(key) || '{}') || {};
    } catch (_) {
      draft = {};
    }

    const reasons = [
      ['', 'Choose a reason'],
      ['Lost shipment', 'Lost shipment'],
      ['Damaged shipment', 'Damaged shipment'],
      ['Missing items', 'Missing items'],
      ['Delivered but not received', 'Delivered but not received'],
      ['Other', 'Other'],
    ];

    const opened = amazonClaimOpenFor === String(delivery.id);

    return `
      <section
        class="qd-amazon-claim-panel"
        data-amazon-draft-key="${esc(key)}"
        aria-label="Amazon claim draft"
        ${opened ? '' : 'hidden'}>

        <div class="qd-amazon-claim-top">
          <div>
            <strong>Amazon Shipping claim</strong>
            <small>Draft preview only · Nothing is submitted</small>
          </div>

          <button type="button"
            class="qd-amazon-claim-close"
            data-detail-action="amazon-claim-close"
            aria-label="Close claim form">
            ${ico('x', 18)}
          </button>
        </div>

        <div class="qd-amazon-claim-fields">
          <label>
            Claim reason
            <select data-amazon-claim-field="reason">
              ${reasons
                .map(
                  ([value, label]) => `
                <option value="${esc(value)}"
                  ${draft.reason === value ? 'selected' : ''}>
                  ${esc(label)}
                </option>
              `,
                )
                .join('')}
            </select>
          </label>

          <label>
            Incident date
            <input type="date"
              data-amazon-claim-field="date"
              value="${esc(draft.date || '')}">
          </label>

          <label>
            Claim amount (£)
            <input type="number"
              min="0"
              step="0.01"
              placeholder="0.00"
              data-amazon-claim-field="amount"
              value="${esc(draft.amount || '')}">
          </label>

          <label class="qd-amazon-claim-wide">
            Description / notes
            <textarea rows="3"
              data-amazon-claim-field="description"
              placeholder="Enter demonstration details only">${esc(draft.description || '')}</textarea>
          </label>
        </div>

        <p class="qd-amazon-claim-note" role="status">
          Draft automatically saved in this browser.
          Nothing is sent to Amazon.
        </p>
      </section>
    `;
  }

  function amazonShippingActivity(data) {
    const events = data?.available && Array.isArray(data.events) ? data.events : [];

    const message = !data
      ? 'Loading saved Amazon Shipping history…'
      : data.error
        ? data.error
        : 'No saved Amazon history for this tracking ID yet.';

    return `
      <section class="qd-block qd-activity qd-amazon-activity" tabindex="-1">

        <div class="qd-title-row">
          <div class="qd-title">
            ${ico('truck', 18, 1.9)}
            <h3>Amazon Shipping activity</h3>
            <span class="qd-log-count">${events.length}</span>
          </div>
        </div>

        <p class="qd-amazon-source">
          ${
            data?.available
              ? 'Amazon Shipping · Retrieved on demand'
              : !data
                ? 'Amazon Shipping · Loading additional updates'
                : 'Amazon Shipping · Not available'
          }
        </p>

        <div class="qd-events">
          ${
            !data
              ? `
            <div class="qd-amazon-fetching"
                 role="status"
                 aria-live="polite">

              ${amazonProgressMarkup(delivery)}

              <div>
                <p>
                  <strong>Retrieving more Amazon Shipping updates…</strong>
                </p>
                <small>
                  OrderWise activity is available above.
                  Please wait.
                </small>
              </div>
            </div>
          `
              : ''
          }
          ${
            events.length
              ? events
                  .map(
                    (item) => `
            <div class="qd-event qd-event-neutral qd-amazon-event">
              <span class="qd-event-marker" aria-hidden="true"></span>

              <div class="qd-event-card">
                <div class="qd-event-top">
                  <b>${esc(item.description || 'Amazon update')}</b>
                  <time>${esc(
                    [item.date ? hd(item.date) : '', item.time, item.timezone_offset]
                      .filter(Boolean)
                      .join(' · '),
                  )}</time>
                </div>

                ${item.location ? `<p class="qd-event-detail">${esc(item.location)}</p>` : ''}

                ${
                  item.note ? `<p class="qd-event-detail qd-amazon-note">${esc(item.note)}</p>` : ''
                }
              </div>
            </div>
          `,
                  )
                  .join('')
              : data
                ? `
            <p class="qd-amazon-empty">${esc(message)}</p>
          `
                : ''
          }
        </div>
      </section>
    `;
  }

  function amazonShippingDocuments(data) {
    const docs = data?.documents || {};

    const available = Boolean(data?.available);
    const pdf = available && docs.pod_available;

    if (!pdf) {
      return '<section class="qd-documents-empty" role="status">No document found</section>';
    }

    return `
      <section class="qd-block qd-pod qd-amazon-documents">

        <div class="qd-title-row">
          <div class="qd-title">
            ${ico('note', 18, 1.9)}
            <h3>Amazon Shipping documents</h3>
          </div>
        </div>

        <p class="qd-amazon-source">
          Saved capture documents · Demo mode
        </p>

        <div class="qd-amazon-doc-grid">

          <article class="qd-amazon-doc-card">
            <h4><a href="${esc(docs.pod_view_url)}" target="_blank" rel="noopener noreferrer" aria-label="Open proof of delivery PDF">Proof of Delivery PDF</a>${documentViewButton(docs.pod_view_url, 'Proof of Delivery PDF')}</h4>

            ${
              pdf
                ? `
              <a
                class="qd-amazon-doc-preview"
                data-preview-state="loading"
                aria-busy="true"
                href="${esc(docs.pod_view_url)}"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Open proof of delivery PDF">

                <span class="qd-document-loading" role="status" aria-label="Loading proof of delivery PDF"><span class="qd-document-donut" aria-hidden="true"></span></span>
                <span class="qd-document-error" role="status">Preview unavailable. Click to open.</span>
                <iframe
                  title="First page of proof of delivery"
                  data-document-preview
                  src="${esc(docs.pod_view_url)}#page=1&toolbar=0&navpanes=0"
                  loading="lazy"
                  tabindex="0">
                </iframe>
              </a>
            `
                : `
              <div class="qd-amazon-doc-preview qd-amazon-doc-missing">
                ${ico('note', 35, 1.5)}
                <span>No document found</span>
              </div>
            `
            }

            <div class="qd-amazon-doc-footer">
              <span>${pdf ? 'Actual saved PDF' : 'Unavailable'}</span>

              ${
                pdf
                  ? `
                <a
                  class="qd-amazon-doc-download"
                  href="${esc(docs.pod_download_url)}">
                  ${ico('download', 15)}
                  Download
                </a>
              `
                  : ''
              }
            </div>
          </article>



        </div>
      </section>
    `;
  }

  function renderAmazonShippingContent(delivery) {
    if (!isOrderDetailPage() || isCreditRefundRecord(delivery) || !isAmazonShippingDelivery(delivery)) {
      return;
    }

    const panel = container()?.querySelector('.dr.qd.qd-tracking-view');

    if (!panel) return;

    const trackingId = amazonShippingId(delivery);
    const validId = /^[A-Z0-9-]{1,64}$/.test(trackingId);

    const data = validId ? amazonShippingCache.get(trackingId) : null;

    if (validId && !data) {
      loadAmazonShipping(trackingId);
    }

    // 1. Add Amazon activity AFTER existing OrderWise activity.

    const activity = panel.querySelector('.qd-activity');

    if (activity) {
      activity.outerHTML = mergedTrackingActivityMarkup(
        delivery,
        data ||
          (validId ? null : { error: 'No valid Amazon Shipping tracking ID for this order.' }),
      );
    }

    // 2. Add PDF and Excel cards to the Documents tab.

    const tabs = panel.querySelector('.qd-section-tabs');

    const loading = panel.querySelector('.qd-merged-fetching');
    if (tabs && loading) {
      loading.classList.add('qd-amazon-loading');
      tabs.insertAdjacentElement('afterend', loading);
    }
    if (tabs && !data && validId) {
      const empty = panel.querySelector('.qd-documents-empty');
      if (empty) empty.textContent = 'Checking documents…';
    }

    if (tabs && data) {
      panel.querySelector('.qd-documents-empty')?.remove();

      tabs.insertAdjacentHTML('afterend', amazonShippingDocuments(data));
    }

    if (!data?.available) return;

    // 3. Add only the five requested fields under Source.

    const summary = panel.querySelector('.qd-summary');

    if (!summary) return;

    const rows = [
      ['Amazon reference', data.reference],
      ['Shipping speed', data.shipping_speed],
      ['Package size', data.package_size],
      ['Package weight', data.package_weight],
      ['Total charge', data.total_charge],
    ].filter(([, value]) => String(value || '').trim());

    const markup = rows
      .map(
        ([label, value]) => `
      <div class="qd-summary-item qd-amazon-detail-row">
        <div>
          <span>${esc(label)}</span>
          <b>${esc(value)}</b>
        </div>
      </div>
    `,
      )
      .join('');

    const sourceRow = [...summary.querySelectorAll('.qd-summary-item')].find(
      (item) => item.querySelector('span')?.textContent.trim() === 'Source',
    );

    if (sourceRow) {
      sourceRow.insertAdjacentHTML('afterend', markup);
    } else {
      summary.insertAdjacentHTML('beforeend', markup);
    }
  }

  function open(id, section = '') {
    if (!get(id)) return;
    if (detailCloseTimer !== null) {
      clearTimeout(detailCloseTimer);
      detailCloseTimer = null;
    }

    if (String(sel) !== String(id)) {
      amazonClaimOpenFor = '';
      amazonShippingSelectionSerial++;
    }

    const amazonDelivery = get(id);
    const selectedDelivery = get(id);

    if (isOrderDetailPage() && !isCreditRefundRecord(amazonDelivery) && isAmazonShippingDelivery(amazonDelivery)) {
      const trackingId = amazonShippingId(amazonDelivery);
      const cached = amazonShippingCache.get(trackingId);

      const age = Date.now() - (amazonShippingCacheTime.get(trackingId) || 0);

      // Successful results last for this page session.
      // Refreshing the browser creates a new page session.
      const maxAge = cached?.available ? Infinity : 30000;

      if (cached && age >= maxAge) {
        amazonShippingCache.delete(trackingId);
        amazonShippingCacheTime.delete(trackingId);
      }
    }

    closeGallery();
    sel = id;
    galleryIndex = null;
    focusedSection = section;

    if (
      isOrderDetailPage() && !isCreditRefundRecord(get(id)) &&
      String(get(id)?.carrier || '')
        .trim()
        .toLowerCase() === 'palletways'
    ) {
      loadPalletwaysPortal(id);
    }

    trackingTab = ['activity', 'details', 'documents', 'action'].includes(section)
      ? section
      : isOrderDetailPage() && isAmazonShippingDelivery(get(id))
        ? 'activity'
        : section === 'activity'
          ? 'activity'
          : 'details';
    const app = $('.app');
    if (sidebarCollapsedBeforeOpen === null) {
      sidebarCollapsedBeforeOpen = app.classList.contains('cl');
    }
    setSidebarCollapsed(true);
    app.classList.add('detail-open');
    app.classList.remove('mobile-open');
    $('.mn')?.setAttribute('aria-expanded', 'false');
    render();
  }

  function close() {
    if (detailCloseTimer !== null) return;

    const panel = container().querySelector('.dr.qd.qd-tracking-view');

    if (isOrderDetailPage() && panel) {
      panel.classList.remove('sl');
      panel.classList.add('qd-closing');

      const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      detailCloseTimer = window.setTimeout(
        () => {
          detailCloseTimer = null;

          sel = null;
          galleryIndex = null;
          focusedSection = '';

          render();
        },
        reducedMotion ? 0 : 320,
      );

      return;
    }

    sel = null;
    galleryIndex = null;
    focusedSection = '';

    render();
  }

  function render() {
    if (externalGallery) {
      if (page === 'Manufacture Claims') return;
      closeGallery();
    }
    const delivery = sel ? get(sel) : null;
    if (delivery && !isCreditRefundRecord(delivery) && isPalletwaysDelivery(delivery)) {
      const cached = palletwaysLiveCache.get(palletwaysTrackingId(delivery));
      if (cached?.ok) applyPalletwaysLive(delivery, cached);
    }
    if (!delivery) {
      const app = $('.app');
      if (app.classList.contains('detail-open')) {
        setSidebarCollapsed(sidebarCollapsedBeforeOpen ?? false);
        sidebarCollapsedBeforeOpen = null;
        app.classList.remove('detail-open');
      }
      container().innerHTML = '';
      syncSelectedTrackingRow();
      return;
    }

    const previousPanel = container().querySelector('.dr.qd');
    const sameDelivery = previousPanel?.dataset.deliveryId === String(sel);
    const previousScrollTop = sameDelivery ? previousPanel.querySelector('.db')?.scrollTop || 0 : 0;

    const url = tlink(delivery);
    const trackingNumber = delivery.trk || delivery.owTrackingNo || '';
    const podItems = podItemsFor(delivery);
    const postcode =
      delivery.palletwaysDetails?.deliveryPostcode ||
      delivery.postcode ||
      splitDeliveryAddress(delivery.addr || '').secondary;
    const failed =
      trackingStatus(delivery.st) === 'Failed' ||
      (delivery.statusSource !== 'Routine Dashboard - Live' && Boolean(delivery.reason));
    const scheduledDate = delivery.date || delivery.providerPlannedDate || '';
    const window = deliveryWindow(delivery);
    const scheduledValue = delivery.amazonScheduledAt
      ? `${detailDateTime(delivery.amazonScheduledAt)} UK time`
      : delivery.providerScheduledAt
        ? detailDateTime(delivery.providerScheduledAt)
        : delivery.palletwaysDetails?.dueAt
          ? `Due by ${detailDateTime(delivery.palletwaysDetails.dueAt)}`
          : scheduledDate
            ? `${hd(scheduledDate)}${window.short !== 'TBD' ? `, ${window.short}` : ''}`
            : delivery.statusSource === 'Routine Dashboard - Live' &&
                trackingStatus(delivery.st) === 'Scheduled'
              ? 'Date unavailable'
              : 'Not scheduled';
    const completedValue =
      trackingStatus(delivery.st) === 'Delivered'
        ? detailDateTime(
            delivery.providerEndedAt ||
              delivery.completedAt ||
              delivery.palletwaysDetails?.dateCompleted,
          ) || 'Date unavailable'
        : 'Not completed yet';
    const provider = carName(delivery.carrier);
    const ownVan = delivery.carrier === 'Own van';
    const courierNotice = courierIssueFollowUpNotice(delivery);
    const customerAddress =
      delivery.providerAddress ||
      delivery.palletwaysDetails?.deliveryAddress ||
      delivery.addr ||
      '';

    const customerCopyButton = (field, value, label) =>
      isOrderDetailPage() && String(value || '').trim()
        ? `<button type="button" class="qd-customer-copy" data-detail-action="copy-customer-field" data-copy-field="${field}" aria-label="Copy ${label}" title="Copy ${label}">${ico('copy', 13, 1.8)}</button>`
        : '';
    container().innerHTML = `<aside class="dr qd ${failed ? 'qd-failed' : ''} ${sameDelivery ? '' : 'sl'}" data-delivery-id="${esc(sel)}" role="dialog" aria-label="Delivery tracking">
      <div class="db">
        <div class="qd-head">
          <span class="ic qd-head-icon ${ownVan ? 'qd-own-van-icon' : ''} ${failed ? 'is-failed' : ''}">${isAmazonShippingDelivery(delivery) ? '<img class="qd-amazon-head-image" src="/assets/amazonicon.webp" alt="Amazon Shipping">' : delivery.carrier === 'XDP' ? '<img class="qd-carrier-head-image" src="/assets/XDPiocn.png" alt="XDP">' : isPalletwaysDelivery(delivery) ? '<img class="qd-carrier-head-image" src="/assets/palletwayicon.png" alt="Palletways">' : delivery.carrier === 'Stopstart' ? '<img class="qd-carrier-head-image qd-stopstart-head-image" src="/assets/stopstarticon.png" alt="Stopstart">' : ico(ownVan ? 'truck' : failed ? 'pkgx' : 'pkg', 26, 1.8)}</span>
          <div class="qd-head-copy">
            <h2>${esc(delivery.cust)}</h2>
            <div class="qd-head-details">
            <div class="qd-head-meta">
              <span>Order #${esc(delivery.order)}</span>
              <span class="qd-head-state">${stat(carrierBadgeStatus(delivery), carrierStatusLabel(delivery))} <span class="mut">· ${esc(provider)}</span></span>
              ${delivery.deliveryMethodRaw ? `<small class="mut">Delivery method: ${esc(delivery.deliveryMethodRaw)}</small>` : ''}
              ${statusSourceLabel(delivery) !== provider ? `<small class="mut">${esc(statusSourceDisplay(delivery))}</small>` : ''}
            </div>
            </div>
          </div>
          <div class="qd-head-actions">
            <button class="x" aria-label="Close" data-detail-action="close">${ico('x', 20)}</button>
          </div>
        </div>
        ${stale(delivery)}
        ${courierNotice ? `<p class="qd-courier-notice" role="status">${esc(courierNotice.text)}</p>` : ''}
        ${isCreditRefundRecord(delivery) ? '' : `<section class="qd-summary" aria-label="Delivery summary">
          <div class="qd-summary-item" data-summary-field="scheduled">
            <div><span>${ico('clock', 14)}Scheduled</span><b>${esc(scheduledValue)}</b></div>
          </div>
          <div class="qd-summary-item ${trackingStatus(delivery.st) === 'Delivered' ? 'is-complete' : 'is-incomplete'}" data-summary-field="completed">
            <div><span>${ico('check', 14)}Completed</span><b>${esc(completedValue)}</b></div>
          </div>
        </section>`}
        <section class="qd-block qd-pair" aria-label="Customer and tracking">
          <div class="qd-customer-block">
            <div class="qd-title-row"><div class="qd-title">${ico('user', 18, 1.9)}<h3>Customer</h3></div></div>

            <div class="qd-customer">
              <span>
                ${ico('pin', 17, 1.8)}
                <span class="qd-customer-inline">${esc(customerAddress)}${customerCopyButton('address', customerAddress, 'address')}</span>
              </span>
              <div class="qd-customer-phone">
                ${ico('phone', 17, 1.8)}
                <span class="qd-customer-inline">${esc(delivery.phone || 'No phone number')}${customerCopyButton('phone', delivery.phone, 'phone number')}</span>
              </div>
              <span>
                ${ico('mail', 17, 1.8)}
                <span class="qd-customer-inline">${esc(delivery.email || 'No email')}${customerCopyButton('email', delivery.email, 'email')}</span>
              </span>
            </div>


          </div>
          ${
            isOrderDetailPage()
              ? `<div class="qd-purchase-block">
            <div class="qd-title-row"><div class="qd-title">${ico('pkg', 18, 1.9)}<h3>Purchased from</h3></div></div>
            <div class="qd-customer"><span>${esc(purchaseChannel(delivery) || 'Not available')}</span></div>
            <div class="qd-purchase-actions-row">
            ${purchaseStoreLogo(delivery, 'purchase-store-logo-detail')}
            </div>
            <div class="qd-purchase-skus"><span class="mut">SKU of items</span><div>${deliverySkuMarkup(delivery)}</div></div>
          </div>`
              : ''
          }
          <div class="qd-tracking">
            <div class="qd-title-row">
              <div class="qd-title">${ico('link', 18, 1.9)}<h3>Tracking</h3></div>
            </div>
            <span class="qd-tracking-number">Tracking No: <strong>${esc(trackingNumber || '—')}${customerCopyButton('trackingNumber', trackingNumber, 'tracking number')}</strong></span>
            ${
              url
                ? `<div class="qd-tracking-actions">
              ${url ? `<a class="qd-text qd-inline-action" href="${esc(url)}" target="_blank" rel="noopener noreferrer">${ico('right', 15, 1.8)} Open link</a><button class="qd-text" type="button" data-detail-action="copy-tracking-link">${ico('copy', 15, 1.8)} Copy link</button>` : ''}
            </div>`
                : ''
            }
            ${delivery.carrier === 'Palletways' && postcode ? `<span class="qd-tracking-postcode">Customer delivery postcode: <strong>${esc(postcode)}</strong></span>` : ''}
          </div>
        </section>
        ${isCreditRefundRecord(delivery) ? '' : palletwaysDetails(delivery, customerCopyButton)}
        ${isCreditRefundRecord(delivery) ? '' : stopstartDetailsMarkup(delivery)}
        ${
          !isCreditRefundRecord(delivery) && delivery.carrier === 'XDP'
            ? `<section class="qd-block qd-order-facts qd-provider qd-xdp-details" aria-label="XDP details">
          <div class="qd-title-row"><div class="qd-title">${ico('truck', 18, 1.9)}<h3>Courier details</h3></div></div>
          <dl class="qd-facts"><div><dt>Latest detail</dt><dd>${
            delivery.xdpLatestDetail ? esc(delivery.xdpLatestDetail).replace(/\r?\n/g, '<br>') : '—'
          }</dd></div>
          <div><dt>Parcel barcode</dt><dd>${
            delivery.xdpParcelBarcodes?.length
              ? delivery.xdpParcelBarcodes
                  .map((barcode) => `<span class="tracking-cell-line">${esc(barcode)}</span>`)
                  .join('')
              : '—'
          }</dd></div></dl>
        </section>`
            : ''
        }
        ${
          !isCreditRefundRecord(delivery) && delivery.carrier !== 'XDP' && (podItems.length || delivery.providerPodNote)
            ? `<section class="qd-block qd-pod">
          <div class="qd-title-row"><div class="qd-title">${ico('check', 18, 1.9)}<h3>Proof of delivery</h3></div>${podItems.length > 1 ? `<span class="qd-pod-count">${podItems.length} images</span>` : ''}</div>
          ${delivery.providerPodNote ? `<p class="qd-pod-note"><strong>Delivery note:</strong> ${esc(delivery.providerPodNote)}</p>` : ''}
          <div class="qd-pod-gallery qd-pod-tiles">
            ${podItems
              .slice(0, 3)
              .map((item, index) =>
                podPreviewMarkup(
                  delivery,
                  item,
                  index,
                  index === 2 ? Math.max(0, podItems.length - 3) : 0,
                ),
              )
              .join('')}
          </div>
        </section>`
            : ''
        }
        ${isCreditRefundRecord(delivery) ? '' : palletwaysDocuments(delivery)}
        ${isCreditRefundRecord(delivery) ? '' : xdpDocuments(delivery)}
        ${isCreditRefundRecord(delivery) ? '' : ['Stopstart', 'XDP'].includes(delivery.carrier) ? mergedTrackingActivityMarkup(delivery, null) : `<section class="qd-block qd-activity" tabindex="-1">${logMarkup(delivery)}</section>`}
      </div>
    </aside>`;

    decorateTrackingPanel(delivery, provider, podItems);
    renderPalletwaysProgress(delivery);
    renderAmazonShippingContent(delivery);
    const renderedPanel = container().querySelector('.qd-tracking-view');
    if (renderedPanel && trackingTab === 'details' && (!sameDelivery || previousPanel?.dataset.qdTab !== 'details')) {
      renderedPanel.classList.add('qd-details-enter');
    }

    syncSelectedTrackingRow();
    if (sameDelivery && focusedSection !== 'activity') {
      container().querySelector('.qd .db').scrollTop = previousScrollTop;
    }
    if (focusedSection === 'activity') {
      const scrollArea = container().querySelector('.db');
      const activity = container().querySelector('.qd-activity');
      if (scrollArea && activity) {
        scrollArea.scrollTop +=
          AtlasViewport.rect(activity).top - AtlasViewport.rect(scrollArea).top - 16;
        activity.focus({ preventScroll: true });
      }
    }
    if (galleryIndex !== null) showGallery(galleryIndex, true);
  }

  container().addEventListener('load', settlePalletwaysPreview, true);
  container().addEventListener('error', settlePalletwaysPreview, true);

  container().addEventListener('input', (event) => {
    const panel = event.target.closest('.qd-amazon-claim-panel');

    if (!panel || !isOrderDetailPage()) return;

    const delivery = sel ? get(sel) : null;

    if (!isAmazonShippingDelivery(delivery)) return;

    const draft = {};

    panel.querySelectorAll('[data-amazon-claim-field]').forEach((field) => {
      draft[field.dataset.amazonClaimField] = field.value;
    });

    try {
      localStorage.setItem(panel.dataset.amazonDraftKey, JSON.stringify(draft));
    } catch (_) {
      // Local storage unavailable. The form remains a demo.
    }
  });

  container().addEventListener('click', (event) => {
    const button = event.target.closest('[data-detail-action]');

    if (!button) return;

    if (button.dataset.detailAction === 'toggle-carrier-scans') {
      toggleCarrierScans(button);
      return;
    }

    if (
      button.dataset.detailAction === 'amazon-claim-toggle' ||
      button.dataset.detailAction === 'amazon-claim-close'
    ) {
      const delivery = sel ? get(sel) : null;

      if (!isOrderDetailPage() || !isAmazonShippingDelivery(delivery)) {
        return;
      }

      const panel = container().querySelector('.qd-tracking-view');

      const form = panel?.querySelector('.qd-amazon-claim-panel');

      const trigger = panel?.querySelector('.qd-amazon-claim-button');

      if (!form) return;

      const opening = button.dataset.detailAction === 'amazon-claim-toggle' && form.hidden;

      form.hidden = !opening;

      amazonClaimOpenFor = opening ? String(delivery.id) : '';

      trigger?.setAttribute('aria-expanded', String(opening));

      if (opening) {
        form.scrollIntoView({
          behavior: 'smooth',
          block: 'nearest',
        });
      }

      return;
    }

    if (button.dataset.detailAction === 'copy-customer-field') {
      const current = sel ? get(sel) : null;
      if (!current) return;

      const values = {
        address:
          current.providerAddress ||
          current.palletwaysDetails?.deliveryAddress ||
          current.addr ||
          '',
        phone: current.phone || '',
        email: current.email || '',
        trackingNumber: current.trk || current.owTrackingNo || '',
        consignmentNumber: current.palletwaysDetails?.consignmentNumber || '',
        deliveryService: current.palletwaysDetails?.deliveryService || '',
      };

      const labels = {
        address: 'Address',
        phone: 'Phone number',
        email: 'Email',
        trackingNumber: 'Tracking number',
        consignmentNumber: 'Consignment number',
        deliveryService: 'Delivery service',
      };

      const field = button.dataset.copyField;

      if (!Object.prototype.hasOwnProperty.call(values, field)) return;

      const value = String(values[field]).trim();

      if (value) {
        copyText(value, `${labels[field]} copied`);
      }

      return;
    }

    if (button.dataset.detailAction === 'tracking-tab') {
      if (!isOrderDetailPage()) return;

      const nextTab = button.dataset.qdTab;

      if (!['activity', 'details', 'documents', 'action'].includes(nextTab)) {
        return;
      }

      trackingTab = nextTab;
      focusedSection = '';

      const panel = container().querySelector('.qd-tracking-view');

      if (!panel) return;

      panel.dataset.qdTab = nextTab;
      panel.classList.toggle('qd-details-enter', nextTab === 'details');

      panel.querySelectorAll('[data-detail-action="tracking-tab"]').forEach((tab) => {
        tab.setAttribute('aria-pressed', String(tab.dataset.qdTab === nextTab));
      });

      // Keep the section tabs and the start of Details in view.
      const scrollContainer = panel.querySelector('.db');

      if (scrollContainer) {
        cancelAnimationFrame(scrollContainer._scrollFrame);

        const start = scrollContainer.scrollTop;
        const tabs = panel.querySelector('.qd-section-tabs');
        const target = nextTab === 'details' && tabs
          ? Math.max(0, start + AtlasViewport.rect(tabs).top - AtlasViewport.rect(scrollContainer).top - 12)
          : scrollContainer.scrollHeight - scrollContainer.clientHeight;
        if (matchMedia('(prefers-reduced-motion: reduce)').matches) {
          scrollContainer.scrollTop = target;
          return;
        }
        const duration = nextTab === 'details' ? 320 : 650;
        const startTime = performance.now();

        const animateScroll = (now) => {
          const progress = Math.min((now - startTime) / duration, 1);
          const eased = 1 - Math.pow(1 - progress, 3);

          scrollContainer.scrollTop = start + (target - start) * eased;

          if (progress < 1) {
            scrollContainer._scrollFrame = requestAnimationFrame(animateScroll);
          }
        };

        scrollContainer._scrollFrame = requestAnimationFrame(animateScroll);
      }

      return;
    }

    if (button.dataset.detailAction === 'close') close();
    if (button.dataset.detailAction === 'refresh-palletways-photos' && sel)
      loadPalletwaysPortal(sel, true);

    if (button.dataset.detailAction === 'close-gallery') closeGallery();
    if (button.dataset.detailAction === 'open-pod-gallery')
      showGallery(Number(button.dataset.podIndex));
    if (button.dataset.detailAction === 'previous-pod') showGallery(galleryIndex - 1);
    if (button.dataset.detailAction === 'next-pod') showGallery(galleryIndex + 1);
    if (button.dataset.detailAction === 'zoom-pod-in') zoomGallery(1.25);
    if (button.dataset.detailAction === 'zoom-pod-out') zoomGallery(0.8);
    if (button.dataset.detailAction === 'rotate-pod') {
      galleryTransform.rotation = (galleryTransform.rotation + 90) % 360;
      galleryTransform.x = 0;
      galleryTransform.y = 0;
      applyGalleryTransform();
    }
    if (button.dataset.detailAction === 'reset-pod-view') {
      galleryTransform = { scale: 1, rotation: 0, x: 0, y: 0 };
      applyGalleryTransform();
    }
    if (button.dataset.detailAction === 'copy-tracking-link') {
      const url = sel ? tlink(get(sel)) : '';
      if (url) copyText(url, 'Tracking link copied');
    }
    if (button.dataset.detailAction === 'copy-pod-link') {
      const delivery = sel ? get(sel) : null;
      const podUrl =
        delivery?.podPhotos?.[Number(button.dataset.podIndex)]?.url ||
        delivery?.podUrl ||
        delivery?.proofUrl;
      if (podUrl) copyText(new URL(podUrl, location.href).href, 'PoD link copied');
    }
    if (button.dataset.detailAction === 'download-pod-image')
      downloadPodImage(Number(button.dataset.podIndex));
  });

  container().addEventListener(
    'wheel',
    (event) => {
      const image = event.target.closest('.qd-gallery-image');
      if (!image?.complete || !image.naturalWidth || !event.deltaY) return;
      event.preventDefault();
      const unit =
        event.deltaMode === 1
          ? 16
          : event.deltaMode === 2
            ? image.closest('.qd-gallery-canvas').clientHeight
            : 1;
      zoomGallery(
        Math.exp(-event.deltaY * unit * 0.002),
        AtlasViewport.x(event),
        AtlasViewport.y(event),
      );
    },
    { passive: false },
  );

  container().addEventListener('pointerdown', (event) => {
    const image = event.target.closest('.qd-gallery-image');
    if (
      !image?.complete ||
      !image.naturalWidth ||
      galleryTransform.scale <= 1 ||
      event.button !== 0
    )
      return;
    event.preventDefault();
    endGalleryDrag();
    galleryDrag = {
      image,
      pointerId: event.pointerId,
      clientX: AtlasViewport.x(event),
      clientY: AtlasViewport.y(event),
      x: galleryTransform.x,
      y: galleryTransform.y,
    };
    image.setPointerCapture(event.pointerId);
    image.classList.add('is-dragging');
  });

  container().addEventListener('pointermove', (event) => {
    if (!galleryDrag || event.pointerId !== galleryDrag.pointerId) return;
    if (!galleryDrag.image.isConnected) {
      endGalleryDrag();
      return;
    }
    event.preventDefault();
    galleryTransform.x = galleryDrag.x + AtlasViewport.x(event) - galleryDrag.clientX;
    galleryTransform.y = galleryDrag.y + AtlasViewport.y(event) - galleryDrag.clientY;
    applyGalleryTransform();
  });

  for (const type of ['pointerup', 'pointercancel', 'lostpointercapture']) {
    container().addEventListener(type, (event) => {
      if (galleryDrag?.pointerId === event.pointerId) endGalleryDrag();
    });
  }

  window.addEventListener('resize', applyGalleryTransform);

  // Close the Tracking sidebar when clicking outside it.
  document.addEventListener(
    'pointerdown',
    (event) => {
      if (!isOrderDetailPage() || !sel) return;

      // Do not interfere with the proof-of-delivery gallery.
      if (galleryIndex !== null) return;

      const panel = container().querySelector('.dr.qd.qd-tracking-view');

      if (!panel || panel.classList.contains('qd-closing')) return;

      // Clicking inside the sidebar must not close it.
      if (panel.contains(event.target)) return;

      close();
    },
    true,
  );

  document.addEventListener(
    'keydown',
    (event) => {
      if (galleryIndex === null) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        event.stopImmediatePropagation();
        closeGallery();
      } else if (event.key === 'ArrowLeft') {
        event.preventDefault();
        showGallery(galleryIndex - 1);
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        showGallery(galleryIndex + 1);
      }
    },
    true,
  );

  function openImages(photos, index = 0, title = 'Claim pictures', opener = null) {
    closeGallery();
    const dialog = opener?.closest('dialog[open]');
    if (dialog && !dialog.contains(container())) {
      // Keep the shared gallery and its existing event listeners in the modal's
      // active top layer, then restore the detail root when the viewer closes.
      galleryPortal = { parent: container().parentNode, next: container().nextSibling };
      dialog.append(container());
    }
    externalGallery = {
      order: title,
      podPhotos: photos.map((photo) => ({ url: photo.url, imageUrl: photo.url, kind: 'Photo' })),
    };
    galleryOpener = opener;
    showGallery(index);
  }

  return { open, close, render, openImages };
})();
let detailOpenRequest = 0;
function op(id, section = '') {
  const request = ++detailOpenRequest;
  const targetPage = page;
  const cached =
    get(id) ||
    [
      ...trackingLoaded,
      ...failedLoaded,
      ...D,
      ...(liveSummary?.today || []),
      ...(liveSummary?.failedPreview || []),
    ].find((delivery) => String(delivery.id) === String(id));
  if (cached && !get(id)) DeliveryStore.add({ ...cached, id });
  if (cached) DeliveryDetail.open(id, section);
  if (document.body.dataset.live === 'true') {
    DeliveryApi.get(id)
      .then((delivery) => {
        if (delivery.error) throw new Error(delivery.error);
        if (page !== targetPage || request !== detailOpenRequest) return;
        const previous = get(id);
        const changed = JSON.stringify(previous) !== JSON.stringify({ ...previous, ...delivery });
        if (previous) DeliveryStore.update(id, delivery);
        else DeliveryStore.add({ ...delivery, id });
        if (!cached) DeliveryDetail.open(id, section);
        else if (sel === id && changed) DeliveryDetail.render();
      })
      .catch((error) => {
        if (page === targetPage && request === detailOpenRequest) {
          toast(
            cached
              ? 'Live details unavailable; showing saved order details.'
              : error.message || 'Could not load order details. Try again.',
          );
        }
      });
  } else if (!cached) {
    toast('Order details unavailable. Refresh the delivery list.');
  }
}

function drawer() {
  DeliveryDetail.render();
}
