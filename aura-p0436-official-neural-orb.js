/* AURA P0.4.3.6 OFFICIAL VECTOR NEURAL ORB */
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
  const NODE_COUNT=286;
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
      birth:.02+rnd()*.62,
      color:rnd()
    });
  }

  const cand=[];
  for(let i=0;i<NODE_COUNT;i++)for(let j=i+1;j<NODE_COUNT;j++){
    const a=nodes[i],b=nodes[j];
    const dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z;
    const d=Math.sqrt(dx*dx+dy*dy+dz*dz);
    if(d<.225)cand.push([d,i,j,rnd()]);
  }
  cand.sort((a,b)=>a[0]-b[0]);
  const edges=[],deg=new Uint8Array(NODE_COUNT);
  for(const [d,i,j,p] of cand){
    if(edges.length>=560)break;
    if(deg[i]>=6||deg[j]>=6)continue;
    deg[i]++;deg[j]++;
    edges.push({i,j,phase:p,birth:.07+p*.58,speed:.12+rnd()*.34});
  }

  const stars=Array.from({length:150},()=>({
    x:(rnd()-.5)*2.35,y:(rnd()-.5)*2.05,r:.25+rnd()*1.25,
    phase:rnd()*TAU,color:rnd(),birth:rnd()*.55
  }));

  const tendrils=Array.from({length:22},(_,i)=>({
    angle:i*TAU/22+(rnd()-.5)*.16,
    len:.18+rnd()*.30,
    bend:(rnd()-.5)*.42,
    phase:rnd()*TAU,
    color:rnd(),
    birth:.46+rnd()*.25
  }));

  let cssW=1,cssH=1,dpr=1,cx=0,cy=0,R=100;
  let rot=0,last=performance.now(),lastFrame=0;
  let pcm=0,prevPcm=0,accent=0;

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
    const lw=R*.62;
    lockup.style.width=lw+'px';
    lockup.style.height=lw*1.18+'px';
    lockup.style.left=cx+'px'; lockup.style.top=(cy+R*.03)+'px';
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
      const a=v*b*(.040+.080*(.5+.5*Math.sin(t*.9+s.phase)));
      ctx.fillStyle=rgba(col,a);ctx.beginPath();ctx.arc(x,y,s.r,0,TAU);ctx.fill();
    }
    ctx.restore();
  }

  function drawWaveform(t,build,state,energy){
    const v=smooth(.48,.82,build);if(v<=.001)return;
    const width=R*1.75, mid=cy, speaking=state==='SPEAKING';
    const amp=R*(.014+(speaking?energy*.115:.010));
    ctx.save();ctx.globalCompositeOperation='lighter';
    const g=ctx.createLinearGradient(cx-width,mid,cx+width,mid);
    g.addColorStop(0,'rgba(218,92,255,0)');
    g.addColorStop(.15,rgba(C.magenta,v*(.18+energy*.10)));
    g.addColorStop(.48,rgba(C.violet,v*(.08+energy*.06)));
    g.addColorStop(.52,rgba(C.cyan,v*(.08+energy*.06)));
    g.addColorStop(.85,rgba(C.cyan,v*(.20+energy*.12)));
    g.addColorStop(1,'rgba(99,243,255,0)');
    ctx.strokeStyle=g;ctx.lineWidth=.8+energy*.85;ctx.beginPath();
    const N=220;
    for(let i=0;i<=N;i++){
      const u=i/N,x=cx-width+u*width*2,dist=Math.abs(u-.5)*2;
      const side=.28+.98*smooth(.08,.94,dist);
      const m=Math.sin(u*TAU*17-t*(1.4+energy*2.8))*.48+
              Math.sin(u*TAU*29+t*.73)*.28+
              Math.sin(u*TAU*47-t*.31)*.16;
      const y=mid+m*amp*side;
      i?ctx.lineTo(x,y):ctx.moveTo(x,y);
    }
    ctx.stroke();
    for(const side of [-1,1])for(let i=0;i<34;i++){
      const u=i/33,x=cx+side*(R*1.12+u*R*.55),p=.5+.5*Math.sin(t*(1.55+u*.9)+i*.82);
      const hh=R*(.010+.040*p+energy*.080*(.3+.7*p));
      const col=side<0?C.magenta:C.cyan;
      ctx.strokeStyle=rgba(col,v*(.045+.085*p+energy*.07));ctx.lineWidth=1;
      ctx.beginPath();ctx.moveTo(x,mid-hh);ctx.lineTo(x,mid+hh);ctx.stroke();
    }
    ctx.restore();
  }

  function drawHalo(build,energy){
    const v=smooth(.34,.72,build);if(v<=.001)return;
    const g=ctx.createRadialGradient(cx,cy,R*.15,cx,cy,R*1.20);
    g.addColorStop(0,rgba(C.violet,v*(.030+energy*.025)));
    g.addColorStop(.55,rgba(C.blue,v*(.014+energy*.015)));
    g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;ctx.beginPath();ctx.arc(cx,cy,R*1.22,0,TAU);ctx.fill();
  }

  function drawGlobe(t,build,state,energy){
    const emerge=smooth(.03,.20,build), aggregate=smooth(.12,.50,build), structure=smooth(.28,.70,build);
    if(emerge<=.001)return;
    const rx=-.055+Math.sin(t*.14)*.018;
    const pts=nodes.map(n=>project(rotatePoint(n,rot,rx)));
    ctx.save();ctx.globalCompositeOperation='lighter';

    for(const e of edges){
      const eb=smooth(e.birth,e.birth+.16,build);if(eb<=.001)continue;
      const a=pts[e.i],b=pts[e.j],depth=clamp(.42+(a.z+b.z)*.38,.10,1);
      const p=.5+.5*Math.sin(t*(.72+e.speed)+e.phase*TAU);
      const stateBoost=/THINKING|ANALYZING|SEARCHING/.test(state)?.060*p:0;
      const alpha=aggregate*eb*depth*(.052+energy*(.050+.060*p)+stateBoost);
      const col=mix(C.magenta,C.cyan,clamp(((a.x+b.x)*.5-cx)/(R*1.55)*.5+.5));
      ctx.strokeStyle=rgba(col,alpha);ctx.lineWidth=.55+depth*.70+energy*.22;
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
      ctx.fillStyle=rgba(col,emerge*nb*depth*(.12+.10*f+energy*.10));
      ctx.beginPath();ctx.arc(p.x,p.y,(.70+n.size*.62)*p.s*(1+energy*.14),0,TAU);ctx.fill();
      if(depth>.74&&f>.82){
        ctx.fillStyle=rgba(C.white,emerge*nb*.10);ctx.beginPath();ctx.arc(p.x,p.y,2.1,0,TAU);ctx.fill();
      }
    }

    if(structure>.001){
      // Bright spherical membrane, several slightly offset shells.
      for(let k=0;k<6;k++){
        const rr=R*(.953+k*.008),col=k%3===0?C.cyan:k%3===1?C.violet:C.magenta;
        ctx.strokeStyle=rgba(col,structure*(.070+energy*.045));ctx.lineWidth=.75+k*.12;
        ctx.beginPath();ctx.arc(cx,cy,rr,0,TAU);ctx.stroke();
      }
      // Curved longitude/latitude traces to make the volume unmistakably spherical.
      for(let k=0;k<10;k++){
        const a=k*TAU/10+rot*.35;
        ctx.save();ctx.translate(cx,cy);ctx.rotate(a*.18);
        ctx.strokeStyle=rgba(k%2?C.violet:C.cyan,structure*(.035+energy*.018));ctx.lineWidth=.55;
        ctx.beginPath();ctx.ellipse(0,0,R*.94,R*(.18+.055*(k%5)),0,0,TAU);ctx.stroke();ctx.restore();
      }
      // Exterior glow ring.
      ctx.strokeStyle=rgba(C.white,structure*(.045+energy*.035));ctx.lineWidth=1.15;
      ctx.beginPath();ctx.arc(cx,cy,R*.986,0,TAU);ctx.stroke();
    }
    ctx.restore();
  }

  function drawTendrils(t,build,energy){
    ctx.save();ctx.globalCompositeOperation='lighter';
    for(const d of tendrils){
      const v=smooth(d.birth,d.birth+.18,build);if(v<=.001)continue;
      const a=d.angle+Math.sin(t*.12+d.phase)*.025;
      const sx=cx+Math.cos(a)*R*.96,sy=cy+Math.sin(a)*R*.96;
      const ex=cx+Math.cos(a)*R*(1+d.len),ey=cy+Math.sin(a)*R*(1+d.len*.62);
      const nx=Math.cos(a+Math.PI/2),ny=Math.sin(a+Math.PI/2),bend=R*d.bend*.42;
      const c1x=lerp(sx,ex,.34)+nx*bend,c1y=lerp(sy,ey,.34)+ny*bend;
      const c2x=lerp(sx,ex,.72)-nx*bend*.55,c2y=lerp(sy,ey,.72)-ny*bend*.55;
      const col=d.color<.44?C.cyan:d.color<.74?C.violet:C.magenta;
      ctx.strokeStyle=rgba(col,v*(.080+energy*.055));ctx.lineWidth=.75+energy*.25;
      ctx.beginPath();ctx.moveTo(sx,sy);ctx.bezierCurveTo(c1x,c1y,c2x,c2y,ex,ey);ctx.stroke();
      ctx.strokeStyle=rgba(col,v*(.30+energy*.10));ctx.lineWidth=1;
      ctx.beginPath();ctx.arc(ex,ey,3.3+energy*1.1,0,TAU);ctx.stroke();
      ctx.fillStyle=rgba(C.white,v*(.16+energy*.10));ctx.beginPath();ctx.arc(ex,ey,1.0+energy*.6,0,TAU);ctx.fill();
    }
    ctx.restore();
  }

  function drawPedestal(t,build,energy){
    const v=smooth(.58,.92,build);if(v<=.001)return;
    const y=cy+R*1.06;
    ctx.save();ctx.globalCompositeOperation='lighter';
    for(let i=0;i<12;i++){
      const rr=R*(.32+i*.073),hh=R*(.022+i*.0018),p=.5+.5*Math.sin(t*.28+i*.52);
      const col=i%3===0?C.cyan:i%3===1?C.violet:C.magenta;
      ctx.strokeStyle=rgba(col,v*(.035+.025*p+energy*.018));ctx.lineWidth=.55+(i%3)*.16;
      ctx.beginPath();ctx.ellipse(cx,y,rr,hh,0,0,TAU);ctx.stroke();
    }
    ctx.strokeStyle=rgba(C.white,v*(.050+energy*.018));ctx.lineWidth=.65;
    ctx.beginPath();ctx.ellipse(cx,y,R*.60,R*.053,0,0,TAU);ctx.stroke();
    ctx.restore();
  }

  function render(now){
    requestAnimationFrame(render);
    if(now-lastFrame<1000/40)return;lastFrame=now;
    const dt=clamp((now-last)/1000,0,.05);last=now;const t=now/1000;
    const state=getState(),raw=getPcm(),build=getBuild();
    const tau=raw>pcm?.040:.19,k=1-Math.exp(-dt/tau);pcm+=(raw-pcm)*k;
    accent=Math.max(accent*Math.exp(-dt/.12),Math.max(0,raw-prevPcm)*1.8);prevPcm=raw;
    rot+=dt*(.025+(/THINKING|ANALYZING|SEARCHING/.test(state)?.042:0)+pcm*.010);
    ctx.clearRect(0,0,cssW,cssH);
    drawBackgroundParticles(t,build);drawWaveform(t,build,state,pcm);drawPedestal(t,build,pcm);
    drawHalo(build,pcm);drawGlobe(t,build,state,pcm);drawTendrils(t,build,pcm);
    const logoBuild=smooth(.38,.74,build),breath=.5+.5*Math.sin(t*.72),speak=state==='SPEAKING'?pcm*.045:0;
    lockup.style.opacity=String(clamp(logoBuild*(.84+pcm*.10),0,1));
    lockup.style.transform=`translate(-50%,-50%) scale(${(.76+logoBuild*.24+breath*.006+speak+accent*.012).toFixed(4)})`;
    lockup.dataset.state=state;
    removeObsolete();quiesceOldCanvases();
  }

  // Keep future legacy canvases under control without touching our own canvas.
  new MutationObserver(()=>{removeObsolete();quiesceOldCanvases()}).observe(stage,{childList:true,subtree:false});
  requestAnimationFrame(render);
})();