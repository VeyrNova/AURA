(() => {
  const LABELS = [
    "Accueil",
    "Conversation",
    "Mémoire",
    "Tâches",
    "Agenda",
    "Modules",
    "Musique",
    "AURA Live",
    "Diagnostics",
    "Paramètres"
  ];

  const bindPointerGlass = (el) => {
    if (!el || el.dataset.auraR8PointerBound === "1") return;
    el.dataset.auraR8PointerBound = "1";

    el.addEventListener("pointermove", (event) => {
      const r = el.getBoundingClientRect();
      if (!r.width || !r.height) return;
      const x = Math.max(0, Math.min(100, ((event.clientX - r.left) / r.width) * 100));
      const y = Math.max(0, Math.min(100, ((event.clientY - r.top) / r.height) * 100));
      el.style.setProperty("--aura-glass-x", `${x.toFixed(1)}%`);
      el.style.setProperty("--aura-glass-y", `${y.toFixed(1)}%`);
    });

    el.addEventListener("pointerleave", () => {
      el.style.setProperty("--aura-glass-x", "50%");
      el.style.setProperty("--aura-glass-y", "50%");
    });
  };

  const bindComposer = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input) return;

    bindPointerGlass(composer);

    if (composer.dataset.auraR8Fix1Bound === "1") return;
    composer.dataset.auraR8Fix1Bound = "1";

    const sync = () => {
      const hasText = Boolean(String(input.value || "").trim());
      const focused = document.activeElement === input;
      composer.classList.toggle("aura-liquid-writing", focused || hasText);
    };

    input.addEventListener("focus", sync);
    input.addEventListener("blur", () => setTimeout(sync, 35));
    input.addEventListener("input", sync);
    sync();
  };

  const markIcon = (btn) => {
    if (btn.querySelector(".aura-r8-icon-node")) return;

    let icon =
      btn.querySelector("svg") ||
      btn.querySelector("i") ||
      btn.querySelector('[class*="icon"]') ||
      btn.querySelector('[class*="Icon"]');

    if (!icon) {
      const candidates = [...btn.children];
      icon = candidates.find(el => {
        const t = String(el.textContent || "").trim();
        const rect = el.getBoundingClientRect();
        return rect.width <= 42 && t.length <= 4;
      }) || candidates[0] || null;
    }

    if (icon) icon.classList.add("aura-r8-icon-node");
  };

  const hideNativeLabels = (btn) => {
    [...btn.querySelectorAll("*")].forEach(el => {
      if (el.classList.contains("aura-r8-icon-node")) return;
      if (el.closest(".aura-r8-icon-node")) return;
      if (el.matches("svg,svg *,i,[class*='icon'],[class*='Icon']")) return;

      const text = String(el.textContent || "").replace(/\s+/g, " ").trim();
      if (text) el.classList.add("aura-r8-native-label");
    });
  };

  const bindDock = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return;

    bindPointerGlass(rail);

    const buttons = [...rail.querySelectorAll(".rail-btn")];
    buttons.forEach((btn, idx) => {
      const original =
        btn.getAttribute("data-liquid-label") ||
        btn.getAttribute("aria-label") ||
        btn.getAttribute("title") ||
        String(btn.textContent || "").replace(/\s+/g, " ").trim();

      const clean =
        (original && original.length <= 28 ? original : "") ||
        LABELS[idx] ||
        `Navigation ${idx + 1}`;

      btn.setAttribute("data-liquid-label", clean);
      btn.setAttribute("title", clean);

      markIcon(btn);
      hideNativeLabels(btn);
    });

    if (rail.dataset.auraR8Fix1Bound === "1") return;
    rail.dataset.auraR8Fix1Bound = "1";

    const expand = () => rail.classList.add("aura-liquid-expanded");
    const collapse = () => {
      requestAnimationFrame(() => {
        if (!rail.matches(":hover") && !rail.contains(document.activeElement)) {
          rail.classList.remove("aura-liquid-expanded");
        }
      });
    };

    rail.addEventListener("mouseenter", expand);
    rail.addEventListener("mouseleave", collapse);
    rail.addEventListener("focusin", expand);
    rail.addEventListener("focusout", () => setTimeout(collapse, 40));

    /* Critical: active navigation item must NOT force expansion. */
    rail.classList.remove("aura-liquid-active");
    if (!rail.matches(":hover") && !rail.contains(document.activeElement)) {
      rail.classList.remove("aura-liquid-expanded");
    }
  };

  const boot = () => {
    bindComposer();
    bindDock();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once:true });
  } else {
    boot();
  }

  const observer = new MutationObserver(() => {
    bindComposer();
    bindDock();
  });

  observer.observe(document.documentElement, {
    childList:true,
    subtree:true
  });
})();
