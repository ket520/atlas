import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from 'file:///C:/Users/NITRO%20V15/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const audit=JSON.parse(await fs.readFile('C:/atlas/docs/guidance-review/source_audit.json','utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('What to update');
const mapping=wb.worksheets.add('Field mapping');
const joins=wb.worksheets.add('Join audit');
const sources=wb.worksheets.add('Scope and evidence');
for(const s of [summary,mapping,joins,sources]) {s.showGridLines=false;s.freezePanes.freezeRows(1);}

const decisions=[
 ['Priority','Finding from current data/code','Impact','Recommended update / owner','Confidence'],
 ['High','Palletways OW Tracking No often differs from Palletways sheet Tracking ID B. Sample OW values include BQS/VAN references; only 55 matching source rows had equal B.','Using OW Tracking No directly as Palletways API ID will miss many shipments.','Keep OW order no → Palletways A → Tracking ID B as explicit join; verify API shipment Reference equals OW order no. Review 979 unequal matched orders before changing code.','Observed OW + sheet; API reference seen in one sample'],
 ['High','Amazon Shipping has 181 OW orders whose matching TrackingId B appears with conflicting Order status G values.','Current code treats these keys as ambiguous and falls back to OW.','Decide latest-row or timestamp rule from Shipment #/event history; do not arbitrarily choose a status.','Observed OW + sheet + code'],
 ['Medium','STOPSTART sheet contains 255 of 509 current OW STOPSTART orders by order ID A.','The other 254 lack a row in this snapshot; status/date/trackability cannot come from this sheet.','Confirm feed completeness and whether old orders should be included; do not infer a carrier failure from missing row.','Observed OW + sheet'],
 ['Medium','Palletways sheet now has header Palletways Status in F, while code uses fixed F. A separate legacy header-based archive expects Status and is not called in sync.','Current fixed-column reader works, but historical code/docs can mislead future changes.','Document fixed A/B/C/F/Z/AA columns; remove or update unused legacy reader only after checking callers.','Code + actual header'],
 ['Medium','XDP A matches all 952 current OW XDP orders in the exported snapshot.','Order join is strong in this snapshot; XDP status I is retained separately from overall status.','Keep A order join; verify event and POD links on representative orders.','Observed OW + sheet'],
 ['Medium','OptimoRoute is matched on OW Order reference ↔ provider orderNo, only when unique. No current live API export was available for a full join audit.','Ambiguous references cannot safely attach provider status/POD.','Export representative provider orders and check reference, scheduled date, completion and POD against OW.','Code verified; data pending'],
 ['Low','Routine Dashboard - Live colour status applies to Own van only; booking status is a separate field.','A white/yellow cell is not a general courier status.','Keep separate fields and note the scope in Guidance.','Code + header'],
];

const fields=[
 ['Displayed / stored item','OW field / join','Secondary source field','Code use today','Assessment','Evidence / follow-up'],
 ['Order number','Sales Activity A Order no','','Primary order ID; duplicate product rows combined','Correct source','delivery_data.py:1005, 1017; Sales Activity header'],
 ['Order reference','Sales Activity E Order reference','OptimoRoute data.orderNo','Unique match required for Own van/Self Delivery/LOCAL MULTIDROP','Needs sample verification','delivery_data.py:1553-1593; verify real provider examples'],
 ['Customer name','Sales Activity C Delivery name','','Displayed customer; fallback order ID','Correct source','delivery_data.py:1020'],
 ['Phone / email','Sales Activity V/W Delivery telephone/email','','Displayed contact','Correct source','delivery_data.py:1021-1022'],
 ['Address / postcode','Sales Activity P/Q Address/Delivery postcode','','Postcode appended if absent','Correct source','delivery_data.py:1010-1025'],
 ['Order date','Sales Activity B Order date','','Order creation date','Correct source','delivery_data.py:1045-1046; not scheduled delivery date'],
 ['Dispatch date','Sales Activity X Despatch Date','Palletways sheet legacy Dispatch Date','OW date; legacy Palletways reader could override but is not in normal sync','Review source freshness','delivery_data.py:1047,1452-1510,1773+'],
 ['Delivery method / carrier','Sales Activity T Delivery method','','Normalized to courier group','Check edge labels','delivery_data.py:56-84; 23,290 OW product rows'],
 ['SKU / items','Sales Activity F/G/H Product SKU/Item Name/Item Quantity','','Products combined by order','Correct source','delivery_data.py:1027-1030,1140-1151'],
 ['Overall status','Sales Activity J Status','Provider-specific statuses','OW fallback, provider mapping and overrides','Review textual OW values','delivery_data.py:87-110,863-888'],
 ['Own van booking status','Order no A','Routine Dashboard - Live E Status / colour in A','Booking text separate; colour overrides Own van overall status','Correct scope; verify colours on live sample','routine_live.py; delivery_data.py:140-171,1398-1450'],
 ['Own van live status','Order reference E','OptimoRoute status','Provider status; Routine live override for Own van','Needs live provider sample','delivery_data.py:100-110,1553-1630'],
 ['Own van scheduled date / ETA','Order reference E','OptimoRoute plannedDate / eta','Provider supplied','Needs live provider sample','delivery_data.py:893-961,1600-1618'],
 ['Own van POD','Order reference E','OptimoRoute photos/signature/POD note','Provider completion details','Needs live provider sample','delivery_data.py:893-961; server.py normalize'],
 ['Amazon join','Sales Activity S Tracking No','Amazon Shipping B TrackingId','Exact tracking ID; ambiguous conflicting status falls back to OW','8,531 of 9,102 OW orders matched','google_sheets.py:283-302; delivery_data.py:1296-1341'],
 ['Amazon status / schedule','Tracking No S','Amazon Shipping G Order status / M Expected Date of Delivery','Mapped status and UTC→UK schedule','181 status-conflict orders','delivery_data.py:174-193,1296-1341'],
 ['Palletways order join','Sales Activity A Order no','Palletways A Customer Ref','Sheet facts joined by exact order number','1,076 of 1,080 OW orders matched','google_sheets.py:264-273; palletways_sheet.py:12-67'],
 ['Palletways tracking ID','OW Tracking No S (often unrelated)','Palletways B Tracking ID; API Reference','Sheet B saved separately; API tries numeric OW tracking then shipment Reference=OW order no','979 unequal matched orders need review','delivery_data.py:238-249,252-420; sheet header and snapshot'],
 ['Palletways consignment / status','Order no A','Palletways C Consignment Number / F Palletways Status','Sheet reference fields; API provides actual physical status','Header F differs from old Status name','google_sheets.py:264-273; delivery_data.py:252-857'],
 ['Palletways booking','Order no A','Palletways Z Booked In / AA Book In Request','Saved as separate booking facts','Column positions match header','palletways_sheet.py:12-67'],
 ['Palletways due / POD','Order no or tracking','Palletways API DueDate, events, POD','API facts applied to order','Needs API coverage check','delivery_data.py:252-857; palletways_live.py'],
 ['XDP order join','Sales Activity A Order no','XDP A Order No','Exact order match; tracking fallback if order unavailable','952 of 952 OW orders matched','google_sheets.py:228-253; xdp_sheet.py:165-230'],
 ['XDP consignment','Order no A','XDP E XDP Consignments','Unique value saved as consignment number','Check multi-consignment orders','google_sheets.py:228-253; xdp_sheet.py:175-217'],
 ['XDP status / detail','Order no A','XDP I Latest Status / J Latest Details','Raw XDP status; only explicit failures alter overall status','Raw vs overall must be distinct','xdp_sheet.py:12-23,165-230'],
 ['XDP activity / POD','Order no A','XDP Activity B Order No / I Status Type / M Raw Event XML; XDP T POD URLs','Activity and documents joined to order','Check representative POD links','google_sheets.py:255-262; xdp_sheet.py:117-160'],
 ['STOPSTART order / activity','Sales Activity A Order no','STOPSTART A Order ID / I Calculated Status / J Delivery Activity','Context and tracking availability; no overall status override','255 of 509 OW orders matched','google_sheets.py:214-226; stopstart.py'],
 ['Courier Issues','Sales Activity A Order no','Van/Palletways/XDP issue tabs','Failure/follow-up context, not carrier status replacement','Separate workbook; live row audit pending','google_sheets.py:23-25,304-310; carrier_issues.py'],
];

const joinRows=[['Source','OW orders in method','Source rows','Matched OW orders','Unmatched OW orders','Status conflicts','OW/source tracking mismatch','Interpretation']];
for(const a of audit) joinRows.push([a.source,a.ow_orders,a.source_rows,a.matched_orders,a.unmatched_orders,a.status_conflict_orders,a.tracking_disagree_orders,a.source==='Palletways'?'OW Tracking No is often not the Palletways tracking ID':a.source==='Amazon Shipping'?'571 OW orders have blank tracking; 181 matched IDs have conflicting statuses':a.source==='STOPSTART'?'Coverage only; missing rows need feed review':'All current OW XDP orders joined by A']);

const notes=[
 ['Evidence','Scope / limitation'],
 ['OW workbook export','Read-only export of the linked Google workbook, 2026-11-02; tabs Sales Activity, Amazon Shipping, Palletways, XDP, XDP Activity, STOPSTART, Routine Dashboard - Live. No cells changed.'],
 ['Join audit','Counts are distinct OW order numbers after grouping product rows. This is a snapshot, not a live API health check.'],
 ['Amazon','Matching key is OW Tracking No S to sheet TrackingId B. Blank OW tracking explains all 571 unmatched current OW Amazon orders in this snapshot.'],
 ['Palletways','Matched by OW Order no to sheet Customer Ref A. Numeric API TrackingID B and OW Tracking No S have different roles; 979 mismatches should not be called errors without confirming OW field meaning.'],
 ['OptimoRoute','Code and older local .xls were available; no current provider API export was run. Mapping/join quality remains pending.'],
 ['Palletways API','Code and sheet/API-derived columns inspected; no authenticated live API call was made.'],
 ['Courier Issues','Separate workbook was not part of the supplied link and was not fetched here.'],
 ['Guidance','Original Guidance page and Google workbook were not edited. Proposed updates are review items, not implemented changes.'],
 ['Code state','Working tree already had unrelated modifications; audit did not change application code.'],
];

function write(s,rows,widths){
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).values=rows;
 s.getRangeByIndexes(0,0,1,rows[0].length).format.fill='#243052';
 s.getRangeByIndexes(0,0,1,rows[0].length).format.font={bold:true,color:'#FFFFFF',size:11};
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.wrapText=true;
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.verticalAlignment='center';
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.rowHeight=56;
 s.getRangeByIndexes(0,0,1,rows[0].length).format.rowHeight=30;
 const abc='ABCDEFGHIJKLMNOPQRSTUVWXYZ';
 widths.forEach((w,i)=>s.getRange(`${abc[i]}:${abc[i]}`).format.columnWidth=w);
}
write(summary,decisions,[13,78,63,77,38]);
write(mapping,fields,[35,45,62,64,42,52]);
write(joins,joinRows,[24,20,18,22,23,19,27,77]);
write(sources,notes,[26,115]);
summary.getRange('A2:E3').format.fill='#FFF0E8';
summary.getRange('A4:E7').format.fill='#FFF8E5';
for (const [sheetName, range] of [['What to update','A1:E8'],['Field mapping','A1:F8'],['Join audit','A1:H5'],['Scope and evidence','A1:B6']]) {
  const preview=await wb.render({sheetName,range,scale:1,format:'png'});
  await fs.writeFile(`C:/atlas/docs/guidance-review/preview_${sheetName.replaceAll(' ','_')}.png`,Buffer.from(await preview.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save('C:/atlas/docs/guidance-review/Data_source_mapping_audit_2026-11-02.xlsx');
console.log('saved');
