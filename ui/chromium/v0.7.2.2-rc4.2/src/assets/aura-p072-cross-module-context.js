/* AURA P0.7.2 — CROSS-MODULE CONTEXT CONTRACT
   Explicit, ephemeral context snapshots shared between AURA workspaces and Conversation.
   No file contents, memory contents, permissions or hidden UI state are inferred here.
*/
(()=>{
  'use strict';
  if(window.__AURA_P072_CONTEXT_BRIDGE__)return;
  window.__AURA_P072_CONTEXT_BRIDGE__=true;

  const VERSION='P0.7.2';
  const SCHEMA='aura.workspace-context.v2';
  const token=new URLSearchParams(location.search).get('token')||'';
  const manager=()=>window.AuraWorkspace;
  const providers=new Map();
  let moduleHint='';
  let lastPosted='';
  let currentSnapshot=null;
  let suppressed=null;
  let refreshTimer=0;
  let refreshSeq=0;
  let systemCache={at:0,data:null};

  const labels={home:'ACCUEIL',talk:'CONVERSATION',plan:'TÂCHES',weather:'MÉTÉO',memory:'MÉMOIRE',system:'DIAGNOSTICS',maps:'MAPS'};
  const safe=(v,n=280)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const finite=v=>Number.isFinite(Number(v));
  const km=m=>{const n=Math.max(0,Number(m)||0)/1000;return n<10?`${n.toFixed(1).replace('.',',')} km`:`${Math.round(n)} km`};
  const duration=s=>{const m=Math.max(0,Math.round((Number(s)||0)/60)),h=Math.floor(m/60),r=m%60;return h?`${h} h ${String(r).padStart(2,'0')}`:`${m} min`};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const currentWorkspace=()=>safe(manager()?.current?.()||document.body.dataset.auraWorkspace||'home',32).toLowerCase()||'home';
  function railSubmode(){const b=q('.aura-p0702-nav-btn.active[data-rail-target],.aura-p0702-nav-btn.is-active[data-rail-target]');return safe(b?.dataset?.railTarget||'',32).toLowerCase()}
  function currentSubmode(id){
    if(id==='plan')return railSubmode()==='agenda'?'agenda':'tasks';
    if(id==='talk'&&(moduleHint==='research'||moduleHint==='documents'))return moduleHint;
    return '';
  }
  function fact(key,label,value,source){const v=safe(value,320);return v?{key:safe(key,40),label:safe(label,80),value:v,source:safe(source||'workspace',48)}:null}
  function ref(type,id,label){const l=safe(label,180);return l?{type:safe(type,32),id:safe(id,96),label:l}:null}
  function compact(items,max=12){return items.filter(Boolean).slice(0,max)}
  function base(id){
    const submode=currentSubmode(id);
    return {schema:SCHEMA,workspace:id,submode,target:labels[id]||id.toUpperCase(),summary:'',facts:[],refs:[],cleared:false};
  }
  function fingerprint(snapshot){
    if(!snapshot)return'';
    const copy={schema:snapshot.schema,workspace:snapshot.workspace,submode:snapshot.submode,target:snapshot.target,summary:snapshot.summary,facts:snapshot.facts,refs:snapshot.refs,cleared:!!snapshot.cleared};
    return JSON.stringify(copy);
  }

  providers.set('home',async()=>{const c=base('home');c.target='Accueil AURA';c.summary='Aucun module métier majeur n’est au premier plan.';return c});
  providers.set('talk',async()=>{
    const c=base('talk');
    if(moduleHint==='research'){c.target='Recherche avec sources';c.summary='Le module Recherche a été demandé depuis le rail AURA.';c.facts=compact([fact('mode','Mode','Recherche IA avec sources','rail')]);}
    else if(moduleHint==='documents'){c.target='Document / pièce jointe';c.summary='Le module Documents a été demandé. Le contenu d’un fichier n’est pas ajouté à ce contrat.';c.facts=compact([fact('mode','Mode','Document joint ou à joindre','rail')]);}
    else{c.target='Conversation principale';c.summary='Conversation AURA en plein écran.';}
    return c;
  });
  providers.set('memory',async()=>{const c=base('memory');c.target='Mémoire persistante';c.summary='Workspace Mémoire actif. Aucun contenu de souvenir n’est copié dans le contrat inter-module.';return c});
  providers.set('plan',async()=>{const c=base('plan'),agenda=c.submode==='agenda';c.target=agenda?'Rappels et agenda':'Liste de tâches';c.summary=agenda?'Vue Agenda/Rappels active dans le workspace Productivité.':'Vue Tâches active dans le workspace Productivité.';c.facts=compact([fact('view','Vue active',agenda?'Agenda / rappels':'Tâches','productivity')]);return c});
  providers.set('weather',async()=>{const c=base('weather');c.target='Prévisions et carte météo';c.summary='Workspace Météo actif. Seules les données explicitement publiées par le module peuvent compléter ce contexte.';return c});
  providers.set('maps',async()=>{
    const c=base('maps');const s=window.AURA_NAVIGATION?.state||{};const o=s.origin||{},d=s.destination||{},route=s.routeSummary||{};
    const origin=safe(o.label||o.shortLabel||'Position actuelle',220),destination=safe(d.shortLabel||d.label||d.name||'',260);
    c.target=destination||'Itinéraire Maps actif';
    const dep=safe(q('#auraTripDeparture')?.value||'',80),brief=safe(q('#auraBriefStatus b')?.textContent||'',100),poi=safe(q('#auraBriefPoi b')?.textContent||'',180);
    c.facts=compact([
      fact('origin','Départ',origin,'maps'),fact('destination','Destination',destination,'maps'),
      finite(route.distance)?fact('distance','Distance',km(route.distance),'maps'):null,
      finite(route.duration)?fact('duration','Durée estimée',duration(route.duration),'maps'):null,
      dep?fact('departure_time','Départ prévu',dep.replace('T',' '),'trip-planner'):null,
      brief?fact('travel_brief','Travel Brief',brief,'travel-brief'):null,
      poi&& !/AUCUN/i.test(poi)?fact('selected_poi','POI sélectionné',poi,'poi'):null,
      fact('navigation','Navigation',s.navigationActive?'ACTIVE':'PRÉPARATION','maps')
    ]);
    c.refs=compact([destination?ref('destination','active-destination',destination):null,poi&&!/AUCUN/i.test(poi)?ref('poi','selected-poi',poi):null],8);
    const bits=[];if(destination)bits.push(`destination ${destination}`);if(finite(route.distance))bits.push(km(route.distance));if(finite(route.duration))bits.push(duration(route.duration));
    c.summary=bits.length?`Itinéraire actif : ${bits.join(' · ')}.`:'Maps est actif, sans itinéraire calculé.';
    return c;
  });

  async function systemStatus(){
    const now=Date.now();if(systemCache.data&&now-systemCache.at<2200)return systemCache.data;
    if(!token)return null;
    try{const r=await fetch(`/api/system?token=${encodeURIComponent(token)}`,{cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);systemCache={at:now,data:d};return d}catch(_){return null}
  }
  providers.set('system',async()=>{
    const c=base('system');c.target='System Live / diagnostics';c.summary='Diagnostics et intelligence locale autorisée.';
    const status=await systemStatus(),di=status?.desktop_intelligence||{};const folders=Array.isArray(di.authorized_folders)?di.authorized_folders:[];const file=di.last_file_read||{},project=di.last_project_analysis||{};const provenance=Array.isArray(project.provenance)?project.provenance:[];
    c.facts=compact([
      fact('authorized_projects','Projets autorisés',String(folders.filter(x=>x?.exists).length),'system'),
      project?.ok?fact('project','Projet actif',project.folder_label||'Projet autorisé','project-intelligence'):null,
      project?.ok?fact('project_files','Fichiers projet',`${Number(project.files_extracted||0)}/${Number(project.files_planned||0)} extraits · ${Number(project.files_matched||0)} pertinents`,'project-intelligence'):null,
      file?.ok?fact('file','Dernier fichier lu',file.name||'Fichier autorisé','file-intelligence'):null
    ]);
    c.refs=compact(provenance.slice(0,8).map((p,i)=>ref('authorized-file',safe(p.file_id||`project-source-${i}`,96),p.name||'fichier')),8);
    if(project?.ok)c.target=safe(project.folder_label||'Projet autorisé',240);
    return c;
  });

  async function collect(){
    const id=currentWorkspace(),provider=providers.get(id)||providers.get('home');
    let snap;try{snap=await provider()}catch(_){snap=base(id);snap.target=labels[id]||id;snap.summary='Contexte du module indisponible.'}
    snap.schema=SCHEMA;snap.workspace=id;snap.submode=safe(snap.submode||currentSubmode(id),40);snap.target=safe(snap.target,280);snap.summary=safe(snap.summary,1400);snap.facts=compact((snap.facts||[]).map(x=>x&&fact(x.key,x.label,x.value,x.source)),12);snap.refs=compact((snap.refs||[]).map(x=>x&&ref(x.type,x.id,x.label)),8);snap.cleared=false;
    return snap;
  }

  async function post(snapshot,{clear=false}={}){
    if(!token)return false;
    const workspace=snapshot?.workspace||currentWorkspace();
    const payload={action:'workspace_context',workspace};if(clear)payload.clear_context=true;else payload.context=snapshot;
    try{const r=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});return r.ok}catch(_){return false}
  }

  function contextCard(){return q('.aura-p0712-context-card')}
  function ensureFactsBox(){const card=contextCard();if(!card)return null;let box=q('[data-p072-context-facts]',card);if(!box){box=document.createElement('div');box.className='aura-p072-context-facts';box.dataset.p072ContextFacts='';card.appendChild(box)}return box}
  function render(snapshot){
    currentSnapshot=snapshot;
    const drawer=q('.aura-p0712-conversation-drawer');
    if(drawer){
      const mod=q('[data-context-module]',drawer),target=q('[data-context-target]',drawer),state=q('[data-context-state]',drawer),clear=q('[data-clear-context]',drawer),context=q('[data-context]',drawer);
      if(mod)mod.textContent=labels[snapshot.workspace]||snapshot.workspace.toUpperCase();if(target)target.textContent=snapshot.cleared?'Contexte explicite effacé':snapshot.target||'—';if(state)state.textContent=snapshot.cleared?'EFFACÉ':'ACTIF';if(context)context.textContent=`CONTEXTE · ${snapshot.submode==='research'?'RECHERCHE':snapshot.submode==='documents'?'DOCUMENTS':labels[snapshot.workspace]||snapshot.workspace.toUpperCase()}`;
      if(clear){clear.disabled=false;clear.title='Effacer les métadonnées contextuelles explicites du module actif';clear.textContent=snapshot.cleared?'CONTEXTE EFFACÉ':'EFFACER LE CONTEXTE'}
      const box=ensureFactsBox();if(box){if(snapshot.cleared||!(snapshot.facts||[]).length)box.innerHTML=snapshot.cleared?'<span>Les métadonnées explicites ont été retirées pour ce module.</span>':'<span>Aucune métadonnée supplémentaire publiée.</span>';else box.innerHTML=snapshot.facts.slice(0,5).map(x=>`<div><small>${escapeHtml(x.label)}</small><b>${escapeHtml(x.value)}</b></div>`).join('')+(snapshot.refs?.length?`<em>${snapshot.refs.length} référence${snapshot.refs.length>1?'s':''} liée${snapshot.refs.length>1?'s':''}</em>`:'')}
    }
    let chip=q('[data-p072-full-context]');const head=q('.aura-p0712-full-head');if(head&&!chip){chip=document.createElement('span');chip.dataset.p072FullContext='';chip.className='aura-p072-full-context';head.querySelector('.aura-p0712-full-actions')?.prepend(chip)}if(chip){chip.textContent=snapshot.submode==='research'?'CONTEXTE · RECHERCHE':snapshot.submode==='documents'?'CONTEXTE · DOCUMENTS':'';chip.hidden=!chip.textContent}
    window.dispatchEvent(new CustomEvent('aura:context-contract-changed',{detail:{version:VERSION,context:snapshot}}));
  }
  function escapeHtml(v){return String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]))}

  async function refresh(reason='manual',force=false){
    clearTimeout(refreshTimer);refreshTimer=0;const seq=++refreshSeq;const snap=await collect();if(seq!==refreshSeq)return false;const fp=fingerprint(snap);
    if(suppressed){if(suppressed.workspace!==snap.workspace||suppressed.fingerprint!==fp)suppressed=null;else{const cleared={...snap,cleared:true,facts:[],refs:[],summary:'Contexte explicite effacé par l’utilisateur.'};render(cleared);return true}}
    render(snap);if(!force&&fp===lastPosted)return true;const ok=await post(snap);if(ok)lastPosted=fp;return ok;
  }
  function schedule(reason='event',delay=90){clearTimeout(refreshTimer);refreshTimer=setTimeout(()=>refresh(reason),delay)}
  async function clearContext(){
    const snap=await collect(),fp=fingerprint(snap);suppressed={workspace:snap.workspace,fingerprint:fp};lastPosted='';await post(snap,{clear:true});const cleared={...snap,cleared:true,facts:[],refs:[],summary:'Contexte explicite effacé par l’utilisateur.'};render(cleared);return true
  }

  const contextPrompts={
    maps:{summary:'Résume le trajet actif avec la destination, la durée, la distance et les points de vigilance disponibles.',tasks:'À partir du trajet actif et de notre conversation, extrais les actions utiles à prévoir avant le départ.',research:'Recherche avec sources les informations utiles liées à la destination ou au trajet actif.',note:'Crée une note de préparation à partir du trajet actif et de notre conversation.'},
    memory:{summary:'Résume ce que nous pouvons déduire du contexte Mémoire actif sans inventer de souvenir non fourni.',tasks:'Extrais de notre conversation les actions ou préférences qui méritent éventuellement d’être retenues.',research:'Recherche les références utiles liées au sujet de notre conversation actuelle.',note:'Crée une note synthétique à partir de notre conversation sans ajouter de souvenir automatiquement.'},
    plan:{summary:'Résume les éléments pertinents pour la vue Tâches ou Agenda actuellement active.',tasks:'Extrais les tâches, décisions et échéances de notre conversation sous forme exploitable.',research:'Recherche avec sources les références utiles pour les tâches ou échéances dont nous parlons.',note:'Crée une note de suivi à partir des tâches, décisions et échéances évoquées.'},
    weather:{summary:'Résume le contexte météo actif avec uniquement les données réellement disponibles.',tasks:'Extrais les actions pratiques à prévoir compte tenu du contexte météo dont nous parlons.',research:'Recherche avec sources les informations météo ou de déplacement utiles au contexte actuel.',note:'Crée une note pratique à partir du contexte météo actuel.'},
    system:{summary:'Résume le contexte Diagnostics/System Live actif sans déduire d’accès ou de permission supplémentaire.',tasks:'Extrais les actions de diagnostic ou de maintenance à effectuer à partir de notre conversation.',research:'Recherche avec sources les références techniques utiles au diagnostic actuel.',note:'Crée une note technique à partir du diagnostic et de notre conversation.'}
  };
  function contextualPrompt(key){const s=currentSnapshot||{};return contextPrompts[s.workspace]?.[key]||({summary:'Résume les points clés de cette conversation.',tasks:'Extrais les tâches, décisions et actions à retenir de cette conversation.',research:'Recherche les références utiles liées au contexte actuel.',note:'Crée une note synthétique à partir de cette conversation.'}[key]||'')}
  function fillDrawer(text){const input=q('.aura-p0712-conversation-drawer [data-input]');if(!input||!text)return false;input.value=text;input.dispatchEvent(new Event('input',{bubbles:true}));input.focus();return true}

  document.addEventListener('click',event=>{
    const module=event.target.closest?.('.aura-p0702-module-grid [data-module]');if(module){const id=safe(module.dataset.module,32).toLowerCase();moduleHint=(id==='research'||id==='documents')?id:'';schedule('module-hint',140)}
    const nav=event.target.closest?.('.aura-p0702-nav-btn[data-rail-target]');if(nav&&nav.dataset.railTarget!=='conversation'&&nav.dataset.railTarget!=='modules')moduleHint='';
    const tab=event.target.closest?.('.aura-p0623-drawer [data-tab]');if(tab)schedule('plan-tab',50);
  },true);
  document.addEventListener('input',event=>{if(event.target?.closest?.('#auraNavigationWorkspace,.aura-p0623-drawer,.aura-p0627-system,.aura-weather-workspace'))schedule('module-input',240)},true);
  window.addEventListener('aura:workspace-will-change',event=>{const to=safe(event.detail?.to||'',32).toLowerCase();if(to&&to!==currentWorkspace())suppressed=null});
  window.addEventListener('aura:workspace-changed',event=>{const next=safe(event.detail?.workspace||currentWorkspace(),32).toLowerCase();if(next!=='talk')moduleHint='';suppressed=null;lastPosted='';schedule('workspace',120)});
  window.addEventListener('aura:workspace-activity',()=>schedule('activity',160));
  window.addEventListener('aura:navigation:route-ready',()=>schedule('route',80));

  document.addEventListener('click',event=>{
    const clear=event.target.closest?.('.aura-p0712-conversation-drawer [data-clear-context]');if(clear){event.preventDefault();event.stopImmediatePropagation();clearContext();return}
    const suggestion=event.target.closest?.('.aura-p0712-conversation-drawer [data-suggest]');if(suggestion){const text=contextualPrompt(suggestion.dataset.suggest);if(text){event.preventDefault();event.stopImmediatePropagation();fillDrawer(text)}}
  },true);

  setInterval(()=>{const id=currentWorkspace();if(id!=='home')refresh('poll')},1800);
  const mo=new MutationObserver(()=>schedule('dom',180));mo.observe(document.body,{subtree:true,attributes:true,attributeFilter:['class','data-aura-workspace']});

  window.AuraContextBridge=Object.freeze({version:VERSION,schema:SCHEMA,get:()=>currentSnapshot?JSON.parse(JSON.stringify(currentSnapshot)):null,refresh:()=>refresh('api',true),clear:clearContext,register(id,provider){id=safe(id,32).toLowerCase();if(!id||typeof provider!=='function')return false;providers.set(id,provider);schedule('provider');return true},providers:()=>[...providers.keys()]});
  schedule('boot',180);
  window.dispatchEvent(new CustomEvent('aura:context-bridge-ready',{detail:{version:VERSION,schema:SCHEMA,features:['explicit-contract','ephemeral-core-context','context-clear','module-providers','contextual-suggestions']}}));
})();
