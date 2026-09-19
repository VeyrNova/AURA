(() => {
  "use strict";

  if (window.__AURA_V2_ATTACHMENT_R10__) return;
  window.__AURA_V2_ATTACHMENT_R10__ = true;

  const SELECTOR = ".workspace > .composer .attach, #composer .attach";

  const svg = `
    <svg class="aura-r10-paperclip"
         viewBox="0 0 24 24"
         aria-hidden="true"
         focusable="false">
      <path d="M8.7 12.3 15.6 5.4a4 4 0 1 1 5.7 5.7l-9.4 9.4a6 6 0 0 1-8.5-8.5l9.1-9.1a2.5 2.5 0 1 1 3.5 3.5l-9.1 9.1a1 1 0 1 1-1.4-1.4l8.4-8.4"/>
    </svg>`;

  function patchButton(btn) {
    if (!(btn instanceof Element)) return false;

    if (btn.dataset.auraR10Paperclip !== "1") {
      btn.dataset.auraR10Paperclip = "1";
      btn.setAttribute("title", "Pièce jointe");
      btn.setAttribute("aria-label", "Pièce jointe");
    }

    if (!btn.querySelector(":scope > .aura-r10-paperclip")) {
      btn.innerHTML = svg;
    }

    return true;
  }

  function apply() {
    let count = 0;
    for (const btn of document.querySelectorAll(SELECTOR)) {
      if (patchButton(btn)) count += 1;
    }
    return count;
  }

  function start() {
    apply();

    let attempts = 0;
    const timer = setInterval(() => {
      attempts += 1;
      const count = apply();
      if (count > 0 || attempts >= 60) clearInterval(timer);
    }, 250);
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      apply();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start, { once: true });
  } else {
    start();
  }

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true
  });

  window.addEventListener("resize", schedule);

  console.info("[AURA] Attachment exact-selector R10 active:", SELECTOR);
})();