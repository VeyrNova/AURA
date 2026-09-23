(() => {
  const attachComposer = () => {
    const composer = document.querySelector("#composer") || document.querySelector(".composer");
    const input = document.querySelector("#messageInput");
    if (!composer || !input) return;

    const syncComposer = () => {
      const active = document.activeElement === input || !!String(input.value || "").trim();
      composer.classList.toggle("aura-liquid-active", active);
    };

    input.addEventListener("focus", syncComposer);
    input.addEventListener("blur", () => setTimeout(syncComposer, 30));
    input.addEventListener("input", syncComposer);
    syncComposer();
  };

  const attachDock = () => {
    const rail = document.querySelector(".rail");
    if (!rail) return;
    rail.classList.add("aura-liquid-dock");

    const buttons = [...rail.querySelectorAll(".rail-btn, button, a")].filter(el => el.closest(".rail") === rail);
    buttons.forEach((btn, idx) => {
      if (!btn.classList.contains("rail-btn")) btn.classList.add("rail-btn");

      const rawLabel =
        btn.getAttribute("data-liquid-label") ||
        btn.getAttribute("aria-label") ||
        btn.getAttribute("title") ||
        btn.innerText ||
        btn.textContent ||
        `ITEM ${idx + 1}`;

      const label = String(rawLabel).replace(/\s+/g, " ").trim() || `ITEM ${idx + 1}`;
      btn.setAttribute("data-liquid-label", label);
      if (!btn.getAttribute("title")) btn.setAttribute("title", label);
    });

    const setActiveState = () => {
      const expanded =
        rail.matches(":hover") ||
        rail.contains(document.activeElement) ||
        buttons.some(b => b.classList.contains("active"));
      rail.classList.toggle("aura-liquid-active", expanded);
    };

    rail.addEventListener("mouseenter", setActiveState);
    rail.addEventListener("mouseleave", () => setTimeout(setActiveState, 30));
    rail.addEventListener("focusin", setActiveState);
    rail.addEventListener("focusout", () => setTimeout(setActiveState, 30));
    setActiveState();
  };

  const boot = () => {
    attachComposer();
    attachDock();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  const mo = new MutationObserver(() => {
    attachComposer();
    attachDock();
  });
  mo.observe(document.documentElement, { childList: true, subtree: true });
})();
