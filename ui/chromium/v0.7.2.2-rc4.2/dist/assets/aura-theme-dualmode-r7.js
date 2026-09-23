(() => {
  const THEME_KEY = "aura.theme.mode";
  const BTN_ID = "auraThemeToggleR7";

  const applyTheme = (theme) => {
    const safeTheme = theme === "light" ? "light" : "dark";
    document.documentElement.setAttribute("data-aura-theme", safeTheme);
    try { localStorage.setItem(THEME_KEY, safeTheme); } catch (_) {}
    updateButton(safeTheme);
  };

  const getSavedTheme = () => {
    try {
      return localStorage.getItem(THEME_KEY) || "dark";
    } catch (_) {
      return "dark";
    }
  };

  const updateButton = (theme) => {
    const btn = document.getElementById(BTN_ID);
    if (!btn) return;
    if (theme === "light") {
      btn.textContent = "MODE SOMBRE";
      btn.setAttribute("aria-label", "Activer le mode sombre");
      btn.title = "Activer le mode sombre";
    } else {
      btn.textContent = "MODE CLAIR";
      btn.setAttribute("aria-label", "Activer le mode clair");
      btn.title = "Activer le mode clair";
    }
  };

  const ensureButton = () => {
    if (document.getElementById(BTN_ID)) return;

    const topActions = document.querySelector(".top-actions") || document.querySelector(".topbar");
    if (!topActions) return;

    const btn = document.createElement("button");
    btn.id = BTN_ID;
    btn.className = "aura-theme-toggle";
    btn.type = "button";
    btn.textContent = "MODE CLAIR";

    btn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-aura-theme") === "light" ? "light" : "dark";
      applyTheme(current === "light" ? "dark" : "light");
    });

    topActions.insertBefore(btn, topActions.firstChild || null);
    updateButton(document.documentElement.getAttribute("data-aura-theme") === "light" ? "light" : "dark");
  };

  const mount = () => {
    applyTheme(getSavedTheme());
    ensureButton();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }

  const observer = new MutationObserver(() => {
    if (!document.getElementById(BTN_ID)) {
      ensureButton();
    }
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });
})();
