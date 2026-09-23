/* ================================================================
   AURA R15 - SOURCE API DOCK BRIDGE
   Only MUSIQUE + PARAMETRES. No legacy synthetic nav click.
   ================================================================ */
(() => {
  "use strict";
  if (window.__AURA_R15_SOURCE_API_BRIDGE__) return;
  window.__AURA_R15_SOURCE_API_BRIDGE__ = true;

  const fold = v => String(v || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g,"")
    .trim()
    .toLowerCase();

  const keyOf = btn => {
    const raw = fold(btn?.dataset?.key || btn?.dataset?.route || btn?.textContent || "");
    if (raw.includes("musique") || raw.includes("music")) return "musique";
    if (raw.includes("parametre") || raw.includes("settings")) return "parametres";
    return raw;
  };

  const dockButton = target => target?.closest?.(
    "#auraR10Dock .aura-r10-dock-btn," +
    "#auraR10Dock [data-key]," +
    ".aura-r10-dock .aura-r10-dock-btn," +
    ".aura-r10-dock [data-key]"
  ) || null;

  const setActive = key => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;
    dock.querySelectorAll(".aura-r10-dock-btn,[data-key]").forEach(btn => {
      btn.classList.toggle("is-active",keyOf(btn) === key);
    });
  };

  const notifySettingsI18n = () => {
    // The existing i18n module listens for clicks on [data-rail-target="settings"].
    // This proxy is OUTSIDE the legacy nav, so it only wakes i18n and does not
    // call the legacy rail route.
    const proxy = document.createElement("button");
    proxy.type = "button";
    proxy.dataset.railTarget = "settings";
    proxy.style.cssText =
      "position:fixed;left:-10000px;top:-10000px;width:1px;height:1px;" +
      "opacity:0;pointer-events:none";
    document.body.appendChild(proxy);
    proxy.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,composed:true}));
    proxy.remove();
  };

  window.addEventListener("click",event=>{
    const btn = dockButton(event.target);
    if (!btn) return;

    const key = keyOf(btn);
    if (key !== "musique" && key !== "parametres") return;

    event.preventDefault();
    event.stopPropagation();

    setActive(key);

    if (key === "musique") {
      const api = window.AuraMusicPlayerV180;
      if (api?.open?.()) {
        console.info("[AURA R15] Musique -> AuraMusicPlayerV180.open()");
      } else {
        console.error("[AURA R15] AuraMusicPlayerV180 API unavailable");
      }
      return;
    }

    const settings = window.AuraP0702Settings;
    if (settings?.open?.()) {
      notifySettingsI18n();
      setTimeout(notifySettingsI18n,120);
      console.info("[AURA R15] Parametres -> AuraP0702Settings.open()");
    } else {
      console.error("[AURA R15] AuraP0702Settings API unavailable");
    }
  },true);

  console.info("[AURA R15] source API bridge ready");
})();
