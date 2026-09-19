(() => {
  "use strict";

  const MARKER = "AURA_A200_R17_SUPERVISED_UI_PRESENTATION_V1";
  const PROTOCOL = "aura.ui-supervised-bridge.v1";
  const REQUEST_EVENT = "aura:a200-supervised-request";
  const RESPONSE_EVENT = "aura:a200-supervised-response";
  const ROOT_ID = "aura-a200-supervised-root";

  const ALLOWED = new Set([
    "runtime.status",
    "approval.confirm",
    "mission.cancel"
  ]);

  const state = {
    sessionId: null,
    lastStatus: null,
    activeApproval: null,
    lastError: null
  };

  function requestId(prefix) {
    const rand = Math.random().toString(16).slice(2);
    return `${prefix}-${Date.now()}-${rand}`;
  }

  function text(value) {
    return value === null || value === undefined ? "" : String(value);
  }

  function emit(type, payload = {}, requireSession = false) {
    if (!ALLOWED.has(type)) {
      throw new Error(`R17 UI command not allowed: ${type}`);
    }
    if (requireSession && !state.sessionId) {
      throw new Error("Runtime session unavailable");
    }

    const detail = {
      protocol: PROTOCOL,
      request_id: requestId("r17-ui"),
      type,
      payload: { ...payload }
    };
    if (state.sessionId) {
      detail.session_id = state.sessionId;
    }

    window.dispatchEvent(new CustomEvent(REQUEST_EVENT, { detail }));
    return detail.request_id;
  }

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (root) return root;

    root = document.createElement("section");
    root.id = ROOT_ID;
    root.dataset.auraA200Marker = MARKER;
    root.setAttribute("aria-live", "polite");
    root.innerHTML = `
      <button
        type="button"
        class="aura-a200-status"
        data-aura-a200-status
        aria-label="État de la supervision AURA"
        title="État de la supervision AURA"
      >
        <span class="aura-a200-dot" aria-hidden="true"></span>
        <span data-aura-a200-status-text>Supervision : connexion…</span>
      </button>

      <div
        class="aura-a200-approval"
        data-aura-a200-approval
        role="dialog"
        aria-modal="true"
        aria-labelledby="aura-a200-approval-title"
        hidden
      >
        <div class="aura-a200-card">
          <div class="aura-a200-eyebrow">AURA · Action supervisée</div>
          <h2 id="aura-a200-approval-title">Autorisation requise</h2>
          <p class="aura-a200-copy" data-aura-a200-copy></p>

          <dl class="aura-a200-meta">
            <div>
              <dt>Action</dt>
              <dd data-aura-a200-action>—</dd>
            </div>
            <div>
              <dt>Cible</dt>
              <dd data-aura-a200-target>—</dd>
            </div>
            <div>
              <dt>Sécurité</dt>
              <dd>Réversible · confirmation explicite</dd>
            </div>
          </dl>

          <div class="aura-a200-actions">
            <button type="button" class="secondary" data-aura-a200-cancel>Annuler</button>
            <button type="button" class="primary" data-aura-a200-approve>Autoriser</button>
          </div>

          <p class="aura-a200-error" data-aura-a200-error hidden></p>
        </div>
      </div>
    `;
    document.body.appendChild(root);

    root.querySelector("[data-aura-a200-status]").addEventListener("click", () => {
      try {
        emit("runtime.status");
      } catch (error) {
        setError(error);
      }
    });

    root.querySelector("[data-aura-a200-approve]").addEventListener("click", () => {
      const approval = state.activeApproval;
      if (!approval) return;
      try {
        emit(
          "approval.confirm",
          {
            approval_id: approval.approval_id,
            presentation_digest: approval.presentation_digest,
            confirm: true
          },
          true
        );
        setApprovalBusy(true, "Autorisation en cours…");
      } catch (error) {
        setError(error);
      }
    });

    root.querySelector("[data-aura-a200-cancel]").addEventListener("click", () => {
      const approval = state.activeApproval;
      if (!approval || !approval.mission_id) return;
      try {
        emit(
          "mission.cancel",
          {
            mission_id: approval.mission_id,
            confirm_cancel: true
          },
          true
        );
        setApprovalBusy(true, "Annulation en cours…");
      } catch (error) {
        setError(error);
      }
    });

    return root;
  }

  function setStatus(mode, label) {
    const root = ensureRoot();
    const button = root.querySelector("[data-aura-a200-status]");
    const labelNode = root.querySelector("[data-aura-a200-status-text]");
    button.dataset.mode = mode;
    labelNode.textContent = label;
  }

  function setError(error) {
    state.lastError = error instanceof Error ? error.message : text(error);
    const root = ensureRoot();
    const node = root.querySelector("[data-aura-a200-error]");
    node.textContent = state.lastError;
    node.hidden = false;
    setStatus("blocked", "Supervision : bloquée");
  }

  function clearError() {
    state.lastError = null;
    const root = ensureRoot();
    const node = root.querySelector("[data-aura-a200-error]");
    node.textContent = "";
    node.hidden = true;
  }

  function setApprovalBusy(busy, label = "") {
    const root = ensureRoot();
    const approve = root.querySelector("[data-aura-a200-approve]");
    const cancel = root.querySelector("[data-aura-a200-cancel]");
    approve.disabled = !!busy;
    cancel.disabled = !!busy;
    if (busy && label) {
      root.querySelector("[data-aura-a200-copy]").textContent = label;
    }
  }

  function hideApproval() {
    const root = ensureRoot();
    root.querySelector("[data-aura-a200-approval]").hidden = true;
    state.activeApproval = null;
    setApprovalBusy(false);
    clearError();
  }

  function presentApproval(approval) {
    if (!approval || typeof approval !== "object") {
      throw new Error("Invalid approval presentation");
    }

    for (const key of ["approval_id", "mission_id", "presentation_digest", "action"]) {
      if (!text(approval[key]).trim()) {
        throw new Error(`Approval presentation missing ${key}`);
      }
    }

    if (text(approval.presentation_digest).length !== 64) {
      throw new Error("Invalid presentation digest");
    }
    if (approval.requires_explicit_confirmation !== true) {
      throw new Error("Approval presentation is not explicitly confirmable");
    }
    if (approval.reversible !== true) {
      throw new Error("R17 refuses non-reversible approval presentation");
    }

    state.activeApproval = { ...approval };
    const root = ensureRoot();
    const dialog = root.querySelector("[data-aura-a200-approval]");
    root.querySelector("[data-aura-a200-action]").textContent = text(approval.action);
    root.querySelector("[data-aura-a200-target]").textContent =
      text(approval.target_title).trim() || "Fenêtre ciblée";
    root.querySelector("[data-aura-a200-copy]").textContent =
      "AURA demande votre accord avant d’exécuter cette action sur Windows.";
    setApprovalBusy(!state.sessionId);
    clearError();
    dialog.hidden = false;
  }

  function ingest(envelope) {
    if (!envelope || typeof envelope !== "object") return false;
    if (envelope.protocol !== PROTOCOL) return false;

    if (text(envelope.session_id).trim()) {
      state.sessionId = text(envelope.session_id).trim();
    }

    const kind = text(envelope.kind);
    const payload =
      envelope.payload && typeof envelope.payload === "object"
        ? envelope.payload
        : {};

    if (kind === "runtime.status") {
      state.lastStatus = { ...payload };
      if (payload.startup_failures && payload.startup_failures.length) {
        setStatus("blocked", "Supervision : erreur de démarrage");
      } else if (payload.mutation_ready === false) {
        setStatus("waiting", "Supervision : validation requise");
      } else {
        setStatus("ready", "Supervision : prête");
      }

      const pending = Array.isArray(payload.pending_approvals)
        ? payload.pending_approvals
        : [];
      if (pending.length === 1) {
        presentApproval(pending[0]);
      } else if (pending.length === 0 && !state.activeApproval) {
        hideApproval();
      }
      return true;
    }

    if (kind === "approval.required") {
      presentApproval(payload.approval || payload);
      setStatus("waiting", "Supervision : autorisation requise");
      return true;
    }

    if (kind === "approval.completed") {
      hideApproval();
      setStatus("ready", "Supervision : action terminée");
      emit("runtime.status");
      return true;
    }

    if (kind === "mission.cancelled" || kind === "mission.terminal") {
      hideApproval();
      setStatus("ready", "Supervision : mission annulée");
      emit("runtime.status");
      return true;
    }

    if (envelope.ok === false) {
      setError(payload.error || "Erreur de supervision");
      return true;
    }

    return false;
  }

  window.addEventListener(RESPONSE_EVENT, (event) => {
    try {
      ingest(event.detail);
    } catch (error) {
      setError(error);
    }
  });

  function boot() {
    ensureRoot();
    setStatus("offline", "Supervision : connexion…");
    try {
      emit("runtime.status");
    } catch (error) {
      setError(error);
    }
  }

  window.AURA_A200_SUPERVISED_UI = Object.freeze({
    marker: MARKER,
    protocol: PROTOCOL,
    requestEvent: REQUEST_EVENT,
    responseEvent: RESPONSE_EVENT,
    ingest,
    requestStatus: () => emit("runtime.status")
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
