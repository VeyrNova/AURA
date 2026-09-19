/* AURA P0.7.4 — VITALS / ACTIVITY MODULE
   Local-first real-time health/activity workspace with strict data isolation.
   No health value is invented. External data is read only from AURA's loopback
   bridge or from a user-selected JSON snapshot kept in the browser session.
*/
(()=>{
  'use strict';
  if(window.__AURA_P074_VITALS__)return;
  window.__AURA_P074_VITALS__=true;

  const VERSION='P0.7.4';
  const token=new URLSearchParams(location.search).get('token')||'';
  const STATE={open:false,root:null,data:null,bridge:null,session:null,share:false,poll:0,fetching:false,lastError:'',range:'24H',registered:false,moduleButton:false};
  const safe=(v,n=180)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const finite=v=>Number.isFinite(Number(v));
  const fmt=(v,d=0)=>finite(v)?Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d}):'—';
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const pct=(v,g)=>finite(v)&&finite(g)&&Number(g)>0?Math.max(0,Math.min(1,Number(v)/Number(g))):0;
  const currentWorkspace=()=>safe(window.AuraWorkspace?.current?.()||document.body.dataset.auraWorkspace||'home',32).toLowerCase();

  function value(v,lo,hi){/* AURA_H185_R7_R1_R1_NULL_SAFE_VALUE */if(v===null||v===undefined||v==='')return null;const n=Number(v);return Number.isFinite(n)&&n>=lo&&n<=hi?n:null}
  function activity(raw){
    raw=raw&&typeof raw==='object'?raw:{};
    return {
      move_kcal:value(raw.move_kcal,0,20000),move_goal_kcal:value(raw.move_goal_kcal,1,20000),
      exercise_min:value(raw.exercise_min,0,1440),exercise_goal_min:value(raw.exercise_goal_min,1,1440),
      stand_hours:value(raw.stand_hours,0,24),stand_goal_hours:value(raw.stand_goal_hours,1,24),
      steps:value(raw.steps,0,200000),distance_km:value(raw.distance_km,0,500),active_energy_kcal:value(raw.active_energy_kcal,0,20000)
    };
  }
  function sanitize(raw){
    raw=raw&&typeof raw==='object'?raw:{};
    const series=Array.isArray(raw.heart_rate_series)?raw.heart_rate_series.slice(-1440).map(p=>({time:safe(p?.time,40),bpm:value(p?.bpm,20,260)})).filter(p=>p.time&&p.bpm!==null):[];
    const workouts=Array.isArray(raw.workouts)?raw.workouts.slice(0,20).map(w=>({name:safe(w?.name||w?.type,80),start:safe(w?.start,40),duration_min:value(w?.duration_min,0,1440),distance_km:value(w?.distance_km,0,500),energy_kcal:value(w?.energy_kcal,0,20000),avg_heart_rate_bpm:value(w?.avg_heart_rate_bpm,20,260)})).filter(w=>w.name):[];
    return {
      source:safe(raw.source,80),device:safe(raw.device,100),updated_at:safe(raw.updated_at,60),
      heart_rate_bpm:value(raw.heart_rate_bpm,20,260),resting_heart_rate_bpm:value(raw.resting_heart_rate_bpm,20,200),
      hrv_ms:value(raw.hrv_ms,0,500),spo2_percent:value(raw.spo2_percent,50,100),temperature_c:value(raw.temperature_c,25,45),
      respiratory_rate_bpm:value(raw.respiratory_rate_bpm,4,60),sleep_duration_hours:value(raw.sleep_duration_hours,0,24),
      activity:activity(raw.activity),heart_rate_series:series,workouts
    };
  }
  function hasMeasurements(d){return !!d&&[d.heart_rate_bpm,d.hrv_ms,d.spo2_percent,d.temperature_c,d.respiratory_rate_bpm,d.activity?.steps,d.sleep_duration_hours].some(v=>v!==null&&v!==undefined)}
  function activeData(){return STATE.session||STATE.data||null}

  function ensureModuleButton(){
    const grid=q('.aura-p0702-module-grid');if(!grid)return false;
    let b=q('[data-module="vitals"]',grid);
    if(!b){
      b=document.createElement('button');b.type='button';b.dataset.module='vitals';b.className='aura-p074-vitals-module-entry';
      b.innerHTML='<span><svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-8-4.7-8-11a4.5 4.5 0 0 1 8-3.2A4.5 4.5 0 0 1 20 10c0 6.3-8 11-8 11Z"/><path d="M5.8 12h3l1.5-3 2.3 6 1.7-3H18"/></svg></span><div><b>SIGNES VITAUX</b><small>Activité · capteurs · données isolées</small></div>';
      grid.appendChild(b);
    }
    STATE.moduleButton=true;return true;
  }

  function createRoot(){
    if(STATE.root?.isConnected)return STATE.root;
    const root=document.createElement('section');root.className='aura-p074-vitals-workspace glass';root.hidden=true;root.setAttribute('aria-label','Signes vitaux et activité temps réel');
    root.innerHTML=`
      <header class="aura-p074-head">
        <div class="aura-p074-title"><span class="aura-p074-heart">♡</span><div><small>AURA · VITALS</small><b>SIGNES VITAUX / ACTIVITÉ TEMPS RÉEL</b><em data-subtitle>Aucune source de capteur connectée</em></div></div>
        <div class="aura-p074-head-meta"><span data-source-state data-state="offline">SOURCE LOCALE · NON CONNECTÉE</span><span class="isolation">DONNÉES ISOLÉES</span></div>
        <div class="aura-p074-head-actions"><button type="button" data-action="share">PARTAGER AVEC CONVERSATION</button><button type="button" data-action="import">IMPORTER SNAPSHOT</button><button type="button" data-action="refresh">ACTUALISER</button><button type="button" data-action="close" aria-label="Fermer">×</button></div>
        <input data-import type="file" accept=".json,application/json" hidden>
      </header>
      <div class="aura-p074-body">
        <div class="aura-p074-metrics">
          <article data-metric="heart"><small>FRÉQUENCE CARDIAQUE</small><strong><span data-v="heart">—</span><i>BPM</i></strong><em data-v="resting">Repos : —</em><svg data-spark="heart" viewBox="0 0 160 34" preserveAspectRatio="none"></svg></article>
          <article data-metric="hrv"><small>VARIABILITÉ (HRV)</small><strong><span data-v="hrv">—</span><i>ms</i></strong><em>Mesure brute du capteur</em></article>
          <article data-metric="spo2"><small>OXYGÈNE SANGUIN</small><strong><span data-v="spo2">—</span><i>% SpO₂</i></strong><em>Aucune interprétation médicale</em></article>
          <article data-metric="temp"><small>TEMPÉRATURE</small><strong><span data-v="temp">—</span><i>°C</i></strong><em>Valeur publiée par la source</em></article>
          <article data-metric="resp"><small>FRÉQUENCE RESPIRATOIRE</small><strong><span data-v="resp">—</span><i>br/min</i></strong><em>Valeur publiée par la source</em></article>
        </div>
        <div class="aura-p074-main-grid">
          <article class="aura-p074-chart-card"><header><div><small>FRÉQUENCE CARDIAQUE</small><b>ÉVOLUTION · <span data-range-label>24H</span></b></div><div class="aura-p074-range"><button data-range="1H">1H</button><button data-range="6H">6H</button><button data-range="12H">12H</button><button data-range="24H" class="active">24H</button></div></header><div class="aura-p074-chart" data-chart><svg viewBox="0 0 900 310" preserveAspectRatio="none"><g data-grid></g><path data-area></path><path data-line></path><g data-points></g></svg><div data-chart-empty>Aucune donnée cardiaque disponible</div></div><footer><span>● Fréquence cardiaque</span><span data-series-count>0 mesure</span></footer></article>
          <article class="aura-p074-activity-card"><header><small>ACTIVITÉ</small><b>AUJOURD’HUI</b></header><div class="aura-p074-rings"><svg viewBox="0 0 150 150"><circle class="ring-bg" cx="75" cy="75" r="56"/><circle data-ring="move" cx="75" cy="75" r="56"/><circle class="ring-bg" cx="75" cy="75" r="42"/><circle data-ring="exercise" cx="75" cy="75" r="42"/><circle class="ring-bg" cx="75" cy="75" r="28"/><circle data-ring="stand" cx="75" cy="75" r="28"/></svg></div><dl><div><dt>BOUGER</dt><dd data-v="move">— / — kcal</dd></div><div><dt>M’ENTRAÎNER</dt><dd data-v="exercise">— / — min</dd></div><div><dt>ME LEVER</dt><dd data-v="stand">— / — h</dd></div></dl><p data-activity-note>Aucune activité publiée.</p></article>
        </div>
        <div class="aura-p074-lower-grid">
          <article><header><small>ACTIVITÉ DU JOUR</small><b>MOUVEMENT</b></header><div class="aura-p074-stat-row"><div><span>Pas</span><b data-v="steps">—</b></div><div><span>Distance</span><b data-v="distance">—</b></div><div><span>Énergie active</span><b data-v="energy">—</b></div></div></article>
          <article><header><small>ENTRAÎNEMENTS</small><b>DERNIERS ÉLÉMENTS</b></header><div class="aura-p074-workouts" data-workouts><p>Aucun entraînement publié.</p></div></article>
          <article><header><small>SOMMEIL</small><b>DURÉE PUBLIÉE</b></header><div class="aura-p074-sleep"><strong data-v="sleep">—</strong><span>heures</span></div><p>Le module n’invente aucun score de sommeil.</p></article>
          <article class="aura-p074-source-card"><header><small>ISOLATION DES DONNÉES</small><b>BRIDGE LOCAL READ-ONLY</b></header><dl><div><dt>Source</dt><dd data-source>—</dd></div><div><dt>Appareil</dt><dd data-device>—</dd></div><div><dt>Dernière mesure</dt><dd data-updated>—</dd></div><div><dt>Bridge</dt><dd data-bridge-path>—</dd></div></dl><p>Les mesures restent locales. Aucun envoi externe n’est effectué par ce module.</p></article>
        </div>
      </div>`;
    document.body.appendChild(root);STATE.root=root;bindRoot(root);return root;
  }

  function sparkPath(series,w=160,h=34){
    if(!series?.length)return'';const vals=series.map(x=>x.bpm).filter(finite);if(!vals.length)return'';const min=Math.min(...vals),max=Math.max(...vals),span=Math.max(8,max-min);return series.map((p,i)=>{const x=series.length===1?w/2:(i/(series.length-1))*w;const y=h-3-((p.bpm-min)/span)*(h-7);return `${i?'L':'M'}${x.toFixed(1)},${y.toFixed(1)}`}).join(' ')
  }
  function chartSeries(d){const all=d?.heart_rate_series||[];const n=STATE.range==='1H'?60:STATE.range==='6H'?360:STATE.range==='12H'?720:1440;return all.slice(-n)}
  function renderChart(d){
    const root=STATE.root,series=chartSeries(d),svg=q('[data-chart] svg',root),line=q('[data-line]',svg),area=q('[data-area]',svg),grid=q('[data-grid]',svg),points=q('[data-points]',svg),empty=q('[data-chart-empty]',root);
    grid.innerHTML='';for(let i=0;i<=6;i++){const y=28+i*39;grid.insertAdjacentHTML('beforeend',`<line x1="35" y1="${y}" x2="885" y2="${y}"/>`)}for(let i=0;i<=8;i++){const x=35+i*106.25;grid.insertAdjacentHTML('beforeend',`<line x1="${x}" y1="28" x2="${x}" y2="262"/>`)}
    if(series.length<2){line.setAttribute('d','');area.setAttribute('d','');points.innerHTML='';empty.hidden=false;q('[data-series-count]',root).textContent=`${series.length} mesure`;return}
    const vals=series.map(p=>p.bpm),min=Math.min(...vals),max=Math.max(...vals),lo=Math.max(20,Math.floor((min-10)/10)*10),hi=Math.min(260,Math.ceil((max+10)/10)*10),span=Math.max(20,hi-lo);
    const pts=series.map((p,i)=>{const x=35+(i/(series.length-1))*850;const y=262-((p.bpm-lo)/span)*234;return{x,y,bpm:p.bpm,time:p.time}});
    const path=pts.map((p,i)=>`${i?'L':'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ');line.setAttribute('d',path);area.setAttribute('d',`${path} L885,262 L35,262 Z`);points.innerHTML='';
    if(pts.length){const peak=pts.reduce((a,b)=>b.bpm>a.bpm?b:a,pts[0]);points.innerHTML=`<circle cx="${peak.x}" cy="${peak.y}" r="5"/><text x="${Math.min(820,peak.x+9)}" y="${Math.max(22,peak.y-10)}">${fmt(peak.bpm)} BPM</text>`}
    empty.hidden=true;q('[data-series-count]',root).textContent=`${series.length} mesures`;
  }
  function setRing(name,ratio){const c=q(`[data-ring="${name}"]`,STATE.root);if(!c)return;const r=Number(c.getAttribute('r')),circ=2*Math.PI*r;c.style.strokeDasharray=`${circ}`;c.style.strokeDashoffset=`${circ*(1-Math.max(0,Math.min(1,ratio)))}`}
  function render(data=activeData()){
    const root=createRoot(),d=data||sanitize({}),a=d.activity||activity({}),bridge=STATE.bridge||{};
    q('[data-v="heart"]',root).textContent=d.heart_rate_bpm===null?'—':fmt(d.heart_rate_bpm);q('[data-v="resting"]',root).textContent=`Repos : ${d.resting_heart_rate_bpm===null?'—':fmt(d.resting_heart_rate_bpm)+' BPM'}`;
    q('[data-v="hrv"]',root).textContent=d.hrv_ms===null?'—':fmt(d.hrv_ms);q('[data-v="spo2"]',root).textContent=d.spo2_percent===null?'—':fmt(d.spo2_percent);q('[data-v="temp"]',root).textContent=d.temperature_c===null?'—':fmt(d.temperature_c,1);q('[data-v="resp"]',root).textContent=d.respiratory_rate_bpm===null?'—':fmt(d.respiratory_rate_bpm,1);
    const spark=q('[data-spark="heart"]',root),sp=sparkPath(chartSeries(d));spark.innerHTML=sp?`<path d="${sp}"/>`:'';
    q('[data-v="move"]',root).textContent=`${a.move_kcal===null?'—':fmt(a.move_kcal)} / ${a.move_goal_kcal===null?'—':fmt(a.move_goal_kcal)} kcal`;q('[data-v="exercise"]',root).textContent=`${a.exercise_min===null?'—':fmt(a.exercise_min)} / ${a.exercise_goal_min===null?'—':fmt(a.exercise_goal_min)} min`;q('[data-v="stand"]',root).textContent=`${a.stand_hours===null?'—':fmt(a.stand_hours)} / ${a.stand_goal_hours===null?'—':fmt(a.stand_goal_hours)} h`;
    setRing('move',pct(a.move_kcal,a.move_goal_kcal));setRing('exercise',pct(a.exercise_min,a.exercise_goal_min));setRing('stand',pct(a.stand_hours,a.stand_goal_hours));
    q('[data-activity-note]',root).textContent=[pct(a.move_kcal,a.move_goal_kcal),pct(a.exercise_min,a.exercise_goal_min),pct(a.stand_hours,a.stand_goal_hours)].some(x=>x>0)?'Progression issue de la source active.':'Aucune activité publiée.';
    q('[data-v="steps"]',root).textContent=a.steps===null?'—':fmt(a.steps);q('[data-v="distance"]',root).textContent=a.distance_km===null?'—':`${fmt(a.distance_km,2)} km`;q('[data-v="energy"]',root).textContent=a.active_energy_kcal===null?'—':`${fmt(a.active_energy_kcal)} kcal`;q('[data-v="sleep"]',root).textContent=d.sleep_duration_hours===null?'—':fmt(d.sleep_duration_hours,1);
    const workouts=q('[data-workouts]',root);workouts.innerHTML=d.workouts?.length?d.workouts.slice(0,4).map(w=>`<div><b>${esc(w.name)}</b><span>${w.duration_min!==null?fmt(w.duration_min)+' min':'durée —'}${w.distance_km!==null?' · '+fmt(w.distance_km,2)+' km':''}${w.avg_heart_rate_bpm!==null?' · '+fmt(w.avg_heart_rate_bpm)+' BPM moy.':''}</span></div>`).join(''):'<p>Aucun entraînement publié.</p>';
    const connected=hasMeasurements(d),source=STATE.session?'Import session':safe(d.source||bridge.source||'',80),device=safe(d.device||bridge.device||'',100),updated=safe(d.updated_at||bridge.updated_at||'',80);
    q('[data-source]',root).textContent=source||'—';q('[data-device]',root).textContent=device||'—';q('[data-updated]',root).textContent=updated||'—';q('[data-bridge-path]',root).textContent=safe(bridge.path||'',180)||'%LOCALAPPDATA%\\AURA\\vitals\\latest.json';
    const status=q('[data-source-state]',root);status.textContent=connected?(STATE.session?'SNAPSHOT SESSION · ACTIF':`${source||'SOURCE LOCALE'} · CONNECTÉE`):'SOURCE LOCALE · NON CONNECTÉE';status.dataset.state=connected?'ready':'offline';q('[data-subtitle]',root).textContent=connected?`${device||source||'Source locale'} · dernière mesure ${updated||'non horodatée'}`:'Aucune source de capteur connectée';
    const share=q('[data-action="share"]',root);share.classList.toggle('active',STATE.share);share.textContent=STATE.share?'PARTAGE CONTEXTE · ACTIF':'PARTAGER AVEC CONVERSATION';
    q('[data-range-label]',root).textContent=STATE.range;qa('[data-range]',root).forEach(b=>b.classList.toggle('active',b.dataset.range===STATE.range));renderChart(d);refreshContext();
  }

  function buildContext(){
    const d=activeData(),bridge=STATE.bridge||{},connected=hasMeasurements(d),facts=[];
    const fact=(key,label,val)=>{const v=safe(val,240);if(v)facts.push({key,label,value:v,source:'vitals-local'})};
    fact('source_status','Source',connected?(safe(d?.source||bridge.source,80)||'Source locale connectée'):'Aucune source connectée');if(d?.device)fact('device','Appareil',d.device);if(d?.updated_at)fact('updated','Dernière mesure',d.updated_at);
    if(STATE.share&&d){
      if(d.heart_rate_bpm!==null)fact('heart_rate','Fréquence cardiaque',`${fmt(d.heart_rate_bpm)} BPM`);if(d.hrv_ms!==null)fact('hrv','HRV',`${fmt(d.hrv_ms)} ms`);if(d.spo2_percent!==null)fact('spo2','SpO₂',`${fmt(d.spo2_percent)} %`);if(d.temperature_c!==null)fact('temperature','Température',`${fmt(d.temperature_c,1)} °C`);if(d.respiratory_rate_bpm!==null)fact('respiratory_rate','Fréquence respiratoire',`${fmt(d.respiratory_rate_bpm,1)} br/min`);if(d.activity?.steps!==null)fact('steps','Pas',fmt(d.activity.steps));if(d.sleep_duration_hours!==null)fact('sleep','Sommeil',`${fmt(d.sleep_duration_hours,1)} h`);
    }
    return {schema:'aura.workspace-context.v2',workspace:'vitals',submode:STATE.share?'shared':'isolated',target:STATE.share?'Signes vitaux · partage explicite':'Signes vitaux · données isolées',summary:STATE.share?'Le partage éphémère des mesures visibles avec Conversation est activé pour cette session.':'Le module Signes vitaux est actif. Les mesures restent isolées tant que le partage Conversation n’est pas activé explicitement.',facts:facts.slice(0,12),refs:[],cleared:false};
  }
  function refreshContext(){window.AuraContextBridge?.refresh?.();window.dispatchEvent(new CustomEvent('aura:vitals-context-changed',{detail:{version:VERSION,share:STATE.share,context:buildContext()}}))}
  function registerContext(){return !!window.AuraContextBridge?.register?.('vitals',async()=>buildContext())}

  async function fetchBridge(){
    if(STATE.fetching||!token)return false;STATE.fetching=true;
    try{const r=await fetch(`/api/vitals?token=${encodeURIComponent(token)}`,{cache:'no-store'});const out=await r.json();STATE.bridge=out||{};STATE.lastError=out?.error||'';if(out?.connected&&out?.data)STATE.data=sanitize(Object.assign({},out.data,{source:out.source||out.data.source,device:out.device||out.data.device,updated_at:out.updated_at||out.data.updated_at}));else STATE.data=null;if(STATE.open)render();return !!out?.connected}catch(e){STATE.lastError=safe(e?.message||e,180);STATE.bridge={connected:false,error:STATE.lastError};if(STATE.open)render();return false}finally{STATE.fetching=false}
  }
  function startPoll(){stopPoll();fetchBridge();STATE.poll=window.AuraWorkloadBudget?.repeat?window.AuraWorkloadBudget.repeat(fetchBridge,'vitals',2200):setInterval(fetchBridge,2200)}function stopPoll(){if(STATE.poll){if(typeof STATE.poll?.stop==='function')STATE.poll.stop();else clearInterval(STATE.poll);STATE.poll=0}}

  function setOpen(on,opts={}){const root=createRoot();STATE.open=!!on;root.hidden=!on;root.classList.toggle('open',!!on);document.body.classList.toggle('aura-vitals-active',!!on);if(on){if(opts?.range)STATE.range=safe(opts.range,8).toUpperCase();startPoll();render();setTimeout(()=>q('[data-action="share"]',root)?.focus({preventScroll:true}),30)}else{stopPoll();STATE.share=false;refreshContext()}return true}
  function open(opts){return setOpen(true,opts||{})}function close(){return setOpen(false)}
  function registerWorkspace(){if(STATE.registered||!window.AuraWorkspace?.register)return STATE.registered;STATE.registered=window.AuraWorkspace.register({id:'vitals',label:'VITALS',available:()=>true,isOpen:()=>STATE.open,open,close,focusTarget:()=>q('.aura-p074-vitals-workspace.open button'),serialize:()=>({range:STATE.range}),restore:s=>open({range:s?.range||'24H'})});return STATE.registered}

  async function importFile(file){if(!file)return false;try{if(file.size>2*1024*1024)throw new Error('snapshot_too_large');const raw=JSON.parse(await file.text());STATE.session=sanitize(raw.data&&typeof raw.data==='object'?Object.assign({},raw.data,{source:raw.source||raw.data.source,device:raw.device||raw.data.device,updated_at:raw.updated_at||raw.data.updated_at}):raw);if(!hasMeasurements(STATE.session))throw new Error('snapshot_without_supported_measurements');STATE.lastError='';render();return true}catch(e){STATE.session=null;STATE.lastError=safe(e?.message||e,160);render();return false}}
  function bindRoot(root){
    root.addEventListener('click',e=>{const b=e.target.closest('[data-action],[data-range]');if(!b)return;if(b.dataset.range){STATE.range=b.dataset.range;render();return}const a=b.dataset.action;if(a==='close'){window.AuraWorkspace?.home?.()||close()}else if(a==='share'){STATE.share=!STATE.share;render()}else if(a==='import'){q('[data-import]',root)?.click()}else if(a==='refresh'){fetchBridge()}});
    q('[data-import]',root)?.addEventListener('change',async e=>{const f=e.target.files?.[0];await importFile(f);e.target.value=''})
  }
  function syncRail(){if(currentWorkspace()!=='vitals')return;qa('.aura-p0702-nav-btn').forEach(b=>b.classList.toggle('active',b.dataset.railTarget==='modules'))}
  function openFromModule(){const pop=q('.aura-p0702-modules-popover');if(pop){pop.classList.remove('open');pop.hidden=true}registerWorkspace();window.AuraWorkspace?.open?.('vitals')||open();setTimeout(syncRail,0)}
  function commandText(){const input=q('#messageInput');return safe(input?.value,120).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/[’'-]/g,' ').replace(/[^a-z0-9 ]+/g,' ').replace(/\s+/g,' ').trim()}
  function consumeCommand(){const v=commandText();if(!['ouvre signes vitaux','ouvre les signes vitaux','ouvre vitals','ouvre activite','ouvre activite temps reel'].includes(v))return false;const input=q('#messageInput');openFromModule();if(input){input.value='';input.dispatchEvent(new Event('input',{bubbles:true}))}return true}

  document.addEventListener('click',e=>{const mod=e.target.closest?.('[data-module="vitals"]');if(mod){e.preventDefault();e.stopImmediatePropagation();openFromModule();return}if(e.target.closest?.('#sendBtn')&&consumeCommand()){e.preventDefault();e.stopImmediatePropagation()}},true);
  document.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&e.target?.matches?.('#messageInput')&&consumeCommand()){e.preventDefault();e.stopImmediatePropagation()}},true);
  window.addEventListener('aura:workspace-changed',e=>{if(safe(e.detail?.workspace,32).toLowerCase()==='vitals')setTimeout(syncRail,0)});
  window.addEventListener('aura:context-bridge-ready',()=>{registerContext();refreshContext()});
  window.addEventListener('aura:context-contract-changed',e=>{if(e.detail?.context?.workspace!=='vitals')return;const drawer=q('.aura-p0712-conversation-drawer');if(drawer){const m=q('[data-context-module]',drawer),c=q('[data-context]',drawer);if(m)m.textContent='SIGNES VITAUX';if(c)c.textContent='CONTEXTE · SIGNES VITAUX'}});
  window.addEventListener('aura:workspace-manager-ready',()=>registerWorkspace());
  const mo=new MutationObserver(()=>{ensureModuleButton();registerWorkspace()});mo.observe(document.documentElement,{subtree:true,childList:true});

  window.AuraVitalsActivity=Object.freeze({version:VERSION,open,close,isOpen:()=>STATE.open,refresh:fetchBridge,ingest:s=>{STATE.session=sanitize(s);render();return hasMeasurements(STATE.session)},clearSession:()=>{STATE.session=null;render()},setContextSharing:on=>{STATE.share=!!on;render();return STATE.share},context:buildContext,state:()=>({open:STATE.open,share:STATE.share,range:STATE.range,connected:hasMeasurements(activeData()),source:safe(activeData()?.source||STATE.bridge?.source,80),error:STATE.lastError})});
  createRoot();ensureModuleButton();registerWorkspace();registerContext();render();
  window.dispatchEvent(new CustomEvent('aura:vitals-ready',{detail:{version:VERSION,privacy:'isolated-by-default',bridge:'loopback-read-only',features:['dynamic-workspace','local-vitals-bridge','session-import','explicit-context-share','conversation-coexistence']}}));
})();
