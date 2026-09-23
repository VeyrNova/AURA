(() => {
  const DEFINITIONS = [
    {
      key:"home", label:"Accueil",
      aliases:["accueil","home"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'
    },
    {
      key:"conversation", label:"Conversation",
      aliases:["conversation","chat"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'
    },
    {
      key:"memory", label:"Mémoire",
      aliases:["memoire","memory"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'
    },
    {
      key:"tasks", label:"Tâches",
      aliases:["taches","tasks","task"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'
    },
    {
      key:"calendar", label:"Agenda",
      aliases:["agenda","calendar","calendrier"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'
    },
    {
      key:"modules", label:"Modules",
      aliases:["modules","apps","applications"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'
    },
    {
      key:"music", label:"Musique",
      aliases:["musique","music"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'
    },
    {
      key:"live", label:"AURA Live",
      aliases:["aura live","live"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'
    },
    {
      key:"diagnostics", label:"Diagnostics",
      aliases:["diagnostics","diagnostic"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'
    },
    {
      key:"settings", label:"Paramètres",
      aliases:["parametres","settings","reglages"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><circle cx="12" cy="12" r="8"/></svg>'
    }
  ];

  let mapping = new Map();
  let mappingObservers = [];
  let panelScanPending = false;

  const normalize = value =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g,"")
      .toLowerCase()
      .replace(/\s+/g," ")
      .trim();

  const signature = el => {
    const ds = el && el.dataset ? Object.values(el.dataset).join(" ") : "";
    return normalize([
      el?.getAttribute?.("aria-label"),
      el?.getAttribute?.("title"),
      el?.getAttribute?.("data-nav"),
      el?.getAttribute?.("data-view"),
      el?.id,
      el?.className,
      ds,
      el?.textContent
    ].filter(Boolean).join(" "));
  };

  const candidates = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return [];
    return [...rail.querySelectorAll(".rail-btn,button,a,[role='button']")]
      .filter(el => el !== rail);
  };

  const resolveMapping = () => {
    mappingObservers.forEach(o => o.disconnect());
    mappingObservers = [];

    const list = candidates();
    const used = new Set();
    const next = new Map();

    for (const def of DEFINITIONS){
      let best = null;
      let bestScore = 0;

      for (const el of list){
        if (used.has(el)) continue;
        const sig = signature(el);
        if (!sig) continue;

        let score = 0;
        for (const aliasRaw of def.aliases){
          const alias = normalize(aliasRaw);
          if (sig === alias) score = Math.max(score,100);
          else if (sig.includes(` ${alias} `)) score = Math.max(score,90);
          else if (sig.startsWith(alias + " ") || sig.endsWith(" " + alias)) score = Math.max(score,82);
          else if (sig.includes(alias)) score = Math.max(score,70);
        }

        if (score > bestScore){
          best = el;
          bestScore = score;
        }
      }

      /* No blind positional fallback: wrong action is worse than disabled. */
      if (best && bestScore >= 70){
        used.add(best);
        next.set(def.key,best);
      }
    }

    mapping = next;
    updateDockMappedState();
    watchMappedTargets();
    syncActive();
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

  const createDock = () => {
    if (document.getElementById("auraR10Dock")) return;

    const dock = document.createElement("nav");
    dock.id = "auraR10Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    DEFINITIONS.forEach(def => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "aura-r10-btn";
      button.dataset.auraKey = def.key;
      button.title = def.label;
      button.setAttribute("aria-label",def.label);

      const icon = document.createElement("span");
      icon.className = "aura-r10-icon";
      icon.setAttribute("aria-hidden","true");
      icon.innerHTML = def.svg;

      const label = document.createElement("span");
      label.className = "aura-r10-label";
      label.setAttribute("aria-hidden","true");
      label.textContent = def.label;

      button.append(icon,label);

      button.addEventListener("click",() => {
        const target = mapping.get(def.key);
        if (!target){
          button.classList.add("is-unmapped");
          return;
        }

        try{
          target.click();
        }catch(_){
          target.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,view:window}));
        }

        requestAnimationFrame(() => {
          syncActive();
          schedulePanelScan();
        });
      });

      dock.appendChild(button);
    });

    document.body.appendChild(dock);
    bindLens(dock);

    const handle = document.createElement("button");
    handle.id = "auraR10DockHandle";
    handle.type = "button";
    handle.title = "Fermer le panneau actif";
    handle.setAttribute("aria-label","Fermer le panneau actif");
    handle.innerHTML = "‹";
    handle.addEventListener("click",() => {
      const close = findVisibleCloseButton();
      if (close) close.click();
      setTimeout(schedulePanelScan,80);
    });
    document.body.appendChild(handle);
  };

  const updateDockMappedState = () => {
    document.querySelectorAll(".aura-r10-btn").forEach(btn => {
      const key = btn.dataset.auraKey;
      const mapped = mapping.has(key);
      btn.classList.toggle("is-unmapped",!mapped);
      btn.disabled = !mapped;
      const def = DEFINITIONS.find(d => d.key === key);
      btn.title = mapped ? def.label : `${def.label} — liaison introuvable`;
    });
  };

  const targetIsActive = el => {
    if (!el) return false;
    return el.classList.contains("active") ||
      el.getAttribute("aria-selected") === "true" ||
      el.getAttribute("aria-current") === "page" ||
      el.dataset.active === "true";
  };

  const syncActive = () => {
    let activeKey = null;
    for (const def of DEFINITIONS){
      if (targetIsActive(mapping.get(def.key))){
        activeKey = def.key;
        break;
      }
    }
    if (!activeKey) activeKey = "home";

    document.querySelectorAll(".aura-r10-btn").forEach(btn => {
      btn.classList.toggle("is-active",btn.dataset.auraKey === activeKey);
    });
  };

  const watchMappedTargets = () => {
    for (const el of mapping.values()){
      const o = new MutationObserver(syncActive);
      o.observe(el,{attributes:true,attributeFilter:["class","aria-selected","aria-current","data-active"]});
      mappingObservers.push(o);
    }
  };

  const baseExcluded = el => {
    return !el ||
      el.id === "auraR10Dock" ||
      el.id === "auraR10DockHandle" ||
      el.closest?.("#auraR10Dock") ||
      el.closest?.(".topbar") ||
      el.closest?.(".composer") ||
      el.closest?.("#composer") ||
      el.classList?.contains("hero") ||
      el.id === "stage";
  };

  const visibleSidePanels = () => {
    const selectors = [
      "[role='dialog']",
      ".modal",
      "[class*='panel']",
      "[class*='Panel']",
      "[class*='workspace']",
      "[class*='Workspace']",
      "[class*='core']",
      "[class*='Core']"
    ].join(",");

    const result = [];
    const seen = new Set();

    for (const el of document.querySelectorAll(selectors)){
      if (seen.has(el) || baseExcluded(el)) continue;
      seen.add(el);

      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) continue;

      const r = el.getBoundingClientRect();
      if (r.width < 280 || r.height < 260) continue;
      if (r.left > 160) continue;
      if (r.width > innerWidth * .88 && r.height > innerHeight * .80) continue;

      result.push(el);
    }
    return result;
  };

  const schedulePanelScan = () => {
    if (panelScanPending) return;
    panelScanPending = true;
    requestAnimationFrame(() => {
      panelScanPending = false;
      const open = visibleSidePanels().length > 0;
      document.body.classList.toggle("aura-r10-panel-open",open);
    });
  };

  const findVisibleCloseButton = () => {
    const candidates = [...document.querySelectorAll("button,[role='button']")];
    return candidates.find(el => {
      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden") return false;
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return false;

      const sig = normalize([
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
        el.textContent,
        el.className
      ].join(" "));

      return sig.includes("fermer") ||
        sig.includes("close") ||
        sig === "x" ||
        sig === "×";
    }) || null;
  };

  const setupComposer = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input) return;

    bindLens(composer);

    if (composer.dataset.auraR10Bound === "1") return;
    composer.dataset.auraR10Bound = "1";

    const sync = () => {
      const writing = document.activeElement === input || Boolean(String(input.value || "").trim());
      composer.classList.toggle("aura-r9-writing",writing);
    };

    input.addEventListener("focus",sync);
    input.addEventListener("blur",() => setTimeout(sync,30));
    input.addEventListener("input",sync);
    sync();
  };

  const boot = () => {
    createDock();
    resolveMapping();
    setupComposer();
    schedulePanelScan();

    /* Global DOM observer only schedules semantic remap/panel scan.
       It never rewrites the historical rail. */
    const observer = new MutationObserver(mutations => {
      let railChanged = false;
      for (const m of mutations){
        if (m.target?.closest?.(".rail") || [...m.addedNodes].some(n => n.nodeType === 1 && (n.matches?.(".rail") || n.querySelector?.(".rail")))){
          railChanged = true;
          break;
        }
      }
      if (railChanged) resolveMapping();
      schedulePanelScan();
    });

    observer.observe(document.body,{childList:true,subtree:true});
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  }else{
    boot();
  }
})();
