(() => {
  "use strict";

  const MARKER = "AURA_A200_R18_LOOPBACK_TRANSPORT_CLIENT_V1";
  const PROTOCOL = "aura.ui-supervised-bridge.v1";
  const REQUEST_EVENT = "aura:a200-supervised-request";
  const RESPONSE_EVENT = "aura:a200-supervised-response";
  const ENDPOINT = "http://127.0.0.1:18765/aura/a200/bridge";
  const TOKEN = "5256bff879cde4a3d03c7de50140282260777d8ee152ad4a97ce25bc6969a4a4";

  function isEnvelope(value) {
    return !!value &&
      typeof value === "object" &&
      value.protocol === PROTOCOL &&
      typeof value.request_id === "string" &&
      typeof value.type === "string";
  }

  function emitResponse(detail) {
    window.dispatchEvent(
      new CustomEvent(RESPONSE_EVENT, { detail })
    );
  }

  async function dispatch(detail) {
    if (!isEnvelope(detail)) {
      return;
    }

    try {
      const response = await fetch(ENDPOINT, {
        method: "POST",
        mode: "cors",
        cache: "no-store",
        credentials: "omit",
        headers: {
          "Content-Type": "application/json",
          "X-AURA-A200-Transport-Token": TOKEN
        },
        body: JSON.stringify(detail)
      });

      const payload = await response.json().catch(() => ({
        protocol: PROTOCOL,
        request_id: detail.request_id,
        ok: false,
        error: "invalid_host_response"
      }));

      if (!response.ok && payload.ok !== false) {
        payload.ok = false;
      }
      if (!payload.protocol) {
        payload.protocol = PROTOCOL;
      }
      if (!payload.request_id) {
        payload.request_id = detail.request_id;
      }
      emitResponse(payload);
    } catch (error) {
      emitResponse({
        protocol: PROTOCOL,
        request_id: detail.request_id,
        ok: false,
        kind: "transport.error",
        payload: {
          error: "host_transport_unavailable",
          message: error instanceof Error ? error.message : String(error)
        }
      });
    }
  }

  window.addEventListener(REQUEST_EVENT, (event) => {
    void dispatch(event.detail);
  });

  window.AURA_A200_HOST_TRANSPORT = Object.freeze({
    marker: MARKER,
    protocol: PROTOCOL,
    endpoint: ENDPOINT
  });
})();
