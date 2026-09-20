const NAV_ITEMS = Object.freeze([
  ["home", "Accueil", "01"],
  ["talk", "Conversation", "02"],
  ["activity", "Activité", "03"],
  ["apps", "Apps", "04"],
]);

export function createPrimaryNav({ onWorkspace } = {}) {
  const element = document.createElement("aside");
  element.className = "aura-v2-rail aura-v2-glass";

  const nav = document.createElement("nav");
  nav.className = "aura-v2-rail__nav";
  nav.setAttribute("aria-label", "Navigation principale");

  for (const [workspace, label, code] of NAV_ITEMS) {
    const button = document.createElement("button");
    button.type = "button";
    button.dataset.workspace = workspace;
    button.innerHTML = `
      <span class="aura-v2-rail__icon" aria-hidden="true">${code}</span>
      <b>${label}</b>
      <i></i>
    `;
    button.addEventListener("click", () => onWorkspace?.(workspace));
    nav.append(button);
  }

  const lower = document.createElement("div");
  lower.className = "aura-v2-rail__lower";
  lower.innerHTML = `
    <button class="aura-v2-profile" type="button" disabled>
      <span aria-hidden="true">A</span>
      <span><small>PROFIL</small><b>Utilisateur local</b></span>
      <em>●</em>
    </button>
    <div class="aura-v2-core-card">
      <span class="aura-v2-core-card__orb" aria-hidden="true"></span>
      <span><b>AURA CORE</b><small>Runtime protégé</small><strong>ONLINE</strong></span>
    </div>
  `;

  element.append(nav, lower);

  return Object.freeze({
    element,
    render(snapshot) {
      for (const button of nav.querySelectorAll("button[data-workspace]")) {
        const active = button.dataset.workspace === snapshot.workspace;
        button.classList.toggle("active", active);
        if (active) {
          button.setAttribute("aria-current", "page");
        } else {
          button.removeAttribute("aria-current");
        }
      }
    },
  });
}
