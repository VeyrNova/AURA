(() => {
  const CANON = [
    { key:"home", label:"Accueil", aliases:["accueil","home","start","dashboard"] },
    { key:"conversation", label:"Conversation", aliases:["conversation","chat","messages","message"] },
    { key:"memory", label:"Mémoire", aliases:["memoire","memory","memories"] },
    { key:"tasks", label:"Tâches", aliases:["taches","tasks","task","todo"] },
    { key:"calendar", label:"Agenda", aliases:["agenda","calendar","calendrier"] },
    { key:"modules", label:"Modules", aliases:["modules","module","apps","applications"] },
    { key:"music", label:"Musique", aliases:["musique","music","audio"] },
    { key:"live", label:"AURA Live", aliases:["aura live","live"] },
    { key:"diagnostics", label:"Diagnostics", aliases:["diagnostics","diagnostic","diag"] },
    { key:"settings", label:"Paramètres", aliases:["parametres","settings","setting","preferences","preferences systeme"] }
  ];

  const normalize = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g,"")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g," ")
    .replace(/\s+/g," ")
    .trim();

  const semanticBlob = (el) => {
    const bits = [
      el.textContent,
      el.innerText,
      el.getAttribute("aria-label"),
      el.getAttribute("title"),
      el.getAttribute("name"),
      el.getAttribute("id"),
      el.getAttribute("class"),
      el.getAttribute("data-view"),
      el.getAttribute("data-route"),
      el.getAttribute("data-panel"),
      el.getAttribute("data-action"),
      el.getAttribute("data-nav"),
      el.getAttribute("data-target")
    ];

    try {
      Object.entries(el.dataset || {}).forEach(([k,v]) => {
        bits.push(k,v);
      });
    } catch (_) {}

    return normalize(bits.filter(Boolean).join(" "));
  };

  const originalCandidates = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return [];
    return [...rail.querySelectorAll("button,a,[role='button'],.rail-btn")]
      .filter((el,index,array) => array.indexOf(el) === index);
  };

  const scoreCandidate = (el, item) => {
    const blob = semanticBlob(el);
    if (!blob) return -1;

    let score = 0;
    for (const alias of item.aliases) {
      const a = normalize(alias);
      if (!a) continue;
      if (blob === a) score = Math.max(score,100);
      else if (blob.startsWith(a+" ") || blob.endsWith(" "+a)) score = Math.max(score,85);
      else if (blob.includes(a)) score = Math.max(score,65);
    }

    if (el.classList.contains("rail-btn")) score += 10;
    return score;
  };

  const findSemanticTarget = (item) => {
    const candidates = originalCandidates()
      .map(el => ({el,score:scoreCandidate(el,item)}))
      .filter(x => x.score > 0)
      .sort((a,b) => b.score-a.score);

    if (candidates.length) return candidates[0].el;

    /* Explicit Settings fallback: search attributes globally, never by index. */
    if (item.key === "settings") {
      const all = [...document.querySelectorAll("button,a,[role='button']")];
      const fallback = all.find(el => {
        const blob = semanticBlob(el);
        return blob.includes("parametres") ||
               blob.includes("settings") ||
               blob.includes("preferences");
      });
      if (fallback) return fallback;
    }

    return null;
  };

  const showRouteError = (label) => {
    let toast = document.getElementById("auraR9RouteError");
    if (!toast) {
      toast = document.createElement("div");
      toast.id = "auraR9RouteError";
      toast.style.cssText = [
        "position:fixed","left:50%","bottom:82px","transform:translateX(-50%)",
        "z-index:9999","padding:9px 14px","border-radius:10px",
        "background:rgba(5,18,30,.96)","border:1px solid rgba(110,225,255,.22)",
        "color:#dff7ff","font:11px system-ui","box-shadow:0 14px 32px rgba(0,0,0,.3)"
      ].join(";");
      document.body.appendChild(toast);
    }
    toast.textContent = `Navigation introuvable : ${label}`;
    toast.style.display = "block";
    clearTimeout(toast._timer);
    toast._timer = setTimeout(() => { toast.style.display="none"; },2200);
  };

  /* ---- Panel safety ---- */

  const PANEL_SELECTORS = [
    "[role='dialog']",
    ".modal",
    "[class*='modal']",
    "[class*='Modal']",
    ".panel",
    "[class*='panel']",
    "[class*='Panel']",
    "[class*='window']",
    "[class*='Window']",
    "[class*='drawer']",
    "[class*='Drawer']"
  ].join(",");

  const isVisible = (el) => {
    if (!(el instanceof HTMLElement)) return false;
    const s = getComputedStyle(el);
    if (s.display === "none" || s.visibility === "hidden" || Number(s.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };

  const isMajorPanel = (el) => {
    if (!isVisible(el)) return false;
    if (el.id === "auraR9Dock") return false;
    if (el.closest("#auraR9Dock")) return false;
    if (el.matches(".hero,#stage,.topbar,.composer,#composer")) return false;
    if (el.closest(".topbar,.composer,#composer")) return false;

    const r = el.getBoundingClientRect();
    if (r.width < 280 || r.height < 230) return false;
    if (r.top < 45) return false;

    /* panels in current AURA open from the left/center */
    if (r.left > innerWidth * .60) return false;

    return true;
  };

  const decoratePanels = () => {
    document.querySelectorAll(".aura-r9-major-panel").forEach(el => {
      if (!isVisible(el)) el.classList.remove("aura-r9-major-panel");
    });

    let found = false;
    document.querySelectorAll(PANEL_SELECTORS).forEach(el => {
      if (isMajorPanel(el)) {
        el.classList.add("aura-r9-major-panel");
        found = true;
      }
    });
    return found;
  };

  let forcedPanelMode = false;

  const syncPanelMode = () => {
    const detected = decoratePanels();
    document.body.classList.toggle("aura-r9-panel-open", forcedPanelMode || detected);
  };

  const clearPanelModeSoon = () => {
    forcedPanelMode = false;
    setTimeout(syncPanelMode,160);
    setTimeout(syncPanelMode,500);
  };

  /* ---- Route dock semantically ---- */
  const installRouting = () => {
    const dock = document.getElementById("auraR9Dock");
    if (!dock || dock.dataset.auraSemanticRouting === "1") return;
    dock.dataset.auraSemanticRouting = "1";

    const buttons = [...dock.querySelectorAll(".aura-r9-dock-btn")];

    buttons.forEach((button,index) => {
      const item =
        CANON.find(x => normalize(button.getAttribute("aria-label")) === normalize(x.label)) ||
        CANON[index] ||
        null;
      if (!item) return;

      button.setAttribute("data-aura-semantic-key",item.key);

      /* Capture phase blocks the old index-based R9 handler. */
      button.addEventListener("click",(event) => {
        event.preventDefault();
        event.stopImmediatePropagation();

        const target = findSemanticTarget(item);
        if (!target) {
          showRouteError(item.label);
          return;
        }

        if (item.key === "home") {
          forcedPanelMode = false;
          document.body.classList.remove("aura-r9-panel-open");
        } else {
          forcedPanelMode = true;
          document.body.classList.add("aura-r9-panel-open");
        }

        target.click();

        buttons.forEach(b => b.classList.remove("is-active"));
        button.classList.add("is-active");

        setTimeout(syncPanelMode,120);
        setTimeout(syncPanelMode,450);
      },true);
    });
  };

  /* Any close-like control releases the dock again. */
  document.addEventListener("click",(event) => {
    const b = event.target.closest("button,a,[role='button']");
    if (!b) return;

    const blob = semanticBlob(b);
    const text = String(b.textContent || "").trim();

    const closeLike =
      blob.includes("close") ||
      blob.includes("fermer") ||
      blob.includes("dismiss") ||
      blob.includes("quitter") ||
      text === "×" ||
      text === "✕" ||
      text === "X";

    if (closeLike) clearPanelModeSoon();
  },true);

  document.addEventListener("keydown",(event) => {
    if (event.key === "Escape") clearPanelModeSoon();
  });

  const boot = () => {
    installRouting();
    syncPanelMode();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }

  /* Safe periodic read-only resync; no DOM mutation loop. */
  setInterval(() => {
    installRouting();
    syncPanelMode();
  },700);
})();
