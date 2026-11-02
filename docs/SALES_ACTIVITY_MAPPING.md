# Current Sales Activity mapping

Manufacturing Claims looks up exact original/replacement order numbers through
`GET /api/manufacture-claims/order-lookup?order=...`, using the retained Sales
Activity index and the same N/AI links as Tracking. A unique replacement fills
automatically; multiple replacements are offered as choices. VariantCode uses
the original order's explicit Product SKU values, combined across product rows;
Parent SKU is never substituted. Existing manually edited values are preserved.
Selling shop autofills through the same AH/store-code mapping used by Tracking.
Autofilled fields flash yellow and fade back to their normal background.
Both original and replacement order numbers are required when saving a claim.
Restart and synchronize after updating to index version 39 to populate Product SKU.

The first row contains headers. Order and product fields map by header name.
Collection Note's dedicated address fields and the store code in AH use explicitly assigned sheet columns.
Other columns can be reordered without changing their header mapping. Headers other than SKU aliases
must retain their spelling and capitalization.

| Index | Header | Application mapping |
|---|---|---|
| 0 | Order no | Stable Tracking order ID; Collection Note lookup and collection order number |
| 1 | Order date | Tracking order date; note dates continue to default to today |
| 2 | Delivery name | Customer / collection recipient |
| 3 | eCommerce order number | Retained in salesActivityDetails |
| 4 | Order reference | Tracking reference, OptimoRoute match, note reference |
| 5 | Product SKU | Tracking SKU list and product items; note Item Code |
| 6 | Item Name | Product description; note Item description |
| 7 | Item Quantity | Product quantity; note QTY |
| 8 | Special instructions | Tracking special instructions |
| 9 | Status | Raw OW status and carrier-status fallback |
| 10 | Order Type | Note Company (column K); retained in salesActivityDetails |
| 11 | Order Analysis | Note Company when Order Type is Shopify (column L); retained in salesActivityDetails |
| 12 | Replacement | Retained in salesActivityDetails |
| 13 | Original order Number | Column N; exact original-order join for Tracking's replacement and credit/refund records |
| 14 | Original order ID | Retained in salesActivityDetails |
| 15 | Address | Tracking address only; never split for Collection Note |
| 16 | Delivery postcode | Tracking postcode and note Post Code |
| 17 | Gross (base) | Retained in salesActivityDetails |
| 18 | Tracking No | Tracking number; Amazon Shipping join |
| 19 | Delivery method | Carrier and delivery-method classification |
| 20 | Customer | Retained in salesActivityDetails |
| 21 | Delivery telephone | Tracking and note telephone |
| 22 | Delivery email | Tracking email |
| 23 | Despatch Date | Tracking dispatch date |
| 24 | EbayUserID | Retained in salesActivityDetails |
| 25 | Order Type ID | Retained in salesActivityDetails |
| 26 | Delivery cost | Retained in salesActivityDetails |
| 34 | Order Category | Column AI; linked Order records are Replacement; linked Credit/Refund records are Credit/Refund |

Tracking exact numeric order searches request `tracking_related=1` on the delivery
list API. The searched order appears first, followed by a labelled section of
records whose Original order Number matches exactly. Those contextual linked rows
also work in reverse: searching a replacement or credit/refund ID shows that
record first, then its saved parent under Original ID Found. A missing parent
record is never invented. Source-only credit records remain visible without
offering a delivery-details action when no delivery record exists. Linked rows
can have different couriers or fall outside the current list filters; normal list
counts and paging are unchanged. Product rows combine by order number. Unknown or
conflicting categories/original numbers are not classified. Credit/Refund records
without a delivery method are retained in `tracking_related_orders` without adding
them to delivery counts or inventing a delivery status. Successful observations
update links for observed orders; records absent from later feeds remain retained.

Tracking saves one record per Order no and combines distinct product rows into
its items array and unique SKU list. Order-level fields retain the last valid row's
values. New informational fields are retained without adding new table columns.

Collection Note combines distinct product rows for the exact order number.
Item Quantity fills QTY when it is a nonnegative number; missing or unsupported
values remain editable and blank. A multi-SKU cell is split into individual codes,
but its description and quantity are not guessed for each code. Restoring a removed
SKU also restores its source description and quantity.

Collection Note reads Street 1 from AB (index 27), Street 2 from AC (index 28),
City from AE (index 30), and Country from AG (index 32). Values, including commas,
are kept intact. Empty or conflicting source values remain blank. The old combined
Address field is never used as a fallback. Post Code comes from Delivery postcode.
Street 3 is read by its column header (Street 3, Address 3, or Delivery address
line 3). When that column has a value for the order, an extra Street 3 row is
inserted below Street 2. A missing or empty column leaves only Street 1 and Street 2.
Tracking appends the postcode when the address does not already contain it.
Earlier address, parent-SKU and description headers remain accepted for backwards
compatibility. Condition, Reason of Return and Collection Date remain manual.

## Purchase stores (AH)

Column AH (zero-based index 33) supplies `storeCode`, independent of its header.
Tracking, the Purchased from drawer and store filtering use this mapping after the next Sales Activity sync.
Orders saved before AH was imported retain their original Order Type / Order Analysis store mapping and icons.
Once AH has been imported, its value takes priority; blank or unknown AH codes have no mapped store.
Hygienic keeps its existing priority rule: Order Type = Sales or HR_Replacement.

| AH value | Store |
|---|---|
| AMAZON | Amazon |
| DEBENHAM | Debenhams - Neshome |
| B&Q | B&Q |
| EBAY_BR | Ebay Bathroom Republic |
| EBAY_WB | EBay Willesden Bathroom |
| SHOPIFY | Shopify - Neshome |
| BATHPROF / BATHREP / BATHROOM | Bathroom Republic - Website |
| WILKO | Wilko |
| WAYFAIR | Wayfair |

Codes ignore capitalization and surrounding spaces. AH distinguishes both eBay stores directly.
Existing store images are retained; Wilko uses assets/wilko.png and Wayfair uses assets/wayfair.jpg.

## Palletways B2B visibility

Settings > Hide data > Palletways B2B excludes Palletways orders whose carrier
Classification is B2B (ignoring case and surrounding spaces). The preference is saved
in the browser. Filtering happens before server paging, and Tracking filter counts
and available stores respect the switch. B2C and unknown classifications stay visible.
The server checks the saved shipment by tracking ID or a unique OW order reference,
then falls back to the saved order detail classification. No portal lookup is required
to filter a shipment already captured in the carrier database.

## Amazon Shipping table Tracking ID

When the Amazon Shipping delivery method is selected, Tracking ID appears immediately
before SKU of items, with a copy button. Sales Activity Order no (column A) identifies
the saved order; Tracking No (column S) supplies the displayed value (`owTrackingNo`).
Blank tracking IDs show a dash without a copy button. This column does not use the
Amazon Shipping tab. Existing carrier status lookups remain unchanged.

## XDP Consignment No

When XDP is selected, Consignment No appears immediately before SKU of items,
with a copy button. XDP tab column A matches OW Order no. The value comes from
a unique XDP Consignments / Consignment / Consignment No / Consignment Number header, or the unique
tracking-ID header if no dedicated consignment header exists. Conflicting values
for an order show a dash; OW tracking is not a fallback for this display column.
Special instructions is displayed under Details in the sidebar instead of the XDP table.

## STOPSTART platform button

The Stopstart table moves Special instructions into the Details sidebar and adds
Tracking immediately after Booking status. STOPSTART column A matches OW Order no.
Column O (Trackability) = Yes enables Open tracking at
https://track-my-order.co.uk/track_my_delivery/{Order ID}/ .
No, Missing, Time Out, blank and conflicting values show no button. A blank legacy O
can use its saved N Fetch Result using the supplied automation's backfill rules.
No extra platform request is made to decide availability. The current A:O layout
reads Delivery Activity from J; older layouts retain the H details mapping.
Unavailable tracking never clears previously saved complete delivery details.

## Own van priority from Routine Dashboard - Live

The app reads Routine Dashboard - Live in the same Google workbook as Sales Activity.
The section begins after HYGIENIC ORDERS in column A and ends before XDP - Long Parcels
in column A; both marker rows are excluded and the boundaries are rediscovered each read.
Order numbers are the first six consecutive digits in the column A cell. Thus
659631 - 601216 matches 659631 only; 650410-59696.remainder matches 650410 only.

| Effective order-cell background | Priority status |
|---|---|
| #FFFF00 | Failed |
| #FFFFFF, including default white, with a six-digit order number | Scheduled |
| #FFC000 | Scheduled |
| #FFE598, all other colours, blanks or no six-digit order number | No override |

Only carrier Own van is overridden. Self Delivery, LOCAL MULTIDROP and other carriers
keep their normal statuses. If the same order appears more than once, Failed wins.
The source label is Routine Dashboard - Live. Carrier facts and observations remain saved.

Every successful normal sync atomically replaces the routine_live_overrides snapshot.
Missing orders or ignored fills remove a prior override and immediately restore the usual
OptimoRoute/OW fallback. A failed read or invalid/missing section markers retains the
previous snapshot and reports Routine Dashboard - Live as unavailable. Normal syncs
run every five minutes. Existing OptimoRoute status mappings remain unchanged.

Override checks are also applied on OW import, OptimoRoute today's/page/detail updates
and restart, using the authoritative snapshot inside the write transaction. Tracking,
Failed Deliveries and Dashboard filters/counts read the resulting saved status.
Count Routine Dashboard Rows.ps1 prints a read-only candidate preview for validation.

### Own van booking status from live column E

Display formatting expands `Del Fri` (and other weekdays) to `Delay to 23-Oct-2026`, using the next matching weekday including today. `o/s` becomes `Out of Stock`; `ND` is retained. Numeric dates use UK day/month order: `partial delivered 5/10` becomes `Partial delivered 5-Oct-2026`. Named dates such as `23-Oct` gain the current UK year; explicit years are preserved. Unknown text and invalid dates are retained, with the first letter capitalized. Raw column E values remain saved so display formatting can be reapplied.

The same marked Routine Dashboard - Live section supplies Booking status from column E.
Column A identifies orders using the first six digits on each line. Values are saved
as supplied and displayed using the booking text formatting rules above. Booking
text does not change the delivery status category.
This mapping is independent of the order-cell colour. Each successful read replaces
routine_live_bookings: blank E values or missing orders clear the old booking value.
Read failures retain the last successful snapshot. Duplicate conflicting E values are
left blank rather than guessed. This applies to Own van only and takes priority over
the older local workbook's Booking status, including during provider/detail updates.

### Multiple order numbers in one Routine cell

Each line in column A identifies a separate order, using the first six digits on
that line. A cell containing 659669 followed by a newline and 659670 applies its
colour-based status and column E booking value to both orders. Extra reference
numbers on the same line remain ignored: 659631 - 601216 matches 659631 only.
Repeated copies of the same order within a cell are deduplicated.
