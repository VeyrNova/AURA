/* AURA P0.4.3.1 CINEMATIC CONTINUITY */
/* AURA P0.4.3 NEURAL CONSTRUCTION BOOT
 * Uses the SAME #stage / Final Orb canvas from boot to final UI.
 * No fake timer-driven construction: percentage remains runtime-owned.
 */
(() => {
  'use strict';
  if (window.__AURA_P043_NEURAL_BOOT__) return;
  window.__AURA_P043_NEURAL_BOOT__ = true;

  const html = document.documentElement;
  const body = document.body;
  const stage = document.getElementById('stage');
  const hero = document.querySelector('.hero');
  const bootPercent = document.getElementById('bootPercent');
  const bootPhase = document.getElementById('bootPhase');
  const bootCard = document.getElementById('bootCard');

  const backdrop = document.getElementById('auraP043Backdrop');
  const hud = document.getElementById('auraP043Hud');
  const hudIndex = document.getElementById('auraP043Index');
  const hudPhase = document.getElementById('auraP043Phase');
  const hudPercent = document.getElementById('auraP043Percent');
  const hudPulse = document.getElementById('auraP043Pulse');

  if (!stage || !hero || !backdrop || !hud) {
    html.classList.remove('aura-p043-running');
    return;
  }

  body.classList.add('aura-p043-boot');

  let releaseStarted = false;
  let finished = false;
  let currentPercent = 0;

  function numPercent() {
    const raw = String(bootPercent?.textContent || '0')
      .replace(',', '.')
      .replace(/[^0-9.]/g, '');
    const v = Number(raw);
    return Number.isFinite(v) ? Math.max(0, Math.min(100, v)) : 0;
  }

  function stageMeta(p) {
    if (p >= 95) return ['05', 'STABILISATION'];
    if (p >= 70) return ['04', 'ACTIVATION'];
    if (p >= 45) return ['03', 'STRUCTURATION'];
    if (p >= 20) return ['02', 'AGRÉGATION'];
    if (p > 0)   return ['01', 'ÉMERGENCE'];
    return ['00', 'SILENCE INITIAL'];
  }

  function forceFullscreenStage() {
    if (finished) return;
    stage.style.setProperty('position', 'fixed', 'important');
    stage.style.setProperty('inset', 'auto', 'important');
    stage.style.setProperty('top', '0px', 'important');
    stage.style.setProperty('left', '0px', 'important');
    stage.style.setProperty('width', '100vw', 'important');
    stage.style.setProperty('height', '100vh', 'important');
    stage.style.setProperty('min-height', '100vh', 'important');
    stage.style.setProperty('z-index', '9002', 'important');
    stage.style.setProperty('overflow', 'hidden', 'important');
  }

  function updateHud() {
    const p = numPercent();
    currentPercent = Math.max(currentPercent, p);
    const [idx, phase] = stageMeta(currentPercent);

    if (hudIndex) hudIndex.textContent = idx;
    if (hudPhase) hudPhase.textContent = phase;
    if (hudPercent) hudPercent.textContent =
      String(Math.round(currentPercent)).padStart(2, '0') + '%';

    if (hudPulse) {
      hudPulse.style.setProperty('--aura-build',
        String(Math.max(0.015, currentPercent / 100)));
    }

    // Runtime remains the source of truth. Only release timing is cinematic.
    if (currentPercent >= 100 && !releaseStarted) {
      releaseStarted = true;
      html.classList.add('aura-p043-stabilizing');
      setTimeout(beginReveal, 1050);
    }
  }

  function beginReveal() {
    if (finished) return;

    const target = hero.getBoundingClientRect();
    if (!target.width || !target.height) {
      setTimeout(beginReveal, 100);
      return;
    }

    html.classList.add('aura-p043-revealing');

    // Ensure the legacy loading card never appears through the dissolving veil.
    try { bootCard?.classList.add('hidden'); } catch (_) {}

    // FLIP-like transition of the SAME stage into its final hero viewport.
    stage.style.setProperty(
      'transition',
      'top 920ms cubic-bezier(.22,.78,.18,1), ' +
      'left 920ms cubic-bezier(.22,.78,.18,1), ' +
      'width 920ms cubic-bezier(.22,.78,.18,1), ' +
      'height 920ms cubic-bezier(.22,.78,.18,1)',
      'important'
    );
    stage.style.setProperty('top', `${target.top}px`, 'important');
    stage.style.setProperty('left', `${target.left}px`, 'important');
    stage.style.setProperty('width', `${target.width}px`, 'important');
    stage.style.setProperty('height', `${target.height}px`, 'important');
    stage.style.setProperty('min-height', `${target.height}px`, 'important');

    backdrop.classList.add('aura-p043-backdrop-reveal');
    hud.classList.add('aura-p043-hud-reveal');

    setTimeout(finishReveal, 980);
  }

  function finishReveal() {
    if (finished) return;
    finished = true;

    stage.style.removeProperty('transition');
    stage.style.setProperty('position', 'absolute', 'important');
    stage.style.setProperty('inset', '0', 'important');
    stage.style.removeProperty('top');
    stage.style.removeProperty('left');
    stage.style.setProperty('width', '100%', 'important');
    stage.style.setProperty('height', '100%', 'important');
    stage.style.setProperty('min-height', '100%', 'important');
    stage.style.removeProperty('z-index');

    backdrop.style.display = 'none';
    hud.style.display = 'none';

    body.classList.remove('aura-p043-boot');
    html.classList.remove(
      'aura-p043-running',
      'aura-p043-stabilizing',
      'aura-p043-revealing'
    );
    html.classList.add('aura-p043-complete');

    // Final Orb + Geometry Guardian re-evaluate their real hero dimensions.
    window.dispatchEvent(new Event('resize'));
  }

  // Geometry must be fullscreen BEFORE Final Orb performs its first sizing pass.
  forceFullscreenStage();
  updateHud();

  const mo = new MutationObserver(() => {
    forceFullscreenStage();
    updateHud();
  });
  if (bootPercent) {
    mo.observe(bootPercent, {
      childList: true,
      characterData: true,
      subtree: true
    });
  }
  if (bootPhase) {
    mo.observe(bootPhase, {
      childList: true,
      characterData: true,
      subtree: true
    });
  }

  window.addEventListener('resize', () => {
    if (!finished && !releaseStarted) forceFullscreenStage();
  }, {passive:true});

  // Recovery safety: status polling may update text between observer turns.
  const watcher = setInterval(() => {
    if (finished) {
      clearInterval(watcher);
      return;
    }
    if (!releaseStarted) forceFullscreenStage();
    updateHud();
  }, 180);
})();
