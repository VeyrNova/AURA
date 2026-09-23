/* AURA MUSIC R17 FIX4 - SINGLE MINIPLAYER OWNERSHIP */
(() => {
  "use strict";
  if (window.__AURA_MUSIC_R17_FIX4_SINGLE_MINI__) return;
  window.__AURA_MUSIC_R17_FIX4_SINGLE_MINI__ = true;

  const ROOT_ID = "aura-music-player-v180";
  const MINI_ID = "aura-global-mini-player-v180";
  const DUP_ID = "aura-music-mini-r17";

  function openFullPlayer() {
    const root = document.getElementById(ROOT_ID);
    if (root) {
      root.classList.add("open");
      sync();
      return;
    }
    const nav = document.getElementById("aura-music-nav-v180");
    if (nav) nav.click();
  }

  function removeDuplicateMini() {
    const dup = document.getElementById(DUP_ID);
    if (dup) dup.remove();
  }

  function bindLegacyMini(mini) {
    if (!mini || mini.dataset.r17Fix4Bound === "1") return;
    mini.dataset.r17Fix4Bound = "1";

    const cover = document.getElementById("aura-global-mini-cover-v180");
    const copy = mini.querySelector(".aura-global-mini-copy");
    for (const el of [cover, copy]) {
      if (!el) continue;
      el.style.cursor = "pointer";
      el.title = "Ouvrir AURA Music";
      el.addEventListener("click", e => {
        if (e.target.closest("button")) return;
        openFullPlayer();
      });
    }
  }

  function sync() {
    removeDuplicateMini();

    const root = document.getElementById(ROOT_ID);
    const mini = document.getElementById(MINI_ID);
    if (!mini) return;

    bindLegacyMini(mini);

    const fullOpen = !!root?.classList.contains("open");
    mini.classList.toggle("r17-full-player-open", fullOpen);
    mini.setAttribute("aria-hidden", fullOpen ? "true" : "false");
  }

  let rootObserver = null;

  function observeRoot() {
    const root = document.getElementById(ROOT_ID);
    if (!root || root.dataset.r17Fix4Observed === "1") return;
    root.dataset.r17Fix4Observed = "1";

    rootObserver?.disconnect();
    rootObserver = new MutationObserver(sync);
    rootObserver.observe(root, { attributes: true, attributeFilter: ["class"] });

    const close = document.getElementById("aura-music-close-v180");
    if (close && close.dataset.r17Fix4Bound !== "1") {
      close.dataset.r17Fix4Bound = "1";
      close.addEventListener("click", () => setTimeout(sync, 0));
    }
  }

  function boot() {
    observeRoot();
    sync();

    const bodyObserver = new MutationObserver(() => {
      observeRoot();
      sync();
    });
    bodyObserver.observe(document.body, { childList: true, subtree: true });

    setInterval(sync, 450);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();