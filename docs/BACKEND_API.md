# Delivery Desk tracking API

## Dashboard workspace (current)

`GET /api/dashboard` returns bounded (three-order) previews and totals for eight
saved-order cohorts, plus an unavailable Version 3 Returns-processing widget.
It accepts `store`, `carrier` and the same `hide_hygienic`, `hide_wayfair`,
`hide_wilko`, `hide_palletways_b2b` flags as Tracking. Source timestamps and
background-sync state accompany the widgets. No external workflows are inferred
from a missing field, and previews never supply invented orders or counts.

`GET /api/deliveries?dashboard_widget=<key>` applies the exact shared cohort before
search, filtering, paging and counts. The response also includes cohort-scoped
filter facets. Dashboard View all carries its delivery-method selection into this
route. The dashboard Stores section contains external website links only; it does
not filter widget data. Supported keys and predicates live in `dashboard_data.widget_condition`:
cancelled (today's UK order date only), hold, out-of-stock,
charge-pending, collect, palletways-next-day, palletways-unbooked, van-unscheduled.
Unbooked requires an explicit No in Palletways tab column Z (Booked In), matched
by column A to an OW Palletways order whose ID is also present in Sales Activity
column A in the latest successful source snapshot. An order merely retained in
local history does not qualify. Source membership is replaced atomically during
each successful OW import; failed reads retain the last successful membership.
Until the first successful snapshot, the widget is unavailable rather than zero.
It has no shipment-status exclusion:
Delivered, Cancelled and Return are still included when Z says No. Column AA
(Book In Request) is not this rule; a blank booking value is unknown. Returns
processing is unavailable until that workflow exists.

The dashboard uses `src/dashboard-home.js` and `static/css/dashboard-home.css`.
Widget selection/order is stored locally under
`deliverydesk-dashboard-widgets-v1`; it supports pointer dragging and keyboard
reordering through Customize Widgets. No provider writes are performed.

The older sections below include historical contracts; check current handlers
and tests before relying on them.

Awaiting Dispatch is available through `dashboard_widget=awaiting-dispatch` in
the dashboard and Tracking APIs. It uses OW raw status `W` (also accepting the
explicit labels Awaiting Despatch / Awaiting Dispatch), across delivery methods,
with the normal dashboard filters. Unscheduled or XDP Awaiting alone does not
qualify an order. Both compact and tall widgets use the same cohort.

`GET /api/order-identifier?order=<exact-identifier>` reads the retained order
index and returns `found`, `order`, `store` and `courier`. Palletways accepts
order ID, `palletwaysSheetTrackingNumber` or `palletwaysSheetConsignmentNumber`;
Amazon Shipping accepts order ID or `owTrackingNo`; XDP accepts order ID or
any complete line of `xdpConsignmentNo`. Carrier results include `trackingId`
and/or `consignmentNumber` as applicable, using the same fields as Tracking.
Carrier IDs accept letters, digits and hyphens; Amazon/XDP matching ignores case.
Multiple matching orders return `found: false, ambiguous: true` rather than
guessing. It does not contact carrier providers. Missing orders return
`found: false`; invalid IDs return 400.
The 1 × 1 Order Identifier utility looks up after typing pauses or on Enter.
The 1 × 1 Generate Collection Note utility checks the existing collection lookup
and opens the automatically filled editor; the user saves the note there.
These utilities and Awaiting Dispatch are available in Customize Widgets,
without changing the default nine-widget layout.

Scope: read-only tracking for Own van (OptimoRoute), Palletways, and XDP. The interface does not plan, schedule, approve, book, or manage redeliveries.

The local server reads OW, Palletways, Courier Issues, Routine Dashboard, and OptimoRoute through read-only integrations. Main pages load without seeded orders.

## Delivery reads

- `GET /deliveries` — one latest-summary row per Order ID for the three supported providers, including orders that no longer appear in the daily Sheet and orders that do not yet have a tracking number.
- `GET /deliveries/:id` — current status and detail for one supported delivery.
- `GET /deliveries/:id/logs?limit=20&cursor=...` — this order's dated changes, newest first, with an older-page cursor. The detail panel previews three recent logs and includes every follow-up remark for failed deliveries; the separate History table on the Tracking page expands a row and loads older logs only as needed. For production, page follow-up remarks separately if an order has enough to make the detail payload large.

## Retained order history

The daily Sheet is an input, not the history store. Import each daily snapshot into a persistent backend database. Match rows by a stable Order ID, not a Sheet row number. Keep one latest-summary record per Order ID, plus append-only dated logs of status, carrier, tracking, contact, address, PoD, and source-presence changes. Preserve earlier values in the snapshots or change events so previous data can still be inspected. Multiple daily versions of one Order ID must never create extra list rows.

When a row disappears from a later Sheet, keep its latest record and all earlier logs. Record a source-presence change such as “Not in latest Sheet”; disappearance alone must not mean `Delivered` or `Failed Delivery`. An order that still appears every day must also retain its prior changes. The UI has Current and History views over the same retained records: a delivered order remains in Current while it is still present in the confirmed current OW feed; an unresolved failed case remains in Current. Agree a data-retention period before production.

Use server-side search and paging for order lists. Support `q` (order number, order reference, tracking number, customer name, phone, postcode), `carrier`, and `status`. Return unique order summaries with a count, and load detailed records only when needed. Do not download all retained orders or logs into the browser for filtering.

The Failed Deliveries page uses the same delivery records, filtered to `Failed Delivery` after status mapping. Its table also needs `orderRef`, `skuItems`, postcode from `addr`, `specialInstructions`, contact details, delivery method, `reason`, current follow-up status (`fu`), `failedAt`, and `followUps`. Each `followUps` entry has `at`, `status`, and `remark`. Keep every follow-up entry; the table shows a short list of statuses, while the Activity log shows each dated remark under a distinct "Follow-up remark" label. Emit those log entries with `kind: "follow-up"`, `status`, and `remark` in addition to `at` and `text`, so the UI does not have to parse a combined sentence. The delivery-method tabs and search filter the same records; clicking a row opens the detail panel.

When supplied and matched to the same order, the detail panel also accepts OW `orderDate` and source `dispatchDate`, plus Carrier Issue `issueNote`, `messagedStatus`, and `scheduledStatus`. These fields display as separate source facts; a message or proposed redelivery is not itself a carrier delivery-status event. Keep each populated Carrier Issue follow-up column as its own `followUps` entry rather than overwriting earlier remarks.

The interface displays four statuses only: `Unscheduled`, `Scheduled`, `Delivered`, and `Failed Delivery`. Provider states such as `Out for Delivery`, `In Transit`, or `Rescheduled` display as `Scheduled`; `Completed` displays as `Delivered`, and `Failed` displays as `Failed Delivery`. Other states are omitted from the tracking list until a mapping is agreed.

Palletways' public documentation describes `Status_Code` and system notes, but does not provide a definitive `Failed Delivery` mapping. Preserve each raw code/note and its source. Map a Palletways consignment to `Failed Delivery` only when a verified event or an authoritative internal source explicitly confirms an unsuccessful delivery attempt. Do not infer failure merely from a late ETA, a missing PoD, or an unspecified exception.

A delivery record should include `id`, `order`, `orderRef`, `skuItems`, `trk`, `trackingUrl`, `podUrl`, `podImageUrl`, `cust`, `phone`, `email`, `addr`, `specialInstructions`, `carrier`, `type`, `st`, `lastSeenAt`, `date` (scheduled date), `deliveryWindowStartAt`, `deliveryWindowEndAt`, `win`, `eta`, `route`, `att`, `reason`, `fu`, `followUps`, `importedAt`, `outForDeliveryAt`, `completedAt`, `failedAt`, and `logs` (each with an ISO timestamp `at` and description `text`). Driver and vehicle details are not required for Customer Service. `deliveryWindowStartAt` and `deliveryWindowEndAt` are the confirmed **order-level customer delivery window**, both date and time in ISO format with timezone. The dashboard shows both times when supplied, falls back to a verified `win` range or ETA, and otherwise shows `TBD`. Do not use a whole route's start/end times or OW `Order date` as the customer's delivery window. `completedAt`, `failedAt`, and each follow-up `at` should contain both date and time when known, using ISO timestamps with a timezone; leave them empty when unknown. Do not infer completion or failure time from the scheduled date. `orderRef`, `skuItems`, `specialInstructions`, and `podUrl` can be empty when unavailable; the table shows a dash. `podUrl` opens the proof; `podImageUrl` is an optional image preview when the proof is a PDF or another non-image format. Only return PoD fields for a proof actually supplied by the provider. The provider supplies the authoritative status, milestones, shipment-specific tracking URL, and PoD link when available. Provider credentials stay on the backend.

## Integration health

- `GET /integrations` — health for OptimoRoute, Palletways, and XDP.

## Notifications

- `GET /notifications`
- `PATCH /notifications/:id/read`
- `PATCH /notifications/read-all`

A notification may include `id`, `type`, `severity` (`high`, `warning`, or `success`), `title`, `message`, `timeLabel`, `read`, `deliveryId`, and `actionLabel`. Notification actions open the read-only tracking detail. Only supported-provider deliveries should be returned.

The frontend copies `trackingUrl` from the delivery payload. `trk` is a display reference, not a replacement for the shipment-specific link.

Do not derive a route map or a shipment URL from a tracking number. A customer tracking link can open the provider page, but does not establish a route polyline for this interface. OptimoRoute's authenticated WS API can return route polylines through `get_routes` with `includeRoutePolyline=true` if the account enables API access. Its customer tracking page may show an address map, ETA, and optionally the driver's position, depending on account settings; that is not the complete route. Palletways' documented authenticated API supports consignment status and PoD, but no route polyline endpoint was verified. No XDP route polyline API was verified from public documentation. Keep provider keys on the backend. Only render route geometry if the backend explicitly supplies verified route data in a future design.


## Replacement / Credit Refund Tracker

The dashboard widget gallery includes a 1x1 Replacement / Credit Refund Tracker
with the same system utility styling as Order Identifier. It accepts an exact
numeric order ID and displays the saved order-family flow, statuses and the
searched order highlight. It does not change the user's existing widget layout.
`GET /api/order-flow?order=<order-id>` returns `found`, `order` and `flow`, without
provider calls or delivery-table results. Connected orders return the same graph
regardless of the searched position. Orders without links display an empty state.
Tracking exact-order searches label each family result under its Order No as
Order, Replacement or Credit/Refund. Ordinary results without family links have
no extra label.
