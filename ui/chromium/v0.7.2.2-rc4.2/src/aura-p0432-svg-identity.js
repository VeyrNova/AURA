/* AURA P0.4.3.2 SVG IDENTITY LAYER */
(() => {
  'use strict';

  if (window.__AURA_P0432_SVG_LAYER__) return;
  window.__AURA_P0432_SVG_LAYER__ = true;

  // The Canvas renderer keeps its fallback branches until the SVG has
  // actually loaded successfully.
  window.__AURA_P0432_SVG_IDENTITY__ = 'loading';

  const stage = document.getElementById('stage');
  if (!stage) {
    window.__AURA_P0432_SVG_IDENTITY__ = false;
    return;
  }

  const CORE_URL = '/assets/aura-brand-core-p0432.svg?v=p0432-20260816';
  const HEADER_URL = '/assets/aura-brand-header-p0432.svg?v=p0432-20260816';

  const layer = document.createElement('div');
  layer.className = 'aura-svg-identity-layer';
  layer.setAttribute('aria-hidden', 'true');
  stage.appendChild(layer);

  let svg = null;
  let branches = [];
  let flows = [];
  let seed = null;
  let seedGlow = null;
  let hub = null;
  let hubRing = null;
  let pcm = 0;
  let lastPcm = 0;
  let accent = 0;
  let last = performance.now();

  const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
  const smooth = (a,b,x) => {
    const t=clamp((x-a)/Math.max(1e-6,b-a));
    return t*t*(3-2*t);
  };

  function getBuild() {
    const card = document.getElementById('bootCard');
    if (card?.classList?.contains('hidden') ||
        document.documentElement.classList.contains('aura-p043-complete')) {
      return 1;
    }
    const el = document.getElementById('bootPercent');
    const n = parseFloat(String(el?.textContent || '100').replace(',','.'));
    return Number.isFinite(n) ? clamp(n/100) : 1;
  }

  function getPcm() {
    const el = document.getElementById('pcmValue');
    const n = parseFloat(String(el?.textContent || '0').replace(',','.'));
    return Number.isFinite(n) ? clamp(n) : 0;
  }

  function getState() {
    return String(document.body?.dataset?.state || 'IDLE').toUpperCase();
  }

  function branchProgress(build,index) {
    const starts=[0.05,0.10,0.15,0.23,0.34,0.42];
    const spans =[0.22,0.25,0.25,0.26,0.28,0.28];
    return smooth(starts[index],starts[index]+spans[index],build);
  }

  function sizeLayer() {
    const r=stage.getBoundingClientRect();
    const min=Math.max(1,Math.min(r.width,r.height));
    const size=Math.max(74,Math.min(152,min*0.125));
    layer.style.setProperty('--aura-svg-size', `${size}px`);
  }

  function replaceHeaderLogo() {
    const mark=document.querySelector('.brand-mark');
    if (!mark) return;
    if (mark.querySelector('.aura-header-svg')) return;
    const img=document.createElement('img');
    img.className='aura-header-svg';
    img.src=HEADER_URL;
    img.alt='';
    img.decoding='async';
    mark.replaceChildren(img);
    mark.classList.add('aura-brand-svg-active');
  }

  async function load() {
    try {
      const res=await fetch(CORE_URL,{cache:'no-store'});
      if (!res.ok) throw new Error(`SVG HTTP ${res.status}`);
      const text=await res.text();
      const doc=new DOMParser().parseFromString(text,'image/svg+xml');
      const root=doc.documentElement;
      if (!root || root.nodeName.toLowerCase()!=='svg') throw new Error('invalid svg');

      svg=document.importNode(root,true);
      svg.classList.add('aura-core-svg');
      layer.appendChild(svg);

      branches=[...svg.querySelectorAll('.branch')];
      flows=[...svg.querySelectorAll('.flow')];
      seed=svg.querySelector('.aura-svg-seed');
      seedGlow=svg.querySelector('.aura-svg-seed-glow');
      hub=svg.querySelector('.aura-svg-hub');
      hubRing=svg.querySelector('.aura-svg-hub-ring');

      for (const p of [...branches,...flows]) {
        p.style.strokeDasharray='1';
        p.style.strokeDashoffset='1';
      }

      sizeLayer();
      replaceHeaderLogo();

      // Canvas branch fallback can now disappear.
      window.__AURA_P0432_SVG_IDENTITY__ = true;
      requestAnimationFrame(frame);
    } catch (err) {
      console.warn('[AURA P0.4.3.2] SVG identity fallback:',err);
      window.__AURA_P0432_SVG_IDENTITY__ = false;
      layer.remove();
    }
  }

  function frame(now) {
    requestAnimationFrame(frame);
    if (!svg) return;

    const dt=clamp((now-last)/1000,0,0.05);
    last=now;

    const raw=getPcm();
    const tau=raw>pcm?0.045:0.19;
    const k=1-Math.exp(-dt/tau);
    pcm+=(raw-pcm)*k;
    accent=Math.max(
      accent*Math.exp(-dt/0.13),
      Math.max(0,raw-lastPcm)*1.8
    );
    lastPcm=raw;

    const build=getBuild();
    const state=getState();
    layer.dataset.state=state;

    for (let i=0;i<branches.length;i++) {
      const p=branchProgress(build,i);
      branches[i].style.strokeDashoffset=String(1-p);
      branches[i].style.opacity=String(0.20+0.80*p);
      if (flows[i]) {
        flows[i].style.strokeDashoffset=String(1-p);
        flows[i].style.opacity=String(p*(state==='THINKING'||state==='SEARCHING'?0.72:0.30));
      }
    }

    const hubBuild=smooth(0.38,0.72,build);
    const seedBuild=smooth(0.12,0.48,build);

    if (hub) {
      hub.style.opacity=String(hubBuild);
      hub.style.transformOrigin='60px 60px';
      hub.style.transform=`scale(${0.58+hubBuild*0.42})`;
    }
    if (hubRing) hubRing.style.opacity=String(hubBuild*0.72);
    if (seed) seed.style.opacity=String(0.25+seedBuild*0.75);
    if (seedGlow) seedGlow.style.opacity=String(0.20+seedBuild*0.68);

    const scale=1+pcm*0.075+accent*0.025;
    layer.style.setProperty('--aura-svg-scale',scale.toFixed(4));
    layer.style.setProperty('--aura-svg-pcm',pcm.toFixed(4));
    layer.style.setProperty('--aura-svg-build',build.toFixed(4));
  }

  if (typeof ResizeObserver!=='undefined') {
    new ResizeObserver(sizeLayer).observe(stage);
  } else {
    window.addEventListener('resize',sizeLayer,{passive:true});
  }

  load();
})();
