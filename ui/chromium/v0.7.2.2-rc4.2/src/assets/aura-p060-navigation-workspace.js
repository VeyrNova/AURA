/* AURA P0.6.0 NAVIGATION WORKSPACE BASE */
/* AURA P0.6.0.1 UNRESOLVED DESTINATION GUARD */
/* AURA P0.6.1 REAL ROUTING ENGINE */
/* AURA P0.6.1.1 WORKSPACE OWNERSHIP + SHELL LAYOUT */
/* AURA P0.6.1.2 NAVIGATION EXPERIENCE */
/* AURA P0.6.1.3 COCKPIT GUIDANCE + VOICE + AUTO REROUTE */
/* AURA P0.6.1.4 DYNAMIC NAVIGATION VIEW + HEADING-UP + VOICE CROSSING */
/* AURA P0.6.1.4.1 HEADING LOCK HOTFIX + STATIONARY NORTH-UP */
/* AURA P0.6.1.5 INDOOR NAVIGATION SIMULATOR + VIRTUAL GPS REPLAY */
/* AURA P0.6.1.5.1 SIMULATOR ARRIVAL STATE + HUD FIX */
/* AURA P0.6.1.5.2 ARRIVAL METRICS FINALIZATION */
/* AURA P0.6.1.5.3 FINAL APPROACH SEMANTICS */
/* AURA P0.6.6.0 MAPS DESKTOP TRIP PLANNING BRIDGE */
/* AURA P0.6.6.0.2 MAP TILE RESILIENCE */
/* AURA P0.6.6.0.3 FROZEN TILE BACKDROP */
/* AURA P0.6.6.1 POI PLACES BRIDGE */
/* AURA P0.6.4.2.2 MAPS ROUTER EVIDENCE BRIDGE */
/* AURA P0.6.4.5.1 LOCAL MAP OPEN ALIAS */
(() => {
  'use strict';
  if (window.__AURA_P060_NAVIGATION__) return;
  window.__AURA_P060_NAVIGATION__ = true;

  const token = new URLSearchParams(location.search).get('token') || '';
  const clamp=(v,a,b)=>Math.max(a,Math.min(b,Number(v)));
  const finite=v=>
    v!==null &&
    v!==undefined &&
    !(typeof v==='string' && !v.trim()) &&
    Number.isFinite(Number(v));
  const hasCoordinates=p=>!!p && finite(p.lat) && finite(p.lon);
  const norm=s=>String(s??'').replace(/\s+/g,' ').trim();
  const wrapLon=lon=>(((Number(lon)+180)%360)+360)%360-180;
  const TILE_SIZE=256;
  const MIN_Z=2;
  const MAX_Z=16;

  let root=null, map=null, tileLayer=null, overlay=null, attribution=null;
  let resizeObserver=null;
  let renderRaf=0;
  let openState=false;
  let centerLat=46.55;
  let centerLon=2.35;
  let zoom=6;
  let drag=null;
  let origin=null;
  let destination=null;
  let routeGeometry=[];
  let routeSteps=[];
  let routeSummary=null;
  let routeRequestSeq=0;
  let routeAbort=null;
  let bootAttempts=0;
  let firstOpen=true;
  let navigationActive=false;
  let navigationWatchId=null;
  let navigationFix=null;
  let routeMetrics=null;
  let navProgressDistance=0;
  let navigationAccuracy=null;
  let navOffRouteFixes=0;
  let navLastRerouteAt=0;
  let navRerouteAbort=null;
  let navCameraPausedUntil=0;
  let navVoiceStepKey=null;
  let navVoiceStage=0;
  let navVoicePrevDistance=Infinity;
  let navVoiceBusyUntil=0;
  let navVoiceBridgeState='unknown';
  let navArrivalHandled=false;
  let navMapBearing=0;
  let navMapBearingValid=false;
  let navHeadingMotionFixes=0;
  let navSummaryCollapsed=true;
  let navSimulationActive=false;
  let navSimulationCompleted=false;
  let navSimulationPaused=false;
  let navSimulationTimer=null;
  let navSimulationDistance=0;
  let navSimulationLastTs=0;
  let navSimulationFactor=1;
  let navSimulationOriginalOrigin=null;
  const NAV_SIM_BASE_KMH=70;
  const NAV_TILT_SCALE=.94;
  const NAV_HEADING_MIN_SPEED=2.2; // m/s ~= 8 km/h before engaging heading-up
  const RECENTS_KEY='aura.navigation.recents.v1';
  const VOICE_KEY='aura.navigation.voice.v1';

  function workspaceActivity(state,label,detail=''){
    window.dispatchEvent(new CustomEvent('aura:workspace-activity',{
      detail:{
        workspace:'maps',
        state:String(state||'ready'),
        label:String(label||'AURA Maps'),
        detail:String(detail||'')
      }
    }));
  }

  function mercatorClampLat(lat){
    return Math.max(-85.05112878,Math.min(85.05112878,Number(lat)||0));
  }

  function worldSize(z){ return TILE_SIZE*Math.pow(2,z); }

  function worldX(lon,z){
    return (wrapLon(lon)+180)/360*worldSize(z);
  }

  function worldY(lat,z){
    const φ=mercatorClampLat(lat)*Math.PI/180;
    const s=Math.sin(φ);
    return (.5-Math.log((1+s)/(1-s))/(4*Math.PI))*worldSize(z);
  }

  function lonFromWorldX(x,z){
    const world=worldSize(z);
    return wrapLon((Number(x)/world)*360-180);
  }

  function latFromWorldY(y,z){
    const world=worldSize(z);
    const yy=Math.max(0,Math.min(world,Number(y)));
    const n=Math.PI-(2*Math.PI*yy/world);
    return mercatorClampLat((180/Math.PI)*Math.atan(Math.sinh(n)));
  }

  function tileUrl(z,x,y){
    return `/api/map-tile/${z}/${x}/${y}.png?token=${encodeURIComponent(token)}`;
  }

  function create(){
    if(document.getElementById('auraNavigationWorkspace')) return;

    root=document.createElement('section');
    root.id='auraNavigationWorkspace';
    root.className='aura-navigation-workspace';
    root.setAttribute('aria-hidden','true');
    root.innerHTML=`
      <div class="aura-nav-shell">
        <aside class="aura-nav-sidebar">
          <div class="aura-nav-brand">
            <div>
              <span>NAVIGATION</span>
              <strong>AURA MAPS</strong>
            </div>
            <button id="auraNavClose" aria-label="Fermer la navigation">×</button>
          </div>

          <div class="aura-nav-status">
            <i></i>
            <span>CARTE ACTIVE</span>
            <b id="auraNavStatus">PRÊTE</b>
          </div>

          <div class="aura-nav-route-form">
            <label>
              <span>DÉPART</span>
              <div class="aura-nav-input-row origin">
                <i></i>
                <input id="auraNavOriginInput" type="text" value="Position actuelle" autocomplete="off">
                <button id="auraNavLocate" title="Utiliser ma position">⌖</button>
              </div>
            </label>

            <div class="aura-nav-route-line"><i></i></div>

            <label>
              <span>DESTINATION</span>
              <div class="aura-nav-input-row destination">
                <i></i>
                <input id="auraNavDestinationInput" type="text" placeholder="Où voulez-vous aller ?" autocomplete="off">
              </div>
            </label>

            <button id="auraNavRouteButton" class="aura-nav-primary" type="button">
              <span>CALCULER L’ITINÉRAIRE</span>
              <small>P0.6.1.5.3 · GUIDAGE + SIMULATION</small>
            </button>
          </div>

          <div class="aura-nav-modes">
            <span>MODE</span>
            <button class="active" data-nav-mode="car">VOITURE</button>
            <button disabled data-nav-mode="walk">À PIED</button>
            <button disabled data-nav-mode="bike">VÉLO</button>
          </div>

          <section id="auraNavSimulator" class="aura-nav-simulator">
            <header><span>MODE TEST INDOOR</span><b id="auraNavSimBadge">SIM GPS</b></header>
            <p>Rejoue l’itinéraire sans déplacement réel.</p>
            <button id="auraNavSimStart" class="aura-nav-sim-start" type="button">SIMULER LE TRAJET</button>
            <div class="aura-nav-sim-tools">
              <button id="auraNavSimPause" type="button" disabled>PAUSE</button>
              <button id="auraNavSimTurn" type="button" disabled>PROCHAIN VIRAGE</button>
              <button id="auraNavSimArrival" type="button" disabled>ARRIVÉE</button>
            </div>
            <footer id="auraNavSimState">PRÊT · 70 km/h · ACCÉLÉRATION AUTO</footer>
          </section>

          <section id="auraNavActiveRoute" class="aura-nav-active-route" aria-live="polite">
            <div class="aura-nav-active-head">
              <span>ITINÉRAIRE ACTIF</span>
              <b id="auraNavSidebarRouteName">—</b>
            </div>
            <div class="aura-nav-active-metrics">
              <div><strong id="auraNavSidebarDistance">—</strong><span>DISTANCE</span></div>
              <div><strong id="auraNavSidebarDuration">—</strong><span>DURÉE</span></div>
            </div>
            <div class="aura-nav-active-meta">
              <div><span>ARRIVÉE</span><b id="auraNavSidebarEta">—</b></div>
              <div><span>TRAFIC</span><b>NON CONNECTÉ</b></div>
            </div>
          </section>

          <section class="aura-nav-recents">
            <div class="aura-nav-section-title">DESTINATIONS RÉCENTES</div>
            <div id="auraNavRecentList" class="aura-nav-recent-list"><span>AUCUNE DESTINATION</span></div>
          </section>

          <div class="aura-nav-sidebar-foot">
            <span>AURA LOCAL NAVIGATION</span>
            <b>OSM · MERCATOR</b>
          </div>
        </aside>

        <main class="aura-nav-map">
          <div id="auraNavTileLayer" class="aura-nav-tile-layer" aria-hidden="true"></div>
          <svg id="auraNavOverlay" class="aura-nav-overlay" aria-hidden="true"></svg>
          <div class="aura-nav-grid"></div>

          <div class="aura-nav-toolbar">
            <span>CARTE</span>
            <button class="active">ITINÉRAIRE</button>
            <button data-nav-toolbar="traffic">TRAFIC</button>
            <button data-nav-toolbar="poi">POI</button>
          </div>

          <div class="aura-nav-map-controls">
            <button data-nav-map="minus" aria-label="Dézoomer">−</button>
            <button data-nav-map="recenter" aria-label="Recentrer">⌖</button>
            <button data-nav-map="plus" aria-label="Zoomer">+</button>
          </div>


          <section id="auraNavGuidanceHud" class="aura-nav-guidance-hud" aria-live="polite">
            <div class="aura-nav-hud-turn">
              <i id="auraNavHudGlyph">↑</i>
              <strong id="auraNavHudDistance">—</strong>
            </div>
            <div class="aura-nav-hud-command">
              <span id="auraNavHudKicker">PROCHAINE MANŒUVRE</span>
              <b id="auraNavHudInstruction">Suivre l’itinéraire</b>
              <small id="auraNavHudRoad">—</small>
            </div>
            <div class="aura-nav-hud-meta">
              <div><span>ARRIVÉE</span><b id="auraNavHudEta">—</b></div>
              <div><span>RESTANT</span><b id="auraNavHudRemaining">—</b></div>
              <button id="auraNavVoiceToggle" type="button" aria-pressed="true" title="Guidage vocal AURA">
                <i></i><span>VOIX AURA</span><b id="auraNavVoiceState">ON</b>
              </button>
            </div>
            <div class="aura-nav-hud-telemetry">
              <span id="auraNavGpsQuality">GPS · —</span>
              <i></i>
              <b id="auraNavSpeed">0 km/h</b>
              <em id="auraNavCameraState">SUIVI AUTO</em>
            </div>
          </section>

          <aside class="aura-nav-summary">
            <header>
              <span>ITINÉRAIRE</span>
              <small id="auraNavRouteState">EN ATTENTE</small>
              <button id="auraNavSummaryToggle" type="button" aria-label="Replier le panneau itinéraire" title="Afficher / masquer les étapes">›</button>
            </header>

            <div class="aura-nav-summary-main">
              <span>DISTANCE</span>
              <strong id="auraNavDistance">—</strong>
              <span>DURÉE ESTIMÉE</span>
              <strong id="auraNavDuration">—</strong>
            </div>

            <dl>
              <div><dt>Départ</dt><dd id="auraNavOriginLabel">Position actuelle</dd></div>
              <div><dt>Destination</dt><dd id="auraNavDestinationLabel">—</dd></div>
              <div><dt>Arrivée</dt><dd id="auraNavEta">—</dd></div>
              <div><dt>Mode</dt><dd>Voiture</dd></div>
              <div><dt>Trafic</dt><dd>Non connecté</dd></div>
            </dl>

            <div class="aura-nav-next-step">
              <div class="aura-nav-next-kicker">
                <span>PROCHAINE INSTRUCTION</span>
                <em id="auraNavNextDistance">—</em>
              </div>
              <div class="aura-nav-next-command">
                <i id="auraNavTurnGlyph">↑</i>
                <div>
                  <b id="auraNavNextInstruction">—</b>
                  <small id="auraNavNextRoad">—</small>
                </div>
              </div>
            </div>

            <div class="aura-nav-step-list" id="auraNavStepList">
              <span>ÉTAPES PRINCIPALES</span>
              <div>—</div>
            </div>

            <footer>
              <span>ROUTING ENGINE</span>
              <b>P0.6.1.5.3</b>
            </footer>
          </aside>

          <div id="auraNavMapHint" class="aura-nav-map-hint">
            GLISSER POUR DÉPLACER · MOLETTE POUR ZOOMER
          </div>

          <div id="auraNavAttribution" class="aura-nav-attribution">
            © OpenStreetMap contributors · AURA MAP
          </div>

          <div class="aura-nav-bottom">
            <span id="auraNavBottomState">CARTE PRÊTE</span>
            <i></i>
            <b id="auraNavCoordinates">—</b>
          </div>
        </main>
      </div>
    `;
    const workspaceHost =
      document.querySelector('#app > .workspace') ||
      document.querySelector('.workspace') ||
      document.body;
    workspaceHost.appendChild(root);
    root.dataset.auraWorkspaceHost =
      workspaceHost === document.body ? 'body-fallback' : 'workspace';


    map=root.querySelector('.aura-nav-map');
    tileLayer=root.querySelector('#auraNavTileLayer');
    overlay=root.querySelector('#auraNavOverlay');
    attribution=root.querySelector('#auraNavAttribution');

    bind();
    resizeObserver=new ResizeObserver(()=>scheduleRender());
    resizeObserver.observe(map);
    render();
  }

  function bind(){
    root.querySelector('#auraNavClose').addEventListener('click',close);
    root.querySelector('#auraNavLocate').addEventListener('click',()=>locate(true));
    root.querySelector('#auraNavVoiceToggle')?.addEventListener('click',()=>setNavigationVoiceEnabled(!navigationVoiceEnabled()));
    root.querySelector('#auraNavSummaryToggle')?.addEventListener('click',()=>setSummaryCollapsed(!navSummaryCollapsed));
    root.querySelector('#auraNavSimStart')?.addEventListener('click',()=>{
      if(!routeSummary || routeGeometry.length<2 || navigationActive)return;
      startNavigation(true);
    });
    root.querySelector('#auraNavSimPause')?.addEventListener('click',()=>toggleSimulationPause());
    root.querySelector('#auraNavSimTurn')?.addEventListener('click',()=>jumpSimulationToNextTurn());
    root.querySelector('#auraNavSimArrival')?.addEventListener('click',()=>jumpSimulationNearArrival());
    syncNavigationVoiceUi();
    setSummaryCollapsed(false);
    syncSimulatorUi();
    bindIntegratedPoiMode();
    bindTrafficWeatherMode();
    bindSendPhonePanel();
    bindTravelBrief();

    root.querySelector('#auraNavRouteButton').addEventListener('click',()=>{
      if(navigationActive){
        stopNavigation(true);
        return;
      }
      if(routeSummary && routeGeometry.length>=2){
        startNavigation();
        return;
      }
      calculateRoute().catch(err=>{
        if(err?.name==='AbortError')return;
        setRouteError(err);
      });
    });

    root.querySelector('#auraNavRecentList')?.addEventListener('click',e=>{
      const btn=e.target?.closest?.('[data-nav-recent]');
      if(!btn)return;
      const label=norm(btn.dataset.navRecent);
      if(label)setDestination({label});
    });

    root.querySelector('#auraNavDestinationInput').addEventListener('input',e=>{
      if(navigationActive)stopNavigation(false);
      const label=norm(e.target.value);
      destination=label?{label,lat:null,lon:null}:null;
      root.querySelector('#auraNavDestinationLabel').textContent=label||'—';
      clearRoute(false);
      root.querySelector('#auraNavRouteState').textContent=
        label?'DESTINATION À GÉOCODER':'EN ATTENTE';
      root.querySelector('#auraNavBottomState').textContent=
        label?'DESTINATION À GÉOCODER':'CARTE PRÊTE';
      scheduleRender();
    });

    root.querySelector('#auraNavOriginInput').addEventListener('input',e=>{
      if(navigationActive)stopNavigation(false);
      const label=norm(e.target.value);
      if(origin) origin.label=label||'Position actuelle';
      root.querySelector('#auraNavOriginLabel').textContent=label||'Position actuelle';
    });

    root.querySelectorAll('[data-nav-map]').forEach(btn=>{
      btn.addEventListener('click',()=>{
        const op=btn.dataset.navMap;
        if(op==='plus') setZoom(zoom+1);
        if(op==='minus') setZoom(zoom-1);
        if(op==='recenter'){
          navCameraPausedUntil=0;
          if(navigationActive)updateGuidanceCamera(true);else recenter();
          updateCameraPauseUi();
          scheduleRender();
        }
      });
    });

    map.addEventListener('wheel',e=>{
      e.preventDefault();
      zoomAt(e.clientX,e.clientY,e.deltaY<0?1:-1);
    },{passive:false});

    // AURA P0.6.6.1.4 POINTER HIT-TEST GUARD
    // Map pointer capture must never steal pointerup/click from toolbar and HUD controls.
    const auraMapInteractiveTarget=target=>!!target?.closest?.(
      'button,input,select,textarea,a,label,[role="button"],.aura-nav-toolbar,.aura-nav-map-controls,.aura-nav-summary,.aura-nav-guidance-hud,.aura-nav-bottom,.aura-nav-map-hint,.aura-nav-attribution,.aura-poi-marker'
    );

    map.addEventListener('pointerdown',e=>{
      if(e.button!==0 || auraMapInteractiveTarget(e.target))return;
      const rect=map.getBoundingClientRect();
      drag={
        id:e.pointerId,
        x:e.clientX,
        y:e.clientY,
        worldX:worldX(centerLon,zoom),
        worldY:worldY(centerLat,zoom),
        width:rect.width,
        height:rect.height
      };
      map.setPointerCapture?.(e.pointerId);
      root.classList.add('dragging');
      if(navigationActive){
        navCameraPausedUntil=Date.now()+8000;
        updateCameraPauseUi();
      }
    });

    map.addEventListener('pointermove',e=>{
      if(!drag || drag.id!==e.pointerId)return;
      const dx=e.clientX-drag.x;
      const dy=e.clientY-drag.y;
      const worldDelta=screenDeltaToWorld(dx,dy);
      centerLon=lonFromWorldX(drag.worldX-worldDelta[0],zoom);
      centerLat=latFromWorldY(drag.worldY-worldDelta[1],zoom);
      scheduleRender();
    });

    const finishDrag=e=>{
      if(!drag)return;
      if(e?.pointerId!=null && e.pointerId!==drag.id)return;
      drag=null;
      root.classList.remove('dragging');
    };
    map.addEventListener('pointerup',finishDrag);
    map.addEventListener('pointercancel',finishDrag);
    map.addEventListener('dblclick',e=>{
      e.preventDefault();
      zoomAt(e.clientX,e.clientY,1);
    });
  }

  function setBusy(flag,label='CALCUL…'){
    root?.classList.toggle('route-busy',!!flag);
    const btn=root?.querySelector('#auraNavRouteButton');
    if(!btn)return;
    btn.disabled=!!flag;
    const span=btn.querySelector('span');
    const small=btn.querySelector('small');
    if(flag){
      if(span)span.textContent=label;
      if(small)small.textContent='OSRM · CALCUL EN COURS';
      return;
    }
    updatePrimaryAction();
  }

  function updatePrimaryAction(){
    const btn=root?.querySelector('#auraNavRouteButton');
    if(!btn)return;
    const span=btn.querySelector('span');
    const small=btn.querySelector('small');
    btn.classList.toggle('navigation-stop',navigationActive);
    btn.classList.toggle('route-ready',!!routeSummary && !navigationActive);
    if(navigationActive){
      if(span)span.textContent=navArrivalHandled?'TERMINER LA NAVIGATION':'ARRÊTER LA NAVIGATION';
      if(small)small.textContent=navArrivalHandled?'DESTINATION ATTEINTE':'GPS · GUIDAGE TEMPS RÉEL';
    }else if(routeSummary){
      if(span)span.textContent='DÉMARRER LA NAVIGATION';
      if(small)small.textContent='GPS · ITINÉRAIRE PRÊT';
    }else{
      if(span)span.textContent='CALCULER L’ITINÉRAIRE';
      if(small)small.textContent='P0.6.1.5.1 · ROUTAGE RÉEL';
    }
    syncSimulatorUi();
  }


  function escapeHtml(value){
    return String(value??'').replace(/[&<>"']/g,ch=>({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[ch]));
  }

  function shortPlaceLabel(value,fallback='Destination'){
    const raw=norm(value?.shortLabel||value?.label||value||'');
    if(!raw)return fallback;
    if(/^position actuelle$/i.test(raw))return 'Position actuelle';
    const first=norm(raw.split(',')[0]);
    return first||raw||fallback;
  }

  function formatEta(seconds){
    const s=Math.max(0,Number(seconds)||0);
    if(!s)return '—';
    return new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit'}).format(new Date(Date.now()+s*1000));
  }

  function haversine(lat1,lon1,lat2,lon2){
    const R=6371000;
    const p1=Number(lat1)*Math.PI/180,p2=Number(lat2)*Math.PI/180;
    const dp=(Number(lat2)-Number(lat1))*Math.PI/180;
    const dl=(Number(lon2)-Number(lon1))*Math.PI/180;
    const a=Math.sin(dp/2)**2+Math.cos(p1)*Math.cos(p2)*Math.sin(dl/2)**2;
    return 2*R*Math.atan2(Math.sqrt(a),Math.sqrt(Math.max(0,1-a)));
  }

  function routeStepParts(step){
    const m=step?.maneuver||{};
    const type=String(m.type||'').toLowerCase();
    const mod=String(m.modifier||'').toLowerCase();
    const road=norm(step?.name||'');
    let command='Continuer';
    if(type==='depart')command='Démarrer';
    else if(type==='arrive')command='Destination';
    else if(type==='roundabout' || type==='rotary'){
      const exit=Number(m.exit||0);
      command=exit?`Au rond-point, prendre la ${exit}e sortie`:'Prendre le rond-point';
    }else if(type==='merge')command='S’insérer';
    else if(type==='on ramp')command='Prendre la bretelle';
    else if(type==='off ramp')command='Prendre la sortie';
    else if(type==='fork'){
      command=mod.includes('left')?'Rester à gauche':mod.includes('right')?'Rester à droite':'Continuer à l’embranchement';
    }else{
      command={
        'left':'Tourner à gauche',
        'right':'Tourner à droite',
        'slight left':'Prendre légèrement à gauche',
        'slight right':'Prendre légèrement à droite',
        'sharp left':'Tourner fortement à gauche',
        'sharp right':'Tourner fortement à droite',
        'straight':'Continuer tout droit',
        'uturn':'Faire demi-tour'
      }[mod] || (type==='turn'?'Tourner':'Continuer');
    }
    return {command,road};
  }

  function isArrivalStep(step){
    return String(step?.maneuver?.type||'').toLowerCase()==='arrive';
  }

  function guidanceStepParts(step){
    if(isArrivalStep(step) && !navArrivalHandled){
      return {command:'Continuez vers la destination',road:shortPlaceLabel(destination)};
    }
    return routeStepParts(step);
  }

  function turnGlyph(step){
    const m=step?.maneuver||{};
    const type=String(m.type||'').toLowerCase();
    const mod=String(m.modifier||'').toLowerCase();
    if(type==='arrive')return '◆';
    if(type==='roundabout'||type==='rotary')return '↻';
    if(type==='merge'||type==='on ramp')return mod.includes('left')?'↖':'↗';
    if(type==='off ramp')return mod.includes('left')?'↙':'↘';
    if(mod.includes('sharp left'))return '↰';
    if(mod.includes('sharp right'))return '↱';
    if(mod.includes('left'))return '←';
    if(mod.includes('right'))return '→';
    if(mod.includes('uturn'))return '↶';
    return '↑';
  }

  function formatDistance(meters){
    const m=Math.max(0,Number(meters)||0);
    if(m<1000)return `${Math.round(m)} m`;
    return `${(m/1000).toFixed(m>=100000?0:m>=10000?1:1)} km`;
  }

  function formatDuration(seconds){
    const s=Math.max(0,Math.round(Number(seconds)||0));
    // At destination the remaining duration is genuinely zero.
    // Keep the historical 1-minute floor only for a route that is still active.
    if(s===0)return '0 min';
    const h=Math.floor(s/3600);
    const m=Math.max(1,Math.round((s%3600)/60));
    return h?`${h} h ${m} min`:`${m} min`;
  }

  function currentClockLabel(){
    return new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit'}).format(new Date());
  }

  function routeStepText(step){
    const parts=routeStepParts(step);
    return parts.road?`${parts.command} sur ${parts.road}`:parts.command;
  }

  function navigationVoiceEnabled(){
    try{return localStorage.getItem(VOICE_KEY)!=='off';}catch(_){return true;}
  }

  function setNavigationVoiceEnabled(enabled){
    try{localStorage.setItem(VOICE_KEY,enabled?'on':'off');}catch(_){}
    syncNavigationVoiceUi();
    if(enabled && navigationActive) navigationSpeak('Guidage vocal AURA activé.');
  }

  function syncNavigationVoiceUi(){
    const enabled=navigationVoiceEnabled();
    const btn=root?.querySelector('#auraNavVoiceToggle');
    const state=root?.querySelector('#auraNavVoiceState');
    if(btn){
      btn.classList.toggle('off',!enabled);
      btn.classList.toggle('unavailable',navVoiceBridgeState==='unavailable');
      btn.setAttribute('aria-pressed',enabled?'true':'false');
    }
    if(state)state.textContent=!enabled?'OFF':navVoiceBridgeState==='unavailable'?'N/A':'ON';
  }

  async function shellAction(action,payload={}){
    if(!token)throw new Error('token_missing');
    const response=await fetch(`/api/action?token=${encodeURIComponent(token)}`,{
      method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({action,...payload})
    });
    let body={};
    try{body=await response.json();}catch(_){}
    if(!response.ok || !body?.ok)throw new Error(body?.error||`http_${response.status}`);
    return body;
  }

  function navigationSpeak(text,options={}){
    const phrase=norm(text);
    if(!phrase || !navigationVoiceEnabled())return Promise.resolve({skipped:true});
    const critical=!!options.critical;
    const guard=typeof options.guard==='function'?options.guard:null;
    const now=Date.now();
    const estimated=Math.min(6200,Math.max(1700,phrase.length*48));
    const delay=critical?Math.max(0,navVoiceBusyUntil-now+220):0;
    navVoiceBusyUntil=Math.max(navVoiceBusyUntil,now+delay+estimated);
    const fire=()=>{
      if(!navigationVoiceEnabled() || (guard && !guard()))return Promise.resolve({skipped:true});
      return shellAction('nav_speak',{text:phrase.slice(0,320),source:'navigation'})
        .then(body=>{navVoiceBridgeState='ready';syncNavigationVoiceUi();return body;})
        .catch(err=>{navVoiceBridgeState='unavailable';syncNavigationVoiceUi();throw err;});
    };
    if(!delay)return fire();
    return new Promise(resolve=>setTimeout(resolve,delay)).then(fire);
  }

  function spokenDistance(meters){
    const m=Math.max(0,Number(meters)||0);
    if(m>=950){
      const km=Math.max(1,Math.round(m/100)/10);
      return `${String(km).replace('.',',')} kilomètre${km>1?'s':''}`;
    }
    const step=m>=300?100:m>=100?50:m>=50?10:5;
    return `${Math.max(5,Math.round(m/step)*step)} mètres`;
  }

  function voiceCommand(step){
    const p=routeStepParts(step);
    let command=p.command
      .replace(/^Tourner /i,'Tournez ')
      .replace(/^Continuer /i,'Continuez ')
      .replace(/^Prendre /i,'Prenez ')
      .replace(/^Rester /i,'Restez ')
      .replace(/^Faire /i,'Faites ')
      .replace(/^S’insérer/i,'Insérez-vous');
    if(p.road && !/arriv/i.test(command))command+=` sur ${p.road}`;
    return command;
  }

  function announceNavigationStep(candidate){
    if(!candidate || !navigationActive || navArrivalHandled)return;
    const key=Math.round(Number(candidate.routeDistance)||0);
    const distance=Math.max(0,key-navProgressDistance);
    if(navVoiceStepKey!==key){
      navVoiceStepKey=key;
      navVoiceStage=0;
      navVoicePrevDistance=Infinity;
    }
    const previous=navVoicePrevDistance;
    navVoicePrevDistance=distance;

    // The OSRM `arrive` maneuver marks the final approach. It is not proof that
    // the vehicle has reached the destination. Never announce "arrival" here;
    // maybeHandleArrival() owns the single real arrival announcement.
    if(isArrivalStep(candidate.step))return;

    // P0.6.1.4 announces on threshold crossing, not on an exact GPS sample.
    // If GPS jumps 62 m -> 43 m, the 45 m final instruction is still emitted.
    let stage=0;
    if(distance<=45 && previous>45)stage=3;
    else if(distance<=180 && previous>180)stage=2;
    else if(distance<=600 && previous>600)stage=1;
    if(stage===0){
      const currentStage=distance<=45?3:distance<=180?2:distance<=600?1:0;
      if(currentStage>navVoiceStage)stage=currentStage;
    }
    if(stage<=navVoiceStage || stage===0)return;
    navVoiceStage=stage;
    const command=voiceCommand(candidate.step);
    const phrase=stage===3?command:`Dans ${spokenDistance(distance)}, ${command.charAt(0).toLowerCase()+command.slice(1)}`;
    const guard=stage===3?()=>{
      const current=nextNavigationStep();
      if(!navigationActive || navArrivalHandled || !current)return false;
      const currentKey=Math.round(Number(current.routeDistance)||0);
      const currentDistance=Math.max(0,currentKey-navProgressDistance);
      return currentKey===key && currentDistance<=80;
    }:null;
    navigationSpeak(phrase+'.',{critical:stage===3,guard}).catch(()=>{});
    try{window.dispatchEvent(new CustomEvent('aura:navigation:instruction',{detail:{distance,stage,text:phrase,step:candidate.step}}));}catch(_){}
  }

  function routePointAtDistance(distance){
    if(!routeMetrics || !routeGeometry.length)return null;
    const target=clamp(Number(distance)||0,0,routeMetrics.total||0);
    let lo=0,hi=routeMetrics.cumulative.length-1;
    while(lo<hi){
      const mid=Math.floor((lo+hi)/2);
      if(routeMetrics.cumulative[mid]<target)lo=mid+1;else hi=mid;
    }
    const i=Math.max(0,Math.min(routeGeometry.length-1,lo));
    const p=routeGeometry[i];
    return p?{lon:p[0],lat:p[1],index:i}:null;
  }

  function routeBearingAtProgress(){
    if(!routeMetrics || !routeGeometry.length)return null;
    const from=routePointAtDistance(navProgressDistance);
    const to=routePointAtDistance(Math.min(routeMetrics.total,navProgressDistance+80));
    if(!from||!to)return null;
    const φ1=from.lat*Math.PI/180,φ2=to.lat*Math.PI/180;
    const λ=(to.lon-from.lon)*Math.PI/180;
    const y=Math.sin(λ)*Math.cos(φ2);
    const x=Math.cos(φ1)*Math.sin(φ2)-Math.sin(φ1)*Math.cos(φ2)*Math.cos(λ);
    return (Math.atan2(y,x)*180/Math.PI+360)%360;
  }

  function guidanceHeading(){
    if(finite(navigationFix?.heading) && Number(navigationFix.heading)>=0)return Number(navigationFix.heading)%360;
    return routeBearingAtProgress();
  }

  function orientationHeading(){
    const speed=finite(navigationFix?.speed)?Math.max(0,Number(navigationFix.speed)):0;
    // At navigation start Chromium usually reports speed=0 and heading=null.
    // Do not rotate the raster map from the OSRM route alone while the vehicle is stationary.
    if(speed<NAV_HEADING_MIN_SPEED || navHeadingMotionFixes<2)return null;
    return guidanceHeading();
  }

  function bearingDelta(target,current){
    return ((Number(target)-Number(current)+540)%360)-180;
  }

  function updateMapOrientation(snap=false){
    if(!navigationActive){
      navMapBearing=0;
      navMapBearingValid=false;
      applyMapTransform();
      return;
    }
    const heading=orientationHeading();
    if(!finite(heading)){
      // Before a reliable moving course exists, keep a clean north-up map.
      // Once heading-up has engaged, keep the last stable bearing during short stops.
      if(!navMapBearingValid)navMapBearing=0;
      applyMapTransform();
      return;
    }
    const target=(Number(heading)+360)%360;
    if(!navMapBearingValid || snap){
      navMapBearing=target;
      navMapBearingValid=true;
    }else{
      const factor=Math.max(0.22,Math.min(.55,(Number(navigationFix?.speed)||0)>12?.48:.34));
      navMapBearing=(navMapBearing+bearingDelta(target,navMapBearing)*factor+360)%360;
    }
    applyMapTransform();
  }

  function applyMapTransform(){
    if(!tileLayer)return;
    const bearing=navigationActive&&navMapBearingValid?navMapBearing:0;
    const tilt=navigationActive?NAV_TILT_SCALE:1;
    tileLayer.style.transformOrigin='50% 50%';
    tileLayer.style.transform=`scaleY(${tilt}) rotate(${-bearing}deg)`;
    root?.style.setProperty('--aura-nav-bearing',`${bearing.toFixed(1)}deg`);
    root?.style.setProperty('--aura-nav-tilt',String(tilt));
  }

  function transformProjectedPoint(x,y,vp){
    if(!navigationActive || !navMapBearingValid)return [x,y];
    const cx=vp.w/2,cy=vp.h/2;
    const dx=x-cx,dy=y-cy;
    const angle=-navMapBearing*Math.PI/180;
    const cos=Math.cos(angle),sin=Math.sin(angle);
    const rx=dx*cos-dy*sin;
    const ry=dx*sin+dy*cos;
    return [cx+rx,cy+ry*NAV_TILT_SCALE];
  }

  function screenDeltaToWorld(dx,dy){
    if(!navigationActive || !navMapBearingValid)return [dx,dy];
    const sy=dy/NAV_TILT_SCALE;
    const angle=navMapBearing*Math.PI/180;
    const cos=Math.cos(angle),sin=Math.sin(angle);
    return [dx*cos-sy*sin,dx*sin+sy*cos];
  }

  function setSummaryCollapsed(collapsed){
    navSummaryCollapsed=!!collapsed;
    root?.classList.toggle('summary-collapsed',navSummaryCollapsed);
    const btn=root?.querySelector('#auraNavSummaryToggle');
    if(btn){
      btn.textContent=navSummaryCollapsed?'‹':'›';
      btn.setAttribute('aria-label',navSummaryCollapsed?'Déplier le panneau itinéraire':'Replier le panneau itinéraire');
      btn.title=navSummaryCollapsed?'Afficher les étapes':'Masquer les étapes';
    }
  }

  function updateGuidanceCamera(snapOrientation=false){
    if(!navigationActive || !hasCoordinates(origin) || !routeMetrics)return;
    if(Date.now()<navCameraPausedUntil){updateCameraPauseUi();return;}
    updateMapOrientation(snapOrientation);
    const speedKmh=Math.max(0,(Number(navigationFix?.speed)||0)*3.6);
    const next=nextNavigationStep();
    const turnDistance=next?Math.max(0,next.routeDistance-navProgressDistance):Infinity;
    const targetZoom=turnDistance<110?16:turnDistance<360?15:speedKmh>90?14:15;
    zoom=clamp(targetZoom,MIN_Z,MAX_Z);
    let lookAhead=speedKmh>90?920:speedKmh>50?600:360;
    if(turnDistance<220)lookAhead=Math.max(55,turnDistance*.68);
    const ahead=routePointAtDistance(Math.min(routeMetrics.total,navProgressDistance+lookAhead));
    if(ahead){
      const z=zoom;
      const world=worldSize(z);
      let ax=worldX(ahead.lon,z),ox=worldX(origin.lon,z);
      let dx=ax-ox;if(dx>world/2)dx-=world;if(dx<-world/2)dx+=world;
      const oy=worldY(origin.lat,z),ay=worldY(ahead.lat,z);
      const bias=.64;
      centerLon=lonFromWorldX(ox+dx*bias,z);
      centerLat=latFromWorldY(oy+(ay-oy)*bias,z);
    }else{centerLat=origin.lat;centerLon=origin.lon;}
    updateCameraPauseUi();
  }

  function updateCameraPauseUi(){
    const el=root?.querySelector('#auraNavCameraState');
    if(!el)return;
    const paused=navigationActive && Date.now()<navCameraPausedUntil;
    const waiting=navigationActive&&!navMapBearingValid;
    const cap=navigationActive&&navMapBearingValid?`CAP ${String(Math.round(navMapBearing)).padStart(3,'0')}° · `:'';
    el.textContent=navSimulationActive
      ? (navSimulationPaused?`${cap}SIM PAUSE`:`${cap}SIMULATION ×${Math.round(navSimulationFactor||1)}`)
      : (paused?`${cap}SUIVI PAUSE · 8 s`:(waiting?'NORD · CAP EN ATTENTE':`${cap}SUIVI AUTO`));
    el.classList.toggle('paused',paused);
  }

  function simulatorAdaptiveFactor(){
    if(!navSimulationActive || !routeMetrics)return 1;
    const next=nextNavigationStep();
    const turnDistance=next?Math.max(0,next.routeDistance-navProgressDistance):Infinity;
    const endDistance=Math.max(0,(routeMetrics.total||0)-navProgressDistance);
    const focus=Math.min(turnDistance,endDistance);
    if(focus>1200)return 40;
    if(focus>650)return 15;
    if(focus>250)return 6;
    return 2;
  }

  function bearingBetweenPoints(a,b){
    if(!a||!b)return null;
    const φ1=Number(a.lat)*Math.PI/180,φ2=Number(b.lat)*Math.PI/180;
    const λ=(Number(b.lon)-Number(a.lon))*Math.PI/180;
    const y=Math.sin(λ)*Math.cos(φ2);
    const x=Math.cos(φ1)*Math.sin(φ2)-Math.sin(φ1)*Math.cos(φ2)*Math.cos(λ);
    return (Math.atan2(y,x)*180/Math.PI+360)%360;
  }

  function syncSimulatorUi(){
    const panel=root?.querySelector('#auraNavSimulator');
    if(!panel)return;
    const start=root.querySelector('#auraNavSimStart');
    const pause=root.querySelector('#auraNavSimPause');
    const turn=root.querySelector('#auraNavSimTurn');
    const arrival=root.querySelector('#auraNavSimArrival');
    const state=root.querySelector('#auraNavSimState');
    const badge=root.querySelector('#auraNavSimBadge');
    const ready=!!routeSummary&&routeGeometry.length>=2;
    if(start){
      start.disabled=!ready||navigationActive;
      start.textContent=navSimulationCompleted?'SIMULATION TERMINÉE':(navSimulationActive?'SIMULATION ACTIVE':'SIMULER LE TRAJET');
    }
    if(pause){pause.disabled=!navSimulationActive;pause.textContent=navSimulationPaused?'REPRENDRE':'PAUSE';}
    if(turn)turn.disabled=!navSimulationActive;
    if(arrival)arrival.disabled=!navSimulationActive;
    if(badge)badge.textContent=navSimulationCompleted?'TERMINÉE':(navSimulationActive?(navSimulationPaused?'PAUSE':'SIM ACTIVE'):'SIM GPS');
    panel.classList.toggle('active',navSimulationActive);
    panel.classList.toggle('paused',navSimulationPaused);
    panel.classList.toggle('completed',navSimulationCompleted);
    if(state){
      state.textContent=navSimulationCompleted
        ? 'TERMINÉE · DESTINATION ATTEINTE'
        : navSimulationActive
          ? `${navSimulationPaused?'PAUSE':'LECTURE'} · ${NAV_SIM_BASE_KMH} km/h · ×${Math.round(navSimulationFactor||1)}`
          : ready?'PRÊT · 70 km/h · ACCÉLÉRATION AUTO':'CALCULE UN ITINÉRAIRE POUR TESTER';
    }
  }

  function clearSimulationTimer(){
    if(navSimulationTimer!=null){clearInterval(navSimulationTimer);navSimulationTimer=null;}
    navSimulationLastTs=0;
  }

  function simulationApplyDistance(distance){
    if(!routeMetrics)return;
    navSimulationDistance=clamp(Number(distance)||0,0,routeMetrics.total||0);
    const p=routePointAtDistance(navSimulationDistance);
    const ahead=routePointAtDistance(Math.min(routeMetrics.total,navSimulationDistance+90));
    if(!p)return;
    const heading=bearingBetweenPoints(p,ahead);
    updateNavigationFix(p.lat,p.lon,{heading,speed:NAV_SIM_BASE_KMH/3.6,accuracy:3});
  }

  function simulationTick(){
    if(!navSimulationActive || navSimulationPaused || !navigationActive || !routeMetrics || navArrivalHandled)return;
    const now=performance.now();
    if(!navSimulationLastTs){navSimulationLastTs=now;return;}
    const dt=Math.min(.5,Math.max(.02,(now-navSimulationLastTs)/1000));
    navSimulationLastTs=now;
    navSimulationFactor=simulatorAdaptiveFactor();
    const advance=(NAV_SIM_BASE_KMH/3.6)*navSimulationFactor*dt;
    navSimulationDistance=Math.max(navSimulationDistance,navProgressDistance);
    simulationApplyDistance(Math.min(routeMetrics.total,navSimulationDistance+advance));
    syncSimulatorUi();
    if(navArrivalHandled || navSimulationDistance>=routeMetrics.total-1)clearSimulationTimer();
  }

  function startSimulationLoop(){
    clearSimulationTimer();
    navSimulationLastTs=performance.now();
    navSimulationTimer=setInterval(simulationTick,100);
    syncSimulatorUi();
  }

  function toggleSimulationPause(){
    if(!navSimulationActive)return;
    navSimulationPaused=!navSimulationPaused;
    navSimulationLastTs=performance.now();
    syncSimulatorUi();
  }

  function jumpSimulationToNextTurn(){
    if(!navSimulationActive || !routeMetrics)return;
    const minTarget=navProgressDistance+120;
    let target=routeMetrics.steps.find(x=>{
      const type=String(x.step?.maneuver?.type||'').toLowerCase();
      return type!=='depart'&&type!=='arrive'&&x.routeDistance>minTarget;
    });
    if(!target)target=nextNavigationStep();
    if(!target)return;
    navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navVoiceBusyUntil=0;
    navSimulationPaused=false;
    simulationApplyDistance(Math.max(0,target.routeDistance-650));
    navSimulationLastTs=performance.now();
    syncSimulatorUi();
  }

  function jumpSimulationNearArrival(){
    if(!navSimulationActive || !routeMetrics)return;
    navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navVoiceBusyUntil=0;
    navSimulationPaused=false;
    simulationApplyDistance(Math.max(0,routeMetrics.total-260));
    navSimulationLastTs=performance.now();
    syncSimulatorUi();
  }

  function updateNavigationTelemetry(){
    const gps=root?.querySelector('#auraNavGpsQuality');
    const speed=root?.querySelector('#auraNavSpeed');
    const acc=finite(navigationAccuracy)?Math.round(Number(navigationAccuracy)):null;
    const kmh=Math.max(0,Math.round((Number(navigationFix?.speed)||0)*3.6));
    if(gps)gps.textContent=navSimulationActive?`SIM GPS · ×${Math.round(navSimulationFactor||1)}`:(acc!=null?`GPS · ±${acc} m`:'GPS · ACTIF');
    if(speed)speed.textContent=`${kmh} km/h`;
    updateCameraPauseUi();
  }

  function updateGuidanceHud(candidate,remaining){
    const hud=root?.querySelector('#auraNavGuidanceHud');
    if(!hud)return;
    hud.classList.toggle('arrived',navArrivalHandled);
    const step=candidate?.step||null;
    const approachingArrival=isArrivalStep(step) && !navArrivalHandled;
    const parts=guidanceStepParts(step);
    const distance=candidate?Math.max(0,candidate.routeDistance-navProgressDistance):0;
    hud.classList.toggle('approaching-destination',approachingArrival);
    hud.classList.toggle('maneuver-now',!navArrivalHandled&&!approachingArrival&&!!candidate&&distance<=55);
    const set=(id,value)=>{const el=root?.querySelector(id);if(el)el.textContent=value;};
    set('#auraNavHudKicker',navArrivalHandled?'ARRIVÉE':approachingArrival?'APPROCHE DESTINATION':'PROCHAINE MANŒUVRE');
    set('#auraNavHudGlyph',navArrivalHandled||approachingArrival?'◆':turnGlyph(step));
    set('#auraNavHudDistance',navArrivalHandled?'ARRIVÉE':candidate?formatDistance(distance):'—');
    set('#auraNavHudInstruction',navArrivalHandled?'Destination atteinte':step?parts.command:'Suivre l’itinéraire');
    set('#auraNavHudRoad',navArrivalHandled?shortPlaceLabel(destination):step?(parts.road||shortPlaceLabel(destination)):'—');
    set('#auraNavHudEta',navArrivalHandled?currentClockLabel():(remaining?formatEta(remaining.duration):routeSummary?formatEta(routeSummary.duration):'—'));
    set('#auraNavHudRemaining',navArrivalHandled?'0 m':(remaining?formatDistance(remaining.distance):routeSummary?formatDistance(routeSummary.distance):'—'));
    updateNavigationTelemetry();
  }

  function maybeHandleArrival(remaining){
    if(navArrivalHandled || !navigationActive || !remaining || !hasCoordinates(destination) || !hasCoordinates(origin))return;
    const direct=haversine(origin.lat,origin.lon,destination.lat,destination.lon);
    const gpsTolerance=navSimulationActive?18:clamp((Number(navigationAccuracy)||20)+8,20,42);
    const routeThreshold=navSimulationActive?22:Math.max(25,gpsTolerance);
    const routeNearEnd=remaining.distance<=routeThreshold && navProgressDistance>=Math.max(0,(routeMetrics?.total||0)-55);
    if(direct<=gpsTolerance || routeNearEnd){
      const wasSimulation=navSimulationActive;
      navArrivalHandled=true;
      if(wasSimulation){
        clearSimulationTimer();
        navSimulationActive=false;
        navSimulationPaused=false;
        navSimulationCompleted=true;
        navSimulationFactor=1;
        root?.classList.remove('simulation-live');
        if(navigationFix)navigationFix.speed=0;
      }
      root?.classList.add('navigation-arrived');
      setStatus('ARRIVÉE');
      const state=root?.querySelector('#auraNavRouteState');if(state)state.textContent='ARRIVÉE';
      const bottom=root?.querySelector('#auraNavBottomState');
      if(bottom)bottom.textContent='ARRIVÉE · 0 m · 0 min · DESTINATION ATTEINTE';
      navigationSpeak(`Vous êtes arrivé à ${shortPlaceLabel(destination)}.`);
      updatePrimaryAction();
      syncSimulatorUi();
    }
  }

  async function rerouteNavigation(){
    if(!navigationActive || !hasCoordinates(origin) || !hasCoordinates(destination))return;
    if(navRerouteAbort || Date.now()-navLastRerouteAt<15000)return;
    navLastRerouteAt=Date.now();
    const controller=new AbortController();navRerouteAbort=controller;
    root?.classList.add('navigation-rerouting');
    setStatus('RECALCUL…');
    const state=root?.querySelector('#auraNavRouteState');if(state)state.textContent='RECALCUL…';
    navigationSpeak('Recalcul de l’itinéraire.');
    try{
      const params=new URLSearchParams({from_lat:String(origin.lat),from_lon:String(origin.lon),to_lat:String(destination.lat),to_lon:String(destination.lon),profile:'driving',token});
      const data=await fetchJson(`/api/nav/route?${params.toString()}`,{signal:controller.signal});
      const route=data?.route;const coords=route?.geometry?.coordinates;
      if(!Array.isArray(coords)||coords.length<2)throw new Error('route_geometry_missing');
      routeGeometry=coords.map(p=>Array.isArray(p)&&p.length>=2?[Number(p[0]),Number(p[1])]:null).filter(Boolean).filter(p=>finite(p[0])&&finite(p[1]));
      routeSteps=Array.isArray(route.steps)?route.steps:[];
      routeSummary={distance:Number(route.distance)||0,duration:Number(route.duration)||0};
      navProgressDistance=0;navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navArrivalHandled=false;
      root?.classList.remove('navigation-arrived');
      buildRouteMetrics();
      const nearest=nearestRouteProgress(origin.lat,origin.lon);if(nearest)navProgressDistance=nearest.routeDistance;
      setStatus('GUIDAGE ACTIF');
      if(state)state.textContent='NAVIGATION ACTIVE';
      updateGuidanceCamera();updateRoutePanel();scheduleRender();
    }catch(err){
      if(err?.name!=='AbortError'){
        setStatus('HORS ITINÉRAIRE');
        if(state)state.textContent='RECALCUL IMPOSSIBLE';
      }
    }finally{
      navRerouteAbort=null;root?.classList.remove('navigation-rerouting');
    }
  }


  function updateRoutePanel(){
    const distance=root?.querySelector('#auraNavDistance');
    const duration=root?.querySelector('#auraNavDuration');
    const state=root?.querySelector('#auraNavRouteState');
    const next=root?.querySelector('#auraNavNextInstruction');
    const nextRoad=root?.querySelector('#auraNavNextRoad');
    const nextDistance=root?.querySelector('#auraNavNextDistance');
    const glyph=root?.querySelector('#auraNavTurnGlyph');
    const list=root?.querySelector('#auraNavStepList');
    const eta=root?.querySelector('#auraNavEta');
    const sideCard=root?.querySelector('#auraNavActiveRoute');
    const sideName=root?.querySelector('#auraNavSidebarRouteName');
    const sideDistance=root?.querySelector('#auraNavSidebarDistance');
    const sideDuration=root?.querySelector('#auraNavSidebarDuration');
    const sideEta=root?.querySelector('#auraNavSidebarEta');

    if(!routeSummary){
      if(distance)distance.textContent='—';
      if(duration)duration.textContent='—';
      if(eta)eta.textContent='—';
      if(next)next.textContent='—';
      if(nextRoad)nextRoad.textContent='—';
      if(nextDistance)nextDistance.textContent='—';
      if(glyph)glyph.textContent='↑';
      if(list)list.innerHTML='<span>ÉTAPES PRINCIPALES</span><div>—</div>';
      sideCard?.classList.remove('visible');
      updateGuidanceHud(null,null);
      updatePrimaryAction();
      return;
    }

    const remaining=navigationActive?navigationRemaining():null;
    const effectiveDistance=navArrivalHandled?0:(remaining?.distance ?? routeSummary.distance);
    const effectiveDuration=navArrivalHandled?0:(remaining?.duration ?? routeSummary.duration);
    const effectiveEta=navArrivalHandled?currentClockLabel():formatEta(effectiveDuration);
    if(distance)distance.textContent=formatDistance(effectiveDistance);
    if(duration)duration.textContent=formatDuration(effectiveDuration);
    if(eta)eta.textContent=effectiveEta;
    if(state)state.textContent=navArrivalHandled?'ARRIVÉE':(navigationActive?'NAVIGATION ACTIVE':'ITINÉRAIRE PRÊT');

    const useful=routeSteps.filter(s=>String(s?.maneuver?.type||'').toLowerCase()!=='depart');
    let activeStep=useful[0]||null;
    let distanceToStep=activeStep?.distance||0;
    let activeCandidate=null;
    if(navigationActive && routeMetrics){
      const candidate=nextNavigationStep();
      activeCandidate=candidate;
      if(candidate){
        activeStep=candidate.step;
        distanceToStep=Math.max(0,candidate.routeDistance-navProgressDistance);
      }
    }
    if(navArrivalHandled){activeStep=null;activeCandidate=null;distanceToStep=0;}
    const approachingArrival=isArrivalStep(activeStep) && !navArrivalHandled;
    const parts=guidanceStepParts(activeStep);
    if(next)next.textContent=navArrivalHandled?'Destination atteinte':(activeStep?parts.command:'Suivre l’itinéraire');
    if(nextRoad)nextRoad.textContent=navArrivalHandled?shortPlaceLabel(destination):(activeStep?(parts.road||shortPlaceLabel(destination)):'—');
    if(nextDistance)nextDistance.textContent=navArrivalHandled?'0 m':(activeStep?formatDistance(distanceToStep):'—');
    if(glyph)glyph.textContent=navArrivalHandled||approachingArrival?'◆':turnGlyph(activeStep);

    if(list){
      let upcoming=useful;
      if(navigationActive && routeMetrics){
        const pending=new Set(routeMetrics.steps.filter(x=>x.routeDistance>=navProgressDistance-10).map(x=>x.step));
        upcoming=useful.filter(step=>pending.has(step));
      }
      const first=upcoming.slice(0,5);
      list.innerHTML='<span>ÉTAPES PRINCIPALES</span>'+
        (first.length
          ?first.map((step,i)=>{
            const p=routeStepParts(step);
            const text=p.road?`${p.command} · ${p.road}`:p.command;
            return `<div><b>${i+1}</b><p>${escapeHtml(text)}</p><em>${escapeHtml(formatDistance(step.distance||0))}</em></div>`;
          }).join('')
          :'<div>—</div>');
    }

    sideCard?.classList.add('visible');
    if(sideName)sideName.textContent=`${shortPlaceLabel(origin,'Départ')} → ${shortPlaceLabel(destination)}`;
    if(sideDistance)sideDistance.textContent=formatDistance(effectiveDistance);
    if(sideDuration)sideDuration.textContent=formatDuration(effectiveDuration);
    if(sideEta)sideEta.textContent=effectiveEta;
    updateGuidanceHud(activeCandidate,navArrivalHandled?{distance:0,duration:0}:(remaining||{distance:effectiveDistance,duration:effectiveDuration}));
    updatePrimaryAction();
  }


  function clearRoute(clearDestinationCoords=false){
    if(navigationActive)stopNavigation(false);
    routeGeometry=[];
    routeSteps=[];
    routeSummary=null;
    routeMetrics=null;
    navProgressDistance=0;
    navSimulationCompleted=false;
    navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navArrivalHandled=false;
    root?.classList.remove('navigation-arrived','navigation-rerouting');
    if(clearDestinationCoords && destination){
      destination={...destination,lat:null,lon:null};
    }
    updateRoutePanel();
    scheduleRender();
  }

  function readRecents(){
    try{
      const value=JSON.parse(localStorage.getItem(RECENTS_KEY)||'[]');
      return Array.isArray(value)?value.filter(x=>norm(x?.label)).slice(0,4):[];
    }catch(_){return [];}
  }

  function renderRecents(){
    const box=root?.querySelector('#auraNavRecentList');
    if(!box)return;
    const recents=readRecents();
    box.innerHTML=recents.length?recents.map(item=>
      `<button type="button" data-nav-recent="${escapeHtml(item.label)}"><i></i><span>${escapeHtml(shortPlaceLabel(item.label))}</span><small>${escapeHtml(item.label)}</small></button>`
    ).join(''):'<span>AUCUNE DESTINATION</span>';
  }

  function rememberDestination(){
    const label=norm(destination?.label||destination?.shortLabel);
    if(!label)return;
    const current=readRecents().filter(x=>norm(x.label).toLowerCase()!==label.toLowerCase());
    current.unshift({label,ts:Date.now()});
    try{localStorage.setItem(RECENTS_KEY,JSON.stringify(current.slice(0,4)));}catch(_){}
    renderRecents();
  }

  function buildRouteMetrics(){
    if(!Array.isArray(routeGeometry)||routeGeometry.length<2){routeMetrics=null;return;}
    const cumulative=[0];
    for(let i=1;i<routeGeometry.length;i++){
      const a=routeGeometry[i-1],b=routeGeometry[i];
      cumulative[i]=cumulative[i-1]+haversine(a[1],a[0],b[1],b[0]);
    }
    const steps=[];
    for(const step of routeSteps){
      const loc=step?.maneuver?.location;
      if(!Array.isArray(loc)||loc.length<2||!finite(loc[0])||!finite(loc[1]))continue;
      let bestIndex=0,best=Infinity;
      for(let i=0;i<routeGeometry.length;i++){
        const p=routeGeometry[i];
        const d=haversine(loc[1],loc[0],p[1],p[0]);
        if(d<best){best=d;bestIndex=i;}
      }
      steps.push({step,index:bestIndex,routeDistance:cumulative[bestIndex]||0});
    }
    steps.sort((a,b)=>a.routeDistance-b.routeDistance);
    routeMetrics={cumulative,total:cumulative[cumulative.length-1]||routeSummary?.distance||0,steps};
  }

  function nearestRouteProgress(lat,lon){
    if(!routeMetrics||!routeGeometry.length)return null;
    let bestIndex=0,best=Infinity;
    const stride=routeGeometry.length>1800?3:routeGeometry.length>900?2:1;
    for(let i=0;i<routeGeometry.length;i+=stride){
      const p=routeGeometry[i];
      const d=haversine(lat,lon,p[1],p[0]);
      if(d<best){best=d;bestIndex=i;}
    }
    const from=Math.max(0,bestIndex-stride*2),to=Math.min(routeGeometry.length-1,bestIndex+stride*2);
    for(let i=from;i<=to;i++){
      const p=routeGeometry[i];
      const d=haversine(lat,lon,p[1],p[0]);
      if(d<best){best=d;bestIndex=i;}
    }
    return {index:bestIndex,distance:best,routeDistance:routeMetrics.cumulative[bestIndex]||0};
  }

  function navigationRemaining(){
    if(!routeSummary||!routeMetrics)return null;
    const total=Math.max(1,routeMetrics.total||routeSummary.distance||1);
    const remainingGeom=Math.max(0,total-navProgressDistance);
    const ratio=clamp(remainingGeom/total,0,1);
    return {
      distance:Math.max(0,(routeSummary.distance||total)*ratio),
      duration:Math.max(0,(routeSummary.duration||0)*ratio)
    };
  }

  function nextNavigationStep(){
    if(!routeMetrics)return null;
    return routeMetrics.steps.find(x=>{
      const type=String(x.step?.maneuver?.type||'').toLowerCase();
      return type!=='depart' && x.routeDistance>=navProgressDistance-8;
    })||null;
  }

  function updateNavigationFix(lat,lon,meta={}){
    if(!finite(lat)||!finite(lon))return;
    navigationFix={
      lat:Number(lat),lon:Number(lon),
      heading:finite(meta.heading)?Number(meta.heading):null,
      speed:finite(meta.speed)?Number(meta.speed):null
    };
    const movingSpeed=finite(navigationFix.speed)?Math.max(0,Number(navigationFix.speed)):0;
    if(navigationActive && movingSpeed>=NAV_HEADING_MIN_SPEED)navHeadingMotionFixes=Math.min(4,navHeadingMotionFixes+1);
    else if(navigationActive && !navMapBearingValid)navHeadingMotionFixes=0;
    navigationAccuracy=finite(meta.accuracy)?Number(meta.accuracy):navigationAccuracy;
    origin={lat:navigationFix.lat,lon:navigationFix.lon,label:'Position actuelle'};
    const nearest=nearestRouteProgress(origin.lat,origin.lon);
    if(nearest){
      // Never jump far backwards because of GPS noise.
      navProgressDistance=Math.max(navProgressDistance-35,nearest.routeDistance);
      if(navigationActive && nearest.distance>90){navOffRouteFixes+=1;}else navOffRouteFixes=0;
    }
    if(navigationActive){
      updateGuidanceCamera();
      if(navOffRouteFixes>=3)rerouteNavigation();
    }
    root?.querySelector('#auraNavOriginLabel') && (root.querySelector('#auraNavOriginLabel').textContent='Position actuelle');
    root?.querySelector('#auraNavOriginInput') && (root.querySelector('#auraNavOriginInput').value='Position actuelle');
    const remaining=navigationRemaining();
    const candidate=nextNavigationStep();
    maybeHandleArrival(remaining);
    announceNavigationStep(candidate);
    updateRoutePanel();
    if(remaining){
      root?.querySelector('#auraNavBottomState') &&
        (root.querySelector('#auraNavBottomState').textContent=navArrivalHandled
          ? 'ARRIVÉE · 0 m · 0 min · DESTINATION ATTEINTE'
          : `${navSimulationActive?'SIMULATION':'GUIDAGE'} · ${formatDistance(remaining.distance)} · ${formatDuration(remaining.duration)} · ARRIVÉE ${formatEta(remaining.duration)}`);
    }
    scheduleRender();
  }

  function startNavigation(simulate=false){
    if(!routeSummary||!routeMetrics||routeGeometry.length<2)return;
    navSimulationActive=!!simulate;
    navSimulationCompleted=false;
    navSimulationPaused=false;
    navSimulationFactor=1;
    navSimulationDistance=0;
    navSimulationOriginalOrigin=simulate&&origin?{...origin}:null;
    clearSimulationTimer();
    navigationActive=true;
    navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navVoiceBusyUntil=0;navArrivalHandled=false;navCameraPausedUntil=0;
    navMapBearingValid=false;
    navHeadingMotionFixes=0;
    root?.classList.add('navigation-live');
    root?.classList.toggle('simulation-live',navSimulationActive);
    setSummaryCollapsed(true);
    root?.classList.remove('navigation-arrived');
    document.body.classList.add('aura-navigation-guidance');
    setStatus(navSimulationActive?'SIMULATION ACTIVE':'GUIDAGE ACTIF');
    const state=root?.querySelector('#auraNavRouteState');
    if(state)state.textContent=navSimulationActive?'SIMULATION ACTIVE':'NAVIGATION ACTIVE';

    if(navSimulationActive){
      simulationApplyDistance(0);
      startSimulationLoop();
    }else if(hasCoordinates(origin)){
      updateNavigationFix(origin.lat,origin.lon);
    }

    zoom=Math.max(zoom,14);
    const initialCandidate=nextNavigationStep();
    const initialTurnDistance=initialCandidate?Math.max(0,initialCandidate.routeDistance-navProgressDistance):Infinity;
    if(!initialCandidate || initialTurnDistance>600){
      navigationSpeak(`${navSimulationActive?'Simulation de navigation démarrée':'Navigation démarrée'} vers ${shortPlaceLabel(destination)}. Arrivée prévue à ${formatEta(routeSummary.duration)}.`);
    }
    updatePrimaryAction();
    updateRoutePanel();
    syncSimulatorUi();

    if(!navSimulationActive && navigator.geolocation?.watchPosition){
      try{
        navigationWatchId=navigator.geolocation.watchPosition(
          pos=>updateNavigationFix(pos.coords.latitude,pos.coords.longitude,{heading:pos.coords.heading,speed:pos.coords.speed,accuracy:pos.coords.accuracy}),
          ()=>{
            root?.classList.add('gps-degraded');
            root?.querySelector('#auraNavBottomState') && (root.querySelector('#auraNavBottomState').textContent='GUIDAGE ACTIF · GPS DÉGRADÉ');
          },
          {enableHighAccuracy:true,maximumAge:1500,timeout:8000}
        );
      }catch(_){navigationWatchId=null;}
    }
  }

  function stopNavigation(refit=true){
    const wasSimulation=navSimulationActive;
    clearSimulationTimer();
    if(navigationWatchId!=null && navigator.geolocation?.clearWatch){
      try{navigator.geolocation.clearWatch(navigationWatchId);}catch(_){}
    }
    navigationWatchId=null;
    navigationActive=false;
    navigationFix=null;
    navSimulationActive=false;navSimulationCompleted=false;navSimulationPaused=false;navSimulationFactor=1;
    root?.classList.remove('simulation-live');
    if(wasSimulation && navSimulationOriginalOrigin){origin={...navSimulationOriginalOrigin};}
    navSimulationOriginalOrigin=null;
    navigationAccuracy=null;
    navProgressDistance=0;
    navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navArrivalHandled=false;navCameraPausedUntil=0;
    if(navRerouteAbort){try{navRerouteAbort.abort();}catch(_){}navRerouteAbort=null;}
    root?.classList.remove('navigation-live','gps-degraded','navigation-arrived','navigation-rerouting');
    document.body.classList.remove('aura-navigation-guidance');
    navMapBearing=0;navMapBearingValid=false;navHeadingMotionFixes=0;navVoiceBusyUntil=0;
    applyMapTransform();
    setSummaryCollapsed(false);
    if(routeSummary){
      setStatus('ITINÉRAIRE PRÊT');
      const state=root?.querySelector('#auraNavRouteState');
      if(state)state.textContent='ITINÉRAIRE PRÊT';
      if(refit)fitRoute(routeGeometry);
    }
    updateRoutePanel();
    syncSimulatorUi();
    scheduleRender();
  }

  async function fetchJson(url,options={}){
    const res=await fetch(url,{cache:'no-store',...options});
    let data=null;
    try{data=await res.json();}catch{}
    if(!res.ok || !data?.ok){
      const code=data?.error||`http_${res.status}`;
      throw new Error(code);
    }
    return data;
  }

  async function geocodeDestination(signal){
    if(hasCoordinates(destination))return destination;

    const query=norm(destination?.label || root?.querySelector('#auraNavDestinationInput')?.value);
    if(!query)throw new Error('destination_missing');

    const params=new URLSearchParams({q:query,token});
    if(hasCoordinates(origin)){
      params.set('lat',String(origin.lat));
      params.set('lon',String(origin.lon));
    }

    root.querySelector('#auraNavRouteState').textContent='GÉOCODAGE…';
    root.querySelector('#auraNavBottomState').textContent=`RECHERCHE · ${query}`;

    const data=await fetchJson(`/api/nav/geocode?${params.toString()}`,{signal});
    const p=data.place;
    if(!p || !finite(p.lat) || !finite(p.lon))throw new Error('destination_not_found');

    destination={
      lat:Number(p.lat),
      lon:Number(p.lon),
      label:norm(p.label||p.display_name||query)||query,
      shortLabel:norm(p.short_label||query)||query
    };

    const input=root.querySelector('#auraNavDestinationInput');
    const label=root.querySelector('#auraNavDestinationLabel');
    if(input)input.value=destination.shortLabel||destination.label;
    if(label)label.textContent=destination.shortLabel||destination.label;

    root.querySelector('#auraNavRouteState').textContent='DESTINATION RÉSOLUE';
    scheduleRender();
    return destination;
  }

  async function ensureOrigin(signal){
    if(hasCoordinates(origin))return origin;

    if(!navigator.geolocation)throw new Error('origin_unavailable');
    root.querySelector('#auraNavRouteState').textContent='POSITION…';

    return await new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>reject(new Error('origin_timeout')),6000);
      if(signal){
        signal.addEventListener('abort',()=>{
          clearTimeout(timer);
          reject(new DOMException('Aborted','AbortError'));
        },{once:true});
      }

      navigator.geolocation.getCurrentPosition(
        pos=>{
          clearTimeout(timer);
          const lat=Number(pos.coords.latitude),lon=Number(pos.coords.longitude);
          if(!finite(lat)||!finite(lon)){
            reject(new Error('origin_invalid'));
            return;
          }
          origin={lat,lon,label:'Position actuelle'};
          root.querySelector('#auraNavOriginInput').value='Position actuelle';
          root.querySelector('#auraNavOriginLabel').textContent='Position actuelle';
          resolve(origin);
        },
        ()=>{
          clearTimeout(timer);
          reject(new Error('origin_unavailable'));
        },
        {enableHighAccuracy:false,timeout:5500,maximumAge:60000}
      );
    });
  }

  async function calculateRoute(){
    if(!root)return;

    routeAbort?.abort();
    const controller=new AbortController();
    routeAbort=controller;
    const seq=++routeRequestSeq;

    setBusy(true,'CALCUL EN COURS…');
    root.querySelector('#auraNavStatus').textContent='CALCUL ROUTE';
    workspaceActivity(
      'loading',
      'Calcul itinéraire',
      shortPlaceLabel(destination,'Destination')
    );

    try{
      await ensureOrigin(controller.signal);
      await geocodeDestination(controller.signal);
      if(seq!==routeRequestSeq)return;

      root.querySelector('#auraNavRouteState').textContent='CALCUL ROUTE…';
      root.querySelector('#auraNavBottomState').textContent='OSRM · CALCUL DE L’ITINÉRAIRE';

      const params=new URLSearchParams({
        from_lat:String(origin.lat),
        from_lon:String(origin.lon),
        to_lat:String(destination.lat),
        to_lon:String(destination.lon),
        profile:'driving',
        token
      });

      const data=await fetchJson(`/api/nav/route?${params.toString()}`,{
        signal:controller.signal
      });
      if(seq!==routeRequestSeq)return;

      const route=data.route;
      const coords=route?.geometry?.coordinates;
      if(!Array.isArray(coords) || coords.length<2)throw new Error('route_geometry_missing');

      routeGeometry=coords
        .map(p=>Array.isArray(p)&&p.length>=2?[Number(p[0]),Number(p[1])]:null)
        .filter(Boolean)
        .filter(p=>finite(p[0])&&finite(p[1]));

      routeSteps=Array.isArray(route.steps)?route.steps:[];
      routeSummary={
        distance:Number(route.distance)||0,
        duration:Number(route.duration)||0
      };
      navProgressDistance=0;navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navArrivalHandled=false;
      root?.classList.remove('navigation-arrived');
      buildRouteMetrics();
      rememberDestination();

      updateRoutePanel();
      fitRoute(routeGeometry);
      root.querySelector('#auraNavStatus').textContent='ITINÉRAIRE PRÊT';
      root.querySelector('#auraNavBottomState').textContent=
        `ROUTE · ${formatDistance(routeSummary.distance)} · ${formatDuration(routeSummary.duration)}`;
      workspaceActivity(
        'ready',
        'Itinéraire prêt',
        `${shortPlaceLabel(origin,'Départ')} → ${shortPlaceLabel(destination,'Destination')} · ${formatDistance(routeSummary.distance)}`
      );
      scheduleRender();
    }finally{
      if(seq===routeRequestSeq){
        setBusy(false);
        routeAbort=null;
      }
    }
  }

  function useRoute(route, options={}){
    if(!root)create();
    const coords=route?.geometry?.coordinates;
    if(!Array.isArray(coords) || coords.length<2)throw new Error('route_geometry_missing');

    routeGeometry=coords
      .map(p=>Array.isArray(p)&&p.length>=2?[Number(p[0]),Number(p[1])]:null)
      .filter(Boolean)
      .filter(p=>finite(p[0])&&finite(p[1]));
    if(routeGeometry.length<2)throw new Error('route_geometry_missing');

    routeSteps=Array.isArray(route.steps)?route.steps:[];
    routeSummary={distance:Number(route.distance)||0,duration:Number(route.duration)||0};
    navProgressDistance=0;navOffRouteFixes=0;navVoiceStepKey=null;navVoiceStage=0;navVoicePrevDistance=Infinity;navArrivalHandled=false;
    root?.classList.remove('navigation-arrived');
    buildRouteMetrics();
    if(options.remember!==false)rememberDestination();
    updateRoutePanel();
    fitRoute(routeGeometry);
    root.querySelector('#auraNavStatus').textContent=String(options.status||'ITINÉRAIRE PRÊT');
    root.querySelector('#auraNavBottomState').textContent=`ROUTE · ${formatDistance(routeSummary.distance)} · ${formatDuration(routeSummary.duration)}`;
    scheduleRender();
    return {distance:routeSummary.distance,duration:routeSummary.duration,points:routeGeometry.length,steps:routeSteps.length};
  }

  function setRouteError(err){
    const code=String(err?.message||err||'route_error');
    const friendly={
      destination_missing:'DESTINATION REQUISE',
      destination_not_found:'DESTINATION INTROUVABLE',
      geocode_unavailable:'GÉOCODAGE INDISPONIBLE',
      origin_unavailable:'POSITION INDISPONIBLE',
      origin_timeout:'POSITION · TIMEOUT',
      route_no_route:'AUCUN ITINÉRAIRE',
      route_unavailable:'ROUTAGE INDISPONIBLE'
    }[code]||'ERREUR ITINÉRAIRE';

    setBusy(false);
    root?.querySelector('#auraNavRouteState') &&
      (root.querySelector('#auraNavRouteState').textContent=friendly);
    root?.querySelector('#auraNavStatus') &&
      (root.querySelector('#auraNavStatus').textContent='ERREUR');
    root?.querySelector('#auraNavBottomState') &&
      (root.querySelector('#auraNavBottomState').textContent=friendly);
    workspaceActivity('error','Itinéraire indisponible',friendly);
  }

  function fitRoute(coords){
    if(!map || !Array.isArray(coords) || coords.length<2)return;
    const rect=map.getBoundingClientRect();
    if(rect.width<100||rect.height<100)return;

    let best=null;
    for(let z=MAX_Z;z>=MIN_Z;z--){
      const xs=[],ys=[];
      for(const [lon,lat] of coords){
        xs.push(worldX(lon,z));
        ys.push(worldY(lat,z));
      }

      // Routes normally do not cross the dateline; normalize if they do.
      const world=worldSize(z);
      const minX=Math.min(...xs),maxX=Math.max(...xs);
      const minY=Math.min(...ys),maxY=Math.max(...ys);
      const spanX=maxX-minX,spanY=maxY-minY;

      const usableW=Math.max(160,rect.width-380);
      const usableH=Math.max(160,rect.height-200);
      if(spanX<=usableW && spanY<=usableH){
        best={z,minX,maxX,minY,maxY};
        break;
      }
    }
    if(!best)return;

    zoom=best.z;
    centerLon=lonFromWorldX((best.minX+best.maxX)/2,zoom);
    centerLat=latFromWorldY((best.minY+best.maxY)/2,zoom);
    zoom=Math.max(MIN_Z,zoom-1);
  }


  function scheduleRender(){
    if(renderRaf)return;
    renderRaf=requestAnimationFrame(()=>{
      renderRaf=0;
      render();
    });
  }

  function setZoom(next){
    zoom=clamp(Math.round(next),MIN_Z,MAX_Z);
    scheduleRender();
  }

  function zoomAt(clientX,clientY,delta){
    if(!map)return;
    const rect=map.getBoundingClientRect();
    if(rect.width<20||rect.height<20)return;

    const next=clamp(zoom+delta,MIN_Z,MAX_Z);
    if(next===zoom)return;

    const px=clientX-rect.left;
    const py=clientY-rect.top;

    const oldCX=worldX(centerLon,zoom);
    const oldCY=worldY(centerLat,zoom);
    const screenOffset=[px-rect.width/2,py-rect.height/2];
    const worldOffset=screenDeltaToWorld(screenOffset[0],screenOffset[1]);
    const anchorX=oldCX+worldOffset[0];
    const anchorY=oldCY+worldOffset[1];

    const scale=Math.pow(2,next-zoom);
    const newAnchorX=anchorX*scale;
    const newAnchorY=anchorY*scale;

    const newCX=newAnchorX-worldOffset[0];
    const newCY=newAnchorY-worldOffset[1];

    zoom=next;
    centerLon=lonFromWorldX(newCX,zoom);
    centerLat=latFromWorldY(newCY,zoom);
    scheduleRender();
  }

  function viewport(){
    if(!map)return null;
    const rect=map.getBoundingClientRect();
    return {w:rect.width,h:rect.height,z:zoom,cx:worldX(centerLon,zoom),cy:worldY(centerLat,zoom)};
  }

  function render(){
    if(!map||!tileLayer||!overlay)return;
    const vp=viewport();
    if(!vp||vp.w<20||vp.h<20)return;

    applyMapTransform();
    renderTiles(vp);
    renderOverlay(vp);

    const coords=root.querySelector('#auraNavCoordinates');
    if(coords) coords.textContent=`${centerLat.toFixed(4)}° · ${centerLon.toFixed(4)}° · Z${zoom}`;
  }

  const AURA_TILE_RETRY_DELAYS=[650,1600,3200];
  const AURA_TILE_SLOW_RETRY_DELAY=7000;
  const AURA_TILE_BACKDROP_MAX_MS=5200;
  let auraTileLastVp=null;
  let auraTileLastTransform='';
  let auraTileBackdropGeneration=0;
  let auraTileBackdropActive=false;

  function auraTileStatus(){
    if(!map)return null;
    let el=map.querySelector('#auraNavTileStatus');
    if(!el){
      el=document.createElement('div');
      el.id='auraNavTileStatus';
      el.className='aura-nav-tile-status';
      el.setAttribute('aria-live','polite');
      el.textContent='CHARGEMENT CARTOGRAPHIQUE';
      map.appendChild(el);
    }
    return el;
  }

  function auraTileBackdrop(){
    if(!map||!tileLayer)return null;
    let layer=map.querySelector('#auraNavTileBackdrop');
    if(!layer){
      layer=document.createElement('div');
      layer.id='auraNavTileBackdrop';
      layer.className='aura-nav-tile-backdrop';
      layer.setAttribute('aria-hidden','true');
      map.insertBefore(layer,tileLayer);
    }
    return layer;
  }

  function auraTileNeedsBackdrop(vp){
    if(!auraTileLastVp)return false;
    if(vp.z!==auraTileLastVp.z)return true;
    const dx=Math.abs(vp.cx-auraTileLastVp.cx);
    const dy=Math.abs(vp.cy-auraTileLastVp.cy);
    return dx>Math.max(180,vp.w*.55) || dy>Math.max(180,vp.h*.55);
  }

  function auraTileCaptureBackdrop(){
    const layer=auraTileBackdrop();
    if(!layer||!tileLayer)return false;
    const loaded=Array.from(tileLayer.querySelectorAll('img[data-aura-state="loaded"]'));
    if(!loaded.length)return false;
    const generation=++auraTileBackdropGeneration;
    layer.replaceChildren();
    for(const img of loaded){
      const clone=img.cloneNode(false);
      clone.removeAttribute('data-aura-bound');
      clone.removeAttribute('data-aura-wanted');
      clone.className='aura-nav-tile aura-nav-tile-backdrop-img';
      clone.style.opacity='1';
      layer.appendChild(clone);
    }
    layer.style.transformOrigin='50% 50%';
    layer.style.transform=auraTileLastTransform||tileLayer.style.transform||'';
    layer.classList.remove('aura-nav-tile-backdrop-retiring');
    layer.classList.add('aura-nav-tile-backdrop-active');
    auraTileBackdropActive=true;
    setTimeout(()=>{
      if(generation===auraTileBackdropGeneration)auraTileRetireBackdrop(true);
    },AURA_TILE_BACKDROP_MAX_MS);
    return true;
  }

  function auraTileRetireBackdrop(force=false){
    const layer=map?.querySelector('#auraNavTileBackdrop');
    if(!layer||!auraTileBackdropActive)return;
    if(layer.classList.contains('aura-nav-tile-backdrop-retiring'))return;
    layer.classList.add('aura-nav-tile-backdrop-retiring');
    const generation=auraTileBackdropGeneration;
    setTimeout(()=>{
      if(generation!==auraTileBackdropGeneration)return;
      layer.replaceChildren();
      layer.classList.remove('aura-nav-tile-backdrop-active','aura-nav-tile-backdrop-retiring');
      layer.style.transform='';
      auraTileBackdropActive=false;
    },force?220:340);
  }

  function auraTileCurrentImages(){
    if(!tileLayer)return [];
    return Array.from(tileLayer.querySelectorAll('img[data-aura-wanted="1"]'));
  }

  function auraTileRefreshStatus(){
    if(!root||!tileLayer)return;
    const current=auraTileCurrentImages();
    const total=current.length;
    let loaded=0,pending=0,failed=0;
    for(const img of current){
      const state=img.dataset.auraState||'';
      if(state==='loaded')loaded++;
      else if(state==='failed')failed++;
      else pending++;
    }
    root.classList.toggle('tiles-loading',pending>0);
    root.classList.toggle('tiles-degraded',failed>0);
    const status=auraTileStatus();
    if(status){
      if(pending>0)status.textContent=`CHARGEMENT CARTOGRAPHIQUE · ${loaded}/${total}`;
      else if(failed>0)status.textContent=`CARTE PARTIELLE · ${failed} TUILE${failed>1?'S':''} À RECHARGER`;
      else status.textContent='CARTE PRÊTE';
    }
    if(auraTileBackdropActive && total>0){
      const coverage=loaded/Math.max(1,total);
      if(coverage>=.72 || (pending===0 && loaded>0))auraTileRetireBackdrop(false);
    }
  }

  function auraTileStart(img,baseUrl,attempt=0){
    if(!img||!img.isConnected)return;
    img.dataset.auraBaseUrl=baseUrl;
    img.dataset.auraAttempt=String(attempt);
    img.dataset.auraState=attempt>0?'retrying':'loading';
    img.classList.remove('aura-nav-tile-failed');
    const retry=attempt>0?`&aura_retry=${attempt}&aura_nonce=${Date.now()}`:'';
    img.src=baseUrl+retry;
    auraTileRefreshStatus();
  }

  function auraTileBind(img){
    if(img.dataset.auraBound==='1')return;
    img.dataset.auraBound='1';
    img.addEventListener('load',()=>{
      img.dataset.auraState='loaded';
      img.dataset.auraAttempt='0';
      img.dataset.auraCycle='0';
      img.classList.remove('aura-nav-tile-failed');
      auraTileRefreshStatus();
    });
    img.addEventListener('error',()=>{
      if(!img.isConnected || img.dataset.auraWanted!=='1')return;
      const attempt=Number(img.dataset.auraAttempt||0);
      const base=img.dataset.auraBaseUrl||img.src;
      if(attempt<AURA_TILE_RETRY_DELAYS.length){
        const next=attempt+1,delay=AURA_TILE_RETRY_DELAYS[attempt];
        img.dataset.auraState='retrying';
        auraTileRefreshStatus();
        setTimeout(()=>{if(img.isConnected&&img.dataset.auraWanted==='1')auraTileStart(img,base,next);},delay);
        return;
      }
      img.dataset.auraState='failed';
      img.classList.add('aura-nav-tile-failed');
      auraTileRefreshStatus();
      const cycle=Number(img.dataset.auraCycle||0);
      if(cycle<1){
        img.dataset.auraCycle=String(cycle+1);
        setTimeout(()=>{
          if(img.isConnected&&img.dataset.auraWanted==='1'&&img.dataset.auraState==='failed')auraTileStart(img,base,1);
        },AURA_TILE_SLOW_RETRY_DELAY);
      }
    });
  }

  function renderTiles(vp){
    const left=vp.cx-vp.w/2;
    const top=vp.cy-vp.h/2;
    if(auraTileNeedsBackdrop(vp))auraTileCaptureBackdrop();

    const padTiles=navigationActive?2:1;
    const minTX=Math.floor(left/TILE_SIZE)-padTiles;
    const maxTX=Math.floor((left+vp.w)/TILE_SIZE)+padTiles;
    const minTY=Math.max(0,Math.floor(top/TILE_SIZE)-padTiles);
    const maxTY=Math.min(Math.pow(2,vp.z)-1,Math.floor((top+vp.h)/TILE_SIZE)+padTiles);
    const n=Math.pow(2,vp.z);
    tileLayer.querySelectorAll('img[data-key]').forEach(img=>{img.dataset.auraWanted='0';});

    for(let ty=minTY;ty<=maxTY;ty++){
      for(let tx=minTX;tx<=maxTX;tx++){
        const wrapped=((tx%n)+n)%n;
        const key=`${vp.z}/${wrapped}/${ty}/${tx}`;
        let img=tileLayer.querySelector(`img[data-key="${CSS.escape(key)}"]`);
        if(!img){
          img=document.createElement('img');
          img.className='aura-nav-tile';
          img.dataset.key=key;
          img.dataset.auraWanted='1';
          img.dataset.auraState='loading';
          img.dataset.auraCycle='0';
          img.alt=''; img.draggable=false; img.decoding='async';
          try{img.fetchPriority=navigationActive?'high':'auto';}catch(_){ }
          auraTileBind(img); tileLayer.appendChild(img); auraTileStart(img,tileUrl(vp.z,wrapped,ty),0);
        }else{
          img.dataset.auraWanted='1';
          img.classList.remove('aura-nav-tile-failed','aura-nav-tile-stale','aura-nav-tile-retiring');
        }
        img.style.left=`${tx*TILE_SIZE-left}px`;
        img.style.top=`${ty*TILE_SIZE-top}px`;
        img.style.width=`${TILE_SIZE}px`;
        img.style.height=`${TILE_SIZE}px`;
      }
    }

    tileLayer.querySelectorAll('img[data-key]').forEach(img=>{
      if(img.dataset.auraWanted!=='1')img.remove();
    });
    auraTileLastVp={w:vp.w,h:vp.h,z:vp.z,cx:vp.cx,cy:vp.cy};
    auraTileLastTransform=tileLayer.style.transform||'';
    auraTileRefreshStatus();
  }

  function project(lat,lon,vp){
    const world=worldSize(vp.z);
    let dx=worldX(lon,vp.z)-vp.cx;
    if(dx>world/2)dx-=world;
    if(dx<-world/2)dx+=world;
    return transformProjectedPoint(vp.w/2+dx,vp.h/2+(worldY(lat,vp.z)-vp.cy),vp);
  }

  function svg(tag,attrs={}){
    const el=document.createElementNS('http://www.w3.org/2000/svg',tag);
    for(const [k,v] of Object.entries(attrs)){
      if(v!=null)el.setAttribute(k,String(v));
    }
    return el;
  }

  function renderOverlay(vp){
    overlay.setAttribute('viewBox',`0 0 ${vp.w} ${vp.h}`);
    overlay.replaceChildren();

    const pathFor=(coords)=>{
      let d='',last=null;
      for(const point of coords){
        const lon=point[0],lat=point[1];
        const p=project(lat,lon,vp);
        if(!last)d+=`M${p[0].toFixed(1)},${p[1].toFixed(1)}`;
        else{
          const jump=Math.hypot(p[0]-last[0],p[1]-last[1]);
          d+=jump>Math.max(vp.w,vp.h)*.7?`M${p[0].toFixed(1)},${p[1].toFixed(1)}`:`L${p[0].toFixed(1)},${p[1].toFixed(1)}`;
        }
        last=p;
      }
      return d;
    };

    if(Array.isArray(routeGeometry) && routeGeometry.length>=2){
      const d=pathFor(routeGeometry);
      overlay.appendChild(svg('path',{d,class:'aura-nav-route-glow'}));
      overlay.appendChild(svg('path',{d,class:'aura-nav-route-live'}));
      if(navigationActive && routeMetrics && navProgressDistance>0){
        let idx=0;
        for(let i=0;i<routeMetrics.cumulative.length;i++){
          if(routeMetrics.cumulative[i]<=navProgressDistance)idx=i;else break;
        }
        if(idx>1){
          overlay.appendChild(svg('path',{d:pathFor(routeGeometry.slice(0,idx+1)),class:'aura-nav-route-complete'}));
        }
      }
    }

    const marker=(point,kind,fallback)=>{
      if(!hasCoordinates(point))return;
      const [x,y]=project(point.lat,point.lon,vp);
      const g=svg('g',{class:`aura-nav-marker aura-nav-marker-${kind}`});
      g.appendChild(svg('circle',{cx:x,cy:y,r:18,class:'pulse pulse-a'}));
      g.appendChild(svg('circle',{cx:x,cy:y,r:18,class:'pulse pulse-b'}));
      g.appendChild(svg('circle',{cx:x,cy:y,r:5,class:'core'}));
      if(kind==='origin' && navigationActive){
        const heading=guidanceHeading();
        if(finite(heading)){
          const screenHeading=(Number(heading)-(navigationActive&&navMapBearingValid?navMapBearing:0)+360)%360;
          const arrow=svg('path',{d:`M${x},${y-13} L${x+7},${y+7} L${x},${y+3} L${x-7},${y+7} Z`,class:'heading-arrow',transform:`rotate(${screenHeading.toFixed(1)} ${x} ${y})`});
          g.appendChild(arrow);
        }
      }
      const label=shortPlaceLabel(point,fallback);
      const estimated=Math.min(124,Math.max(52,label.length*6.1+18));
      const placeLeft=x>vp.w*.72;
      const rectX=placeLeft?x-estimated-15:x+14;
      const textX=placeLeft?x-23:x+23;
      const anchor=placeLeft?'end':'start';
      g.appendChild(svg('rect',{x:rectX,y:y-11,width:estimated,height:22,rx:6,class:'label-bg'}));
      const t=svg('text',{x:textX,y:y+3,'text-anchor':anchor});
      t.textContent=label;
      g.appendChild(t);
      overlay.appendChild(g);
    };

    marker(origin,'origin','Position actuelle');
    marker(destination,'destination','Destination');
  }


  function locate(userInitiated=false){
    if(!navigator.geolocation){
      if(userInitiated) setStatus('LOCALISATION INDISPONIBLE');
      return;
    }

    setStatus('LOCALISATION…');
    navigator.geolocation.getCurrentPosition(
      pos=>{
        const lat=Number(pos.coords.latitude);
        const lon=Number(pos.coords.longitude);
        if(!finite(lat)||!finite(lon))return;

        origin={lat,lon,label:'Position actuelle'};
        centerLat=lat;
        centerLon=lon;
        zoom=Math.max(zoom,11);
        root.querySelector('#auraNavOriginInput').value='Position actuelle';
        root.querySelector('#auraNavOriginLabel').textContent='Position actuelle';
        setStatus('POSITION ACQUISE');
        scheduleRender();
      },
      ()=>{
        setStatus(userInitiated?'LOCALISATION REFUSÉE':'CARTE PRÊTE');
      },
      {enableHighAccuracy:false,timeout:3500,maximumAge:60000}
    );
  }

  function setStatus(text){
    const el=root?.querySelector('#auraNavStatus');
    if(el)el.textContent=String(text||'PRÊTE');
  }

  function recenter(){
    if(hasCoordinates(origin)){
      centerLat=origin.lat;
      centerLon=origin.lon;
      zoom=Math.max(zoom,11);
    }else if(hasCoordinates(destination)){
      centerLat=destination.lat;
      centerLon=destination.lon;
    }
    scheduleRender();
  }

  function setOrigin(value){
    if(!value)return;
    origin={
      lat:finite(value.lat)?Number(value.lat):null,
      lon:finite(value.lon)?Number(value.lon):null,
      label:norm(value.label)||'Départ'
    };
    const input=root?.querySelector('#auraNavOriginInput');
    const label=root?.querySelector('#auraNavOriginLabel');
    if(input)input.value=origin.label;
    if(label)label.textContent=origin.label;
    if(hasCoordinates(origin)){
      centerLat=origin.lat;centerLon=origin.lon;
    }
    scheduleRender();
  }

  function setDestination(value){
    if(!value){
      destination=null;
      const input=root?.querySelector('#auraNavDestinationInput');
      const label=root?.querySelector('#auraNavDestinationLabel');
      if(input)input.value='';
      if(label)label.textContent='—';
      scheduleRender();
      return;
    }

    destination={
      lat:finite(value.lat)?Number(value.lat):null,
      lon:finite(value.lon)?Number(value.lon):null,
      label:norm(value.label)||'Destination',
      shortLabel:norm(value.shortLabel)||shortPlaceLabel(value,'Destination')
    };
    const input=root?.querySelector('#auraNavDestinationInput');
    const label=root?.querySelector('#auraNavDestinationLabel');
    if(input)input.value=destination.shortLabel||destination.label;
    if(label)label.textContent=destination.shortLabel||destination.label;

    const state=root?.querySelector('#auraNavRouteState');
    const bottom=root?.querySelector('#auraNavBottomState');
    clearRoute(false);
    if(hasCoordinates(destination)){
      if(state)state.textContent='DESTINATION RÉSOLUE';
      if(bottom)bottom.textContent='DESTINATION GÉOCODÉE · PRÊTE AU CALCUL';
    }else{
      if(state)state.textContent='DESTINATION À GÉOCODER';
      if(bottom)bottom.textContent='DESTINATION À GÉOCODER';
    }
    scheduleRender();
  }

  function open(opts={}){
    create();
    if(!navigationActive)setSummaryCollapsed(false);

    // P0.6.1.1 workspace ownership:
    // Navigation owns the central workspace while open. Close the weather
    // workspace first so two full-size modules can never fight for focus.
    try{
      window.AURA_WORKSPACES?.weather?.close?.();
    }catch(_){}

    if(opts.center && hasCoordinates(opts.center)){
      centerLat=Number(opts.center.lat);
      centerLon=Number(opts.center.lon);
      if(finite(opts.center.zoom))zoom=clamp(Math.round(opts.center.zoom),MIN_Z,MAX_Z);
    }
    if(opts.origin)setOrigin(opts.origin);
    if(opts.destination)setDestination(opts.destination);

    root.classList.add('open');
    root.setAttribute('aria-hidden','false');
    openState=true;
    document.documentElement.classList.add('aura-navigation-open');
    document.body.classList.add('aura-workspace-active','aura-navigation-active');
    workspaceActivity(
      'ready',
      'AURA Maps ouvert',
      shortPlaceLabel(destination,'Navigation')
    );

    if(firstOpen){
      firstOpen=false;
      // P0.8.5.4.7.5.1: never overwrite an explicit route origin supplied by Core.
      if(!opts.origin && !hasCoordinates(origin))setTimeout(()=>locate(false),120);
    }
    setTimeout(()=>scheduleRender(),30);
  }

  function close(){
    if(!root)return;
    if(navigationActive)stopNavigation(false);
    root.classList.remove('open');
    root.setAttribute('aria-hidden','true');
    openState=false;
    document.documentElement.classList.remove('aura-navigation-open');
    document.body.classList.remove('aura-navigation-active');
    if(!document.body.classList.contains('aura-weather-active')){
      document.body.classList.remove('aura-workspace-active');
    }
  }

  function maybeOpenFromText(text){
    const q=norm(text);
    if(!q)return;
    if(/\b(m[ée]t[ée]o|pluie|temp[ée]rature|nuages?|pression|vent)\b/i.test(q))return;
    if(!/\b(carte|navigation|itin[ée]raire|emm[eè]ne[- ]?moi|route\s+(?:vers|pour)|aller\s+(?:[àa]|vers))\b/i.test(q))return;

    let dest='';
    const m=q.match(/(?:emm[eè]ne[- ]?moi|itin[ée]raire|navigation|route|aller)\s+(?:vers|pour|[àa]|au|aux)\s+(.+)$/i);
    if(m)dest=norm(m[1]).replace(/[?.!]+$/,'');

    open(dest?{destination:{label:dest}}:{});
  }

  function normalizeLocalMapCommand(value){
    return String(value||'')
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g,'')
      .toLowerCase()
      .replace(/[’']/g,' ')
      .replace(/[^a-z0-9 ]+/g,' ')
      .replace(/\s+/g,' ')
      .trim();
  }

  const LOCAL_MAP_OPEN_COMMANDS=new Set([
    'ouvre la carte',
    'ouvre carte',
    'affiche la carte',
    'ouvre maps',
    'ouvre aura maps',
    'ouvre la navigation',
    'affiche maps',
  ]);

  async function speakLocalMapConfirmation(){
    try{
      const token=new URLSearchParams(location.search).get('token')||'';
      if(!token)return;
      await fetch(`/api/action?token=${encodeURIComponent(token)}`,{
        method:'POST',
        cache:'no-store',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({action:'voice_speak',text:"J'ouvre Maps."})
      });
    }catch(_){}
  }

  function consumeLocalMapOpen(input){
    if(!input || !('value' in input))return false;
    const value=normalizeLocalMapCommand(input.value);
    if(!LOCAL_MAP_OPEN_COMMANDS.has(value))return false;

    open({});
    input.value='';
    input.style.height='auto';
    input.dispatchEvent(new Event('input',{bubbles:true}));
    workspaceActivity('ready','AURA Maps ouvert','Commande locale');
    speakLocalMapConfirmation();
    return true;
  }

  function installComposerBridge(){
    document.addEventListener('keydown',e=>{
      if(e.key!=='Enter'||e.shiftKey||e.ctrlKey||e.altKey||e.metaKey)return;
      const el=e.target;
      if(!el || !('value' in el))return;

      // Exact navigation-open commands are local UI commands. Consume them
      // before main.js can call send_message, so quota/provider state is irrelevant.
      if(consumeLocalMapOpen(el)){
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      // Destination/itinerary requests still travel through the validated Core
      // Maps Tool route; this early visual opening only prepares the workspace.
      maybeOpenFromText(el.value);
    },true);

    document.addEventListener('click',e=>{
      const btn=e.target?.closest?.('button');
      if(!btn)return;
      const active=document.activeElement;

      if(
        btn.id==='sendBtn'
        && active
        && 'value' in active
        && consumeLocalMapOpen(active)
      ){
        e.preventDefault();
        e.stopImmediatePropagation();
        return;
      }

      if(active && 'value' in active){
        setTimeout(()=>maybeOpenFromText(active.value),0);
      }
    },true);
  }

  /* AURA P0.6.6.1.3 POI CORE-INTEGRATED RUNTIME */
  /* AURA P0.6.6.1.5 OVERPASS RELIABILITY + POI STATE POLISH */
  /* AURA P0.6.6.1.6 SEGMENTED OVERPASS CORRIDOR */
  /* AURA P0.6.6.1.7 POI FAST CATEGORY PIPELINE */
  /* AURA P0.6.6.1.8 POI COMPACT PANEL LAYOUT */
  const AURA_POI_CLIENT_TIMEOUT_MS=32000;
  const AURA_POI_CATEGORIES=[
    {id:'parking',label:'PARKING',glyph:'P'},
    {id:'fuel',label:'CARBURANT',glyph:'F'},
    {id:'charging',label:'RECHARGE',glyph:'EV'},
    {id:'restaurant',label:'RESTAURANTS',glyph:'R'},
    {id:'hotel',label:'HÔTELS',glyph:'H'},
    {id:'services',label:'SERVICES',glyph:'+'}
  ];
  let auraPoiPanel=null,auraPoiMarkerLayer=null,auraPoiOpen=false,auraPoiBusy=false;
  let auraPoiCategory='fuel',auraPoiRadiusM=2000,auraPoiResults=[],auraPoiSelectedId='';
  let auraPoiPositionTimer=null;

  function auraPoiMeta(id){return AURA_POI_CATEGORIES.find(x=>x.id===id)||AURA_POI_CATEGORIES[0];}
  function auraPoiEsc(s){return String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));}
  function auraPoiNorm(s){return String(s??'').replace(/\s+/g,' ').trim();}
  function auraPoiDistance(m){const v=Math.max(0,Number(m)||0);return v<1000?`${Math.round(v)} m`:`${(v/1000).toFixed(v<10000?1:0).replace('.',',')} km`;}

  function auraPoiSampleGeometry(points,maxPoints=28){
    const clean=Array.isArray(points)?points.filter(p=>Array.isArray(p)&&p.length>=2&&finite(p[0])&&finite(p[1])).map(p=>[Number(p[0]),Number(p[1])]):[];
    if(clean.length<=maxPoints)return clean;
    const out=[];
    for(let i=0;i<maxPoints;i++){
      const idx=Math.round(i*(clean.length-1)/(maxPoints-1));
      const p=clean[idx];
      if(!out.length||out[out.length-1][0]!==p[0]||out[out.length-1][1]!==p[1])out.push(p);
    }
    return out;
  }

  function auraPoiSearchGeometry(){
    const geometry=auraPoiSampleGeometry(routeGeometry||[]);
    if(geometry.length>=2)return {geometry,mode:'route'};
    if(destination&&finite(destination.lon)&&finite(destination.lat))return {geometry:[[Number(destination.lon),Number(destination.lat)]],mode:'destination'};
    if(finite(centerLon)&&finite(centerLat))return {geometry:[[Number(centerLon),Number(centerLat)]],mode:'map'};
    return {geometry:[],mode:'none'};
  }

  function auraPoiSetState(text,error=false){
    const el=auraPoiPanel?.querySelector('#auraPoiState');
    if(el){el.textContent=String(text||'PRÊT');el.classList.toggle('error',!!error);}
  }

  function auraPoiRenderResults(){
    const box=auraPoiPanel?.querySelector('#auraPoiResults');
    if(!box)return;
    if(!auraPoiResults.length){
      box.innerHTML='<div class="aura-poi-empty">Aucun lieu affiche. Choisissez une categorie puis lancez la recherche.</div>';
      return;
    }
    box.innerHTML=auraPoiResults.map((item,i)=>{
      const id=String(item.id||`${item.osm_type||'poi'}-${item.osm_id||i}`);
      const meta=auraPoiMeta(item.category||auraPoiCategory);
      const parts=[];
      if(finite(item.route_offset_m)&&Number(item.route_offset_m)>150)parts.push(`A ${auraPoiDistance(item.route_offset_m)} DU DEPART`);
      if(finite(item.distance_to_route_m))parts.push(`${auraPoiDistance(item.distance_to_route_m)} DU TRAJET`);
      const secondary=[auraPoiNorm(item.address),auraPoiNorm(item.opening_hours)].filter(Boolean).slice(0,2).join(' · ');
      return `<button type="button" class="aura-poi-result ${auraPoiSelectedId===id?'selected':''}" data-poi-id="${auraPoiEsc(id)}">
        <span class="aura-poi-result-icon" data-category="${auraPoiEsc(meta.id)}">${auraPoiEsc(meta.glyph)}</span>
        <span class="aura-poi-result-copy"><b>${auraPoiEsc(item.name||meta.label)}</b><small>${auraPoiEsc(parts.join(' · ')||meta.label)}</small>${secondary?`<em>${auraPoiEsc(secondary)}</em>`:''}</span><i>VOIR</i>
      </button>`;
    }).join('');
    box.querySelectorAll('[data-poi-id]').forEach(btn=>btn.addEventListener('click',()=>auraPoiSelect(btn.dataset.poiId,true)));
  }

  function auraPoiUpdateMarkers(){
    if(!auraPoiMarkerLayer)return;
    const vp=viewport();
    if(!vp||vp.w<20||vp.h<20)return;
    auraPoiMarkerLayer.querySelectorAll('[data-poi-id]').forEach(marker=>{
      const item=auraPoiResults.find((x,i)=>String(x.id||`${x.osm_type||'poi'}-${x.osm_id||i}`)===marker.dataset.poiId);
      if(!item||!finite(item.lat)||!finite(item.lon)){marker.hidden=true;return;}
      const p=project(Number(item.lat),Number(item.lon),vp);
      if(!p||!finite(p[0])||!finite(p[1])||p[0]<-48||p[0]>vp.w+48||p[1]<-48||p[1]>vp.h+48){marker.hidden=true;return;}
      marker.hidden=false;marker.style.left=`${Number(p[0]).toFixed(1)}px`;marker.style.top=`${Number(p[1]).toFixed(1)}px`;
      marker.classList.toggle('selected',marker.dataset.poiId===auraPoiSelectedId);
    });
  }

  function auraPoiCreateMarkers(){
    if(!auraPoiMarkerLayer)return;
    auraPoiMarkerLayer.replaceChildren();
    auraPoiResults.forEach((item,i)=>{
      if(!finite(item.lat)||!finite(item.lon))return;
      const id=String(item.id||`${item.osm_type||'poi'}-${item.osm_id||i}`),meta=auraPoiMeta(item.category||auraPoiCategory);
      const btn=document.createElement('button');btn.type='button';btn.className='aura-poi-marker';btn.dataset.poiId=id;btn.dataset.category=meta.id;btn.title=auraPoiNorm(item.name||meta.label);btn.innerHTML=`<span>${auraPoiEsc(meta.glyph)}</span>`;
      btn.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();auraPoiSelect(id,false);});
      auraPoiMarkerLayer.appendChild(btn);
    });
    auraPoiUpdateMarkers();
  }

  function auraPoiSelect(id,center=false){
    auraPoiSelectedId=String(id||'');auraPoiRenderResults();auraPoiUpdateMarkers();
    const item=auraPoiResults.find((x,i)=>String(x.id||`${x.osm_type||'poi'}-${x.osm_id||i}`)===auraPoiSelectedId);
    if(!item)return;
    auraPoiSetState(`${auraPoiNorm(item.name||'LIEU')} · SELECTIONNE`);
    if(center&&finite(item.lat)&&finite(item.lon)){
      centerLat=Number(item.lat);centerLon=Number(item.lon);zoom=clamp(Math.max(14,Math.min(16,Number(zoom)||14)),MIN_Z,MAX_Z);scheduleRender();
    }
  }

  function auraPoiClear(){
    auraPoiResults=[];auraPoiSelectedId='';auraPoiMarkerLayer?.replaceChildren();auraPoiRenderResults();auraPoiSetState('MARQUEURS EFFACES');
  }

  function auraPoiResetForSearch(message='RECHERCHE EN COURS...'){
    auraPoiResults=[];auraPoiSelectedId='';
    auraPoiMarkerLayer?.replaceChildren();
    const box=auraPoiPanel?.querySelector('#auraPoiResults');
    if(box)box.innerHTML=`<div class="aura-poi-empty">${auraPoiEsc(message)}</div>`;
  }

  async function auraPoiSearch(){
    if(auraPoiBusy)return;
    const geo=auraPoiSearchGeometry();
    if(!geo.geometry.length){auraPoiSetState('AUCUNE POSITION OU ROUTE DISPONIBLE',true);return;}
    auraPoiBusy=true;
    const btn=auraPoiPanel?.querySelector('#auraPoiSearch');if(btn)btn.disabled=true;
    const lockedControls=Array.from(auraPoiPanel?.querySelectorAll('[data-poi-category],#auraPoiRadius')||[]);lockedControls.forEach(x=>x.disabled=true);
    auraPoiResetForSearch(`Recherche ${auraPoiMeta(auraPoiCategory).label.toLowerCase()} en cours...`);
    auraPoiSetState('RECHERCHE PROGRESSIVE OSM / OVERPASS...');
    const controller=new AbortController();
    const timeout=setTimeout(()=>controller.abort(),AURA_POI_CLIENT_TIMEOUT_MS);
    try{
      const r=await fetch(`/api/nav/pois?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify({category:auraPoiCategory,radius_m:auraPoiRadiusM,geometry:geo.geometry}),signal:controller.signal});
      let data=null;try{data=await r.json();}catch(_){ }
      if(!r.ok||!data?.ok)throw new Error(data?.error||`http_${r.status}`);
      auraPoiResults=Array.isArray(data.places)?data.places:[];auraPoiSelectedId='';auraPoiRenderResults();auraPoiCreateMarkers();
      const source=String(data.cache_state||'').includes('cache')?'CACHE OSM':'OSM / OVERPASS';
      const mode=geo.mode==='route'?'SUR LE TRAJET':geo.mode==='destination'?'AUTOUR DE LA DESTINATION':'AUTOUR DE LA CARTE';
      const partial=data?.partial?' · PARTIEL':'';const seg=(data?.segments_total&&data?.segments_checked)?` · ${data.segments_checked}/${data.segments_total} ZONES`:'';auraPoiSetState(`${auraPoiResults.length} LIEU${auraPoiResults.length>1?'X':''} · ${mode} · ${source}${seg}${partial}`);
    }catch(e){
      auraPoiResults=[];auraPoiSelectedId='';auraPoiMarkerLayer?.replaceChildren();auraPoiRenderResults();
      if(e?.name==='AbortError'){
        auraPoiSetState('DELAI OVERPASS DEPASSE · REESSAYER',true);
      }else{
        const code=String(e?.message||e);const friendly={invalid_poi_request:'REQUETE POI INVALIDE',poi_unavailable:'OVERPASS TEMPORAIREMENT INDISPONIBLE · REESSAYER',poi_no_geometry:'AUCUNE ROUTE OU POSITION',poi_invalid_category:'CATEGORIE INVALIDE'}[code]||'RECHERCHE POI INDISPONIBLE';
        auraPoiSetState(friendly,true);
      }
    }finally{
      clearTimeout(timeout);auraPoiBusy=false;if(btn)btn.disabled=false;lockedControls.forEach(x=>x.disabled=false);
    }
  }

  function auraPoiEnsurePanel(){
    if(!root||!map)return false;
    const sidebar=root.querySelector('.aura-nav-sidebar');if(!sidebar)return false;
    auraPoiMarkerLayer=root.querySelector('#auraPoiMarkerLayer');
    if(!auraPoiMarkerLayer){auraPoiMarkerLayer=document.createElement('div');auraPoiMarkerLayer.id='auraPoiMarkerLayer';auraPoiMarkerLayer.className='aura-poi-marker-layer';map.appendChild(auraPoiMarkerLayer);}
    auraPoiPanel=sidebar.querySelector('#auraPoiPlaces');
    if(!auraPoiPanel){auraPoiPanel=document.createElement('section');auraPoiPanel.id='auraPoiPlaces';auraPoiPanel.className='aura-poi-places';sidebar.appendChild(auraPoiPanel);}
    auraPoiPanel.dataset.auraPoiRuntime='core-integrated-p066118';
    if(auraPoiPanel.dataset.auraPoiBuilt118!=='1'){
      auraPoiPanel.dataset.auraPoiBuilt118='1';
      auraPoiPanel.innerHTML=`<header><div><span>MAPS DESKTOP</span><b>POI & PLACES</b></div><em>v1.0.0</em></header>
        <div class="aura-poi-categories" role="group" aria-label="Categorie de lieux">${AURA_POI_CATEGORIES.map(c=>`<button type="button" data-poi-category="${auraPoiEsc(c.id)}" class="${c.id===auraPoiCategory?'active':''}"><i>${auraPoiEsc(c.glyph)}</i><span>${auraPoiEsc(c.label)}</span></button>`).join('')}</div>
        <div class="aura-poi-tools"><label><span>RAYON AUTOUR DU TRAJET</span><select id="auraPoiRadius"><option value="1000">1 km</option><option value="2000" selected>2 km</option><option value="5000">5 km</option></select></label><button id="auraPoiSearch" type="button"><span>RECHERCHER</span><small>SUR LE TRAJET ACTIF</small></button></div>
        <div id="auraPoiResults" class="aura-poi-results"><div class="aura-poi-empty">Choisissez une categorie puis recherchez les lieux utiles le long du trajet.</div></div>
        <footer><span id="auraPoiState">PRET · CARBURANT · 2 KM</span><button id="auraPoiClear" type="button">EFFACER</button></footer>`;
      auraPoiPanel.querySelectorAll('[data-poi-category]').forEach(b=>b.addEventListener('click',()=>{auraPoiCategory=String(b.dataset.poiCategory||'fuel');auraPoiPanel.querySelectorAll('[data-poi-category]').forEach(x=>x.classList.toggle('active',x===b));auraPoiResults=[];auraPoiSelectedId='';auraPoiMarkerLayer?.replaceChildren();auraPoiRenderResults();auraPoiSetState(`PRET · ${auraPoiMeta(auraPoiCategory).label} · ${auraPoiRadiusM/1000} KM`);}));
      auraPoiPanel.querySelector('#auraPoiRadius')?.addEventListener('change',e=>{auraPoiRadiusM=Math.max(500,Math.min(5000,Number(e.target.value)||2000));auraPoiSetState(`PRET · ${auraPoiMeta(auraPoiCategory).label} · ${auraPoiRadiusM/1000} KM`);});
      auraPoiPanel.querySelector('#auraPoiSearch')?.addEventListener('click',auraPoiSearch);auraPoiPanel.querySelector('#auraPoiClear')?.addEventListener('click',auraPoiClear);
    }
    const trip=sidebar.querySelector('#auraTripPlanner');if(trip&&auraPoiPanel.nextElementSibling!==trip)trip.insertAdjacentElement('beforebegin',auraPoiPanel);
    if(!auraPoiPositionTimer)auraPoiPositionTimer=setInterval(()=>{if(!openState)return;if(navigationActive&&auraPoiOpen){auraPoiSetOpen(false);return;}auraPoiUpdateMarkers();},160);
    return true;
  }

  function auraPoiSetOpen(open){
    if(!auraPoiEnsurePanel())return;
    auraPoiOpen=!!open;root.classList.toggle('poi-mode',auraPoiOpen);auraPoiPanel.classList.toggle('open',auraPoiOpen);
    const poi=root.querySelector('.aura-nav-toolbar [data-nav-toolbar="poi"]');if(poi){poi.disabled=false;poi.removeAttribute('disabled');poi.classList.toggle('active',auraPoiOpen);poi.setAttribute('aria-pressed',auraPoiOpen?'true':'false');}
    const route=Array.from(root.querySelectorAll('.aura-nav-toolbar button')).find(b=>auraPoiNorm(b.textContent).toUpperCase()==='ITINERAIRE'||auraPoiNorm(b.textContent).toUpperCase()==='ITINÉRAIRE');if(route){route.classList.toggle('active',!auraPoiOpen);route.setAttribute('aria-pressed',auraPoiOpen?'false':'true');}
    if(auraPoiOpen){requestAnimationFrame(()=>{const sidebar=root.querySelector('.aura-nav-sidebar');if(sidebar&&auraPoiPanel){const y=Math.max(0,auraPoiPanel.offsetTop-8);try{sidebar.scrollTo({top:y,behavior:'smooth'});}catch(_){sidebar.scrollTop=y;}}});}
  }

  function auraPoiToggle(){auraPoiSetOpen(!auraPoiOpen);}

  function bindIntegratedPoiMode(){
    const poi=root?.querySelector('.aura-nav-toolbar [data-nav-toolbar="poi"]');
    if(poi){poi.disabled=false;poi.removeAttribute('disabled');poi.setAttribute('aria-disabled','false');if(poi.dataset.auraPoiCoreBound!=='1'){poi.dataset.auraPoiCoreBound='1';poi.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();auraPoiToggle();});}}
    const route=Array.from(root?.querySelectorAll('.aura-nav-toolbar button')||[]).find(b=>{const t=auraPoiNorm(b.textContent).toUpperCase();return t==='ITINERAIRE'||t==='ITINÉRAIRE';});
    if(route&&route.dataset.auraPoiCoreBound!=='1'){route.dataset.auraPoiCoreBound='1';route.addEventListener('click',()=>{if(auraPoiOpen)auraPoiSetOpen(false);});}
    auraPoiEnsurePanel();
  }

  /* AURA P0.6.6.2 TRAFFIC + WEATHER CONTEXT */
  const AURA_ROUTE_CONTEXT_TIMEOUT_MS=18000;
  let auraContextPanel=null,auraContextMarkerLayer=null,auraContextOpen=false,auraContextBusy=false;
  let auraContextData=null,auraContextAbort=null,auraContextMarkerTimer=null,auraContextFingerprint='';

  const auraContextNorm=s=>String(s??'').replace(/\s+/g,' ').trim();
  const auraContextEsc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const auraContextClock=ts=>{
    const d=new Date(Number(ts||0)*1000);
    if(!Number.isFinite(d.getTime()))return '—';
    return new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit'}).format(d);
  };
  const auraContextTemp=v=>finite(v)?`${Math.round(Number(v))}°`:'—';
  const auraContextKm=m=>{
    const km=Math.max(0,Number(m)||0)/1000;
    return km<10?`${km.toFixed(1).replace('.',',')} km`:`${Math.round(km)} km`;
  };
  const auraContextVisibility=m=>{
    if(!finite(m))return '—';
    const v=Math.max(0,Number(m));
    return v<1000?`${Math.round(v)} m`:`${(v/1000).toFixed(v<10000?1:0).replace('.',',')} km`;
  };
  function auraContextWmo(code){
    const c=Number(code);
    if(c===0)return 'CIEL DÉGAGÉ';
    if(c===1)return 'PEU NUAGEUX';
    if(c===2)return 'VARIABLE';
    if(c===3)return 'NUAGEUX';
    if(c===45||c===48)return 'BROUILLARD';
    if(c>=51&&c<=57)return 'BRUINE';
    if(c>=61&&c<=67)return 'PLUIE';
    if(c>=71&&c<=77)return 'NEIGE';
    if(c>=80&&c<=82)return 'AVERSES';
    if(c>=85&&c<=86)return 'AVERSES DE NEIGE';
    if(c>=95)return 'ORAGES';
    return 'CONDITIONS VARIABLES';
  }
  function auraContextLevelLabel(level){
    return ({normal:'CONDITIONS NORMALES',watch:'CONDITIONS À SURVEILLER',difficult:'CONDITIONS DIFFICILES'})[String(level||'normal')]||'CONDITIONS NORMALES';
  }
  function auraContextLevelClass(level){
    return ['normal','watch','difficult'].includes(String(level))?String(level):'normal';
  }
  function auraContextDepartureTs(){
    const v=root?.querySelector('#auraTripDeparture')?.value;
    const d=v?new Date(v):new Date();
    return Math.floor((Number.isFinite(d.getTime())?d:new Date()).getTime()/1000);
  }
  function auraContextRouteFingerprint(){
    const g=Array.isArray(routeGeometry)?routeGeometry:[];
    const first=g[0]||[],last=g[g.length-1]||[];
    return [
      Math.round(Number(routeSummary?.distance)||0),Math.round(Number(routeSummary?.duration)||0),
      Number(first[0]||0).toFixed(4),Number(first[1]||0).toFixed(4),
      Number(last[0]||0).toFixed(4),Number(last[1]||0).toFixed(4),
      Math.round(auraContextDepartureTs()/900)
    ].join('|');
  }
  function auraContextSampleGeometry(points,maxPoints=40){
    const clean=Array.isArray(points)?points.filter(p=>Array.isArray(p)&&p.length>=2&&finite(p[0])&&finite(p[1])).map(p=>[Number(p[0]),Number(p[1])]):[];
    if(clean.length<=maxPoints)return clean;
    const out=[];
    for(let i=0;i<maxPoints;i++){
      const idx=Math.round(i*(clean.length-1)/(maxPoints-1)),p=clean[idx];
      if(!out.length||out[out.length-1][0]!==p[0]||out[out.length-1][1]!==p[1])out.push(p);
    }
    return out;
  }
  function auraContextSetState(text,error=false){
    const el=auraContextPanel?.querySelector('#auraRouteContextState');
    if(el){el.textContent=String(text||'PRÊT');el.classList.toggle('error',!!error);}
  }
  function auraContextRender(){
    if(!auraContextPanel)return;
    const summary=auraContextPanel.querySelector('#auraRouteContextSummary');
    const timeline=auraContextPanel.querySelector('#auraRouteWeatherTimeline');
    const traffic=auraContextPanel.querySelector('#auraRouteTrafficStatus');
    const weather=auraContextPanel.querySelector('#auraRouteWeatherStatus');
    if(!summary||!timeline||!traffic||!weather)return;
    if(!auraContextData){
      traffic.innerHTML='<span>TRAFIC TEMPS RÉEL</span><b>NON CONNECTÉ</b><small>Durée OSRM · hors trafic live</small>';
      weather.innerHTML='<span>MÉTÉO TRAJET</span><b>EN ATTENTE</b><small>Prévision selon l’heure de passage</small>';
      summary.innerHTML='<strong>ANALYSE DU TRAJET</strong><span>Calculez un itinéraire puis actualisez le contexte.</span>';
      timeline.innerHTML='<div class="aura-route-context-empty">Aucune prévision de trajet chargée.</div>';
      return;
    }
    const d=auraContextData;
    const live=!!d?.traffic?.live;
    traffic.innerHTML=`<span>TRAFIC TEMPS RÉEL</span><b class="${live?'live':'offline'}">${live?'CONNECTÉ':'NON CONNECTÉ'}</b><small>${auraContextEsc(d?.traffic?.message||'Durée OSRM · hors trafic live')}</small>`;
    const samples=Array.isArray(d.weather_samples)?d.weather_samples:[];
    weather.innerHTML=`<span>MÉTÉO TRAJET</span><b>${samples.length?`${samples.length} POINT${samples.length>1?'S':''}`:'INDISPONIBLE'}</b><small>${samples.length?'Open-Meteo · heure de passage':'Aucune prévision exploitable'}</small>`;
    const risk=d.risk||{};const level=auraContextLevelClass(risk.level);
    const reasons=Array.isArray(risk.reasons)?risk.reasons:[];
    summary.innerHTML=`<strong class="${level}">${auraContextEsc(auraContextLevelLabel(level))}</strong><span>${auraContextEsc(reasons.length?reasons.join(' · '):'Aucun signal météo notable sur les points analysés.')}</span><small>Indicateur local AURA · pas une vigilance officielle.</small>`;
    if(!samples.length){timeline.innerHTML='<div class="aura-route-context-empty">Prévision hors horizon ou source météo indisponible.</div>';return;}
    timeline.innerHTML=samples.map((s,i)=>{
      const pos=Number(s.fraction)||0;
      const label=i===0?'DÉPART':i===samples.length-1?'ARRIVÉE':`${Math.round(pos*100)}% TRAJET`;
      const parts=[`PLUIE ${finite(s.precipitation_probability)?Math.round(Number(s.precipitation_probability))+'%':'—'}`,`VENT ${finite(s.wind_speed)?Math.round(Number(s.wind_speed))+' km/h':'—'}`];
      if(finite(s.wind_gusts)&&Number(s.wind_gusts)>=45)parts.push(`RAFALES ${Math.round(Number(s.wind_gusts))}`);
      if(finite(s.visibility)&&Number(s.visibility)<8000)parts.push(`VISI. ${auraContextVisibility(s.visibility)}`);
      return `<article class="aura-route-weather-card ${auraContextLevelClass(s.risk_level)}">
        <header><span>${label}</span><b>${auraContextClock(s.eta_ts)}</b></header>
        <div><strong>${auraContextTemp(s.temperature)}</strong><span>${auraContextEsc(auraContextWmo(s.weather_code))}</span></div>
        <footer>${auraContextEsc(parts.join(' · '))}</footer>
      </article>`;
    }).join('');
  }
  function auraContextUpdateMarkers(){
    if(!auraContextMarkerLayer||!auraContextOpen)return;
    const samples=Array.isArray(auraContextData?.weather_samples)?auraContextData.weather_samples:[];
    const vp=viewport();if(!vp||vp.w<20||vp.h<20)return;
    auraContextMarkerLayer.querySelectorAll('[data-context-index]').forEach(el=>{
      const s=samples[Number(el.dataset.contextIndex)];
      if(!s||!finite(s.lat)||!finite(s.lon)){el.hidden=true;return;}
      const p=project(Number(s.lat),Number(s.lon),vp);
      if(!p||!finite(p[0])||!finite(p[1])||p[0]<-50||p[0]>vp.w+50||p[1]<-50||p[1]>vp.h+50){el.hidden=true;return;}
      el.hidden=false;el.style.left=`${p[0].toFixed(1)}px`;el.style.top=`${p[1].toFixed(1)}px`;
    });
  }
  function auraContextCreateMarkers(){
    if(!auraContextMarkerLayer)return;
    auraContextMarkerLayer.replaceChildren();
    const samples=Array.isArray(auraContextData?.weather_samples)?auraContextData.weather_samples:[];
    samples.forEach((s,i)=>{
      const el=document.createElement('div');el.className=`aura-route-weather-marker ${auraContextLevelClass(s.risk_level)}`;el.dataset.contextIndex=String(i);el.innerHTML=`<b>${auraContextEsc(auraContextTemp(s.temperature))}</b><span>${auraContextClock(s.eta_ts)}</span>`;auraContextMarkerLayer.appendChild(el);
    });
    auraContextUpdateMarkers();
  }
  async function auraContextRefresh(force=false){
    if(auraContextBusy)return;
    if(!routeSummary||!Array.isArray(routeGeometry)||routeGeometry.length<2){auraContextData=null;auraContextRender();auraContextSetState('ITINÉRAIRE REQUIS',true);return;}
    const fp=auraContextRouteFingerprint();
    if(!force&&auraContextData&&auraContextFingerprint===fp){auraContextRender();auraContextCreateMarkers();return;}
    auraContextBusy=true;auraContextAbort?.abort?.();auraContextAbort=new AbortController();
    const btn=auraContextPanel?.querySelector('#auraRouteContextRefresh');if(btn)btn.disabled=true;
    auraContextSetState('ANALYSE MÉTÉO DU TRAJET…');
    const timeout=setTimeout(()=>auraContextAbort?.abort?.(),AURA_ROUTE_CONTEXT_TIMEOUT_MS);
    try{
      const geometry=auraContextSampleGeometry(routeGeometry,40);
      const body={geometry,duration_s:Number(routeSummary.duration)||0,distance_m:Number(routeSummary.distance)||0,departure_ts:auraContextDepartureTs()};
      const r=await fetch(`/api/nav/context?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:auraContextAbort.signal});
      let data=null;try{data=await r.json();}catch(_){ }
      if(!r.ok||!data?.ok)throw new Error(data?.error||`http_${r.status}`);
      auraContextData=data;auraContextFingerprint=fp;auraContextRender();auraContextCreateMarkers();
      const cache=String(data.cache_state||'').includes('cache')?' · CACHE':'';
      auraContextSetState(`${(data.weather_samples||[]).length} POINTS MÉTÉO · OPEN-METEO${cache}`);
    }catch(e){
      auraContextData=null;auraContextRender();auraContextMarkerLayer?.replaceChildren();
      const code=String(e?.name==='AbortError'?'timeout':e?.message||e);
      const friendly=code==='timeout'?'DÉLAI MÉTÉO DÉPASSÉ · RÉESSAYER':code==='weather_horizon'?'DÉPART HORS HORIZON MÉTÉO':'CONTEXTE MÉTÉO INDISPONIBLE';
      auraContextSetState(friendly,true);
    }finally{clearTimeout(timeout);auraContextBusy=false;if(btn)btn.disabled=false;}
  }
  function auraContextEnsurePanel(){
    if(!root||!map)return false;
    const sidebar=root.querySelector('.aura-nav-sidebar');if(!sidebar)return false;
    auraContextMarkerLayer=map.querySelector('#auraRouteContextMarkerLayer');
    if(!auraContextMarkerLayer){auraContextMarkerLayer=document.createElement('div');auraContextMarkerLayer.id='auraRouteContextMarkerLayer';auraContextMarkerLayer.className='aura-route-context-marker-layer';map.appendChild(auraContextMarkerLayer);}
    auraContextPanel=sidebar.querySelector('#auraRouteContext');
    if(!auraContextPanel){auraContextPanel=document.createElement('section');auraContextPanel.id='auraRouteContext';auraContextPanel.className='aura-route-context';sidebar.appendChild(auraContextPanel);}
    if(auraContextPanel.dataset.auraContextBuilt!=='p0662'){
      auraContextPanel.dataset.auraContextBuilt='p0662';
      auraContextPanel.innerHTML=`<header><div><span>MAPS DESKTOP</span><b>TRAFIC + MÉTÉO</b></div><em>v1.0.0</em></header>
        <div class="aura-route-context-status-grid"><div id="auraRouteTrafficStatus"></div><div id="auraRouteWeatherStatus"></div></div>
        <div id="auraRouteContextSummary" class="aura-route-context-summary"></div>
        <div id="auraRouteWeatherTimeline" class="aura-route-weather-timeline"></div>
        <button id="auraRouteContextRefresh" class="aura-route-context-refresh" type="button"><span>ACTUALISER LE CONTEXTE</span><small>MÉTÉO SELON L’HEURE DE PASSAGE</small></button>
        <footer><span id="auraRouteContextState">PRÊT</span><small>Trafic live non connecté</small></footer>`;
      auraContextPanel.querySelector('#auraRouteContextRefresh')?.addEventListener('click',()=>auraContextRefresh(true));
      auraContextRender();
    }
    const trip=sidebar.querySelector('#auraTripPlanner');if(trip&&auraContextPanel.nextElementSibling!==trip)trip.insertAdjacentElement('beforebegin',auraContextPanel);
    if(!auraContextMarkerTimer)auraContextMarkerTimer=setInterval(()=>{if(!openState)return;if(navigationActive&&auraContextOpen){auraContextSetOpen(false);return;}auraContextUpdateMarkers();},160);
    return true;
  }
  function auraContextSetOpen(open){
    if(!auraContextEnsurePanel())return;
    auraContextOpen=!!open;
    if(auraContextOpen&&auraPoiOpen)auraPoiSetOpen(false);
    root.classList.toggle('traffic-weather-mode',auraContextOpen);auraContextPanel.classList.toggle('open',auraContextOpen);
    const traffic=root.querySelector('.aura-nav-toolbar [data-nav-toolbar="traffic"]');if(traffic){traffic.disabled=false;traffic.removeAttribute('disabled');traffic.classList.toggle('active',auraContextOpen);traffic.setAttribute('aria-pressed',auraContextOpen?'true':'false');}
    const route=Array.from(root.querySelectorAll('.aura-nav-toolbar button')).find(b=>{const t=auraContextNorm(b.textContent).toUpperCase();return t==='ITINERAIRE'||t==='ITINÉRAIRE';});if(route){route.classList.toggle('active',!auraContextOpen&&!auraPoiOpen);route.setAttribute('aria-pressed',auraContextOpen||auraPoiOpen?'false':'true');}
    if(auraContextOpen){requestAnimationFrame(()=>{const sidebar=root.querySelector('.aura-nav-sidebar');if(sidebar&&auraContextPanel){const y=Math.max(0,auraContextPanel.offsetTop-8);try{sidebar.scrollTo({top:y,behavior:'smooth'});}catch(_){sidebar.scrollTop=y;}}});auraContextRefresh(false);}
    else auraContextMarkerLayer?.replaceChildren();
  }
  function auraContextToggle(){auraContextSetOpen(!auraContextOpen);}
  function bindTrafficWeatherMode(){
    let traffic=root?.querySelector('.aura-nav-toolbar [data-nav-toolbar="traffic"]');
    if(!traffic){traffic=Array.from(root?.querySelectorAll('.aura-nav-toolbar button')||[]).find(b=>auraContextNorm(b.textContent).toUpperCase()==='TRAFIC');if(traffic)traffic.dataset.navToolbar='traffic';}
    if(traffic){traffic.disabled=false;traffic.removeAttribute('disabled');traffic.setAttribute('aria-disabled','false');if(traffic.dataset.auraContextBound!=='1'){traffic.dataset.auraContextBound='1';traffic.addEventListener('click',ev=>{ev.preventDefault();ev.stopPropagation();auraContextToggle();});}}
    const poi=root?.querySelector('.aura-nav-toolbar [data-nav-toolbar="poi"]');if(poi&&poi.dataset.auraContextBound!=='1'){poi.dataset.auraContextBound='1';poi.addEventListener('click',()=>{if(auraContextOpen)auraContextSetOpen(false);},true);}
    const route=Array.from(root?.querySelectorAll('.aura-nav-toolbar button')||[]).find(b=>{const t=auraContextNorm(b.textContent).toUpperCase();return t==='ITINERAIRE'||t==='ITINÉRAIRE';});if(route&&route.dataset.auraContextBound!=='1'){route.dataset.auraContextBound='1';route.addEventListener('click',()=>{if(auraContextOpen)auraContextSetOpen(false);});}
    auraContextEnsurePanel();
  }

  /* AURA P0.6.6.3 SEND TO PHONE */
  const AURA_SEND_PHONE_TIMEOUT_MS=7000;
  let auraSendPhonePanel=null,auraSendPhoneOpen=false,auraSendPhoneBusy=false,auraSendPhoneProvider='google';
  let auraSendPhoneLast=null,auraSendPhoneFingerprint='';

  const auraSendNorm=s=>String(s??'').replace(/\s+/g,' ').trim();
  const auraSendEsc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  function auraSendHasPoint(p){return !!p&&finite(p.lat)&&finite(p.lon);}
  function auraSendCurrentLocationDefault(){
    const label=auraSendNorm(origin?.label).toLowerCase();
    return label==='position actuelle'||label.includes('position actuelle');
  }
  function auraSendFingerprint(){
    const o=auraSendHasPoint(origin)?origin:(Array.isArray(routeGeometry)&&routeGeometry.length?{lon:routeGeometry[0][0],lat:routeGeometry[0][1]}:null);
    const d=auraSendHasPoint(destination)?destination:(Array.isArray(routeGeometry)&&routeGeometry.length?{lon:routeGeometry.at(-1)?.[0],lat:routeGeometry.at(-1)?.[1]}:null);
    return [auraSendPhoneProvider,Number(o?.lat||0).toFixed(5),Number(o?.lon||0).toFixed(5),Number(d?.lat||0).toFixed(5),Number(d?.lon||0).toFixed(5),Math.round(Number(routeSummary?.distance)||0),auraSendPhonePanel?.querySelector('#auraSendUsePhoneLocation')?.checked?'phone':'fixed'].join('|');
  }
  function auraSendRoutePoints(){
    const first=Array.isArray(routeGeometry)&&routeGeometry.length?routeGeometry[0]:null;
    const last=Array.isArray(routeGeometry)&&routeGeometry.length?routeGeometry[routeGeometry.length-1]:null;
    const o=auraSendHasPoint(origin)?{lat:Number(origin.lat),lon:Number(origin.lon),label:auraSendNorm(origin.label)||'Départ'}:(first&&finite(first[0])&&finite(first[1])?{lat:Number(first[1]),lon:Number(first[0]),label:'Départ'}:null);
    const d=auraSendHasPoint(destination)?{lat:Number(destination.lat),lon:Number(destination.lon),label:auraSendNorm(destination.shortLabel||destination.label)||'Destination'}:(last&&finite(last[0])&&finite(last[1])?{lat:Number(last[1]),lon:Number(last[0]),label:'Destination'}:null);
    return {origin:o,destination:d};
  }
  function auraSendSetState(text,error=false){
    const el=auraSendPhonePanel?.querySelector('#auraSendPhoneState');if(!el)return;el.textContent=String(text||'PRÊT');el.classList.toggle('error',!!error);
  }
  function auraSendDrawQr(qr){
    const canvas=auraSendPhonePanel?.querySelector('#auraSendQr');if(!canvas)return false;
    const size=Number(qr?.size)||0,rows=Array.isArray(qr?.rows)?qr.rows:[];
    if(size<21||rows.length!==size)return false;
    const scale=Math.max(3,Math.floor(180/size));canvas.width=size*scale;canvas.height=size*scale;
    const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)return false;
    ctx.imageSmoothingEnabled=false;ctx.fillStyle='#ffffff';ctx.fillRect(0,0,canvas.width,canvas.height);ctx.fillStyle='#071018';
    rows.forEach((row,y)=>{if(typeof row!=='string'||row.length!==size)return;for(let x=0;x<size;x++)if(row[x]==='1')ctx.fillRect(x*scale,y*scale,scale,scale);});
    return true;
  }
  function auraSendRenderMeta(data){
    const meta=auraSendPhonePanel?.querySelector('#auraSendPhoneMeta');if(!meta)return;
    const km=Math.max(0,Number(routeSummary?.distance)||0)/1000;const min=Math.max(0,Math.round((Number(routeSummary?.duration)||0)/60));
    const provider=data?.provider==='apple'?'APPLE PLANS':'GOOGLE MAPS';
    meta.innerHTML=`<div><span>DESTINATION</span><b>${auraSendEsc(destination?.shortLabel||destination?.label||'Destination')}</b></div><div><span>TRAJET AURA</span><b>${km>=10?Math.round(km):km.toFixed(1).replace('.',',')} km · ${min} min</b></div><div><span>OUVERTURE MOBILE</span><b>${provider}</b></div>`;
  }
  async function auraSendCopy(){
    const url=String(auraSendPhoneLast?.url||'');if(!url){auraSendSetState('GÉNÉREZ D’ABORD LE QR',true);return;}
    let ok=false;try{await navigator.clipboard.writeText(url);ok=true;}catch(_){try{const t=document.createElement('textarea');t.value=url;t.setAttribute('readonly','');t.style.position='fixed';t.style.opacity='0';document.body.appendChild(t);t.select();ok=document.execCommand('copy');t.remove();}catch(__){}}
    auraSendSetState(ok?'LIEN COPIÉ':'COPIE IMPOSSIBLE',!ok);
  }
  async function auraSendGenerate(force=false){
    if(auraSendPhoneBusy)return;
    const points=auraSendRoutePoints();
    if(!routeSummary||!points.origin||!points.destination){auraSendPhoneLast=null;auraSendPhonePanel?.classList.remove('ready');auraSendSetState('ITINÉRAIRE REQUIS',true);return;}
    const fp=auraSendFingerprint();if(!force&&auraSendPhoneLast&&auraSendPhoneFingerprint===fp){auraSendDrawQr(auraSendPhoneLast.qr);auraSendRenderMeta(auraSendPhoneLast);return;}
    auraSendPhoneBusy=true;auraSendSetState('GÉNÉRATION LOCALE DU QR…');
    const gen=auraSendPhonePanel?.querySelector('#auraSendGenerate');if(gen)gen.disabled=true;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),AURA_SEND_PHONE_TIMEOUT_MS);
    try{
      const usePhone=!!auraSendPhonePanel?.querySelector('#auraSendUsePhoneLocation')?.checked;
      const body={provider:auraSendPhoneProvider,origin:points.origin,destination:points.destination,use_phone_location:usePhone};
      const r=await fetch(`/api/nav/share?token=${encodeURIComponent(token)}`,{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
      let data=null;try{data=await r.json();}catch(_){ }
      if(!r.ok||!data?.ok)throw new Error(data?.error||`http_${r.status}`);
      if(!auraSendDrawQr(data.qr))throw new Error('qr_render');
      auraSendPhoneLast=data;auraSendPhoneFingerprint=fp;auraSendRenderMeta(data);auraSendPhonePanel?.classList.add('ready');
      auraSendSetState(`${data.provider==='apple'?'APPLE PLANS':'GOOGLE MAPS'} · QR PRÊT`);
    }catch(e){auraSendPhoneLast=null;auraSendPhonePanel?.classList.remove('ready');auraSendSetState(e?.name==='AbortError'?'DÉLAI QR DÉPASSÉ':'QR INDISPONIBLE',true);}
    finally{clearTimeout(timer);auraSendPhoneBusy=false;if(gen)gen.disabled=false;}
  }
  function auraSendSetProvider(provider){
    auraSendPhoneProvider=provider==='apple'?'apple':'google';
    auraSendPhonePanel?.querySelectorAll('[data-send-provider]').forEach(b=>b.classList.toggle('active',b.dataset.sendProvider===auraSendPhoneProvider));
    auraSendPhoneLast=null;auraSendPhoneFingerprint='';if(auraSendPhoneOpen)auraSendGenerate(true);
  }
  function auraSendEnsurePanel(){
    if(!root)return false;const sidebar=root.querySelector('.aura-nav-sidebar');if(!sidebar)return false;
    auraSendPhonePanel=sidebar.querySelector('#auraSendPhone');
    if(!auraSendPhonePanel){auraSendPhonePanel=document.createElement('section');auraSendPhonePanel.id='auraSendPhone';auraSendPhonePanel.className='aura-send-phone';}
    if(auraSendPhonePanel.dataset.auraSendBuilt!=='p0663'){
      auraSendPhonePanel.dataset.auraSendBuilt='p0663';
      auraSendPhonePanel.innerHTML=`<button id="auraSendPhoneToggle" class="aura-send-phone-launch" type="button"><span>ENVOYER AU TÉLÉPHONE</span><small>QR · GOOGLE MAPS · APPLE PLANS</small><i>›</i></button>
        <div class="aura-send-phone-body"><header><div><span>MAPS DESKTOP</span><b>SEND TO PHONE</b></div><em>v1.0.0</em></header>
        <div class="aura-send-provider" role="group" aria-label="Application mobile"><button class="active" data-send-provider="google" type="button">GOOGLE MAPS</button><button data-send-provider="apple" type="button">APPLE PLANS</button></div>
        <label class="aura-send-origin"><input id="auraSendUsePhoneLocation" type="checkbox"><span><b>UTILISER LA POSITION DU TÉLÉPHONE AU DÉPART</b><small>Recommandé si le départ AURA est « Position actuelle ».</small></span></label>
        <div class="aura-send-qr-wrap"><canvas id="auraSendQr" aria-label="QR code du trajet"></canvas><div id="auraSendPhoneMeta" class="aura-send-meta"><div><span>TRAJET</span><b>En attente</b></div></div></div>
        <div class="aura-send-actions"><button id="auraSendGenerate" type="button"><span>GÉNÉRER LE QR</span><small>100 % LOCAL</small></button><button id="auraSendCopy" type="button"><span>COPIER LE LIEN</span><small>POUR MESSAGE / MAIL</small></button></div>
        <div class="aura-send-notice">Le fournisseur mobile recalcule l’itinéraire avec ses propres données. Le tracé OSRM exact d’AURA n’est donc pas garanti.</div>
        <footer><span id="auraSendPhoneState">PRÊT</span><small>Coordonnées envoyées au fournisseur uniquement à l’ouverture du lien mobile.</small></footer></div>`;
      const check=auraSendPhonePanel.querySelector('#auraSendUsePhoneLocation');if(check)check.checked=auraSendCurrentLocationDefault();
      auraSendPhonePanel.querySelector('#auraSendPhoneToggle')?.addEventListener('click',()=>auraSendSetOpen(!auraSendPhoneOpen));
      auraSendPhonePanel.querySelectorAll('[data-send-provider]').forEach(b=>b.addEventListener('click',()=>auraSendSetProvider(String(b.dataset.sendProvider||'google'))));
      auraSendPhonePanel.querySelector('#auraSendUsePhoneLocation')?.addEventListener('change',()=>{auraSendPhoneLast=null;auraSendPhoneFingerprint='';if(auraSendPhoneOpen)auraSendGenerate(true);});
      auraSendPhonePanel.querySelector('#auraSendGenerate')?.addEventListener('click',()=>auraSendGenerate(true));
      auraSendPhonePanel.querySelector('#auraSendCopy')?.addEventListener('click',auraSendCopy);
    }
    const trip=sidebar.querySelector('#auraTripPlanner');
    if(trip){if(auraSendPhonePanel.nextElementSibling!==trip)trip.insertAdjacentElement('beforebegin',auraSendPhonePanel);}else if(!auraSendPhonePanel.isConnected)sidebar.appendChild(auraSendPhonePanel);
    return true;
  }
  function auraSendSetOpen(open){
    if(!auraSendEnsurePanel())return;auraSendPhoneOpen=!!open;auraSendPhonePanel.classList.toggle('open',auraSendPhoneOpen);auraSendPhonePanel.querySelector('#auraSendPhoneToggle')?.setAttribute('aria-expanded',auraSendPhoneOpen?'true':'false');
    if(auraSendPhoneOpen){const check=auraSendPhonePanel.querySelector('#auraSendUsePhoneLocation');if(check&&auraSendPhoneLast===null)check.checked=auraSendCurrentLocationDefault();requestAnimationFrame(()=>auraSendGenerate(false));}
  }
  /* AURA P0.6.6.3.1 SEND PHONE VISIBILITY + REBIND */
  function bindSendPhonePanel(){
    let attempts=0;
    const ensure=()=>{
      if(auraSendEnsurePanel())return true;
      attempts+=1;
      if(attempts<24)setTimeout(ensure,250);
      return false;
    };
    ensure();
    if(root&&!root.dataset.auraSendPhoneRebind){
      root.dataset.auraSendPhoneRebind='p06631';
      let queued=false;
      const observer=new MutationObserver(()=>{
        if(queued)return;queued=true;
        setTimeout(()=>{queued=false;auraSendEnsurePanel();},0);
      });
      observer.observe(root,{childList:true,subtree:true});
    }
  }

  /* AURA P0.6.6.4 AURA TRAVEL BRIEF */
  let auraBriefPanel=null,auraBriefOpen=false,auraBriefBusy=false,auraBriefObserver=null,auraBriefInputTimer=null;

  const auraBriefEsc=s=>String(s??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const auraBriefNorm=s=>String(s??'').replace(/\s+/g,' ').trim();
  function auraBriefClock(date){
    const d=date instanceof Date?date:new Date(date);
    return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('fr-FR',{hour:'2-digit',minute:'2-digit'}).format(d):'—';
  }
  function auraBriefDateTime(date){
    const d=date instanceof Date?date:new Date(date);
    return Number.isFinite(d.getTime())?new Intl.DateTimeFormat('fr-FR',{day:'2-digit',month:'2-digit',hour:'2-digit',minute:'2-digit'}).format(d):'—';
  }
  function auraBriefKm(m){const km=Math.max(0,Number(m)||0)/1000;return km<10?`${km.toFixed(1).replace('.',',')} km`:`${Math.round(km)} km`;}
  function auraBriefDuration(s){const min=Math.max(0,Math.round((Number(s)||0)/60));const h=Math.floor(min/60),m=min%60;return h?`${h} h ${String(m).padStart(2,'0')}`:`${m} min`;}
  function auraBriefMoney(v){return `${Math.max(0,Number(v)||0).toFixed(2).replace('.',',')} €`;}
  function auraBriefDeparture(){
    const v=root?.querySelector('#auraTripDeparture')?.value;
    const d=v?new Date(v):new Date();
    return Number.isFinite(d.getTime())?d:new Date();
  }
  function auraBriefFuel(){
    const km=Math.max(0,Number(routeSummary?.distance)||0)/1000;
    const rawConsumption=root?.querySelector('#auraTripConsumption')?.value,rawPrice=root?.querySelector('#auraTripFuelPrice')?.value;
    const consumption=finite(rawConsumption)?Math.max(0,Number(rawConsumption)):6.5;
    const price=finite(rawPrice)?Math.max(0,Number(rawPrice)):1.85;
    return {consumption,price,cost:km*consumption/100*price};
  }
  function auraBriefPoi(){
    if(!auraPoiSelectedId)return null;
    return auraPoiResults.find((x,i)=>String(x.id||`${x.osm_type||'poi'}-${x.osm_id||i}`)===String(auraPoiSelectedId))||null;
  }
  function auraBriefWeatherFresh(){
    try{return !!auraContextData&&auraContextFingerprint===auraContextRouteFingerprint();}catch(_){return false;}
  }
  function auraBriefLevel(){
    if(!routeSummary)return {level:'missing',label:'ITINÉRAIRE REQUIS'};
    if(!auraBriefWeatherFresh())return {level:'partial',label:'BRIEF PARTIEL'};
    const level=auraContextLevelClass(auraContextData?.risk?.level);
    if(level==='difficult')return {level,label:'PRUDENCE RENFORCÉE'};
    if(level==='watch')return {level,label:'CONDITIONS À SURVEILLER'};
    return {level:'ready',label:'PRÊT À PARTIR'};
  }
  function auraBriefSelectedPoiText(){
    const poi=auraBriefPoi();
    if(poi){
      const meta=auraPoiMeta(poi.category||auraPoiCategory);
      const distance=finite(poi.distance_to_route_m)?` · ${auraPoiDistance(poi.distance_to_route_m)} du trajet`:'';
      return `<b>${auraBriefEsc(poi.name||meta.label)}</b><small>${auraBriefEsc(meta.label+distance)}</small>`;
    }
    if(auraPoiResults.length){const meta=auraPoiMeta(auraPoiCategory);return `<b>AUCUN LIEU SÉLECTIONNÉ</b><small>${auraPoiResults.length} résultat${auraPoiResults.length>1?'s':''} · ${auraBriefEsc(meta.label)}</small>`;}
    return '<b>AUCUN LIEU SÉLECTIONNÉ</b><small>Optionnel · utilisez POI si nécessaire</small>';
  }
  function auraBriefWeatherText(){
    if(!auraBriefWeatherFresh())return {title:'MÉTÉO À ACTUALISER',detail:'Aucune prévision fraîche pour ce départ.'};
    const samples=Array.isArray(auraContextData?.weather_samples)?auraContextData.weather_samples:[];
    if(!samples.length)return {title:'MÉTÉO INDISPONIBLE',detail:'Prévision hors horizon ou source indisponible.'};
    const temps=samples.map(x=>Number(x.temperature)).filter(Number.isFinite);
    const rain=samples.map(x=>Number(x.precipitation_probability)).filter(Number.isFinite);
    const wind=samples.map(x=>Number(x.wind_speed)).filter(Number.isFinite);
    const risk=auraContextLevelClass(auraContextData?.risk?.level);
    const title=auraContextLevelLabel(risk);
    const bits=[];
    if(temps.length)bits.push(`${Math.round(Math.min(...temps))}–${Math.round(Math.max(...temps))}°`);
    if(rain.length)bits.push(`pluie max ${Math.round(Math.max(...rain))}%`);
    if(wind.length)bits.push(`vent max ${Math.round(Math.max(...wind))} km/h`);
    return {title,detail:bits.join(' · ')||`${samples.length} points météo analysés`};
  }
  function auraBriefNarrative(){
    if(!routeSummary)return 'Calculez d’abord un itinéraire pour générer le Travel Brief.';
    const dep=auraBriefDeparture(),arrival=new Date(dep.getTime()+Math.max(0,Number(routeSummary.duration)||0)*1000),fuel=auraBriefFuel();
    const weather=auraBriefWeatherFresh()?auraContextLevelLabel(auraContextData?.risk?.level).toLowerCase():'météo à actualiser';
    return `Départ prévu le ${auraBriefDateTime(dep)} vers ${auraBriefNorm(destination?.shortLabel||destination?.label||'la destination')}. ${auraBriefKm(routeSummary.distance)}, ${auraBriefDuration(routeSummary.duration)}, arrivée vers ${auraBriefClock(arrival)}. Carburant estimé ${auraBriefMoney(fuel.cost)} hors péages. ${weather}. Trafic temps réel ${auraContextData?.traffic?.live?'connecté':'non connecté'}.`;
  }
  function auraBriefRender(){
    if(!auraBriefPanel)return;
    const status=auraBriefPanel.querySelector('#auraBriefStatus');
    const route=auraBriefPanel.querySelector('#auraBriefRoute');
    const context=auraBriefPanel.querySelector('#auraBriefContext');
    const poiBox=auraBriefPanel.querySelector('#auraBriefPoi');
    const notes=auraBriefPanel.querySelector('#auraBriefNotes');
    const narrative=auraBriefPanel.querySelector('#auraBriefNarrative');
    const start=auraBriefPanel.querySelector('#auraBriefStart');
    const refresh=auraBriefPanel.querySelector('#auraBriefRefresh');
    if(!status||!route||!context||!poiBox||!notes||!narrative)return;
    const level=auraBriefLevel();status.className=`aura-brief-status ${level.level}`;status.innerHTML=`<b>${auraBriefEsc(level.label)}</b><small>${routeSummary?'Synthèse locale des données Maps disponibles.':'Aucun trajet actif.'}</small>`;
    if(!routeSummary){
      route.innerHTML='<div class="aura-brief-empty">Calculez un itinéraire pour préparer le départ.</div>';
      context.innerHTML='<div><span>MÉTÉO</span><b>EN ATTENTE</b><small>Itinéraire requis</small></div><div><span>TRAFIC LIVE</span><b>NON CONNECTÉ</b><small>Aucune donnée temps réel</small></div>';
      poiBox.innerHTML=auraBriefSelectedPoiText();notes.innerHTML='<span>PÉAGES</span><b>NON RENSEIGNÉS PAR OSRM</b>';narrative.textContent=auraBriefNarrative();if(start)start.disabled=true;if(refresh)refresh.disabled=true;return;
    }
    const dep=auraBriefDeparture(),arrival=new Date(dep.getTime()+Math.max(0,Number(routeSummary.duration)||0)*1000),fuel=auraBriefFuel();
    route.innerHTML=`<div><span>DISTANCE</span><b>${auraBriefKm(routeSummary.distance)}</b></div><div><span>DURÉE</span><b>${auraBriefDuration(routeSummary.duration)}</b></div><div><span>ARRIVÉE</span><b>${auraBriefClock(arrival)}</b></div><div><span>CARBURANT*</span><b>${auraBriefMoney(fuel.cost)}</b></div><p><span>DÉPART</span><b>${auraBriefEsc(auraBriefDateTime(dep))}</b><small>${auraBriefEsc(origin?.label||'Position actuelle')} → ${auraBriefEsc(destination?.shortLabel||destination?.label||'Destination')}</small></p>`;
    const weather=auraBriefWeatherText();const live=!!auraContextData?.traffic?.live;
    context.innerHTML=`<div><span>MÉTÉO TRAJET</span><b>${auraBriefEsc(weather.title)}</b><small>${auraBriefEsc(weather.detail)}</small></div><div><span>TRAFIC LIVE</span><b class="${live?'live':'offline'}">${live?'CONNECTÉ':'NON CONNECTÉ'}</b><small>${auraBriefEsc(auraContextData?.traffic?.message||'Durée OSRM hors trafic live')}</small></div>`;
    poiBox.innerHTML=auraBriefSelectedPoiText();
    const riskReasons=auraBriefWeatherFresh()&&Array.isArray(auraContextData?.risk?.reasons)?auraContextData.risk.reasons:[];
    const warnings=[];if(riskReasons.length)warnings.push(...riskReasons.slice(0,2));if(!live)warnings.push('Trafic temps réel non connecté');warnings.push('Péages non renseignés par OSRM');
    notes.innerHTML=warnings.slice(0,4).map(x=>`<span>${auraBriefEsc(x)}</span>`).join('');narrative.textContent=auraBriefNarrative();if(start)start.disabled=false;if(refresh)refresh.disabled=false;
  }
  function auraBriefSetState(text,error=false){const el=auraBriefPanel?.querySelector('#auraBriefState');if(el){el.textContent=String(text||'PRÊT');el.classList.toggle('error',!!error);}}
  async function auraBriefRefresh(forceWeather=false){
    if(auraBriefBusy)return;
    if(!routeSummary){auraBriefRender();auraBriefSetState('ITINÉRAIRE REQUIS',true);return;}
    auraBriefBusy=true;const refresh=auraBriefPanel?.querySelector('#auraBriefRefresh');if(refresh)refresh.disabled=true;auraBriefSetState('PRÉPARATION DU BRIEF…');
    try{
      const stale=!auraBriefWeatherFresh();if(forceWeather||stale)await auraContextRefresh(!!forceWeather);
      auraBriefRender();auraBriefSetState(auraBriefWeatherFresh()?'BRIEF À JOUR':'BRIEF PARTIEL · MÉTÉO INDISPONIBLE',!auraBriefWeatherFresh());
    }catch(_){auraBriefRender();auraBriefSetState('BRIEF PARTIEL',true);}
    finally{auraBriefBusy=false;if(refresh)refresh.disabled=!routeSummary;}
  }
  function auraBriefEnsurePanel(){
    if(!root)return false;const sidebar=root.querySelector('.aura-nav-sidebar');if(!sidebar)return false;
    auraBriefPanel=sidebar.querySelector('#auraTravelBrief');if(!auraBriefPanel){auraBriefPanel=document.createElement('section');auraBriefPanel.id='auraTravelBrief';auraBriefPanel.className='aura-travel-brief';}
    if(auraBriefPanel.dataset.auraBriefBuilt!=='p0664'){
      auraBriefPanel.dataset.auraBriefBuilt='p0664';auraBriefPanel.innerHTML=`<button id="auraBriefToggle" class="aura-brief-launch" type="button"><span>AURA TRAVEL BRIEF</span><small>PRÊT À PARTIR · TRAJET · MÉTÉO · COÛT</small><i>›</i></button><div class="aura-brief-body"><header><div><span>MAPS DESKTOP</span><b>AURA TRAVEL BRIEF</b></div><em>v1.0.0</em></header><div id="auraBriefStatus" class="aura-brief-status partial"></div><div id="auraBriefRoute" class="aura-brief-route"></div><div id="auraBriefContext" class="aura-brief-context"></div><section class="aura-brief-poi-wrap"><span>ARRÊT / POI SÉLECTIONNÉ</span><div id="auraBriefPoi" class="aura-brief-poi"></div></section><div id="auraBriefNotes" class="aura-brief-notes"></div><p id="auraBriefNarrative" class="aura-brief-narrative"></p><div class="aura-brief-actions"><button id="auraBriefStart" type="button"><span>DÉMARRER</span><small>NAVIGATION AURA</small></button><button id="auraBriefPhone" type="button"><span>TÉLÉPHONE</span><small>QR / LIEN</small></button><button id="auraBriefRefresh" type="button"><span>ACTUALISER LE BRIEF</span><small>RECALCULER LA MÉTÉO</small></button></div><footer><span id="auraBriefState">PRÊT</span><small>* estimation carburant locale hors péages</small></footer></div>`;
      auraBriefPanel.querySelector('#auraBriefToggle')?.addEventListener('click',()=>auraBriefSetOpen(!auraBriefOpen));
      auraBriefPanel.querySelector('#auraBriefRefresh')?.addEventListener('click',()=>auraBriefRefresh(true));
      auraBriefPanel.querySelector('#auraBriefStart')?.addEventListener('click',()=>{if(!routeSummary)return;auraBriefSetOpen(false);startNavigation();});
      auraBriefPanel.querySelector('#auraBriefPhone')?.addEventListener('click',()=>{if(!routeSummary){auraBriefSetState('ITINÉRAIRE REQUIS',true);return;}auraBriefSetOpen(false);auraSendSetOpen(true);});
    }
    const send=sidebar.querySelector('#auraSendPhone'),trip=sidebar.querySelector('#auraTripPlanner');
    if(send){if(auraBriefPanel.nextElementSibling!==send)send.insertAdjacentElement('beforebegin',auraBriefPanel);}else if(trip){if(auraBriefPanel.nextElementSibling!==trip)trip.insertAdjacentElement('beforebegin',auraBriefPanel);}else if(!auraBriefPanel.isConnected)sidebar.appendChild(auraBriefPanel);
    return true;
  }
  function auraBriefSetOpen(open){
    if(!auraBriefEnsurePanel())return;auraBriefOpen=!!open;auraBriefPanel.classList.toggle('open',auraBriefOpen);auraBriefPanel.querySelector('#auraBriefToggle')?.setAttribute('aria-expanded',auraBriefOpen?'true':'false');
    if(auraBriefOpen){if(auraSendPhoneOpen)auraSendSetOpen(false);if(auraPoiOpen)auraPoiSetOpen(false);if(auraContextOpen)auraContextSetOpen(false);auraBriefRender();requestAnimationFrame(()=>auraBriefRefresh(false));}
  }
  function bindTravelBrief(){
    let attempts=0;const ensure=()=>{if(auraBriefEnsurePanel())return true;attempts+=1;if(attempts<24)setTimeout(ensure,250);return false;};ensure();
    if(root&&root.dataset.auraTravelBriefBound!=='p0664'){
      root.dataset.auraTravelBriefBound='p0664';
      root.addEventListener('input',e=>{if(!auraBriefOpen)return;if(!['auraTripDeparture','auraTripConsumption','auraTripFuelPrice'].includes(String(e.target?.id||'')))return;clearTimeout(auraBriefInputTimer);auraBriefInputTimer=setTimeout(auraBriefRender,80);},true);
      root.querySelectorAll('.aura-nav-toolbar button').forEach(btn=>btn.addEventListener('click',()=>{if(auraBriefOpen)auraBriefSetOpen(false);},true));
      let queued=false;const observer=new MutationObserver(()=>{if(queued)return;queued=true;setTimeout(()=>{queued=false;auraBriefEnsurePanel();if(auraBriefOpen)auraBriefRender();},0);});observer.observe(root,{childList:true,subtree:true});
      auraBriefObserver=observer;
    }
  }

  function getRouteGeometry(){
    if(!Array.isArray(routeGeometry))return [];
    return routeGeometry
      .filter(p=>Array.isArray(p)&&p.length>=2&&finite(p[0])&&finite(p[1]))
      .map(p=>[Number(p[0]),Number(p[1])]);
  }

  function projectPoint(lat,lon){
    if(!map||!finite(lat)||!finite(lon))return null;
    const vp=viewport();
    if(!vp||vp.w<20||vp.h<20)return null;
    const p=project(Number(lat),Number(lon),vp);
    if(!p||!finite(p[0])||!finite(p[1]))return null;
    const margin=48;
    return {
      x:Number(p[0]),y:Number(p[1]),w:vp.w,h:vp.h,
      visible:p[0]>=-margin&&p[0]<=vp.w+margin&&p[1]>=-margin&&p[1]<=vp.h+margin
    };
  }

  window.AURA_NAVIGATION={
    open,close,setOrigin,setDestination,recenter,calculateRoute,useRoute,getRouteGeometry,projectPoint,clearRoute,startNavigation,stopNavigation,rerouteNavigation,setNavigationVoiceEnabled,
    centerOn(lat,lon,z=zoom){
      if(finite(lat)&&finite(lon)){
        centerLat=Number(lat);
        centerLon=Number(lon);
        zoom=clamp(Math.round(z),MIN_Z,MAX_Z);
        scheduleRender();
      }
    },
    get state(){
      return {open:openState,centerLat,centerLon,zoom,origin,destination,navigationActive,routeSummary};
    }
  };

  window.AURA_WORKSPACES = window.AURA_WORKSPACES || {};
  window.AURA_WORKSPACES.navigation = {
    open,
    close,
    setOrigin,
    setDestination,
    calculateRoute,
    useRoute,
    getRouteGeometry,
    projectPoint,
    clearRoute,
    startNavigation,
    stopNavigation,
    rerouteNavigation,
    setNavigationVoiceEnabled,
    recenter
  };


  /* AURA P0.8.5.4.7.5.1 — MAPS WORKSPACE ROUTE INJECTION BRIDGE */
  let auraCoreMapsBridgeSeq=0;

  function auraCoreMapsPoint(value,label,fallbackPoint=null){
    let lat=null,lon=null;
    if(Array.isArray(value) && value.length>=2){
      lat=Number(value[0]);lon=Number(value[1]);
    }
    if((!finite(lat)||!finite(lon)) && Array.isArray(fallbackPoint) && fallbackPoint.length>=2){
      lat=Number(fallbackPoint[0]);lon=Number(fallbackPoint[1]);
    }
    return {
      lat:finite(lat)?lat:null,
      lon:finite(lon)?lon:null,
      label:norm(label)||'Destination'
    };
  }

  function auraCoreMapsFallbackRoute(payload){
    const raw=Array.isArray(payload?.route_points)?payload.route_points:[];
    const coordinates=raw
      .filter(p=>Array.isArray(p)&&p.length>=2&&finite(p[0])&&finite(p[1]))
      .map(p=>[Number(p[1]),Number(p[0])]);
    if(coordinates.length<2)return null;
    const distanceKm=Number(payload?.distance_km);
    const durationMin=Number(payload?.duration_min);
    return {
      geometry:{type:'LineString',coordinates},
      distance:finite(distanceKm)?Math.max(0,distanceKm*1000):0,
      duration:finite(durationMin)?Math.max(0,durationMin*60):0,
      steps:[]
    };
  }

  async function auraConsumeCoreMapsPayload(payload){
    if(!payload || typeof payload!=='object')return;
    const mode=String(payload.mode||'').toLowerCase();
    const rawPoints=Array.isArray(payload.route_points)?payload.route_points:[];
    const first=rawPoints.length?rawPoints[0]:null;
    const last=rawPoints.length?rawPoints[rawPoints.length-1]:null;
    const originPoint=auraCoreMapsPoint(
      payload.origin_coordinates,
      payload.origin_label||payload.origin||'Départ',
      first
    );
    const destinationPoint=auraCoreMapsPoint(
      payload.destination_coordinates,
      payload.label||payload.destination||'Destination',
      last
    );

    if(mode!=='directions'){
      open({
        center:hasCoordinates(destinationPoint)?destinationPoint:undefined,
        destination:destinationPoint
      });
      return;
    }

    const seq=++auraCoreMapsBridgeSeq;
    workspaceActivity(
      'loading',
      'Maps Core bridge',
      `${shortPlaceLabel(originPoint,'Départ')} → ${shortPlaceLabel(destinationPoint,'Destination')}`
    );

    // Passing an explicit origin prevents the legacy first-open geolocation
    // routine from replacing a user-specified departure such as Toulon.
    open({
      origin:originPoint,
      destination:destinationPoint
    });

    // Reassert the Core points after workspace creation before route calculation.
    setOrigin(originPoint);
    setDestination(destinationPoint);

    try{
      await calculateRoute();
      if(seq!==auraCoreMapsBridgeSeq)return;
      const auraRouteEvidence={
        source:'core-shared-native',
        origin:originPoint,
        destination:destinationPoint,
        originLabel:String(originPoint?.label||''),
        destinationLabel:String(destinationPoint?.label||''),
        points:rawPoints.length,
        ts:Date.now()
      };
      window.__AURA_P08547615_MAPS_LAST_ROUTE__=auraRouteEvidence;
      window.dispatchEvent(new CustomEvent('aura:maps:core-route-visible',{detail:auraRouteEvidence}));
    }catch(err){
      if(seq!==auraCoreMapsBridgeSeq)return;
      const fallback=auraCoreMapsFallbackRoute(payload);
      if(fallback){
        useRoute(fallback,{status:'ITINÉRAIRE PRÊT · CORE',remember:true});
        workspaceActivity(
          'ready',
          'Itinéraire prêt',
          `${shortPlaceLabel(originPoint,'Départ')} → ${shortPlaceLabel(destinationPoint,'Destination')} · CORE`
        );
        const auraRouteEvidence={
          source:'core-fallback',
          origin:originPoint,
          destination:destinationPoint,
          originLabel:String(originPoint?.label||''),
          destinationLabel:String(destinationPoint?.label||''),
          points:rawPoints.length,
          ts:Date.now()
        };
        window.__AURA_P08547615_MAPS_LAST_ROUTE__=auraRouteEvidence;
        window.dispatchEvent(new CustomEvent('aura:maps:core-route-visible',{detail:auraRouteEvidence}));
      }else{
        setRouteError(err);
      }
    }
  }

  /* AURA P0.8.5.4.7.6.1.5 — MAPS SHARED EVENT BUS COMPLETION */
  function connectCoreMapsStream(){
    if(!token || window.__AURA_P08547615_MAPS_BUS__)return;
    window.__AURA_SHARED_EVENT_SUBSCRIBERS__=window.__AURA_SHARED_EVENT_SUBSCRIBERS__||{};
    window.__AURA_SHARED_EVENT_SUBSCRIBERS__.maps=true;
    const handler=e=>{
      const msg=e?.detail||{};
      if(msg?.type==='workspace.maps_route'){
        Promise.resolve(auraConsumeCoreMapsPayload(msg.data||{})).catch(setRouteError);
      }
    };
    window.__AURA_P08547615_MAPS_BUS__=handler;
    window.addEventListener('aura:hub-event',handler);
  }

  window.addEventListener('aura:navigation:open',e=>open(e.detail||{}));
  window.addEventListener('aura:navigation:close',close);

  let workspaceObserver=null;
  function installWorkspaceOwnership(){
    if(workspaceObserver || !document.body)return;
    workspaceObserver=new MutationObserver(()=>{
      // WX can also be opened directly from its rail button, without an
      // aura:workspace:weather event. In that case Navigation yields.
      if(openState && document.body.classList.contains('aura-weather-active')){
        close();
      }
    });
    workspaceObserver.observe(document.body,{
      attributes:true,
      attributeFilter:['class']
    });
  }

  function boot(){
    create();
    renderRecents();
    updatePrimaryAction();
    installComposerBridge();
    installWorkspaceOwnership();
    connectCoreMapsStream();
  }

  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',boot,{once:true});
  }else{
    boot();
  }
})();
