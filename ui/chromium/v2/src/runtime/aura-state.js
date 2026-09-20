export const AURA_UI_STATES = Object.freeze([
  "STARTUP",
  "IDLE",
  "LISTENING",
  "TRANSCRIBING",
  "THINKING",
  "SEARCHING",
  "ANALYZING",
  "ACTING",
  "WAITING_APPROVAL",
  "SPEAKING",
  "PAUSED",
  "SUCCESS",
  "WARNING",
  "ERROR",
  "OFFLINE",
]);

const STATE_SET = new Set(AURA_UI_STATES);

function normalizeState(value) {
  const next = String(value || "IDLE").trim().toUpperCase();
  return STATE_SET.has(next) ? next : "IDLE";
}

export function createAuraState(initial = {}) {
  let snapshot = Object.freeze({
    state: normalizeState(initial.state || "IDLE"),
    mode: initial.mode === "developer" ? "developer" : "normal",
    activity: String(initial.activity || "AURA prête"),
    runtime: String(initial.runtime || "Local"),
    voice: String(initial.voice || "Prête"),
  });

  const listeners = new Set();

  function publish(next) {
    snapshot = Object.freeze({ ...snapshot, ...next });
    for (const listener of listeners) {
      listener(snapshot);
    }
    return snapshot;
  }

  return Object.freeze({
    getSnapshot: () => snapshot,
    subscribe(listener) {
      if (typeof listener !== "function") {
        throw new TypeError("listener must be a function");
      }
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    setState(value, activity) {
      const next = { state: normalizeState(value) };
      if (activity !== undefined) {
        next.activity = String(activity);
      }
      return publish(next);
    },
    setMode(mode) {
      return publish({ mode: mode === "developer" ? "developer" : "normal" });
    },
    update(patch = {}) {
      const next = { ...patch };
      if ("state" in next) {
        next.state = normalizeState(next.state);
      }
      if ("mode" in next) {
        next.mode = next.mode === "developer" ? "developer" : "normal";
      }
      return publish(next);
    },
  });
}
