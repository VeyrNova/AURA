/* AURA P0.6.6.1 MAPS DESKTOP — POI & PLACES */
/* AURA P0.6.6.1.1 POI TOOLBAR ACTIVATION FIX */
/* AURA P0.6.6.1.2 POI MODE DELEGATED ACTIVATION + MAPS MODE UX */
(() => {
  'use strict';
  if(window.__AURA_P066112_POI_PLACES__) return;
  window.__AURA_P066112_POI_PLACES__ = true;
  window.__AURA_P0661_POI_PLACES__ = true;

  const token = new URLSearchParams(location.search).get('token') || '';
  const finite = v => v !== null && v !== undefined && Number.isFinite(Number(v));
  const norm = s => String(s ?? '').replace(/\s+/g, ' ').trim();
  const esc = s => String(s ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const CATEGORIES = [
    {id:'parking', label:'PARKING', short:'P', glyph:'P'},
    {id:'fuel', label:'CARBURANT', short:'FUEL', glyph:'F'},
    {id:'charging', label:'RECHARGE', short:'EV', glyph:'⚡'},
    {id:'restaurant', label:'RESTAURANTS', short:'FOOD', glyph:'R'},
    {id:'hotel', label:'HÔTELS', short:'HOTEL', glyph:'H'},
    {id:'services', label:'SERVICES', short:'SERV', glyph:'+'},
  ];

  let root = null, panel = null, markerLayer = null, toolbarPoi = null;
  let category = 'fuel', radiusM = 2000, results = [], selectedId = null;
  let busy = false, positionTimer = null, panelOpen = false, lastNavigationActive = false;
  let delegatedToolbarBound = false;

  function categoryMeta(id){ return CATEGORIES.find(x => x.id === id) || CATEGORIES[0]; }

  function sampleGeometry(points, maxPoints = 28){
    const clean = Array.isArray(points) ? points.filter(p => Array.isArray(p) && p.length >= 2 && finite(p[0]) && finite(p[1])).map(p => [Number(p[0]), Number(p[1])]) : [];
    if(clean.length <= maxPoints) return clean;
    const out = [];
    for(let i=0;i<maxPoints;i++){
      const idx = Math.round(i * (clean.length - 1) / (maxPoints - 1));
      const p = clean[idx];
      if(!out.length || out[out.length-1][0] !== p[0] || out[out.length-1][1] !== p[1]) out.push(p);
    }
    return out;
  }

  function searchGeometry(){
    const api = window.AURA_NAVIGATION;
    if(!api) return {geometry:[], mode:'none'};
    let geometry = [];
    try{ geometry = sampleGeometry(api.getRouteGeometry?.() || []); }catch(_){}
    if(geometry.length >= 2) return {geometry, mode:'route'};
    const state = api.state || {};
    if(state.destination && finite(state.destination.lon) && finite(state.destination.lat)){
      return {geometry:[[Number(state.destination.lon), Number(state.destination.lat)]], mode:'destination'};
    }
    if(finite(state.centerLon) && finite(state.centerLat)){
      return {geometry:[[Number(state.centerLon), Number(state.centerLat)]], mode:'map'};
    }
    return {geometry:[], mode:'none'};
  }

  async function fetchJson(url, opts = {}){
    const r = await fetch(url, {cache:'no-store', ...opts});
    let data = null; try{ data = await r.json(); }catch(_){}
    if(!r.ok || !data?.ok) throw new Error(data?.error || `http_${r.status}`);
    return data;
  }

  function setState(text, error = false){
    const el = panel?.querySelector('#auraPoiState');
    if(el){ el.textContent = String(text || 'PRÊT'); el.classList.toggle('error', !!error); }
  }

  function setBusy(on){
    busy = !!on;
    const btn = panel?.querySelector('#auraPoiSearch');
    if(btn){ btn.disabled = busy; btn.classList.toggle('busy', busy); }
    if(on) setState('RECHERCHE OSM / OVERPASS…');
  }

  function formatDistance(m){
    const v = Math.max(0, Number(m) || 0);
    if(v < 1000) return `${Math.round(v)} m`;
    return `${(v/1000).toFixed(v < 10000 ? 1 : 0).replace('.', ',')} km`;
  }

  function resultMeta(item){
    const parts = [];
    if(finite(item.route_offset_m) && Number(item.route_offset_m) > 150){
      parts.push(`À ${formatDistance(item.route_offset_m)} DU DÉPART`);
    }
    if(finite(item.distance_to_route_m)){
      parts.push(`${formatDistance(item.distance_to_route_m)} DU TRAJET`);
    }
    return parts.join(' · ');
  }

  function secondary(item){
    const values = [];
    if(norm(item.address)) values.push(norm(item.address));
    if(norm(item.opening_hours)) values.push(norm(item.opening_hours));
    if(norm(item.brand) && norm(item.brand).toLocaleLowerCase('fr') !== norm(item.name).toLocaleLowerCase('fr')) values.push(norm(item.brand));
    return values.slice(0,2).join(' · ');
  }

  function renderResults(){
    const box = panel?.querySelector('#auraPoiResults');
    if(!box) return;
    if(!results.length){
      box.innerHTML = '<div class="aura-poi-empty">Aucun lieu affiché. Choisissez une catégorie puis lancez la recherche.</div>';
      return;
    }
    box.innerHTML = results.map((item, i) => {
      const id = String(item.id || `${item.osm_type || 'poi'}-${item.osm_id || i}`);
      const meta = categoryMeta(item.category || category);
      return `<button type="button" class="aura-poi-result ${selectedId===id?'selected':''}" data-poi-id="${esc(id)}">
        <span class="aura-poi-result-icon" data-category="${esc(meta.id)}">${esc(meta.glyph)}</span>
        <span class="aura-poi-result-copy">
          <b>${esc(item.name || meta.label)}</b>
          <small>${esc(resultMeta(item) || meta.label)}</small>
          ${secondary(item)?`<em>${esc(secondary(item))}</em>`:''}
        </span>
        <i>VOIR</i>
      </button>`;
    }).join('');
    box.querySelectorAll('[data-poi-id]').forEach(btn => btn.addEventListener('click', () => selectPoi(btn.dataset.poiId, true)));
  }

  function clearMarkers(){
    results = [];
    selectedId = null;
    if(markerLayer) markerLayer.replaceChildren();
    renderResults();
    setState('MARQUEURS EFFACÉS');
  }

  function selectPoi(id, center = false){
    selectedId = String(id || '');
    renderResults();
    updateMarkers();
    const item = results.find((x, i) => String(x.id || `${x.osm_type || 'poi'}-${x.osm_id || i}`) === selectedId);
    if(!item) return;
    setState(`${norm(item.name || 'LIEU')} · ${resultMeta(item) || 'SÉLECTIONNÉ'}`);
    if(center && finite(item.lat) && finite(item.lon)){
      try{
        const api = window.AURA_NAVIGATION;
        const current = api?.state?.zoom || 13;
        api?.centerOn?.(Number(item.lat), Number(item.lon), Math.max(14, Math.min(16, Number(current) || 14)));
      }catch(_){}
    }
  }

  function createMarkers(){
    if(!markerLayer) return;
    markerLayer.replaceChildren();
    results.forEach((item, i) => {
      if(!finite(item.lat) || !finite(item.lon)) return;
      const id = String(item.id || `${item.osm_type || 'poi'}-${item.osm_id || i}`);
      const meta = categoryMeta(item.category || category);
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'aura-poi-marker';
      btn.dataset.poiId = id;
      btn.dataset.category = meta.id;
      btn.title = norm(item.name || meta.label);
      btn.innerHTML = `<span>${esc(meta.glyph)}</span>`;
      btn.addEventListener('click', ev => { ev.stopPropagation(); selectPoi(id, false); });
      markerLayer.appendChild(btn);
    });
    updateMarkers();
  }

  function updateMarkers(){
    if(!markerLayer || !results.length || !window.AURA_NAVIGATION?.projectPoint) return;
    const markers = markerLayer.querySelectorAll('[data-poi-id]');
    markers.forEach(marker => {
      const item = results.find((x, i) => String(x.id || `${x.osm_type || 'poi'}-${x.osm_id || i}`) === marker.dataset.poiId);
      if(!item) return;
      let p = null;
      try{ p = window.AURA_NAVIGATION.projectPoint(Number(item.lat), Number(item.lon)); }catch(_){}
      if(!p || !finite(p.x) || !finite(p.y) || p.visible === false){
        marker.hidden = true;
        return;
      }
      marker.hidden = false;
      marker.style.left = `${Number(p.x).toFixed(1)}px`;
      marker.style.top = `${Number(p.y).toFixed(1)}px`;
      marker.classList.toggle('selected', marker.dataset.poiId === selectedId);
    });
  }

  function ensurePositionLoop(){
    if(positionTimer) return;
    positionTimer = setInterval(() => {
      if(!root?.classList.contains('open')) return;
      updateMarkers();
      const active = !!window.AURA_NAVIGATION?.state?.navigationActive;
      if(active && !lastNavigationActive && panelOpen) setPanelOpen(false);
      lastNavigationActive = active;
    }, 140);
  }

  function toolbarButton(label){
    if(!root) return null;
    const wanted = String(label || '').toUpperCase();
    return Array.from(root.querySelectorAll('.aura-nav-toolbar button')).find(b => norm(b.textContent).toUpperCase() === wanted) || null;
  }

  function bindToolbarState(){
    if(!root) return;
    toolbarPoi = root.querySelector('.aura-nav-toolbar button[data-nav-toolbar="poi"]') || toolbarButton('POI');
    if(toolbarPoi){
      toolbarPoi.disabled = false;
      toolbarPoi.removeAttribute('disabled');
      toolbarPoi.dataset.navToolbar = 'poi';
      toolbarPoi.setAttribute('aria-disabled','false');
      toolbarPoi.setAttribute('aria-pressed', panelOpen ? 'true' : 'false');
      toolbarPoi.title = 'Afficher les lieux utiles';
    }
    const routeToolbar = toolbarButton('ITINÉRAIRE');
    if(routeToolbar){
      routeToolbar.setAttribute('aria-pressed', panelOpen ? 'false' : 'true');
      routeToolbar.classList.toggle('active', !panelOpen);
    }
  }

  function setPanelOpen(open){
    panelOpen = !!open;
    if((!panel || !panel.isConnected) && !install(true)) return;
    panel?.classList.toggle('open', panelOpen);
    root?.classList.toggle('poi-mode', panelOpen);
    bindToolbarState();
    toolbarPoi?.classList.toggle('active', panelOpen);
    if(panelOpen){
      requestAnimationFrame(() => {
        const sidebar = root?.querySelector('.aura-nav-sidebar');
        if(sidebar && panel){
          const y = Math.max(0, panel.offsetTop - 10);
          try{ sidebar.scrollTo({top:y, behavior:'smooth'}); }
          catch(_){ sidebar.scrollTop = y; }
        }
      });
    }
  }

  function onToolbarCapture(ev){
    const target = ev.target instanceof Element ? ev.target.closest('#auraNavigationWorkspace .aura-nav-toolbar button') : null;
    if(!target) return;
    const label = norm(target.textContent).toUpperCase();
    if(target.dataset.navToolbar === 'poi' || label === 'POI'){
      ev.preventDefault();
      ev.stopPropagation();
      if(typeof ev.stopImmediatePropagation === 'function') ev.stopImmediatePropagation();
      if(!install(true)) return;
      setPanelOpen(!panelOpen);
      return;
    }
    if(label === 'ITINÉRAIRE' && panelOpen) setPanelOpen(false);
  }

  function ensureDelegatedToolbar(){
    if(delegatedToolbarBound) return;
    delegatedToolbarBound = true;
    document.addEventListener('click', onToolbarCapture, true);
  }

  async function search(){
    if(busy) return;
    const geo = searchGeometry();
    if(!geo.geometry.length){
      setState('AUCUNE POSITION OU ROUTE DISPONIBLE', true);
      return;
    }
    setBusy(true);
    try{
      const payload = {category, radius_m:radiusM, geometry:geo.geometry};
      const data = await fetchJson(`/api/nav/pois?token=${encodeURIComponent(token)}`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify(payload)
      });
      results = Array.isArray(data.places) ? data.places : [];
      selectedId = null;
      renderResults();
      createMarkers();
      const source = String(data.cache_state || '').includes('cache') ? 'CACHE OSM' : 'OSM / OVERPASS';
      const mode = geo.mode === 'route' ? 'SUR LE TRAJET' : geo.mode === 'destination' ? 'AUTOUR DE LA DESTINATION' : 'AUTOUR DE LA CARTE';
      setState(`${results.length} LIEU${results.length>1?'X':''} · ${mode} · ${source}`);
    }catch(e){
      const code = String(e?.message || e);
      const friendly = {
        invalid_poi_request:'REQUÊTE POI INVALIDE',
        poi_unavailable:'OVERPASS INDISPONIBLE',
        poi_no_geometry:'AUCUNE ROUTE OU POSITION',
        poi_invalid_category:'CATÉGORIE INVALIDE'
      }[code] || 'RECHERCHE POI INDISPONIBLE';
      setState(friendly, true);
    }finally{ setBusy(false); }
  }

  function install(force = false){
    root = document.getElementById('auraNavigationWorkspace');
    if(!root) return false;

    const sidebar = root.querySelector('.aura-nav-sidebar');
    const map = root.querySelector('.aura-nav-map');
    if(!sidebar || !map) return false;

    markerLayer = document.getElementById('auraPoiMarkerLayer');
    if(!markerLayer){
      markerLayer = document.createElement('div');
      markerLayer.id = 'auraPoiMarkerLayer';
      markerLayer.className = 'aura-poi-marker-layer';
      markerLayer.setAttribute('aria-label', 'Lieux utiles sur la carte');
      map.appendChild(markerLayer);
    }

    panel = document.getElementById('auraPoiPlaces');
    if(!panel){
      panel = document.createElement('section');
      panel.id = 'auraPoiPlaces';
      panel.className = 'aura-poi-places';
      panel.innerHTML = `
        <header>
          <div><span>MAPS DESKTOP</span><b>POI & PLACES</b></div>
          <em>P0.6.6.1.2</em>
        </header>
        <div class="aura-poi-categories" role="group" aria-label="Catégorie de lieux">
          ${CATEGORIES.map(c => `<button type="button" data-poi-category="${esc(c.id)}" class="${c.id===category?'active':''}"><i>${esc(c.glyph)}</i><span>${esc(c.label)}</span></button>`).join('')}
        </div>
        <div class="aura-poi-tools">
          <label><span>RAYON AUTOUR DU TRAJET</span>
            <select id="auraPoiRadius">
              <option value="1000">1 km</option>
              <option value="2000" selected>2 km</option>
              <option value="5000">5 km</option>
            </select>
          </label>
          <button id="auraPoiSearch" type="button"><span>RECHERCHER</span><small>SUR LE TRAJET ACTIF</small></button>
        </div>
        <div id="auraPoiResults" class="aura-poi-results">
          <div class="aura-poi-empty">Choisissez une catégorie puis recherchez les lieux utiles le long du trajet.</div>
        </div>
        <footer>
          <span id="auraPoiState">PRÊT · CARBURANT · 2 KM</span>
          <button id="auraPoiClear" type="button">EFFACER</button>
        </footer>`;

      // POI is a real Maps mode: show it before the trip planner so the response to the toolbar click is immediate.
      const trip = sidebar.querySelector('#auraTripPlanner');
      if(trip) trip.insertAdjacentElement('beforebegin', panel);
      else{
        const form = sidebar.querySelector('.aura-nav-route-form');
        if(form) form.insertAdjacentElement('afterend', panel);
        else sidebar.appendChild(panel);
      }
    }else{
      // Repair the position if an older P0.6.6.1 panel is already mounted in the current WebView.
      const trip = sidebar.querySelector('#auraTripPlanner');
      if(trip && panel.nextElementSibling !== trip) trip.insertAdjacentElement('beforebegin', panel);
    }

    if(panel.dataset.auraPoiBound112 !== '1'){
      panel.dataset.auraPoiBound112 = '1';
      panel.querySelectorAll('[data-poi-category]').forEach(btn => btn.addEventListener('click', () => {
        category = String(btn.dataset.poiCategory || 'fuel');
        panel.querySelectorAll('[data-poi-category]').forEach(x => x.classList.toggle('active', x === btn));
        setState(`PRÊT · ${categoryMeta(category).label} · ${radiusM/1000} KM`);
      }));
      panel.querySelector('#auraPoiRadius')?.addEventListener('change', e => {
        radiusM = Math.max(500, Math.min(5000, Number(e.target.value) || 2000));
        setState(`PRÊT · ${categoryMeta(category).label} · ${radiusM/1000} KM`);
      });
      panel.querySelector('#auraPoiSearch')?.addEventListener('click', search);
      panel.querySelector('#auraPoiClear')?.addEventListener('click', clearMarkers);
    }

    bindToolbarState();
    panel.classList.toggle('open', panelOpen);
    root.classList.toggle('poi-mode', panelOpen);
    ensurePositionLoop();
    return true;
  }

  function boot(){
    ensureDelegatedToolbar();
    if(install()) return;
    let n = 0;
    const t = setInterval(() => { if(install() || ++n > 150) clearInterval(t); }, 120);
  }

  if(document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot, {once:true});
  else boot();
})();
