(() => {
  "use strict";
  const ROOT_ID = "aura-project-active-v130";
  const JSON_URL = "workspace_project_active_v130.json";
  const REFRESH_MS = 1600;
  const INTERACTIVE_SELECTOR = 'button, a[href], input, textarea, select, option, [role="button"], [contenteditable], [tabindex]';
  const STORAGE_KEY = "aura_project_active_v130_pos";

  const esc = (value) => String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");

  function isDocked(root) {
    return root.parentElement?.matches("aside.telemetry.glass") === true;
  }

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (!root) {
      root = document.createElement("aside");
      root.id = ROOT_ID;
      root.className = "aura-project-active-v130";
      root.setAttribute("aria-live", "polite");
      root.setAttribute("aria-label", "Projet actif AURA");
      document.body.appendChild(root);
    }

    const host = document.querySelector("aside.telemetry.glass");
    if (host && root.parentElement !== host) {
      host.appendChild(root);
      root.style.removeProperty("left");
      root.style.removeProperty("top");
      root.style.removeProperty("right");
      sessionStorage.removeItem(STORAGE_KEY);
    }

    return root;
  }

  function actuallyVisibleV130(el) {
    if (!el || !el.isConnected) return false;
    let node = el;
    while (node && node.nodeType === 1) {
      const style = window.getComputedStyle(node);
      if (style.display === "none" || style.visibility === "hidden" || Number(style.opacity || 1) === 0) return false;
      node = node.parentElement;
    }
    const rect = el.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return false;
    if (rect.bottom <= 0 || rect.right <= 0 || rect.top >= window.innerHeight || rect.left >= window.innerWidth) return false;
    const x = Math.max(0, Math.min(window.innerWidth - 1, rect.left + Math.min(rect.width / 2, 24)));
    const y = Math.max(0, Math.min(window.innerHeight - 1, rect.top + Math.min(rect.height / 2, 18)));
    const top = document.elementFromPoint(x, y);
    return !!top && (top === el || el.contains(top) || top.contains(el));
  }

  function foregroundPanelRectV130() {
    const labels = new Set(["PRODUCTIVITY CORE", "AURA PERSONAL RESULTS"]);
    const nodes = document.querySelectorAll("body *");
    for (const el of nodes) {
      if (!labels.has((el.textContent || "").trim())) continue;
      if (!actuallyVisibleV130(el)) continue;
      let node = el.parentElement;
      while (node && node !== document.body) {
        const rect = node.getBoundingClientRect();
        if (
          rect.width >= 300 &&
          rect.width <= 760 &&
          rect.height >= 120 &&
          rect.height <= window.innerHeight &&
          rect.right > 0 &&
          rect.left < window.innerWidth
        ) {
          return rect;
        }
        node = node.parentElement;
      }
    }
    return null;
  }

  function placeProjectCardV130(root) {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const pos = JSON.parse(stored);
        if (pos && typeof pos.left === "number" && typeof pos.top === "number") {
          const clamped = clampPos(pos.left, pos.top, root);
          root.style.left = `${clamped.left}px`;
          root.style.top = `${clamped.top}px`;
          root.style.removeProperty("right");
          sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ left: clamped.left, top: clamped.top }));
          return;
        }
      } catch (_) {}
    }

    root.style.removeProperty("left");
    root.style.removeProperty("top");
    root.style.removeProperty("right");
    
    const blocker = foregroundPanelRectV130();
    if (!blocker) return;

    const cardWidth = window.innerWidth <= 1250 ? 285 : 320;
    const gap = 16;
    const shiftedRight = Math.max(24, Math.ceil(window.innerWidth - blocker.left + gap));
    const shiftedLeft = window.innerWidth - shiftedRight - cardWidth;

    if (shiftedLeft >= 220) {
      root.style.right = `${shiftedRight}px`;
    }
  }

  let isDragging = false;
  let pointerId = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let rootStartLeft = 0;
  let rootStartTop = 0;
  let prevUserSelect = null;

  function clampPos(left, top, root) {
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const w = root.offsetWidth;
    const h = root.offsetHeight;
    const maxLeft = Math.max(0, vw - w);
    const maxTop = Math.max(0, vh - h);
    return {
      left: Math.max(0, Math.min(left, maxLeft)),
      top: Math.max(0, Math.min(top, maxTop))
    };
  }

  function savePos(root) {
    const left = parseInt(root.style.left, 10) || 0;
    const top = parseInt(root.style.top, 10) || 0;
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ left, top }));
  }

  function cleanupDrag(root) {
    const savedPointerId = pointerId;
    const savedUserSelect = prevUserSelect;
    
    isDragging = false;
    pointerId = null;
    prevUserSelect = null;

    if (savedUserSelect !== null) {
      document.body.style.userSelect = savedUserSelect;
    }
    
    if (savedPointerId !== null) {
      try {
        if (root.hasPointerCapture(savedPointerId)) {
          root.releasePointerCapture(savedPointerId);
        }
      } catch (_) {}
    }
  }

  function initDrag(root) {
    function onPointerDown(e) {
      const head = e.target.closest(".aura-project-active-v130__head");
      if (!head || !root.contains(head)) return;
      if (e.target.closest(INTERACTIVE_SELECTOR)) return;

      e.preventDefault();
      root.setPointerCapture(e.pointerId);
      pointerId = e.pointerId;
      isDragging = true;
      prevUserSelect = document.body.style.userSelect;
      document.body.style.userSelect = "none";

      const rect = root.getBoundingClientRect();
      rootStartLeft = rect.left;
      rootStartTop = rect.top;
      dragStartX = e.clientX;
      dragStartY = e.clientY;
    }

    function onPointerMove(e) {
      if (!isDragging || pointerId === null || e.pointerId !== pointerId) return;
      e.preventDefault();

      const dx = e.clientX - dragStartX;
      const dy = e.clientY - dragStartY;
      
      let newLeft = rootStartLeft + dx;
      let newTop = rootStartTop + dy;

      const clamped = clampPos(newLeft, newTop, root);
      root.style.left = `${clamped.left}px`;
      root.style.top = `${clamped.top}px`;
      root.style.removeProperty("right");
      
      savePos(root);
    }

    function onPointerUp(e) {
      if (!isDragging || pointerId === null || e.pointerId !== pointerId) return;
      cleanupDrag(root);
    }

    function onPointerCancel(e) {
      if (!isDragging || pointerId === null || e.pointerId !== pointerId) return;
      cleanupDrag(root);
    }

    function onLostPointerCapture(e) {
      if (!isDragging) return;
      cleanupDrag(root);
    }

    function onDblClick(e) {
      const head = e.target.closest(".aura-project-active-v130__head");
      if (!head || !root.contains(head)) return;
      if (e.target.closest(INTERACTIVE_SELECTOR)) return;

      sessionStorage.removeItem(STORAGE_KEY);
      root.style.removeProperty("left");
      root.style.removeProperty("top");
      root.style.removeProperty("right");
      placeProjectCardV130(root);
    }

    function onResize() {
      const stored = sessionStorage.getItem(STORAGE_KEY);
      if (stored) {
        try {
          const pos = JSON.parse(stored);
          if (pos && typeof pos.left === "number" && typeof pos.top === "number") {
            const clamped = clampPos(pos.left, pos.top, root);
            root.style.left = `${clamped.left}px`;
            root.style.top = `${clamped.top}px`;
            root.style.removeProperty("right");
            savePos(root);
          }
        } catch (_) {}
      }
    }

    root.addEventListener("pointerdown", onPointerDown);
    root.addEventListener("pointermove", onPointerMove);
    root.addEventListener("pointerup", onPointerUp);
    root.addEventListener("pointercancel", onPointerCancel);
    root.addEventListener("lostpointercapture", onLostPointerCapture);
    root.addEventListener("dblclick", onDblClick);
    window.addEventListener("resize", onResize);
  }

  function render(snapshot) {
    const root = ensureRoot();
    const card = snapshot?.project_active;

    // v1.3.0 persistent workspace policy:
    // Project Active remains available across Home / Conversation / modules.
    // Foreground productivity/personal-result panels cause relocation, not disappearance.
    if (!isDocked(root)) {
      placeProjectCardV130(root);
    }

    if (!card || card.visible !== true) {
      root.classList.remove("is-visible");
      root.innerHTML = "";
      return;
    }

    const rawProgress = card.progress_percent;
    const hasProgress =
      rawProgress !== null &&
      rawProgress !== undefined &&
      String(rawProgress).trim() !== "" &&
      Number.isFinite(Number(rawProgress));
    const progress = hasProgress
      ? Math.max(0, Math.min(100, Number(rawProgress)))
      : 0;
    const progressScaleV25D2 = hasProgress ? (progress / 100) : 0;
    const rawProgressLabel = String(card.progress_label || "").trim();
    const progressLabel = hasProgress ? (rawProgressLabel || `${progress}%`) : "—";
    const formatRoadmapDateV25D = (value) => {
      const raw = String(value || "").trim();
      const m = raw.match(/^(\d{4})-(\d{2})-(\d{2})/);
      return m ? `${m[3]}/${m[2]}/${m[1]}` : (raw || "—");
    };
    const forecastFinishV25D = formatRoadmapDateV25D(card.forecast_finish);
    const baselineFinishV25D = formatRoadmapDateV25D(card.baseline_finish);
    const scheduleDaysV25D = Number(card.schedule_variance_days);
    const scheduleLabelV25D = String(card.schedule_label || (
      Number.isFinite(scheduleDaysV25D)
        ? (scheduleDaysV25D > 0
            ? `${scheduleDaysV25D} JOURS D'AVANCE`
            : (scheduleDaysV25D < 0
                ? `${Math.abs(scheduleDaysV25D)} JOURS DE RETARD`
                : "DANS LES TEMPS"))
        : "—"
    ));
    const confidenceV25D = Number(card.confidence_percent);
    const confidenceLabelV25D = Number.isFinite(confidenceV25D)
      ? `${Math.round(confidenceV25D)}%`
      : "—";
    const artifactCount = Number(card.artifact_count || 0);
    const artifactText = artifactCount === 1 ? "1 artefact lié" : `${artifactCount} artefacts liés`;

    root.innerHTML = `
      <div class="aura-project-active-v130__head">
        <div>
          <div class="aura-project-active-v130__eyebrow">PROJET ACTIF</div>
          <div class="aura-project-active-v130__title">${esc(card.project_name || "Projet")}</div>
        </div>
        <span class="aura-project-active-v130__status"><i></i>${esc((card.status || "active").toUpperCase())}</span>
      </div>
      <div class="aura-project-active-v130__progress">
        <div class="aura-project-active-v130__progress-row">
          <span>PROGRESSION</span><strong>${progressLabel}</strong>
        </div>
        <progress
          class="aura-project-active-v130__native-progress-v25d8"
          max="100"
          value="${progress}"
          aria-label="Progression ${progressLabel}">${progressLabel}</progress>
      </div>
      <div class="aura-project-active-v130__section">
        <span>FIN ESTIMÉE</span>
        <strong>${esc(forecastFinishV25D)} · CIBLE ${esc(baselineFinishV25D)}</strong>
      </div>
      <div class="aura-project-active-v130__section is-next">
        <span>PLANNING</span>
        <strong>${esc(scheduleLabelV25D)} · CONFIANCE ${esc(confidenceLabelV25D)}</strong>
      </div>
      <div class="aura-project-active-v130__section">
        <span>DERNIÈRE ACTION</span>
        <strong>${esc(card.last_action || "Aucune action enregistrée")}</strong>
      </div>
      <div class="aura-project-active-v130__section is-next">
        <span>PROCHAINE ACTION</span>
        <strong>${esc(card.next_action || "Aucune prochaine action définie")}</strong>
      </div>
      <div class="aura-project-active-v130__footer">
        <span>${esc(artifactText)}</span>
        <span>${esc((card.tags || []).slice(0, 3).join(" · "))}</span>
      </div>
    `;
    root.classList.add("is-visible");
  }

  async function refresh() {
    try {
      const response = await fetch(`${JSON_URL}?t=${Date.now()}`, {
        cache: "no-store",
        credentials: "same-origin"
      });
      if (!response.ok) return;
      render(await response.json());
    } catch (_) {}
  }

  function boot() {
    const root = ensureRoot();
    if (!isDocked(root)) {
      initDrag(root);
    }
    refresh();
    window.setInterval(refresh, REFRESH_MS);
    window.addEventListener("focus", refresh);
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) refresh();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
// AURA ROADMAP V25-D — schedule-aware Project Active live binding
// AURA ROADMAP V25-D.1 R6 R1 — SEMANTIC SVG PROGRESS BAR
// AURA ROADMAP V25-D.1 R7 — INLINE GRADIENT PROGRESS
// AURA ROADMAP V25-D.1 R8 — NATIVE HTML PROGRESS
