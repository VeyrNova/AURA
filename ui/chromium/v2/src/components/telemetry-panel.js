export function createTelemetryPanel() {
  const element = document.createElement("aside");
  element.className = "aura-v2-telemetry aura-v2-glass";
  element.innerHTML = `
    <header class="aura-v2-panel-title">
      <span>SYSTEM LIVE</span>
      <i>UI V2 · DORMANT</i>
    </header>

    <div class="aura-v2-metric">
      <label>DISPLAY GPU</label>
      <strong>DETECTION...</strong>
      <small>Visual runtime</small>
    </div>

    <div class="aura-v2-metric">
      <label>COMPUTE GPU</label>
      <strong>POLICY CONTROLLED</strong>
      <small>Compute route isolated</small>
    </div>

    <div class="aura-v2-separator"></div>

    <div class="aura-v2-metric">
      <label>VOICE RUNTIME</label>
      <strong data-role="voice">READY</strong>
      <small>Explicit microphone control</small>
    </div>

    <div class="aura-v2-metric">
      <label>INTELLIGENCE</label>
      <strong data-role="provider">LOCAL / CLOUD</strong>
      <small data-role="route">LOCAL RUNTIME</small>
    </div>

    <div class="aura-v2-separator"></div>

    <div class="aura-v2-metric">
      <label>EVENT LINK</label>
      <strong>NOT CONNECTED</strong>
      <small>Foundation preview only</small>
    </div>

    <div class="aura-v2-pcm">
      <div><span>LIVE PCM</span><b>0.00</b></div>
      <span class="aura-v2-pcm__line" aria-hidden="true"></span>
    </div>

    <div class="aura-v2-privacy">
      <span aria-hidden="true">◆</span>
      <p><b>LOCAL CONTROL</b><br>La V2 reste dormante. Aucun contrôle OS direct n'est exposé par cette prévisualisation.</p>
    </div>
  `;

  return Object.freeze({
    element,
    render(snapshot) {
      element.querySelector('[data-role="voice"]').textContent = snapshot.voice.toUpperCase();
      element.querySelector('[data-role="provider"]').textContent = snapshot.provider.toUpperCase();
      element.querySelector('[data-role="route"]').textContent = snapshot.route;
    },
  });
}
