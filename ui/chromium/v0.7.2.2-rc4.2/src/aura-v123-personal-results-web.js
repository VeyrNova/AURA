(() => {
  'use strict';
  if (window.__AURA_V123_PERSONAL_RESULTS_WEB__) return;
  window.__AURA_V123_PERSONAL_RESULTS_WEB__ = { version: '1.2.3-ft5-ux1' };

  const ROOT_ID='aura-v123-personal-results';
  const titles={mail:'MAIL',calendar:'AGENDA',contacts:'CONTACTS',tasks:'TÂCHES',drive:'DRIVE',obsidian:'OBSIDIAN'};
  const empty={mail:'Aucun mail à afficher.',calendar:'Aucun élément d’agenda à afficher.',contacts:'Aucun contact Google à afficher.',tasks:'Aucune tâche à afficher.',drive:'Aucun élément Drive à afficher.',obsidian:'Aucun resultat Obsidian a afficher.'};
  const order={
    mail:['sender','subject','preview','date_time','read_state'],
    calendar:['source','start_time','title','duration','location_or_meet','participants_optional'],
    contacts:['name','organization_role','email','phone'],
    tasks:['source','title','due','status','notes','completed'],
    drive:['type_icon','name','location','modified','size_optional'],
    obsidian:['source','title','note_type','relative_path','snippet']
  };
  /* AURA_V123_AGGREGATED_SOURCE_BADGES */
  const labels={source:'Source',
    sender:'Expéditeur',subject:'Objet',preview:'Aperçu',date_time:'Date',read_state:'État',
    start_time:'Heure',title:'Titre',duration:'Durée',location_or_meet:'Lieu',
    participants_optional:'Participants',name:'Nom',organization_role:'Organisation',
    email:'Email',phone:'Téléphone',due:'Échéance',status:'État',notes:'Notes',completed:'Terminé',type_icon:'Type',location:'Emplacement',
    modified:'Modifié',size_optional:'Taille',
    note_type:'Type',relative_path:'Note',snippet:'Contexte'
  };
  const internalFields=new Set([
    'message_id','thread_id','id','evidence_refs','source','capability_id',
    'receipt_id','pending_confirmation','clarification_required'
  ]);

  function cleanString(v){
    if(v==null)return '';
    const s=String(v).trim();
    if(!s||s==='null'||s==='undefined'||s==='None')return '';
    return s;
  }

  function addressParts(v){
    if(v==null)return [];
    if(Array.isArray(v)){
      return v.flatMap(addressParts).filter(Boolean);
    }
    if(typeof v==='object'){
      const name=cleanString(v.display_name||v.name||v.label);
      const address=cleanString(v.address||v.email||v.value);
      if(name&&address&&name.toLowerCase()!==address.toLowerCase())return [`${name}\n${address}`];
      if(name)return [name];
      if(address)return [address];
      return [];
    }
    const s=cleanString(v);
    if(!s)return [];
    if((s.startsWith('{')&&s.endsWith('}'))||(s.startsWith('[')&&s.endsWith(']'))){
      try{return addressParts(JSON.parse(s))}catch{}
    }
    return [s];
  }

  function senderValue(item){
    const candidates=[
      item&&item.sender,
      item&&item.from_address,
      item&&item.from_,
      item&&item.from,
      item&&item.sender_address,
      item&&item.sender_email,
      item&&item.sender_name
    ];
    for(const candidate of candidates){
      const parts=addressParts(candidate);
      if(parts.length)return [...new Set(parts)].join(' · ');
    }
    return 'Expéditeur non renseigné';
  }

  function textValue(field,v,item){
    if(field==='sender')return senderValue(item||{});
    if(v==null)return '';
    if(typeof v==='boolean'){
      if(field==='type_icon')return v?'Dossier':'Fichier';
      return v?'Oui':'Non';
    }
    if(Array.isArray(v))return v.slice(0,8).map(x=>textValue(field,x,item)).filter(Boolean).join(', ');
    if(typeof v==='object'){
      const out=[];
      for(const k of ['display_name','name','email','address','value']){
        const x=cleanString(v[k]);
        if(x)out.push(x);
      }
      if(out.length)return [...new Set(out)].join(' · ');
      return '';
    }
    let s=cleanString(v);
    if(field==='preview'&&s.length>220)s=s.slice(0,217)+'...';
    return s;
  }


  // AURA_V123_SYSTEM_LIVE_COEXISTENCE_BEGIN
  const SYSTEM_LIVE_SELECTORS=[
    '.telemetry',
    '#auraSystemStatePanel:not([hidden])',
    '.aura-p08514-panel:not([hidden])',
    '.aura-p0627-system.open'
  ];
  const SYSTEM_LIVE_GAP=14;

  function visibleRightPanelRect(el){
    if(!el||!el.isConnected)return null;
    const style=window.getComputedStyle(el);
    if(!style||style.display==='none'||style.visibility==='hidden'||Number(style.opacity||1)===0)return null;
    const rect=el.getBoundingClientRect();
    if(!rect||rect.width<120||rect.height<90)return null;
    if(rect.right<window.innerWidth*.72||rect.left<window.innerWidth*.42)return null;
    return rect;
  }

  function syncSystemLiveCoexistence(panel){
    const p=panel||document.getElementById(ROOT_ID);
    if(!p)return;
    const rects=SYSTEM_LIVE_SELECTORS
      .map(selector=>visibleRightPanelRect(document.querySelector(selector)))
      .filter(Boolean);
    if(!rects.length){
      p.style.removeProperty('--aura-v123-pr-right');
      p.classList.remove('aura-v123-pr-system-live-coexist');
      delete p.dataset.systemLiveReserve;
      return;
    }
    const leftEdge=Math.min(...rects.map(rect=>rect.left));
    const reserve=Math.max(18,Math.ceil(window.innerWidth-leftEdge+SYSTEM_LIVE_GAP));
    const safeReserve=Math.min(reserve,Math.max(18,window.innerWidth-360));
    p.style.setProperty('--aura-v123-pr-right',`${safeReserve}px`);
    p.classList.add('aura-v123-pr-system-live-coexist');
    p.dataset.systemLiveReserve=String(safeReserve);
  }

  function syncSystemLiveSoon(){
    const p=document.getElementById(ROOT_ID);
    if(!p)return;
    syncSystemLiveCoexistence(p);
    syncConversationResultReserve(p);
    window.requestAnimationFrame(()=>syncSystemLiveCoexistence(p));
    window.setTimeout(()=>syncSystemLiveCoexistence(p),80);
    window.setTimeout(()=>syncSystemLiveCoexistence(p),320);
  }
  // AURA_V123_SYSTEM_LIVE_COEXISTENCE_END


  // AURA_V123_CONVERSATION_RESULTS_COEXISTENCE_BEGIN
  function clearConversationResultReserve(){
    document.body.classList.remove('aura-v123-personal-results-open');
    document.documentElement.style.removeProperty('--aura-v123-conversation-right-reserve');
  }
  function syncConversationResultReserve(panel){
    const p=panel||document.getElementById(ROOT_ID);
    if(!p||p.hidden){clearConversationResultReserve();return;}
    const rect=p.getBoundingClientRect();
    if(!rect||rect.width<120||rect.height<90){clearConversationResultReserve();return;}
    const reserve=Math.max(0,Math.ceil(window.innerWidth-rect.left+14));
    document.documentElement.style.setProperty('--aura-v123-conversation-right-reserve',`${reserve}px`);
    document.body.classList.add('aura-v123-personal-results-open');
  }
  function syncConversationResultSoon(){
    const p=document.getElementById(ROOT_ID);
    syncConversationResultReserve(p);
    window.requestAnimationFrame(()=>syncConversationResultReserve(p));
    window.setTimeout(()=>syncConversationResultReserve(p),80);
  }
  document.addEventListener('click',e=>{
    const p=document.getElementById(ROOT_ID);
    if(p&&(e.target===p||p.contains(e.target))){
      window.setTimeout(()=>syncConversationResultReserve(p),0);
    }
  },true);
  window.addEventListener('resize',syncConversationResultSoon,{passive:true});
  window.addEventListener('aura:workspace-changed',syncConversationResultSoon);
  // AURA_V123_CONVERSATION_RESULTS_COEXISTENCE_END

  function ensurePanel(){
    let p=document.getElementById(ROOT_ID);
    if(p)return p;
    p=document.createElement('section');
    p.id=ROOT_ID;
    p.setAttribute('role','region');
    p.setAttribute('aria-label','Résultats AURA');
    p.innerHTML='<div class="aura-v123-pr-header"><div><div class="aura-v123-pr-eyebrow">AURA · RÉSULTATS</div><div class="aura-v123-pr-title">RÉSULTATS</div></div><div class="aura-v123-pr-actions"><div class="aura-v123-pr-count"></div><button type="button" class="aura-v123-pr-close" aria-label="Fermer">×</button></div></div><div class="aura-v123-pr-body"></div>';
    p.querySelector('.aura-v123-pr-close').addEventListener('click',()=>{p.hidden=true});
    (document.body||document.documentElement).appendChild(p);
    return p;
  }


  // AURA_V130_TASKS_FAILED_RECEIPT_PERSONAL_RESULTS_GUARD
  function sanitizeTasksReceiptPayloadV130(payload){
    if(!payload || String(payload.kind||'').toLowerCase()!=='tasks') return payload;
    const rows=Array.isArray(payload.items)?payload.items:[];
    const bad=i=>{
      const st=String(i&&i.status||'').trim().toLowerCase();
      const tt=String(
        (i&&(i.title||i.summary||i.content||i.name||i.subject||i.text||i.preview))||''
      ).trim().toLowerCase();
      return st==='failed'
        ||tt.startsWith('action non executee')
        ||tt.startsWith('action non exécutée')
        ||tt.startsWith("recu d'action")
        ||tt.startsWith("reçu d'action");
    };
    const items=rows.filter(i=>!bad(i));
    if(items.length===rows.length) return payload;
    const next={...payload,items,count:items.length};
    const breakdown=payload.source_breakdown;
    if(breakdown&&typeof breakdown==='object'){
      const removed=rows.length-items.length;
      const google=Math.max(0,Number(breakdown.google||0)-removed);
      next.source_breakdown={...breakdown,google};
    }
    next.filtered_failed_receipts_v130=rows.length-items.length;
    return next;
  }

  function render(payload){
    payload=sanitizeTasksReceiptPayloadV130(payload);
    if(!payload||typeof payload!=='object')return;
    const kind=String(payload.kind||'generic');
    if(!Object.prototype.hasOwnProperty.call(titles,kind))return;
    const p=ensurePanel();
    syncSystemLiveCoexistence(p);
    syncConversationResultReserve(p);
    const items=Array.isArray(payload.items)?payload.items:[];
    const n=Number.isFinite(Number(payload.count))?Number(payload.count):items.length;
    p.dataset.kind=kind;
    p.querySelector('.aura-v123-pr-title').textContent=titles[kind];
    p.querySelector('.aura-v123-pr-count').textContent=`${n} résultat${n===1?'':'s'}`;
    const body=p.querySelector('.aura-v123-pr-body');
    body.replaceChildren();
    if(!items.length){
      const e=document.createElement('div');
      e.className='aura-v123-pr-empty';
      e.textContent=empty[kind];
      body.appendChild(e);
      p.hidden=false;
      syncSystemLiveSoon();
      return;
    }
    for(const raw of items.slice(0,50)){
      const item=(raw&&typeof raw==='object')?raw:{title:String(raw)};
      const card=document.createElement('article');
      card.className=`aura-v123-pr-card aura-v123-pr-${kind}`;
      const base=order[kind]||[];
      const fields=[...base,...Object.keys(item).filter(k=>!base.includes(k)&&!internalFields.has(k))];
      for(const field of fields){
        const value=textValue(field,item[field],item);
        if(!value)continue;
        const row=document.createElement('div');
        row.className=`aura-v123-pr-row aura-v123-pr-field-${field}`;
        const key=document.createElement('span');
        key.className='aura-v123-pr-key';
        key.textContent=labels[field]||field.replaceAll('_',' ');
        const val=document.createElement('span');
        val.className='aura-v123-pr-value';
        val.textContent=value;
        row.append(key,val);
        card.appendChild(row);
      }
      body.appendChild(card);
    }
    p.hidden=false;
    syncSystemLiveSoon();
  }

  window.addEventListener('resize',syncSystemLiveSoon,{passive:true});
  window.addEventListener('aura:workspace-changed',syncSystemLiveSoon);
  window.addEventListener('aura:system-state-module-ready',syncSystemLiveSoon);

  window.addEventListener('aura:hub-event',e=>{
    const msg=e&&e.detail?e.detail:{};
    if(String(msg.type||'')==='personal_result')render(msg.data||{});
  });

  window.__AURA_V123_PERSONAL_RESULTS_WEB__.render=render;
})();

/* AURA ROADMAP W131-3D4-R1 — WINDOWS PERSONAL RESULTS HEADER TRUTH */
;(() => {
  'use strict';
  if (window.__AURA_W131_WINDOWS_HEADER_TRUTH__) return;
  window.__AURA_W131_WINDOWS_HEADER_TRUTH__ = true;

  const upper = value => String(value == null ? '' : value).trim().toUpperCase();
  const lower = value => String(value == null ? '' : value).trim().toLowerCase();

  function isPcPayload(payload) {
    if (!payload || typeof payload !== 'object') return false;
    const source = upper(payload.source);
    const sources = Array.isArray(payload.sources) ? payload.sources.map(upper) : [];
    const provider = lower(payload.provider_id);
    const capability = lower(payload.capability_id);
    return source === 'WINDOWS'
      || sources.includes('WINDOWS')
      || provider === 'pc-control.windows'
      || capability.startsWith('pc.');
  }

  function applyWindowsHeader(payload) {
    if (!isPcPayload(payload)) return false;

    const items = Array.isArray(payload.items) ? payload.items : [];
    const rawCount = Number(payload.count);
    const count = Number.isFinite(rawCount) && rawCount >= 0
      ? Math.trunc(rawCount)
      : items.length;
    const noun = count === 1 ? 'élément' : 'éléments';
    const label = `${count} ${noun} · WINDOWS`;

    const update = () => {
      const panel = document.querySelector('section[aria-label="Résultats AURA"]');
      const target = panel?.querySelector('.aura-v123-pr-count');
      if (!target) return false;
      target.textContent = label;
      target.dataset.auraW131Source = 'WINDOWS';
      return true;
    };

    try { queueMicrotask(update); } catch (_) {}
    try { requestAnimationFrame(update); } catch (_) {}
    window.setTimeout(update, 0);
    window.setTimeout(update, 80);
    return true;
  }

  window.addEventListener('aura:hub-event', event => {
    const message = event?.detail || {};
    if (String(message?.type || '') !== 'personal_result') return;
    applyWindowsHeader(message?.data || {});
  });

  window.AuraW131WindowsHeaderTruth = Object.freeze({
    version: 'W131-3D4-R1',
    isPcPayload,
    applyWindowsHeader
  });
})();

/* AURA_O140_R2_OBSIDIAN_PERSONAL_RESULTS_WEB */
