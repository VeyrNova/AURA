/* AURA P0.6.5.3 — Local Document Intelligence
   Read-only observability before changing any routing policy.
*/
(()=>{
  'use strict';

  const topCenter=document.querySelector('.top-center');
  const workspace=document.querySelector('.workspace');
  const routeText=document.querySelector('#routeText');
  const providerState=document.querySelector('#providerState');
  const providerSub=document.querySelector('#providerSub');
  const stateText=document.querySelector('#stateText');
  const messages=document.querySelector('#messages');
  if(!topCenter||!workspace||!routeText)return;

  const pill=document.createElement('button');
  pill.className='aura-p0640-router-pill';
  pill.type='button';
  pill.title='Observatoire du routeur AURA';
  pill.innerHTML='<i></i><b>ROUTER</b><span data-route>OBSERVE</span>';
  topCenter.appendChild(pill);

  const panel=document.createElement('aside');
  panel.className='aura-p0640-router-panel glass';
  panel.innerHTML=`
    <header>
      <div><i></i><b>INTELLIGENT ROUTER</b><span>P0.6.5.4 · PROJECT INTELLIGENCE</span></div>
      <button data-close aria-label="Fermer">×</button>
    </header>
    <section class="aura-p0640-grid">
      <article><small>WORKSPACE</small><b data-workspace>HOME</b><span>Contexte UI actif</span></article>
      <article><small>OBSERVED DELIVERY</small><b data-delivery>LOCAL UI</b><span data-delivery-detail>Signaux UI historiques</span></article>
      <article><small>PROVIDER</small><b data-provider>—</b><span data-model>—</span></article>
      <article><small>STATE</small><b data-state>IDLE</b><span data-state-detail>Runtime</span></article>
    </section>
    <section class="aura-p0640-contract">
      <div><b>ROUTING CONTRACT</b><span>Périmètre explicite</span></div>
      <p>Le Router canonique possède les routes déterministes allowlistées. Documents et LLM conversationnel restent verrouillés en Shadow.</p>
      <div class="aura-p0640-rules">
        <span>LOCAL UI <i>workspace / palette</i></span>
        <span>LOCAL CORE <i>intentions déterministes</i></span>
        <span>TOOL <i>research / documents / météo</i></span>
        <span>LLM <i>Groq / Gemini / local</i></span>
        <span class="aura-p0643-owner-rule">OWNED <i>Intent · Tools RO · Local zero-LLM · Desktop Safe/Folders/Files/LocalDoc/Project/Deny · Fast Selector · AgentPlan RO</i></span>
        <span class="aura-p0643-shadow-rule">SHADOW <i>Documents · LLM · future/unregistered routes</i></span>
      </div>
    </section>
    <section class="aura-p0641-live-contract">
      <div class="title"><b>CORE CONTRACT · LIVE</b><span>OWNED + SHADOW</span></div>
      <div class="body">
        <article><small>DELIVERY</small><b data-contract-delivery>—</b></article>
        <article><small>ROUTE</small><b data-contract-route>—</b></article>
        <article><small>REASON</small><b data-contract-reason>En attente d'une décision…</b></article>
        <article><small>PROVIDER</small><b data-contract-provider>—</b></article>
        <article><small>OWNER</small><b data-contract-owner>—</b></article>
        <article><small>MODE</small><b data-contract-mode>—</b></article>
      </div>
    </section>
    <section class="aura-p0649-guardrails" data-guard-state="unknown">
      <div class="title"><b>CUTOVER GUARDRAILS</b><span data-guard-status>CHECKING</span></div>
      <div class="body">
        <article><small>MASTER</small><b data-guard-master>—</b></article>
        <article><small>ACTIVE GATES</small><b data-guard-gates>—</b></article>
        <article><small>OWNED / SHADOW</small><b data-guard-counts>—</b></article>
        <article><small>VIOLATIONS</small><b data-guard-violations>—</b></article>
        <article class="wide"><small>LOCKED NEXT CUTOVER</small><b data-guard-locked>DOCUMENT · LLM</b></article>
      </div>
    </section>
    <section class="aura-p0642-compare" data-compare-state="pending">
      <div class="title"><b>SHADOW COMPARISON</b><span data-compare-label>PENDING</span></div>
      <div class="body">
        <article><small>OBSERVED</small><b data-compare-observed>—</b></article>
        <article><small>CORE</small><b data-compare-core>—</b></article>
        <article class="wide"><small>ASSESSMENT</small><b data-compare-reason>En attente d'une décision Core…</b></article>
      </div>
      <footer>
        <span>MATCH <b data-stat-match>0</b></span>
        <span>MISMATCH <b data-stat-mismatch>0</b></span>
        <span>PENDING <b data-stat-pending>0</b></span>
        <strong data-stat-rate>—</strong>
      </footer>
    </section>
    <section class="aura-p06481-selector" data-selector-state="idle">
      <div class="title"><b>LAST FAST SELECTOR</b><span data-selector-match>—</span></div>
      <div class="body">
        <article><small>OWNER</small><b data-selector-owner>—</b></article>
        <article><small>MODE</small><b data-selector-mode>—</b></article>
        <article><small>OUTCOME</small><b data-selector-outcome>Jamais observé</b></article>
        <article><small>EVIDENCE</small><b data-selector-evidence>—</b></article>
      </div>
    </section>
    <section class="aura-p0640-history">
      <div class="title"><b>DECISION TRACE</b><span>Session uniquement</span></div>
      <div data-history><div class="empty">En attente d’activité…</div></div>
    </section>
    <footer><span>CTRL + SHIFT + K</span><b>GUARDRAILS ACTIVE</b></footer>`;
  workspace.appendChild(panel);

  const $=(s)=>panel.querySelector(s);
  const historyEl=$('[data-history]');
  const trace=[];
  const token=new URLSearchParams(location.search).get('token')||'';
  let contractTimer=0;
  let contractSeq=-1;
  let runtimeEvidenceSeq=-1;
  let historyContractSeq=-1;
  let historyEvidenceSeq=-1;
  let lastSelectorContract=null;
  let lastSelectorEvidence=null;
  let compareTimer=0;
  let compareRetries=0;
  let latestContract=null;
  let contractSeenAt=0;
  const comparisonStats={match:0,mismatch:0,pending:0};
  const comparisonBySeq=new Map();
  const legacyEvidence=[];
  let open=false;
  let lastSignature='';
  let lastProvider='';
  let lastModel='';

  function now(){
    return new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit',second:'2-digit'});
  }

  function workspaceId(){
    // Navigation predates AuraWorkspace and owns its surface through the
    // aura-navigation-active body class. Reflect that real UI owner here.
    if(document.body.classList.contains('aura-navigation-active'))return 'MAPS';
    return String(
      document.body.dataset.auraWorkspace
      ||window.AuraWorkspace?.current?.()
      ||'home'
    ).toUpperCase();
  }

  function provider(){
    const p=String(providerState?.textContent||'').trim();
    const m=String(providerSub?.textContent||'').trim();
    return {provider:p||'—',model:m||'—'};
  }

  function providerLikeRoute(route){
    const value=String(route||'').trim();
    if(!value)return false;
    // Topbar values such as "GEMINI · GEMINI-3.6-FLASH" are provider state,
    // not proof of the delivery used by the current turn.
    return /^(?:GROQ|GEMINI|LLAMA|LOCAL RUNTIME|LOCAL LLM)(?:\s*[·\-:].*)?$/i.test(value);
  }

  function routeSignal(){
    const route=String(routeText.textContent||'').trim();
    if(providerLikeRoute(route))return null;

    if(/DOCUMENT|PDF|FILE|FICHIER/i.test(route)){
      return {delivery:'DOCUMENT',route:'document',detail:route,strength:'strong',source:'route-label'};
    }
    if(/MAPS?|CARTE|ITINÉRAIRE|ITINERAIRE/i.test(route)){
      return {delivery:'TOOL',route:'maps',detail:route,strength:'strong',source:'route-label'};
    }
    if(/WEATHER|METEO|MÉTÉO/i.test(route)){
      return {delivery:'TOOL',route:'weather',detail:route,strength:'strong',source:'route-label'};
    }
    if(/RESEARCH|SEARCH|WEB/i.test(route)){
      return {delivery:'TOOL',route:'web-search',detail:route,strength:'strong',source:'route-label'};
    }
    if(/LOCAL ACTION|TASK|TÂCHE|REMINDER|RAPPEL|NOTE|MEMORY|MÉMOIRE|SYSTEM|SYSTÈME|INTENT/i.test(route)){
      return {delivery:'LOCAL_CORE',route:'intent-manager',detail:route,strength:'strong',source:'route-label'};
    }
    if(/\bLLM\b/i.test(route)){
      return {delivery:'LLM',route:'llm',detail:route,strength:'strong',source:'route-label'};
    }
    return null;
  }

  function inferRoute(){
    const signal=routeSignal();
    const state=String(stateText?.textContent||'IDLE').trim().toUpperCase();
    const wid=workspaceId();

    if(signal){
      return {
        kind:signal.delivery.replace('_',' '),
        detail:signal.detail,
        confidence:signal.strength,
      };
    }

    if(['PLAN','WEATHER','MEMORY','SYSTEM','MAPS'].includes(wid) && state==='IDLE'){
      return {kind:'LOCAL UI',detail:`${wid} workspace`,confidence:'medium'};
    }

    return {kind:'LOCAL UI',detail:'Aucun signal de route explicite',confidence:'weak'};
  }

  function normalizeObserved(route){
    const kind=String(route?.kind||'').toUpperCase();
    if(kind==='DOCUMENT')return 'DOCUMENT';
    if(kind==='TOOL')return 'TOOL';
    if(kind==='LOCAL CORE')return 'LOCAL_CORE';
    if(kind==='LLM')return 'LLM';
    if(kind==='ROUTER')return 'ROUTER';
    return 'LOCAL_UI';
  }

  function normalizeRouteFamily(value){
    const route=String(value||'').trim().toLowerCase().replace(/_/g,'-');
    if(!route)return '';

    if(route==='web-search'||route.includes('research'))return 'web-search';
    if(route==='knowledge-reference'||route.includes('knowledge'))return 'knowledge-reference';
    if(route==='web-fetch'||route.includes('fetch'))return 'web-fetch';
    if(route==='weather'||route.includes('meteo')||route.includes('météo'))return 'weather';
    if(route==='maps'||route.includes('itinerary')||route.includes('itinéraire')||route.includes('itineraire'))return 'maps';
    if(route.startsWith('document'))return 'document';
    if(route==='intent-manager'||route.includes('intent'))return 'intent-manager';
    if(route==='adaptive-feedback')return 'adaptive-feedback';
    if(route==='self-dialogue')return 'self-dialogue';
    if(route==='social-ambient')return 'social-ambient';
    if(route==='grounding')return 'grounding';
    if(route==='agent-kernel'||route.includes('agent-kernel'))return 'agent-kernel';
    if(route==='system-safe-app'||route.includes('safe-app'))return 'system-safe-app';
    if(route==='system-policy-deny'||route.includes('policy-deny'))return 'system-policy-deny';
    if(route==='system-folder-registry')return 'system-folder-registry';
    if(route==='system-authorized-folder')return 'system-authorized-folder';
    if(route==='system-authorized-file')return 'system-authorized-file';
    if(route==='system-local-document')return 'system-local-document';
    if(route==='system-authorized-project')return 'system-authorized-project';
    if(route==='fast-agent-router')return 'fast-agent-router';
    if(route.includes('llm'))return 'llm';
    return route;
  }

  function rememberEvidence(delivery,route,detail,source='runtime',strength='strong'){
    const normalized=String(delivery||'').toUpperCase();
    if(!['LOCAL_CORE','TOOL','DOCUMENT','ROUTER','LLM'].includes(normalized))return;
    const item={
      delivery:normalized,
      route:normalizeRouteFamily(route),
      detail:String(detail||'').trim()||normalized,
      source:String(source||'runtime'),
      strength:String(strength||'strong'),
      at:Date.now(),
    };
    const previous=legacyEvidence[0];
    if(
      previous
      && previous.delivery===item.delivery
      && previous.route===item.route
      && previous.detail===item.detail
      && previous.source===item.source
      && item.at-previous.at<180
    )return;
    legacyEvidence.unshift(item);
    if(legacyEvidence.length>40)legacyEvidence.length=40;
  }

  function evidenceFromActivity(data){
    const text=`${data?.workspace||''} ${data?.label||''} ${data?.detail||''}`.trim();
    if(!text)return null;

    // "ouvre la carte" is a LOCAL UI command. It must never corroborate the
    // previous TOOL contract just because both involve Maps.
    if(/AURA MAPS OUVERT.*COMMANDE LOCALE/i.test(text)){
      return null;
    }

    if(/DOCUMENT|PDF|FICHIER|CHARGEMENT DU DOCUMENT|ANALYSE.*DOCUMENT/i.test(text)){
      return {delivery:'DOCUMENT',route:'document',detail:text,source:'workspace-activity'};
    }
    if(/MAPS?|CARTE|ITINÉRAIRE|ITINERAIRE/i.test(text)){
      return {delivery:'TOOL',route:'maps',detail:text,source:'workspace-activity'};
    }
    if(/MÉTÉO|METEO|WEATHER/i.test(text)){
      return {delivery:'TOOL',route:'weather',detail:text,source:'workspace-activity'};
    }
    if(
      /SYSTEM|APPLICATION OUVERTE|ACTION LOCALE|OUVERTURE SÉCURISÉE|OUVERTURE SECURISEE/i.test(text)
      && /APPLICATION|CALCULATRICE|BLOC-NOTES|EXPLORATEUR|PAINT|SAFE/i.test(text)
    ){
      return {delivery:'LOCAL_CORE',route:'system-safe-app',detail:text,source:'workspace-activity'};
    }
    if(/RECHERCHE|SEARCH|WEB|SOURCES?|YAHOO|DUCKDUCKGO/i.test(text)){
      return {delivery:'TOOL',route:'web-search',detail:text,source:'workspace-activity'};
    }
    if(
      /(TÂCHE|TACHE|RAPPEL|NOTE|SOUVENIR|MÉMOIRE|MEMOIRE|ACTION LOCALE|PRODUCTIVITÉ|PRODUCTIVITE)/i.test(text)
      && /(CRÉ|CRE|AJOUT|SUPPR|TERMIN|ENREGISTR|MIS À JOUR|MISE À JOUR|SYNCHRONIS)/i.test(text)
    ){
      return {delivery:'LOCAL_CORE',route:'intent-manager',detail:text,source:'workspace-activity'};
    }
    return null;
  }

  function evidenceWindow(){
    if(!latestContract||!contractSeenAt)return [];
    // Route correlation lets us safely keep a wider pre-contract window for
    // UI modules that publish "loading/ready" just before Core exposes its snapshot.
    const minAt=contractSeenAt-8000;
    return legacyEvidence.filter(item=>item.at>=minAt);
  }

  function evidenceCompatibleWithCore(item,core){
    if(!item||!core)return false;
    const coreDelivery=String(core.delivery||'').toUpperCase();
    if(item.delivery!==coreDelivery)return false;

    const coreRoute=normalizeRouteFamily(core.route);
    const evidenceRoute=normalizeRouteFamily(item.route);

    // TOOL and DOCUMENT routes must match their family. A maps event cannot
    // validate web-fetch, and a web-search event cannot validate weather.
    if(coreDelivery==='TOOL'||coreDelivery==='DOCUMENT'){
      return Boolean(coreRoute && evidenceRoute && coreRoute===evidenceRoute);
    }

    // For local/LLM routes, delivery-level corroboration is still acceptable
    // when no precise historical route is available.
    if(coreRoute && evidenceRoute){
      return coreRoute===evidenceRoute;
    }
    return true;
  }

  function strongestEvidenceFor(core){
    const coreDelivery=String(core?.delivery||'').toUpperCase();
    const candidates=evidenceWindow();

    const same=candidates.find(item=>evidenceCompatibleWithCore(item,core));
    if(same)return same;

    // Provider/model is positive evidence only when Core itself says LLM.
    if(coreDelivery==='LLM'){
      const p=provider();
      const state=String(stateText?.textContent||'').toUpperCase();
      if(
        /GROQ|GEMINI|LLAMA/i.test(`${p.provider} ${p.model}`)
        && /THINK|GENERAT|SPEAK|STREAM|BUSY|WORK/i.test(state)
      ){
        return {
          delivery:'LLM',
          route:'llm',
          detail:`${p.provider} · ${p.model}`,
          source:'provider-active',
          strength:'medium',
          at:Date.now(),
        };
      }
    }

    // Only an explicit route-label can contradict the Core. Unrelated
    // workspace activity is ignored instead of turning into a false mismatch.
    const contradiction=candidates.find(item=>
      item.source==='route-label'
      && item.strength==='strong'
      && item.delivery!==coreDelivery
    );
    return contradiction||null;
  }

  function compareReason(evidence,core){
    const coreDelivery=String(core?.delivery||'').toUpperCase();
    if(!coreDelivery)return {
      state:'pending',
      observed:'—',
      reason:'Aucune décision Core disponible pour ce tour.'
    };

    if(!evidence)return {
      state:'pending',
      observed:'UNVERIFIED',
      reason:`Aucun signal UI explicite ne confirme encore ${coreDelivery}.`
    };

    if(evidenceCompatibleWithCore(evidence,core))return {
      state:'match',
      observed:evidence.delivery,
      reason:`Corroboré (${normalizeRouteFamily(core.route)}) par ${evidence.source} : ${evidence.detail}.`
    };

    return {
      state:'mismatch',
      observed:evidence.delivery,
      reason:`Contradiction explicite : ${evidence.delivery} via ${evidence.source}, Core=${coreDelivery}.`
    };
  }

  function addTrace(kind,detail,source='runtime'){
    const signature=`${kind}|${detail}|${source}`;
    if(signature===lastSignature)return;
    lastSignature=signature;
    trace.unshift({time:now(),kind:String(kind),detail:String(detail||''),source:String(source)});
    if(trace.length>14)trace.length=14;
    renderHistory();
  }

  function renderHistory(){
    historyEl.innerHTML=trace.length?trace.map(item=>`
      <article>
        <time>${item.time}</time>
        <b>${escapeHtml(item.kind)}</b>
        <span>${escapeHtml(item.detail)}</span>
        <i>${escapeHtml(item.source)}</i>
      </article>`).join(''):'<div class="empty">En attente d’activité…</div>';
  }

  function escapeHtml(v){
    return String(v??'').replace(/[&<>"']/g,m=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[m]));
  }

  function render(source='runtime'){
    const wid=workspaceId();
    const p=provider();
    const state=String(stateText?.textContent||'IDLE').trim().toUpperCase()||'IDLE';
    const route=inferRoute();

    $('[data-workspace]').textContent=wid;
    $('[data-delivery]').textContent=route.kind;
    $('[data-delivery-detail]').textContent=route.detail||'—';
    $('[data-provider]').textContent=p.provider;
    $('[data-model]').textContent=p.model;
    $('[data-state]').textContent=state;

    pill.querySelector('[data-route]').textContent=route.kind;
    pill.dataset.route=route.kind.toLowerCase().replace(/\s+/g,'-');

    if(p.provider!==lastProvider||p.model!==lastModel){
      lastProvider=p.provider;lastModel=p.model;
      if(p.provider!=='—')addTrace('PROVIDER',`${p.provider} · ${p.model}`,'provider');
    }

    const explicit=routeSignal();
    if(explicit){
      rememberEvidence(
        explicit.delivery,
        explicit.route,
        explicit.detail,
        explicit.source,
        explicit.strength
      );
    }

    addTrace(route.kind,route.detail,source);

    if(
      explicit
      && latestContract
      && open
      && evidenceCompatibleWithCore(explicit,latestContract)
    ){
      scheduleComparison(latestContract,{preserveRetries:true});
    }
  }

  function renderComparison(result,evidence,core){
    const section=panel.querySelector('.aura-p0642-compare');
    if(!section)return;

    section.dataset.compareState=result.state;
    $('[data-compare-label]').textContent=result.state.toUpperCase();
    $('[data-compare-observed]').textContent=result.observed||evidence?.delivery||'—';
    $('[data-compare-core]').textContent=String(core?.delivery||'—').toUpperCase();
    $('[data-compare-reason]').textContent=result.reason;

    $('[data-stat-match]').textContent=String(comparisonStats.match);
    $('[data-stat-mismatch]').textContent=String(comparisonStats.mismatch);
    $('[data-stat-pending]').textContent=String(comparisonStats.pending);

    const decided=comparisonStats.match+comparisonStats.mismatch;
    $('[data-stat-rate]').textContent=decided
      ?`${Math.round((comparisonStats.match/decided)*100)}% MATCH`
      :'—';
  }

  function renderNewContractPending(core){
    renderComparison(
      {
        state:'pending',
        observed:'UNVERIFIED',
        reason:`Nouveau contrat ${normalizeRouteFamily(core?.route)||String(core?.delivery||'').toUpperCase()}; recherche d’une preuve corrélée…`
      },
      null,
      core
    );
  }

  function adjustStats(seq,nextState){
    const key=Number(seq);
    if(!Number.isFinite(key))return;
    const previous=comparisonBySeq.get(key);

    if(previous===nextState)return;
    if(previous && comparisonStats[previous]>0)comparisonStats[previous]-=1;
    comparisonStats[nextState]+=1;
    comparisonBySeq.set(key,nextState);
  }

  function finalizeComparison(){
    clearTimeout(compareTimer);
    compareTimer=0;
    if(!latestContract)return;

    const evidence=strongestEvidenceFor(latestContract);
    const result=compareReason(evidence,latestContract);

    if(
      (result.state==='pending'||result.state==='mismatch')
      && compareRetries<2
    ){
      compareRetries+=1;
      renderComparison(result,evidence,latestContract);
      compareTimer=setTimeout(finalizeComparison,520);
      return;
    }

    const seq=Number(latestContract.seq);
    const previous=comparisonBySeq.get(seq);
    adjustStats(seq,result.state);
    renderComparison(result,evidence,latestContract);

    if(previous!==result.state){
      addTrace(
        result.state==='match'?'MATCH':result.state==='mismatch'?'MISMATCH':'PENDING',
        `${result.observed||'UNVERIFIED'} ↔ ${String(latestContract.delivery||'—').toUpperCase()} · ${result.reason}`,
        'shadow-compare'
      );
    }
  }

  function scheduleComparison(contract,{preserveRetries=false}={}){
    latestContract=contract||null;
    if(!preserveRetries)compareRetries=0;
    clearTimeout(compareTimer);
    compareTimer=setTimeout(finalizeComparison,preserveRetries?120:220);
  }

  function renderGuardrails(readiness){
    const section=panel.querySelector('.aura-p0649-guardrails');
    if(!section)return;

    const info=readiness&&typeof readiness==='object'?readiness:{};
    const runtime=info.runtime&&typeof info.runtime==='object'?info.runtime:{};
    const status=String(info.status||'UNKNOWN').toUpperCase();
    const safe=Boolean(info.safe);
    const master=Boolean(info.master_enabled);
    const active=Number(info.active_scopes||0);
    const total=Number(info.total_scopes||5);
    const violations=Array.isArray(info.violations)?info.violations:[];
    const locked=Array.isArray(info.next_cutover_locked)?info.next_cutover_locked:['DOCUMENT','LLM'];

    section.dataset.guardState=(
      status==='SAFE'?'safe':
      status==='LEGACY_FALLBACK'?'fallback':
      status==='PARTIAL'?'partial':
      status==='GUARDED'?'guarded':
      safe?'safe':'blocked'
    );

    $('[data-guard-status]').textContent=status;
    $('[data-guard-master]').textContent=master?'ON':'OFF · LEGACY';
    $('[data-guard-gates]').textContent=`${active}/${total}`;
    $('[data-guard-counts]').textContent=
      `${Number(runtime.canonical_owned||0)} / ${Number(runtime.legacy_shadow||0)}`;
    $('[data-guard-violations]').textContent=violations.length
      ?String(violations.length)
      :'0';
    $('[data-guard-locked]').textContent=locked.join(' · ')||'—';
  }

  function selectorOutcome(detail){
    const text=String(detail||'');
    const m=text.match(/\bdecision=([a-z_-]+)/i);
    if(m)return m[1].toUpperCase();
    if(/candidate accepted/i.test(text))return 'STARTED';
    return 'OBSERVED';
  }

  function renderSelectorHistory(){
    const section=panel.querySelector('.aura-p06481-selector');
    if(!section)return;

    if(!lastSelectorContract){
      section.dataset.selectorState='idle';
      $('[data-selector-owner]').textContent='—';
      $('[data-selector-mode]').textContent='—';
      $('[data-selector-outcome]').textContent='Jamais observé';
      $('[data-selector-evidence]').textContent='—';
      $('[data-selector-match]').textContent='—';
      return;
    }

    $('[data-selector-owner]').textContent=String(lastSelectorContract.owner||'legacy').toUpperCase();
    $('[data-selector-mode]').textContent=String(lastSelectorContract.mode||'shadow').toUpperCase();

    if(lastSelectorEvidence){
      $('[data-selector-outcome]').textContent=selectorOutcome(lastSelectorEvidence.detail);
      $('[data-selector-evidence]').textContent=String(lastSelectorEvidence.detail||'preuve runtime');
      $('[data-selector-match]').textContent='MATCH';
      section.dataset.selectorState='match';
    }else{
      $('[data-selector-outcome]').textContent='EN COURS';
      $('[data-selector-evidence]').textContent='En attente de la preuve worker…';
      $('[data-selector-match]').textContent='PENDING';
      section.dataset.selectorState='pending';
    }
  }

  function ingestRouterHistory(payload){
    const decisions=Array.isArray(payload?.decisions)?payload.decisions:[];
    const evidenceHistory=Array.isArray(payload?.evidence_history)?payload.evidence_history:[];

    for(const item of decisions){
      const seq=Number(item?.seq);
      if(!Number.isFinite(seq)||seq<=historyContractSeq)continue;
      historyContractSeq=Math.max(historyContractSeq,seq);

      if(normalizeRouteFamily(item?.route)==='fast-agent-router'){
        lastSelectorContract={...item};
        lastSelectorEvidence=null;
        addTrace(
          'SELECTOR',
          `fast-agent-router · ${String(item?.owner||'legacy').toUpperCase()}/${String(item?.mode||'shadow').toUpperCase()} · ${item?.reason||'—'}`,
          'core-contract-history'
        );
      }
    }

    for(const item of evidenceHistory){
      const seq=Number(item?.seq);
      if(!Number.isFinite(seq)||seq<=historyEvidenceSeq)continue;
      historyEvidenceSeq=Math.max(historyEvidenceSeq,seq);

      if(normalizeRouteFamily(item?.route)==='fast-agent-router'){
        lastSelectorEvidence={...item};
        addTrace(
          'SELECTOR EVIDENCE',
          String(item?.detail||'fast-agent-router runtime evidence'),
          'core-evidence-history'
        );

        if(lastSelectorContract){
          adjustStats(Number(lastSelectorContract.seq),'match');
          addTrace(
            'MATCH',
            `ROUTER ↔ ROUTER · fast-agent-router · ${item?.detail||'selector evidence'}`,
            'selector-history-compare'
          );
        }
      }
    }

    renderSelectorHistory();
  }

  async function refreshContract(){
    if(!open||!token)return;
    try{
      const response=await fetch(`/api/router-contract?token=${encodeURIComponent(token)}`,{cache:'no-store'});
      const payload=await response.json();
      if(!response.ok)return;
      const d=payload?.decision||{};
      const runtimeEvidence=payload?.evidence||{};
      ingestRouterHistory(payload);
      renderGuardrails(payload?.readiness||{});

      // Evidence comes from the result that ACTUALLY executed, not from the
      // canonical decision. Feed it into the existing legacy-evidence window.
      const evidenceSeq=Number(runtimeEvidence.seq);
      if(
        Number.isFinite(evidenceSeq)
        && evidenceSeq>=0
        && evidenceSeq!==runtimeEvidenceSeq
      ){
        runtimeEvidenceSeq=evidenceSeq;
        rememberEvidence(
          String(runtimeEvidence.delivery||''),
          String(runtimeEvidence.route||''),
          `${runtimeEvidence.route||'tool'} · ${runtimeEvidence.detail||'runtime result'}`,
          String(runtimeEvidence.source||'core-runtime-result'),
          'strong'
        );
        addTrace(
          'EVIDENCE',
          `${String(runtimeEvidence.delivery||'').toUpperCase()} · ${runtimeEvidence.route||'—'} · ${runtimeEvidence.detail||'—'}`,
          'core-runtime-result'
        );
        const runtimeItem={
          delivery:String(runtimeEvidence.delivery||'').toUpperCase(),
          route:String(runtimeEvidence.route||''),
        };
        if(
          latestContract
          && open
          && evidenceCompatibleWithCore(runtimeItem,latestContract)
        ){
          scheduleComparison(latestContract,{preserveRetries:true});
        }
      }

      $('[data-contract-delivery]').textContent=String(d.delivery||'—');
      $('[data-contract-route]').textContent=String(d.route||'—');
      $('[data-contract-reason]').textContent=String(d.reason||'En attente d’une décision…');
      $('[data-contract-provider]').textContent=d.provider
        ?`${String(d.provider).toUpperCase()}${d.model?` · ${d.model}`:''}`
        :'—';
      $('[data-contract-owner]').textContent=String(d.owner||'legacy').toUpperCase();
      $('[data-contract-mode]').textContent=String(d.mode||'shadow').toUpperCase();

      const seq=Number(d.seq);
      if(Number.isFinite(seq)&&seq>=0&&seq!==contractSeq){
        contractSeq=seq;
        latestContract=d;
        contractSeenAt=Date.now();

        // Never leave the previous route's MATCH visible under a new Core
        // contract while the new evidence is still being correlated.
        renderNewContractPending(d);

        addTrace(
          `CONTRACT ${String(d.delivery||'').toUpperCase()}`,
          `${d.route||'—'} · ${d.reason||'—'}`,
          'core-contract'
        );
        scheduleComparison(d);
      }else if(Number.isFinite(seq)&&seq>=0){
        latestContract=d;
      }
    }catch(_){}
  }

  function updateContractPolling(){
    if(contractTimer){if(typeof contractTimer?.stop==='function')contractTimer.stop();else clearInterval(contractTimer)}
    contractTimer=0;
    clearTimeout(compareTimer);
    compareTimer=0;
    if(open){
      refreshContract();
      contractTimer=window.AuraWorkloadBudget?.repeat?window.AuraWorkloadBudget.repeat(refreshContract,'router-observatory',650):setInterval(refreshContract,650);
    }
  }

  function setOpen(value){
    open=!!value;
    if(open){
      const cutoff=Date.now()-12000;
      while(legacyEvidence.length && legacyEvidence[legacyEvidence.length-1].at<cutoff){
        legacyEvidence.pop();
      }
    }
    panel.classList.toggle('open',open);
    pill.classList.toggle('active',open);
    document.body.classList.toggle('aura-router-observatory-open',open);
    updateContractPolling();
    window.dispatchEvent(new CustomEvent('aura:router-observatory',{
      detail:{open}
    }));
  }

  pill.addEventListener('click',()=>setOpen(!open));
  $('[data-close]').addEventListener('click',()=>setOpen(false));

  document.addEventListener('keydown',event=>{
    const key=event.key.toLowerCase();
    if(event.ctrlKey&&event.shiftKey&&(key==='k'||key==='r')){
      event.preventDefault();
      event.stopImmediatePropagation();
      setOpen(!open);
    }
  },true);

  window.addEventListener('aura:workspace-changed',event=>{
    render('workspace');
    addTrace('WORKSPACE',String(event.detail?.workspace||'home').toUpperCase(),'workspace');
  });

  window.addEventListener('aura:workspace-activity',event=>{
    const d=event.detail||{};
    const detail=`${String(d.workspace||'').toUpperCase()} · ${d.label||''}${d.detail?` · ${d.detail}`:''}`;
    addTrace(
      String(d.state||'activity').toUpperCase(),
      detail,
      'workspace-activity'
    );

    const evidence=evidenceFromActivity(d);
    if(evidence){
      rememberEvidence(
        evidence.delivery,
        evidence.route,
        evidence.detail,
        evidence.source,
        'strong'
      );
    }

    render('workspace-activity');
    if(
      evidence
      && latestContract
      && open
      && evidenceCompatibleWithCore(evidence,latestContract)
    ){
      scheduleComparison(latestContract,{preserveRetries:true});
    }
  });

  const observer=new MutationObserver(()=>render('runtime'));
  [routeText,providerState,providerSub,stateText].filter(Boolean).forEach(node=>{
    observer.observe(node,{childList:true,subtree:true,characterData:true});
  });

  if(messages){
    new MutationObserver(records=>{
      for(const record of records){
        for(const node of record.addedNodes){
          if(!(node instanceof HTMLElement))continue;
          if(node.matches('.message.user'))addTrace('INPUT','Message utilisateur','conversation');
          if(node.matches('.message.aura')){
            const p=provider();
            const route=inferRoute();
            addTrace(route.kind,route.detail||`${p.provider} · ${p.model}`,'response');
          }
        }
      }
      render('conversation');
    }).observe(messages,{childList:true});
  }

  window.addEventListener('beforeunload',()=>{
    clearInterval(contractTimer);
    clearTimeout(compareTimer);
    document.body.classList.remove('aura-router-observatory-open');
  });

  window.AuraRouterObservatory=Object.freeze({
    snapshot(){
      const p=provider();
      const route=inferRoute();
      return {
        workspace:workspaceId(),
        route,
        provider:p,
        state:String(stateText?.textContent||'IDLE').trim(),
        coreContract:latestContract?{...latestContract}:null,
        comparison:{
          ...comparisonStats,
          bySeq:Object.fromEntries(comparisonBySeq),
        },
        evidenceWindowMs:8000,
        lastSelectorContract:lastSelectorContract?{...lastSelectorContract}:null,
        lastSelectorEvidence:lastSelectorEvidence?{...lastSelectorEvidence}:null,
        guardrails:{
          status:$('[data-guard-status]')?.textContent||'UNKNOWN',
          master:$('[data-guard-master]')?.textContent||'—',
          gates:$('[data-guard-gates]')?.textContent||'—',
          counts:$('[data-guard-counts]')?.textContent||'—',
          violations:$('[data-guard-violations]')?.textContent||'—',
          locked:$('[data-guard-locked]')?.textContent||'—',
        },
        evidence:legacyEvidence.slice(0,12).map(item=>({...item})),
        trace:trace.map(item=>({...item})),
      };
    },
    open(){setOpen(true)},
    close(){setOpen(false)},
  });

  render('startup');
})();
