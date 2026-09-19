(() => {
'use strict';
if(window.__AURA_V123_VISIBLE_PRODUCTIVITY_REBIND__)return;
const S={cache:{tasks:null,calendar:null},stamp:{tasks:0,calendar:0},pending:null,reason:null,returnTarget:null,month:new Date(new Date().getFullYear(),new Date().getMonth(),1),timer:null};
window.__AURA_V123_VISIBLE_PRODUCTIVITY_REBIND__=S;
const D='.aura-p0623-drawer',C='.aura-p0623-content',RID='aura-v123-personal-results';
const q=(s,r=document)=>r.querySelector(s),qa=(s,r=document)=>Array.from(r.querySelectorAll(s));
const t=v=>String(v==null?'':v).trim();
const esc=v=>t(v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
function token(){
  try{const x=new URL(location.href).searchParams.get('token');if(x)return x}catch{}
  try{for(const e of (performance.getEntriesByType('resource')||[]).slice().reverse()){const n=t(e&&e.name);if(n.includes('/api/events')){const x=new URL(n,location.href).searchParams.get('token');if(x)return x}}}catch{}
  return '';
}
async function action(action,payload={}){
  const tok=token();if(!tok)throw new Error('AURA token indisponible');
  const r=await fetch(`/api/action?token=${encodeURIComponent(tok)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})});
  let b={};try{b=await r.json()}catch{}
  if(!r.ok||b?.ok===false)throw new Error(t(b?.error||b?.message||`HTTP ${r.status}`));
  return b;
}
function kind(p){const k=t(p&&p.kind).toLowerCase();if(['tasks','task','todo','todos'].includes(k))return'tasks';if(['calendar','agenda','events','event'].includes(k))return'calendar';return k}
function items(p){if(!p||typeof p!=='object')return[];for(const k of ['items','tasks','events','results'])if(Array.isArray(p[k]))return p[k];return[]}
function src(i){const s=t(i&&(i.source||i.origin||i.provider||i.provider_id)).toUpperCase();if(s.includes('GOOGLE'))return'GOOGLE';if(s.includes('AURA')||s.includes('LOCAL'))return'AURA';return s}
function title(i){return t(i&&(i.title||i.summary||i.content||i.name||i.subject))||'Sans titre'}
function dateOf(i){const r=i&&(i.start_time||i.start||i.start_at||i.date_time||i.due||i.due_at||i.trigger_at||i.scheduled_at||i.when||i.date);if(!r)return null;const d=new Date(r);return Number.isNaN(d.getTime())?null:d}
function fmt(d){if(!d)return'';try{return new Intl.DateTimeFormat('fr-FR',{dateStyle:'short',timeStyle:'short'}).format(d)}catch{return d.toLocaleString()}}
function same(a,b){return a&&b&&a.getFullYear()===b.getFullYear()&&a.getMonth()===b.getMonth()&&a.getDate()===b.getDate()}
function status(kind,msg,err=false){qa(`[data-v123-sync-status="${kind}"]`).forEach(x=>{x.textContent=msg||'';x.classList.toggle('is-error',!!err)})}
function ensureCalendarTab(){
  const d=q(D);if(!d)return false;const n=q(':scope > nav',d)||q('nav',d);if(!n)return false;
  let b=q('[data-tab="calendar"]',n);if(!b){b=document.createElement('button');b.type='button';b.dataset.tab='calendar';b.textContent='CALENDRIER';const r=q('[data-tab="reminders"]',n);r?n.insertBefore(b,r):n.appendChild(b)}
  qa('.aura-v0922-agenda-calendar-bridge',d).forEach(x=>x.remove());return true;
}
function taskSurface(){
  const d=q(D);if(!d||!q('[data-tab="tasks"].active',d))return;const c=q(C,d);if(!c)return;
  if(!q('.aura-v123-native-syncbar[data-kind="tasks"]',c)){const b=document.createElement('div');b.className='aura-v123-native-syncbar';b.dataset.kind='tasks';b.innerHTML='<div><b>TÂCHES · AURA + GOOGLE</b><small data-v123-sync-status="tasks">Synchronisation prête</small></div><button type="button" data-v123-refresh="tasks">ACTUALISER TOUT</button>';c.insertBefore(b,c.firstChild)}
  let g=q('.aura-v123-google-task-section',c);if(!g){g=document.createElement('section');g.className='aura-v123-google-task-section';const f=q('form[data-form="task"]',c);f&&f.nextSibling?c.insertBefore(g,f.nextSibling):c.appendChild(g)}
  const l=q('.aura-p0623-list',c);if(l&&!l.previousElementSibling?.classList?.contains('aura-v123-local-label')){const z=document.createElement('div');z.className='aura-v123-local-label';z.innerHTML='<span>AURA LOCAL</span><small>Tâches enregistrées dans AURA</small>';l.parentNode.insertBefore(z,l)}
  renderTasks();
}
function renderTasks(){
  qa('.aura-v123-google-task-section').forEach(g=>{const p=S.cache.tasks;if(!p){g.innerHTML='<div class="aura-v123-section-head"><span>GOOGLE TASKS</span><small>En attente</small></div><div class="aura-v123-native-empty">Chargement Google non effectué.</div>';return}
    const raw=items(p);const isReceiptArtifact=i=>{const st=t(i&&i.status).toLowerCase(),tt=t(title(i)).toLowerCase();return st==='failed'||tt.startsWith('action non executee')||tt.startsWith('action non exécutée')||tt.startsWith("recu d'action")||tt.startsWith("reçu d'action")};const rejected=raw.filter(isReceiptArtifact);const all=raw.filter(i=>!isReceiptArtifact(i));let rows=all.filter(x=>src(x)==='GOOGLE');if(!rows.length&&all.length&&!all.some(x=>src(x)==='AURA'))rows=all;
    g.innerHTML=`<div class="aura-v123-section-head"><span>GOOGLE TASKS</span><small>${rows.length} tâche${rows.length===1?'':'s'}</small></div>`+(rows.map(i=>`<div class="aura-v123-google-task-row"><span class="aura-v123-source-badge google">GOOGLE</span><div><b>${esc(title(i))}</b><small>${esc(fmt(dateOf(i))||t(i.status)||'Google Tasks')}</small></div></div>`).join('')||(rejected.length?'<div class="aura-v123-native-empty is-error">Synchronisation Google Tasks indisponible — aucun reçu d’action n’est affiché comme tâche.</div>':'<div class="aura-v123-native-empty">Aucune tâche Google.</div>'));
  })
}
function monthItems(){return items(S.cache.calendar).map(i=>({i,d:dateOf(i)})).filter(x=>x.d)}
function calendar(){
  const d=q(D);if(!d)return;ensureCalendarTab();const n=q(':scope > nav',d)||q('nav',d);if(n)qa('[data-tab]',n).forEach(b=>b.classList.toggle('active',b.dataset.tab==='calendar'));
  qa('.aura-v0922-agenda-calendar-bridge',d).forEach(x=>x.remove());const c=q(C,d);if(!c)return;
  const m=new Date(S.month.getFullYear(),S.month.getMonth(),1),st=new Date(m);st.setDate(st.getDate()-((st.getDay()+6)%7));const all=monthItems();
  let cells=['LUN','MAR','MER','JEU','VEN','SAM','DIM'].map(x=>`<div class="aura-v123-cal-weekday">${x}</div>`).join('');
  for(let i=0;i<42;i++){const day=new Date(st);day.setDate(st.getDate()+i);const ev=all.filter(x=>same(x.d,day));cells+=`<div class="aura-v123-cal-day${day.getMonth()===m.getMonth()?'':' muted'}${same(day,new Date())?' today':''}"><div class="aura-v123-cal-num">${day.getDate()}</div>${ev.slice(0,4).map(x=>{const s=src(x.i)||'AURA';return`<div class="aura-v123-cal-pill ${s==='GOOGLE'?'google':'aura'}"><span>${s==='GOOGLE'?'G':'A'}</span>${esc(title(x.i))}</div>`}).join('')}${ev.length>4?`<small>+${ev.length-4}</small>`:''}</div>`}
  const list=all.filter(x=>x.d.getMonth()===m.getMonth()&&x.d.getFullYear()===m.getFullYear()).sort((a,b)=>a.d-b.d).slice(0,30);
  c.innerHTML=`<section class="aura-v123-native-calendar"><div class="aura-v123-native-syncbar" data-kind="calendar"><div><b>AGENDA · AURA + GOOGLE</b><small data-v123-sync-status="calendar">${S.cache.calendar?'Synchronisé':'Synchronisation prête'}</small></div><button type="button" data-v123-refresh="calendar">ACTUALISER TOUT</button></div><div class="aura-v123-cal-toolbar"><button data-v123-month="-1">‹</button><button data-v123-today>AUJOURD’HUI</button><strong>${esc(new Intl.DateTimeFormat('fr-FR',{month:'long',year:'numeric'}).format(m).toUpperCase())}</strong><button data-v123-month="1">›</button></div><div class="aura-v123-cal-grid">${cells}</div><div class="aura-v123-cal-list"><div class="aura-v123-section-head"><span>ÉLÉMENTS DU MOIS</span><small>${list.length}</small></div>${list.map(x=>{const s=src(x.i)||'AURA';return`<div class="aura-v123-cal-list-row"><span class="aura-v123-source-badge ${s==='GOOGLE'?'google':'aura'}">${esc(s)}</span><div><b>${esc(title(x.i))}</b><small>${esc(fmt(x.d))}</small></div></div>`}).join('')||'<div class="aura-v123-native-empty">Aucun événement ou rappel pour ce mois.</div>'}</div></section>`;
}
function hidePanel(){const p=document.getElementById(RID);if(p)p.hidden=true;try{window.dispatchEvent(new Event('resize'))}catch{}}
function restore(target){if(!target)return;const b=q(`[data-rail-target="${target}"]`);if(b){b.click();setTimeout(()=>target==='agenda'?calendar():taskSurface(),80)}}
function fresh(k){return!!S.cache[k]&&(Date.now()-S.stamp[k])<60000}
async function refresh(k,reason='native'){
  if(S.pending)return;S.pending=k;S.reason=reason;S.returnTarget=reason==='native'?(k==='calendar'?'agenda':'tasks'):null;status(k,'Synchronisation AURA + Google…');qa(`[data-v123-refresh="${k}"]`).forEach(b=>b.disabled=true);
  try{await action('send_message',{text:k==='tasks'?'Aura, affiche mes taches':'Aura, affiche mon agenda',silent:true,speak:false,source:'native-productivity-refresh-v123'});
    clearTimeout(S.timer);S.timer=setTimeout(()=>{if(S.pending===k){S.pending=null;S.reason=null;S.returnTarget=null;status(k,'Réponse non reçue',true);qa(`[data-v123-refresh="${k}"]`).forEach(b=>b.disabled=false)}},20000)
  }catch(e){S.pending=null;S.reason=null;S.returnTarget=null;status(k,t(e&&e.message)||'Échec',true);qa(`[data-v123-refresh="${k}"]`).forEach(b=>b.disabled=false)}
}
window.addEventListener('aura:hub-event',e=>{const m=e&&e.detail||{},ty=t(m.type);if(ty==='personal_result'){const k=kind(m.data||{});if(k==='tasks'||k==='calendar'){const incoming=m.data||{};if(k==='tasks'){const rr=items(incoming),artifact=i=>{const st=t(i&&i.status).toLowerCase(),tt=t(title(i)).toLowerCase();return st==='failed'||tt.startsWith('action non executee')||tt.startsWith('action non exécutée')||tt.startsWith("recu d'action")||tt.startsWith("reçu d'action")};if(rr.length&&rr.every(artifact)){if(S.pending===k){clearTimeout(S.timer);S.pending=null;S.reason=null;S.returnTarget=null;qa(`[data-v123-refresh="${k}"]`).forEach(b=>b.disabled=false)}status(k,'Réponse Google Tasks invalide — reçu d’action ignoré',true);return}}S.cache[k]=incoming;S.stamp[k]=Date.now();const pending=S.pending===k;if(pending){clearTimeout(S.timer);S.pending=null;status(k,'Synchronisé');qa(`[data-v123-refresh="${k}"]`).forEach(b=>b.disabled=false);if(S.reason==='native')setTimeout(hidePanel,0);S.reason=null}k==='tasks'?setTimeout(taskSurface,0):q(`${D} [data-tab="calendar"].active`)&&setTimeout(calendar,0)}}else if(ty==='aura_message'&&S.returnTarget){const z=S.returnTarget;S.returnTarget=null;setTimeout(()=>restore(z),120)}});
document.addEventListener('click',e=>{const b=e.target.closest(`${D} [data-tab="calendar"]`);if(b){e.preventDefault();e.stopImmediatePropagation();calendar()}},true);
document.addEventListener('click',e=>{
  const r=e.target.closest('[data-v123-refresh]');if(r){e.preventDefault();refresh(r.dataset.v123Refresh,'native');return}
  const mb=e.target.closest('[data-v123-month]');if(mb){S.month=new Date(S.month.getFullYear(),S.month.getMonth()+(Number(mb.dataset.v123Month)||0),1);calendar();return}
  if(e.target.closest('[data-v123-today]')){const n=new Date();S.month=new Date(n.getFullYear(),n.getMonth(),1);calendar();return}
  const rail=e.target.closest('[data-rail-target]');if(!rail)return;const id=rail.dataset.railTarget;if(id!=='tasks'&&id!=='agenda')return;setTimeout(()=>{ensureCalendarTab();if(id==='agenda'){calendar();if(!fresh('calendar'))refresh('calendar','native')}else{taskSurface();if(!fresh('tasks'))refresh('tasks','native')}},100)
});
function sync(){if(!ensureCalendarTab())return;if(q(`${D} [data-tab="calendar"].active`))calendar();else if(q(`${D} [data-tab="tasks"].active`))taskSurface()}
window.addEventListener('aura:workspace-changed',()=>setTimeout(sync,50));window.addEventListener('resize',()=>setTimeout(sync,50),{passive:true});
let n=0;const boot=setInterval(()=>{sync();if(++n>=30)clearInterval(boot)},300);
// AURA_V123_VISIBLE_WEB_PRODUCTIVITY_REBIND
// AURA_V123_NATIVE_TASKS_GOOGLE_SECTION
// AURA_V123_NATIVE_CALENDAR_MONTH_GRID
// AURA_V123_NATIVE_REFRESH_ALL
})();
;(() => {
  'use strict';
  if (window.__AURA_V123_CONVERSATION_RESULTS_RECOVERY__) return;
  window.__AURA_V123_CONVERSATION_RESULTS_RECOVERY__ = {
    version: '1.2.3-d3-r5-r5',
    lastKind: null,
    lastAt: 0
  };

  const RECOVERY_ID = 'aura-v123-personal-results-recovery';

  const esc = value => String(value == null ? '' : value)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
    .replace(/"/g,'&quot;').replace(/'/g,'&#39;');

  const txt = value => String(value == null ? '' : value).trim();

  function kindOf(payload){
    const k=txt(payload && payload.kind).toLowerCase();
    if(k==='task'||k==='todo'||k==='todos')return 'tasks';
    if(k==='agenda'||k==='events'||k==='event')return 'calendar';
    if(k==='contact'||k==='people')return 'contacts';
    if(k==='files'||k==='file'||k==='google_drive')return 'drive';
    return k || 'results';
  }

  function itemsOf(payload){
    if(!payload || typeof payload!=='object')return [];
    for(const key of ['items','tasks','events','contacts','files','results']){
      if(Array.isArray(payload[key]))return payload[key];
    }
    return [];
  }

  function titleOf(item){
    return txt(item && (
      item.title || item.summary || item.name || item.display_name ||
      item.filename || item.file_name || item.subject || item.content
    )) || 'Sans titre';
  }

  function sourceOf(item){
    const raw=txt(item && (item.source || item.origin || item.provider || item.provider_id)).toUpperCase();
    if(raw.includes('GOOGLE'))return 'GOOGLE';
    if(raw.includes('AURA') || raw.includes('LOCAL'))return 'AURA';
    return raw || 'AURA';
  }

  function detailOf(kind,item){
    if(!item || typeof item!=='object')return '';
    if(kind==='tasks'){
      return [
        item.due || item.due_at || item.date,
        item.status || item.state,
        item.notes
      ].map(txt).filter(Boolean).join(' · ');
    }
    if(kind==='calendar'){
      return [
        item.start_time || item.start || item.date_time || item.date,
        item.end_time || item.end,
        item.location
      ].map(txt).filter(Boolean).join(' · ');
    }
    if(kind==='contacts'){
      const emails=Array.isArray(item.emails)?item.emails.join(', '):(item.email || item.email_address);
      const phones=Array.isArray(item.phones)?item.phones.join(', '):(item.phone || item.phone_number);
      return [emails,phones,item.organization || item.company].map(txt).filter(Boolean).join(' · ');
    }
    if(kind==='drive'){
      return [
        item.mime_type || item.type,
        item.modified_time || item.modified_at,
        item.size
      ].map(txt).filter(Boolean).join(' · ');
    }
    return txt(item.description || item.subtitle || item.status || '');
  }

  function labelFor(kind){
    return ({
      tasks:'TÂCHES',
      calendar:'AGENDA',
      contacts:'CONTACTS',
      drive:'DRIVE'
    })[kind] || 'RÉSULTATS';
  }

  function existingRendererVisible(){
    const p=document.getElementById('aura-v123-personal-results');
    if(!p || p.hidden)return false;
    const r=p.getBoundingClientRect();
    return r.width>20 && r.height>20;
  }

  function cleanupRecoveryLayout(){
    document.body.classList.remove('aura-v123-personal-results-recovery-open');
    if(!existingRendererVisible()){
      document.body.classList.remove('aura-v123-personal-results-open');
      document.body.style.removeProperty('--aura-v123-conversation-right-reserve');
    }
  }

  function positionPanel(panel){
    if(!panel)return;
    const sys=
      document.querySelector('.telemetry') ||
      document.querySelector('#systemLive') ||
      document.querySelector('[data-system-live]') ||
      document.querySelector('.aura-p0851-system-hud');
    let right=16;
    if(sys){
      const sr=sys.getBoundingClientRect();
      if(sr.width>40)right=Math.max(16,Math.round(window.innerWidth-sr.left+14));
    }
    const width=Math.max(340,Math.min(470,Math.round(window.innerWidth*0.30)));
    panel.style.right=right+'px';
    panel.style.width=width+'px';
    document.body.style.setProperty('--aura-v123-conversation-right-reserve',(width+28)+'px');
  }

  function ensurePanel(){
    let panel=document.getElementById(RECOVERY_ID);
    if(panel)return panel;
    panel=document.createElement('section');
    panel.id=RECOVERY_ID;
    panel.className='aura-v123-pr-recovery';
    panel.setAttribute('role','dialog');
    panel.setAttribute('aria-label','Résultats AURA');
    panel.innerHTML=`
      <header class="aura-v123-prr-head">
        <div>
          <small>AURA PERSONAL RESULTS</small>
          <strong data-prr-title>RÉSULTATS</strong>
        </div>
        <button type="button" data-prr-close aria-label="Fermer">×</button>
      </header>
      <div class="aura-v123-prr-meta" data-prr-meta></div>
      <div class="aura-v123-prr-body" data-prr-body></div>`;
    document.body.appendChild(panel);
    panel.querySelector('[data-prr-close]').addEventListener('click',()=>{
      panel.hidden=true;
      cleanupRecoveryLayout();
      try{window.dispatchEvent(new Event('resize'));}catch{}
    });
    return panel;
  }

  function fallbackRender(payload){
    const kind=kindOf(payload);
    const items=itemsOf(payload);
    const panel=ensurePanel();
    const title=panel.querySelector('[data-prr-title]');
    const meta=panel.querySelector('[data-prr-meta]');
    const body=panel.querySelector('[data-prr-body]');
    const psrc=String(payload&&payload.source||'').trim().toUpperCase();
    const psources=Array.isArray(payload&&payload.sources)?payload.sources.map(x=>String(x||'').trim().toUpperCase()):[];
    const provider=String(payload&&payload.provider_id||'').trim().toLowerCase();
    const capability=String(payload&&payload.capability_id||'').trim().toLowerCase();
    const status=String(payload&&payload.status||'').trim().toLowerCase();
    const receiptId=String(payload&&payload.receipt_id||'').trim();
    const fallbackText=String(payload&&payload.fallback_text||'').trim();
    const srcs=items.map(sourceOf).map(x=>String(x||'').trim().toUpperCase());
    const isWindows=(srcs.length&&srcs.every(x=>x==='WINDOWS'))||psrc==='WINDOWS'||psources.includes('WINDOWS')||provider==='pc-control.windows'||capability.startsWith('pc.');
    const isObsidian=psrc==='OBSIDIAN'||psources.includes('OBSIDIAN')||provider==='obsidian.creative'||capability.startsWith('obsidian.');
    const isYouTube=psrc==='YOUTUBE'||psources.includes('YOUTUBE')||provider==='youtube.studio-copilot'||capability.startsWith('youtube.');
    const isFailed=isWindows&&(status==='failed'||status==='error');
    const panelTitle=String(payload&&payload.title||'').trim();
    if(title)title.textContent=((isWindows||isObsidian||isYouTube)&&panelTitle)?panelTitle:labelFor(kind);
    if(meta){const label=isWindows?'WINDOWS':(isObsidian?'OBSIDIAN':(isYouTube?'YOUTUBE':'AURA + GOOGLE'));meta.textContent=`${items.length} \u00e9l\u00e9ment${items.length===1?'':'s'} \u00b7 ${label}`;}/* AURA_W132_R7_PC_FAILURE_META_TRUTH */

    const rows=items.map(item=>{
      const source=sourceOf(item);
      const detail=detailOf(kind,item);
      return `<article class="aura-v123-prr-row">
        <span class="aura-v123-prr-source ${source==='GOOGLE'?'google':'aura'}">${esc(source)}</span>
        <div class="aura-v123-prr-main">
          <b>${esc(titleOf(item))}</b>
          ${detail?`<small>${esc(detail)}</small>`:''}
        </div>
      </article>`;
    }).join('');

    const failureRow=isFailed?`<article class="aura-v123-prr-row aura-v123-prr-failed">
      <span class="aura-v123-prr-source aura">WINDOWS</span>
      <div class="aura-v123-prr-main">
        <b>${esc(fallbackText||'Action Windows \u00e9chou\u00e9e.')}</b>
        <small>${esc(receiptId?`\u00c9CHEC \u00b7 Receipt ${receiptId}`:'\u00c9CHEC')}</small>
      </div>
    </article>`:'';

    if(body)body.innerHTML=rows || failureRow || '<div class="aura-v123-prr-empty">Aucun \u00e9l\u00e9ment \u00e0 afficher.</div>';/* AURA_W132_R7_PC_FAILURE_BODY_TRUTH */
    panel.hidden=false;
    positionPanel(panel);
    document.body.classList.add('aura-v123-personal-results-open');
    document.body.classList.add('aura-v123-personal-results-recovery-open');
    try{window.dispatchEvent(new Event('resize'));}catch{}
  }

  function renderConversationResult(payload){
    const state=window.__AURA_V123_VISIBLE_PRODUCTIVITY_REBIND__;
    // Native Tasks/Agenda refresh keeps returnTarget until the normal AURA text
    // response arrives. Do not open a Conversation result panel for that refresh.
    if(state && state.returnTarget)return;

    const workspace=txt(document.body && document.body.dataset && document.body.dataset.auraWorkspace).toLowerCase();
    const conversationActive=
      workspace==='talk' ||
      !!document.querySelector('#conversation:not([hidden])') ||
      !!document.querySelector('[data-rail-target="conversation"].active');
    if(!conversationActive)return;

    let apiCalled=false;
    try{
      const api=window.__AURA_V123_PERSONAL_RESULTS_WEB__;
      if(api && typeof api.render==='function'){
        api.render(payload);
        apiCalled=true;
      }
    }catch(err){
      console.warn('[AURA] Personal Results renderer failed; recovery panel used.',err);
    }

    setTimeout(()=>{
      if(existingRendererVisible()){
        const recovery=document.getElementById(RECOVERY_ID);
        if(recovery)recovery.hidden=true;
        document.body.classList.remove('aura-v123-personal-results-recovery-open');
        return;
      }
      fallbackRender(payload);
    }, apiCalled ? 60 : 0);
  }

  window.addEventListener('aura:hub-event',event=>{
    const msg=event && event.detail || {};
    if(txt(msg.type)!=='personal_result')return;
    const payload=msg.data || {};
    window.__AURA_V123_CONVERSATION_RESULTS_RECOVERY__.lastKind=kindOf(payload);
    window.__AURA_V123_CONVERSATION_RESULTS_RECOVERY__.lastAt=Date.now();
    renderConversationResult(payload);
  });

  window.addEventListener('resize',()=>{
    const p=document.getElementById(RECOVERY_ID);
    if(p && !p.hidden)positionPanel(p);
  },{passive:true});

  window.addEventListener('aura:workspace-changed',()=>{
    setTimeout(()=>{
      const p=document.getElementById(RECOVERY_ID);
      const workspace=txt(document.body && document.body.dataset && document.body.dataset.auraWorkspace).toLowerCase();
      if(p && !p.hidden && workspace!=='talk'){
        p.hidden=true;
        cleanupRecoveryLayout();
      }
    },30);
  });

  // AURA_V123_CONVERSATION_PERSONAL_RESULTS_DIRECT_RECOVERY
})();
;(()=>{
'use strict';
if(window.__AURA_W131_3D4_R5B_ACTIVE__)return;
window.__AURA_W131_3D4_R5B_ACTIVE__=true;

const ROOT_ID='aura-v123-personal-results';
const DELAYS=[0,10,25,50,100,200,350,500,750,1000,1500,2000,3000];

function reconcileWindowsHeader(){
  const panel=document.getElementById(ROOT_ID);
  if(!panel)return false;

  const meta=panel.querySelector('.aura-v123-pr-count');
  const badges=[...panel.querySelectorAll('.aura-v123-prr-source')];
  if(!meta||!badges.length)return false;

  const sources=badges
    .map(x=>String(x.textContent||'').trim().toUpperCase())
    .filter(Boolean);

  if(sources.length!==badges.length)return false;
  if(!sources.every(x=>x==='WINDOWS'))return false;

  const n=badges.length;
  const desired=`${n} \u00e9l\u00e9ment${n===1?'':'s'} \u00b7 WINDOWS`;

  if(meta.textContent!==desired)meta.textContent=desired;
  return true;
}

function settleWindowsHeader(){
  DELAYS.forEach(ms=>setTimeout(reconcileWindowsHeader,ms));
}

window.addEventListener('aura:hub-event',e=>{
  const d=e&&e.detail||{};
  if(String(d.type||'')==='personal_result')settleWindowsHeader();
});

window.addEventListener('load',()=>setTimeout(settleWindowsHeader,0));
setTimeout(settleWindowsHeader,0);

/* AURA_W131_3D4_R5B_INSTALL_MARK */
})();
;(()=>{
'use strict';
if(window.__AURA_W131_3D4_R10B_SCOPED_WINDOWS_HEADER_AUTHORITY__)return;
window.__AURA_W131_3D4_R10B_SCOPED_WINDOWS_HEADER_AUTHORITY__=true;

const R10B_ROOT_ID='aura-v123-personal-results';
let r10bObservedPanel=null;
let r10bObserver=null;
let r10bScheduled=false;

function r10bReconcile(){
  r10bScheduled=false;
  const panel=document.getElementById(R10B_ROOT_ID);
  if(!panel)return false;

  const meta=panel.querySelector('.aura-v123-pr-count');
  const badges=[...panel.querySelectorAll('.aura-v123-prr-source')];
  if(!meta||!badges.length)return false;

  const sources=badges.map(el=>String(el.textContent||'').trim().toUpperCase()).filter(Boolean);
  if(sources.length!==badges.length)return false;
  if(!sources.every(src=>src==='WINDOWS'))return false;

  const n=badges.length;
  const wanted=`${n} \u00e9l\u00e9ment${n===1?'':'s'} \u00b7 WINDOWS`;
  if(String(meta.textContent||'')!==wanted)meta.textContent=wanted;
  return true;
}

function r10bSchedule(){
  if(r10bScheduled)return;
  r10bScheduled=true;
  setTimeout(r10bReconcile,0);
}

function r10bArm(){
  const panel=document.getElementById(R10B_ROOT_ID);
  if(!panel){
    r10bSchedule();
    return false;
  }

  if(r10bObservedPanel!==panel){
    if(r10bObserver)r10bObserver.disconnect();
    r10bObserver=new MutationObserver(()=>r10bSchedule());
    r10bObserver.observe(panel,{subtree:true,childList:true,characterData:true});
    r10bObservedPanel=panel;
  }

  r10bSchedule();
  return true;
}

window.addEventListener('aura:hub-event',e=>{
  const d=e&&e.detail||{};
  if(String(d.type||'')==='personal_result'){
    setTimeout(r10bArm,0);
    setTimeout(r10bArm,25);
    setTimeout(r10bArm,100);
    setTimeout(r10bArm,300);
  }
});

window.addEventListener('load',()=>setTimeout(r10bArm,0));
setTimeout(r10bArm,0);

/* AURA_W131_3D4_R10B_SCOPED_WINDOWS_HEADER_AUTHORITY */
})();

/* AURA_O140_R2_OBSIDIAN_RECOVERY_LABEL */

/* AURA_Y150_R2_YOUTUBE_RECOVERY_LABEL */


/* ==== AURA_Y150_R4_TRUE_ANALYTICS_PANEL ==== */
(function(){
  const MARKER = "__AURA_Y150_ANALYTICS_JSON__:";
  if (window.__AURA_Y150_R4_TRUE_ANALYTICS_PANEL__) return;
  window.__AURA_Y150_R4_TRUE_ANALYTICS_PANEL__ = true;

  function txt(el){ return String((el && el.textContent) || ""); }
  function moneyLike(n){
    try { return String(Number(n || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
    catch(_){ return String(n || "0"); }
  }
  function scoreLike(n){
    const v = Number(n || 0);
    if (!isFinite(v)) return "0";
    return (Math.round(v * 10) / 10).toFixed(1);
  }
  function locatePanel(){
    const all = Array.from(document.querySelectorAll("*"));
    return all.find(el => /BILAN YOUTUBE/i.test(txt(el)) && /YOUTUBE/i.test(txt(el)));
  }
  function findMarkerNode(panel){
    const marker = "__AURA_Y150_ANALYTICS_JSON__";
    const all = [panel].concat(Array.from(panel.querySelectorAll("*")));
    const hits = all.filter(el => txt(el).indexOf(marker) >= 0);
    hits.sort((a,b) => {
      const ac = a.children ? a.children.length : 0;
      const bc = b.children ? b.children.length : 0;
      if (ac !== bc) return ac - bc;
      return txt(a).length - txt(b).length;
    });
    return hits[0] || null;
  }

  function extractPayload(panel){
    const marker = "__AURA_Y150_ANALYTICS_JSON__";
    const node = findMarkerNode(panel);
    if (!node) return null;

    const raw = txt(node);
    const idx = raw.indexOf(marker);
    if (idx < 0) return null;

    let tail = raw.slice(idx + marker.length);
    tail = tail.replace(/^[^A-Za-z0-9+/=]+/, "");

    function decode(candidate){
      if (!candidate) return null;
      try {
        const binary = atob(candidate);
        const bytes = Uint8Array.from(binary, ch => ch.charCodeAt(0));
        const json = new TextDecoder("utf-8", {fatal:false}).decode(bytes);
        const parsed = JSON.parse(json);
        return parsed && parsed.panel_kind === "youtube_analytics_dashboard"
          ? parsed
          : null;
      } catch(_){ return null; }
    }

    const direct = tail.replace(/\s+/g, "").match(/^([A-Za-z0-9+/=]+)/);
    let parsed = decode(direct && direct[1]);
    if (parsed) return parsed;

    return decode(tail.replace(/[^A-Za-z0-9+/=]/g, ""));
  }

  function nearestScrollable(panel){
    const markerNode = findMarkerNode(panel);
    let cur = markerNode || panel;

    for (let depth = 0; cur && depth < 8; depth += 1, cur = cur.parentElement){
      const t = txt(cur);
      if (
        /ABONNES/i.test(t)
        && /VUES TOTALES/i.test(t)
        && /VIDEOS/i.test(t)
        && /CROISSANCE 29 JOURS/i.test(t)
      ) {
        return cur;
      }
    }

    const candidates = [panel].concat(Array.from(panel.querySelectorAll("div,section,article")));
    let best = panel;
    let score = -1;
    for (const el of candidates){
      const childCount = el.children ? el.children.length : 0;
      const t = txt(el);
      const s = childCount + (/YOUTUBE/i.test(t)?3:0) + (/ABONNES/i.test(t)?2:0);
      if (s > score){ score = s; best = el; }
    }
    return best;
  }
  function card(label, value, sub){
    return `
      <div class="aura-y150-kpi-card">
        <div class="aura-y150-kpi-label">${label}</div>
        <div class="aura-y150-kpi-value">${value}</div>
        <div class="aura-y150-kpi-sub">${sub || "&nbsp;"}</div>
      </div>`;
  }
  function actionPill(action){
    const safe = String(action || "monitor");
    const labels = {
      double_down:"A POUSSER",
      hook_retention:"RETENTION",
      distribution:"DISTRIBUTION",
      packaging:"PACKAGING",
      monitor:"SURVEILLER",
      watch:"SURVEILLER"
    };
    const label = labels[safe] || safe.toUpperCase();
    return `<span class="aura-y150-pill aura-y150-pill-${safe.toLowerCase().replace(/[^a-z0-9]+/g,"-")}">${label}</span>`;
  }
  function renderDashboard(host, data){
    if (!host || !data) return;
    const k = data.kpis || {};
    const top = Array.isArray(data.top_videos) ? data.top_videos : [];
    const opp = Array.isArray(data.opportunities) ? data.opportunities : [];
    const notes = Array.isArray(data.notes) ? data.notes : [];

    host.innerHTML = `
      <div class="aura-y150-dashboard" data-y150-dashboard="1">
        <div class="aura-y150-head">
          <div class="aura-y150-eyebrow">YOUTUBE ANALYTICS</div>
          <div class="aura-y150-title">BILAN YOUTUBE</div>
          <div class="aura-y150-sub">${data.channel_title || "Neural Echo Music"} - snapshot ${data.captured_at || ""}</div>
        </div>

        <div class="aura-y150-kpi-grid">
          ${card("ABONNES", moneyLike(k.subscribers), "+" + moneyLike(k.subs_growth || 0) + " / 29 j")}
          ${card("VUES TOTALES", moneyLike(k.views), "+" + moneyLike(k.views_growth || 0) + " / 29 j")}
          ${card("VIDEOS", moneyLike(k.videos), "+" + moneyLike(k.uploads_growth || 0) + " publications")}
          ${card("RETENTION MEDIANE", scoreLike(k.median_retention) + "%", moneyLike(k.snapshot_rows) + " videos analysees")}
        </div>

        <div class="aura-y150-section">
          <div class="aura-y150-section-title">OPPORTUNITES PRIORITAIRES</div>
          <div class="aura-y150-opps">
            ${(opp.length ? opp : []).map(row => `
              <div class="aura-y150-opp-card">
                <div class="aura-y150-opp-title">${row.title || ""}</div>
                <div class="aura-y150-opp-meta">
                  ${actionPill(row.action)}
                  <span>score ${scoreLike(row.score)}</span>
                  <span>${scoreLike(row.views_per_day)} vues/j</span>
                  <span>ret. ${scoreLike(row.retention)}%</span>
                </div>
              </div>
            `).join("")}
          </div>
        </div>

        <div class="aura-y150-section">
          <div class="aura-y150-section-title">TOP VIDEOS</div>
          <div class="aura-y150-table">
            <div class="aura-y150-row aura-y150-row-head">
              <div>TITRE</div><div>VUES</div><div>V/J</div><div>RET.</div><div>SCORE</div><div>ACTION</div>
            </div>
            ${top.map(row => `
              <div class="aura-y150-row">
                <div class="aura-y150-cell-title">${row.title || ""}</div>
                <div>${moneyLike(row.views)}</div>
                <div>${scoreLike(row.views_per_day)}</div>
                <div>${scoreLike(row.retention)}%</div>
                <div>${scoreLike(row.score)}</div>
                <div>${actionPill(row.action)}</div>
              </div>
            `).join("")}
          </div>
        </div>

        <div class="aura-y150-section">
          <div class="aura-y150-section-title">NOTES ANALYTIQUES</div>
          <ul class="aura-y150-notes">
            ${notes.map(n => `<li>${n}</li>`).join("")}
          </ul>
        </div>
      </div>`;
    host.setAttribute("data-y150-rendered", "1");
  }

  function process(){
    const panel = locatePanel();
    if (!panel) return;
    if (panel.querySelector("[data-y150-dashboard='1']")) return;
    const payload = extractPayload(panel);
    if (!payload) return;
    renderDashboard(nearestScrollable(panel), payload);
  }

  let ticks = 0;
  const obs = new MutationObserver(() => {
    process();
    ticks += 1;
    if (ticks > 120) {
      try { obs.disconnect(); } catch(_){}
    }
  });
  try { obs.observe(document.documentElement || document.body, { childList:true, subtree:true, characterData:true }); } catch(_){}
  setTimeout(process, 50);
  setTimeout(process, 250);
  setTimeout(process, 1000);

  // R4-R2: AURA can finish booting before the user asks for YouTube analytics.
  // Keep a bounded local poll alive for 10 minutes, then stop automatically.
  let auraY150R4R2Tries = 0;
  const auraY150R4R2Timer = setInterval(() => {
    process();
    auraY150R4R2Tries += 1;
    if (
      document.querySelector("[data-y150-dashboard='1']")
      || auraY150R4R2Tries >= 1200
    ) {
      clearInterval(auraY150R4R2Timer);
    }
  }, 500);
})();
/* ==== /AURA_Y150_R4_TRUE_ANALYTICS_PANEL ==== */

/* AURA_Y150_R4_R2_LATE_RESULT_POLL */

/* AURA_Y150_R4_R3_DOM_DECODER_FIX */

/* AURA_Y150_R4_R4_DATA_TRUTH */

/* AURA_Y150_R5_UTF8_BASE64_DECODE */
