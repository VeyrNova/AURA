(()=>{
  'use strict';
  if(window.__AURA_ROADMAP_V25E1__)return;
  window.__AURA_ROADMAP_V25E1__=true;

  const token=new URLSearchParams(location.search).get('token')||'';
  const API=`/api/roadmap?token=${encodeURIComponent(token)}`;
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmtDate=v=>{
    const s=String(v||'').trim(),m=s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    return m?`${m[3]}/${m[2]}/${m[1]}`:(s||'—');
  };
  const pct=v=>Number.isFinite(Number(v))?`${Number(v).toFixed(1).replace('.0','')}%`:'—';
  const statusLabels={done:'TERMINÉ',planned:'PLANIFIÉ',in_progress:'EN COURS',blocked:'BLOQUÉ',archived:'ARCHIVÉ',deleted:'SUPPRIMÉ',cancelled:'ANNULÉ'};
  const statusClass=s=>`is-${String(s||'planned').replace(/_/g,'-')}`;
  const activeLife=m=>!(m?.lifecycle?.archived||m?.lifecycle?.deleted||m?.lifecycle?.cancelled);

  const state={data:null,query:'',status:'all',phase:'all',showArchived:false,editing:null,loading:false};

  const root=document.createElement('section');
  root.id='aura-roadmap-workspace-v25e';
  root.className='aura-roadmap-v25e glass';
  root.setAttribute('aria-label','AURA Roadmap');
  root.innerHTML=`
    <header class="aura-roadmap-v25e__header">
      <div>
        <small>AURA LIVE · PILOTAGE PROJET</small>
        <h2>AURA ROADMAP</h2>
        <p>Baseline historique, prévision dynamique et édition sécurisée.</p>
      </div>
      <div class="aura-roadmap-v25e__header-actions">
        <span class="aura-roadmap-v25e__bridge" data-roadmap-bridge>CONNEXION…</span>
        <button type="button" data-roadmap-refresh>↻ ACTUALISER</button>
        <button type="button" class="is-primary" data-roadmap-add>＋ AJOUTER UNE ÉTAPE</button>
        <button type="button" data-roadmap-history>HISTORIQUE</button>
        <button type="button" data-roadmap-close>FERMER</button>
      </div>
    </header>
    <div class="aura-roadmap-v25e__summary" data-roadmap-summary></div>
    <div class="aura-roadmap-v25e__toolbar">
      <input type="search" data-roadmap-search placeholder="Rechercher une étape, une version, une phase…" />
      <select data-roadmap-status>
        <option value="all">Tous les statuts</option>
        <option value="in_progress">En cours</option>
        <option value="planned">Planifié</option>
        <option value="done">Terminé</option>
        <option value="blocked">Bloqué</option>
        <option value="archived">Archivé</option>
      </select>
      <select data-roadmap-phase><option value="all">Toutes les phases</option></select>
      <label><input type="checkbox" data-roadmap-archived /> Afficher archivées / supprimées</label>
    </div>
    <div class="aura-roadmap-v25e__content" data-roadmap-content>
      <div class="aura-roadmap-v25e__loading">Chargement de la roadmap…</div>
    </div>
    <div class="aura-roadmap-v25e__modal" data-roadmap-modal hidden></div>
    <div class="aura-roadmap-v25e__toast" data-roadmap-toast hidden></div>
  `;

  function hero(){
    return $('.workspace > .hero')||$('.hero')||$('.workspace')||document.body;
  }
  hero().appendChild(root);

  function toast(message,type='ok'){
    const el=$('[data-roadmap-toast]',root);
    el.textContent=String(message||'');
    el.dataset.type=type;el.hidden=false;
    clearTimeout(toast.t);toast.t=setTimeout(()=>el.hidden=true,2600);
  }

  async function request(method='GET',payload=null){
    const init={method,cache:'no-store',headers:{}};
    if(payload){init.headers['Content-Type']='application/json';init.body=JSON.stringify(payload)}
    const r=await fetch(API,init);
    let data={};
    try{data=await r.json()}catch(_){}
    if(!r.ok||data?.ok===false)throw new Error(data?.error||data?.message||`HTTP ${r.status}`);
    return data;
  }

  function setBridge(ok,text){
    const el=$('[data-roadmap-bridge]',root);
    el.classList.toggle('is-ok',!!ok);
    el.classList.toggle('is-error',!ok);
    el.textContent=text;
  }

  async function load({quiet=false}={}){
    if(state.loading)return;
    state.loading=true;
    if(!quiet)$('[data-roadmap-content]',root).innerHTML='<div class="aura-roadmap-v25e__loading">Synchronisation RoadmapService…</div>';
    try{
      const data=await request('GET');
      state.data=data;
      setBridge(true,'ÉDITION CONNECTÉE');
      render();
      try{
        const probe=await request('POST',{operation:'validate',actor:'roadmap-ui-v25e'});
        if(probe?.ok)setBridge(true,'ÉDITION CONNECTÉE');
      }catch(e){setBridge(false,'LECTURE SEULE');toast(`Bridge édition: ${e.message}`,'error')}
    }catch(e){
      setBridge(false,'INDISPONIBLE');
      $('[data-roadmap-content]',root).innerHTML=`<div class="aura-roadmap-v25e__error">Roadmap indisponible · ${esc(e.message)}</div>`;
    }finally{state.loading=false}
  }

  function summary(){
    const p=state.data?.schedule?.project||{};
    const s=state.data?.schedule?.scope||{};
    const variance=Number(p.schedule_variance_days);
    const varianceLabel=Number.isFinite(variance)?(variance>0?`${variance} j d'avance`:variance<0?`${Math.abs(variance)} j de retard`:'dans les temps'):'—';
    return `
      <article><span>PROGRESSION</span><strong>${pct(p.actual_total_progress_percent)}</strong><small>pondérée</small></article>
      <article><span>FIN ESTIMÉE</span><strong>${fmtDate(p.forecast_finish)}</strong><small>cible ${fmtDate(p.baseline_finish)}</small></article>
      <article class="${variance<0?'is-late':'is-ahead'}"><span>PLANNING</span><strong>${esc(varianceLabel)}</strong><small>earned schedule</small></article>
      <article><span>CONFIANCE</span><strong>${pct(p.confidence_percent)}</strong><small>${esc(p.confidence_label||'')}</small></article>
      <article><span>PÉRIMÈTRE AJOUTÉ</span><strong>${Number(s.added_scope_count||0)}</strong><small>${Number(s.added_scope_remaining_workload_days||0)} j charge restante</small></article>
    `;
  }

  function filtered(){
    const rows=[...(state.data?.roadmap?.milestones||[])];
    const q=state.query.toLowerCase();
    return rows.filter(m=>{
      const life=activeLife(m);
      if(!state.showArchived&&!life)return false;
      const st=String(m?.forecast?.status||'planned');
      if(state.status!=='all'&&st!==state.status)return false;
      if(state.phase!=='all'&&String(m.phase||'Unassigned')!==state.phase)return false;
      if(q){
        const hay=[m.id,m.phase,m.version,m.title,m.description].join(' ').toLowerCase();
        if(!hay.includes(q))return false;
      }
      return true;
    });
  }

  function renderPhaseSelect(){
    const select=$('[data-roadmap-phase]',root);
    const phases=state.data?.phases||[];
    const current=state.phase;
    select.innerHTML='<option value="all">Toutes les phases</option>'+phases.map(p=>`<option value="${esc(p)}">${esc(p)}</option>`).join('');
    select.value=phases.includes(current)?current:'all';
    state.phase=select.value;
  }

  function milestoneRow(m,index,all){
    const st=String(m?.forecast?.status||'planned');
    const life=m.lifecycle||{};
    const locked=!(m?.baseline?.status==='not_in_baseline'||m?.baseline?.status==='not_in_2026_08_30_baseline'||(!m?.baseline?.start&&!m?.baseline?.end));
    const dep=(m.dependencies||[]).join(', ')||'—';
    return `<article class="aura-roadmap-v25e__milestone ${statusClass(st)} ${!activeLife(m)?'is-inactive':''}" data-mid="${esc(m.id)}">
      <div class="aura-roadmap-v25e__milestone-main">
        <div class="aura-roadmap-v25e__status-dot"></div>
        <div class="aura-roadmap-v25e__identity">
          <div><code>${esc(m.id)}</code>${m.version?`<em>${esc(m.version)}</em>`:''}<span class="aura-roadmap-v25e__status ${statusClass(st)}">${esc(statusLabels[st]||st.toUpperCase())}</span></div>
          <h4>${esc(m.title||m.id)}</h4>
          <p>${esc(m.description||'')}</p>
        </div>
        <div class="aura-roadmap-v25e__weight"><span>POIDS</span><b>${Number(m.weight||0).toFixed(2).replace(/\.00$/,'')}</b></div>
        <div class="aura-roadmap-v25e__row-progress"><span>${pct(m?.forecast?.progress_percent)}</span><progress max="100" value="${Number(m?.forecast?.progress_percent||0)}"></progress></div>
      </div>
      <div class="aura-roadmap-v25e__dates">
        <div class="${locked?'is-locked':''}"><span>BASELINE ${locked?'🔒':''}</span><b>${fmtDate(m?.baseline?.start)} → ${fmtDate(m?.baseline?.end)}</b></div>
        <div><span>FORECAST</span><b>${fmtDate(m?.forecast?.start)} → ${fmtDate(m?.forecast?.end)}</b></div>
        <div><span>RÉEL</span><b>${fmtDate(m?.actual?.start)} → ${fmtDate(m?.actual?.end)}</b></div>
        <div><span>DÉPENDANCES</span><b>${esc(dep)}</b></div>
      </div>
      <div class="aura-roadmap-v25e__actions">
        <button type="button" data-action="edit">MODIFIER</button>
        <button type="button" data-action="up" title="Monter">↑</button>
        <button type="button" data-action="down" title="Descendre">↓</button>
        ${life.archived||life.deleted?`<button type="button" data-action="restore">RESTAURER</button>`:`<button type="button" data-action="archive">ARCHIVER</button><button type="button" class="is-danger" data-action="delete">SUPPRIMER</button>`}
      </div>
    </article>`;
  }

  function render(){
    if(!state.data)return;
    $('[data-roadmap-summary]',root).innerHTML=summary();
    renderPhaseSelect();
    const rows=filtered();
    const groups=new Map();
    rows.forEach(m=>{
      const phase=String(m.phase||'Unassigned');
      if(!groups.has(phase))groups.set(phase,[]);
      groups.get(phase).push(m);
    });
    const html=[...groups.entries()].map(([phase,items])=>`
      <section class="aura-roadmap-v25e__phase" data-phase="${esc(phase)}">
        <header>
          <div><small>PHASE</small><h3>${esc(phase)}</h3><span>${items.length} étape${items.length>1?'s':''}</span></div>
          <div>
            <button type="button" data-phase-action="add">＋ ÉTAPE</button>
            <button type="button" data-phase-action="rename">RENOMMER</button>
            <button type="button" data-phase-action="archive" class="is-danger-ghost">ARCHIVER LA PHASE</button>
          </div>
        </header>
        <div>${items.map((m,i)=>milestoneRow(m,i,items)).join('')}</div>
      </section>`).join('');
    $('[data-roadmap-content]',root).innerHTML=html||'<div class="aura-roadmap-v25e__empty">Aucune étape avec ces filtres.</div>';
  }

  function openEditor(m=null,presetPhase=''){
    state.editing=m||null;
    const isNew=!m;
    const modal=$('[data-roadmap-modal]',root);
    const f=m?.forecast||{},a=m?.actual||{},b=m?.baseline||{};
    modal.hidden=false;
    modal.innerHTML=`<div class="aura-roadmap-v25e__modal-card">
      <header><div><small>${isNew?'NOUVELLE ÉTAPE':'MODIFICATION'}</small><h3>${isNew?'Ajouter une étape':esc(m.id)}</h3></div><button type="button" data-modal-close>×</button></header>
      <form data-roadmap-form>
        <div class="aura-roadmap-v25e__form-grid">
          <label>ID <input name="id" ${isNew?'':'disabled'} value="${esc(m?.id||'')}" required pattern="[A-Za-z0-9._-]{1,48}"></label>
          <label>Phase <input name="phase" value="${esc(m?.phase||presetPhase||'')}" required></label>
          <label>Version <input name="version" value="${esc(m?.version||'')}"></label>
          <label>Poids <input name="weight" type="number" min="0" max="100" step="0.05" value="${Number(m?.weight??1)}"></label>
          <label class="span-2">Titre <input name="title" value="${esc(m?.title||'')}" required></label>
          <label class="span-2">Description <textarea name="description">${esc(m?.description||'')}</textarea></label>
          <label>Statut
            <select name="status">${['planned','in_progress','blocked','done','archived','cancelled'].map(s=>`<option value="${s}" ${String(f.status||'planned')===s?'selected':''}>${esc(statusLabels[s]||s)}</option>`).join('')}</select>
          </label>
          <label>Progression % <input name="progress" type="number" min="0" max="100" step="0.1" value="${Number(f.progress_percent||0)}"></label>
          <label>Forecast début <input name="forecast_start" type="date" value="${esc(String(f.start||'').slice(0,10))}"></label>
          <label>Forecast fin <input name="forecast_end" type="date" value="${esc(String(f.end||'').slice(0,10))}"></label>
          <label>Réel début <input name="actual_start" type="date" value="${esc(String(a.start||'').slice(0,10))}"></label>
          <label>Réel fin <input name="actual_end" type="date" value="${esc(String(a.end||'').slice(0,10))}"></label>
          <label class="span-2">Dépendances <input name="dependencies" value="${esc((m?.dependencies||[]).join(', '))}" placeholder="RM25D, D160…"></label>
          ${isNew?'':`<div class="span-2 aura-roadmap-v25e__baseline-lock"><b>BASELINE VERROUILLÉE</b><span>${fmtDate(b.start)} → ${fmtDate(b.end)}</span><small>La baseline historique ne peut pas être modifiée depuis l’éditeur.</small></div>`}
        </div>
        <footer><button type="button" data-modal-close>ANNULER</button><button type="submit" class="is-primary">ENREGISTRER</button></footer>
      </form>
    </div>`;
  }

  async function saveEditor(form){
    const fd=new FormData(form);
    const milestone={
      id:String(fd.get('id')||state.editing?.id||'').trim(),
      phase:String(fd.get('phase')||'').trim(),
      version:String(fd.get('version')||'').trim(),
      title:String(fd.get('title')||'').trim(),
      description:String(fd.get('description')||'').trim(),
      weight:Number(fd.get('weight')||1),
      dependencies:String(fd.get('dependencies')||'').split(',').map(s=>s.trim()).filter(Boolean),
      forecast:{
        status:String(fd.get('status')||'planned'),
        progress_percent:Number(fd.get('progress')||0),
        start:String(fd.get('forecast_start')||'')||null,
        end:String(fd.get('forecast_end')||'')||null
      },
      actual:{
        start:String(fd.get('actual_start')||'')||null,
        end:String(fd.get('actual_end')||'')||null
      }
    };
    const payload=state.editing
      ?{operation:'update_milestone',milestone_id:state.editing.id,patch:milestone,actor:'roadmap-ui-v25e',reason:'Modification depuis AURA Roadmap'}
      :{operation:'add_milestone',milestone,actor:'roadmap-ui-v25e',reason:'Ajout depuis AURA Roadmap'};
    try{
      const data=await request('POST',payload);
      state.data=data;$('[data-roadmap-modal]',root).hidden=true;render();toast(state.editing?'Étape mise à jour':'Étape ajoutée');
    }catch(e){toast(e.message,'error')}
  }

  async function mutate(payload,success){
    try{
      const data=await request('POST',{...payload,actor:'roadmap-ui-v25e'});
      state.data=data;render();toast(success||'Roadmap mise à jour');
    }catch(e){toast(e.message,'error')}
  }

  function showHistory(){
    const modal=$('[data-roadmap-modal]',root);
    const revs=state.data?.revisions||[];
    modal.hidden=false;
    modal.innerHTML=`<div class="aura-roadmap-v25e__modal-card is-history">
      <header><div><small>ROADMAP REVISIONS</small><h3>Historique des modifications</h3></div><button type="button" data-modal-close>×</button></header>
      <div class="aura-roadmap-v25e__history">${revs.map(r=>`<article><div><b>${esc(r.operation||'revision')}</b><span>${esc(r.captured_at||'')}</span><small>${esc(r.actor||'')} · ${esc(r.reason||'')}</small></div><button type="button" data-revision="${esc(r.revision_id)}">RESTAURER</button></article>`).join('')||'<p>Aucune révision.</p>'}</div>
    </div>`;
  }

  function ensureOpenButton(){
    const card=$('#aura-project-active-v130,.aura-project-active-v130');
    if(!card||$('[data-roadmap-open-v25e]',card))return;
    const head=$('.aura-project-active-v130__head',card)||card;
    const btn=document.createElement('button');
    btn.type='button';btn.dataset.roadmapOpenV25e='1';btn.className='aura-roadmap-v25e__open-btn';
    btn.textContent='ROADMAP';
    btn.addEventListener('click',()=>{document.body.classList.add('aura-roadmap-editor-v25e');load()});
    head.appendChild(btn);
  }

  root.addEventListener('click',e=>{
    const target=e.target.closest('button');if(!target)return;
    if(target.matches('[data-roadmap-close]')){document.body.classList.remove('aura-roadmap-editor-v25e');return}
    if(target.matches('[data-roadmap-refresh]')){load();return}
    if(target.matches('[data-roadmap-add]')){openEditor();return}
    if(target.matches('[data-roadmap-history]')){showHistory();return}
    if(target.matches('[data-modal-close]')){$('[data-roadmap-modal]',root).hidden=true;return}
    if(target.dataset.revision){
      if(confirm('Restaurer cette révision de la roadmap ? Une nouvelle révision de sécurité sera créée.')){
        mutate({operation:'restore_revision',revision_id:target.dataset.revision,reason:'Restauration de révision depuis AURA Roadmap'},'Révision restaurée');
        $('[data-roadmap-modal]',root).hidden=true;
      } return;
    }
    const phaseEl=target.closest('[data-phase]');
    if(target.dataset.phaseAction&&phaseEl){
      const phase=phaseEl.dataset.phase;
      if(target.dataset.phaseAction==='add'){openEditor(null,phase);return}
      if(target.dataset.phaseAction==='rename'){
        const next=prompt('Nouveau nom de phase :',phase);
        if(next&&next.trim()&&next.trim()!==phase)mutate({operation:'rename_phase',old_phase:phase,new_phase:next.trim(),reason:'Renommage de phase depuis AURA Roadmap'},'Phase renommée');
        return;
      }
      if(target.dataset.phaseAction==='archive'){
        if(confirm(`Archiver toutes les étapes actives de la phase « ${phase} » ?`))mutate({operation:'archive_phase',phase,reason:'Archivage de phase depuis AURA Roadmap'},'Phase archivée');
        return;
      }
    }
    const row=target.closest('[data-mid]');if(!row)return;
    const id=row.dataset.mid;
    const all=state.data?.roadmap?.milestones||[];
    const m=all.find(x=>String(x.id)===id);if(!m)return;
    const action=target.dataset.action;
    if(action==='edit'){openEditor(m);return}
    if(action==='archive'&&confirm(`Archiver ${id} ?`)){mutate({operation:'archive_milestone',milestone_id:id,reason:'Archivage depuis AURA Roadmap'},'Étape archivée');return}
    if(action==='delete'&&confirm(`Supprimer logiquement ${id} ? Elle restera dans l’historique et pourra être restaurée.`)){mutate({operation:'delete_milestone_soft',milestone_id:id,reason:'Suppression logique depuis AURA Roadmap'},'Étape supprimée');return}
    if(action==='restore'){mutate({operation:'restore_milestone',milestone_id:id,status:'planned',reason:'Restauration depuis AURA Roadmap'},'Étape restaurée');return}
    if(action==='up'||action==='down'){
      const idx=all.findIndex(x=>String(x.id)===id);
      if(action==='up'&&idx>0)mutate({operation:'move_milestone',milestone_id:id,before_id:String(all[idx-1].id),reason:'Réorganisation depuis AURA Roadmap'},'Étape déplacée');
      if(action==='down'&&idx>=0&&idx<all.length-1)mutate({operation:'move_milestone',milestone_id:id,after_id:String(all[idx+1].id),reason:'Réorganisation depuis AURA Roadmap'},'Étape déplacée');
    }
  });

  root.addEventListener('submit',e=>{if(e.target.matches('[data-roadmap-form]')){e.preventDefault();saveEditor(e.target)}});
  $('[data-roadmap-search]',root).addEventListener('input',e=>{state.query=e.target.value;render()});
  $('[data-roadmap-status]',root).addEventListener('change',e=>{state.status=e.target.value;render()});
  $('[data-roadmap-phase]',root).addEventListener('change',e=>{state.phase=e.target.value;render()});
  $('[data-roadmap-archived]',root).addEventListener('change',e=>{state.showArchived=e.target.checked;render()});

  // AURA ROADMAP V25-E1.1 - STABLE PROJECT ACTIVE BUTTON
  // Project Active re-renders its innerHTML on each live refresh. The former
  // 700 ms polling loop re-added ROADMAP after paint, making ROADMAP / ACTIVE
  // visibly blink and exchange positions. MutationObserver runs immediately
  // after the DOM mutation and before the next browser paint.
  let roadmapButtonObserverV25E11 = null;
  function bindRoadmapButtonObserverV25E11(){
    const card=$('#aura-project-active-v130,.aura-project-active-v130');
    if(!card)return false;
    if(roadmapButtonObserverV25E11)roadmapButtonObserverV25E11.disconnect();
    ensureOpenButton();
    roadmapButtonObserverV25E11=new MutationObserver(()=>ensureOpenButton());
    roadmapButtonObserverV25E11.observe(card,{childList:true,subtree:true});
    return true;
  }
  (function waitForProjectActiveV25E11(){
    if(!bindRoadmapButtonObserverV25E11())setTimeout(waitForProjectActiveV25E11,250);
  })();
})();