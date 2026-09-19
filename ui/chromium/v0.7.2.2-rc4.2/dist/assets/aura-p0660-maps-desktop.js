/* AURA P0.6.6.0 MAPS DESKTOP — TRIP PLANNING */
(() => {
  'use strict';
  if(window.__AURA_P0660_TRIP_PLANNING__)return;
  window.__AURA_P0660_TRIP_PLANNING__=true;

  const token=new URLSearchParams(location.search).get('token')||'';
  const STORE='aura.maps.desktop.trip-planning.v1';
  const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
  const norm=s=>String(s??'').replace(/\s+/g,' ').trim();
  const esc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  let root=null,panel=null,compareBtn=null,lastRoutes=[],selectedIndex=0,busy=false;

  function loadPrefs(){
    try{return Object.assign({consumption:6.5,fuelPrice:1.85},JSON.parse(localStorage.getItem(STORE)||'{}'));}
    catch(_){return {consumption:6.5,fuelPrice:1.85};}
  }
  function savePrefs(){
    if(!panel)return;
    const consumption=Math.max(0,Math.min(40,Number(panel.querySelector('#auraTripConsumption')?.value)||0));
    const fuelPrice=Math.max(0,Math.min(5,Number(panel.querySelector('#auraTripFuelPrice')?.value)||0));
    try{localStorage.setItem(STORE,JSON.stringify({consumption,fuelPrice}));}catch(_){}
  }
  function defaultDeparture(){
    const d=new Date(Date.now()+5*60000);d.setSeconds(0,0);
    const off=d.getTimezoneOffset();return new Date(d.getTime()-off*60000).toISOString().slice(0,16);
  }
  async function fetchJson(url,opts={}){
    const r=await fetch(url,{cache:'no-store',...opts});
    let data=null;try{data=await r.json();}catch(_){}
    if(!r.ok||!data?.ok)throw new Error(data?.error||`http_${r.status}`);
    return data;
  }
  async function geocode(label,signal){
    const q=norm(label);if(!q)throw new Error('place_missing');
    const data=await fetchJson(`/api/nav/geocode?q=${encodeURIComponent(q)}&token=${encodeURIComponent(token)}`,{signal});
    const p=data.place||{};if(!finite(p.lat)||!finite(p.lon))throw new Error('place_not_found');
    return {lat:Number(p.lat),lon:Number(p.lon),label:norm(p.label)||q,shortLabel:norm(p.short_label)||q};
  }
  async function currentPosition(signal){
    if(!navigator.geolocation)throw new Error('origin_unavailable');
    return await new Promise((resolve,reject)=>{
      const t=setTimeout(()=>reject(new Error('origin_timeout')),6500);
      signal?.addEventListener('abort',()=>{clearTimeout(t);reject(new DOMException('Aborted','AbortError'));},{once:true});
      navigator.geolocation.getCurrentPosition(pos=>{
        clearTimeout(t);const lat=Number(pos.coords.latitude),lon=Number(pos.coords.longitude);
        if(!finite(lat)||!finite(lon))return reject(new Error('origin_invalid'));
        resolve({lat,lon,label:'Position actuelle',shortLabel:'Position actuelle'});
      },()=>{clearTimeout(t);reject(new Error('origin_unavailable'));},{enableHighAccuracy:false,timeout:6000,maximumAge:60000});
    });
  }
  async function resolvePoints(signal){
    const api=window.AURA_NAVIGATION;if(!api)throw new Error('navigation_unavailable');
    const state=api.state||{};
    const originInput=norm(root.querySelector('#auraNavOriginInput')?.value)||'Position actuelle';
    const destInput=norm(root.querySelector('#auraNavDestinationInput')?.value);
    if(!destInput)throw new Error('destination_missing');

    let origin=state.origin&&finite(state.origin.lat)&&finite(state.origin.lon)?state.origin:null;
    if(originInput && !/^(position actuelle|ma position)$/i.test(originInput)){
      if(!origin || norm(origin.label).toLocaleLowerCase('fr')!==originInput.toLocaleLowerCase('fr'))origin=await geocode(originInput,signal);
    }else if(!origin){origin=await currentPosition(signal);}

    let destination=state.destination&&finite(state.destination.lat)&&finite(state.destination.lon)?state.destination:null;
    const known=norm(destination?.shortLabel||destination?.label).toLocaleLowerCase('fr');
    if(!destination || (destInput && known!==destInput.toLocaleLowerCase('fr')))destination=await geocode(destInput,signal);

    api.setOrigin(origin);api.setDestination(destination);
    return {origin,destination};
  }
  const km=m=>Math.max(0,Number(m)||0)/1000;
  function fmtKm(m){const v=km(m);return v<10?`${v.toFixed(1).replace('.',',')} km`:`${Math.round(v)} km`;}
  function fmtDuration(sec){const m=Math.max(1,Math.round((Number(sec)||0)/60)),h=Math.floor(m/60),r=m%60;return h?`${h} h ${String(r).padStart(2,'0')}`:`${m} min`;}
  function departureDate(){const v=panel.querySelector('#auraTripDeparture')?.value;const d=v?new Date(v):new Date();return Number.isFinite(d.getTime())?d:new Date();}
  function fmtClock(d){return new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit'}).format(d);}
  function cost(route){
    const consumption=Math.max(0,Number(panel.querySelector('#auraTripConsumption')?.value)||0);
    const fuelPrice=Math.max(0,Number(panel.querySelector('#auraTripFuelPrice')?.value)||0);
    return km(route.distance)*consumption/100*fuelPrice;
  }
  function badgeFor(route,i){
    if(!lastRoutes.length)return i===0?'RECOMMANDÉ':`OPTION ${i+1}`;
    const minDur=Math.min(...lastRoutes.map(r=>Number(r.duration)||Infinity));
    const minDist=Math.min(...lastRoutes.map(r=>Number(r.distance)||Infinity));
    if((Number(route.duration)||0)===minDur && (Number(route.distance)||0)===minDist)return 'RAPIDE + COURT';
    if((Number(route.duration)||0)===minDur)return 'PLUS RAPIDE';
    if((Number(route.distance)||0)===minDist)return 'PLUS COURT';
    return `ALTERNATIVE ${i+1}`;
  }
  function renderRoutes(){
    const box=panel.querySelector('#auraTripRoutes');
    if(!lastRoutes.length){box.innerHTML='<div class="aura-trip-empty">Aucune comparaison calculée.</div>';return;}
    const dep=departureDate();
    box.innerHTML=lastRoutes.map((r,i)=>{
      const eta=new Date(dep.getTime()+(Number(r.duration)||0)*1000);
      const c=cost(r);
      return `<button class="aura-trip-route ${i===selectedIndex?'selected':''}" data-route-index="${i}" type="button">
        <div class="aura-trip-route-head"><span>${esc(badgeFor(r,i))}</span><b>${fmtDuration(r.duration)}</b></div>
        <div class="aura-trip-route-grid">
          <div><small>DISTANCE</small><strong>${fmtKm(r.distance)}</strong></div>
          <div><small>ARRIVÉE</small><strong>${fmtClock(eta)}</strong></div>
          <div><small>CARBURANT*</small><strong>${c>0?c.toLocaleString('fr-FR',{style:'currency',currency:'EUR',maximumFractionDigits:2}):'—'}</strong></div>
        </div>
        <div class="aura-trip-route-foot"><span>Péages : non renseignés par OSRM</span><em>${i===selectedIndex?'SÉLECTIONNÉ':'CHOISIR'}</em></div>
      </button>`;
    }).join('');
    box.querySelectorAll('[data-route-index]').forEach(btn=>btn.addEventListener('click',()=>selectRoute(Number(btn.dataset.routeIndex))));
  }
  function selectRoute(i){
    const route=lastRoutes[i];if(!route)return;
    selectedIndex=i;
    try{window.AURA_NAVIGATION?.useRoute?.(route,{status:`TRAJET ${i+1} SÉLECTIONNÉ`});}catch(e){setState('ERREUR DE SÉLECTION',true);return;}
    renderRoutes();setState(`TRAJET ${i+1} PRÊT · LE COCKPIT UTILISERA CET ITINÉRAIRE`);
  }
  function setState(text,error=false){
    const el=panel?.querySelector('#auraTripState');if(el){el.textContent=String(text||'PRÊT');el.classList.toggle('error',!!error);}
  }
  function setBusy(on){busy=!!on;if(compareBtn){compareBtn.disabled=busy;compareBtn.classList.toggle('busy',busy);}setState(on?'COMPARAISON DES ROUTES…':'PRÊT');}
  async function compare(){
    if(busy)return;setBusy(true);const controller=new AbortController();
    try{
      savePrefs();const {origin,destination}=await resolvePoints(controller.signal);
      const params=new URLSearchParams({
        from_lat:String(origin.lat),from_lon:String(origin.lon),to_lat:String(destination.lat),to_lon:String(destination.lon),
        profile:'driving',alternatives:'true',token
      });
      const data=await fetchJson(`/api/nav/route?${params.toString()}`,{signal:controller.signal});
      lastRoutes=Array.isArray(data.routes)&&data.routes.length?data.routes:[data.route].filter(Boolean);
      if(!lastRoutes.length)throw new Error('route_no_route');
      selectedIndex=0;renderRoutes();selectRoute(0);
      panel.classList.add('has-results');
      setState(lastRoutes.length>1?`${lastRoutes.length} ITINÉRAIRES COMPARÉS · OPTION 1 SÉLECTIONNÉE`:'1 ITINÉRAIRE DISPONIBLE · AUCUNE ALTERNATIVE OSRM');
    }catch(e){
      const code=String(e?.message||e);const friendly={destination_missing:'DESTINATION REQUISE',origin_unavailable:'POSITION INDISPONIBLE',origin_timeout:'POSITION · TIMEOUT',place_not_found:'LIEU INTROUVABLE',route_no_route:'AUCUN ITINÉRAIRE',route_unavailable:'ROUTAGE INDISPONIBLE'}[code]||'PLANIFICATION INDISPONIBLE';
      setState(friendly,true);
    }finally{busy=false;if(compareBtn){compareBtn.disabled=false;compareBtn.classList.remove('busy');}}
  }
  function install(){
    root=document.getElementById('auraNavigationWorkspace');
    if(!root||!window.AURA_NAVIGATION)return false;
    const form=root.querySelector('.aura-nav-route-form');if(!form||form.querySelector('#auraTripCompareButton'))return true;
    const prefs=loadPrefs();
    const direct=form.querySelector('#auraNavRouteButton');
    if(direct){direct.querySelector('span').textContent='ITINÉRAIRE DIRECT';const sm=direct.querySelector('small');if(sm)sm.textContent='COCKPIT · ROUTE PRINCIPALE';}
    compareBtn=document.createElement('button');compareBtn.id='auraTripCompareButton';compareBtn.type='button';compareBtn.className='aura-trip-compare';compareBtn.innerHTML='<span>COMPARER / PLANIFIER</span><small>ALTERNATIVES · COÛT · HEURE DE DÉPART</small>';
    form.appendChild(compareBtn);
    panel=document.createElement('section');panel.id='auraTripPlanner';panel.className='aura-trip-planner';panel.innerHTML=`
      <header><div><span>MAPS DESKTOP</span><b>PRÉPARATION TRAJET</b></div><em>P0.6.6.0</em></header>
      <div class="aura-trip-settings">
        <label><span>DÉPART PRÉVU</span><input id="auraTripDeparture" type="datetime-local" value="${defaultDeparture()}"></label>
        <div class="aura-trip-cost-settings">
          <label><span>CONSO L/100</span><input id="auraTripConsumption" type="number" min="0" max="40" step="0.1" value="${Number(prefs.consumption)||6.5}"></label>
          <label><span>CARBURANT €/L</span><input id="auraTripFuelPrice" type="number" min="0" max="5" step="0.01" value="${Number(prefs.fuelPrice)||1.85}"></label>
        </div>
      </div>
      <div id="auraTripRoutes" class="aura-trip-routes"><div class="aura-trip-empty">Entrez une destination puis comparez les routes.</div></div>
      <footer><span id="auraTripState">PRÊT</span><small>* estimation locale hors péages</small></footer>`;
    form.insertAdjacentElement('afterend',panel);
    compareBtn.addEventListener('click',compare);
    panel.querySelectorAll('input').forEach(el=>el.addEventListener('change',()=>{savePrefs();renderRoutes();}));
    return true;
  }
  function boot(){
    if(install())return;let n=0;const t=setInterval(()=>{if(install()||++n>80)clearInterval(t);},125);
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',boot,{once:true});else boot();
})();
