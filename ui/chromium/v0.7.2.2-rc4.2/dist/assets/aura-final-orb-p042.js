/* AURA P0.4.3.1 CINEMATIC CONTINUITY */
/* AURA P0.4.2.5 BRAND CORE + FRAGMENTED MEMBRANE */
/* AURA P0.4.2.4 FINAL ORB IDENTITY PASS */
/* AURA P0.4.2 FINAL ORB FOUNDATION
 * Local deterministic neural-orb renderer.
 * No external CDN, no shader/post-process dependency.
 * Reads the already validated AURA DOM state, boot % and real PCM telemetry.
 */
(() => {
  'use strict';
  if (window.__AURA_P042_FINAL_ORB__) return;

  const host = document.getElementById('stage');
  if (!host) return;

  window.__AURA_P042_FINAL_ORB__ = true;
  window.__AURA_FINAL_ORB_ACTIVE__ = true;
  document.documentElement.classList.add('aura-p042-final-orb');

  const canvas = document.createElement('canvas');
  canvas.className = 'aura-final-orb-canvas';
  canvas.setAttribute('aria-hidden', 'true');
  host.appendChild(canvas);

  const ctx = canvas.getContext('2d', {
    alpha: true,
    desynchronized: true
  });
  if (!ctx) return;

  // P0.4.2 owns the visible orb. Keep the legacy canvas object alive for
  // rollback/compatibility, but collapse its drawing buffer so the hidden
  // Three.js renderer cannot continue consuming a full-size render budget.
  function quiesceLegacyRenderer() {
    const legacy = host.querySelectorAll
      ? host.querySelectorAll('canvas:not(.aura-final-orb-canvas)')
      : [];
    for (const oldCanvas of legacy) {
      try {
        if (oldCanvas.width > 4) oldCanvas.width = 2;
        if (oldCanvas.height > 4) oldCanvas.height = 2;
        oldCanvas.style.width = '2px';
        oldCanvas.style.height = '2px';
        oldCanvas.dataset.auraP042Quiesced = '1';
      } catch (_) {}
    }
  }
  quiesceLegacyRenderer();

  const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
  const lerp = (a, b, t) => a + (b - a) * t;
  const smooth = (a, b, x) => {
    const t = clamp((x - a) / Math.max(1e-6, b - a));
    return t * t * (3 - 2 * t);
  };
  const TAU = Math.PI * 2;

  const COLORS = {
    violet: [139, 92, 255],
    magenta: [216, 76, 255],
    cyan: [84, 217, 255],
    blue: [66, 123, 255],
    white: [234, 247, 255],
    dark: [5, 7, 13]
  };

  const rgba = (c, a) =>
    `rgba(${Math.round(c[0])},${Math.round(c[1])},${Math.round(c[2])},${clamp(a)})`;

  const mix = (a, b, t) => [
    lerp(a[0], b[0], t),
    lerp(a[1], b[1], t),
    lerp(a[2], b[2], t)
  ];

  let seed = 0xA0422026;
  const rnd = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 4294967296;
  };

  // ---- Deterministic 3D neural topology ----
  const NODE_COUNT = 184;
  const nodes = [];
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < NODE_COUNT; i++) {
    const u = (i + 0.5) / NODE_COUNT;
    const y = 1 - 2 * u;
    const rr = Math.sqrt(Math.max(0, 1 - y * y));
    const a = i * golden + (rnd() - 0.5) * 0.16;
    const shell = 0.27 + rnd() * 0.62;
    nodes.push({
      x: Math.cos(a) * rr * shell,
      y: y * shell,
      z: Math.sin(a) * rr * shell,
      size: 0.55 + rnd() * 1.2,
      phase: rnd() * TAU,
      pulse: rnd()
    });
  }

  const edges = [];
  const degrees = new Array(NODE_COUNT).fill(0);
  const candidates = [];
  for (let i = 0; i < NODE_COUNT; i++) {
    for (let j = i + 1; j < NODE_COUNT; j++) {
      const a = nodes[i], b = nodes[j];
      const dx = a.x - b.x, dy = a.y - b.y, dz = a.z - b.z;
      const d = Math.sqrt(dx * dx + dy * dy + dz * dz);
      if (d < 0.31) candidates.push([d, i, j, rnd()]);
    }
  }
  candidates.sort((a, b) => a[0] - b[0]);
  for (const [d, i, j, phase] of candidates) {
    if (edges.length >= 336) break;
    if (degrees[i] >= 5 || degrees[j] >= 5) continue;
    degrees[i]++; degrees[j]++;
    edges.push({ i, j, d, phase, speed: 0.18 + rnd() * 0.34 });
  }

  const haloBits = Array.from({ length: 56 }, (_, i) => ({
    a: rnd() * TAU,
    r: 1.02 + rnd() * 0.23,
    y: (rnd() - 0.5) * 1.42,
    size: 0.5 + rnd() * 1.35,
    speed: (0.018 + rnd() * 0.032) * (rnd() > 0.5 ? 1 : -1),
    phase: rnd() * TAU,
    index: i
  }));

  let cssW = 1, cssH = 1, dpr = 1;
  let cx = 0, cy = 0, R = 100;
  let last = performance.now();
  let lastFrame = 0;
  let rotY = 0.0, rotX = -0.11;
  let pcm = 0, pcmAccent = 0, previousPcm = 0;
  let bootVisual = 0;
  let auraBuildLastValue = -1;
  let auraBuildLastChange = performance.now();

  function resize() {
    const rect = host.getBoundingClientRect
      ? host.getBoundingClientRect()
      : { width: host.clientWidth || 900, height: host.clientHeight || 600 };
    cssW = Math.max(1, rect.width || host.clientWidth || 900);
    cssH = Math.max(1, rect.height || host.clientHeight || 600);
    dpr = Math.min(1.5, Math.max(1, window.devicePixelRatio || 1));
    canvas.width = Math.round(cssW * dpr);
    canvas.height = Math.round(cssH * dpr);
    canvas.style.width = cssW + 'px';
    canvas.style.height = cssH + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cx = cssW * 0.5;
    cy = cssH * 0.485;
    R = Math.min(cssW, cssH) * 0.355;
    quiesceLegacyRenderer();
  }

  if (typeof ResizeObserver !== 'undefined') {
    new ResizeObserver(resize).observe(host);
  } else {
    window.addEventListener('resize', resize);
  }
  resize();

  function getBoot() {
    const el = document.getElementById('bootPercent');
    const v = parseFloat(String(el?.textContent || '100').replace(',', '.'));
    const card = document.getElementById('bootCard');
    if (card?.classList?.contains('hidden')) return 100;
    return Number.isFinite(v) ? clamp(v, 0, 100) : 100;
  }

  function getPcm() {
    const el = document.getElementById('pcmValue');
    const v = parseFloat(String(el?.textContent || '0').replace(',', '.'));
    return Number.isFinite(v) ? clamp(v) : 0;
  }

  function getState() {
    return String(document.body?.dataset?.state || 'IDLE').toUpperCase();
  }

  function rotatePoint(p, ry, rx) {
    const cosy = Math.cos(ry), siny = Math.sin(ry);
    let x = p.x * cosy + p.z * siny;
    let z = -p.x * siny + p.z * cosy;
    const cosx = Math.cos(rx), sinx = Math.sin(rx);
    const y = p.y * cosx - z * sinx;
    z = p.y * sinx + z * cosx;
    return { x, y, z };
  }

  function project(p, scale = 1) {
    const perspective = 1 / (1.0 + p.z * 0.14);
    return {
      x: cx + p.x * R * scale * perspective,
      y: cy + p.y * R * scale * perspective,
      z: p.z,
      s: perspective
    };
  }

  function drawEllipseArc(x, y, rx, ry, start, end, rot, color, alpha, width = 1) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(rot);
    ctx.beginPath();
    ctx.ellipse(0, 0, rx, ry, 0, start, end);
    ctx.strokeStyle = rgba(color, alpha);
    ctx.lineWidth = width;
    ctx.stroke();
    ctx.restore();
  }

  function drawPedestal(t, build, energy) {
    const a = smooth(0.48, 0.90, build) * (0.12 + energy * 0.08);
    if (a <= 0.002) return;
    const y = cy + R * 0.94;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    drawEllipseArc(cx, y, R * 0.72, R * 0.145, 0, TAU, 0,
      COLORS.cyan, a * 0.70, 1.0);
    drawEllipseArc(cx, y, R * 0.54, R * 0.095, 0.14, Math.PI * 1.72, 0,
      COLORS.violet, a * 0.82, 1.15);
    drawEllipseArc(cx, y + 2, R * 0.35, R * 0.055, Math.PI * 0.7, TAU * 0.98, 0,
      COLORS.magenta, a * 0.52, 0.8);
    ctx.restore();
  }

  function drawVerticalBeam(build, cognition, energy) {
    const a = smooth(0.52, 0.88, build) * (0.018 + cognition * 0.04 + energy * 0.025);
    if (a <= 0.001) return;
    const g = ctx.createLinearGradient(cx, cy - R * 1.2, cx, cy + R * 1.18);
    g.addColorStop(0, 'rgba(84,217,255,0)');
    g.addColorStop(0.36, rgba(COLORS.cyan, a));
    g.addColorStop(0.5, rgba(COLORS.white, a * 1.35));
    g.addColorStop(0.64, rgba(COLORS.violet, a));
    g.addColorStop(1, 'rgba(139,92,255,0)');
    ctx.save();
    ctx.strokeStyle = g;
    ctx.lineWidth = Math.max(0.7, R * 0.006);
    ctx.beginPath();
    ctx.moveTo(cx, cy - R * 1.2);
    ctx.lineTo(cx, cy + R * 1.18);
    ctx.stroke();
    ctx.restore();
  }

  function drawHaloParticles(t, build, state, energy) {
    const visible = smooth(0.68, 1.0, build);
    if (visible <= 0.002) return;
    const listen = state === 'LISTENING' ? 1 : 0;
    const search = state === 'SEARCHING' ? 1 : 0;
    const outward = search * 0.06;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (const p of haloBits) {
      const a = p.a + t * p.speed;
      const rr = p.r + outward * Math.sin(t * 1.3 + p.phase);
      const x = cx + Math.cos(a) * R * rr;
      const yy = cy + p.y * R * 0.72 + Math.sin(t * 0.6 + p.phase) * R * 0.015;
      const alpha = visible * (0.105 + 0.095 * Math.sin(t * 0.9 + p.phase)) *
        (1 - listen * 0.18) + energy * 0.050;
      ctx.fillStyle = rgba(
        p.index % 3 === 0 ? COLORS.cyan :
        p.index % 3 === 1 ? COLORS.violet : COLORS.magenta,
        clamp(alpha, 0, 0.32)
      );
      ctx.beginPath();
      ctx.arc(x, yy, p.size * (0.8 + energy * 0.35), 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawMembrane(build, state, energy) {
    const visible = smooth(0.54, 0.90, build);
    if (visible <= 0.002) return;

    const focus = state === 'LISTENING' ? 1 : 0;
    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const speaking = state === 'SPEAKING' ? 1 : 0;
    const base = visible * (
      0.055 + focus * 0.024 + thinking * 0.022 +
      speaking * 0.018 + energy * 0.040
    );

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    // Short disconnected shell fragments. The sphere must be implied,
    // never read as a complete orbit/planet ring.
    const segments = 12;
    for (let i = 0; i < segments; i++) {
      const a = i * TAU / segments +
        0.11 * Math.sin(i * 2.71);
      const span = 0.16 + (i % 4) * 0.055;
      const rr = R * (0.885 + (i % 3) * 0.014);
      const squash = 0.92 + (i % 2) * 0.035;
      const rot = (i % 4 - 1.5) * 0.055;
      const c = i % 4 === 0 ? COLORS.magenta :
                i % 3 === 0 ? COLORS.violet :
                COLORS.cyan;

      drawEllipseArc(
        cx, cy,
        rr, rr * squash,
        a, a + span,
        rot,
        c,
        base * (0.68 + (i % 3) * 0.12),
        Math.max(0.55, R * 0.0021)
      );
    }

    ctx.restore();
  }

  function drawCognitiveArcs(t, build, state, energy) {
    const visible = smooth(0.60, 0.90, build);
    if (visible <= 0.002) return;
    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const acting = state === 'ACTING' ? 1 : 0;
    const activity = 0.055 + thinking * 0.09 + acting * 0.045 + energy * 0.055;

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    const phase = t * (0.035 + thinking * 0.055);
    drawEllipseArc(cx, cy, R * 0.73, R * 0.24,
      0.12 + phase, 2.35 + phase, -0.28,
      COLORS.cyan, visible * activity, 0.9);

    drawEllipseArc(cx, cy, R * 0.66, R * 0.31,
      2.62 - phase * 0.72, 5.06 - phase * 0.72, 0.48,
      COLORS.violet, visible * activity * 0.92, 0.85);

    drawEllipseArc(cx, cy, R * 0.54, R * 0.19,
      4.02 + phase * 0.48, 6.04 + phase * 0.48, 1.04,
      COLORS.magenta, visible * activity * 0.62, 0.75);

    ctx.restore();
  }

  function drawNeuralNetwork(t, build, state, energy, accent) {
    const emerge = smooth(0.025, 0.20, build);
    const aggregate = smooth(0.12, 0.50, build);
    if (emerge <= 0.001) return;

    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const listening = state === 'LISTENING' ? 1 : 0;

    const projected = new Array(nodes.length);
    for (let i = 0; i < nodes.length; i++) {
      projected[i] = project(rotatePoint(nodes[i], rotY, rotX), 1);
    }

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';

    // Filaments.
    if (aggregate > 0.001) {
      for (let e = 0; e < edges.length; e++) {
        const edge = edges[e];
        const a = projected[edge.i], b = projected[edge.j];
        const depth = clamp(0.44 + (a.z + b.z) * 0.42, 0.14, 1);
        const pulse = 0.5 + 0.5 * Math.sin(t * (0.9 + edge.speed) + edge.phase * TAU);
        const stateBoost = thinking * pulse * 0.06 + listening * 0.025;
        const voiceBoost = energy * (0.045 + pulse * 0.04);
        const edgeThreshold = 0.16 + edge.phase * 0.56;
        const edgeBuild = smooth(edgeThreshold, edgeThreshold + 0.16, build);
        if (edgeBuild <= 0.002) continue;

        const constructionAge = Math.max(0, (performance.now() - auraBuildLastChange) / 1000);
        const constructionWave = build < 0.95
          ? Math.max(0, Math.sin(t * 1.65 + edge.phase * TAU + edge.i * 0.11))
          : 0;
        const constructionBoost = build < 0.95
          ? (0.025 + constructionWave * 0.060) * (0.55 + Math.min(1, constructionAge / 3) * 0.45)
          : 0;

        const alpha = aggregate * edgeBuild * depth *
          (0.054 + stateBoost * 1.20 + voiceBoost * 1.30 + constructionBoost);

        const colorT = clamp((a.x + b.x) / (R * 1.6) * 0.5 + 0.5);
        const c = mix(COLORS.cyan, COLORS.violet, colorT);
        ctx.strokeStyle = rgba(c, alpha);
        ctx.lineWidth = 0.70 + depth * 0.62 + energy * 0.36;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        const mx = (a.x + b.x) * 0.5 + (a.y - b.y) * 0.035;
        const my = (a.y + b.y) * 0.5 + (b.x - a.x) * 0.035;
        ctx.quadraticCurveTo(mx, my, b.x, b.y);
        ctx.stroke();

        // Synaptic packet.
        if (thinking > 0 || energy > 0.08 || build < 0.95) {
          const q = (t * (0.16 + edge.speed * 0.22) + edge.phase) % 1;
          if (q < 0.54) {
            const qq = q / 0.54;
            const x = lerp(a.x, b.x, qq);
            const y = lerp(a.y, b.y, qq);
            const bootPacket = build < 0.95 ? 0.085 : 0;
            ctx.fillStyle = rgba(
              thinking ? COLORS.cyan : (build < 0.95 ? COLORS.cyan : COLORS.magenta),
              aggregate * edgeBuild *
              (thinking * 0.14 + energy * 0.18 + bootPacket) * depth
            );
            ctx.beginPath();
            ctx.arc(x, y, 0.65 + energy * 0.8, 0, TAU);
            ctx.fill();
          }
        }
      }
    }

    // Nodes.
    for (let i = 0; i < nodes.length; i++) {
      const n = nodes[i];
      const p = projected[i];
      const depth = clamp(0.48 + p.z * 0.52, 0.16, 1);
      const flicker = 0.55 + 0.45 * Math.sin(t * 0.72 + n.phase);
      const nodeThreshold = 0.035 + n.pulse * 0.63;
      const nodeBuild = smooth(nodeThreshold, nodeThreshold + 0.15, build);
      if (nodeBuild <= 0.002) continue;

      const constructionAge = Math.max(0, (performance.now() - auraBuildLastChange) / 1000);
      const constructionScan = build < 0.95
        ? Math.max(0, Math.sin(t * 1.35 + n.phase * 1.7 + i * 0.075))
        : 0;
      const alpha = emerge * nodeBuild * depth *
        (0.15 + flicker * 0.12 + thinking * 0.075 + energy * 0.13 +
         accent * 0.08 + constructionScan * 0.075 *
         (0.60 + Math.min(1, constructionAge / 4) * 0.40));
      const c = i % 7 === 0 ? COLORS.magenta :
                i % 3 === 0 ? COLORS.violet : COLORS.cyan;
      ctx.fillStyle = rgba(c, alpha);
      ctx.beginPath();
      ctx.arc(p.x, p.y,
        (0.80 + n.size * 0.92) * p.s * (1 + energy * 0.18),
        0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawCore(t, build, state, energy, accent) {
    const structured = smooth(0.28, 0.60, build);
    const active = smooth(0.46, 0.82, build);
    if (structured <= 0.001) return;

    const listen = state === 'LISTENING' ? 1 : 0;
    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const speaking = state === 'SPEAKING' ? 1 : 0;

    const radius = R * (0.205 + energy * 0.012 + accent * 0.008);
    const pulse = 0.5 + 0.5 * Math.sin(t * 1.10);
    const stateGlow = listen * 0.09 + thinking * 0.08 + speaking * 0.10;

    // Soft chamber: transparent edge, no black badge.
    const chamber = ctx.createRadialGradient(
      cx, cy, radius * 0.05,
      cx, cy, radius * 1.08
    );
    chamber.addColorStop(0,
      `rgba(20,31,58,${0.58 * structured + energy * 0.08})`);
    chamber.addColorStop(0.42,
      `rgba(8,15,31,${0.42 * structured})`);
    chamber.addColorStop(0.76,
      `rgba(4,9,21,${0.24 * structured})`);
    chamber.addColorStop(1,'rgba(2,5,13,0)');
    ctx.fillStyle=chamber;
    ctx.beginPath();
    ctx.arc(cx,cy,radius*1.10,0,TAU);
    ctx.fill();

    ctx.save();
    ctx.globalCompositeOperation='lighter';

    // Broken cognitive corona close to the core.
    for(let i=0;i<10;i++){
      const a=i*TAU/10 + t*(0.007+(i%3)*0.002);
      const span=0.19+(i%3)*0.055;
      const rr=radius*(1.08+(i%2)*0.10);
      const c=i%4===0?COLORS.magenta:
              i%3===0?COLORS.violet:COLORS.cyan;
      drawEllipseArc(
        cx,cy,rr,rr*(0.95+(i%2)*0.025),
        a,a+span,(i%3-1)*0.035,
        c,
        active*(0.09+stateGlow*0.10+energy*0.08),
        Math.max(0.7,R*0.0030)
      );
    }

    // P0.4.3.2: Canvas keeps this only as an SVG-load fallback.
    if (window.__AURA_P0432_SVG_IDENTITY__ !== true) {
    // Six neural branches matching the AURA brand mark:
    // cyan/white upper branches + cyan left,
    // violet/magenta right and lower branches.
    const branchAngles=[
      Math.PI,
      -2.08,
      -1.06,
      0,
      1.06,
      2.08
    ];
    const branchColors=[
      COLORS.cyan,
      mix(COLORS.cyan,COLORS.white,0.38),
      mix(COLORS.cyan,COLORS.white,0.48),
      mix(COLORS.violet,COLORS.magenta,0.45),
      COLORS.magenta,
      COLORS.violet
    ];

    const inner=radius*0.22;
    const outer=radius*0.80;

    ctx.lineCap='round';
    for(let i=0;i<6;i++){
      const a=branchAngles[i];
      const wobble=Math.sin(t*0.62+i*1.31)*radius*0.018;
      const x1=cx+Math.cos(a)*inner;
      const y1=cy+Math.sin(a)*inner;
      const x2=cx+Math.cos(a)*outer;
      const y2=cy+Math.sin(a)*outer;
      const px=Math.cos(a+Math.PI/2)*wobble;
      const py=Math.sin(a+Math.PI/2)*wobble;

      const grad=ctx.createLinearGradient(x1,y1,x2,y2);
      grad.addColorStop(0,rgba(COLORS.white,
        active*(0.56+energy*0.15)));
      grad.addColorStop(0.30,rgba(branchColors[i],
        active*(0.92+energy*0.06)));
      grad.addColorStop(1,rgba(branchColors[i],
        active*(0.68+energy*0.15)));

      ctx.strokeStyle=grad;
      ctx.lineWidth=Math.max(1.0,R*(0.0060+energy*0.0015));
      ctx.beginPath();
      ctx.moveTo(x1,y1);
      ctx.quadraticCurveTo(
        (x1+x2)*0.5+px,
        (y1+y2)*0.5+py,
        x2,y2
      );
      ctx.stroke();

      // Small terminal synapse.
      ctx.fillStyle=rgba(branchColors[i],
        active*(0.42+energy*0.18));
      ctx.beginPath();
      ctx.arc(x2,y2,
        Math.max(0.8,R*(0.0045+energy*0.0015)),
        0,TAU);
      ctx.fill();
    }

    }

    // Central living neural seed.
    const seedR=R*(0.030+energy*0.007+accent*0.004);
    const seedGrad=ctx.createRadialGradient(
      cx-seedR*0.18,cy-seedR*0.18,0,
      cx,cy,seedR
    );
    seedGrad.addColorStop(0,rgba(COLORS.white,
      active*(0.92+energy*0.06)));
    seedGrad.addColorStop(0.22,rgba(COLORS.cyan,
      active*(0.92+energy*0.06)));
    seedGrad.addColorStop(0.58,rgba(COLORS.violet,
      active*(0.82+energy*0.12)));
    seedGrad.addColorStop(1,rgba(COLORS.magenta,0));
    ctx.fillStyle=seedGrad;
    ctx.beginPath();
    ctx.arc(cx,cy,seedR,0,TAU);
    ctx.fill();

    // Inner hexagonal synaptic cell, subtly echoing the brand icon.
    const hexR=radius*0.24;
    ctx.strokeStyle=rgba(
      mix(COLORS.cyan,COLORS.violet,0.48),
      active*(0.34+energy*0.14)
    );
    ctx.lineWidth=Math.max(0.65,R*0.0028);
    ctx.beginPath();
    for(let i=0;i<6;i++){
      const a=-Math.PI/2+i*TAU/6;
      const x=cx+Math.cos(a)*hexR;
      const y=cy+Math.sin(a)*hexR;
      i?ctx.lineTo(x,y):ctx.moveTo(x,y);
    }
    ctx.closePath();
    ctx.stroke();

    ctx.restore();
  }

  function drawHorizontalWave(t, build, energy, state) {
    const active = smooth(0.54, 0.86, build);
    if (active <= 0.001) return;

    const speaking = state === 'SPEAKING' ? 1 : 0;
    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const width = R * 0.82;
    const amp = R * (0.006 + energy * 0.028 + thinking * 0.004);

    const grad = ctx.createLinearGradient(cx - width, cy, cx + width, cy);
    grad.addColorStop(0, 'rgba(84,217,255,0)');
    grad.addColorStop(0.20, rgba(COLORS.cyan, active * (0.11 + energy * 0.08)));
    grad.addColorStop(0.50, rgba(COLORS.white, active * (0.14 + energy * 0.10)));
    grad.addColorStop(0.80, rgba(COLORS.violet, active * (0.12 + energy * 0.09)));
    grad.addColorStop(1, 'rgba(216,76,255,0)');

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.strokeStyle = grad;
    ctx.lineWidth = 0.65 + energy * 0.55 + speaking * 0.10;
    ctx.beginPath();
    const segments = 64;
    for (let i = 0; i <= segments; i++) {
      const u = i / segments;
      const x = cx - width + u * width * 2;
      const envelope = Math.sin(Math.PI * u);
      const y = cy + Math.sin(
        u * TAU * 2.35 - t * (0.68 + energy * 1.8)
      ) * amp * envelope;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.restore();
  }

  function render(now) {
      requestAnimationFrame(render);

      // AURA_R30_FIX1_HIDDEN_LEGACY_ORB_GUARD
      // P0436 owns the visible orb. P042 remains as a rollback fallback,
      // but must not spend a full render budget after its canvas is hidden/collapsed.
      const auraR30HiddenLegacyOrb =
        canvas.width <= 4 ||
        canvas.height <= 4 ||
        canvas.style.visibility === 'hidden' ||
        canvas.style.opacity === '0';

      if (auraR30HiddenLegacyOrb) {
        last = now;
        lastFrame = now;
        return;
      }
    const auraVisualFps=window.AuraVisualBudget?.fps('legacy-orb',36)||36;
    if (now - lastFrame < 1000 / auraVisualFps) return;
    lastFrame = now;

    const dt = clamp((now - last) / 1000, 0, 0.05);
    last = now;
    const t = now / 1000;

    const state = getState();
    const rawPcm = getPcm();
    const attack = rawPcm > pcm ? 0.045 : 0.22;
    const k = 1 - Math.exp(-dt / attack);
    pcm += (rawPcm - pcm) * k;
    pcmAccent = Math.max(
      pcmAccent * Math.exp(-dt / 0.14),
      Math.max(0, rawPcm - previousPcm) * 2.0
    );
    previousPcm = rawPcm;

    const bootTarget = getBoot() / 100;
    if (Math.abs(bootTarget - auraBuildLastValue) > 0.0005) {
      auraBuildLastValue = bootTarget;
      auraBuildLastChange = now;
    }
    const bk = 1 - Math.exp(-dt / (bootTarget > bootVisual ? 0.17 : 0.32));
    bootVisual += (bootTarget - bootVisual) * bk;
    const build = clamp(bootVisual);

    const idle = state === 'IDLE' ? 1 : 0;
    const listening = state === 'LISTENING' ? 1 : 0;
    const thinking = /THINKING|ANALYZING|SEARCHING/.test(state) ? 1 : 0;
    const acting = state === 'ACTING' ? 1 : 0;

    const breath = idle * (0.5 + 0.5 * Math.sin(t * 0.96));
    const buildStillness = build < 0.95
      ? (0.5 + 0.5 * Math.sin(t * 0.58)) * 0.004
      : 0;
    const scale = 1 + breath * 0.006 + pcm * 0.010 + buildStillness;

    const constructing = build < 0.95 ? 1 : 0;
    const stationaryAge = Math.max(0, (now - auraBuildLastChange) / 1000);
    const constructionMotion = constructing *
      (0.030 + 0.018 * (0.5 + 0.5 * Math.sin(t * 0.42)) +
       0.012 * Math.min(1, stationaryAge / 5));

    rotY += dt * (
      0.055 + listening * 0.012 + thinking * 0.095 +
      acting * 0.045 + constructionMotion
    );
    rotX = -0.11 + Math.sin(t * 0.16) * 0.035;

    ctx.clearRect(0, 0, cssW, cssH);
    ctx.save();
    ctx.translate(cx, cy);
    ctx.scale(scale, scale);
    ctx.translate(-cx, -cy);

    drawHaloParticles(t, build, state, pcm);
    drawVerticalBeam(build, thinking, pcm);
    drawNeuralNetwork(t, build, state, pcm, pcmAccent);
    drawMembrane(build, state, pcm);
    drawHorizontalWave(t, build, pcm, state);
    drawCore(t, build, state, pcm, pcmAccent);

    ctx.restore();
  }

  requestAnimationFrame(render);
})();
