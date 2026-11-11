const fs = require('fs');
const vm = require('vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync('src/dashboard-home.js', 'utf8');
const helpers = source.slice(source.indexOf('  let resizeDrag'), source.indexOf('  const used'));
const placement = source.slice(source.indexOf('  function widgetPositions'), source.indexOf('  function emptySlotsMarkup'));
const swap = source.slice(source.indexOf('  function swappedWidgetPositions'), source.indexOf('  function previewWidgetSwap'));

vm.runInNewContext(`
  let sizes = {}, order = [], editing = true;
  const widgetType = key => key.replace(/--[123]x[123]$/, '');
  ${helpers} ${placement} ${swap}
  const keys = ['large', 'left', 'middle', 'right'];
  for (const smallHeight of [1, 2]) {
    const largeHeight = 3 - smallHeight;
    sizes = {large: '3x' + largeHeight, left:'1x' + smallHeight, middle:'1x' + smallHeight, right:'1x' + smallHeight};
    const above = {large:{row:gridRow(1,largeHeight),column:'1 / span 3'}};
    const below = {large:{row:gridRow(smallHeight+1,largeHeight),column:'1 / span 3'}};
    ['left','middle','right'].forEach((key,i) => {
      above[key] = {row:gridRow(largeHeight+1,smallHeight),column:String(i+1)};
      below[key] = {row:gridRow(1,smallHeight),column:String(i+1)};
    });
    for (const target of ['left','middle','right']) {
      for (const reverse of [false,true]) {
        for (const [initial,expected] of [[above,below],[below,above]]) {
          const result = swappedWidgetPositions(keys,initial,reverse?target:'large',reverse?'large':target);
          assert.ok(result, 'A valid layout must exist for a full-width widget and three smaller widgets');
          assert.deepEqual(JSON.parse(JSON.stringify(result)),JSON.parse(JSON.stringify(expected)));
          const occupied = new Set();
          keys.forEach(key => widgetCells(key,(parseInt(result[key].row)-1)*3+parseInt(result[key].column)-1).forEach(cell=>{
            assert.ok(cell>=0 && cell<9 && !occupied.has(cell));occupied.add(cell);
          }));
          assert.equal(occupied.size,9);
        }
      }
    }
  }
`, { assert, document:{addEventListener(){},querySelector(){return null;}}, window:{addEventListener(){}} });
console.log('PASS: full-width swaps in both directions preserve all small-widget columns, fill all nine cells and never overlap');
