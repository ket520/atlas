const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('src/dashboard-home.js', 'utf8');
const sizing = source.slice(
  source.indexOf('  const sizeColumns'),
  source.indexOf('  const widgetSize ='),
);
const begin = source.slice(
  source.indexOf('  function beginPicker'),
  source.indexOf('  function finishPicker'),
);
const move = source.slice(
  source.indexOf('  function movePicker'),
  source.indexOf('  function beginPicker'),
);
const sentinel = new Error('Preview markup reached');
const context = {
  assert,
  sentinel,
  document: {
    getElementById: () => ({}),
    createElement: () => {
      throw sentinel;
    },
  },
  AtlasViewport: {
    rect: () => ({
      width: 920,
      height: 620,
    }),
  },
  getComputedStyle: () => ({
    columnGap: '10',
    rowGap: '10',
  }),
};
vm.runInNewContext(
  `
${sizing}
const layoutRows = () => 3;
let order = [], sizes = {}, pickerDrag;
${begin}
for (const size of ['1x1','2x1','3x1','1x2','2x2','3x2','1x3','2x3','3x3']) {
  assert.throws(() => beginPicker({size, key: 'test'}, {}), error => error === sentinel);
}
const overlaps = (a, length, b, otherLength) => a < b + otherLength && b < a + length;
const columns = () => 1; const units = () => 1;
let affected = false;
const card = {style: {gridColumn: '1', gridRow: '1'}, dataset: {dashWidget: 'test'}, classList: {toggle: (_, value) => {affected = value;}}};
pickerDrag = {size: '2x2', width: 200, height: 200, ghost: {style: {}},
  slots: [{left: 0, top: 0, right: 200, bottom: 200, row: 1, column: 1}],
  slotElements: [{classList: {toggle() {}}}], grid: {querySelectorAll: () => [card]}};
${move}
movePicker(94,94);
assert.equal(pickerDrag.ready,0);
assert.equal(affected,true);
`,
  context,
);
console.log('PASS: gallery pickup geometry for all nine sizes and drop-target highlighting');

const swapPreview = source.slice(
  source.indexOf('  function previewWidgetSwap'),
  source.indexOf('  function finishWidgetDrag'),
);
vm.runInNewContext(
  `
  let updates = 0, solves = 0;
  const widgetDrag = {
    key: 'a', original: ['a','b'], preview: ['a','b'], originalPositions: {a:{row:'1',column:'1'},b:{row:'1',column:'2'}},
    slots: [
      {left:0,right:100,top:0,bottom:100,width:100,height:100},
      {left:100,right:200,top:0,bottom:100,width:100,height:100}
    ],
    ghost: {}, grid: {}, card: {classList:{toggle(){}}},
    targetIndicator: {style:{}}, metrics: {cellWidth:100,cellHeight:100,gapX:0,gapY:0},
    slotElements: [{classList:{toggle(){},remove(){}}},{classList:{toggle(){},remove(){}}}]
  };
  const AtlasViewport = {rect: () => ({left:100,right:200,top:0,bottom:100,width:100,height:100})};
  const swappedWidgetPositions = () => { solves++; return widgetDrag.originalPositions; };
  const columns = () => 1, units = () => 2;
  const positionWidgets = () => { updates++; };
  ${swapPreview}
  previewWidgetSwap();
  for(let i=0;i<100;i++) previewWidgetSwap();
  assert.equal(solves,1);
  assert.equal(updates,1);
  assert.equal(widgetDrag.targetIndicator.style.width,'100px');
  assert.equal(widgetDrag.targetIndicator.style.height,'200px');
  assert.equal(widgetDrag.targetIndicator.hidden,false);
`,
  {
    assert,
  },
);
console.log('PASS: unchanged drop targets do not restart layout animations or repeat packing');
