const productLinkLookups = new Map();
const PRODUCT_LINK_HOSTS = Object.freeze({
  'Shopify - Neshome': 'neshome.co.uk',
  'Bathroom Republic - Website': 'bathroomrepublic.co.uk',
  'B&Q': 'www.diy.com',
  Amazon: 'www.amazon.co.uk',
  'Ebay Bathroom Republic': 'www.ebay.co.uk',
  'EBay Willesden Bathroom': 'www.ebay.co.uk',
});

function deliveryProductLink(delivery, sku, item = {}) {
  const store = purchaseChannel(delivery);
  if (!Object.hasOwn(PRODUCT_LINK_HOSTS, store)) return esc(sku);
  const query = new URLSearchParams({store, sku});
  const isAmazon = store === 'Amazon';
  const isEbay = ['Ebay Bathroom Republic', 'EBay Willesden Bathroom'].includes(store);
  const platformId = String(isAmazon ? item.asin || '' : isEbay ? item.ebayItemId || '' : '').trim();
  const verifiedId = isAmazon ? /^[A-Z0-9]{10}$/.test(platformId) : isEbay && /^\d{9,15}$/.test(platformId);
  if ((isAmazon || isEbay) && !verifiedId) return esc(sku);
  if (verifiedId) query.set('platform_id', platformId);
  return `<span data-product-lookup="${esc(query.toString())}" data-product-store="${esc(store)}">${esc(sku)}</span>`;
}

function verifiedProductUrl(target, store) {
  try {
    const url = new URL(target, location.origin);
    if (url.protocol !== 'https:' || url.hostname !== PRODUCT_LINK_HOSTS[store]) return '';
    switch (url.hostname) {
      case 'www.diy.com':
        return url.pathname.endsWith('.prd') ? url.href : '';
      case 'www.amazon.co.uk':
        return /^\/gp\/product\/[A-Z0-9]{10}$/.test(url.pathname) ? url.href : '';
      case 'www.ebay.co.uk':
        return /^\/itm\/(?:[^/]+\/)?\d{9,15}$/.test(url.pathname) ? url.href : '';
      default:
        return url.pathname.startsWith('/products/') ? url.href : '';
    }
  } catch {
    return '';
  }
}

function lookupProductLink(query) {
  let entry = productLinkLookups.get(query);
  if (!entry || entry.expires <= Date.now()) {
    if (productLinkLookups.size >= 256) {
      productLinkLookups.delete(productLinkLookups.keys().next().value);
    }
    entry = {
      expires: Date.now() + 60000,
      result: fetch(`/api/product-link?${query}`)
        .then(response => response.ok ? response.json() : null)
        .then(result => result?.url || null)
        .catch(() => null),
    };
    productLinkLookups.set(query, entry);
  }
  return entry.result;
}

function hydrateProductLinks(root) {
  root.querySelectorAll('[data-product-lookup]').forEach(async element => {
    const target = await lookupProductLink(element.dataset.productLookup);
    if (!target || !element.isConnected) return;
    const url = verifiedProductUrl(target, element.dataset.productStore);
    if (!url) return;
    const link = document.createElement('a');
    link.className = 'qd-product-link';
    link.href = url;
    link.target = '_blank';
    link.rel = 'noopener noreferrer';
    link.textContent = element.textContent;
    link.title = `Open ${element.textContent} on ${element.dataset.productStore}`;
    element.replaceWith(link);
  });
}

