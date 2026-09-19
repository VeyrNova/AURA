/* AURA P0.8.2.5 — DEFERRED DRAFT REHYDRATE HOTFIX
   Final continuity guard for prepared / manually edited drafts across Conversation surfaces.
   Root cause fixed: an empty programmatic field during drawer/workspace transition must never
   overwrite a protected non-empty draft before the destination composer is ready.
   Safety: presentation-only; no Send click, no auto-submit, no network, no LLM, no Core action.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0825_DEFERRED_DRAFT_REHYDRATE__)return;
  window.__AURA_P0825_DEFERRED_DRAFT_REHYDRATE__=true;

  const VERSION='P0.8.2.5';
  const STORE_KEY='aura.p0825.draft';
  const STORE_TTL=2*60*60*1000;
  const STATE={draft:'',reason:'boot',updatedAt:0,protectUntil:0,restoring:false,sendPending:false,observer:null};
  const q=(s,r=document)=>r.querySelector(s);
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));
  const val=el=>String(el?.value??'');
  const now=()=>Date.now();

  function globalInput(){return q('#messageInput')}
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

  function persist(){
    try{
      if(!STATE.draft){sessionStorage.removeItem(STORE_KEY);return}
      sessionStorage.setItem(STORE_KEY,JSON.stringify({text:STATE.draft,ts:STATE.updatedAt||now()}));
    }catch(_e){}
  }
  function loadPersisted(){
    try{
      const raw=JSON.parse(sessionStorage.getItem(STORE_KEY)||'null');
      if(raw&&typeof raw.text==='string'&&raw.text&&now()-Number(raw.ts||0)<STORE_TTL){STATE.draft=raw.text;STATE.updatedAt=Number(raw.ts)||now();STATE.reason='session-restore';return true}
      sessionStorage.removeItem(STORE_KEY);
    }catch(_e){}
    return false;
  }
  function setDraft(text,reason='set',protectMs=0){
    text=String(text??'');
    STATE.draft=text;STATE.reason=reason;STATE.updatedAt=now();
    if(protectMs>0)STATE.protectUntil=Math.max(STATE.protectUntil,now()+protectMs);
    persist();return STATE.draft;
  }
  function clearDraft(reason='clear'){
    STATE.draft='';STATE.reason=reason;STATE.updatedAt=now();STATE.protectUntil=0;persist();
    emit('aura:p0825-draft-cleared',{reason,autoSend:false});
  }
  function captureNonEmpty(reason='capture',protectMs=0){
    const di=drawerInput(),gi=globalInput();
    const candidates=drawerOpen()?[di,gi]:[activeInput(),gi,di];
    for(const el of candidates){const t=val(el);if(t)return setDraft(t,reason,protectMs)}
    return STATE.draft;
  }
  function suggestionPrompt(eventId){
    try{
      const list=window.AuraSuggestionEngine?.suggestions?.();
      if(!Array.isArray(list))return '';
      const s=list.find(x=>String(x?.eventId||'')===String(eventId||''))||window.AuraSuggestionEngine?.top?.();
      return String(s?.prompt||'');
    }catch(_e){return ''}
  }
  function write(el,text,reason='rehydrate'){
    if(!el||!text||val(el)===text)return false;
    STATE.restoring=true;
    try{
      el.value=text;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      try{el.setSelectionRange?.(text.length,text.length)}catch(_e){}
      STATE.reason=reason;
    }finally{STATE.restoring=false}
    return true;
  }
  function rehydrate(reason='rehydrate'){
    if(STATE.sendPending||!STATE.draft)return false;
    const target=activeInput();if(!target)return false;
    const current=val(target);
    if(current){
      // A non-empty destination is newer visible intent; keep it and refresh the mirror.
      if(current!==STATE.draft)setDraft(current,reason+'-active-wins');
      return false;
    }
    const changed=write(target,STATE.draft,reason);
    if(changed)emit('aura:draft-restored',{surface:surface(),reason,length:STATE.draft.length,deferred:true,autoSend:false});
    return changed;
  }
  function wave(reason='wave'){
    [0,25,80,180,360,650,1050,1650,2400].forEach(ms=>setTimeout(()=>rehydrate(reason+'-'+ms),ms));
  }

  // Trust boundary: real user edits are authoritative, including a deliberate clear.
  document.addEventListener('input',event=>{
    const t=event.target;if(t!==globalInput()&&t!==drawerInput())return;
    if(STATE.restoring)return;
    const text=val(t);
    if(event.isTrusted){setDraft(text,text?'trusted-input':'trusted-clear');return}
    if(text){setDraft(text,'programmatic-nonempty',Math.max(0,STATE.protectUntil-now()));return}
    // Critical P0.8.2.5 rule: synthetic empty transitions never erase a protected/non-empty draft.
    if(STATE.draft&&!STATE.sendPending){wave('synthetic-empty-ignored');return}
  },true);

  // Capture before any close/full/min handler registered on the drawer can mutate the workspace.
  document.addEventListener('click',event=>{
    const close=event.target.closest?.('.aura-p0712-conversation-drawer [data-close],.aura-p071-conversation-drawer [data-close],[data-full],[data-full-close],[data-full-min]');
    if(close){captureNonEmpty('pre-surface-click',4200);wave('post-surface-click')}

    const send=event.target.closest?.('#sendBtn,.aura-p0712-conversation-drawer [data-send],.aura-p071-conversation-drawer [data-send]');
    if(send){
      captureNonEmpty('pre-send');STATE.sendPending=true;
      [80,220,600,1200].forEach(ms=>setTimeout(()=>{
        const any=val(globalInput())||val(drawerInput());
        if(any){STATE.sendPending=false;setDraft(any,'send-not-cleared');return}
        clearDraft('send-complete');STATE.sendPending=false;
      },ms));
    }
  },true);

  // Strongest source for proactive handoff: use the Suggestion Engine contract, not DOM timing.
  window.addEventListener('aura:suggestion-prepared',event=>{
    const prompt=suggestionPrompt(event.detail?.eventId);
    if(prompt)setDraft(prompt,'suggestion-contract',5000);else captureNonEmpty('suggestion-dom-fallback',5000);
    wave('suggestion-prepared');
  });

  // Transition events rehydrate only. They must never capture an empty destination.
  ['aura:composer-surface-changed','aura:workspace-will-change','aura:workspace-changed','aura:workspace-restored','aura:workspace-overlay-changed'].forEach(name=>{
    window.addEventListener(name,()=>{if(STATE.draft)STATE.protectUntil=Math.max(STATE.protectUntil,now()+2600);wave(name)});
  });

  if(window.MutationObserver){
    STATE.observer=new MutationObserver(()=>{if(STATE.draft)STATE.protectUntil=Math.max(STATE.protectUntil,now()+1800);wave('surface-attribute')});
    STATE.observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-aura-conversation-drawer','data-aura-composer-surface']});
  }

  loadPersisted();
  setTimeout(()=>{captureNonEmpty('boot-nonempty');wave('boot')},180);
  window.addEventListener('load',()=>wave('load'),{once:true});

  window.AuraDraftRehydrate=Object.freeze({
    version:VERSION,
    get:()=>STATE.draft,
    capture:()=>captureNonEmpty('api-capture',2000),
    restore:()=>rehydrate('api-restore'),
    clear:()=>clearDraft('api-clear'),
    audit:()=>({version:VERSION,surface:surface(),draftLength:STATE.draft.length,globalLength:val(globalInput()).length,drawerLength:val(drawerInput()).length,activeLength:val(activeInput()).length,protectMs:Math.max(0,STATE.protectUntil-now()),sendPending:STATE.sendPending,lastReason:STATE.reason,autoSend:false,networkAccess:false,backgroundLlm:false,execution:'none'}),
    authority:'deferred-draft-presentation-continuity-no-send',autoSend:false,networkAccess:false,backgroundLlm:false
  });
  emit('aura:p0825-draft-rehydrate-ready',{features:['suggestion-contract-draft','synthetic-empty-guard','deferred-rehydrate-wave','trusted-clear-authority','send-clear-authority','session-ttl-mirror'],autoSend:false});
})();
