# Google Sheet → Atlas frontend gap audit (12 November 2026)

Source: the OW workbook `1F2DnKdPEm-LdxM1Ag6hTcvP7a8glhnESl9m7-UlvNcs`. All 17 tabs were read through the configured read-only service account. Counts below are populated **sheet rows**, not distinct orders. The audit retained only headers and counts; no customer rows were saved. `_Sales_Activity_Import` returned no values through the API despite a configured 19,027-row grid, so its contents could not be assessed.

The current Atlas instance has `ATLAS_GOOGLE_SHEETS_ENABLED=false` and uses the PostgreSQL test delivery source. This is a comparison with the workbook and current frontend/backend code, not proof that the frontend currently synchronizes these tabs.

| Tab | Data rows returned | Populated columns | Current Atlas use / principal gaps |
|---|---:|---:|---|
| Sales Activity | 29,212 | 34 | Core orders/items/statuses. Missing order address from new split address columns; item description and several commercial/reference fields are retained but not shown. |
| Amazon Shipping | 21,034 | 45 | Reads TrackingId, Order status, Expected Date of Delivery. Claims, package, pickup/return, OTP/photo and other shipment facts are not imported from this tab. |
| Amazon Import | 18,098 | 45 | Same 45 headers as Amazon Shipping; import/staging tab is not read directly. |
| Palletways | 1,403 | 80 | Reads order/tracking/consignment/status and booking flags/date/time. Many shipment facts may appear from the separate Palletways API, but the sheet columns themselves are not generally imported. |
| Palletways Mapping | 1,232 | 3 | Redundant order/tracking/consignment mapping; not read directly. |
| XDP | 1,309 | 47 | Reads status, latest detail, consignment, POD URLs and parcel barcodes. Route, ETA window, latest location/event time and several operational facts are not directly imported. |
| XDP Activity Raw Archive | 12,682 | 14 | Archive is not read directly; XDP Activity supplies the activity feed. |
| XDP Mapping | 755 | 2 | Not read directly. |
| XDP Activity | 12,682 | 14 | Reads order, status type and raw event XML; event rendering uses the parsed feed. Other explicit columns are not mapped individually. |
| XDP Documents | 3,489 | 6 | Not read directly. XDP's separate POD URLs column is used. |
| Routine Dashboard - Live | 725 | 13 | Uses order text/colour in A and booking status in E. Other columns are not mapped. This is a layout sheet, not a conventional single-header table. |
| Completed Van | 22,369 | 13 | Not read by the Atlas code. Despite the headers, Status is usually a numeric sequence and Note is usually a phone number; these should not be treated as delivery history fields. |
| XDP Mapping Audit | 2 | 6 | Diagnostic tab, not displayed. |
| _Sales_Activity_Import | 0 returned | 0 returned | API returned no values; cannot classify. |
| STOPSTART | 402 | 15 | Reads order, status, delivery activity, fetch result and trackability; details are parsed for the frontend. Other raw columns are not mapped individually. |
| _Sync_Control | 5 | 8 | Uses integration, frequency, trigger status and last applied to show a schedule; full control configuration is not displayed. Disabled in the current Atlas configuration. |
| _Sync_Run_Log | 5,801 | 10 | Displays runs with nonzero insert/update activity using integration, start, result and counts; duration, API requests, finish time and full error details are not shown. Disabled in the current Atlas configuration. |

## Highest-value gaps

1. **Delivery address:** `Sales Activity` column P (`Address`) is empty, while Address1 (29,016 rows), Address2 (13,454), Address3 (325), Delivery Town (28,837), Country1 (23,360), and Country 2 (28,580) contain data. `row_to_delivery()` still reads `Address`; in the current Atlas cache, the saved `address` field is empty for all 27,916 orders checked. The detail drawer therefore has only postcode unless another provider supplies an address. The split fields are already used separately by Collection Note.
2. **Product description:** `Item Name` has 29,212 values and is saved in each item as `description`, but the purchase-items table in the order drawer shows SKU and quantity only.
3. **Order commerce/reference facts:** eCommerce order number (22,140), Gross (base) (29,212), Customer (29,212), Delivery cost (29,212), Account number (29,195), EbayUserID (3,892), Original order ID (1,746), and Order Type ID (29,212) are not general order-detail fields. Most are retained in `salesActivityDetails`; Account number is not retained. Gross is displayed for refund records. Original order number is used for related orders. `EbayUserID` is not an eBay item ID and cannot establish a product link.
4. **XDP route/ETA:** Route has 342 values and ETA Window 340. Latest Location, Event Date and Event Time have 1,222 values each. Atlas does not directly map these XDP columns to dedicated detail fields. Activity XML may convey some of the event context.
5. **Completed Van requires interpretation before use:** 22,369 rows exist in an unused tab. Of 20,504 populated `Status` cells, 20,459 are numeric (often 1, 2, 3, etc.), so this appears to be a stop/sequence number rather than a delivery outcome. `Date` has 19,841 formatted dates. Of 16,864 populated `Note` cells, 14,542 are phone-like; only 2,300 contain letters, including call and failed-delivery comments. Do not add these columns as a status/history panel without defining the sheet's actual schema.
6. **Amazon Shipping claims and package information:** Claims Id/Status/Raised/Updated each have 187 values; processed value has 74. Item Count, dimensions, weight, declared value, delivery speed, OTP eligibility, photo availability, pickup and customer-return flags are populated for most Amazon Shipping rows. Atlas reads only tracking ID, status and expected delivery date from this sheet; the live Amazon API may supply other details independently.
7. **XDP Documents:** 3,489 rows provide document type and URL in a separate tab. Atlas currently uses URLs from XDP's main tab, so this list could have additional documents, but overlap needs checking before joining.

## Lower-priority or operational fields

- Palletways has manifest, service, weight/lifts, insurance, collection/delivery contact and address, latest event, POD, media, label and sync fields. The detail drawer already shows many similar facts obtained from the Palletways API; sheet-specific gaps need record-by-record comparison to avoid duplicate or older values.
- `Amazon Import`, mapping tabs, raw archives and audit tabs appear to be staging or diagnostics. Their column counts should not be treated as missing customer-facing UI by default.
- `Routine Dashboard - Live` has values outside A and E, but its first row is not a usable schema. These need layout/section interpretation before mapping.
- `_Sync_Control` and `_Sync_Run_Log` contain more operational metadata than the current Data Trafficking page shows. They are currently disconnected in Atlas because Google Sheets is disabled.

## Existing frontend coverage

Atlas already displays core order number/reference, customer/contact, SKU and quantity, purchase store, status and carrier, tracking, scheduled/dispatch/completed dates, replacement/refund relationships, selected Palletways booking/details, XDP detail/POD, and STOPSTART delivery activity. The separate raw Google Sheet explorer supports Sales Activity and Palletways only, and returns HTTP 410 while Google Sheets is disabled.
