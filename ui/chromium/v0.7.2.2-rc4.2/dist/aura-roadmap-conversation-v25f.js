(()=>{
  'use strict';
  if(window.__AURA_ROADMAP_CONVERSATION_V25F1__)return;
  window.__AURA_ROADMAP_CONVERSATION_V25F1__=true;

  const token=new URLSearchParams(location.search).get('token')||'';
  const ENDPOINT=`/api/roadmap-conversation?token=${encodeURIComponent(token)}`;
  let busy=false;
  let bypass=false;

  const fold=s=>String(s||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();

  function activeInput(){
    try{
      if(String(window.AuraComposerSurface?.current?.()||'')==='drawer'){
        return document.querySelector('.aura-p0712-conversation-drawer [data-input]')
          ||document.querySelector('.aura-p071-conversation-drawer [data-input]');
      }
    }catch(_){}
    return document.querySelector('#messageInput')
      ||document.querySelector('.workspace>.composer textarea')
      ||document.querySelector('.workspace>.composer input[type="text"]')
      ||document.querySelector('#composer textarea')
      ||document.querySelector('#composer input[type="text"]');
  }

  function candidate(text){
    const f=fold(text);
    return /\broadmap\b/.test(f)
      || /\brm\d/.test(f)
      || f.includes('projet aura')
      || f.includes('prochaine etape')
      || f.includes('avancement du projet')
      || f.includes('progression du projet')
      || f.includes('fin estimee')
      || f.includes("jours d'avance")
      || f.includes('jours de retard')
      || f.includes('etapes bloquees')
      || f.includes('etape bloquee')
      || f.includes('phase du projet');
  }

  // AURA ROADMAP RM26-3B — DEV COMPOSER ROUTING GUARD
  function isDeveloperComposer(input){
    if(!input)return false;
    let placeholder='';
    try{
      placeholder=fold(input.getAttribute?.('placeholder')||input.placeholder||'');
    }catch(_){}
    if(placeholder.startsWith('aura dev'))return true;
    if(placeholder.includes('build, patch ou test'))return true;
    try{
      const root=input.closest?.(
        '[data-aura-developer],[data-developer-composer],.aura-developer,.aura-dev-composer'
      );
      if(root)return true;
    }catch(_){}
    return false;
  }

  function sendButton(input){
    if(!input)return document.querySelector('#sendBtn');
    const root=input.closest('form,.composer,#composer')||document;
    return root.querySelector('#sendBtn,button[type="submit"],button.send,.send-button,[data-send]')
      ||document.querySelector('#sendBtn');
  }

  function clearInput(input){
    if(!input)return;
    input.value='';
    input.dispatchEvent(new Event('input',{bubbles:true}));
    input.dispatchEvent(new Event('change',{bubbles:true}));
  }

  function fallbackNormal(input,button){
    bypass=true;
    try{
      if(button&&!button.disabled)button.click();
    }finally{
      setTimeout(()=>{bypass=false},0);
    }
  }

  async function dispatch(text,input,button){
    if(busy)return;
    busy=true;
    try{
      const response=await fetch(ENDPOINT,{
        method:'POST',
        cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({text})
      });
      let body={};
      try{body=await response.json()}catch(_){}
      if(!response.ok)throw new Error(body?.message||body?.error||`HTTP ${response.status}`);
      if(!body?.handled){
        fallbackNormal(input,button);
        return;
      }
      clearInput(input);
      if(body.ui_action==='open_roadmap'){
        document.querySelector('[data-roadmap-open-v25e]')?.click();
      }
      try{
        window.dispatchEvent(new CustomEvent('aura:roadmap-conversation',{
          detail:{intent:body.intent||'',mutation:body.mutation||null,handled:true}
        }));
      }catch(_){}
    }catch(err){
      console.warn('[AURA Roadmap V25-F1] fallback to normal conversation',err);
      fallbackNormal(input,button);
    }finally{
      busy=false;
    }
  }

  document.addEventListener('click',event=>{
    if(bypass||busy)return;
    const button=event.target.closest('#sendBtn,button[type="submit"],button.send,.send-button,[data-send]');
    if(!button)return;
    const input=activeInput();
    if(isDeveloperComposer(input))return;
    const text=String(input?.value||'').trim();
    if(!text||!candidate(text))return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    dispatch(text,input,button);
  },true);

  document.addEventListener('keydown',event=>{
    if(bypass||busy||event.key!=='Enter'||event.shiftKey||event.ctrlKey||event.altKey||event.metaKey)return;
    const input=activeInput();
    if(!input||event.target!==input)return;
    if(isDeveloperComposer(input))return;
    const text=String(input.value||'').trim();
    if(!text||!candidate(text))return;
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    dispatch(text,input,sendButton(input));
  },true);

  window.AuraRoadmapConversationV25F1={candidate};
})();
