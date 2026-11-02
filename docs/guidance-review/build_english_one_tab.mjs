import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from 'file:///C:/Users/NITRO%20V15/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const wb=Workbook.create();
const s=wb.worksheets.add('Status mapping review');
s.showGridLines=false;
s.freezePanes.freezeRows(8);

s.getRange('A1:G1').format.fill='#1E2B4B';
s.getRange('A1').values=[['Delivery Desk | Cross-platform status mapping review']];
s.getRange('A1').format.font={bold:true,color:'#FFFFFF',size:16};
s.getRange('A1:G1').format.rowHeight=38;
s.getRange('A2:G2').format.fill='#E8F1F6';
s.getRange('A2').values=[['Scope: OrderWise (OW), XDP, Palletways, OptimoRoute, Amazon Shipping and Own Van Routine Dashboard | 2 Nov 2026']];
s.getRange('A3').values=[['Decision rule']];
s.getRange('B3').values=[['Keep a broad shared status when it serves the same operational workflow. Preserve each carrier’s exact source label beside it.']];
s.getRange('A4').values=[['Confirmed keep']];
s.getRange('B4').values=[['OptimoRoute scheduled → Out for Delivery (own-van same-day plan); pre-last-mile states → Scheduled; operational exceptions → Failed/Rejected; XDP source status remains separate from overall Awaiting.']];
s.getRange('A5').values=[['Review only']];
s.getRange('B5').values=[['OW literal Cancelled; OptimoRoute cancelled; Amazon statuses that fall back to OW Completed; wording of OW Completed as a delivery proxy.']];
s.getRange('A6').values=[['Evidence limit']];
s.getRange('B6').values=[['OW workbook and local code/database snapshot checked read-only. No live carrier API call. Exact meanings of OW Sales Activity status codes need internal OW documentation.']];
s.getRange('A3:A6').format.font={bold:true,color:'#243052',size:11};
s.getRange('A3:G6').format.wrapText=true;
s.getRange('A3:G6').format.verticalAlignment='center';
s.getRange('A3:G6').format.rowHeight=50;
s.getRange('A5:G5').format.fill='#FFF0E8';

const rows=[
 ['Platform','Raw value / event','Platform meaning','Current shared status','Assessment','Reason / next action','Evidence'],
 ['OW','Completed / C','Order workflow completed; not itself carrier proof of delivery.','Delivered when no stronger carrier result','KEEP, clarify','Business fallback/proxy. Show status source as OW. OW Completed coexists with carrier In Transit in real orders.','delivery_data.py:863–888; OW export'],
 ['OW','Awaiting despatch / W; Invoice waiting / I; Partially despatched / P','Order or despatch workflow stage, not a carrier delivery scan.','Unscheduled for W/I; Scheduled for P','KEEP','Broad operational grouping is reasonable; retain raw OW wording.','src/ui.js OW_STATUS_DESCRIPTION; delivery_data.py'],
 ['OW','Cancelled (literal text)','Order cancelled in the OW export.','Usually Unscheduled unless delivery method overrides','REVIEW','155 distinct OW orders have literal Cancelled; only 74 use TO BE CANCELLED method. Confirm cancellation priority and explicit text mapping.','OW export; delivery_data.py:87–97,863–888'],
 ['Own Van Routine','White / amber / yellow order-cell fill','Internal same-day planning / failed-workflow colour rules; not carrier terminology.','Scheduled / Scheduled / Failed','KEEP','Applies only to Own van and has configured priority. Preserve booking text separately.','routine_live.py; delivery_data.py:140–171'],
 ['OptimoRoute','unscheduled','Order is not planned.','Unscheduled','KEEP','Same operational meaning.','OptimoRoute API Order Status Values'],
 ['OptimoRoute','scheduled','Provider says service has not started; in this business, adding an own-van order to the plan means it will go out that day.','Out for Delivery','KEEP — confirmed business rule','Do not describe this as driver already on route; retain raw scheduled status.','User-confirmed rule; OptimoRoute API'],
 ['OptimoRoute','on_route / servicing','Driver is travelling to the stop / serving at the stop.','Out for Delivery','KEEP','Both are in the active own-van delivery workflow.','OptimoRoute API Order Status Values'],
 ['OptimoRoute','success / failed / rejected','Successfully completed / driver failed / driver rejected.','Delivered / Failed / Rejected','KEEP','Shared buckets are operational; raw label distinguishes driver rejection from recipient refusal.','OptimoRoute API Order Status Values'],
 ['OptimoRoute','cancelled','Customer cancelled the provider order.','Falls back to OW','REVIEW','Provider value exists but is absent from mapper. Confirm whether it should override OW cancellation status.','OptimoRoute API; delivery_data.py:100–110'],
 ['XDP','DELIVERED','Carrier says item delivered; POD may be available.','Overall Awaiting; XDP-specific filter shows DELIVERED','KEEP AS DESIGNED; business decision open','Guidance and tests explicitly separate carrier-specific labels from saved overall status. 768 current OW XDP orders have raw DELIVERED.','XDP FAQ; src/admin.js; tests/test_xdp_sheet.py'],
 ['XDP','NEXT STOP / DELIVERY / COLLECT','Next stop; at delivery depot; at collection depot in sampled details.','Overall Awaiting; raw status remains filterable','KEEP','Guidance rows are reference groupings, not saved overall mappings.','XDP sheet I/J; src/admin.js mapping note'],
 ['XDP','DAMAGE / NOT RECEIVED / DELETE','Carrier exception/event codes; exact internal DELETE meaning not publicly defined.','Failed','KEEP; check DELETE meaning','Failed is the action queue. Keep source label; avoid describing DELETE as a failed doorstep attempt without evidence.','XDP sheet I/J; xdp_sheet.py:12–23'],
 ['XDP','EMAIL / blank','Notification event / no usable carrier status.','Awaiting','KEEP','Awaiting is the shared unverified XDP state, not carrier unscheduled.','XDP sheet I/J; xdp_sheet.py'],
 ['Palletways','POD/POD','POD event with delivery evidence, date/time or signature.','Delivered','KEEP','Carrier evidence supports delivery.','Palletways API docs; palletways_live.py:489+'],
 ['Palletways','VL/SCN/800; VP/DAR','Local delivery vehicle scan / driver arrived, per current event interpretation.','Out for Delivery','KEEP','Active last-mile stage; preserve event detail.','palletways_live.py:580–624'],
 ['Palletways','Hub/depot movement (BAY, VU, VL, JIN, ARC)','Freight moving in the carrier network.','Scheduled (via In Transit)','KEEP','Scheduled is deliberately broad pre-last-mile workflow; raw In Transit remains available.','palletways_live.py:625–643; delivery_data.py:222+'],
 ['Palletways','BIN booking / POC','Booking workflow / POC event; POC precise expansion not confirmed.','Scheduled','KEEP; check POC wording','These belong to pre-last-mile operational work. Avoid claiming POC alone proves a booked delivery.','palletways_live.py:645–675; Palletways API'],
 ['Palletways','Damaged / Lost / Refused / Return','Different exception and disposition reasons.','Failed / Lost / Rejected / Return','KEEP','Shared queues group work; preserve exact reason and who refused.','palletways_live.py:489–580; delivery_data.py:222+'],
 ['Palletways','TrackingID vs OW Tracking No','TrackingID is carrier-assigned; Reference is the customer reference.','Different identifiers','KEEP','979 matched orders have unequal numbers; this is not 979 data errors. Join via OW order no ↔ Palletways Customer Ref/API Reference.','Palletways API docs; OW/Palletways export'],
 ['Amazon Shipping','READY_FOR_RECEIVE / IN_TRANSIT','Package ready for pickup / picked up and moving through network.','Scheduled','KEEP','Both fit the deliberately broad pre-last-mile shared bucket; source label remains visible.','Amazon Shipping API status model'],
 ['Amazon Shipping','OUT_FOR_DELIVERY / DELIVERED','Last-mile delivery / successfully delivered.','Out for Delivery / Delivered','KEEP','Matches operational meaning.','Amazon Shipping API status model'],
 ['Amazon Shipping','LOST / UNDELIVERABLE','Lost / cannot be delivered.','Failed','KEEP','Failed is the work queue; raw Lost/Undeliverable remains visible.','Amazon Shipping API status model; src/admin.js'],
 ['Amazon Shipping','DELIVERY_ATTEMPTED / REJECTED / AWAITING_CUSTOMER_PICKUP / RETURNED_TO_SELLER','Attempt failed / recipient rejected / held for pickup / returned to seller.','Unmapped; falls back to OW','REVIEW','7 + 1 + 1 + 2 matched OW orders respectively have OW Completed. Fallback may show Delivered despite carrier issue. Assign to existing buckets.','Amazon Shipping export; delivery_data.py:174–183,1296+'],
 ['All methods','OW fallback source label','A proxy when no usable carrier result exists; not a POD claim.','May show Delivered from OW Completed','KEEP, clarify','Show OW as source and explain fallback in Guidance; do not present it as carrier confirmation.','delivery_data.py; src/ui.js statusSourceDisplay'],
];
const start=8;
s.getRangeByIndexes(start,0,rows.length,7).values=rows;
s.getRangeByIndexes(start,0,1,7).format.fill='#243052';
s.getRangeByIndexes(start,0,1,7).format.font={bold:true,color:'#FFFFFF',size:11};
s.getRangeByIndexes(start,0,rows.length,7).format.wrapText=true;
s.getRangeByIndexes(start,0,rows.length,7).format.verticalAlignment='center';
s.getRangeByIndexes(start,0,rows.length,7).format.rowHeight=62;
s.getRangeByIndexes(start,0,1,7).format.rowHeight=34;
for(let i=1;i<rows.length;i++){
 const judgment=rows[i][4];
 if(judgment.startsWith('REVIEW')) s.getRangeByIndexes(start+i,0,1,7).format.fill='#FFF0E8';
 else if(i%2===0) s.getRangeByIndexes(start+i,0,1,7).format.fill='#F2F6FA';
}
for(const [col,width] of Object.entries({A:21,B:42,C:66,D:36,E:27,F:93,G:57})) s.getRange(`${col}:${col}`).format.columnWidth=width;
const preview=await wb.render({sheetName:'Status mapping review',range:'A1:G13',scale:1,format:'png'});
await fs.writeFile('C:/atlas/docs/guidance-review/english_one_tab_preview.png',Buffer.from(await preview.arrayBuffer()));
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save('C:/atlas/docs/guidance-review/Delivery_Desk_Status_Mapping_Review_EN_2026-11-02.xlsx');
console.log(`saved ${rows.length-1} mapping rows`);
