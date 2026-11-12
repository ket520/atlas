const TRACKING_STATUS_SOURCES = Object.freeze({
  'Own van': 'OptimoRoute',
  'Self Delivery': 'OptimoRoute',
  'LOCAL MULTIDROP': 'OptimoRoute',
  Palletways: 'Atlas API · Palletways',
  AMZ: 'Amazon Shipping',
  XDP: 'XDP',
  Stopstart: 'Stopstart',
  Yodel: 'Yodel',
});

const usesSourceTrackingStatus = () => page === 'Deliveries' && !trackingOrderKind();

const trackingFacetStatus = item => fsrc
  ? item.carrierStatus || 'Status unavailable'
  : item.salesStatus || item.rawStatus || 'Status unavailable';

const trackingDisplayStatus = delivery => {
  if (!fsrc) {
    return {
      label: delivery.statusView?.sales || delivery.rawStatus || 'Status unavailable',
      source: 'Atlas API · Sales Activity',
    };
  }
  const view = delivery.statusView;
  return {
    label: view?.carrier || 'Status unavailable',
    source: view?.source || TRACKING_STATUS_SOURCES[delivery.carrier] || 'Carrier',
  };
};

