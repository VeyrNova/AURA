(() => {
  "use strict";

  const MARKER = "AURA_A200_R20_CONVERSATION_INTENT_PREVIEW_UI_V1";
  const PREVIEW_ENDPOINT =
    "http://127.0.0.1:18766/aura/a200/intent/preview";
  const TOKEN = "5256bff879cde4a3d03c7de50140282260777d8ee152ad4a97ce25bc6969a4a4";
  const INTENT_EVENT = "aura:a200-conversation-intent";
  const REQUEST_EVENT = "aura:a200-supervised-request";
  const RESPONSE_EVENT = "aura:a200-supervised-response";
  const ROOT_ID = "aura-a200-intent-preview-root";

  const READ_ONLY_TYPES = new Set([
    "runtime.status",
    "pc.read_foreground"
  ]);

  const state = {
    sessionId: null,
    activePreview: null,
    lastExecution: null
  };

  function id(prefix) {
    return `${prefix}-${Date.now()}-${
      Math.random().toString(16).slice(2)
    }`;
  }

  function ensureRoot() {
    let root = document.getElementById(ROOT_ID);
    if (root) return root;

    root = document.createElement("section");
    root.id = ROOT_ID;
    root.dataset.auraA200R20 = MARKER;
    root.hidden = true;
    root.innerHTML = `
      <div data-r20-card>
        <div data-r20-eyebrow>AURA · Plan d’intention</div>
        <strong data-r20-title></strong>
        <div data-r20-risk></div>
        <ol data-r20-steps></ol>
        <div>
          <button type="button" data-r20-dismiss>Fermer</button>
          <button type="button" data-r20-execute>
            Exécuter la lecture
          </button>
        </div>
        <div data-r20-result></div>
      </div>
    `;
    document.body.appendChild(root);

    root
      .querySelector("[data-r20-dismiss]")
      .addEventListener("click", () => {
        root.hidden = true;
      });

    root
      .querySelector("[data-r20-execute]")
      .addEventListener("click", () => {
        try {
          executeActiveReadOnly();
        } catch (error) {
          setResult(error instanceof Error
            ? error.message
            : String(error));
        }
      });

    return root;
  }

  function setResult(text) {
    ensureRoot()
      .querySelector("[data-r20-result]")
      .textContent = String(text || "");
  }

  function render(preview) {
    state.activePreview = preview;
    const root = ensureRoot();
    root.hidden = false;
    root.querySelector("[data-r20-title]").textContent =
      preview.title || preview.intent_kind || "Aperçu";
    root.querySelector("[data-r20-risk]").textContent =
      `Risque : ${preview.risk || "unknown"}`;

    const steps = root.querySelector("[data-r20-steps]");
    steps.textContent = "";
    for (const step of preview.steps || []) {
      const li = document.createElement("li");
      li.textContent = String(step);
      steps.appendChild(li);
    }

    const execute = root.querySelector("[data-r20-execute]");
    execute.hidden = !(
      preview.execution_allowed === true &&
      preview.requires_explicit_confirmation === true &&
      READ_ONLY_TYPES.has(preview.command_type)
    );

    setResult(
      preview.execution_allowed
        ? "Aperçu prêt — confirmation requise."
        : "Aucune exécution directe autorisée."
    );
  }

  async function preview(text) {
    const request = {
      schema: "aura.a200.intent-preview-request.v1",
      request_id: id("r20-preview"),
      text: String(text || "")
    };

    const body = JSON.stringify(request);
    const response = await fetch(PREVIEW_ENDPOINT, {
      method: "POST",
      mode: "cors",
      cache: "no-store",
      credentials: "omit",
      headers: {
        "Content-Type": "application/json",
        "X-AURA-A200-Transport-Token": TOKEN
      },
      body
    });

    const payload = await response.json();
    if (!response.ok || payload.ok !== true) {
      throw new Error(
        payload.message ||
        payload.error ||
        "intent preview failed"
      );
    }
    render(payload.preview);
    return payload.preview;
  }

  function executeActiveReadOnly() {
    const preview = state.activePreview;
    if (!preview) {
      throw new Error("No active plan preview");
    }
    if (preview.execution_allowed !== true) {
      throw new Error("Plan is not executable");
    }
    if (preview.requires_explicit_confirmation !== true) {
      throw new Error("Explicit confirmation missing");
    }
    if (!READ_ONLY_TYPES.has(preview.command_type)) {
      throw new Error("R20 permits read-only execution only");
    }
    if (
      typeof preview.plan_digest !== "string" ||
      preview.plan_digest.length !== 64
    ) {
      throw new Error("Invalid plan digest");
    }

    const detail = {
      protocol: "aura.ui-supervised-bridge.v1",
      request_id: id("r20-read"),
      type: preview.command_type,
      payload: {
        ...(preview.command_payload || {}),
        r20_plan_digest: preview.plan_digest
      }
    };
    if (
      preview.command_type !== "runtime.status" &&
      state.sessionId
    ) {
      detail.session_id = state.sessionId;
    }
    if (
      preview.command_type !== "runtime.status" &&
      !detail.session_id
    ) {
      throw new Error("Runtime session unavailable");
    }

    state.lastExecution = {
      request_id: detail.request_id,
      command_type: detail.type,
      plan_digest: preview.plan_digest,
      result: null
    };

    window.dispatchEvent(
      new CustomEvent(REQUEST_EVENT, { detail })
    );
    setResult("Lecture structurée envoyée.");
    return detail.request_id;
  }

  window.addEventListener(RESPONSE_EVENT, (event) => {
    const detail = event.detail || {};
    if (detail.session_id) {
      state.sessionId = String(detail.session_id);
    }
    if (
      state.lastExecution &&
      detail.request_id === state.lastExecution.request_id
    ) {
      state.lastExecution.result = detail;
      setResult(
        detail.ok === true
          ? "Lecture terminée."
          : "Lecture refusée."
      );
    }
  });

  window.addEventListener(INTENT_EVENT, (event) => {
    const detail = event.detail || {};
    void preview(detail.text).catch((error) => {
      setResult(
        error instanceof Error
          ? error.message
          : String(error)
      );
    });
  });

  window.AURA_A200_INTENT_HANDOFF = Object.freeze({
    marker: MARKER,
    preview,
    executeActiveReadOnly,
    getActivePreview: () => state.activePreview,
    getLastExecution: () => state.lastExecution
  });

  ensureRoot();
})();
