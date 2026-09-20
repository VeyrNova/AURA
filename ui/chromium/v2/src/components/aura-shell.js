import { createNeuralOrb } from "./neural-orb.js";
import { createTopBar } from "./top-bar.js";
import { createPrimaryNav } from "./primary-nav.js";
import { createTelemetryPanel } from "./telemetry-panel.js";
import { createConversationSurface } from "./conversation-surface.js";
import { createComposer } from "./composer.js";

export function createAuraShell({ onWorkspace } = {}) {
  const element = document.createElement("div");
  element.className = "aura-v2-shell";
  element.dataset.mode = "normal";

  const topBar = createTopBar();
  const primaryNav = createPrimaryNav({ onWorkspace });
  const telemetry = createTelemetryPanel();
  const conversation = createConversationSurface();
  const composer = createComposer();
  const neuralOrb = createNeuralOrb();

  const workspace = document.createElement("main");
  workspace.className = "aura-v2-workspace";
  workspace.innerHTML = `
    <section class="aura-v2-hero">
      <div class="aura-v2-scanlines" aria-hidden="true"></div>
      <div class="aura-v2-core-label">
        <span>NEURAL CORE</span>
        <strong data-role="core-state">IDLE</strong>
        <small>UI V2 shell parity preview</small>
      </div>
      <div class="aura-v2-orb-slot" data-role="orb"></div>
      <div class="aura-v2-stage-copy">
        <p data-role="activity">AURA prête</p>
        <h1 data-role="headline">Comment puis-je t'aider ?</h1>
      </div>
    </section>
  `;

  workspace.querySelector('[data-role="orb"]').append(neuralOrb.element);
  workspace.append(telemetry.element, conversation.element, composer.element);
  element.append(topBar.element, primaryNav.element, workspace);

  return Object.freeze({
    element,
    render(snapshot) {
      element.dataset.mode = snapshot.mode;
      element.dataset.state = snapshot.state;
      element.dataset.workspace = snapshot.workspace;

      topBar.render(snapshot);
      primaryNav.render(snapshot);
      telemetry.render(snapshot);
      conversation.render(snapshot);
      composer.render(snapshot);
      neuralOrb.setState(snapshot.state);

      workspace.querySelector('[data-role="core-state"]').textContent = snapshot.state;
      workspace.querySelector('[data-role="activity"]').textContent = snapshot.activity;
      workspace.querySelector('[data-role="headline"]').textContent =
        snapshot.workspace === "talk" ? "Conversation avec AURA" : "Comment puis-je t'aider ?";
    },
  });
}
