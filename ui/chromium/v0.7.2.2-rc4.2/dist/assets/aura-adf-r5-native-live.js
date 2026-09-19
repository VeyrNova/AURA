(() => {
  "use strict";

  const ROOT_ID = "aura-adf-live-native";
  const STATE_URL = "./aura_developer_fabric_live_state.json";
  const POS_KEY = "aura-adf-live-native-pos-v2";
  const POLL_MS = 350;
  let lastRunId = "";
  let dismissedRunId = "";
  let bootstrapped = false;
  let bootRunId = "";
  let timer = null;

  const esc = (value) => String(value == null ? "" : value);

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (root) return root;

    root = document.createElement("section");
    root.id = ROOT_ID;
    root.className = "aura-adf-live-native";
    root.setAttribute("aria-label", "AURA Developer Fabric Live");
    root.innerHTML = `
      <header class="aura-adf-live-native__head">
        <div class="aura-adf-live-native__identity">
          <span class="aura-adf-live-native__pulse" aria-hidden="true"></span>
          <div>
            <strong>AURA DEVELOPER FABRIC <i>· LIVE</i></strong>
            <small id="auraAdfLiveSubtitle">Coding Fabric local</small>
          </div>
        </div>
        <div class="aura-adf-live-native__actions">
          <button type="button" data-adf-copy title="Copier les logs">COPIER</button>
          <button type="button" data-adf-min title="Réduire">—</button>
          <button type="button" data-adf-close title="Fermer">×</button>
        </div>
      </header>

      <div class="aura-adf-live-native__pipeline" aria-label="Pipeline Developer Fabric">
        <span data-stage="sandbox"><i></i>SANDBOX</span>
        <b>›</b>
        <span data-stage="aider"><i></i>AIDER</span>
        <b>›</b>
        <span data-stage="afg"><i></i>AFG</span>
        <b>›</b>
        <span data-stage="harvest"><i></i>HARVEST</span>
        <b>›</b>
        <span data-stage="staging"><i></i>STAGING</span>
      </div>

      <div class="aura-adf-live-native__meta">
        <div><span>AGENT</span><b id="auraAdfLiveAgent">—</b></div>
        <div><span>MODEL</span><b id="auraAdfLiveModel">—</b></div>
        <div class="aura-adf-live-native__target"><span>TARGET</span><b id="auraAdfLiveTarget">—</b></div>
        <div><span>ELAPSED</span><b id="auraAdfLiveElapsed">0.0s</b></div>
      </div>

      <div class="aura-adf-live-native__terminal-wrap">
        <pre id="auraAdfLiveOutput" class="aura-adf-live-native__terminal">En attente d'une session Coding Fabric…</pre>
      </div>

      <footer class="aura-adf-live-native__foot">
        <div>
          <span class="aura-adf-live-native__shield">◆</span>
          <b id="auraAdfLiveSafety">SOURCE READ-ONLY · NO CANONICAL WRITE</b>
        </div>
        <strong id="auraAdfLiveStatus">IDLE</strong>
      </footer>
    `;
    document.body.appendChild(root);

    const output = root.querySelector("#auraAdfLiveOutput");
    const copy = root.querySelector("[data-adf-copy]");
    const min = root.querySelector("[data-adf-min]");
    const close = root.querySelector("[data-adf-close]");
    const head = root.querySelector(".aura-adf-live-native__head");

    copy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(output.textContent || "");
        copy.textContent = "COPIÉ";
        setTimeout(() => { copy.textContent = "COPIER"; }, 1200);
      } catch (_) {
        copy.textContent = "ERREUR";
        setTimeout(() => { copy.textContent = "COPIER"; }, 1200);
      }
    });

    min.addEventListener("click", () => {
      root.classList.toggle("is-minimized");
    });

    close.addEventListener("click", () => {
      dismissedRunId = lastRunId;
      root.classList.remove("is-visible");
    });

    initDrag(root, head);
    restorePosition(root);
    return root;
  }

  function restorePosition(root) {
    try {
      const raw = sessionStorage.getItem(POS_KEY);
      if (!raw) return;
      const pos = JSON.parse(raw);
      if (!pos || typeof pos.left !== "number" || typeof pos.top !== "number") return;
      const clamped = clamp(root, pos.left, pos.top);
      root.style.left = `${clamped.left}px`;
      root.style.top = `${clamped.top}px`;
      root.style.right = "auto";
    } catch (_) {}
  }

  function clamp(root, left, top) {
    const rect = root.getBoundingClientRect();
    const w = rect.width || 760;
    const h = Math.min(rect.height || 520, window.innerHeight - 32);
    const minVisible = 160;
    const minLeft = window.innerWidth <= 760 ? 12 : 214;
    const minTop = window.innerWidth <= 760 ? 64 : 80;
    return {
      left: Math.max(minLeft, Math.min(left, window.innerWidth - minVisible)),
      top: Math.max(minTop, Math.min(top, Math.max(minTop, window.innerHeight - Math.min(h, 86))))
    };
  }

  function initDrag(root, head) {
    let dragging = false;
    let pointerId = null;
    let startX = 0;
    let startY = 0;
    let startLeft = 0;
    let startTop = 0;
    let oldSelect = "";

    const interactive = "button,a,input,textarea,select,option,[role='button'],[contenteditable],[tabindex]";

    function finish(event) {
      if (!dragging) return;
      dragging = false;
      try {
        if (pointerId != null && head.hasPointerCapture(pointerId)) {
          head.releasePointerCapture(pointerId);
        }
      } catch (_) {}
      document.body.style.userSelect = oldSelect;
      const rect = root.getBoundingClientRect();
      try {
        sessionStorage.setItem(POS_KEY, JSON.stringify({ left: rect.left, top: rect.top }));
      } catch (_) {}
      pointerId = null;
    }

    head.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      if (event.target.closest(interactive)) return;
      const rect = root.getBoundingClientRect();
      dragging = true;
      pointerId = event.pointerId;
      startX = event.clientX;
      startY = event.clientY;
      startLeft = rect.left;
      startTop = rect.top;
      oldSelect = document.body.style.userSelect;
      document.body.style.userSelect = "none";
      try { head.setPointerCapture(pointerId); } catch (_) {}
    });

    head.addEventListener("pointermove", (event) => {
      if (!dragging || event.pointerId !== pointerId) return;
      const pos = clamp(
        root,
        startLeft + (event.clientX - startX),
        startTop + (event.clientY - startY)
      );
      root.style.left = `${pos.left}px`;
      root.style.top = `${pos.top}px`;
      root.style.right = "auto";
    });

    head.addEventListener("pointerup", finish);
    head.addEventListener("pointercancel", finish);
    head.addEventListener("lostpointercapture", finish);

    window.addEventListener("resize", () => {
      const rect = root.getBoundingClientRect();
      const pos = clamp(root, rect.left, rect.top);
      root.style.left = `${pos.left}px`;
      root.style.top = `${pos.top}px`;
      root.style.right = "auto";
    });
  }

  function stageRank(phase) {
    const p = String(phase || "").toLowerCase();
    if (p.includes("staging")) return 4;
    if (p.includes("harvest")) return 3;
    if (p.includes("afg") || p.includes("model")) return 2;
    if (p.includes("aider") || p.includes("generation")) return 1;
    return 0;
  }

  function renderStages(root, state) {
    const rank = stageRank(state.phase);
    const names = ["sandbox", "aider", "afg", "harvest", "staging"];
    names.forEach((name, index) => {
      const el = root.querySelector(`[data-stage="${name}"]`);
      if (!el) return;
      el.classList.toggle("is-done", index < rank);
      el.classList.toggle("is-active", index === rank && state.active);
      el.classList.toggle("is-failed", !state.active && state.status === "failed" && index === rank);
    });
  }

  function render(state) {
    const root = ensureRoot();
    const runId = esc(state.run_id);

    if (!bootstrapped) {
      if (runId) {
        bootRunId = runId;
        lastRunId = runId;
      }
      bootstrapped = true;
      root.classList.remove("is-visible");
    } else {
      const isNewRun = runId && runId !== lastRunId;

      if (isNewRun) {
        lastRunId = runId;
        dismissedRunId = "";
        root.classList.remove("is-minimized");
      }

      if (runId && runId !== dismissedRunId && runId !== bootRunId) {
        root.classList.add("is-visible");
      }
    }

    root.classList.toggle("is-running", !!state.active);
    root.classList.toggle("is-success", state.status === "edit_generated" || state.status === "complete");
    root.classList.toggle("is-error", state.status === "failed" || state.status === "token_limit");

    root.querySelector("#auraAdfLiveAgent").textContent = esc(state.agent || "aider");
    root.querySelector("#auraAdfLiveModel").textContent = esc(state.model || "—");
    root.querySelector("#auraAdfLiveTarget").textContent = esc(state.target || "—");
    root.querySelector("#auraAdfLiveElapsed").textContent =
      `${Number(state.elapsed_s || 0).toFixed(1)}s`;

    const subtitle = root.querySelector("#auraAdfLiveSubtitle");
    subtitle.textContent = esc(state.phase_label || state.phase || "Coding Fabric local");

    const status = root.querySelector("#auraAdfLiveStatus");
    status.textContent = esc(String(state.status || (state.active ? "RUNNING" : "IDLE")).toUpperCase());

    const safety = root.querySelector("#auraAdfLiveSafety");
    safety.textContent = state.canonical_write === true
      ? "CANONICAL WRITE ACTIVE"
      : "SOURCE READ-ONLY · NO CANONICAL WRITE";

    const output = root.querySelector("#auraAdfLiveOutput");
    const wrap = root.querySelector(".aura-adf-live-native__terminal-wrap");
    const nearBottom = wrap.scrollHeight - wrap.scrollTop - wrap.clientHeight < 90;
    const lines = Array.isArray(state.lines) ? state.lines : [];
    output.textContent = lines.length
      ? lines.join("\n")
      : "En attente de la sortie Aider…";
    if (nearBottom || state.active) wrap.scrollTop = wrap.scrollHeight;

    renderStages(root, state);
  }

  async function poll() {
    try {
      const response = await fetch(`${STATE_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (response.ok) {
        const state = await response.json();
        if (state && typeof state === "object") render(state);
      }
    } catch (_) {
      // UI telemetry is intentionally non-authoritative; no product behavior depends on it.
    } finally {
      timer = window.setTimeout(poll, POLL_MS);
    }
  }

  function boot() {
    ensureRoot();
    if (timer) clearTimeout(timer);
    poll();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }

  window.AURADeveloperFabricLive = Object.freeze({
    open() { ensureRoot().classList.add("is-visible"); },
    close() { ensureRoot().classList.remove("is-visible"); },
    refresh: poll
  });
})();
