(() => {
  const NAV = [
    {
      id:"home",
      label:"Accueil",
      aliases:["accueil","home"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 10.5 12 3.7l8.5 6.8"/><path d="M5.5 9.5V20h13V9.5"/><path d="M9.5 20v-6h5v6"/></svg>'
    },
    {
      id:"conversation",
      label:"Conversation",
      aliases:["conversation","chat"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M5 5.5h14v10H9l-4 3v-13Z"/><path d="M8 9h8M8 12h5"/></svg>'
    },
    {
      id:"memory",
      label:"Mémoire",
      aliases:["memoire","mémoire","memory"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5.5" rx="6.5" ry="2.5"/><path d="M5.5 5.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/><path d="M5.5 10.5v5c0 1.4 2.9 2.5 6.5 2.5s6.5-1.1 6.5-2.5v-5"/></svg>'
    },
    {
      id:"tasks",
      label:"Tâches",
      aliases:["taches","tâches","tasks"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="4.5" width="14" height="16" rx="2"/><path d="M9 4.5v-1h6v1"/><path d="m8.5 12 2 2 5-5"/></svg>'
    },
    {
      id:"calendar",
      label:"Agenda",
      aliases:["agenda","calendar","calendrier"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="6" width="15" height="14" rx="2"/><path d="M8 3.5V8M16 3.5V8M4.5 10h15"/><path d="M8 14h3M13 14h3M8 17h3"/></svg>'
    },
    {
      id:"modules",
      label:"Modules",
      aliases:["modules","apps","applications"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="6" height="6" rx="1"/><rect x="14" y="4" width="6" height="6" rx="1"/><rect x="4" y="14" width="6" height="6" rx="1"/><rect x="14" y="14" width="6" height="6" rx="1"/></svg>'
    },
    {
      id:"music",
      label:"Musique",
      aliases:["musique","music"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V7l9-2v11"/><circle cx="6.5" cy="18" r="2.5"/><circle cx="15.5" cy="16" r="2.5"/></svg>'
    },
    {
      id:"live",
      label:"AURA Live",
      aliases:["aura live","live"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="14" height="14" rx="3"/><path d="M9 14v-4M12 16V8M15 13v-2"/></svg>'
    },
    {
      id:"diagnostics",
      label:"Diagnostics",
      aliases:["diagnostics","diagnostic"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="5" width="16" height="12" rx="2"/><path d="M8 20h8M12 17v3"/><path d="M7.5 12h2l1.2-3 2.1 6 1.2-3h2.5"/></svg>'
    },
    {
      id:"settings",
      label:"Paramètres",
      aliases:["parametres","paramètres","settings","reglages","réglages"],
      svg:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M18.2 13.4v-2.8l-1.9-.6a6.6 6.6 0 0 0-.7-1.6l.9-1.8-2-2-1.8.9a6.6 6.6 0 0 0-1.6-.7L10.6 3H7.8l-.6 1.9a6.6 6.6 0 0 0-1.6.7l-1.8-.9-2 2 .9 1.8a6.6 6.6 0 0 0-.7 1.6l-1.9.6v2.8l1.9.6c.2.6.4 1.1.7 1.6l-.9 1.8 2 2 1.8-.9c.5.3 1 .5 1.6.7l.6 1.9h2.8l.6-1.9c.6-.2 1.1-.4 1.6-.7l1.8.9 2-2-.9-1.8c.3-.5.5-1 .7-1.6l1.8-.6Z"/></svg>'
    }
  ];

  const normalize = (value) =>
    String(value || "")
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g,"")
      .toLowerCase()
      .replace(/[^a-z0-9]+/g," ")
      .trim();

  const originalButtons = () =>
    [...document.querySelectorAll(".rail .rail-btn, .rail button, .rail a")]
      .filter((el,index,array) => array.indexOf(el) === index);

  const descriptor = (el) => normalize([
    el.getAttribute("aria-label"),
    el.getAttribute("title"),
    el.getAttribute("data-label"),
    el.getAttribute("data-view"),
    el.getAttribute("data-route"),
    el.innerText,
    el.textContent
  ].filter(Boolean).join(" "));

  const resolveOriginal = (item) => {
    const buttons = originalButtons();
    const aliases = item.aliases.map(normalize);

    let best = null;
    let bestScore = 0;

    for (const btn of buttons){
      const d = descriptor(btn);
      if (!d) continue;

      let score = 0;
      for (const alias of aliases){
        if (d === alias) score = Math.max(score,100);
        else if (d.startsWith(alias + " ")) score = Math.max(score,90);
        else if (d.endsWith(" " + alias)) score = Math.max(score,85);
        else if ((" " + d + " ").includes(" " + alias + " ")) score = Math.max(score,80);
        else if (d.includes(alias)) score = Math.max(score,65);
      }

      if (score > bestScore){
        bestScore = score;
        best = btn;
      }
    }

    return bestScore >= 65 ? best : null;
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

  const buildDock = () => {
    document.getElementById("auraR9Dock")?.remove();
    if (document.getElementById("auraR10Dock")) return;

    if (!originalButtons().length) return;

    const dock = document.createElement("nav");
    dock.id = "auraR10Dock";
    dock.setAttribute("aria-label","Navigation AURA");

    NAV.forEach(item => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "aura-r10-dock-btn";
      btn.dataset.navId = item.id;
      btn.setAttribute("aria-label",item.label);
      btn.title = item.label;

      const icon = document.createElement("span");
      icon.className = "aura-r10-dock-icon";
      icon.setAttribute("aria-hidden","true");
      icon.innerHTML = item.svg;

      const label = document.createElement("span");
      label.className = "aura-r10-dock-label";
      label.setAttribute("aria-hidden","true");
      label.textContent = item.label;

      btn.append(icon,label);

      btn.addEventListener("click",() => {
        const target = resolveOriginal(item);

        if (!target){
          btn.classList.add("is-unresolved");
          btn.title = item.label + " — liaison introuvable";
          return;
        }

        btn.classList.remove("is-unresolved");
        target.click();

        [...dock.querySelectorAll(".aura-r10-dock-btn")].forEach(x => {
          x.classList.toggle("is-active",x === btn);
        });

        setTimeout(updatePanelAwareDock,80);
      });

      dock.appendChild(btn);
    });

    document.body.appendChild(dock);
    bindLens(dock);

    /* Resolve once at boot only to visually mark any missing mapping. */
    NAV.forEach(item => {
      const btn = dock.querySelector(`[data-nav-id="${item.id}"]`);
      if (btn && !resolveOriginal(item)){
        btn.classList.add("is-unresolved");
        btn.title = item.label + " — liaison introuvable";
      }
    });

    dock.querySelector('[data-nav-id="home"]')?.classList.add("is-active");
  };

  const isVisible = el => {
    if (!el || el.id === "auraR10Dock") return false;
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden" || Number(cs.opacity) === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0 && r.bottom > 0 && r.right > 0;
  };

  const findLeftPanel = () => {
    const excluded = new Set([
      document.documentElement,
      document.body,
      document.getElementById("app"),
      document.querySelector(".topbar"),
      document.querySelector(".hero"),
      document.querySelector(".workspace"),
      document.querySelector(".composer"),
      document.querySelector("#composer")
    ]);

    let best = null;
    let bestArea = 0;

    const candidates = document.querySelectorAll(
      '[role="dialog"], [class*="drawer"], [class*="Drawer"], [class*="modal"], [class*="Modal"], [class*="panel"], [class*="Panel"], [class*="workspace"], [class*="Workspace"]'
    );

    for (const el of candidates){
      if (excluded.has(el) || !isVisible(el)) continue;

      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);

      if (r.left > 70) continue;
      if (r.top < 55) continue;
      if (r.width < 260 || r.height < 240) continue;

      const pos = cs.position;
      if (!["fixed","absolute","sticky"].includes(pos)) continue;

      const area = r.width * r.height;
      if (area > bestArea){
        best = {el,r};
        bestArea = area;
      }
    }

    return best;
  };

  const updatePanelAwareDock = () => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;

    const panel = findLeftPanel();

    dock.classList.remove("aura-r10-panel-hidden","aura-r10-panel-shifted");
    dock.style.left = window.innerWidth <= 980 ? "12px" : "22px";

    if (!panel) return;

    const {r} = panel;
    const hideThreshold = Math.min(window.innerWidth * .38,620);

    if (r.width >= hideThreshold){
      dock.classList.add("aura-r10-panel-hidden");
      return;
    }

    const expandedDockWidth = window.innerWidth <= 980 ? 190 : 220;
    const desiredLeft = Math.ceil(r.right + 12);

    if (desiredLeft + expandedDockWidth + 16 < window.innerWidth){
      dock.style.left = desiredLeft + "px";
      dock.classList.add("aura-r10-panel-shifted");
    } else {
      dock.classList.add("aura-r10-panel-hidden");
    }
  };

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

      composer.classList.toggle("aura-r10-writing",writing);
    };

    input.addEventListener("focus",sync);
    input.addEventListener("blur",() => setTimeout(sync,30));
    input.addEventListener("input",sync);
    sync();
  };

  const boot = () => {
    buildDock();
    setupComposer();
    updatePanelAwareDock();

    /* Polling is deliberately used instead of a document-wide MutationObserver:
       it cannot create the startup loop seen in R8 FIX2. */
    setInterval(updatePanelAwareDock,250);
    window.addEventListener("resize",updatePanelAwareDock);
  };

  if (document.readyState === "loading"){
    document.addEventListener("DOMContentLoaded",boot,{once:true});
  } else {
    boot();
  }
})();

/* ================================================================
   AURA LIQUID GLASS R11 - DIRECT WORKSPACE ROUTER
   No legacy rail delegation for core workspaces.
   ================================================================ */
(() => {
  if (window.__AURA_R11_DIRECT_ROUTER__) return;
  window.__AURA_R11_DIRECT_ROUTER__ = true;

  const workspace = () => window.AuraWorkspace || null;

  const wsOpen = (id) => {
    try {
      const api = workspace();
      if (!api?.open) return false;
      return api.open(id) !== false;
    } catch (e) {
      console.warn("[AURA R11] workspace open failed", id, e);
      return false;
    }
  };

  const wsHome = () => {
    try {
      const api = workspace();
      if (!api?.home) return false;
      return api.home() !== false;
    } catch (e) {
      console.warn("[AURA R11] workspace home failed", e);
      return false;
    }
  };

  const clickExact = (selectors) => {
    for (const selector of selectors) {
      const el = document.querySelector(selector);
      if (el && !el.closest("#auraR10Dock")) {
        el.click();
        return true;
      }
    }
    return false;
  };

  const setPlan = (mode) => {
    const opened = wsOpen("plan");
    const selector = mode === "agenda"
      ? '.aura-p0623-drawer [data-tab="reminders"]'
      : '.aura-p0623-drawer [data-tab="tasks"]';

    const forceTab = () => {
      const tab = document.querySelector(selector);
      if (tab) tab.click();
    };

    [25, 70, 150, 300, 600].forEach(ms => setTimeout(forceTab, ms));
    return opened;
  };

  const openMusic = () => {
    const player = document.getElementById("aura-music-player-v180");
    if (player) {
      player.classList.add("open");
      return true;
    }
    return clickExact(["#aura-music-nav-v180"]);
  };

  const __AURA_R11_SETTINGS_LANGUAGE_FIX__ = true;

  const ensureSettingsLanguageControl = async panel => {
    try {
      const body = panel?.querySelector(".aura-p0702-settings-body") || panel;
      if (!body || body.querySelector("[data-aura-language-setting]")) return;

      const wrap = document.createElement("div");
      wrap.dataset.auraLanguageSetting = "1";
      wrap.style.cssText = [
        "margin-top:14px",
        "padding:12px",
        "border:1px solid rgba(120,220,255,.20)",
        "border-radius:14px",
        "background:rgba(6,18,34,.50)",
        "display:grid",
        "gap:9px"
      ].join(";");

      const title = document.createElement("div");
      title.innerHTML = "<small style='display:block;opacity:.62;letter-spacing:.08em'>GÃ‰NÃ‰RAL / GENERAL</small><b>Langue / Language</b>";

      const select = document.createElement("select");
      select.setAttribute("aria-label","Langue / Language");
      select.style.cssText = "width:100%;padding:10px 11px;border-radius:10px;border:1px solid rgba(120,220,255,.28);background:#0b1b2f;color:#eef7ff;outline:none";
      select.innerHTML = "<option value='fr-FR'>FranÃ§ais</option><option value='en-US'>English</option>";

      const note = document.createElement("small");
      note.style.cssText = "opacity:.72;line-height:1.4";
      note.textContent = "Le texte, la reconnaissance vocale et Camilla/XTTS suivent cette langue.";

      wrap.append(title, select, note);
      body.appendChild(wrap);

      const token = new URLSearchParams(location.search).get("token") || "";
      let current = window.AURAI18N?.getLocale?.() || "fr-FR";

      const localeApi = async (action, locale) => {
        if (!token) throw new Error("missing_token");
        const response = await fetch(`/api/locale?token=${encodeURIComponent(token)}`, {
          method:"POST",
          cache:"no-store",
          headers:{"Content-Type":"application/json"},
          body:JSON.stringify({action, ...(locale ? {locale} : {})})
        });
        const data = await response.json().catch(()=>({}));
        if (!response.ok) throw new Error(data.error || `locale ${response.status}`);
        return data;
      };

      try {
        const data = await localeApi("get");
        if (data?.locale) current = data.locale;
      } catch (_) {}

      select.value = current === "en-US" ? "en-US" : "fr-FR";

      select.addEventListener("change", async () => {
        const wanted = select.value;
        const previous = current;
        select.disabled = true;
        note.textContent = wanted === "en-US" ? "Applying languageâ€¦" : "Application de la langueâ€¦";
        try {
          const data = await localeApi("set", wanted);
          current = data?.locale || wanted;
          window.AURAI18N?.setLocale?.(current);
          note.textContent = current === "en-US" ? "Language applied to AURA." : "Langue appliquÃ©e Ã  AURA.";
          window.dispatchEvent(new CustomEvent("aura:runtime-locale-changed",{detail:data || {locale:current}}));
        } catch (err) {
          select.value = previous;
          note.textContent = previous === "en-US" ? "Unable to change language." : "Impossible de changer la langue.";
        } finally {
          select.disabled = false;
        }
      });
    } catch (err) {
      console.warn("[AURA R11] settings language fallback failed",err);
    }
  };

  const openSettingsPanel = () => {
    const panel = document.querySelector(".aura-p0702-settings-popover");
    const legacy = document.querySelector('.aura-p0702-nav-btn[data-rail-target="settings"]');

    if (!panel) {
      if (legacy) {
        legacy.click();
        return true;
      }
      return false;
    }

    try {
      if (legacy) legacy.click();
    } catch (_) {}

    const show = () => {
      const modules = document.querySelector(".aura-p0702-modules-popover");
      const mail = document.querySelector(".aura-p0702-mail-popover");

      if (modules) {
        modules.classList.remove("open");
        modules.hidden = true;
      }
      if (mail) {
        mail.classList.remove("open");
        mail.hidden = true;
      }

      panel.hidden = false;
      panel.classList.add("open");
      panel.style.position = "fixed";
      panel.style.zIndex = "2147482000";

      const dock = document.getElementById("auraR10Dock");
      const dr = dock?.getBoundingClientRect?.();
      const width = Math.min(390, Math.max(300, window.innerWidth - 48));
      const leftCandidate = (dr?.right || 78) + 14;
      const left = Math.min(Math.max(18,leftCandidate), Math.max(18,window.innerWidth - width - 18));

      panel.style.left = `${left}px`;
      panel.style.right = "auto";
      panel.style.top = "88px";
      panel.style.width = `${width}px`;
      panel.style.maxWidth = "calc(100vw - 36px)";
      panel.style.maxHeight = "calc(100vh - 118px)";
      panel.style.overflow = "auto";
      panel.style.opacity = "1";
      panel.style.transform = "none";
      panel.style.pointerEvents = "auto";

      ensureSettingsLanguageControl(panel);
    };

    show();
    setTimeout(show,30);
    setTimeout(show,120);
    return true;
  };

  /* ================================================================
     AURA R12 - DEDICATED LIQUID GLASS SETTINGS
     Owns the Settings surface. Does not delegate to legacy rail.
     ================================================================ */
  const __AURA_R12_DEDICATED_SETTINGS__ = true;

  const auraR12LocaleToken = () => new URLSearchParams(location.search).get("token") || "";

  const auraR12LocaleApi = async (action, locale) => {
    const token = auraR12LocaleToken();
    if (!token) throw new Error("missing_token");
    const response = await fetch(`/api/locale?token=${encodeURIComponent(token)}`, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({action, ...(locale ? {locale} : {})})
    });
    const data = await response.json().catch(()=>({}));
    if (!response.ok) throw new Error(data.error || `locale ${response.status}`);
    return data;
  };

  const auraR12CurrentLocale = () =>
    window.AURAI18N?.getLocale?.() ||
    window.__AURA_BOOT_LOCALE__ ||
    "fr-FR";

  const auraR12InstallStyle = () => {
    if (document.getElementById("auraR12SettingsStyle")) return;
    const style = document.createElement("style");
    style.id = "auraR12SettingsStyle";
    style.textContent = `
      #auraR12SettingsPanel{
        position:fixed;
        z-index:2147482500;
        width:min(430px,calc(100vw - 40px));
        max-height:calc(100vh - 120px);
        overflow:auto;
        border:1px solid rgba(117,222,255,.25);
        border-radius:22px;
        background:
          radial-gradient(circle at 12% 0%,rgba(93,199,255,.12),transparent 32%),
          linear-gradient(150deg,rgba(6,18,32,.94),rgba(7,12,26,.96));
        box-shadow:
          inset 0 1px 0 rgba(255,255,255,.07),
          0 28px 85px rgba(0,0,0,.48),
          0 0 44px rgba(89,185,255,.08);
        backdrop-filter:blur(30px) saturate(145%);
        color:#eaf8ff;
        padding:0;
        opacity:0;
        transform:translateX(-8px) scale(.985);
        pointer-events:none;
        transition:opacity .18s ease,transform .18s ease;
      }
      #auraR12SettingsPanel.open{
        opacity:1;
        transform:none;
        pointer-events:auto;
      }
      #auraR12SettingsPanel[hidden]{display:none!important}
      #auraR12SettingsPanel header{
        display:flex;
        align-items:flex-start;
        justify-content:space-between;
        gap:20px;
        padding:18px 20px;
        border-bottom:1px solid rgba(120,220,255,.12);
      }
      #auraR12SettingsPanel header small{
        display:block;
        font-size:9px;
        letter-spacing:.16em;
        opacity:.58;
        margin-bottom:5px;
      }
      #auraR12SettingsPanel header b{
        display:block;
        font-size:16px;
        letter-spacing:.055em;
      }
      #auraR12SettingsPanel [data-r12-close]{
        width:34px;height:34px;border-radius:11px;
        border:1px solid rgba(120,220,255,.18);
        background:rgba(10,25,43,.62);
        color:#bcecff;font-size:18px;cursor:pointer;
      }
      #auraR12SettingsPanel .aura-r12-settings-body{
        padding:18px 20px 20px;
        display:grid;gap:16px;
      }
      #auraR12SettingsPanel .aura-r12-card{
        border:1px solid rgba(120,220,255,.14);
        border-radius:16px;
        background:rgba(7,21,38,.54);
        padding:15px;
      }
      #auraR12SettingsPanel .aura-r12-card>small{
        display:block;
        opacity:.58;
        letter-spacing:.12em;
        font-size:9px;
        margin-bottom:6px;
      }
      #auraR12SettingsPanel .aura-r12-card>strong{
        display:block;
        font-size:14px;
        margin-bottom:5px;
      }
      #auraR12SettingsPanel .aura-r12-card>p{
        margin:0 0 14px;
        opacity:.68;
        font-size:11px;
        line-height:1.5;
      }
      #auraR12SettingsPanel .aura-r12-language-grid{
        display:grid;
        grid-template-columns:1fr 1fr;
        gap:10px;
      }
      #auraR12SettingsPanel .aura-r12-lang{
        min-height:62px;
        border-radius:13px;
        border:1px solid rgba(125,220,255,.16);
        background:rgba(9,25,43,.58);
        color:#cfefff;
        text-align:left;
        padding:11px 12px;
        cursor:pointer;
        transition:.16s ease;
      }
      #auraR12SettingsPanel .aura-r12-lang:hover{
        border-color:rgba(125,220,255,.38);
        background:rgba(22,57,81,.5);
      }
      #auraR12SettingsPanel .aura-r12-lang.active{
        border-color:rgba(159,111,255,.62);
        background:
          radial-gradient(circle at 0 0,rgba(142,87,255,.22),transparent 55%),
          rgba(31,27,68,.72);
        box-shadow:inset 0 0 0 1px rgba(190,151,255,.12);
      }
      #auraR12SettingsPanel .aura-r12-lang b{
        display:block;font-size:13px;margin-bottom:3px;
      }
      #auraR12SettingsPanel .aura-r12-lang span{
        display:block;font-size:10px;opacity:.64;
      }
      #auraR12SettingsPanel [data-r12-status]{
        display:block;
        margin-top:11px;
        min-height:16px;
        font-size:10px;
        opacity:.68;
      }
      html[data-aura-theme="light"] #auraR12SettingsPanel{
        background:
          radial-gradient(circle at 12% 0%,rgba(84,161,210,.13),transparent 34%),
          linear-gradient(150deg,rgba(245,250,253,.96),rgba(232,242,248,.97));
        border-color:rgba(67,137,178,.24);
        color:#163a50;
        box-shadow:0 26px 70px rgba(50,83,105,.18);
      }
      html[data-aura-theme="light"] #auraR12SettingsPanel .aura-r12-card,
      html[data-aura-theme="light"] #auraR12SettingsPanel .aura-r12-lang{
        background:rgba(255,255,255,.62);
        color:#173c52;
        border-color:rgba(65,137,179,.18);
      }
      @media(max-width:700px){
        #auraR12SettingsPanel{
          left:16px!important;
          right:16px!important;
          width:auto!important;
          top:76px!important;
          max-height:calc(100vh - 100px);
        }
      }
    `;
    document.head.appendChild(style);
  };

  const auraR12CloseAccessibility = () => {
    try {
      window.AuraAccessibility?.close?.();
    } catch (_) {}
    const p = document.getElementById("aura-p075-panel");
    if (p) {
      p.classList.remove("open");
      p.hidden = true;
    }
  };

  const auraR12EnsureSettings = () => {
    let panel = document.getElementById("auraR12SettingsPanel");
    if (panel) return panel;

    auraR12InstallStyle();

    panel = document.createElement("section");
    panel.id = "auraR12SettingsPanel";
    panel.hidden = true;
    panel.setAttribute("role","dialog");
    panel.setAttribute("aria-modal","false");
    panel.setAttribute("aria-label","ParamÃ¨tres AURA");

    panel.innerHTML = `
      <header>
        <div>
          <small>AURA Â· SETTINGS</small>
          <b data-r12-title>PARAMÃˆTRES</b>
        </div>
        <button type="button" data-r12-close aria-label="Fermer">Ã—</button>
      </header>
      <div class="aura-r12-settings-body">
        <section class="aura-r12-card">
          <small data-r12-general>GÃ‰NÃ‰RAL</small>
          <strong data-r12-language-title>Langue</strong>
          <p data-r12-language-note>Choisis la langue de lâ€™interface, de la reconnaissance vocale et de Camilla.</p>
          <div class="aura-r12-language-grid">
            <button type="button" class="aura-r12-lang" data-r12-locale="fr-FR">
              <b>FranÃ§ais</b>
              <span>Interface et voix en franÃ§ais</span>
            </button>
            <button type="button" class="aura-r12-lang" data-r12-locale="en-US">
              <b>English</b>
              <span>English interface and voice</span>
            </button>
          </div>
          <span data-r12-status></span>
        </section>
      </div>
    `;

    document.body.appendChild(panel);

    panel.querySelector("[data-r12-close]")?.addEventListener("click",() => {
      panel.classList.remove("open");
      setTimeout(()=>{ panel.hidden = true; },170);
    });

    panel.addEventListener("click", async event => {
      const button = event.target.closest("[data-r12-locale]");
      if (!button) return;

      const wanted = button.dataset.r12Locale;
      const status = panel.querySelector("[data-r12-status]");
      const all = [...panel.querySelectorAll("[data-r12-locale]")];
      all.forEach(b => b.disabled = true);

      if (status) status.textContent =
        wanted === "en-US" ? "Applying languageâ€¦" : "Application de la langueâ€¦";

      try {
        const data = await auraR12LocaleApi("set",wanted);
        const locale = data?.locale || wanted;
        window.AURAI18N?.setLocale?.(locale);
        window.dispatchEvent(new CustomEvent("aura:runtime-locale-changed",{
          detail:data || {locale}
        }));
        auraR12RenderSettings(locale);
        if (status) status.textContent =
          locale === "en-US" ? "Language applied to AURA." : "Langue appliquÃ©e Ã  AURA.";
      } catch (err) {
        console.warn("[AURA R12] locale switch failed",err);
        if (status) status.textContent =
          wanted === "en-US" ? "Unable to change language." : "Impossible de changer la langue.";
      } finally {
        all.forEach(b => b.disabled = false);
      }
    });

    return panel;
  };

  const auraR12RenderSettings = locale => {
    const panel = document.getElementById("auraR12SettingsPanel");
    if (!panel) return;
    const en = locale === "en-US";

    const set = (sel,text) => {
      const el = panel.querySelector(sel);
      if (el) el.textContent = text;
    };

    set("[data-r12-title]", en ? "SETTINGS" : "PARAMÃˆTRES");
    set("[data-r12-general]", en ? "GENERAL" : "GÃ‰NÃ‰RAL");
    set("[data-r12-language-title]", en ? "Language" : "Langue");
    set("[data-r12-language-note]", en
      ? "Choose the language used by the interface, speech recognition and Camilla."
      : "Choisis la langue de lâ€™interface, de la reconnaissance vocale et de Camilla."
    );

    panel.querySelectorAll("[data-r12-locale]").forEach(b => {
      b.classList.toggle("active",b.dataset.r12Locale === locale);
      b.setAttribute("aria-pressed",String(b.dataset.r12Locale === locale));
    });
  };

  const openAuraSettingsR12 = async () => {
    auraR12CloseAccessibility();

    const legacySettings = document.querySelector(".aura-p0702-settings-popover");
    if (legacySettings) {
      legacySettings.classList.remove("open");
      legacySettings.hidden = true;
    }

    const panel = auraR12EnsureSettings();

    let locale = auraR12CurrentLocale();
    try {
      const data = await auraR12LocaleApi("get");
      if (data?.locale) locale = data.locale;
    } catch (_) {}

    auraR12RenderSettings(locale);

    panel.hidden = false;
    panel.classList.add("open");

    const dock = document.getElementById("auraR10Dock");
    const dr = dock?.getBoundingClientRect?.();
    const width = Math.min(430,Math.max(320,window.innerWidth - 40));
    const left = Math.min(
      Math.max(18,(dr?.right || 78) + 16),
      Math.max(18,window.innerWidth - width - 18)
    );

    panel.style.left = `${left}px`;
    panel.style.right = "auto";
    panel.style.top = "84px";
    panel.style.width = `${width}px`;

    return true;
  };

  const route = (key) => {
    switch (key) {
      case "accueil":
        return wsHome() || clickExact([
          '.aura-p0702-nav-btn[data-rail-target="home"]',
          '[data-rail-target="home"]'
        ]);

      case "conversation":
        return wsOpen("talk") || clickExact([
          '.aura-p0702-nav-btn[data-rail-target="conversation"]',
          '[data-rail-target="conversation"]'
        ]);

      case "memoire":
        return wsOpen("memory") || clickExact([
          '.aura-p0702-nav-btn[data-rail-target="memory"]',
          '[data-rail-target="memory"]'
        ]);

      case "taches":
        return setPlan("tasks");

      case "agenda":
        return setPlan("agenda");

      case "modules":
        return clickExact([
          '.aura-p0702-nav-btn[data-rail-target="modules"]',
          '[data-rail-target="modules"]'
        ]);

      case "musique":
        return openMusic();

      case "aura-live":
        return wsOpen("aura-live") || clickExact([
          '.aura-p0702-nav-btn[data-rail-target="aura-live"]',
          '[data-rail-target="aura-live"]'
        ]);

      case "diagnostics":
        return wsOpen("system") || clickExact([
          '.aura-p0702-nav-btn[data-rail-target="diagnostics"]',
          '[data-rail-target="diagnostics"]'
        ]);

      case "parametres":
        return openAuraSettingsR12();

      default:
        return false;
    }
  };

  const setActive = (key) => {
    const dock = document.getElementById("auraR10Dock");
    if (!dock) return;
    dock.querySelectorAll(".aura-r10-dock-btn").forEach(btn => {
      btn.classList.toggle("is-active", btn.dataset.key === key);
    });
  };

  document.addEventListener("click", (event) => {
    const btn = event.target?.closest?.("#auraR10Dock .aura-r10-dock-btn");
    if (!btn) return;

    const key = String(btn.dataset.key || "").trim();
    if (!key) return;

    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();

    const ok = route(key);
    if (ok) {
      setActive(key);
      console.info("[AURA R11] direct route:", key);
    } else {
      console.warn("[AURA R11] route unavailable:", key);
    }
  }, true);

  console.info("[AURA R11] direct workspace router ready");
})();
