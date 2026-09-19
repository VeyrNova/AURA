/* AURA P0.6.2.8.2 — SystemService Allowlist Fix */
(()=>{
  'use strict';
  const token=new URLSearchParams(location.search).get('token')||'';
  if(!token)return;
  const $=(s,r=document)=>r.querySelector(s);
  const $$=(s,r=document)=>[...r.querySelectorAll(s)];
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const rail=$('.rail'),workspace=$('.workspace');
  if(!rail||!workspace)return;
  const sysBtn=$$('.rail-btn',rail).find(b=>/^SYS$/i.test(String($('small',b)?.textContent||'').trim()));
  if(!sysBtn)return;
  sysBtn.classList.remove('locked');
  sysBtn.id='systemBtn';
  sysBtn.title='État système et sécurité AURA';

  const panel=document.createElement('section');
  panel.className='aura-p0627-system glass';
  panel.innerHTML=`
    <header>
      <div><span>DESKTOP INTELLIGENCE</span><small>v0.8.7 · Authorized Project Intelligence</small></div>
      <div class="aura-p0627-head-actions"><i data-live>SYNC</i><button data-close aria-label="Fermer">×</button></div>
    </header>
    <div class="aura-p0627-banner"><b>◆ MODE SÉCURISÉ</b><span>Applications fixes + dossiers explicitement autorisés. Aucun chemin brut n'est ouvert ou listé avant autorisation.</span></div>
    <section class="aura-p0650-desktop-contract">
      <div><small>POLICY MODEL</small><b data-desktop-policy>ALLOW / CONFIRM / DENY</b></div>
      <div><small>SAFE APP</small><b data-policy-safe>—</b></div>
      <div><small>FOLDER REGISTRY</small><b data-policy-folder-reg>—</b></div>
      <div><small>FOLDER OPEN</small><b data-policy-folder-open>—</b></div>
      <div><small>FILE READ</small><b data-policy-file-read>—</b></div>
      <div><small>LOCAL ANALYSIS</small><b data-policy-file-analysis>—</b></div>
      <div><small>PROJECT ANALYSIS</small><b data-policy-project-analysis>—</b></div>
      <div><small>RUN PROGRAM</small><b data-policy-run>—</b></div>
      <div><small>SYSTEM CHANGE</small><b data-policy-system>—</b></div>
    </section>
    <section class="aura-p0627-resources">
      <article><small>CPU</small><b data-cpu>—</b><i><em data-cpu-bar></em></i></article>
      <article><small>RAM</small><b data-ram>—</b><i><em data-ram-bar></em></i></article>
      <article><small>VRAM</small><b data-vram>—</b><i><em data-vram-bar></em></i></article>
      <article><small>DISQUE</small><b data-disk>—</b><i><em data-disk-bar></em></i></article>
    </section>
    <section class="aura-p0628-safe-actions">
      <div><span>ACTIONS LOCALES SÛRES</span><small>Allowlist fixe · aucun chemin/argument arbitraire</small></div>
      <nav>
        <button data-safe-app="calculator">◫ <b>CALCULATRICE</b></button>
        <button data-safe-app="notepad">≡ <b>BLOC-NOTES</b></button>
        <button data-safe-app="explorer">▦ <b>EXPLORATEUR</b></button>
        <button data-safe-app="paint">◇ <b>PAINT</b></button>
      </nav>
    </section>
    <section class="aura-p0651-folders">
      <div class="aura-p0651-title">
        <div><span>PROJETS / DOSSIERS AUTORISÉS</span><small>Registre explicite · métadonnées uniquement · aucune suppression</small></div>
        <b data-folder-count>0</b>
      </div>
      <div class="aura-p0651-authorize">
        <input data-folder-path type="text" spellcheck="false" placeholder="C:\\Users\\...\\MonProjet">
        <input data-folder-label type="text" maxlength="80" placeholder="Nom du projet (optionnel)">
        <button data-folder-authorize>AUTORISER</button>
      </div>
      <div class="aura-p0651-action" data-folder-action>Aucun dossier autorisé pour le moment.</div>
      <div class="aura-p0651-folder-list" data-folder-list></div>
      <div class="aura-p0651-preview">
        <div><span>APERÇU DU DOSSIER</span><small data-folder-preview-meta>Non chargé</small></div>
        <div data-folder-preview class="aura-p0651-preview-list"><i>Sélectionne LISTER sur un dossier autorisé.</i></div>
      </div>
      <div class="aura-p0652-file">
        <div><span>FICHIER AUTORISÉ · LECTURE LOCALE</span><small data-file-meta>Non chargé</small></div>
        <pre data-file-preview>Aucun contenu de fichier chargé.</pre>
      </div>
      <div class="aura-p0653-analysis">
        <div><span>INTELLIGENCE DOCUMENTAIRE LOCALE</span><small>Extractif · sans LLM · sans cloud</small></div>
        <div class="aura-p0653-controls">
          <input data-analysis-query type="text" maxlength="600" placeholder="Terme à chercher ou question contextuelle">
          <button data-analysis-mode="summary">RÉSUMER</button>
          <button data-analysis-mode="search">CHERCHER</button>
          <button data-analysis-mode="context">CONTEXTE</button>
        </div>
        <div class="aura-p0653-analysis-meta" data-analysis-meta>Aucune analyse locale.</div>
        <pre data-analysis-result>Aucun résultat.</pre>
      </div>
      <div class="aura-p0654-project">
        <div class="aura-p0654-project-title"><span>INTELLIGENCE PROJET AUTORISÉE</span><small>Multi-fichiers · provenance · direct-child uniquement</small></div>
        <div class="aura-p0654-project-controls">
          <select data-project-folder aria-label="Projet autorisé"></select>
          <input data-project-query type="text" maxlength="600" placeholder="Terme ou question multi-fichiers">
          <button data-project-mode="summary">SYNTHÈSE</button>
          <button data-project-mode="search">CHERCHER</button>
          <button data-project-mode="context">CONTEXTE</button>
        </div>
        <div class="aura-p0654-project-meta" data-project-meta>Aucune analyse projet.</div>
        <div class="aura-p0654-provenance" data-project-provenance></div>
        <pre data-project-result>Aucun résultat multi-fichiers.</pre>
      </div>
    </section>
    <div class="aura-p0627-grid">
      <section class="aura-p0627-card">
        <div class="title"><span>MACHINE</span><small>Local runtime</small></div>
        <div class="aura-p0627-kv" data-machine></div>
      </section>
      <section class="aura-p0627-card">
        <div class="title"><span>RUNTIME AURA</span><small>Resource Guardian</small></div>
        <div class="aura-p0627-kv" data-runtime></div>
      </section>
    </div>
    <section class="aura-p0627-card capabilities">
      <div class="title"><span>CAPACITÉS SÉCURISÉES</span><small>Fail-closed · permissions déterministes</small></div>
      <div data-capabilities class="aura-p0627-cap-list"><div class="aura-p0627-empty">Synchronisation…</div></div>
    </section>
    <section class="aura-p0627-card audit">
      <div class="title"><span>AUDIT SÉCURITÉ</span><small>Derniers arbitrages SecurityPolicyEngine</small></div>
      <div data-audit class="aura-p0627-audit-list"><div class="aura-p0627-empty">Aucun événement chargé.</div></div>
    </section>
    <footer><span data-permissions>Permissions locales : —</span><b>DESKTOP · AUTHORIZED PROJECT INTELLIGENCE</b></footer>`;
  workspace.appendChild(panel);

  let timer=0,active=false;
  // P0.6.5.3.2 — keep the latest SystemService desktop snapshot available
  // to event handlers. `di` inside render() is function-local.
  let latestDesktopIntelligence={};
  let selectedProjectFolderId='';
  const pct=v=>Math.max(0,Math.min(100,Number(v)||0));
  const setBar=(sel,v)=>{const e=$(sel,panel);if(e)e.style.width=`${pct(v)}%`};
  const kv=(label,value)=>`<div><small>${esc(label)}</small><b title="${esc(value)}">${esc(value||'—')}</b></div>`;
  const statusLabel=s=>({
    enabled:'ACTIF',
    locked:'VERROUILLÉ',
    blocked:'BLOQUÉ',
    'confirmation-required':'CONFIRMATION',
  }[String(s||'')]||String(s||'').toUpperCase());

  const humanSize=n=>{
    n=Number(n)||0;
    if(n<1024)return `${n} o`;
    if(n<1024*1024)return `${(n/1024).toFixed(1)} Ko`;
    if(n<1024*1024*1024)return `${(n/(1024*1024)).toFixed(1)} Mo`;
    return `${(n/(1024*1024*1024)).toFixed(1)} Go`;
  };
  const folderActionLabel=a=>({
    AUTHORIZE_FOLDER:'Autorisation',
    REVOKE_AUTHORIZED_FOLDER:'Révocation',
    LIST_AUTHORIZED_FOLDER:'Lecture métadonnées',
    OPEN_AUTHORIZED_FOLDER:'Ouverture',
  }[String(a||'')]||String(a||''));

  async function fetchStatus(){
    const r=await fetch(`/api/system?token=${encodeURIComponent(token)}`,{cache:'no-store'});
    const d=await r.json();if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;
  }
  async function action(name,payload={}){
    const r=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{
      method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action:name,...payload})
    });
    let d={};try{d=await r.json()}catch{}
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);
    return d;
  }
  function render(d){
    if(!d?.ok){$('[data-live]',panel).textContent='ERROR';return}
    const r=d.resources||{},m=d.machine||{},s=d.security||{},di=d.desktop_intelligence||{};
    latestDesktopIntelligence=di;
    const policy=di.policy||{};
    $('[data-live]',panel).textContent='LIVE';
    $('[data-desktop-policy]',panel).textContent=String(policy.model||'ALLOW_CONFIRM_DENY').replaceAll('_',' / ');
    $('[data-policy-safe]',panel).textContent=String(policy.OPEN_SAFE_APP||'—');
    $('[data-policy-folder-reg]',panel).textContent=String(policy.AUTHORIZE_FOLDER||'—');
    $('[data-policy-folder-open]',panel).textContent=String(policy.OPEN_AUTHORIZED_FOLDER||'—');
    $('[data-policy-file-read]',panel).textContent=String(policy.READ_AUTHORIZED_FILE||'—');
    $('[data-policy-file-analysis]',panel).textContent=String(policy.ANALYZE_AUTHORIZED_FILE||'—');
    $('[data-policy-project-analysis]',panel).textContent=String(policy.ANALYZE_AUTHORIZED_PROJECT||'—');
    $('[data-policy-run]',panel).textContent=String(policy.RUN_PROGRAM||'—');
    $('[data-policy-system]',panel).textContent=String(policy.MODIFY_SYSTEM||'—');
    $('[data-cpu]',panel).textContent=`${Number(r.cpu_percent||0).toFixed(0)}%`;
    $('[data-ram]',panel).textContent=`${Number(r.ram_used_pct||0).toFixed(0)}%`;
    $('[data-vram]',panel).textContent=r.vram_total_mb?`${Number(r.vram_used_pct||0).toFixed(0)}%`:'N/A';
    $('[data-disk]',panel).textContent=`${Number(r.disk_used_pct||0).toFixed(0)}%`;
    setBar('[data-cpu-bar]',r.cpu_percent);setBar('[data-ram-bar]',r.ram_used_pct);
    setBar('[data-vram-bar]',r.vram_used_pct);setBar('[data-disk-bar]',r.disk_used_pct);

    $('[data-machine]',panel).innerHTML=[
      kv('Nom',m.name),kv('OS',`${m.os||''} ${m.release||''}`.trim()),
      kv('Architecture',m.architecture),kv('Python',m.python),
      kv('CPU',m.processor||`${r.cpu_physical||0} cœurs / ${r.cpu_logical||0} threads`),
    ].join('');
    $('[data-runtime]',panel).innerHTML=[
      kv('RAM',`${Number(r.ram_available_gb||0).toFixed(1)} / ${Number(r.ram_total_gb||0).toFixed(1)} Gio libres`),
      kv('GPU',r.gpu_name||'Non détecté'),
      kv('VRAM',r.vram_total_mb?`${Math.round(r.vram_used_mb||0)} / ${Math.round(r.vram_total_mb||0)} Mio`:'Non disponible'),
      kv('Disque',`${Number(r.disk_free_gb||0).toFixed(1)} / ${Number(r.disk_total_gb||0).toFixed(1)} Gio libres`),
      kv('AURA RSS',r.aura_process_rss_mb?`${Number(r.aura_process_rss_mb).toFixed(0)} Mio`:'N/A'),
    ].join('');

    const folders=Array.isArray(di.authorized_folders)?di.authorized_folders:[];
    $('[data-folder-count]',panel).textContent=String(folders.length);
    const projectSelect=$('[data-project-folder]',panel);
    if(projectSelect){
      const valid=folders.filter(f=>f.exists);
      if(!selectedProjectFolderId||!valid.some(f=>String(f.id)===selectedProjectFolderId)){
        selectedProjectFolderId=String(valid[0]?.id||'');
      }
      projectSelect.innerHTML=valid.length
        ?valid.map(f=>`<option value="${esc(f.id)}" ${String(f.id)===selectedProjectFolderId?'selected':''}>${esc(f.label||'Projet')}</option>`).join('')
        :'<option value="">Aucun projet autorisé</option>';
    }
    $('[data-folder-list]',panel).innerHTML=folders.length?folders.map(f=>`
      <article data-folder-row="${esc(f.id)}" class="${f.exists?'ready':'missing'}">
        <div>
          <b>${esc(f.label||'Projet')}</b>
          <small title="${esc(f.path||'')}">${esc(f.path||'')}</small>
        </div>
        <i>${f.exists?'AUTORISÉ':'INDISPONIBLE'}</i>
        <nav>
          <button data-folder-cmd="open" data-folder-id="${esc(f.id)}" ${f.exists?'':'disabled'}>OUVRIR</button>
          <button data-folder-cmd="scan" data-folder-id="${esc(f.id)}" ${f.exists?'':'disabled'}>LISTER</button>
          <button data-folder-cmd="revoke" data-folder-id="${esc(f.id)}">RÉVOQUER</button>
        </nav>
      </article>`).join(''):'<div class="aura-p0627-empty">Aucun dossier autorisé.</div>';

    const last=di.last_folder_action||{};
    $('[data-folder-action]',panel).textContent=last.action
      ?`${last.ok?'✓':'×'} ${folderActionLabel(last.action)}${last.label?` · ${last.label}`:''} — ${last.detail||''}`
      :'Aucun dossier autorisé pour le moment.';
    $('[data-folder-action]',panel).dataset.ok=last.action?(last.ok?'yes':'no'):'';

    const listing=di.last_folder_listing||{};
    const entries=Array.isArray(listing.entries)?listing.entries:[];
    $('[data-folder-preview-meta]',panel).textContent=listing.folder_id
      ?`${listing.label||'Dossier'} · ${entries.length} élément(s) · non récursif`
      :'Non chargé';
    $('[data-folder-preview]',panel).innerHTML=listing.folder_id
      ?(entries.length?entries.map(e=>`
        <article class="${e.read_supported?'readable':''}">
          <span>${e.kind==='folder'?'▦':(e.kind==='file'?'·':'↗')}</span>
          <b title="${esc(e.name||'')}">${esc(e.name||'')}</b>
          <small>${e.kind==='file'?humanSize(e.size_bytes):esc(String(e.kind||''))}</small>
          ${e.read_supported&&e.file_id
            ?`<button data-file-read data-folder-id="${esc(listing.folder_id)}" data-file-id="${esc(e.file_id)}">LIRE</button>`
            :''}
        </article>`).join(''):'<i>Dossier vide.</i>')
      :'<i>Sélectionne LISTER sur un dossier autorisé.</i>';

    const fileRead=di.last_file_read||{};
    $('[data-file-meta]',panel).textContent=fileRead.name
      ?`${fileRead.name} · ${humanSize(fileRead.size_bytes)} · ${Number(fileRead.text_chars||0)} caractères${fileRead.truncated?' · extrait':''}`
      :(fileRead.error?`Erreur · ${fileRead.error}`:'Non chargé');
    $('[data-file-preview]',panel).textContent=fileRead.ok
      ?String(fileRead.preview||'')
      :(fileRead.detail?String(fileRead.detail):'Aucun contenu de fichier chargé.');

    const analysis=di.last_file_analysis||{};
    $('[data-analysis-meta]',panel).textContent=analysis.ok
      ?`${analysis.name||'Fichier'} · ${String(analysis.mode||'').toUpperCase()} · ${Number(analysis.result_chars||0)} caractères · LOCAL`
      :(analysis.error?`Erreur · ${analysis.error}`:'Aucune analyse locale.');
    $('[data-analysis-result]',panel).textContent=analysis.ok
      ?String(analysis.text||'')
      :(analysis.detail?String(analysis.detail):'Aucun résultat.');

    const project=di.last_project_analysis||{};
    $('[data-project-meta]',panel).textContent=project.ok
      ?`${project.folder_label||'Projet'} · ${String(project.mode||'').toUpperCase()} · ${Number(project.files_extracted||0)}/${Number(project.files_planned||0)} fichier(s) · ${Number(project.files_matched||0)} source(s) pertinente(s) · LOCAL`
      :(project.error?`Erreur · ${project.error}`:'Aucune analyse projet.');
    $('[data-project-result]',panel).textContent=project.ok
      ?String(project.text||'')
      :(project.detail?String(project.detail):'Aucun résultat multi-fichiers.');
    const provenance=Array.isArray(project.provenance)?project.provenance:[];
    $('[data-project-provenance]',panel).innerHTML=provenance.length
      ?provenance.map(p=>`<span title="${esc(String(p.chars||0))} caractères locaux">${esc(p.name||'fichier')}${Number(p.matches||0)>0?` · ${Number(p.matches)} hit(s)`:''}</span>`).join('')
      :'';

    const caps=s.capabilities||[];
    $('[data-capabilities]',panel).innerHTML=caps.length?caps.map(c=>`
      <article class="cap ${esc(c.status)}">
        <div><b>${esc(c.action)}</b><small>${esc(c.permission)}</small></div>
        <span>${esc(c.risk)}</span><i>${esc(statusLabel(c.status))}</i>
      </article>`).join(''):'<div class="aura-p0627-empty">Aucune capacité déclarée.</div>';

    const audit=s.recent_audit||[];
    $('[data-audit]',panel).innerHTML=audit.length?audit.map(a=>`
      <article class="${a.allowed?'allowed':'denied'}">
        <span>${a.allowed?'✓':'×'}</span>
        <div><b>${esc(a.action)} · ${esc(a.risk)}</b><small>${esc(a.reason)}</small></div>
        <time>${esc(String(a.timestamp||'').replace('T',' '))}</time>
      </article>`).join(''):'<div class="aura-p0627-empty">Aucun audit enregistré.</div>';
    $('[data-permissions]',panel).textContent=`Permissions locales : ${(s.granted_permissions||[]).join(' · ')||'aucune'}`;
  }
  function workspaceActivity(state,label,detail=''){
    window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
      detail:{workspace:'system',state,label,detail}
    }));
  }
  async function refresh(){
    if(!active)return;
    workspaceActivity('loading','Actualisation','Télémétrie locale');
    try{
      const status=await fetchStatus();
      render(status);
      workspaceActivity(status?.ok?'ready':'error',status?.ok?'Système LIVE':'État indisponible',status?.ok?'SecurityPolicyEngine actif':'Snapshot invalide');
    }catch(e){
      $('[data-live]',panel).textContent='OFFLINE';
      workspaceActivity('error','System offline',String(e.message||'Erreur SYS'));
    }
  }
  window.addEventListener('aura:workspace-refresh',event=>{
    if(String(event.detail?.workspace||'')==='system'){refresh();}
  });

  function open(){
    active=true;panel.classList.add('open');sysBtn.classList.add('active');
    $('.aura-p0626-memory')?.classList.remove('open');$('#memoryBtn')?.classList.remove('active');
    $('.aura-p0623-drawer')?.classList.remove('open');$('.aura-p0623-productivity-btn')?.classList.remove('active');
    clearInterval(timer);refresh();timer=setInterval(refresh,2500);
  }
  function close(){
    active=false;panel.classList.remove('open');sysBtn.classList.remove('active');clearInterval(timer);timer=0;
  }
  $('[data-folder-authorize]',panel).addEventListener('click',async()=>{
    const path=String($('[data-folder-path]',panel).value||'').trim();
    const label=String($('[data-folder-label]',panel).value||'').trim();
    if(!path){
      $('[data-folder-action]',panel).textContent='× Indique un chemin de dossier à autoriser.';
      $('[data-folder-action]',panel).dataset.ok='no';
      return;
    }
    const button=$('[data-folder-authorize]',panel);
    button.disabled=true;
    workspaceActivity('loading','Autorisation dossier','SecurityPolicyEngine');
    try{
      await action('system_authorize_folder',{path,label});
      setTimeout(refresh,180);setTimeout(refresh,700);
    }catch(e){
      $('[data-folder-action]',panel).textContent=`× ${String(e.message||'Autorisation refusée')}`;
      $('[data-folder-action]',panel).dataset.ok='no';
    }finally{
      button.disabled=false;
    }
  });

  $('[data-project-folder]',panel).addEventListener('change',event=>{
    selectedProjectFolderId=String(event.target.value||'');
  });

  $$('[data-project-mode]',panel).forEach(button=>button.addEventListener('click',async()=>{
    const folderId=String($('[data-project-folder]',panel).value||selectedProjectFolderId||'');
    if(!folderId){
      $('[data-project-meta]',panel).textContent='Autorise d’abord un projet/dossier.';
      return;
    }
    selectedProjectFolderId=folderId;
    const mode=String(button.dataset.projectMode||'');
    const query=String($('[data-project-query]',panel).value||'').trim();
    if((mode==='search'||mode==='context')&&!query){
      $('[data-project-meta]',panel).textContent='Indique un terme ou une question multi-fichiers.';
      return;
    }
    button.disabled=true;
    workspaceActivity('loading','Intelligence projet',`${mode} · multi-fichiers locaux`);
    try{
      await action('system_analyze_authorized_project',{folder_id:folderId,mode,query});
      $('[data-project-meta]',panel).textContent='Analyse projet terminée · synchronisation…';
      workspaceActivity('ready','Analyse projet terminée','Provenance locale · aucun LLM/cloud');
      setTimeout(refresh,220);setTimeout(refresh,850);setTimeout(refresh,1500);
    }catch(e){
      $('[data-project-meta]',panel).textContent=`Erreur · ${String(e.message||'analyse refusée')}`;
      workspaceActivity('error','Analyse projet refusée',String(e.message||''));
    }finally{
      setTimeout(()=>{button.disabled=false},300);
    }
  }));

  $$('[data-analysis-mode]',panel).forEach(button=>button.addEventListener('click',async()=>{
    const last=latestDesktopIntelligence.last_file_read||{};
    const folderId=String(last.folder_id||'');
    const fileId=String(last.file_id||'');
    if(!folderId||!fileId){
      try{
        const fresh=await fetchStatus();
        latestDesktopIntelligence=fresh?.desktop_intelligence||latestDesktopIntelligence;
      }catch(_){}
    }
    const current=latestDesktopIntelligence.last_file_read||{};
    const currentFolderId=String(current.folder_id||folderId||'');
    const currentFileId=String(current.file_id||fileId||'');
    if(!currentFolderId||!currentFileId){
      $('[data-analysis-meta]',panel).textContent='Lis d’abord un fichier autorisé.';
      return;
    }
    const mode=String(button.dataset.analysisMode||'');
    const query=String($('[data-analysis-query]',panel).value||'').trim();
    if((mode==='search'||mode==='context')&&!query){
      $('[data-analysis-meta]',panel).textContent='Indique un terme ou une question.';
      return;
    }
    button.disabled=true;
    workspaceActivity('loading','Intelligence documentaire',`${mode} · local uniquement`);
    try{
      const result=await action('system_analyze_authorized_file',{
        folder_id:currentFolderId,
        file_id:currentFileId,
        mode,
        query
      });
      $('[data-analysis-meta]',panel).textContent='Analyse locale terminée · synchronisation…';
      workspaceActivity('ready','Analyse locale terminée','Aucun LLM / cloud');
      setTimeout(refresh,180);setTimeout(refresh,700);setTimeout(refresh,1300);
    }catch(e){
      workspaceActivity('error','Analyse locale refusée',String(e.message||''));
    }finally{
      setTimeout(()=>{button.disabled=false},250);
    }
  }));

  $('[data-folder-preview]',panel).addEventListener('click',async event=>{
    const button=event.target.closest('button[data-file-read]');
    if(!button)return;
    const folderId=String(button.dataset.folderId||'');
    const fileId=String(button.dataset.fileId||'');
    if(!folderId||!fileId)return;
    button.disabled=true;
    workspaceActivity('loading','Lecture fichier','Extraction locale uniquement');
    try{
      await action('system_read_authorized_file',{folder_id:folderId,file_id:fileId});
      workspaceActivity('ready','Fichier lu','Aucun upload cloud');
      setTimeout(refresh,160);setTimeout(refresh,650);
    }catch(e){
      workspaceActivity('error','Lecture refusée',String(e.message||''));
    }finally{
      setTimeout(()=>{button.disabled=false},250);
    }
  });

  $('[data-folder-list]',panel).addEventListener('click',async event=>{
    const button=event.target.closest('button[data-folder-cmd]');
    if(!button)return;
    const folderId=String(button.dataset.folderId||'');
    const cmd=String(button.dataset.folderCmd||'');
    if(!folderId)return;
    if(cmd==='revoke'){
      const label=String(button.closest('[data-folder-row]')?.querySelector('b')?.textContent||'ce dossier');
      if(!confirm(`Retirer l’autorisation pour « ${label} » ?\\nAucun fichier ne sera supprimé.`))return;
    }
    const name={open:'system_open_folder',scan:'system_scan_folder',revoke:'system_revoke_folder'}[cmd];
    if(!name)return;
    button.disabled=true;
    try{
      await action(name,{folder_id:folderId});
      setTimeout(refresh,160);setTimeout(refresh,650);
    }finally{
      setTimeout(()=>{button.disabled=false},250);
    }
  });

  $$('[data-safe-app]',panel).forEach(button=>button.addEventListener('click',async()=>{
    const appId=String(button.dataset.safeApp||'');
    button.disabled=true;
    workspaceActivity('loading','Action locale','Ouverture sécurisée');
    try{
      await action('system_open_safe_app',{app_id:appId});
      button.classList.add('ok');setTimeout(()=>button.classList.remove('ok'),700);
      workspaceActivity('ready','Application ouverte',appId);
      setTimeout(refresh,120);
    }catch(_){
      button.classList.add('error');setTimeout(()=>button.classList.remove('error'),900);
      workspaceActivity('error','Action refusée ou indisponible',appId);
    }finally{
      button.disabled=false;
    }
  }));
  sysBtn.addEventListener('click',()=>active?close():open());
  $('[data-close]',panel).addEventListener('click',close);
  $('#homeBtn')?.addEventListener('click',close);
  $('#talkBtn')?.addEventListener('click',close);
  $('#memoryBtn')?.addEventListener('click',close);
  $('.aura-p0623-productivity-btn')?.addEventListener('click',close);
})();
