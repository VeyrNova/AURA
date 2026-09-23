(() => {
  const ROUTES = [
    {
      id:"home",
      label:"Accueil",
      aliases:["accueil","home"]
    },
    {
      id:"conversation",
      label:"Conversation",
      aliases:["conversation","chat"]
    },
    {
      id:"memory",
      label:"Mémoire",
      aliases:["mémoire","memoire","memory"]
    },
    {
      id:"tasks",
      label:"Tâches",
      aliases:["tâches","taches","tasks","task"]
    },
    {
      id:"calendar",
      label:"Agenda",
      aliases:["agenda","calendar","calendrier"]
    },
    {
      id:"modules",
      label:"Modules",
      aliases:["modules","module","apps","applications"]
    },
    {
      id:"music",
      label:"Musique",
      aliases:["musique","music"]
    },
    {
      id:"live",
      label:"AURA Live",
      aliases:["aura live","live"]
    },
    {
      id:"diagnostics",
      label:"Diagnostics",
      aliases:["diagnostics","diagnostic"]
    },
    {
      id:"settings",
      label:"Paramètres",
      aliases:["paramètres","parametres","settings","setting"]
    }
  ];

  const norm = value => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g,"")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g," ")
    .trim();

  const candidateText = el => norm([
    el.textContent,
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-route"),
    el.getAttribute("data-action"),
    el.getAttribute("data-panel"),
    el.id,
    el.className
  ].filter(Boolean).join(" "));

  const getLegacyCandidates = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return [];

    const raw = [...rail.querySelectorAll(
      ".rail-btn, button, a, [role='button'], [data-route], [data-action]"
    )];

    const seen = new Set();
    return raw.filter(el => {
      if (seen.has(el)) return false;
      seen.add(el);
      return true;
    });
  };

  const scoreCandidate = (candidate, route) => {
    const text = candidateText(candidate);
    if (!text) return 0;

    let score = 0;
    for (const aliasRaw of route.aliases){
      const alias = norm(aliasRaw);
      if (!alias) continue;
      if (text === alias) score = Math.max(score,100);
      if (text.startsWith(alias + " ")) score = Math.max(score,90);
      if (text.includes(" " + alias + " ")) score = Math.max(score,80);
      if (text.includes(alias)) score = Math.max(score,65);
    }

    if (candidate.classList.contains("rail-btn")) score += 8;
    if (candidate.tagName === "BUTTON") score += 5;
    if (candidate.hasAttribute("data-route")) score += 5;
    return score;
  };

  const resolveTargets = () => {
    const candidates = getLegacyCandidates();
    const used = new Set();
    const result = new Map();

    for (const route of ROUTES){
      const ranked = candidates
        .filter(c => !used.has(c))
        .map(c => [c,scoreCandidate(c,route)])
        .filter(([,s]) => s > 0)
        .sort((a,b) => b[1]-a[1]);

      if (ranked.length){
        const target = ranked[0][0];
        used.add(target);
        result.set(route.id,target);
      }
    }

    /* Fallback only for unresolved routes:
       use remaining rail-btn order, never the full mixed candidate list. */
    const fallback = candidates.filter(c =>
      c.classList.contains("rail-btn") && !used.has(c)
    );

    ROUTES.forEach(route => {
      if (!result.has(route.id) && fallback.length){
        const target = fallback.shift();
        used.add(target);
        result.set(route.id,target);
      }
    });

    return result;
  };

  const fireTarget = target => {
    if (!target) return false;

    try {
      target.dispatchEvent(new MouseEvent("pointerdown",{
        bubbles:true,cancelable:true,view:window
      }));
    } catch(_){}

    try { target.click(); }
    catch(_){
      try {
        target.dispatchEvent(new MouseEvent("click",{
          bubbles:true,cancelable:true,view:window
        }));
      } catch(__){}
    }
    return true;
  };

  const refreshBindings = () => {
    const dock = document.getElementById("auraR9Dock");
    if (!dock) return;

    const targets = resolveTargets();

    ROUTES.forEach(route => {
      const btn = dock.querySelector(`[data-aura-route="${route.id}"]`);
      if (!btn) return;

      const target = targets.get(route.id) || null;
      btn._auraTarget = target;
      btn.dataset.routeStatus = target ? "bound" : "missing";

      if (target){
        const t = candidateText(target);
        btn.title = `${route.label}`;
        btn.dataset.boundTarget = t.slice(0,80);
      }
    });
  };

  const retrofitDock = () => {
    const dock = document.getElementById("auraR9Dock");
    if (!dock) return false;

    const buttons = [...dock.querySelectorAll(".aura-r9-dock-btn")];
    buttons.forEach((btn,index) => {
      const route = ROUTES[index];
      if (!route) return;

      btn.dataset.auraRoute = route.id;
      btn.setAttribute("aria-label",route.label);
      btn.title = route.label;

      /* Remove the old index-based click by cloning the node. */
      const clean = btn.cloneNode(true);
      clean.dataset.auraRoute = route.id;
      clean.setAttribute("aria-label",route.label);
      clean.title = route.label;

      clean.addEventListener("click",() => {
        /* Re-resolve immediately because legacy overlays can rebuild the rail. */
        refreshBindings();
        const latest = document.querySelector(
          `#auraR9Dock .aura-r9-dock-btn[data-aura-route="${route.id}"]`
        );
        const target = latest && latest._auraTarget;
        if (!target) return;

        fireTarget(target);

        document.querySelectorAll("#auraR9Dock .aura-r9-dock-btn")
          .forEach(x => x.classList.remove("is-active"));
        latest.classList.add("is-active");

        /* Re-evaluate panels after action animation. */
        setTimeout(updateDockPosition,80);
        setTimeout(updateDockPosition,280);
      });

      btn.replaceWith(clean);
    });

    refreshBindings();
    return true;
  };

  /* Find the smallest substantial left-side overlay panel with a close control.
     Dock moves immediately to its right edge rather than covering it. */
  const findLeftPanel = () => {
    const all = [...document.querySelectorAll("body *")];
    const candidates = [];

    for (const el of all){
      if (el.id === "auraR9Dock" || el.closest("#auraR9Dock")) continue;

      const style = getComputedStyle(el);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity) === 0) continue;

      const r = el.getBoundingClientRect();
      if (r.left > 70 || r.width < 240 || r.width > 900 || r.height < 280) continue;
      if (r.right < 250 || r.bottom < 300) continue;

      /* Require a close-like control somewhere inside this panel. */
      const controls = [...el.querySelectorAll("button,[role='button']")];
      const hasClose = controls.some(b => {
        const s = norm([
          b.textContent,
          b.getAttribute("aria-label"),
          b.getAttribute("title"),
          b.className
        ].filter(Boolean).join(" "));
        const raw = String(b.textContent || "").trim();
        return s.includes("close") || s.includes("fermer") ||
               raw === "×" || raw === "✕" || raw === "X";
      });

      if (!hasClose) continue;
      candidates.push([el,r]);
    }

    if (!candidates.length) return null;

    /* Prefer the narrowest valid left-side panel: avoids selecting a huge map canvas. */
    candidates.sort((a,b) => a[1].width - b[1].width);
    return candidates[0];
  };

  const updateDockPosition = () => {
    const dock = document.getElementById("auraR9Dock");
    if (!dock) return;

    document.querySelectorAll(".aura-r9-detected-panel")
      .forEach(el => el.classList.remove("aura-r9-detected-panel"));

    const found = findLeftPanel();
    if (!found){
      dock.style.setProperty("--aura-r9-dock-left",
        window.innerWidth <= 980 ? "12px" : "22px");
      dock.classList.remove("aura-r9-panel-aware");
      return;
    }

    const [panel,r] = found;
    panel.classList.add("aura-r9-detected-panel");

    const desired = Math.min(
      window.innerWidth - 82,
      Math.max(12,r.right + 12)
    );

    dock.style.setProperty("--aura-r9-dock-left",`${Math.round(desired)}px`);
    dock.classList.add("aura-r9-panel-aware");
  };

  const boot = () => {
    let attempts = 0;

    const wait = setInterval(() => {
      attempts++;
      const dock = document.getElementById("auraR9Dock");

      if (dock){
        clearInterval(wait);
        retrofitDock();
        updateDockPosition();

        /* No DOM MutationObserver here: keep startup deterministic. */
        setInterval(() => {
          refreshBindings();
          updateDockPosition();
        },400);

        window.addEventListener("resize",updateDockPosition,{passive:true});
      }

      if (attempts > 50) clearInterval(wait);
    },100);
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }
})();
