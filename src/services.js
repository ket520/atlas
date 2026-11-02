const DeliveryStore = (() => {
  let deliveries = [];
  let activity = [];
  let integrations = [];

  function hydrate(state) {
    const byOrder = new Map();
    for (const delivery of state.deliveries) {
      if (!delivery.carrier) continue;
      const key = String(delivery.order || delivery.id || '').trim().toUpperCase();
      if (!key) continue;
      const previous = byOrder.get(key);
      if (!previous) {
        byOrder.set(key, { ...delivery, logs: [...(delivery.logs || [])] });
        continue;
      }
      const latest = String(delivery.updatedAt || '') >= String(previous.updatedAt || '') ? delivery : previous;
      const uniqueLogs = new Map([...previous.logs, ...(delivery.logs || [])]
        .map(entry => [`${entry.at}|${entry.text}`, entry]));
      byOrder.set(key, {
        ...latest,
        logs: [...uniqueLogs.values()].sort((a, b) => String(a.at).localeCompare(String(b.at))),
      });
    }
    deliveries = [...byOrder.values()].filter(delivery => Boolean(trackingStatus(delivery.st)));
    activity = state.activity;
    integrations = state.integrations.filter(source =>
      ['OptimoRoute', 'Palletways', 'Courier Issues', 'XDP'].includes(source[0]));
  }

  return {
    hydrate,
    deliveries: () => deliveries,
    activity: () => activity,
    integrations: () => integrations,
    find: id => deliveries.find(delivery => delivery.id === id),
    add: delivery => deliveries.push(delivery),
    update(id, changes) {
      const delivery = deliveries.find(item => item.id === id);
      if (!delivery) return null;
      Object.assign(delivery, changes);
      return delivery;
    },
    log: entry => activity.unshift(entry),
  };
})();
