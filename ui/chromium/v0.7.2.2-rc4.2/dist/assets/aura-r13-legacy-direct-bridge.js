/* ================================================================
   AURA R13 - LEGACY DIRECT BRIDGE
   Loaded LAST. Window-capture ownership for MUSIQUE + PARAMETRES only.
   ================================================================ */
(() => {
  "use strict";
  if (window.__AURA_R13_LEGACY_DIRECT_BRIDGE__) return;
  window.__AURA_R13_LEGACY_DIRECT_BRIDGE__ = true;

  const TAG = "20260921-r13a";

  const fold = value => String(value || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase();

  const buttonKey = btn => {
    const raw = fold(btn?.dataset?.key || btn?.dataset?.route || btn?.textContent || "");
    if (raw.includes("musique") || raw.includes("music")) return "musique";
    if (raw.includes("parametre") || raw.includes("settings")) return "parametres";
    return raw;
  };

  const setDockActive = key => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;
    dock.querySelectorAll(".aura-r10-dock-btn,[data-key]").forEach(btn => {
      btn.classList.toggle("is-active", buttonKey(btn) === key);
    });
  };

  const ensureMusicCss = () => {
    if (document.querySelector('link[href*="aura_music_player_v180.css"]')) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `./aura_music_player_v180.css?v=${TAG}`;
    link.dataset.auraR13MusicCss = "1";
    document.head.appendChild(link);
  };

  const openMusicNow = () => {
    const root = document.getElementById("aura-music-player-v180");
    const nav = document.getElementById("aura-music-nav-v180");

    if (root) {
      root.classList.add("open");
      try {
        if (typeof nav?.onclick === "function") {
          nav.onclick.call(nav, new MouseEvent("click",{bubbles:false,cancelable:true}));
        }
      } catch (_) {}
      return true;
    }

    if (nav) {
      try {
        if (typeof nav.onclick === "function") {
          nav.onclick.call(nav, new MouseEvent("click",{bubbles:false,cancelable:true}));
        } else {
          nav.click();
        }
        return true;
      } catch (err) {
        console.warn("[AURA R13] music legacy handler failed",err);
      }
    }
    return false;
  };

  const loadMusicRuntime = () => {
    ensureMusicCss();
    if (openMusicNow()) return true;

    if (!window.__AURA_R13_MUSIC_RELOAD_STARTED__) {
      window.__AURA_R13_MUSIC_RELOAD_STARTED__ = true;
      const script = document.createElement("script");
      script.src = `./aura_music_player_v180.js?v=${TAG}`;
      script.dataset.auraR13MusicLoader = "1";
      script.onload = () => {
        [0,60,160,360].forEach(ms => setTimeout(openMusicNow,ms));
      };
      script.onerror = err => {
        console.error("[AURA R13] music runtime load failed",err);
        window.__AURA_R13_MUSIC_RELOAD_STARTED__ = false;
      };
      document.body.appendChild(script);
    }

    [80,180,420,800].forEach(ms => setTimeout(openMusicNow,ms));
    return true;
  };

  const closeAccessibility = () => {
    try { window.AuraAccessibility?.close?.(); } catch (_) {}
    const panel = document.getElementById("aura-p075-panel");
    if (panel) {
      panel.classList.remove("open");
      panel.hidden = true;
    }
  };

  const localeToken = () => new URLSearchParams(location.search).get("token") || "";

  const localeApi = async (action, locale) => {
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

  const triggerExistingI18n = () => {
    try {
      const proxy = document.createElement("button");
      proxy.type = "button";
      proxy.dataset.railTarget = "settings";
      proxy.style.cssText = "position:fixed;left:-9999px;top:-9999px;width:1px;height:1px;opacity:0;pointer-events:none";
      document.body.appendChild(proxy);
      proxy.dispatchEvent(new MouseEvent("click",{bubbles:true,cancelable:true,composed:true}));
      proxy.remove();
    } catch (_) {}
  };

  const ensureFallbackLanguageControl = async panel => {
    const body = panel?.querySelector(".aura-p0702-settings-body") || panel;
    if (!body || body.querySelector("[data-aura-language-setting]")) return;

    const wrap = document.createElement("div");
    wrap.dataset.auraLanguageSetting = "1";
    wrap.style.cssText = [
      "margin-top:14px",
      "padding:13px",
      "border:1px solid rgba(120,220,255,.18)",
      "border-radius:14px",
      "background:rgba(6,18,34,.48)",
      "display:grid",
      "gap:9px"
    ].join(";");

    const heading = document.createElement("div");
    heading.innerHTML = "<small style='display:block;opacity:.62;letter-spacing:.09em'>GÃ‰NÃ‰RAL / GENERAL</small><b>Langue / Language</b>";

    const select = document.createElement("select");
    select.setAttribute("aria-label","Langue / Language");
    select.style.cssText = "width:100%;padding:10px 11px;border-radius:10px;border:1px solid rgba(120,220,255,.28);background:#0b1b2f;color:#eef7ff";
    select.innerHTML = "<option value='fr-FR'>FranÃ§ais</option><option value='en-US'>English</option>";

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
        note.textContent = previous === "en-US" ? "Unable to change language." : "Impossible de changer la langue.";
      } finally {
        select.disabled = false;
      }
    });
  };

  const ensureSettingsPanel = () => {
    let panel = document.querySelector(".aura-p0702-settings-popover");
    if (panel) return panel;

    panel = document.createElement("section");
    panel.className = "aura-p0702-popover aura-p0702-settings-popover glass";
    panel.hidden = true;
    panel.innerHTML = `
      <header>
        <div><small>AURA WORKSPACE</small><b>PARAMÃˆTRES</b></div>
        <button type="button" data-pop-close aria-label="Fermer">Ã—</button>
      </header>
      <div class="aura-p0702-settings-body">
        <b>Configuration locale AURA</b>
        <p>RÃ©glages de lâ€™interface et de la langue.</p>
      </div>`;

    panel.querySelector("[data-pop-close]")?.addEventListener("click",()=>{
      panel.classList.remove("open");
      panel.hidden = true;
    });

    document.body.appendChild(panel);
    return panel;
  };

  const positionSettings = panel => {
    const dock = document.getElementById("auraR10Dock");
    const dr = dock?.getBoundingClientRect?.();
    const width = Math.min(390,Math.max(310,window.innerWidth - 44));
    const left = Math.min(
      Math.max(18,(dr?.right || 150) + 14),
      Math.max(18,window.innerWidth - width - 18)
    );

    Object.assign(panel.style,{
      position:"fixed",
      zIndex:"2147483000",
      left:`${left}px`,
      right:"auto",
      top:"82px",
      width:`${width}px`,
      maxWidth:"calc(100vw - 36px)",
      maxHeight:"calc(100vh - 110px)",
      overflow:"auto",
      opacity:"1",
      transform:"none",
      pointerEvents:"auto",
      display:"block"
    });
  };

  const openSettings = () => {
    closeAccessibility();

    const oldR12 = document.getElementById("auraR12SettingsPanel");
    if (oldR12) {
      oldR12.classList.remove("open");
      oldR12.hidden = true;
    }

    const panel = ensureSettingsPanel();
    panel.hidden = false;
    panel.classList.add("open");
    positionSettings(panel);

    triggerExistingI18n();

    [0,60,180].forEach(ms => setTimeout(()=>{
      panel.hidden = false;
      panel.classList.add("open");
      positionSettings(panel);
      ensureFallbackLanguageControl(panel);
    },ms));

    return true;
  };

  const findDockButton = target => {
    if (!target?.closest) return null;
    return target.closest(
      "#auraR10Dock .aura-r10-dock-btn," +
      "#auraR10Dock [data-key]," +
      ".aura-r10-dock .aura-r10-dock-btn," +
      ".aura-r10-dock [data-key]"
    );
  };

  /* Window capture deliberately runs BEFORE all document-level legacy/R10/R11
     capture listeners, including listeners that call stopImmediatePropagation(). */
  window.addEventListener("click",event=>{
    const btn = findDockButton(event.target);
    if (!btn) return;

    const key = buttonKey(btn);
    if (key !== "musique" && key !== "parametres") return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    setDockActive(key);

    if (key === "musique") {
      console.info("[AURA R13] direct legacy music bridge");
      loadMusicRuntime();
      return;
    }

    console.info("[AURA R13] direct legacy settings bridge");
    openSettings();
  },true);

  console.info("[AURA R13] legacy direct bridge ready");
})();
