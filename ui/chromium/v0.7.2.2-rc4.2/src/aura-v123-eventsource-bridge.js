(() => {
  'use strict';
  if (window.__AURA_V123_EVENTSOURCE_BRIDGE__) return;

  const NativeEventSource = window.EventSource;
  if (typeof NativeEventSource !== 'function') return;

  function dispatchEnvelope(raw) {
    try {
      const msg = typeof raw === 'string' ? JSON.parse(raw) : raw;
      if (!msg || typeof msg !== 'object') return;
      window.dispatchEvent(new CustomEvent('aura:hub-event', { detail: msg }));
    } catch {}
  }

  function WrappedEventSource(url, config) {
    const es = new NativeEventSource(url, config);
    try {
      es.addEventListener('message', event => {
        dispatchEnvelope(event && event.data);
      });
    } catch {}
    return es;
  }

  WrappedEventSource.prototype = NativeEventSource.prototype;
  try { Object.setPrototypeOf(WrappedEventSource, NativeEventSource); } catch {}
  for (const key of ['CONNECTING', 'OPEN', 'CLOSED']) {
    try { WrappedEventSource[key] = NativeEventSource[key]; } catch {}
  }

  window.EventSource = WrappedEventSource;
  window.__AURA_V123_EVENTSOURCE_BRIDGE__ = {
    installed: true,
    native_preserved: true,
    duplicate_connection: false
  };
})();
