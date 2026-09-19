/* AURA P0.8.2.1 — CONTROLLED SUGGESTION TEST HOTFIX
   Safe local validation surface for P0.8.2 Suggestion Engine.
   - No CPU/RAM/GPU stress.
   - No LLM call and no network request.
   - Never enables a watcher automatically.
   - Publishes one clearly simulated event through AuraEventWatchers only after explicit click.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0821_CONTROLLED_TEST__)return;
  window.__AURA_P0821_CONTROLLED_TEST__=true;

  const VERSION='P0.8.2.1';
  const q=(s,r=document)=>r.querySelector(s);
  const safe=(v,n=240)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const watchers=()=>window.AuraEventWatchers;
  const engine=()=>window.AuraSuggestionEngine;
  let timer=0;

  function systemEnabled(){
    try{return !!watchers()?.settings?.()?.families?.system}catch(_e){return false}
  }
  function panel(){return q('.aura-p081-panel')}
  function strip(root=panel()){return root?q('.aura-p082-engine-strip',root):null}
  function setStatus(text,kind='info'){
    const root=panel(),box=root&&q('.aura-p0821-test-status',root);if(!box)return;
    box.textContent=safe(text,260);box.dataset.kind=kind;
  }
  function renderState(root=panel()){
    if(!root)return false;const bar=q('.aura-p0821-testbar',root);if(!bar)return false;
    const button=q('[data-p0821-test-local]',bar),on=systemEnabled();
    if(button){button.disabled=!on;button.setAttribute('aria-disabled',String(!on));button.title=on?'Injecter une détection système simulée':'Activez d’abord la surveillance SYSTÈME'}
    const gate=q('[data-p0821-gate]',bar);if(gate)gate.textContent=on?'SYSTÈME AUTORISÉ · PRÊT':'ACTIVEZ SYSTÈME POUR TESTER';
    return true;
  }
  function ensureBar(){
    const root=panel(),anchor=strip(root);if(!root||root.hidden||!anchor)return false;
    let bar=q('.aura-p0821-testbar',root);
    if(!bar){
      bar=document.createElement('section');bar.className='aura-p0821-testbar';
      bar.innerHTML=`<div class="aura-p0821-test-copy"><span><small>VALIDATION CONTRÔLÉE · v1.0.0</small><b>TEST LOCAL SANS CHARGE SYSTÈME</b></span><i data-p0821-gate>ÉTAT</i></div><div class="aura-p0821-test-actions"><button type="button" data-p0821-test-local>TEST LOCAL</button><span class="aura-p0821-test-status" data-kind="info">Simule une RAM à 96 % sans modifier les ressources réelles.</span></div>`;
      anchor.insertAdjacentElement('afterend',bar);
    }
    renderState(root);return true;
  }
  function schedule(delay=40){clearTimeout(timer);timer=setTimeout(()=>requestAnimationFrame(()=>ensureBar()),Math.max(0,delay))}

  function runControlledTest(){
    const w=watchers(),e=engine();
    if(!w||typeof w.publish!=='function'){setStatus('Event Watchers indisponible.','error');return false}
    if(!e){setStatus('Suggestion Engine indisponible.','error');return false}
    if(!systemEnabled()){setStatus('Activez SYSTÈME avant de lancer le test.','warn');renderState();return false}
    const ok=w.publish({
      family:'system',
      severity:'important',
      title:'Test contrôlé P0.8.2.1',
      message:'RAM simulée à 96 % de manière soutenue. Aucun usage mémoire réel n’a été modifié.',
      source:'test-local-controlled',
      fingerprint:'p0821-controlled-system-test',
      suggestion:'Analyse cette simulation de pression mémoire. Propose uniquement des vérifications sûres et explique la priorité, sans exécuter aucune action.',
      meta:{controlledTest:true,simulated:true,realSystemImpact:false,expectedPriority:'high',expectedScore:81}
    });
    if(ok){
      setStatus('Test injecté · priorité HAUTE attendue (~81). Utilisez POURQUOI ? puis PRÉPARER AVEC AURA.','ok');
      setTimeout(()=>{try{e.refresh?.()}catch(_e){} schedule(20)},30);
      window.dispatchEvent(new CustomEvent('aura:p0821-controlled-test',{detail:{version:VERSION,ok:true,simulated:true,expectedPriority:'high',expectedScore:81,autoSend:false,systemImpact:false}}));
      return true;
    }
    setStatus('Test non injecté : déjà présent récemment ou surveillance non autorisée. Effacez l’historique puis réessayez.','warn');return false;
  }

  document.addEventListener('click',ev=>{
    const b=ev.target.closest?.('[data-p0821-test-local]');if(b){ev.preventDefault();ev.stopImmediatePropagation();runControlledTest();return}
    if(ev.target.closest?.('[data-module="activity-center"],[data-p081-family],[data-p081-action]'))schedule(80);
  },true);
  window.addEventListener('aura:event-watchers-ui-activated',()=>schedule(80));
  window.addEventListener('aura:activity-center-opened',()=>schedule(60));
  window.addEventListener('aura:watcher-permission-changed',()=>schedule(20));
  window.addEventListener('aura:suggestion-created',()=>schedule(20));
  window.addEventListener('aura:watcher-events-cleared',()=>{schedule(20);setTimeout(()=>setStatus('Historique effacé. Le test peut être relancé.','info'),50)});
  setTimeout(()=>schedule(0),180);

  window.AuraSuggestionControlledTest=Object.freeze({version:VERSION,run:runControlledTest,ready:()=>!!(watchers()&&engine()),systemEnabled,authority:'explicit-click-simulated-event-only',networkAccess:false,backgroundLlm:false,systemImpact:false,autoSend:false});
  window.dispatchEvent(new CustomEvent('aura:p0821-controlled-test-ready',{detail:{version:VERSION,authority:'explicit-click-simulated-event-only',networkAccess:false,backgroundLlm:false,systemImpact:false,autoSend:false}}));
})();
