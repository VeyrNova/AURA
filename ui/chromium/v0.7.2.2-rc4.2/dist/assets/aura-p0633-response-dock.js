/* AURA P0.6.3.3 — Contextual Response Dock
   Keep contextual workspaces visible while still surfacing AURA's latest answer.
*/
(()=>{
  'use strict';

  const messages=document.querySelector('#messages');
  const workspace=document.querySelector('.workspace');
  if(!messages||!workspace)return;

  const token=new URLSearchParams(location.search).get('token')||'';

  const dock=document.createElement('aside');
  dock.className='aura-p0633-response-dock glass';
  dock.setAttribute('aria-live','polite');
  dock.innerHTML=`
    <header>
      <div><i></i><b>AURA</b><span data-context>RÉPONSE CONTEXTUELLE</span></div>
      <div class="aura-p0633-actions">
        <button data-replay title="Relire vocalement la réponse">◉ <span>RELIRE</span></button>
        <button data-talk title="Ouvrir la conversation complète">TALK</button>
        <button data-close aria-label="Fermer la réponse">×</button>
      </div>
    </header>
    <p data-text></p>
    <footer><span data-hint>Conversation conservée en arrière-plan</span></footer>`;
  workspace.appendChild(dock);

  const textEl=dock.querySelector('[data-text]');
  const contextEl=dock.querySelector('[data-context]');
  const replayBtn=dock.querySelector('[data-replay]');
  const talkBtn=dock.querySelector('[data-talk]');
  const closeBtn=dock.querySelector('[data-close]');
  const hintEl=dock.querySelector('[data-hint]');

  const LABELS={
    plan:'PLAN',
    weather:'WEATHER',
    memory:'MEM',
    system:'SYS',
  };

  let latestText='';
  let latestWorkspace='';
  let collapseTimer=0;
  let lastSeenNode=null;

  function currentWorkspace(){
    return String(
      document.body.dataset.auraWorkspace
      ||window.AuraWorkspace?.current?.()
      ||'home'
    ).trim().toLowerCase();
  }

  function hide(){
    clearTimeout(collapseTimer);
    dock.classList.remove('show','collapsed');
  }

  function scheduleCollapse(){
    clearTimeout(collapseTimer);
    collapseTimer=setTimeout(()=>{
      if(dock.classList.contains('show'))dock.classList.add('collapsed');
    },14000);
  }

  function showAnswer(text,workspaceId){
    const clean=String(text||'').trim();
    if(!clean||!LABELS[workspaceId])return;

    latestText=clean;
    latestWorkspace=workspaceId;
    textEl.textContent=clean;
    contextEl.textContent=`RÉPONSE · ${LABELS[workspaceId]}`;
    hintEl.textContent=`${LABELS[workspaceId]} reste au premier plan · TALK conserve l'historique`;

    dock.classList.remove('collapsed');
    dock.classList.add('show');
    scheduleCollapse();
  }

  async function localAction(action,payload={}){
    if(!token)throw new Error('token');
    const response=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{
      method:'POST',
      cache:'no-store',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action,...payload}),
    });
    let data={};try{data=await response.json()}catch{}
    if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);
    return data;
  }

  function inspectNode(node){
    if(!(node instanceof HTMLElement))return;
    if(!node.matches('.message.aura'))return;
    if(node===lastSeenNode)return;
    lastSeenNode=node;

    // Read only the message body's text; never clone or interpret model HTML.
    const body=node.querySelector('p');
    const text=String(body?.textContent||'').trim();
    const workspaceId=currentWorkspace();

    // HOME/TALK already expose the full Conversation surface. The contextual
    // dock is only useful when another workspace intentionally stays open.
    if(workspaceId==='home'||workspaceId==='talk'){
      hide();
      return;
    }
    showAnswer(text,workspaceId);
  }

  const observer=new MutationObserver(records=>{
    for(const record of records){
      for(const node of record.addedNodes){
        inspectNode(node);
      }
    }
  });
  observer.observe(messages,{childList:true});

  replayBtn.addEventListener('click',async()=>{
    if(!latestText)return;
    replayBtn.disabled=true;
    try{
      await localAction('voice_speak',{text:latestText});
      replayBtn.classList.add('ok');
      setTimeout(()=>replayBtn.classList.remove('ok'),700);
    }catch(_){
      replayBtn.classList.add('error');
      setTimeout(()=>replayBtn.classList.remove('error'),900);
    }finally{
      replayBtn.disabled=false;
      scheduleCollapse();
    }
  });

  talkBtn.addEventListener('click',()=>{
    hide();
    window.AuraWorkspace?.open?.('talk');
  });

  closeBtn.addEventListener('click',hide);

  // A collapsed response remains as a small unobtrusive pill. Clicking anywhere
  // on its body expands it again without changing keyboard focus.
  dock.addEventListener('click',event=>{
    if(!dock.classList.contains('collapsed'))return;
    if(event.target.closest('button'))return;
    dock.classList.remove('collapsed');
    scheduleCollapse();
  });

  window.addEventListener('aura:workspace-changed',event=>{
    const next=String(event.detail?.workspace||'home');
    if(next==='talk'||next==='home'){
      hide();
      return;
    }
    // A response belongs to the workspace in which it was generated. Do not
    // carry an old MEM answer into SYS, WEATHER, etc.
    if(latestWorkspace && next!==latestWorkspace)hide();
  });

  window.AuraResponseDock=Object.freeze({
    show(text,workspaceId=currentWorkspace()){
      showAnswer(text,String(workspaceId||''));
    },
    hide,
    latest(){
      return {text:latestText,workspace:latestWorkspace};
    },
  });
})();
