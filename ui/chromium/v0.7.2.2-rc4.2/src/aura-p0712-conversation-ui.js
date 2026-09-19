/* AURA P0.7.1.2 — CONVERSATION UI COEXISTENCE + VISUAL REDESIGN
   - One real chat engine/history; drawer is a contextual view over #messages/#messageInput/#sendBtn.
   - Contextual drawer coexists with right-side workspaces instead of covering them.
   - Full Conversation gets a dedicated presentation surface without changing Core routing.
*/
(()=>{
  'use strict';
  if(window.__AURA_P071_CONVERSATION_DRAWER__)return;
  window.__AURA_P071_CONVERSATION_DRAWER__=true;

  const VERSION='P0.7.1.2';
  const messages=document.querySelector('#messages');
  const sourceInput=document.querySelector('#messageInput');
  const sourceSend=document.querySelector('#sendBtn');
  if(!messages||!sourceInput||!sourceSend)return;

  const manager=()=>window.AuraWorkspace;
  const overlayApi=()=>manager()?.overlays;
  const workspaceLabels={home:'ACCUEIL',talk:'CONVERSATION',plan:'TÂCHES',weather:'MÉTÉO',memory:'MÉMOIRE',system:'DIAGNOSTICS',maps:'MAPS'};
  const promptStarters={
    summary:'Résume les points clés de cette conversation.',
    tasks:'Extrais les tâches, décisions et actions à retenir de cette conversation.',
    research:'Recherche les références utiles liées au contexte actuel.',
    note:'Crée une note synthétique à partir de cette conversation.'
  };

  function q(sel,root=document){return root.querySelector(sel)}
  function currentWorkspace(){return String(manager()?.current?.()||document.body.dataset.auraWorkspace||'home').trim().toLowerCase()||'home'}
  function railSubmode(){
    const active=q('.aura-p0702-nav-btn.active[data-rail-target],.aura-p0702-nav-btn.is-active[data-rail-target]');
    return String(active?.dataset?.railTarget||'').trim().toLowerCase();
  }
  function labelFor(id){
    if(id==='plan')return railSubmode()==='agenda'?'AGENDA':'TÂCHES';
    return workspaceLabels[id]||String(id||'').toUpperCase();
  }
  function contextTarget(id){
    if(id==='maps'){
      const d=window.AURA_NAVIGATION?.state?.destination;
      return String(d?.label||d?.name||'Itinéraire actif').trim()||'Itinéraire actif';
    }
    if(id==='memory')return'Mémoire persistante';
    if(id==='plan')return railSubmode()==='agenda'?'Rappels et agenda':'Liste de tâches';
    if(id==='weather')return'Prévisions et carte météo';
    if(id==='system')return'System Live / diagnostics';
    if(id==='talk')return'Conversation principale';
    return'Workspace actif';
  }

  // Full Conversation presentation header. It is decorative/UI-only and reuses the existing close semantics.
  const conversation=q('#conversation');
  let fullHead=null;
  if(conversation&&!q('.aura-p0712-full-head',conversation)){
    fullHead=document.createElement('header');
    fullHead.className='aura-p0712-full-head';
    fullHead.innerHTML=`<div class="aura-p0712-full-title"><span>◉</span><div><small>AURA</small><b>CONVERSATION EN COURS</b></div></div><div class="aura-p0712-full-actions"><button type="button" data-full-min title="Retour à l’accueil">—</button><button type="button" data-full-close title="Fermer">×</button></div>`;
    conversation.prepend(fullHead);
    q('[data-full-min]',fullHead)?.addEventListener('click',()=>manager()?.home?.());
    q('[data-full-close]',fullHead)?.addEventListener('click',()=>{
      const existing=q('#closeTalk');
      if(existing)existing.click();else manager()?.home?.();
    });
  }

  const drawer=document.createElement('aside');
  drawer.className='aura-p071-conversation-drawer aura-p0712-conversation-drawer glass';
  drawer.hidden=true;
  drawer.setAttribute('aria-label','Conversation AURA');
  drawer.innerHTML=`
    <header class="aura-p071-head aura-p0712-head">
      <div class="aura-p071-title aura-p0712-title"><span class="aura-p0712-brandmark">A</span><span><small>AURA</small><b>AURA · CONVERSATION</b><em data-context>CONTEXTE · ACCUEIL</em></span></div>
      <div class="aura-p071-head-actions"><button type="button" data-full title="Ouvrir la conversation complète">PLEIN ÉCRAN</button><button type="button" data-close aria-label="Fermer le drawer">×</button></div>
    </header>
    <div class="aura-p0712-main">
      <div class="aura-p0712-thread">
        <div class="aura-p071-history" data-history aria-live="polite"></div>
        <div class="aura-p071-footer-note"><span data-state>Historique synchronisé avec AURA</span><b data-unread hidden></b></div>
        <footer class="aura-p071-composer aura-p0712-composer">
          <button type="button" data-attach class="aura-p071-attach" title="Joindre un fichier">＋</button>
          <div><textarea data-input rows="1" maxlength="4000" placeholder="Parle-moi ou écris ton message…"></textarea><small data-hint>Le module actif reste au premier plan.</small></div>
          <button type="button" data-send class="aura-p071-send" title="Envoyer">➤</button>
        </footer>
      </div>
      <aside class="aura-p0712-context-side" aria-label="Contexte actif">
        <section class="aura-p0712-context-card"><header>CONTEXTE ACTIF</header><dl><div><dt>Module</dt><dd data-context-module>—</dd></div><div><dt>Cible</dt><dd data-context-target>—</dd></div><div><dt>État</dt><dd data-context-state>ACTIF</dd></div></dl></section>
        <section class="aura-p0712-suggestions"><header>SUGGESTIONS</header><button data-suggest="summary">▣ <span>Résumer la conversation</span></button><button data-suggest="tasks">□ <span>Extraire les tâches</span></button><button data-suggest="research">⌕ <span>Rechercher des références</span></button><button data-suggest="note">◇ <span>Créer une note</span></button></section>
        <button type="button" class="aura-p0712-clear-context" data-clear-context disabled title="Le contexte explicite sera activé avec P0.7.2 Cross-Module Context">EFFACER LE CONTEXTE</button>
      </aside>
    </div>`;
  document.body.appendChild(drawer);

  const history=q('[data-history]',drawer),contextEl=q('[data-context]',drawer),stateEl=q('[data-state]',drawer),drawerInput=q('[data-input]',drawer),sendBtn=q('[data-send]',drawer),attachBtn=q('[data-attach]',drawer),closeBtn=q('[data-close]',drawer),fullBtn=q('[data-full]',drawer),hintEl=q('[data-hint]',drawer),contextModule=q('[data-context-module]',drawer),contextTargetEl=q('[data-context-target]',drawer),contextState=q('[data-context-state]',drawer);
  let renderTimer=0,inputSync=false,unread=0,drawerWanted=false;
  let knownAuraCount=messages.querySelectorAll('.message.aura').length;

  function isOpen(){return !drawer.hidden&&drawer.classList.contains('open')}
  function conversationRailButton(){return q('.aura-p0702-nav-btn[data-rail-target="conversation"]')}
  function setRailState(){const b=conversationRailButton();if(!b)return;b.classList.toggle('drawer-open',isOpen());b.classList.toggle('has-unread',unread>0&&!isOpen());b.dataset.drawerUnread=String(unread||0)}
  function clearUnread(){unread=0;setRailState()}
  function closeRailPopovers(){for(const el of document.querySelectorAll('.aura-p0702-modules-popover,.aura-p0702-settings-popover')){el.classList.remove('open');el.hidden=true}}

  function syncLayoutClasses(){
    const id=currentWorkspace(),contextual=isOpen()&&id!=='home'&&id!=='talk';
    document.body.classList.toggle('aura-p0711-drawer-contextual',contextual); // backward-compatible marker
    document.body.classList.toggle('aura-p0712-drawer-contextual',contextual);
    document.body.classList.toggle('aura-p0712-coexist-right-panel',contextual&&['memory','plan','system','weather'].includes(id));
    document.body.dataset.auraConversationContext=contextual?id:'';
  }
  function updateContext(){
    const id=currentWorkspace(),label=labelFor(id),target=contextTarget(id);
    contextEl.textContent=`CONTEXTE · ${label}`;
    contextModule.textContent=label;
    contextTargetEl.textContent=target;
    contextState.textContent=id==='home'?'INACTIF':'ACTIF';
    hintEl.textContent=id==='home'?'Conversation AURA':'Le module actif reste au premier plan.';
    drawer.dataset.context=id;syncLayoutClasses();
  }

  function roleOf(node){if(node.classList?.contains('aura'))return'aura';if(node.classList?.contains('user'))return'user';return'system'}
  function textOf(node){const p=node.querySelector?.('p');return String(p?.textContent||node.textContent||'').replace(/\s+$/,'').trim()}
  function renderHistory(){
    clearTimeout(renderTimer);renderTimer=0;const fragment=document.createDocumentFragment();let count=0;
    for(const node of [...messages.children]){
      if(!(node instanceof HTMLElement)||node.matches('.empty-conversation')||!node.matches('.message'))continue;
      const text=textOf(node);if(!text)continue;count++;
      const item=document.createElement('article'),role=roleOf(node);item.className=`aura-p071-message ${role}`;
      const avatar=document.createElement('span');avatar.className='aura-p0712-msg-avatar';avatar.textContent=role==='aura'?'A':role==='user'?'●':'·';
      const wrap=document.createElement('div'),tag=document.createElement('small'),p=document.createElement('p');tag.textContent=role==='aura'?'AURA':role==='user'?'VOUS':'SYSTÈME';p.textContent=text;wrap.append(tag,p);item.append(avatar,wrap);fragment.appendChild(item);
    }
    history.replaceChildren(fragment);
    if(!count){const empty=document.createElement('div');empty.className='aura-p071-empty';empty.innerHTML='<b>AURA EST PRÊTE</b><span>La conversation apparaîtra ici sans quitter ton module.</span>';history.appendChild(empty)}
    if(isOpen())requestAnimationFrame(()=>{history.scrollTop=history.scrollHeight});
  }
  function scheduleRender(){if(renderTimer)return;renderTimer=setTimeout(renderHistory,35)}

  function syncInputState(){
    const disabled=!!sourceInput.disabled||!!sourceSend.disabled;drawerInput.disabled=disabled;sendBtn.disabled=disabled;drawerInput.maxLength=sourceInput.maxLength>0?sourceInput.maxLength:4000;
    if(!inputSync&&drawerInput.value!==sourceInput.value){inputSync=true;drawerInput.value=sourceInput.value||'';inputSync=false}
    stateEl.textContent=disabled?'Runtime AURA indisponible':'Historique synchronisé avec AURA';drawer.classList.toggle('runtime-disabled',disabled);
  }
  function openDirect(){drawerWanted=true;closeRailPopovers();drawer.hidden=false;void drawer.offsetWidth;drawer.classList.add('open');document.documentElement.dataset.auraConversationDrawer='open';updateContext();syncInputState();renderHistory();clearUnread();setRailState();syncLayoutClasses();setTimeout(()=>{try{drawerInput.focus({preventScroll:true})}catch(_){drawerInput.focus?.()}},30);return true}
  function closeDirect(){drawerWanted=false;drawer.classList.remove('open');document.documentElement.dataset.auraConversationDrawer='closed';setRailState();syncLayoutClasses();setTimeout(()=>{if(!drawer.classList.contains('open'))drawer.hidden=true;syncLayoutClasses()},150);return true}
  function openDrawer(source='api'){const ov=overlayApi();if(ov?.open&&ov.list?.().some(x=>x.id==='conversation-drawer'))return ov.open('conversation-drawer',{source});return openDirect()}
  function closeDrawer(){const ov=overlayApi();if(ov?.close&&ov.list?.().some(x=>x.id==='conversation-drawer'))return ov.close('conversation-drawer');return closeDirect()}
  function toggleDrawer(){return isOpen()?closeDrawer():openDrawer('toggle')}
  function registerOverlay(){const ov=overlayApi();if(!ov?.register)return false;if(ov.list?.().some(x=>x.id==='conversation-drawer'))return true;return ov.register({id:'conversation-drawer',label:'Conversation',preserveOnWorkspaceChange:true,available:()=>true,isOpen,open:openDirect,close:closeDirect})}

  function send(){syncInputState();if(drawerInput.disabled)return false;const text=String(drawerInput.value||'').trim();if(!text)return false;inputSync=true;sourceInput.value=text;sourceInput.dispatchEvent(new Event('input',{bubbles:true}));inputSync=false;sourceSend.click();drawerInput.value='';setTimeout(syncInputState,0);setTimeout(scheduleRender,20);return true}
  function fillSuggestion(key){const text=promptStarters[key];if(!text)return;drawerInput.value=text;drawerInput.dispatchEvent(new Event('input',{bubbles:true}));drawerInput.focus()}

  drawerInput.addEventListener('input',()=>{if(inputSync)return;inputSync=true;sourceInput.value=drawerInput.value;sourceInput.dispatchEvent(new Event('input',{bubbles:true}));inputSync=false;drawerInput.style.height='auto';drawerInput.style.height=`${Math.min(drawerInput.scrollHeight,112)}px`});
  sourceInput.addEventListener('input',()=>{if(inputSync)return;inputSync=true;drawerInput.value=sourceInput.value||'';inputSync=false});
  drawerInput.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}});sendBtn.addEventListener('click',send);
  attachBtn.addEventListener('click',()=>{const attach=q('.workspace>.composer .attach,#composer .attach');if(attach&&!attach.classList.contains('disabled')&&attach.getAttribute('aria-disabled')!=='true')attach.click();else stateEl.textContent='Pièce jointe indisponible dans ce contexte'});
  closeBtn.addEventListener('click',closeDrawer);fullBtn.addEventListener('click',()=>{closeDrawer();setTimeout(()=>manager()?.open?.('talk'),0)});
  drawer.addEventListener('click',event=>{const b=event.target.closest?.('[data-suggest]');if(b)fillSuggestion(b.dataset.suggest)});

  document.addEventListener('click',event=>{
    const railConversation=event.target?.closest?.('.aura-p0702-nav-btn[data-rail-target="conversation"]');
    const dockTalk=event.target?.closest?.('.aura-p0633-response-dock [data-talk]');
    if(!railConversation&&!dockTalk)return;const current=currentWorkspace();if(current==='home'||current==='talk')return;
    event.preventDefault();event.stopImmediatePropagation();if(railConversation)toggleDrawer();else openDrawer('response-dock');
  },true);

  const observer=new MutationObserver(()=>{const now=messages.querySelectorAll('.message.aura').length;if(now>knownAuraCount&&!isOpen()){unread+=now-knownAuraCount;setRailState()}knownAuraCount=now;scheduleRender()});observer.observe(messages,{childList:true,subtree:true,characterData:true});
  const stateObserver=new MutationObserver(syncInputState);stateObserver.observe(sourceInput,{attributes:true,attributeFilter:['disabled','placeholder','maxlength']});stateObserver.observe(sourceSend,{attributes:true,attributeFilter:['disabled']});

  window.addEventListener('aura:workspace-will-change',event=>{const to=String(event.detail?.to||'').trim().toLowerCase();if(isOpen()&&to&&to!=='home'&&to!=='talk')drawerWanted=true});
  window.addEventListener('aura:workspace-changed',event=>{
    const next=String(event.detail?.workspace||currentWorkspace()).trim().toLowerCase();updateContext();setRailState();syncLayoutClasses();
    if(next==='talk'||next==='home'){if(isOpen())closeDrawer();else{drawerWanted=false;syncLayoutClasses()}return}
    if(drawerWanted&&!isOpen())setTimeout(()=>{const now=currentWorkspace();if(drawerWanted&&!isOpen()&&now!=='home'&&now!=='talk')openDrawer('workspace-persist-recover')},35);
  });
  window.addEventListener('aura:workspace-overlay-changed',()=>{setRailState();syncLayoutClasses()});
  window.addEventListener('aura:workspace-manager-ready',registerOverlay);window.addEventListener('aura:left-rail-ready',setRailState);

  registerOverlay();setTimeout(registerOverlay,40);setTimeout(registerOverlay,180);renderHistory();syncInputState();updateContext();setRailState();
  window.AuraConversationDrawer=Object.freeze({version:VERSION,open:openDrawer,close:closeDrawer,toggle:toggleDrawer,isOpen,refresh:renderHistory,context:currentWorkspace,wanted:()=>drawerWanted,refreshLayout:syncLayoutClasses});
  window.dispatchEvent(new CustomEvent('aura:conversation-drawer-ready',{detail:{version:VERSION,features:['coexistence-layout','context-sidecar','suggestion-starters','full-conversation-redesign']}}));
})();
