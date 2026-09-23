(() => {
  const ITEMS = [
    ["Accueil", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'],
    ["Conversation", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'],
    ["Mémoire", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'],
    ["Tâches", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'],
    ["Agenda", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'],
    ["Modules", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'],
    ["Musique", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'],
    ["AURA Live", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'],
    ["Diagnostics", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'],
    ["Paramètres", '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19 13.5v-3l-2-.6a7 7 0 0 0-.7-1.7l1-1.8-2.1-2.1-1.8 1a7 7 0 0 0-1.7-.7L11 2.5H8l-.6 2.1a7 7 0 0 0-1.7.7l-1.8-1-2.1 2.1 1 1.8a7 7 0 0 0-.7 1.7L.5 10.5v3l2.1.6c.2.6.4 1.2.7 1.7l-1 1.8 2.1 2.1 1.8-1c.5.3 1.1.5 1.7.7l.6 2.1h3l.6-2.1c.6-.2 1.2-.4 1.7-.7l1.8 1 2.1-2.1-1-1.8c.3-.5.5-1.1.7-1.7l2.1-.6Z" transform="scale(.82) translate(2.7 2.7)"/></svg>']
  ];

  const bindLens = (el) => {
    if (!el || el.dataset.auraR9Lens === "1") return;
    el.dataset.auraR9Lens = "1";

    el.addEventListener("pointermove", e => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const x = Math.max(0, Math.min(100, ((e.clientX-r.left)/r.width)*100));
      const y = Math.max(0, Math.min(100, ((e.clientY-r.top)/r.height)*100));
      el.style.setProperty("--gx", `${x.toFixed(1)}%`);
      el.style.setProperty("--gy", `${y.toFixed(1)}%`);
    });

    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--gx","50%");
      el.style.setProperty("--gy","50%");
    });
  };

  const originalButtons = () => [...document.querySelectorAll(".rail .rail-btn")];

  const syncDockActive = (dock, originals) => {
    const dockButtons = [...dock.querySelectorAll(".aura-r9-dock-btn")];
    let activeIndex = originals.findIndex(btn => btn.classList.contains("active"));
    if (activeIndex < 0) activeIndex = 0;
    dockButtons.forEach((btn,i) => btn.classList.toggle("is-active",i === activeIndex));
  };

  const buildDock = () => {
    if (document.getElementById("auraR9Dock")) return;

    const originals = originalButtons();
    if (!originals.length) return;

    const dock = document.createElement("nav");
    dock.id = "auraR9Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    ITEMS.forEach(([label,svg],index) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "aura-r9-dock-btn";
      b.setAttribute("aria-label",label);
      b.title = label;

      const icon = document.createElement("span");
      icon.className = "aura-r9-dock-icon";
      icon.setAttribute("aria-hidden","true");
      icon.innerHTML = svg;

      const text = document.createElement("span");
      text.className = "aura-r9-dock-label";
      text.setAttribute("aria-hidden","true");
      text.textContent = label;

      b.append(icon,text);

      b.addEventListener("click", () => {
        const target = originalButtons()[index];
        if (target) target.click();
        [...dock.querySelectorAll(".aura-r9-dock-btn")].forEach((x,i) => {
          x.classList.toggle("is-active",i === index);
        });
      });

      dock.appendChild(b);
    });

    document.body.appendChild(dock);
    bindLens(dock);
    syncDockActive(dock,originals);

    /* Safe observer: reads original button classes only;
       it never mutates the original rail. */
    const activeObserver = new MutationObserver(() => {
      syncDockActive(dock, originalButtons());
    });

    originals.forEach(btn => activeObserver.observe(btn,{attributes:true,attributeFilter:["class"]}));
  };

  const setupComposer = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input) return;

    bindLens(composer);

    if (composer.dataset.auraR9Bound === "1") return;
    composer.dataset.auraR9Bound = "1";

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
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }
})();
