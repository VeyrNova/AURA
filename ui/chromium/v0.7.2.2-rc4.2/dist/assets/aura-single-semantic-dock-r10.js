(() => {
  const DEFINITIONS = [
    {
      id:"home", label:"Accueil",
      aliases:["accueil","home"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'
    },
    {
      id:"conversation", label:"Conversation",
      aliases:["conversation","chat"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'
    },
    {
      id:"memory", label:"Mémoire",
      aliases:["mémoire","memoire","memory"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'
    },
    {
      id:"tasks", label:"Tâches",
      aliases:["tâches","taches","tasks"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'
    },
    {
      id:"agenda", label:"Agenda",
      aliases:["agenda","calendar","calendrier"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'
    },
    {
      id:"modules", label:"Modules",
      aliases:["modules","apps","applications"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'
    },
    {
      id:"music", label:"Musique",
      aliases:["musique","music"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'
    },
    {
      id:"live", label:"AURA Live",
      aliases:["aura live","live"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'
    },
    {
      id:"diagnostics", label:"Diagnostics",
      aliases:["diagnostics","diagnostic"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'
    },
    {
      id:"settings", label:"Paramètres",
      aliases:["paramètres","parametres","settings","réglages","reglages"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 3.5v2M12 18.5v2M3.5 12h2M18.5 12h2M6 6l1.5 1.5M16.5 16.5 18 18M18 6l-1.5 1.5M7.5 16.5 6 18"/></svg>'
    }
  ];

  const normalize = value =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g,"")
      .toLowerCase()
      .replace(/\s+/g," ")
      .trim();

  const accessibleName = el => normalize([
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-route"),
    el.getAttribute("data-action"),
    el.getAttribute("data-tab"),
    el.textContent
  ].filter(Boolean).join(" "));

  const clickable = root =>
    [...root.querySelectorAll(
      'button,a,[role="button"],[data-route],[data-action],[data-tab],[tabindex]'
    )];

  const scoreRoot = root => {
    const rect = root.getBoundingClientRect();
    if (rect.width < 35 || rect.height < 160 || rect.left > 360) return -1;

    const names = clickable(root).map(accessibleName);
    let score = 0;

    for (const def of DEFINITIONS){
      const aliases = def.aliases.map(normalize);
      if (names.some(name => aliases.some(alias => name === alias || name.includes(alias)))){
        score++;
      }
    }

    return score;
  };

  const findLegacyNav = () => {
    const explicit = [...document.querySelectorAll(
      '.rail, nav, aside, [class*="rail"], [class*="sidebar"], [class*="navigation"], [class*="nav-"]'
    )];

    let best = null;
    let bestScore = -1;

    for (const root of explicit){
      if (root.id === "auraR10Dock") continue;
      const score = scoreRoot(root);
      if (score > bestScore){
        best = root;
        bestScore = score;
      }
    }

    return bestScore >= 4 ? best : document.querySelector(".rail");
  };

  const findTarget = (navRoot, def) => {
    if (!navRoot) return null;

    const aliases = def.aliases.map(normalize);
    const nodes = clickable(navRoot);

    const ranked = nodes
      .map(el => {
        const name = accessibleName(el);
        let quality = 0;

        for (const alias of aliases){
          if (name === alias) quality = Math.max(quality,100);
          else if (name.startsWith(alias)) quality = Math.max(quality,80);
          else if (name.includes(alias)) quality = Math.max(quality,60);
        }

        return {el,quality};
      })
      .filter(x => x.quality > 0)
      .sort((a,b) => b.quality-a.quality);

    return ranked[0]?.el || null;
  };

  const removeOldCustomDocks = () => {
    document.querySelectorAll(
      '#auraR9Dock,#auraR8Dock,.aura-r9-dock,.aura-r8-dock'
    ).forEach(el => el.remove());
  };

  const bindLens = el => {
    if (!el || el.dataset.auraR10Lens === "1") return;
    el.dataset.auraR10Lens = "1";

    el.addEventListener("pointermove", e => {
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

  let navRoot = null;
  const targets = new Map();

  const refreshTargets = () => {
    const candidate = findLegacyNav();
    if (candidate) navRoot = candidate;

    if (navRoot){
      navRoot.style.setProperty("display","none","important");
      navRoot.setAttribute("aria-hidden","true");
    }

    for (const def of DEFINITIONS){
      targets.set(def.id,findTarget(navRoot,def));
    }

    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    for (const def of DEFINITIONS){
      const btn = dock.querySelector(`[data-r10-id="${def.id}"]`);
      const target = targets.get(def.id);
      if (!btn) continue;

      btn.disabled = !target;
      btn.title = target ? def.label : `${def.label} — commande introuvable`;
    }
  };

  const syncActive = clickedId => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    let activeId = null;

    for (const def of DEFINITIONS){
      const target = targets.get(def.id);
      if (!target) continue;

      const active =
        target.classList.contains("active") ||
        target.getAttribute("aria-current") === "page" ||
        target.getAttribute("aria-selected") === "true" ||
        target.getAttribute("data-active") === "true";

      if (active){
        activeId = def.id;
        break;
      }
    }

    activeId = activeId || clickedId || "home";

    dock.querySelectorAll(".aura-r10-btn").forEach(btn => {
      btn.classList.toggle("is-active",btn.dataset.r10Id === activeId);
    });
  };

  const buildDock = () => {
    removeOldCustomDocks();

    let dock = document.getElementById("auraR10Dock");
    if (dock) return dock;

    dock = document.createElement("nav");
    dock.id = "auraR10Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    for (const def of DEFINITIONS){
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "aura-r10-btn";
      btn.dataset.r10Id = def.id;
      btn.setAttribute("aria-label",def.label);

      const icon = document.createElement("span");
      icon.className = "aura-r10-icon";
      icon.setAttribute("aria-hidden","true");
      icon.innerHTML = def.svg;

      const label = document.createElement("span");
      label.className = "aura-r10-label";
      label.setAttribute("aria-hidden","true");
      label.textContent = def.label;

      btn.append(icon,label);

      btn.addEventListener("click",() => {
        const target = targets.get(def.id);
        if (!target) return;

        try{
          target.click();
        }catch(_){
          target.dispatchEvent(new MouseEvent("click",{
            bubbles:true,
            cancelable:true,
            view:window
          }));
        }

        syncActive(def.id);
        setTimeout(() => syncActive(def.id),180);
        setTimeout(repositionDock,240);
      });

      dock.appendChild(btn);
    }

    document.body.appendChild(dock);
    bindLens(dock);
    return dock;
  };

  const visible = el => {
    if (!el) return false;
    const style = getComputedStyle(el);
    const r = el.getBoundingClientRect();

    return (
      style.display !== "none" &&
      style.visibility !== "hidden" &&
      Number(style.opacity || 1) > .05 &&
      r.width > 0 &&
      r.height > 0
    );
  };

  const findOpenPanel = () => {
    const closeButtons = [...document.querySelectorAll(
      'button,[role="button"],[aria-label],[title]'
    )].filter(visible);

    const probableClose = closeButtons.filter(btn => {
      const n = accessibleName(btn);
      const t = normalize(btn.textContent);
      return (
        n.includes("fermer") ||
        n.includes("close") ||
        t === "x" ||
        t === "×"
      );
    });

    let best = null;
    let bestArea = 0;

    for (const close of probableClose){
      let el = close.parentElement;

      for (let depth=0; el && depth<7; depth++,el=el.parentElement){
        if (
          !el ||
          el.id === "auraR10Dock" ||
          el === navRoot ||
          el.matches(".topbar,.hero,.composer,#composer,.rail")
        ) continue;

        const r = el.getBoundingClientRect();
        if (
          visible(el) &&
          r.left < window.innerWidth * .35 &&
          r.top > 45 &&
          r.width >= 280 &&
          r.height >= 280
        ){
          const area = r.width*r.height;
          if (area > bestArea && r.width < window.innerWidth*.94){
            best = el;
            bestArea = area;
          }
        }
      }
    }

    return best;
  };

  let lastPanel = null;

  const repositionDock = () => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    if (lastPanel && lastPanel !== document.body){
      lastPanel.classList.remove("aura-r10-front-panel");
    }

    const panel = findOpenPanel();
    lastPanel = panel;

    if (!panel){
      document.body.classList.remove("aura-r10-panel-open");
      document.documentElement.style.setProperty("--r10-dock-left","22px");
      return;
    }

    panel.classList.add("aura-r10-front-panel");
    document.body.classList.add("aura-r10-panel-open");

    const r = panel.getBoundingClientRect();
    const dockCollapsed = 58;
    const margin = 12;

    let left = r.right + margin;

    if (left + dockCollapsed > window.innerWidth - 12){
      left = window.innerWidth - dockCollapsed - 14;
    }

    left = Math.max(14,left);
    document.documentElement.style.setProperty("--r10-dock-left",`${Math.round(left)}px`);
  };

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
    refreshTargets();
    syncActive();
    setupComposer();
    repositionDock();

    /* Read-only reconciliation timer: no MutationObserver feedback loops. */
    setInterval(() => {
      refreshTargets();
      syncActive();
      repositionDock();
    },700);

    window.addEventListener("resize",repositionDock);
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  }else{
    boot();
  }
})();
