# Delivery Desk

Run `& ".\Start Delivery Desk.ps1"` from this folder. The script uses port 3000 by default, replaces an existing Delivery Desk process on that port, checks that the dashboard responds, and opens it in your browser. You can also run `python server.py` directly when port 3000 is free. The server needs internet access to read the connected Google Sheet and OptimoRoute API. The provided `.env` and `credentials/google_service_account.json` remain local and are ignored by Git.

The main HTML pages are in `pages/`, their JavaScript is in `src/`, and shared CSS is in `static/css/`. Browser URLs remain `/dashboard.html`, `/deliveries.html`, and the other existing page names. `templates/` holds the retained source explorer pages; `static/js/` contains their scripts and the active collection-note editor. The superseded copies of the main frontend have been removed. API notes and third-party notices are in `docs/`.

On the first visit in a browser tab, an animated Delivery Desk startup screen
opens while the initial overview loads. Slow loads offer Continue to workspace;
the startup also clears automatically so the app stays accessible. Navigation and
refreshes in the same tab do not replay it. Reduced-motion preferences are respected.

## Main pages

Desktop screens automatically zoom the interface out to fit a 1920 x 1080
reference workspace (for example, 1440 x 810 uses 75%). Navigation and controls
shrink together; mobile layouts and printed documents retain their own sizing.

Manufacturing Claims accepts claims through **New claim** and retains the order
date, original/replacement order numbers, VariantCode, reason, solution and selling
shop. Reasons and solutions offer an **Others** option for custom text. Selling
shops use the existing Tracking shop list. Claims may include up to five JPG,
PNG, WebP or GIF pictures (5 MB each, 15 MB total), with previews before saving
and clickable pictures in the table. Claims and original pictures are stored in
the shared local database and survive refreshes. Restart the server after adding
this feature so its API routes are loaded.
The **XLSX** and **PDF** buttons download the currently displayed claims with the
same column names, row order, text values and picture thumbnails. Order numbers
remain text in XLSX, preserving leading zeroes. PDF downloads use landscape
pages with repeating table headers; XLSX includes a frozen header and printable
landscape layout.

The dashboard's B&Q NesHome store button connects the installed, signed-in
ExpressVPN app to UK London, then opens B&Q in a separate Chrome (or Edge) window.
Closing the last tab in that window disconnects ExpressVPN, including a VPN
connection that was already active before clicking. Keep Delivery Desk running
until the B&Q window closes. Other store links open normally. B&Q cookies and
sign-in state are kept locally in the ignored `data/bq-native-profile/` folder.
This feature works from the local `http://localhost` or `http://127.0.0.1` dashboard.
ExpressVPN is detected from its running app, PATH, Windows installation records,
and common install folders, then Downloads/Desktop/Documents and all accessible
local drives if needed. The discovered path is cached until the app moves.
If the desktop app is closed, Delivery Desk starts it beside the discovered
`expressvpnctl.exe`. A full drive search can take time; inaccessible folders and
directory junctions are skipped. Downloaded installers are not used as VPN apps.

The navigation contains Dashboard, Tracking, Failed Deliveries, Integrations and Settings. Dashboard previews up to 25 of today's ongoing deliveries and 25 failed or rejected deliveries. Its **View all** buttons open the corresponding lists. The delivery pages use OW `Sales Activity` for order identity, customer details and delivery method. The server reads the sheet at most once every five minutes unless it is refreshed. It saves each observed order in `data/delivery-desk.sqlite3`, so orders stay searchable after they disappear from a later sheet. Carrier status changes observed between reads are recorded in the activity log; changes that occurred entirely between reads cannot be reconstructed without source events.

Tracking is one list with no Current/History split. It starts with 25 orders and automatically appends the next batch of up to 25 when the user scrolls to the bottom of the table. Existing rows and scroll position are retained. Failed requests keep the loaded rows; scrolling up and back down retries the batch. Search, status, carrier and date filters run against the entire saved order index on the server, including orders not loaded in the browser. Failed Deliveries uses the same paging and shows only orders whose current status is Failed or Rejected. The source sheet still needs to be read during synchronization so its complete contents can be indexed; pagination limits what the browser loads and renders.

The delivery status is grouped into Unscheduled, Scheduled, Out for Delivery, Delivered, Failed, Rejected, Cancelled, and Return. A mapped OptimoRoute or Palletways status takes priority for its matching order; otherwise the OW order status is the display fallback. The small label below the table status names the source used, while the activity log shows the full OW status description. OW code X means Cancelled and is excluded from Failed Deliveries. These OW categories are order-level approximations, not independent delivery confirmation. The original codes remain saved. XDP uses OW until its carrier connection is available. Today's OptimoRoute stops are checked in bulk; older Own van statuses are checked for the visible page of up to 25 orders and again when a detail is opened. Status filtering uses the saved index, so older orders become filterable by carrier status after their page has been checked.

The connected Palletways tracking sheet uses `Customer Ref` to match OW `Order no`. Its `Tracking ID`, `Due Date`, `Status`, and `Date Completed` are used for matching deliveries. An 11-digit `Tracking ID` opens Palletways' public tracking page. `JOB COMPLETE` with a completion date maps to Delivered; the observed depot and hub transit labels map to Scheduled. `DELETED` is left unverified internally and shown verbatim in Tracking. The sheet has no PoD file; the detail panel links to Palletways for available PoD. Direct Palletways PoD PDF retrieval needs a separate Palletways API key, which is not configured. XDP carrier tracking API is also not connected to the main pages.

Courier Issues is a separate read-only Google workbook. It matches OW `Order no` to `Van.Order ID`, `Palletways.Order number`, or `XDP.Order number`; Van also checks `Order Reference` when both sides provide one. The `Van` tab supplies operational status, notes, message and rescheduling status, and actual follow-up remarks; the first three repeated `Follow up` headers contain method/area/numeric values and are not treated as remarks. The `Palletways` tab supplies narrative issue status, dispatch date, and multiple follow-ups. The `XDP` tab supplies issue type, details, dispatch date, and follow-ups. Exact own-van matches in `Cancelled Orders` and `COMPLETED VAN DELIVERIES` are shown as separate source records. The latter tab's numeric `Status` values are not treated as proof of delivery. These facts remain in the order detail and activity log; the Failed Deliveries page includes an order only while its current status is Failed or Rejected. Courier Issues never overwrites carrier tracking status, OW customer details, or the source Google Sheet.

Opening an Own van order tries to match its OW `Order reference` to a unique OptimoRoute `orderNo`. A unique match adds planned date, tracking link, completion status/time and all available PoD photos and signature. Each image has its own open and copy actions. Repeated or missing references are left unmatched. The original OW order remains visible. OptimoRoute activity observations are stored in the shared `data/delivery-desk.sqlite3` database. On first use, the app copies any existing `data/optimoroute-activity.sqlite3` records into the shared database without deleting the old file.

For deployment, keep `data/delivery-desk.sqlite3` on persistent storage and include it in backups. The old `data/optimoroute-activity.sqlite3` is a migration backup and is not required by a fresh deployment after migration. Source credentials, environment settings, and the external Routine Dashboard workbook are separate from the database and must be configured in the deployment environment. Do not commit the database or credentials to Git.

Each OW refresh also checks up to three pages of today's OptimoRoute stops in batches of 25 to populate the Dashboard's today list. This is deliberately bounded; the full OptimoRoute explorer remains available for older or unmatched stops. If a carrier request fails, the OW order list still loads and the response identifies that source as unavailable.

## Source tools retained

The original OW sheet explorer (`excel.html`), Palletways sheet explorer (`palletways.html`), and OptimoRoute explorer (`optimoroute.html`) remain available by direct URL. Integrations and Settings remain in the main sidebar. The sheet explorers preserve full columns, search, pagination and CSV export. The OptimoRoute explorer preserves its paging, filters, completion/PoD display, live route inspection and activity search.

The OptimoRoute connection is read-only. The server rejects write methods. Credentials and local databases are never served as public files.

## Amazon Shipping status

Selecting Amazon Shipping in Tracking uses the matched column G values for its
status filter and table labels (for example Ready To Receive and In Transit).
Options and counts cover the saved order index, including statuses outside the
general mapping. Orders without an unambiguous nonempty match keep their existing
fallback status. All methods continues to use the shared status groups. Switching
into or out of Amazon clears the selected status filter.

Each delivery synchronization reads the `Amazon Shipping` tab in the same Google workbook as `Sales Activity`. For all Amazon delivery methods grouped as AMZ, OW `Tracking No` matches column B (Tracking ID), and column G supplies the status: `OUT_FOR_DELIVERY` becomes Out for Delivery, `DELIVERED` becomes Delivered, and `IN_TRANSIT` becomes Scheduled. These saved statuses drive Tracking, counts, and filters, with Amazon Shipping shown as the status source. Missing IDs, unsupported statuses, or conflicting duplicate rows fall back to OW. If the tab cannot be read, the last matched status is retained for the same tracking ID and the source is shown as unavailable. The on-demand browser lookup continues to supply detailed history and documents separately.

Amazon's scheduled date is read from column M in `dd/mm/yyyy HH:MM (UTC)` format and converted to `Europe/London`, including British Summer Time. Tracking and order details show the UK date and time; date filters use that UK date. Item SKUs come from Sales Activity, preferring Parent SKU and accepting Product SKU when that is the supplied header.

The Palletways Tracking table number heading switches between **Tracking No**
(column B) and **Consignment No** (column C) from the Palletways tab, matched by
order number in column A. The selected display and copy button use the same
value, and the browser remembers the choice. Portal lookups continue using B.

## Palletways shipment photos

Opening a Palletways order first matches its OW order number to column A of the
Palletways tab in the Sales Activity workbook, then uses column B as its tracking
ID to load portal photos on demand. The sheet mapping is cached for five minutes;
Refresh photos rereads it. Photos are discovered from consignment notes and portal file links,
including links outside the note table; the lookup is not limited to a saved order.
The Documents tab shows loading or portal errors and provides Refresh photos to
retry, bypassing the two-minute metadata cache. A valid saved Palletways portal
login is required. Orders without portal photos show an empty state. The server
keeps one visible Palletways browser running and reuses its logged-in context for
subsequent order and photo requests. Browser operations run on one dedicated worker
thread. Finding photos does not close the browser. If sign-in expires, sign in in the open Palletways window
and click Refresh photos. Each lookup displays the shipment page for inspection.
Shipment images use Playwright's authenticated portal session. Delivery-note PDFs
and shipping labels use the Palletways API, not Playwright or spreadsheet links.

## STOPSTART

When Stopstart is selected in Tracking, its status filter and table use column I
verbatim. XDP similarly uses column I of the XDP tab in the Sales Activity workbook,
with title case labels such as Exception for EXCEPTION. XDP joins a uniquely named
order column, or a uniquely named tracking column when no order is supplied.
Missing or conflicting statuses use the existing fallback. All methods retains
the shared status groups. Source read failures retain saved courier statuses.

The STOPSTART tab in the Sales Activity workbook is read during normal synchronization.
Column A matches the exact OW order number for Stopstart deliveries; column H supplies
the expected delivery date, delivery window, driver and Stop Start reference. These
details appear on the order's Details tab. A window such as `09:27 (+2hr window)`
means `09:27 - 11:27` in UK local time, not a timezone shift. Dates use Europe/London
with GMT/BST offsets. Planned windows are merged chronologically with OW activity
and labelled as expected delivery, not delivery confirmation. Changed observations
are retained locally without adding duplicates. A failed sheet read preserves saved
details. Conflicting source rows are shown in history without choosing a current plan.
STOPSTART details do not replace the existing OW delivery status.

## Collection note

Collection Note opens a records table. Choose **Create collection note** to open
the form, then **Save note** to store its current fields, item rows and formatting
in `data/delivery-desk.sqlite3`. **Back to records** returns to the list; **Open note**
restores a saved note for editing, printing or export. Saving an opened note updates
that record. Creating another note creates a separate record, including for the same
order. Records survive browser and server restarts; include the database in backups.

Enter an exact OW order number in Collection Note to fill company/channel, recipient,
available delivery address fields, postcode, telephone, collection order number and
item SKUs from Sales Activity. All filled fields remain editable. Missing source
address fields and item descriptions are left for manual entry. The current Sales
Activity export supplies Product SKU, Item Name, Item Quantity and Address; these
fill item codes, descriptions and QTY. Collection Note reads Street 1 from AB,
Street 2 from AC, City from AE, and Country from AG. These fields retain their source
values, including commas; the combined Address field is no longer split or used as
a fallback. When a Street 3 column exists and has data for the order, an extra
Street 3 row appears directly below Street 2. Missing or empty Street 3 values
leave only Street 1 and Street 2.
Post Code comes from Delivery postcode. Order Date and the
lower Date default to today in the browser; Collection Date, missing QTY, Condition and
Reason of Return remain manual. Clear note clears the draft and restores today's
dates. The lookup reads the sheet at most once every five minutes and never writes
back to it.

The item table keeps a minimum of four rows. After lookup, extra wholly empty rows
are removed: one item leaves three blank rows, while five items use five rows.
Rows containing manual values are preserved. Add item row adds a manual row;
the cross inside the Item Code cell deletes that item row. Enter inserts a row below
the active cell in any of the three tables. Drag across cells in a table and press
Delete or Backspace to clear the selected inputs. Undo and Redo restore edits,
formatting, inserted/deleted rows and Clear note; Ctrl+Z and Ctrl+Y also work.
The right Messages panel displays all activity messages and SKUs without internal
scrollbars. Lookup progress shows an active loading bar while waiting for or reading
the sheet, then the actual number of source rows searched and form cells processed.
Server progress is streamed to the browser; completion appears after the form is
filled. The sheet fits its available width without horizontal scrolling. Found SKUs
appear in green boxes while present in the item table, and red boxes when removed;
editing, deleting, Undo and Redo update those states. Item deletion does not add
messages to the activity list. The panel and row-delete controls are hidden when printing.

The formatting toolbar downloads the current edited note as PDF or XLSX.
PDF and XLSX preserve the sheet's headers, borders, table widths and cell formatting,
including manually added item rows. Exports omit the messages,
toolbar, selection outlines and temporary yellow highlights, and never write to
Google Sheets. PDF generation needs Playwright and its local Chromium browser:
install the dependencies in `requirements.txt`, then run `python -m playwright install chromium`.

The current 27-column Sales Activity mapping is documented in
`docs/SALES_ACTIVITY_MAPPING.md`. Imports match headers, so inserting or reordering
columns does not shift fields. Tracking combines the product rows for each order.

## Checks

Run `python -m unittest discover -s tests`. Live Google and OptimoRoute requests need network access and valid account permissions; the tests use local fixtures and mocks.
