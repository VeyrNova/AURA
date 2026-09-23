(() => {
  "use strict";
  if (window.__AURA_R17_FIX12__) return;
  window.__AURA_R17_FIX12__ = true;

  const REMOVE = [
    "#aura-r17-fix8-wave",
    "#aura-r17-fix9-wave",
    "#aura-r17-fix10-wave",
    "#aura-r17-fix11-wave",
    ".aura-r17-fluid-wave",
    ".aura-r17-wave-v6",
    ".aura-r17-fix7-wave"
  ];

  function clean() {
    for (const selector of REMOVE) {
      document.querySelectorAll(selector).forEach(node => node.remove());
    }

    const root = document.getElementById("aura-music-player-v180");
    if (!root) return;

    root.querySelectorAll(".aura-music-premium-visualizer").forEach(v => {
      v.replaceChildren();
      v.setAttribute("aria-hidden","true");
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", clean, { once:true });
  } else {
    clean();
  }

  /* One delayed cleanup is enough for components created just after open.
     No animation loop and no permanent interval are used. */
  window.setTimeout(clean, 250);
  window.setTimeout(clean, 900);
})();