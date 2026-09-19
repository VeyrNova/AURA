/* AURA P0.8.2.7 — COMPOSER GEOMETRY ROOT-CAUSE FIX
   Root cause verified against the installed AURA bundle:
   - #messageInput native input handler auto-sizes from scrollHeight.
   - P0.8.2.3 could dispatch input while the global composer was display:none.
   - hidden textarea scrollHeight becomes 0, leaving inline height:0px after reveal.
   Fix:
   - drawer -> global/full: reveal global composer BEFORE draft synchronization;
   - drawer opening: copy the source draft BEFORE hiding global composer;
   - recover canonical textarea height after every surface transition;
   - retain one visible composer and no automatic Send.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0827_COMPOSER_GEOMETRY__)return;
  window.__AURA_P0827_COMPOSER_GEOMETRY__=true;

  const VERSION='P0.8.2.7';
  const STATE={mode:'global',lastReason:'boot',observer:null,lastHeight:0,lastValueLength:0};
  const q=(s,r=document)=>r.querySelector(s);
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));
  const visible=el=>{
    if(!el||!el.isConnected)return false;
    const s=getComputedStyle(el),r=el.getBoundingClientRect();
    return s.display!=='none'&&s.visibility!=='hidden'&&Number(s.opacity||1)>0&&r.width>2&&r.height>2;
  };

  function globalComposer(){return q('#composer.composer')||q('.workspace>.composer')||q('.composer:not(.aura-p0712-composer):not(.aura-p071-composer)')}
  function globalInput(){return q('#messageInput')}
  function drawerRoot(){return q('.aura-p0712-conversation-drawer')||q('.aura-p071-conversation-drawer')}
  function drawerInput(){return q('.aura-p0712-conversation-drawer [data-input]')||q('.aura-p071-conversation-drawer [data-input]')}
  function fullConversation(){return String(document.body.dataset.auraWorkspace||'').trim().toLowerCase()==='talk'}
  function drawerOpen(){
    if(fullConversation())return false;
    if(document.documentElement.dataset.auraConversationDrawer==='open')return true;
    try{return !!window.AuraConversationDrawer?.isOpen?.()}catch(_e){return false}
  }

  function exposeGlobal(exposed){
    const gc=globalComposer();
    document.body.classList.toggle('aura-p0823-single-composer',!exposed);
    if(gc){
      gc.dataset.auraComposerSuppressed=exposed?'false':'true';
      gc.setAttribute('aria-hidden',exposed?'false':'true');
    }
    return gc;
  }

  function copyDraft(next){
    const src=globalInput(),din=drawerInput();
    if(!src||!din)return false;
    if(next==='drawer'){
      if(din.value!==src.value){
        din.value=src.value||'';
        din.dispatchEvent(new Event('input',{bubbles:true}));
      }
      return true;
    }
    if(din.value!==src.value){
      src.value=din.value||'';
      // This event is now dispatched only AFTER the source composer has been exposed.
      src.dispatchEvent(new Event('input',{bubbles:true}));
    }
    return true;
  }

  function fitGlobalInput(reason='fit'){
    const src=globalInput(),gc=globalComposer();
    if(!src||!gc)return false;
    const cs=getComputedStyle(gc);
    if(cs.display==='none'||cs.visibility==='hidden')return false;
    src.style.height='auto';
    // Native AURA caps this textarea at 92 px. Keep the same contract with a safe floor.
    const measured=Number(src.scrollHeight||0);
    const height=Math.max(18,Math.min(92,measured||18));
    src.style.height=`${height}px`;
    STATE.lastHeight=height;STATE.lastValueLength=String(src.value||'').length;
    emit('aura:composer-height-recovered',{reason,height,valueLength:STATE.lastValueLength,autoSend:false});
    return true;
  }

  function recover(reason='recover'){
    requestAnimationFrame(()=>{
      fitGlobalInput(reason+'-raf');
      try{window.AuraConversationDraft?.restore?.()}catch(_e){}
      requestAnimationFrame(()=>fitGlobalInput(reason+'-settled'));
    });
    setTimeout(()=>fitGlobalInput(reason+'-80'),80);
    setTimeout(()=>fitGlobalInput(reason+'-220'),220);
  }

  function apply(reason='runtime'){
    const next=fullConversation()?'full':drawerOpen()?'drawer':'global';
    const activeDrawer=next==='drawer';

    if(activeDrawer){
      // SOURCE FIX: synchronize while the native composer is still measurable, then hide it.
      exposeGlobal(true);
      copyDraft('drawer');
      exposeGlobal(false);
    }else{
      // SOURCE FIX: reveal first, force layout, then synchronize so native auto-height never sees scrollHeight=0.
      const gc=exposeGlobal(true);
      if(gc)void gc.offsetHeight;
      copyDraft(next);
      recover(reason);
    }

    const dr=drawerRoot();
    if(dr)dr.dataset.auraComposerPrimary=activeDrawer?'true':'false';
    document.body.dataset.auraComposerSurface=next;
    document.documentElement.dataset.auraComposerSurface=next;

    const changed=STATE.mode!==next;STATE.mode=next;STATE.lastReason=reason;
    if(changed)emit('aura:composer-surface-changed',{surface:next,reason,autoSend:false});
    setTimeout(()=>window.AuraPanelBaseline?.run?.(),20);
    return next;
  }

  function schedule(reason='deferred',delay=0){setTimeout(()=>requestAnimationFrame(()=>apply(reason)),Math.max(0,delay))}

  ['aura:workspace-overlay-changed','aura:workspace-changed','aura:workspace-restored','aura:suggestion-prepared','aura:activity-center-opened','aura:activity-center-closed'].forEach(name=>window.addEventListener(name,()=>schedule(name,20)));
  document.addEventListener('click',event=>{
    if(event.target.closest?.('[data-rail-target="conversation"],[data-full],[data-close],[data-full-close],[data-full-min],[data-p082-prepare]')){
      schedule('ui-click',40);schedule('ui-click-late',180);
    }
  },true);
  document.addEventListener('input',event=>{
    if(event.target===globalInput()&&!drawerOpen())recover('global-input');
  },true);

  if(window.MutationObserver){
    STATE.observer=new MutationObserver(()=>schedule('drawer-attribute',0));
    STATE.observer.observe(document.documentElement,{attributes:true,attributeFilter:['data-aura-conversation-drawer']});
  }
  window.addEventListener('load',()=>schedule('load',100),{once:true});
  setTimeout(()=>apply('script-ready'),160);

  window.AuraComposerSurface=Object.freeze({
    version:VERSION,
    current:()=>STATE.mode,
    refresh:()=>apply('api'),
    recoverHeight:()=>{recover('api-height');return true},
    audit:()=>{
      const gc=globalComposer(),dr=drawerRoot(),src=globalInput(),din=drawerInput();
      return {
        version:VERSION,surface:STATE.mode,drawerOpen:drawerOpen(),fullConversation:fullConversation(),
        globalComposerFound:!!gc,globalComposerVisible:visible(gc),drawerFound:!!dr,drawerVisible:visible(dr),
        draftMatch:!!(src&&din)&&src.value===din.value,globalSuppressed:gc?.dataset?.auraComposerSuppressed==='true',
        globalInputValueLength:String(src?.value||'').length,globalInputInlineHeight:String(src?.style?.height||''),
        lastRecoveredHeight:STATE.lastHeight,rootCause:'hidden-scrollHeight-zero-fixed',
        autoSend:false,networkAccess:false,backgroundLlm:false,execution:'none'
      };
    },
    authority:'single-visible-composer-reveal-before-sync-height-safe-no-send',
    autoSend:false,networkAccess:false,backgroundLlm:false
  });
  emit('aura:p0827-composer-geometry-ready',{features:['reveal-before-sync','hidden-scrollheight-zero-guard','height-recovery','single-visible-composer','no-auto-send'],autoSend:false});
})();
