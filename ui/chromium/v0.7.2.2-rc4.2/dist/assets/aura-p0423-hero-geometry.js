/* AURA P0.4.2.3 HERO GEOMETRY RESTORE */
(() => {
  'use strict';
  if (window.__AURA_P0423_GEOMETRY__) return;
  window.__AURA_P0423_GEOMETRY__ = true;

  const hero = document.querySelector('.hero');
  const stage = document.getElementById('stage');
  const workspace = hero?.closest('.workspace') || hero?.parentElement;

  if (!hero || !stage || !workspace) return;

  let lastHeight = 0;

  function measureTargetHeight() {
    const wr = workspace.getBoundingClientRect();
    let h = Number(wr.height || 0);

    // Fallback if the workspace is itself temporarily unresolved.
    if (h < 240) {
      const top = Number(wr.top || hero.getBoundingClientRect().top || 0);
      h = Math.max(360, window.innerHeight - top - 96);
    }

    // Guard against accidental fullscreen overflow.
    const viewportCap = Math.max(360, window.innerHeight - 120);
    return Math.max(360, Math.min(h, viewportCap));
  }

  function anchor() {
    const h = Math.round(measureTargetHeight());
    if (Math.abs(h - lastHeight) < 2) return;
    lastHeight = h;

    hero.style.setProperty('height', `${h}px`, 'important');
    hero.style.setProperty('min-height', `${h}px`, 'important');
    hero.style.setProperty('max-height', `${h}px`, 'important');
    hero.style.setProperty('position', 'relative', 'important');
    hero.style.setProperty('overflow', 'hidden', 'important');

    // P0.4.3 temporarily owns #stage during neural construction.
    // Keep computing HERO geometry, but do not reclaim the stage until
    // the cinematic transition has completed.
    if (!document.documentElement.classList.contains('aura-p043-running')) {
      stage.style.setProperty('position', 'absolute', 'important');
      stage.style.setProperty('inset', '0', 'important');
      stage.style.setProperty('width', '100%', 'important');
      stage.style.setProperty('height', '100%', 'important');
      stage.style.setProperty('min-height', '100%', 'important');

      // Let any ResizeObserver owned by Final Orb run after geometry is settled.
      window.dispatchEvent(new Event('resize'));
    }
  }

  anchor();
  requestAnimationFrame(anchor);
  setTimeout(anchor, 60);
  setTimeout(anchor, 250);

  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(anchor).observe(workspace);
  } else {
    window.addEventListener('resize', anchor, {passive:true});
  }
})();
