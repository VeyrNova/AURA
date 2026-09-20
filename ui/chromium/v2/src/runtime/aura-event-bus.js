export function createAuraEventBus() {
  const topics = new Map();

  function bucket(topic) {
    const key = String(topic || "").trim();
    if (!key) {
      throw new Error("topic is required");
    }
    if (!topics.has(key)) {
      topics.set(key, new Set());
    }
    return topics.get(key);
  }

  return Object.freeze({
    on(topic, listener) {
      if (typeof listener !== "function") {
        throw new TypeError("listener must be a function");
      }
      const listeners = bucket(topic);
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    emit(topic, payload) {
      const listeners = topics.get(String(topic || "").trim());
      if (!listeners) return 0;
      for (const listener of listeners) {
        listener(payload);
      }
      return listeners.size;
    },
    clear(topic) {
      if (topic === undefined) {
        topics.clear();
        return;
      }
      topics.delete(String(topic));
    },
  });
}
