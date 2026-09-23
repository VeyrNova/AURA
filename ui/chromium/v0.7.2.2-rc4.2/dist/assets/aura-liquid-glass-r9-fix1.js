(() => {
  const ITEMS = [
    { key:"home", label:"Accueil", aliases:["accueil","home"] },
    { key:"conversation", label:"Conversation", aliases:["conversation","chat"] },
    { key:"memory", label:"Mémoire", aliases:["memoire","memory"] },
    { key:"tasks", label:"Tâches", aliases:["taches","tasks","task"] },
    { key:"agenda", label:"Agenda", aliases:["agenda","calendar","calendrier"] },
    { key:"modules", label:"Modules", aliases:["modules","apps","applications"] },
    { key:"music", label:"Musique", aliases:["musique","music"] },
    { key:"live", label:"AURA Live", aliases:["aura live","live"] },
    { key:"diagnostics", label:"Diagnostics", aliases:["diagnostics","diagnostic"] },
    { key:"settings", label:"Paramètres", aliases:["parametres","settings","setting"] }
  ];

  const normalize = (value) =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g,"")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g," ")
      .replace(/\s+/g," ")
      .trim();

  const getOriginalCandidates = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return [];
    return [...rail.querySelectorAll(".rail-btn, button, a, [role='button']")]
      .filter((el,index,array) => array.indexOf(el) === index);
  };

  const descriptor = (el) => normalize([
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-nav"),
    el.getAttribute("data-route"),
    el.getAttribute("data-target"),
    el.textContent
  ].filter(Boolean).join(" "));

  const scoreTarget = (el,item) => {
    const d = descriptor(el);
    if (!d) return -1;

    let score = 0;
    for (const alias of item.aliases.map(normalize)) {
      if (d === alias) score = Math.max(score,100);
      else if (d.startsWith(alias + " ")) score = Math.max(score,90);
      else if (d.includes(" " + alias + " ")) score = Math.max(score,80);
      else if (d.includes(alias)) score = Math.max(score,65);
    }

    /* Avoid accidental cross-links. */
    const disallow = {
      home:["conversation","memoire","taches","agenda","modules","musique","diagnostic","parametre"],
      conversation:["aura live"],
      memory:["music","musique"],
      tasks:["agenda"],
      agenda:["taches"],
      modules:["diagnostic"],
      music:["memoire"],
      live:["musique"],
      diagnostics:["parametre"],
      settings:["diagnostic"]
    };
    for (const bad of (disallow[item.key] || [])) {
      if (d.includes(normalize(bad))) score -= 25;
    }
    return score;
  };

  const resolveTarget = (item) => {
    const candidates = getOriginalCandidates();
    const ranked = candidates
      .map(el => ({el,score:scoreTarget(el,item),d:descriptor(el)}))
      .filter(x => x.score > 0)
      .sort((a,b) => b.score-a.score);

    return ranked.length ? ranked[0].el : null;
  };

  const dock = () => document.getElementById("auraR9Dock");

  const setActiveKey = (key) => {
    const d = dock();
    if (!d) return;
    d.querySelectorAll(".aura-r9-dock-btn").forEach(btn => {
      btn.classList.toggle("is-active",btn.dataset.auraKey === key);
    });
  };

  const decorateDock = () => {
    const d = dock();
    if (!d || d.dataset.auraR9Fix1 === "1") return;
    d.dataset.auraR9Fix1 = "1";

    const buttons = [...d.querySelectorAll(".aura-r9-dock-btn")];
    buttons.forEach((btn,index) => {
      const item = ITEMS[index];
      if (!item) return;

      btn.dataset.auraKey = item.key;
      btn.setAttribute("aria-label",item.label);
      btn.title = item.label;

      /* Replace only the click routing; visual SVG from R9 is preserved. */
      const replacement = btn.cloneNode(true);
      replacement.dataset.auraKey = item.key;
      replacement.setAttribute("aria-label",item.label);
      replacement.title = item.label;

      replacement.addEventListener("click",() => {
        const target = resolveTarget(item);
        if (!target) {
          replacement.classList.add("aura-r9-link-error");
          replacement.title = `${item.label} — lien introuvable`;
          console.warn("[AURA R9 FIX1] target not found:",item.key);
          return;
        }

        replacement.classList.remove("aura-r9-link-error");
        target.click();
        setActiveKey(item.key);

        if (item.key === "home") {
          document.body.classList.remove("aura-r9-panel-mode");
        } else {
          document.body.classList.add("aura-r9-panel-mode");
        }

        setTimeout(scanOperationalPanels,180);
        setTimeout(scanOperationalPanels,650);
      });

      btn.replaceWith(replacement);
    });
  };

  const visible = (el) => {
    if (!el || !(el instanceof Element)) return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  };

  const isCloseControl = (el) => {
    const d = normalize([
      el.getAttribute("aria-label"),
      el.getAttribute("title"),
      el.textContent
    ].filter(Boolean).join(" "));
    return d === "x" || d === "×" || d.includes("fermer") || d.includes("close");
  };

  const findPanelAncestor = (close) => {
    let node = close.parentElement;
    for (let depth=0; node && depth<9; depth++, node=node.parentElement) {
      if (node === document.body || node === document.documentElement) break;
      if (node.matches(".topbar,.hero,.workspace,.composer,#composer,#auraR9Dock,.rail")) continue;

      const r = node.getBoundingClientRect();
      if (r.width >= 320 && r.height >= 240 && r.width <= innerWidth*0.98 && r.height <= innerHeight*0.96) {
        return node;
      }
    }
    return null;
  };

  const scanOperationalPanels = () => {
    const closeControls = [...document.querySelectorAll("button,[role='button'],a")]
      .filter(el => visible(el) && isCloseControl(el));

    const panels = [];
    for (const close of closeControls) {
      const panel = findPanelAncestor(close);
      if (panel && !panels.includes(panel)) panels.push(panel);
    }

    panels.forEach(panel => panel.classList.add("aura-r9-panel-surface"));

    /* Do not mistake the host's top-center X for an AURA panel. */
    const realPanels = panels.filter(panel => {
      const r = panel.getBoundingClientRect();
      return r.left < innerWidth * .72 && r.top > 55;
    });

    document.body.classList.toggle("aura-r9-panel-mode", realPanels.length > 0);

    if (!realPanels.length) {
      /* If the active original nav says home, restore Home active state. */
      const home = resolveTarget(ITEMS[0]);
      if (home && home.classList.contains("active")) setActiveKey("home");
    }
  };

  const setupComposerLens = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input || composer.dataset.auraR9Fix1Composer === "1") return;
    composer.dataset.auraR9Fix1Composer = "1";

    const sync = () => {
      composer.classList.toggle(
        "aura-r9-writing",
        document.activeElement === input || Boolean(String(input.value || "").trim())
      );
    };
    input.addEventListener("focus",sync);
    input.addEventListener("blur",() => setTimeout(sync,30));
    input.addEventListener("input",sync);
    sync();
  };

  const boot = () => {
    decorateDock();
    setupComposerLens();
    scanOperationalPanels();

    /* Safe periodic read-only reconciliation.
       No DOM observer and no innerHTML mutation loop. */
    window.setInterval(scanOperationalPanels,700);

    document.addEventListener("click",(event) => {
      const control = event.target.closest("button,[role='button'],a");
      if (control && isCloseControl(control)) {
        setTimeout(scanOperationalPanels,120);
        setTimeout(scanOperationalPanels,420);
      }
    },true);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }
})();
