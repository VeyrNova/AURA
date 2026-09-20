export function createTopBar() {
  const element = document.createElement("header");
  element.className = "aura-v2-topbar aura-v2-glass";
  element.innerHTML = `
    <div class="aura-v2-brand">
      <span class="aura-v2-brand__mark" aria-hidden="true"><i></i><b></b></span>
      <span class="aura-v2-brand__copy">
        <strong>AURA</strong>
        <small>NEURAL OPERATING INTERFACE</small>
      </span>
    </div>

    <div class="aura-v2-topbar__center" aria-label="État AURA">
      <span class="aura-v2-state-pill">
        <i data-role="state-dot"></i>
        <b data-role="state">IDLE</b>
      </span>
      <span class="aura-v2-route-pill" data-role="route">LOCAL RUNTIME</span>
    </div>

    <div class="aura-v2-topbar__actions">
      <span class="aura-v2-mini-chip" data-role="core">CORE · FOUNDATION</span>
      <span class="aura-v2-mini-chip" data-role="voice">VOICE · READY</span>
      <button class="aura-v2-power" type="button" aria-label="Fermer AURA" disabled>⏻</button>
    </div>
  `;

  return Object.freeze({
    element,
    render(snapshot) {
      element.dataset.state = snapshot.state;
      element.querySelector('[data-role="state"]').textContent = snapshot.state;
      element.querySelector('[data-role="route"]').textContent = snapshot.route;
      element.querySelector('[data-role="voice"]').textContent = `VOICE · ${snapshot.voice.toUpperCase()}`;
    },
  });
}
