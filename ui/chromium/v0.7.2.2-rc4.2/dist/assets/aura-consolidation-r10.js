(() => {
  "use strict";

  const PRODUCT_VERSION = "2.3";
  const RUNTIME_VERSION = "3";
  const UI_VERSION = "0.7.2.2-rc4.2";

  const ITEMS = [
    ["home","Accueil",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'],
    ["conversation","Conversation",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'],
    ["memory","Mémoire",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'],
    ["tasks","Tâches",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'],
    ["agenda","Agenda",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'],
    ["modules","Modules",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'],
    ["music","Musique",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'],
    ["aura-live","AURA Live",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'],
    ["diagnostics","Diagnostics",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'],
    ["settings","Paramètres",'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.6a7 7 0 0 0-.7-1.7l1-1.8-2.1-2.1-1.8 1a7 7 0 0 0-1.7-.7L11 2.5H8l-.6 2.1a7 7 0 0 0-1.7.7l-1.8-1-2.1 2.1 1 1.8a7 7 0 0 0-.7 1.7L.5 10.5v3l2.1.6c.2.6.4 1.2.7 1.7l-1 1.8 2.1 2.1 1.8-1c.5.3 1.1.5 1.7.7l.6 2.1h3l.6-2.1c.6-.2 1.2-.4 1.7-.7l1.8 1 2.1-2.1-1-1.8c.3-.5.5-1.1.7-1.7l2.1-.6Z" transform="scale(.82) translate(2.7 2.7)"/></svg>']
  ];

  const semanticSelector = id => {
    if (id === "music") return "#aura-music-nav-v180";
    return `.aura-p0702-nav-btn[data-rail-target="${id}"]`;
  };

  function targetFor(id){
    let el = document.querySelector(semanticSelector(id));
    if (el) return el;
    if (id === "home") return document.querySelector("#homeBtn");
    if (id === "conversation") return document.querySelector("#talkBtn");
    return null;
  }

  function activate(id){
    const target = targetFor(id);
    if (target){
      target.click();
      if (id === "settings"){
        setTimeout(() => window.AURAI18N?.apply?.(), 80);
        setTimeout(ensureVersionBlock, 160);
      }
      return true;
    }

    const api = window.AuraWorkspace;
    if (!api) return false;
    if (id === "home") return api.home?.() !== false;
    if (id === "conversation") return api.open?.("talk") !== false;
    if (id === "memory") return api.open?.("memory") !== false;
    if (id === "aura-live") return api.open?.("aura-live") !== false;
    if (id === "diagnostics") return api.open?.("system") !== false;
    return false;
  }

  function labelFor(id, fallback){
    const en = window.AURAI18N?.getLocale?.() === "en-US";
    const map = en ? {
      home:"Home",conversation:"Conversation",memory:"Memory",tasks:"Tasks",
      agenda:"Calendar",modules:"Modules",music:"Music","aura-live":"AURA Live",
      diagnostics:"Diagnostics",settings:"Settings"
    } : {
      home:"Accueil",conversation:"Conversation",memory:"Mémoire",tasks:"Tâches",
      agenda:"Agenda",modules:"Modules",music:"Musique","aura-live":"AURA Live",
      diagnostics:"Diagnostics",settings:"Paramètres"
    };
    return map[id] || fallback;
  }

  function bindLens(el){
    if (!el || el.dataset.r10Lens === "1") return;
    el.dataset.r10Lens = "1";
    el.addEventListener("pointermove", e => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const x = Math.max(0,Math.min(100,((e.clientX-r.left)/r.width)*100));
      const y = Math.max(0,Math.min(100,((e.clientY-r.top)/r.height)*100));
      el.style.setProperty("--gx",`${x.toFixed(1)}%`);
      el.style.setProperty("--gy",`${y.toFixed(1)}%`);
    });
    el.addEventListener("pointerleave",()=>{
      el.style.setProperty("--gx","50%");
      el.style.setProperty("--gy","50%");
    });
  }

  function ensureDock(){
    let dock = document.getElementById("auraR10Dock");
    if (!dock){
      dock = document.createElement("nav");
      dock.id = "auraR10Dock";
      dock.setAttribute("aria-label","Navigation AURA");
      ITEMS.forEach(([id,label,svg])=>{
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "aura-r10-dock-btn";
        btn.dataset.r10Target = id;
        const icon = document.createElement("span");
        icon.className = "aura-r10-dock-icon";
        icon.innerHTML = svg;
        const text = document.createElement("span");
        text.className = "aura-r10-dock-label";
        text.textContent = labelFor(id,label);
        btn.append(icon,text);
        btn.title = labelFor(id,label);
        btn.setAttribute("aria-label",labelFor(id,label));
        btn.addEventListener("click",()=>activate(id));
        dock.appendChild(btn);
      });
      document.body.appendChild(dock);
      bindLens(dock);
    }
    syncDockLabels();
    syncActive();
    return dock;
  }

  function syncDockLabels(){
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;
    dock.querySelectorAll("[data-r10-target]").forEach(btn=>{
      const id = btn.dataset.r10Target;
      const label = labelFor(id,id);
      const span = btn.querySelector(".aura-r10-dock-label");
      if (span) span.textContent = label;
      btn.title = label;
      btn.setAttribute("aria-label",label);
    });
  }

  function visible(el){
    if (!el || !el.isConnected) return false;
    if (el.hidden) return false;
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 20 && r.height > 20;
  }

  function syncLayout(){
    const mapsOpen =
      visible(document.querySelector("#auraNavigationWorkspace.open")) ||
      document.body.classList.contains("aura-navigation-active");

    const leftSelectors = [
      ".aura-p0623-drawer.open",
      ".aura-p0626-memory.open",
      ".aura-p0627-system.open",
      ".conversation.open",
      ".aura-p0702-popover.open",
      "#aura-roadmap-workspace-v25e"
    ];

    const leftOpen = leftSelectors.some(sel=>{
      const el = document.querySelector(sel);
      if (!visible(el)) return false;
      const r = el.getBoundingClientRect();
      return r.left < innerWidth * .38;
    });

    document.body.classList.toggle("aura-r10-maps-open",mapsOpen);
    document.body.classList.toggle("aura-r10-left-panel-open",!mapsOpen && leftOpen);
  }

  function syncActive(){
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    let active = "home";
    const settings = document.querySelector(".aura-p0702-settings-popover");
    const modules = document.querySelector(".aura-p0702-modules-popover");
    const music = document.querySelector("#aura-music-player-v180");

    if (visible(settings)) active = "settings";
    else if (visible(modules)) active = "modules";
    else if (music?.classList.contains("open")) active = "music";
    else {
      const w = window.AuraWorkspace?.current?.() || document.body.dataset.auraWorkspace || "home";
      if (w === "talk") active = "conversation";
      else if (w === "memory") active = "memory";
      else if (w === "plan"){
        const agendaActive =
          document.querySelector('.aura-p0623-drawer [data-tab="calendar"].active,.aura-p0623-drawer [data-tab="reminders"].active');
        active = agendaActive ? "agenda" : "tasks";
      }
      else if (w === "aura-live") active = "aura-live";
      else if (w === "system") active = "diagnostics";
      else if (w === "maps" || w === "weather") active = "modules";
    }

    dock.querySelectorAll("[data-r10-target]").forEach(btn=>{
      btn.classList.toggle("is-active",btn.dataset.r10Target === active);
    });
  }

  function applyVersions(){
    const coreSub = document.querySelector("#coreSub");
    if (coreSub) coreSub.textContent = `AURA v${PRODUCT_VERSION} · Runtime v${RUNTIME_VERSION}`;

    const telemetryVersion = document.querySelector("aside.telemetry .panel-title i");
    if (telemetryVersion) telemetryVersion.textContent = `AURA v${PRODUCT_VERSION} · RUNTIME v${RUNTIME_VERSION}`;

    ensureVersionBlock();
  }

  function ensureVersionBlock(){
    const body = document.querySelector(".aura-p0702-settings-body");
    if (!body || document.getElementById("auraR10VersionBlock")) return;

    const box = document.createElement("div");
    box.id = "auraR10VersionBlock";
    box.style.cssText =
      "margin-top:12px;padding:11px 12px;border:1px solid rgba(120,200,255,.18);border-radius:11px;background:rgba(6,18,34,.28);display:grid;gap:5px";

    const en = window.AURAI18N?.getLocale?.() === "en-US";
    box.innerHTML = `
      <small style="opacity:.62;letter-spacing:.08em">${en ? "VERSIONS" : "VERSIONS"}</small>
      <b>AURA v${PRODUCT_VERSION}</b>
      <span style="font-size:11px;opacity:.76">Runtime v${RUNTIME_VERSION} · UI ${UI_VERSION}</span>
    `;
    body.appendChild(box);
  }

  function ensureRoadmapBanner(){
    const root = document.querySelector("#aura-roadmap-workspace-v25e");
    const header = root?.querySelector(".aura-roadmap-v25e__header");
    if (!root || !header) return;
    let box = document.getElementById("auraR10RoadmapCurrent");
    if (!box){
      box = document.createElement("div");
      box.id = "auraR10RoadmapCurrent";
      header.insertAdjacentElement("afterend",box);
    }
    const en = window.AURAI18N?.getLocale?.() === "en-US";
    box.innerHTML = en ? `
      <strong>CURRENT TRACK · 20/09/2026</strong>
      <p>AURA v${PRODUCT_VERSION} · Runtime v${RUNTIME_VERSION} · UI ${UI_VERSION}<br>
      Repository integrity repair closed. UI V2 foundation + shell parity merged but dormant.
      Current local track: RC4.2 premium/liquid-glass validation.
      P240 installer certification remains paused; P250 Command Center is queued.
      GitHub synchronization remains blocked until local validation.</p>
    ` : `
      <strong>ÉTAT COURANT · 20/09/2026</strong>
      <p>AURA v${PRODUCT_VERSION} · Runtime v${RUNTIME_VERSION} · UI ${UI_VERSION}<br>
      Réparation d’intégrité du dépôt clôturée. Fondation UI V2 + shell parity fusionnées mais dormantes.
      Chantier local actuel : validation UI premium/liquid glass sur RC4.2.
      Certification installateur P240 toujours en pause ; P250 Command Center reste en attente.
      Synchronisation GitHub bloquée jusqu’à validation locale.</p>
    `;
  }

  function setupComposer(){
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input) return;
    bindLens(composer);
  }

  function tick(){
    ensureDock();
    syncLayout();
    syncActive();
    applyVersions();
    ensureRoadmapBanner();
    setupComposer();
  }

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",tick,{once:true});
  } else tick();

  window.addEventListener("aura:workspace-changed",()=>{
    setTimeout(()=>{syncLayout();syncActive()},20);
  });
  window.addEventListener("aura:locale-changed",()=>{
    syncDockLabels();
    ensureVersionBlock();
    ensureRoadmapBanner();
    setTimeout(()=>window.AURAI18N?.apply?.(),20);
  });

  document.addEventListener("click",()=>{
    setTimeout(()=>{syncLayout();syncActive();ensureRoadmapBanner();},30);
  },true);

  /* Safe observer: only schedules reconciliation; no subtree rewriting loop. */
  let pending = false;
  const mo = new MutationObserver(()=>{
    if (pending) return;
    pending = true;
    requestAnimationFrame(()=>{
      pending = false;
      tick();
    });
  });
  mo.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:["class","hidden"]});

  setTimeout(tick,500);
  setTimeout(tick,1500);
})();
