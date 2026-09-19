/* AURA P0.4.D3 FINAL ORB RUNTIME PROBE */
(() => {
  'use strict';
  if (window.__AURA_P04D3_PROBE__) return;
  window.__AURA_P04D3_PROBE__ = true;

  const token = new URLSearchParams(location.search).get('token') || '';
  const enc = encodeURIComponent;
  const clean = v => String(v ?? '')
    .replace(/\s+/g, ' ')
    .replace(/[|]/g, '/')
    .slice(0, 190);

  function send(tag, message, dpr = window.devicePixelRatio || 1) {
    if (!token) return;
    const payload = clean(`P04D3_${tag}|${message}`);
    fetch(`/api/client-info?token=${enc(token)}`, {
      method: 'POST',
      cache: 'no-store',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        webgl_renderer: payload,
        dpr: Number(dpr || 1)
      })
    }).catch(() => {});
  }

  window.addEventListener('error', ev => {
    send('ERR',
      `msg=${clean(ev.message)} src=${clean((ev.filename || '').split('/').pop())}` +
      ` line=${ev.lineno || 0}:${ev.colno || 0}`
    );
  }, true);

  window.addEventListener('unhandledrejection', ev => {
    const reason = ev.reason && (ev.reason.stack || ev.reason.message || ev.reason);
    send('REJECT', clean(reason));
  });

  function n(v) {
    const x = Number(v);
    return Number.isFinite(x) ? Math.round(x) : -1;
  }

  function styleSummary(el) {
    if (!el) return 'missing';
    const cs = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return `${n(r.width)}x${n(r.height)}` +
      ` pos=${cs.position} disp=${cs.display}` +
      ` vis=${cs.visibility} op=${cs.opacity} z=${cs.zIndex}`;
  }

  function alphaSample(canvas) {
    if (!canvas) return 'none';
    try {
      const ctx = canvas.getContext('2d');
      if (!ctx || !canvas.width || !canvas.height) return 'noctx';
      const x = Math.max(0, Math.min(canvas.width - 1, Math.floor(canvas.width / 2)));
      const y = Math.max(0, Math.min(canvas.height - 1, Math.floor(canvas.height / 2)));
      const d = ctx.getImageData(x, y, 1, 1).data;
      return `${d[0]},${d[1]},${d[2]},${d[3]}`;
    } catch (e) {
      return 'sampleerr:' + clean(e.message);
    }
  }

  function snapshot(label) {
    const hero = document.querySelector('.hero');
    const stage = document.getElementById('stage');
    const canvas = document.querySelector('.aura-final-orb-canvas');
    const legacy = stage
      ? [...stage.querySelectorAll('canvas:not(.aura-final-orb-canvas)')]
      : [];
    const bp = document.getElementById('bootPercent');
    const bc = document.getElementById('bootCard');
    const pcm = document.getElementById('pcmValue');

    send('SNAP1',
      `${label} hero=${styleSummary(hero)} stage=${styleSummary(stage)}`
    );

    send('SNAP2',
      `${label} canvas=${styleSummary(canvas)}` +
      ` buf=${canvas ? canvas.width + 'x' + canvas.height : 'missing'}` +
      ` alpha=${alphaSample(canvas)}`
    );

    send('SNAP3',
      `${label} flags=p042:${!!window.__AURA_P042_FINAL_ORB__}` +
      ` active:${!!window.__AURA_FINAL_ORB_ACTIVE__}` +
      ` htmlcls:${document.documentElement.classList.contains('aura-p042-final-orb')}` +
      ` connected:${!!canvas?.isConnected}`
    );

    send('SNAP4',
      `${label} state=${clean(document.body?.dataset?.state || '')}` +
      ` boot=${clean(bp?.textContent || '')}` +
      ` bootHidden=${!!bc?.classList?.contains('hidden')}` +
      ` pcm=${clean(pcm?.textContent || '')}` +
      ` legacy=${legacy.length}` +
      ` lbuf=${legacy.map(c => c.width + 'x' + c.height).join(',').slice(0, 60)}`
    );

    const resources = performance.getEntriesByType('resource')
      .filter(e => /aura-final-orb-p042|aura-p04-d3/i.test(e.name))
      .map(e => `${e.name.split('/').pop()}:${Math.round(e.duration)}ms`)
      .join(',');
    send('RES', `${label} ${resources || 'no-resource-entry'}`);
  }

  // Probe before/after the Final Orb script has had time to initialize/render.
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => snapshot('dom'), {once:true});
  } else {
    snapshot('immediate');
  }
  setTimeout(() => snapshot('t500'), 500);
  setTimeout(() => snapshot('t1500'), 1500);
  setTimeout(() => snapshot('t3500'), 3500);
})();
