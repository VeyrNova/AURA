/* AURA P0.8.2 — SUGGESTION ENGINE
   Deterministic proactive recommendation layer.
   Authority / privacy contract:
   - Consumes only P0.8.1 detections and the explicit AuraContextBridge contract.
   - No background LLM request, no web request, no filesystem access, no conversation scraping.
   - Ranks and explains suggestions locally; never executes an action automatically.
   - Handoff only prepares a prompt in Conversation and never presses Send.
*/
(()=>{
  'use strict';
  if(window.__AURA_P082_SUGGESTION_ENGINE__)return;
  window.__AURA_P082_SUGGESTION_ENGINE__=true;

  const VERSION='P0.8.2';
  const STORAGE='aura.suggestion-engine.p082';
  const MAX_SUGGESTIONS=80;
  const FAMILY_LABELS={agenda:'AGENDA',tasks:'TÂCHES',system:'SYSTÈME',files:'FICHIERS',research:'RECHERCHE'};
  const PRIORITY_LABELS={low:'FAIBLE',normal:'NORMALE',high:'HAUTE',urgent:'URGENTE'};
  const PRIORITY_ORDER={low:1,normal:2,high:3,urgent:4};
  const STATE={items:new Map(),settings:{enabled:true,explainability:true},bootstrapped:false,lastTopId:'',decorateTimer:0};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const safe=(v,n=320)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const clone=v=>{try{return JSON.parse(JSON.stringify(v))}catch(_e){return null}};
  const escapeHtml=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));
  const watchers=()=>window.AuraEventWatchers;

  function defaultStore(){return {settings:{enabled:true,explainability:true},items:[]}}
  function normalizeSettings(raw){return {enabled:raw?.enabled!==false,explainability:raw?.explainability!==false}}
  function normalizeSuggestion(raw){
    if(!raw||typeof raw!=='object')return null;
    const id=safe(raw.id,100);if(!id)return null;
    const priority=['low','normal','high','urgent'].includes(raw.priority)?raw.priority:'normal';
    return {id,eventId:safe(raw.eventId||id,100),family:safe(raw.family,24),priority,score:Math.max(0,Math.min(100,Number(raw.score)||0)),title:safe(raw.title,140),whyNow:safe(raw.whyNow,500),recommendedAction:safe(raw.recommendedAction,500),prompt:safe(raw.prompt,1000),source:safe(raw.source,100),context:raw.context&&typeof raw.context==='object'?clone(raw.context):null,requiresConfirmation:true,execution:'none',createdAt:safe(raw.createdAt,40)||new Date().toISOString()};
  }
  function load(){
    let raw=defaultStore();try{raw=JSON.parse(localStorage.getItem(STORAGE)||'{}')}catch(_e){}
    STATE.settings=normalizeSettings(raw.settings||{});STATE.items.clear();
    (Array.isArray(raw.items)?raw.items:[]).slice(0,MAX_SUGGESTIONS).map(normalizeSuggestion).filter(Boolean).forEach(x=>STATE.items.set(x.eventId,x));
  }
  function persist(){
    try{localStorage.setItem(STORAGE,JSON.stringify({settings:STATE.settings,items:[...STATE.items.values()].slice(0,MAX_SUGGESTIONS)}))}catch(_e){}
  }

  function explicitContextFor(family){
    const raw=window.AuraContextBridge?.get?.();if(!raw||typeof raw!=='object'||raw.cleared)return null;
    const workspace=safe(raw.workspace,32).toLowerCase();
    const allowed=(family==='agenda'||family==='tasks')?workspace==='plan':family==='system'?workspace==='system':false;
    if(!allowed)return null;
    const facts=Array.isArray(raw.facts)?raw.facts.slice(0,6).map(f=>({label:safe(f?.label,80),value:safe(f?.value,160),source:safe(f?.source,60)})).filter(f=>f.label&&f.value):[];
    return {workspace,target:safe(raw.target,220),summary:safe(raw.summary,420),facts};
  }

  function urgencyBoost(event){
    const text=`${safe(event?.title,140)} ${safe(event?.message,520)}`.toLowerCase();let boost=0;
    if(/moins d[’']une heure/.test(text))boost+=18;
    const mins=text.match(/(?:dans|environ)\s+(\d+)\s*min/);if(mins){const n=Number(mins[1]);boost+=n<=10?20:n<=30?10:4}
    const hours=text.match(/(?:dans|environ)\s+(\d+)\s*h/);if(hours){const n=Number(hours[1]);boost+=n<=3?12:n<=12?6:2}
    const pct=[...text.matchAll(/(\d{2,3})\s*%/g)].map(x=>Number(x[1])).filter(Number.isFinite);const peak=pct.length?Math.max(...pct):0;if(peak>=98)boost+=12;else if(peak>=95)boost+=8;else if(peak>=90)boost+=4;
    return boost;
  }
  function scoreEvent(event){
    const severity={info:28,important:62,critical:88}[event?.severity]??28;
    const family={agenda:10,tasks:9,system:11,files:4,research:5}[event?.family]??0;
    return Math.max(0,Math.min(100,Math.round(severity+family+urgencyBoost(event))));
  }
  function priorityFor(score){return score>=86?'urgent':score>=66?'high':score>=42?'normal':'low'}
  function recommendedAction(event){
    switch(event?.family){
      case'agenda':return'Préparer le rendez-vous, vérifier ce qui est nécessaire avant le départ ou le début, puis te laisser choisir les actions à effectuer.';
      case'tasks':return'Revoir la priorité, identifier la prochaine étape concrète et proposer un plan court avant toute modification de la tâche.';
      case'system':return'Vérifier les métriques concernées, isoler les causes probables et proposer uniquement des contrôles sûrs avant toute action système.';
      case'files':return'Comparer le changement ou relancer une analyse en lecture seule, puis présenter les différences avant toute écriture.';
      case'research':return'Résumer ce qui a réellement changé, qualifier l’importance du nouveau résultat et indiquer si une action mérite ton attention.';
      default:return'Examiner la détection et proposer la prochaine étape sans exécuter d’action automatiquement.';
    }
  }
  function buildPrompt(event,context){
    let base=safe(event?.suggestion,850);
    if(!base){
      const family=FAMILY_LABELS[event?.family]||'ÉVÉNEMENT';
      base=`Analyse cette détection ${family} : « ${safe(event?.title,120)} ». ${safe(event?.message,360)} Propose la prochaine étape utile, mais n’exécute aucune action sans ma confirmation.`;
    }
    if(context?.target)base+=` Contexte actif explicitement autorisé : ${safe(context.target,180)}.`;
    return safe(base,1000);
  }
  function buildSuggestion(event){
    if(!event||!event.id)return null;const score=scoreEvent(event),priority=priorityFor(score),context=explicitContextFor(event.family);
    return normalizeSuggestion({id:`sg-${event.id}`,eventId:event.id,family:event.family,priority,score,title:safe(event.title,140)||'Suggestion AURA',whyNow:safe(event.message,500)||'Une détection autorisée vient d’être publiée.',recommendedAction:recommendedAction(event),prompt:buildPrompt(event,context),source:safe(event.source,100)||'watcher',context,requiresConfirmation:true,execution:'none',createdAt:new Date().toISOString()});
  }
  function evaluate(event,{silent=false}={}){
    if(!STATE.settings.enabled)return null;const s=buildSuggestion(event);if(!s)return null;STATE.items.set(s.eventId,s);persist();scheduleDecorate();
    if(!silent){emit('aura:suggestion-created',{suggestion:clone(s),authority:'recommend-only',requiresConfirmation:true});announceTopChange()}
    return clone(s);
  }
  function all(){return [...STATE.items.values()].sort((a,b)=>(PRIORITY_ORDER[b.priority]-PRIORITY_ORDER[a.priority])||(b.score-a.score)||Date.parse(b.createdAt)-Date.parse(a.createdAt)).map(clone)}
  function watcherEvents(){return Array.isArray(watchers()?.events?.())?watchers().events():[]}
  function eventById(id){return watcherEvents().find(e=>e.id===id)||null}
  function activeItems(){const statuses=new Map(watcherEvents().map(e=>[e.id,e.status]));return all().filter(s=>statuses.get(s.eventId)!=='dismissed')}
  function top(){return activeItems()[0]||null}
  function explain(id){const s=STATE.items.get(id)||STATE.items.get(safe(id,100))||[...STATE.items.values()].find(x=>x.id===id);return s?clone({priority:s.priority,score:s.score,whyNow:s.whyNow,recommendedAction:s.recommendedAction,source:s.source,context:s.context,requiresConfirmation:true,execution:'none'}):null}

  function fillConversation(prompt){
    if(!prompt)return false;
    try{window.AuraEventWatchers?.close?.()}catch(_e){}
    try{window.AuraConversationDrawer?.open?.()}catch(_e){}
    const tryFill=()=>{
      const input=q('.aura-p0712-conversation-drawer [data-input]')||q('.aura-p071-conversation-drawer [data-input]')||q('#messageInput');if(!input)return false;
      input.value=prompt;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();return true;
    };
    if(tryFill())return true;setTimeout(tryFill,80);setTimeout(tryFill,220);return true;
  }
  function prepare(eventId){
    const s=STATE.items.get(eventId)||all().find(x=>x.id===eventId);if(!s)return false;
    const ok=fillConversation(s.prompt);if(ok)emit('aura:suggestion-prepared',{eventId:s.eventId,suggestionId:s.id,requiresConfirmation:true,autoSend:false});return ok;
  }
  function announceTopChange(){
    const t=top();if(!t||t.id===STATE.lastTopId)return;STATE.lastTopId=t.id;
    if(t.priority==='urgent'||t.priority==='high')window.AuraAccessibility?.announce?.(`Suggestion ${PRIORITY_LABELS[t.priority].toLowerCase()}. ${t.title}.`);
  }

  function ensureEngineStrip(root){
    let strip=q('.aura-p082-engine-strip',root);if(strip)return strip;
    strip=document.createElement('section');strip.className='aura-p082-engine-strip';
    const overview=q('.aura-p081-overview',root);if(overview)overview.insertAdjacentElement('afterend',strip);else q('.aura-p081-body',root)?.prepend(strip);return strip;
  }
  function renderEngineStrip(root){
    const strip=ensureEngineStrip(root),items=activeItems(),t=items[0],high=items.filter(x=>x.priority==='urgent'||x.priority==='high').length;
    strip.innerHTML=`<div class="aura-p082-engine-head"><span><small>SUGGESTION ENGINE · v1.0.0</small><b>${t?'PRIORISATION ACTIVE':'EN ATTENTE'}</b></span><i>LOCAL · 0 ACTION AUTO</i></div>${t?`<div class="aura-p082-next"><span class="aura-p082-priority" data-priority="${t.priority}">${PRIORITY_LABELS[t.priority]} · ${t.score}</span><div><small>PROCHAINE SUGGESTION</small><strong>${escapeHtml(t.title)}</strong><p>${escapeHtml(t.recommendedAction)}</p></div><button type="button" data-p082-prepare="${escapeHtml(t.eventId)}">PRÉPARER</button></div>`:`<div class="aura-p082-empty">Les détections autorisées seront classées ici avant toute proposition.</div>`}<div class="aura-p082-engine-foot"><span>${items.length} suggestion${items.length>1?'s':''} active${items.length>1?'s':''}</span><span>${high} priorité${high>1?'s':''} haute${high>1?'s':''}</span><span>Décision locale déterministe</span></div>`;
  }
  function decorateCard(card){
    const id=safe(card.dataset.eventId,100),s=STATE.items.get(id);if(!s)return;
    card.dataset.p082Priority=s.priority;card.style.setProperty('--aura-p082-score',String(s.score));
    let insight=q('.aura-p082-insight',card);if(!insight){insight=document.createElement('div');insight.className='aura-p082-insight';const actions=q('.aura-p081-event-actions',card);actions?.insertAdjacentElement('beforebegin',insight)}
    insight.innerHTML=`<div class="aura-p082-insight-line"><span class="aura-p082-priority" data-priority="${s.priority}">${PRIORITY_LABELS[s.priority]} · ${s.score}</span><span>${escapeHtml(s.recommendedAction)}</span></div><div class="aura-p082-explain" hidden><b>POURQUOI MAINTENANT ?</b><p>${escapeHtml(s.whyNow)}</p><small>Source : ${escapeHtml(s.source)} · aucune action exécutée</small></div>`;
    const existing=q('[data-p081-event-action="suggest"]',card);if(existing){existing.textContent='PRÉPARER AVEC AURA';existing.dataset.p082Prepare=id}
    const actions=q('.aura-p081-event-actions',card);if(actions&&!q('[data-p082-explain]',actions)){const b=document.createElement('button');b.type='button';b.dataset.p082Explain=id;b.textContent='POURQUOI ?';actions.prepend(b)}
  }
  function decorate(){
    clearTimeout(STATE.decorateTimer);STATE.decorateTimer=0;const root=q('.aura-p081-panel');if(!root||root.hidden)return false;
    watcherEvents().forEach(e=>{if(!STATE.items.has(e.id))evaluate(e,{silent:true})});renderEngineStrip(root);qa('.aura-p081-event[data-event-id]',root).forEach(decorateCard);return true;
  }
  function scheduleDecorate(delay=30){clearTimeout(STATE.decorateTimer);STATE.decorateTimer=setTimeout(()=>{requestAnimationFrame(()=>decorate())},Math.max(0,delay))}

  function onCaptureClick(e){
    const prep=e.target.closest?.('[data-p082-prepare]');if(prep){e.preventDefault();e.stopImmediatePropagation();prepare(prep.dataset.p082Prepare);return}
    const explainBtn=e.target.closest?.('[data-p082-explain]');if(explainBtn){e.preventDefault();e.stopImmediatePropagation();const card=explainBtn.closest('.aura-p081-event'),box=q('.aura-p082-explain',card);if(box){box.hidden=!box.hidden;explainBtn.textContent=box.hidden?'POURQUOI ?':'MASQUER'}return}
    const legacy=e.target.closest?.('[data-p081-event-action="suggest"]');if(legacy){const card=legacy.closest('.aura-p081-event'),id=safe(card?.dataset?.eventId,100);if(STATE.items.has(id)){e.preventDefault();e.stopImmediatePropagation();prepare(id);return}}
    if(e.target.closest?.('[data-module="activity-center"],[data-p081-action]'))scheduleDecorate(80);
  }
  function onStatus(e){const id=safe(e.detail?.id,100);if(e.detail?.status==='dismissed'&&id){}scheduleDecorate(20);announceTopChange()}
  function backfill(){watcherEvents().forEach(e=>evaluate(e,{silent:true}));persist();scheduleDecorate(80);announceTopChange()}
  function bootstrap(){
    if(STATE.bootstrapped)return;STATE.bootstrapped=true;load();
    document.addEventListener('click',onCaptureClick,true);
    window.addEventListener('aura:watcher-detected',e=>evaluate(e.detail?.event||{}));
    window.addEventListener('aura:watcher-event-status',onStatus);
    window.addEventListener('aura:watcher-events-cleared',()=>{STATE.items.clear();persist();scheduleDecorate(20)});
    window.addEventListener('aura:event-watchers-ui-activated',()=>scheduleDecorate(100));
    window.addEventListener('aura:workspace-overlay-changed',()=>scheduleDecorate(80));
    window.addEventListener('aura:event-watchers-ready',()=>setTimeout(backfill,80),{once:true});
    if(watchers())setTimeout(backfill,120);
    emit('aura:suggestion-engine-ready',{authority:'recommend-only-no-execution',backgroundLlm:false,networkAccess:false,context:'explicit-contract-only',requiresConfirmation:true,features:['deterministic-priority','local-ranking','why-now','recommended-next-step','explicit-context-only','conversation-handoff-no-send','no-background-llm','no-auto-execution']});
  }

  window.AuraSuggestionEngine=Object.freeze({version:VERSION,evaluate,score:scoreEvent,suggestions:all,top,explain,prepare,refresh:()=>{backfill();return top()},settings:()=>clone(STATE.settings),setEnabled:on=>{STATE.settings.enabled=!!on;persist();scheduleDecorate();return STATE.settings.enabled},authority:'recommend-only-no-execution'});
  bootstrap();
})();
