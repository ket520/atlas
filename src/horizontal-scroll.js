/* Consistent horizontal input for existing and dynamically rendered scroll areas. */
(() => {
  'use strict';
  let pointedElement = null;
  const editable = element => element?.closest('input, textarea, select, [contenteditable]:not([contenteditable="false"]), [role="slider"], [role="spinbutton"]');

  function scrollerFrom(element, amount) {
    for (let current = element instanceof Element ? element : null; current; current = current.parentElement) {
      const range = current.scrollWidth - current.clientWidth;
      if (range <= 1) continue;
      const style = getComputedStyle(current);
      if (!['auto', 'scroll', 'overlay'].includes(style.overflowX)) continue;
      const minimum = style.direction === 'rtl' ? -range : 0;
      const maximum = style.direction === 'rtl' ? 0 : range;
      if (!amount || (amount < 0 ? current.scrollLeft > minimum + .5 : current.scrollLeft < maximum - .5)) return current;
    }
    return null;
  }

  document.addEventListener('pointermove', event => { pointedElement = event.target; }, {passive: true});
  document.addEventListener('pointerleave', () => { pointedElement = null; });

  document.addEventListener('pointerdown', event => {
    if (event.button !== 0 || editable(event.target) || event.target.closest('button, a, [role="button"], [tabindex]')) return;
    const scroller = scrollerFrom(event.target, 0);
    if (!scroller) return;
    if (!scroller.hasAttribute('tabindex')) scroller.tabIndex = 0;
    scroller.focus({preventScroll: true});
  });

  document.addEventListener('keydown', event => {
    if (event.defaultPrevented || event.isComposing || event.altKey || event.ctrlKey || event.metaKey
      || !['ArrowLeft', 'ArrowRight'].includes(event.key) || editable(event.target)
      || event.target.closest('[role="tablist"], [role="listbox"], [role="tree"]')) return;
    const amount = event.key === 'ArrowRight' ? 80 : -80;
    const target = event.target === document.body || event.target === document.documentElement
      ? (pointedElement?.isConnected ? pointedElement : event.target) : event.target;
    const scroller = scrollerFrom(target, amount);
    if (!scroller) return;
    event.preventDefault();
    scroller.scrollLeft += amount;
  });

  document.addEventListener('wheel', event => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey) return;
    const amount = event.shiftKey ? (event.deltaX || event.deltaY)
      : Math.abs(event.deltaX) > Math.abs(event.deltaY) ? event.deltaX : 0;
    if (!amount) return;
    const scroller = scrollerFrom(event.target, amount);
    if (!scroller) return;
    const scale = event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? scroller.clientWidth : 1;
    event.preventDefault();
    scroller.scrollLeft += amount * scale;
  }, {passive: false});
})();
