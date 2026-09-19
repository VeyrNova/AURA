(() => {
  "use strict";

  const MARKER = "AURA_A200_R21_COMPOSER_SUPERVISED_PLAN_UI_V1";
  const INTENT_API = "AURA_A200_INTENT_HANDOFF";
  const REQUEST_EVENT = "aura:a200-supervised-request";
  const RESPONSE_EVENT = "aura:a200-supervised-response";
  const PLAN_BUTTON_ATTR = "data-aura-a200-r21-plan";
  const PANEL_ID = "aura-a200-r21-supervised-plan";

  const state = {
    sessionId: null,
    activeInput: null,
    activePreview: null,
    resolvedTarget: null,
    approvalPresentation: null,
    waiting: new Map()
  };

  const COMPOSER_SELECTORS = [
    "[data-aura-composer] textarea",
    "[data-aura-composer] input[type='text']",
    "[data-aura-composer] [contenteditable='true']",
    "[data-composer] textarea",
    "[data-composer] input[type='text']",
    ".aura-composer textarea",
    ".aura-composer input[type='text']",
    "[class*='composer'] textarea",
    "[class*='composer'] input[type='text']"
  ];

  function requestId(prefix) {
    return `${prefix}-${Date.now()}-${Math.random()
      .toString(16)
      .slice(2)}`;
  }

  function findComposerInput(root = document) {
    for (const selector of COMPOSER_SELECTORS) {
      const candidate = root.querySelector(selector);
      if (candidate) return candidate;
    }
    return null;
  }

  function readInputValue(input) {
    if (!input) return "";
    if (typeof input.value === "string") return input.value.trim();
    return String(input.textContent || "").trim();
  }

  function ensurePanel() {
    let panel = document.getElementById(PANEL_ID);
    if (panel) return panel;

    panel = document.createElement("section");
    panel.id = PANEL_ID;
    panel.hidden = true;
    panel.innerHTML = `
      <div data-r21-card>
        <div data-r21-eyebrow>AURA · Plan supervisé</div>
        <strong data-r21-title>Plan</strong>
        <div data-r21-risk></div>
        <ol data-r21-steps></ol>
        <div data-r21-target></div>
        <div data-r21-actions>
          <button type="button" data-r21-dismiss>Fermer</button>
          <button type="button" data-r21-prepare>
            Préparer l’approbation
          </button>
        </div>
        <div data-r21-result></div>
      </div>
    `;
    document.body.appendChild(panel);

    panel
      .querySelector("[data-r21-dismiss]")
      .addEventListener("click", () => {
        panel.hidden = true;
      });

    panel
      .querySelector("[data-r21-prepare]")
      .addEventListener("click", () => {
        void prepareSupervisedMutation().catch((error) => {
          setResult(
            error instanceof Error
              ? error.message
              : String(error)
          );
        });
      });

    return panel;
  }

  function setResult(value) {
    ensurePanel()
      .querySelector("[data-r21-result]")
      .textContent = String(value || "");
  }

  function renderPreview(preview) {
    state.activePreview = preview;
    const panel = ensurePanel();
    panel.hidden = false;
    panel.querySelector("[data-r21-title]").textContent =
      preview.title || preview.intent_kind || "Plan";
    panel.querySelector("[data-r21-risk]").textContent =
      `Risque : ${preview.risk || "unknown"}`;

    const steps = panel.querySelector("[data-r21-steps]");
    steps.textContent = "";
    for (const step of preview.steps || []) {
      const li = document.createElement("li");
      li.textContent = String(step);
      steps.appendChild(li);
    }

    panel.querySelector("[data-r21-target]").textContent = "";
    const prepare = panel.querySelector("[data-r21-prepare]");
    prepare.hidden = !(
      preview.intent_kind === "supervised_mutation" &&
      preview.requires_supervised_path === true &&
      preview.execution_allowed === false
    );

    setResult(
      preview.intent_kind === "supervised_mutation"
        ? "Plan supervisé prêt. Aucune mutation n’a eu lieu."
        : "Aperçu généré."
    );
  }

  function attachPlanButton(input) {
    if (!input || !input.parentElement) return false;
    state.activeInput = input;

    const parent = input.parentElement;
    if (
      parent.querySelector &&
      parent.querySelector(`[${PLAN_BUTTON_ATTR}]`)
    ) {
      return true;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.setAttribute(PLAN_BUTTON_ATTR, "");
    button.textContent = "Plan AURA";
    button.addEventListener("click", () => {
      const text = readInputValue(input);
      if (!text) {
        setResult("Le composer est vide.");
        return;
      }
      void planText(text).catch((error) => {
        setResult(
          error instanceof Error
            ? error.message
            : String(error)
        );
      });
    });
    parent.appendChild(button);
    return true;
  }

  function bindComposer(root = document) {
    const input = findComposerInput(root);
    if (!input) return false;
    return attachPlanButton(input);
  }

  async function planText(text) {
    const api = window[INTENT_API];
    if (
      !api ||
      typeof api.preview !== "function"
    ) {
      throw new Error("R20 intent preview API unavailable");
    }

    const preview = await api.preview(String(text || ""));
    renderPreview(preview);
    return preview;
  }

  function extractExactTarget(value) {
    const seen = new Set();

    function visit(node) {
      if (!node || typeof node !== "object") return null;
      if (seen.has(node)) return null;
      seen.add(node);

      if (
        Number.isInteger(node.hwnd) &&
        node.hwnd > 0 &&
        typeof node.title === "string" &&
        node.title.trim()
      ) {
        return {
          hwnd: node.hwnd,
          title: node.title
        };
      }

      for (const child of Object.values(node)) {
        const found = visit(child);
        if (found) return found;
      }
      return null;
    }

    return visit(value);
  }

  function sendStructured(type, payload = {}, options = {}) {
    const request_id = requestId("r21");
    const detail = {
      protocol: "aura.ui-supervised-bridge.v1",
      request_id,
      type,
      payload
    };
    if (options.session !== false) {
      if (!state.sessionId) {
        return Promise.reject(
          new Error("Runtime session unavailable")
        );
      }
      detail.session_id = state.sessionId;
    }

    const promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        state.waiting.delete(request_id);
        reject(new Error(`timeout waiting for ${type}`));
      }, 7000);
      state.waiting.set(request_id, {
        resolve,
        reject,
        timer,
        type
      });
    });

    window.dispatchEvent(
      new CustomEvent(REQUEST_EVENT, { detail })
    );
    return promise;
  }

  async function prepareSupervisedMutation() {
    const preview = state.activePreview;
    if (!preview) {
      throw new Error("No active R21 preview");
    }
    if (
      preview.intent_kind !== "supervised_mutation" ||
      preview.execution_allowed !== false ||
      preview.requires_supervised_path !== true
    ) {
      throw new Error("Active preview is not a supervised mutation");
    }

    // R21 currently permits only the reversible minimize preview.
    const normalized = String(
      preview.normalized_text || ""
    );
    if (
      !normalized.includes("minimise") &&
      !normalized.includes("minimize")
    ) {
      throw new Error(
        "R21 gate permits only minimize-window preparation"
      );
    }

    const readResponse = await sendStructured(
      "pc.read_foreground",
      {}
    );
    if (readResponse.ok !== true) {
      throw new Error("Target resolution failed");
    }

    const target = extractExactTarget(readResponse);
    if (!target) {
      throw new Error(
        "Exact foreground HWND/title not present in read response"
      );
    }
    state.resolvedTarget = target;

    ensurePanel()
      .querySelector("[data-r21-target]")
      .textContent = `${target.title} · HWND ${target.hwnd}`;

    const prepareResponse = await sendStructured(
      "pc.prepare_minimize_window",
      {
        hwnd: target.hwnd,
        title: target.title,
        r21_plan_digest: preview.plan_digest
      }
    );

    if (
      prepareResponse.kind !== "approval.required" ||
      prepareResponse.ok !== true
    ) {
      throw new Error(
        "R15 prepare response did not return approval.required"
      );
    }

    const preparePayload = prepareResponse.payload || {};
    if (preparePayload.phase !== "waiting_confirmation") {
      throw new Error(
        "R15 prepare response did not reach waiting_confirmation"
      );
    }

    // Certified R15 contract:
    // BridgeResponse(kind="approval.required", payload={"approval": {...}})
    const presentation = preparePayload.approval || null;

    if (!presentation) {
      throw new Error("Approval presentation missing at payload.approval");
    }
    if (
      presentation.reversible !== true ||
      presentation.requires_explicit_confirmation !== true
    ) {
      throw new Error(
        "Approval presentation safety contract invalid"
      );
    }
    if (
      presentation.target_hwnd !== target.hwnd ||
      presentation.target_title !== target.title
    ) {
      throw new Error(
        "Approval presentation target does not match resolved foreground"
      );
    }
    if (
      typeof presentation.presentation_digest !== "string" ||
      presentation.presentation_digest.length !== 64 ||
      typeof presentation.challenge_digest !== "string" ||
      presentation.challenge_digest.length !== 64
    ) {
      throw new Error("Approval presentation digests invalid");
    }

    state.approvalPresentation = presentation;
    setResult(
      "Approbation explicite requise. Aucune mutation n’a eu lieu."
    );
    return prepareResponse;
  }

  async function cancelPreparedMission() {
    const p = state.approvalPresentation;
    if (!p || !p.mission_id) {
      throw new Error("No prepared mission to cancel");
    }
    const response = await sendStructured(
      "mission.cancel",
      {
        mission_id: p.mission_id,
        confirm_cancel: true
      }
    );
    state.approvalPresentation = null;
    setResult("Mission supervisée annulée.");
    return response;
  }

  window.addEventListener(RESPONSE_EVENT, (event) => {
    const detail = event.detail || {};
    if (detail.session_id) {
      state.sessionId = String(detail.session_id);
    }

    const pending = state.waiting.get(detail.request_id);
    if (pending) {
      clearTimeout(pending.timer);
      state.waiting.delete(detail.request_id);
      pending.resolve(detail);
    }
  });

  function startBinding() {
    bindComposer(document);

    if (typeof MutationObserver === "function") {
      const observer = new MutationObserver(() => {
        if (!state.activeInput || !document.contains(state.activeInput)) {
          bindComposer(document);
        }
      });
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
      window.AURA_A200_R21_COMPOSER_OBSERVER = observer;
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener(
      "DOMContentLoaded",
      startBinding,
      { once: true }
    );
  } else {
    startBinding();
  }

  window.AURA_A200_COMPOSER_SUPERVISION = Object.freeze({
    marker: MARKER,
    selectors: [...COMPOSER_SELECTORS],
    bindComposer,
    planText,
    prepareSupervisedMutation,
    cancelPreparedMission,
    getActivePreview: () => state.activePreview,
    getResolvedTarget: () => state.resolvedTarget,
    getApprovalPresentation: () =>
      state.approvalPresentation
  });
})();
