/* AURA P0.8.5.3.4 — ADAPTIVE WORKLOAD BUDGET
   Polling/service cadence only. P2 exactly preserves existing timings.
   No UI layout, CSS, color, branding, model or voice-policy changes.
*/
(()=>{
  'use strict';
  if(window.__AURA_P08534_WORKLOAD_BUDGET__)return;
  window.__AURA_P08534_WORKLOAD_BUDGET__=true;

  const VERSION='P0.8.5.3.4';
  const FALLBACKS={
    P1:{heartbeat:1200,runtimeStatus:1000,systemState:6500,vitals:3500,routerObservatory:1000},
    P2:{heartbeat:900,runtimeStatus:700,systemState:4000,vitals:2200,routerObservatory:650},
    P3:{heartbeat:700,runtimeStatus:500,systemState:2500,vitals:1500,routerObservatory:450}
  };
  const DEFAULT_KEYS={
    heartbeat:'browser_heartbeat_ms',
    'runtime-status':'browser_runtime_status_ms',
    'system-state':'system_state_poll_ms',
    vitals:'vitals_poll_ms',
    'router-observatory':'router_observatory_poll_ms'
  };
  const STATE={code:'P2',label:'BALANCED',source:'safe-p2-default',defaults:{},budgets:{...FALLBACKS.P2},loaded:false,lastAt:0};

  const codeOf=(v)=>{
    const s=String(v||'').toUpperCase();
    if(s==='P1'||s==='P2'||s==='P3')return s;
    const low=String(v||'').toLowerCase();
    if(low==='efficient')return'P1';
    if(low==='performance')return'P3';
    return'P2';
  };
  const finite=(v)=>Number.isFinite(Number(v))&&Number(v)>0;
  const clamp=(v)=>Math.max(100,Math.min(60000,Math.round(Number(v))));
  function snapshot(){
    return{
      version:VERSION,code:STATE.code,label:STATE.label,source:STATE.source,
      budgets:{...STATE.budgets},runtimeDefaults:{...STATE.defaults},
      loaded:STATE.loaded,lastAt:STATE.lastAt,
      featureSwitch:false,layoutSwitch:false,voicePolicySwitch:false,modelSwitch:false
    };
  }
  function emit(){
    window.dispatchEvent(new CustomEvent('aura:workload-budget-ready',{detail:snapshot()}));
  }
  function apply(detail){
    const code=codeOf(detail?.code);
    const defs=detail?.runtimeDefaults||{};
    const base={...(FALLBACKS[code]||FALLBACKS.P2)};
    for(const [channel,key] of Object.entries(DEFAULT_KEYS)){
      const field=channel==='runtime-status'?'runtimeStatus':channel==='system-state'?'systemState':channel==='router-observatory'?'routerObservatory':channel;
      if(finite(defs[key]))base[field]=clamp(defs[key]);
    }
    STATE.code=code;
    STATE.label=String(detail?.label||({P1:'EFFICIENT',P2:'BALANCED',P3:'PERFORMANCE'}[code]));
    STATE.source=String(detail?.source||'visual-profile-bridge');
    STATE.defaults={...defs};
    STATE.budgets=base;
    STATE.loaded=!!detail?.loaded;
    STATE.lastAt=Date.now();
    emit();
  }
  function interval(channel,fallback){
    const fb=Number(fallback)||1000;
    if(STATE.code==='P2')return fb; // exact compatibility baseline
    const key=channel==='runtime-status'?'runtimeStatus':channel==='system-state'?'systemState':channel==='router-observatory'?'routerObservatory':channel;
    const value=STATE.budgets[key];
    return finite(value)?clamp(value):fb;
  }
  function repeat(fn,channel,fallback){
    let stopped=false,timer=0;
    const schedule=()=>{if(!stopped)timer=setTimeout(run,interval(channel,fallback));};
    const run=()=>{
      if(stopped)return;
      try{
        Promise.resolve(fn()).catch(()=>{}).finally(schedule);
      }catch(_e){schedule();}
    };
    schedule();
    return Object.freeze({
      stop(){stopped=true;if(timer)clearTimeout(timer);timer=0;},
      channel,
      fallback:Number(fallback)||1000
    });
  }

  window.AuraWorkloadBudget=Object.freeze({version:VERSION,interval,repeat,snapshot});
  const initial=window.AuraVisualBudget?.snapshot?.();
  if(initial)apply(initial);else emit();
  window.addEventListener('aura:visual-budget-ready',e=>apply(e.detail||{}));
})();
