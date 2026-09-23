(() => {
  const NAV = [
    {
      key:"home",
      label:"Accueil",
      aliases:["accueil","home"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'
    },
    {
      key:"conversation",
      label:"Conversation",
      aliases:["conversation","chat"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'
    },
    {
      key:"memory",
      label:"Mémoire",
      aliases:["memoire","memory"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'
    },
    {
      key:"tasks",
      label:"Tâches",
      aliases:["taches","tasks","task"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'
    },
    {
      key:"agenda",
      label:"Agenda",
      aliases:["agenda","calendar","calendrier"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'
    },
    {
      key:"modules",
      label:"Modules",
      aliases:["modules","apps","applications"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'
    },
    {
      key:"music",
      label:"Musique",
      aliases:["musique","music"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'
    },
    {
      key:"live",
      label:"AURA Live",
      aliases:["aura live","live"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'
    },
    {
      key:"diagnostics",
      label:"Diagnostics",
      aliases:["diagnostics","diagnostic"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'
    },
    {
      key:"settings",
      label:"Paramètres",
      aliases:["parametres","settings","setting"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.6a7 7 0 0 0-.7-1.7l1-1.8-2.1-2.1-1.8 1a7 7 0 0 0-1.7-.7L11 2.5H8l-.6 2.1a7 7 0 0 0-1.7.7l-1.8-1-2.1 2.1 1 1.8a7 7 0 0 0-.7 1.7L.5 10.5v3l2.1.6c.2.6.4 1.2.7 1.7l-1 1.8 2.1 2.1 1.8-1c.5.3 1.1.5 1.7.7l.6 2.1h3l.6-2.1c.6-.2 1.2-.4 1.7-.7l1.8 1 2.1-2.1-1-1.8c.3-.5.5-1.1.7-1.7l2.1-.6Z" transform="scale(.82) translate(2.7 2.7)"/></svg>'
    }
  ];

  const norm = (value) => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g,"")
    .toLowerCase()
    .replace(/\s+/g," ")
    .trim();

  const descriptor = (el) => {
    if (!el) return "";
    const attrs = [
      el.getAttribute("aria-label"),
      el.getAttribute("title"),
      el.getAttribute("data-route"),
      el.getAttribute("data-tab"),
      el.getAttribute("data-panel"),
      el.getAttribute("data-action"),
      el.getAttribute("data-view"),
      el.getAttribute("href"),
      el.textContent
    ];
    return norm(attrs.filter(Boolean).join(" | "));
  };

  const scoreTarget = (el,item) => {
    if (!el || el.closest("#auraR10Dock")) return -1;
    if (el.id === "auraThemeToggleR7") return -1;

    const d = descriptor(el);
    if (!d) return -1;

    let score = -1;
    for (const alias of item.aliases){
      const a = norm(alias);
      if (d === a) score = Math.max(score,140);
      if (d.startsWith(a+" |") || d.endsWith("| "+a)) score = Math.max(score,120);
      if (d.includes(a)) score = Math.max(score,80);
    }

    if (el.closest(".rail")) score += 50;
    if (el.classList.contains("rail-btn")) score += 40;
    if (el.matches("button,[role='button'],a")) score += 20;

    const r = el.getBoundingClientRect();
    if (r.width > 0 && r.height > 0) score += 5;

    return score;
  };

  const resolveTarget = (item) => {
    const preferred = [
      ...document.querySelectorAll(".rail .rail-btn,.rail button,.rail a,.rail [role='button']")
    ];

    let pool = preferred;
    let best = null;
    let bestScore = -1;

    for (const el of pool){
      const s = scoreTarget(el,item);
      if (s > bestScore){
        bestScore = s;
        best = el;
      }
    }

    if (best && bestScore >= 70) return best;

    pool = [
      ...document.querySelectorAll(
        "button,[role='button'],a,[data-route],[data-tab],[data-panel],[data-action],[data-view]"
      )
    ];

    best = null;
    bestScore = -1;

    for (const el of pool){
      const s = scoreTarget(el,item);
      if (s > bestScore){
        bestScore = s;
        best = el;
      }
    }

    return bestScore >= 90 ? best : null;
  };

  const bindLens = (el) => {
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

  const setDockActive = (key) => {
    document.querySelectorAll("#auraR10Dock .aura-r10-nav").forEach(btn => {
      btn.classList.toggle("is-active",btn.dataset.key === key);
    });
  };

  const buildDock = () => {
    document.getElementById("auraR9Dock")?.remove();

    let dock = document.getElementById("auraR10Dock");
    if (dock) return dock;

    dock = document.createElement("nav");
    dock.id = "auraR10Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    NAV.forEach(item => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "aura-r10-nav";
      btn.dataset.key = item.key;
      btn.setAttribute("aria-label",item.label);
      btn.title = item.label;

      btn.innerHTML = `
        <span class="aura-r10-icon" aria-hidden="true">${item.svg}</span>
        <span class="aura-r10-label" aria-hidden="true">${item.label}</span>
      `;

      btn.addEventListener("click",() => {
        const target = resolveTarget(item);

        if (!target){
          console.warn("[AURA R10] navigation target not found:",item.key,item.label);
          return;
        }

        console.info("[AURA R10] navigation:",item.key,"=>",descriptor(target));
        target.click();
        setDockActive(item.key);

        schedulePanels(80);
        schedulePanels(220);
        schedulePanels(500);
      });

      dock.appendChild(btn);
    });

    document.body.appendChild(dock);
    bindLens(dock);
    setDockActive("home");

    return dock;
  };

  /* ---------------- PANEL DECORATION ---------------- */

  const panelSpecs = [
    {
      rx:/conversation en cours/i,
      classes:["aura-r10-panel","aura-r10-side-panel","aura-r10-conversation-panel"]
    },
    {
      rx:/productivity core/i,
      classes:["aura-r10-panel","aura-r10-side-panel"]
    },
    {
      rx:/memory core/i,
      classes:["aura-r10-panel","aura-r10-side-panel"]
    },
    {
      rx:/\bmind\b/i,
      classes:["aura-r10-panel","aura-r10-mind-panel"]
    },
    {
      rx:/accessibilite.*mouvement|accessibilite/i,
      classes:["aura-r10-panel","aura-r10-accessibility"]
    }
  ];

  const looksPanel = (el) => {
    if (!el || el === document.body || el === document.documentElement) return false;
    if (el.id === "auraR10Dock") return false;
    if (el.closest("#auraR10Dock")) return false;

    const r = el.getBoundingClientRect();
    if (r.width < 260 || r.height < 150) return false;
    if (r.width > innerWidth * .97 || r.height > innerHeight * .97) return false;

    const cs = getComputedStyle(el);
    return (
      cs.position === "fixed" ||
      cs.position === "absolute" ||
      cs.overflow !== "visible" ||
      /panel|modal|drawer|overlay|dialog/i.test(el.className || "")
    );
  };

  const findPanelAncestor = (node) => {
    let cur = node;
    let fallback = null;

    for (let i=0; cur && cur !== document.body && i<10; i++,cur=cur.parentElement){
      const r = cur.getBoundingClientRect();

      if (r.width >= 280 && r.height >= 180){
        fallback = cur;
        if (looksPanel(cur)) return cur;
      }
    }

    return fallback;
  };

  const candidateHeadings = () => [
    ...document.querySelectorAll(
      "h1,h2,h3,h4,h5,strong,b,[class*='title'],[class*='Title'],[class*='header'],[class*='Header'],[class*='heading'],[class*='Heading']"
    )
  ];

  let applyingPanels = false;

  const decoratePanels = () => {
    if (applyingPanels) return;
    applyingPanels = true;

    try{
      const headings = candidateHeadings();

      for (const spec of panelSpecs){
        for (const node of headings){
          const txt = norm(node.textContent);
          if (!txt || txt.length > 140) continue;

          if (spec.rx.test(txt)){
            const panel = findPanelAncestor(node);
            if (!panel) continue;

            spec.classes.forEach(cls => {
              if (!panel.classList.contains(cls)) panel.classList.add(cls);
            });

            break;
          }
        }
      }
    } finally {
      applyingPanels = false;
    }
  };

  let panelTimer = 0;

  const schedulePanels = (delay=120) => {
    clearTimeout(panelTimer);
    panelTimer = setTimeout(decoratePanels,delay);
  };

  /* ---------------- COMPOSER ---------------- */

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

      composer.classList.toggle("aura-r9-writing",writing);
    };

    input.addEventListener("focus",sync);
    input.addEventListener("blur",() => setTimeout(sync,30));
    input.addEventListener("input",sync);
    sync();
  };

  const boot = () => {
    buildDock();
    setupComposer();
    schedulePanels(50);
    schedulePanels(250);
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }

  /* Throttled observer: only schedules read/decorate work.
     No innerHTML mutation loop. */
  const observer = new MutationObserver(() => {
    schedulePanels(140);
    if (!document.getElementById("auraR10Dock")) buildDock();
    setupComposer();
  });

  observer.observe(document.documentElement,{
    childList:true,
    subtree:true
  });
})();
