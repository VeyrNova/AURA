/* AURA P0.8.2.6 — VISIBLE COMPOSER DRAFT AUTHORITY HOTFIX
   Canonical draft authority for Conversation handoff.
   Fixes the remaining case where a workspace/full-conversation transition creates or clears
   the visible composer after earlier restore waves have completed.
   Rules:
   - suggestion-prepared seeds one canonical local draft;
   - only the actually visible Conversation composer is rehydrated;
   - trusted user edits/clears are authoritative;
   - user Send clears the canonical draft after the UI accepts the send;
   - no automatic Send, no click(), no network, no LLM, no Core/voice action.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0826_VISIBLE_COMPOSER_DRAFT_AUTHORITY__)return;
  window.__AURA_P0826_VISIBLE_COMPOSER_DRAFT_AUTHORITY__=true;

  const VERSION='P0.8.2.6';
  const STORE_KEY='aura.p0826.canonicalDraft';
  const TTL=2*60*60*1000;
  const STATE={draft:'',updatedAt:0,lastReason:'boot',restoring:false,timer:0,lastSurface:'',sendPending:false};
  const q=(s,r=document)=>r.querySelector(s);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const now=()=>Date.now();
  const val=el=>String(el?.value??'');
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));

  function visible(el){
    if(!el||!el.isConnected||el.disabled)return false;
    const s=getComputedStyle(el),r=el.getBoundingClientRect();
    if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity||1)<=0)return false;
    if(r.width<8||r.height<8)return false;
    const hiddenParent=el.closest?.('[hidden],[aria-hidden="true"]');
    if(hiddenParent&&hiddenParent!==el)return false;
    return true;
  }
  function drawerInput(){return q('.aura-p0712-conversation-drawer [data-input]')||q('.aura-p071-conversation-drawer [data-input]')}
  function globalInputs(){
    const list=[];
    const add=el=>{if(el&&!list.includes(el))list.push(el)};
    add(q('#messageInput'));
    qa('#composer textarea,#composer input[type="text"],.workspace>.composer textarea,.workspace>.composer input[type="text"],.workspace .composer textarea,.workspace .composer input[type="text"]').forEach(add);
    return list;
  }
  function candidates(){
    const out=[];const add=el=>{if(el&&!out.includes(el))out.push(el)};
    add(drawerInput());globalInputs().forEach(add);return out;
  }
  function drawerOpen(){
    if(document.documentElement.dataset.auraConversationDrawer==='open')return true;
    try{return !!window.AuraConversationDrawer?.isOpen?.()}catch(_e){return false}
  }
  function fullConversation(){return String(document.body.dataset.auraWorkspace||'').trim().toLowerCase()==='talk'}
  function surfaceName(el){
    if(!el)return'none';
    if(el===drawerInput())return'drawer';
    if(fullConversation())return'full';
    return'global';
  }
  function activeVisibleInput(){
    const din=drawerInput();
    if(drawerOpen()&&visible(din))return din;
    const globals=globalInputs().filter(visible);
    if(globals.length)return globals.sort((a,b)=>b.getBoundingClientRect().width-a.getBoundingClientRect().width)[0];
    if(visible(din))return din;
    return candidates().find(visible)||null;
  }

  function persist(){
    try{
      if(!STATE.draft){sessionStorage.removeItem(STORE_KEY);return}
      sessionStorage.setItem(STORE_KEY,JSON.stringify({text:STATE.draft,ts:STATE.updatedAt||now()}));
    }catch(_e){}
  }
  function load(){
    try{
      const raw=JSON.parse(sessionStorage.getItem(STORE_KEY)||'null');
      if(raw&&typeof raw.text==='string'&&raw.text&&now()-Number(raw.ts||0)<TTL){STATE.draft=raw.text;STATE.updatedAt=Number(raw.ts)||now();STATE.lastReason='session';return true}
      sessionStorage.removeItem(STORE_KEY);
    }catch(_e){}
    return false;
  }
  function setDraft(text,reason='set'){
    STATE.draft=String(text??'');STATE.updatedAt=now();STATE.lastReason=reason;persist();return STATE.draft;
  }
  function clearDraft(reason='clear'){
    STATE.draft='';STATE.updatedAt=now();STATE.lastReason=reason;persist();emit('aura:p0826-draft-cleared',{reason,autoSend:false});
  }
  function promptFor(eventId){
    try{
      const list=window.AuraSuggestionEngine?.suggestions?.();
      const s=Array.isArray(list)?(list.find(x=>String(x?.eventId||'')===String(eventId||''))||window.AuraSuggestionEngine?.top?.()):window.AuraSuggestionEngine?.top?.();
      return String(s?.prompt||'');
    }catch(_e){return''}
  }
  function seedFromExisting(reason='existing'){
    const vis=activeVisibleInput();if(vis&&val(vis))return setDraft(val(vis),reason+'-visible');
    for(const el of candidates()){if(val(el))return setDraft(val(el),reason+'-candidate')}
    try{const t=String(window.AuraDraftRehydrate?.get?.()||'');if(t)return setDraft(t,reason+'-p0825')}catch(_e){}
    return STATE.draft;
  }
  function write(el,text,reason){
    if(!el||!text||val(el)===text)return false;
    STATE.restoring=true;
    try{
      el.value=text;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      try{el.setSelectionRange?.(text.length,text.length)}catch(_e){}
      STATE.lastReason=reason;
    }finally{STATE.restoring=false}
    return true;
  }
  function reconcile(reason='interval'){
    if(STATE.sendPending)return false;
    if(!STATE.draft)seedFromExisting(reason+'-seed');
    if(!STATE.draft)return false;
    const target=activeVisibleInput();if(!target)return false;
    const current=val(target);
    STATE.lastSurface=surfaceName(target);
    if(current)return false; // Never overwrite a non-empty visible user/program state.
    const changed=write(target,STATE.draft,reason+'-'+STATE.lastSurface);
    if(changed)emit('aura:draft-restored',{surface:STATE.lastSurface,reason,length:STATE.draft.length,canonical:true,autoSend:false});
    return changed;
  }

  function isComposerInput(el){return !!el&&candidates().includes(el)}
  document.addEventListener('input',event=>{
    const el=event.target;if(!isComposerInput(el)||STATE.restoring)return;
    const text=val(el);
    if(event.isTrusted){setDraft(text,text?'trusted-edit':'trusted-clear');return}
    if(text&&!STATE.draft)setDraft(text,'synthetic-seed');
    // Synthetic empty never clears canonical state.
  },true);

  document.addEventListener('click',event=>{
    const send=event.target.closest?.('#sendBtn,.aura-p0712-conversation-drawer [data-send],.aura-p071-conversation-drawer [data-send]');
    if(send&&event.isTrusted){
      seedFromExisting('pre-send');STATE.sendPending=true;
      setTimeout(()=>{
        const still=candidates().map(val).find(Boolean)||'';
        if(still){STATE.sendPending=false;setDraft(still,'send-retained');reconcile('send-retained');return}
        clearDraft('send-accepted');STATE.sendPending=false;
      },700);
    }
    if(event.target.closest?.('[data-close],[data-full],[data-full-close],[data-full-min],[data-rail-target="conversation"]')){
      seedFromExisting('pre-surface-click');setTimeout(()=>reconcile('post-surface-click'),40);setTimeout(()=>reconcile('post-surface-click-late'),500);
    }
  },true);

  window.addEventListener('aura:suggestion-prepared',event=>{
    const prompt=promptFor(event.detail?.eventId)||seedFromExisting('suggestion-fallback');
    if(prompt)setDraft(prompt,'suggestion-contract');
    [0,40,120,300,700,1400,2600].forEach(ms=>setTimeout(()=>reconcile('suggestion-'+ms),ms));
  });
  ['aura:composer-surface-changed','aura:workspace-will-change','aura:workspace-changed','aura:workspace-restored','aura:workspace-overlay-changed'].forEach(name=>window.addEventListener(name,()=>{
    seedFromExisting(name);[0,60,220,650,1400].forEach(ms=>setTimeout(()=>reconcile(name+'-'+ms),ms));
  }));

  load();setTimeout(()=>{seedFromExisting('boot');reconcile('boot')},180);
  STATE.timer=setInterval(()=>reconcile('authority-loop'),250);

  window.AuraConversationDraft=Object.freeze({
    version:VERSION,
    get:()=>STATE.draft,
    set:text=>{setDraft(text,'api-set');reconcile('api-set');return STATE.draft},
    restore:()=>reconcile('api-restore'),
    clear:()=>clearDraft('api-clear'),
    active:()=>{const el=activeVisibleInput();return {surface:surfaceName(el),found:!!el,length:val(el).length}},
    audit:()=>{const el=activeVisibleInput();return {version:VERSION,draftLength:STATE.draft.length,activeSurface:surfaceName(el),activeLength:val(el).length,candidateCount:candidates().length,visibleCandidates:candidates().filter(visible).length,lastReason:STATE.lastReason,sendPending:STATE.sendPending,intervalMs:250,autoSend:false,networkAccess:false,backgroundLlm:false,execution:'none'}},
    authority:'canonical-draft-visible-composer-no-send',autoSend:false,networkAccess:false,backgroundLlm:false
  });
  emit('aura:p0826-visible-composer-draft-ready',{authority:'canonical-draft-visible-composer-no-send',features:['canonical-draft','visible-composer-selection','continuous-rehydrate','trusted-user-clear','send-clear','suggestion-contract-seed'],autoSend:false});
})();
