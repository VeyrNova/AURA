(() => {
  window.__AURA_R16_CLEAN_CONSOLIDATED__ = true;
  window.__AURA_R16_1_UI_STABILITY__ = true;
  const ITEMS = [
    { key:"accueil", label:"Accueil", aliases:["accueil","home"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>' },
    { key:"conversation", label:"Conversation", aliases:["conversation","chat"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>' },
    { key:"memoire", label:"Mémoire", aliases:["memoire","memory"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>' },
    { key:"taches", label:"Tâches", aliases:["taches","tasks"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>' },
    { key:"agenda", label:"Agenda", aliases:["agenda","calendar","calendrier"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>' },
    { key:"modules", label:"Modules", aliases:["modules","apps","applications"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>' },
    { key:"musique", label:"Musique", aliases:["musique","music"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>' },
    { key:"aura-live", label:"AURA Live", aliases:["aura live","live"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>' },
    { key:"diagnostics", label:"Diagnostics", aliases:["diagnostics","diagnostic"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>' },
    { key:"parametres", label:"Paramètres", aliases:["parametres","settings"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></svg>' }
  ];

  const normalize = value =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g,"")
      .replace(/\s+/g," ")
      .trim()
      .toLowerCase();

  const semanticText = el => normalize([
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-label"),
    el.getAttribute("data-section"),
    el.textContent
  ].filter(Boolean).join(" "));

  const sourceButtons = () => [...document.querySelectorAll(".rail .rail-btn")];

  const scoreTarget = (el,item) => {
    const text = semanticText(el);
    if (!text) return -1;

    const canonical = normalize(item.label);
    if (text === canonical) return 100;
    if (text.startsWith(canonical)) return 95;
    if (text.includes(canonical)) return 90;

    let best = -1;
    for (const alias of item.aliases){
      const a = normalize(alias);
      if (text === a) best = Math.max(best,88);
      else if (text.startsWith(a)) best = Math.max(best,82);
      else if (text.includes(a)) best = Math.max(best,76);
    }
    return best;
  };

  const findSemanticTarget = item => {
    const sources = sourceButtons();
    let best = null;
    let bestScore = -1;

    for (const el of sources){
      const score = scoreTarget(el,item);
      if (score > bestScore){
        best = el;
        bestScore = score;
      }
    }

    if (best && bestScore >= 70) return best;

    /* strict fallback only: search other clickable controls by exact semantics */
    const candidates = [...document.querySelectorAll(
      "button,[role='button'],a,[tabindex]"
    )].filter(el => !el.closest("#auraR10Dock"));

    for (const el of candidates){
      const score = scoreTarget(el,item);
      if (score > bestScore){
        best = el;
        bestScore = score;
      }
    }

    return bestScore >= 88 ? best : null;
  };

  const bindLens = el => {
    if (!el || el.dataset.auraR10Lens === "1") return;
    el.dataset.auraR10Lens = "1";

    el.addEventListener("pointermove",e => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;

      const x = Math.max(0,Math.min(100,((e.clientX-r.left)/r.width)*100));
      const y = Math.max(0,Math.min(100,((e.clientY-r.top)/r.height)*100));

      el.style.setProperty("--gx",`${x.toFixed(1)}%`);
      el.style.setProperty("--gy",`${y.toFixed(1)}%`);
    });

    el.addEventListener("pointerleave",() => {
      el.style.setProperty("--gx","50%");
      el.style.setProperty("--gy","50%");
    });
  };

  /* --------------------------------------------------------------
     Left-overlay detection / safe positioning
     -------------------------------------------------------------- */
  const excludedPanel = el => {
    if (!el || !(el instanceof HTMLElement)) return true;
    if (el.closest("#auraR10Dock")) return true;
    if (el.matches("html,body,#app,.topbar,.workspace,.hero,#stage,.composer,#composer,.telemetry,.rail")) return true;
    if (el.closest(".topbar,.composer,#composer")) return true;
    return false;
  };

  const detectLeftPanel = () => {
    const existing = [...document.querySelectorAll(".aura-r10-safe-panel")];
    for (const el of existing){
      const cs = getComputedStyle(el);
      const r = el.getBoundingClientRect();
      if (cs.display === "none" || cs.visibility === "hidden" || r.width < 50 || r.height < 50){
        el.classList.remove("aura-r10-safe-panel");
      }
    }

    const candidates = [...document.body.querySelectorAll("*")]
      .filter(el => {
        if (excludedPanel(el)) return false;

        const cs = getComputedStyle(el);
        if (!["fixed","absolute","sticky"].includes(cs.position)) return false;
        if (cs.display === "none" || cs.visibility === "hidden") return false;
        if (Number(cs.opacity || 1) < .08) return false;

        const r = el.getBoundingClientRect();

        if (r.left > 48) return false;
        if (r.top < 48) return false;
        if (r.width < 280 || r.height < 220) return false;

        /* Exclude full-screen shells/backdrops. */
        if (r.width > innerWidth * .94 && r.height > innerHeight * .88) return false;

        return true;
      })
      .sort((a,b) => {
        const ar=a.getBoundingClientRect();
        const br=b.getBoundingClientRect();
        return (br.width*br.height) - (ar.width*ar.height);
      });

    const panel = candidates[0];
    if (panel){
      for (const el of existing){
        if (el !== panel) el.classList.remove("aura-r10-safe-panel");
      }
      panel.classList.add("aura-r10-safe-panel");
    }
  };

  const schedulePanelScan = () => {
    requestAnimationFrame(() => {
      detectLeftPanel();
      setTimeout(detectLeftPanel,80);
      setTimeout(detectLeftPanel,260);
      setTimeout(detectLeftPanel,600);
    });
  };

  /* --------------------------------------------------------------
     Dock
     -------------------------------------------------------------- */
  const setActive = key => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    dock.querySelectorAll(".aura-r10-dock-btn").forEach(btn => {
      btn.classList.toggle("is-active",btn.dataset.key === key);
    });
  };


  /* --------------------------------------------------------------
     R16 clean direct routing
     -------------------------------------------------------------- */
  const ws = () => window.AuraWorkspace || null;

  const wsOpen = id => {
    try{
      const api=ws();
      if(!api?.open) return false;
      return api.open(id)!==false;
    }catch(err){
      console.warn("[AURA R16] workspace open failed:",id,err);
      return false;
    }
  };

  const wsHome = () => {
    try{
      const api=ws();
      if(!api?.home) return false;
      return api.home()!==false;
    }catch(err){
      console.warn("[AURA R16] workspace home failed:",err);
      return false;
    }
  };

  const openPlan = mode => {
    const opened=wsOpen("plan");
    const selector=mode==="agenda"
      ? '.aura-p0623-drawer [data-tab="reminders"]'
      : '.aura-p0623-drawer [data-tab="tasks"]';
    const pick=()=>document.querySelector(selector)?.click();
    [30,90,180,360,650].forEach(ms=>setTimeout(pick,ms));
    return opened;
  };

  const clickExact = selector => {
    const el=document.querySelector(selector);
    if(!el) return false;
    el.click();
    return true;
  };

  const wakeSettingsI18n = () => {
    try{
      const proxy=document.createElement("button");
      proxy.type="button";
      proxy.dataset.railTarget="settings";
      proxy.style.cssText="position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;opacity:0;pointer-events:none";
      document.body.appendChild(proxy);
      proxy.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,composed:true}));
      proxy.remove();
    }catch(_){}
  };

  const ensureSettingsLanguage = panel => {
    const body=panel?.querySelector(".aura-p0702-settings-body");
    if(!body || body.querySelector("[data-aura-language-setting]")) return;

    setTimeout(()=>{
      if(body.querySelector("[data-aura-language-setting]")) return;

      const wrap=document.createElement("div");
      wrap.dataset.auraLanguageSetting="1";
      wrap.style.cssText="margin-top:14px;padding:13px;border:1px solid rgba(120,220,255,.18);border-radius:14px;background:rgba(6,18,34,.48);display:grid;gap:9px";

      const title=document.createElement("div");
      title.innerHTML="<small style='display:block;opacity:.62;letter-spacing:.09em'>GÉNÉRAL / GENERAL</small><b>Langue / Language</b>";

      const select=document.createElement("select");
      select.setAttribute("aria-label","Langue / Language");
      select.style.cssText="width:100%;padding:10px 11px;border-radius:10px;border:1px solid rgba(120,220,255,.28);background:#0b1b2f;color:#eef7ff";
      select.innerHTML="<option value='fr-FR'>Français</option><option value='en-US'>English</option>";

      const note=document.createElement("small");
      note.style.cssText="opacity:.70;line-height:1.4";
      note.textContent="Le texte, la reconnaissance vocale et Camilla/XTTS suivent cette langue.";

      wrap.append(title,select,note);
      body.appendChild(wrap);

      const token=new URLSearchParams(location.search).get("token")||"";
      let current=window.AURAI18N?.getLocale?.()||window.__AURA_BOOT_LOCALE__||"fr-FR";
      select.value=current==="en-US"?"en-US":"fr-FR";

      select.addEventListener("change",async()=>{
        const wanted=select.value;
        const previous=current;
        select.disabled=true;
        note.textContent=wanted==="en-US"?"Applying language…":"Application de la langue…";
        try{
          if(!token) throw new Error("missing_token");
          const response=await fetch(`/api/locale?token=${encodeURIComponent(token)}`,{
            method:"POST",
            cache:"no-store",
            headers:{"Content-Type":"application/json"},
            body:JSON.stringify({action:"set",locale:wanted})
          });
          const data=await response.json().catch(()=>({}));
          if(!response.ok) throw new Error(data.error||`locale ${response.status}`);
          current=data?.locale||wanted;
          window.AURAI18N?.setLocale?.(current);
          window.dispatchEvent(new CustomEvent("aura:runtime-locale-changed",{detail:data||{locale:current}}));
          note.textContent=current==="en-US"?"Language applied to AURA.":"Langue appliquée à AURA.";
        }catch(err){
          select.value=previous;
          note.textContent=previous==="en-US"?"Unable to change language.":"Impossible de changer la langue.";
        }finally{
          select.disabled=false;
        }
      });
    },140);
  };

  const closeSettingsDirect = () => {
    const panel=document.querySelector(".aura-p0702-settings-popover");
    if(!panel) return false;

    panel.classList.remove("open","aura-r16-settings");
    panel.hidden=true;

    try{
      const api=ws();
      api?.overlay?.close?.("rail-settings");
    }catch(_){}

    return true;
  };

  const openSettingsDirect = () => {
    try{ window.AuraAccessibility?.close?.(); }catch(_){}
    const accessibility=document.getElementById("aura-p075-panel");
    if(accessibility){
      accessibility.classList.remove("open");
      accessibility.hidden=true;
    }

    const panel=document.querySelector(".aura-p0702-settings-popover");
    if(!panel){
      console.warn("[AURA R16.1] Settings panel unavailable");
      return false;
    }

    if(!panel.hidden && panel.classList.contains("open")){
      return closeSettingsDirect();
    }

    const modules=document.querySelector(".aura-p0702-modules-popover");
    if(modules){
      modules.classList.remove("open");
      modules.hidden=true;
    }

    panel.hidden=false;
    panel.classList.add("open","aura-r16-settings");
    wakeSettingsI18n();
    ensureSettingsLanguage(panel);
    return true;
  };

  const openMusicDirect = () => {
    const nav=document.getElementById("aura-music-nav-v180");
    const root=document.getElementById("aura-music-player-v180");

    if(nav && typeof nav.onclick==="function"){
      try{
        nav.onclick.call(nav);
        const opened=document.getElementById("aura-music-player-v180");
        if(opened){
          opened.hidden=false;
          opened.classList.add("open");
          opened.style.setProperty("z-index","9000","important");
        }
        return true;
      }catch(err){
        console.error("[AURA R16] historical openMusic handler failed:",err);
      }
    }

    if(root){
      root.hidden=false;
      root.classList.add("open");
      root.style.setProperty("z-index","9000","important");
      return true;
    }

    console.warn("[AURA R16] Premium music player unavailable");
    return false;
  };

  const routeDirect = key => {
    if(key!=="parametres") closeSettingsDirect();

    switch(key){
      case "accueil": return wsHome() || clickExact('.aura-p0702-nav-btn[data-rail-target="home"]');
      case "conversation": return wsOpen("talk");
      case "memoire": return wsOpen("memory");
      case "taches": return openPlan("tasks");
      case "agenda": return openPlan("agenda");
      case "modules": return clickExact('.aura-p0702-nav-btn[data-rail-target="modules"]');
      case "musique": return openMusicDirect();
      case "aura-live": return wsOpen("aura-live");
      case "diagnostics": return wsOpen("system");
      case "parametres": return openSettingsDirect();
      default: return false;
    }
  };

  document.addEventListener("click",event => {
    if(event.target?.closest?.(".aura-p0702-settings-popover [data-pop-close]")){
      closeSettingsDirect();
    }
  },true);

  window.addEventListener("aura:workspace-changed",() => {
    closeSettingsDirect();
    setTimeout(schedulePanelScan,0);
  });

  const enforceDockViewport = () => {
    const dock=document.getElementById("auraR10Dock");
    if(!dock) return;
    dock.classList.add("aura-r16-contained");
  };

  const buildDock = () => {
    if (document.getElementById("auraR10Dock")) return;

    const dock = document.createElement("nav");
    dock.id = "auraR10Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    for (const item of ITEMS){
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "aura-r10-dock-btn";
      btn.dataset.key = item.key;
      btn.title = item.label;
      btn.setAttribute("aria-label",item.label);

      const icon = document.createElement("span");
      icon.className = "aura-r10-dock-icon";
      icon.setAttribute("aria-hidden","true");
      icon.innerHTML = item.svg;

      const label = document.createElement("span");
      label.className = "aura-r10-dock-label";
      label.setAttribute("aria-hidden","true");
      label.textContent = item.label;

      btn.append(icon,label);

      btn.addEventListener("click",() => {
        const ok = routeDirect(item.key);
        if (!ok){
          console.warn("[AURA R16] Direct route unavailable:",item.label);
          return;
        }

        setActive(item.key);
        schedulePanelScan();
      });

      dock.appendChild(btn);
    }

    dock.addEventListener("mouseenter",() => {
      document.body.classList.add("aura-r10-dock-open");
      schedulePanelScan();
    });

    dock.addEventListener("mouseleave",() => {
      document.body.classList.remove("aura-r10-dock-open");
      schedulePanelScan();
    });

    dock.addEventListener("focusin",() => {
      document.body.classList.add("aura-r10-dock-open");
      schedulePanelScan();
    });

    dock.addEventListener("focusout",() => {
      setTimeout(() => {
        if (!dock.contains(document.activeElement)){
          document.body.classList.remove("aura-r10-dock-open");
          schedulePanelScan();
        }
      },30);
    });

    document.body.appendChild(dock);
    enforceDockViewport();
    window.addEventListener("resize",enforceDockViewport,{passive:true});
    bindLens(dock);
    setActive("accueil");
  };

  /* --------------------------------------------------------------
     Composer
     -------------------------------------------------------------- */
  const setupComposer = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");

    if (!composer || !input) return;

    bindLens(composer);

    if (composer.dataset.auraR10Bound === "1") return;
    composer.dataset.auraR10Bound = "1";

    const sync = () => {
      const writing =
        document.activeElement === input ||
        Boolean(String(input.value || "").trim());

      composer.classList.toggle("aura-r10-writing",writing);
    };

    input.addEventListener("focus",sync);
    input.addEventListener("blur",() => setTimeout(sync,30));
    input.addEventListener("input",sync);
    sync();
  };

  const boot = () => {
    buildDock();
    setupComposer();
    schedulePanelScan();

    /* Watch only for new nodes such as module panels.
       Attribute changes are intentionally NOT observed. */
    const observer = new MutationObserver(() => schedulePanelScan());
    observer.observe(document.body,{childList:true,subtree:true});
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }
})();

/* === AURA R16.13 TOP LEVEL LIVE PORTAL JS === */
(()=>{
  "use strict";
  if(window.__AURA_R1613_LIVE_PORTAL__) return;
  window.__AURA_R1613_LIVE_PORTAL__=true;

  const PORTAL_ID="aura-r1613-live-portal";

  const portal=()=>{
    let p=document.getElementById(PORTAL_ID);
    if(!p){
      p=document.createElement("div");
      p.id=PORTAL_ID;
      p.setAttribute("aria-label","AURA Live viewport");
      document.body.appendChild(p);
    }
    return p;
  };

  const telemetry=()=>{
    const exact=document.querySelector(".aura-p0813-system-hud-persistent");
    if(exact) return exact;
    const hero=document.querySelector(".workspace > .hero");
    return hero?.querySelector("aside.telemetry.glass") || document.querySelector("aside.telemetry.glass");
  };

  const roadmap=()=>document.getElementById("aura-roadmap-workspace-v25e");

  const moveIntoPortal=(node)=>{
    if(!node || !document.body.classList.contains("aura-live-active")) return false;
    const p=portal();
    if(node.parentNode!==p) p.appendChild(node);
    return true;
  };

  const sync=()=>{
    const live=document.body.classList.contains("aura-live-active");
    const p=document.getElementById(PORTAL_ID);

    if(!live){
      /* AuraWorkspace restores the telemetry node synchronously when
         AURA Live closes. Do not fight that restore operation. */
      if(p && p.childElementCount===0) p.remove();
      return;
    }

    moveIntoPortal(telemetry());

    if(document.body.classList.contains("aura-roadmap-editor-v25e")){
      moveIntoPortal(roadmap());
    }
  };

  const obs=new MutationObserver(sync);
  obs.observe(document.body,{
    attributes:true,
    attributeFilter:["class"],
    childList:true,
    subtree:true
  });

  document.addEventListener("aura:workspace-changed",()=>queueMicrotask(sync));
  window.addEventListener("resize",sync,{passive:true});

  /* Initial + short delayed passes cover the manager's synchronous
     re-parent followed by component render. */
  sync();
  setTimeout(sync,0);
  setTimeout(sync,80);
  setTimeout(sync,240);
})();
/* === END AURA R16.13 TOP LEVEL LIVE PORTAL JS === */

/* === AURA R16.14 ROADMAP PORTAL OPEN FIX JS === */
(()=>{
  "use strict";
  if(window.__AURA_R1614_ROADMAP_PORTAL_OPEN_FIX__) return;
  window.__AURA_R1614_ROADMAP_PORTAL_OPEN_FIX__=true;

  const PORTAL_ID="aura-r1613-live-portal";
  let fallbackTimer=0;

  const portal=()=>document.getElementById(PORTAL_ID);
  const roadmap=()=>document.getElementById("aura-roadmap-workspace-v25e");

  function putRoadmapInPortal(){
    const p=portal();
    const r=roadmap();
    if(!p || !r) return false;
    if(r.parentNode!==p) p.appendChild(r);
    return true;
  }

  function refreshRoadmapIfNativeOpenWasMissed(){
    const r=roadmap();
    if(!r) return;

    const content=r.querySelector("[data-roadmap-content]");
    const text=String(content?.textContent||"").trim().toLowerCase();

    const needsLoad=
      !content ||
      !text ||
      text.includes("chargement de la roadmap") ||
      text.includes("synchronisation roadmapservice");

    if(needsLoad){
      r.querySelector("[data-roadmap-refresh]")?.click();
    }
  }

  function ensureRoadmapOpen(){
    if(!document.body.classList.contains("aura-live-active")) return false;

    document.body.classList.add("aura-roadmap-editor-v25e");

    let attempts=0;
    const place=()=>{
      attempts++;
      if(putRoadmapInPortal()){
        clearTimeout(fallbackTimer);
        fallbackTimer=setTimeout(refreshRoadmapIfNativeOpenWasMissed,80);
        return;
      }
      if(attempts<12) setTimeout(place,40);
    };
    place();
    return true;
  }

  document.addEventListener("click",(event)=>{
    const button=event.target?.closest?.("[data-roadmap-open-v25e]");
    if(!button) return;

    setTimeout(ensureRoadmapOpen,0);
  },true);

  const observer=new MutationObserver(()=>{
    if(
      document.body.classList.contains("aura-live-active") &&
      document.body.classList.contains("aura-roadmap-editor-v25e")
    ){
      putRoadmapInPortal();
    }
  });
  observer.observe(document.body,{attributes:true,attributeFilter:["class"]});

  window.AuraR1614RoadmapPortal={
    open:ensureRoadmapOpen,
    sync:putRoadmapInPortal
  };
})();
/* === END AURA R16.14 ROADMAP PORTAL OPEN FIX JS === */