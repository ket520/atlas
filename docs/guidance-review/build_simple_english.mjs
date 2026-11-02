import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from 'file:///C:/Users/NITRO%20V15/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const wb=Workbook.create();
const s=wb.worksheets.add('Status map');
s.showGridLines=false;
s.freezePanes.freezeRows(5);

s.getRange('A1:F1').format.fill='#1E2B4B';
s.getRange('A1').values=[['Delivery Desk — Simple status map']];
s.getRange('A1').format.font={bold:true,color:'#FFFFFF',size:16};
s.getRange('A1:F1').format.rowHeight=40;
s.getRange('A2').values=[['Read across: the left column is our shared status; each other cell shows the source values currently grouped there.']];
s.getRange('A3').values=[['XDP note: its raw labels stay in the XDP filter. Only DAMAGE, DELETE and NOT RECEIVED change the shared status to Failed.']];
s.getRange('A2:F3').format.fill='#E8F1F6';
s.getRange('A2:F3').format.rowHeight=30;
s.getRange('A2:F3').format.font={color:'#243052',size:10};

const rows=[
 ['Our shared status','OW (order status)','Own van / OptimoRoute','XDP','Palletways','Amazon Shipping'],
 ['Awaiting','—','—','Most XDP orders (shared status); raw XDP label shown separately','—','—'],
 ['Unscheduled','W, K, H, I, A, U, Y; unknown/blank','OptimoRoute: unscheduled','—','Unscheduled','No OW tracking number'],
 ['Scheduled','P, S; SCHEDULED\nRoutine white/amber (Own van only)','—','DELIVERY (reference label only)','In Transit; Scheduled','READY_FOR_RECEIVE; IN_TRANSIT'],
 ['Out for Delivery','OUT FOR DELIVERY','scheduled (same-day plan); on_route; servicing','NEXT STOP (reference label only)','Out for Delivery; local vehicle/driver-arrived event','OUT_FOR_DELIVERY'],
 ['Delivered','C; Completed (OW fallback)','success','DELIVERED (reference label only; shared status remains Awaiting)','Delivered; POD event','DELIVERED'],
 ['Failed','FAILED; FAILED DELIVERY\nRoutine yellow (Own van only)','failed','DAMAGE; DELETE; NOT RECEIVED','Failed; Damaged','UNDELIVERABLE; LOST'],
 ['Rejected','REJECTED','rejected','—','Refused','—'],
 ['Lost','—','—','—','Lost','— (LOST goes to Failed work queue)'],
 ['Cancelled','X; TO BE CANCELLED method','—','—','—','—'],
 ['Return','RETURN','returned','—','Return','—'],
 ['Unassigned','ON HOLD - TBC method','—','—','—','—'],
];
s.getRangeByIndexes(4,0,rows.length,6).values=rows;
s.getRange('A5:F5').format.fill='#243052';
s.getRange('A5:F5').format.font={bold:true,color:'#FFFFFF',size:11};
s.getRange('A5:F5').format.rowHeight=35;
s.getRange('A6:F17').format.wrapText=true;
s.getRange('A6:F17').format.verticalAlignment='center';
s.getRange('A6:F17').format.rowHeight=72;
s.getRange('A6:A17').format.font={bold:true,color:'#243052',size:11};
for(let i=6;i<=17;i++) if(i%2===0)s.getRange(`A${i}:F${i}`).format.fill='#F2F6FA';
s.getRange('A10:F10').format.fill='#E6F4F5';
s.getRange('A11:F11').format.fill='#E9F4E9';
s.getRange('A12:F12').format.fill='#FFF1E8';

s.getRange('A19:F19').format.fill='#243052';
s.getRange('A19').values=[['Only items to review']];
s.getRange('A19').format.font={bold:true,color:'#FFFFFF',size:12};
s.getRange('A19:F19').format.rowHeight=32;
const issues=[
 ['1','OW literal “Cancelled”','155 OW orders use the word Cancelled; only 74 have the TO BE CANCELLED method. The text is missing from the shared-status mapper.','Check whether OW Status = Cancelled must always set shared Cancelled.','',''],
 ['2','Amazon exception values','7 DELIVERY_ATTEMPTED + 1 REJECTED + 1 AWAITING_CUSTOMER_PICKUP + 2 RETURNED_TO_SELLER orders also have OW Completed. Unmapped carrier values may fall back to shared Delivered.','Assign these carrier values to existing work queues.','',''],
 ['3','OptimoRoute cancelled','The provider defines cancelled, but the shared-status mapper has no rule for it.','Confirm whether provider cancellation should override OW.','',''],
];
s.getRange('A20:F22').values=issues;
s.getRange('A20:F22').format.wrapText=true;
s.getRange('A20:F22').format.verticalAlignment='center';
s.getRange('A20:F22').format.rowHeight=82;
s.getRange('A20:F22').format.fill='#FFF0E8';
s.getRange('A20:B22').format.font={bold:true,color:'#243052',size:10};
s.getRange('A24').values=[['Source: 2 Nov 2026 read-only OW workbook export, current code and saved database snapshot. Platform meanings checked against XDP, Palletways, OptimoRoute and Amazon official documentation.']];
s.getRange('A24:F24').format.fill='#E8F1F6';
s.getRange('A24:F24').format.rowHeight=28;
for(const [col,width] of Object.entries({A:25,B:38,C:46,D:48,E:40,F:40}))s.getRange(`${col}:${col}`).format.columnWidth=width;
const preview=await wb.render({sheetName:'Status map',range:'A1:F17',scale:1,format:'png'});
await fs.writeFile('C:/atlas/docs/guidance-review/simple_english_preview.png',Buffer.from(await preview.arrayBuffer()));
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save('C:/atlas/docs/guidance-review/Delivery_Desk_Status_Mapping_Review_EN_2026-11-02.xlsx');
console.log('saved one-sheet matrix');
