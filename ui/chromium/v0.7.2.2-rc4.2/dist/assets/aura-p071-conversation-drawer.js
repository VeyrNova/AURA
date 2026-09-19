/* AURA P0.7.1 — CONVERSATION DRAWER
   Context-preserving conversation overlay for Workspace Manager v2.
   Reuses the existing Conversation history and composer; no second chat engine.
*/
(()=>{
  'use strict';
  if(window.__AURA_P071_CONVERSATION_DRAWER__)return;
  window.__AURA_P071_CONVERSATION_DRAWER__=true;

  const VERSION='P0.7.1';
  const messages=document.querySelector('#messages');
  const sourceInput=document.querySelector('#messageInput');
  const sourceSend=document.querySelector('#sendBtn');
  if(!messages||!sourceInput||!sourceSend)return;

  const manager=()=>window.AuraWorkspace;
  const overlayApi=()=>manager()?.overlays;
  const workspaceLabels={
    home:'ACCUEIL',talk:'CONVERSATION',plan:'TÂCHES',weather:'MÉTÉO',memory:'MÉMOIRE',system:'DIAGNOSTICS',maps:'MAPS'
  };

  const drawer=document.createElement('aside');
  drawer.className='aura-p071-conversation-drawer glass';
  drawer.hidden=true;
  drawer.setAttribute('aria-label','Conversation AURA');
  drawer.innerHTML=`
    <header class="aura-p071-head">
      <div class="aura-p071-title"><i></i><span><small>CONVERSATION DRAWER</small><b>CONVERSATION</b><em data-context>CONTEXTE · ACCUEIL</em></span></div>
      <div class="aura-p071-head-actions">
        <button type="button" data-full title="Ouvrir la conversation complète">PLEIN ÉCRAN</button>
        <button type="button" data-close aria-label="Fermer le drawer">×</button>
      </div>
    </header>
    <div class="aura-p071-history" data-history aria-live="polite"></div>
    <div class="aura-p071-footer-note"><span data-state>Historique synchronisé avec AURA</span><b data-unread hidden></b></div>
    <footer class="aura-p071-composer">
      <button type="button" data-attach class="aura-p071-attach" title="Joindre un fichier">＋</button>
      <div><textarea data-input rows="1" maxlength="4000" placeholder="Écris à AURA…"></textarea><small data-hint>Le module actif reste au premier plan.</small></div>
      <button type="button" data-send class="aura-p071-send" title="Envoyer">➤</button>
    </footer>`;
  document.body.appendChild(drawer);

  const history=drawer.querySelector('[data-history]');
  const contextEl=drawer.querySelector('[data-context]');
  const stateEl=drawer.querySelector('[data-state]');
  const drawerInput=drawer.querySelector('[data-input]');
  const sendBtn=drawer.querySelector('[data-send]');
  const attachBtn=drawer.querySelector('[data-attach]');
  const closeBtn=drawer.querySelector('[data-close]');
  const fullBtn=drawer.querySelector('[data-full]');
  const hintEl=drawer.querySelector('[data-hint]');

  let renderTimer=0;
  let inputSync=false;
  let unread=0;
  let knownAuraCount=messages.querySelectorAll('.message.aura').length;

  function currentWorkspace(){
    return String(manager()?.current?.()||document.body.dataset.auraWorkspace||'home').trim().toLowerCase()||'home';
  }
  function isOpen(){return !drawer.hidden&&drawer.classList.contains('open')}
  function conversationRailButton(){return document.querySelector('.aura-p0702-nav-btn[data-rail-target="conversation"]')}
  function setRailState(){
    const b=conversationRailButton();if(!b)return;
    b.classList.toggle('drawer-open',isOpen());
    b.classList.toggle('has-unread',unread>0&&!isOpen());
    b.dataset.drawerUnread=String(unread||0);
  }
  function clearUnread(){unread=0;setRailState()}

  function closeRailPopovers(){
    for(const el of document.querySelectorAll('.aura-p0702-modules-popover,.aura-p0702-settings-popover')){
      el.classList.remove('open');el.hidden=true;
    }
  }

  function updateContext(){
    const id=currentWorkspace();
    const label=workspaceLabels[id]||id.toUpperCase();
    contextEl.textContent=`CONTEXTE · ${label}`;
    hintEl.textContent=id==='home'?'Conversation AURA':'Le module actif reste au premier plan.';
    drawer.dataset.context=id;
  }

  function roleOf(node){
    if(node.classList?.contains('aura'))return'aura';
    if(node.classList?.contains('user'))return'user';
    return'system';
  }
  function textOf(node){
    const p=node.querySelector?.('p');
    return String(p?.textContent||node.textContent||'').replace(/\s+$/,'').trim();
  }
  function renderHistory(){
    clearTimeout(renderTimer);renderTimer=0;
    const fragment=document.createDocumentFragment();
    let count=0;
    for(const node of [...messages.children]){
      if(!(node instanceof HTMLElement))continue;
      if(node.matches('.empty-conversation'))continue;
      if(!node.matches('.message'))continue;
      const text=textOf(node);if(!text)continue;
      count++;
      const item=document.createElement('article');
      const role=roleOf(node);
      item.className=`aura-p071-message ${role}`;
      const tag=document.createElement('small');tag.textContent=role==='aura'?'AURA':role==='user'?'VOUS':'SYSTÈME';
      const p=document.createElement('p');p.textContent=text;
      item.append(tag,p);fragment.appendChild(item);
    }
    history.replaceChildren(fragment);
    if(!count){
      const empty=document.createElement('div');empty.className='aura-p071-empty';empty.innerHTML='<b>AURA EST PRÊTE</b><span>La conversation apparaîtra ici sans quitter ton module.</span>';
      history.appendChild(empty);
    }
    if(isOpen())requestAnimationFrame(()=>{history.scrollTop=history.scrollHeight});
  }
  function scheduleRender(){if(renderTimer)return;renderTimer=setTimeout(renderHistory,35)}

  function syncInputState(){
    const disabled=!!sourceInput.disabled||!!sourceSend.disabled;
    drawerInput.disabled=disabled;sendBtn.disabled=disabled;
    drawerInput.maxLength=sourceInput.maxLength>0?sourceInput.maxLength:4000;
    if(!inputSync&&drawerInput.value!==sourceInput.value){inputSync=true;drawerInput.value=sourceInput.value||'';inputSync=false}
    stateEl.textContent=disabled?'Runtime AURA indisponible':'Historique synchronisé avec AURA';
    drawer.classList.toggle('runtime-disabled',disabled);
  }

  function openDirect(){
    closeRailPopovers();
    drawer.hidden=false;
    void drawer.offsetWidth;
    drawer.classList.add('open');
    document.documentElement.dataset.auraConversationDrawer='open';
    updateContext();syncInputState();renderHistory();clearUnread();setRailState();
    setTimeout(()=>{try{drawerInput.focus({preventScroll:true})}catch(_){drawerInput.focus?.()}},30);
    return true;
  }
  function closeDirect(){
    drawer.classList.remove('open');
    document.documentElement.dataset.auraConversationDrawer='closed';
    setRailState();
    setTimeout(()=>{if(!drawer.classList.contains('open'))drawer.hidden=true},150);
    return true;
  }
  function openDrawer(source='api'){
    const ov=overlayApi();
    if(ov?.open&&ov.list?.().some(x=>x.id==='conversation-drawer'))return ov.open('conversation-drawer',{source});
    return openDirect();
  }
  function closeDrawer(){
    const ov=overlayApi();
    if(ov?.close&&ov.list?.().some(x=>x.id==='conversation-drawer'))return ov.close('conversation-drawer');
    return closeDirect();
  }
  function toggleDrawer(){return isOpen()?closeDrawer():openDrawer('toggle')}

  function registerOverlay(){
    const ov=overlayApi();if(!ov?.register)return false;
    if(ov.list?.().some(x=>x.id==='conversation-drawer'))return true;
    return ov.register({
      id:'conversation-drawer',label:'Conversation',preserveOnWorkspaceChange:true,
      available:()=>true,isOpen,open:openDirect,close:closeDirect,
    });
  }

  function send(){
    syncInputState();if(drawerInput.disabled)return false;
    const text=String(drawerInput.value||'').trim();if(!text)return false;
    inputSync=true;sourceInput.value=text;sourceInput.dispatchEvent(new Event('input',{bubbles:true}));inputSync=false;
    sourceSend.click();
    drawerInput.value='';
    setTimeout(syncInputState,0);setTimeout(scheduleRender,20);
    return true;
  }

  drawerInput.addEventListener('input',()=>{
    if(inputSync)return;
    inputSync=true;sourceInput.value=drawerInput.value;sourceInput.dispatchEvent(new Event('input',{bubbles:true}));inputSync=false;
    drawerInput.style.height='auto';drawerInput.style.height=`${Math.min(drawerInput.scrollHeight,112)}px`;
  });
  sourceInput.addEventListener('input',()=>{
    if(inputSync)return;
    inputSync=true;drawerInput.value=sourceInput.value||'';inputSync=false;
  });
  drawerInput.addEventListener('keydown',event=>{
    if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();send()}
  });
  sendBtn.addEventListener('click',send);
  attachBtn.addEventListener('click',()=>{
    const attach=document.querySelector('.workspace>.composer .attach,#composer .attach');
    if(attach&&!attach.classList.contains('disabled')&&attach.getAttribute('aria-disabled')!=='true')attach.click();
    else stateEl.textContent='Pièce jointe indisponible dans ce contexte';
  });
  closeBtn.addEventListener('click',closeDrawer);
  fullBtn.addEventListener('click',()=>{
    closeDrawer();setTimeout(()=>manager()?.open?.('talk'),0);
  });

  // Intercept the product-facing CONVERSATION item only when a contextual
  // workspace is active. HOME keeps the historical full Conversation behavior.
  document.addEventListener('click',event=>{
    const railConversation=event.target?.closest?.('.aura-p0702-nav-btn[data-rail-target="conversation"]');
    const dockTalk=event.target?.closest?.('.aura-p0633-response-dock [data-talk]');
    if(!railConversation&&!dockTalk)return;
    const current=currentWorkspace();
    if(current==='home'||current==='talk')return;
    event.preventDefault();event.stopImmediatePropagation();
    if(railConversation)toggleDrawer();else openDrawer('response-dock');
  },true);

  const observer=new MutationObserver(()=>{
    scheduleRender();syncInputState();
    const next=messages.querySelectorAll('.message.aura').length;
    if(next>knownAuraCount&&!isOpen()&&currentWorkspace()!=='talk')unread+=next-knownAuraCount;
    knownAuraCount=next;setRailState();
  });
  observer.observe(messages,{childList:true,subtree:true,characterData:true});
  const stateObserver=new MutationObserver(syncInputState);
  stateObserver.observe(sourceInput,{attributes:true,attributeFilter:['disabled','placeholder','maxlength']});
  stateObserver.observe(sourceSend,{attributes:true,attributeFilter:['disabled']});

  window.addEventListener('aura:workspace-changed',event=>{
    const next=String(event.detail?.workspace||currentWorkspace());
    updateContext();setRailState();
    // Explicit full Conversation owns the surface; never duplicate it with a drawer.
    if(next==='talk'&&isOpen())closeDrawer();
  });
  window.addEventListener('aura:workspace-overlay-changed',()=>setRailState());
  window.addEventListener('aura:workspace-manager-ready',registerOverlay);
  window.addEventListener('aura:left-rail-ready',setRailState);

  // Workspace Manager normally exists before this asset, but keep delayed
  // registration for custom startup ordering and cache recovery.
  registerOverlay();setTimeout(registerOverlay,40);setTimeout(registerOverlay,180);
  renderHistory();syncInputState();updateContext();setRailState();

  window.AuraConversationDrawer=Object.freeze({
    version:VERSION,open:openDrawer,close:closeDrawer,toggle:toggleDrawer,isOpen,
    refresh:renderHistory,context:currentWorkspace,
  });
  window.dispatchEvent(new CustomEvent('aura:conversation-drawer-ready',{detail:{version:VERSION}}));
})();
