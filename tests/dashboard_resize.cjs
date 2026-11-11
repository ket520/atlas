const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('src/dashboard-home.js', 'utf8');
const helpers = source.slice(source.indexOf('  let resizeDrag'), source.indexOf('  const used'));
const occupiedCells = source.slice(
  source.indexOf('  function occupiedWidgetCells'),
  source.indexOf('  function pickUpWidget'),
);
const swap = source.slice(
  source.indexOf('  function swappedWidgetPositions'),
  source.indexOf('  function previewWidgetSwap'),
);
const placement = source.slice(
  source.indexOf('  function widgetPositions'),
  source.indexOf('  function emptySlotsMarkup'),
);
vm.runInNewContext(
  `let sizes = {}, order = [], editing = true; const widgetType = key => key.replace(/--[123]x[123]$/, ''); let saves = 0; const save = () => saves++; const refreshPicker = () => {}; ${helpers} ${placement} ${swap} ${occupiedCells}
for (const type of ['collection-generator', 'order-identifier', 'order-flow-tracker']) {
 const key = type + '--3x3';
 order = [key]; sizes = {[key]: '2x2'};
 assert.equal(widgetSize(key), '1x1');
 assert.equal(resizeControls(key), '');
 assert.equal(growthTarget(key, 'right'), null);
 const before = JSON.stringify(sizes), saveCount = saves;
 applyWidgetSize(key, {row: 1, column: 1, width: 3, height: 3});
 assert.equal(JSON.stringify(sizes), before);
 assert.equal(saves, saveCount);
}
sizes = {};
order = ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h', 'i'];
const checkLayout = () => {
 const positions = widgetPositions(), occupied = new Set();
 assert.equal(layoutRows(),3);
 assert.equal(Object.keys(positions).length, order.length);
 for(const key of order) {
  const pos = positions[key], slot = (parseInt(pos.row)-1)*3 + parseInt(pos.column)-1;
  assert.ok(slot%3 + columns(key) <= 3); assert.ok(Math.floor(slot/3)+units(key)<=3);
  for(const cell of widgetCells(key,slot)) {assert.ok(!occupied.has(cell)); occupied.add(cell);}
 }
};
for (const [direction, slot, expected, targetSlot] of [
 ['top',4,'1x2',1], ['bottom',4,'1x2',4], ['left',4,'2x1',3], ['right',4,'2x1',4]
]) {
 order=['a','b','c','d','e','f','g','h','i']; sizes={'a-slot':slot}; normalizeLayout();
 resizeWidget('a',direction); assert.equal(widgetSize('a'),expected); assert.equal(sizes['a-slot'],targetSlot); checkLayout();
 assert.ok(order.length < 9);
}
order=['a']; sizes={'a-slot':4}; normalizeLayout();
for(const direction of ['left','right','top','bottom']) {resizeWidget('a',direction); checkLayout();}
assert.equal(widgetSize('a'),'3x3'); assert.equal(sizes['a-slot'],0);
for(const direction of ['left','right','top','bottom']) assert.equal(growthTarget('a',direction),null);
const savedCount=saves; resizeWidget('a','right'); assert.equal(saves,savedCount);
assert.ok(resizeControls('a').includes('data-resize-handle'));
assert.ok(!resizeControls('a').includes('data-resize-toggle'));
const small=snappedRect(2,2,-1000,-1000,1,1,100,100); assert.equal(small.width,1); assert.equal(small.height,1);
const large=snappedRect(1,1,1000,1000,2,2,100,100); assert.equal(large.width,2); assert.equal(large.height,2);
editing=false; assert.equal(resizeControls('a'),''); resizeWidget('a','top'); assert.equal(saves,savedCount); editing=true;
sizes=JSON.parse(JSON.stringify(sizes)); checkLayout(); assert.equal(widgetSize('a'),'3x3');
for (const size of widgetSizes) {
  order=['a']; sizes={a:size,'a-slot':0}; normalizeLayout(); checkLayout();
  assert.equal(columns('a'),Number(size.split('x')[0]));
  assert.equal(units('a'),Number(size.split('x')[1]));
}
order=['a']; sizes={a:'2x2','a-slot':0};
resizeWidget('a','top',-1); assert.equal(widgetSize('a'),'2x1'); assert.equal(sizes['a-slot'],3);
resizeWidget('a','left',-1); assert.equal(widgetSize('a'),'1x1'); assert.equal(sizes['a-slot'],4);
const minimum=saves; resizeWidget('a','right',-1); assert.equal(saves,minimum); checkLayout();
order=['large','small','neighbor']; sizes={large:'1x2', 'large-slot':0, 'small-slot':1, 'neighbor-slot':4};
const swapped=swappedWidgetPositions(order,widgetPositions(),'large','small');
assert.ok(swapped); assert.equal(parseInt(swapped.large.column),2); assert.equal(parseInt(swapped.small.column),1);
const cells=new Set();
for(const key of order) {
 const pos=swapped[key]; const slot=(parseInt(pos.row)-1)*3+parseInt(pos.column)-1;
 for(const cell of widgetCells(key,slot)) {assert.ok(!cells.has(cell)); cells.add(cell);}
}
order=['a','b']; sizes={}; const simple=swappedWidgetPositions(order,widgetPositions(),'a','b');
assert.equal(parseInt(simple.a.column),2); assert.equal(parseInt(simple.b.column),1);
for (const size of widgetSizes) {
 const [width,height]=size.split('x').map(Number);
 for(let column=1;column<=4-width;column++) for(let row=1;row<=4-height;row++) {
  for(const edge of ['n','ne','e','se','s','sw','w','nw']) {
   for(const dx of [-1000,-100,0,100,1000]) for(const dy of [-1000,0,1000]) {
    const rect=snappedRect(width,height,dx,dy,column,row,100,100,edge);
    assert.ok(rect.column>=1 && rect.row>=1 && rect.width>=1 && rect.height>=1);
    assert.ok(rect.column+rect.width<=4 && rect.row+rect.height<=4);
    if(!edge.includes('w')) assert.equal(rect.column,column);
    if(!edge.includes('e')) assert.equal(rect.column+rect.width,column+width);
    if(!edge.includes('n')) assert.equal(rect.row,row);
    if(!edge.includes('s')) assert.equal(rect.row+rect.height,row+height);
   }
  }
 }
}
order=['identifier','charge','depot'];
sizes={identifier:'1x1','identifier-slot':3,charge:'1x3','charge-slot':2,depot:'1x2','depot-slot':1};
const mixed=swappedWidgetPositions(order,widgetPositions(),'identifier','charge');
assert.ok(mixed);
assert.equal(mixed.charge.row,'1 / span 3');
assert.equal(parseInt(mixed.charge.column),1);
assert.equal(parseInt(mixed.identifier.column),3);
assert.equal(mixed.identifier.row,'2');
assert.equal(mixed.depot.row,'1 / span 2');
const reverse=swappedWidgetPositions(order,widgetPositions(),'charge','identifier');
assert.ok(reverse);
assert.equal(reverse.charge.row,'1 / span 3');
assert.equal(parseInt(reverse.charge.column),1);
assert.equal(reverse.identifier.row,'2');
order=['moving','other']; sizes={moving:'1x2','moving-slot':0,'other-slot':1};
const occupied=occupiedWidgetCells(order,widgetPositions(),'moving');
assert.ok(!occupied.has(0)); assert.ok(!occupied.has(3)); assert.ok(occupied.has(1));
assert.ok(widgetCells('moving',3).every(cell=>!occupied.has(cell)));
order=['moving','other']; sizes={moving:'1x2','moving-slot':3,'other-slot':1};
assert.ok(widgetCells('moving',0).every(cell=>!occupiedWidgetCells(order,widgetPositions(),'moving').has(cell)));
console.log('PASS: all nine sizes and eight directions preserve opposite edges and grid bounds');
console.log('PASS: four growth directions, fixed grid boundaries, collisions, edit mode, disabled controls and persistence');
`,
  {
    assert,
    console,
    window: {
      addEventListener() {},
    },
    document: {
      addEventListener() {},
      querySelector() {
        return null;
      },
    },
  },
);

const tableColumns = source.slice(
  source.indexOf('  function widgetTableColumns'),
  source.indexOf('  function expandedTableMarkup'),
);
vm.runInNewContext(
  `
  let width = 1;
  const columns = () => width;
  ${tableColumns}
  const stock = {key: 'out-of-stock'};
  assert.equal(widgetTableColumns(stock, 'a').map(field => field.key).join(','), 'order,cust,orderDate');
  width = 2;
  assert.ok(widgetTableColumns(stock, 'a').some(field => field.key === 'bookingStatus'));
  assert.ok(!widgetTableColumns(stock, 'a').some(field => field.key === 'skuItems'));
  width = 3;
  assert.ok(widgetTableColumns(stock, 'a').some(field => field.key === 'skuItems'));
  assert.ok(widgetTableColumns(stock, 'a').some(field => field.key === 'specialInstructions'));
  assert.ok(widgetTableColumns({key: 'palletways-next-day'}, 'a').some(field => field.key === 'palletwaysSheetStatus'));
  console.log('PASS: size-based fields and widget-specific information');
`,
  {
    assert,
  },
);
