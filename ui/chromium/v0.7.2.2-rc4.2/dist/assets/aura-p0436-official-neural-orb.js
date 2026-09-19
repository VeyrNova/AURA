/* AURA P0.4.3.6 OFFICIAL VECTOR NEURAL ORB */
/* AURA P0.4.3.7 REFERENCE FIDELITY PASS */
/* AURA P0.4.3.8 ELECTRIC MEMBRANE + TENDRIL REFINEMENT */
/* AURA P0.4.3.9 TRUE STAGED NEURAL CONSTRUCTION */
/* AURA P0.4.3.10 CHECKPOINT VISUAL INTERPOLATION */
(() => {
  'use strict';
  if (window.__AURA_P0436_OFFICIAL_ORB__) return;
  window.__AURA_P0436_OFFICIAL_ORB__ = true;

  const stage = document.getElementById('stage');
  if (!stage) return;

  const TAU = Math.PI * 2;
  const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,v));
  const lerp=(a,b,t)=>a+(b-a)*t;
  const smooth=(a,b,x)=>{const t=clamp((x-a)/Math.max(1e-6,b-a));return t*t*(3-2*t)};
  const C={
    cyan:[99,243,255], cyan2:[59,187,255], blue:[98,135,255],
    violet:[155,92,255], purple:[186,76,255], magenta:[218,92,255],
    white:[243,250,255]
  };
  const rgba=(c,a)=>`rgba(${c[0]|0},${c[1]|0},${c[2]|0},${clamp(a)})`;
  const mix=(a,b,t)=>[lerp(a[0],b[0],t),lerp(a[1],b[1],t),lerp(a[2],b[2],t)];

  // Remove obsolete identity layers from prior experiments.
  const obsoleteSelector=[
    '.aura-ref-orb-layer','.aura-svg-identity-layer','.aura-reference-logo',
    '.aura-reference-procedural-canvas','.aura-p0434-procedural-reference-orb'
  ].join(',');
  const removeObsolete=()=>stage.querySelectorAll(obsoleteSelector).forEach(el=>el.remove());
  removeObsolete();

  // Crucial compatibility: include the historical allowed class so P0.4.2's
  // legacy canvas-hiding rule can never hide this renderer.
  const canvas=document.createElement('canvas');
  canvas.className='aura-final-orb-canvas aura-p0436-orb-canvas';
  canvas.setAttribute('aria-hidden','true');
  stage.appendChild(canvas);

  // Exact official vector lockup supplied by the user.
  const lockup=document.createElement('img');
  lockup.className='aura-p0436-lockup';
  lockup.src='/assets/AURA_LOGO_LOCKUP_MASTER.svg?v=p0436-20260816';
  lockup.alt='';
  lockup.decoding='async';
  stage.appendChild(lockup);

  // Official topbar symbol. Existing AURA wordmark text stays intact.
  const brandMark=document.querySelector('.brand-mark');
  if(brandMark){
    const brandImg=document.createElement('img');
    brandImg.className='aura-p0436-header-symbol';
    brandImg.src='/assets/AURA_LOGO_SYMBOL_NEON.svg?v=p0436-20260816';
    brandImg.alt=''; brandImg.decoding='async';
    brandMark.replaceChildren(brandImg);
    brandMark.classList.add('aura-p0436-brand-active');
  }

  const ctx=canvas.getContext('2d',{alpha:true,desynchronized:true});
  if(!ctx)return;

  let seed=0xA0436;
  const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};

  // Dense shell-biased neural sphere.
  const NODE_COUNT=348;
  const nodes=[];
  const golden=Math.PI*(3-Math.sqrt(5));
  for(let i=0;i<NODE_COUNT;i++){
    const u=(i+.5)/NODE_COUNT;
    const y=1-2*u;
    const rr=Math.sqrt(Math.max(0,1-y*y));
    const a=i*golden+(rnd()-.5)*.20;
    const shell=.72+rnd()*.27;
    nodes.push({
      x:Math.cos(a)*rr*shell,
      y:y*shell,
      z:Math.sin(a)*rr*shell,
      size:.55+rnd()*1.55,
      phase:rnd()*TAU,
      birth:.08+rnd()*.80,
      color:rnd()
    });
  }

  const cand=[];
  for(let i=0;i<NODE_COUNT;i++)for(let j=i+1;j<NODE_COUNT;j++){
    const a=nodes[i],b=nodes[j];
    const dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z;
    const d=Math.sqrt(dx*dx+dy*dy+dz*dz);
    if(d<.228)cand.push([d,i,j,rnd()]);
  }
  cand.sort((a,b)=>a[0]-b[0]);
  const edges=[],deg=new Uint8Array(NODE_COUNT);
  for(const [d,i,j,p] of cand){
    if(edges.length>=860)break;
    if(deg[i]>=7||deg[j]>=7)continue;
    deg[i]++;deg[j]++;
    edges.push({i,j,phase:p,birth:.12+p*.74,speed:.12+rnd()*.34});
  }

  const stars=Array.from({length:190},()=>({
    x:(rnd()-.5)*2.35,y:(rnd()-.5)*2.05,r:.25+rnd()*1.25,
    phase:rnd()*TAU,color:rnd(),birth:rnd()*.55
  }));

  const tendrils=Array.from({length:30},(_,i)=>({
    angle:i*TAU/30+(rnd()-.5)*.12,
    len:.12+rnd()*.20,
    bend:(rnd()-.5)*.32,
    phase:rnd()*TAU,
    color:rnd(),
    birth:.74+rnd()*.20
  }));

  let cssW=1,cssH=1,dpr=1,cx=0,cy=0,R=100;
  let rot=0,last=performance.now(),lastFrame=0;
  let pcm=0,prevPcm=0,accent=0;
  let auraBuildLastValue=-1;
  let auraBuildChangedAt=performance.now();

  // P0.4.3.10:
  // trueBuild is always the real runtime percentage.
  // visualBuild only interpolates the geometry toward that real checkpoint.
  // It never exceeds trueBuild and never writes bootPercent.
  let auraVisualBuild=0;
  let auraVisualInitialized=false;

  function quiesceOldCanvases(){
    for(const c of stage.querySelectorAll('canvas')){
      if(c===canvas)continue;
      c.style.setProperty('opacity','0','important');
      c.style.setProperty('visibility','hidden','important');
      c.style.setProperty('pointer-events','none','important');
      try{if(c.width>4)c.width=2;if(c.height>4)c.height=2}catch(_){ }
    }
  }

  function resize(){
    const r=stage.getBoundingClientRect();
    cssW=Math.max(1,r.width);cssH=Math.max(1,r.height);
    dpr=Math.min(1.5,Math.max(1,window.devicePixelRatio||1));
    canvas.width=Math.round(cssW*dpr);canvas.height=Math.round(cssH*dpr);
    canvas.style.width=cssW+'px';canvas.style.height=cssH+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    cx=cssW*.50; cy=cssH*.455;
    R=Math.min(cssW,cssH)*.305;
    const lw=R*.72;
    lockup.style.width=lw+'px';
    lockup.style.height=lw*1.10+'px';
    lockup.style.left=cx+'px'; lockup.style.top=(cy+R*.015)+'px';
    quiesceOldCanvases();
  }
  if(typeof ResizeObserver!=='undefined')new ResizeObserver(resize).observe(stage);
  else window.addEventListener('resize',resize,{passive:true});
  resize();

  const getState=()=>String(document.body?.dataset?.state||'IDLE').toUpperCase();
  function getPcm(){
    const n=parseFloat(String(document.getElementById('pcmValue')?.textContent||'0').replace(',','.'));
    return Number.isFinite(n)?clamp(n):0;
  }
  function getBuild(){
    const card=document.getElementById('bootCard');
    if(card?.classList?.contains('hidden')||document.documentElement.classList.contains('aura-p043-complete'))return 1;
    const n=parseFloat(String(document.getElementById('bootPercent')?.textContent||'100').replace(',','.'));
    return Number.isFinite(n)?clamp(n/100):1;
  }

  function rotatePoint(p,ry,rx){
    const cyy=Math.cos(ry),syy=Math.sin(ry);
    let x=p.x*cyy+p.z*syy, z=-p.x*syy+p.z*cyy;
    const cxx=Math.cos(rx),sxx=Math.sin(rx);
    const y=p.y*cxx-z*sxx; z=p.y*sxx+z*cxx;
    return{x,y,z};
  }
  function project(p){
    const s=1/(1+p.z*.10);
    return{x:cx+p.x*R*s,y:cy+p.y*R*s,z:p.z,s};
  }

  function drawBackgroundParticles(t,build){
    const v=smooth(.02,.34,build);
    ctx.save();ctx.globalCompositeOperation='lighter';
    for(const s of stars){
      const b=smooth(s.birth,s.birth+.18,build);if(b<=.001)continue;
      const x=cx+s.x*R+Math.sin(t*.14+s.phase)*R*.009;
      const y=cy+s.y*R*.76+Math.cos(t*.12+s.phase)*R*.006;
      const col=s.color<.42?C.cyan2:s.color<.76?C.violet:C.magenta;
      const a=v*b*(.060+.115*(.5+.5*Math.sin(t*.9+s.phase)));
      ctx.fillStyle=rgba(col,a);ctx.beginPath();ctx.arc(x,y,s.r,0,TAU);ctx.fill();
    }
    ctx.restore();
  }

  function drawWaveform(t,build,state,energy){
    const v=smooth(.40,.72,build);if(v<=.001)return;
    const speaking=state==='SPEAKING';
    const voiceEnergy=speaking?Math.max(.24,energy):energy;
    const width=R*1.78, mid=cy;
    const amp=R*(.013+(speaking?voiceEnergy*.150:.0065));

    ctx.save();ctx.globalCompositeOperation='lighter';

    // Broad low-alpha aura behind the waveform.
    const haze=ctx.createLinearGradient(cx-width,mid,cx+width,mid);
    haze.addColorStop(0,'rgba(218,92,255,0)');
    haze.addColorStop(.18,rgba(C.magenta,v*(.055+voiceEnergy*.035)));
    haze.addColorStop(.50,rgba(C.violet,v*(.025+voiceEnergy*.020)));
    haze.addColorStop(.82,rgba(C.cyan,v*(.060+voiceEnergy*.040)));
    haze.addColorStop(1,'rgba(99,243,255,0)');
    ctx.strokeStyle=haze;ctx.lineWidth=5+voiceEnergy*5;
    ctx.beginPath();ctx.moveTo(cx-width,mid);ctx.lineTo(cx+width,mid);ctx.stroke();

    const g=ctx.createLinearGradient(cx-width,mid,cx+width,mid);
    g.addColorStop(0,'rgba(218,92,255,0)');
    g.addColorStop(.12,rgba(C.magenta,v*(.32+voiceEnergy*.18)));
    g.addColorStop(.42,rgba(C.violet,v*(.16+voiceEnergy*.12)));
    g.addColorStop(.58,rgba(C.cyan,v*(.16+voiceEnergy*.12)));
    g.addColorStop(.88,rgba(C.cyan,v*(.34+voiceEnergy*.20)));
    g.addColorStop(1,'rgba(99,243,255,0)');
    ctx.strokeStyle=g;ctx.lineWidth=1.0+voiceEnergy*1.20;ctx.beginPath();

    const N=240;
    for(let i=0;i<=N;i++){
      const u=i/N,x=cx-width+u*width*2,dist=Math.abs(u-.5)*2;
      const side=.22+1.12*smooth(.06,.94,dist);
      const m=Math.sin(u*TAU*17-t*(1.55+voiceEnergy*3.0))*.50+
              Math.sin(u*TAU*31+t*.78)*.30+
              Math.sin(u*TAU*53-t*.36)*.18;
      const y=mid+m*amp*side;
      i?ctx.lineTo(x,y):ctx.moveTo(x,y);
    }
    ctx.stroke();

    // AURA P0.8.5.4.6.9.5 — clean voice waveform.
    // Vertical spectrum/analyzer bars intentionally removed.
    // The single horizontal waveform above remains driven by real PCM telemetry.
    ctx.restore();
  }

  function drawHalo(build,energy){
    const v=smooth(.34,.78,build);if(v<=.001)return;
    ctx.save();ctx.globalCompositeOperation='lighter';

    const g=ctx.createRadialGradient(cx,cy,R*.10,cx,cy,R*1.28);
    g.addColorStop(0,rgba(C.white,v*(.020+energy*.018)));
    g.addColorStop(.24,rgba(C.violet,v*(.055+energy*.040)));
    g.addColorStop(.58,rgba(C.blue,v*(.025+energy*.025)));
    g.addColorStop(.88,rgba(C.magenta,v*(.010+energy*.014)));
    g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*1.30,0,TAU);ctx.fill();

    const inner=ctx.createRadialGradient(cx,cy,0,cx,cy,R*.58);
    inner.addColorStop(0,rgba(C.violet,v*(.065+energy*.050)));
    inner.addColorStop(.38,rgba(C.blue,v*(.020+energy*.024)));
    inner.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=inner;ctx.beginPath();ctx.arc(cx,cy,R*.60,0,TAU);ctx.fill();
    ctx.restore();
  }

  function drawGlobe(t,build,state,energy){
    const emerge=smooth(.03,.22,build), aggregate=smooth(.15,.62,build), structure=smooth(.46,.90,build);
    if(emerge<=.001)return;
    const rx=-.055+Math.sin(t*.14)*.018;
    const pts=nodes.map(n=>project(rotatePoint(n,rot,rx)));
    ctx.save();ctx.globalCompositeOperation='lighter';

    for(const e of edges){
      const eb=smooth(e.birth,e.birth+.16,build);if(eb<=.001)continue;
      const a=pts[e.i],b=pts[e.j],depth=clamp(.42+(a.z+b.z)*.38,.10,1);
      const p=.5+.5*Math.sin(t*(.72+e.speed)+e.phase*TAU);
      const stateBoost=/THINKING|ANALYZING|SEARCHING/.test(state)?.060*p:0;
      const centerBoost=1+Math.max(0,1-Math.hypot((a.x+b.x)*.5-cx,(a.y+b.y)*.5-cy)/(R*.95))*.38;
      const alpha=aggregate*eb*depth*centerBoost*(.095+energy*(.082+.092*p)+stateBoost*1.20);
      const col=mix(C.magenta,C.cyan,clamp(((a.x+b.x)*.5-cx)/(R*1.55)*.5+.5));
      ctx.strokeStyle=rgba(col,alpha);ctx.lineWidth=.64+depth*.88+energy*.34;
      ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
      if(build<.98||energy>.04){
        const q=(t*(.10+e.speed*.14)+e.phase)%1;
        if(q<.30){
          const qq=q/.30,x=lerp(a.x,b.x,qq),y=lerp(a.y,b.y,qq);
          ctx.fillStyle=rgba(energy>.08?C.white:(e.phase>.5?C.magenta:C.cyan),aggregate*eb*depth*(.08+energy*.18));
          ctx.beginPath();ctx.arc(x,y,.65+energy*1.0,0,TAU);ctx.fill();
        }
      }
    }

    for(let i=0;i<nodes.length;i++){
      const n=nodes[i],nb=smooth(n.birth,n.birth+.14,build);if(nb<=.001)continue;
      const p=pts[i],depth=clamp(.48+p.z*.52,.15,1),f=.5+.5*Math.sin(t*.65+n.phase);
      const col=n.color<.42?C.cyan:n.color<.74?C.violet:C.magenta;
      const radialBoost=1+Math.max(0,1-Math.hypot(p.x-cx,p.y-cy)/(R*.94))*.34;
      ctx.fillStyle=rgba(col,emerge*nb*depth*radialBoost*(.19+.15*f+energy*.14));
      ctx.beginPath();ctx.arc(p.x,p.y,(.82+n.size*.70)*p.s*(1+energy*.16),0,TAU);ctx.fill();
      if(depth>.74&&f>.82){
        ctx.fillStyle=rgba(C.white,emerge*nb*.18);ctx.beginPath();ctx.arc(p.x,p.y,2.35,0,TAU);ctx.fill();
      }
    }

    if(structure>.001){
      // Soft continuous base: enough to read the globe, never a hard perfect ring.
      for(let k=0;k<3;k++){
        const rr=R*(.958+k*.010);
        const col=k===0?C.cyan:k===1?C.violet:C.magenta;
        ctx.strokeStyle=rgba(col,structure*(.072+energy*.036));
        ctx.lineWidth=.72+k*.18;
        ctx.beginPath();ctx.arc(cx,cy,rr,0,TAU);ctx.stroke();
      }

      // Electric shell fragments: shorter, brighter, irregular, reference-like.
      for(let k=0;k<42;k++){
        const phase=k*TAU/42+Math.sin(k*2.37)*.052+rot*.08;
        const built=smooth(.42+(k%11)*.040,.56+(k%11)*.040,build);
        if(built<=.001)continue;
        const span=.040+(k%6)*.019;
        const rr=R*(.975+(k%4)*.005);
        const pulse=.54+.46*Math.sin(t*(.52+(k%5)*.055)+k*.83);
        const col=k%7===0?C.white:k%4===0?C.magenta:k%3===0?C.cyan:C.violet;

        // glow pass
        ctx.strokeStyle=rgba(col,structure*built*(.085+.090*pulse+energy*.065));
        ctx.lineWidth=3.0+(k%3)*.50+energy*.70;
        ctx.beginPath();ctx.arc(cx,cy,rr,phase,phase+span);ctx.stroke();

        // crisp pass
        ctx.strokeStyle=rgba(col,structure*built*(.25+.18*pulse+energy*.13));
        ctx.lineWidth=.85+(k%3)*.24+energy*.25;
        ctx.beginPath();ctx.arc(cx,cy,rr,phase,phase+span);ctx.stroke();

        const a=phase+span*.52;
        const hx=cx+Math.cos(a)*rr,hy=cy+Math.sin(a)*rr;
        const hot=1.3+(k%5)*.30+energy*.55;
        ctx.fillStyle=rgba(C.white,structure*built*(.12+.16*pulse+energy*.08));
        ctx.beginPath();ctx.arc(hx,hy,hot*1.8,0,TAU);ctx.fill();
        ctx.fillStyle=rgba(col,structure*built*(.32+.22*pulse+energy*.12));
        ctx.beginPath();ctx.arc(hx,hy,hot,0,TAU);ctx.fill();
      }

      // Interior curved traces: more numerous but lower alpha.
      for(let k=0;k<16;k++){
        const a=k*TAU/16+rot*.26;
        ctx.save();ctx.translate(cx,cy);ctx.rotate(a*.15);
        ctx.strokeStyle=rgba(
          k%4===0?C.magenta:k%3===0?C.cyan:C.violet,
          structure*(.040+energy*.020)
        );
        ctx.lineWidth=.50+(k%3)*.07;
        ctx.beginPath();
        ctx.ellipse(0,0,R*.945,R*(.115+.041*(k%8)),0,0,TAU);
        ctx.stroke();
        ctx.restore();
      }

      // Thin exterior bloom.
      ctx.strokeStyle=rgba(C.white,structure*(.080+energy*.050));
      ctx.lineWidth=1.05+energy*.35;
      ctx.beginPath();ctx.arc(cx,cy,R*.994,0,TAU);ctx.stroke();
    }
    ctx.restore();
  }

  function drawConstructionActivity(t,build,age){
    if(build<=.035 || build>=.95)return;

    const phaseLife=.55+.45*Math.sin(t*.85);
    const ageGain=.72+.28*Math.min(1,age/5);

    ctx.save();
    ctx.globalCompositeOperation='lighter';

    // Rotating assembly arcs around the not-yet-finished membrane.
    const arcCount=7;
    for(let i=0;i<arcCount;i++){
      const a=(t*(.055+i*.006)+i*TAU/arcCount)%TAU;
      const span=.055+.020*(i%3);
      const rr=R*(.982+(i%2)*.008);
      const col=i%3===0?C.cyan:i%3===1?C.violet:C.magenta;

      ctx.strokeStyle=rgba(col,(.060+.050*phaseLife)*ageGain);
      ctx.lineWidth=1.0+(i%2)*.35;
      ctx.beginPath();
      ctx.arc(cx,cy,rr,a,a+span);
      ctx.stroke();

      const hx=cx+Math.cos(a+span)*rr;
      const hy=cy+Math.sin(a+span)*rr;
      ctx.fillStyle=rgba(C.white,(.10+.10*phaseLife)*ageGain);
      ctx.beginPath();
      ctx.arc(hx,hy,1.25,0,TAU);
      ctx.fill();
    }

    // Pending nodes flicker as "construction targets". They do NOT become
    // permanently visible until their real birth threshold is reached.
    let shown=0;
    const rx=-.055+Math.sin(t*.14)*.018;
    for(let i=0;i<nodes.length && shown<34;i++){
      const n=nodes[i];
      if(n.birth<=build || n.birth>build+.17)continue;
      if(((i*17)%7)>2)continue;

      const p=project(rotatePoint(n,rot,rx));
      const pulse=.5+.5*Math.sin(t*1.7+n.phase+i*.09);
      const col=n.color<.42?C.cyan:n.color<.74?C.violet:C.magenta;
      const near=1-clamp((n.birth-build)/.17);

      ctx.fillStyle=rgba(col,(.025+.070*pulse)*near*ageGain);
      ctx.beginPath();
      ctx.arc(p.x,p.y,.75+1.25*pulse,0,TAU);
      ctx.fill();

      shown++;
    }

    // Moving assembly packets travel along topology that is close to its
    // real threshold. This keeps a long STRUCTURATION stage visibly alive.
    let packets=0;
    for(let i=0;i<edges.length && packets<22;i++){
      const e=edges[i];
      if(e.birth<=build || e.birth>build+.12)continue;
      if(((i*13)%9)>2)continue;

      const a=project(rotatePoint(nodes[e.i],rot,-.055));
      const b=project(rotatePoint(nodes[e.j],rot,-.055));
      const q=(t*(.18+e.speed*.10)+e.phase)%1;
      const x=lerp(a.x,b.x,q);
      const y=lerp(a.y,b.y,q);
      const col=e.phase>.52?C.magenta:C.cyan;

      ctx.fillStyle=rgba(col,.055+.095*phaseLife);
      ctx.beginPath();
      ctx.arc(x,y,.75+phaseLife*.65,0,TAU);
      ctx.fill();

      packets++;
    }

    // Small central assembly pulse while structure is incomplete.
    const pulseR=R*(.12+.018*Math.sin(t*.95));
    const g=ctx.createRadialGradient(cx,cy,0,cx,cy,pulseR);
    g.addColorStop(0,rgba(C.white,.025*ageGain));
    g.addColorStop(.28,rgba(C.cyan,.032*ageGain));
    g.addColorStop(.62,rgba(C.violet,.020*ageGain));
    g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;
    ctx.beginPath();
    ctx.arc(cx,cy,pulseR,0,TAU);
    ctx.fill();

    ctx.restore();
  }

  function drawTendrils(t,build,energy){
    ctx.save();ctx.globalCompositeOperation='lighter';

    for(let idx=0;idx<tendrils.length;idx++){
      const d=tendrils[idx];
      const v=smooth(d.birth,d.birth+.14,build);if(v<=.001)continue;

      const a=d.angle+Math.sin(t*.14+d.phase)*.022;
      const sx=cx+Math.cos(a)*R*.982,sy=cy+Math.sin(a)*R*.982;
      const ex=cx+Math.cos(a)*R*(1+d.len),ey=cy+Math.sin(a)*R*(1+d.len*.72);

      const nx=Math.cos(a+Math.PI/2),ny=Math.sin(a+Math.PI/2);
      const bend=R*d.bend*.30;
      const c1x=lerp(sx,ex,.32)+nx*bend,c1y=lerp(sy,ey,.32)+ny*bend;
      const c2x=lerp(sx,ex,.72)-nx*bend*.48,c2y=lerp(sy,ey,.72)-ny*bend*.48;

      const col=d.color<.42?C.cyan:d.color<.74?C.violet:C.magenta;
      const pulse=.55+.45*Math.sin(t*.48+d.phase+idx*.31);

      // very soft halo
      ctx.strokeStyle=rgba(col,v*(.028+energy*.028));
      ctx.lineWidth=2.2+energy*.7;
      ctx.beginPath();ctx.moveTo(sx,sy);ctx.bezierCurveTo(c1x,c1y,c2x,c2y,ex,ey);ctx.stroke();

      // crisp dendrite
      ctx.strokeStyle=rgba(col,v*(.20+.11*pulse+energy*.075));
      ctx.lineWidth=.72+energy*.26;
      ctx.beginPath();ctx.moveTo(sx,sy);ctx.bezierCurveTo(c1x,c1y,c2x,c2y,ex,ey);ctx.stroke();

      // terminal neuron: small halo + ring + point
      ctx.strokeStyle=rgba(col,v*(.42+energy*.14));
      ctx.lineWidth=.85;
      ctx.beginPath();ctx.arc(ex,ey,3.1+energy*.7,0,TAU);ctx.stroke();

      ctx.fillStyle=rgba(C.white,v*(.24+energy*.10));
      ctx.beginPath();ctx.arc(ex,ey,.95+energy*.35,0,TAU);ctx.fill();
    }
    ctx.restore();
  }

  function drawPedestal(t,build,energy){
    const v=smooth(.46,.82,build);if(v<=.001)return;
    const y=cy+R*1.095;
    ctx.save();ctx.globalCompositeOperation='lighter';

    // broad floor glow
    ctx.save();ctx.translate(cx,y);ctx.scale(1,.15);
    const floor=ctx.createRadialGradient(0,0,R*.12,0,0,R*1.22);
    floor.addColorStop(0,rgba(C.white,v*(.030+energy*.018)));
    floor.addColorStop(.22,rgba(C.violet,v*(.085+energy*.040)));
    floor.addColorStop(.50,rgba(C.blue,v*(.048+energy*.032)));
    floor.addColorStop(.74,rgba(C.magenta,v*(.030+energy*.024)));
    floor.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=floor;ctx.beginPath();ctx.arc(0,0,R*1.22,0,TAU);ctx.fill();
    ctx.restore();

    for(let i=0;i<18;i++){
      const rr=R*(.24+i*.058),hh=R*(.018+i*.0018);
      const p=.5+.5*Math.sin(t*.31+i*.43);
      const col=i%5===0?C.cyan:i%3===0?C.magenta:C.violet;
      ctx.strokeStyle=rgba(col,v*(.052+.052*p+energy*.026));
      ctx.lineWidth=.52+(i%4)*.12;
      ctx.beginPath();ctx.ellipse(cx,y,rr,hh,0,0,TAU);ctx.stroke();
    }

    // three main holographic bands
    for(const [rr,hh,col] of [
      [.42,.038,C.violet],[.62,.047,C.magenta],[.86,.060,C.cyan]
    ]){
      ctx.strokeStyle=rgba(col,v*(.15+energy*.052));
      ctx.lineWidth=1.0;
      ctx.beginPath();ctx.ellipse(cx,y,R*rr,R*hh,0,0,TAU);ctx.stroke();
    }

    // core energy point
    const g=ctx.createRadialGradient(cx,y,0,cx,y,R*.34);
    g.addColorStop(0,rgba(C.white,v*(.16+energy*.05)));
    g.addColorStop(.18,rgba(C.violet,v*(.12+energy*.05)));
    g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;ctx.beginPath();ctx.ellipse(cx,y,R*.34,R*.055,0,0,TAU);ctx.fill();

    ctx.restore();
  }

  function render(now){
    requestAnimationFrame(render);
    const auraVisualFps=window.AuraVisualBudget?.fps('official-orb',40)||40;
    if(now-lastFrame<1000/auraVisualFps)return;lastFrame=now;
    const dt=clamp((now-last)/1000,0,.05);last=now;const t=now/1000;
    const state=getState(),raw=getPcm(),trueBuild=getBuild();

    if(Math.abs(trueBuild-auraBuildLastValue)>.0005){
      auraBuildLastValue=trueBuild;
      auraBuildChangedAt=now;
    }
    const buildAge=Math.max(0,(now-auraBuildChangedAt)/1000);

    if(!auraVisualInitialized){
      auraVisualBuild=Math.min(trueBuild,.015);
      auraVisualInitialized=true;
    }

    // Smooth only the VISUAL construction.
    // Large runtime jumps (e.g. 56 -> 86) unfold over ~1-2 seconds.
    // Final 100% converges faster so the orb is complete before UI reveal.
    const delta=trueBuild-auraVisualBuild;
    if(delta>0.00001){
      let buildTau=trueBuild>=.995 ? .34 :
                   delta>=.22      ? .72 :
                   delta>=.10      ? .58 :
                                     .42;
      const buildK=1-Math.exp(-dt/buildTau);
      auraVisualBuild+=delta*buildK;
      if(auraVisualBuild>trueBuild)auraVisualBuild=trueBuild;
    }else if(delta<-.00001){
      // Defensive monotonic recovery; runtime should never move backwards,
      // but if it does, follow it without overshoot.
      const buildK=1-Math.exp(-dt/.28);
      auraVisualBuild+=delta*buildK;
      if(auraVisualBuild<trueBuild)auraVisualBuild=trueBuild;
    }

    const build=clamp(auraVisualBuild,0,trueBuild);

    const tau=raw>pcm?.040:.19,k=1-Math.exp(-dt/tau);pcm+=(raw-pcm)*k;
    accent=Math.max(accent*Math.exp(-dt/.12),Math.max(0,raw-prevPcm)*1.8);prevPcm=raw;

    // Visual floor only: a SPEAKING frame remains visibly alive even if a screenshot
    // lands between PCM packets. Actual telemetry and audio path remain untouched.
    const visualEnergy=state==='SPEAKING'?Math.max(.24,pcm):pcm;

    rot+=dt*(.025+(/THINKING|ANALYZING|SEARCHING/.test(state)?.042:0)+visualEnergy*.010);
    ctx.clearRect(0,0,cssW,cssH);
    drawBackgroundParticles(t,build);
    drawWaveform(t,build,state,visualEnergy);
    drawPedestal(t,build,visualEnergy);
    drawHalo(build,visualEnergy);
    drawGlobe(t,build,state,visualEnergy);
    drawConstructionActivity(t,build,buildAge);
    // AURA P0.8.5.4.6.9.5 — clean orb silhouette.
    // External tendrils intentionally disabled; internal neural topology is preserved.

    // Brief stabilization bloom generated from the actual final checkpoint.
    if(trueBuild>=.995 && build>.90){
      const completion=smooth(.90,.995,build);
      ctx.save();
      ctx.globalCompositeOperation='lighter';
      const rg=ctx.createRadialGradient(cx,cy,R*.55,cx,cy,R*1.08);
      rg.addColorStop(0,'rgba(255,255,255,0)');
      rg.addColorStop(.72,rgba(C.violet,.018*completion));
      rg.addColorStop(.94,rgba(C.cyan,.045*completion));
      rg.addColorStop(1,'rgba(0,0,0,0)');
      ctx.fillStyle=rg;
      ctx.beginPath();ctx.arc(cx,cy,R*1.09,0,TAU);ctx.fill();
      ctx.restore();
    }

    const logoBuild=smooth(.28,.66,build),breath=.5+.5*Math.sin(t*.72),speak=state==='SPEAKING'?visualEnergy*.040:0;
    lockup.style.opacity=String(clamp(logoBuild*(.94+visualEnergy*.06),0,1));
    lockup.style.transform=`translate(-50%,-50%) scale(${(.82+logoBuild*.18+breath*.004+speak+accent*.010).toFixed(4)})`;
    lockup.dataset.state=state;
    removeObsolete();quiesceOldCanvases();
  }

  // Keep future legacy canvases under control without touching our own canvas.
  new MutationObserver(()=>{removeObsolete();quiesceOldCanvases()}).observe(stage,{childList:true,subtree:false});
  requestAnimationFrame(render);
})();