import fs from 'node:fs/promises';
import { Workbook, SpreadsheetFile } from 'file:///C:/Users/NITRO%20V15/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const wb = Workbook.create();
const review = wb.worksheets.add('Review');
const rules = wb.worksheets.add('Rule evidence');
const ow = wb.worksheets.add('OW snapshot');
for (const s of [review, rules, ow]) { s.showGridLines = false; s.freezePanes.freezeRows(2); }

const findings = [
  ['Priority', 'Finding', 'Code / OW evidence', 'Guidance implication', 'Action'],
  ['High', 'OW live values are text, while Guidance mainly lists legacy letter codes.', 'Sales Activity!J; delivery_data.py:863-888', 'Show actual text values separately from the code mapping.', 'Confirm intended meaning of each current OW text value with supervisor/OW owner.'],
  ['High', 'Cancelled in OW Status currently falls through to Unscheduled.', 'OW: Cancelled 187 rows; ow_status_name has X but no CANCELLED', 'Do not state that OW Status=Cancelled is mapped to Cancelled.', 'Decide whether code should map CANCELLED; this workbook does not change code.'],
  ['High', 'XDP and STOPSTART labels in Guidance are reference labels, not all applied overall statuses.', 'delivery_status; xdp_sheet.apply_status; src/admin.js:529-552', 'Split raw carrier label from displayed overall status.', 'Clarify legend and source priority in Guidance later.'],
  ['Medium', 'Routine live colour override applies only to Own van.', 'delivery_data.py:140-171', 'Do not extend this priority to Self Delivery or LOCAL MULTIDROP.', 'Verify whether this scope is intended.'],
  ['Medium', 'OptimoRoute scheduled maps to Out for Delivery.', 'delivery_data.py:100-110', 'The word scheduled has source-specific meaning.', 'Retain explicit source and raw value in every row.'],
  ['Medium', 'Amazon no Tracking No is Unscheduled before OW status; XDP defaults to Awaiting.', 'delivery_data.py:87-97', 'These are method-specific precedence rules.', 'Use the Rule evidence tab for exact conditions.'],
  ['Low', 'Courier Issues and STOPSTART plans give context but normally do not replace overall status.', 'docs/CODE_MAP.md; delivery_data.py sync flow', 'Do not imply every source label determines the filter status.', 'Confirm with a few real order examples.'],
];

const ruleRows = [
  ['Carrier / scope','Source field','Raw value / condition','Overall status','Priority / condition','Evidence','Review note'],
  ['All','OW Sales Activity J','W,K,H,I,A,U,Y,UNSCHEDULED, unknown/blank','Unscheduled','Fallback','delivery_data.py:863-888','Unknown includes current OW text values not explicitly mapped.'],
  ['All','OW Sales Activity J','P,S,SCHEDULED','Scheduled','Fallback','delivery_data.py:863-888',''],
  ['All','OW Sales Activity J','C,DELIVERED,COMPLETE,COMPLETED','Delivered','Fallback','delivery_data.py:863-888','OW current Completed is covered after uppercase normalization.'],
  ['All','OW Sales Activity J','X','Cancelled','Fallback','delivery_data.py:863-888','OW current Cancelled text is not covered.'],
  ['All','OW Sales Activity J','FAILED DELIVERY,FAILED','Failed','Fallback','delivery_data.py:863-888',''],
  ['All','OW Sales Activity J','OUT FOR DELIVERY / REJECTED / RETURN','Matching status','Fallback','delivery_data.py:863-888','Three separate explicit mappings.'],
  ['Any','OW Sales Activity T','TO BE CANCELLED','Cancelled','Method override','delivery_data.py:87-97','Overrides OW J except XDP check is evaluated first.'],
  ['Any','OW Sales Activity T','ON HOLD - TBC','Unassigned','Method override','delivery_data.py:87-97',''],
  ['Own van','Routine Dashboard - Live A fill','#FFFF00 / #FFFFFF with order / #FFC000','Failed / Scheduled','Highest for Own van','routine_live.py:7-9; delivery_data.py:140-171','White requires order number and valid section.'],
  ['Own van, Self Delivery, LOCAL MULTIDROP','OptimoRoute status','unscheduled','Unscheduled','Provider when matched','delivery_data.py:100-110','Routine live override only Own van.'],
  ['Own van, Self Delivery, LOCAL MULTIDROP','OptimoRoute status','scheduled,on_route,servicing','Out for Delivery','Provider when matched','delivery_data.py:100-110','Provider scheduled differs from overall Scheduled.'],
  ['Own van, Self Delivery, LOCAL MULTIDROP','OptimoRoute status','success / failed / rejected / returned','Delivered / Failed / Rejected / Return','Provider when matched','delivery_data.py:100-110',''],
  ['Amazon Shipping','OW Tracking No S','blank','Unscheduled','Before OW fallback','delivery_data.py:87-97',''],
  ['Amazon Shipping','Amazon Shipping G','IN_TRANSIT,READY_FOR_RECEIVE','Scheduled','Matched provider status','delivery_data.py:174-183',''],
  ['Amazon Shipping','Amazon Shipping G','OUT_FOR_DELIVERY / DELIVERED','Out for Delivery / Delivered','Matched provider status','delivery_data.py:174-183',''],
  ['Amazon Shipping','Amazon Shipping G','LOST,UNDELIVERABLE','Failed','Matched provider status','delivery_data.py:174-183','Not overall Lost.'],
  ['Palletways','API derived status','In Transit,Scheduled,Unscheduled','Scheduled / Unscheduled','Provider when matched','delivery_data.py:222-235',''],
  ['Palletways','API derived status','Out for Delivery,Delivered','Out for Delivery / Delivered','Provider when matched','delivery_data.py:222-235',''],
  ['Palletways','API derived status','Failed,Damaged,Refused,Lost,Return','Failed / Failed / Rejected / Lost / Return','Provider when matched','delivery_data.py:222-235',''],
  ['XDP','Delivery method T','XDP variants','Awaiting','Initial status before OW','delivery_data.py:87-90','Exception: XDP I failures below.'],
  ['XDP','XDP I','DAMAGE,DELETE,NOT RECEIVED','Failed','Overrides Awaiting','xdp_sheet.py:11-23','Other XDP labels stay reference only; often overall Awaiting.'],
  ['Stopstart','STOPSTART sheet','Expected Today / past expected / tracking unavailable','OW fallback','Context only','docs/CODE_MAP.md; delivery_data.py','Labels in Guidance are not overall-status mappings.'],
  ['Yodel, UK Next Day, Wayfair','OW Sales Activity J','OW codes/text','OW mapped status','Fallback','delivery_data.py:87-97; src/admin.js:540-552','No provider status mapper found in current code.'],
  ['All','Courier Issues','Issue and follow-up','No replacement','Context only','docs/CODE_MAP.md',''],
];

const snapshot = [
  ['Source','Observation','Count (product rows)','Meaning / limitation'],
  ['OW Sales Activity','Rows with Order no',23290,'Product rows, not unique orders; exported read-only on 2026-11-02.'],
  ['OW Status J','Completed',18923,'Code maps to Delivered, unless a higher priority source overrides.'],
  ['OW Status J','Invoice waiting to be printed',3663,'No explicit code mapping; falls back to Unscheduled.'],
  ['OW Status J','Awaiting despatch',464,'No explicit code mapping; falls back to Unscheduled.'],
  ['OW Status J','Cancelled',187,'No explicit code mapping; falls back to Unscheduled unless method override.'],
  ['OW Status J','Awaiting conversion',36,'No explicit code mapping; falls back to Unscheduled.'],
  ['OW Status J','Partially despatched',10,'No explicit code mapping; falls back to Unscheduled.'],
  ['OW Status J','Paused',7,'No explicit code mapping; falls back to Unscheduled.'],
  ['OW Delivery method T','TO BE CANCELLED',181,'Method override maps Cancelled; counts do not prove overlap with OW Status=Cancelled.'],
  ['OW Delivery method T','ON HOLD - TBC',31,'Method override maps Unassigned.'],
  ['OW workbook','Google Sheet URL','', 'https://docs.google.com/spreadsheets/d/1F2DnKdPEm-LdxM1Ag6hTcvP7a8glhnESl9m7-UlvNcs/edit?gid=0#gid=0'],
];

function put(sheet, rows, widths) {
  sheet.getRangeByIndexes(0,0,rows.length,rows[0].length).values=rows;
  const letters='ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  for(let i=0;i<widths.length;i++) sheet.getRange(`${letters[i]}:${letters[i]}`).format.columnWidth=widths[i];
  sheet.getRangeByIndexes(0,0,1,rows[0].length).format.fill='#243052';
  sheet.getRangeByIndexes(0,0,1,rows[0].length).format.font={bold:true,color:'#FFFFFF',size:11};
  sheet.getRangeByIndexes(0,0,rows.length,rows[0].length).format.wrapText=true;
  sheet.getRangeByIndexes(0,0,rows.length,rows[0].length).format.verticalAlignment='center';
  sheet.getRangeByIndexes(0,0,rows.length,rows[0].length).format.rowHeight=34;
  sheet.getRangeByIndexes(0,0,1,rows[0].length).format.rowHeight=30;
}
put(review,findings,[13,66,52,60,57]);
put(rules,ruleRows,[36,31,48,35,34,40,58]);
put(ow,snapshot,[27,39,24,83]);
review.getRange('A2:E4').format.fill='#FFF0E8';
review.getRange('A5:E8').format.fill='#FFF8E5';
ow.getRange('A5:D9').format.fill='#FFF0E8';
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save('C:/atlas/docs/guidance-review/Guidance_status_source_audit_2026-11-02.xlsx');
console.log('saved');
