/* AURA P0.4.3.3 TRUE BRAND ORB REFERENCE */
(() => {
  'use strict';

  if (window.__AURA_P0433_TRUE_BRAND__) return;
  window.__AURA_P0433_TRUE_BRAND__ = true;

  const STAGE_URL = '/assets/aura-brand-orb-reference-stage-p0433.png?v=p0433-20260816';
  const ICON_URL = '/assets/aura-brand-icon-reference-p0433.png?v=p0433-20260816';

  // This pass deliberately overrides the wrong interpreted identity.
  window.__AURA_P0432_SVG_IDENTITY__ = 'reference-lock';

  const clamp = (v, a=0, b=1) => Math.max(a, Math.min(b, v));

  function getStage() {
    return document.getElementById('stage');
  }

  function getBuild() {
    const card = document.getElementById('bootCard');
    if (card?.classList?.contains('hidden') ||
        document.documentElement.classList.contains('aura-p043-complete')) {
      return 1;
    }
    const el = document.getElementById('bootPercent');
    const n = parseFloat(String(el?.textContent || '100').replace(',', '.'));
    return Number.isFinite(n) ? clamp(n / 100) : 1;
  }

  function getPcm() {
    const el = document.getElementById('pcmValue');
    const n = parseFloat(String(el?.textContent || '0').replace(',', '.'));
    return Number.isFinite(n) ? clamp(n) : 0;
  }

  function getState() {
    return String(document.body?.dataset?.state || 'IDLE').toUpperCase();
  }

  function removeWrongSvgIdentity() {
    document.querySelectorAll('.aura-svg-identity-layer').forEach(el => el.remove());
  }

  function patchHeaderIcon() {
    const mark = document.querySelector('.brand-mark');
    if (!mark || mark.querySelector('.aura-brand-ref-icon')) return;
    const img = document.createElement('img');
    img.className = 'aura-brand-ref-icon';
    img.src = ICON_URL;
    img.alt = '';
    img.decoding = 'async';
    mark.replaceChildren(img);
    mark.classList.add('aura-brand-ref-active');
  }

  function ensureLayer() {
    const stage = getStage();
    if (!stage) return null;

    let layer = stage.querySelector('.aura-ref-orb-layer');
    if (!layer) {
      layer = document.createElement('div');
      layer.className = 'aura-ref-orb-layer';
      layer.setAttribute('aria-hidden', 'true');
      const img = document.createElement('img');
      img.src = STAGE_URL;
      img.alt = '';
      img.decoding = 'async';
      layer.appendChild(img);
      stage.appendChild(layer);
    }
    return layer;
  }

  function hideOldCanvasCore() {
    // Keep the live network / particles. Only hide the incorrect interpreted core overlays.
    const c = document.querySelector('canvas');
    if (!c) return;
    // nothing direct to hide here; old SVG is already removed above.
  }

  let layer = null;
  let last = performance.now();
  let pcm = 0;
  let attack = 0;

  function tick(now) {
    requestAnimationFrame(tick);

    if (!layer) {
      layer = ensureLayer();
      patchHeaderIcon();
      removeWrongSvgIdentity();
      hideOldCanvasCore();
      if (!layer) return;
    }

    const dt = clamp((now - last) / 1000, 0, 0.05);
    last = now;

    const rawPcm = getPcm();
    const tau = rawPcm > pcm ? 0.045 : 0.18;
    const k = 1 - Math.exp(-dt / tau);
    pcm += (rawPcm - pcm) * k;
    attack = Math.max(attack * Math.exp(-dt / 0.12), Math.max(0, rawPcm - pcm) * 1.65);

    const build = getBuild();
    const state = getState();
    layer.dataset.state = state;

    const bootOpacity = 0.10 + build * 0.92;
    const breathe = 0.006 * Math.sin(now / 920);
    const speakBoost = state === 'SPEAKING' ? 0.020 + pcm * 0.085 : 0;
    const thinkBoost = ['THINKING', 'ANALYZING', 'SEARCHING'].includes(state) ? 0.010 : 0;
    const listenBoost = state === 'LISTENING' ? 0.008 : 0;

    const scale = 0.88 + build * 0.14 + breathe + speakBoost + thinkBoost + listenBoost + attack * 0.018;
    const opacity = clamp(bootOpacity + pcm * 0.10 + speakBoost * 0.18, 0, 1);

    layer.style.setProperty('--aura-ref-orb-scale', scale.toFixed(4));
    layer.style.setProperty('--aura-ref-orb-opacity', opacity.toFixed(4));

    // Kill any wrong SVG identity that might be re-added later.
    removeWrongSvgIdentity();
  }

  function boot() {
    patchHeaderIcon();
    removeWrongSvgIdentity();
    ensureLayer();
    requestAnimationFrame(tick);
  }

  const obs = new MutationObserver(() => {
    removeWrongSvgIdentity();
    patchHeaderIcon();
    ensureLayer();
  });
  obs.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot, { once: true });
  } else {
    boot();
  }
})();
