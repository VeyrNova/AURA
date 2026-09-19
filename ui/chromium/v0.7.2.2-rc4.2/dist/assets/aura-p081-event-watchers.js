/* AURA P0.8.3.2 — EVENT DEDUP + COOLDOWN MERGE HOTFIX
   Based on AURA P0.8.1.5 Event Watchers Global Top Baseline Normalization.
   Proactive detection foundation for AURA.
   Privacy / authority contract:
   - All watcher families are OFF by default and require an explicit user opt-in.
   - This layer detects and proposes; it never executes a sensitive action automatically.
   - System watcher only reads the existing authenticated loopback /api/system endpoint.
   - Agenda, Tasks, Files and Research consume explicit published events/snapshots only.
   - No filesystem enumeration, hidden DOM scraping, conversation reading or cloud transmission.
*/
(()=>{
  'use strict';
  if(window.__AURA_P081_EVENT_WATCHERS__)return;
  window.__AURA_P081_EVENT_WATCHERS__=true;

  const VERSION='P0.8.1.5';
  const STORAGE='aura.event-watchers.p081';
  const MAX_EVENTS=80;
  const POLL_MS=15000;
  const token=new URLSearchParams(location.search).get('token')||'';
  const FAMILIES=['agenda','tasks','system','files','research'];
  const LABELS={agenda:'AGENDA',tasks:'TÂCHES',system:'SYSTÈME',files:'FICHIERS',research:'RECHERCHE'};
  const ICONS={agenda:'◷',tasks:'✓',system:'◇',files:'▱',research:'⌕'};
  const STATE={settings:null,events:[],panel:null,entry:null,registered:false,passiveRegistered:false,overlayRegistered:false,activationTimer:0,timer:0,sourceTimer:0,systemHud:null,systemHudPinned:false,system:{high:{}},sources:new Map(),lastSnapshots:{agenda:null,tasks:null}};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const safe=(v,n=220)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const clone=v=>{try{return JSON.parse(JSON.stringify(v))}catch(_e){return null}};
  const nowIso=()=>new Date().toISOString();
  const finite=v=>Number.isFinite(Number(v));
  const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const uid=()=>`evt-${Date.now().toString(36)}-${Math.random().toString(36).slice(2,8)}`;

  function defaults(){return {paused:false,families:{agenda:false,tasks:false,system:false,files:false,research:false},system:{ram:90,cpu:95,vram:95,sustainSeconds:120},retention:MAX_EVENTS}}
  function normalizeSettings(raw){
    const d=defaults(),r=raw&&typeof raw==='object'?raw:{};
    d.paused=!!r.paused;
    FAMILIES.forEach(k=>d.families[k]=!!r.families?.[k]);
    ['ram','cpu','vram'].forEach(k=>{const n=Number(r.system?.[k]);if(Number.isFinite(n)&&n>=50&&n<=100)d.system[k]=Math.round(n)});
    const s=Number(r.system?.sustainSeconds);if(Number.isFinite(s)&&s>=30&&s<=900)d.system.sustainSeconds=Math.round(s);
    return d;
  }
  function load(){
    try{const raw=JSON.parse(localStorage.getItem(STORAGE)||'{}');STATE.events=collapseEventHistory(Array.isArray(raw.events)?raw.events.slice(0,MAX_EVENTS).map(normalizeEvent).filter(Boolean):[]);return normalizeSettings(raw.settings)}catch(_e){STATE.events=[];return defaults()}
  }
  function persist(){
    try{localStorage.setItem(STORAGE,JSON.stringify({settings:STATE.settings,events:STATE.events.slice(0,MAX_EVENTS)}))}catch(_e){}
  }
  function enabled(family){return !STATE.settings.paused&&!!STATE.settings.families[family]}
  function normalizeEvent(raw){
    if(!raw||typeof raw!=='object')return null;
    const family=FAMILIES.includes(safe(raw.family,24))?safe(raw.family,24):'';if(!family)return null;
    const severity=['info','important','critical'].includes(raw.severity)?raw.severity:'info';
    return {id:safe(raw.id,80)||uid(),family,severity,title:safe(raw.title,120)||LABELS[family],message:safe(raw.message,500),at:safe(raw.at,40)||nowIso(),source:safe(raw.source,80)||'aura-event',fingerprint:safe(raw.fingerprint,180),status:['new','seen','dismissed'].includes(raw.status)?raw.status:'new',suggestion:safe(raw.suggestion,420),meta:raw.meta&&typeof raw.meta==='object'?clone(raw.meta):null};
  }
  function eventFingerprint(e){return safe(e.fingerprint||`${e.family}|${e.title}|${e.message}`,180)}
  const DEDUP_WINDOW_MS=20*60*1000;
  function isNotificationTest(e){return !!e?.meta?.notificationTest||(/^p083-local-test/i.test(safe(e?.source,80))&&/^Test notification P0\.8\.3/i.test(safe(e?.title,120)))}
  function eventDedupKey(e){return isNotificationTest(e)?'p083-notification-test':eventFingerprint(e)}
  function repeatCount(e){const n=Number(e?.meta?.repeatCount);return Number.isFinite(n)&&n>=1?Math.min(999,Math.round(n)):1}
  function eventTime(e){const t=Date.parse(e?.at||'');return Number.isFinite(t)?t:0}
  function mergeEvent(target,incoming,{historical=false}={}){
    if(!target||!incoming)return target;
    const previous=repeatCount(target),added=repeatCount(incoming),first=target?.meta?.firstOccurrenceAt||incoming?.meta?.firstOccurrenceAt||target.at||incoming.at||nowIso();
    const incomingNewer=eventTime(incoming)>=eventTime(target);
    if(incomingNewer){target.at=incoming.at||nowIso();target.severity=incoming.severity||target.severity;target.title=incoming.title||target.title;target.message=incoming.message||target.message;target.suggestion=incoming.suggestion||target.suggestion;target.source=incoming.source||target.source}
    target.meta=Object.assign({},target.meta||{},incoming.meta||{},{repeatCount:Math.min(999,previous+added),firstOccurrenceAt:first,lastOccurrenceAt:incoming.at||target.at||nowIso(),deduplicated:true});
    if(isNotificationTest(target)||isNotificationTest(incoming)){target.fingerprint='p083-notification-test';target.meta.notificationTest=true;target.meta.simulated=true}
    if(!historical)target.status='new';
    return target;
  }
  function collapseEventHistory(list){
    const out=[];
    for(const e0 of Array.isArray(list)?list:[]){
      const e=e0;const key=eventDedupKey(e);const t=eventTime(e);let recent=null;
      for(const x of out){if(eventDedupKey(x)!==key)continue;const xt=eventTime(x);if(!t||!xt||Math.abs(xt-t)<DEDUP_WINDOW_MS){recent=x;break}}
      if(recent)mergeEvent(recent,e,{historical:true});
      else{e.meta=Object.assign({},e.meta||{},{repeatCount:repeatCount(e),firstOccurrenceAt:e?.meta?.firstOccurrenceAt||e.at,lastOccurrenceAt:e?.meta?.lastOccurrenceAt||e.at});if(isNotificationTest(e))e.fingerprint='p083-notification-test';out.push(e)}
    }
    return out.slice(0,MAX_EVENTS);
  }
  function unread(){return STATE.events.filter(e=>e.status==='new').length}
  function emit(name,detail){window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}))}
  function addEvent(raw){
    const e=normalizeEvent(raw);if(!e||!enabled(e.family))return false;
    const key=eventDedupKey(e),now=Date.now(),recent=STATE.events.find(x=>eventDedupKey(x)===key&&(!eventTime(x)||now-eventTime(x)<DEDUP_WINDOW_MS));
    if(recent){mergeEvent(recent,e);persist();render();updateEntry();const count=repeatCount(recent);emit('aura:watcher-detected',{event:clone(recent),unread:unread(),merged:true,repeatCount:count,dedupKey:key});emit('aura:watcher-event-merged',{eventId:recent.id,repeatCount:count,dedupKey:key});return true}
    e.meta=Object.assign({},e.meta||{},{repeatCount:repeatCount(e),firstOccurrenceAt:e.at,lastOccurrenceAt:e.at});if(isNotificationTest(e))e.fingerprint='p083-notification-test';
    STATE.events.unshift(e);STATE.events=STATE.events.slice(0,MAX_EVENTS);persist();render();updateEntry();
    emit('aura:watcher-detected',{event:clone(e),unread:unread(),merged:false,repeatCount:repeatCount(e),dedupKey:key});
    window.AuraAccessibility?.announce?.(`${LABELS[e.family]||e.family}. ${e.title}.`);
    return true;
  }
  function setEventStatus(id,status){const e=STATE.events.find(x=>x.id===id);if(!e)return false;e.status=status;persist();render();updateEntry();emit('aura:watcher-event-status',{id,status,unread:unread()});return true}
  function clearEvents(){STATE.events=[];persist();render();updateEntry();emit('aura:watcher-events-cleared',{unread:0});return true}

  function moduleGrid(){return q('.aura-p0702-module-grid')||q('[class*="module-grid"]')}
  function ensureEntry(){const grid=moduleGrid();if(!grid)return null;const legacy=q('[data-module="activity-center"]',grid);if(legacy)legacy.remove();return q('[data-module="notifications"]',grid)||null;}
  function updateEntry(){
    const b=STATE.entry||q('[data-module="activity-center"]');if(!b)return;
    const n=unread(),badge=q('[data-p081-badge]',b);if(badge){badge.textContent=String(Math.min(n,99));badge.hidden=!n}
    b.dataset.active=STATE.settings?.paused?'paused':(FAMILIES.some(enabled)?'watching':'off');
    b.setAttribute('aria-label',`Activity Center, ${n} détection${n>1?'s':''} non lue${n>1?'s':''}`);
  }

  function familyCard(id){
    const on=!!STATE.settings.families[id];
    const descriptions={agenda:'Rendez-vous et échéances publiés explicitement',tasks:'Tâches et dates limites publiées explicitement',system:'Pression RAM / CPU / VRAM via le runtime local',files:'Changements de fichiers autorisés publiés par File Intelligence',research:'Résultats de recherches surveillées publiés explicitement'};
    return `<button type="button" class="aura-p081-family ${on?'active':''}" data-p081-family="${id}" aria-pressed="${on}"><span class="aura-p081-family-icon">${ICONS[id]}</span><span><b>${LABELS[id]}</b><small>${descriptions[id]}</small></span><i>${on?'ACTIF':'OFF'}</i></button>`;
  }
  function ensurePanel(){
    if(STATE.panel?.isConnected)return STATE.panel;
    const root=document.createElement('aside');root.className='aura-p081-panel';root.hidden=true;root.setAttribute('role','dialog');root.setAttribute('aria-modal','false');root.setAttribute('aria-label','Activity Center AURA');
    root.innerHTML=`
      <header><div><small>AURA · PROACTIVE CORE</small><b>ACTIVITY CENTER</b><em>Détecter et proposer · jamais agir sans accord</em></div><div class="aura-p081-head-actions"><button type="button" data-p081-action="pause" aria-pressed="false">PAUSE</button><button type="button" data-p081-action="close" aria-label="Fermer">×</button></div></header>
      <div class="aura-p081-body">
        <section class="aura-p081-overview"><div><span class="aura-p081-dot"></span><b data-p081-state>VEILLE ARRÊTÉE</b><small data-p081-summary>Aucune surveillance active</small></div><strong data-p081-unread>0</strong></section>
        <section class="aura-p081-section"><div class="aura-p081-section-title"><span>SURVEILLANCES AUTORISÉES</span><small>OFF PAR DÉFAUT</small></div><div class="aura-p081-families">${FAMILIES.map(familyCard).join('')}</div></section>
        <section class="aura-p081-section aura-p081-events-section"><div class="aura-p081-section-title"><span>DÉTECTIONS RÉCENTES</span><button type="button" data-p081-action="mark-seen">TOUT MARQUER LU</button></div><div class="aura-p081-events" data-p081-events></div></section>
        <section class="aura-p081-privacy"><b>CONTRÔLE LOCAL</b><span>Les surveillances restent locales. Agenda, tâches, fichiers et recherche ne sont lus que via des événements explicitement publiés par leurs modules. Aucune action sensible n’est exécutée ici.</span></section>
      </div>
      <footer><button type="button" data-p081-action="clear">EFFACER L’HISTORIQUE</button><span data-p081-footer>Event Watchers · P0.8.1.5</span></footer>`;
    root.addEventListener('click',onPanelClick);document.body.appendChild(root);STATE.panel=root;render();return root;
  }
  function eventCard(e){
    const dt=new Date(e.at);const when=Number.isNaN(dt.getTime())?'':dt.toLocaleString('fr-FR',{hour:'2-digit',minute:'2-digit',day:'2-digit',month:'2-digit'});
    const repeats=repeatCount(e);return `<article class="aura-p081-event" data-status="${e.status}" data-severity="${e.severity}" data-event-id="${escapeHtml(e.id)}"><div class="aura-p081-event-icon">${ICONS[e.family]}</div><div class="aura-p081-event-main"><div class="aura-p081-event-meta"><b>${escapeHtml(LABELS[e.family])}</b><span>${escapeHtml(when)}${repeats>1?` <em class="aura-p0832-repeat">×${repeats}</em>`:''}</span></div><strong>${escapeHtml(e.title)}</strong><p>${escapeHtml(e.message||'Événement détecté.')}</p><div class="aura-p081-event-actions">${e.suggestion?'<button type="button" data-p081-event-action="suggest">PROPOSER À AURA</button>':''}<button type="button" data-p081-event-action="dismiss">IGNORER</button></div></div></article>`;
  }
  function render(){
    const root=STATE.panel;if(!root)return;
    FAMILIES.forEach(id=>{const b=q(`[data-p081-family="${id}"]`,root);if(b){const on=!!STATE.settings.families[id];b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));const i=q('i',b);if(i)i.textContent=on?'ACTIF':'OFF'}});
    const active=FAMILIES.filter(enabled),paused=STATE.settings.paused;
    const state=q('[data-p081-state]',root),summary=q('[data-p081-summary]',root),count=q('[data-p081-unread]',root),pause=q('[data-p081-action="pause"]',root),list=q('[data-p081-events]',root);
    if(state)state.textContent=paused?'VEILLE EN PAUSE':active.length?'VEILLE ACTIVE':'VEILLE ARRÊTÉE';
    if(summary)summary.textContent=paused?'Aucune détection pendant la pause':active.length?`${active.length} surveillance${active.length>1?'s':''} autorisée${active.length>1?'s':''}`:'Activez uniquement les sources utiles';
    if(count)count.textContent=String(unread());
    if(pause){pause.textContent=paused?'REPRENDRE':active.length?'PAUSE':'VEILLE OFF';pause.disabled=!active.length&&!paused;pause.setAttribute('aria-pressed',String(paused));pause.classList.toggle('active',paused)}
    if(list)list.innerHTML=STATE.events.length?STATE.events.slice(0,30).map(eventCard).join(''):'<div class="aura-p081-empty"><span>◇</span><b>AUCUNE DÉTECTION</b><small>Les événements autorisés apparaîtront ici.</small></div>';
    root.dataset.watching=active.length?'true':'false';root.dataset.paused=paused?'true':'false';
  }
  const currentWorkspace=()=>safe(window.AuraWorkspace?.current?.()||document.body.dataset.auraWorkspace||'home',32).toLowerCase()||'home';
  const overlayApi=()=>window.AuraWorkspace?.overlays||null;
  const panelIsOpen=()=>!!STATE.panel&&!STATE.panel.hidden&&STATE.panel.classList.contains('open');
  function syncDockContext(){
    const open=panelIsOpen(),id=currentWorkspace();
    document.body.classList.toggle('aura-p0812-activity-docked',open);
    document.body.dataset.auraActivityContext=open?id:'';
    document.documentElement.dataset.auraActivityCenter=open?'open':'closed';
    STATE.panel?.setAttribute('data-workspace-context',id);
    pinSystemLive('dock-sync');
  }
  const SYSTEM_HUD_ANCHORS=['displayGpu','computeGpu','voiceState','providerState','eventLink','wave'];
  function systemHudCandidate(){
    const nodes=SYSTEM_HUD_ANCHORS.map(id=>document.getElementById(id)).filter(Boolean);
    if(nodes.length<5)return null;
    let el=nodes[0];
    while(el&&el!==document.body&&el!==document.documentElement){
      if(nodes.every(n=>el.contains(n))&&!el.querySelector('#stage')&&!el.matches('.workspace,.hero,#conversation')){
        const r=el.getBoundingClientRect?.();
        if(!r||!r.width||r.width<=520)return el;
      }
      el=el.parentElement;
    }
    return null;
  }
  function measureSystemHud(hud){
    const r=hud?.getBoundingClientRect?.();
    const w=Math.round(Number(r?.width)||0);
    const width=Math.max(286,Math.min(410,w||318));
    document.documentElement.style.setProperty('--aura-p0813-system-hud-measured',`${width}px`);
    return width;
  }
  function pinSystemLive(reason='runtime'){
    const hud=STATE.systemHud?.isConnected?STATE.systemHud:systemHudCandidate();
    if(!hud)return false;
    if(STATE.systemHud&&STATE.systemHud!==hud)STATE.systemHud.classList.remove('aura-p0813-system-hud-persistent');
    STATE.systemHud=hud;
    hud.classList.add('aura-p0813-system-hud-persistent');
    hud.dataset.auraShellPersistent='system-live';
    hud.setAttribute('aria-label',hud.getAttribute('aria-label')||'System Live AURA');
    const width=measureSystemHud(hud);
    document.body.classList.add('aura-p0813-system-hud-ready');
    document.documentElement.dataset.auraSystemHud='persistent';
    if(!STATE.systemHudPinned){
      STATE.systemHudPinned=true;
      emit('aura:system-live-persistent',{reason,width,anchors:SYSTEM_HUD_ANCHORS.slice()});
    }
    return true;
  }
  function scheduleSystemLivePin(reason='deferred',delay=0){
    setTimeout(()=>{pinSystemLive(reason);requestAnimationFrame(()=>pinSystemLive(`${reason}-frame`))},Math.max(0,delay));
  }
  function openDirect(){
    const p=ensurePanel();
    if(window.AuraConversationDrawer?.isOpen?.())window.AuraConversationDrawer.close();
    p.hidden=false;void p.offsetWidth;p.classList.add('open');syncDockContext();markVisibleSeenLater();
    q('[data-p081-action="close"]',p)?.focus({preventScroll:true});updateEntry();
    emit('aura:activity-center-opened',{unread:unread(),mode:'workspace-dock',context:currentWorkspace()});return true;
  }
  function closeDirect(){
    if(!STATE.panel)return false;STATE.panel.classList.remove('open');syncDockContext();
    setTimeout(()=>{if(STATE.panel&&!STATE.panel.classList.contains('open'))STATE.panel.hidden=true},150);
    STATE.entry?.focus?.({preventScroll:true});emit('aura:activity-center-closed',{mode:'workspace-dock'});return true;
  }
  function registerOverlay(){
    const ov=overlayApi();if(!ov?.register)return false;
    if(ov.list?.().some(x=>x.id==='activity-center')){STATE.overlayRegistered=true;return true}
    STATE.overlayRegistered=!!ov.register({id:'activity-center',label:'Activity Center',preserveOnWorkspaceChange:true,available:()=>true,isOpen:panelIsOpen,open:openDirect,close:closeDirect});
    return STATE.overlayRegistered;
  }
  function openPanel(){const ov=overlayApi();if(registerOverlay()&&ov?.open)return ov.open('activity-center',{source:'event-watchers'});return openDirect()}
  function closePanel(){const ov=overlayApi();if(STATE.overlayRegistered&&ov?.close)return ov.close('activity-center');return closeDirect()}
  function togglePanel(){return panelIsOpen()?closePanel():openPanel()}
  function markVisibleSeenLater(){setTimeout(()=>{let changed=false;STATE.events.forEach(e=>{if(e.status==='new'){e.status='seen';changed=true}});if(changed){persist();render();updateEntry()}},1200)}
  function setFamily(id,on){if(!FAMILIES.includes(id))return false;STATE.settings.families[id]=!!on;persist();if(id==='system'){clearTimeout(STATE.timer);STATE.timer=0;if(on&&!STATE.settings.paused)scheduleSystem(50)}render();updateEntry();emit('aura:watcher-permission-changed',{family:id,enabled:!!on});return true}
  function setPaused(on){STATE.settings.paused=!!on;persist();clearTimeout(STATE.timer);STATE.timer=0;if(!on&&STATE.settings.families.system)scheduleSystem(50);render();updateEntry();emit('aura:watchers-paused',{paused:STATE.settings.paused});return STATE.settings.paused}

  function fillConversation(text){
    const v=safe(text,420);if(!v)return false;
    if(window.AuraConversationDrawer?.open)window.AuraConversationDrawer.open();
    setTimeout(()=>{const input=q('.aura-p0712-conversation-drawer [data-input]')||q('#messageInput');if(!input)return;input.value=v;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus()},80);return true;
  }
  function onPanelClick(ev){
    const family=ev.target.closest?.('[data-p081-family]');if(family){setFamily(family.dataset.p081Family,!STATE.settings.families[family.dataset.p081Family]);return}
    const a=ev.target.closest?.('[data-p081-action]');if(a){const id=a.dataset.p081Action;if(id==='close')closePanel();else if(id==='pause')setPaused(!STATE.settings.paused);else if(id==='clear')clearEvents();else if(id==='mark-seen'){STATE.events.forEach(e=>{if(e.status==='new')e.status='seen'});persist();render();updateEntry()}return}
    const ea=ev.target.closest?.('[data-p081-event-action]');if(!ea)return;const card=ea.closest('[data-event-id]'),e=STATE.events.find(x=>x.id===card?.dataset.eventId);if(!e)return;
    if(ea.dataset.p081EventAction==='dismiss')setEventStatus(e.id,'dismissed');
    else if(ea.dataset.p081EventAction==='suggest'){setEventStatus(e.id,'seen');fillConversation(e.suggestion);closePanel()}
  }

  function percentFrom(obj,paths){for(const path of paths){let cur=obj;for(const part of path.split('.'))cur=cur&&typeof cur==='object'?cur[part]:undefined;if(finite(cur))return Number(cur)}return null}
  function systemMetrics(data){
    const cpu=percentFrom(data,['cpu_percent','cpu.percent','system.cpu_percent','system.cpu.percent','desktop.cpu_percent']);
    const ram=percentFrom(data,['ram_percent','memory_percent','ram.percent','memory.percent','system.ram_percent','system.memory_percent']);
    const vram=percentFrom(data,['vram_percent','gpu.vram_percent','system.vram_percent','gpu.memory_percent']);
    return {cpu,ram,vram};
  }
  function checkSustained(key,value,threshold){
    const h=STATE.system.high,now=Date.now();if(!finite(value)||Number(value)<threshold){delete h[key];return}
    if(!h[key])h[key]={since:now,lastNotify:0};
    const elapsed=(now-h[key].since)/1000;if(elapsed<STATE.settings.system.sustainSeconds)return;
    if(now-h[key].lastNotify<10*60*1000)return;h[key].lastNotify=now;
    const names={ram:'Mémoire vive élevée',cpu:'Charge processeur élevée',vram:'Mémoire GPU élevée'};
    addEvent({family:'system',severity:Number(value)>=98?'critical':'important',title:names[key],message:`${key.toUpperCase()} à ${Math.round(Number(value))} % depuis environ ${Math.max(1,Math.round(elapsed/60))} min.`,source:'local-runtime',fingerprint:`system-${key}-high`,suggestion:`Analyse l’état système actuel : ${key.toUpperCase()} reste autour de ${Math.round(Number(value))} %. Explique les causes probables et propose uniquement des vérifications sûres avant toute action.`});
  }
  async function pollSystem(){
    if(!enabled('system')||!token)return false;
    try{const r=await fetch(`/api/system?token=${encodeURIComponent(token)}`,{cache:'no-store'});const d=await r.json();if(!r.ok)return false;const runtimeMetadata=d&&typeof d.runtime_metadata==='object'?{...d.runtime_metadata,ui:{release:'0.7.2.2-rc4.2'}}:null;if(runtimeMetadata){window.__AURA_RUNTIME_METADATA__=runtimeMetadata;emit('aura:runtime-metadata',runtimeMetadata);}const m=systemMetrics(d);checkSustained('ram',m.ram,STATE.settings.system.ram);checkSustained('cpu',m.cpu,STATE.settings.system.cpu);checkSustained('vram',m.vram,STATE.settings.system.vram);emit('aura:watcher-system-sampled',{metrics:m});return true}catch(_e){return false}
  }
  function scheduleSystem(delay=POLL_MS){clearTimeout(STATE.timer);STATE.timer=setTimeout(async()=>{await pollSystem();scheduleSystem(POLL_MS)},Math.max(50,delay))}

  function parseDate(v){const d=new Date(v);return Number.isNaN(d.getTime())?null:d}
  function processAgenda(snapshot){
    if(!enabled('agenda'))return false;const items=Array.isArray(snapshot?.events)?snapshot.events:Array.isArray(snapshot)?snapshot:[];const now=Date.now();
    items.slice(0,100).forEach(item=>{const start=parseDate(item?.start||item?.date||item?.at);if(!start)return;const mins=(start.getTime()-now)/60000;if(mins<0||mins>30)return;const title=safe(item?.title||item?.label||'Rendez-vous',100);addEvent({family:'agenda',severity:mins<=10?'important':'info',title:'Rendez-vous prochain',message:`${title} commence dans environ ${Math.max(1,Math.round(mins))} min.`,source:safe(snapshot?.source,60)||'agenda-published',fingerprint:`agenda-${safe(item?.id||title,80)}-${start.toISOString()}`,suggestion:`Prépare-moi pour « ${title} » qui commence dans environ ${Math.max(1,Math.round(mins))} minutes. Utilise uniquement le contexte déjà autorisé et propose les actions utiles sans les exécuter.`})});STATE.lastSnapshots.agenda=clone(snapshot);return true;
  }
  function processTasks(snapshot){
    if(!enabled('tasks'))return false;const items=Array.isArray(snapshot?.tasks)?snapshot.tasks:Array.isArray(snapshot)?snapshot:[];const now=Date.now();
    items.slice(0,150).forEach(item=>{if(item?.done||item?.completed||String(item?.status).toLowerCase()==='done')return;const due=parseDate(item?.due||item?.deadline||item?.at);if(!due)return;const hours=(due.getTime()-now)/3600000;if(hours<0||hours>24)return;const title=safe(item?.title||item?.label||'Tâche',100);addEvent({family:'tasks',severity:hours<=3?'important':'info',title:'Échéance proche',message:`${title} arrive à échéance ${hours<1?'dans moins d’une heure':`dans environ ${Math.max(1,Math.round(hours))} h`}.`,source:safe(snapshot?.source,60)||'tasks-published',fingerprint:`task-${safe(item?.id||title,80)}-${due.toISOString()}`,suggestion:`La tâche « ${title} » arrive bientôt à échéance. Aide-moi à décider de la priorité et des prochaines étapes, sans modifier la tâche tant que je n’ai pas confirmé.`})});STATE.lastSnapshots.tasks=clone(snapshot);return true;
  }
  function processFile(detail){
    if(!enabled('files'))return false;const name=safe(detail?.name||detail?.file_name||detail?.label||'Fichier autorisé',120);const kind=safe(detail?.kind||detail?.change||'modifié',40);return addEvent({family:'files',severity:'info',title:'Fichier surveillé modifié',message:`${name} · ${kind}.`,source:safe(detail?.source,60)||'authorized-file-intelligence',fingerprint:`file-${safe(detail?.file_id||detail?.id||name,100)}-${safe(detail?.version||detail?.mtime||detail?.updated_at||kind,80)}`,suggestion:`Le fichier autorisé « ${name} » a changé. Propose-moi une comparaison ou une nouvelle analyse, sans écrire ni supprimer de fichier.`})
  }
  function processResearch(detail){
    if(!enabled('research'))return false;const topic=safe(detail?.topic||detail?.query||detail?.label||'Recherche surveillée',120);const summary=safe(detail?.summary||detail?.message||'Un nouveau résultat a été publié.',260);return addEvent({family:'research',severity:detail?.important?'important':'info',title:`Nouveau résultat · ${topic}`,message:summary,source:safe(detail?.source,60)||'research-published',fingerprint:`research-${safe(detail?.id||topic,100)}-${safe(detail?.version||detail?.published_at||summary,80)}`,suggestion:`Un nouveau résultat est disponible pour « ${topic} ». Résume ce qui a réellement changé avec les sources disponibles et dis-moi si cela mérite une action.`})
  }
  function publish(raw){const family=safe(raw?.family||raw?.type,24).toLowerCase();if(!FAMILIES.includes(family))return false;if(family==='agenda')return processAgenda(raw);if(family==='tasks')return processTasks(raw);if(family==='files')return processFile(raw);if(family==='research')return processResearch(raw);if(family==='system')return addEvent({...raw,family:'system'});return false}

  function registerSource(id,adapter){id=safe(id,48);if(!id||typeof adapter!=='function')return false;STATE.sources.set(id,adapter);return true}
  async function pollSources(){for(const [id,fn] of STATE.sources){try{const out=await fn({enabled,settings:clone(STATE.settings)});if(Array.isArray(out))out.forEach(publish);else if(out)publish(out)}catch(_e){emit('aura:watcher-source-error',{source:id})}}}

  function onKey(e){
    if(e.ctrlKey&&e.altKey&&!e.shiftKey&&e.key.toLowerCase()==='w'){
      e.preventDefault();activateUi('keyboard');togglePanel();return;
    }
    if(e.key==='Escape'&&STATE.panel&&!STATE.panel.hidden){e.preventDefault();closePanel()}
  }
  function registerFeeds(){
    window.addEventListener('aura:agenda-snapshot',e=>processAgenda(e.detail||{}));
    window.addEventListener('aura:tasks-snapshot',e=>processTasks(e.detail||{}));
    window.addEventListener('aura:authorized-file-changed',e=>processFile(e.detail||{}));
    window.addEventListener('aura:file-watch-event',e=>processFile(e.detail||{}));
    window.addEventListener('aura:research-watch-event',e=>processResearch(e.detail||{}));
    window.addEventListener('aura:watcher-feed',e=>publish(e.detail||{}));
  }
  function activateUi(reason='manual'){
    if(STATE.registered){ensureEntry();registerOverlay();syncDockContext();return true}
    STATE.registered=true;
    ensureEntry();
    registerOverlay();
    registerFeeds();
    if(!STATE.sourceTimer)STATE.sourceTimer=setInterval(()=>pollSources(),30000);
    if(STATE.settings.families.system&&!STATE.settings.paused)scheduleSystem(1200);
    emit('aura:event-watchers-ui-activated',{reason,bootIsolation:true});
    return true;
  }
  function requestActivation(reason='deferred',delay=0){
    if(STATE.registered)return;
    clearTimeout(STATE.activationTimer);
    STATE.activationTimer=setTimeout(()=>{
      const run=()=>activateUi(reason);
      if('requestIdleCallback' in window)requestIdleCallback(run,{timeout:1800});else setTimeout(run,0);
    },Math.max(0,delay));
  }
  function registerPassive(){
    if(STATE.passiveRegistered)return;STATE.passiveRegistered=true;
    document.addEventListener('keydown',onKey,true);
    document.addEventListener('click',e=>{
      const activity=e.target.closest?.('[data-module="activity-center"]');
      if(activity){e.preventDefault();e.stopImmediatePropagation();activateUi('activity-click');const pop=q('.aura-p0702-modules-popover');if(pop){pop.classList.remove('open');pop.hidden=true}openPanel();return}
      const modules=e.target.closest?.('[data-module="modules"],[data-rail-target="modules"],.aura-p0702-modules-trigger');
      if(modules)requestActivation('modules-open',120);
    },true);
    window.addEventListener('aura:workspace-manager-ready',()=>{registerOverlay();scheduleSystemLivePin('workspace-manager-ready',60);requestActivation('workspace-manager-ready',1800)},{once:true});
    window.addEventListener('aura:workspace-changed',()=>{scheduleSystemLivePin('workspace-changed',0);syncDockContext()});
    window.addEventListener('aura:workspace-overlay-changed',e=>{
      const current=safe(e.detail?.current,40).toLowerCase();
      if(current==='conversation-drawer'&&panelIsOpen())queueMicrotask(()=>closePanel());
      else syncDockContext();
    });
    window.addEventListener('aura:startup-ready',()=>{scheduleSystemLivePin('startup-ready',20);requestActivation('startup-ready',800)},{once:true});
    window.addEventListener('aura:ui-ready',()=>{scheduleSystemLivePin('ui-ready',20);requestActivation('ui-ready',800)},{once:true});
    window.addEventListener('load',()=>{scheduleSystemLivePin('window-load',120);setTimeout(()=>pinSystemLive('window-load-safety'),6000);requestActivation('window-load-safety',45000)},{once:true});
  }

  /* P0.8.1.4 — GLOBAL LAYOUT AUDIT
     Measures only geometry of known AURA surfaces. It never reads module content. */
  const LAYOUT_SURFACES=Object.freeze([
    {id:'memory',selector:'.aura-p0626-memory',role:'workspace'},
    {id:'tasks-agenda',selector:'.aura-p0623-drawer',role:'workspace'},
    {id:'diagnostics',selector:'.aura-p0627-system:not(.aura-p0813-system-hud-persistent)',role:'workspace'},
    {id:'weather',selector:'.aura-weather-workspace',role:'workspace'},
    {id:'vitals',selector:'.aura-p074-vitals-workspace',role:'workspace'},
    {id:'maps',selector:'#auraNavigationWorkspace,.aura-p066-maps-workspace,.aura-maps-workspace',role:'workspace'},
    {id:'conversation',selector:'.aura-p0712-conversation-drawer,.aura-p071-conversation-drawer',role:'dock'},
    {id:'activity-center',selector:'.aura-p081-panel',role:'dock'},
    {id:'system-live',selector:'.aura-p0813-system-hud-persistent',role:'hud'},
    {id:'accessibility',selector:'.aura-p075-panel',role:'utility'},
    {id:'modules',selector:'.aura-p0702-modules-popover',role:'utility'},
    {id:'full-conversation',selector:'body[data-aura-workspace="talk"] #conversation',role:'workspace'}
  ]);
  function layoutVisible(el){if(!el||!el.isConnected||el.hidden)return false;const s=getComputedStyle(el),r=el.getBoundingClientRect();return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>4&&r.height>4}
  function layoutAudit(){
    const rows=[];
    LAYOUT_SURFACES.forEach(spec=>{qa(spec.selector).forEach((el,index)=>{if(!layoutVisible(el))return;const r=el.getBoundingClientRect();rows.push({id:spec.id+(index?`-${index+1}`:''),role:spec.role,left:+r.left.toFixed(1),right:+r.right.toFixed(1),top:+r.top.toFixed(1),bottom:+r.bottom.toFixed(1),width:+r.width.toFixed(1),height:+r.height.toFixed(1),topDelta:+(r.top-topTarget).toFixed(1),bottomDelta:+(r.bottom-bottomTarget).toFixed(1)})})});
    const aligned=rows.filter(x=>x.role!=='utility').every(x=>Math.abs(x.topDelta)<=3&&Math.abs(x.bottomDelta)<=3);
    const lanes=rows.filter(x=>['workspace','dock','hud'].includes(x.role)).sort((a,b)=>a.left-b.left);const gaps=[];
    for(let i=1;i<lanes.length;i++){const prev=lanes[i-1],cur=lanes[i],gap=cur.left-prev.right;if(gap>=-2)gaps.push({between:`${prev.id} → ${cur.id}`,gap:+gap.toFixed(1),delta:+(gap-gapTarget).toFixed(1)})}
    const spacing=gaps.every(x=>Math.abs(x.delta)<=3);
    const target=baselineTargetGeometry();
    const topTarget=target.top,bottomTarget=target.bottom,gapTarget=target.gap;
    const report={version:'P0.8.1.5',topTarget,bottomTarget,gapTarget,aligned,spacing,ok:aligned&&spacing,surfaces:rows,gaps};
    emit('aura:layout-audit',report);return report;
  }

  /* P0.8.1.5 — GLOBAL TOP BASELINE NORMALIZATION
     CSS top values are not enough for legacy surfaces because some of them live inside
     transformed containers. This layer measures final viewport geometry and applies a
     Y-only individual translate, preserving every module's horizontal transform/animation.
     SYSTEM LIVE is the canonical top reference. The composer is the canonical lower rail. */
  const BASELINE_SURFACES=Object.freeze([
    {id:'memory',selector:'.aura-p0626-memory',mode:'main'},
    {id:'tasks-agenda',selector:'.aura-p0623-drawer',mode:'main'},
    {id:'diagnostics',selector:'.aura-p0627-system:not(.aura-p0813-system-hud-persistent)',mode:'main'},
    {id:'weather',selector:'.aura-weather-workspace',mode:'main'},
    {id:'vitals',selector:'.aura-p074-vitals-workspace',mode:'main'},
    {id:'maps',selector:'#auraNavigationWorkspace,.aura-p066-maps-workspace,.aura-maps-workspace',mode:'main'},
    {id:'conversation-drawer',selector:'.aura-p0712-conversation-drawer,.aura-p071-conversation-drawer',mode:'main'},
    {id:'activity-center',selector:'.aura-p081-panel',mode:'main'},
    {id:'full-conversation',selector:'body[data-aura-workspace="talk"] #conversation',mode:'main'},
    {id:'accessibility',selector:'.aura-p075-panel',mode:'utility'},
    {id:'modules',selector:'.aura-p0702-modules-popover',mode:'utility'},
    {id:'system-live',selector:'.aura-p0813-system-hud-persistent',mode:'main',reference:true}
  ]);
  let baselineTimer=0,baselineGeneration=0;
  function visibleGeometry(el){
    if(!el||!el.isConnected||el.hidden)return false;
    const s=getComputedStyle(el),r=el.getBoundingClientRect();
    return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>8&&r.height>8;
  }
  function composerRect(){
    const candidates=['.workspace>.composer','.workspace .composer','#composer','.composer'];
    for(const sel of candidates){const el=q(sel);if(visibleGeometry(el))return el.getBoundingClientRect()}
    return null;
  }
  function baselineTargetGeometry(){
    pinSystemLive('p0815-baseline-target');
    const hud=(STATE.systemHud&&visibleGeometry(STATE.systemHud))?STATE.systemHud:q('.aura-p0813-system-hud-persistent');
    const hr=visibleGeometry(hud)?hud.getBoundingClientRect():null;
    const root=getComputedStyle(document.documentElement);
    const cssTop=parseFloat(root.getPropertyValue('--aura-p0814-surface-top'))||102;
    const cssBottom=parseFloat(root.getPropertyValue('--aura-p0814-surface-bottom'))||84;
    const gap=parseFloat(root.getPropertyValue('--aura-p0814-surface-gap'))||14;
    const cr=composerRect();
    const top=hr?hr.top:cssTop;
    let bottom=cr?cr.top-gap:(window.innerHeight-cssBottom);
    if(bottom<=top+180)bottom=hr?hr.bottom:(window.innerHeight-cssBottom);
    return {top:+top.toFixed(2),bottom:+bottom.toFixed(2),height:+Math.max(180,bottom-top).toFixed(2),gap:+gap.toFixed(2),reference:hr?'system-live':'css-fallback',composer:!!cr};
  }
  function clearBaseline(el){
    if(!el)return;el.classList.remove('aura-p0815-baseline-main','aura-p0815-baseline-utility');
    el.style.removeProperty('--aura-p0815-shift-y');el.style.removeProperty('--aura-p0815-target-height');
    delete el.dataset.auraBaselineShift;delete el.dataset.auraBaselineTarget;
  }
  function normalizeElementBaseline(el,spec,target){
    if(!visibleGeometry(el)){clearBaseline(el);return null}
    const r=el.getBoundingClientRect();
    const prev=Number(el.dataset.auraBaselineShift||0)||0;
    const baseTop=r.top-prev;
    const shift=target.top-baseTop;
    el.style.setProperty('--aura-p0815-shift-y',`${shift.toFixed(2)}px`);
    el.dataset.auraBaselineShift=String(shift);
    el.dataset.auraBaselineTarget=String(target.top);
    if(spec.mode==='main'){
      el.classList.add('aura-p0815-baseline-main');el.classList.remove('aura-p0815-baseline-utility');
      el.style.setProperty('--aura-p0815-target-height',`${target.height.toFixed(2)}px`);
    }else{
      el.classList.add('aura-p0815-baseline-utility');el.classList.remove('aura-p0815-baseline-main');
      el.style.removeProperty('--aura-p0815-target-height');
    }
    const afterTop=baseTop+shift;
    return {id:spec.id,mode:spec.mode,beforeTop:+r.top.toFixed(2),baseTop:+baseTop.toFixed(2),shift:+shift.toFixed(2),targetTop:target.top,projectedTop:+afterTop.toFixed(2)};
  }
  function normalizePanelBaseline(reason='runtime'){
    const target=baselineTargetGeometry(),rows=[];
    BASELINE_SURFACES.forEach(spec=>qa(spec.selector).forEach(el=>{const row=normalizeElementBaseline(el,spec,target);if(row)rows.push(row)}));
    baselineGeneration++;
    const report={version:'P0.8.1.5',reason,generation:baselineGeneration,target,surfaces:rows};
    document.documentElement.dataset.auraPanelBaseline='normalized';
    emit('aura:panel-baseline-normalized',report);
    return report;
  }
  function schedulePanelBaseline(reason='deferred',delay=0){
    clearTimeout(baselineTimer);
    baselineTimer=setTimeout(()=>{
      requestAnimationFrame(()=>{
        normalizePanelBaseline(reason);
        setTimeout(()=>normalizePanelBaseline(`${reason}-settled`),180);
      });
    },Math.max(0,delay));
  }
  function installBaselineHooks(){
    window.addEventListener('resize',()=>schedulePanelBaseline('resize',80),{passive:true});
    ['aura:workspace-changed','aura:workspace-restored','aura:workspace-overlay-changed','aura:activity-center-opened','aura:activity-center-closed','aura:system-live-persistent'].forEach(name=>window.addEventListener(name,()=>schedulePanelBaseline(name,30)));
    window.addEventListener('aura:startup-ready',()=>schedulePanelBaseline('startup-ready',120),{once:true});
    window.addEventListener('aura:ui-ready',()=>schedulePanelBaseline('ui-ready',120),{once:true});
    window.addEventListener('load',()=>schedulePanelBaseline('load',240),{once:true});
    document.addEventListener('click',event=>{
      if(event.target.closest?.('.aura-p0702-nav-btn,[data-rail-target],[data-module],#closeTalk,[data-close],[data-p081-action]'))schedulePanelBaseline('ui-click',60);
    },true);
  }
  installBaselineHooks();
  schedulePanelBaseline('script-ready',180);
  window.AuraPanelBaseline=Object.freeze({version:'P0.8.1.5',run:()=>normalizePanelBaseline('api'),target:()=>baselineTargetGeometry(),surfaces:()=>BASELINE_SURFACES.map(x=>({...x}))});
  STATE.settings=load();
  persist(); // P0.8.3.2 persists collapsed history immediately.
  registerPassive();
  scheduleSystemLivePin('script-ready',80);
  window.AuraEventWatchers=Object.freeze({
    version:VERSION,open:()=>{activateUi('api-open');return openPanel()},close:closePanel,toggle:()=>{activateUi('api-toggle');return togglePanel()},publish,registerSource,
    enable:(family,on=true)=>{activateUi('api-enable');return setFamily(safe(family,24).toLowerCase(),!!on)},pause:(on=true)=>setPaused(!!on),
    settings:()=>clone(STATE.settings),events:()=>clone(STATE.events),unread,clear:clearEvents,
    ingestAgenda:processAgenda,ingestTasks:processTasks,ingestFile:processFile,ingestResearch:processResearch,
    systemSample:pollSystem,activate:activateUi,isOpen:panelIsOpen,dockContext:currentWorkspace,pinSystemLive:()=>pinSystemLive('api'),systemHud:()=>STATE.systemHud,layoutAudit
  });
  window.AuraLayoutAudit=Object.freeze({version:'P0.8.1.5',run:layoutAudit,surfaces:()=>LAYOUT_SURFACES.map(x=>({...x}))});
  emit('aura:event-watchers-ready',{privacy:'opt-in-local',authority:'detect-and-propose-only',bootIsolation:true,activation:'post-startup-lazy',families:FAMILIES,features:['activity-center','opt-in-watchers','local-system-watch','published-agenda-events','published-task-events','authorized-file-events','research-events','suggestion-handoff','local-history','boot-isolation','workspace-docking','overlay-contract','drawer-mutual-exclusion','persistent-system-live','system-hud-reservation','combined-right-docks','global-layout-rhythm','canonical-gutters','panel-height-alignment','layout-audit','viewport-baseline-normalization','system-live-top-reference','composer-bottom-reference']});
})();
