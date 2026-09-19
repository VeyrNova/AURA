/* AURA P0.7.0 — WORKSPACE MANAGER V2
   Major-workspace lifecycle, Maps ownership, overlay contract and local resume state.
   Backward-compatible with the P0.6.3 AuraWorkspace public API.
*/
(()=>{
  'use strict';
  if(window.__AURA_P070_WORKSPACE_V2__)return;
  window.__AURA_P070_WORKSPACE_V2__=true;

  const VERSION='P0.7.0';
  const SNAPSHOT_KEY='aura.workspace.v2.snapshot.v1';
  const SNAPSHOT_TTL_MS=24*60*60*1000;
  const workspaceToken=new URLSearchParams(location.search).get('token')||'';
  const workspaceRoot=document.querySelector('.workspace');
  const registry=new Map();
  const overlayRegistry=new Map();
  const overlayStack=[];
  const activityState=new Map();
  const lifecycleState=new Map();

  let internal=false;
  let raf=0;
  let lastState='__init__';
  let lastCoreWorkspace='__init__';
  let lastRequested='';
  let lastRequestedAt=0;
  let previousOpenSet=new Set();
  let transitionTimer=0;
  let statusHideTimer=0;
  let observer=null;

  const LABELS={home:'HOME',talk:'TALK',plan:'PLAN',weather:'WEATHER',memory:'MEM',system:'SYS',maps:'MAPS'};

  const normId=value=>String(value||'').trim().toLowerCase();
  const safeCall=(fn,...args)=>{try{return typeof fn==='function'?fn(...args):undefined}catch(_){return undefined}};
  const available=item=>!!item && (typeof item.available!=='function'||safeCall(item.available)!==false);
  const isOpen=item=>!!item && safeCall(item.isOpen)===true;
  const byId=id=>registry.get(normId(id))||null;
  const openIds=()=>[...registry.values()].filter(item=>available(item)&&isOpen(item)).map(item=>item.id);
  const buttonFor=id=>safeCall(byId(id)?.button)||null;

  function clonePlace(value){
    if(!value||typeof value!=='object')return null;
    const out={};
    if(Number.isFinite(Number(value.lat)))out.lat=Number(value.lat);
    if(Number.isFinite(Number(value.lon)))out.lon=Number(value.lon);
    if(value.label)out.label=String(value.label).slice(0,300);
    if(value.shortLabel)out.shortLabel=String(value.shortLabel).slice(0,180);
    return Object.keys(out).length?out:null;
  }

  function readSnapshot(){
    try{
      const raw=localStorage.getItem(SNAPSHOT_KEY);
      if(!raw)return {schema:1,lastWorkspace:'',states:{},savedAt:0};
      const parsed=JSON.parse(raw);
      if(!parsed||parsed.schema!==1)return {schema:1,lastWorkspace:'',states:{},savedAt:0};
      if(Number(parsed.savedAt)>0 && Date.now()-Number(parsed.savedAt)>SNAPSHOT_TTL_MS){
        localStorage.removeItem(SNAPSHOT_KEY);
        return {schema:1,lastWorkspace:'',states:{},savedAt:0};
      }
      return {
        schema:1,
        lastWorkspace:normId(parsed.lastWorkspace),
        states:parsed.states&&typeof parsed.states==='object'?parsed.states:{},
        savedAt:Number(parsed.savedAt)||0,
      };
    }catch(_){
      return {schema:1,lastWorkspace:'',states:{},savedAt:0};
    }
  }

  let resumeSnapshot=readSnapshot();

  function writeSnapshot(next){
    resumeSnapshot={
      schema:1,
      lastWorkspace:normId(next?.lastWorkspace),
      states:next?.states&&typeof next.states==='object'?next.states:{},
      savedAt:Number(next?.savedAt)||Date.now(),
    };
    try{localStorage.setItem(SNAPSHOT_KEY,JSON.stringify(resumeSnapshot))}catch(_){}
    updateResumeChip();
  }

  function serializeWorkspace(id){
    const item=byId(id);
    if(!item||typeof item.serialize!=='function')return null;
    const value=safeCall(item.serialize);
    return value&&typeof value==='object'?value:null;
  }

  function rememberWorkspace(id){
    const workspaceId=normId(id);
    if(!workspaceId||workspaceId==='home')return;
    const states={...(resumeSnapshot.states||{})};
    const state=serializeWorkspace(workspaceId);
    if(state)states[workspaceId]=state;
    writeSnapshot({schema:1,lastWorkspace:workspaceId,states,savedAt:Date.now()});
  }

  function stateFor(id){
    return activityState.get(normId(id))||{state:'ready',label:'Prêt',detail:'',at:0};
  }

  function phaseFor(id){
    return lifecycleState.get(normId(id))||'closed';
  }

  function setPhase(id,phase,source='manager'){
    const workspaceId=normId(id);
    if(!workspaceId||workspaceId==='home'||!registry.has(workspaceId))return;
    const next=['opening','open','closing','closed'].includes(phase)?phase:'closed';
    if(lifecycleState.get(workspaceId)===next)return;
    lifecycleState.set(workspaceId,next);
    window.dispatchEvent(new CustomEvent('aura:workspace-lifecycle',{
      detail:{workspace:workspaceId,phase:next,source,version:VERSION}
    }));
  }

  function emitActivity(id,state='ready',label='',detail=''){
    const workspaceId=normId(id);
    if(!registry.has(workspaceId))return false;
    const normalized=['loading','ready','error'].includes(String(state))?String(state):'ready';
    const next={
      state:normalized,
      label:String(label||'').trim()||(normalized==='loading'?'Synchronisation':normalized==='error'?'Erreur':'Prêt'),
      detail:String(detail||'').trim(),
      at:Date.now(),
    };
    activityState.set(workspaceId,next);
    renderActivity(workspaceId);
    return true;
  }

  const status=document.createElement('div');
  status.className='aura-p0631-workspace-status glass aura-p070-workspace-status';
  status.innerHTML='<i></i><b>HOME</b><span>Prêt</span>';
  workspaceRoot?.appendChild(status);
  const statusName=status.querySelector('b');
  const statusText=status.querySelector('span');

  const resumeChip=document.createElement('button');
  resumeChip.type='button';
  resumeChip.className='aura-p070-resume-chip glass';
  resumeChip.hidden=true;
  resumeChip.innerHTML='<i></i><span><small>DERNIER WORKSPACE</small><b>REPRENDRE</b></span><em>↗</em>';
  workspaceRoot?.appendChild(resumeChip);

  function renderActivity(id){
    const item=stateFor(id);
    const button=buttonFor(id);
    if(button){
      button.dataset.workspaceState=item.state;
      button.setAttribute('aria-busy',item.state==='loading'?'true':'false');
    }
    const current=openIds()[0]||'home';
    if(current!==id||!status)return;
    clearTimeout(statusHideTimer);
    status.dataset.state=item.state;
    statusName.textContent=LABELS[id]||byId(id)?.label||String(id).toUpperCase();
    statusText.textContent=item.detail?`${item.label} · ${item.detail}`:item.label;
    status.classList.add('show');
    if(item.state==='ready')statusHideTimer=setTimeout(()=>status.classList.remove('show'),950);
    else if(item.state==='error')statusHideTimer=setTimeout(()=>status.classList.remove('show'),3600);
  }

  function transition(){
    clearTimeout(transitionTimer);
    document.body.classList.remove('aura-workspace-transition');
    void document.body.offsetWidth;
    document.body.classList.add('aura-workspace-transition');
    transitionTimer=setTimeout(()=>document.body.classList.remove('aura-workspace-transition'),190);
  }

  function focusWorkspace(id,{force=false}={}){
    const item=byId(id);
    if(!item||(!force&&id==='home'))return;
    setTimeout(()=>{
      const target=safeCall(item.focusTarget);
      if(!target||target.disabled)return;
      try{target.focus({preventScroll:true})}catch(_){target.focus?.()}
    },35);
  }

  function announceWillChange(from,to,source){
    window.dispatchEvent(new CustomEvent('aura:workspace-will-change',{
      detail:{from:from||'home',to:to||'home',source:String(source||'manager'),version:VERSION}
    }));
  }

  function registerWorkspace(def,{core=false,replace=false}={}){
    const id=normId(def?.id);
    if(!/^[a-z0-9._-]{1,32}$/.test(id))return false;
    if(registry.has(id)&&!replace)return false;
    const item={
      id,
      label:String(def?.label||LABELS[id]||id.toUpperCase()).slice(0,40),
      core:!!core,
      available:typeof def?.available==='function'?def.available:()=>true,
      isOpen:typeof def?.isOpen==='function'?def.isOpen:()=>false,
      open:typeof def?.open==='function'?def.open:()=>false,
      close:typeof def?.close==='function'?def.close:()=>false,
      button:typeof def?.button==='function'?def.button:()=>null,
      focusTarget:typeof def?.focusTarget==='function'?def.focusTarget:()=>null,
      serialize:typeof def?.serialize==='function'?def.serialize:null,
      restore:typeof def?.restore==='function'?def.restore:null,
    };
    registry.set(id,item);
    if(!activityState.has(id))activityState.set(id,{state:'ready',label:'Prêt',detail:'',at:0});
    lifecycleState.set(id,isOpen(item)?'open':'closed');
    scheduleNormalize();
    updateResumeChip();
    window.dispatchEvent(new CustomEvent('aura:workspace-registered',{detail:{workspace:id,version:VERSION}}));
    return true;
  }

  function unregisterWorkspace(id){
    const item=byId(id);
    if(!item||item.core||isOpen(item))return false;
    registry.delete(item.id);
    activityState.delete(item.id);
    lifecycleState.delete(item.id);
    updateResumeChip();
    return true;
  }

  function registerOverlay(def){
    const id=normId(def?.id);
    if(!/^[a-z0-9._-]{1,32}$/.test(id)||overlayRegistry.has(id))return false;
    overlayRegistry.set(id,{
      id,
      label:String(def?.label||id.toUpperCase()).slice(0,40),
      available:typeof def?.available==='function'?def.available:()=>true,
      isOpen:typeof def?.isOpen==='function'?def.isOpen:()=>false,
      open:typeof def?.open==='function'?def.open:()=>false,
      close:typeof def?.close==='function'?def.close:()=>false,
      preserveOnWorkspaceChange:def?.preserveOnWorkspaceChange===true,
    });
    return true;
  }

  function overlayIsOpen(id){
    const item=overlayRegistry.get(normId(id));
    return !!item&&safeCall(item.isOpen)===true;
  }

  function publishOverlay(source='manager'){
    const open=overlayStack.filter(id=>overlayIsOpen(id));
    overlayStack.splice(0,overlayStack.length,...open);
    document.body.dataset.auraWorkspaceOverlay=open[open.length-1]||'';
    window.dispatchEvent(new CustomEvent('aura:workspace-overlay-changed',{
      detail:{stack:[...open],current:open[open.length-1]||'',source,version:VERSION}
    }));
  }

  function openOverlay(id,payload,source='api'){
    const item=overlayRegistry.get(normId(id));
    if(!item||safeCall(item.available)===false)return false;
    if(!overlayIsOpen(item.id))safeCall(item.open,payload);
    const at=overlayStack.indexOf(item.id);
    if(at>=0)overlayStack.splice(at,1);
    overlayStack.push(item.id);
    publishOverlay(source);
    return true;
  }

  function closeOverlay(id,source='api'){
    const item=overlayRegistry.get(normId(id));
    if(!item)return false;
    if(overlayIsOpen(item.id))safeCall(item.close);
    const at=overlayStack.indexOf(item.id);
    if(at>=0)overlayStack.splice(at,1);
    publishOverlay(source);
    return true;
  }

  function closeTopOverlay(source='escape'){
    for(let i=overlayStack.length-1;i>=0;i--){
      const id=overlayStack[i];
      if(overlayIsOpen(id))return closeOverlay(id,source);
      overlayStack.splice(i,1);
    }
    return false;
  }

  function closeOverlaysForWorkspaceChange(source='workspace-change'){
    for(const [id,item] of overlayRegistry){
      if(item.preserveOnWorkspaceChange)continue;
      if(overlayIsOpen(id))closeOverlay(id,source);
    }
  }

  function closeWorkspace(id,source='api'){
    const item=byId(id);
    if(!item||!available(item)||!isOpen(item))return false;
    rememberWorkspace(item.id);
    setPhase(item.id,'closing',source);
    internal=true;
    try{safeCall(item.close)}finally{internal=false}
    scheduleNormalize();
    return true;
  }

  function closeOthers(except='',source='manager'){
    const keep=normId(except);
    for(const item of registry.values()){
      if(item.id!==keep&&isOpen(item))closeWorkspace(item.id,source);
    }
  }

  function openWorkspace(id,opts={},source='api'){
    const item=byId(id);
    if(!item||!available(item))return false;
    const current=openIds()[0]||'home';
    if(isOpen(item)){
      closeOthers(item.id,source);
      lastRequested=item.id;
      lastRequestedAt=Date.now();
      scheduleNormalize();
      focusWorkspace(item.id,{force:true});
      return true;
    }
    announceWillChange(current,item.id,source);
    closeOverlaysForWorkspaceChange(source);
    closeOthers(item.id,source);
    lastRequested=item.id;
    lastRequestedAt=Date.now();
    setPhase(item.id,'opening',source);
    internal=true;
    try{safeCall(item.open,opts)}finally{internal=false}
    scheduleNormalize();
    focusWorkspace(item.id,{force:true});
    return true;
  }

  async function syncCoreWorkspace(workspaceId){
    const id=normId(workspaceId)||'home';
    if(!workspaceToken||id===lastCoreWorkspace)return;
    lastCoreWorkspace=id;
    try{
      const response=await fetch(`/api/action?token=${encodeURIComponent(workspaceToken)}`,{
        method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'workspace_context',workspace:id})
      });
      if(!response.ok)throw new Error(`HTTP ${response.status}`);
    }catch(_){
      lastCoreWorkspace='__retry__';
    }
  }

  function updateResumeChip(){
    if(!resumeChip)return;
    const current=openIds()[0]||'home';
    const id=normId(resumeSnapshot.lastWorkspace);
    const item=byId(id);
    const valid=current==='home'&&id&&item&&available(item)&&Date.now()-Number(resumeSnapshot.savedAt||0)<=SNAPSHOT_TTL_MS;
    resumeChip.hidden=!valid;
    resumeChip.classList.toggle('show',!!valid);
    if(!valid)return;
    const label=item.label||LABELS[id]||id.toUpperCase();
    resumeChip.querySelector('b').textContent=`REPRENDRE ${label}`;
    const when=Number(resumeSnapshot.savedAt)||0;
    resumeChip.title=when?`Dernier workspace local · ${new Date(when).toLocaleString('fr-FR')}`:'Dernier workspace local';
  }

  function publish(current){
    const workspaceId=normId(current)||'home';
    if(workspaceId===lastState){updateResumeChip();return}
    const previous=lastState==='__init__'?'home':lastState;
    lastState=workspaceId;
    document.body.dataset.auraWorkspace=workspaceId;
    document.body.dataset.auraWorkspaceV2=VERSION;
    document.body.dataset.auraWorkspacePhase=workspaceId==='home'?'home':phaseFor(workspaceId);
    if(workspaceId!=='home')rememberWorkspace(workspaceId);
    syncCoreWorkspace(workspaceId);
    transition();
    if(status){
      clearTimeout(statusHideTimer);
      status.classList.remove('show');
      if(workspaceId!=='home')renderActivity(workspaceId);
    }
    updateResumeChip();
    window.dispatchEvent(new CustomEvent('aura:workspace-changed',{
      detail:{workspace:workspaceId,previous,version:VERSION}
    }));
  }

  function normalize(){
    raf=0;
    let opened=openIds();
    const newlyOpened=opened.filter(id=>!previousOpenSet.has(id));

    if(opened.length>1){
      const published=normId(document.body.dataset.auraWorkspace);
      let keep='';
      if(newlyOpened.length===1){
        const candidate=newlyOpened[0];
        // Conversation can be passively opened by incoming messages. It must
        // not steal ownership from an active contextual workspace.
        if(candidate==='talk'&&published&&published!=='home'&&opened.includes(published))keep=published;
        else keep=candidate;
      }
      if(!keep&&lastRequested&&Date.now()-lastRequestedAt<500&&opened.includes(lastRequested))keep=lastRequested;
      if(!keep&&published&&published!=='home'&&opened.includes(published))keep=published;
      if(!keep)keep=opened[opened.length-1];
      closeOthers(keep,'normalize-conflict');
      opened=openIds();
    }

    const openedSet=new Set(opened);
    for(const item of registry.values()){
      const isNowOpen=openedSet.has(item.id);
      setPhase(item.id,isNowOpen?'open':'closed','normalize');
      const button=buttonFor(item.id);
      if(button)button.classList.toggle('active',isNowOpen);
    }
    const home=document.querySelector('#homeBtn');
    if(home)home.classList.toggle('active',opened.length===0);

    previousOpenSet=openedSet;
    const current=opened[0]||'';
    if(current)document.body.dataset.auraWorkspacePhase='open';
    publish(current);
  }

  function scheduleNormalize(){
    if(raf)return;
    raf=requestAnimationFrame(normalize);
  }

  function workspaceFromButton(button){
    if(!button)return'';
    for(const item of registry.values()){
      const owner=buttonFor(item.id);
      if(owner&&button===owner)return item.id;
    }
    return'';
  }

  function restoreLast(source='resume-chip'){
    const stored=readSnapshot();
    if(stored.lastWorkspace || !resumeSnapshot.lastWorkspace) resumeSnapshot=stored;
    const id=normId(resumeSnapshot.lastWorkspace);
    const item=byId(id);
    if(!item||!available(item))return false;
    const state=resumeSnapshot.states?.[id]||null;
    const current=openIds()[0]||'home';
    announceWillChange(current,id,source);
    closeOverlaysForWorkspaceChange(source);
    closeOthers(id,source);
    lastRequested=id;
    lastRequestedAt=Date.now();
    setPhase(id,'opening',source);
    internal=true;
    try{
      if(typeof item.restore==='function')safeCall(item.restore,state);
      else safeCall(item.open,state||{});
    }finally{internal=false}
    scheduleNormalize();
    focusWorkspace(id,{force:true});
    setTimeout(()=>{
      if(isOpen(item))window.dispatchEvent(new CustomEvent('aura:workspace-restored',{detail:{workspace:id,source,version:VERSION}}));
    },80);
    return true;
  }

  function snapshot(){
    const current=openIds()[0]||'home';
    if(current!=='home')rememberWorkspace(current);
    const stored=readSnapshot();
    const snap=stored.lastWorkspace ? stored : resumeSnapshot;
    return JSON.parse(JSON.stringify({
      version:VERSION,
      current,
      lastWorkspace:snap.lastWorkspace,
      savedAt:snap.savedAt,
      states:snap.states,
      overlays:overlayStack.filter(id=>overlayIsOpen(id)),
    }));
  }

  function refreshWorkspace(id){
    const target=normId(id)||openIds()[0]||'home';
    if(target==='home'||!registry.has(target))return false;
    window.dispatchEvent(new CustomEvent('aura:workspace-refresh',{detail:{workspace:target,source:'workspace-v2-api'}}));
    return true;
  }

  // Built-in workspace adapters. Owners keep their own UI cleanup logic.
  registerWorkspace({
    id:'talk',label:'TALK',
    available:()=>!!document.querySelector('#talkBtn'),
    isOpen:()=>document.querySelector('#conversation')?.classList.contains('open')===true,
    open:()=>document.querySelector('#talkBtn')?.click(),
    close:()=>{const x=document.querySelector('#closeTalk');if(x)x.click();else document.querySelector('#conversation')?.classList.remove('open')},
    button:()=>document.querySelector('#talkBtn'),
    focusTarget:()=>document.querySelector('#messageInput'),
  },{core:true});

  registerWorkspace({
    id:'plan',label:'PLAN',
    available:()=>!!document.querySelector('.aura-p0623-productivity-btn'),
    isOpen:()=>document.querySelector('.aura-p0623-drawer')?.classList.contains('open')===true,
    open:()=>document.querySelector('.aura-p0623-productivity-btn')?.click(),
    close:()=>document.querySelector('.aura-p0623-productivity-btn')?.click(),
    button:()=>document.querySelector('.aura-p0623-productivity-btn'),
    focusTarget:()=>document.querySelector('.aura-p0623-drawer.open .aura-p0623-content input:not([type="hidden"]), .aura-p0623-drawer.open button[data-tab]'),
  },{core:true});

  registerWorkspace({
    id:'weather',label:'WEATHER',
    available:()=>!!document.querySelector('#auraWeatherBtn'),
    isOpen:()=>document.body.classList.contains('aura-weather-active'),
    open:()=>document.querySelector('#auraWeatherBtn')?.click(),
    close:()=>document.querySelector('#auraWeatherBtn')?.click(),
    button:()=>document.querySelector('#auraWeatherBtn'),
    focusTarget:()=>document.querySelector('.aura-weather-workspace.open button, .aura-weather-workspace.open [tabindex]'),
  },{core:true});

  registerWorkspace({
    id:'memory',label:'MEM',
    available:()=>!!document.querySelector('#memoryBtn'),
    isOpen:()=>document.querySelector('.aura-p0626-memory')?.classList.contains('open')===true,
    open:()=>document.querySelector('#memoryBtn')?.click(),
    close:()=>document.querySelector('#memoryBtn')?.click(),
    button:()=>document.querySelector('#memoryBtn'),
    focusTarget:()=>document.querySelector('.aura-p0626-memory.open [data-search], .aura-p0626-memory.open button'),
  },{core:true});

  registerWorkspace({
    id:'system',label:'SYS',
    available:()=>!!document.querySelector('#systemBtn'),
    isOpen:()=>document.querySelector('.aura-p0627-system')?.classList.contains('open')===true,
    open:()=>document.querySelector('#systemBtn')?.click(),
    close:()=>document.querySelector('#systemBtn')?.click(),
    button:()=>document.querySelector('#systemBtn'),
    focusTarget:()=>document.querySelector('.aura-p0627-system.open [data-safe-app], .aura-p0627-system.open button'),
  },{core:true});

  registerWorkspace({
    id:'maps',label:'MAPS',
    available:()=>typeof window.AURA_NAVIGATION?.open==='function',
    isOpen:()=>document.querySelector('#auraNavigationWorkspace')?.classList.contains('open')===true||document.body.classList.contains('aura-navigation-active'),
    open:opts=>window.AURA_NAVIGATION?.open?.(opts||{}),
    close:()=>window.AURA_NAVIGATION?.close?.(),
    focusTarget:()=>document.querySelector('#auraNavigationWorkspace.open #auraNavDestinationInput'),
    serialize:()=>{
      const s=window.AURA_NAVIGATION?.state;
      if(!s)return null;
      const destination=clonePlace(s.destination);
      const origin=clonePlace(s.origin);
      const currentOrigin=origin&&/position actuelle/i.test(String(origin.label||''));
      return {
        center:Number.isFinite(Number(s.centerLat))&&Number.isFinite(Number(s.centerLon))?{lat:Number(s.centerLat),lon:Number(s.centerLon),zoom:Number(s.zoom)||6}:null,
        destination,
        origin:currentOrigin?null:origin,
      };
    },
    restore:state=>{
      const opts={};
      if(state?.center&&Number.isFinite(Number(state.center.lat))&&Number.isFinite(Number(state.center.lon)))opts.center={lat:Number(state.center.lat),lon:Number(state.center.lon),zoom:Number(state.center.zoom)||6};
      if(state?.destination)opts.destination=state.destination;
      if(state?.origin)opts.origin=state.origin;
      window.AURA_NAVIGATION?.open?.(opts);
    },
  },{core:true});

  // Capture direct rail navigation before legacy module listeners.
  document.addEventListener('click',event=>{
    const button=event.target?.closest?.('.rail-btn, #homeBtn');
    if(!button||internal)return;
    if(button.matches?.('#homeBtn')){
      const current=openIds()[0]||'home';
      announceWillChange(current,'home','rail-home');
      closeOverlaysForWorkspaceChange('rail-home');
      closeOthers('','rail-home');
      lastRequested='';lastRequestedAt=Date.now();
      setTimeout(scheduleNormalize,0);
      return;
    }
    const requested=workspaceFromButton(button);
    if(!requested)return;
    const item=byId(requested);
    const current=openIds()[0]||'home';
    lastRequested=requested;lastRequestedAt=Date.now();
    if(!isOpen(item)){
      announceWillChange(current,requested,'rail');
      closeOverlaysForWorkspaceChange('rail');
      closeOthers(requested,'rail');
      setPhase(requested,'opening','rail');
    }else if(requested!=='talk'){
      rememberWorkspace(requested);
      setPhase(requested,'closing','rail-toggle');
    }
    focusWorkspace(requested,{force:true});
    setTimeout(scheduleNormalize,0);
  },true);

  // Escape closes overlays first, then the major workspace. Command Palette owns
  // its own Escape handling and must not accidentally close the workspace below.
  document.addEventListener('keydown',event=>{
    if(event.key!=='Escape'||event.defaultPrevented||internal)return;
    if(document.body.classList.contains('aura-command-palette-open')||event.target?.closest?.('.aura-p0635-palette'))return;
    if(closeTopOverlay('escape')){
      event.preventDefault();
      return;
    }
    const current=openIds()[0]||'';
    if(!current)return;
    event.preventDefault();
    announceWillChange(current,'home','escape');
    closeWorkspace(current,'escape');
    lastRequested='';lastRequestedAt=Date.now();
    setTimeout(()=>{
      const railButton=buttonFor(current)||document.querySelector('#homeBtn');
      try{railButton?.focus({preventScroll:true})}catch(_){railButton?.focus?.()}
    },30);
  },true);

  // Existing owners can still open themselves (navigation text trigger, weather
  // events, incoming TALK). Mutation observation reconciles ownership.
  observer=new MutationObserver(scheduleNormalize);
  observer.observe(document.body,{subtree:true,attributes:true,attributeFilter:['class'],childList:true});

  window.addEventListener('aura:workspace-activity',event=>{
    const d=event.detail||{};
    emitActivity(d.workspace,d.state,d.label,d.detail);
  });

  // Maps can also be requested by its explicit event contract.
  window.addEventListener('aura:navigation:open',()=>{
    lastRequested='maps';lastRequestedAt=Date.now();
    closeOverlaysForWorkspaceChange('navigation-event');
    closeOthers('maps','navigation-event');
    setPhase('maps','opening','navigation-event');
    setTimeout(scheduleNormalize,0);
  });

  resumeChip?.addEventListener('click',()=>restoreLast('resume-chip'));

  // P0.6.3.4.1 UI-local contextual actions, extended with MAPS.
  function normalizeCommand(text){
    return String(text||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[’'-]/g,' ').replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim();
  }
  const REFRESH_COMMANDS=new Set(['rafraichis ici','rafraichis cette fenetre','rafraichis ce panneau','actualise ici','actualise cette fenetre','actualise ce panneau','mets a jour cette fenetre','mets a jour ce panneau']);
  const OPEN_COMMANDS=new Map([
    ['ouvre talk','talk'],['ouvre la conversation','talk'],['ouvre conversation','talk'],['va dans talk','talk'],['affiche la conversation','talk'],
    ['ouvre plan','plan'],['ouvre le plan','plan'],['ouvre la planification','plan'],['va dans plan','plan'],['affiche plan','plan'],
    ['ouvre weather','weather'],['ouvre la meteo','weather'],['ouvre meteo','weather'],['va dans weather','weather'],['affiche la meteo','weather'],
    ['ouvre mem','memory'],['ouvre la memoire','memory'],['ouvre memoire','memory'],['va dans mem','memory'],['affiche la memoire','memory'],
    ['ouvre sys','system'],['ouvre le systeme','system'],['ouvre systeme','system'],['va dans sys','system'],['affiche le systeme','system'],
    ['ouvre maps','maps'],['ouvre la carte','maps'],['ouvre carte','maps'],['ouvre navigation','maps'],['ouvre la navigation','maps'],['ouvre itineraire','maps'],['ouvre l itineraire','maps'],['va dans maps','maps'],
  ]);
  const ACTION_LABELS={talk:'TALK',plan:'PLAN',weather:'WEATHER',memory:'MEM',system:'SYS',maps:'MAPS'};

  async function speakLocal(text){
    if(!workspaceToken||!text)return;
    try{await fetch(`/api/action?token=${encodeURIComponent(workspaceToken)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:'voice_speak',text:String(text)})})}catch(_){}
  }

  function showLocalConfirmation(text,workspaceId){
    if(window.AuraResponseDock?.show&&workspaceId&&workspaceId!=='talk')window.AuraResponseDock.show(text,workspaceId);
  }

  function executeTypedContextAction(rawText){
    const value=normalizeCommand(rawText);
    if(!value)return false;
    const current=openIds()[0]||'home';
    if(REFRESH_COMMANDS.has(value)&&['plan','weather','memory','system'].includes(current)){
      refreshWorkspace(current);
      const reply=`J'actualise ${ACTION_LABELS[current]}.`;
      showLocalConfirmation(reply,current);speakLocal(reply);return true;
    }
    const target=OPEN_COMMANDS.get(value);
    if(target&&openWorkspace(target,{},'ui-local-context-action')){
      const reply=`J'ouvre ${ACTION_LABELS[target]}.`;
      if(target!=='talk')showLocalConfirmation(reply,target);
      speakLocal(reply);return true;
    }
    return false;
  }

  function consumeComposerAction(){
    const input=document.querySelector('#messageInput');
    const text=String(input?.value||'').trim();
    if(!text||!executeTypedContextAction(text))return false;
    input.value='';input.style.height='auto';input.dispatchEvent(new Event('input',{bubbles:true}));return true;
  }

  document.addEventListener('keydown',event=>{
    if(event.key==='Enter'&&!event.shiftKey&&event.target?.matches?.('#messageInput')&&consumeComposerAction()){
      event.preventDefault();event.stopImmediatePropagation();
    }
  },true);
  document.addEventListener('click',event=>{
    if(event.target?.closest?.('#sendBtn')&&consumeComposerAction()){
      event.preventDefault();event.stopImmediatePropagation();
    }
  },true);

  const overlayApi=Object.freeze({
    register:registerOverlay,
    unregister(id){const key=normId(id);if(overlayIsOpen(key))return false;return overlayRegistry.delete(key)},
    open:(id,payload)=>openOverlay(id,payload,'api'),
    close:id=>closeOverlay(id,'api'),
    closeTop:()=>closeTopOverlay('api'),
    current:()=>overlayStack.filter(id=>overlayIsOpen(id)).slice(-1)[0]||'',
    list:()=>[...overlayRegistry.values()].map(item=>({id:item.id,label:item.label,available:safeCall(item.available)!==false,open:overlayIsOpen(item.id),preserveOnWorkspaceChange:item.preserveOnWorkspaceChange})),
  });

  const api={
    version:VERSION,
    current:()=>openIds()[0]||'home',
    conversationPolicy:()=>({passiveAutoOpen:'background-when-context-workspace-active',explicitTalkClick:'foreground'}),
    open:(id,opts)=>openWorkspace(id,opts||{},'api'),
    close:id=>closeWorkspace(normId(id),'api'),
    home(){
      const current=openIds()[0]||'home';
      announceWillChange(current,'home','api');
      closeOverlaysForWorkspaceChange('api-home');
      closeOthers('','api-home');
      lastRequested='';lastRequestedAt=Date.now();scheduleNormalize();return true;
    },
    refresh:refreshWorkspace,
    restoreLast,
    snapshot,
    register:def=>registerWorkspace(def,{core:false}),
    unregister:unregisterWorkspace,
    state(id){return {...stateFor(normId(id)),phase:phaseFor(id)}},
    activity:emitActivity,
    executeTypedContextAction,
    list:()=>[...registry.values()].map(item=>({id:item.id,label:item.label,available:available(item),open:isOpen(item),phase:phaseFor(item.id),activity:{...stateFor(item.id)},resumable:typeof item.restore==='function'||typeof item.open==='function'})),
    overlays:overlayApi,
  };

  window.AuraWorkspace=Object.freeze(api);
  window.AuraWorkspaceV2=window.AuraWorkspace;
  document.body.dataset.auraWorkspaceV2=VERSION;

  window.addEventListener('beforeunload',()=>{
    const current=openIds()[0]||'home';
    if(current!=='home')rememberWorkspace(current);
  });

  scheduleNormalize();
  setTimeout(()=>{scheduleNormalize();updateResumeChip()},80);
  window.dispatchEvent(new CustomEvent('aura:workspace-manager-ready',{
    detail:{version:VERSION,manager:'v2',workspaces:[...registry.keys()],features:['lifecycle','maps-ownership','overlay-contract','local-resume','dynamic-registry']}
  }));
})();
