const APP_CONFIG = Object.freeze({
  api: {
    enabled: false,
    baseUrl: '/api',
    timeoutMs: 90000,
  },
  routes: {
    Dashboard: 'dashboard.html',
    Deliveries: 'deliveries.html',
    'Failed Deliveries': 'failed-deliveries.html',
    'Collective Note': 'collective-note.html',
    'Manufacture Claims': 'manufacture-claims.html',
    Integrations: 'integrations.html',
    Guidance: 'guidance.html',
    Settings: 'settings.html',
  },
  carriers: {
    external: {
      Palletways: 'Palletways',
      XDP: 'XDP',
    },
    supported: ['Own van', 'Self Delivery', 'LOCAL MULTIDROP', 'Palletways', 'AMZ', 'XDP', 'Yodel', 'Stopstart', 'UK Next Day', 'Wayfair', 'Charge Pending (Remote Postcode)', 'Collect in Person', 'Do Not Pick Yet', 'Cancelled', 'On Hold', 'Unassigned'],
  },
});

const DELIVERY_PAGE_SIZE = 25;

// Sidebar and dashboard shortcuts share the same order and availability.
const SIDEBAR_ITEMS = Object.freeze([
  {target: 'Dashboard'}, {target: 'Deliveries'}, {target: 'Failed Deliveries'},
  {target: 'Replacement', version: 2}, {target: 'Collective Note'},
  {target: 'Return', version: 3}, {target: 'Free Return', version: 3},
  {target: 'Manufacture Claims'}, {target: 'Logistics Claims', version: 3},
  {target: 'Refund', version: 2},
  {target: 'Integrations', bottom: true}, {target: 'Guidance', bottom: true},
  {target: 'Settings', bottom: true},
]);

const TrackingVisibility = (() => {
  const key = 'delivery-desk-hide-hygienic-tracking';
  let hideHygienic = true;
  const wayfairKey = 'delivery-desk-hide-wayfair-tracking';
  let hideWayfair = true;
  const wilkoKey = 'delivery-desk-hide-wilko-tracking';
  let hideWilko = false;
  const palletwaysB2bKey = 'delivery-desk-hide-palletways-b2b';
  let hidePalletwaysB2b = false;
  try { hideHygienic = localStorage.getItem(key) !== 'false'; } catch {}
  try { hideWayfair = localStorage.getItem(wayfairKey) !== 'false'; } catch {}
  try { hideWilko = localStorage.getItem(wilkoKey) === 'true'; } catch {}
  try { hidePalletwaysB2b = localStorage.getItem(palletwaysB2bKey) === 'true'; } catch {}
  return {
    enabled: () => hideHygienic,
    wayfairEnabled: () => hideWayfair,
    wilkoEnabled: () => hideWilko,
    palletwaysB2bEnabled: () => hidePalletwaysB2b,
    setPalletwaysB2bEnabled(value) {
      hidePalletwaysB2b = Boolean(value);
      try { localStorage.setItem(palletwaysB2bKey, String(hidePalletwaysB2b)); } catch {}
    },
    includesPalletwaysClassification: (carrier, classification) => !hidePalletwaysB2b
      || carrier !== 'Palletways' || String(classification || '').trim().toUpperCase() !== 'B2B',
    includesStore: value => {
      const store = String(value || '').trim().toLowerCase();
      return !(hideWilko && ['wilko', 'weiko'].includes(store))
        && !(hideWayfair && store === 'wayfair')
        && !(hideHygienic && store === 'hygienic cleaning company (uk) ltd');
    },
    setWilkoEnabled(value) {
      hideWilko = Boolean(value);
      try { localStorage.setItem(wilkoKey, String(hideWilko)); } catch {}
    },
    setWayfairEnabled(value) {
      hideWayfair = Boolean(value);
      try { localStorage.setItem(wayfairKey, String(hideWayfair)); } catch {}
    },
    setEnabled(value) {
      hideHygienic = Boolean(value);
      try { localStorage.setItem(key, String(hideHygienic)); } catch {}
    },
    includesOrderType: value => !hideHygienic || !['sales', 'hg_replacement'].includes(String(value || '').trim().toLowerCase()),
    includesCarrier: value => !hideWayfair || String(value || '').trim().toLowerCase() !== 'wayfair',
  };
})();

const DELIVERY_STATUS_MAP = Object.freeze({
  Awaiting: 'Awaiting',
  'Status unverified': 'Unscheduled',
  Unscheduled: 'Unscheduled',
  Unassigned: 'Unassigned',
  New: 'Unscheduled',
  Scheduled: 'Scheduled',
  Rescheduled: 'Scheduled',
  'Out for Delivery': 'Out for Delivery',
  'In Transit': 'Scheduled',
  Delivered: 'Delivered',
  Completed: 'Delivered',
  'Failed Delivery': 'Failed',
  Failed: 'Failed',
  Rejected: 'Rejected',
  Lost: 'Lost',
  Cancelled: 'Cancelled',
  Return: 'Return',
});

const trackingStatus = status => DELIVERY_STATUS_MAP[status] || '';

class ApiError extends Error {
  constructor(message, status = 0, payload = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

const ApiClient = (() => {
  async function request(path, options = {}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), APP_CONFIG.api.timeoutMs);

    try {
      const response = await fetch(`${APP_CONFIG.api.baseUrl}${path}`, {
        ...options,
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          ...(options.headers || {}),
        },
        signal: controller.signal,
      });

      const contentType = response.headers.get('content-type') || '';
      const payload = contentType.includes('application/json')
        ? await response.json()
        : await response.text();

      if (!response.ok) {
        const message = payload?.message || payload?.detail || payload?.error || `Request failed (${response.status})`;
        throw new ApiError(message, response.status, payload);
      }

      return payload;
    } catch (error) {
      if (error.name === 'AbortError') {
        throw new ApiError('Request timed out');
      }
      throw error;
    } finally {
      clearTimeout(timeout);
    }
  }

  return {
    get: path => request(path),
    patch: (path, body) => request(path, { method: 'PATCH', body: JSON.stringify(body) }),
  };
})();

const DeliveryApi = Object.freeze({
  summary() {
    return ApiClient.get('/deliveries/summary');
  },
  list(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([name, value]) => {
      (Array.isArray(value) ? value : [value]).forEach(item => {
        if (item !== '' && item != null) query.append(name, item);
      });
    });
    const suffix = query.toString() ? `?${query}` : '';
    return ApiClient.get(`/deliveries${suffix}`);
  },

  get(id) {
    return ApiClient.get(`/deliveries/${encodeURIComponent(id)}`);
  },

  integrations() {
    return ApiClient.get('/integrations');
  },
});
