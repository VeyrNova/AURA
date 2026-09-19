/* AURA P0.8.5.3.3 — ADAPTIVE VISUAL RUNTIME BUDGET
   Technical frame budgets only. No layout/color/geometry/branding changes.
   P2 exactly preserves the validated active UI baseline.
*/
(()=>{
  'use strict';
  if(window.__AURA_P08533_VISUAL_BUDGET__)return;
  window.__AURA_P08533_VISUAL_BUDGET__=true;

  const VERSION='P0.8.5.3.3';
  const token=new URLSearchParams(location.search).get('token')||'';
  const FALLBACKS={
    P1:{core:30,legacyOrb:24,officialOrb:30,nativeOpenGL:36},
    P2:{core:48,legacyOrb:36,officialOrb:40,nativeOpenGL:60},
    P3:{core:60,legacyOrb:48,officialOrb:60,nativeOpenGL:72}
  };
  const STATE={code:'P2',label:'BALANCED',source:'safe-p2-default',budgets:{...FALLBACKS.P2},runtimeDefaults:{},loaded:false,lastAt:0};

  const finite=(v)=>Number.isFinite(Number(v))&&Number(v)>0;
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,Number(v)));
  function codeOf(v){
    const s=String(v||'').toUpperCase();
    if(s==='P1'||s==='P2'||s==='P3')return s;
    const low=String(v||'').toLowerCase();
    if(low==='efficient')return'P1';
    if(low==='performance')return'P3';
    return'P2';
  }
  function setRoot(){
    const root=document.documentElement;
    root.dataset.auraVisualProfile=STATE.code.toLowerCase();
    root.dataset.auraVisualBudget='adaptive';
    root.style.setProperty('--aura-visual-core-fps',String(STATE.budgets.core));
    root.style.setProperty('--aura-visual-official-orb-fps',String(STATE.budgets.officialOrb));
    root.style.setProperty('--aura-visual-native-opengl-fps',String(STATE.budgets.nativeOpenGL));
  }
  function emit(){
    window.dispatchEvent(new CustomEvent('aura:visual-budget-ready',{detail:snapshot()}));
  }
  function snapshot(){
    return{
      version:VERSION,code:STATE.code,label:STATE.label,source:STATE.source,
      budgets:{...STATE.budgets},runtimeDefaults:{...STATE.runtimeDefaults},loaded:STATE.loaded,lastAt:STATE.lastAt,
      layoutSwitch:false,colorSwitch:false,geometrySwitch:false
    };
  }
  function fps(channel,fallback){
    if(!window.AuraVisualBudget?.enabled)return Number(fallback)||60;
    const key=channel==='core'?'core':channel==='legacy-orb'?'legacyOrb':channel==='official-orb'?'officialOrb':channel==='native-opengl'?'nativeOpenGL':'';
    if(!key)return Number(fallback)||60;
    // P2 is an exact compatibility baseline: preserve the caller's validated value.
    if(STATE.code==='P2')return Number(fallback)||STATE.budgets[key];
    const v=STATE.budgets[key];
    return finite(v)?clamp(v,12,90):(Number(fallback)||60);
  }
  function apply(profile){
    const adaptive=profile?.adaptive_runtime||{};
    const defs=adaptive?.runtime_defaults||{};
    const code=codeOf(adaptive?.code||adaptive?.id||profile?.recommended_profile?.id);
    const base={...(FALLBACKS[code]||FALLBACKS.P2)};
    if(finite(defs.browser_core_fps))base.core=Number(defs.browser_core_fps);
    if(finite(defs.browser_legacy_orb_fps))base.legacyOrb=Number(defs.browser_legacy_orb_fps);
    if(finite(defs.browser_official_orb_fps))base.officialOrb=Number(defs.browser_official_orb_fps);
    if(finite(defs.native_opengl_fps))base.nativeOpenGL=Number(defs.native_opengl_fps);
    STATE.code=code;
    STATE.label=String(adaptive?.label||profile?.recommended_profile?.label||({P1:'EFFICIENT',P2:'BALANCED',P3:'PERFORMANCE'}[code]));
    STATE.source=String(adaptive?.source||'hardware-profile');
    STATE.budgets=base;
    STATE.runtimeDefaults={...defs};
    STATE.loaded=true;
    STATE.lastAt=Date.now();
    setRoot();emit();
  }
  async function refresh(){
    if(!token)return snapshot();
    try{
      const r=await fetch(`/api/hardware-profile?token=${encodeURIComponent(token)}`,{cache:'no-store'});
      if(!r.ok)throw new Error(`HTTP ${r.status}`);
      apply(await r.json());
    }catch(_e){
      // Safe failure mode: exact P2 baseline remains active.
      STATE.source='safe-p2-fallback';
      STATE.lastAt=Date.now();
      setRoot();emit();
    }
    return snapshot();
  }

  window.AuraVisualBudget={
    version:VERSION,
    enabled:true,
    fps,
    refresh,
    snapshot
  };
  setRoot();
  // Profile retrieval is local-loopback only and does not block first paint.
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',refresh,{once:true});
  else refresh();
  window.addEventListener('aura:hardware-profile-ready',()=>refresh());
})();
