(() => {
  const ID = "auraR5Identity";
  if (document.getElementById(ID)) return;

  const mount = () => {
    const hero = document.querySelector(".hero");
    if (!hero) return;

    const box = document.createElement("div");
    box.id = ID;
    box.className = "aura-r5-identity";
    box.setAttribute("aria-hidden", "true");
    box.innerHTML = `
      <span class="aura-r5-identity__name">AURA</span>
      <span class="aura-r5-identity__time">--:--</span>
      <span class="aura-r5-identity__date">--</span>
    `;
    hero.appendChild(box);

    const timeEl = box.querySelector(".aura-r5-identity__time");
    const dateEl = box.querySelector(".aura-r5-identity__date");

    const fmtDate = new Intl.DateTimeFormat("fr-FR", {
      weekday: "long",
      day: "2-digit",
      month: "long",
      year: "numeric",
    });

    const tick = () => {
      const now = new Date();
      timeEl.textContent =
        String(now.getHours()).padStart(2, "0") + ":" +
        String(now.getMinutes()).padStart(2, "0");
      dateEl.textContent = fmtDate.format(now).toUpperCase();
    };

    tick();
    setInterval(tick, 1000);
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount, { once: true });
  } else {
    mount();
  }
})();
