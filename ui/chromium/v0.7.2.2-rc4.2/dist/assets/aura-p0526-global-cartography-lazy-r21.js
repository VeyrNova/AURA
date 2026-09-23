/* AURA R21 - LAZY GLOBAL CARTOGRAPHY LOADER */
(() => {
  'use strict';

  if (window.__AURA_R21_GLOBAL_CARTO_LOADER__) return;

  const state = {
    status: window.AURA_P0526_GLOBAL_CARTO ? 'loaded' : 'idle',
    promise: null,
    observer: null
  };

  window.__AURA_R21_GLOBAL_CARTO_LOADER__ = state;

  const weatherVisible = () => {
    const root = document.getElementById('auraWeatherWorkspace');
    return !!(
      root?.classList?.contains('open') ||
      document.body?.classList?.contains('aura-weather-active')
    );
  };

  const load = () => {
    if (window.AURA_P0526_GLOBAL_CARTO) {
      state.status = 'loaded';
      return Promise.resolve(window.AURA_P0526_GLOBAL_CARTO);
    }

    if (state.promise) return state.promise;

    state.status = 'loading';

    state.promise = new Promise((resolve, reject) => {
      const existing = document.querySelector(
        'script[data-aura-r21-global-carto="1"]'
      );

      if (existing) {
        existing.addEventListener('load', () => {
          state.status = 'loaded';
          resolve(window.AURA_P0526_GLOBAL_CARTO || null);
        }, { once: true });

        existing.addEventListener('error', () => {
          state.status = 'error';
          state.promise = null;
          reject(new Error('aura_global_carto_load_failed'));
        }, { once: true });

        return;
      }

      const script = document.createElement('script');
      script.src = '/assets/aura-p0526-global-cartography.js?v=20260923-r21-lazy';
      script.async = true;
      script.dataset.auraR21GlobalCarto = '1';

      script.addEventListener('load', () => {
        state.status = 'loaded';
        state.observer?.disconnect();
        window.dispatchEvent(new CustomEvent('aura:global-cartography-ready'));
        resolve(window.AURA_P0526_GLOBAL_CARTO || null);
      }, { once: true });

      script.addEventListener('error', () => {
        state.status = 'error';
        state.promise = null;
        reject(new Error('aura_global_carto_load_failed'));
      }, { once: true });

      document.head.appendChild(script);
    });

    return state.promise;
  };

  const maybeLoad = () => {
    if (!weatherVisible()) return;
    load().catch(() => {});
  };

  window.AURA_R21_LOAD_GLOBAL_CARTOGRAPHY = load;

  const arm = () => {
    if (state.status === 'loaded') return;

    state.observer = new MutationObserver(maybeLoad);
    state.observer.observe(document.body, {
      attributes: true,
      attributeFilter: ['class'],
      childList: true,
      subtree: true
    });

    window.addEventListener('aura:workspace-changed', maybeLoad);
    window.addEventListener('aura:ui-ready', maybeLoad);
    maybeLoad();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', arm, { once: true });
  } else {
    arm();
  }
})();
