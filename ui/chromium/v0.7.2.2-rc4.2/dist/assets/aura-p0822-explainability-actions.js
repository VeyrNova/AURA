/* AURA P0.8.2.2 — EXPLAINABILITY & SUGGESTION ACTIONS HOTFIX
   Makes P0.8.2 priority reasoning visible at the top of Activity Center.
   Safety contract:
   - deterministic/local score explanation only;
   - reads only AuraSuggestionEngine + AuraEventWatchers public contracts;
   - no LLM, network, filesystem, OS action, or automatic send;
   - PREPARER AVEC AURA keeps P0.8.2 handoff semantics (fill only, never Send).
*/
(()=>{
  'use strict';
  if(window.__AURA_P0822_EXPLAINABILITY_ACTIONS__)return;
  window.__AURA_P0822_EXPLAINABILITY_ACTIONS__=true;

  const VERSION='P0.8.2.2';
  const PRIORITY_LABELS={low:'FAIBLE',normal:'NORMALE',high:'HAUTE',urgent:'URGENTE'};
  const SEVERITY_POINTS={info:28,important:62,critical:88};
  const FAMILY_POINTS={agenda:10,tasks:9,system:11,files:4,research:5};
  const FAMILY_LABELS={agenda:'AGENDA',tasks:'TÂCHES',system:'SYSTÈME',files:'FICHIERS',research:'RECHERCHE'};
  const STATE={timer:0,openTopId:'',lastPrepared:''};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const safe=(v,n=500)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const engine=()=>window.AuraSuggestionEngine;
  const watchers=()=>window.AuraEventWatchers;
  const panel=()=>q('.aura-p081-panel');
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));

  function eventFor(eventId){
    const list=watchers()?.events?.();
    return Array.isArray(list)?list.find(e=>safe(e?.id,100)===safe(eventId,100))||null:null;
  }
  function urgencyFactors(event){
    const text=`${safe(event?.title,140)} ${safe(event?.message,520)}`.toLowerCase();
    const out=[];
    if(/moins d[’']une heure/.test(text))out.push({key:'time-lt-hour',label:'Échéance dans moins d’une heure',points:18});
    const mins=text.match(/(?:dans|environ)\s+(\d+)\s*min/);
    if(mins){const n=Number(mins[1]);out.push({key:'minutes',label:`Temporalité · ${n} min`,points:n<=10?20:n<=30?10:4});}
    const hours=text.match(/(?:dans|environ)\s+(\d+)\s*h/);
    if(hours){const n=Number(hours[1]);out.push({key:'hours',label:`Temporalité · ${n} h`,points:n<=3?12:n<=12?6:2});}
    const pct=[...text.matchAll(/(\d{2,3})\s*%/g)].map(x=>Number(x[1])).filter(Number.isFinite);
    const peak=pct.length?Math.max(...pct):0;
    if(peak>=98)out.push({key:'pressure',label:`Pression ≥ 98 % · pic ${peak} %`,points:12});
    else if(peak>=95)out.push({key:'pressure',label:`Pression ≥ 95 % · pic ${peak} %`,points:8});
    else if(peak>=90)out.push({key:'pressure',label:`Pression ≥ 90 % · pic ${peak} %`,points:4});
    return out;
  }
  function priorityFor(score){return score>=86?'urgent':score>=66?'high':score>=42?'normal':'low'}
  function thresholdText(priority){
    return priority==='urgent'?'URGENTE ≥ 86':priority==='high'?'HAUTE ≥ 66':priority==='normal'?'NORMALE ≥ 42':'FAIBLE < 42';
  }
  function breakdown(eventId){
    const e=eventFor(eventId),s=engine()?.suggestions?.().find(x=>x.eventId===eventId)||engine()?.top?.();
    if(!e||!s)return null;
    const severity=SEVERITY_POINTS[e.severity]??28,family=FAMILY_POINTS[e.family]??0;
    const factors=[
      {key:'severity',label:`Sévérité ${safe(e.severity,20).toUpperCase()||'INFO'}`,points:severity},
      {key:'family',label:`Famille ${FAMILY_LABELS[e.family]||safe(e.family,24).toUpperCase()||'ÉVÉNEMENT'}`,points:family},
      ...urgencyFactors(e)
    ];
    const computed=Math.max(0,Math.min(100,Math.round(factors.reduce((n,f)=>n+f.points,0))));
    return {event:e,suggestion:s,factors,computed,engineScore:Number(s.score)||0,priority:s.priority,priorityLabel:PRIORITY_LABELS[s.priority]||s.priority,threshold:thresholdText(s.priority),matchesEngine:computed===(Number(s.score)||0),controlledTest:!!e?.meta?.controlledTest,simulated:!!e?.meta?.simulated};
  }
  function factorHtml(f){return `<span class="aura-p0822-factor"><b>${esc(f.label)}</b><i>+${Number(f.points)||0}</i></span>`}
  function explanationHtml(b){
    if(!b)return '';
    const x=engine()?.explain?.(b.suggestion.eventId)||{};
    const safety=b.simulated?'Simulation locale · aucun impact système réel':'Détection autorisée · lecture et classement uniquement';
    return `<div class="aura-p0822-explain-body">
      <div class="aura-p0822-explain-head"><span><small>POURQUOI CETTE PRIORITÉ ?</small><b>${esc(b.priorityLabel)} · ${b.engineScore}/100</b></span><i>${esc(b.threshold)}</i></div>
      <p class="aura-p0822-why">${esc(x.whyNow||b.event.message||'Détection autorisée reçue.')}</p>
      <div class="aura-p0822-factors">${b.factors.map(factorHtml).join('')}</div>
      <div class="aura-p0822-scoreline"><span>CALCUL LOCAL</span><strong>${b.computed}/100</strong><em>${b.matchesEngine?'COHÉRENT AVEC v1.0.0':'À REVÉRIFIER'}</em></div>
      <div class="aura-p0822-nextstep"><small>PROCHAINE ÉTAPE PROPOSÉE</small><p>${esc(x.recommendedAction||b.suggestion.recommendedAction||'Examiner la détection avant toute action.')}</p></div>
      <div class="aura-p0822-safety"><b>0 ACTION AUTO</b><span>${esc(safety)}. « Préparer avec AURA » remplit Conversation mais n’envoie aucun message.</span></div>
    </div>`;
  }

  function enhanceTop(root=panel()){
    if(!root||root.hidden)return false;
    const top=engine()?.top?.(),next=q('.aura-p082-next',root);if(!top||!next)return false;
    const b=breakdown(top.eventId);if(!b)return false;
    const badge=q('.aura-p082-priority',next);if(badge)badge.textContent=`${b.priorityLabel} · ${b.engineScore}/100`;
    const original=q('[data-p082-prepare]',next);
    let actions=q('.aura-p0822-top-actions',next);
    if(!actions){
      actions=document.createElement('div');actions.className='aura-p0822-top-actions';
      const why=document.createElement('button');why.type='button';why.dataset.p0822ExplainTop=top.eventId;why.className='aura-p0822-why-btn';why.textContent='POURQUOI ?';why.setAttribute('aria-expanded',STATE.openTopId===top.eventId?'true':'false');actions.appendChild(why);
      if(original){original.textContent='PRÉPARER AVEC AURA';original.classList.add('aura-p0822-prepare-btn');actions.appendChild(original)}
      next.appendChild(actions);
    }else{
      const why=q('[data-p0822-explain-top]',actions);if(why){why.dataset.p0822ExplainTop=top.eventId;why.setAttribute('aria-expanded',STATE.openTopId===top.eventId?'true':'false');why.textContent=STATE.openTopId===top.eventId?'MASQUER':'POURQUOI ?'}
      const prep=q('[data-p082-prepare]',actions);if(prep)prep.textContent='PRÉPARER AVEC AURA';
    }
    let box=q('.aura-p0822-top-explain',next);if(!box){box=document.createElement('section');box.className='aura-p0822-top-explain';next.appendChild(box)}
    box.dataset.eventId=top.eventId;box.innerHTML=explanationHtml(b);box.hidden=STATE.openTopId!==top.eventId;
    return true;
  }
  function enhanceCards(root=panel()){
    if(!root||root.hidden)return;
    qa('.aura-p081-event[data-event-id]',root).forEach(card=>{
      const id=safe(card.dataset.eventId,100),b=breakdown(id);if(!b)return;
      const badge=q('.aura-p082-insight .aura-p082-priority',card);if(badge)badge.textContent=`${b.priorityLabel} · ${b.engineScore}/100`;
      const explain=q('.aura-p082-explain',card);if(explain){explain.innerHTML=explanationHtml(b);explain.classList.add('aura-p0822-card-explain')}
      const why=q('[data-p082-explain]',card);if(why){why.textContent=explain&&!explain.hidden?'MASQUER':'POURQUOI ?';why.title='Afficher le détail local du score et les facteurs de priorité'}
      const prep=q('[data-p082-prepare],[data-p081-event-action="suggest"]',card);if(prep)prep.textContent='PRÉPARER AVEC AURA';
    });
  }
  function sync(){clearTimeout(STATE.timer);STATE.timer=0;const root=panel();if(!root||root.hidden)return false;enhanceTop(root);enhanceCards(root);return true}
  function schedule(delay=40){clearTimeout(STATE.timer);STATE.timer=setTimeout(()=>requestAnimationFrame(()=>sync()),Math.max(0,delay))}
  function scheduleSettled(){schedule(20);setTimeout(()=>sync(),100);setTimeout(()=>sync(),260)}

  document.addEventListener('click',ev=>{
    const topWhy=ev.target.closest?.('[data-p0822-explain-top]');
    if(topWhy){ev.preventDefault();ev.stopImmediatePropagation();const id=safe(topWhy.dataset.p0822ExplainTop,100);STATE.openTopId=STATE.openTopId===id?'':id;sync();emit('aura:suggestion-explanation-toggled',{eventId:id,open:STATE.openTopId===id,backgroundLlm:false,networkAccess:false});return}
    if(ev.target.closest?.('[data-module="activity-center"],[data-p081-family],[data-p081-action],[data-p0821-test-local]'))scheduleSettled();
  },true);
  ['aura:suggestion-created','aura:watcher-detected','aura:watcher-event-status','aura:event-watchers-ui-activated','aura:activity-center-opened','aura:workspace-overlay-changed','aura:p0821-controlled-test'].forEach(name=>window.addEventListener(name,()=>scheduleSettled()));
  window.addEventListener('aura:watcher-events-cleared',()=>{STATE.openTopId='';scheduleSettled()});
  window.addEventListener('aura:suggestion-prepared',ev=>{STATE.lastPrepared=safe(ev.detail?.eventId,100);window.AuraAccessibility?.announce?.('Suggestion préparée dans Conversation. Aucun message envoyé.');emit('aura:p0822-prepared-confirmed',{eventId:STATE.lastPrepared,autoSend:false});});
  setTimeout(()=>scheduleSettled(),220);

  window.AuraSuggestionExplainability=Object.freeze({
    version:VERSION,
    top:()=>{const t=engine()?.top?.();return t?breakdown(t.eventId):null},
    breakdown,
    refresh:()=>{sync();return engine()?.top?.()||null},
    audit:()=>{const t=engine()?.top?.();const b=t?breakdown(t.eventId):null;return {ready:!!(engine()&&watchers()),topEventId:t?.eventId||'',score:b?.engineScore??null,computed:b?.computed??null,scoreMatch:!!b?.matchesEngine,priority:b?.priority||'',explainButton:!!q('[data-p0822-explain-top]'),prepareButton:!!q('.aura-p0822-top-actions [data-p082-prepare]'),autoSend:false,networkAccess:false,backgroundLlm:false,execution:'none'}},
    authority:'explain-and-prepare-only-no-execution',backgroundLlm:false,networkAccess:false,autoSend:false
  });
  emit('aura:p0822-explainability-ready',{authority:'explain-and-prepare-only-no-execution',backgroundLlm:false,networkAccess:false,autoSend:false,features:['visible-score-100','deterministic-factor-breakdown','why-now','safety-reminder','prepare-with-aura-no-send']});
})();
