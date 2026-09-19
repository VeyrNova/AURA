/* AURA P0.6.2.6 — Memory Control Center */
(()=>{
  'use strict';
  const token=new URLSearchParams(location.search).get('token')||'';
  if(!token)return;
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const norm=v=>String(v??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  const toast=msg=>{const t=$('#toast');if(!t)return;t.textContent=msg;t.classList.add('show');clearTimeout(toast.t);toast.t=setTimeout(()=>t.classList.remove('show'),2600)};
  async function command(action,payload={}){
    const r=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action,...payload})});
    let d={};try{d=await r.json()}catch{}
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
    return d;
  }
  async function getMemory(sensitive=false){
    const r=await fetch(`/api/memory?token=${encodeURIComponent(token)}&sensitive=${sensitive?1:0}`,{cache:'no-store'});
    const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;
  }

  async function speakMemory(text){
    const clean=String(text||'').replace(/\s+/g,' ').trim().slice(0,500);
    if(!clean)return;
    try{await command('voice_speak',{text:clean,source:'memory-feedback'})}
    catch(_){/* Voice feedback is non-blocking; MEM management must still work. */}
  }

  const memBtn=$$('.rail .rail-btn').find(b=>/^MEM$/i.test(String($('small',b)?.textContent||'').trim()));
  const workspace=$('.workspace');
  if(!memBtn||!workspace)return;
  memBtn.classList.remove('locked');
  memBtn.id='memoryBtn';
  memBtn.title='Mémoire locale AURA';

  const drawer=document.createElement('section');
  drawer.className='aura-p0626-memory glass';
  drawer.innerHTML=`
    <header>
      <div><span>MEMORY CORE</span><small>Long-term local context</small></div>
      <button data-close aria-label="Fermer">×</button>
    </header>
    <div class="aura-p0626-status">
      <div><small>SOUVENIRS</small><b data-count>—</b></div>
      <div><small>MODE</small><b data-mode>—</b></div>
      <div><small>CAPTURE</small><b data-auto>—</b></div>
    </div>
    <div class="aura-p0626-toolbar">
      <input data-search maxlength="160" placeholder="Rechercher dans la mémoire…">
      <label><input type="checkbox" data-sensitive> <span>SENSIBLES</span></label>
    </div>
    <form class="aura-p0626-add" data-add>
      <textarea name="content" maxlength="1800" placeholder="Ajouter un souvenir explicite…" required></textarea>
      <div>
        <select name="type">
          <option value="">AUTO</option><option value="fact">FAIT</option><option value="preference">PRÉFÉRENCE</option>
          <option value="project">PROJET</option><option value="goal">OBJECTIF</option><option value="habit">HABITUDE</option>
        </select>
        <select name="importance">
          <option value="3">IMPORTANCE 3</option><option value="1">IMPORTANCE 1</option><option value="2">IMPORTANCE 2</option>
          <option value="4">IMPORTANCE 4</option><option value="5">IMPORTANCE 5</option>
        </select>
        <button>RETENIR</button>
      </div>
    </form>
    <section class="aura-p0626-context">
      <div class="aura-p0626-section-title"><span>CONTEXTE RÉCENT</span><small>Mémoires injectées récemment</small></div>
      <div data-context></div>
    </section>
    <section class="aura-p0626-records">
      <div class="aura-p0626-section-title"><span>MÉMOIRE PERSISTANTE</span><small data-visible>—</small></div>
      <div data-list><div class="aura-p0626-empty">Synchronisation du Core…</div></div>
    </section>
    <footer>
      <button data-private>MODE PRIVÉ</button>
      <button class="danger" data-clear>EFFACER LE PROFIL</button>
      <small>Local SQLite · Les souvenirs sensibles sont masqués par défaut.</small>
    </footer>`;
  workspace.appendChild(drawer);

  let snapshot={records:[],context:[]},showSensitive=false,query='';
  const typeLabel=t=>({fact:'FAIT',preference:'PRÉF.',project:'PROJET',goal:'OBJECTIF',habit:'HABITUDE'}[String(t||'').toLowerCase()]||String(t||'FAIT').toUpperCase());
  const fmt=v=>{if(!v)return'';const d=new Date(v);return Number.isNaN(+d)?String(v):d.toLocaleString('fr-FR',{dateStyle:'short',timeStyle:'short'})};

  function row(r,context=false){
    const sensitive=r.is_sensitive?'<i class="sensitive">SENSIBLE</i>':'';
    return `<article class="aura-p0626-row ${context?'context':''}">
      <div class="meta"><span>${esc(typeLabel(r.type))}</span>${sensitive}<b>${'◆'.repeat(Math.max(1,Math.min(5,Number(r.importance)||1)))}</b></div>
      <p data-read="${Number(r.id)||0}" title="Double-cliquer pour écouter ce souvenir">${esc(r.content||'')}</p>
      <small>${esc(r.source_label||r.source||'local')}${r.created_at?` · ${esc(fmt(r.created_at))}`:''}${r.access_count?` · utilisé ${Number(r.access_count)}×`:''}</small>
      ${context?'':`<button data-delete="${Number(r.id)||0}" title="Oublier ce souvenir">×</button>`}
    </article>`;
  }

  function render(){
    $('[data-count]',drawer).textContent=String(snapshot.count??0);
    $('[data-mode]',drawer).textContent=snapshot.private_mode?'PRIVÉ':'NORMAL';
    $('[data-mode]',drawer).classList.toggle('private',!!snapshot.private_mode);
    $('[data-auto]',drawer).textContent=snapshot.private_mode?'SUSPENDUE':(snapshot.auto_capture?'ACTIVE':'OFF');
    const privateBtn=$('[data-private]',drawer);
    privateBtn.textContent=snapshot.private_mode?'QUITTER LE MODE PRIVÉ':'MODE PRIVÉ';
    $('.aura-p0626-add textarea',drawer).disabled=!!snapshot.private_mode;
    $('.aura-p0626-add button',drawer).disabled=!!snapshot.private_mode;

    const ctx=(snapshot.context||[]);
    $('[data-context]',drawer).innerHTML=ctx.length?ctx.map(x=>row(x,true)).join(''):'<div class="aura-p0626-empty compact">Aucun souvenir injecté récemment.</div>';

    const q=norm(query.trim());
    const records=(snapshot.records||[]).filter(r=>!q||norm(`${r.content} ${r.type} ${r.source_label}`).includes(q));
    $('[data-visible]',drawer).textContent=`${records.length} affiché${records.length>1?'s':''}`;
    $('[data-list]',drawer).innerHTML=records.length?records.map(x=>row(x,false)).join(''):'<div class="aura-p0626-empty">Aucun souvenir correspondant.</div>';
    $$('[data-read]',drawer).forEach(p=>p.addEventListener('dblclick',()=>{
      const id=Number(p.dataset.read||0);
      const memory=(snapshot.records||[]).find(r=>Number(r.id)===id);
      if(memory?.content)speakMemory(String(memory.content));
    }));
    $$('[data-delete]',drawer).forEach(b=>b.addEventListener('click',async()=>{
      if(!confirm('Oublier ce souvenir de la mémoire locale AURA ?'))return;
      try{
        await command('memory_delete',{id:Number(b.dataset.delete)});
        speakMemory("D'accord. J'oublie ce souvenir.");
        setTimeout(refresh,80);
      }catch(e){toast(`Mémoire · ${e.message}`)}
    }));
  }

  function workspaceActivity(state,label,detail=''){
    window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
      detail:{workspace:'memory',state,label,detail}
    }));
  }
  async function refresh(){
    workspaceActivity('loading','Synchronisation','Mémoire locale');
    try{
      snapshot=await getMemory(showSensitive);
      render();
      workspaceActivity('ready','Mémoire synchronisée',`${Number(snapshot.count||0)} souvenir(s)`);
    }catch(e){
      $('[data-list]',drawer).innerHTML=`<div class="aura-p0626-empty">Core indisponible · ${esc(e.message)}</div>`;
      workspaceActivity('error','Mémoire indisponible',String(e.message||'Erreur MEM'));
    }
  }
  window.addEventListener('aura:workspace-refresh',event=>{
    if(String(event.detail?.workspace||'')==='memory'){refresh();}
  });

  const close=()=>{drawer.classList.remove('open');memBtn.classList.remove('active')};
  memBtn.addEventListener('click',()=>{
    const opening=!drawer.classList.contains('open');
    $('.aura-p0623-drawer')?.classList.remove('open');
    $('.aura-p0623-productivity-btn')?.classList.remove('active');
    drawer.classList.toggle('open',opening);memBtn.classList.toggle('active',opening);
    if(opening)refresh();
  });
  $('[data-close]',drawer).addEventListener('click',close);
  $('#homeBtn')?.addEventListener('click',close);
  $('#talkBtn')?.addEventListener('click',close);
  $('.aura-p0623-productivity-btn')?.addEventListener('click',close);
  $('[data-search]',drawer).addEventListener('input',e=>{query=e.target.value||'';render()});
  $('[data-sensitive]',drawer).addEventListener('change',e=>{showSensitive=!!e.target.checked;refresh()});

  $('[data-add]',drawer).addEventListener('submit',async e=>{
    e.preventDefault();
    // P0.6.2.6.1 — Event.currentTarget becomes null after an awaited promise
    // in browsers. Keep the form reference before awaiting the Core command.
    const form=e.currentTarget;
    const f=new FormData(form);
    try{
      const content=String(f.get('content')||'').trim();
      await command('memory_create',{content,memory_type:f.get('type')||'',importance:Number(f.get('importance')||3)});
      form.reset();
      speakMemory(`D'accord. Je retiens que ${content}`);
      setTimeout(refresh,80);
    }catch(err){
      toast(`Mémoire · ${err.message==='private_mode'?'mode privé actif':err.message}`);
    }
  });
  $('[data-private]',drawer).addEventListener('click',async()=>{
    const enable=!snapshot.private_mode;
    try{
      await command('memory_private',{enabled:enable});
      speakMemory(enable
        ?"Mode privé activé. Je suspends la mémorisation jusqu'à sa désactivation."
        :"Mode privé désactivé. Ma mémoire est de nouveau active.");
      setTimeout(refresh,80);
    }catch(e){toast(`Mémoire · ${e.message}`)}
  });
  $('[data-clear]',drawer).addEventListener('click',async()=>{
    const confirmText=prompt('Cette action efface les souvenirs, la continuité de session et les préférences relationnelles.\\n\\nTape EFFACER pour confirmer :','');
    if(String(confirmText||'').trim().toUpperCase()!=='EFFACER')return;
    try{
      await command('memory_clear_profile',{confirm:'EFFACER'});
      speakMemory("Le profil mémoire a été effacé.");
      setTimeout(refresh,100);
    }catch(e){toast(`Mémoire · ${e.message}`)}
  });

  window.__AURA_SHARED_EVENT_SUBSCRIBERS__=window.__AURA_SHARED_EVENT_SUBSCRIBERS__||{};
  window.__AURA_SHARED_EVENT_SUBSCRIBERS__.memory=true;
  window.addEventListener('aura:hub-event',e=>{const ev=e.detail||{};
    if(/^memory\./.test(String(ev.type||''))&&drawer.classList.contains('open'))setTimeout(refresh,50);
  });
})();
