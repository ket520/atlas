# Delivery Desk code map

Orientation recorded 2026-10-20. Check the implementation before changing behavior: older design documents and parts of README describe earlier versions.

## Runtime and entry points

- `python server.py`: Python standard-library `ThreadingHTTPServer`, bound to localhost, default port 3000 (`PORT` overrides). No Flask, frontend build, or package.json.
- `server.py`: environment loading, read-only OptimoRoute client/normalization, explorer pagination sessions, HTTP API dispatch, public-file allowlist, collection save/delete/export, PoD image proxy. Starts Amazon background prefetch when run directly.
- Main URLs serve `pages/`: dashboard, deliveries, failed-deliveries, collective-note, integrations, settings, index and van-deliveries.
- `src/boot.js` defines the ordered script list. Feature modules `status-views.js`, `palletways-shipments.js`, and `product-links.js` load before `ui.js`; their rendering functions run after the app starts. `startup.js` runs early.
- Main CSS lives in `static/css/`: general, dashboard, tracking, failed-deliveries, startup, collection. README's statement that CSS is in src is stale.
- Other top-level HTML URLs resolve under `templates/`; source explorers use retained `static/js/` scripts. Collection Note is active code in `static/js/collection.js`. The superseded main-app templates and their eight legacy scripts have been removed; main pages use `pages/` and `src/`.

## Frontend ownership

| File | Responsibility |
| --- | --- |
| `src/api.js` | Routes, carrier/status constants, fetch timeout/error handling, delivery API |
| `src/services.js` | In-memory DeliveryStore, order deduplication, hydration and selection lookup |
| `src/status-views.js` | Tracking status labels and source selection |
| `src/palletways-shipments.js` | Multiple-consignment rendering, escaped structured details and backend detail requests |
| `src/product-links.js` | Verified product-link lookup, caching and official-domain validation |
| `src/ui.js` | Shared state/helpers/icons, filters, sidebar animation, DeliveryDetail drawer, gallery, activity timeline, carrier data/documents and Amazon lookup polling |
| `src/dashboard.js` | Dashboard cards and previews, paging, failed carousel, list scrolling |
| `src/dashboard-home.js` | Current dashboard workspace: filters, widget rendering, drag/order preferences, customization dialog and cohort navigation; `vDash()` delegates here |
| `src/deliveries.js` | Tracking/failed tables, carrier and classification filters, date sorting, server paging, scrollbar |
| `src/admin.js` | Collection records list, integrations, settings |
| `src/app.js` | Render dispatch, sidebar, delegated actions, navigation, lazy collection mounting, live summary refresh |
| `src/startup.js` | Per-tab startup overlay and ready event |
| `static/js/collection.js` | Editable collection form, undo/redo, formatting, row/cell operations, streamed lookup, records and export layout |
| `static/js/data-explorer.js` | Google Sheet explorer |
| `static/js/optimoroute*.js`, `order-activity.js` | Retained OptimoRoute explorer, live reads and activity |

Global script ordering matters. Main `R()` rendering replaces view markup; Collection Note has explicit mounted-form preservation. List requests and detail opening use request counters to discard superseded responses. Store hydration can replace visible records, so selected details are preserved explicitly.

## Backend and data flow

`atlas_config.py` reads local settings. `atlas_postgres_provider.py` reads the employee API; `atlas_palletways.py` bridges structured shipment details through the same server-side authentication. `palletways_shipments.py` normalizes consignments and derives shipment stages, while `status_views.py` keeps Sales Activity and courier status displays separate. `product_links.py` resolves and verifies product pages; `shopify_products.py` reads configured Shopify product URLs. Credentials remain server-side.

`GET /api/deliveries/summary` or `/api/deliveries` -> `cached_or_schedule_sync()` -> serve retained SQLite data immediately and schedule one background refresh when needed. Cache interval is 300 seconds; saved sync metadata survives restart. `query_records()` performs search/filter/sort/count/limit/offset in SQL. Normal browser page size is 25, API maximum 100.

`delivery_data.sync()` reads OW Sales Activity first, then STOPSTART, Amazon Shipping, Palletways API deltas, Courier Issues, Routine Dashboard, and today's OptimoRoute. Secondary source failures are reported individually. `current_or_sync()` retains saved orders when the live OW read fails. Orders missing from a later sheet are not deleted.

| File | Responsibility |
| --- | --- |
| `delivery_data.py` | Normalization/status mapping, SQLite order index/activity, preservation on import, carrier joins, synchronization, paging/facets/summary, detail enrichment |
| `dashboard_data.py` | Widget cohorts and bounded previews for `/api/dashboard`; shared SQL conditions and scoped Tracking facets for View all |
| `google_sheets.py` | Read-only Sheets access; gspread plus direct service-account HTTP fallback; preserve duplicate/blank headers; source tab readers |
| `sales_activity.py` | SKU header aliases and product item extraction |
| `routine_dashboard.py` | Local workbook path and booking row reader |
| `carrier_issues.py` | Exact order/carrier/reference joins, issue records and follow-up history |
| `stopstart.py` | UK delivery-window parsing, saved plans and observation history |
| `activity_log.py` | OptimoRoute observation/event history, aliases, lookup, legacy DB migration |
| `operations.py` | Read-only OptimoRoute route/dispatch/live operations |
| `collection_note.py` | Exact numeric order lookup, cached sheet and progress callbacks, editable-field mapping |
| `collection_records.py` | Shared-database collection note CRUD and latest note for order |
| `collection_export.py` | Layout validation; XLSX via openpyxl; PDF via Playwright Chromium |

## Carrier rules and workers

- OW `Order no` is order identity. Repeated product rows combine into one delivery. Customer/source fields remain OW facts; mapped carrier status can override OW status.
- Own van, Self Delivery and LOCAL MULTIDROP use OptimoRoute. Match OW order reference to a unique provider orderNo; ambiguous matches must not be guessed. Retain all PoD photos and signature. Today enrichment is bounded; detail lookup also enriches matching orders.
- Amazon: OW tracking ID joins sheet column B; G is status; M is UTC scheduled time converted to Europe/London. Current mappings also include READY_FOR_RECEIVE, LOST and UNDELIVERABLE, beyond README's older three-state description. No tracking ID is Unscheduled. Unknown/conflicting matches fall back to OW.
- `amazon_shipping_live.py`: reusable Playwright browser, serialized lookup scheduler, viewer/session tracking, cancellation/supersession, seven-step progress. `amazon_background_prefetch.py` scans scheduled IDs, skips saved captures and active jobs, and defers failed/non-delivered attempts. Foreground work can supersede prefetch.
- `amazon_shipping_demo.py`: saved capture normalization, delivery confirmation, document/excel/preview serving. `amazon_shipping_capture_parser.py` and capture scripts provide capture/history/document support. `amazon_shipping_demo_live.py`, `amazon_steps.py`, and `install_amazon_on_demand.py` are additional helper/installation scripts; do not run patch installers during ordinary startup.
- Palletways: `palletways_live.py` handles authenticated API requests, request pacing, event normalization/status derivation, deltas and PDF documents. `palletways_store.py` stores shipment/event/sync state in the shared database. `delivery_data.apply_palletways_api_data()` applies stored carrier facts to orders.
- `palletways_portal.py`: authenticated portal notes/photos via one reusable browser on a dedicated worker; metadata cache 120 seconds. `palletways_sheet.py`: exact order-to-tracking mapping cache 300 seconds. Photos use browser session; delivery PDFs and labels use API.
- Current Palletways mapping includes DELETED -> Rejected; README's older unverified description differs.
- Courier Issues supplies contextual facts/history without replacing carrier status. Failed list is strictly current Failed or Rejected. STOPSTART plans do not confirm delivery or replace OW status. XDP currently falls back to OW.

## Persistence and boundaries

- Primary persistent file: `data/delivery-desk.sqlite3`. Main tables: deliveries (JSON payload), activity, sync_metadata, collection_notes; additional OptimoRoute and Palletways tables share it.
- `activity_log.py` migrates legacy `data/optimoroute-activity.sqlite3` without deleting it. `palletways_store.py` enables WAL on its connections.
- Collection records store editable paper HTML plus summary. Exact address positions are AB/AC/AE/AG for street1/street2/city/country; optional street3 is header matched. Combined Address is not a collection-address fallback.
- Collection lookup emits NDJSON progress. Export sends a measured cell layout rather than blindly printing the app shell.
- Environment values and service account remain server-side. Avoid reading/outputting secret values for orientation. Public files are explicitly restricted. Browser profiles, capture data, SQLite files, caches, logs and backups are runtime/history artifacts, not the active source tree.
- OptimoRoute client permits only enumerated read methods. Local collection notes are intentionally writable through POST/DELETE; export also uses POST.

## Verification and documentation

- Existing checks: `python -m unittest discover -s tests`. Fixtures/mocks cover paging/status precedence, source joins, source mappings, progress, collection CRUD/export, portal lifecycle and public file protection. Reading/orientation does not require starting the server or contacting providers.
- `docs/SALES_ACTIVITY_MAPPING.md` documents source fields. `docs/BACKEND_API.md` and `ExcelDatabase/Database_ERD_Draft.md` contain historical/proposed behavior (including Current/History and older status restrictions), not a complete current API contract.
- No application behavior changes were made as part of creating this map. This is an orientation aid, not a complete line-by-line audit or a test result.

## Routine live priority added 2026-10-22

`routine_live.py` reads Google Sheets effective fills (including conditional formatting)
for column A between HYGIENIC ORDERS and XDP - Long Parcels. `delivery_data.archive_routine_live`
atomically replaces `routine_live_overrides`; `apply_routine_live_status` enforces it
on Own van writes. This priority source overrides OptimoRoute/OW until an order is
absent from a successful source snapshot. Failed source reads retain the last snapshot.
`tests/test_routine_live.py` covers extraction, scope, status changes, removals, failed
reads, provider refreshes/restart and stale provider payloads.
