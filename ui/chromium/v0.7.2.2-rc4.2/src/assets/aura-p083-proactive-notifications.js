/* AURA P0.8.3.2 — NOTIFICATION DEDUP + COOLDOWN HOTFIX
   Baseline: AURA P0.8.3 — PROACTIVE NOTIFICATION LAYER
   In-app notification surface above Suggestion Engine P0.8.2.
   Authority / privacy contract:
   - Consumes only explicit aura:suggestion-created events.
   - NORMAL => discrete shell indicator; HIGH/URGENT => compact in-app notification.
   - No Windows notification, no sound, no network, no background LLM, no automatic action.
   - VIEW opens Activity Center. IGNORE hides only the notification; the detection remains in Activity Center.
*/
(()=>{
  'use strict';
  if(window.__AURA_P083_PROACTIVE_NOTIFICATIONS__)return;
  window.__AURA_P083_PROACTIVE_NOTIFICATIONS__=true;

  const VERSION='P0.8.3.2';
  const STORAGE='aura.proactive-notifications.p083';
  const COOLDOWN={normal:20*60*1000,high:10*60*1000,urgent:5*60*1000};
  const GLOBAL_POPUP_COOLDOWN=45*1000;
  const PRIORITY_ORDER={low:0,normal:1,high:2,urgent:3};
  const LABELS={low:'FAIBLE',normal:'NORMALE',high:'HAUTE',urgent:'URGENTE'};
  const STATE={settings:{mode:'standard'},shown:new Map(),pending:new Map(),host:null,card:null,rail:null,timer:0,lastPopupAt:0,current:null,decorTimer:0,focusEventId:'',focusTimer:0};
  const q=(s,r=document)=>r.querySelector(s);
  const safe=(v,n=360)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const clone=v=>{try{return JSON.parse(JSON.stringify(v))}catch(_e){return null}};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));

  function normalizeSettings(raw){return {mode:raw?.mode==='silent'?'silent':'standard'}}
  function load(){
    try{const raw=JSON.parse(localStorage.getItem(STORAGE)||'{}');STATE.settings=normalizeSettings(raw.settings||raw);const h=raw.shown&&typeof raw.shown==='object'?raw.shown:{};Object.entries(h).forEach(([k,v])=>{const n=Number(v);if(Number.isFinite(n)&&Date.now()-n<24*60*60*1000)STATE.shown.set(k,n)})}catch(_e){STATE.settings={mode:'standard'}}
  }
  function persist(){try{localStorage.setItem(STORAGE,JSON.stringify({settings:STATE.settings,shown:Object.fromEntries([...STATE.shown.entries()].slice(-80))}))}catch(_e){}}
  function activityOpen(){const p=q('.aura-p081-panel');return !!(p&&!p.hidden&&p.classList.contains('open'))}
  function normalizeSuggestion(raw){
    if(!raw||typeof raw!=='object')return null;const eventId=safe(raw.eventId||raw.id,100);if(!eventId)return null;
    const priority=['low','normal','high','urgent'].includes(raw.priority)?raw.priority:'normal';
    return {id:safe(raw.id||eventId,100),eventId,priority,score:Math.max(0,Math.min(100,Number(raw.score)||0)),title:safe(raw.title,150)||'Suggestion AURA',whyNow:safe(raw.whyNow,420),recommendedAction:safe(raw.recommendedAction,520),source:safe(raw.source,90),test:!!raw.test||/^p083-local-test/i.test(safe(raw.source,90))};
  }
  function priorityOfPending(){let best='low';for(const s of STATE.pending.values())if(PRIORITY_ORDER[s.priority]>PRIORITY_ORDER[best])best=s.priority;return best}

  function ensureRail(){
    let b=q('.aura-p0702-nav-btn[data-rail-target="modules"]');if(!b)return null;
    let dot=q('.aura-p083-rail-indicator',b);if(!dot){dot=document.createElement('span');dot.className='aura-p083-rail-indicator';dot.hidden=true;dot.setAttribute('aria-hidden','true');b.appendChild(dot)}
    STATE.rail=dot;return dot;
  }
  function updateRail(){
    const dot=ensureRail();if(!dot)return;const p=priorityOfPending();dot.hidden=STATE.pending.size===0;dot.dataset.priority=p;const btn=dot.closest('button');if(btn)btn.dataset.p083Pending=STATE.pending.size?String(STATE.pending.size):'';
  }
  function clearPending(){STATE.pending.clear();updateRail()}

  function ensureHost(){
    if(STATE.host?.isConnected)return STATE.host;
    const host=document.createElement('div');host.className='aura-p083-notification-host';host.hidden=true;host.setAttribute('aria-live','polite');host.setAttribute('aria-atomic','true');document.body.appendChild(host);STATE.host=host;return host;
  }
  function rightAnchorPx(){
    const candidates=[q('.aura-p0813-system-hud-persistent'),q('.aura-p0712-conversation-drawer.open'),q('.aura-p071-conversation-drawer.open')].filter(Boolean).filter(el=>{const r=el.getBoundingClientRect();return r.width>80&&r.height>80});
    if(!candidates.length)return 18;const left=Math.min(...candidates.map(el=>el.getBoundingClientRect().left));return Math.max(18,Math.round(innerWidth-left+14));
  }
  function hideNotification(reason='dismiss'){
    clearTimeout(STATE.timer);STATE.timer=0;if(!STATE.host)return false;const cur=STATE.current;STATE.host.classList.remove('open');STATE.host.hidden=true;STATE.host.innerHTML='';STATE.current=null;emit('aura:proactive-notification-hidden',{reason,eventId:cur?.eventId||'',priority:cur?.priority||''});return true
  }
  function showNotification(raw,{force=false,test=false}={}){
    const s=normalizeSuggestion(Object.assign({},raw,{test:test||raw?.test}));if(!s)return false;
    if(activityOpen()&&!force)return false;
    if(STATE.settings.mode==='silent'&&!force){emit('aura:proactive-notification-suppressed',{reason:'silent-mode',eventId:s.eventId,priority:s.priority});return false}
    if(!force&&PRIORITY_ORDER[s.priority]<PRIORITY_ORDER.high)return false;
    const key=`${s.eventId}|${s.priority}`,last=STATE.shown.get(key)||0,wait=COOLDOWN[s.priority]||COOLDOWN.normal;
    if(!force&&Date.now()-last<wait){emit('aura:proactive-notification-suppressed',{reason:'deduplicated',eventId:s.eventId,priority:s.priority});return false}
    if(!force&&Date.now()-STATE.lastPopupAt<GLOBAL_POPUP_COOLDOWN&&s.priority!=='urgent'){emit('aura:proactive-notification-suppressed',{reason:'global-cooldown',eventId:s.eventId,priority:s.priority});return false}
    const host=ensureHost();clearTimeout(STATE.timer);host.hidden=false;host.style.right=`${rightAnchorPx()}px`;host.dataset.priority=s.priority;host.setAttribute('role',s.priority==='urgent'?'alert':'status');
    host.innerHTML=`<article class="aura-p083-card" data-p083-event="${esc(s.eventId)}"><header><span class="aura-p083-level" data-priority="${s.priority}">${LABELS[s.priority]} · ${Math.round(s.score)}/100</span><i>${s.test?'SIMULATION LOCALE':'AURA · PROACTIVE'}</i></header><strong>${esc(s.title)}</strong><p>${esc(s.recommendedAction||s.whyNow||'Une suggestion mérite ton attention.')}</p><footer><button type="button" data-p083-action="view">VOIR</button><button type="button" data-p083-action="ignore">IGNORER</button></footer><small>0 ACTION AUTO · Activity Center conserve la détection</small></article>`;
    STATE.current=s;STATE.lastPopupAt=Date.now();STATE.shown.set(key,STATE.lastPopupAt);persist();requestAnimationFrame(()=>host.classList.add('open'));
    const delay=s.priority==='urgent'?15000:9000;STATE.timer=setTimeout(()=>hideNotification('timeout'),delay);
    emit('aura:proactive-notification-shown',{eventId:s.eventId,priority:s.priority,score:s.score,test:s.test,mode:STATE.settings.mode,autoAction:false});return true
  }

  function processSuggestion(raw,{force=false,test=false}={}){
    const s=normalizeSuggestion(raw);if(!s)return false;
    if(!activityOpen()&&PRIORITY_ORDER[s.priority]>=PRIORITY_ORDER.normal){STATE.pending.set(s.eventId,s);updateRail()}
    if(s.priority==='high'||s.priority==='urgent')showNotification(s,{force,test});
    emit('aura:proactive-suggestion-observed',{eventId:s.eventId,priority:s.priority,popup:s.priority==='high'||s.priority==='urgent',mode:STATE.settings.mode});return true
  }
  function focusActivityEvent(eventId,{attempt=0}={}){
    const id=safe(eventId,100);if(!id)return false;
    const root=q('.aura-p081-panel');
    if(!root||root.hidden||!root.classList.contains('open')){if(attempt<10)setTimeout(()=>focusActivityEvent(id,{attempt:attempt+1}),80+attempt*35);return false}
    try{window.AuraSuggestionEngine?.refresh?.()}catch(_e){}
    const card=[...root.querySelectorAll('.aura-p081-event[data-event-id]')].find(el=>safe(el.dataset.eventId,100)===id);
    if(!card){if(attempt<10)setTimeout(()=>focusActivityEvent(id,{attempt:attempt+1}),90+attempt*40);return false}
    root.querySelectorAll('.aura-p083-focus-target').forEach(el=>el.classList.remove('aura-p083-focus-target'));
    card.classList.add('aura-p083-focus-target');card.scrollIntoView?.({block:'center',behavior:'smooth'});
    clearTimeout(STATE.focusTimer);STATE.focusTimer=setTimeout(()=>card.classList.remove('aura-p083-focus-target'),3600);
    const explain=q('[data-p082-explain]',card);if(explain)explain.focus?.({preventScroll:true});else card.setAttribute('tabindex','-1'),card.focus?.({preventScroll:true});
    STATE.focusEventId='';emit('aura:proactive-notification-focused',{eventId:id,found:true});return true
  }
  function openActivityCenter(){
    const target=STATE.current?clone(STATE.current):null;const eventId=safe(target?.eventId,100);if(eventId)STATE.focusEventId=eventId;
    hideNotification('view');if(eventId)STATE.pending.delete(eventId);updateRail();try{window.AuraEventWatchers?.open?.()}catch(_e){}
    setTimeout(()=>{if(eventId)focusActivityEvent(eventId);else{const strip=q('.aura-p082-engine-strip,.aura-p0822-top-explain');strip?.scrollIntoView?.({block:'nearest'})}q('.aura-p081-panel [data-p081-action="close"]')?.focus?.({preventScroll:true})},120);
    emit('aura:proactive-notification-view',{eventId,priority:target?.priority||'',targeted:!!eventId});return true
  }

  function ensureSettings(){
    const root=q('.aura-p081-panel');if(!root||root.hidden)return null;let box=q('.aura-p083-settings',root);if(!box){
      box=document.createElement('section');box.className='aura-p083-settings aura-p081-section';box.innerHTML=`<div class="aura-p083-settings-head"><span><small>NOTIFICATIONS PROACTIVES · v1.0.0</small><b>ATTENTION SANS INTERRUPTION</b></span><i data-p083-mode-label>STANDARD</i></div><div class="aura-p083-settings-actions"><button type="button" data-p083-mode="standard">STANDARD</button><button type="button" data-p083-mode="silent">SILENCIEUX</button><button type="button" data-p083-test>TEST NOTIFICATION</button></div><p>Normal : indicateur discret sur MODULES · Haute/Urgente : carte in-app · aucun son ni action automatique.</p>`;
      const engine=q('.aura-p082-engine-strip',root);if(engine)engine.insertAdjacentElement('afterend',box);else q('.aura-p081-overview',root)?.insertAdjacentElement('afterend',box)
    }
    renderSettings(box);return box
  }
  function renderSettings(box=ensureSettings()){
    if(!box)return;box.dataset.mode=STATE.settings.mode;const lab=q('[data-p083-mode-label]',box);if(lab)lab.textContent=STATE.settings.mode==='silent'?'SILENCIEUX':'STANDARD';box.querySelectorAll('[data-p083-mode]').forEach(b=>{const on=b.dataset.p083Mode===STATE.settings.mode;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on))});
    const test=q('[data-p083-test]',box),sys=!!window.AuraEventWatchers?.settings?.()?.families?.system;if(test){test.disabled=!sys;test.setAttribute('aria-disabled',String(!sys));test.title=sys?'Créer une détection système simulée persistante puis tester la notification':'Activez d’abord la surveillance SYSTÈME'}
  }
  function setMode(mode){STATE.settings.mode=mode==='silent'?'silent':'standard';persist();if(STATE.settings.mode==='silent')hideNotification('silent-mode');renderSettings();window.AuraAccessibility?.announce?.(`Notifications proactives : mode ${STATE.settings.mode==='silent'?'silencieux':'standard'}.`);emit('aura:proactive-notification-mode',{mode:STATE.settings.mode});return STATE.settings.mode}
  function testNotification(){
    const w=window.AuraEventWatchers,settings=w?.settings?.();
    if(!w||typeof w.publish!=='function')return false;
    if(!settings?.families?.system){window.AuraAccessibility?.announce?.('Activez la surveillance système avant le test de notification.');renderSettings();return false}
    const requestedId=`evt-p083-${Date.now().toString(36)}`,fingerprint='p083-notification-test';
    setTimeout(()=>{
      const ok=w.publish({id:requestedId,family:'system',severity:'important',title:'Test notification P0.8.3.2',message:'RAM simulée à 96 % pour valider déduplication, cooldown et routage VOIR. Aucun usage mémoire réel n’est modifié.',source:'p083-local-test',fingerprint,suggestion:'Analyse cette simulation de pression mémoire. Propose uniquement des vérifications sûres et explique la priorité, sans exécuter aucune action.',meta:{notificationTest:true,simulated:true,realSystemImpact:false,expectedPriority:'high',expectedScore:81}});
      if(!ok){window.AuraAccessibility?.announce?.('Le test de notification n’a pas pu être créé.');emit('aura:proactive-notification-test',{ok:false,eventId:requestedId,reason:'watcher-rejected'});return}
      setTimeout(()=>{try{window.AuraSuggestionEngine?.refresh?.()}catch(_e){};const ev=(w.events?.()||[]).find(x=>x.fingerprint===fingerprint||x?.meta?.notificationTest&&/^p083-local-test/i.test(String(x.source||'')));const eventId=safe(ev?.id||requestedId,100),repeatCount=Math.max(1,Number(ev?.meta?.repeatCount)||1);const s=window.AuraSuggestionEngine?.suggestions?.().find(x=>x.eventId===eventId);if(s&&STATE.settings.mode==='standard'&&!STATE.current)showNotification(Object.assign({},s,{test:true}),{force:true,test:true});if(STATE.settings.mode==='silent'){STATE.pending.set(eventId,normalizeSuggestion(Object.assign({},s||{id:`sg-${eventId}`,eventId,priority:'high',score:81,title:'Test notification P0.8.3.2',recommendedAction:'Ouvrir Activity Center sur la détection simulée.',source:'p083-local-test'},{test:true})));updateRail()}emit('aura:proactive-notification-test',{ok:true,eventId,persisted:true,merged:repeatCount>1,repeatCount,simulated:true,autoAction:false})},50);
    },20);
    closeActivityPanel();return true
  }

  function onClick(e){
    const action=e.target.closest?.('[data-p083-action]');if(action){e.preventDefault();e.stopImmediatePropagation();if(action.dataset.p083Action==='view')openActivityCenter();else if(action.dataset.p083Action==='ignore'){const id=STATE.current?.eventId;if(id)STATE.pending.delete(id);updateRail();hideNotification('ignored')}return}
    const mode=e.target.closest?.('[data-p083-mode]');if(mode){e.preventDefault();e.stopImmediatePropagation();setMode(mode.dataset.p083Mode);return}
    const test=e.target.closest?.('[data-p083-test]');if(test){e.preventDefault();e.stopImmediatePropagation();testNotification();return}
  }
  function scheduleDecor(delay=50){clearTimeout(STATE.decorTimer);STATE.decorTimer=setTimeout(()=>{ensureRail();updateRail();ensureSettings()},delay)}
  function bootstrap(){
    load();document.addEventListener('click',onClick,true);document.addEventListener('keydown',e=>{if(e.key==='Escape'&&STATE.current)hideNotification('escape')},true);
    window.addEventListener('aura:suggestion-created',e=>processSuggestion(e.detail?.suggestion||{}));
    window.addEventListener('aura:activity-center-opened',()=>{hideNotification('activity-open');clearPending();scheduleDecor(30);if(STATE.focusEventId)setTimeout(()=>focusActivityEvent(STATE.focusEventId),90)});
    window.addEventListener('aura:activity-center-closed',()=>scheduleDecor(30));
    window.addEventListener('aura:watcher-events-cleared',()=>{clearPending();hideNotification('history-cleared')});
    window.addEventListener('aura:watcher-event-status',e=>{if(e.detail?.status==='dismissed'){STATE.pending.delete(safe(e.detail?.id,100));updateRail();if(STATE.current?.eventId===safe(e.detail?.id,100))hideNotification('event-dismissed')}});window.addEventListener('aura:watcher-permission-changed',()=>scheduleDecor(20));
    window.addEventListener('aura:event-watchers-ui-activated',()=>scheduleDecor(100));window.addEventListener('aura:event-watchers-ready',()=>scheduleDecor(120));window.addEventListener('aura:accessibility-changed',()=>scheduleDecor(40));
    setTimeout(()=>scheduleDecor(0),120);setTimeout(()=>scheduleDecor(0),700);setTimeout(()=>scheduleDecor(0),1800);
    emit('aura:proactive-notifications-ready',{mode:STATE.settings.mode,authority:'notify-only-no-execution',surface:'in-app-only',windowsNotifications:false,sound:false,networkAccess:false,backgroundLlm:false,autoAction:false,features:['event-dedup-merge','repeat-counter','stable-test-fingerprint','normal-shell-indicator','high-compact-notification','urgent-emphasis','view-activity-center','targeted-focus-handoff','persistent-local-test-event','ignore-notification-only','dedup-cooldown','silent-mode','accessibility-motion-aware','local-test']});
  }

  window.AuraProactiveNotifications=Object.freeze({
    version:VERSION,mode:()=>STATE.settings.mode,setMode,notify:s=>processSuggestion(s),test:testNotification,openActivityCenter,focusEvent:id=>focusActivityEvent(id),hide:()=>hideNotification('api'),pending:()=>[...STATE.pending.values()].map(clone),audit:()=>({mode:STATE.settings.mode,pending:STATE.pending.size,current:clone(STATE.current),focusEventId:STATE.focusEventId,activityOpen:activityOpen(),autoAction:false,networkAccess:false,backgroundLlm:false,windowsNotifications:false,sound:false}),authority:'notify-only-no-execution'
  });
  bootstrap();
})();
