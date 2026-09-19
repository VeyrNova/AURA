/* AURA P0.6.2.3 — File + Productivity Three.js Exposure */
(()=>{
  'use strict';
  const qs=new URLSearchParams(location.search), token=qs.get('token')||'';
  if(!token)return;
  const $=(s,r=document)=>r.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const toast=msg=>{const t=$('#toast');if(!t)return;t.textContent=msg;t.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove('show'),2600)};
  async function command(action,payload={}){const r=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})});let d={};try{d=await r.json()}catch{}if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d}
  async function get(path){const r=await fetch(`${path}?token=${encodeURIComponent(token)}`,{cache:'no-store'});const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d}

  // Attachment control: reuse the existing RC4.2 '+' placeholder.
  const attach=$('.composer .attach'), composer=$('#composer');
  let chip=null,fileInput=null;
  if(attach&&composer){
    attach.classList.remove('disabled');attach.removeAttribute('aria-disabled');attach.title='Joindre un document à AURA';
    fileInput=document.createElement('input');fileInput.type='file';fileInput.hidden=true;
    fileInput.accept='.pdf,.docx,.pptx,.xlsx,.txt,.md,.log,.py,.json,.csv,.tsv,.xml,.yaml,.yml,.ini,.cfg,.toml,.html,.htm';
    document.body.appendChild(fileInput);
    chip=document.createElement('div');chip.className='aura-p0623-file-chip';chip.hidden=true;composer.appendChild(chip);
    attach.addEventListener('click',()=>fileInput.click());
    fileInput.addEventListener('change',async()=>{const file=fileInput.files?.[0];fileInput.value='';if(!file)return;chip.hidden=false;chip.innerHTML=`<span>◈</span><b>${esc(file.name)}</b><small>ENVOI…</small><button title="Retirer">×</button>`;try{const r=await fetch(`/api/files/upload?token=${encodeURIComponent(token)}`,{method:'POST',headers:{'Content-Type':'application/octet-stream','X-AURA-Filename':encodeURIComponent(file.name),'X-AURA-Mime':file.type||'application/octet-stream'},body:file});const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);toast(`Document transmis · ${file.name}`)}catch(e){chip.hidden=true;toast(`Document refusé · ${e.message}`)}});
    chip.addEventListener('click',e=>{if(e.target.tagName==='BUTTON')command('file_clear').catch(()=>{});});
  }
  function applyFile(d){if(!chip)return;if(d.active){chip.hidden=false;chip.innerHTML=`<span>◈</span><b>${esc(d.name||'Document')}</b><small>${esc(d.meta||'PRÊT')}</small><button title="Retirer">×</button>`}else chip.hidden=true}
  get('/api/files/status').then(applyFile).catch(()=>{});

  // Productivity rail entry + native AURA drawer.
  const rail=$('.rail'), talk=$('#talkBtn');let drawer=null,prodBtn=null,currentTab='tasks';
  if(rail&&talk){
    prodBtn=document.createElement('button');prodBtn.className='rail-btn aura-p0623-productivity-btn';prodBtn.title='Tâches, rappels et notes';prodBtn.innerHTML='<span>✓</span><small>PLAN</small>';talk.insertAdjacentElement('afterend',prodBtn);
    drawer=document.createElement('section');drawer.className='aura-p0623-drawer glass';drawer.innerHTML=`
      <header><div><span>PRODUCTIVITY CORE</span><small>Tasks · Reminders · Notes</small></div><button data-close>×</button></header>
      <nav><button data-tab="tasks" class="active">TÂCHES</button><button data-tab="reminders">RAPPELS</button><button data-tab="notes">NOTES</button></nav>
      <div class="aura-p0623-content"><div class="aura-p0623-loading">Synchronisation du Core…</div></div>`;
    $('.workspace').appendChild(drawer);
    const close=()=>{drawer.classList.remove('open');prodBtn.classList.remove('active')};
    prodBtn.addEventListener('click',()=>{drawer.classList.toggle('open');prodBtn.classList.toggle('active',drawer.classList.contains('open'));if(drawer.classList.contains('open'))refresh()});
    $('[data-close]',drawer).addEventListener('click',close);$('#homeBtn')?.addEventListener('click',close);$('#talkBtn')?.addEventListener('click',close);
    drawer.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{currentTab=b.dataset.tab;drawer.querySelectorAll('[data-tab]').forEach(x=>x.classList.toggle('active',x===b));refresh()}));
  }
  let snapshot={tasks:[],reminders:[],notes:[]};
  const fmtDate=v=>{if(!v)return'—';const d=new Date(v);return Number.isNaN(+d)?String(v):d.toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'short'})};
  function render(){if(!drawer)return;const c=$('.aura-p0623-content',drawer);if(currentTab==='tasks'){
      const rows=(snapshot.tasks||[]).map(x=>`<div class="aura-p0623-row"><div><b>${esc(x.title||'Tâche')}</b><small>${esc(x.status||'TODO')} · ${esc(fmtDate(x.due_date))}</small></div>${String(x.status)!=='DONE'?`<button data-task-complete="${Number(x.id)||0}">✓</button>`:''}</div>`).join('')||'<div class="aura-p0623-empty">Aucune tâche active.</div>';
      c.innerHTML=`<form class="aura-p0623-form" data-form="task"><input name="title" maxlength="280" placeholder="Nouvelle tâche…" required><input name="due" type="datetime-local"><button>AJOUTER</button></form><div class="aura-p0623-list">${rows}</div>`;
    }else if(currentTab==='reminders'){
      const rows=(snapshot.reminders||[]).map(x=>`<div class="aura-p0623-row"><div><b>${esc(x.content||'Rappel')}</b><small>${esc(fmtDate(x.trigger_at))}</small></div><button data-reminder-delete="${Number(x.id)||0}">×</button></div>`).join('')||'<div class="aura-p0623-empty">Aucun rappel actif.</div>';
      c.innerHTML=`<form class="aura-p0623-form" data-form="reminder"><input name="content" maxlength="500" placeholder="Nouveau rappel…" required><input name="when" type="datetime-local" required><button>AJOUTER</button></form><div class="aura-p0623-list">${rows}</div>`;
    }else{
      const rows=(snapshot.notes||[]).map(x=>`<div class="aura-p0623-row note"><div><b>${esc(x.title||'Note')}</b><small>${esc(String(x.content||'').slice(0,180))}</small></div><button data-note-delete="${Number(x.id)||0}">×</button></div>`).join('')||'<div class="aura-p0623-empty">Aucune note.</div>';
      c.innerHTML=`<form class="aura-p0623-form notes" data-form="note"><input name="title" maxlength="220" placeholder="Titre (optionnel)"><textarea name="content" maxlength="8000" placeholder="Écrire une note…" required></textarea><button>ENREGISTRER</button></form><div class="aura-p0623-list">${rows}</div>`;
    }
    wireContent(c);
  }
  function wireContent(c){
    c.querySelector('[data-form="task"]')?.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await command('task_create',{title:f.get('title'),due_date:f.get('due')||''});toast('Tâche créée');setTimeout(refresh,80)}catch(err){toast(`Tâche · ${err.message}`)}});
    c.querySelector('[data-form="reminder"]')?.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await command('reminder_create',{content:f.get('content'),trigger_at:f.get('when')});toast('Rappel créé');setTimeout(refresh,80)}catch(err){toast(`Rappel · ${err.message}`)}});
    c.querySelector('[data-form="note"]')?.addEventListener('submit',async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{await command('note_create',{title:f.get('title')||'',content:f.get('content')});toast('Note enregistrée');setTimeout(refresh,80)}catch(err){toast(`Note · ${err.message}`)}});
    c.querySelectorAll('[data-task-complete]').forEach(b=>b.addEventListener('click',async()=>{try{await command('task_complete',{identifier:b.dataset.taskComplete});toast('Tâche terminée');setTimeout(refresh,80)}catch(e){toast(`Tâche · ${e.message}`)}}));
    c.querySelectorAll('[data-reminder-delete]').forEach(b=>b.addEventListener('click',async()=>{try{await command('reminder_delete',{id:Number(b.dataset.reminderDelete)});setTimeout(refresh,80)}catch(e){toast(`Rappel · ${e.message}`)}}));
    c.querySelectorAll('[data-note-delete]').forEach(b=>b.addEventListener('click',async()=>{try{await command('note_delete',{id:Number(b.dataset.noteDelete)});setTimeout(refresh,80)}catch(e){toast(`Note · ${e.message}`)}}));
  }
  function workspaceActivity(state,label,detail=''){
    window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
      detail:{workspace:'plan',state,label,detail}
    }));
  }
  async function refresh(){
    workspaceActivity('loading','Synchronisation','Tâches · rappels · notes');
    try{
      snapshot=await get('/api/productivity');
      render();
      workspaceActivity('ready','Synchronisé',`${(snapshot.tasks||[]).length} tâche(s) · ${(snapshot.reminders||[]).length} rappel(s)`);
    }catch(e){
      if(drawer)$('.aura-p0623-content',drawer).innerHTML=`<div class="aura-p0623-empty">Core indisponible · ${esc(e.message)}</div>`;
      workspaceActivity('error','Core indisponible',String(e.message||'Erreur PLAN'));
    }
  }

  window.addEventListener('aura:workspace-refresh',event=>{
    if(String(event.detail?.workspace||'')==='plan'){refresh();}
  });

  // P0.8.5.4.7.6.1.4 — shared browser event bus; no extra SSE connection.
  window.__AURA_SHARED_EVENT_SUBSCRIBERS__=window.__AURA_SHARED_EVENT_SUBSCRIBERS__||{};
  window.__AURA_SHARED_EVENT_SUBSCRIBERS__.files=true;
  window.addEventListener('aura:hub-event',e=>{const ev=e.detail||{};const t=String(ev.type||''),d=ev.data||{};
    if(t==='file.loading'&&chip){chip.hidden=false;chip.innerHTML=`<span>◈</span><b>${esc(d.name||'Document')}</b><small>EXTRACTION…</small><button title="Retirer">×</button>`}
    else if(t==='file.ready'){applyFile(d);toast(`Document prêt · ${d.name||''}`)}
    else if(t==='file.cleared'){applyFile({active:false});toast('Document retiré')}
    else if(t==='file.error'){applyFile({active:false});toast(`Document · ${d.message||d.error||'analyse impossible'}`)}
    else if(/^(task|reminder|note|productivity)\./.test(t)){if(drawer?.classList.contains('open'))setTimeout(refresh,40)}
  });
})();
