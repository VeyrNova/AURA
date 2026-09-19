(() => {
  "use strict";
  if (window.__AURA_V2_LIVE_DIST_UI_R5__) return;
  window.__AURA_V2_LIVE_DIST_UI_R5__ = true;

  const norm = v => String(v || "").replace(/\s+/g, " ").trim();

  const visible = e => {
    if (!(e instanceof Element)) return false;
    const s = getComputedStyle(e);
    const r = e.getBoundingClientRect();
    return s.display !== "none" &&
           s.visibility !== "hidden" &&
           s.opacity !== "0" &&
           r.width > 0 &&
           r.height > 0;
  };

  function realApprovalPending() {
    const exact = [
      '[data-status="waiting_confirmation"]',
      '[data-state="waiting_confirmation"]',
      '[data-status="pending_approval"]',
      '[data-state="pending_approval"]'
    ];

    if (exact.some(sel => [...document.querySelectorAll(sel)].some(visible))) {
      return true;
    }

    const words =
      /(confirmer|confirmation|approuver|approbation|autoriser|autorisation|annuler|ex[eé]cuter)/i;

    return [...document.querySelectorAll('[role="dialog"],[aria-modal="true"]')]
      .some(e => visible(e) && words.test(norm(e.textContent)));
  }

  function syncBlockedBadge() {
    const pending = realApprovalPending();
    const wanted = /^supervision\s*:\s*bloqu[eé]e?$/i;

    const nodes = [...document.querySelectorAll(
      'button,[role="button"],[role="status"],div,span,p,label'
    )];

    for (const e of nodes) {
      if (!wanted.test(norm(e.textContent))) continue;
      if ([...e.children].some(c => wanted.test(norm(c.textContent)))) continue;

      const badge = e.closest(
        '[role="status"],[class*="badge" i],[class*="supervision" i],[class*="status" i]'
      ) || e;

      if (pending) {
        if (badge.dataset.auraV2R5Hidden === "1") {
          delete badge.dataset.auraV2R5Hidden;
          badge.removeAttribute("aria-hidden");
        }
      } else {
        badge.dataset.auraV2R5Hidden = "1";
        badge.setAttribute("aria-hidden", "true");
      }
    }
  }

  function purgeStrayPlanAura() {
    const wanted = /^plan\s+aura$/i;
    const nodes = [...document.querySelectorAll(
      'button,[role="button"],input[value],div,span,p,label'
    )];

    for (const e of nodes) {
      const text = e.matches("input[value]") ? norm(e.value) : norm(e.textContent);
      if (!wanted.test(text)) continue;
      if ([...e.children].some(c => wanted.test(norm(c.textContent)))) continue;

      const r = e.getBoundingClientRect();
      if (r.top < innerHeight * 0.65) continue;

      e.dataset.auraV2R5Hidden = "1";
      e.setAttribute("aria-hidden", "true");

      let p = e.parentElement;
      for (let i = 0; p && i < 4; i++, p = p.parentElement) {
        const pr = p.getBoundingClientRect();
        if (/^plan\s+aura$/i.test(norm(p.textContent)) && pr.height <= 140) {
          p.dataset.auraV2R5Hidden = "1";
          break;
        }
      }
    }
  }

  function repair() {
    purgeStrayPlanAura();
    syncBlockedBadge();
  }

  let queued = false;
  function schedule() {
    if (queued) return;
    queued = true;
    requestAnimationFrame(() => {
      queued = false;
      repair();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", repair, { once: true });
  } else {
    repair();
  }

  new MutationObserver(schedule).observe(document.documentElement, {
    childList: true,
    subtree: true,
    characterData: true,
    attributes: true,
    attributeFilter: ["class","style","hidden","data-state","data-status"]
  });

  window.addEventListener("aura:a200:approval", schedule);
  window.addEventListener("aura:a200:state", schedule);
  window.addEventListener("resize", schedule);

  console.info("[AURA] Live dist UI final fix R5 active");
})();