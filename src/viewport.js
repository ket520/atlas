/* Desktop app zoom, with one coordinate space for pointer-driven interactions. */
const AtlasViewport = (() => {
  const root = document.documentElement;
  let scale = 1;
  function update() {
    const enabled = innerWidth > 760 && root.dataset.atlasAutoScale !== 'off';
    scale = enabled ? Math.min(1, innerWidth / 1920, innerHeight / 1080) : 1;
    root.classList.toggle('atlas-scaled', scale < 1);
    if (scale < 1) {
      root.style.zoom = String(scale);
      root.style.width = `${innerWidth / scale}px`;
      root.style.height = `${innerHeight / scale}px`;
      root.style.setProperty('--atlas-viewport-width', `${innerWidth / scale}px`);
      root.style.setProperty('--atlas-viewport-height', `${innerHeight / scale}px`);
    } else {
      ['zoom', 'width', 'height', '--atlas-viewport-width', '--atlas-viewport-height'].forEach(key => root.style.removeProperty(key));
    }
  }
  function rect(element) {
    if (!element) return undefined;
    const value = element.getBoundingClientRect();
    return {x: value.x / scale, y: value.y / scale, left: value.left / scale,
      top: value.top / scale, right: value.right / scale, bottom: value.bottom / scale,
      width: value.width / scale, height: value.height / scale};
  }
  update();
  window.addEventListener('resize', update);
  return {rect, x: event => event.clientX / scale, y: event => event.clientY / scale,
    get width() { return innerWidth / scale; }, get height() { return innerHeight / scale; },
    get scale() { return scale; }};
})();
