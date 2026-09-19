/* AURA ADF-H R5 R4.4 — DEV SURFACE PARITY */
(() => {
  "use strict";
  const VERSION="ADF-H-R5-R4.4";
  const token=new URLSearchParams(location.search).get("token")||"";
  if(!token)return;

  const IDS={
    frame:"aura-adf-h-r5-frame",
    underbar:"aura-adf-h-r5-underbar",
    glow:"aura-adf-h-r5-glow",
    badge:"aura-adf-h-r5-badge",
    status:"aura-adf-h-r5-status",
    workspace:"aura-adf-h-r5-workspace"
  };
  const SERIAL_KEY="aura-adf-h-r5-r4-4-workspace-serial";
  const MARKED_ATTR="data-aura-adf-marked";

  let enabled=false,initialized=false,lastSnapshot=null,timer=null;
  let lastWorkspaceSerial=Number(sessionStorage.getItem(SERIAL_KEY)||0);
  document.documentElement.dataset.auraAdfH=VERSION;

  function make(tag,className,text){
    const el=document.createElement(tag);
    if(className)el.className=className;
    if(text!==undefined&&text!==null)el.textContent=String(text);
    return el;
  }
  function ensure(id,text){
    let el=document.getElementById(id);
    if(!el){
      el=document.createElement("div");el.id=id;
      if(text)el.textContent=text;
      document.body.appendChild(el);
    }
    return el;
  }
  function visible(el){
    if(!el) return false;
    const r=el.getBoundingClientRect(), s=getComputedStyle(el);
    return r.width>0 && r.height>0 && s.display!=="none" && s.visibility!=="hidden" && s.opacity!=="0";
  }
  function mark(el,key){
    if(!el) return;
    const prev=(el.getAttribute(MARKED_ATTR)||"").split(" ").filter(Boolean);
    if(!prev.includes(key)) prev.push(key);
    el.setAttribute(MARKED_ATTR, prev.join(" "));
  }
  function unmark(key, className){
    document.querySelectorAll('.'+className).forEach(el=>el.classList.remove(className));
    document.querySelectorAll('['+MARKED_ATTR+']').forEach(el=>{
      const keys=(el.getAttribute(MARKED_ATTR)||"").split(" ").filter(Boolean).filter(x=>x!==key);
      if(keys.length) el.setAttribute(MARKED_ATTR, keys.join(" ")); else el.removeAttribute(MARKED_ATTR);
    });
  }
  function addClass(el, className, key){
    if(!el) return;
    el.classList.add(className);
    mark(el,key);
  }
  function findComposer(){
    const nodes=[...document.querySelectorAll('textarea,input[type="text"],input:not([type]),[contenteditable="true"]')]
      .filter(el=>{
        const r=el.getBoundingClientRect(),s=getComputedStyle(el);
        return r.width>180&&r.height>18&&s.display!=="none"&&s.visibility!=="hidden";
      });
    nodes.sort((a,b)=>b.getBoundingClientRect().top-a.getBoundingClientRect().top);
    return nodes[0]||null;
  }
  function detectSidebar(){
    const nodes=[...document.querySelectorAll('aside,nav,section,div')].filter(visible);
    let best=null,score=-1;
    for(const el of nodes){
      const r=el.getBoundingClientRect();
      if(r.left>30||r.top>120||r.width<150||r.width>260||r.height<window.innerHeight*0.58) continue;
      const local=(window.innerHeight-r.top)+(220-r.width);
      if(local>score){score=local;best=el;}
    }
    return best;
  }
  function detectRightRail(){
    const nodes=[...document.querySelectorAll('aside,section,div')].filter(visible);
    let best=null,score=-1;
    for(const el of nodes){
      const r=el.getBoundingClientRect();
      if(r.right<window.innerWidth-24||r.top>120||r.width<180||r.width>340||r.height<window.innerHeight*0.34) continue;
      const local=r.height - (window.innerWidth-r.right)*4;
      if(local>score){score=local;best=el;}
    }
    return best;
  }
  function detectProjectCard(){
    const nodes=[...document.querySelectorAll('section,div,article')].filter(visible);
    let best=null,score=-1;
    for(const el of nodes){
      const r=el.getBoundingClientRect();
      if(r.top<70||r.top>190||r.left<window.innerWidth*0.56||r.left>window.innerWidth*0.76||r.width<220||r.width>360||r.height<120||r.height>280) continue;
      const local=(300-abs(window.innerWidth*0.74-r.left)) + (240-r.height);
      if(local>score){score=local;best=el;}
    }
    return best;
    function abs(x){ return x < 0 ? -x : x; }
  }
  function closeWorkspace(){document.getElementById(IDS.workspace)?.remove()}

  function applySurfaceParity(){
    const composer=findComposer();
    if(composer){
      composer.classList.add('aura-adf-dev-composer');
      addClass(composer.closest('form,section,div')||composer, 'aura-adf-dev-composer-wrap', 'composer-wrap');
      if('placeholder' in composer){
        if(composer.dataset.auraAdfPlaceholder===undefined)
          composer.dataset.auraAdfPlaceholder=composer.getAttribute('placeholder')||'';
        composer.setAttribute('placeholder','AURA DEV // Build, patch ou test ?');
      }
    }
    // R5 R31: preserve normal sidebar geometry; no Developer sizing class.
    addClass(detectRightRail(),'aura-adf-dev-rightrail','rightrail');
    addClass(detectProjectCard(),'aura-adf-dev-card','projectcard');
  }
  function clearSurfaceParity(){
    document.documentElement.classList.remove('aura-adf-dev-active');
    [IDS.glow,IDS.frame,IDS.underbar,IDS.badge,IDS.status].forEach(id=>document.getElementById(id)?.remove());
    document.querySelectorAll('.aura-adf-dev-composer').forEach(c=>{
      c.classList.remove('aura-adf-dev-composer');
      if('placeholder' in c&&c.dataset.auraAdfPlaceholder!==undefined){
        c.setAttribute('placeholder',c.dataset.auraAdfPlaceholder||'');
        delete c.dataset.auraAdfPlaceholder;
      }
    });
    ['aura-adf-dev-composer-wrap','aura-adf-dev-sidebar','aura-adf-dev-rightrail','aura-adf-dev-card'].forEach(cls=>{
      document.querySelectorAll('.'+cls).forEach(el=>el.classList.remove(cls));
    });
    document.querySelectorAll('['+MARKED_ATTR+']').forEach(el=>el.removeAttribute(MARKED_ATTR));
    closeWorkspace();
  }


  function findTopRuntimeStateChip(){
    const labels=new Set([
      'IDLE','SPEAKING','LISTENING','THINKING','WORKING','PROCESSING'
    ]);
    const nodes=[...document.querySelectorAll('button,span,div')];
    let best=null;
    for(const el of nodes){
      if(!visible(el)) continue;
      const text=(el.textContent||'').trim().toUpperCase();
      if(!labels.has(text)) continue;
      const r=el.getBoundingClientRect();
      if(r.top<6||r.bottom>74||r.width<34||r.width>150||r.height<16||r.height>46) continue;
      if(!best||r.left<best.getBoundingClientRect().left) best=el;
    }
    return best;
  }

  function alignHeaderDevIndicators(){
    if(!enabled) return;
    const badge=document.getElementById(IDS.badge);
    const status=document.getElementById(IDS.status);
    const anchor=findTopRuntimeStateChip();
    if(!badge||!status||!anchor) return;

    const ar=anchor.getBoundingClientRect();
    const br=badge.getBoundingClientRect();
    const sr=status.getBoundingClientRect();
    const centerY=ar.top+(ar.height/2);

    const badgeTop=Math.round(centerY-(br.height/2));
    const badgeLeft=Math.max(220,Math.round(ar.left-br.width-10));
    const statusTop=Math.round(centerY-(sr.height/2));
    const statusLeft=Math.max(220,Math.round(badgeLeft-sr.width-12));

    badge.style.top=badgeTop+'px';
    badge.style.left=badgeLeft+'px';
    status.style.top=statusTop+'px';
    status.style.left=statusLeft+'px';
  }

  function applyVisual(next){
    next=!!next;
    if(initialized&&enabled===next) return;
    initialized=true; enabled=next;
    if(enabled){
      document.documentElement.classList.add('aura-adf-dev-active');
      ensure(IDS.glow); ensure(IDS.frame); ensure(IDS.underbar); ensure(IDS.badge,'DEV MODE'); ensure(IDS.status,'WRITE GATED · AUDIT ON');
      applySurfaceParity();
      requestAnimationFrame(()=>requestAnimationFrame(alignHeaderDevIndicators));
    } else {
      clearSurfaceParity();
    }
  }

  function refreshSurfaceIfNeeded(){
    if(!enabled) return;
    applySurfaceParity();
  }
  function chip(label){ return make('div','adf-chip',label); }
  function card(title){
    const root=make('section','adf-card');
    root.appendChild(make('div','adf-card-head',title));
    const body=make('div','adf-card-body');
    root.appendChild(body);
    return {root,body};
  }
  function empty(title,sub){
    const root=make('div','adf-empty');
    root.appendChild(make('strong','',title));
    root.appendChild(make('span','',sub));
    return root;
  }
  function openWorkspace(data){
    closeWorkspace();
    const overlay=document.createElement('div'); overlay.id=IDS.workspace;
    const panel=make('div','adf-panel'); const head=make('div','adf-head');
    const titleWrap=make('div','adf-title-wrap');
    titleWrap.appendChild(make('div','adf-title','AURA // DEVELOPER'));
    titleWrap.appendChild(make('div','adf-subtitle','HIGH-CONTRAST DEVELOPMENT WORKSPACE'));
    head.appendChild(titleWrap);
    head.appendChild(make('span','adf-head-status','ACTIVE'));
    head.appendChild(make('span','adf-gate','WRITE GATED'));
    const close=make('button','adf-close','×');
    close.setAttribute('aria-label','Fermer'); close.addEventListener('click',closeWorkspace); head.appendChild(close);

    const grid=make('div','adf-grid'); const left=make('aside','adf-left'); const right=make('main','adf-right');
    left.appendChild(make('div','adf-section-title','SESSION'));
    const modeCard=make('div','adf-mode-card'); const modeRow=make('div','adf-mode-row');
    modeRow.appendChild(make('span','adf-dot')); modeRow.appendChild(make('span','','MODE DÉVELOPPEUR ACTIF')); modeCard.appendChild(modeRow);
    modeCard.appendChild(make('div','adf-mode-note','Profil visuel différencié : prune/ambre sur le workspace et sur la surface principale.'));
    left.appendChild(modeCard);
    left.appendChild(make('div','adf-section-title','PROTECTIONS'));
    const chips=make('div','adf-chip-grid'); ['STAGING','TESTS','APPLY','DUAL GATE','RELEASE GATE','ROLLBACK'].forEach(x=>chips.appendChild(chip(x))); left.appendChild(chips);
    left.appendChild(make('div','adf-footer','Pour quitter : « Aura, désactive le mode développeur ». Les détails techniques restent silencieux côté TTS.'));

    right.appendChild(make('div','adf-section-title','ACTIVITÉ'));
    const txCard=card('TRANSACTIONS RÉCENTES'); const txs=Array.isArray(data?.recent_transactions)?data.recent_transactions:[];
    if(!txs.length){ txCard.body.appendChild(empty('Aucune transaction récente','Les opérations validées apparaîtront ici.')); }
    else { txs.slice(0,8).forEach(tx=>{ const row=make('div','adf-tx'); row.appendChild(make('div','adf-tx-id',tx?.transaction_id||'transaction')); row.appendChild(make('div','adf-tx-state',tx?.rolled_back?'ROLLBACK':(tx?.tests_passed===false?'FAILED':'VALIDATED'))); txCard.body.appendChild(row); }); }
    right.appendChild(txCard.root);
    const auditCard=card('AUDIT'); const audit=data?.audit_head;
    if(!audit){ auditCard.body.appendChild(empty('Aucun événement d’audit','La chaîne d’audit apparaîtra après une opération de développement.')); }
    else { [['Séquence',audit.sequence??audit.seq??'—'],['Événement',audit.event_hash??audit.hash??'—'],['Précédent',audit.prev_hash??'—']].forEach(([label,value])=>{ const row=make('div','adf-audit-line'); row.appendChild(make('span','',label)); row.appendChild(make('span','adf-audit-value',String(value).slice(0,22))); auditCard.body.appendChild(row); }); }
    right.appendChild(auditCard.root);

    grid.append(left,right); panel.append(head,grid); overlay.appendChild(panel); document.body.appendChild(overlay);
  }
  function maybeOpenWorkspace(data){
    const req=data?.workspace_request||{}; const serial=Number(req.serial||0); const requestedAt=Number(req.requested_at||0);
    const fresh=requestedAt>0&&Math.abs((Date.now()/1000)-requestedAt)<=15;
    if(serial>lastWorkspaceSerial){
      lastWorkspaceSerial=serial; sessionStorage.setItem(SERIAL_KEY,String(serial)); if(enabled&&fresh) openWorkspace(data);
    }
  }
  async function poll(){
    try{
      const response=await fetch(`/api/developer-fabric?token=${encodeURIComponent(token)}`,{method:'GET',cache:'no-store'});
      if(!response.ok) return; const data=await response.json(); if(!data||data.ok!==true) return;
      lastSnapshot=data; applyVisual(!!data?.developer_mode?.enabled); maybeOpenWorkspace(data); refreshSurfaceIfNeeded();
    }catch(_){ }
  }
  function start(){ if(!document.body){ setTimeout(start,50); return; } poll(); if(timer===null) timer=setInterval(poll,700); }
  window.addEventListener('resize',()=>{
    if(!enabled) return;
    setTimeout(refreshSurfaceIfNeeded,120);
    requestAnimationFrame(alignHeaderDevIndicators);
  });
  window.AuraDeveloperModeSurface=Object.freeze({ version:VERSION, refresh:poll, open:()=>openWorkspace(lastSnapshot||{}), close:closeWorkspace, enabled:()=>enabled });
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',start,{once:true}); else start();
})();

/* AURA ADF-H R6.3.3 — DISMISSIBLE ACTIONABLE AUTO-OPEN */
(() => {
  "use strict";
  if (window.__AURA_ADF_H_R633__) return;
  window.__AURA_ADF_H_R633__ = true;

  const token = new URLSearchParams(location.search).get("token") || "";
  if (!token) return;

  const HANDLED_KEY = "aura-adf-h-r6-3-3-selftest-handled-key";
  const DISMISSED_KEY = "aura-adf-h-r6-3-3-selftest-dismissed-key";

  let handledKey = sessionStorage.getItem(HANDLED_KEY) || "";
  let dismissedKey = sessionStorage.getItem(DISMISSED_KEY) || "";
  let desiredKey = "";
  let desiredState = null;
  let lastState = null;
  let renderedKey = "";
  let timer = null;
  let openRetryTimer = null;
  let openRetryCount = 0;
  let firstFetch = true;
  const bootEpoch = Date.now() / 1000;

  function el(tag, cls, text){
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined&&text!==null)n.textContent=String(text);
    return n;
  }

  function actionableKey(state){
    if(!state) return "";
    const pending=state.pending;
    const receipt=state.last_receipt;
    const rollback=state.last_rollback;

    if(pending){
      const approvals=(pending.approvals_received||[]).join("|");
      return "pending:"+String(pending?.proposal?.transaction_id||pending?.created_at||"")+":"+approvals;
    }
    if(receipt){
      return "receipt:"+String(receipt.transaction_id||receipt.applied_at||"");
    }
    if(rollback){
      return "rollback:"+String(rollback.transaction_id||rollback.rolled_back_at||"");
    }

    /* IDLE / EMPTY is deliberately NOT actionable. */
    return "";
  }

  function stateUpdatedAt(state){
    const value=Number(state?.updated_at||0);
    return Number.isFinite(value)?value:0;
  }

  function metaRow(root,label,value,cls){
    root.appendChild(el("span","",label));
    root.appendChild(el("strong",cls||"",value??"—"));
  }

  function copyText(text,button){
    const done=()=>{
      button.textContent="COPIÉ";
      setTimeout(()=>button.textContent="COPIER",1200);
    };
    if(navigator.clipboard&&navigator.clipboard.writeText){
      navigator.clipboard.writeText(text).then(done).catch(()=>fallback());
    }else fallback();

    function fallback(){
      const ta=document.createElement("textarea");
      ta.value=text;
      ta.style.position="fixed";
      ta.style.opacity="0";
      document.body.appendChild(ta);
      ta.select();
      try{document.execCommand("copy");done()}catch(_){}
      ta.remove();
    }
  }

  function approvalBlock(root,phrase){
    const wrap=el("div","adf-r62-approval");
    wrap.appendChild(el("code","",phrase));
    const b=el("button","adf-r62-copy","COPIER");
    b.addEventListener("click",()=>copyText(phrase,b));
    wrap.appendChild(b);
    root.appendChild(wrap);
  }

  function render(state){
    const overlay=document.getElementById("aura-adf-h-r5-workspace");
    if(!overlay) return false;
    const right=overlay.querySelector(".adf-right");
    if(!right) return false;

    right.querySelector(".adf-r62-transaction")?.remove();

    const card=el("section","adf-r62-transaction");
    const head=el("div","adf-r62-head","SELF-DEVELOPMENT TRANSACTION");
    const badge=el("span","adf-r62-state");
    head.appendChild(badge);
    card.appendChild(head);
    const body=el("div","adf-r62-body");
    card.appendChild(body);

    const pending=state?.pending;
    const receipt=state?.last_receipt;
    const rollback=state?.last_rollback;

    if(pending){
      badge.textContent="AWAITING APPROVAL";
      const proposal=pending.proposal||{};
      const validation=pending.validation||{};
      const assessment=pending.assessment||{};
      const edits=Array.isArray(proposal.edits)?proposal.edits:[];
      const edit=edits[0]||{};
      const required=Array.isArray(assessment.required_approvals)?assessment.required_approvals:[];
      const meta=el("div","adf-r62-meta");
      metaRow(meta,"Transaction",proposal.transaction_id||"—");
      metaRow(meta,"Fichier",edit.path||"runtime/developer_fabric/selftest_dev_patch.py");
      metaRow(meta,"Risque",assessment.max_risk||"unknown");
      metaRow(meta,"Staging",validation.passed===true?"PASS":"FAIL",
        validation.passed===true?"adf-r62-ok":"adf-r62-warn");
      body.appendChild(meta);

      body.appendChild(el("div","adf-r62-label","DIFF"));
      body.appendChild(el("pre","adf-r62-code",edit.diff||"(aucun diff disponible)"));

      body.appendChild(el("div","adf-r62-label","APPROBATION EXACTE REQUISE"));
      if(required.length){
        required.forEach(p=>approvalBlock(body,String(p)));
      }else{
        body.appendChild(el("div","adf-r62-warn","Aucune phrase d’approbation n’a été fournie."));
      }
    }else if(receipt){
      badge.textContent="APPLIED";
      const meta=el("div","adf-r62-meta");
      metaRow(meta,"Transaction",receipt.transaction_id||"—");
      metaRow(meta,"État","APPLIQUÉ","adf-r62-ok");
      metaRow(meta,"Tests post-apply","PASS","adf-r62-ok");
      body.appendChild(meta);

      const rollbackPhrase=String(receipt.rollback_phrase||"");
      if(rollbackPhrase){
        body.appendChild(el("div","adf-r62-label","ROLLBACK EXACT"));
        approvalBlock(body,rollbackPhrase);
      }
    }else if(rollback){
      badge.textContent="ROLLED BACK";
      const meta=el("div","adf-r62-meta");
      metaRow(meta,"Transaction",rollback.transaction_id||"—");
      metaRow(meta,"État","ROLLBACK TERMINÉ","adf-r62-ok");
      body.appendChild(meta);
    }else{
      badge.textContent="IDLE";
      body.appendChild(el("div","adf-r62-warn","Aucune transaction de micro-test active."));
    }

    right.insertBefore(card,right.firstChild);
    renderedKey=actionableKey(state);
    return true;
  }

  function clearOpenRetry(){
    if(openRetryTimer!==null){
      clearTimeout(openRetryTimer);
      openRetryTimer=null;
    }
    openRetryCount=0;
  }

  function commitHandled(key){
    handledKey=key;
    desiredKey="";
    desiredState=null;
    clearOpenRetry();
    if(key) sessionStorage.setItem(HANDLED_KEY,key);
    else sessionStorage.removeItem(HANDLED_KEY);
  }

  function dismissCurrent(){
    const key=renderedKey || desiredKey || actionableKey(lastState);
    desiredKey="";
    desiredState=null;
    clearOpenRetry();

    if(key){
      dismissedKey=key;
      handledKey=key;
      sessionStorage.setItem(DISMISSED_KEY,key);
      sessionStorage.setItem(HANDLED_KEY,key);
    }
    renderedKey="";
  }

  function surfaceReady(){
    try{
      return !!(
        window.AuraDeveloperModeSurface &&
        typeof window.AuraDeveloperModeSurface.open==="function" &&
        typeof window.AuraDeveloperModeSurface.enabled==="function" &&
        window.AuraDeveloperModeSurface.enabled()
      );
    }catch(_){
      return false;
    }
  }

  function scheduleOpenRetry(){
    if(!desiredKey || desiredKey===dismissedKey || openRetryTimer!==null) return;
    openRetryCount++;
    const delay=Math.min(120+openRetryCount*80,700);
    openRetryTimer=setTimeout(()=>{
      openRetryTimer=null;
      tryOpenDesired();
    },delay);
  }

  function tryOpenDesired(){
    if(!desiredKey || !desiredState) return;

    if(desiredKey===dismissedKey || desiredKey===handledKey){
      desiredKey="";
      desiredState=null;
      clearOpenRetry();
      return;
    }

    if(!surfaceReady()){
      scheduleOpenRetry();
      return;
    }

    try{
      if(!document.getElementById("aura-adf-h-r5-workspace")){
        window.AuraDeveloperModeSurface.open();
      }
    }catch(_){
      scheduleOpenRetry();
      return;
    }

    setTimeout(()=>{
      if(desiredKey===dismissedKey){
        desiredKey="";
        desiredState=null;
        clearOpenRetry();
        return;
      }
      if(render(desiredState)){
        commitHandled(desiredKey);
      }else{
        scheduleOpenRetry();
      }
    },90);
  }

  function queueAutoOpen(state,key){
    if(!key || key===handledKey || key===dismissedKey) return;
    desiredKey=key;
    desiredState=state;
    openRetryCount=0;
    tryOpenDesired();
  }

  function shouldAutoOpenOnFirstFetch(state,key){
    if(!key || key===handledKey || key===dismissedKey) return false;
    const updated=stateUpdatedAt(state);
    return updated>0 && updated>=bootEpoch-15;
  }

  async function fetchState(){
    try{
      const r=await fetch(`/api/developer-selftest?token=${encodeURIComponent(token)}`,{
        method:"GET",cache:"no-store"
      });
      if(!r.ok) return;
      const payload=await r.json();
      if(!payload||payload.ok!==true) return;

      const state=payload.state||{};
      lastState=state;
      const key=actionableKey(state);

      if(firstFetch){
        firstFetch=false;
        if(shouldAutoOpenOnFirstFetch(state,key)){
          queueAutoOpen(state,key);
        }else{
          if(key && key!==dismissedKey){
            handledKey=key;
            sessionStorage.setItem(HANDLED_KEY,key);
          }
        }
        if(document.getElementById("aura-adf-h-r5-workspace")) render(state);
        return;
      }

      if(key && key!==handledKey && key!==dismissedKey){
        if(dismissedKey && key!==dismissedKey){
          dismissedKey="";
          sessionStorage.removeItem(DISMISSED_KEY);
        }
        queueAutoOpen(state,key);
      }else if(document.getElementById("aura-adf-h-r5-workspace")){
        render(state);
      }

      if(desiredKey) tryOpenDesired();
    }catch(_){}
  }

  document.addEventListener("click",(ev)=>{
    try{
      const target=ev.target;
      if(!(target instanceof Element)) return;
      const close=target.closest("#aura-adf-h-r5-workspace .adf-close");
      if(close) dismissCurrent();
    }catch(_){}
  },true);

  document.addEventListener("keydown",(ev)=>{
    if(ev.key!=="Escape") return;
    if(document.getElementById("aura-adf-h-r5-workspace")) dismissCurrent();
  },true);

  function start(){
    fetchState();
    if(timer===null) timer=setInterval(fetchState,600);
  }

  window.AuraDeveloperSelftestSurfaceR633=Object.freeze({
    version:"ADF-H-R6.3.3",
    refresh:fetchState,
    handled:()=>handledKey,
    dismissed:()=>dismissedKey,
    pendingOpen:()=>desiredKey,
    dismiss:dismissCurrent
  });

  if(document.readyState==="loading"){
    document.addEventListener("DOMContentLoaded",start,{once:true});
  }else start();
})();
