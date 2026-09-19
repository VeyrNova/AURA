/* AURA v2.3 Skills Center */
(()=>{
'use strict';
if(window.__AURA_V23_SKILLS_CENTER__)return;
window.__AURA_V23_SKILLS_CENTER__=true;

const SKILLS=[{"skill_id":"developer","title":"Developer","description":"Contexte Developer Fabric et workspace. L'Ã©tat Ã©phÃ©mÃ¨re workspace reste exÃ©cutÃ© par le shell/MainWindow existant.","commands":["workspace_context"],"permissions":["developer_workspace"],"owner":"ui.shell_host","risk":"developer_context","version":"2.3.0","enabled":true},{"skill_id":"files","title":"Fichiers","description":"Cycle de contexte fichier de l'interface. Les lectures autorisÃ©es restent propriÃ©taires du skill systÃ¨me.","commands":["file_clear"],"permissions":["conversation_file_context"],"owner":"services.core_bridge","risk":"local_context","version":"2.3.0","enabled":true},{"skill_id":"memory","title":"MÃ©moire","description":"CrÃ©ation, suppression et mode privÃ© de mÃ©moire via le MemoryService existant.","commands":["memory_clear_profile","memory_create","memory_delete","memory_private"],"permissions":["personal_memory"],"owner":"services.core_bridge","risk":"personal_data_mutation","version":"2.3.0","enabled":true},{"skill_id":"navigation","title":"Navigation","description":"Cartographie, itinÃ©raires et localisation. Fondation dÃ©clarative avant branchement dÃ©diÃ©.","commands":[],"permissions":["network","location_context"],"owner":"tools.maps","risk":"network_read","version":"2.3.0","enabled":true},{"skill_id":"productivity","title":"ProductivitÃ©","description":"Notes, tÃ¢ches et rappels via les services existants.","commands":["note_create","note_delete","reminder_create","reminder_delete","task_complete","task_create"],"permissions":["local_storage"],"owner":"services.core_bridge","risk":"local_mutation","version":"2.3.0","enabled":true},{"skill_id":"research","title":"Recherche","description":"Recherche Web et investigation explicite via les exÃ©cuteurs dÃ©jÃ  validÃ©s.","commands":["research_query"],"permissions":["network"],"owner":"services.core_bridge","risk":"network_read","version":"2.3.0","enabled":true},{"skill_id":"system","title":"SystÃ¨me","description":"Actions PC et fichiers explicitement autorisÃ©s, avec les garde-fous existants.","commands":["system_analyze_authorized_file","system_analyze_authorized_project","system_authorize_folder","system_open_folder","system_open_safe_app","system_read_authorized_file","system_revoke_folder","system_scan_folder"],"permissions":["filesystem_authorized","desktop_control"],"owner":"services.core_bridge","risk":"privileged_local_action","version":"2.3.0","enabled":true},{"skill_id":"voice","title":"Voix","description":"Sortie vocale et arrÃªt vocal. Le microphone reste une commande UI explicite hors Skills.","commands":["nav_speak","stop_speaking","voice_speak"],"permissions":["audio_output"],"owner":"services.core_bridge","risk":"audio_output","version":"2.3.0","enabled":true},{"skill_id":"weather","title":"MÃ©tÃ©o","description":"MÃ©tÃ©o courante via le service mÃ©tÃ©o existant.","commands":["weather_current"],"permissions":["network","location_context"],"owner":"services.core_bridge","risk":"network_read","version":"2.3.0","enabled":true}];
const state={
  open:false,
  events:[],
  bySkill:Object.fromEntries(SKILLS.map(s=>[s.skill_id,{last:null,count:0}]))
};
const q=(s,r=document)=>r.querySelector(s);
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));

function modeLabel(d){
  const mode=String(d?.mode||'').toUpperCase();
  const phase=String(d?.phase||'').toUpperCase();
  if(mode==='EXECUTE')return phase?`EXECUTE Â· ${phase}`:'EXECUTE';
  if(mode==='CONSULT')return 'CONSULT';
  return mode||'IDLE';
}
function statusClass(d){
  const mode=String(d?.mode||'').toLowerCase();
  const phase=String(d?.phase||'').toLowerCase();
  if(['rejected','error','failed'].includes(phase))return 'error';
  if(mode==='execute')return 'execute';
  if(mode==='consult')return 'consult';
  return 'idle';
}
function cardState(skill){
  const live=state.bySkill[skill.skill_id]?.last;
  if(live)return modeLabel(live);
  if(!skill.enabled)return 'DISABLED';
  if(!(skill.commands||[]).length)return 'FOUNDATION';
  return 'READY';
}
function cardClass(skill){
  const live=state.bySkill[skill.skill_id]?.last;
  if(live)return statusClass(live);
  if(!skill.enabled)return 'error';
  if(!(skill.commands||[]).length)return 'foundation';
  return 'ready';
}
function renderCards(){
  const grid=q('[data-aura-v23-skills-grid]');
  if(!grid)return;
  grid.innerHTML=SKILLS.map(skill=>{
    const b=state.bySkill[skill.skill_id]||{};
    const last=b.last;
    const perms=(skill.permissions||[]).join(' Â· ')||'Aucune';
    return `<article class="aura-v23-skill-card ${cardClass(skill)}">
      <div class="aura-v23-skill-card-head">
        <div><span class="aura-v23-skill-kicker">${esc(skill.skill_id).toUpperCase()}</span>
        <h3>${esc(skill.title)}</h3></div>
        <span class="aura-v23-skill-state">${esc(cardState(skill))}</span>
      </div>
      <p class="aura-v23-skill-desc">${esc(skill.description)}</p>
      <div class="aura-v23-skill-meta">
        <div><span>OWNER</span><strong>${esc(skill.owner)}</strong></div>
        <div><span>RISK</span><strong>${esc(skill.risk)}</strong></div>
        <div><span>COMMANDS</span><strong>${(skill.commands||[]).length}</strong></div>
        <div><span>EVENTS</span><strong>${Number(b.count||0)}</strong></div>
      </div>
      <div class="aura-v23-skill-foot"><span>PERMISSIONS</span><b>${esc(perms)}</b></div>
      <div class="aura-v23-skill-foot"><span>LAST</span><b>${esc(last?.command||'â€”')}</b></div>
    </article>`;
  }).join('');
}
function renderActivity(){
  const list=q('[data-aura-v23-skills-activity]');
  if(!list)return;
  if(!state.events.length){
    list.innerHTML='<div class="aura-v23-skills-empty"><b>En attente dâ€™activitÃ©</b><span>CONSULT et EXECUTE apparaÃ®tront ici en temps rÃ©el.</span></div>';
    return;
  }
  list.innerHTML=state.events.slice(0,24).map(ev=>{
    const d=ev.data||{};
    const t=new Date(ev.ts).toLocaleTimeString('fr-FR',{hour:'2-digit',minute:'2-digit',second:'2-digit'});
    return `<div class="aura-v23-skill-event ${statusClass(d)}">
      <span class="aura-v23-event-dot"></span><span class="aura-v23-event-time">${esc(t)}</span>
      <strong>${esc(d.skill_id||'skill')}</strong><code>${esc(d.command||'â€”')}</code>
      <em>${esc(modeLabel(d))}</em>
    </div>`;
  }).join('');
}
function renderSummary(){
  const set=(k,v)=>{const el=q(`[data-aura-v23-summary="${k}"]`);if(el)el.textContent=String(v)};
  set('total',SKILLS.length);
  set('active',SKILLS.filter(s=>s.enabled&&(s.commands||[]).length).length);
  set('foundation',SKILLS.filter(s=>s.enabled&&!(s.commands||[]).length).length);
  set('execute',state.events.filter(e=>String(e.data?.mode||'').toLowerCase()==='execute').length);
  set('consult',state.events.filter(e=>String(e.data?.mode||'').toLowerCase()==='consult').length);
}
function render(){renderCards();renderActivity();renderSummary()}

function consume(msg){
  if(!msg||String(msg.type||'')!=='skill_activity')return;
  const d=msg.data&&typeof msg.data==='object'?msg.data:{};
  const id=String(d.skill_id||'');
  if(!id)return;
  const b=state.bySkill[id]||(state.bySkill[id]={last:null,count:0});
  b.last={...d};b.count=(b.count||0)+1;
  state.events.unshift({ts:Date.now(),data:{...d}});
  if(state.events.length>80)state.events.length=80;
  render();

  const launch=q('[data-aura-v23-skills-launch]');
  if(launch){
    launch.dataset.live=String(d.mode||'').toLowerCase();
    clearTimeout(launch.__auraLiveTimer);
    launch.__auraLiveTimer=setTimeout(()=>{launch.dataset.live=''},1600);
  }
}
function openPanel(){
  const p=q('[data-aura-v23-skills-panel]');if(!p)return;
  state.open=true;p.hidden=false;requestAnimationFrame(()=>p.classList.add('open'));
  q('[data-aura-v23-skills-launch]')?.classList.add('active');
}
function closePanel(){
  const p=q('[data-aura-v23-skills-panel]');if(!p)return;
  state.open=false;p.classList.remove('open');
  q('[data-aura-v23-skills-launch]')?.classList.remove('active');
  setTimeout(()=>{if(!state.open)p.hidden=true},180);
}
function install(){
  if(q('[data-aura-v23-skills-panel]'))return;

  const rail=q('.rail');
  if(rail){
    const btn=document.createElement('button');
    btn.type='button';
    btn.className='rail-btn aura-v23-skills-launch';
    btn.dataset.auraV23SkillsLaunch='1';
    btn.title='Skills Center';
    btn.setAttribute('aria-label','Ouvrir Skills Center');
    btn.innerHTML='<span>SK</span><small>SKILLS</small>';
    const spacer=q('.rail-spacer',rail);
    if(spacer)rail.insertBefore(btn,spacer);else rail.appendChild(btn);
    btn.addEventListener('click',()=>state.open?closePanel():openPanel());
  }

  const panel=document.createElement('section');
  panel.className='aura-v23-skills-panel glass';
  panel.dataset.auraV23SkillsPanel='1';
  panel.hidden=true;
  panel.innerHTML=`
    <div class="aura-v23-skills-shell">
      <header class="aura-v23-skills-head">
        <div>
          <span class="aura-v23-skills-eyebrow">AURA Â· CAPABILITY RUNTIME</span>
          <h2>Skills Center <b>v2.3</b></h2>
          <p>Registre actif, propriÃ©taires dâ€™exÃ©cution et activitÃ© live.</p>
        </div>
        <div class="aura-v23-skills-head-actions">
          <span class="aura-v23-skills-live"><i></i> LIVE</span>
          <button type="button" data-aura-v23-skills-close aria-label="Fermer">Ã—</button>
        </div>
      </header>

      <div class="aura-v23-skills-summary">
        <div><span>TOTAL</span><strong data-aura-v23-summary="total">0</strong></div>
        <div><span>ACTIVE</span><strong data-aura-v23-summary="active">0</strong></div>
        <div><span>FOUNDATION</span><strong data-aura-v23-summary="foundation">0</strong></div>
        <div><span>EXECUTE</span><strong data-aura-v23-summary="execute">0</strong></div>
        <div><span>CONSULT</span><strong data-aura-v23-summary="consult">0</strong></div>
      </div>

      <div class="aura-v23-skills-body">
        <main class="aura-v23-skills-main">
          <div class="aura-v23-section-title"><span>CAPABILITIES</span><b>${SKILLS.length} modules</b></div>
          <div class="aura-v23-skills-grid" data-aura-v23-skills-grid></div>
        </main>
        <aside class="aura-v23-skills-side">
          <div class="aura-v23-section-title"><span>ACTIVITÃ‰ LIVE</span><b>SkillRegistry</b></div>
          <div class="aura-v23-skills-activity" data-aura-v23-skills-activity></div>
          <div class="aura-v23-skills-policy">
            <span>MIC POLICY</span><strong>BUTTON ONLY</strong>
            <p><code>mic_start</code>, <code>mic_stop</code> et <code>send_message</code> restent hors Skills.</p>
          </div>
        </aside>
      </div>
    </div>`;
  document.body.appendChild(panel);
  q('[data-aura-v23-skills-close]',panel)?.addEventListener('click',closePanel);
  panel.addEventListener('click',e=>{if(e.target===panel)closePanel()});
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&state.open)closePanel()});
  render();
}

window.addEventListener('aura:hub-event',e=>consume(e.detail));
window.addEventListener('aura:skills-open',openPanel);
window.addEventListener('aura:skills-close',closePanel);

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});
else install();
})();
