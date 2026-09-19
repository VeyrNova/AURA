/* AURA I18N R4 UTF8 FIX1 - ASCII SAFE CANONICAL ASSET */
(() => {
"use strict";
const SUPPORTED=new Set(["fr-FR","en-US"]);
const boot=String(window.__AURA_BOOT_LOCALE__||"").trim();
const saved=String(localStorage.getItem("aura.locale")||"").trim();
const browser=(navigator.language||"fr-FR").startsWith("en")?"en-US":"fr-FR";
let locale=SUPPORTED.has(boot)?boot:(SUPPORTED.has(saved)?saved:browser);
const exact={
"fr-FR":{"Settings":"Param\u00e8tres","Search":"Rechercher","Send":"Envoyer","Cancel":"Annuler","Close":"Fermer","Back":"Retour","Next":"Suivant","Calendar":"Agenda","Memory":"M\u00e9moire","Weather":"M\u00e9t\u00e9o","System":"Syst\u00e8me","Voice":"Voix","Skills":"Comp\u00e9tences","Ready":"Pr\u00eate","Listening":"\u00c9coute","Thinking":"R\u00e9flexion","LOCAL CONTROL":"CONTR\u00d4LE LOCAL","SYSTEM LIVE":"SYST\u00c8ME EN DIRECT"},
"en-US":{"Param\u00e8tres":"Settings","Rechercher":"Search","Envoyer":"Send","Annuler":"Cancel","Fermer":"Close","Retour":"Back","Suivant":"Next","Agenda":"Calendar","M\u00e9moire":"Memory","M\u00e9t\u00e9o":"Weather","Syst\u00e8me":"System","Voix":"Voice","Comp\u00e9tences":"Skills","Pr\u00eate":"Ready","\u00c9coute":"Listening","R\u00e9flexion":"Thinking","CONTR\u00d4LE LOCAL":"LOCAL CONTROL","SYST\u00c8ME EN DIRECT":"SYSTEM LIVE","RC4.2 transmet le texte uniquement entre la coque locale et le Core local. Aucun acc\u00e8s OS direct depuis JavaScript.":"RC4.2 exchanges text only between the local shell and the local Core. JavaScript has no direct OS access."}
};
const keyed={
"fr-FR":{"common.settings":"Param\u00e8tres","common.search":"Rechercher","common.send":"Envoyer","common.cancel":"Annuler","voice.ready":"Voix disponible","voice.listening":"\u00c9coute"},
"en-US":{"common.settings":"Settings","common.search":"Search","common.send":"Send","common.cancel":"Cancel","voice.ready":"Voice available","voice.listening":"Listening"}
};
function t(k,f){return keyed[locale]?.[k]??f??k}
function apply(root=document){
 document.documentElement.lang=locale;
 root.querySelectorAll?.("[data-i18n]").forEach(el=>{const k=el.getAttribute("data-i18n"); if(k) el.textContent=t(k,el.textContent)});
 const base=root===document?document.body:root;
 if(!base)return;
 const w=document.createTreeWalker(base,NodeFilter.SHOW_TEXT);
 let n;
 while((n=w.nextNode())){
   const p=n.parentElement;
   if(!p||["SCRIPT","STYLE","TEXTAREA","INPUT"].includes(p.tagName))continue;
   const raw=n.nodeValue||"", core=raw.trim();
   if(!core)continue;
   const mapped=exact[locale]?.[core];
   if(mapped&&mapped!==core)n.nodeValue=raw.replace(core,mapped);
 }
}
function setLocale(next){
 if(!SUPPORTED.has(next))return false;
 locale=next;localStorage.setItem("aura.locale",locale);apply();
 window.dispatchEvent(new CustomEvent("aura:locale-changed",{detail:{locale}}));
 return true;
}
window.AURAI18N={getLocale:()=>locale,setLocale,t,apply,supported:["fr-FR","en-US"]};
const bootApply=()=>{localStorage.setItem("aura.locale",locale);apply();setTimeout(()=>apply(),700);setTimeout(()=>apply(),2200)};
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",bootApply,{once:true});else bootApply();
})();

/* AURA I18N R2 \u2014 SETTINGS + HOT LANGUAGE SWITCH */
(() => {
  "use strict";
  if (window.__AURA_I18N_R2_SETTINGS__) return;
  window.__AURA_I18N_R2_SETTINGS__ = true;

  const token = new URLSearchParams(location.search).get("token") || "";

  async function api(action, locale) {
    if (!token) return {ok:false,error:"missing_token"};
    const response = await fetch(`/api/locale?token=${encodeURIComponent(token)}`, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({action, ...(locale ? {locale} : {})})
    });
    let data = {};
    try { data = await response.json(); } catch (_) {}
    if (!response.ok) throw new Error(data.error || `locale ${response.status}`);
    return data;
  }

  function railLabels(locale) {
    const en = locale === "en-US";
    const labels = en ? {
      home:"HOME", conversation:"CONVERSATION", memory:"MEMORY", tasks:"TASKS",
      agenda:"CALENDAR", modules:"MODULES", "aura-live":"AURA LIVE",
      diagnostics:"DIAGNOSTICS", settings:"SETTINGS"
    } : {
      home:"ACCUEIL", conversation:"CONVERSATION", memory:"M\u00c9MOIRE", tasks:"T\u00c2CHES",
      agenda:"AGENDA", modules:"MODULES", "aura-live":"AURA LIVE",
      diagnostics:"DIAGNOSTICS", settings:"PARAM\u00c8TRES"
    };
    document.querySelectorAll("[data-rail-target]").forEach(btn => {
      const id = btn.dataset.railTarget;
      if (!labels[id]) return;
      const labelNode = btn.querySelector(":scope > b");
      if (labelNode) labelNode.textContent = labels[id].charAt(0) + labels[id].slice(1).toLowerCase();
      btn.setAttribute("aria-label", labels[id]);
      btn.title = labels[id];
    });
  }

  function statusText(locale, state) {
    const en = locale === "en-US";
    if (state === "saving") return en ? "Applying language\u2026" : "Application de la langue\u2026";
    if (state === "ok") return en ? "Language applied to AURA." : "Langue appliqu\u00e9e \u00e0 AURA.";
    if (state === "error") return en ? "Unable to change language." : "Impossible de changer la langue.";
    return en ? "Text, speech recognition and Camilla/XTTS follow this language." :
                "Le texte, la reconnaissance vocale et Camilla/XTTS suivent cette langue.";
  }

  async function installControl() {
    const panel = document.querySelector(".aura-p0702-settings-popover");
    const body = panel?.querySelector(".aura-p0702-settings-body");
    if (!body || body.querySelector("[data-aura-language-setting]")) return;

    const wrap = document.createElement("div");
    wrap.dataset.auraLanguageSetting = "1";
    wrap.style.cssText = "margin-top:14px;padding:12px;border:1px solid rgba(120,200,255,.18);border-radius:12px;background:rgba(6,18,34,.34);display:grid;gap:8px";

    const heading = document.createElement("div");
    heading.innerHTML = "<small style='display:block;opacity:.62;letter-spacing:.08em'>G\u00c9N\u00c9RAL / GENERAL</small><b>Langue / Language</b>";

    const select = document.createElement("select");
    select.setAttribute("aria-label", "Langue / Language");
    select.style.cssText = "width:100%;padding:9px 10px;border-radius:9px;border:1px solid rgba(120,200,255,.25);background:#0b1b2f;color:#eef7ff";
    select.innerHTML = "<option value='fr-FR'>Fran\u00e7ais</option><option value='en-US'>English</option>";

    const note = document.createElement("small");
    note.style.cssText = "opacity:.68;line-height:1.35";

    wrap.append(heading, select, note);
    body.appendChild(wrap);

    let current = window.AURAI18N?.getLocale?.() || "fr-FR";
    try {
      const data = await api("get");
      if (data?.locale) current = data.locale;
    } catch (_) {}

    select.value = current;
    note.textContent = statusText(current, "idle");
    railLabels(current);

    select.addEventListener("change", async () => {
      const wanted = select.value;
      const previous = current;
      select.disabled = true;
      note.textContent = statusText(wanted, "saving");
      try {
        const data = await api("set", wanted);
        const loc = data.locale || wanted;
        current = loc;
        window.AURAI18N?.setLocale?.(loc);
        railLabels(loc);
        note.textContent = statusText(loc, "ok");
        window.dispatchEvent(new CustomEvent("aura:runtime-locale-changed", {detail:data}));
      } catch (err) {
        select.value = previous;
        note.textContent = statusText(previous, "error");
      } finally {
        select.disabled = false;
      }
    });
  }

  function applyCurrent() {
    const loc = window.AURAI18N?.getLocale?.() || "fr-FR";
    railLabels(loc);
    installControl();
  }

  document.addEventListener("click", event => {
    if (event.target?.closest?.('[data-rail-target="settings"]')) {
      setTimeout(applyCurrent, 0);
      setTimeout(applyCurrent, 150);
    }
  }, true);

  window.addEventListener("aura:locale-changed", e => railLabels(e.detail?.locale || "fr-FR"));

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyCurrent, {once:true});
  } else {
    applyCurrent();
  }

  setTimeout(applyCurrent, 700);
  setTimeout(applyCurrent, 2200);
})();

/* AURA I18N R3 \u2014 VISIBLE CORE SURFACE COMPLETION */
(() => {
  "use strict";
  if (window.__AURA_I18N_R3_SURFACES__) return;
  window.__AURA_I18N_R3_SURFACES__ = true;

  const PAIRS = [
    ["ACCUEIL","HOME"],
    ["CONVERSATION","CONVERSATION"],
    ["M\u00c9MOIRE","MEMORY"],
    ["T\u00c2CHES","TASKS"],
    ["AGENDA","CALENDAR"],
    ["MODULES","MODULES"],
    ["DIAGNOSTICS","DIAGNOSTICS"],
    ["PARAM\u00c8TRES","SETTINGS"],
    ["PROFIL","PROFILE"],
    ["Profil AURA actif","Active AURA profile"],
    ["Navigation AURA","AURA navigation"],

    ["Fermer","Close"],
    ["Retour","Back"],
    ["Suivant","Next"],
    ["Annuler","Cancel"],
    ["Rechercher","Search"],
    ["RECHERCHER","SEARCH"],
    ["Envoyer","Send"],
    ["ENVOYER","SEND"],
    ["Joindre un fichier","Attach a file"],
    ["\u00c9cris \u00e0 AURA\u2026","Write to AURA\u2026"],
    ["Historique synchronis\u00e9 avec AURA","Conversation history synced with AURA"],
    ["Runtime AURA indisponible","AURA runtime unavailable"],
    ["Le module actif reste au premier plan.","The active module stays in the foreground."],
    ["Conversation AURA","AURA conversation"],
    ["AURA \u00b7 CONVERSATION","AURA \u00b7 CONVERSATION"],

    ["MODE SYNTHETIQUE  backend AURA","SYNTHETIC MODE \u00b7 AURA backend"],
    ["MODE SYNTH\u00c9TIQUE  backend AURA","SYNTHETIC MODE \u00b7 AURA backend"],
    ["BOITE DE RECEPTION","INBOX"],
    ["BO\u00ceTE DE R\u00c9CEPTION","INBOX"],
    ["Afficher les mails de test","Show test emails"],
    ["Rechercher dans les mails","Search emails"],
    ["BROUILLON","DRAFT"],
    ["Preparer un message","Prepare a message"],
    ["Pr\u00e9parer un message","Prepare a message"],
    ["Confirmation AURA requise","AURA confirmation required"],

    ["Retourner \u00e0 l\u2019accueil AURA","Return to AURA home"],
    ["Retourner \u00e0 l'accueil AURA","Return to AURA home"],
    ["Ouvrir la Conversation compl\u00e8te","Open full Conversation"],
    ["Ouvrir la conversation compl\u00e8te","Open full conversation"],
    ["T\u00e2ches \u00b7 rappels \u00b7 notes","Tasks \u00b7 reminders \u00b7 notes"],
    ["M\u00e9t\u00e9o et localisation","Weather and location"],
    ["Cartes \u00b7 itin\u00e9raires \u00b7 POI \u00b7 m\u00e9t\u00e9o trajet","Maps \u00b7 routes \u00b7 POI \u00b7 route weather"],
    ["M\u00e9moire locale AURA","AURA local memory"],
    ["Syst\u00e8me \u00b7 s\u00e9curit\u00e9 \u00b7 actions locales","System \u00b7 security \u00b7 local actions"],

    ["D\u00e9part","Start"],
    ["Destination","Destination"],
    ["CALCUL EN COURS\u2026","CALCULATING\u2026"],
    ["CALCUL EN COURS...","CALCULATING..."],
    ["CALCUL ROUTE","ROUTE CALCULATION"],
    ["CALCUL ROUTE\u2026","CALCULATING ROUTE\u2026"],
    ["OSRM \u00b7 CALCUL DE L\u2019ITIN\u00c9RAIRE","OSRM \u00b7 CALCULATING ROUTE"],
    ["OSRM \u00b7 CALCUL DE L'ITIN\u00c9RAIRE","OSRM \u00b7 CALCULATING ROUTE"],
    ["DESTINATION REQUISE","DESTINATION REQUIRED"],
    ["DESTINATION INTROUVABLE","DESTINATION NOT FOUND"],
    ["G\u00c9OCODAGE INDISPONIBLE","GEOCODING UNAVAILABLE"],
    ["ITIN\u00c9RAIRE INDISPONIBLE","ROUTE UNAVAILABLE"],
    ["POSITION INDISPONIBLE","LOCATION UNAVAILABLE"],

    ["M\u00e9t\u00e9o contextuelle","Contextual weather"],
    ["Couches m\u00e9t\u00e9o","Weather layers"],
    ["Aucune donn\u00e9e horaire structur\u00e9e dans la r\u00e9ponse Aura.","No structured hourly data in AURA's response."],
    ["Demande la m\u00e9t\u00e9o \u00e0 Aura. Les donn\u00e9es affich\u00e9es ici proviendront de sa r\u00e9ponse.","Ask AURA for the weather. The data displayed here will come from its response."],
    ["Demande la m\u00e9t\u00e9o \u00e0 Aura.","Ask AURA for the weather."],

    ["G\u00c9N\u00c9RAL","GENERAL"],
    ["G\u00c9N\u00c9RAL / GENERAL","GENERAL"],
    ["Langue","Language"],
    ["Langue / Language","Language"],
    ["Application de la langue\u2026","Applying language\u2026"],
    ["Langue appliqu\u00e9e \u00e0 AURA.","Language applied to AURA."],
    ["Impossible de changer la langue.","Unable to change language."],
    ["Le texte, la reconnaissance vocale et Camilla/XTTS suivent cette langue.","Text, speech recognition and Camilla/XTTS follow this language."],

    ["Voix","Voice"],
    ["VOIX","VOICE"],
    ["Voix disponible","Voice available"],
    ["Pr\u00eate","Ready"],
    ["PR\u00caTE","READY"],
    ["\u00c9coute","Listening"],
    ["\u00c9COUTE","LISTENING"],
    ["R\u00e9flexion","Thinking"],
    ["R\u00c9FLEXION","THINKING"],
    ["Camilla se charge en arri\u00e8re-plan","Camilla is loading in the background"],
    ["Camilla indisponible \u00b7 Piper actif","Camilla unavailable \u00b7 Piper active"],
    ["CONTR\u00d4LE LOCAL","LOCAL CONTROL"],
    ["SYST\u00c8ME EN DIRECT","SYSTEM LIVE"],

    ["Aucun r\u00e9sultat","No results"],
    ["Aucune donn\u00e9e","No data"],
    ["Indisponible","Unavailable"],
    ["Disponible","Available"],
    ["Chargement\u2026","Loading\u2026"],
    ["Chargement...","Loading..."],
    ["En cours","In progress"],
    ["Termin\u00e9","Completed"],
    ["Erreur","Error"],
    ["S\u00e9curit\u00e9","Security"],
    ["Syst\u00e8me","System"],
    ["M\u00e9t\u00e9o","Weather"],
    ["M\u00e9moire","Memory"],
    ["Param\u00e8tres","Settings"],
    ["T\u00e2ches","Tasks"]
  ];

  const frToEn = new Map(PAIRS);
  const enToFr = new Map(PAIRS.map(([fr,en]) => [en,fr]));

  // Attribute-only phrases can be more descriptive than visible labels.
  const ATTR_PAIRS = [
    ["Fermer","Close"],
    ["Joindre un fichier","Attach a file"],
    ["Profil AURA actif","Active AURA profile"],
    ["Navigation AURA","AURA navigation"],
    ["M\u00e9t\u00e9o contextuelle","Contextual weather"],
    ["Couches m\u00e9t\u00e9o","Weather layers"],
    ["Conversation AURA","AURA conversation"]
  ];
  const attrFrToEn = new Map(ATTR_PAIRS);
  const attrEnToFr = new Map(ATTR_PAIRS.map(([fr,en]) => [en,fr]));

  function locale() {
    return window.AURAI18N?.getLocale?.() || window.__AURA_BOOT_LOCALE__ || "fr-FR";
  }

  function targetMap(loc) {
    return loc === "en-US" ? frToEn : enToFr;
  }

  function targetAttrMap(loc) {
    return loc === "en-US" ? attrFrToEn : attrEnToFr;
  }

  function translateExact(value, loc) {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (!trimmed) return value;
    const mapped = targetMap(loc).get(trimmed);
    if (!mapped || mapped === trimmed) return value;
    const lead = value.match(/^\s*/)?.[0] || "";
    const tail = value.match(/\s*$/)?.[0] || "";
    return lead + mapped + tail;
  }

  function translateAttr(value, loc) {
    if (typeof value !== "string") return value;
    const trimmed = value.trim();
    if (!trimmed) return value;
    const map = targetAttrMap(loc);
    const mapped = map.get(trimmed) || targetMap(loc).get(trimmed);
    return mapped || value;
  }

  function excluded(node) {
    const el = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement;
    if (!el) return true;
    return !!el.closest(
      "script,style,code,pre,[contenteditable='true']," +
      ".aura-p071-history,[data-history]," +
      ".message-content,.chat-message,.assistant-message,.user-message," +
      "[data-aura-chat-content],[data-conversation-message]"
    );
  }

  function translateText(root, loc) {
    if (!root || excluded(root)) return;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (excluded(node)) continue;
      const next = translateExact(node.nodeValue, loc);
      if (next !== node.nodeValue) node.nodeValue = next;
    }
  }

  function translateAttributes(root, loc) {
    const nodes = [];
    if (root?.nodeType === Node.ELEMENT_NODE) nodes.push(root);
    root?.querySelectorAll?.("[title],[aria-label],[placeholder]").forEach(el => nodes.push(el));
    for (const el of nodes) {
      if (excluded(el)) continue;
      for (const name of ["title","aria-label","placeholder"]) {
        if (!el.hasAttribute?.(name)) continue;
        const oldValue = el.getAttribute(name);
        const next = translateAttr(oldValue, loc);
        if (next !== oldValue) el.setAttribute(name, next);
      }
    }
  }

  function normalizeKnownSurfaces(loc) {
    // Navigation rail has stable semantic ids. Apply deterministic labels rather
    // than depending on whatever language its source module originally emitted.
    const rail = loc === "en-US" ? {
      home:"Home", conversation:"Conversation", memory:"Memory", tasks:"Tasks",
      agenda:"Calendar", modules:"Modules", "aura-live":"AURA Live",
      diagnostics:"Diagnostics", settings:"Settings"
    } : {
      home:"Accueil", conversation:"Conversation", memory:"M\u00e9moire", tasks:"T\u00e2ches",
      agenda:"Agenda", modules:"Modules", "aura-live":"AURA Live",
      diagnostics:"Diagnostics", settings:"Param\u00e8tres"
    };
    document.querySelectorAll("[data-rail-target]").forEach(btn => {
      const id = btn.dataset.railTarget;
      const label = rail[id];
      if (!label) return;
      const labelNode = btn.querySelector(":scope > b");
      if (labelNode) labelNode.textContent = label;
      btn.title = label;
      btn.setAttribute("aria-label", label);
    });

    const langSelect = document.querySelector("[data-aura-language-setting] select");
    const langWrap = document.querySelector("[data-aura-language-setting]");
    if (langSelect && langWrap) {
      const small = langWrap.querySelector("small");
      const bold = langWrap.querySelector("b");
      if (small) small.textContent = loc === "en-US" ? "GENERAL" : "G\u00c9N\u00c9RAL";
      if (bold) bold.textContent = loc === "en-US" ? "Language" : "Langue";
      langSelect.setAttribute("aria-label", loc === "en-US" ? "Language" : "Langue");
    }
  }

  function apply(root = document) {
    const loc = locale();
    document.documentElement.lang = loc;
    const base = root === document ? document.body : root;
    if (!base) return;
    normalizeKnownSurfaces(loc);
    translateText(base, loc);
    translateAttributes(base, loc);
  }

  let timer = 0;
  function schedule(delay = 0) {
    clearTimeout(timer);
    timer = setTimeout(() => {
      const run = () => apply();
      if ("requestIdleCallback" in window) {
        requestIdleCallback(run, {timeout: 250});
      } else {
        run();
      }
    }, delay);
  }

  // No MutationObserver: AURA has historical UI invariants against global DOM
  // observers. Re-apply only after user/workspace events plus a low-frequency
  // idle safety pass for asynchronously updated status text.
  for (const evt of [
    "aura:locale-changed",
    "aura:runtime-locale-changed",
    "aura:workspace-manager-ready",
    "aura:workspace-changed",
    "aura:voice-state",
    "aura:voice-status",
    "aura:route-updated",
    "aura:weather-updated"
  ]) {
    window.addEventListener(evt, () => {
      schedule(0);
      schedule(180);
      schedule(700);
    });
  }

  document.addEventListener("click", () => {
    schedule(0);
    schedule(120);
    schedule(450);
  }, true);

  document.addEventListener("change", () => {
    schedule(0);
    schedule(160);
  }, true);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) schedule(0);
  });

  const idlePass = () => {
    schedule(0);
    setTimeout(idlePass, 2500);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      schedule(0);
      schedule(350);
      schedule(1200);
      setTimeout(idlePass, 2500);
    }, {once:true});
  } else {
    schedule(0);
    schedule(350);
    schedule(1200);
    setTimeout(idlePass, 2500);
  }

  window.AURAI18NSurfaces = Object.freeze({
    version: "R3",
    pairCount: PAIRS.length,
    apply,
    schedule
  });
})();

/* AURA I18N R4 PERSISTENCE FIX1 - authoritative persisted locale on boot */
(() => {
  "use strict";
  if (window.__AURA_I18N_R4_PERSISTENCE_FIX1__) return;
  window.__AURA_I18N_R4_PERSISTENCE_FIX1__ = true;

  const token = new URLSearchParams(location.search).get("token") || "";

  async function fetchPersistedLocale() {
    if (!token) return null;
    const response = await fetch(`/api/locale?token=${encodeURIComponent(token)}`, {
      method: "POST",
      cache: "no-store",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({action:"get"})
    });
    if (!response.ok) return null;
    const data = await response.json().catch(() => null);
    const loc = data?.locale;
    return (loc === "fr-FR" || loc === "en-US") ? loc : null;
  }

  async function syncPersistedLocale() {
    try {
      const loc = await fetchPersistedLocale();
      if (!loc) return false;
      window.__AURA_BOOT_LOCALE__ = loc;
      try { localStorage.setItem("aura.locale", loc); } catch (_) {}
      const changed = window.AURAI18N?.setLocale?.(loc);
      window.AURAI18NSurfaces?.apply?.();
      window.dispatchEvent(new CustomEvent("aura:persisted-locale-synced", {
        detail: {locale:loc, changed:changed !== false}
      }));
      return true;
    } catch (_) {
      return false;
    }
  }

  const boot = () => {
    syncPersistedLocale();
    setTimeout(syncPersistedLocale, 250);
    setTimeout(syncPersistedLocale, 900);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, {once:true});
  } else {
    boot();
  }

  window.AURAI18NPersistence = Object.freeze({sync: syncPersistedLocale});
})();

/* AURA I18N R5 - COMPLETE PRODUCT SURFACE + PRODUCT STATUS */
(() => {
  "use strict";
  if (window.__AURA_I18N_R5__) return;
  window.__AURA_I18N_R5__ = true;
  const PAIRS = [["Configuration locale AURA", "Local AURA configuration"], ["Le rail est pr\u00eat pour le workspace Param\u00e8tres final. Les r\u00e9glages techniques existants restent inchang\u00e9s afin de ne pas modifier le runtime valid\u00e9.", "The navigation rail is ready for the final Settings workspace. Existing technical settings remain unchanged to preserve the validated runtime."], ["Profil", "Profile"], ["Local + hybride", "Local + hybrid"], ["SOUVENIRS", "MEMORIES"], ["Rechercher dans la m\u00e9moire...", "Search memory..."], ["SENSIBLES", "SENSITIVE"], ["Ajouter un souvenir explicite...", "Add an explicit memory..."], ["RETENIR", "REMEMBER"], ["CONTEXTE R\u00c9CENT", "RECENT CONTEXT"], ["M\u00e9moires inject\u00e9es r\u00e9cemment", "Recently injected memories"], ["Aucun souvenir inject\u00e9 r\u00e9cemment.", "No memory injected recently."], ["M\u00c9MOIRE PERSISTANTE", "PERSISTENT MEMORY"], ["MODE PRIV\u00c9", "PRIVATE MODE"], ["EFFACER LE PROFIL", "CLEAR PROFILE"], ["T\u00c2CHES \u00b7 AURA + GOOGLE", "TASKS \u00b7 AURA + GOOGLE"], ["Synchronisation AURA + Google...", "AURA + Google synchronization..."], ["ACTUALISER TOUT", "REFRESH ALL"], ["Nouvelle t\u00e2che...", "New task..."], ["AJOUTER", "ADD"], ["En attente", "Pending"], ["Chargement Google non effectu\u00e9.", "Google loading not performed."], ["T\u00e2ches enregistr\u00e9es dans AURA", "Tasks stored in AURA"], ["CALENDRIER", "CALENDAR"], ["RAPPELS", "REMINDERS"], ["AGENDA \u00b7 AURA + GOOGLE", "CALENDAR \u00b7 AURA + GOOGLE"], ["Synchronis\u00e9", "Synchronized"], ["AUJOURD'HUI", "TODAY"], ["\u00c9L\u00c9MENTS DU MOIS", "MONTH ITEMS"], ["Aucun \u00e9v\u00e9nement ou rappel pour ce mois.", "No event or reminder for this month."], ["M\u00c9T\u00c9O", "WEATHER"], ["Pr\u00e9visions \u00b7 carte m\u00e9t\u00e9o", "Forecast \u00b7 weather map"], ["RECHERCHE", "SEARCH"], ["Recherche IA avec sources", "AI search with sources"], ["G\u00e9rer, rechercher ou joindre un fichier", "Manage, search or attach a file"], ["Centre d'activit\u00e9 et alertes", "Activity and alerts center"], ["Courriels recherche brouillons envoi", "Email search drafts sending"], ["Recherche & gestion", "Search & management"], ["SIGNES VITAUX", "VITAL SIGNS"], ["Activit\u00e9 \u00b7 capteurs \u00b7 donn\u00e9es isol\u00e9es", "Activity \u00b7 sensors \u00b7 isolated data"], ["Runtime \u00b7 modules \u00b7 \u00e9tat simul\u00e9", "Runtime \u00b7 modules \u00b7 simulated state"], ["ACCESSIBILIT\u00c9", "ACCESSIBILITY"], ["Contraste \u00b7 texte \u00b7 mouvement", "Contrast \u00b7 text \u00b7 motion"], ["PROJECT ACTIF", "ACTIVE PROJECT"], ["PROJET ACTIF", "ACTIVE PROJECT"], ["PROGRESSION", "PROGRESS"], ["FIN ESTIM\u00c9E", "ESTIMATED FINISH"], ["DERNI\u00c8RE ACTION", "LAST ACTION"], ["PROCHAINE ACTION", "NEXT ACTION"], ["MODE S\u00c9CURIS\u00c9", "SECURE MODE"], ["ACTIONS LOCALES S\u00dbRES", "SAFE LOCAL ACTIONS"], ["CALCULATRICE", "CALCULATOR"], ["BLOC-NOTES", "NOTEPAD"], ["EXPLORATEUR", "EXPLORER"], ["PROJETS / DOSSIERS AUTORIS\u00c9S", "AUTHORIZED PROJECTS / FOLDERS"], ["Nom du projet (optionnel)", "Project name (optional)"], ["AUTORISER", "AUTHORIZE"], ["Aucun dossier autoris\u00e9 pour le moment.", "No folder authorized yet."], ["APER\u00c7U DU DOSSIER", "FOLDER PREVIEW"], ["FICHIER AUTORIS\u00c9 - LECTURE LOCALE", "AUTHORIZED FILE - LOCAL READ"], ["Aucun contenu de fichier charg\u00e9.", "No file content loaded."], ["INTELLIGENCE DOCUMENTAIRE LOCALE", "LOCAL DOCUMENT INTELLIGENCE"], ["CONTEXTE ACTIF", "ACTIVE CONTEXT"], ["M\u00e9moire persistante", "Persistent memory"], ["SUGGESTIONS", "SUGGESTIONS"], ["R\u00e9sumer la conversation", "Summarize the conversation"], ["Extraire les t\u00e2ches", "Extract tasks"], ["Rechercher des r\u00e9f\u00e9rences", "Search references"], ["Cr\u00e9er une note", "Create a note"], ["Parle-moi ou \u00e9cris ton message...", "Speak to me or type your message..."], ["Pr\u00eate pour la suite", "Ready for what's next"], ["Entr\u00e9e pour envoyer \u00b7 maintenir le micro pour parler", "Enter to send \u00b7 hold the microphone to speak"], ["\u00c9cris \u00e0 AURA...", "Write to AURA..."], ["JANVIER", "JANUARY"], ["F\u00c9VRIER", "FEBRUARY"], ["MARS", "MARCH"], ["AVRIL", "APRIL"], ["MAI", "MAY"], ["JUIN", "JUNE"], ["JUILLET", "JULY"], ["AO\u00dbT", "AUGUST"], ["SEPTEMBRE", "SEPTEMBER"], ["OCTOBRE", "OCTOBER"], ["NOVEMBRE", "NOVEMBER"], ["D\u00c9CEMBRE", "DECEMBER"], ["LUN", "MON"], ["MAR", "TUE"], ["MER", "WED"], ["JEU", "THU"], ["VEN", "FRI"], ["SAM", "SAT"], ["DIM", "SUN"]];
  const FR_EN = new Map(PAIRS);
  const EN_FR = new Map(PAIRS.map(([fr,en]) => [en,fr]));
  const PRODUCT = {
    productVersion:"v2.3",
    intelligenceRuntime:"v3",
    uiRelease:"0.7.2.2-rc4.2"
  };
  function locale(){ return window.AURAI18N?.getLocale?.() || window.__AURA_BOOT_LOCALE__ || "fr-FR"; }
  function excluded(node){
    const el=node?.nodeType===Node.ELEMENT_NODE?node:node?.parentElement;
    if(!el) return true;
    return !!el.closest("script,style,code,pre,[contenteditable='true'],.message-content,.assistant-message,.user-message,[data-conversation-message]");
  }
  function exact(value,loc){
    if(typeof value!=="string") return value;
    const core=value.trim(); if(!core) return value;
    const map=loc==="en-US"?FR_EN:EN_FR;
    let mapped=map.get(core);
    if(!mapped){
      const month=core.match(/^(JANVIER|F\u00c9VRIER|MARS|AVRIL|MAI|JUIN|JUILLET|AO\u00dbT|SEPTEMBRE|OCTOBRE|NOVEMBRE|D\u00c9CEMBRE)\s+(\d{4})$/i);
      if(month && loc==="en-US") mapped=(FR_EN.get(month[1].toUpperCase())||month[1])+" "+month[2];
      const shown=core.match(/^(\d+)\s+affich\u00e9s$/i); if(shown && loc==="en-US") mapped=shown[1]+" shown";
    }
    if(!mapped || mapped===core) return value;
    const lead=value.match(/^\s*/)?.[0]||"", tail=value.match(/\s*$/)?.[0]||"";
    return lead+mapped+tail;
  }
  function productOverride(value,loc){
    if(typeof value!=="string") return value;
    const core=value.trim(), en=loc==="en-US";
    const m=new Map([
      ["AURA v2.0","AURA v2.3"],
      ["v1.3.0 INTERACTIVE","PRODUCT v2.3 \u00b7 INTELLIGENCE v3"],
      ["P0.7","UI 0.7.2.2-rc4.2"],
      ["M190 \u2014 Mind / Neural State Visualization",en?"P230 \u2014 AURA Skills v2.3 certified":"P230 \u2014 AURA Skills v2.3 certifi\u00e9"],
      ["A200 \u2014 Autonomous PC Agent + AURA OS Final Acceptance",en?"P240 \u2014 Product Installer v2.4 paused":"P240 \u2014 Installeur produit v2.4 en pause"],
      ["96.4%","\u2014"],
      ["71 JOURS D'AVANCE \u00b7 CONFIANCE 95%",en?"P240 PAUSED \u00b7 CLEAN WINDOWS ACCEPTANCE PENDING":"P240 EN PAUSE \u00b7 VALIDATION WINDOWS PROPRE EN ATTENTE"]
    ]);
    return m.get(core)||value;
  }
  function apply(root=document){
    const loc=locale(); document.documentElement.lang=loc;
    const base=root===document?document.body:root; if(!base) return;
    const w=document.createTreeWalker(base,NodeFilter.SHOW_TEXT); let n;
    while((n=w.nextNode())){ if(excluded(n)) continue; let v=productOverride(n.nodeValue,loc); v=exact(v,loc); if(v!==n.nodeValue)n.nodeValue=v; }
    base.querySelectorAll?.("[title],[aria-label],[placeholder]").forEach(el=>{
      if(excluded(el))return;
      for(const a of ["title","aria-label","placeholder"]){ if(!el.hasAttribute(a))continue; let v=el.getAttribute(a); v=productOverride(v,loc); v=exact(v,loc); el.setAttribute(a,v); }
    });
  }
  let timer=0; function schedule(d=0){clearTimeout(timer);timer=setTimeout(()=>apply(),d);}
  ["aura:locale-changed","aura:runtime-locale-changed","aura:persisted-locale-synced","aura:workspace-changed","aura:workspace-manager-ready","aura:voice-status"].forEach(e=>window.addEventListener(e,()=>{schedule(0);setTimeout(()=>apply(),180);setTimeout(()=>apply(),700);}));
  document.addEventListener("click",()=>{schedule(0);setTimeout(()=>apply(),120);setTimeout(()=>apply(),450);},true);
  document.addEventListener("change",()=>{schedule(0);setTimeout(()=>apply(),160);},true);
  const loop=()=>{apply();setTimeout(loop,1800);};
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>{apply();setTimeout(loop,1800);},{once:true});
  else {apply();setTimeout(loop,1800);}
  window.AURAI18NR5=Object.freeze({apply,product:PRODUCT});
})();
