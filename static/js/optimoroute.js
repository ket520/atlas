(() => {
  "use strict";
  const $ = (id) => document.getElementById(id),
    labels = {
      unscheduled: "Unscheduled",
      scheduled: "Scheduled",
      on_route: "On route",
      servicing: "Servicing",
      success: "Completed",
      failed: "Failed",
      rejected: "Rejected",
      cancelled: "Cancelled",
    };
  let records = [],
    pages = [],
    controller,
    complete = false,
    currentPage = 0,
    nextUrl = null;
  const esc = (value) =>
    String(value ?? "").replace(
      /[&<>"']/g,
      (char) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[char],
    );
  const safeUrl = (value) => {
    try {
      const url = new URL(value);
      return ["https:", "http:"].includes(url.protocol) &&
        !url.username &&
        !url.password
        ? url.href
        : "";
    } catch {
      return "";
    }
  };
  const link = (url, text) =>
    safeUrl(url)
      ? `<a href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>`
      : "—";
  const time = (value) =>
    value?.unixTimestamp
      ? new Date(value.unixTimestamp * 1000).toLocaleString()
      : value?.localTime?.replace("T", " ") || "—";
  const orderType = (r) =>
    ({ D: "Delivery", P: "Pickup", T: "Task" })[r.orderType] ||
    r.orderType ||
    "-";
  const duration = (r) => {
    const start = r.startedAt?.unixTimestamp,
      end = r.completedAt?.unixTimestamp;
    if (Number.isFinite(start) && Number.isFinite(end) && end >= start)
      return `${Math.round(((end - start) / 60) * 10) / 10} min (actual)`;
    return Number.isFinite(r.plannedDuration)
      ? `${r.plannedDuration} min (planned)`
      : "-";
  };
  const cellText = (value) =>
    `<span class="or-cell-text" title="${esc(value || "-")}">${esc(value || "-")}</span>`;
  const clock = (value) =>
    value?.unixTimestamp
      ? new Date(value.unixTimestamp * 1000).toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        })
      : value?.localTime?.split("T")[1]?.slice(0, 5) || "-";
  const trackButton = (url) =>
    safeUrl(url)
      ? `<a class="or-track" href="${esc(safeUrl(url))}" target="_blank" rel="noopener noreferrer">Track order <span aria-hidden="true">&#8599;</span></a>`
      : '<span class="or-unavailable">Unavailable</span>';
  const podPaths = {
    signature:
      '<path d="m14 4 6 6M4 20l4-1 12-12a2 2 0 0 0-3-3L5 16l-1 4Zm6 0h10"/>',
    photo:
      '<rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 17 6-6 4 4 3-3 5 5"/>',
    note: '<path d="M14 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V10l-7-7Z"/><path d="M14 3v7h7M7 14h10M7 17h6"/>',
  };
  const podIcon = (kind, name) =>
    `<button type="button" class="or-pod-icon" data-pod="${kind}" title="${esc(name)}" aria-label="${esc(name)}"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${podPaths[kind]}</svg></button>`;
  const today = new Date();
  today.setMinutes(today.getMinutes() - today.getTimezoneOffset());
  $("or-from").value = $("or-to").value = today.toISOString().slice(0, 10);
  for (const [value, name] of Object.entries(labels))
    $("or-status").add(new Option(name, value));
  const matches = () =>
    (pages[currentPage]?.records || []).filter(
      (r) =>
        (!$("or-status").value || r.status === $("or-status").value) &&
        (!$("or-driver").value || r.driver === $("or-driver").value) &&
        JSON.stringify(r)
          .toLowerCase()
          .includes($("pw-search").value.trim().toLowerCase()),
    );
  function render() {
    const rows = matches();
    $("pw-count").textContent = `${rows.length} on this page`;
    $("or-page").textContent = `Page ${currentPage + 1} | 25 records per page`;
    $("or-prev").disabled = !!controller || currentPage === 0;
    $("or-next").disabled =
      !!controller || !(pages[currentPage + 1] || nextUrl);
    $("pw-search").disabled = !records.length;
    $("pw-export").disabled = !pages.length;
    $("or-csv").disabled = !records.length;
    $("pw-records").innerHTML = rows.length
      ? `<div class="or-table-wrap"><table class="or-table"><thead><tr><th>Order ID</th><th>Location</th><th>Address</th><th>Order type</th><th>Status</th><th>Driver</th><th>Planned delivery date</th><th>Scheduled time</th><th>Start time</th><th>End time</th><th>Live ETA</th><th>Tracking</th><th>POD</th><th>Duration</th><th>Vehicle</th><th>Stop number</th><th>Phone</th><th>Email</th><th>Delivery window</th><th>Delivery instructions</th><th>Location notes</th><th>POD note</th><th>Map</th><th>OptimoRoute reference</th><th>Completion information</th></tr></thead><tbody>${rows.map((r) => `<tr data-id="${esc(r.id)}" tabindex="0" aria-label="View order ${esc(r.orderNo || r.id)}"><td><span class="or-order">${esc(r.orderNo || "Reference unavailable")}</span></td><td>${cellText(r.customer)}</td><td>${cellText(r.address)}</td><td>${esc(orderType(r))}</td><td><span class="or-badge" data-status="${esc(r.status)}">${esc(labels[r.status] || r.status)}</span></td><td>${esc(r.driver || "Unassigned")}</td><td class="or-nowrap">${esc(r.plannedDate || r.date || "-")}</td><td class="or-nowrap">${esc(r.scheduledAt || "-")}</td><td class="or-nowrap" title="${esc(time(r.startedAt))}">${esc(clock(r.startedAt))}</td><td class="or-nowrap" title="${esc(time(r.completedAt))}">${esc(clock(r.completedAt))}</td><td class="or-nowrap">${esc(r.eta || "-")}</td><td>${trackButton(r.trackingUrl)}</td><td><div class="or-pod">${r.signature ? podIcon("signature", "Signature available") : ""}${r.photos?.length ? podIcon("photo", "Photos available") : ""}${r.podNote ? podIcon("note", "Note available") : ""}${!r.signature && !r.photos?.length && !r.podNote ? '<span class="or-no-pod" title="No proof of delivery">-</span>' : ""}</div></td><td class="or-nowrap">${esc(duration(r))}</td><td>${cellText(r.vehicle)}</td><td>${esc(r.stopNumber ?? "-")}</td><td>${cellText(r.phone)}</td><td>${cellText(r.email)}</td><td>${cellText(windows(r))}</td><td>${cellText(r.instructions)}</td><td>${cellText(r.locationNotes)}</td><td class="or-note-cell">${cellText(r.podNote)}</td><td>${link(mapUrl(r), "Map")}</td><td>${cellText(r.providerOrderNo)}</td><td>${cellText(r.completionError)}</td></tr>`).join("")}</tbody></table></div>`
      : '<p class="mut">No deliveries match this selection.</p>';
    document.dispatchEvent(
      new CustomEvent("optimoroute-page", {
        detail: pages[currentPage]?.records || [],
      }),
    );
  }
  const windows = (r) =>
    (r.timeWindows || []).map((w) => `${w.twFrom} - ${w.twTo}`).join(", ");
  const mapUrl = (r) =>
    Number.isFinite(r.latitude) && Number.isFinite(r.longitude)
      ? `https://www.google.com/maps/search/?api=1&query=${r.latitude},${r.longitude}`
      : "";
  function detail(r) {
    $("or-detail-title").textContent = `Order ${r.orderNo || r.id}`;
    const fields = {
      "Order ID": r.orderNo,
      Location: r.customer,
      Address: r.address,
      "Order type": orderType(r),
      Status: labels[r.status] || r.status,
      Date: r.plannedDate || r.date,
      Time: `${clock(r.startedAt)} - ${clock(r.completedAt)}`,
      Duration: duration(r),
    };
    $("or-detail-body").innerHTML = `<dl class="or-details">${Object.entries(
      fields,
    )
      .map(
        ([name, value]) => `<dt>${esc(name)}</dt><dd>${esc(value || "-")}</dd>`,
      )
      .join(
        "",
      )}</dl><h3>Delivery instructions</h3><p class="or-note">${esc(r.instructions || "No instructions recorded.")}</p><h3 id="or-pod-photo">POD photos</h3><div class="or-photos">${(r.photos || []).map((photo, index) => (safeUrl(photo.url) ? `<a href="${esc(safeUrl(photo.url))}" target="_blank" rel="noopener noreferrer"><img src="${esc(safeUrl(photo.url))}" alt="POD photo ${index + 1}" loading="lazy" referrerpolicy="no-referrer"></a>` : "")).join("") || "<p>No POD photos recorded.</p>"}</div><h3 id="or-pod-signature">Signature</h3>${safeUrl(r.signature?.url) ? `<div class="or-photos"><a href="${esc(safeUrl(r.signature.url))}" target="_blank" rel="noopener noreferrer"><img src="${esc(safeUrl(r.signature.url))}" alt="Customer signature" referrerpolicy="no-referrer"></a></div>` : "<p>No signature recorded.</p>"}`;
    $("or-detail").showModal();
  }
  $("or-close").onclick = () => $("or-detail").close();
  let pressedOutside = false;
  const outsideDialog = (event) => {
    const box = $("or-detail").getBoundingClientRect();
    return (
      event.clientX < box.left ||
      event.clientX > box.right ||
      event.clientY < box.top ||
      event.clientY > box.bottom
    );
  };
  $("or-detail").addEventListener("pointerdown", (event) => {
    pressedOutside = event.target === $("or-detail") && outsideDialog(event);
  });
  $("or-detail").addEventListener("click", (event) => {
    if (
      pressedOutside &&
      event.target === $("or-detail") &&
      outsideDialog(event)
    )
      $("or-detail").close();
    pressedOutside = false;
  });
  function openRow(event) {
    if (event.target.closest("a")) return;
    const row = event.target.closest("tr[data-id]");
    if (!row) return;
    const record = records.find((r) => String(r.id) === row.dataset.id);
    if (!record) return;
    const icon = event.target.closest("[data-pod]");
    if (icon?.dataset.pod === "note") {
      const cell = row.querySelector(".or-note-cell");
      cell?.scrollIntoView({ block: "nearest", inline: "center" });
      cell?.classList.toggle("or-note-expanded");
      return;
    }
    detail(record);
    if (icon)
      document
        .getElementById(`or-pod-${icon.dataset.pod}`)
        ?.scrollIntoView({ block: "start" });
  }
  $("pw-records").onclick = openRow;
  $("pw-records").onkeydown = (event) => {
    if (
      event.target.matches("tr[data-id]") &&
      ["Enter", " "].includes(event.key)
    ) {
      event.preventDefault();
      openRow(event);
    }
  };
  for (const id of ["or-driver", "pw-search"])
    $(id).addEventListener("input", render);
  $("or-status").onchange = () => refresh();
  $("pw-stop").onclick = () => controller?.abort();
  async function load(url, reset = false) {
    if (controller) return;
    controller = new AbortController();
    $("or-loading").hidden = false;
    $("pw-records").setAttribute("aria-busy", "true");
    const previous = { records, pages, currentPage, nextUrl, complete };
    if (reset) {
      records = [];
      pages = [];
      currentPage = 0;
      nextUrl = null;
      complete = false;
    }
    $("pw-fetch").disabled = true;
    $("pw-stop").disabled = false;
    for (const id of ["or-scope", "or-status", "or-day", "or-from", "or-to"])
      $(id).disabled = true;
    $("pw-status").dataset.error = "false";
    $("pw-status").textContent = "Loading the next 25 deliveries...";
    render();
    try {
      const target = new URL(url, location.href);
      if (target.origin !== location.origin)
        throw new Error("Invalid backend pagination.");
      const response = await fetch(target, {
        signal: controller.signal,
        redirect: "error",
        headers: { Accept: "application/json" },
      });
      if (
        !(response.headers.get("content-type") || "").includes(
          "application/json",
        )
      )
        throw new Error("Start the Python server to connect to OptimoRoute.");
      const payload = await response.json();
      if (!response.ok)
        throw new Error(payload.error || `HTTP ${response.status}`);
      if (
        !Array.isArray(payload.records) ||
        payload.records.length > 25 ||
        !(
          payload.next === null ||
          (typeof payload.next === "string" && payload.next)
        )
      )
        throw new Error("Unexpected backend response.");
      pages.push(payload);
      records.push(...payload.records);
      currentPage = pages.length - 1;
      nextUrl = payload.next;
      complete = nextUrl === null;
      $("pw-status").textContent = payload.records.length
        ? `${payload.records.length} deliveries loaded. Use Next to load another batch.`
        : nextUrl
          ? "No orders in this part of the history. Click Next to continue."
          : "End of delivery history.";
      $("or-synced").textContent = `Updated ${new Date().toLocaleString()}`;
      $("or-coverage").textContent =
        `History: ${payload.coverage.from} to ${payload.coverage.to}`;
      const selection = $("or-driver").value;
      $("or-driver").replaceChildren(new Option("All drivers", ""));
      [...new Set(records.map((r) => r.driver).filter(Boolean))]
        .sort()
        .forEach((name) => $("or-driver").add(new Option(name, name)));
      $("or-driver").value = selection;
      $("pw-raw").textContent = JSON.stringify(pages, null, 2);
    } catch (error) {
      if (reset)
        ({ records, pages, currentPage, nextUrl, complete } = previous);
      $("pw-status").dataset.error = "true";
      $("pw-status").textContent =
        error.name === "AbortError"
          ? "Loading stopped. You can retry."
          : error.message;
    } finally {
      $("or-loading").hidden = true;
      $("pw-records").setAttribute("aria-busy", "false");
      controller = null;
      $("pw-fetch").disabled = false;
      $("pw-stop").disabled = true;
      for (const id of ["or-scope", "or-status", "or-day", "or-from", "or-to"])
        $(id).disabled = false;
      render();
    }
  }
  function refresh() {
    const scope = $("or-scope").value;
    const params =
      scope === "all"
        ? new URLSearchParams({ scope: "all" })
        : scope === "day"
          ? new URLSearchParams({
              from: $("or-day").value,
              to: $("or-day").value,
            })
          : new URLSearchParams({
              from: $("or-from").value,
              to: $("or-to").value,
            });
    if (scope === "day" && !$("or-day").value) return;
    if ($("or-status").value) params.set("status", $("or-status").value);
    return load(`/api/integrations/optimoroute/data?${params}`, true);
  }
  $("pw-form").onsubmit = (event) => {
    event.preventDefault();
    refresh();
  };
  function updateDateControls() {
    const scope = $("or-scope").value;
    $("or-dates").hidden = scope !== "dates";
    $("or-day").closest("label").hidden = scope === "dates";
    $("or-date-help").textContent =
      scope === "dates"
        ? "Choose From and To to view deliveries within that date range."
        : "Pick a delivery date to see only that day's orders, or select All deliveries to clear it.";
    $("or-from").required = $("or-to").required = scope === "dates";
    $("or-day").required = scope === "day";
  }
  $("or-scope").onchange = () => {
    if ($("or-scope").value === "all") $("or-day").value = "";
    if ($("or-scope").value === "day" && !$("or-day").value)
      $("or-day").value = today.toISOString().slice(0, 10);
    updateDateControls();
    refresh();
  };
  $("or-day").onchange = () => {
    $("or-scope").value = $("or-day").value ? "day" : "all";
    updateDateControls();
    refresh();
  };
  for (const id of ["or-from", "or-to"])
    $(id).onchange = () => {
      if (
        $("or-from").value &&
        $("or-to").value &&
        $("or-to").value >= $("or-from").value
      )
        refresh();
    };
  $("or-prev").onclick = () => {
    if (!controller && currentPage > 0) {
      currentPage--;
      render();
    }
  };
  $("or-next").onclick = () => {
    if (pages[currentPage + 1]) {
      currentPage++;
      render();
    } else if (nextUrl) load(nextUrl);
  };
  function download(content, type, extension) {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `optimoroute-${complete ? "complete" : "partial"}-${$("or-from").value}.${extension}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  $("pw-export").onclick = () =>
    download(
      JSON.stringify(
        { complete, exportedAt: new Date().toISOString(), records, pages },
        null,
        2,
      ),
      "application/json",
      "json",
    );
  $("or-csv").onclick = () => {
    const columns = [
      "Order ID",
      "Customer",
      "Address",
      "Order type",
      "Status",
      "Driver",
      "Planned delivery date",
      "Scheduled time",
      "Start time",
      "End time",
      "Live ETA",
      "Tracking link",
      "POD note",
      "POD photos",
      "Signature",
      "Phone",
      "Email",
      "Instructions",
      "Duration",
      "Vehicle",
      "Stop number",
      "Delivery window",
      "Location notes",
      "OptimoRoute reference",
      "Completion information",
      "Barcode scans",
      "Completion GPS",
      "Customer rating",
      "Customer feedback",
    ];
    const cell = (value) =>
      `"${String(value ?? "")
        .replace(/^[=+@\-\t\r]/, "'$&")
        .replace(/"/g, '""')}"`;
    const rows = matches().map((r) => [
      r.orderNo || r.id,
      r.customer,
      r.address,
      orderType(r),
      labels[r.status] || r.status,
      r.driver,
      r.plannedDate || r.date,
      r.scheduledAt,
      time(r.startedAt),
      time(r.completedAt),
      r.eta,
      r.trackingUrl,
      r.podNote,
      r.photos.map((p) => p.url).join(" | "),
      r.signature?.url,
      r.phone,
      r.email,
      r.instructions,
      duration(r),
      r.vehicle,
      r.stopNumber,
      windows(r),
      r.locationNotes,
      r.providerOrderNo,
      r.completionError,
      (r.barcodes || []).map((b) => b.barcode).join(" | "),
      r.completionPosition
        ? `${r.completionPosition.latitude}, ${r.completionPosition.longitude}`
        : "",
      r.customerFeedback?.rating,
      r.customerFeedback?.comment,
    ]);
    download(
      "\uFEFF" +
        [columns, ...rows].map((row) => row.map(cell).join(",")).join("\r\n"),
      "text/csv;charset=utf-8",
      "csv",
    );
  };
  document.addEventListener("optimoroute-updated", (event) => {
    if (controller || !pages[currentPage]) return;
    const updated = new Map(event.detail.map((r) => [r.id, r]));
    records = records.map((r) => updated.get(r.id) || r);
    for (const page of pages)
      page.records = page.records.map((r) => updated.get(r.id) || r);
    render();
    $("or-synced").textContent = `Live update: ${new Date().toLocaleString()}`;
  });
  updateDateControls();
  refresh();
})();
