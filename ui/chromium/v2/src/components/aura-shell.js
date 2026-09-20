import { createNeuralOrb } from "./neural-orb.js";

export function createAuraShell() {
  const root = document.createElement("main");
  root.className = "aura-v2-shell";
  root.dataset.mode = "normal";

  root.innerHTML = `
    <header class="aura-v2-topbar">
      <div class="aura-v2-brand">
        <strong>AURA</strong>
        <span>PERSONAL INTELLIGENCE</span>
      </div>
      <div class="aura-v2-topbar__status">
        <span class="aura-v2-status-dot"></span>
        <span data-role="runtime">Local</span>
      </div>
    </header>

    <nav class="aura-v2-nav" aria-label="Navigation principale">
      <button type="button" data-workspace="home" aria-current="page">Accueil</button>
      <button type="button" data-workspace="activity">Activité</button>
      <button type="button" data-workspace="memory">Mémoire</button>
      <button type="button" data-workspace="apps">Apps</button>
    </nav>

    <section class="aura-v2-stage" aria-live="polite">
      <div class="aura-v2-orb-slot" data-role="orb"></div>
      <p class="aura-v2-activity" data-role="activity">AURA prête</p>
      <h1>Comment puis-je t'aider ?</h1>
    </section>

    <section class="aura-v2-conversation" aria-label="Conversation">
      <div class="aura-v2-empty">
        La migration V2 est encore dormante. Cette surface sert de fondation structurelle.
      </div>
    </section>

    <footer class="aura-v2-composer">
      <button type="button" aria-label="Ajouter une pièce jointe" disabled>+</button>
      <label>
        <span class="sr-only">Message</span>
        <textarea rows="1" placeholder="Écris à AURA…" disabled></textarea>
      </label>
      <button type="button" aria-label="Parler" disabled>●</button>
      <button type="button" aria-label="Envoyer" disabled>➤</button>
    </footer>

    <aside class="aura-v2-developer" data-role="developer" hidden>
      <strong>Developer Mode</strong>
      <dl>
        <div><dt>State</dt><dd data-role="debug-state">IDLE</dd></div>
        <div><dt>Runtime</dt><dd>Foundation / dormant</dd></div>
        <div><dt>Transport</dt><dd>Not connected</dd></div>
      </dl>
    </aside>
  `;

  const neuralOrb = createNeuralOrb();
  root.querySelector('[data-role="orb"]').append(neuralOrb.element);

  return Object.freeze({
    element: root,
    render(snapshot) {
      root.dataset.mode = snapshot.mode;
      root.dataset.state = snapshot.state;
      root.querySelector('[data-role="runtime"]').textContent = snapshot.runtime;
      root.querySelector('[data-role="activity"]').textContent = snapshot.activity;
      root.querySelector('[data-role="debug-state"]').textContent = snapshot.state;
      root.querySelector('[data-role="developer"]').hidden = snapshot.mode !== "developer";
      neuralOrb.setState(snapshot.state);
    },
  });
}
