/* AURA P0.8.4 — SENSITIVE ACTION CONFIRMATION
   Roadmap n074: explicit user confirmation for risky actions.
   Security contract:
   - Reuses existing security-policy ownership; this layer does NOT decide/execute OS actions.
   - ALLOW: callers may proceed under their existing policy.
   - CONFIRM: explicit modal approval required, bound to exact action + target, short-lived, one-shot receipt.
   - DENY: immediate refusal, no modal and no executor call.
   - No network, no background LLM, no programmatic click, no automatic action.
*/
(()=>{
  'use strict';
  if(window.__AURA_P084_SENSITIVE_ACTION_CONFIRMATION__)return;
  window.__AURA_P084_SENSITIVE_ACTION_CONFIRMATION__=true;

  const VERSION='P0.8.4';
  const CONFIRM_TTL_MS=30000;
  const RECEIPT_TTL_MS=15000;
  const MAX_HISTORY=50;
  const ACTION_POLICY=Object.freeze({
    open_calculator:'allow',open_notepad:'allow',open_explorer:'allow',open_paint:'allow',
    read_file:'allow',search_files:'allow',open_file:'allow',
    write_file:'confirm',rename_file:'confirm',move_file:'confirm',delete_file:'confirm',
    send_email:'confirm',run_program:'confirm',install_software:'confirm',modify_system:'confirm',
    shutdown:'confirm',reboot:'confirm',kill_process:'confirm',network_change:'confirm'
  });
  const CRITICAL=new Set(['delete_file','install_software','modify_system','shutdown','reboot','kill_process','network_change']);
  const STATE={active:null,queue:[],host:null,timer:0,receipts:new Map(),history:[],decorTimer:0,lastTest:null};
  const q=(s,r=document)=>r.querySelector(s);
  const safe=(v,n=300)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const clone=v=>{try{return JSON.parse(JSON.stringify(v))}catch(_e){return null}};
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const emit=(name,detail)=>window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}));
  const now=()=>Date.now();
  function uuid(){try{return crypto.randomUUID()}catch(_e){return `p084-${now().toString(36)}-${Math.random().toString(36).slice(2,10)}`}}
  function actionKey(meta){return `${safe(meta.action,80).toLowerCase()}|${safe(meta.target,260)}|${safe(meta.summary,260)}`}
  function normalizeRisk(v,action){const r=safe(v,30).toLowerCase();if(['low','medium','high','critical'].includes(r))return r;return CRITICAL.has(action)?'critical':'high'}
  function policy(action,requested){
    const a=safe(action,80).toLowerCase();const explicit=safe(requested,20).toLowerCase();
    if(explicit==='deny')return'deny';if(explicit==='allow'&&ACTION_POLICY[a]==='allow')return'allow';
    return ACTION_POLICY[a]||'confirm';
  }
  function normalize(raw){
    if(!raw||typeof raw!=='object')return null;const action=safe(raw.action,80).toLowerCase();if(!action)return null;
    const decision=policy(action,raw.policy);return {id:safe(raw.id,100)||uuid(),action,target:safe(raw.target,300)||'Cible non précisée',summary:safe(raw.summary,420)||`Autoriser l’action « ${action} » ?`,reason:safe(raw.reason,420)||'Cette action peut modifier l’état local et nécessite votre accord explicite.',risk:normalizeRisk(raw.risk,action),decision,source:safe(raw.source,100)||'aura-local',simulation:!!raw.simulation,requestedAt:now(),expiresAt:now()+CONFIRM_TTL_MS};
  }
  function record(meta,outcome,extra={}){const row={at:new Date().toISOString(),action:meta?.action||'',risk:meta?.risk||'',outcome,source:meta?.source||'',simulation:!!meta?.simulation,...extra};STATE.history.unshift(row);STATE.history=STATE.history.slice(0,MAX_HISTORY);renderControl();emit('aura:sensitive-action-decision',clone(row));return row}
  function cleanupReceipts(){const t=now();for(const [id,r] of STATE.receipts)if(r.expiresAt<=t||r.used)STATE.receipts.delete(id)}
  function issueReceipt(meta){cleanupReceipts();const id=uuid(),receipt={id,key:actionKey(meta),action:meta.action,target:meta.target,issuedAt:now(),expiresAt:now()+RECEIPT_TTL_MS,used:false};STATE.receipts.set(id,receipt);return clone(receipt)}
  function consume(receiptId,raw){cleanupReceipts();const r=STATE.receipts.get(safe(receiptId,120));const meta=normalize(raw);if(!r||!meta||r.used||r.expiresAt<=now()||r.key!==actionKey(meta))return false;r.used=true;STATE.receipts.delete(r.id);emit('aura:sensitive-action-receipt-consumed',{receiptId:r.id,action:r.action,target:r.target});return true}

  function ensureHost(){if(STATE.host?.isConnected)return STATE.host;const host=document.createElement('div');host.className='aura-p084-confirm-host';host.hidden=true;host.setAttribute('aria-live','assertive');document.body.appendChild(host);STATE.host=host;return host}
  function riskLabel(r){return r==='critical'?'CRITIQUE':r==='high'?'ÉLEVÉ':r==='medium'?'MODÉRÉ':'FAIBLE'}
  function renderModal(meta){
    const host=ensureHost(),critical=meta.risk==='critical';host.hidden=false;host.dataset.risk=meta.risk;host.innerHTML=`<div class="aura-p084-backdrop" aria-hidden="true"></div><section class="aura-p084-dialog" role="alertdialog" aria-modal="true" aria-labelledby="p084-title" aria-describedby="p084-desc"><header><span><small>AURA · CONFIRMATION SENSIBLE</small><b id="p084-title">AUTORISATION REQUISE</b></span><i data-p084-risk>${riskLabel(meta.risk)}</i></header><div class="aura-p084-body"><p id="p084-desc">${esc(meta.summary)}</p><dl><div><dt>ACTION</dt><dd>${esc(meta.action.toUpperCase())}</dd></div><div><dt>CIBLE</dt><dd>${esc(meta.target)}</dd></div><div><dt>POURQUOI</dt><dd>${esc(meta.reason)}</dd></div></dl>${meta.simulation?'<div class="aura-p084-simulation">SIMULATION LOCALE · aucune action réelle ne sera exécutée.</div>':''}${critical?'<label class="aura-p084-ack"><input type="checkbox" data-p084-ack> <span>Je comprends que cette action peut modifier ou supprimer des données / paramètres.</span></label>':''}<div class="aura-p084-expiry"><span>Cette demande expire automatiquement.</span><b data-p084-countdown>30 s</b></div></div><footer><button type="button" data-p084-cancel>ANNULER</button><button type="button" data-p084-confirm ${critical?'disabled aria-disabled="true"':''}>CONFIRMER</button></footer><small class="aura-p084-foot">Aucune action ne part avant votre confirmation explicite.</small></section>`;
    requestAnimationFrame(()=>host.classList.add('open'));q('[data-p084-cancel]',host)?.focus?.();
  }
  function closeModal(){clearInterval(STATE.timer);STATE.timer=0;if(!STATE.host)return;STATE.host.classList.remove('open');STATE.host.hidden=true;STATE.host.innerHTML=''}
  function settle(outcome,reason='user'){
    const cur=STATE.active;if(!cur)return false;STATE.active=null;closeModal();let result;
    if(outcome==='confirmed'){const receipt=issueReceipt(cur.meta);record(cur.meta,'confirmed',{receiptId:receipt.id});result={ok:true,confirmed:true,decision:'confirm',reason:'user-confirmed',receipt,action:cur.meta.action,target:cur.meta.target,simulation:cur.meta.simulation,autoAction:false}}
    else{record(cur.meta,outcome,{reason});result={ok:false,confirmed:false,decision:cur.meta.decision,reason,action:cur.meta.action,target:cur.meta.target,simulation:cur.meta.simulation,autoAction:false}}
    try{cur.resolve(result)}catch(_e){};emit(outcome==='confirmed'?'aura:sensitive-action-confirmed':'aura:sensitive-action-cancelled',clone(result));setTimeout(processQueue,0);return true
  }
  function tick(){const cur=STATE.active;if(!cur)return;const left=Math.max(0,cur.meta.expiresAt-now());const el=q('[data-p084-countdown]',STATE.host);if(el)el.textContent=`${Math.ceil(left/1000)} s`;if(left<=0)settle('expired','expired')}
  function processQueue(){if(STATE.active||!STATE.queue.length)return;const item=STATE.queue.shift();STATE.active=item;renderModal(item.meta);tick();STATE.timer=setInterval(tick,250)}
  function request(raw){
    const meta=normalize(raw);if(!meta)return Promise.resolve({ok:false,confirmed:false,decision:'deny',reason:'invalid-request',autoAction:false});
    if(meta.decision==='deny'){record(meta,'denied',{reason:'policy-deny'});return Promise.resolve({ok:false,confirmed:false,decision:'deny',reason:'policy-deny',action:meta.action,target:meta.target,autoAction:false})}
    if(meta.decision==='allow'){record(meta,'allowed',{reason:'policy-allow'});return Promise.resolve({ok:true,confirmed:true,decision:'allow',reason:'policy-allow',action:meta.action,target:meta.target,receipt:null,autoAction:false})}
    if(STATE.queue.length>=5){record(meta,'denied',{reason:'confirmation-queue-full'});return Promise.resolve({ok:false,confirmed:false,decision:'confirm',reason:'confirmation-queue-full',autoAction:false})}
    return new Promise(resolve=>{STATE.queue.push({meta,resolve});emit('aura:sensitive-action-pending',{action:meta.action,target:meta.target,risk:meta.risk,simulation:meta.simulation,expiresAt:meta.expiresAt});processQueue()})
  }

  function ensureControl(){
    const root=q('.aura-p081-panel');if(!root||root.hidden)return null;let box=q('.aura-p084-control',root);if(!box){box=document.createElement('section');box.className='aura-p084-control aura-p081-section';box.innerHTML=`<div class="aura-p084-control-head"><span><small>ACTIONS SENSIBLES · v1.0.0</small><b>CONFIRMATION EXPLICITE</b></span><i data-p084-status>PROTECTION ACTIVE</i></div><p>Les actions à risque classées CONFIRM doivent être approuvées avant exécution. Le reçu est lié à l’action et à sa cible, puis expire.</p><div class="aura-p084-control-actions"><button type="button" data-p084-test>TEST CONFIRMATION</button><span data-p084-test-state>Aucune action automatique.</span></div>`;const anchor=q('.aura-p083-settings',root)||q('.aura-p082-engine-strip',root)||q('.aura-p081-overview',root);anchor?.insertAdjacentElement('afterend',box)}renderControl(box);return box
  }
  function renderControl(box=ensureControl()){if(!box)return;const st=q('[data-p084-status]',box);if(st)st.textContent=STATE.active?'CONFIRMATION EN ATTENTE':'PROTECTION ACTIVE';const s=q('[data-p084-test-state]',box);if(s&&STATE.lastTest)s.textContent=STATE.lastTest}
  async function testConfirmation(){
    const box=ensureControl(),btn=q('[data-p084-test]',box);if(btn)btn.disabled=true;STATE.lastTest='Simulation en attente de votre décision…';renderControl(box);
    const r=await request({action:'delete_file',target:'SIMULATION · C:\\AURA\\test_confirmation.txt',summary:'Simuler la suppression d’un fichier test AURA.',reason:'Valider la barrière Sensitive Action Confirmation sans toucher au système de fichiers.',risk:'critical',policy:'confirm',source:'p084-local-test',simulation:true});
    STATE.lastTest=r.confirmed?'TEST CONFIRMÉ · aucun fichier supprimé.':r.reason==='expired'?'TEST EXPIRÉ · aucune action.':'TEST ANNULÉ · aucune action.';if(btn)btn.disabled=false;renderControl(box);emit('aura:sensitive-action-test',{confirmed:!!r.confirmed,reason:r.reason,simulation:true,autoAction:false});return r
  }
  function onClick(e){const ack=e.target.closest?.('[data-p084-ack]');if(ack){const b=q('[data-p084-confirm]',STATE.host);if(b){b.disabled=!ack.checked;b.setAttribute('aria-disabled',String(!ack.checked))}return}if(e.target.closest?.('[data-p084-cancel]')){e.preventDefault();e.stopImmediatePropagation();settle('cancelled','user-cancelled');return}if(e.target.closest?.('[data-p084-confirm]')){e.preventDefault();e.stopImmediatePropagation();const b=e.target.closest('[data-p084-confirm]');if(!b.disabled)settle('confirmed','user-confirmed');return}if(e.target.closest?.('[data-p084-test]')){e.preventDefault();e.stopImmediatePropagation();testConfirmation();return}}
  function scheduleDecor(ms=40){clearTimeout(STATE.decorTimer);STATE.decorTimer=setTimeout(()=>ensureControl(),ms)}
  function bootstrap(){
    document.addEventListener('click',onClick,true);document.addEventListener('change',onClick,true);document.addEventListener('keydown',e=>{if(e.key==='Escape'&&STATE.active){e.preventDefault();e.stopImmediatePropagation();settle('cancelled','escape')}},true);
    window.addEventListener('aura:sensitive-action-request',e=>{const d=e.detail||{};request(d).then(r=>{try{if(typeof d.resolve==='function')d.resolve(r)}catch(_e){}})});
    window.addEventListener('aura:activity-center-opened',()=>scheduleDecor(20));window.addEventListener('aura:event-watchers-ui-activated',()=>scheduleDecor(80));
    setTimeout(()=>scheduleDecor(0),180);setTimeout(()=>scheduleDecor(0),900);
    emit('aura:sensitive-actions-ready',{policy:'ALLOW/CONFIRM/DENY',confirmationTtlMs:CONFIRM_TTL_MS,receiptTtlMs:RECEIPT_TTL_MS,oneShotReceipt:true,networkAccess:false,backgroundLlm:false,autoAction:false,executesActions:false});
  }
  window.AuraSensitiveActions=Object.freeze({version:VERSION,request,consume,classify:(action,requested)=>policy(action,requested),history:()=>STATE.history.map(clone),pending:()=>STATE.active?clone(STATE.active.meta):null,test:testConfirmation,audit:()=>({active:!!STATE.active,queued:STATE.queue.length,receipts:STATE.receipts.size,history:STATE.history.length,confirmationTtlMs:CONFIRM_TTL_MS,receiptTtlMs:RECEIPT_TTL_MS,networkAccess:false,backgroundLlm:false,autoAction:false,executesActions:false}),authority:'confirmation-only-no-execution'});
  bootstrap();
})();
