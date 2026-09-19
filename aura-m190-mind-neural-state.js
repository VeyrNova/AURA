/* AURA_M190_R1_ISOLATED_MIND_NEURAL_STATE
 * AURA_M190_R1_R1_VITALS_CONNECTIVITY_SYNC
 * AURA_M190_R2_REAL_SIGNAL_REACTIVE_TOPOLOGY
 * AURA_M190_R2_R1_SELF_CONTEXT_FEEDBACK_GUARD
 * AURA_M190_R2_R2_TRANSIENT_SIGNAL_HOLD_WINDOW
 * AURA_M190_R2_R3_WORKSPACE_ACTIVITY_TOOLS_SIGNAL
 * AURA_M190_R3_CINEMATIC_MIND_WORKSPACE_REDESIGN
 *
 * MIND / NEURAL STATE — cinematic workspace redesign.
 * Deterministic, read-only representation of AURA runtime/UI signals.
 * Simulated/derived visualization only; not literal consciousness.
 */
(() => {
  'use strict';
  if(window.__AURA_M190_MIND__) return;
  window.__AURA_M190_MIND__=true;

  const VERSION='m190-r3-20260910';
  const STATE={
    root:null,open:false,registered:false,ctxRegistered:false,raf:0,lastFrame:0,lastUi:0,
    recent:[],history:[],view:'global',lastRuntime:'',historyTimer:0
  };

  const q=(s,r=document)=>r?.querySelector?.(s)||null;
  const qa=(s,r=document)=>[...(r?.querySelectorAll?.(s)||[])];
  const safe=(v,n=180)=>String(v??'').replace(/[\u0000-\u001f\u007f]/g,' ').replace(/\s+/g,' ').trim().slice(0,n);
  const clamp=(v,a=0,b=100)=>Math.max(a,Math.min(b,Number(v)||0));
  const runtimeState=()=>safe(document.body?.dataset?.state||q('#stateText')?.textContent||'IDLE',32).toUpperCase();
  const currentWorkspace=()=>safe(window.AuraWorkspace?.current?.()||document.body?.dataset?.auraWorkspace||'home',32).toLowerCase()||'home';
  const nowClock=()=>new Date().toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});

  const PROFILES=Object.freeze({
    IDLE:{label:'CALME',activation:22,focus:28,flow:18},
    READY:{label:'DISPONIBLE',activation:34,focus:40,flow:28},
    LISTENING:{label:'RÉCEPTIF',activation:48,focus:78,flow:42},
    THINKING:{label:'FOCALISÉ',activation:72,focus:88,flow:74},
    ANALYZING:{label:'ANALYSE',activation:76,focus:92,flow:80},
    SEARCHING:{label:'EXPLORATION',activation:82,focus:84,flow:86},
    ACTING:{label:'EXÉCUTION',activation:88,focus:76,flow:90},
    SPEAKING:{label:'EXPRESSION',activation:66,focus:62,flow:78},
    ERROR:{label:'DÉGRADÉ',activation:64,focus:36,flow:18}
  });

  function profile(){
    const raw=runtimeState();
    const key=Object.prototype.hasOwnProperty.call(PROFILES,raw)?raw:
      (/THINK|ANALYZ/.test(raw)?'ANALYZING':
       /SEARCH/.test(raw)?'SEARCHING':
       /LISTEN/.test(raw)?'LISTENING':
       /SPEAK/.test(raw)?'SPEAKING':
       /ACT/.test(raw)?'ACTING':
       /ERR|FAIL/.test(raw)?'ERROR':'IDLE');
    return {...PROFILES[key],runtime:raw,key};
  }

  const NODE_SIGNAL=Object.seal({
    memory:{at:0,strength:0,source:'none'},
    tools:{at:0,strength:0,source:'none'},
    context:{at:0,strength:0,source:'none'},
    activity:{at:0,strength:0,source:'none'},
    language:{at:0,strength:0,source:'none'},
    planning:{at:0,strength:0,source:'none'}
  });
  const NODE_TTL_MS=12000;
  const nodeNow=()=>performance?.now?.()||Date.now();

  function addRecent(kind,label,source='runtime'){
    const clean=safe(label,120);
    if(!clean)return;
    const last=STATE.recent[0];
    if(last&&last.kind===kind&&last.label===clean&&Date.now()-last.at<900)return;
    STATE.recent.unshift({kind:safe(kind,24),label:clean,source:safe(source,32),at:Date.now(),clock:nowClock()});
    STATE.recent=STATE.recent.slice(0,7);
  }

  function pulseNode(name,strength=1,source='event'){
    const key=String(name||'').toLowerCase();
    const slot=NODE_SIGNAL[key];
    if(!slot)return false;
    slot.at=nodeNow();
    slot.strength=clamp(Number(strength||0)*100,0,100)/100;
    slot.source=safe(source,48)||'event';
    return true;
  }

  function eventPulse(name,base=1){
    const slot=NODE_SIGNAL[name];
    if(!slot||!slot.at)return 0;
    const age=Math.max(0,nodeNow()-slot.at);
    if(age>=NODE_TTL_MS)return 0;
    return slot.strength*(1-age/NODE_TTL_MS)*base;
  }

  function routerToolSignal(){
    try{
      const snap=window.AuraRouterObservatory?.snapshot?.();
      const kind=safe(snap?.route?.kind||'',32).toUpperCase();
      const state=safe(snap?.state||'',24).toUpperCase();
      const live=!/^(?:IDLE|READY|PRÊT|PRET)?$/.test(state);
      if(/^(?:TOOL|DOCUMENT|LOCAL CORE|LOCAL_CORE)$/.test(kind))return live?1:0.55;
    }catch(_){}
    return 0;
  }

  function contextSignal(){
    try{
      const c=window.AuraContextBridge?.get?.();
      const workspace=safe(c?.workspace||'',32).toLowerCase();
      if(c&&typeof c==='object'&&!c.cleared&&workspace&&workspace!=='mind')return 0.72;
    }catch(_){}
    return 0;
  }

  function nodeSignalSnapshot(){
    const runtime=runtimeState();
    const workspace=currentWorkspace();
    const levels={memory:0,tools:0,context:0,activity:0,language:0,planning:0};

    if(workspace==='memory')levels.memory=1;
    if(workspace==='plan')levels.planning=1;
    if(workspace==='talk'||workspace==='conversation')levels.language=Math.max(levels.language,0.72);

    if(runtime!=='IDLE'&&runtime!=='READY')levels.activity=0.62;
    if(runtime==='LISTENING'||runtime==='SPEAKING')levels.language=1;
    else if(runtime==='THINKING'||runtime==='ANALYZING')levels.language=Math.max(levels.language,0.72);

    levels.tools=Math.max(levels.tools,routerToolSignal());
    levels.context=Math.max(levels.context,contextSignal());

    for(const key of Object.keys(levels)){
      levels[key]=Math.max(levels[key],eventPulse(key));
      levels[key]=Math.round(clamp(levels[key]*100,0,100))/100;
    }
    return levels;
  }

  function nodeStateLabel(level){
    return level>=0.72?'ACTIF':level>=0.28?'SIGNAL':'VEILLE';
  }

  function vitalsStatus(){
    try{
      const vs=window.AuraVitalsActivity?.state?.();
      return {connected:!!vs?.connected,source:safe(vs?.source||'',64)};
    }catch(_){return {connected:false,source:''}}
  }

  function signalSnapshot(){
    const p=profile();
    const vitals=vitalsStatus();
    return {
      schema:'aura.mind.derived-state.v2',
      representation:'simulated-derived',
      runtime_state:p.runtime,
      derived_label:p.label,
      activation:p.activation,
      focus:p.focus,
      flow:p.flow,
      workspace:currentWorkspace(),
      vitals_bridge_connected:vitals.connected,
      vitals_source:vitals.source,
      consciousness_claim:false,
      node_signals:nodeSignalSnapshot()
    };
  }

  function createRoot(){
    if(STATE.root?.isConnected)return STATE.root;
    const root=document.createElement('section');
    root.className='aura-m190-mind-workspace aura-m190-r3 glass';
    root.hidden=true;
    root.setAttribute('aria-label','Mind / Neural State Visualization');
    root.innerHTML=`
      <header class="aura-m190-head">
        <div class="aura-m190-title">
          <span class="aura-m190-glyph" aria-hidden="true">◈</span>
          <div>
            <small>AURA · MIND UI</small>
            <b>MIND / NEURAL STATE</b>
            <em>Représentation dérivée du runtime · pas une conscience littérale</em>
          </div>
        </div>
        <div class="aura-m190-quote">“Observer, comprendre, connecter.”<small>AURA</small></div>
        <div class="aura-m190-head-meta">
          <span data-derived-state>SIMULÉ · CALME</span>
          <span class="aura-m190-readonly">LECTURE SEULE</span>
        </div>
        <button type="button" class="aura-m190-close" data-action="close" aria-label="Fermer">×</button>
      </header>

      <div class="aura-m190-shell">
        <nav class="aura-m190-local-nav" aria-label="Vues Mind">
          <button data-view="global" class="active"><i>◉</i><span><b>ÉTAT GLOBAL</b><small>Vue temps réel</small></span></button>
          <button data-view="topology"><i>⌘</i><span><b>TOPOLOGIE</b><small>Connexions modules</small></span></button>
          <button data-view="signals"><i>⌁</i><span><b>SIGNAUX</b><small>Flux et activité</small></span></button>
          <button data-view="history"><i>◷</i><span><b>HISTORIQUE</b><small>Dernières transitions</small></span></button>
        </nav>

        <main class="aura-m190-main">
          <section class="aura-m190-top">
            <article class="aura-m190-neural-card">
              <div class="aura-m190-canvas-wrap">
                <canvas data-neural-canvas aria-hidden="true"></canvas>
                <div class="aura-m190-core-label">
                  <small>NEURAL CORE</small>
                  <b data-core-state>CALME</b>
                  <span data-runtime-state>IDLE</span>
                </div>
                <div class="aura-m190-legend">
                  <span class="active"><i></i>ACTIF</span>
                  <span class="signal"><i></i>SIGNAL</span>
                  <span class="idle"><i></i>VEILLE</span>
                </div>
                <div class="aura-m190-version">RUNTIME VISUALIZATION<br><b>M190 · R3</b></div>
              </div>
            </article>

            <aside class="aura-m190-side">
              <section class="aura-m190-state-card">
                <header><small>ÉTAT COGNITIF SIMULÉ</small><span>⌁</span></header>
                <strong data-state-label>CALME</strong>
                <p>État dérivé du mode d’exécution d’AURA. Il décrit l’interface et le runtime, pas une expérience subjective.</p>
              </section>

              <section class="aura-m190-meters">
                <header><small>MÉTRIQUES TEMPS RÉEL</small></header>
                <div><span>ACTIVATION</span><b data-meter-value="activation">22%</b><i><u data-meter="activation"></u></i></div>
                <div><span>FOCUS</span><b data-meter-value="focus">28%</b><i><u data-meter="focus"></u></i></div>
                <div><span>FLUX</span><b data-meter-value="flow">18%</b><i><u data-meter="flow"></u></i></div>
              </section>

              <section class="aura-m190-signals">
                <header><small>SIGNAUX ACTIFS</small><b><i></i>TEMPS RÉEL</b></header>
                <div class="aura-m190-signal-head"><span>Module</span><span>État</span><span>Source</span></div>
                <div><span>Runtime</span><strong data-signal-runtime>IDLE</strong><em>AURA</em></div>
                <div><span>Workspace</span><strong data-signal-workspace>MIND</strong><em>UI</em></div>
                <div><span>Vitals bridge</span><strong data-signal-vitals>NON CONNECTÉ</strong><em>SYSTEM</em></div>
                <div><span>Contexte</span><strong data-signal-context>LOCAL</strong><em>CONTEXT</em></div>
              </section>

              <section class="aura-m190-nodes">
                <header><small>TOPOLOGIE DES MODULES</small><b>COUCHES REPRÉSENTÉES</b></header>
                <div class="aura-m190-node-grid">
                  <span data-node-chip="memory">MEMORY · VEILLE</span>
                  <span data-node-chip="tools">TOOLS · VEILLE</span>
                  <span data-node-chip="context">CONTEXT · VEILLE</span>
                  <span data-node-chip="activity">ACTIVITY · VEILLE</span>
                  <span data-node-chip="language">LANGUAGE · VEILLE</span>
                  <span data-node-chip="planning">PLANNING · VEILLE</span>
                </div>
              </section>
            </aside>
          </section>

          <section class="aura-m190-bottom">
            <article class="aura-m190-recent">
              <header><small>ÉVÉNEMENTS RÉCENTS</small><button data-action="clear-events">EFFACER</button></header>
              <div data-recent-events></div>
            </article>

            <article class="aura-m190-history">
              <header><small>HISTORIQUE D’ÉTAT</small><b>DERNIÈRES TRANSITIONS</b></header>
              <canvas data-history-canvas aria-hidden="true"></canvas>
            </article>

            <article class="aura-m190-active-modules">
              <header><small>MODULES ACTIFS</small><b data-active-count>0 / 6</b></header>
              <div data-active-module-grid></div>
            </article>

            <article class="aura-m190-resonance">
              <header><small>RÉSONANCE CONTEXTUELLE</small><b>SIMULÉE</b></header>
              <canvas data-resonance-canvas aria-hidden="true"></canvas>
              <div class="aura-m190-resonance-values">
                <span>COHÉRENCE <b data-res-coherence>—</b></span>
                <span>RÉACTIVITÉ <b data-res-reactivity>—</b></span>
                <span>INTÉGRATION <b data-res-integration>—</b></span>
              </div>
            </article>
          </section>
        </main>
      </div>

      <footer class="aura-m190-foot">
        <span>M190 · DERIVED STATE FOUNDATION</span>
        <span>SIMULATED REPRESENTATION · NOT CONSCIOUSNESS</span>
      </footer>`;
    (document.getElementById('app')||document.body).appendChild(root);
    STATE.root=root;
    bind(root);
    layoutRoot();
    resizeCanvases();
    seedHistory();
    renderRecent();
    return root;
  }

  function ensureModuleButton(){
    const grid=q('.aura-p0702-module-grid');
    if(!grid)return false;
    let b=q('[data-module="mind"]',grid);
    if(!b){
      b=document.createElement('button');
      b.type='button'; b.dataset.module='mind'; b.className='aura-m190-module-entry';
      b.innerHTML='<span><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M4 12h3M17 12h3M12 4v3M12 17v3M6.3 6.3l2.1 2.1M15.6 15.6l2.1 2.1M17.7 6.3l-2.1 2.1M8.4 15.6l-2.1 2.1"/></svg></span><div><b>MIND / NEURAL STATE</b><small>Runtime · modules · état simulé</small></div>';
      grid.appendChild(b);
    }
    return true;
  }

  function registerWorkspace(){
    if(STATE.registered||!window.AuraWorkspace?.register)return STATE.registered;
    STATE.registered=!!window.AuraWorkspace.register({
      id:'mind',label:'MIND',available:()=>true,isOpen:()=>STATE.open,
      open:()=>setOpen(true),close:()=>setOpen(false),
      focusTarget:()=>q('.aura-m190-mind-workspace.open button'),
      serialize:()=>({version:VERSION,view:STATE.view}),
      restore:s=>{STATE.view=safe(s?.view||'global',20)||'global';setOpen(true)}
    });
    return STATE.registered;
  }

  function buildContext(){
    const s=signalSnapshot();
    return {
      schema:'aura.workspace-context.v2',
      workspace:'mind',submode:'derived-read-only',
      target:'Mind / Neural State · représentation simulée',
      summary:'Visualisation déterministe de signaux runtime AURA. Aucun état mental humain ni conscience littérale n’est inféré.',
      facts:[
        {key:'runtime_state',label:'État runtime',value:s.runtime_state,source:'mind-derived'},
        {key:'derived_state',label:'État simulé',value:s.derived_label,source:'mind-derived'},
        {key:'workspace',label:'Workspace',value:s.workspace,source:'mind-derived'},
        {key:'representation',label:'Nature',value:'Représentation déterministe dérivée — pas une conscience littérale',source:'mind-derived'}
      ],
      refs:[],cleared:false
    };
  }

  function registerContext(){
    if(STATE.ctxRegistered)return true;
    STATE.ctxRegistered=!!window.AuraContextBridge?.register?.('mind',async()=>buildContext());
    return STATE.ctxRegistered;
  }

  async function refreshVitalsConnectivity(){
    try{
      const api=window.AuraVitalsActivity;
      if(!api?.refresh){updateUi(true);return false;}
      await Promise.resolve(api.refresh());
      updateUi(true);
      return !!api.state?.()?.connected;
    }catch(_){updateUi(true);return false}
  }

  function setOpen(on){
    const root=createRoot();
    STATE.open=!!on;
    root.hidden=!STATE.open;
    root.classList.toggle('open',STATE.open);
    if(STATE.open){
      layoutRoot(); updateUi(true); resizeCanvases(); startRender(); refreshVitalsConnectivity();
    }
    return STATE.open;
  }

  function openFromModule(){
    const pop=q('.aura-p0702-modules-popover');
    if(pop){pop.classList.remove('open');pop.hidden=true}
    registerWorkspace();
    if(window.AuraWorkspace?.open)window.AuraWorkspace.open('mind'); else setOpen(true);
  }

  function bind(root){
    root.addEventListener('click',e=>{
      const action=e.target.closest?.('[data-action]')?.dataset?.action;
      if(action==='close'){
        if(window.AuraWorkspace?.home)window.AuraWorkspace.home(); else setOpen(false);
      }
      if(action==='clear-events'){STATE.recent=[];renderRecent()}
      const view=e.target.closest?.('[data-view]')?.dataset?.view;
      if(view){
        STATE.view=view;
        qa('[data-view]',root).forEach(b=>b.classList.toggle('active',b.dataset.view===view));
        root.dataset.view=view;
      }
    });
  }

  function layoutRoot(){
    const root=STATE.root;if(!root)return;
    const rail=q('.rail')||q('.left-rail')||q('.sidebar');
    const composer=q('.composer')||q('.aura-composer')||q('[data-composer]');
    const top=q('.topbar')||q('.top-bar')||q('.header-bar');
    const rb=rail?.getBoundingClientRect?.();
    const cb=composer?.getBoundingClientRect?.();
    const tb=top?.getBoundingClientRect?.();
    const left=Math.max(80,Math.round((rb?.right||80)+10));
    const topPx=Math.max(62,Math.round((tb?.bottom||62)+8));
    const bottom=Math.max(76,Math.round(window.innerHeight-(cb?.top||window.innerHeight-86)+8));
    root.style.left=`${left}px`;
    root.style.top=`${topPx}px`;
    root.style.bottom=`${bottom}px`;
    root.style.right='12px';
  }

  function toolActivityFromWorkspace(d){
    const id=safe(d?.workspace||'',32).toLowerCase();
    if(['weather','maps','research','document','browser'].includes(id))return true;
    const text=`${safe(d?.workspace||'',48)} ${safe(d?.label||'',120)} ${safe(d?.detail||'',180)}`;
    return /(?:MÉTÉO|METEO|WEATHER|MAPS?|CARTE|ITINÉRAIRE|ITINERAIRE|RECHERCHE|SEARCH|WEB|DOCUMENT|PDF|FICHIER)/i.test(text);
  }

  function seedHistory(){
    if(STATE.history.length)return;
    const p=profile();
    for(let i=0;i<12;i++)STATE.history.push({at:Date.now()-(11-i)*5000,activation:p.activation,focus:p.focus,flow:p.flow,label:p.label});
  }

  function sampleHistory(force=false){
    const p=profile();
    const last=STATE.history[STATE.history.length-1];
    if(!force&&last&&Date.now()-last.at<3500&&last.label===p.label)return;
    STATE.history.push({at:Date.now(),activation:p.activation,focus:p.focus,flow:p.flow,label:p.label});
    STATE.history=STATE.history.slice(-36);
  }

  function updateUi(force=false){
    if(!STATE.root)return;
    const now=performance.now();
    if(!force&&now-STATE.lastUi<220)return;
    STATE.lastUi=now;
    const root=STATE.root,p=profile(),s=signalSnapshot(),nodes=s.node_signals;

    if(STATE.lastRuntime!==p.runtime){
      if(STATE.lastRuntime)addRecent('runtime',`État ${p.label}`,'Runtime');
      STATE.lastRuntime=p.runtime;
      sampleHistory(true);
    }

    q('[data-derived-state]',root).textContent=`SIMULÉ · ${p.label}`;
    q('[data-core-state]',root).textContent=p.label;
    q('[data-runtime-state]',root).textContent=p.runtime;
    q('[data-state-label]',root).textContent=p.label;
    q('[data-signal-runtime]',root).textContent=p.runtime;
    q('[data-signal-workspace]',root).textContent=s.workspace.toUpperCase();
    q('[data-signal-vitals]',root).textContent=s.vitals_bridge_connected?'SOURCE CONNECTÉE':'NON CONNECTÉ';
    q('[data-signal-context]',root).textContent=window.AuraContextBridge?'BRIDGE LOCAL':'LOCAL';

    for(const key of ['activation','focus','flow']){
      const val=clamp(p[key]);
      q(`[data-meter="${key}"]`,root).style.width=`${val}%`;
      q(`[data-meter-value="${key}"]`,root).textContent=`${Math.round(val)}%`;
    }

    let activeCount=0;
    for(const [name,level] of Object.entries(nodes)){
      const chip=q(`[data-node-chip="${name}"]`,root);
      if(chip){
        const state=level>=0.72?'active':level>=0.28?'signal':'idle';
        chip.dataset.nodeLevel=state;
        chip.textContent=`${name.toUpperCase()} · ${nodeStateLabel(level)}`;
      }
      if(level>=0.28)activeCount++;
    }
    q('[data-active-count]',root).textContent=`${activeCount} / 6`;
    renderModuleGrid(nodes);
    renderResonance(nodes,p);
    renderRecent();
    sampleHistory(false);
  }

  function renderRecent(){
    const host=q('[data-recent-events]',STATE.root); if(!host)return;
    const rows=STATE.recent.length?STATE.recent:[{kind:'idle',label:'Aucune transition récente',source:'Mind',clock:'—'}];
    host.innerHTML=rows.slice(0,5).map(x=>`<div><time>${safe(x.clock,12)}</time><i data-kind="${safe(x.kind,16)}"></i><span>${safe(x.label,90)}</span><em>${safe(x.source,24)}</em></div>`).join('');
  }

  function renderModuleGrid(nodes){
    const host=q('[data-active-module-grid]',STATE.root);if(!host)return;
    host.innerHTML=['memory','tools','context','activity','language','planning'].map(name=>{
      const level=Number(nodes[name]||0);
      const state=level>=0.72?'active':level>=0.28?'signal':'idle';
      return `<span data-state="${state}"><b>${name.toUpperCase()}</b><small>${nodeStateLabel(level)}</small></span>`;
    }).join('');
  }

  function resizeCanvas(c){
    if(!c)return;
    const box=c.getBoundingClientRect(),dpr=Math.min(2,window.devicePixelRatio||1);
    const w=Math.max(240,Math.floor(box.width*dpr)),h=Math.max(120,Math.floor(box.height*dpr));
    if(c.width!==w)c.width=w;if(c.height!==h)c.height=h;
  }
  function resizeCanvases(){
    resizeCanvas(q('[data-neural-canvas]',STATE.root));
    resizeCanvas(q('[data-history-canvas]',STATE.root));
    resizeCanvas(q('[data-resonance-canvas]',STATE.root));
  }

  /* AURA_M190_R3_R2_NEURAL_CORE_GEOMETRY_VISUAL_HIERARCHY_JS */
  const NODES=Object.freeze([
    {name:'LANGUAGE',x:0.00,y:-0.90,z:0.18},
    {name:'MEMORY',x:0.86,y:-0.24,z:-0.08},
    {name:'ACTIVITY',x:0.72,y:0.58,z:0.22},
    {name:'PLANNING',x:0.04,y:0.92,z:-0.10},
    {name:'CONTEXT',x:-0.80,y:0.56,z:0.18},
    {name:'TOOLS',x:-0.88,y:-0.26,z:-0.18}
  ]);

  function project(node,angle,w,h){
    const ca=Math.cos(angle),sa=Math.sin(angle);
    const x=node.x*ca-node.z*sa,z=node.x*sa+node.z*ca,y=node.y;
    const scale=1/(1.45+z*0.28);
    return {x:w/2+x*w*0.53*scale,y:h/2+y*h*0.48*scale,z,scale};
  }

    /* AURA_M190_R4_CINEMATIC_NEURAL_VISUAL_ENGINE_REBUILD_JS */
  const VISUAL_NODE_META=Object.freeze({
    LANGUAGE:{glyph:'⌁'}, MEMORY:{glyph:'◫'}, ACTIVITY:{glyph:'∿'},
    PLANNING:{glyph:'▦'}, CONTEXT:{glyph:'◇'}, TOOLS:{glyph:'⚙'}
  });

  function seededUnit(n){
    const x=Math.sin(n*12.9898+78.233)*43758.5453;
    return x-Math.floor(x);
  }

  function drawStarfield(ctx,w,h,dpr,t){
    ctx.save();
    for(let i=0;i<96;i++){
      const x=seededUnit(i*2+1)*w, y=seededUnit(i*2+2)*h;
      const tw=.18+.38*(.5+.5*Math.sin(t*(.35+seededUnit(i+81)*.65)+i));
      const s=(.45+seededUnit(i+171)*1.25)*dpr;
      ctx.fillStyle=i%5===0?`rgba(150,86,255,${tw})`:`rgba(72,210,255,${tw*.72})`;
      ctx.beginPath();ctx.arc(x,y,s,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

    /* AURA_M190_R4_R4_REFERENCE_FIDELITY_TUNING */
  function drawOrbitalField(ctx,cx,cy,w,h,dpr,t){
    ctx.save();ctx.translate(cx,cy);
    const maxR=Math.min(w*.47,h*.70);
    for(let i=0;i<7;i++){
      const r=maxR*(.34+i*.095);
      ctx.save();ctx.rotate(t*(i%2?-.012:.010)+i*.17);
      ctx.strokeStyle=i%2
        ?`rgba(117,76,255,${.034+i*.005})`
        :`rgba(53,188,255,${.030+i*.006})`;
      ctx.lineWidth=Math.max(.8,dpr*.52);
      ctx.beginPath();ctx.ellipse(0,0,r,r*(.62+i*.015),0,0,Math.PI*2);ctx.stroke();
      ctx.restore();
    }
    for(let i=0;i<3;i++){
      const r=maxR*(.44+i*.16),a=t*(.05+i*.015)+i*2.1;
      const x=Math.cos(a)*r,y=Math.sin(a)*r*.64;
      ctx.fillStyle=i===1?'rgba(189,88,255,.28)':'rgba(68,222,255,.26)';
      ctx.beginPath();ctx.arc(x,y,(1.25+i*.25)*dpr,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

    /* AURA_M190_R4_R3_ORGANIC_NEURAL_LINKS_ORB_DEPTH */
    function drawPlasmaLink(ctx,core,node,dpr,level,index,t){
    const dx=node.x-core.x,dy=node.y-core.y,dist=Math.max(1,Math.hypot(dx,dy));
    const nx=-dy/dist,ny=dx/dist;
    const sign=index%2===0?1:-1;
    const bend=(24+level*15)*dpr;
    const phase=t*.56+index*1.43;
    const sway=(Math.sin(phase)*.68+Math.sin(phase*.47+index)*.32)*bend*sign;
    const c1x=core.x+dx*.27+nx*sway;
    const c1y=core.y+dy*.27+ny*sway;
    const c2x=core.x+dx*.72-nx*sway*.58;
    const c2y=core.y+dy*.72-ny*sway*.58;

    const drawCurve=(offset,width,alpha,color,skew=0)=>{
      ctx.globalAlpha=alpha;
      ctx.strokeStyle=color;
      ctx.lineWidth=width*dpr*(1+level*.22);
      ctx.beginPath();
      ctx.moveTo(core.x+nx*offset*dpr,core.y+ny*offset*dpr);
      ctx.bezierCurveTo(
        c1x+nx*(offset+skew)*dpr,c1y+ny*(offset+skew)*dpr,
        c2x+nx*(offset-skew*.7)*dpr,c2y+ny*(offset-skew*.7)*dpr,
        node.x,node.y
      );
      ctx.stroke();
    };

    ctx.save();ctx.globalCompositeOperation='lighter';
    const grad=ctx.createLinearGradient(core.x,core.y,node.x,node.y);
    grad.addColorStop(0,'rgba(103,235,255,.96)');
    grad.addColorStop(.34,'rgba(87,187,255,.76)');
    grad.addColorStop(.70,level>=.72?'rgba(180,91,255,.92)':'rgba(119,92,255,.74)');
    grad.addColorStop(1,level>=.72?'rgba(228,90,255,.94)':'rgba(112,119,255,.80)');

    drawCurve(0,16,.026+level*.016,grad,0);
    drawCurve(0,8,.050+level*.022,grad,0);
    drawCurve(0,4.2,.16+level*.065,grad,0);
    drawCurve(0,1.45,.74+level*.11,grad,0);

    drawCurve(4.6,.70,.32+level*.14,'rgba(227,249,255,.86)',1.4);
    drawCurve(-4.1,.56,.22+level*.11,level>=.72?'rgba(236,151,255,.78)':'rgba(128,231,255,.68)',-1.1);

    for(let k=0;k<4;k++){
      const u=((t*.145+k*.23+index*.11)%1),omt=1-u;
      const x=omt*omt*omt*core.x+3*omt*omt*u*c1x+3*omt*u*u*c2x+u*u*u*node.x;
      const y=omt*omt*omt*core.y+3*omt*omt*u*c1y+3*omt*u*u*c2y+u*u*u*node.y;
      ctx.globalAlpha=.16+level*.22;
      ctx.fillStyle=k%2?'rgba(207,121,255,.82)':'rgba(119,238,255,.84)';
      ctx.beginPath();ctx.arc(x,y,(1.0+level*.65)*dpr,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

    function drawSatelliteOrb(ctx,n,dpr,t){
    const level=n.level||0,active=level>=.72,signal=level>=.28;
    const baseR=(active?50:signal?46:42)*dpr;
    const pulse=1+Math.sin(t*(1.7+level*.7)+n.index*.9)*(.022+level*.03);
    const r=baseR*pulse;
    const rgb=active?'193,78,255':signal?'66,222,255':'103,101,242';

    ctx.save();
    ctx.globalCompositeOperation='lighter';

    const outer=ctx.createRadialGradient(n.x,n.y,r*.25,n.x,n.y,r*2.45);
    outer.addColorStop(0,`rgba(${rgb},${.36+level*.28})`);
    outer.addColorStop(.30,`rgba(${rgb},${.15+level*.17})`);
    outer.addColorStop(.68,`rgba(${rgb},${.035+level*.05})`);
    outer.addColorStop(1,`rgba(${rgb},0)`);
    ctx.fillStyle=outer;ctx.beginPath();ctx.arc(n.x,n.y,r*2.45,0,Math.PI*2);ctx.fill();

    const orb=ctx.createRadialGradient(n.x-r*.34,n.y-r*.38,r*.06,n.x,n.y,r);
    orb.addColorStop(0,'rgba(255,255,255,.99)');
    orb.addColorStop(.10,'rgba(214,249,255,.97)');
    orb.addColorStop(.24,`rgba(${rgb},.92)`);
    orb.addColorStop(.58,active?'rgba(102,35,196,.92)':signal?'rgba(21,99,169,.91)':'rgba(29,35,99,.94)');
    orb.addColorStop(.84,'rgba(12,16,55,.96)');
    orb.addColorStop(1,'rgba(4,8,25,.99)');
    ctx.fillStyle=orb;ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);ctx.fill();

    ctx.strokeStyle=active?'rgba(236,154,255,.98)':signal?'rgba(139,245,255,.98)':'rgba(151,145,255,.78)';
    ctx.lineWidth=(active?2.1:1.55)*dpr;
    ctx.beginPath();ctx.arc(n.x,n.y,r*.94,0,Math.PI*2);ctx.stroke();

    ctx.strokeStyle='rgba(232,248,255,.16)';ctx.lineWidth=.8*dpr;
    ctx.beginPath();ctx.arc(n.x,n.y,r*.72,0,Math.PI*2);ctx.stroke();
    ctx.beginPath();ctx.arc(n.x,n.y,r*.48,0,Math.PI*2);ctx.stroke();

    ctx.globalAlpha=.78;
    ctx.strokeStyle=active?'rgba(219,103,255,.72)':signal?'rgba(80,218,255,.62)':'rgba(113,128,255,.42)';
    ctx.lineWidth=1*dpr;
    ctx.beginPath();ctx.arc(n.x,n.y,r*1.17,t*.38+n.index,-t*.31+n.index+Math.PI*1.12);ctx.stroke();

    ctx.globalAlpha=.30+level*.24;
    ctx.strokeStyle=active?'rgba(107,239,255,.82)':'rgba(185,120,255,.66)';
    ctx.lineWidth=.75*dpr;
    ctx.beginPath();ctx.ellipse(n.x,n.y,r*1.32,r*.54,t*.13+n.index*.4,0,Math.PI*2);ctx.stroke();

    const shine=ctx.createRadialGradient(n.x-r*.38,n.y-r*.44,0,n.x-r*.30,n.y-r*.36,r*.42);
    shine.addColorStop(0,'rgba(255,255,255,.96)');
    shine.addColorStop(.18,'rgba(220,250,255,.62)');
    shine.addColorStop(1,'rgba(255,255,255,0)');
    ctx.fillStyle=shine;ctx.beginPath();ctx.arc(n.x-r*.26,n.y-r*.31,r*.43,0,Math.PI*2);ctx.fill();

    ctx.globalCompositeOperation='source-over';ctx.globalAlpha=1;
    ctx.fillStyle='rgba(249,254,255,.99)';
    ctx.font=`${Math.round(18*dpr)}px "Segoe UI Symbol","Segoe UI",sans-serif`;
    ctx.textAlign='center';ctx.textBaseline='middle';
    ctx.fillText(VISUAL_NODE_META[n.name]?.glyph||'•',n.x,n.y-1*dpr);

    ctx.fillStyle='rgba(238,250,255,.96)';
    ctx.font=`700 ${Math.round(9.5*dpr)}px ui-monospace,Consolas,monospace`;
    ctx.textBaseline='alphabetic';
    ctx.fillText(n.name,n.x,n.y+r+16*dpr);

    ctx.fillStyle=active?'rgba(235,169,255,.82)':signal?'rgba(129,235,255,.80)':'rgba(166,184,211,.58)';
    ctx.font=`600 ${Math.round(6.5*dpr)}px ui-monospace,Consolas,monospace`;
    ctx.fillText(nodeStateLabel(level),n.x,n.y+r+28*dpr);
    ctx.restore();
  }

      function drawNeuralCore(ctx,core,dpr,t,p){
    const pulse=1+Math.sin(t*(1.35+p.activation/120))*.024,r=142*dpr*pulse;
    ctx.save();ctx.globalCompositeOperation='lighter';

    const halo=ctx.createRadialGradient(core.x,core.y,0,core.x,core.y,r*1.78);
    halo.addColorStop(0,'rgba(239,253,255,.66)');
    halo.addColorStop(.10,'rgba(79,226,255,.64)');
    halo.addColorStop(.30,'rgba(93,117,255,.48)');
    halo.addColorStop(.50,'rgba(184,68,255,.28)');
    halo.addColorStop(.72,'rgba(88,37,198,.085)');
    halo.addColorStop(1,'rgba(50,24,155,0)');
    ctx.fillStyle=halo;ctx.beginPath();ctx.arc(core.x,core.y,r*1.78,0,Math.PI*2);ctx.fill();

    const orb=ctx.createRadialGradient(core.x-r*.26,core.y-r*.30,r*.07,core.x,core.y,r);
    orb.addColorStop(0,'rgba(243,255,255,.82)');
    orb.addColorStop(.13,'rgba(127,242,255,.76)');
    orb.addColorStop(.34,'rgba(62,177,241,.72)');
    orb.addColorStop(.56,'rgba(80,92,229,.72)');
    orb.addColorStop(.76,'rgba(134,47,204,.74)');
    orb.addColorStop(1,'rgba(18,8,58,.96)');
    ctx.fillStyle=orb;ctx.beginPath();ctx.arc(core.x,core.y,r*.72,0,Math.PI*2);ctx.fill();

    for(let i=0;i<4;i++){
      ctx.strokeStyle=i%2?'rgba(207,93,255,.30)':'rgba(105,226,255,.29)';
      ctx.lineWidth=(1.0-i*.09)*dpr;
      ctx.beginPath();
      ctx.arc(core.x,core.y,r*(.82+i*.14),t*(i%2?-.15:.11)+i,t*(i%2?-.15:.11)+i+Math.PI*(1.00+i*.08));
      ctx.stroke();
    }

    ctx.strokeStyle='rgba(222,250,255,.26)';ctx.lineWidth=.70*dpr;
    ctx.beginPath();ctx.arc(core.x,core.y,r*.57,0,Math.PI*2);ctx.stroke();

    for(let i=0;i<24;i++){
      const a=i/24*Math.PI*2+t*(i%2?.055:-.038),rr=r*(.55+.19*seededUnit(i+401));
      const x=core.x+Math.cos(a)*rr,y=core.y+Math.sin(a)*rr;
      ctx.fillStyle=i%3===0?'rgba(229,126,255,.30)':'rgba(145,240,255,.32)';
      ctx.beginPath();ctx.arc(x,y,(.60+seededUnit(i+731)*.78)*dpr,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  function drawNeural(now){
    const c=q('[data-neural-canvas]',STATE.root);if(!c)return;
    const ctx=c.getContext('2d');if(!ctx)return;
    const w=c.width,h=c.height,dpr=Math.min(2,window.devicePixelRatio||1);
    const p=profile(),levels=nodeSignalSnapshot(),t=now/1000;
    ctx.clearRect(0,0,w,h);
    const field=ctx.createRadialGradient(w*.5,h*.47,0,w*.5,h*.47,Math.max(w,h)*.70);
    field.addColorStop(0,'rgba(27,66,139,.20)');field.addColorStop(.35,'rgba(72,38,143,.10)');
    field.addColorStop(.68,'rgba(12,35,72,.035)');field.addColorStop(1,'rgba(2,7,18,0)');
    ctx.fillStyle=field;ctx.fillRect(0,0,w,h);
    drawStarfield(ctx,w,h,dpr,t);drawOrbitalField(ctx,w/2,h/2,w,h,dpr,t);
    const angle=0; /* AURA_M190_R4_R2_FIXED_ORB_COMPOSITION_FIDELITY */
    const pts=NODES.map((n,index)=>({...project(n,angle,w,h),name:n.name,index,level:Number(levels[n.name.toLowerCase()]||0)}));
    const core={x:w/2,y:h/2};
    pts.forEach((n,i)=>drawPlasmaLink(ctx,core,n,dpr,n.level,i,t));
    drawNeuralCore(ctx,core,dpr,t,p);
    [...pts].sort((a,b)=>a.z-b.z).forEach(n=>drawSatelliteOrb(ctx,n,dpr,t));
  }

  function drawHistory(){
    const c=q('[data-history-canvas]',STATE.root);if(!c)return;
    const ctx=c.getContext('2d');if(!ctx)return;
    const w=c.width,h=c.height,dpr=Math.min(2,window.devicePixelRatio||1);
    ctx.clearRect(0,0,w,h);
    const pad=16*dpr,items=STATE.history.slice(-28);
    ctx.strokeStyle='rgba(126,193,255,.10)';ctx.lineWidth=1;
    for(let i=1;i<4;i++){const y=pad+(h-pad*2)*i/4;ctx.beginPath();ctx.moveTo(pad,y);ctx.lineTo(w-pad,y);ctx.stroke()}
    if(items.length<2)return;
    const values=items.map(x=>(x.activation+x.focus+x.flow)/3);
    const pts=values.map((v,i)=>({x:pad+(w-pad*2)*i/(values.length-1),y:h-pad-(h-pad*2)*v/100}));
    /* AURA_M190_R3_R1_VISUAL_POLISH_READABILITY_JS */
    const grad=ctx.createLinearGradient(pad,0,w-pad,0);grad.addColorStop(0,'rgba(52,211,255,.95)');grad.addColorStop(1,'rgba(180,74,255,.98)');
    const area=ctx.createLinearGradient(0,pad,0,h-pad);area.addColorStop(0,'rgba(130,82,255,.22)');area.addColorStop(1,'rgba(45,205,255,.015)');
    ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.lineTo(pts[pts.length-1].x,h-pad);ctx.lineTo(pts[0].x,h-pad);ctx.closePath();ctx.fillStyle=area;ctx.fill();
    ctx.strokeStyle=grad;ctx.lineWidth=2.35*dpr;ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.stroke();
    for(let i=Math.max(0,pts.length-5);i<pts.length;i++){const pt=pts[i];ctx.fillStyle='rgba(211,244,255,.72)';ctx.beginPath();ctx.arc(pt.x,pt.y,1.5*dpr,0,Math.PI*2);ctx.fill()}
    const last=pts[pts.length-1];ctx.fillStyle='rgba(244,252,255,.98)';ctx.beginPath();ctx.arc(last.x,last.y,3.4*dpr,0,Math.PI*2);ctx.fill();
    ctx.strokeStyle='rgba(168,103,255,.75)';ctx.lineWidth=1*dpr;ctx.beginPath();ctx.arc(last.x,last.y,6*dpr,0,Math.PI*2);ctx.stroke();
  }

  function renderResonance(nodes,p){
    const values=Object.values(nodes);
    const avg=values.reduce((a,b)=>a+b,0)/Math.max(1,values.length);
    const active=values.filter(v=>v>=.28).length/6;
    const coherence=Math.round(clamp((p.focus*.55+p.flow*.25+avg*100*.20)));
    const reactivity=Math.round(clamp((p.activation*.55+active*100*.45)));
    const integration=Math.round(clamp((p.flow*.45+p.focus*.25+active*100*.30)));
    q('[data-res-coherence]',STATE.root).textContent=`${coherence}%`;
    q('[data-res-reactivity]',STATE.root).textContent=`${reactivity}%`;
    q('[data-res-integration]',STATE.root).textContent=`${integration}%`;
    drawRadar([coherence,reactivity,integration,Math.round(avg*100),Math.round((p.activation+p.focus)/2)]);
  }

  function drawRadar(vals){
    const c=q('[data-resonance-canvas]',STATE.root);if(!c)return;
    const ctx=c.getContext('2d');if(!ctx)return;
    const w=c.width,h=c.height,dpr=Math.min(2,window.devicePixelRatio||1);
    ctx.clearRect(0,0,w,h);
    const cx=w*.35,cy=h*.52,r=Math.min(w*.29,h*.41),n=5;
    const point=(i,ratio)=>{const a=-Math.PI/2+i*Math.PI*2/n;return [cx+Math.cos(a)*r*ratio,cy+Math.sin(a)*r*ratio]};
    ctx.strokeStyle='rgba(112,190,255,.23)';ctx.lineWidth=1.1*dpr;
    for(const ratio of [.33,.66,1]){
      ctx.beginPath();for(let i=0;i<n;i++){const [x,y]=point(i,ratio);i?ctx.lineTo(x,y):ctx.moveTo(x,y)}ctx.closePath();ctx.stroke();
    }
    const g=ctx.createLinearGradient(cx-r,cy,cx+r,cy);g.addColorStop(0,'rgba(43,210,255,.40)');g.addColorStop(1,'rgba(169,78,255,.46)');
    ctx.fillStyle=g;ctx.strokeStyle='rgba(146,188,255,.94)';ctx.lineWidth=1.8*dpr;
    ctx.beginPath();vals.forEach((v,i)=>{const [x,y]=point(i,clamp(v)/100);i?ctx.lineTo(x,y):ctx.moveTo(x,y)});ctx.closePath();ctx.fill();ctx.stroke();
  }

  function renderLoop(now){
    STATE.raf=requestAnimationFrame(renderLoop);
    if(!STATE.open)return;
    if(now-STATE.lastFrame<1000/30)return;
    STATE.lastFrame=now;
    updateUi(false);drawNeural(now);drawHistory();
  }
  function startRender(){if(!STATE.raf)STATE.raf=requestAnimationFrame(renderLoop)}

  document.addEventListener('click',e=>{
    const mod=e.target.closest?.('[data-module="mind"]');
    if(mod){e.preventDefault();e.stopImmediatePropagation();openFromModule()}
  },true);

  window.addEventListener('resize',()=>{layoutRoot();if(STATE.open)resizeCanvases()});
  window.addEventListener('aura:workspace-manager-ready',()=>registerWorkspace());
  window.addEventListener('aura:context-bridge-ready',()=>registerContext());
  window.addEventListener('aura:vitals-ready',()=>{refreshVitalsConnectivity();updateUi(true)});
  window.addEventListener('aura:vitals-context-changed',()=>updateUi(true));
  window.addEventListener('aura:context-contract-changed',e=>{
    const id=safe(e.detail?.context?.workspace||'',32).toLowerCase();
    if(id&&id!=='mind'){pulseNode('context',.80,'context');addRecent('context','Contexte mis à jour','Context')}
    updateUi(true);
  });
  window.addEventListener('aura:workspace-changed',e=>{
    const id=safe(e.detail?.workspace||'',32).toLowerCase();
    if(id==='mind')setOpen(true);else if(STATE.open)setOpen(false);
    if(id==='memory')pulseNode('memory',1,'workspace');
    if(id==='plan')pulseNode('planning',1,'workspace');
    if(id==='talk'||id==='conversation')pulseNode('language',.8,'workspace');
    addRecent('workspace',`Workspace ${id.toUpperCase()||'HOME'}`,'UI');
    updateUi(true);
  });
  window.addEventListener('aura:workspace-activity',e=>{
    const d=e.detail||{},id=safe(d.workspace||'',32).toLowerCase();
    pulseNode('activity',.68,'workspace-activity');
    if(id==='memory')pulseNode('memory',String(d.state||'').toLowerCase()==='loading'?1:.72,'memory-activity');
    if(id==='plan')pulseNode('planning',String(d.state||'').toLowerCase()==='loading'?1:.72,'plan-activity');
    if(toolActivityFromWorkspace(d))pulseNode('tools',String(d.state||'').toLowerCase()==='loading'?1:.82,'workspace-tool-activity');
    addRecent('activity',`${safe(d.label||id||'Activité',80)}`,'Activity');
    updateUi(true);
  });
  window.addEventListener('aura:router-observatory',()=>{pulseNode('tools',.72,'router');addRecent('tool','Route outil détectée','Router');updateUi(true)});
  window.addEventListener('aura:tasks-snapshot',()=>{pulseNode('planning',.92,'tasks');addRecent('planning','Tâches actualisées','Tasks');updateUi(true)});
  window.addEventListener('aura:agenda-snapshot',()=>{pulseNode('planning',.92,'agenda');addRecent('planning','Agenda actualisé','Agenda');updateUi(true)});

  const mo=new MutationObserver(()=>{ensureModuleButton();registerWorkspace();registerContext()});
  mo.observe(document.documentElement,{subtree:true,childList:true});

  window.AuraMindState=Object.freeze({
    version:VERSION,open:()=>setOpen(true),close:()=>setOpen(false),isOpen:()=>STATE.open,
    state:signalSnapshot,nodeSignals:()=>({...nodeSignalSnapshot()}),context:buildContext,
    refresh:()=>{updateUi(true);return signalSnapshot()}
  });

  createRoot();ensureModuleButton();registerWorkspace();registerContext();updateUi(true);refreshVitalsConnectivity();
  window.dispatchEvent(new CustomEvent('aura:mind-ready',{detail:{
    version:VERSION,representation:'simulated-derived',readOnly:true,consciousnessClaim:false,
    features:['cinematic-r3-layout','runtime-state','reactive-topology','event-history','derived-resonance','vitals-connectivity-only','context-contract']
  }}));
})();
