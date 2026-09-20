export function createNeuralOrb() {
  const root = document.createElement("div");
  root.className = "aura-v2-orb";
  root.setAttribute("role", "img");
  root.setAttribute("aria-label", "État neuronal AURA");

  root.innerHTML = `
    <div class="aura-v2-orb__halo"></div>
    <div class="aura-v2-orb__ring aura-v2-orb__ring--outer"></div>
    <div class="aura-v2-orb__ring aura-v2-orb__ring--inner"></div>
    <div class="aura-v2-orb__core"></div>
  `;

  return Object.freeze({
    element: root,
    setState(state) {
      const value = String(state || "IDLE").toUpperCase();
      root.dataset.state = value;
      root.setAttribute("aria-label", `État neuronal AURA : ${value}`);
    },
  });
}
