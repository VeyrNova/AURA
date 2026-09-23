/* ================================================================
   AURA R14 - FINAL MUSIC + SETTINGS DIRECT BRIDGE
   Replaces R13 ownership for these two dock entries only.
   ================================================================ */
(() => {
  "use strict";
  if (window.__AURA_R14_MUSIC_SETTINGS_BRIDGE__) return;
  window.__AURA_R14_MUSIC_SETTINGS_BRIDGE__ = true;

  const VERSION = "20260921-r14";

  const fold = value => String(value || "")
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

  const setDockActive = key => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;
    dock.querySelectorAll(".aura-r10-dock-btn,[data-key]").forEach(btn => {
      btn.classList.toggle("is-active",keyOf(btn) === key);
    });
  };

  const closeSettings = () => {
    const panel = document.querySelector(".aura-p0702-settings-popover");
    if (panel) {
      panel.classList.remove("open","aura-r14-settings");
      panel.hidden = true;
    }
  };

  const closeAccessibility = () => {
    try { window.AuraAccessibility?.close?.(); } catch (_) {}
    const panel = document.getElementById("aura-p075-panel");
    if (panel) {
      panel.classList.remove("open");
      panel.hidden = true;
    }
  };

  const installStyle = () => {
    if (document.getElementById("auraR14BridgeStyle")) return;
    const style = document.createElement("style");
    style.id = "auraR14BridgeStyle";
    style.textContent = `
      .aura-p0702-settings-popover.aura-r14-settings{
        position:fixed!important;
        z-index:2147483646!important;
        left:168px!important;
        right:auto!important;
        top:72px!important;
        width:min(420px,calc(100vw - 190px))!important;
        max-width:420px!important;
        max-height:calc(100vh - 100px)!important;
        overflow:auto!important;
        opacity:1!important;
        transform:none!important;
        pointer-events:auto!important;
        display:block!important;
        border-radius:20px!important;
        box-shadow:0 28px 90px rgba(0,0,0,.48),0 0 0 1px rgba(111,228,247,.05) inset!important;
        backdrop-filter:blur(28px) saturate(145%)!important;
      }
      .aura-p0702-settings-popover.aura-r14-settings .aura-p0702-settings-body{
        padding:16px!important;
      }
      .aura-p0702-settings-popover.aura-r14-settings [data-aura-language-setting]{
        margin-top:14px!important;
      }
      #aura-music-player-v180.aura-r14-force-open{
        z-index:2147483646!important;
        visibility:visible!important;
        opacity:1!important;
        pointer-events:auto!important;
      }
      @media(max-width:760px){
        .aura-p0702-settings-popover.aura-r14-settings{
          left:14px!important;
          right:14px!important;
          top:68px!important;
          width:auto!important;
          max-width:none!important;
          max-height:calc(100vh - 88px)!important;
        }
      }
    `;
    document.head.appendChild(style);
  };

  const localeToken = () => new URLSearchParams(location.search).get("token") || "";

  const localeApi = async (action,locale) => {
    const token = localeToken();
    if (!token) throw new Error("missing_token");
    const response = await fetch(`/api/locale?token=${encodeURIComponent(token)}`,{
      method:"POST",
      cache:"no-store",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify({action,...(locale ? {locale} : {})})
    });
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.error || `locale ${response.status}`);
    return data;
  };

  const ensureLanguageControl = async panel => {
    const body = panel?.querySelector(".aura-p0702-settings-body");
    if (!body) return;

    if (body.querySelector("[data-aura-language-setting]")) return;

    const wrap = document.createElement("div");
    wrap.dataset.auraLanguageSetting = "1";
    wrap.style.cssText =
      "margin-top:14px;padding:13px;border:1px solid rgba(120,220,255,.18);" +
      "border-radius:14px;background:rgba(6,18,34,.48);display:grid;gap:9px";

    const heading = document.createElement("div");
    heading.innerHTML =
      "<small style='display:block;opacity:.62;letter-spacing:.09em'>GÃ‰NÃ‰RAL / GENERAL</small>" +
      "<b>Langue / Language</b>";

    const select = document.createElement("select");
    select.setAttribute("aria-label","Langue / Language");
    select.style.cssText =
      "width:100%;padding:10px 11px;border-radius:10px;" +
      "border:1px solid rgba(120,220,255,.28);background:#0b1b2f;color:#eef7ff";
    select.innerHTML =
      "<option value='fr-FR'>FranÃ§ais</option><option value='en-US'>English</option>";

    const note = document.createElement("small");
    note.style.cssText = "opacity:.70;line-height:1.4";

    wrap.append(heading,select,note);
    body.appendChild(wrap);

    let current = window.AURAI18N?.getLocale?.() || window.__AURA_BOOT_LOCALE__ || "fr-FR";
    try {
      const data = await localeApi("get");
      if (data?.locale) current = data.locale;
    } catch (_) {}

    select.value = current === "en-US" ? "en-US" : "fr-FR";
    note.textContent = current === "en-US"
      ? "Text, speech recognition and Camilla/XTTS follow this language."
      : "Le texte, la reconnaissance vocale et Camilla/XTTS suivent cette langue.";

    select.addEventListener("change",async()=>{
      const wanted = select.value;
      const previous = current;
      select.disabled = true;
      note.textContent = wanted === "en-US" ? "Applying languageâ€¦" : "Application de la langueâ€¦";
      try {
        const data = await localeApi("set",wanted);
        current = data?.locale || wanted;
        window.AURAI18N?.setLocale?.(current);
        window.dispatchEvent(new CustomEvent("aura:runtime-locale-changed",{detail:data || {locale:current}}));
        note.textContent = current === "en-US" ? "Language applied to AURA." : "Langue appliquÃ©e Ã  AURA.";
      } catch (err) {
        select.value = previous;
        note.textContent = previous === "en-US"
          ? "Unable to change language."
          : "Impossible de changer la langue.";
      } finally {
        select.disabled = false;
      }
    });
  };

  const openSettings = () => {
    installStyle();
    closeAccessibility();

    const r12 = document.getElementById("auraR12SettingsPanel");
    if (r12) {
      r12.classList.remove("open");
      r12.hidden = true;
    }

    const panel = document.querySelector(".aura-p0702-settings-popover");
    if (!panel) {
      console.error("[AURA R14] legacy settings panel not found");
      return false;
    }

    panel.hidden = false;
    panel.classList.add("open","aura-r14-settings");

    // Explicit inline geometry protects against late legacy repositioning.
    panel.style.setProperty("left","168px","important");
    panel.style.setProperty("right","auto","important");
    panel.style.setProperty("top","72px","important");
    panel.style.setProperty("z-index","2147483646","important");
    panel.style.setProperty("opacity","1","important");
    panel.style.setProperty("transform","none","important");
    panel.style.setProperty("pointer-events","auto","important");

    ensureLanguageControl(panel);

    [50,180,420].forEach(ms => setTimeout(()=>{
      panel.hidden = false;
      panel.classList.add("open","aura-r14-settings");
      panel.style.setProperty("left","168px","important");
      panel.style.setProperty("top","72px","important");
      panel.style.setProperty("z-index","2147483646","important");
    },ms));

    console.info("[AURA R14] settings opened");
    return true;
  };

  const ensureMusicCss = () => {
    if (document.querySelector('link[href*="aura_music_player_v180.css"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `./aura_music_player_v180.css?v=${VERSION}`;
    document.head.appendChild(link);
  };

  const revealMusicRoot = () => {
    installStyle();
    ensureMusicCss();

    const root = document.getElementById("aura-music-player-v180");
    const nav = document.getElementById("aura-music-nav-v180");

    if (!root) return false;

    try {
      if (nav && typeof nav.onclick === "function") {
        nav.onclick.call(nav);
      }
    } catch (err) {
      console.warn("[AURA R14] nav onclick failed",err);
    }

    root.hidden = false;
    root.removeAttribute("aria-hidden");
    root.classList.add("open","aura-r14-force-open");
    root.style.setProperty("z-index","2147483646","important");
    root.style.setProperty("visibility","visible","important");
    root.style.setProperty("opacity","1","important");
    root.style.setProperty("pointer-events","auto","important");

    // Only override display if the active .open CSS still resolves to none.
    try {
      if (getComputedStyle(root).display === "none") {
        root.style.setProperty("display","block","important");
      }
    } catch (_) {}

    console.info("[AURA R14] music root revealed");
    return true;
  };

  const reloadMusicRuntime = () => {
    ensureMusicCss();

    const oldReload = document.querySelector('script[data-aura-r14-music-reload]');
    if (oldReload) oldReload.remove();

    const script = document.createElement("script");
    script.src = `./aura_music_player_v180.js?v=${VERSION}-${Date.now()}`;
    script.dataset.auraR14MusicReload = "1";
    script.onload = () => {
      [0,50,140,320,700].forEach(ms => setTimeout(revealMusicRoot,ms));
    };
    script.onerror = err => console.error("[AURA R14] music runtime reload failed",err);
    document.body.appendChild(script);
  };

  const openMusic = () => {
    closeSettings();

    if (revealMusicRoot()) {
      setTimeout(revealMusicRoot,100);
      setTimeout(revealMusicRoot,350);
      return true;
    }

    reloadMusicRuntime();

    [120,300,650,1100].forEach(ms => setTimeout(revealMusicRoot,ms));
    console.info("[AURA R14] music runtime reload requested");
    return true;
  };

  const dockButtonFrom = target => target?.closest?.(
    "#auraR10Dock .aura-r10-dock-btn," +
    "#auraR10Dock [data-key]," +
    ".aura-r10-dock .aura-r10-dock-btn," +
    ".aura-r10-dock [data-key]"
  ) || null;

  window.addEventListener("click",event=>{
    const btn = dockButtonFrom(event.target);
    if (!btn) return;

    const key = keyOf(btn);
    if (key !== "musique" && key !== "parametres") return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    setDockActive(key);

    if (key === "musique") {
      openMusic();
      return;
    }

    openSettings();
  },true);

  console.info("[AURA R14] final music/settings bridge ready");
})();
