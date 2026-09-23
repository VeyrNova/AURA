/* AURA P0.5.2.1 IMMERSIVE GEOSPATIAL WEATHER MAP */
/* AURA P0.5.2.2 WEATHER MAP READABILITY + TEMPORAL COHERENCE */
/* AURA P0.5.2.3.1 LOCALIZED CARTOGRAPHY MARKER FIX */
/* AURA P0.5.2.3.2 WEATHER ERROR RECOVERY */
/* AURA P0.5.2.4 ADAPTIVE MAP NAVIGATION + CITY LOD */
/* AURA P0.5.2.4.1 MAP GEOGRAPHY + CITY VISIBILITY HOTFIX */
/* AURA P0.5.2.4.2 FOREGROUND VECTOR CARTOGRAPHY */
/* AURA P0.5.2.4.3 VIEWPORT NULL CENTER FIX */
/* AURA P0.5.2.5 HIGH FIDELITY LOCAL CARTOGRAPHY */
/* AURA P0.5.2.5.1 CARTOGRAPHIC READABILITY + CITY HIERARCHY */
/* AURA P0.5.2.6 GLOBAL NAVIGABLE CARTOGRAPHY */
/* AURA P0.5.2.7 HYBRID WORLD MAP TILES */
/* AURA P0.5.2.7.1 LOOPBACK TILE PROXY */
/* AURA P0.5.2.7.2 TILE COMPOSITING FIX */
/* AURA P0.5.2.8 WORLDWIDE AURA CARTOGRAPHIC CONTEXT */
/* AURA P0.5.2.8.1 REGIONAL CONTEXT ACTIVATION FIX */
/* AURA P0.5.2.8.2 CONTEXT REQUEST STABILIZATION */
/* AURA P0.5.2.8.3 FAST WORLD CONTEXT */
/* AURA P0.5.2.8.4 WEB MERCATOR OVERLAY ALIGNMENT */
/* AURA P0.5.2.8.5 LOCAL FIDELITY GUARD */
/* AURA P0.5.2.8.6 NEARBY CITY LABEL CAP */
/* AURA P0.5.2.8.7 SEMANTIC WEATHER LAYERS */
/* AURA P0.5.2.8.8 WIND FLOW DIRECTION FIX */
(() => {
  'use strict';
  if (window.__AURA_P0521_WEATHER_MAP__) return;
  window.__AURA_P0521_WEATHER_MAP__ = true;

  const clamp=(v,a=0,b=1)=>Math.max(a,Math.min(b,Number(v)||0));
  const norm=s=>String(s??'').replace(/\s+/g,' ').trim();
  const finite=v=>Number.isFinite(Number(v));
  const num=(v,fallback=null)=>finite(v)?Number(v):fallback;
  const fmt=(v,d=0)=>finite(v)?Number(v).toFixed(d):'—';
  const token=new URLSearchParams(location.search).get('token')||'';
  const LAYERS={
    wind:{label:'VENT',unit:'km/h'},
    rain:{label:'PLUIE',unit:'%'},
    temperature:{label:'TEMPÉRATURE',unit:'°C'},
    clouds:{label:'NUAGES',unit:'%'},
    waves:{label:'VAGUES',unit:'m'},
    pressure:{label:'PRESSION',unit:'hPa'}
  };


  const LOCAL_CONTEXT={
    southeast:{
      name:'CÔTE D’AZUR',
      bounds:{latMin:42.5,latMax:44.9,lonMin:4.7,lonMax:8.4},
      cities:[
        {n:'Marseille',lat:43.2965,lon:5.3698,p:10},{n:'Aix-en-Provence',lat:43.5297,lon:5.4474,p:7},
        {n:'Toulon',lat:43.1242,lon:5.9280,p:8},{n:'Hyères',lat:43.1204,lon:6.1286,p:6},
        {n:'Brignoles',lat:43.4058,lon:6.0617,p:5},{n:'Le Luc',lat:43.3944,lon:6.3131,p:4},
        {n:'Vidauban',lat:43.4275,lon:6.4327,p:5},{n:'Le Muy',lat:43.4719,lon:6.5661,p:4},
        {n:'Draguignan',lat:43.5362,lon:6.4666,p:6},{n:'Fréjus',lat:43.4326,lon:6.7356,p:8},
        {n:'Saint-Raphaël',lat:43.4236,lon:6.7735,p:7},{n:'Sainte-Maxime',lat:43.3086,lon:6.6380,p:6},
        {n:'Saint-Tropez',lat:43.2677,lon:6.6407,p:6},{n:'Grasse',lat:43.6581,lon:6.9254,p:6},
        {n:'Cannes',lat:43.5528,lon:7.0174,p:8},{n:'Antibes',lat:43.5804,lon:7.1251,p:7},
        {n:'Nice',lat:43.7102,lon:7.2620,p:9},{n:'Monaco',lat:43.7384,lon:7.4246,p:7},
        {n:'Menton',lat:43.7756,lon:7.5043,p:6},{n:'Sanremo',lat:43.8170,lon:7.7770,p:6},
        {n:'Imperia',lat:43.8868,lon:8.0270,p:5},{n:'Cuneo',lat:44.3845,lon:7.5427,p:5},
        {n:'Gênes',lat:44.4056,lon:8.9463,p:6}
      ],
      coast:[
        [5.11,43.29],[5.28,43.28],[5.39,43.28],[5.49,43.27],[5.63,43.25],[5.78,43.19],[5.91,43.13],
        [6.04,43.11],[6.17,43.09],[6.28,43.10],[6.39,43.13],[6.49,43.20],[6.58,43.28],[6.69,43.38],
        [6.76,43.42],[6.85,43.45],[6.95,43.50],[7.02,43.54],[7.09,43.57],[7.16,43.59],[7.23,43.64],
        [7.28,43.67],[7.34,43.70],[7.40,43.72],[7.46,43.74],[7.53,43.77],[7.60,43.80],[7.71,43.82],
        [7.82,43.84],[7.95,43.86],[8.07,43.88],[8.18,43.92]
      ],
      borderFI:[[7.48,43.79],[7.47,43.88],[7.45,43.98],[7.38,44.09],[7.29,44.18],[7.23,44.28],[7.15,44.37],[7.07,44.46]],
      borderFS:[[6.80,46.16],[6.69,46.13],[6.59,46.13],[6.49,46.15],[6.36,46.20]],
      areas:[
        {n:'BOUCHES-DU-RHÔNE',lat:43.58,lon:5.45,t:'land'},
        {n:'VAR',lat:43.70,lon:6.18,t:'land'},
        {n:'ALPES-MARITIMES',lat:43.93,lon:7.15,t:'land'},
        {n:'MÉDITERRANÉE',lat:42.94,lon:6.52,t:'sea'}
      ],
      view:{lat:1.18,lon:3.45}
    },
    kanto:{
      name:'KANTŌ',
      bounds:{latMin:34.6,latMax:37.1,lonMin:138.3,lonMax:141.4},
      cities:[
        {n:'Tokyo',lat:35.6762,lon:139.6503,p:10},
        {n:'Yokohama',lat:35.4437,lon:139.6380,p:9},
        {n:'Kawasaki',lat:35.5308,lon:139.7030,p:8},
        {n:'Saitama',lat:35.8617,lon:139.6455,p:8},
        {n:'Chiba',lat:35.6073,lon:140.1063,p:8},
        {n:'Hachioji',lat:35.6558,lon:139.3389,p:6},
        {n:'Machida',lat:35.5465,lon:139.4386,p:5},
        {n:'Yokosuka',lat:35.2813,lon:139.6722,p:6},
        {n:'Kamakura',lat:35.3192,lon:139.5467,p:5},
        {n:'Narita',lat:35.7767,lon:140.3189,p:5},
        {n:'Funabashi',lat:35.6947,lon:139.9826,p:6},
        {n:'Kawagoe',lat:35.9251,lon:139.4858,p:5},
        {n:'Kashiwa',lat:35.8676,lon:139.9758,p:5},
        {n:'Tsukuba',lat:36.0835,lon:140.0764,p:5},
        {n:'Mito',lat:36.3659,lon:140.4712,p:6},
        {n:'Utsunomiya',lat:36.5551,lon:139.8828,p:6},
        {n:'Maebashi',lat:36.3895,lon:139.0634,p:5},
        {n:'Takasaki',lat:36.3219,lon:139.0033,p:5}
      ],
      coasts:[
        [
          [138.95,35.15],[139.10,35.18],[139.26,35.20],[139.39,35.25],
          [139.52,35.30],[139.61,35.35],[139.66,35.43],[139.70,35.51],
          [139.73,35.58],[139.77,35.63]
        ],
        [
          [139.77,35.63],[139.87,35.62],[139.98,35.61],[140.10,35.61],
          [140.20,35.65],[140.31,35.70],[140.45,35.76],[140.58,35.84],
          [140.68,35.94],[140.76,36.08],[140.81,36.25],[140.86,36.45]
        ],
        [
          [139.82,35.03],[139.82,35.13],[139.84,35.24],[139.88,35.34],
          [139.92,35.42],[139.97,35.51],[140.02,35.57]
        ]
      ],
      areas:[
        {n:'SAITAMA',lat:35.98,lon:139.55,t:'land'},
        {n:'TOKYO',lat:35.72,lon:139.48,t:'land'},
        {n:'CHIBA',lat:35.73,lon:140.35,t:'land'},
        {n:'KANAGAWA',lat:35.34,lon:139.42,t:'land'},
        {n:'BAIE DE TOKYO',lat:35.40,lon:139.88,t:'sea'}
      ],
      view:{lat:1.28,lon:3.15}
    }
  };

  let root=null, shell=null, canvas=null, ctx=null, geoOverlay=null, tileLayer=null, tileAttribution=null;
  let geoRenderKey='';
  let tileRenderKey='';
  let tileReady=false;
  let tileErrorBurst=0;
  const tileNodes=new Map();
  const MIN_MAP_ZOOM=.008;
  const MAX_MAP_ZOOM=15.0;

  // P0.5.2.8.5:
  // Global GSHHG is a regional/world reference, not a street-level coast.
  // At local zoom, the detailed OSM raster becomes authoritative.
  const AURA_WORLD_COAST_MIN_LATSPAN=1.55;
  const AURA_CITY_CONTEXT_MIN_LATSPAN=1.55;

  // P0.5.2.8.6
  // Aura never adds more than ten contextual city labels around the
  // requested weather location. The OSM raster may still contain its own
  // native map labels underneath.
  const AURA_NEARBY_CITY_LABEL_CAP=10;

  const TILE_PROVIDER=window.AURA_MAP_TILE_PROVIDER||{
    id:'aura-loopback-osm',
    template:'/api/map-tile/{z}/{x}/{y}.png?token={token}',
    minZoom:2,
    maxZoom:15,
    localLatSpanMax:14,
    attribution:'© OpenStreetMap contributors'
  };
  let payload=null, field=null, activeLayer='wind', timeIndex=0;
  let weatherError=null;
  let animationTimer=0, drawRaf=0, animPhase=0, bootAttempts=0;
  let particles=[];
  let zoomFactor=1;
  let viewCenterLat=null, viewCenterLon=null;
  let dragState=null;

  // P0.5.2.8: worldwide Aura context overlay.
  // PACA/Kantō keep their embedded local atlas; everywhere else gets
  // OpenStreetMap coastline + nearby place nodes through the Aura loopback.
  let worldContext=null;
  let worldContextTimer=0;
  let worldContextPendingKey='';
  let worldContextLoadedKey='';
  let worldContextAbort=null;
  let worldContextRequestSeq=0;
  let worldContextTimeoutTimer=0;
  const worldContextCache=new Map();

  function waitForWorkspace(){
    root=document.getElementById('auraWeatherWorkspace');
    if(!root || !window.AURA_WORKSPACES?.weather){
      if(++bootAttempts<300)setTimeout(waitForWorkspace,100);
      return;
    }
    mount();
    connectWeatherStream();
  }

  function mount(){
    if(document.getElementById('auraWxGeoMap'))return;
    shell=document.createElement('section');
    shell.id='auraWxGeoMap';
    shell.className='aura-wx-geo-map';
    shell.innerHTML=`
      <div class="aura-wx-map-surface">
        <div id="auraWxTileLayer" class="aura-wx-tile-layer" aria-hidden="true"></div>
        <canvas id="auraWxMapCanvas"></canvas>
        <svg id="auraWxGeoOverlay" aria-hidden="true"></svg>
        <div class="aura-wx-map-scan"></div>
        <div class="aura-wx-map-target"><i></i><span id="auraWxMapTargetLabel">—</span></div>
        <div id="auraWxMapNoData" class="aura-wx-map-nodata">CHAMP MÉTÉO EN ATTENTE</div>
        <div id="auraWxLayerNotice" class="aura-wx-layer-notice"></div>
      </div>

      <div class="aura-wx-map-toolbar">
        <span>COUCHES</span>
        ${Object.entries(LAYERS).map(([k,v])=>`<button data-wx-layer="${k}" class="${k==='wind'?'active':''}">${v.label}</button>`).join('')}
      </div>


      <div class="aura-wx-map-nav">
        <button data-map-nav="minus" aria-label="Dézoomer">−</button>
        <button data-map-nav="recenter" aria-label="Recentrer">⌖</button>
        <button data-map-nav="plus" aria-label="Zoomer">+</button>
      </div>

      <div class="aura-wx-map-animation">
        <button id="auraWxPlay" aria-label="Lecture animation">▶</button>
        <span>ANIMATION</span>
        <b id="auraWxMapMode">CHAMP 5×5</b>
      </div>

      <aside class="aura-wx-map-details">
        <header>DÉTAILS DU CHAMP <small id="auraWxLayerStatus">CHAMP · —</small></header>
        <div class="aura-wx-detail-main"><span id="auraWxLayerName">VENT · CHAMP</span><strong id="auraWxLayerValue">—</strong></div>
        <div class="aura-wx-detail-local"><span>POINT ACTUEL</span><b id="auraWxLocalValue">—</b></div>
        <dl>
          <div><dt>Plage régionale</dt><dd id="auraWxLayerRange">—</dd></div>
          <div><dt>Direction</dt><dd id="auraWxWindDir">—</dd></div>
          <div><dt>Rafales</dt><dd id="auraWxGust">—</dd></div>
          <div><dt>Pression</dt><dd id="auraWxPressure">—</dd></div>
          <div><dt>Nuages</dt><dd id="auraWxCloud">—</dd></div>
        </dl>
        <footer><span>OPEN-METEO · AURA CORE</span><b id="auraWxFieldClock">—</b></footer>
      </aside>

      <div class="aura-wx-map-legend"><span id="auraWxLegendMax">—</span><i></i><span id="auraWxLegendMin">—</span><b id="auraWxLegendUnit"></b></div>

      <div id="auraWxTileAttribution" class="aura-wx-tile-attribution">AURA MAP PROXY · VECTOR FALLBACK</div>

      <div class="aura-wx-map-timeline">
        <button class="active" data-offset="0">MAINTENANT</button>
        <button data-offset="3">+3 H</button>
        <button data-offset="6">+6 H</button>
        <button data-offset="12">+12 H</button>
        <button data-offset="24">+24 H</button>
        <div class="aura-wx-time-track"><i id="auraWxTimeProgress"></i></div>
        <strong id="auraWxTimeLabel">—</strong>
      </div>
    `;
    root.appendChild(shell);
    tileLayer=shell.querySelector('#auraWxTileLayer');
    tileAttribution=shell.querySelector('#auraWxTileAttribution');
    canvas=shell.querySelector('#auraWxMapCanvas');
    geoOverlay=shell.querySelector('#auraWxGeoOverlay');
    geoRenderKey='';
    tileRenderKey='';
    ctx=canvas.getContext('2d',{alpha:true,desynchronized:true});

    shell.querySelectorAll('[data-wx-layer]').forEach(btn=>btn.addEventListener('click',()=>{
      activeLayer=btn.dataset.wxLayer||'wind';
      shell.querySelectorAll('[data-wx-layer]').forEach(b=>b.classList.toggle('active',b===btn));
      updateDetails(); scheduleDraw();
    }));
    shell.querySelectorAll('[data-offset]').forEach(btn=>btn.addEventListener('click',()=>{
      const off=Math.max(0,Number(btn.dataset.offset)||0);
      const max=Math.max(0,(field?.times?.length||1)-1);
      timeIndex=Math.min(off,max);
      shell.querySelectorAll('[data-offset]').forEach(b=>b.classList.toggle('active',b===btn));
      updateTime(); updateDetails(); scheduleDraw();
    }));
    shell.querySelector('#auraWxPlay').addEventListener('click',togglePlay);
    shell.querySelectorAll('[data-map-nav]').forEach(btn=>btn.addEventListener('click',()=>{
      const mode=btn.dataset.mapNav;
      if(mode==='plus')zoomAtCenter(1.18);
      else if(mode==='minus')zoomAtCenter(1/1.18);
      else recenterMap();
    }));

    canvas.addEventListener('wheel',e=>{
      if(!field)return;
      if(Math.abs(e.deltaY)<1)return;
      e.preventDefault();
      const factor=Math.exp(-e.deltaY*.00135);
      zoomAtPointer(e.clientX,e.clientY,factor);
    },{passive:false});

    canvas.addEventListener('pointerdown',e=>{
      if(e.button!==0 || !field)return;
      const vp=viewport();
      const r=canvas.getBoundingClientRect();
      const tileMode=tileBaseActive(vp);
      const tileZ=tileMode?tileZoomForViewport(vp,r.width):null;

      dragState={
        id:e.pointerId,
        x:e.clientX,
        y:e.clientY,
        lat:vp.lat,
        lon:vp.lon,
        latSpan:vp.latSpan,
        lonSpan:vp.lonSpan,
        tileMode,
        tileZ,
        worldX:tileMode?mercatorWorldX(vp.lon,tileZ):null,
        worldY:tileMode?mercatorWorldY(vp.lat,tileZ):null
      };
      canvas.setPointerCapture?.(e.pointerId);
      shell.classList.add('map-dragging');
    });

    canvas.addEventListener('pointermove',e=>{
      if(!dragState || dragState.id!==e.pointerId)return;
      const r=canvas.getBoundingClientRect();
      if(r.width<10||r.height<10)return;
      const dx=e.clientX-dragState.x;
      const dy=e.clientY-dragState.y;

      if(dragState.tileMode && dragState.tileZ!=null){
        viewCenterLon=mercatorLonFromWorldX(
          dragState.worldX-dx,
          dragState.tileZ
        );
        viewCenterLat=Math.max(
          -82,
          Math.min(
            82,
            mercatorLatFromWorldY(
              dragState.worldY-dy,
              dragState.tileZ
            )
          )
        );
      }else{
        viewCenterLon=wrapLon(dragState.lon-dx/r.width*dragState.lonSpan);
        viewCenterLat=Math.max(
          -82,
          Math.min(82,dragState.lat+dy/r.height*dragState.latSpan)
        );
      }

      scheduleDraw();
    });

    const finishDrag=e=>{
      if(!dragState || (e?.pointerId!=null && dragState.id!==e.pointerId))return;
      dragState=null;
      shell.classList.remove('map-dragging');
    };
    canvas.addEventListener('pointerup',finishDrag);
    canvas.addEventListener('pointercancel',finishDrag);
    canvas.addEventListener('lostpointercapture',finishDrag);
    canvas.addEventListener('dblclick',()=>recenterMap());
    new ResizeObserver(()=>{resize();scheduleDraw()}).observe(shell);
    resize();
    seedParticles();
    requestAnimationFrame(animate);
  }

  function resize(){
    if(!canvas||!shell)return;
    const r=shell.getBoundingClientRect();
    const dpr=Math.min(1.5,Math.max(1,window.devicePixelRatio||1));
    canvas.width=Math.max(1,Math.round(r.width*dpr));
    canvas.height=Math.max(1,Math.round(r.height*dpr));
    canvas.style.width=r.width+'px'; canvas.style.height=r.height+'px';
    tileRenderKey='';
    if(geoOverlay){
      geoOverlay.setAttribute('viewBox',`0 0 ${Math.max(1,r.width)} ${Math.max(1,r.height)}`);
      geoOverlay.setAttribute('width',Math.max(1,r.width));
      geoOverlay.setAttribute('height',Math.max(1,r.height));
    }
    ctx?.setTransform(dpr,0,0,dpr,0,0);
  }

  function seedParticles(){
    let seed=0xA0521;
    const rnd=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/4294967296};
    particles=Array.from({length:290},()=>({x:rnd(),y:rnd(),s:.25+rnd()*.75,p:rnd()*Math.PI*2}));
  }

  function normalizePayload(d={}){
    const location=d.place_label||d.location||'';
    const hours=Array.isArray(d.hourly_forecast)?d.hourly_forecast.slice(0,8).map(h=>({
      time:String(h.time||'').slice(11,16)||String(h.time||''),
      temp:finite(h.temperature)?Number(h.temperature).toFixed(0):'—'
    })):[];
    const summary=location && finite(d.temperature)
      ? `À ${location}, il fait actuellement ${Number(d.temperature).toFixed(1)} °C. Conditions actuelles : ${d.condition||'conditions variables'}. Le ressenti est de ${finite(d.apparent)?Number(d.apparent).toFixed(1):'—'} °C. L'humidité est de ${finite(d.humidity)?Number(d.humidity).toFixed(0):'—'}%, et le vent souffle à ${finite(d.wind_speed)?Number(d.wind_speed).toFixed(0):'—'} km/h. Les précipitations actuelles sont de ${finite(d.precipitation)?Number(d.precipitation).toFixed(1):'—'} mm.`
      : '';
    return {
      query:location,
      location,
      temperature:d.temperature,
      feels:d.apparent,
      condition:d.condition,
      wind:finite(d.wind_speed)?`${Number(d.wind_speed).toFixed(0)} km/h`:'',
      windNumber:d.wind_speed,
      humidity:finite(d.humidity)?`${Number(d.humidity).toFixed(0)} %`:'',
      humidityNumber:d.humidity,
      precipitation:finite(d.precipitation)?`${Number(d.precipitation).toFixed(1)} mm`:'',
      precipNumber:d.precipitation,
      precipMm:d.precipitation,
      precipUnit:'mm',
      source:'Open-Meteo',
      verifiedAt:String(d.checked_at||'').slice(11,16),
      hourly:hours,
      summary
    };
  }

  function consumeWeatherPayload(d={}){
    weatherError=null;
    shell?.classList.remove('weather-error');

    const previousPlace=norm(payload?.place_label||payload?.location||'').toLowerCase();
    const nextPlace=norm(d?.place_label||d?.location||'').toLowerCase();
    payload=d||{};

    if(nextPlace && nextPlace!==previousPlace){
      zoomFactor=1;
      viewCenterLat=null;
      viewCenterLon=null;
      dragState=null;

      worldContext=null;
      worldContextPendingKey='';
      worldContextLoadedKey='';
      worldContextRequestSeq++;

      if(worldContextTimeoutTimer){
        clearTimeout(worldContextTimeoutTimer);
        worldContextTimeoutTimer=0;
      }

      window.__AURA_WORLD_CONTEXT_STATE__='idle';
      try{worldContextAbort?.abort();}catch{}
      worldContextAbort=null;
      geoRenderKey='';
    }

    field=(d.weather_field && Array.isArray(d.weather_field.points))?d.weather_field:null;
    timeIndex=d.tomorrow && field?.times?.length>24?24:0;
    const loc=d.place_label||d.location||'—';
    const target=shell?.querySelector('#auraWxMapTargetLabel'); if(target)target.textContent=loc;
    const noData=shell?.querySelector('#auraWxMapNoData');
    if(noData)noData.textContent=field?'':'CHAMP MÉTÉO RÉGIONAL INDISPONIBLE';
    shell?.classList.toggle('has-field',!!field);
    root?.classList.toggle('aura-wx-has-geofield',!!field);
    shell?.classList.toggle('marine-unavailable',!d.marine_field);

    /* AURA R16.4 WEATHER PAYLOAD RESPECTS MANUAL DISMISS: incoming data updates must not reopen a UI the user closed. */
    const auraWeatherUiVisible=()=>!!(root?.classList?.contains('open')||document.body.classList.contains('aura-weather-active'));
    if(auraWeatherUiVisible()){
      try{window.AURA_WORKSPACES?.weather?.open(normalizePayload(d));}catch{}
    }
    setTimeout(()=>{
      if(!auraWeatherUiVisible())return;
      try{window.AURA_WORKSPACES?.weather?.open(normalizePayload(d));}catch{}
    },650);
    updateTime(); updateDetails(); scheduleDraw();
  }

  function connectWeatherStream(){
    if(!token || window.__AURA_P0521_WEATHER_BUS__)return;
    window.__AURA_SHARED_EVENT_SUBSCRIBERS__=window.__AURA_SHARED_EVENT_SUBSCRIBERS__||{};
    window.__AURA_SHARED_EVENT_SUBSCRIBERS__.weather=true;
    const handler=e=>{
      try{
        const msg=e.detail||{};
        if(msg?.type==='weather_workspace')consumeWeatherPayload(msg.data||{});
      }catch{}
    };
    window.__AURA_P0521_WEATHER_BUS__=handler;
    window.addEventListener('aura:hub-event',handler);
  }

  window.addEventListener('aura:weather:error',ev=>{
    const detail=ev.detail||{};
    weatherError=String(detail.message||'DONNÉES MÉTÉO INDISPONIBLES');
    field=null;
    payload={
      ...(payload||{}),
      place_label: detail.query || payload?.place_label || payload?.location || '',
      location: detail.query || payload?.location || ''
    };
    shell?.classList.add('weather-error');
    shell?.classList.remove('has-field');
    root?.classList.remove('aura-wx-has-geofield');
    const noData=shell?.querySelector('#auraWxMapNoData');
    if(noData)noData.textContent='CHAMP MÉTÉO INDISPONIBLE';
    updateTime();
    updateDetails();
    scheduleDraw();
  });

  function fieldHour(point){
    const hs=point?.hours||[];
    return hs[Math.min(timeIndex,Math.max(0,hs.length-1))]||{};
  }

  function valuesFor(layer=activeLayer){
    if(!field)return [];
    const key={wind:'wind_speed',rain:'rain_probability',temperature:'temperature',clouds:'cloud_cover',pressure:'pressure'}[layer];
    if(!key)return [];
    return field.points.map(p=>num(fieldHour(p)[key],null)).filter(v=>v!=null);
  }

  function centerPoint(){
    if(!field?.points?.length)return null;
    const lat=num(field.center_latitude,payload?.latitude);
    const lon=num(field.center_longitude,payload?.longitude);
    let best=null,dist=Infinity;
    for(const p of field.points){
      const d=(num(p.latitude,0)-lat)**2+(num(p.longitude,0)-lon)**2;
      if(d<dist){dist=d;best=p}
    }
    return best;
  }

  function compass(deg){
    if(!finite(deg))return '—';
    const names=['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSO','SO','OSO','O','ONO','NO','NNO'];
    return `${names[Math.round((((Number(deg)%360)+360)%360)/22.5)%16]} · ${Math.round(Number(deg))}°`;
  }

  // Open-Meteo exposes meteorological "from" directions:
  // 0° = wind coming from north, therefore flowing toward south.
  function metFromDegToFlowDeg(deg){
    return (((Number(deg)%360)+360)%360 + 180) % 360;
  }

  function flowDegToMetFromDeg(deg){
    return (((Number(deg)%360)+360)%360 + 180) % 360;
  }


  function approxDistanceKm(aLat,aLon,bLat,bLon){
    const mean=(Number(aLat)+Number(bLat))*.5*Math.PI/180;
    const dx=lonDelta(aLon,bLon)*111.32*Math.max(.18,Math.abs(Math.cos(mean)));
    const dy=(Number(aLat)-Number(bLat))*111.32;
    return Math.hypot(dx,dy);
  }

  function contextRadiusKm(vp){
    if(!vp || !tileBaseActive(vp))return null;
    if(atlasForViewport(vp))return null;

    // At local/detail scale OSM already contains the authoritative place
    // labels. No Overpass city-context request is required.
    if(vp.latSpan<AURA_CITY_CONTEXT_MIN_LATSPAN)return null;

    // P0.5.2.8.1
    // The previous 4.6° cutoff excluded the default regional view of
    // large-area locations such as New York and Queensland.
    //
    // Keep the factual OSM tile base for the full viewport, while Aura
    // enriches the LOCAL CONTEXT around the map centre. We therefore do
    // not need to download context for the entire visible continent.
    if(vp.latSpan>13.5)return null;

    const visibleKm=Math.max(1,vp.latSpan*111.32);

    if(vp.latSpan<.55)
      return Math.max(40,Math.min(60,visibleKm*.82));

    if(vp.latSpan<1.4)
      return Math.max(50,Math.min(72,visibleKm*.58));

    if(vp.latSpan<2.7)
      return Math.max(60,Math.min(85,visibleKm*.40));

    if(vp.latSpan<4.8)
      return Math.max(70,Math.min(95,visibleKm*.28));

    // Regional view: cities within 100 km are enough for an Aura context.
    // The full geographic background remains OpenStreetMap.
    return 100;
  }

  function worldContextCovers(vp,ctx=worldContext){
    if(!ctx || !vp)return false;
    const radius=Number(ctx.radius_km)||0;
    if(radius<=0)return false;

    const needed=contextRadiusKm(vp);
    if(!needed)return false;

    const d=approxDistanceKm(
      Number(ctx.center_lat),
      Number(ctx.center_lon),
      vp.lat,
      vp.lon
    );

    const regional=vp.latSpan>=4.8;

    return regional
      ?d<=Math.max(26,radius*.48)
      :(d<=Math.max(18,radius*.42) && needed<=radius*1.18);
  }

  function dynamicContextForViewport(vp){
    if(atlasForViewport(vp))return null;
    return worldContextCovers(vp) ? worldContext : null;
  }

  function contextRequestKey(vp,radius){
    const step=
      radius<=85 ? .12 :
      radius<=125 ? .20 :
      radius<=120 ? .26 :
      vp.latSpan>=4.8 ? .58 :
      .46;

    const lat=Math.round(vp.lat/step)*step;
    const lon=wrapLon(Math.round(vp.lon/step)*step);
    return `${lat.toFixed(3)}|${lon.toFixed(3)}|${Math.round(radius)}`;
  }

  function scheduleWorldContext(vp,force=false){
    const radius=contextRadiusKm(vp);
    if(!radius){
      if(
        atlasForViewport(vp) ||
        (
          tileBaseActive(vp) &&
          vp.latSpan<AURA_CITY_CONTEXT_MIN_LATSPAN
        )
      ){
        worldContextPendingKey='';

        if(worldContextTimeoutTimer){
          clearTimeout(worldContextTimeoutTimer);
          worldContextTimeoutTimer=0;
        }

        if(
          tileBaseActive(vp) &&
          !atlasForViewport(vp) &&
          vp.latSpan<AURA_CITY_CONTEXT_MIN_LATSPAN
        ){
          try{worldContextAbort?.abort('aura_osm_detail');}catch{}
          worldContextAbort=null;
          worldContextRequestSeq++;
          window.__AURA_WORLD_CONTEXT_STATE__='osm-detail';
        }
      }
      return;
    }

    if(!force && worldContextCovers(vp))return;

    const key=contextRequestKey(vp,radius);
    if(!force && (key===worldContextPendingKey || key===worldContextLoadedKey))return;

    if(worldContextCache.has(key)){
      worldContext=worldContextCache.get(key);
      worldContextLoadedKey=key;
      worldContextPendingKey='';
      geoRenderKey='';
      window.__AURA_WORLD_CONTEXT_STATE__='cache';
      scheduleDraw();
      return;
    }

    worldContextPendingKey=key;
    if(worldContextTimer)clearTimeout(worldContextTimer);

    worldContextTimer=setTimeout(async()=>{
      const scheduledKey=worldContextPendingKey;
      const parts=scheduledKey.split('|');
      const lat=Number(parts[0]);
      const lon=Number(parts[1]);
      const radiusKm=Number(parts[2]);

      if(!token || !Number.isFinite(lat) || !Number.isFinite(lon) || !Number.isFinite(radiusKm)){
        worldContextPendingKey='';
        return;
      }

      try{worldContextAbort?.abort();}catch{}
      const requestSeq=++worldContextRequestSeq;
      const requestController=new AbortController();
      worldContextAbort=requestController;

      if(worldContextTimeoutTimer){
        clearTimeout(worldContextTimeoutTimer);
        worldContextTimeoutTimer=0;
      }

      window.__AURA_WORLD_CONTEXT_STATE__='loading';

      // Never keep CTX LOAD indefinitely. A new viewport or a 12 s
      // timeout invalidates this request without touching the OSM base.
      worldContextTimeoutTimer=setTimeout(()=>{
        if(requestSeq!==worldContextRequestSeq)return;
        window.__AURA_WORLD_CONTEXT_STATE__='timeout';
        try{requestController.abort('aura_context_timeout');}catch{}
        scheduleDraw();
      },9000);

      const url=
        `/api/map-context?token=${encodeURIComponent(token)}`+
        `&lat=${encodeURIComponent(lat.toFixed(5))}`+
        `&lon=${encodeURIComponent(lon.toFixed(5))}`+
        `&radius_km=${encodeURIComponent(String(Math.round(radiusKm)))}`;

      try{
        const response=await fetch(url,{
          method:'GET',
          cache:'no-store',
          signal:requestController.signal
        });

        if(!response.ok)throw new Error(`context_http_${response.status}`);

        const data=await response.json();
        if(requestSeq!==worldContextRequestSeq)return;
        if(!data?.ok)throw new Error(String(data?.error||'context_invalid'));

        const ctxData={
          key:scheduledKey,
          center_lat:Number(data.center_lat),
          center_lon:Number(data.center_lon),
          radius_km:Number(data.radius_km),
          coastlines:Array.isArray(data.coastlines)?data.coastlines:[],
          cities:Array.isArray(data.cities)?data.cities:[],
          source:String(data.source||'openstreetmap-overpass'),
          cache_state:String(data.cache_state||'network')
        };

        worldContext=ctxData;
        worldContextCache.set(scheduledKey,ctxData);
        if(worldContextCache.size>18){
          const first=worldContextCache.keys().next().value;
          worldContextCache.delete(first);
        }

        worldContextLoadedKey=scheduledKey;
        worldContextPendingKey='';
        geoRenderKey='';

        if(worldContextTimeoutTimer){
          clearTimeout(worldContextTimeoutTimer);
          worldContextTimeoutTimer=0;
        }

        window.__AURA_WORLD_CONTEXT_STATE__=ctxData.cache_state==='cache'?'cache':'live';
        scheduleDraw();
      }catch(err){
        if(requestSeq!==worldContextRequestSeq)return;

        if(worldContextTimeoutTimer){
          clearTimeout(worldContextTimeoutTimer);
          worldContextTimeoutTimer=0;
        }

        worldContextPendingKey='';

        if(err?.name==='AbortError'){
          if(window.__AURA_WORLD_CONTEXT_STATE__!=='timeout'){
            window.__AURA_WORLD_CONTEXT_STATE__='idle';
          }
          scheduleDraw();
          return;
        }

        window.__AURA_WORLD_CONTEXT_STATE__='unavailable';
        console.warn?.('AURA map context unavailable',err);
        scheduleDraw();
      }
    },900);
  }

  function overlayDynamicCoastlines(w,h,vp){
    // Old cached / dynamic coast geometry must never override the factual
    // OSM coastline when the user is in local/detail view.
    if(tileBaseActive(vp) && vp.latSpan<AURA_WORLD_COAST_MIN_LATSPAN)return false;

    const context=dynamicContextForViewport(vp);
    if(!context || !geoOverlay)return false;

    let drawn=0;
    for(const coast of context.coastlines||[]){
      if(!Array.isArray(coast)||coast.length<2)continue;

      overlayPath(coast,w,h,vp,{
        stroke:'rgba(112,224,239,.78)',
        'stroke-width':1.05,
        'stroke-linejoin':'round',
        'stroke-linecap':'round',
        filter:'url(#auraGeoSoftGlow)',
        'class':'aura-geo-dynamic-coast'
      });

      overlayPath(coast,w,h,vp,{
        stroke:'rgba(36,135,171,.16)',
        'stroke-width':3.4,
        'stroke-linejoin':'round',
        'stroke-linecap':'round',
        'class':'aura-geo-dynamic-coast-glow'
      });

      drawn++;
    }
    return drawn>0;
  }

  function overlayDynamicNearbyCities(w,h,vp){
    // OSM labels are already detailed and factual in local/detail view.
    // Aura-specific nearby-city labels are reserved for regional context.
    if(tileBaseActive(vp) && vp.latSpan<AURA_CITY_CONTEXT_MIN_LATSPAN)return;

    const context=dynamicContextForViewport(vp);
    if(!context || !geoOverlay || !Array.isArray(context.cities))return;

    const focusLat=num(payload?.latitude,vp.lat);
    const focusLon=num(payload?.longitude,vp.lon);
    const targetName=normalizedPlaceName();

    const maxLabels=Math.min(
      AURA_NEARBY_CITY_LABEL_CAP,
      vp.zoom<.65 ? 7 : 10
    );

    const visible=context.cities
      .filter(city=>{
        const key=norm(city.n||'')
          .toLowerCase()
          .normalize('NFD')
          .replace(/[\u0300-\u036f]/g,'');

        if(!key || key===targetName)return false;

        return (
          Number(city.lat)>vp.lat-vp.latSpan*.60 &&
          Number(city.lat)<vp.lat+vp.latSpan*.60 &&
          Math.abs(lonDelta(Number(city.lon),vp.lon))<vp.lonSpan*.60
        );
      })
      .map(city=>({
        city,
        dist:sqDist(
          Number(city.lat),Number(city.lon),
          focusLat,focusLon
        )
      }));

    const majors=visible
      .filter(x=>(Number(x.city.p)||0)>=8)
      .sort((a,b)=>(Number(b.city.p)||0)-(Number(a.city.p)||0)||a.dist-b.dist);

    const nearest=visible
      .slice()
      .sort((a,b)=>a.dist-b.dist)
      .slice(0,vp.zoom<.9?5:7);

    const towns=visible
      .filter(x=>(Number(x.city.p)||0)>=6)
      .sort((a,b)=>(Number(b.city.p)||0)-(Number(a.city.p)||0)||a.dist-b.dist);

    const byName=new Map();
    for(const item of [...majors,...nearest,...towns]){
      const n=String(item.city.n||'').trim();
      if(n)byName.set(n,item);
    }

    // The user asked for a nearby-city context, not a list of the biggest
    // cities anywhere in the request radius. Rank the selected pool by true
    // proximity to the requested weather location, with importance only as
    // a tie-breaker.
    const candidates=[...byName.values()]
      .sort((a,b)=>
        a.dist-b.dist ||
        (Number(b.city.p)||0)-(Number(a.city.p)||0)
      )
      .slice(0,AURA_NEARBY_CITY_LABEL_CAP*2);

    const [tx,ty]=project(focusLat,focusLon,w,h,vp);

    const occupied=[
      {x:w-240,y:48,w:238,h:Math.max(120,h-104)},
      {x:8,y:8,w:390,h:58}
    ];

    if(tx>-40&&tx<w+40&&ty>-40&&ty<h+40){
      occupied.unshift({x:tx-16,y:ty-18,w:232,h:38});
    }

    const offsets=[
      [-13,-20,'end'],
      [13,-20,'start'],
      [-13,18,'end'],
      [13,18,'start'],
      [-20,-36,'end'],
      [20,34,'start'],
      [-30,34,'end'],
      [30,-42,'start'],
      [-38,-5,'end'],
      [38,-5,'start']
    ];

    let drawn=0;

    for(const item of candidates){
      if(drawn>=maxLabels)break;

      const city=item.city;
      const [x,y]=project(Number(city.lat),Number(city.lon),w,h,vp);
      if(x<20||x>w-238||y<20||y>h-44)continue;

      const importance=Number(city.p)||0;
      const major=importance>=8;
      const fontSize=importance>=11?10.6:importance>=8?9.5:8.2;
      const label=String(city.n||'').trim();
      const approxW=Math.max(34,label.length*(fontSize*.59)+(major?8:14));
      const boxH=major?17:18;

      let placement=null;
      for(const off of offsets){
        const [dx,dy,anchorText]=off;
        const bx=anchorText==='end' ? x+dx-approxW : x+dx;
        const by=y+dy-boxH/2;
        const rect={x:bx,y:by,w:approxW,h:boxH};

        if(bx<4||by<3||bx+approxW>w-238||by+boxH>h-38)continue;
        if(overlayRectCollides(rect,occupied,major?4:3))continue;

        placement={dx,dy,anchorText,rect};
        break;
      }
      if(!placement)continue;

      occupied.push(placement.rect);

      const group=svgNode('g',{
        'class':major
          ?'aura-geo-city aura-geo-city-major aura-geo-city-world'
          :'aura-geo-city aura-geo-city-local aura-geo-city-world'
      });

      group.appendChild(svgNode('circle',{
        cx:x.toFixed(1),
        cy:y.toFixed(1),
        r:major?2.7:1.9,
        fill:major?'rgba(157,239,248,.94)':'rgba(101,198,218,.75)'
      }));

      const lineEndX=placement.anchorText==='end'
        ?placement.rect.x+placement.rect.w
        :placement.rect.x;
      const lineEndY=placement.rect.y+placement.rect.h*.5;

      group.appendChild(svgNode('line',{
        x1:x.toFixed(1),y1:y.toFixed(1),
        x2:lineEndX.toFixed(1),y2:lineEndY.toFixed(1),
        stroke:major?'rgba(108,204,220,.23)':'rgba(96,182,202,.17)',
        'stroke-width':major?.7:.55
      }));

      if(!major){
        group.appendChild(svgNode('rect',{
          x:placement.rect.x.toFixed(1),
          y:placement.rect.y.toFixed(1),
          width:placement.rect.w.toFixed(1),
          height:placement.rect.h,
          rx:4,
          fill:'rgba(1,11,18,.72)',
          stroke:'rgba(92,205,224,.11)',
          'stroke-width':.55
        }));
      }

      const text=svgNode('text',{
        x:(placement.anchorText==='end'
          ?placement.rect.x+placement.rect.w-(major?2:5)
          :placement.rect.x+(major?2:5)).toFixed(1),
        y:(placement.rect.y+(major?11.7:12.2)).toFixed(1),
        'text-anchor':placement.anchorText,
        fill:major?'rgba(218,244,248,.94)':'rgba(171,215,225,.82)',
        'font-size':fontSize,
        'font-family':'system-ui, sans-serif',
        'font-weight':major?650:540,
        'letter-spacing':major?'.025em':'.015em'
      });

      text.textContent=label;
      group.appendChild(text);
      geoOverlay.appendChild(group);
      drawn++;
    }
  }


  function atlasFor(lat,lon){
    lat=Number(lat);lon=Number(lon);
    for(const atlas of Object.values(LOCAL_CONTEXT)){
      const b=atlas.bounds;
      if(lat>=b.latMin&&lat<=b.latMax&&lon>=b.lonMin&&lon<=b.lonMax)return atlas;
    }
    return null;
  }

  function sqDist(aLat,aLon,bLat,bLon){
    const dx=lonDelta(aLon,bLon)*Math.max(.45,Math.abs(Math.cos(((aLat+bLat)*.5)*Math.PI/180)));
    const dy=Number(aLat)-Number(bLat);
    return dx*dx+dy*dy;
  }

  function currentAtlas(){
    const lat=num(payload?.latitude, num(field?.center_latitude, null));
    const lon=num(payload?.longitude, num(field?.center_longitude, null));
    if(lat==null||lon==null)return null;
    return atlasFor(lat,lon);
  }

  function atlasKeyAt(lat,lon){
    if(lat==null||lon==null)return null;
    for(const [key,atlas] of Object.entries(LOCAL_CONTEXT)){
      const b=atlas.bounds;
      if(lat>=b.latMin&&lat<=b.latMax&&lon>=b.lonMin&&lon<=b.lonMax)return key;
    }
    return null;
  }

  function atlasForViewport(vp){
    if(!vp)return null;
    const key=atlasKeyAt(vp.lat,vp.lon);
    return key ? LOCAL_CONTEXT[key] : null;
  }

  function localCartoForViewport(vp){
    if(!vp)return null;
    const key=atlasKeyAt(vp.lat,vp.lon);
    return key ? (window.AURA_P0525_LOCAL_CARTO?.[key] || null) : null;
  }

  function currentAtlasKey(){
    const lat=num(payload?.latitude, num(field?.center_latitude, null));
    const lon=num(payload?.longitude, num(field?.center_longitude, null));
    if(lat==null||lon==null)return null;
    for(const [key,atlas] of Object.entries(LOCAL_CONTEXT)){
      const b=atlas.bounds;
      if(lat>=b.latMin&&lat<=b.latMax&&lon>=b.lonMin&&lon<=b.lonMax)return key;
    }
    return null;
  }

  function currentHiResCarto(vp=null){
    if(vp)return localCartoForViewport(vp);
    const key=currentAtlasKey();
    if(!key)return null;
    return window.AURA_P0525_LOCAL_CARTO?.[key] || null;
  }

  function nearestAtlasCity(atlas,lat,lon){
    if(!atlas?.cities?.length||lat==null||lon==null)return null;
    let best=null, bestD=Infinity;
    for(const city of atlas.cities){
      const d=sqDist(city.lat,city.lon,lat,lon);
      if(d<bestD){best=city;bestD=d;}
    }
    return best;
  }

  function drawPolyline(points,w,h,vp,stroke,alpha=1,width=1.2,dash=null){
    if(!points?.length)return;
    ctx.save();
    ctx.strokeStyle=stroke;ctx.lineWidth=width; if(dash)ctx.setLineDash(dash);
    ctx.beginPath();
    let moved=false;
    for(const pt of points){
      const [x,y]=project(pt[1],pt[0],w,h,vp);
      if(!moved){ctx.moveTo(x,y);moved=true;} else ctx.lineTo(x,y);
    }
    ctx.globalAlpha=alpha;
    ctx.stroke();
    ctx.restore();
  }

  function normalizedPlaceName(){
    return norm(payload?.place_label||payload?.location||'')
      .split(',')[0]
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g,'');
  }

  function rectsOverlap(a,b,pad=3){
    return !(
      a.x+a.w+pad < b.x ||
      b.x+b.w+pad < a.x ||
      a.y+a.h+pad < b.y ||
      b.y+b.h+pad < a.y
    );
  }

  function cityLodMinPriority(z){
    if(z<.62)return 7;
    if(z<.90)return 6;
    if(z<1.35)return 5;
    if(z<2.10)return 4;
    return 3;
  }

  function cityLodLimit(z){
    const requested=
      z<.62 ? 6 :
      z<.90 ? 8 :
      10;

    return Math.min(AURA_NEARBY_CITY_LABEL_CAP,requested);
  }

  function drawRegionalAtlas(w,h,vp){
    const atlas=currentAtlas();
    if(!atlas)return;

    const focusLat=num(payload?.latitude,vp.lat);
    const focusLon=num(payload?.longitude,vp.lon);
    const targetName=normalizedPlaceName();

    const coastSets=[];
    if(Array.isArray(atlas.coast) && atlas.coast.length>1)coastSets.push(atlas.coast);
    if(Array.isArray(atlas.coasts)){
      for(const coast of atlas.coasts){
        if(Array.isArray(coast) && coast.length>1)coastSets.push(coast);
      }
    }
    for(const coast of coastSets){
      drawPolyline(coast,w,h,vp,'rgba(126,232,248,.72)',.98,2.0);
      drawPolyline(coast,w,h,vp,'rgba(48,143,177,.20)',.88,5.0);
    }

    if(Array.isArray(atlas.borderFI) && atlas.borderFI.length>1){
      drawPolyline(atlas.borderFI,w,h,vp,'rgba(197,224,236,.42)',.96,1.25,[5,4]);
    }

    const minPriority=cityLodMinPriority(vp.zoom);
    const maxLabels=Math.min(
      AURA_NEARBY_CITY_LABEL_CAP,
      cityLodLimit(vp.zoom)
    );

    const allVisible=(atlas.cities||[])
      .filter(city=>{
        const cityKey=norm(city.n).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
        if(cityKey===targetName)return false;
        return (
          city.lat>vp.lat-vp.latSpan*.58 &&
          city.lat<vp.lat+vp.latSpan*.58 &&
          Math.abs(lonDelta(city.lon,vp.lon))<vp.lonSpan*.58
        );
      })
      .map(city=>({
        city,
        dist:sqDist(city.lat,city.lon,focusLat,focusLon)
      }));

    const nearest=allVisible.slice().sort((a,b)=>a.dist-b.dist).slice(0,5);
    const prioritized=allVisible.filter(x=>(x.city.p||0)>=minPriority);

    const byName=new Map();
    for(const item of [...nearest,...prioritized]){
      byName.set(item.city.n,item);
    }

    const visible=[...byName.values()]
      .sort((a,b)=>
        a.dist-b.dist ||
        (b.city.p||0)-(a.city.p||0)
      )
      .slice(0,AURA_NEARBY_CITY_LABEL_CAP*2);

    const [tx,ty]=project(focusLat,focusLon,w,h,vp);
    const occupied=[
      {x:tx+10,y:ty-14,w:220,h:28},
      {x:w-235,y:46,w:230,h:Math.max(120,h-105)}
    ];

    const offsets=[
      [-12,-20,'left'],
      [-12,12,'left'],
      [12,-26,'right'],
      [12,18,'right'],
      [-18,-38,'left'],
      [18,34,'right'],
      [-28,34,'left'],
      [28,-42,'right']
    ];

    ctx.save();
    let drawn=0;

    for(const item of visible){
      if(drawn>=maxLabels)break;

      const city=item.city;
      const [x,y]=project(city.lat,city.lon,w,h,vp);
      if(x<18||x>w-242||y<20||y>h-42)continue;

      const priority=city.p||0;
      const isNear=nearest.some(n=>n.city.n===city.n);
      const fontSize=priority>=9?10:priority>=7?9:8;
      const weight=(priority>=8||isNear)?600:500;

      ctx.font=`${weight} ${fontSize}px system-ui`;
      const textW=Math.ceil(ctx.measureText(city.n).width);
      const boxW=textW+14, boxH=18;

      let placement=null;
      for(const off of offsets){
        const side=off[2];
        const bx=side==='left' ? x+off[0]-boxW : x+off[0];
        const by=y+off[1]-boxH/2;
        const box={x:bx,y:by,w:boxW,h:boxH};

        if(bx<4||by<3||bx+boxW>w-235||by+boxH>h-36)continue;
        if(occupied.some(r=>rectsOverlap(box,r,3)))continue;

        placement={box,side,dx:off[0],dy:off[1]};
        break;
      }
      if(!placement)continue;

      occupied.push(placement.box);

      ctx.beginPath();
      ctx.fillStyle=(priority>=8||isNear)
        ?'rgba(151,241,251,.88)'
        :'rgba(117,200,219,.64)';
      ctx.arc(x,y,(priority>=8||isNear)?2.3:1.7,0,Math.PI*2);
      ctx.fill();

      const lineEndX=placement.side==='left'
        ? placement.box.x+placement.box.w
        : placement.box.x;
      const lineEndY=placement.box.y+placement.box.h*.5;

      ctx.save();
      ctx.strokeStyle='rgba(103,200,220,.22)';
      ctx.lineWidth=.7;
      ctx.beginPath();
      ctx.moveTo(x,y);
      ctx.lineTo(lineEndX,lineEndY);
      ctx.stroke();
      ctx.restore();

      ctx.fillStyle=(priority>=8||isNear)
        ?'rgba(222,248,252,.88)'
        :'rgba(154,208,221,.64)';
      ctx.shadowColor='rgba(0,7,12,.98)';
      ctx.shadowBlur=7;
      ctx.textAlign=placement.side==='left'?'right':'left';

      const textX=placement.side==='left'
        ? placement.box.x+placement.box.w-3
        : placement.box.x+3;
      const textY=placement.box.y+12;
      ctx.fillText(city.n,textX,textY);
      drawn++;
    }

    ctx.restore();

    if(atlas.name){
      ctx.save();
      ctx.font='600 9px system-ui';
      ctx.fillStyle='rgba(103,198,220,.30)';
      ctx.textAlign='left';
      ctx.fillText(atlas.name,24,54);
      ctx.restore();
    }
  }


  function localCurrentFor(layer){
    if(!payload)return null;
    const map={
      wind:payload.wind_speed,
      rain:payload.precipitation,
      temperature:payload.temperature,
      clouds:payload.cloud_cover,
      pressure:payload.pressure_msl ?? payload.pressure,
      waves:null
    };
    const value=map[layer];
    if(!finite(value))return null;
    if(layer==='rain')return {value:Number(value),unit:'mm'};
    return {value:Number(value),unit:LAYERS[layer]?.unit||''};
  }

  function fieldClock(){
    const times=field?.times||[];
    const stamp=times[Math.min(timeIndex,Math.max(0,times.length-1))]||'';
    return stamp ? String(stamp).slice(11,16) : `T+${timeIndex}H`;
  }

  function updateDetails(){
    if(!shell)return;
    const cp=centerPoint(); const h=fieldHour(cp);
    const vals=valuesFor(); const lo=vals.length?Math.min(...vals):null, hi=vals.length?Math.max(...vals):null;
    const def=LAYERS[activeLayer];
    const value={
      wind:h.wind_speed,rain:h.rain_probability,temperature:h.temperature,clouds:h.cloud_cover,
      pressure:h.pressure,waves:null
    }[activeLayer];

    const semanticTitle={
      wind:'VENT · CHAMP',
      rain:'PLUIE · PROBABILITÉ',
      temperature:'TEMPÉRATURE · CHAMP',
      clouds:'NUAGES · COUVERTURE',
      waves:'VAGUES · MARINE',
      pressure:'PRESSION · CHAMP'
    }[activeLayer]||`${def.label} · CHAMP`;

    shell.querySelector('#auraWxLayerName').textContent=semanticTitle;
    shell.querySelector('#auraWxLayerValue').textContent=value==null?'—':`${fmt(value,activeLayer==='temperature'?1:0)} ${def.unit}`;
    shell.querySelector('#auraWxLayerRange').textContent=(lo==null||hi==null)?'—':`${fmt(lo,activeLayer==='temperature'?1:0)}–${fmt(hi,activeLayer==='temperature'?1:0)} ${def.unit}`;
    shell.querySelector('#auraWxWindDir').textContent=finite(h.wind_direction ?? payload?.wind_direction)?`DE ${compass(h.wind_direction ?? payload?.wind_direction)}`:'—';
    shell.querySelector('#auraWxGust').textContent=finite(h.wind_gusts ?? payload?.wind_gusts)?`${fmt(h.wind_gusts ?? payload?.wind_gusts,0)} km/h`:'—';
    shell.querySelector('#auraWxPressure').textContent=finite(h.pressure ?? payload?.pressure_msl ?? payload?.pressure)?`${fmt(h.pressure ?? payload?.pressure_msl ?? payload?.pressure,0)} hPa`:'—';
    shell.querySelector('#auraWxCloud').textContent=finite(h.cloud_cover ?? payload?.cloud_cover)?`${fmt(h.cloud_cover ?? payload?.cloud_cover,0)} %`:'—';

    const local=localCurrentFor(activeLayer);
    const localEl=shell.querySelector('#auraWxLocalValue');
    const localLabel=shell.querySelector('.aura-wx-detail-local span');
    if(localLabel){
      localLabel.textContent=activeLayer==='rain'?'PRÉCIP. ACTUELLES':'POINT ACTUEL';
    }
    if(localEl){
      localEl.textContent=local ? `${fmt(local.value,activeLayer==='temperature'?1:activeLayer==='rain'?1:0)} ${local.unit}` : '—';
      localEl.parentElement?.classList.toggle('available',!!local);
    }

    const clock=fieldClock();
    shell.querySelector('#auraWxLayerStatus').textContent=activeLayer==='waves'&&!payload?.marine_field?'MARINE N/A':`CHAMP · ${clock}`;
    shell.querySelector('#auraWxFieldClock').textContent=`ÉCHANTILLON ${clock}`;
    shell.querySelector('#auraWxLegendMax').textContent=hi==null?'—':fmt(hi,activeLayer==='temperature'?1:0);
    shell.querySelector('#auraWxLegendMin').textContent=lo==null?'—':fmt(lo,activeLayer==='temperature'?1:0);
    shell.querySelector('#auraWxLegendUnit').textContent=def.unit;
    const legendBar=shell.querySelector('.aura-wx-map-legend i');
    if(legendBar)legendBar.style.background=legendGradientFor(activeLayer);
    shell.dataset.layer=activeLayer;

    const notice=shell.querySelector('#auraWxLayerNotice');
    if(notice){
      let text='';
      if(activeLayer==='rain' && vals.length && Math.max(...vals)<2) text='RISQUE DE PLUIE NUL OU TRÈS FAIBLE · CHAMP HORAIRE';
      else if(activeLayer==='rain' && vals.length) text='COUCHE PLUIE = PROBABILITÉ RÉGIONALE · PRÉCIP. ACTUELLES EN mm';
      else if(activeLayer==='clouds' && vals.length && Math.max(...vals)<5) text='CIEL DÉGAGÉ · COUVERTURE NUAGÉUSE TRÈS FAIBLE';
      else if(activeLayer==='pressure' && !vals.length && finite(payload?.pressure_msl ?? payload?.pressure)) text='PRESSION RÉGIONALE NON FOURNIE · VALEUR LOCALE UNIQUEMENT';
      else if(activeLayer==='waves' && !payload?.marine_field) text='COUCHE MARINE NON CONNECTÉE';
      notice.textContent=text;
      notice.classList.toggle('show',!!text);
    }
  }

  function updateTime(){
    if(!shell)return;
    const times=field?.times||[];
    const stamp=times[Math.min(timeIndex,Math.max(0,times.length-1))]||'';
    shell.querySelector('#auraWxTimeLabel').textContent=stamp?String(stamp).replace('T',' · '):`T+${timeIndex}H`;
    const max=Math.max(1,times.length-1);
    shell.querySelector('#auraWxTimeProgress').style.width=`${clamp(timeIndex/max)*100}%`;
    shell.querySelectorAll('[data-offset]').forEach(b=>b.classList.toggle('active',Number(b.dataset.offset)===timeIndex));
  }

  function togglePlay(){
    const btn=shell?.querySelector('#auraWxPlay');
    if(animationTimer){clearInterval(animationTimer);animationTimer=0;if(btn)btn.textContent='▶';return}
    if(btn)btn.textContent='Ⅱ';
    animationTimer=setInterval(()=>{
      const max=Math.max(0,(field?.times?.length||1)-1);
      timeIndex=max?((timeIndex+1)%(max+1)):0;
      updateTime();updateDetails();scheduleDraw();
    },1050);
  }

  function lonDelta(lon,center){
    let d=Number(lon)-Number(center);
    while(d>180)d-=360; while(d<-180)d+=360; return d;
  }

  function wrapLon(lon){
    let v=Number(lon)||0;
    while(v>180)v-=360;
    while(v<-180)v+=360;
    return v;
  }

  function baseViewportSpans(lat,lon){
    let latSpan=Math.max(1,num(field?.lat_span,6));
    let lonSpan=Math.max(1,num(field?.lon_span,latSpan*1.5));
    const atlas=atlasFor(lat,lon);

    if(atlas?.view){
      latSpan=Math.min(latSpan,Number(atlas.view.lat)||latSpan);

      // P0.5.2.5: local map scale respects geographic proportions.
      // 1° longitude shrinks by cos(latitude), so lon span is derived
      // from the actual map-panel aspect ratio instead of a hand-tuned value.
      const rect=shell?.getBoundingClientRect();
      const aspect=Math.max(1.25,Math.min(3.2,(rect?.width||1200)/Math.max(1,(rect?.height||560))));
      const cosLat=Math.max(.35,Math.abs(Math.cos(Number(lat)*Math.PI/180)));
      lonSpan=latSpan*aspect/cosLat;
    }else if(atlas){
      latSpan=Math.max(2.0,Math.min(3.6,latSpan*.52));
      lonSpan=Math.max(3.0,Math.min(5.4,lonSpan*.52));
    }

    return {latSpan,lonSpan};
  }

  function hasExplicitMapCenter(v){
    return v !== null && v !== undefined && v !== '' && finite(v);
  }

  function viewport(){
    const targetLat=num(payload?.latitude, num(field?.center_latitude,0));
    const targetLon=num(payload?.longitude, num(field?.center_longitude,0));

    // P0.5.2.4.3:
    // Number(null) === 0, therefore finite(null) was true and the map
    // silently opened around 0°N / 0°E instead of the weather location.
    const lat=hasExplicitMapCenter(viewCenterLat)?Number(viewCenterLat):targetLat;
    const lon=hasExplicitMapCenter(viewCenterLon)?Number(viewCenterLon):targetLon;

    const spans=baseViewportSpans(targetLat,targetLon);
    const z=Math.max(MIN_MAP_ZOOM,Math.min(MAX_MAP_ZOOM,zoomFactor||1));

    const rawLatSpan=(spans.latSpan*1.16)/z;
    const latSpan=Math.max(.08,Math.min(150,rawLatSpan));

    // Physical map proportions follow the CURRENT view latitude while panning.
    const rect=shell?.getBoundingClientRect();
    const aspect=Math.max(1.20,Math.min(3.35,(rect?.width||1200)/Math.max(1,(rect?.height||560))));
    const cosLat=Math.max(.30,Math.abs(Math.cos(Number(lat)*Math.PI/180)));
    const lonSpan=Math.max(.12,Math.min(360,latSpan*aspect/cosLat));

    return {
      lat,
      lon,
      targetLat,
      targetLon,
      zoom:z,
      latSpan,
      lonSpan
    };
  }

  function viewportCenterSelfCheck(){
    return (
      hasExplicitMapCenter(null)===false &&
      hasExplicitMapCenter(undefined)===false &&
      hasExplicitMapCenter('')===false &&
      hasExplicitMapCenter(0)===true &&
      hasExplicitMapCenter(43.427)===true
    );
  }

  function recenterMap(){
    zoomFactor=1;
    geoRenderKey='';
    tileRenderKey='';
    viewCenterLat=null;
    viewCenterLon=null;
    dragState=null;
    shell?.classList.remove('map-dragging');
    scheduleDraw();
  }

  function zoomAtCenter(factor){
    const next=Math.max(MIN_MAP_ZOOM,Math.min(MAX_MAP_ZOOM,zoomFactor*factor));
    if(Math.abs(next-zoomFactor)<.0001)return;
    zoomFactor=next;
    scheduleDraw();
  }

  function zoomAtPointer(clientX,clientY,factor){
    if(!canvas)return;
    const rect=canvas.getBoundingClientRect();
    if(rect.width<10||rect.height<10)return;

    const oldVp=viewport();
    const px=Math.max(0,Math.min(1,(clientX-rect.left)/rect.width));
    const py=Math.max(0,Math.min(1,(clientY-rect.top)/rect.height));

    const next=Math.max(MIN_MAP_ZOOM,Math.min(MAX_MAP_ZOOM,zoomFactor*factor));
    if(Math.abs(next-zoomFactor)<.0001)return;

    if(tileBaseActive(oldVp)){
      const oldZ=tileZoomForViewport(oldVp,rect.width);

      const anchorWorldX=
        mercatorWorldX(oldVp.lon,oldZ)+(px-.5)*rect.width;
      const anchorWorldY=
        mercatorWorldY(oldVp.lat,oldZ)+(py-.5)*rect.height;

      const anchorLon=mercatorLonFromWorldX(anchorWorldX,oldZ);
      const anchorLat=mercatorLatFromWorldY(anchorWorldY,oldZ);

      viewCenterLat=oldVp.lat;
      viewCenterLon=oldVp.lon;
      zoomFactor=next;

      const newVp=viewport();
      const newZ=tileZoomForViewport(newVp,rect.width);

      const centerWorldX=
        mercatorWorldX(anchorLon,newZ)-(px-.5)*rect.width;
      const centerWorldY=
        mercatorWorldY(anchorLat,newZ)-(py-.5)*rect.height;

      viewCenterLon=mercatorLonFromWorldX(centerWorldX,newZ);
      viewCenterLat=Math.max(
        -82,
        Math.min(82,mercatorLatFromWorldY(centerWorldY,newZ))
      );

      scheduleDraw();
      return;
    }

    const anchorLon=wrapLon(oldVp.lon+(px-.5)*oldVp.lonSpan);
    const anchorLat=oldVp.lat+(.5-py)*oldVp.latSpan;

    viewCenterLat=oldVp.lat;
    viewCenterLon=oldVp.lon;
    zoomFactor=next;

    const newVp=viewport();
    viewCenterLon=wrapLon(anchorLon-(px-.5)*newVp.lonSpan);
    viewCenterLat=Math.max(-82,Math.min(82,anchorLat-(.5-py)*newVp.latSpan));

    scheduleDraw();
  }

  function mercatorClampLat(lat){
    return Math.max(-85.05112878,Math.min(85.05112878,Number(lat)||0));
  }

  function mercatorWorldX(lon,z){
    const world=256*Math.pow(2,z);
    return (wrapLon(lon)+180)/360*world;
  }

  function mercatorWorldY(lat,z){
    const world=256*Math.pow(2,z);
    const φ=mercatorClampLat(lat)*Math.PI/180;
    const s=Math.sin(φ);
    return (.5-Math.log((1+s)/(1-s))/(4*Math.PI))*world;
  }

  function mercatorLonFromWorldX(x,z){
    const world=256*Math.pow(2,z);
    return wrapLon((Number(x)/world)*360-180);
  }

  function mercatorLatFromWorldY(y,z){
    const world=256*Math.pow(2,z);
    const yy=Math.max(0,Math.min(world,Number(y)));
    const n=Math.PI-(2*Math.PI*yy/world);
    return mercatorClampLat((180/Math.PI)*Math.atan(Math.sinh(n)));
  }

  function tileZoomForViewport(vp,w){
    const byWidth=Math.log2(Math.max(1,(360*Math.max(256,w))/(256*Math.max(.01,vp.lonSpan))));
    return Math.max(
      TILE_PROVIDER.minZoom||2,
      Math.min(TILE_PROVIDER.maxZoom||15,Math.round(byWidth))
    );
  }

  function tileBaseWanted(vp){
    // P0.5.2.7.1: same-origin loopback proxy. Browser online/offline state
    // does not decide availability; Aura shell serves cache or upstream.
    return !!(
      tileLayer &&
      token &&
      vp &&
      vp.latSpan<=(TILE_PROVIDER.localLatSpanMax||14)
    );
  }

  function clearTileLayer(){
    if(!tileLayer)return;
    for(const node of tileNodes.values())node.remove();
    tileNodes.clear();
    tileLayer.replaceChildren();
    tileLayer.classList.remove('ready');
    tileReady=false;
    tileRenderKey='';
  }

  function tileUrl(z,x,y){
    return String(TILE_PROVIDER.template||'')
      .replace('{z}',String(z))
      .replace('{x}',String(x))
      .replace('{y}',String(y))
      .replace('{token}',encodeURIComponent(token));
  }

  function updateTileAttribution(active){
    if(!tileAttribution)return;
    tileAttribution.textContent=active
      ?`${TILE_PROVIDER.attribution||'© OpenStreetMap contributors'} · AURA MAP LIVE`
      :(tileErrorBurst>0?'AURA MAP PROXY INDISPONIBLE · VECTOR':'AURA MAP PROXY · VECTOR FALLBACK');
    tileAttribution.classList.toggle('online',!!active);
  }

  function tileBaseActive(vp){
    return tileBaseWanted(vp) && tileReady;
  }

  function renderOnlineTiles(w,h,vp){
    if(!tileLayer)return;

    if(!tileBaseWanted(vp)){
      tileLayer.style.opacity='0';
      updateTileAttribution(false);
      return;
    }

    const z=tileZoomForViewport(vp,w);
    const n=Math.pow(2,z);
    const cx=mercatorWorldX(vp.lon,z);
    const cy=mercatorWorldY(vp.lat,z);
    const left=cx-w*.5;
    const top=cy-h*.5;

    const minRawX=Math.floor(left/256);
    const maxRawX=Math.floor((left+w)/256);
    const minY=Math.max(0,Math.floor(top/256));
    const maxY=Math.min(n-1,Math.floor((top+h)/256));

    const key=[
      z,
      Math.round(left),
      Math.round(top),
      Math.round(w),
      Math.round(h)
    ].join('|');

    if(key===tileRenderKey){
      tileLayer.style.opacity=tileReady?'1':'0';
      updateTileAttribution(tileReady);
      return;
    }
    tileRenderKey=key;

    const wanted=new Set();
    let requested=0;

    for(let rawX=minRawX;rawX<=maxRawX;rawX++){
      const x=((rawX%n)+n)%n;
      for(let y=minY;y<=maxY;y++){
        const id=`${z}/${rawX}/${y}`;
        wanted.add(id);
        requested++;

        let img=tileNodes.get(id);
        if(!img){
          img=document.createElement('img');
          img.className='aura-wx-map-tile';
          img.alt='';
          img.decoding='async';
          img.loading='eager';
          img.referrerPolicy='strict-origin-when-cross-origin';
          img.dataset.tileId=id;

          img.addEventListener('load',()=>{
            tileReady=true;
            tileErrorBurst=0;
            window.__AURA_MAP_TILE_PROXY_STATE__='ready';
            window.__AURA_MAP_TILE_COMPOSITE_STATE__='visible';
            tileLayer?.classList.add('ready');
            if(tileLayer)tileLayer.style.opacity='1';
            updateTileAttribution(true);
            geoRenderKey='';
            try{
              const liveVp=viewport();
              scheduleWorldContext(liveVp);
            }catch{}
            scheduleDraw();
          });

          img.addEventListener('error',()=>{
            tileErrorBurst++;
            window.__AURA_MAP_TILE_PROXY_STATE__='error';
            if(tileErrorBurst>=Math.max(4,Math.ceil(requested*.6))){
              tileReady=false;
              tileLayer?.classList.remove('ready');
              if(tileLayer)tileLayer.style.opacity='0';
              updateTileAttribution(false);
              geoRenderKey='';
              scheduleDraw();
            }
          });

          img.src=tileUrl(z,x,y);
          tileNodes.set(id,img);
          tileLayer.appendChild(img);
        }

        img.style.left=`${rawX*256-left}px`;
        img.style.top=`${y*256-top}px`;
        img.style.width='256px';
        img.style.height='256px';
        img.style.display='block';
      }
    }

    for(const [id,img] of [...tileNodes.entries()]){
      if(!wanted.has(id)){
        img.remove();
        tileNodes.delete(id);
      }
    }

    tileLayer.style.opacity=tileReady?'1':'0';
    updateTileAttribution(tileReady);
  }

  function project(lat,lon,w,h,vp){
    // P0.5.2.8.4:
    // When OpenStreetMap raster tiles are visible, every Aura overlay must
    // use THE SAME Web Mercator pixel plane and integer tile zoom.
    //
    // The previous latitude-linear projection kept the centre correct but
    // progressively displaced coastlines/cities away from the centre.
    if(tileBaseActive(vp)){
      const z=tileZoomForViewport(vp,w);
      const world=256*Math.pow(2,z);

      const cx=mercatorWorldX(vp.lon,z);
      const cy=mercatorWorldY(vp.lat,z);
      const px=mercatorWorldX(lon,z);
      const py=mercatorWorldY(lat,z);

      let dx=px-cx;
      if(dx>world*.5)dx-=world;
      else if(dx<-world*.5)dx+=world;

      return [
        w*.5+dx,
        h*.5+(py-cy)
      ];
    }

    // Offline/global vector fallback preserves the historical projection.
    return [
      w*(.5+lonDelta(lon,vp.lon)/vp.lonSpan),
      h*(.5-(Number(lat)-vp.lat)/vp.latSpan)
    ];
  }

  const SVG_NS='http://www.w3.org/2000/svg';

  function svgNode(name,attrs={}){
    const el=document.createElementNS(SVG_NS,name);
    for(const [k,v] of Object.entries(attrs)){
      if(v!=null)el.setAttribute(k,String(v));
    }
    return el;
  }

  function overlayPolygon(points,w,h,vp,attrs={}){
    if(!geoOverlay || !Array.isArray(points) || points.length<3)return null;

    let d='';
    let started=false;
    let lastX=null;
    for(const pt of points){
      if(!pt || pt.length<2)continue;
      const [x,y]=project(pt[1],pt[0],w,h,vp);
      if(lastX!=null && Math.abs(x-lastX)>w*.72){
        started=false;
        lastX=x;
        continue;
      }
      if(!started){
        d+=`M${x.toFixed(1)},${y.toFixed(1)}`;
        started=true;
      }else{
        d+=`L${x.toFixed(1)},${y.toFixed(1)}`;
      }
      lastX=x;
    }
    if(!d)return null;
    d+='Z';

    const path=svgNode('path',{
      d,
      'vector-effect':'non-scaling-stroke',
      ...attrs
    });
    geoOverlay.appendChild(path);
    return path;
  }

  function overlayPath(points,w,h,vp,attrs={}){
    if(!geoOverlay || !Array.isArray(points) || points.length<2)return null;
    let d='';
    let started=false;
    let lastX=null;

    for(const pt of points){
      if(!pt || pt.length<2)continue;
      const [x,y]=project(pt[1],pt[0],w,h,vp);

      if(lastX!=null && Math.abs(x-lastX)>w*.68){
        started=false;
        lastX=x;
        continue;
      }

      if(!started){
        d+=`M${x.toFixed(1)},${y.toFixed(1)}`;
        started=true;
      }else{
        d+=`L${x.toFixed(1)},${y.toFixed(1)}`;
      }
      lastX=x;
    }

    if(!d)return null;
    const path=svgNode('path',{
      d,
      fill:'none',
      'vector-effect':'non-scaling-stroke',
      ...attrs
    });
    geoOverlay.appendChild(path);
    return path;
  }

  function overlayStableWorldPath(points,w,h,vp,attrs={}){
    if(!geoOverlay || !Array.isArray(points) || points.length<2)return null;

    let d='';
    let started=false;
    let last=null;

    const maxJump=
      vp.latSpan<3
        ?Math.max(80,Math.min(w,h)*.19)
        :vp.latSpan<7
          ?Math.max(120,Math.min(w,h)*.28)
          :Math.max(180,Math.min(w,h)*.42);

    for(const pt of points){
      if(!pt || pt.length<2)continue;

      const cur=project(pt[1],pt[0],w,h,vp);
      const x=cur[0],y=cur[1];

      if(last){
        const dx=x-last[0];
        const dy=y-last[1];
        const dist=Math.hypot(dx,dy);

        // Never invent a long cyan chord between generalized or
        // disconnected source points.
        if(
          Math.abs(dx)>w*.55 ||
          Math.abs(dy)>h*.55 ||
          dist>maxJump
        ){
          started=false;
        }
      }

      if(!started){
        d+=`M${x.toFixed(1)},${y.toFixed(1)}`;
        started=true;
      }else{
        d+=`L${x.toFixed(1)},${y.toFixed(1)}`;
      }

      last=cur;
    }

    if(!d)return null;

    const path=svgNode('path',{
      d,
      fill:'none',
      'vector-effect':'non-scaling-stroke',
      ...attrs
    });

    geoOverlay.appendChild(path);
    return path;
  }


  function globalBBoxVisible(b,vp,pad=.03){
    if(!Array.isArray(b)||b.length<4)return true;

    const minLat=Number(b[1]),maxLat=Number(b[3]);
    const padLat=vp.latSpan*pad;
    if(maxLat<vp.lat-vp.latSpan*.5-padLat || minLat>vp.lat+vp.latSpan*.5+padLat)return false;

    if(vp.lonSpan>=350)return true;

    const minLon=Number(b[0]),maxLon=Number(b[2]);
    const center=(minLon+maxLon)*.5;
    const half=Math.abs(maxLon-minLon)*.5;
    const d=Math.abs(lonDelta(center,vp.lon));
    return d <= vp.lonSpan*.5 + half + vp.lonSpan*pad;
  }

  function globalCartoResolution(vp){
    const g=window.AURA_P0526_GLOBAL_CARTO;
    if(!g)return null;
    return vp.latSpan<=42 ? g.intermediate : g.low;
  }

  function renderGlobalLand(w,h,vp){
    const g=window.AURA_P0526_GLOBAL_CARTO?.low;
    if(!g)return;

    for(const item of g.land||[]){
      if(!globalBBoxVisible(item.b,vp,.04))continue;
      overlayPolygon(item.p,w,h,vp,{
        fill:'rgba(8,29,38,.36)',
        stroke:'none'
      });
    }

    for(const item of g.water||[]){
      if(!globalBBoxVisible(item.b,vp,.04))continue;
      overlayPolygon(item.p,w,h,vp,{
        fill:'rgba(1,11,19,.30)',
        stroke:'none'
      });
    }
  }

  function renderGlobalLines(w,h,vp){
    const data=globalCartoResolution(vp);
    if(!data)return;

    for(const item of data.coast||[]){
      if(!globalBBoxVisible(item.b,vp,.04))continue;
      overlayStableWorldPath(item.p,w,h,vp,{
        stroke:vp.latSpan<10?'rgba(112,224,239,.72)':'rgba(112,207,223,.52)',
        'stroke-width':vp.latSpan<10?1.0:.78,
        'stroke-linejoin':'round',
        'stroke-linecap':'round',
        filter:vp.latSpan<10?'url(#auraGeoSoftGlow)':null
      });
    }

    for(const item of data.borders||[]){
      if(!globalBBoxVisible(item.b,vp,.025))continue;
      overlayStableWorldPath(item.p,w,h,vp,{
        stroke:'rgba(173,205,216,.27)',
        'stroke-width':vp.latSpan<10?.78:.62,
        'stroke-dasharray':vp.latSpan<28?'4 5':'3 6',
        'stroke-linecap':'round'
      });
    }
  }

  function overlayCountryLabels(w,h,vp){
    if(!geoOverlay)return;
    const list=window.AURA_P0526_GLOBAL_CARTO?.countries||[];
    if(!list.length)return;

    const maxLabels=
      vp.latSpan>100?24:
      vp.latSpan>55?30:
      vp.latSpan>25?24:
      vp.latSpan>10?18:
      10;

    const minPop=
      vp.latSpan>100?25000000:
      vp.latSpan>55?12000000:
      vp.latSpan>25?5000000:
      vp.latSpan>10?1500000:
      0;

    const visible=list
      .filter(c=>{
        if((c.pop||0)<minPop)return false;
        if(c.lat<vp.lat-vp.latSpan*.48||c.lat>vp.lat+vp.latSpan*.48)return false;
        return vp.lonSpan>=350 || Math.abs(lonDelta(c.lon,vp.lon))<vp.lonSpan*.48;
      })
      .sort((a,b)=>(b.pop||0)-(a.pop||0))
      .slice(0,maxLabels);

    const occupied=[];
    for(const c of visible){
      const [x,y]=project(c.lat,c.lon,w,h,vp);
      if(x<45||x>w-260||y<34||y>h-50)continue;

      const font=vp.latSpan>55?8.4:9.0;
      const approxW=Math.max(38,c.n.length*font*.58);
      const rect={x:x-approxW*.5,y:y-9,w:approxW,h:18};
      if(overlayRectCollides(rect,occupied,5))continue;
      occupied.push(rect);

      const text=svgNode('text',{
        x:x.toFixed(1),
        y:y.toFixed(1),
        'text-anchor':'middle',
        fill:'rgba(145,194,207,.26)',
        'font-size':font,
        'font-family':'system-ui, sans-serif',
        'font-weight':600,
        'letter-spacing':'.11em',
        'class':'aura-geo-country-label'
      });
      text.textContent=String(c.n||'').toUpperCase();
      geoOverlay.appendChild(text);
    }
  }

  function overlayCountryGeometry(w,h,vp){
    if(!geoOverlay)return;

    const hires=currentHiResCarto(vp);

    // Online local map tiles already contain accurate land/water geometry.
    // PACA/Kantō keep their validated high-resolution Aura overlay.
    if(tileBaseActive(vp) && !hires)return;

    if(hires && vp.latSpan<9){
      for(const poly of hires.land||[]){
        overlayPolygon(poly,w,h,vp,{
          fill:'rgba(8,29,38,.42)',
          stroke:'none'
        });
      }
      for(const poly of hires.water||[]){
        overlayPolygon(poly,w,h,vp,{
          fill:'rgba(1,11,19,.36)',
          stroke:'none'
        });
      }
      return;
    }

    renderGlobalLand(w,h,vp);
  }


  function overlayLiveWorldReference(w,h,vp){
    if(!geoOverlay || !tileBaseActive(vp))return false;
    if(currentHiResCarto(vp))return false;

    // At local/detail scale OpenStreetMap is authoritative.
    // GSHHG intermediate is intentionally suppressed because it cannot
    // trace ports, bays, estuaries and small islands pixel-for-pixel.
    if(vp.latSpan<AURA_WORLD_COAST_MIN_LATSPAN || vp.latSpan>13.5)return false;

    const data=globalCartoResolution(vp);
    if(!data)return false;

    let drawn=0;

    for(const item of data.coast||[]){
      if(!globalBBoxVisible(item.b,vp,.04))continue;

      overlayStableWorldPath(item.p,w,h,vp,{
        stroke:'rgba(112,224,239,.58)',
        'stroke-width':vp.latSpan<4?.82:.68,
        'stroke-linejoin':'round',
        'stroke-linecap':'round',
        filter:vp.latSpan<4?'url(#auraGeoSoftGlow)':null,
        'class':'aura-geo-world-reference-coast'
      });
      drawn++;
    }

    for(const item of data.borders||[]){
      if(!globalBBoxVisible(item.b,vp,.025))continue;

      overlayStableWorldPath(item.p,w,h,vp,{
        stroke:'rgba(171,210,219,.16)',
        'stroke-width':.54,
        'stroke-dasharray':'4 6',
        'stroke-linecap':'round',
        'class':'aura-geo-world-reference-border'
      });
    }

    return drawn>0;
  }


  function overlayRegionalGeometry(w,h,vp){
    if(!geoOverlay)return;

    const atlas=atlasForViewport(vp);
    const hires=currentHiResCarto(vp);

    // P0.5.2.8: outside the embedded PACA/Kantō atlases, OSM tiles remain
    // the factual basemap while a dynamic OSM vector coastline adds the
    // same cyan Aura contour language used by Vidauban.
    if(tileBaseActive(vp) && !hires){
      // P0.5.2.8.3: coastline no longer waits for the network context.
      // Immediate vector reference comes from the bundled worldwide carto.
      overlayLiveWorldReference(w,h,vp);
      overlayDynamicCoastlines(w,h,vp);
      return;
    }

    if(atlas && hires && vp.latSpan<9){
      for(const coast of hires.coast||[]){
        overlayPath(coast,w,h,vp,{
          stroke:'rgba(112,224,239,.76)',
          'stroke-width':1.05,
          'stroke-linejoin':'round',
          'stroke-linecap':'round',
          filter:'url(#auraGeoSoftGlow)'
        });
      }

      for(const border of hires.borders||[]){
        overlayPath(border,w,h,vp,{
          stroke:'rgba(179,211,222,.34)',
          'stroke-width':.85,
          'stroke-dasharray':'4 5',
          'stroke-linecap':'round'
        });
      }
      return;
    }

    renderGlobalLines(w,h,vp);
  }


  function overlayDefs(){
    if(!geoOverlay)return;
    const defs=svgNode('defs');
    const filter=svgNode('filter',{
      id:'auraGeoGlow',
      x:'-30%',y:'-30%',width:'160%',height:'160%'
    });
    const blur=svgNode('feGaussianBlur',{
      stdDeviation:'1.3',
      result:'blur'
    });
    const merge=svgNode('feMerge');
    merge.appendChild(svgNode('feMergeNode',{in:'blur'}));
    merge.appendChild(svgNode('feMergeNode',{in:'SourceGraphic'}));
    filter.appendChild(blur);
    filter.appendChild(merge);
    defs.appendChild(filter);

    const soft=svgNode('filter',{
      id:'auraGeoSoftGlow',
      x:'-20%',y:'-20%',width:'140%',height:'140%'
    });
    const softBlur=svgNode('feGaussianBlur',{
      stdDeviation:'.45',
      result:'softBlur'
    });
    const softMerge=svgNode('feMerge');
    softMerge.appendChild(svgNode('feMergeNode',{in:'softBlur'}));
    softMerge.appendChild(svgNode('feMergeNode',{in:'SourceGraphic'}));
    soft.appendChild(softBlur);
    soft.appendChild(softMerge);
    defs.appendChild(soft);

    geoOverlay.appendChild(defs);
  }

  function overlayRectCollides(rect,occupied,pad=3){
    return occupied.some(o=>rectsOverlap(rect,o,pad));
  }

  function overlayAreaLabels(w,h,vp){
    const atlas=atlasForViewport(vp);
    if(!atlas || !geoOverlay || !Array.isArray(atlas.areas))return;

    for(const area of atlas.areas){
      const [x,y]=project(area.lat,area.lon,w,h,vp);
      if(x<18||x>w-244||y<22||y>h-40)continue;

      const text=svgNode('text',{
        x:x.toFixed(1),
        y:y.toFixed(1),
        'text-anchor':'middle',
        fill:area.t==='sea'
          ?'rgba(85,172,198,.26)'
          :'rgba(126,178,192,.20)',
        'font-size':area.t==='sea'?10:9,
        'font-family':'system-ui, sans-serif',
        'font-weight':600,
        'letter-spacing':area.t==='sea'?'.16em':'.14em',
        'class':'aura-geo-area-label'
      });
      text.textContent=area.n;
      geoOverlay.appendChild(text);
    }
  }

  function overlayNearbyCities(w,h,vp){
    const atlas=atlasForViewport(vp);
    if(!atlas || !geoOverlay)return;

    const focusLat=num(payload?.latitude,vp.lat);
    const focusLon=num(payload?.longitude,vp.lon);
    const targetName=normalizedPlaceName();

    const maxLabels=Math.min(
      AURA_NEARBY_CITY_LABEL_CAP,
      vp.zoom<.65 ? 8 : 10
    );

    const visible=(atlas.cities||[])
      .filter(city=>{
        const key=norm(city.n).toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g,'');
        if(key===targetName)return false;
        return (
          city.lat>vp.lat-vp.latSpan*.59 &&
          city.lat<vp.lat+vp.latSpan*.59 &&
          Math.abs(lonDelta(city.lon,vp.lon))<vp.lonSpan*.59
        );
      })
      .map(city=>({
        city,
        dist:sqDist(city.lat,city.lon,focusLat,focusLon)
      }));

    const majors=visible
      .filter(x=>(x.city.p||0)>=8)
      .sort((a,b)=>(b.city.p||0)-(a.city.p||0)||a.dist-b.dist);

    const nearest=visible
      .slice()
      .sort((a,b)=>a.dist-b.dist)
      .slice(0,vp.zoom<.85?4:6);

    const others=visible
      .filter(x=>(x.city.p||0)>=6)
      .sort((a,b)=>(b.city.p||0)-(a.city.p||0)||a.dist-b.dist);

    const byName=new Map();
    for(const item of [...majors,...nearest,...others]){
      byName.set(item.city.n,item);
    }
    const candidates=[...byName.values()]
      .sort((a,b)=>
        a.dist-b.dist ||
        (Number(b.city.p)||0)-(Number(a.city.p)||0)
      )
      .slice(0,AURA_NEARBY_CITY_LABEL_CAP*2);

    const [tx,ty]=project(focusLat,focusLon,w,h,vp);
    const occupied=[
      {x:w-240,y:48,w:238,h:Math.max(120,h-104)},
      {x:8,y:8,w:390,h:58}
    ];
    if(tx>-40&&tx<w+40&&ty>-40&&ty<h+40){
      occupied.unshift({x:tx-16,y:ty-18,w:228,h:38});
    }

    const offsets=[
      [-13,-20,'end'],
      [13,-20,'start'],
      [-13,18,'end'],
      [13,18,'start'],
      [-20,-36,'end'],
      [20,34,'start'],
      [-30,34,'end'],
      [30,-42,'start'],
      [-38,-5,'end'],
      [38,-5,'start']
    ];

    let drawn=0;

    for(const item of candidates){
      if(drawn>=maxLabels)break;

      const city=item.city;
      const [x,y]=project(city.lat,city.lon,w,h,vp);
      if(x<20||x>w-238||y<20||y>h-44)continue;

      const importance=city.p||0;
      const major=importance>=8;
      const fontSize=importance>=10?10.5:importance>=8?9.5:8.2;
      const approxW=Math.max(34,city.n.length*(fontSize*.59)+(major?8:14));
      const boxH=major?17:18;

      let placement=null;
      for(const off of offsets){
        const [dx,dy,anchorText]=off;
        const bx=anchorText==='end' ? x+dx-approxW : x+dx;
        const by=y+dy-boxH/2;
        const rect={x:bx,y:by,w:approxW,h:boxH};

        if(bx<4||by<3||bx+approxW>w-238||by+boxH>h-38)continue;
        if(overlayRectCollides(rect,occupied,major?4:3))continue;

        placement={dx,dy,anchorText,rect};
        break;
      }
      if(!placement)continue;

      occupied.push(placement.rect);

      const group=svgNode('g',{
        'class':major?'aura-geo-city aura-geo-city-major':'aura-geo-city aura-geo-city-local'
      });

      group.appendChild(svgNode('circle',{
        cx:x.toFixed(1),
        cy:y.toFixed(1),
        r:major?2.7:1.9,
        fill:major?'rgba(157,239,248,.92)':'rgba(101,198,218,.72)'
      }));

      const lineEndX=placement.anchorText==='end'
        ? placement.rect.x+placement.rect.w
        : placement.rect.x;
      const lineEndY=placement.rect.y+placement.rect.h*.5;

      group.appendChild(svgNode('line',{
        x1:x.toFixed(1),y1:y.toFixed(1),
        x2:lineEndX.toFixed(1),y2:lineEndY.toFixed(1),
        stroke:major?'rgba(108,204,220,.22)':'rgba(96,182,202,.16)',
        'stroke-width':major?.7:.55
      }));

      if(!major){
        group.appendChild(svgNode('rect',{
          x:placement.rect.x.toFixed(1),
          y:placement.rect.y.toFixed(1),
          width:placement.rect.w.toFixed(1),
          height:placement.rect.h,
          rx:4,
          fill:'rgba(1,11,18,.64)',
          stroke:'rgba(92,205,224,.09)',
          'stroke-width':.55
        }));
      }

      const text=svgNode('text',{
        x:(placement.anchorText==='end'
          ? placement.rect.x+placement.rect.w-(major?2:5)
          : placement.rect.x+(major?2:5)).toFixed(1),
        y:(placement.rect.y+(major?11.7:12.2)).toFixed(1),
        'text-anchor':placement.anchorText,
        fill:major?'rgba(215,242,247,.90)':'rgba(164,210,221,.77)',
        'font-size':fontSize,
        'font-family':'system-ui, sans-serif',
        'font-weight':major?650:540,
        'letter-spacing':major?'.025em':'.015em'
      });
      text.textContent=city.n;
      group.appendChild(text);

      geoOverlay.appendChild(group);
      drawn++;
    }
  }


  function overlayTarget(w,h,vp){
    if(!geoOverlay)return;

    const lat=num(payload?.latitude,field?.center_latitude);
    const lon=num(payload?.longitude,field?.center_longitude);
    if(lat==null||lon==null)return;

    const [x,y]=project(lat,lon,w,h,vp);
    if(x<-40||x>w+40||y<-40||y>h+40)return;

    const g=svgNode('g',{'class':'aura-geo-target'});
    g.appendChild(svgNode('circle',{
      cx:x.toFixed(1),cy:y.toFixed(1),r:10,
      fill:'rgba(104,82,255,.10)',
      stroke:'rgba(106,245,255,.92)',
      'stroke-width':1.25
    }));
    g.appendChild(svgNode('circle',{
      cx:x.toFixed(1),cy:y.toFixed(1),r:3.2,
      fill:'rgba(128,95,255,.70)',
      stroke:'rgba(167,250,255,.96)',
      'stroke-width':.9
    }));
    g.appendChild(svgNode('line',{
      x1:(x-16).toFixed(1),y1:y.toFixed(1),
      x2:(x+16).toFixed(1),y2:y.toFixed(1),
      stroke:'rgba(100,241,255,.70)','stroke-width':.8
    }));
    g.appendChild(svgNode('line',{
      x1:x.toFixed(1),y1:(y-16).toFixed(1),
      x2:x.toFixed(1),y2:(y+16).toFixed(1),
      stroke:'rgba(100,241,255,.70)','stroke-width':.8
    }));
    geoOverlay.appendChild(g);
  }

  function renderGeographyOverlay(w,h,vp){
    if(!geoOverlay)return;

    const targetLat=num(payload?.latitude,field?.center_latitude,0);
    const targetLon=num(payload?.longitude,field?.center_longitude,0);
    const key=[
      Math.round(w),Math.round(h),
      vp.lat.toFixed(4),vp.lon.toFixed(4),
      vp.latSpan.toFixed(4),vp.lonSpan.toFixed(4),
      Number(targetLat).toFixed(4),Number(targetLon).toFixed(4)
    ].join('|');

    if(key===geoRenderKey)return;
    geoRenderKey=key;

    while(geoOverlay.firstChild)geoOverlay.removeChild(geoOverlay.firstChild);

    overlayDefs();
    overlayCountryGeometry(w,h,vp);
    overlayRegionalGeometry(w,h,vp);

    const atlas=atlasForViewport(vp);
    if(atlas && vp.latSpan<8){
      overlayAreaLabels(w,h,vp);
      overlayNearbyCities(w,h,vp);
    }else if(tileBaseActive(vp)){
      overlayDynamicNearbyCities(w,h,vp);
    }else{
      overlayCountryLabels(w,h,vp);
    }

    overlayTarget(w,h,vp);
  }


  function drawScaleBar(w,h,vp){
    const kmPerLon=111.32*Math.max(.15,Math.abs(Math.cos(vp.lat*Math.PI/180)));
    const visibleKm=Math.max(1,vp.lonSpan*kmPerLon);
    const desired=visibleKm*(115/Math.max(1,w));
    const steps=[1,2,5,10,20,25,50,100,200,250,500,1000,2000,5000,10000,20000];
    let km=steps[0];
    for(const s of steps){
      if(s<=desired)km=s;
      else break;
    }

    const px=Math.max(28,Math.min(130,km/visibleKm*w));
    const x=26, y=h-48;

    ctx.save();
    ctx.strokeStyle='rgba(138,222,236,.46)';
    ctx.fillStyle='rgba(154,220,232,.52)';
    ctx.lineWidth=1;
    ctx.beginPath();
    ctx.moveTo(x,y);ctx.lineTo(x+px,y);
    ctx.moveTo(x,y-4);ctx.lineTo(x,y+4);
    ctx.moveTo(x+px,y-4);ctx.lineTo(x+px,y+4);
    ctx.stroke();

    ctx.font='600 8px system-ui';
    ctx.textAlign='left';
    ctx.fillText(`${km} km`,x,y-8);

    const mode=
      vp.latSpan>95?'MONDE':
      vp.latSpan>38?'CONTINENT':
      vp.latSpan>12?'VUE LARGE':
      vp.latSpan>3.2?'RÉGIONAL':
      vp.latSpan>.75?'LOCAL':'DÉTAIL';
    ctx.textAlign='right';
    ctx.fillStyle='rgba(127,197,214,.40)';
    const fieldState=weatherFieldVisible(vp)?'CHAMP MÉTÉO':'CARTOGRAPHIE LIBRE';
    const ctxRuntime=String(window.__AURA_WORLD_CONTEXT_STATE__||'');
    const contextState=atlasForViewport(vp)
      ?'AURA HIRES'
      :(tileBaseActive(vp) && vp.latSpan<AURA_CITY_CONTEXT_MIN_LATSPAN)
        ?'OSM DETAIL'
        :dynamicContextForViewport(vp)
          ?'AURA CITIES'
          :worldContextPendingKey
            ?(ctxRuntime==='timeout'?'CTX TIMEOUT':'CTX LOAD')
            :ctxRuntime==='timeout'
              ?'CTX TIMEOUT'
              :ctxRuntime==='unavailable'
                ?'CTX ERROR'
                :'BASE';

    const projectionState=tileBaseActive(vp)?'MERCATOR':'VECTOR';
    const cityCapState=`CITIES≤${AURA_NEARBY_CITY_LABEL_CAP}`;
    const coastState=
      tileBaseActive(vp) && !atlasForViewport(vp)
        ?(vp.latSpan<AURA_WORLD_COAST_MIN_LATSPAN
            ?'OSM COAST'
            :'AURA REGIONAL COAST')
        :'';

    const baseState=tileBaseActive(vp)
      ?`MAP LIVE · ${contextState} · ${projectionState} · ${cityCapState}${coastState?` · ${coastState}`:''}`
      :'VECTOR';
    ctx.fillText(`${mode} · ${fieldState} · ${baseState} · ×${vp.zoom.toFixed(3)}`,Math.min(w-250,x+440),y-8);
    ctx.restore();
  }

  function bboxIntersectsViewport(b,vp){
    if(!Array.isArray(b)||b.length<4)return true;

    const minLat=Number(b[1]), maxLat=Number(b[3]);
    const viewMinLat=vp.lat-vp.latSpan*.64;
    const viewMaxLat=vp.lat+vp.latSpan*.64;
    if(maxLat<viewMinLat || minLat>viewMaxLat)return false;

    const minLon=Number(b[0]), maxLon=Number(b[2]);
    const center=(minLon+maxLon)*.5;
    const half=Math.abs(maxLon-minLon)*.5;
    const d=Math.abs(lonDelta(center,vp.lon));

    return d <= vp.lonSpan*.64 + half;
  }

  function drawBaseMap(w,h,vp){
    const liveTiles=tileBaseActive(vp);

    if(liveTiles){
      // P0.5.2.7.2: NEVER cover the online cartographic base with an opaque
      // atmospheric canvas. The canvas remains transparent and only applies
      // a restrained AURA tint above the raster tiles.
      ctx.fillStyle='rgba(1,9,16,.16)';
      ctx.fillRect(0,0,w,h);

      const bg=ctx.createRadialGradient(
        w*.48,h*.48,20,
        w*.48,h*.48,Math.max(w,h)*.72
      );
      bg.addColorStop(0,'rgba(12,55,73,.10)');
      bg.addColorStop(1,'rgba(1,6,11,.03)');
      ctx.fillStyle=bg;
      ctx.fillRect(0,0,w,h);
    }else{
      // Offline vector fallback keeps the historical opaque Aura field.
      ctx.fillStyle='rgba(1,9,16,.97)';
      ctx.fillRect(0,0,w,h);

      const bg=ctx.createRadialGradient(
        w*.48,h*.48,20,
        w*.48,h*.48,Math.max(w,h)*.72
      );
      bg.addColorStop(0,'rgba(13,50,68,.42)');
      bg.addColorStop(1,'rgba(1,6,11,.12)');
      ctx.fillStyle=bg;
      ctx.fillRect(0,0,w,h);
    }

    ctx.save();
    ctx.strokeStyle=liveTiles
      ?'rgba(82,184,218,.035)'
      :'rgba(82,184,218,.09)';
    ctx.lineWidth=liveTiles?.55:.7;
    const latStep=vp.latSpan>25?10:vp.latSpan>10?5:vp.latSpan>5?2:1;
    const lonStep=vp.lonSpan>30?10:vp.lonSpan>12?5:vp.lonSpan>6?2:1;
    for(let lat=Math.floor((vp.lat-vp.latSpan/2)/latStep)*latStep;lat<=vp.lat+vp.latSpan/2;lat+=latStep){
      const a=project(lat,vp.lon-vp.lonSpan/2,w,h,vp),b=project(lat,vp.lon+vp.lonSpan/2,w,h,vp);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
    }
    for(let lon=Math.floor((vp.lon-vp.lonSpan/2)/lonStep)*lonStep;lon<=vp.lon+vp.lonSpan/2;lon+=lonStep){
      const a=project(vp.lat-vp.latSpan/2,lon,w,h,vp),b=project(vp.lat+vp.latSpan/2,lon,w,h,vp);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();
    }
    ctx.restore();

    const world=window.AURA_P0521_WORLD||[];
    const labels=[];
    const localAtlas=atlasForViewport(vp);
    const localHiRes=currentHiResCarto(vp);
    ctx.save();

    // P0.5.2.6: SVG is now authoritative for BOTH local and global cartography.
    // Canvas keeps only the atmospheric background/grid/scale.
    for(const f of []){
      const b=f.b||[];
      const cy=(b[1]+b[3])/2, cx=(b[0]+b[2])/2;
      if(!bboxIntersectsViewport(b,vp))continue;
      let visible=false;
      ctx.beginPath();
      for(const ring of f.p||[]){
        let first=true,lastX=null;
        for(const pt of ring){
          const [x,y]=project(pt[1],pt[0],w,h,vp);
          if(lastX!=null&&Math.abs(x-lastX)>w*.65){first=true;lastX=x;continue;}
          if(first){ctx.moveTo(x,y);first=false;} else ctx.lineTo(x,y);
          lastX=x;
          if(x>-80&&x<w+80&&y>-80&&y<h+80)visible=true;
        }
      }
      if(!visible)continue;
      ctx.fillStyle='rgba(7,27,36,.86)';
      ctx.strokeStyle=localAtlas
        ?'rgba(132,225,241,.50)'
        :'rgba(116,218,235,.38)';
      ctx.lineWidth=localAtlas
        ?Math.max(1.25,Math.min(2.0,vp.zoom*.95))
        :1.0;
      ctx.fill();ctx.stroke();
      if(vp.lonSpan<35){
        const [lx,ly]=project(cy,cx,w,h,vp);
        if(lx>70&&lx<w-280&&ly>45&&ly<h-70)labels.push([f.n,lx,ly]);
      }
    }
    ctx.font='600 10px system-ui';ctx.fillStyle='rgba(167,224,236,.44)';ctx.textAlign='center';
    for(const [name,x,y] of labels.slice(0,12)){
      ctx.save();ctx.shadowColor='rgba(0,8,14,.95)';ctx.shadowBlur=7;ctx.fillText(String(name).toUpperCase(),x,y);ctx.restore();
    }
    drawScaleBar(w,h,vp);
    if(!localAtlas && vp.lat-vp.latSpan/2<45.5 && vp.lat+vp.latSpan/2>31 && vp.lon-vp.lonSpan/2<38 && vp.lon+vp.lonSpan/2>-6){
      const sea=project(Math.max(34,Math.min(43,vp.lat-vp.latSpan*.28)),Math.max(-1,Math.min(18,vp.lon)),w,h,vp);
      ctx.save();ctx.font='500 10px system-ui';ctx.fillStyle='rgba(87,178,211,.20)';ctx.fillText('MÉDITERRANÉE',sea[0],sea[1]);ctx.restore();
    }
    ctx.restore();
  }

  // P0.5.2.8.7
  // Each weather layer now has its own visual grammar instead of reusing
  // the same radial glow with a different colour.

  function rgba(c,a=1){
    return `rgba(${c[0]},${c[1]},${c[2]},${a})`;
  }

  function mixColor(a,b,t){
    t=clamp(t);
    return [
      Math.round(a[0]+(b[0]-a[0])*t),
      Math.round(a[1]+(b[1]-a[1])*t),
      Math.round(a[2]+(b[2]-a[2])*t)
    ];
  }

  function multiStopColor(stops,value){
    const v=Number(value);
    if(!Number.isFinite(v))return stops[0][1];
    if(v<=stops[0][0])return stops[0][1];
    for(let i=1;i<stops.length;i++){
      const [v1,c1]=stops[i-1], [v2,c2]=stops[i];
      if(v<=v2){
        const t=(v-v1)/Math.max(.0001,v2-v1);
        return mixColor(c1,c2,t);
      }
    }
    return stops[stops.length-1][1];
  }

  function temperatureColor(v){
    return multiStopColor([
      [-15,[74,214,255]],
      [0,[57,151,255]],
      [10,[83,111,255]],
      [20,[126,93,255]],
      [30,[224,80,229]],
      [40,[255,122,93]],
      [50,[255,190,92]]
    ],v);
  }

  function rainColor(v){
    return multiStopColor([
      [0,[49,105,180]],
      [15,[58,159,255]],
      [35,[72,225,255]],
      [60,[105,241,184]],
      [80,[205,107,255]],
      [100,[255,91,209]]
    ],v);
  }

  function pressureColor(v){
    return multiStopColor([
      [970,[47,208,255]],
      [995,[66,163,255]],
      [1013,[118,105,255]],
      [1030,[205,87,255]],
      [1050,[255,112,202]]
    ],v);
  }

  function fieldKeyForLayer(layer){
    return {
      rain:'rain_probability',
      temperature:'temperature',
      clouds:'cloud_cover',
      pressure:'pressure'
    }[layer]||null;
  }

  function drawRainField(w,h,vp){
    const vals=valuesFor('rain');
    if(!vals.length)return;

    ctx.save();
    ctx.globalCompositeOperation='screen';

    const baseRadius=Math.max(54,Math.min(128,Math.min(w,h)*.13));

    field.points.forEach((p,i)=>{
      const probability=num(fieldHour(p).rain_probability,null);
      if(probability==null || probability<2)return;

      const t=clamp(probability/100);
      const [x,y]=project(p.latitude,p.longitude,w,h,vp);
      const radius=baseRadius*(.72+.42*t);
      const c=rainColor(probability);

      const g=ctx.createRadialGradient(x,y,0,x,y,radius);
      g.addColorStop(0,rgba(c,.08+.42*Math.pow(t,.9)));
      g.addColorStop(.46,rgba(c,.04+.26*Math.pow(t,1.15)));
      g.addColorStop(1,rgba(c,0));
      ctx.fillStyle=g;
      ctx.fillRect(x-radius,y-radius,radius*2,radius*2);

      // Radar-like precipitation texture. It is tied to probability only:
      // no fictitious millimetres are generated.
      if(probability>=18){
        const drops=Math.min(9,2+Math.floor(probability/14));
        ctx.strokeStyle=rgba(c,.14+.24*t);
        ctx.lineWidth=.7+.7*t;
        for(let d=0;d<drops;d++){
          const a=(i*1.91+d*2.37+animPhase*.00018)%(Math.PI*2);
          const rr=radius*(.18+((d*37+i*11)%67)/100*.62);
          const px=x+Math.cos(a)*rr;
          const py=y+Math.sin(a)*rr*.58;
          ctx.beginPath();
          ctx.moveTo(px-2,py-5);
          ctx.lineTo(px+2,py+5);
          ctx.stroke();
        }
      }
    });

    ctx.restore();
  }

  function drawTemperatureField(w,h,vp){
    const vals=valuesFor('temperature');
    if(!vals.length)return;

    ctx.save();
    ctx.globalCompositeOperation='screen';
    ctx.filter='blur(10px)';

    const radius=Math.max(85,Math.min(165,Math.min(w,h)*.18));
    for(const p of field.points){
      const v=num(fieldHour(p).temperature,null);
      if(v==null)continue;

      const [x,y]=project(p.latitude,p.longitude,w,h,vp);
      const c=temperatureColor(v);
      const g=ctx.createRadialGradient(x,y,0,x,y,radius);
      g.addColorStop(0,rgba(c,.28));
      g.addColorStop(.55,rgba(c,.16));
      g.addColorStop(1,rgba(c,0));
      ctx.fillStyle=g;
      ctx.fillRect(x-radius,y-radius,radius*2,radius*2);
    }

    ctx.filter='none';
    ctx.restore();
  }

  function drawCloudField(w,h,vp){
    const vals=valuesFor('clouds');
    if(!vals.length)return;

    ctx.save();
    ctx.globalCompositeOperation='screen';
    ctx.filter='blur(18px)';

    const radius=Math.max(78,Math.min(150,Math.min(w,h)*.16));
    field.points.forEach((p,i)=>{
      const cloud=num(fieldHour(p).cloud_cover,null);
      if(cloud==null || cloud<4)return;

      const t=clamp(cloud/100);
      const [x,y]=project(p.latitude,p.longitude,w,h,vp);
      const drift=Math.sin(i*1.73+animPhase*.00008)*radius*.10;
      const g=ctx.createRadialGradient(x+drift,y,0,x+drift,y,radius);
      g.addColorStop(0,`rgba(220,238,245,${.04+.28*t})`);
      g.addColorStop(.58,`rgba(170,205,218,${.025+.18*t})`);
      g.addColorStop(1,'rgba(135,180,198,0)');
      ctx.fillStyle=g;
      ctx.fillRect(x-radius*1.2,y-radius,radius*2.4,radius*2);
    });

    ctx.filter='none';
    ctx.restore();
  }

  function drawPressureField(w,h,vp){
    const vals=valuesFor('pressure');
    if(!vals.length)return;

    const mean=vals.reduce((a,b)=>a+b,0)/vals.length;
    let low=null,high=null;

    ctx.save();
    ctx.globalCompositeOperation='screen';

    const radius=Math.max(92,Math.min(165,Math.min(w,h)*.18));
    field.points.forEach(p=>{
      const pressure=num(fieldHour(p).pressure,null);
      if(pressure==null)return;

      if(!low || pressure<low.value)low={p,value:pressure};
      if(!high || pressure>high.value)high={p,value:pressure};

      const [x,y]=project(p.latitude,p.longitude,w,h,vp);
      const c=pressureColor(pressure);
      const anomaly=Math.min(1,Math.abs(pressure-mean)/10);
      const g=ctx.createRadialGradient(x,y,0,x,y,radius);
      g.addColorStop(0,rgba(c,.11+.16*anomaly));
      g.addColorStop(.60,rgba(c,.05+.09*anomaly));
      g.addColorStop(1,rgba(c,0));
      ctx.fillStyle=g;
      ctx.fillRect(x-radius,y-radius,radius*2,radius*2);
    });

    // Highlight only the measured field extrema. These are not presented as
    // meteorological isobars, avoiding false contour precision.
    for(const item of [low,high]){
      if(!item)continue;
      const [x,y]=project(item.p.latitude,item.p.longitude,w,h,vp);
      const isHigh=item===high;
      const c=isHigh?[222,93,255]:[72,222,255];
      ctx.strokeStyle=rgba(c,.34);
      ctx.fillStyle=rgba(c,.70);
      ctx.lineWidth=1;
      for(let k=0;k<3;k++){
        ctx.beginPath();
        ctx.ellipse(x,y,44+k*23,22+k*12,0,0,Math.PI*2);
        ctx.stroke();
      }
      ctx.font='700 10px system-ui';
      ctx.textAlign='center';
      ctx.fillText(`${isHigh?'H':'L'} ${Math.round(item.value)}`,x,y-8);
    }

    ctx.restore();
  }

  function drawSemanticField(w,h,vp,layer){
    if(layer==='rain')return drawRainField(w,h,vp);
    if(layer==='temperature')return drawTemperatureField(w,h,vp);
    if(layer==='clouds')return drawCloudField(w,h,vp);
    if(layer==='pressure')return drawPressureField(w,h,vp);
  }

  function legendGradientFor(layer){
    if(layer==='rain')return 'linear-gradient(180deg,#ff5bd1 0%,#cd6bff 22%,#69f1b8 48%,#48e1ff 72%,#3aa0ff 100%)';
    if(layer==='temperature')return 'linear-gradient(180deg,#ffbe5c 0%,#ff7a5d 18%,#e050e5 38%,#7e5dff 62%,#3997ff 82%,#4ad6ff 100%)';
    if(layer==='clouds')return 'linear-gradient(180deg,#f2fbff 0%,#c4dfe9 38%,#7fa9bb 72%,#304b5a 100%)';
    if(layer==='pressure')return 'linear-gradient(180deg,#ff70ca 0%,#cd57ff 34%,#7669ff 58%,#42d0ff 100%)';
    return 'linear-gradient(180deg,#f05cff,#8e5cff,#43c7ff,#5cf2ff)';
  }

  function weatherFieldBounds(){
    if(!field?.points?.length)return null;
    const lats=field.points.map(p=>Number(p.latitude)).filter(Number.isFinite);
    const centerLon=num(field?.center_longitude,num(payload?.longitude,0));
    if(!lats.length)return null;

    let lonRadius=0;
    for(const p of field.points){
      if(!finite(p.longitude))continue;
      lonRadius=Math.max(lonRadius,Math.abs(lonDelta(Number(p.longitude),centerLon)));
    }

    return {
      latMin:Math.min(...lats),
      latMax:Math.max(...lats),
      lon:centerLon,
      lonRadius:Math.max(.01,lonRadius)
    };
  }

  function insideWeatherField(lat,lon,pad=.08){
    const b=weatherFieldBounds();
    if(!b)return false;

    const latPad=Math.max(.03,(b.latMax-b.latMin)*pad);
    const lonPad=Math.max(.03,b.lonRadius*2*pad);

    return (
      lat>=b.latMin-latPad &&
      lat<=b.latMax+latPad &&
      Math.abs(lonDelta(lon,b.lon))<=b.lonRadius+lonPad
    );
  }

  function weatherFieldVisible(vp){
    const b=weatherFieldBounds();
    if(!b)return false;

    if(b.latMax<vp.lat-vp.latSpan*.5 || b.latMin>vp.lat+vp.latSpan*.5)return false;
    if(vp.lonSpan>=350)return true;

    return Math.abs(lonDelta(b.lon,vp.lon)) <= vp.lonSpan*.5+b.lonRadius;
  }

  function interpolateWind(lat,lon){
    if(!field?.points?.length)return {speed:0,directionFrom:270,flowDirection:90};
    let sumU=0,sumV=0,total=0;

    for(const fp of field.points){
      const hr=fieldHour(fp);
      const speed=num(hr.wind_speed,null),directionFrom=num(hr.wind_direction,null);
      if(speed==null||directionFrom==null)continue;

      const dLat=(Number(fp.latitude)-lat)*1.25;
      const dLon=lonDelta(fp.longitude,lon)*Math.max(.40,Math.abs(Math.cos(lat*Math.PI/180)));
      const dist2=dLat*dLat+dLon*dLon;

      if(dist2<1e-7){
        return {
          speed,
          directionFrom,
          flowDirection:metFromDegToFlowDeg(directionFrom)
        };
      }

      const weight=1/(dist2+1e-5);
      const flowRad=(metFromDegToFlowDeg(directionFrom)*Math.PI)/180;
      // east-positive x, north-negative y (canvas convention)
      sumU += Math.sin(flowRad) * speed * weight;
      sumV += -Math.cos(flowRad) * speed * weight;
      total += weight;
    }

    if(total<=0)return {speed:0,directionFrom:270,flowDirection:90};

    const u=sumU/total, v=sumV/total;
    const speed=Math.hypot(u,v);
    const flowDirection=(Math.atan2(u,-v)*180/Math.PI+360)%360;
    const directionFrom=flowDegToMetFromDeg(flowDirection);
    return {speed,directionFrom,flowDirection};
  }

  function drawWind(w,h,vp){
    if(!field)return;
    ctx.save();ctx.globalCompositeOperation='lighter';
    for(let i=0;i<particles.length;i++){
      const p=particles[i];
      const lat=vp.lat+(p.y-.5)*vp.latSpan;
      const lon=wrapLon(vp.lon+(p.x-.5)*vp.lonSpan);
      if(!insideWeatherField(lat,lon))continue;

      const flow=interpolateWind(lat,lon);
      const speed=Math.max(0,num(flow.speed,0));
      const flowDir=num(flow.flowDirection,90);
      const rad=(flowDir*Math.PI)/180;

      const drift=(animPhase*(.00045+.000022*speed)*(0.65+p.s*.55)+i*.019)%1;
      const x=((p.x+Math.sin(rad)*drift+3)%1)*w;
      const y=((p.y-Math.cos(rad)*drift*.52+3)%1)*h;

      const len=10+Math.min(34,speed*.72)*(0.55+p.s*.65);
      const dx=Math.sin(rad)*len,dy=-Math.cos(rad)*len;
      const tailX=x-dx,tailY=y-dy;

      const g=ctx.createLinearGradient(tailX,tailY,x,y);
      g.addColorStop(0,'rgba(74,121,255,0)');
      g.addColorStop(.58,`rgba(85,197,255,${.10+.18*p.s})`);
      g.addColorStop(1,`rgba(108,247,255,${.34+.45*p.s})`);
      ctx.strokeStyle=g;
      ctx.lineWidth=.48+p.s*.82;
      ctx.beginPath();ctx.moveTo(tailX,tailY);ctx.lineTo(x,y);ctx.stroke();
    }

    // Actual Open-Meteo sample vectors: visible but subordinate to the flow.
    // They now use the exact same flow convention as particles.
    ctx.strokeStyle='rgba(213,250,255,.42)';
    ctx.fillStyle='rgba(213,250,255,.48)';
    ctx.lineWidth=.8;
    for(const fp of field.points.filter((_,i)=>i%2===0)){
      const hr=fieldHour(fp);
      const dirFrom=num(hr.wind_direction,null);
      if(dirFrom==null)continue;

      const [x,y]=project(fp.latitude,fp.longitude,w,h,vp);
      const flowDir=metFromDegToFlowDeg(dirFrom);
      const rad=(flowDir*Math.PI)/180;
      const len=9+Math.min(19,num(hr.wind_speed,0)*.34);
      const ex=x+Math.sin(rad)*len,ey=y-Math.cos(rad)*len;

      ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(ex,ey);ctx.stroke();
      ctx.beginPath();ctx.arc(ex,ey,1.45,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  function drawFieldLattice(w,h,vp){
    if(!field?.points?.length)return;
    const rows=Math.max(1,Number(field.rows)||5),cols=Math.max(1,Number(field.cols)||5);
    const pts=field.points.map(p=>project(p.latitude,p.longitude,w,h,vp));
    ctx.save();
    ctx.strokeStyle='rgba(89,214,241,.07)';
    ctx.fillStyle='rgba(108,232,248,.18)';
    ctx.lineWidth=.65;
    for(let r=0;r<rows;r++){
      ctx.beginPath();
      for(let c=0;c<cols;c++){
        const p=pts[r*cols+c];if(!p)continue;
        if(c===0)ctx.moveTo(...p);else ctx.lineTo(...p);
      }
      ctx.stroke();
    }
    for(let c=0;c<cols;c++){
      ctx.beginPath();
      for(let r=0;r<rows;r++){
        const p=pts[r*cols+c];if(!p)continue;
        if(r===0)ctx.moveTo(...p);else ctx.lineTo(...p);
      }
      ctx.stroke();
    }
    for(const p of pts){
      ctx.beginPath();ctx.arc(p[0],p[1],1.35,0,Math.PI*2);ctx.fill();
    }
    ctx.restore();
  }

  function drawTarget(w,h,vp){
    const lat=num(payload?.latitude,field?.center_latitude),lon=num(payload?.longitude,field?.center_longitude);if(lat==null||lon==null)return;
    const [x,y]=project(lat,lon,w,h,vp);

    // SVG foreground owns the visible crosshair in P0.5.2.5.
    if(!geoOverlay){
      ctx.save();ctx.strokeStyle='rgba(92,244,255,.88)';ctx.fillStyle='rgba(138,76,255,.28)';ctx.lineWidth=1.2;
      ctx.beginPath();ctx.arc(x,y,11+Math.sin(animPhase*.003)*2,0,Math.PI*2);ctx.stroke();ctx.beginPath();ctx.arc(x,y,4,0,Math.PI*2);ctx.fill();ctx.stroke();
      ctx.beginPath();ctx.moveTo(x-18,y);ctx.lineTo(x+18,y);ctx.moveTo(x,y-18);ctx.lineTo(x,y+18);ctx.stroke();ctx.restore();
    }

    const target=shell?.querySelector('.aura-wx-map-target');
    if(target){target.style.left=`${x}px`;target.style.top=`${y}px`;}
  }

  function draw(){
    drawRaf=0;if(!ctx||!canvas||!shell)return;
    const r=shell.getBoundingClientRect();const w=r.width,h=r.height;if(w<20||h<20)return;
    let vp=viewport();
    if(!viewportCenterSelfCheck()){
      const targetLat=num(payload?.latitude,num(field?.center_latitude,0));
      const targetLon=num(payload?.longitude,num(field?.center_longitude,0));
      vp={...vp,lat:targetLat,lon:targetLon,targetLat,targetLon};
    }
    renderOnlineTiles(w,h,vp);
    scheduleWorldContext(vp);
    ctx.clearRect(0,0,w,h);drawBaseMap(w,h,vp);
    if(field){
      if(activeLayer==='wind'){
        drawFieldLattice(w,h,vp);
        drawWind(w,h,vp);
      } else if(activeLayer==='waves'){
        // No marine provider is wired: keep the geographic base only.
        // Never synthesize or imply factual wave heights.
      } else {
        drawSemanticField(w,h,vp,activeLayer);
      }
    }

    // P0.5.2.4.2: geography is now a foreground vector layer.
    // This prevents weather animation/scalar fields from visually swallowing it.
    renderGeographyOverlay(w,h,vp);
    drawTarget(w,h,vp);
  }

  function scheduleDraw(){if(!drawRaf)drawRaf=requestAnimationFrame(draw)}
  function animate(ts){animPhase=ts;if(activeLayer==='wind'||activeLayer==='rain'||activeLayer==='clouds'||activeLayer==='waves')scheduleDraw();requestAnimationFrame(animate)}

  waitForWorkspace();
})();
