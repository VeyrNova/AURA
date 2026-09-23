
from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import os

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
DEV_ACCENT = "#F0A23A"
DEV_ACCENT_BRIGHT = "#F6B85F"
MAX_WEBVIEWS = 8

try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except Exception:
    QApplication = None
    QWebEngineView = object
    WEBENGINE_AVAILABLE = False

def _candidate_webviews(window=None):
    if not WEBENGINE_AVAILABLE:
        return []
    found = []
    seen = set()
    def add(view):
        if view is None:
            return
        ident = id(view)
        if ident in seen:
            return
        seen.add(ident)
        found.append(view)

    if window is not None:
        if isinstance(window, QWebEngineView):
            add(window)
        try:
            for view in window.findChildren(QWebEngineView):
                add(view)
        except Exception:
            pass

    try:
        app = QApplication.instance()
        if app is not None:
            for top in app.topLevelWidgets():
                if isinstance(top, QWebEngineView):
                    add(top)
                try:
                    for view in top.findChildren(QWebEngineView):
                        add(view)
                except Exception:
                    pass
    except Exception:
        pass

    # Prefer visible webviews first.
    try:
        found.sort(key=lambda v: (not bool(v.isVisible()), -(int(v.width()) * int(v.height()))))
    except Exception:
        pass
    return found[:MAX_WEBVIEWS]

def _run_js(view, script: str) -> bool:
    try:
        page = view.page()
        if page is None:
            return False
        page.runJavaScript(script)
        return True
    except Exception:
        return False

def developer_mode_script(enabled: bool) -> str:
    flag = "true" if enabled else "false"
    return r"""
(() => {
  const enabled = __FLAG__;
  const D = document;
  const root = D.documentElement;
  if (!root) return {ok:false, reason:"no-root"};

  const STYLE_ID = "aura-dev-mode-web-style";
  const OVERLAY_ID = "aura-dev-mode-web-overlay";
  const BADGE_ID = "aura-dev-mode-web-badge";
  const STATUS_ID = "aura-dev-mode-web-status";
  const AMBIENT_ID = "aura-dev-mode-web-ambient";

  let style = D.getElementById(STYLE_ID);
  if (!style) {
    style = D.createElement("style");
    style.id = STYLE_ID;
    style.textContent = `
      html.aura-dev-active, body.aura-dev-active {
        --aura-dev-accent: #F0A23A !important;
        --aura-dev-accent-bright: #F6B85F !important;
      }
      #${OVERLAY_ID} {
        position: fixed; inset: 4px; z-index: 2147483000;
        pointer-events: none; border: 2px solid rgba(240,162,58,.78);
        border-radius: 12px;
        box-shadow: inset 0 0 34px rgba(240,162,58,.08),
                    0 0 24px rgba(240,162,58,.12);
      }
      #${BADGE_ID} {
        position: fixed; right: 22px; top: 18px; z-index: 2147483002;
        pointer-events: none; padding: 6px 12px;
        border: 1px solid rgba(240,162,58,.95); border-radius: 8px;
        background: rgba(12,15,22,.94); color: #F6B85F;
        font: 800 12px/1.2 Inter, Segoe UI, sans-serif;
        letter-spacing: 1.3px;
        box-shadow: 0 0 20px rgba(240,162,58,.16);
      }
      #${STATUS_ID} {
        position: fixed; right: 22px; top: 56px; z-index: 2147483002;
        pointer-events: none; padding: 5px 10px;
        border: 1px solid rgba(240,162,58,.45); border-radius: 7px;
        background: rgba(12,15,22,.90); color: #D7A457;
        font: 650 10px/1.2 Inter, Segoe UI, sans-serif;
        letter-spacing: .35px;
      }
      #${AMBIENT_ID} {
        position: fixed; inset: 0; z-index: 2147482999; pointer-events: none;
        background:
          radial-gradient(circle at 88% 8%, rgba(240,162,58,.14), transparent 27%),
          radial-gradient(circle at 4% 94%, rgba(240,162,58,.07), transparent 22%);
        mix-blend-mode: screen;
      }
      .aura-dev-composer {
        outline: 1px solid rgba(240,162,58,.72) !important;
        box-shadow: 0 0 0 3px rgba(240,162,58,.08) !important;
      }
    `;
    (D.head || root).appendChild(style);
  }

  const variableKeys = ["--aura-accent","--accent","--accent-primary","--neon-primary","--primary-accent"];
  if (enabled) {
    root.classList.add("aura-dev-active");
    if (D.body) D.body.classList.add("aura-dev-active");

    variableKeys.forEach((key, index) => {
      const dataKey = "auraDevVar" + index;
      if (!(dataKey in root.dataset)) root.dataset[dataKey] = root.style.getPropertyValue(key) || "";
      root.style.setProperty(key, "#F0A23A");
    });

    function ensure(id, text) {
      let el = D.getElementById(id);
      if (!el) {
        el = D.createElement("div"); el.id = id;
        if (text) el.textContent = text;
        (D.body || root).appendChild(el);
      }
      return el;
    }
    ensure(AMBIENT_ID, "");
    ensure(OVERLAY_ID, "");
    ensure(BADGE_ID, "AURA // DEV");
    ensure(STATUS_ID, "DEV ACTIVE · WRITE GATED · AUDIT ON");

    const candidates = [...D.querySelectorAll('textarea,input[type="text"],input:not([type]),[contenteditable="true"]')]
      .filter(el => {
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 140 && r.height > 18 && s.visibility !== "hidden" && s.display !== "none";
      });
    candidates.sort((a,b) => b.getBoundingClientRect().top - a.getBoundingClientRect().top);
    const composer = candidates[0];
    if (composer) {
      composer.classList.add("aura-dev-composer");
      if ("placeholder" in composer) {
        if (!composer.dataset.auraDevOriginalPlaceholder)
          composer.dataset.auraDevOriginalPlaceholder = composer.getAttribute("placeholder") || "";
        composer.setAttribute("placeholder", "AURA DEV // Que veux-tu modifier ?");
      }
    }
  } else {
    root.classList.remove("aura-dev-active");
    if (D.body) D.body.classList.remove("aura-dev-active");
    [OVERLAY_ID,BADGE_ID,STATUS_ID,AMBIENT_ID].forEach(id => {
      const el=D.getElementById(id); if(el) el.remove();
    });
    variableKeys.forEach((key,index) => {
      const dataKey="auraDevVar"+index;
      const old=root.dataset[dataKey];
      if (old) root.style.setProperty(key,old); else root.style.removeProperty(key);
      delete root.dataset[dataKey];
    });
    D.querySelectorAll(".aura-dev-composer").forEach(el => {
      el.classList.remove("aura-dev-composer");
      if ("placeholder" in el && el.dataset.auraDevOriginalPlaceholder !== undefined) {
        el.setAttribute("placeholder", el.dataset.auraDevOriginalPlaceholder || "");
        delete el.dataset.auraDevOriginalPlaceholder;
      }
    });
  }
  return {ok:true, enabled};
})();
""".replace("__FLAG__", flag)

def apply_web_developer_mode(window, enabled: bool) -> dict[str, Any]:
    script = developer_mode_script(bool(enabled))
    views = _candidate_webviews(window)
    applied = sum(1 for view in views if _run_js(view, script))
    return {
        "schema":"aura.dev-web-visual-result.v1",
        "enabled":bool(enabled),
        "webengine_available":WEBENGINE_AVAILABLE,
        "webviews_found":len(views),
        "webviews_applied":applied,
    }

def _workspace_data(root=None):
    base = Path(root).resolve() if root is not None else ROOT
    from runtime.aura_developer_live_bridge import workspace_snapshot
    return workspace_snapshot(base)

def workspace_script(snapshot: dict[str, Any]) -> str:
    payload = json.dumps(snapshot, ensure_ascii=False).replace("</", "<\\/")
    return r"""
(() => {
  const D=document, root=D.documentElement;
  if(!root) return {ok:false};
  const ID="aura-dev-workspace-web";
  const existing=D.getElementById(ID);
  if(existing){ existing.remove(); return {ok:true, action:"closed-existing"}; }

  const data=__PAYLOAD__;
  const overlay=D.createElement("div");
  overlay.id=ID;
  Object.assign(overlay.style,{
    position:"fixed", inset:"0", zIndex:"2147483100",
    background:"rgba(4,6,10,.76)", backdropFilter:"blur(8px)",
    display:"flex", alignItems:"center", justifyContent:"center",
    pointerEvents:"auto", fontFamily:"Inter, Segoe UI, sans-serif"
  });

  const panel=D.createElement("div");
  Object.assign(panel.style,{
    width:"min(1080px,90vw)", height:"min(720px,84vh)",
    background:"linear-gradient(180deg,rgba(16,19,28,.99),rgba(8,11,17,.99))",
    border:"1px solid rgba(240,162,58,.68)", borderRadius:"16px",
    boxShadow:"0 24px 90px rgba(0,0,0,.55),0 0 34px rgba(240,162,58,.12)",
    color:"#E8E9ED", display:"flex", flexDirection:"column", overflow:"hidden"
  });

  const header=D.createElement("div");
  Object.assign(header.style,{
    display:"flex",alignItems:"center",padding:"18px 22px",
    borderBottom:"1px solid rgba(240,162,58,.24)"
  });
  const title=D.createElement("div");
  title.textContent="AURA // DEVELOPER WORKSPACE";
  Object.assign(title.style,{color:"#F6B85F",fontSize:"16px",fontWeight:"800",letterSpacing:"1.1px"});
  const safety=D.createElement("div");
  safety.textContent="WRITE GATED · TESTS REQUIRED · AUDIT ON";
  Object.assign(safety.style,{marginLeft:"18px",color:"#B98A4D",fontSize:"10px",fontWeight:"700"});
  const close=D.createElement("button");
  close.textContent="FERMER";
  Object.assign(close.style,{
    marginLeft:"auto",background:"#171B25",color:"#F6B85F",
    border:"1px solid rgba(240,162,58,.45)",borderRadius:"7px",
    padding:"7px 12px",cursor:"pointer"
  });
  close.onclick=()=>overlay.remove();
  header.append(title,safety,close);

  const body=D.createElement("div");
  Object.assign(body.style,{display:"grid",gridTemplateColumns:"320px 1fr",gap:"0",flex:"1",minHeight:"0"});

  const left=D.createElement("div");
  Object.assign(left.style,{padding:"20px",borderRight:"1px solid rgba(240,162,58,.18)",overflow:"auto"});
  const mode=D.createElement("div");
  mode.textContent=(data.developer_mode && data.developer_mode.enabled) ? "● MODE DÉVELOPPEUR ACTIF" : "○ MODE DÉVELOPPEUR INACTIF";
  Object.assign(mode.style,{color:"#F6B85F",fontSize:"13px",fontWeight:"800",marginBottom:"18px"});
  const gates=D.createElement("pre");
  gates.textContent=JSON.stringify(data.safety||{},null,2);
  Object.assign(gates.style,{whiteSpace:"pre-wrap",color:"#C7CBD3",fontSize:"11px",lineHeight:"1.55"});
  left.append(mode,gates);

  const right=D.createElement("div");
  Object.assign(right.style,{padding:"20px",overflow:"auto"});
  const section=D.createElement("div");
  section.textContent="TRANSACTIONS RÉCENTES";
  Object.assign(section.style,{color:"#F6B85F",fontSize:"11px",fontWeight:"800",letterSpacing:".8px",marginBottom:"10px"});
  const tx=D.createElement("pre");
  tx.textContent=JSON.stringify(data.recent_transactions||[],null,2);
  Object.assign(tx.style,{whiteSpace:"pre-wrap",color:"#D6D9DF",fontSize:"11px",lineHeight:"1.5",background:"#090C12",padding:"14px",borderRadius:"9px"});
  const auditTitle=D.createElement("div");
  auditTitle.textContent="AUDIT HEAD";
  Object.assign(auditTitle.style,{color:"#F6B85F",fontSize:"11px",fontWeight:"800",letterSpacing:".8px",margin:"18px 0 10px"});
  const audit=D.createElement("pre");
  audit.textContent=JSON.stringify(data.audit_head||null,null,2);
  Object.assign(audit.style,{whiteSpace:"pre-wrap",color:"#D6D9DF",fontSize:"11px",lineHeight:"1.5",background:"#090C12",padding:"14px",borderRadius:"9px"});
  right.append(section,tx,auditTitle,audit);

  body.append(left,right);
  panel.append(header,body);
  overlay.append(panel);
  (D.body||root).appendChild(overlay);
  return {ok:true, action:"opened"};
})();
""".replace("__PAYLOAD__", payload)

def open_web_developer_workspace(window, *, root=None) -> dict[str, Any]:
    script = workspace_script(_workspace_data(root))
    views = _candidate_webviews(window)
    applied = sum(1 for view in views if _run_js(view, script))
    return {
        "schema":"aura.dev-web-workspace-result.v1",
        "webengine_available":WEBENGINE_AVAILABLE,
        "webviews_found":len(views),
        "webviews_applied":applied,
        "opened":applied > 0,
    }

def capability_snapshot():
    return {
        "schema":"aura.developer-web-surface-capabilities.v1",
        "qwebengine_binding":True,
        "threejs_shell_overlay":True,
        "z_index":2147483000,
        "amber_identity":True,
        "web_workspace":True,
        "native_qt_fallback_preserved":True,
        "web_asset_mutation_required":False,
    }
