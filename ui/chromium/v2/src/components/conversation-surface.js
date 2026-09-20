export function createConversationSurface() {
  const element = document.createElement("section");
  element.className = "aura-v2-conversation aura-v2-glass";
  element.setAttribute("aria-label", "Conversation");
  element.innerHTML = `
    <header>
      <div>
        <span>CONVERSATION</span>
        <small data-role="status">Lien local non connecté</small>
      </div>
      <button type="button" aria-label="Fermer la conversation" disabled>×</button>
    </header>
    <div class="aura-v2-messages">
      <article class="aura-v2-message aura">
        <span>AURA</span>
        <p>La surface V2 est prête pour la migration du contrat conversationnel. Le runtime de production reste RC4.2.</p>
      </article>
    </div>
  `;

  return Object.freeze({
    element,
    render(snapshot) {
      element.dataset.state = snapshot.state;
      element.querySelector('[data-role="status"]').textContent =
        snapshot.workspace === "talk" ? "Prévisualisation Conversation V2" : "Surface contextuelle";
      element.classList.toggle("is-primary", snapshot.workspace === "talk");
    },
  });
}
