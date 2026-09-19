/* AURA P0.4.3.4 PROCEDURAL REFERENCE ORB REBUILD */
(() => {
  'use strict';
  if (window.__AURA_P0434_REFERENCE_REBUILD__) return;
  window.__AURA_P0434_REFERENCE_REBUILD__ = true;

  const stage = document.getElementById('stage');
  if (!stage) return;

  // Kill previous wrong/image identity layers.
  const cleanup = () => {
    stage.querySelectorAll(
      '.aura-ref-orb-layer,.aura-svg-identity-layer'
    ).forEach(el => el.remove());
  };
  cleanup();

  const canvas = document.createElement('canvas');
  canvas.className = 'aura-reference-procedural-canvas';
  canvas.setAttribute('aria-hidden','true');
  stage.appendChild(canvas);

  const logo = document.createElement('img');
  logo.className = 'aura-reference-logo';
  logo.src = '/assets/aura-logo-official-p0434.svg?v=p0434-20260816';
  logo.alt = '';
  logo.decoding = 'async';
  stage.appendChild(logo);

  // Replace header mark with official A symbol.
  const brandMark = document.querySelector('.brand-mark');
  if (brandMark) {
    const icon = document.createElement('img');
    icon.className = 'aura-reference-header-icon';
    icon.src = '/assets/aura-logo-icon-p0434.svg?v=p0434-20260816';
    icon.alt = '';
    icon.decoding = 'async';
    brandMark.replaceChildren(icon);
    brandMark.classList.add('aura-reference-brand-active');
  }

  const ctx = canvas.getContext('2d', {
    alpha: true,
    desynchronized: true
  });
  if (!ctx) return;

  const TAU = Math.PI * 2;
  const clamp = (v,a=0,b=1) => Math.max(a,Math.min(b,v));
  const lerp = (a,b,t) => a+(b-a)*t;
  const smooth = (a,b,x) => {
    const t=clamp((x-a)/Math.max(1e-6,b-a));
    return t*t*(3-2*t);
  };

  const C = {
    cyan:[54,194,255],
    cyan2:[84,217,255],
    blue:[66,123,255],
    violet:[139,92,255],
    purple:[173,75,255],
    magenta:[231,73,255],
    white:[235,248,255]
  };
  const rgba=(c,a)=>`rgba(${c[0]|0},${c[1]|0},${c[2]|0},${clamp(a)})`;
  const mix=(a,b,t)=>[
    lerp(a[0],b[0],t),
    lerp(a[1],b[1],t),
    lerp(a[2],b[2],t)
  ];

  let seed = 0xA0434;
  const rnd = () => {
    seed=(seed*1664525+1013904223)>>>0;
    return seed/4294967296;
  };

  // Reference-inspired neural globe.
  const NODE_COUNT=226;
  const nodes=[];
  const golden=Math.PI*(3-Math.sqrt(5));
  for(let i=0;i<NODE_COUNT;i++){
    const u=(i+.5)/NODE_COUNT;
    const y=1-2*u;
    const rr=Math.sqrt(Math.max(0,1-y*y));
    const a=i*golden+(rnd()-.5)*.15;
    const shell=.70+rnd()*.28;
    nodes.push({
      x:Math.cos(a)*rr*shell,
      y:y*shell,
      z:Math.sin(a)*rr*shell,
      size:.55+rnd()*1.25,
      phase:rnd()*TAU,
      birth:.02+rnd()*.68,
      color:rnd()
    });
  }

  const edges=[];
  const deg=new Array(NODE_COUNT).fill(0);
  const cand=[];
  for(let i=0;i<NODE_COUNT;i++){
    for(let j=i+1;j<NODE_COUNT;j++){
      const a=nodes[i],b=nodes[j];
      const dx=a.x-b.x,dy=a.y-b.y,dz=a.z-b.z;
      const d=Math.sqrt(dx*dx+dy*dy+dz*dz);
      if(d<.235)cand.push([d,i,j,rnd()]);
    }
  }
  cand.sort((a,b)=>a[0]-b[0]);
  for(const [d,i,j,p] of cand){
    if(edges.length>=430)break;
    if(deg[i]>=5||deg[j]>=5)continue;
    deg[i]++;deg[j]++;
    edges.push({
      i,j,phase:p,
      birth:.09+p*.56,
      speed:.14+rnd()*.28
    });
  }

  const stars=Array.from({length:90},()=>({
    a:rnd()*TAU,
    r:.15+rnd()*1.12,
    y:(rnd()-.5)*1.72,
    size:.35+rnd()*1.2,
    phase:rnd()*TAU,
    color:rnd()
  }));

  const tendrils=Array.from({length:18},(_,i)=>({
    angle:i*TAU/18+(rnd()-.5)*.22,
    len:.20+rnd()*.23,
    bend:(rnd()-.5)*.42,
    phase:rnd()*TAU,
    speed:.18+rnd()*.25,
    color:rnd()
  }));

  let cssW=1,cssH=1,dpr=1,cx=0,cy=0,R=100;
  let rot=0,last=performance.now(),lastFrame=0;
  let pcm=0,prevPcm=0,accent=0;

  function resize(){
    const r=stage.getBoundingClientRect();
    cssW=Math.max(1,r.width);
    cssH=Math.max(1,r.height);
    dpr=Math.min(1.35,Math.max(1,window.devicePixelRatio||1));
    canvas.width=Math.round(cssW*dpr);
    canvas.height=Math.round(cssH*dpr);
    canvas.style.width=cssW+'px';
    canvas.style.height=cssH+'px';
    ctx.setTransform(dpr,0,0,dpr,0,0);
    cx=cssW*.5;
    cy=cssH*.465;
    R=Math.min(cssW,cssH)*.295;
    const logoSize=R*.72;
    logo.style.width=logoSize+'px';
    logo.style.height=logoSize*.92+'px';
    logo.style.left=cx+'px';
    logo.style.top=cy+'px';
  }

  if(typeof ResizeObserver!=='undefined'){
    new ResizeObserver(resize).observe(stage);
  }else{
    window.addEventListener('resize',resize,{passive:true});
  }
  resize();

  function getBuild(){
    const card=document.getElementById('bootCard');
    if(card?.classList?.contains('hidden') ||
       document.documentElement.classList.contains('aura-p043-complete')) return 1;
    const el=document.getElementById('bootPercent');
    const n=parseFloat(String(el?.textContent||'100').replace(',','.'));
    return Number.isFinite(n)?clamp(n/100):1;
  }
  function getPcm(){
    const el=document.getElementById('pcmValue');
    const n=parseFloat(String(el?.textContent||'0').replace(',','.'));
    return Number.isFinite(n)?clamp(n):0;
  }
  function getState(){
    return String(document.body?.dataset?.state||'IDLE').toUpperCase();
  }

  function rotatePoint(p,ry,rx){
    const cyy=Math.cos(ry),syy=Math.sin(ry);
    let x=p.x*cyy+p.z*syy;
    let z=-p.x*syy+p.z*cyy;
    const cxx=Math.cos(rx),sxx=Math.sin(rx);
    const y=p.y*cxx-z*sxx;
    z=p.y*sxx+z*cxx;
    return{x,y,z};
  }
  function project(p,scale=1){
    const persp=1/(1+p.z*.12);
    return{
      x:cx+p.x*R*scale*persp,
      y:cy+p.y*R*scale*persp,
      z:p.z,
      s:persp
    };
  }

  function drawStars(t,build){
    const v=smooth(.02,.35,build);
    if(v<=.001)return;
    ctx.save();
    ctx.globalCompositeOperation='lighter';
    for(const s of stars){
      const a=s.a+t*.010*Math.sin(s.phase);
      const x=cx+Math.cos(a)*R*s.r;
      const y=cy+s.y*R*.62+Math.sin(t*.42+s.phase)*R*.006;
      const c=s.color<.45?C.cyan:s.color<.78?C.violet:C.magenta;
      const alpha=v*(.035+.055*(.5+.5*Math.sin(t*.8+s.phase)));
      ctx.fillStyle=rgba(c,alpha);
      ctx.beginPath();
      ctx.arc(x,y,s.size,0,TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawGlobe(t,build,state,energy){
    const emerge=smooth(.04,.22,build);
    const aggregate=smooth(.13,.50,build);
    const structure=smooth(.30,.72,build);
    if(emerge<=.001)return;

    const pts=new Array(nodes.length);
    const rx=-.06+Math.sin(t*.15)*.018;
    for(let i=0;i<nodes.length;i++){
      pts[i]=project(rotatePoint(nodes[i],rot,rx),1);
    }

    ctx.save();
    ctx.globalCompositeOperation='lighter';

    // Internal mesh
    for(const e of edges){
      const eb=smooth(e.birth,e.birth+.18,build);
      if(eb<=.001)continue;
      const a=pts[e.i],b=pts[e.j];
      const depth=clamp(.45+(a.z+b.z)*.34,.10,1);
      const pulse=.5+.5*Math.sin(t*(.75+e.speed)+e.phase*TAU);
      const voice=energy*(.025+.055*pulse);
      const think=/THINKING|SEARCHING|ANALYZING/.test(state)?.055*pulse:0;
      const alpha=aggregate*eb*depth*(.030+voice+think);
      const mid=(a.x+b.x)*.5;
      const colorT=clamp((mid-cx)/(R*1.4)*.5+.5);
      const col=mix(C.magenta,C.cyan,colorT);
      ctx.strokeStyle=rgba(col,alpha);
      ctx.lineWidth=.45+depth*.55+energy*.20;
      ctx.beginPath();
      ctx.moveTo(a.x,a.y);
      ctx.lineTo(b.x,b.y);
      ctx.stroke();

      if(build<.96||energy>.05){
        const q=(t*(.09+e.speed*.14)+e.phase)%1;
        if(q<.35){
          const qq=q/.35;
          const x=lerp(a.x,b.x,qq);
          const y=lerp(a.y,b.y,qq);
          ctx.fillStyle=rgba(
            energy>.05?C.white:(e.phase>.5?C.magenta:C.cyan),
            aggregate*eb*depth*(.05+energy*.12)
          );
          ctx.beginPath();
          ctx.arc(x,y,.55+energy*.8,0,TAU);
          ctx.fill();
        }
      }
    }

    // Nodes
    for(let i=0;i<nodes.length;i++){
      const n=nodes[i];
      const nb=smooth(n.birth,n.birth+.14,build);
      if(nb<=.001)continue;
      const p=pts[i];
      const depth=clamp(.52+p.z*.48,.16,1);
      const flick=.45+.55*Math.sin(t*.55+n.phase);
      const c=n.color<.45?C.cyan2:n.color<.76?C.violet:C.magenta;
      const alpha=emerge*nb*depth*(.075+.075*flick+energy*.085);
      ctx.fillStyle=rgba(c,alpha);
      ctx.beginPath();
      ctx.arc(p.x,p.y,(.50+n.size*.58)*p.s*(1+energy*.12),0,TAU);
      ctx.fill();
    }

    // Multi-layer spherical membrane like reference
    if(structure>.001){
      for(let ring=0;ring<5;ring++){
        const rr=R*(.955+ring*.008);
        const col=ring%3===0?C.cyan:ring%3===1?C.violet:C.magenta;
        const base=structure*(.035+energy*.022);
        ctx.strokeStyle=rgba(col,base);
        ctx.lineWidth=.65+ring*.15;
        ctx.beginPath();
        ctx.arc(cx,cy,rr,0,TAU);
        ctx.stroke();
      }

      // latitude / longitude arcs
      for(let k=0;k<8;k++){
        const tilt=(k/8)*Math.PI;
        ctx.save();
        ctx.translate(cx,cy);
        ctx.rotate(tilt*.42);
        ctx.strokeStyle=rgba(k%2?C.violet:C.cyan,structure*.022);
        ctx.lineWidth=.6;
        ctx.beginPath();
        ctx.ellipse(0,0,R*.92,R*(.18+.06*(k%4)),0,0,TAU);
        ctx.stroke();
        ctx.restore();
      }
    }

    ctx.restore();
  }

  function drawTendrils(t,build,state,energy){
    const v=smooth(.42,.82,build);
    if(v<=.001)return;
    ctx.save();
    ctx.globalCompositeOperation='lighter';

    for(const d of tendrils){
      const a=d.angle+Math.sin(t*.15+d.phase)*.03;
      const sx=cx+Math.cos(a)*R*.94;
      const sy=cy+Math.sin(a)*R*.94;
      const ex=cx+Math.cos(a)*R*(1+d.len);
      const ey=cy+Math.sin(a)*R*(1+d.len*.58);
      const nx=Math.cos(a+Math.PI/2);
      const ny=Math.sin(a+Math.PI/2);
      const bend=R*d.bend*(.25+.15*Math.sin(t*d.speed+d.phase));
      const c1x=lerp(sx,ex,.36)+nx*bend;
      const c1y=lerp(sy,ey,.36)+ny*bend;
      const c2x=lerp(sx,ex,.72)-nx*bend*.55;
      const c2y=lerp(sy,ey,.72)-ny*bend*.55;

      const c=d.color<.45?C.cyan:d.color<.75?C.violet:C.magenta;
      ctx.strokeStyle=rgba(c,v*(.050+energy*.030));
      ctx.lineWidth=.65+energy*.18;
      ctx.beginPath();
      ctx.moveTo(sx,sy);
      ctx.bezierCurveTo(c1x,c1y,c2x,c2y,ex,ey);
      ctx.stroke();

      ctx.strokeStyle=rgba(c,v*(.16+energy*.06));
      ctx.lineWidth=.9;
      ctx.beginPath();
      ctx.arc(ex,ey,3.0+energy*.9,0,TAU);
      ctx.stroke();

      ctx.fillStyle=rgba(C.white,v*(.12+energy*.08));
      ctx.beginPath();
      ctx.arc(ex,ey,1.1+energy*.5,0,TAU);
      ctx.fill();
    }

    ctx.restore();
  }

  function drawWaveform(t,build,state,energy){
    const v=smooth(.62,.90,build);
    if(v<=.001)return;
    const speaking=state==='SPEAKING';
    const width=R*1.58;
    const baseAmp=R*(.016+(speaking?energy*.14:.008));
    const mid=cy;

    ctx.save();
    ctx.globalCompositeOperation='lighter';

    const grad=ctx.createLinearGradient(cx-width,mid,cx+width,mid);
    grad.addColorStop(0,rgba(C.magenta,0));
    grad.addColorStop(.18,rgba(C.magenta,v*(.22+energy*.10)));
    grad.addColorStop(.50,rgba(C.white,v*(.10+energy*.08)));
    grad.addColorStop(.82,rgba(C.cyan,v*(.25+energy*.12)));
    grad.addColorStop(1,rgba(C.cyan,0));

    ctx.strokeStyle=grad;
    ctx.lineWidth=.85+energy*.7;
    ctx.beginPath();

    const N=190;
    for(let i=0;i<=N;i++){
      const u=i/N;
      const x=cx-width+u*width*2;
      const dist=Math.abs(u-.5)*2;
      // Larger waveform toward the sides, calmer behind center logo.
      const sideGain=.30+.95*smooth(.12,.95,dist);
      const multi=
        Math.sin(u*TAU*18-t*(1.5+energy*3.0))*.46+
        Math.sin(u*TAU*31+t*.7)*.28+
        Math.sin(u*TAU*53-t*.35)*.18;
      const y=mid+multi*baseAmp*sideGain;
      if(i===0)ctx.moveTo(x,y);else ctx.lineTo(x,y);
    }
    ctx.stroke();

    // Vertical analyzer bars toward far left/right.
    for(let side of [-1,1]){
      for(let i=0;i<31;i++){
        const u=i/30;
        const x=cx+side*(R*1.08+u*R*.48);
        const pulse=.5+.5*Math.sin(t*(1.8+u*.7)+i*.72);
        const amp=R*(.012+.045*pulse+energy*.095*(.4+.6*pulse));
        const c=side<0?C.magenta:C.cyan;
        ctx.strokeStyle=rgba(c,v*(.05+.09*pulse+energy*.08));
        ctx.lineWidth=1;
        ctx.beginPath();
        ctx.moveTo(x,mid-amp);
        ctx.lineTo(x,mid+amp);
        ctx.stroke();
      }
    }

    ctx.restore();
  }

  function drawPedestal(t,build,energy){
    const v=smooth(.72,.96,build);
    if(v<=.001)return;

    const y=cy+R*1.04;
    ctx.save();
    ctx.globalCompositeOperation='lighter';

    for(let i=0;i<9;i++){
      const rr=R*(.36+i*.085);
      const h=R*(.022+i*.002);
      const pulse=.5+.5*Math.sin(t*.32+i*.75);
      const c=i%3===0?C.cyan:i%3===1?C.violet:C.magenta;
      ctx.strokeStyle=rgba(c,v*(.025+.020*pulse+energy*.016));
      ctx.lineWidth=.55+(i%3)*.15;
      ctx.beginPath();
      ctx.ellipse(cx,y,rr,h,0,0,TAU);
      ctx.stroke();
    }

    // bright inner ring
    ctx.strokeStyle=rgba(C.violet,v*(.10+energy*.035));
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.ellipse(cx,y,R*.58,R*.055,0,0,TAU);
    ctx.stroke();

    ctx.restore();
  }

  function drawAuraGlow(build,energy,state){
    const v=smooth(.52,.82,build);
    if(v<=.001)return;

    const g=ctx.createRadialGradient(cx,cy,R*.08,cx,cy,R*.62);
    const speaking=state==='SPEAKING';
    g.addColorStop(0,rgba(C.white,v*(.025+energy*.030)));
    g.addColorStop(.22,rgba(C.violet,v*(.028+energy*.045)));
    g.addColorStop(.55,rgba(C.purple,v*(.010+energy*.020)));
    g.addColorStop(1,'rgba(0,0,0,0)');
    ctx.fillStyle=g;
    ctx.beginPath();
    ctx.arc(cx,cy,R*.64,0,TAU);
    ctx.fill();
  }

  function render(now){
    requestAnimationFrame(render);
    if(now-lastFrame<1000/36)return;
    lastFrame=now;

    const dt=clamp((now-last)/1000,0,.05);
    last=now;
    const t=now/1000;

    const state=getState();
    const raw=getPcm();
    const tau=raw>pcm?.045:.20;
    const k=1-Math.exp(-dt/tau);
    pcm+=(raw-pcm)*k;
    accent=Math.max(accent*Math.exp(-dt/.14),Math.max(0,raw-prevPcm)*1.7);
    prevPcm=raw;

    const build=getBuild();

    rot += dt*(.035+
      (/THINKING|SEARCHING|ANALYZING/.test(state)?.042:0));

    ctx.clearRect(0,0,cssW,cssH);

    drawStars(t,build);
    drawWaveform(t,build,state,pcm);
    drawPedestal(t,build,pcm);
    drawAuraGlow(build,pcm,state);
    drawGlobe(t,build,state,pcm);
    drawTendrils(t,build,state,pcm);

    // Logo follows same build/state/PCM, but remains SVG-crisp.
    const logoBuild=smooth(.48,.80,build);
    const pulse=state==='SPEAKING'?pcm*.055:0;
    const breathe=(.5+.5*Math.sin(t*.72))*.006;
    logo.style.opacity=String(clamp(logoBuild*(.82+pcm*.10),0,1));
    logo.style.transform=
      `translate(-50%,-50%) scale(${(.90+logoBuild*.10+breathe+pulse+accent*.015).toFixed(4)})`;
    logo.dataset.state=state;

    cleanup();
  }

  requestAnimationFrame(render);
})();
