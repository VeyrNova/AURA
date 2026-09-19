/* AURA P0.6.2.4 — Response Quality & UX Consolidation */
(()=>{
  'use strict';
  const token=new URLSearchParams(location.search).get('token')||'';
  if(!token)return;
  const $=(s,r=document)=>r.querySelector(s);
  const messages=$('#messages'),workspace=$('.workspace');
  if(!messages||!workspace)return;

  let turnActive=false;
  let turnRoute=null;
  let turnKind='';
  let lastAuraRow=null;
  let activityHideTimer=0;
  let documentActive=false;
  let documentCompletedSeen=false;

  // P0.6.2.4.2 — the document HUD must not depend on the timing of a single
  // document.analysis SSE event. Keep a tiny local mirror of the attachment
  // state and classify only explicit document-scoped turns.
  const documentScopeRe=/\b(?:ce|cet|cette|le|la|du|dans\s+le|dans\s+la|dans\s+ce|dans\s+cette)\s+(?:document|fichier|pdf|facture|pi[eè]ce\s+jointe)\b|\b(?:présent(?:e|es|s)?|figure(?:nt)?|indiqu[ée]s?|mentionn[ée]s?|contenu(?:e|es|s)?)\s+(?:dans|sur)\s+(?:ce|cet|cette|le|la)\s+(?:document|fichier|pdf|facture)\b|\b(?:analyse|analysez|résume|resume|cherche|recherche|trouve|vérifie|verifie)\s+(?:uniquement\s+)?(?:dans\s+)?(?:ce|cet|cette|le|la)?\s*(?:document|fichier|pdf|facture)\b/i;
  const explicitWebRe=/\b(?:sur\s+internet|sur\s+le\s+web|dans\s+le\s+web|en\s+ligne|recherche\s+web|recherche\s+internet|sources?\s+web)\b/i;
  function documentTurnHint(text){
    const value=String(text||'').replace(/\s+/g,' ').trim();
    return !!(documentActive&&value&&documentScopeRe.test(value)&&!explicitWebRe.test(value));
  }
  fetch(`/api/files/status?token=${encodeURIComponent(token)}`,{cache:'no-store'})
    .then(r=>r.ok?r.json():null).then(d=>{if(d)documentActive=!!d.active}).catch(()=>{});

  const activity=document.createElement('section');
  activity.className='aura-p0624-activity glass';
  activity.innerHTML='<div class="aura-p0624-activity-head"><span>CORE ACTIVITY</span><b>READY</b></div><div class="aura-p0624-activity-body"><strong>Prête</strong><small>Runtime local connecté</small></div><div class="aura-p0624-activity-track"><i></i></div><div class="aura-p0624-activity-route"></div>';
  workspace.appendChild(activity);
  const aState=$('.aura-p0624-activity-head b',activity),aTitle=$('.aura-p0624-activity-body strong',activity),aDetail=$('.aura-p0624-activity-body small',activity),aFill=$('.aura-p0624-activity-track i',activity),aRoute=$('.aura-p0624-activity-route',activity);

  function routeText(route){
    if(!route)return'';
    const p=String(route.provider||'').toUpperCase();
    const m=String(route.model||'').replace(/^models\//,'');
    return [p,m].filter(Boolean).join(' · ').slice(0,76);
  }
  function workspaceActivity(state,label,detail=''){
    window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
      detail:{workspace:'talk',state,label,detail}
    }));
  }

  function showActivity(title,detail='',progress=35,route=null,state='ACTIVE',hold=0){
    clearTimeout(activityHideTimer);
    activity.classList.add('show');
    aState.textContent=String(state||'ACTIVE').toUpperCase();
    aTitle.textContent=String(title||'AURA travaille');
    aDetail.textContent=String(detail||'');
    aFill.style.width=Math.max(3,Math.min(100,Number(progress)||0))+'%';
    const rt=routeText(route||turnRoute);aRoute.textContent=rt;aRoute.hidden=!rt;
    const normalizedState=String(state||'ACTIVE').toUpperCase()==='ERROR'
      ?'error'
      :String(state||'ACTIVE').toUpperCase()==='DONE'
        ?'ready':'loading';
    workspaceActivity(normalizedState,String(title||'AURA travaille'),String(detail||''));
    if(hold>0)activityHideTimer=setTimeout(()=>activity.classList.remove('show'),hold);
  }
  function completeActivity(title='Terminé',detail=''){
    showActivity(title,detail,100,turnRoute,'DONE',950);
  }
  function failActivity(detail='Opération interrompue'){
    showActivity('Erreur',detail,100,turnRoute,'ERROR',1800);
    activity.classList.add('error');
    setTimeout(()=>activity.classList.remove('error'),1900);
  }

  function appendInline(parent,text){
    const src=String(text||'');
    const rx=/(\*\*([^*]+)\*\*|`([^`]+)`|\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)|\*([^*]+)\*)/g;
    let last=0,m;
    while((m=rx.exec(src))){
      if(m.index>last)parent.appendChild(document.createTextNode(src.slice(last,m.index)));
      let el;
      if(m[2]!=null){el=document.createElement('strong');el.textContent=m[2]}
      else if(m[3]!=null){el=document.createElement('code');el.textContent=m[3]}
      else if(m[4]!=null){el=document.createElement('a');el.textContent=m[4];el.href=m[5];el.target='_blank';el.rel='noreferrer noopener'}
      else{el=document.createElement('em');el.textContent=m[6]}
      parent.appendChild(el);last=rx.lastIndex;
    }
    if(last<src.length)parent.appendChild(document.createTextNode(src.slice(last)));
  }
  function safeMarkdown(raw){
    const root=document.createElement('div');root.className='aura-p0624-rich-text';
    const lines=String(raw||'').replace(/\r/g,'').split('\n');
    let para=null,list=null,listType='',pre=null;
    const closePara=()=>{para=null};
    const closeList=()=>{list=null;listType=''};
    for(let i=0;i<lines.length;i++){
      const line=lines[i];
      if(/^```/.test(line.trim())){
        closePara();closeList();
        if(pre){pre=null;continue}
        pre=document.createElement('pre');const code=document.createElement('code');pre.appendChild(code);root.appendChild(pre);continue;
      }
      if(pre){const code=pre.firstChild;code.textContent+=(code.textContent?'\n':'')+line;continue}
      if(!line.trim()){closePara();closeList();continue}
      const h=line.match(/^(#{1,4})\s+(.+)$/);
      if(h){closePara();closeList();const el=document.createElement('h'+Math.min(4,h[1].length+1));appendInline(el,h[2]);root.appendChild(el);continue}
      const ul=line.match(/^\s*[-*]\s+(.+)$/),ol=line.match(/^\s*\d+[.)]\s+(.+)$/);
      if(ul||ol){closePara();const typ=ul?'ul':'ol';if(!list||listType!==typ){closeList();list=document.createElement(typ);listType=typ;root.appendChild(list)}const li=document.createElement('li');appendInline(li,(ul||ol)[1]);list.appendChild(li);continue}
      const q=line.match(/^>\s?(.*)$/);
      if(q){closePara();closeList();const b=document.createElement('blockquote');appendInline(b,q[1]);root.appendChild(b);continue}
      closeList();
      if(!para){para=document.createElement('p');root.appendChild(para)}else para.appendChild(document.createElement('br'));
      appendInline(para,line);
    }
    return root;
  }
  function enrichMessages(){
    messages.querySelectorAll('.message.aura > p:not([data-p0624-rendered])').forEach(p=>{
      const rich=safeMarkdown(p.textContent||'');rich.dataset.p0624Rendered='1';p.replaceWith(rich);
    });
  }
  function decorateRow(row,route){
    if(!row||!route)return;
    let badge=$('.aura-p0624-route-badge',row);
    if(!badge){badge=document.createElement('div');badge.className='aura-p0624-route-badge';const meta=row.querySelector(':scope > span');if(meta)meta.insertAdjacentElement('afterend',badge);else row.prepend(badge)}
    const text=routeText(route);badge.textContent=text;badge.hidden=!text;
  }
  function latestAura(){const rows=messages.querySelectorAll('.message.aura');return rows[rows.length-1]||null}
  function decorateLatest(route=turnRoute){setTimeout(()=>{enrichMessages();const row=latestAura();if(row&&route){lastAuraRow=row;decorateRow(row,route)}},0)}
  new MutationObserver(()=>enrichMessages()).observe(messages,{childList:true,subtree:true});
  enrichMessages();

  window.__AURA_SHARED_EVENT_SUBSCRIBERS__=window.__AURA_SHARED_EVENT_SUBSCRIBERS__||{};
  window.__AURA_SHARED_EVENT_SUBSCRIBERS__.quality=true;
  window.addEventListener('aura:hub-event',e=>{
    const ev=e.detail||{};
    const t=String(ev.type||''),d=ev.data||{};
    if(t==='user_message'){
      turnActive=true;turnRoute=null;lastAuraRow=null;documentCompletedSeen=false;
      turnKind=documentTurnHint(d.text)?'document':'';
      if(turnKind==='document')showActivity('Préparation du document','Analyse de la demande',12,null,'DOCUMENT');
    }
    else if(t==='provider'){
      turnRoute={provider:d.provider||'',model:d.model||''};
      if(turnActive){
        if(turnKind==='document')showActivity('Route documentaire','Sélection du moteur d’analyse',34,turnRoute,'DOCUMENT');
        else showActivity('Génération de la réponse','Route IA active',44,turnRoute,'AI');
      }
    }
    else if(t==='llm.route'){
      turnRoute={provider:d.provider||'',model:d.model||''};
      // P0.6.2.4.1 — do not let generic LLM telemetry overwrite the
      // specialised document pipeline HUD.
      if(turnKind==='document'){
        showActivity('Analyse IA du document','Génération de la réponse',56,turnRoute,'DOCUMENT');
      }else{
        turnKind='llm';
        showActivity('Génération de la réponse',d.voice?'Réponse vocale + affichage':'Réponse texte',46,turnRoute,'AI');
      }
    }
    else if(t==='llm.failover'){
      turnRoute={provider:d.to||'',model:d.model||''};
      if(turnKind==='document'){
        showActivity('Bascule documentaire',`${String(d.from||'').toUpperCase()} → ${String(d.to||'').toUpperCase()}`,58,turnRoute,'FAILOVER');
      }else{
        turnKind='llm';
        showActivity('Bascule du fournisseur',`${String(d.from||'').toUpperCase()} → ${String(d.to||'').toUpperCase()}`,52,turnRoute,'FAILOVER');
      }
    }
    else if(t==='llm.completed'){
      turnRoute={provider:d.provider||'',model:d.model||''};
      if(turnKind==='document'){
        showActivity('Analyse reçue','Construction de la réponse',82,turnRoute,'DOCUMENT');
      }else{
        completeActivity('Réponse prête',`${Number(d.latency_seconds||0).toFixed(1)} s · ${Number(d.chars||0)} caractères`);
      }
    }
    else if(t==='llm.error'){failActivity(`${String(d.provider||'IA').toUpperCase()} · ${d.error||'erreur'}`)}
    else if(t==='file.loading'){documentActive=true;turnKind='document';showActivity('Chargement du document',d.name||'Pièce jointe',10,null,'FILE')}
    else if(t==='file.ready'){documentActive=!!d.active||true;showActivity('Document prêt',d.name||'Extraction terminée',24,null,'FILE',800)}
    else if(t==='file.cleared'){documentActive=false;if(turnKind==='document')turnKind='';}
    else if(t==='file.error'){documentActive=false;failActivity(d.message||d.error||'Document impossible à charger')}
    else if(t==='document.analysis'){
      turnKind='document';
      if(d.provider||d.model)turnRoute={provider:d.provider||'',model:d.model||''};
      const stage=String(d.stage||'').toLowerCase();
      const labels={preparing:['Préparation du document','Extraction et contexte'],routing:['Route documentaire',d.native?'PDF natif · analyse visuelle':'Contexte texte sélectionné'],generating:['Analyse IA du document','Génération de la réponse'],streaming:['Analyse reçue','Construction de la réponse'],completed:['Analyse terminée',`${Number(d.latency_seconds||0).toFixed(1)} s`],error:['Analyse impossible',d.message||d.error||'Erreur document']};
      const pair=labels[stage]||['Analyse du document',stage];
      if(stage==='completed'){documentCompletedSeen=true;completeActivity(pair[0],pair[1]);}
      else if(stage==='error')failActivity(pair[1]);
      else showActivity(pair[0],pair[1],Number(d.progress||50),turnRoute,'DOCUMENT');
    }
    else if(t==='research.started'){turnKind='research';turnRoute={provider:'WEB',model:d.engine||'free-web-search'};showActivity('Recherche Web','Préparation de la requête',16,turnRoute,'RESEARCH')}
    else if(t==='research.searching'){showActivity('Recherche Web','Interrogation des moteurs gratuits',42,turnRoute,'RESEARCH')}
    else if(t==='research.sources'){showActivity('Sources trouvées',`${(d.sources||[]).length} source(s) collectée(s)`,70,turnRoute,'RESEARCH')}
    else if(t==='research.completed'){
      const backend=d.backend_label||d.backend||'Web';turnRoute={provider:'WEB',model:backend};
      if(lastAuraRow)decorateRow(lastAuraRow,turnRoute);else decorateLatest(turnRoute);
      completeActivity('Recherche terminée',`${Number(d.item_count||0)} résultat(s) · ${d.synthesis||'synthèse'}`);
    }
    else if(t==='research.error'){failActivity('Recherche Web indisponible')}
    else if(t==='state'&&turnActive){
      const s=String(d.state||'').toUpperCase();
      if(s==='THINKING'&&!turnKind)showActivity('AURA réfléchit','Analyse de la demande',28,turnRoute,'THINKING');
      else if(s==='ANALYZING'&&!turnKind)showActivity('Analyse en cours','Traitement local / IA',48,turnRoute,'ANALYZING');
      else if(s==='SEARCHING'&&!turnKind)showActivity('Recherche en cours','Collecte de sources',42,turnRoute,'SEARCHING');
    }
    else if(t==='aura_message'){
      decorateLatest(turnRoute);
      if(turnActive){
        if(turnKind==='document'&&!documentCompletedSeen)completeActivity('Analyse terminée','Réponse documentaire prête');
        else if(!['research','document'].includes(turnKind))completeActivity('Réponse prête','');
      }
      turnActive=false;
    }
    else if(t==='error'&&turnActive){failActivity(d.text||'Erreur du Core');turnActive=false}
  });
})();
