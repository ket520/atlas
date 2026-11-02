import fs from 'node:fs/promises';
import {Workbook,SpreadsheetFile} from 'file:///C:/Users/NITRO%20V15/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool/dist/artifact_tool.mjs';

const md=await fs.readFile('C:/atlas/docs/guidance-review/Cross_platform_status_crosswalk.md','utf8');
function tableAfter(heading){
 const tail=md.slice(md.indexOf(heading));
 const lines=tail.split(/\r?\n/).slice(1);
 const rows=[];
 for(const line of lines){
  if(!line.startsWith('|')){if(rows.length)break;continue;}
  if(/^\|\s*[-:]+/.test(line))continue;
  rows.push(line.split('|').slice(1,-1).map(x=>x.trim().replaceAll('**','').replaceAll('`','')));
 }
 return rows;
}
const wb=Workbook.create();
const datasets=[
 ['Unified phases',tableAfter('## 先按 Delivery Desk 现有业务含义读'),[22,70,70]],
 ['Platform crosswalk',tableAfter('## 各平台的原意和现有映射'),[42,92,36,85,25]],
 ['Action list',[
  ['Priority','Review outcome','Reason / evidence','Next decision'],
  ['1','Keep established broad status buckets','Scheduled covers pre-last-mile work; Failed covers operational exceptions; raw carrier labels remain visible','Do not change these merely because platform wording differs'],
  ['2','Keep OptimoRoute scheduled → Out for Delivery','User-confirmed own-van rule: OptimoRoute same-day planning means dispatch that day','Show raw scheduled separately from driver physically on_route'],
  ['3','Keep XDP raw status separate from overall Awaiting for now','Guidance note and tests explicitly specify separate XDP source filter; 768 current OW orders have XDP DELIVERED','Only change overall status after a business decision about XDP verification'],
  ['4','Review OW Cancelled and OptimoRoute cancelled','155 OW orders have literal Cancelled; only 74 use TO BE CANCELLED method. OptimoRoute cancelled is absent from mapper','Confirm cancellation priority, then add explicit mappings if intended'],
  ['5','Review unmapped Amazon values and OW fallback label','7 DELIVERY_ATTEMPTED, 1 REJECTED, 1 AWAITING_CUSTOMER_PICKUP, 2 RETURNED_TO_SELLER matched OW orders all have OW Completed; fallback may show Delivered','Assign each to an existing operational bucket and label OW fallback as proxy'],
 ],[13,58,95,80]],
];
for(const [name,rows,widths] of datasets){
 const s=wb.worksheets.add(name);s.showGridLines=false;s.freezePanes.freezeRows(1);
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).values=rows;
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.wrapText=true;
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.verticalAlignment='center';
 s.getRangeByIndexes(0,0,rows.length,rows[0].length).format.rowHeight=name==='Platform crosswalk'?72:65;
 s.getRangeByIndexes(0,0,1,rows[0].length).format.fill='#243052';
 s.getRangeByIndexes(0,0,1,rows[0].length).format.font={bold:true,color:'#FFFFFF',size:11};
 s.getRangeByIndexes(0,0,1,rows[0].length).format.rowHeight=30;
 const abc='ABCDEFGHIJKLMNOPQRSTUVWXYZ';widths.forEach((w,i)=>s.getRange(`${abc[i]}:${abc[i]}`).format.columnWidth=w);
 if(name==='Platform crosswalk'){
   for(let i=1;i<rows.length;i++) if(rows[i][4].includes('明确')||rows[i][4].includes('高风险')||rows[i][4].includes('漏映射')) s.getRangeByIndexes(i,0,1,rows[0].length).format.fill='#FFF0E8';
 }
}
for(const [sheetName,range] of [['Unified phases','A1:C8'],['Platform crosswalk','A1:E7'],['Action list','A1:D6']]){
 const b=await wb.render({sheetName,range,scale:1,format:'png'});
 await fs.writeFile(`C:/atlas/docs/guidance-review/crosswalk_preview_${sheetName.replaceAll(' ','_')}.png`,Buffer.from(await b.arrayBuffer()));
}
const out=await SpreadsheetFile.exportXlsx(wb);
await out.save('C:/atlas/docs/guidance-review/Cross_platform_status_crosswalk_2026-11-02.xlsx');
console.log(datasets.map(([n,r])=>`${n}: ${r.length}`).join(', '));
