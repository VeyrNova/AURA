export function createComposer() {
  const element = document.createElement("footer");
  element.className = "aura-v2-composer aura-v2-glass";
  element.innerHTML = `
    <button class="aura-v2-composer__action" type="button" aria-label="Ajouter une pièce jointe" disabled>＋</button>
    <label class="aura-v2-composer__input">
      <span class="sr-only">Message</span>
      <textarea rows="1" placeholder="Écris à AURA…" disabled></textarea>
      <small data-role="hint">Fondation V2 dormante · interaction désactivée</small>
    </label>
    <button class="aura-v2-composer__action mic" type="button" aria-label="Maintenir pour parler" disabled>◉</button>
    <button class="aura-v2-composer__action send" type="button" aria-label="Envoyer" disabled>➤</button>
  `;

  return Object.freeze({
    element,
    render(snapshot) {
      const hint = element.querySelector('[data-role="hint"]');
      hint.textContent = snapshot.state === "WAITING_APPROVAL"
        ? "Confirmation utilisateur requise"
        : "Fondation V2 dormante · interaction désactivée";
    },
  });
}
