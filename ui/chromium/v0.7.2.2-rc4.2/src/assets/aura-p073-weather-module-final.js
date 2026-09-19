/* AURA P0.7.3 — WEATHER MODULE FINAL
   Unified Workspace adapter for the existing AURA Weather/Open-Meteo module.
   This file does not fetch weather data and does not replace the native Weather engine.
*/
(()=>{
  'use strict';
  if(window.__AURA_P073_WEATHER_FINAL__)return;
  window.__AURA_P073_WEATHER_FINAL__=true;

  const VERSION='P0.7.3';
  const ROOT_SELECTOR='.aura-weather-workspace';
  const STATE={root:null,latest:null,observer:null,scanTimer:0,enhanceTimer:0,registered:false,lastFingerprint:'',lastContext:null};
  const safe=(v,n=320)=>String(v??'').replace(/\s+/g,' ').trim().slice(0,n);
  const qa=(s,r=document)=>[...r.querySelectorAll(s)];
  const q=(s,r=document)=>r.querySelector(s);
  const visible=el=>!!(el&&el.isConnected&&getComputedStyle(el).display!=='none'&&getComputedStyle(el).visibility!=='hidden');
  const num=v=>{const n=Number(String(v??'').replace(',','.'));return Number.isFinite(n)?n:null};
  const fmt=v=>String(v??'').replace('.',',');
  const esc=v=>String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));

  function activeWorkspace(){return safe(window.AuraWorkspace?.current?.()||document.body.dataset.auraWorkspace||'',32).toLowerCase()}
  function findRoot(){return q(`${ROOT_SELECTOR}.open`)||q(`${ROOT_SELECTOR}[aria-hidden="false"]`)||q(ROOT_SELECTOR)}
  function text(root){return safe(root?.innerText||root?.textContent||'',12000)}
  function nativeText(root){if(!root)return'';try{const clone=root.cloneNode(true);clone.querySelectorAll?.('[data-p073-weather-bar]').forEach(el=>el.remove());return text(clone)}catch(_){return text(root)}}
  function firstMatch(source,regex){const m=String(source||'').match(regex);return m?safe(m[1]??m[2]??m[0],180):''}
  function structuredValue(...keys){
    const d=STATE.latest||{};
    for(const k of keys){if(d[k]!==undefined&&d[k]!==null&&safe(d[k],300)!=='')return d[k]}
    return null;
  }
  function inputLocation(root){
    const sels=['[data-weather-location]','[data-location]','.weather-location','.location-label','[class*="weather"][class*="location"]','input[type="search"]','input[placeholder*="ville" i]','input[placeholder*="localisation" i]','input[placeholder*="lieu" i]'];
    for(const s of sels){for(const el of qa(s,root)){const v=safe(el.value||el.dataset?.weatherLocation||el.dataset?.location||el.textContent,220);if(v&&!/recherch|localisation|ville|lieu/i.test(v))return v}}
    const raw=nativeText(root);
    return firstMatch(raw,/(?:LOCATION|LOCALISATION|LIEU)\s*[·:\-]?\s*([^\n|]{2,100})/i);
  }
  function activeControl(root,kind){
    const wanted=kind==='layer'?/(?:VENT|PLUIE|TEMP[ÉE]RATURE|NUAGES?|VAGUES?|PRESSION)/i:/(?:MAINTENANT|\+\s*3\s*H|\+\s*6\s*H|\+\s*12\s*H|\+\s*24\s*H)/i;
    const controls=qa('button,[role="button"],[role="tab"],input[type="radio"]+label',root);
    const selected=controls.filter(el=>wanted.test(safe(el.textContent||el.value,80))&&(el.classList.contains('active')||el.classList.contains('selected')||el.getAttribute('aria-selected')==='true'||el.getAttribute('aria-pressed')==='true'||el.previousElementSibling?.checked));
    if(selected.length)return safe(selected[0].textContent||selected[0].value,80).toUpperCase();
    const dataSel=kind==='layer'?root.dataset?.weatherLayer:root.dataset?.weatherTimeline;
    return safe(dataSel||'',80).toUpperCase();
  }
  function conditionFrom(raw){
    const labels=['ciel dégagé','principalement dégagé','partiellement nuageux','couvert','brouillard givrant','brouillard','bruine légère','bruine modérée','bruine forte','pluie légère','pluie modérée','forte pluie','neige légère','neige modérée','fortes chutes de neige','averses légères','averses modérées','fortes averses','orage avec grêle légère','orage avec forte grêle','orage','conditions variables'];
    const lower=raw.toLowerCase();return labels.find(x=>lower.includes(x))||'';
  }
  function extract(root){
    if(!root)return null;
    const raw=nativeText(root),d=STATE.latest||{};
    const location=safe(structuredValue('place_label','location')||inputLocation(root),260);
    let temperature=structuredValue('temperature');if(temperature===null)temperature=firstMatch(raw,/(-?\d{1,2}(?:[.,]\d+)?)\s*°\s*C/i);
    let apparent=structuredValue('apparent','apparent_temperature');if(apparent===null)apparent=firstMatch(raw,/(?:RESSENTI|APPARENTE?)\s*[·:\-]?\s*(-?\d{1,2}(?:[.,]\d+)?)\s*°?\s*C?/i);
    let humidity=structuredValue('humidity');if(humidity===null)humidity=firstMatch(raw,/HUMIDIT[ÉE]\s*[·:\-]?\s*(\d{1,3})\s*%/i);
    let wind=structuredValue('wind_speed');if(wind===null)wind=firstMatch(raw,/VENT(?:\s+MOYEN)?\s*[·:\-]?\s*(\d{1,3}(?:[.,]\d+)?)\s*(?:KM\s*\/\s*H|KMH)/i);
    let rain=structuredValue('rain_probability_now');if(rain===null)rain=firstMatch(raw,/(?:RISQUE\s+(?:DE\s+)?PLUIE(?:\s+MAINTENANT)?|PLUIE)\s*[·:\-]?\s*(\d{1,3})\s*%/i);
    let precip=structuredValue('precipitation');if(precip===null)precip=firstMatch(raw,/PR[ÉE]CIPITATIONS?(?:\s+ACTUELLES?)?\s*[·:\-]?\s*(\d+(?:[.,]\d+)?)\s*MM/i);
    let pressure=structuredValue('pressure');if(pressure===null)pressure=firstMatch(raw,/PRESSION\s*[·:\-]?\s*(\d{3,4}(?:[.,]\d+)?)\s*HPA/i);
    let visibilityKm=structuredValue('visibility_km');if(visibilityKm===null)visibilityKm=firstMatch(raw,/VISIBILIT[ÉE]\s*[·:\-]?\s*(\d+(?:[.,]\d+)?)\s*KM/i);
    const condition=safe(structuredValue('condition')||conditionFrom(raw),120);
    const layer=activeControl(root,'layer');const timeline=activeControl(root,'timeline');
    const checked=safe(structuredValue('checked_at')||firstMatch(raw,/(?:V[ÉE]RIFI[ÉE]E?|ACTUALIS[ÉE]E?|MISE?\s+À\s+JOUR)\s*(?:À|LE)?\s*([0-2]?\d:[0-5]\d)/i),80);
    const source=/OPEN[-\s]?METEO/i.test(raw)||safe(d.source,80).toLowerCase().includes('open-meteo')?'Open-Meteo':'Open-Meteo';
    return {location,temperature,apparent,humidity,wind,rain,precip,pressure,visibilityKm,condition,layer,timeline,checked,source};
  }
  function fact(key,label,value,source='weather'){const v=safe(value,300);return v?{key,label,value:v,source}:null}
  function contextFrom(data){
    data=data||{};const facts=[];
    if(data.temperature!==null&&data.temperature!=='')facts.push(fact('temperature','Température',`${fmt(data.temperature)} °C`));
    if(data.condition)facts.push(fact('condition','Conditions',data.condition));
    if(data.apparent!==null&&data.apparent!=='')facts.push(fact('apparent','Ressenti',`${fmt(data.apparent)} °C`));
    if(data.humidity!==null&&data.humidity!=='')facts.push(fact('humidity','Humidité',`${fmt(data.humidity)} %`));
    if(data.wind!==null&&data.wind!=='')facts.push(fact('wind','Vent',`${fmt(data.wind)} km/h`));
    if(data.rain!==null&&data.rain!=='')facts.push(fact('rain_probability','Risque de pluie',`${fmt(data.rain)} %`));
    if(data.precip!==null&&data.precip!=='')facts.push(fact('precipitation','Précipitations',`${fmt(data.precip)} mm`));
    if(data.pressure!==null&&data.pressure!=='')facts.push(fact('pressure','Pression',`${fmt(data.pressure)} hPa`));
    if(data.visibilityKm!==null&&data.visibilityKm!=='')facts.push(fact('visibility','Visibilité',`${fmt(data.visibilityKm)} km`));
    if(data.layer)facts.push(fact('layer','Couche active',data.layer,'weather-ui'));
    if(data.timeline)facts.push(fact('timeline','Échéance',data.timeline,'weather-ui'));
    if(data.checked)facts.push(fact('checked_at','Actualisation',data.checked,'weather'));
    facts.push(fact('source','Source',data.source||'Open-Meteo','weather'));
    const summary=[];if(data.location)summary.push(data.location);if(data.temperature!==null&&data.temperature!=='')summary.push(`${fmt(data.temperature)} °C`);if(data.condition)summary.push(data.condition);if(data.wind!==null&&data.wind!=='')summary.push(`vent ${fmt(data.wind)} km/h`);
    return {schema:'aura.workspace-context.v2',workspace:'weather',submode:'forecast',target:data.location||'Prévisions et carte météo',summary:summary.length?`Météo active : ${summary.join(' · ')}.`:'Workspace Météo actif ; aucune mesure visible supplémentaire n’a encore été publiée.',facts:facts.filter(Boolean).slice(0,12),refs:[],cleared:false};
  }
  function updateStatus(root,data){
    const bar=q('[data-p073-weather-bar]',root);if(!bar)return;
    const loc=q('[data-p073-location]',bar),state=q('[data-p073-state]',bar),layer=q('[data-p073-layer]',bar),time=q('[data-p073-time]',bar);
    if(loc)loc.textContent=data?.location||'LOCALISATION MÉTÉO';
    const has=!!(data&&(data.temperature!==null&&data.temperature!==''||data.condition||data.humidity!==null&&data.humidity!==''));
    if(state){state.textContent=has?'DONNÉES ACTIVES':'EN ATTENTE';state.dataset.state=has?'ready':'waiting'}
    if(layer){layer.textContent=data?.layer?`COUCHE · ${data.layer}`:'COUCHE · —'}
    if(time){time.textContent=data?.timeline?`ÉCHÉANCE · ${data.timeline}`:'ÉCHÉANCE · ACTUELLE'}
  }
  function nativeRefresh(root){
    const controls=qa('button,[role="button"]',root).filter(el=>!el.closest('[data-p073-weather-bar]'));
    const btn=controls.find(el=>/(ACTUALISER|RAFRA[IÎ]CHIR|METTRE\s+À\s+JOUR|RECHERCHER|RELANCER|↻|⟳)/i.test(safe(el.textContent||el.getAttribute('aria-label'),100)));
    if(btn&&!btn.disabled){btn.click();return true}
    const input=qa('input',root).find(el=>/ville|lieu|localisation|recherch/i.test(`${el.placeholder||''} ${el.getAttribute('aria-label')||''}`));
    if(input){input.dispatchEvent(new KeyboardEvent('keydown',{key:'Enter',code:'Enter',bubbles:true}));return true}
    return false;
  }
  function openConversation(){if(window.AuraConversationDrawer?.open){window.AuraConversationDrawer.open();return true}const btn=q('.aura-p0702-nav-btn[data-rail-target="conversation"]');if(btn){btn.click();return true}return false}
  function closeWeather(){if(window.AuraWorkspace?.home){window.AuraWorkspace.home();return true}const btn=q('.aura-p0702-nav-btn[data-rail-target="home"]');if(btn){btn.click();return true}return false}
  function buildBar(root){
    let bar=q('[data-p073-weather-bar]',root);if(bar)return bar;
    bar=document.createElement('div');bar.className='aura-p073-weather-bar';bar.dataset.p073WeatherBar='';
    bar.innerHTML=`<div class="aura-p073-brand"><span class="aura-p073-kicker">AURA · MÉTÉO</span><b data-p073-location>LOCALISATION MÉTÉO</b></div><div class="aura-p073-weather-meta"><span class="aura-p073-provider">OPEN-METEO · DONNÉES RÉELLES</span><span data-p073-state data-state="waiting">EN ATTENTE</span><span data-p073-layer>COUCHE · —</span><span data-p073-time>ÉCHÉANCE · ACTUELLE</span></div><div class="aura-p073-actions"><button type="button" data-p073-action="conversation">CONVERSATION</button><button type="button" data-p073-action="refresh">ACTUALISER</button><button type="button" data-p073-action="close" aria-label="Fermer le module météo">×</button></div>`;
    root.appendChild(bar);return bar;
  }
  function enhance(root){
    if(!root)return false;STATE.root=root;root.classList.add('aura-p073-weather-final');root.dataset.auraWeatherFinal=VERSION;buildBar(root);scan('enhance');return true;
  }
  function fingerprint(data){try{return JSON.stringify(data)}catch(_){return''}}
  function scan(reason='scan'){
    clearTimeout(STATE.scanTimer);STATE.scanTimer=0;const root=findRoot();if(!root)return null;if(root!==STATE.root||!root.classList.contains('aura-p073-weather-final'))enhance(root);
    const data=extract(root),fp=fingerprint(data);STATE.lastContext=contextFrom(data);updateStatus(root,data);
    if(fp!==STATE.lastFingerprint){STATE.lastFingerprint=fp;window.dispatchEvent(new CustomEvent('aura:weather-context-changed',{detail:{version:VERSION,reason,data,context:STATE.lastContext}}));window.AuraContextBridge?.refresh?.()}
    return data;
  }
  function schedule(reason='event',delay=100){clearTimeout(STATE.scanTimer);STATE.scanTimer=setTimeout(()=>scan(reason),delay)}
  function publish(data){if(data&&typeof data==='object')STATE.latest=Object.assign({},STATE.latest||{},data);schedule('publish',20);return true}
  function registerProvider(){
    if(!window.AuraContextBridge?.register)return false;
    const ok=window.AuraContextBridge.register('weather',async()=>{const root=findRoot();const data=root?extract(root):(STATE.latest?extract({innerText:'',textContent:'',querySelectorAll:()=>[],dataset:{}}):{});const c=contextFrom(data);STATE.lastContext=c;return c});STATE.registered=!!ok;return !!ok;
  }
  function ensureProvider(){if(STATE.registered)return true;if(registerProvider())return true;return false}

  document.addEventListener('click',event=>{
    const action=event.target.closest?.('[data-p073-action]');if(action){const root=action.closest(ROOT_SELECTOR)||findRoot();const a=action.dataset.p073Action;if(a==='conversation')openConversation();else if(a==='refresh'){const ok=nativeRefresh(root);action.dataset.result=ok?'triggered':'unavailable';schedule('refresh',240)}else if(a==='close')closeWeather();return}
    if(event.target.closest?.(ROOT_SELECTOR))schedule('weather-click',80);
  },true);
  document.addEventListener('input',event=>{if(event.target.closest?.(ROOT_SELECTOR))schedule('weather-input',180)},true);
  document.addEventListener('change',event=>{if(event.target.closest?.(ROOT_SELECTOR))schedule('weather-change',100)},true);
  window.addEventListener('aura:workspace-changed',event=>{if(safe(event.detail?.workspace,32).toLowerCase()==='weather')setTimeout(()=>{enhance(findRoot());ensureProvider();scan('workspace')},80)});
  window.addEventListener('aura:context-bridge-ready',()=>{ensureProvider();schedule('context-ready',50)});
  window.addEventListener('aura:weather-workspace-data',event=>publish(event.detail?.data||event.detail||{}));
  window.addEventListener('resize',()=>schedule('resize',100));

  const mo=new MutationObserver(muts=>{if(muts.some(m=>m.target?.closest?.(ROOT_SELECTOR)||[...m.addedNodes].some(n=>n.nodeType===1&&(n.matches?.(ROOT_SELECTOR)||n.querySelector?.(ROOT_SELECTOR)))))schedule('dom',100)});
  mo.observe(document.documentElement,{subtree:true,childList:true,attributes:true,attributeFilter:['class','aria-selected','aria-pressed','aria-hidden','data-weather-layer','data-weather-timeline']});STATE.observer=mo;

  window.AuraWeatherModuleFinal=Object.freeze({version:VERSION,enhance:()=>enhance(findRoot()),refresh:()=>scan('api'),publish,getContext:()=>STATE.lastContext?JSON.parse(JSON.stringify(STATE.lastContext)):contextFrom(findRoot()?extract(findRoot()):{}),openConversation,nativeRefresh:()=>nativeRefresh(findRoot()),isReady:()=>!!findRoot()});
  ensureProvider();setTimeout(()=>{enhance(findRoot());scan('boot')},120);
  window.dispatchEvent(new CustomEvent('aura:weather-final-ready',{detail:{version:VERSION,provider:'open-meteo',network:'existing-weather-engine-only',features:['unified-workspace','conversation-drawer','explicit-context','native-refresh','layer-timeline-context']}}));
})();
