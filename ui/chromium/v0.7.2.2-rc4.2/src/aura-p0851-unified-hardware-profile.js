/* AURA P0.8.5.1.1 — UNIFIED HARDWARE PROFILE TELEMETRY HOTFIX
   Roadmap n081: CPU/GPU/RAM/VRAM/audio inventory + deterministic recommended profile.
   Contract: local authenticated loopback only; UI consumes data and NEVER applies settings in P0.8.5.1.
*/
(()=>{
  'use strict';
  if(window.__AURA_P0851_HARDWARE_PROFILE__)return;
  window.__AURA_P0851_HARDWARE_PROFILE__=true;
  const VERSION='P0.8.5.1.1', SCHEMA='aura.hardware-profile.v1';
  const token=new URLSearchParams(location.search).get('token')||'';
  const STATE={panel:null,button:null,data:null,system:null,loading:false,lastAt:0,overlayRegistered:false};
  const q=(s,r=document)=>r.querySelector(s);
  const safe=(v,n=180)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const esc=v=>safe(v,500).replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const finite=v=>Number.isFinite(Number(v));
  const num=(obj,paths)=>{for(const path of paths){let cur=obj;for(const p of path.split('.'))cur=cur&&typeof cur==='object'?cur[p]:undefined;if(finite(cur))return Number(cur)}return null};
  const text=(obj,paths)=>{for(const path of paths){let cur=obj;for(const p of path.split('.'))cur=cur&&typeof cur==='object'?cur[p]:undefined;if(cur!==undefined&&cur!==null&&String(cur).trim())return safe(cur)}return''};
  const gib=v=>finite(v)?`${Number(v).toFixed(Number(v)>=10?0:1)} Gio`:'—';
  const mib=v=>finite(v)?`${Math.round(Number(v))} Mio`:'—';
  function emit(name,detail){window.dispatchEvent(new CustomEvent(name,{detail:Object.assign({version:VERSION},detail||{})}))}

  async function localJson(path){
    if(!token)throw new Error('token local absent');
    const sep=path.includes('?')?'&':'?';
    const r=await fetch(`${path}${sep}token=${encodeURIComponent(token)}`,{cache:'no-store'});
    let d={};try{d=await r.json()}catch(_e){}
    if(!r.ok)throw new Error(d.error||`HTTP ${r.status}`);return d;
  }
  function currentGpuFallback(data){
    const inv=data?.inventory||{};
    const display=safe(inv.display_gpu?.name||'');const compute=safe(inv.compute_gpu?.name||'');
    const domDisplay=safe(q('#displayGpu')?.textContent||'');const domCompute=safe(q('#computeGpu')?.textContent||'');
    if((!display||/attente|detect|unknown/i.test(display))&&domDisplay)inv.display_gpu={...(inv.display_gpu||{}),name:domDisplay,source:'bridge-dom'};
    if((!compute||/non détect|unknown/i.test(compute))&&domCompute)inv.compute_gpu={...(inv.compute_gpu||{}),name:domCompute,source:'bridge-dom'};
    return data;
  }
  function liveMetrics(system,profile){
    const sys={
      cpu:num(system,['cpu_percent','cpu.percent','system.cpu_percent','system.cpu.percent','desktop.cpu_percent']),
      ram:num(system,['ram_percent','memory_percent','ram.percent','memory.percent','system.ram_percent','system.memory_percent']),
      vram:num(system,['vram_percent','gpu.vram_percent','system.vram_percent','gpu.memory_percent'])
    };
    const snap=profile?.current_load||{};
    const fallback={cpu:num(snap,['cpu_percent']),ram:num(snap,['ram_percent']),vram:num(snap,['vram_percent'])};
    // Some legacy /api/system builds expose zero placeholders. RAM=0 on a running desktop is impossible,
    // so an all-zero triplet is treated as unavailable rather than as real telemetry.
    const zeroBundle=sys.cpu===0&&sys.ram===0&&sys.vram===0;
    return {
      cpu:zeroBundle?(fallback.cpu??sys.cpu):(sys.cpu??fallback.cpu),
      ram:zeroBundle?(fallback.ram??sys.ram):(sys.ram??fallback.ram),
      vram:zeroBundle?(fallback.vram??sys.vram):(sys.vram??fallback.vram),
      source:zeroBundle?'profile-snapshot-fallback':'system-service'
    };
  }
  async function refresh(force=false){
    if(STATE.loading)return STATE.data;STATE.loading=true;renderLoading();
    try{
      const [profile,system]=await Promise.all([
        localJson(`/api/hardware-profile${force?'?refresh=1':''}`),
        localJson('/api/system').catch(()=>null)
      ]);
      STATE.data=currentGpuFallback(profile);STATE.system=system;STATE.lastAt=Date.now();render();
      emit('aura:hardware-profile-ready',{profile:STATE.data?.recommended_profile?.id||'unknown',schema:STATE.data?.schema||'',readOnly:true});
      return STATE.data;
    }catch(e){renderError(e);emit('aura:hardware-profile-error',{error:safe(e?.message||e)});return null}
    finally{STATE.loading=false}
  }
  function ensureButton(){
    const title=q('.telemetry .panel-title');if(!title)return null;
    let b=q('[data-p0851-open]',title);if(!b){b=document.createElement('button');b.type='button';b.className='aura-p0851-open';b.dataset.p0851Open='1';b.textContent='PROFIL';b.title='Profil matériel AURA';title.appendChild(b)}
    STATE.button=b;return b;
  }
  function ensurePanel(){
    if(STATE.panel?.isConnected)return STATE.panel;
    const p=document.createElement('section');p.className='aura-p0851-panel glass';p.hidden=true;p.setAttribute('role','dialog');p.setAttribute('aria-label','Profil matériel AURA');
    p.innerHTML=`<header class="aura-p0851-head"><div><small>AURA · PORTABILITY CORE</small><b>HARDWARE PROFILE</b><span>Inventaire local · recommandation uniquement</span></div><button type="button" data-p0851-close aria-label="Fermer">×</button></header><div class="aura-p0851-body" data-p0851-body></div><footer><span>READ ONLY · AUCUN RÉGLAGE APPLIQUÉ</span><div><button type="button" data-p0851-refresh>RÉÉVALUER</button><button type="button" data-p0851-close>FERMER</button></div></footer>`;
    document.body.appendChild(p);STATE.panel=p;layout();return p;
  }
  function layout(){
    const p=STATE.panel;if(!p||p.hidden)return;const sys=q('.telemetry'),composer=q('#composer'),rail=q('.rail'),top=q('.topbar');if(!sys)return;
    const sr=sys.getBoundingClientRect(),cr=composer?.getBoundingClientRect(),rr=rail?.getBoundingClientRect(),tr=top?.getBoundingClientRect();
    const topY=Math.max(sr.top,tr?.bottom?tr.bottom+12:sr.top),bottomY=cr?.top?cr.top-12:innerHeight-18,leftMin=(rr?.right||12)+12,rightEdge=sr.left-12;
    const avail=Math.max(360,rightEdge-leftMin),w=Math.min(580,avail);
    p.style.top=`${Math.round(topY)}px`;p.style.left=`${Math.round(Math.max(leftMin,rightEdge-w))}px`;p.style.width=`${Math.round(w)}px`;p.style.height=`${Math.max(380,Math.round(bottomY-topY))}px`;
  }
  function open(){const p=ensurePanel();p.hidden=false;requestAnimationFrame(()=>{p.classList.add('open');layout()});registerOverlay();refresh(false);STATE.button?.setAttribute('aria-expanded','true');emit('aura:hardware-profile-opened',{readOnly:true});return true}
  function close(){const p=STATE.panel;if(!p)return false;p.classList.remove('open');p.hidden=true;STATE.button?.setAttribute('aria-expanded','false');emit('aura:hardware-profile-closed',{});return true}
  function isOpen(){return !!STATE.panel&&!STATE.panel.hidden}
  function registerOverlay(){
    if(STATE.overlayRegistered)return true;const ov=window.AuraWorkspace?.overlay;if(!ov?.register)return false;
    if(ov.list?.().some?.(x=>x.id==='hardware-profile')){STATE.overlayRegistered=true;return true}
    STATE.overlayRegistered=!!ov.register({id:'hardware-profile',label:'Hardware Profile',preserveOnWorkspaceChange:true,available:()=>true,isOpen,open,close});return STATE.overlayRegistered;
  }
  const line=(label,value,sub='')=>`<div class="aura-p0851-line"><span>${esc(label)}</span><div><b>${esc(value||'—')}</b>${sub?`<small>${esc(sub)}</small>`:''}</div></div>`;
  const load=(label,v)=>`<div class="aura-p0851-load"><span>${label}</span><b>${finite(v)?`${Math.round(v)} %`:'—'}</b><i><em style="width:${finite(v)?Math.max(0,Math.min(100,Number(v))):0}%"></em></i></div>`;
  function render(){
    const body=q('[data-p0851-body]',ensurePanel());if(!body)return;const d=STATE.data||{},inv=d.inventory||{},cpu=inv.cpu||{},mem=inv.memory||{},dg=inv.display_gpu||{},cg=inv.compute_gpu||{},audio=inv.audio||{},p=d.recommended_profile||{},metrics=liveMetrics(STATE.system||{},d),topology=d.topology||{};
    const vram=cg.dedicated_vram_mib;const vramText=finite(vram)?`${(Number(vram)/1024).toFixed(1)} Gio VRAM dédiée`:'VRAM dédiée non exposée';
    const audioValue=audio.default_output||audio.default_input||`Runtime ${safe(audio.runtime_state||'local').toUpperCase()}`;
    const audioSub=[audio.default_input?`Entrée: ${audio.default_input}`:'',audio.output_devices?`${audio.output_devices} sortie(s)`:'',audio.input_devices?`${audio.input_devices} entrée(s)`:''].filter(Boolean).join(' · ');
    body.innerHTML=`<section class="aura-p0851-profile-card" data-profile="${esc(p.id||'unknown')}"><div><small>PROFIL RECOMMANDÉ</small><strong>${esc(p.label||'ANALYSE')}</strong><span>${esc((p.reasons||[]).join(' · ')||'Capacités en cours d’évaluation')}</span></div><i>${p.id==='performance'?'P3':p.id==='balanced'?'P2':'P1'}</i></section><div class="aura-p0851-grid"><section><h3>INVENTAIRE</h3>${line('CPU',cpu.model||'CPU local',`${cpu.logical_cores||'—'} threads${cpu.physical_cores?` · ${cpu.physical_cores} cœurs`:''}`)}${line('RAM',gib(mem.total_gib),finite(mem.available_gib)?`${gib(mem.available_gib)} disponibles`:safe(mem.source))}${line('DISPLAY GPU',dg.name||q('#displayGpu')?.textContent||'—',safe(dg.source))}${line('COMPUTE GPU',cg.name||q('#computeGpu')?.textContent||'—',`${vramText}${cg.driver?` · driver ${cg.driver}`:''}`)}${line('AUDIO',audioValue,audioSub||safe(audio.source))}${line('TOPOLOGIE',safe(topology.kind||'unknown').toUpperCase(),topology.display_compute_separated?'Affichage et calcul séparés':'Adaptateur partagé ou unique')}</section><section><h3>CHARGE ACTUELLE</h3><div class="aura-p0851-load-grid">${load('CPU',metrics.cpu)}${load('RAM',metrics.ram)}${load('VRAM',metrics.vram)}</div><h3>RECOMMANDATIONS</h3><div class="aura-p0851-recos">${line('VISUEL',p.recommendations?.visual||'—')}${line('VOIX',p.recommendations?.voice||'—')}${line('IA LOCALE',p.recommendations?.local_ai||'—')}</div><div class="aura-p0851-safety"><b>ÉTAPE P0.8.5.1</b><p>Le profil est calculé automatiquement mais <strong>aucun paramètre n’est changé</strong>. L’application adaptative sera traitée séparément en P0.8.5.3.</p></div></section></div><div class="aura-p0851-source">Schema ${esc(d.schema||SCHEMA)} · ${d.generated_at?new Date(d.generated_at).toLocaleString('fr-FR'):'local'} · télémétrie ${esc(metrics.source||'locale')} · Core/bridge owns hardware</div>`;
  }
  function renderLoading(){const body=q('[data-p0851-body]',ensurePanel());if(body)body.innerHTML='<div class="aura-p0851-loading"><i></i><b>ANALYSE MATÉRIELLE LOCALE</b><span>CPU · RAM · GPU · VRAM · audio</span></div>'}
  function renderError(e){const body=q('[data-p0851-body]',ensurePanel());if(body)body.innerHTML=`<div class="aura-p0851-error"><b>PROFIL INDISPONIBLE</b><span>${esc(e?.message||e||'Erreur locale')}</span><small>Aucun réglage n’a été modifié.</small></div>`}
  function onClick(e){if(e.target.closest('[data-p0851-open]')){isOpen()?close():open();return}if(e.target.closest('[data-p0851-close]')){close();return}if(e.target.closest('[data-p0851-refresh]')){refresh(true);return}}
  function boot(){ensureButton();ensurePanel();registerOverlay();document.addEventListener('click',onClick,true);window.addEventListener('resize',layout);window.addEventListener('aura:workspace-changed',()=>setTimeout(layout,30));setTimeout(ensureButton,500);setTimeout(registerOverlay,500);document.documentElement.dataset.auraHardwareProfile='p08511';emit('aura:hardware-profile-module-ready',{schema:SCHEMA,readOnly:true,appliesChanges:false})}
  window.AuraHardwareProfile=Object.freeze({version:VERSION,schema:SCHEMA,open,close,isOpen,refresh,get:()=>STATE.data?JSON.parse(JSON.stringify(STATE.data)):null,contract:()=>({readOnly:true,localLoopbackOnly:true,appliesChanges:false,adaptiveApplication:'P0.8.5.3'})});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
