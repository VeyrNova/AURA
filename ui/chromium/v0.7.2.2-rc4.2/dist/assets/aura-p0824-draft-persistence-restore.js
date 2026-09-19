/* AURA P0.8.2.4 — DRAFT PERSISTENCE & RESTORE HOTFIX
   Keeps one in-memory draft mirror across Conversation Drawer/global/full surface transitions.
   - capture BEFORE drawer close / workspace transition;
   - restore only into the active input when an unexpected empty value appears;
   - deliberate user clearing and normal Send clearing remain authoritative;
   - no Send click, no automatic submission, no network, no LLM, no Core/voice change.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0824_DRAFT_PERSISTENCE_RESTORE__)return;
  window.__AURA_P0824_DRAFT_PERSISTENCE_RESTORE__=true;

  const VERSION='P0.8.2.4';
  const STATE={draft:'',syncing:false,lastReason:'boot',observer:null,lastCaptureAt:0};
  const q=(s,r=document)=>r.querySelector(s);
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));
  const value=el=>String(el?.value??'');

  function globalInput(){return q('#messageInput')}
  function drawerRoot(){return q('.aura-p0712-conversation-drawer')||q('.aura-p071-conversation-drawer')}
  function drawerInput(){return q('.aura-p0712-conversation-drawer [data-input]')||q('.aura-p071-conversation-drawer [data-input]')}
  function fullConversation(){return String(document.body.dataset.auraWorkspace||'').trim().toLowerCase()==='talk'}
  function drawerOpen(){
    if(fullConversation())return false;
    if(document.documentElement.dataset.auraConversationDrawer==='open')return true;
    try{return !!window.AuraConversationDrawer?.isOpen?.()}catch(_e){return false}
  }
  function surface(){
    try{const s=window.AuraComposerSurface?.current?.();if(s)return String(s)}catch(_e){}
    return fullConversation()?'full':drawerOpen()?'drawer':'global';
  }
  function activeInput(){return surface()==='drawer'?drawerInput():globalInput()}

  function capture(el,reason='capture'){
    if(STATE.syncing||!el)return STATE.draft;
    STATE.draft=value(el);STATE.lastReason=reason;STATE.lastCaptureAt=Date.now();
    return STATE.draft;
  }
  function captureBest(reason='capture-best'){
    const di=drawerInput(),gi=globalInput();
    if(drawerOpen()&&di)return capture(di,reason);
    if(gi)return capture(gi,reason);
    if(di)return capture(di,reason);
    return STATE.draft;
  }
  function write(el,text,reason='restore'){
    if(!el||value(el)===text)return false;
    STATE.syncing=true;
    try{
      el.value=text;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      STATE.lastReason=reason;
    }finally{STATE.syncing=false}
    return true;
  }
  function restore(reason='restore'){
    const target=activeInput();
    if(!target)return false;
    const current=value(target);
    // Never overwrite a non-empty active field. It is newer user intent.
    if(current){if(current!==STATE.draft)capture(target,reason+'-active-wins');return false}
    if(!STATE.draft)return false;
    const changed=write(target,STATE.draft,reason);
    if(changed)emit('aura:draft-restored',{surface:surface(),reason,length:STATE.draft.length,autoSend:false});
    return changed;
  }
  function settle(reason='settle'){
    [0,30,90,180].forEach(ms=>setTimeout(()=>restore(reason+'-'+ms),ms));
  }

  // Capture every intentional edit on either composer. A deliberate clear therefore clears the mirror too.
  document.addEventListener('input',event=>{
    const t=event.target;
    if(t===globalInput()||t===drawerInput())capture(t,'input');
  },true);

  // Critical fix: capture the drawer BEFORE its close handler can hide/replace/switch surfaces.
  document.addEventListener('click',event=>{
    const close=event.target.closest?.('.aura-p0712-conversation-drawer [data-close],.aura-p071-conversation-drawer [data-close],[data-full],[data-full-close],[data-full-min]');
    if(close){captureBest('pre-close-click');settle('post-close-click')}
    const prepare=event.target.closest?.('[data-p082-prepare]');
    if(prepare)setTimeout(()=>{captureBest('post-prepare-click');settle('post-prepare-click')},0);
  },true);

  window.addEventListener('aura:suggestion-prepared',()=>setTimeout(()=>{captureBest('suggestion-prepared');settle('suggestion-prepared')},0));
  ['aura:composer-surface-changed','aura:workspace-will-change','aura:workspace-changed','aura:workspace-restored','aura:workspace-overlay-changed'].forEach(name=>{
    window.addEventListener(name,()=>{captureBest(name+'-capture');settle(name+'-restore')});
  });

  // Targeted attributes only; no global subtree observer.
  if(window.MutationObserver){
    STATE.observer=new MutationObserver(()=>{captureBest('surface-attribute-capture');settle('surface-attribute-restore')});
    STATE.observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-aura-conversation-drawer','data-aura-composer-surface']});
  }

  window.addEventListener('load',()=>{captureBest('load');settle('load')},{once:true});
  setTimeout(()=>{captureBest('script-ready');settle('script-ready')},180);

  window.AuraDraftPersistence=Object.freeze({
    version:VERSION,
    get:()=>STATE.draft,
    capture:()=>captureBest('api-capture'),
    restore:()=>restore('api-restore'),
    audit:()=>({version:VERSION,surface:surface(),draftLength:STATE.draft.length,globalValueLength:value(globalInput()).length,drawerValueLength:value(drawerInput()).length,activeValueLength:value(activeInput()).length,draftMatchesActive:!!activeInput()&&value(activeInput())===STATE.draft,lastReason:STATE.lastReason,autoSend:false,networkAccess:false,backgroundLlm:false,execution:'none'}),
    authority:'draft-presentation-continuity-no-send',autoSend:false,networkAccess:false,backgroundLlm:false
  });
  emit('aura:p0824-draft-persistence-ready',{features:['pre-close-capture','active-surface-restore','deliberate-clear-respected','single-draft-continuity'],autoSend:false});
})();
