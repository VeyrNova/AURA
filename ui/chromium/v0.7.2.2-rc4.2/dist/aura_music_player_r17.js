
/* AURA_MUSIC_R17_EXPRESSIVE_PLAYER
   Original AURA implementation inspired by modern expressive player UX.
   No PixelPlayer source code or assets are copied.
*/
(() => {
  "use strict";
  if (window.__AURA_MUSIC_R17_EXPRESSIVE_PLAYER__) return;
  window.__AURA_MUSIC_R17_EXPRESSIVE_PLAYER__ = true;

  const ROOT_ID = "aura-music-player-v180";
  const MINI_ID = "aura-music-mini-r17";
  const q = (s, p = document) => p.querySelector(s);
  const qa = (s, p = document) => [...p.querySelectorAll(s)];
  const root = () => document.getElementById(ROOT_ID);

  function currentThemeIsLight() {
    const toggler = qa("button").find(b => /MODE\s+(SOMBRE|CLAIR)/i.test((b.textContent || "").trim()));
    if (toggler) return /MODE\s+SOMBRE/i.test((toggler.textContent || "").trim());
    const html = document.documentElement;
    const body = document.body;
    return html.dataset.theme === "light" ||
      html.classList.contains("light") ||
      body?.classList.contains("light") ||
      body?.dataset.theme === "light";
  }

  function setTheme() {
    const light = currentThemeIsLight();
    const r = root();
    const m = document.getElementById(MINI_ID);
    if (r) r.classList.toggle("r17-light", light);
    if (m) m.classList.toggle("r17-light", light);
  }

  function setAccent(rgb) {
    const [r, g, b] = rgb;
    const value = `${r},${g},${b}`;
    const player = root();
    const mini = document.getElementById(MINI_ID);
    if (player) player.style.setProperty("--r17-accent-rgb", value);
    if (mini) mini.style.setProperty("--r17-accent-rgb", value);
  }

  let lastArtwork = "";
  function updateArtworkAndAccent() {
    const player = root();
    const cover = document.getElementById("aura-music-cover-v180");
    if (!player || !cover) return;

    const bg = cover.style.backgroundImage || getComputedStyle(cover).backgroundImage || "";
    if (bg && bg !== "none") player.style.setProperty("--r17-art", bg);
    else player.style.setProperty("--r17-art", "none");

    if (!bg || bg === "none" || bg === lastArtwork) return;
    lastArtwork = bg;

    const match = bg.match(/^url\((['"]?)(.*?)\1\)$/);
    const src = match?.[2] || "";
    if (!src) {
      setAccent([76, 215, 235]);
      return;
    }

    const img = new Image();
    img.onload = () => {
      try {
        const c = document.createElement("canvas");
        c.width = c.height = 28;
        const ctx = c.getContext("2d", { willReadFrequently: true });
        ctx.drawImage(img, 0, 0, 28, 28);
        const data = ctx.getImageData(0, 0, 28, 28).data;
        let rr = 0, gg = 0, bb = 0, count = 0;
        for (let i = 0; i < data.length; i += 16) {
          const a = data[i + 3];
          if (a < 180) continue;
          const r = data[i], g = data[i + 1], b = data[i + 2];
          const lum = (r + g + b) / 3;
          if (lum < 28 || lum > 232) continue;
          rr += r; gg += g; bb += b; count++;
        }
        if (!count) return setAccent([76, 215, 235]);
        let r = Math.round(rr / count), g = Math.round(gg / count), b = Math.round(bb / count);
        const max = Math.max(r, g, b), min = Math.min(r, g, b);
        if (max - min < 34) {
          const boost = Math.max(0, 56 - (max - min));
          b = Math.min(255, b + boost);
          g = Math.min(255, g + Math.round(boost * .55));
        }
        const high = Math.max(r, g, b);
        if (high < 150) {
          const k = 150 / Math.max(1, high);
          r = Math.min(235, Math.round(r * k));
          g = Math.min(235, Math.round(g * k));
          b = Math.min(235, Math.round(b * k));
        }
        setAccent([r, g, b]);
      } catch (_e) {
        setAccent([76, 215, 235]);
      }
    };
    img.onerror = () => setAccent([76, 215, 235]);
    img.src = src;
  }

  function closeAuxPanels(keep) {
    const history = document.getElementById("aura-music-library-history-btn-v180");
    const collections = document.getElementById("aura-music-library-collections-v180");
    if (keep !== "history" && history?.classList.contains("active")) history.click();
    if (keep !== "collections" && collections?.classList.contains("active")) collections.click();
  }

  function playlistTitle(text) {
    const title = q(".aura-music-playlist-title", root());
    if (title) title.textContent = text;
  }

  function selectTab(tab) {
    const player = root();
    if (!player) return;
    player.dataset.r17tab = tab;
    qa(".aura-music-r17-tab", player).forEach(b => {
      b.classList.toggle("active", b.dataset.tab === tab);
      b.setAttribute("aria-selected", b.dataset.tab === tab ? "true" : "false");
    });

    if (tab === "player") {
      closeAuxPanels("");
      playlistTitle("À SUIVRE");
    } else if (tab === "library") {
      closeAuxPanels("");
      playlistTitle("BIBLIOTHÈQUE");
    } else if (tab === "queue") {
      closeAuxPanels("");
      playlistTitle("FILE D’ATTENTE");
    } else if (tab === "playlists") {
      closeAuxPanels("collections");
      playlistTitle("PLAYLISTES");
      setTimeout(() => {
        const b = document.getElementById("aura-music-library-collections-v180");
        if (b && !b.classList.contains("active")) b.click();
      }, 80);
    }
  }

  function ensureTabs() {
    const player = root();
    const head = q(".aura-music-head", player);
    if (!player || !head) return false;
    if (q(".aura-music-r17-tabs", head)) return true;

    const tabs = document.createElement("nav");
    tabs.className = "aura-music-r17-tabs";
    tabs.setAttribute("aria-label", "Navigation AURA Music");
    tabs.innerHTML = `
      <button type="button" class="aura-music-r17-tab active" data-tab="player">LECTURE</button>
      <button type="button" class="aura-music-r17-tab" data-tab="library">BIBLIOTHÈQUE</button>
      <button type="button" class="aura-music-r17-tab" data-tab="playlists">PLAYLISTES</button>
      <button type="button" class="aura-music-r17-tab" data-tab="queue">FILE</button>`;
    const right = q(".aura-music-head-right", head);
    head.insertBefore(tabs, right || null);
    tabs.addEventListener("click", e => {
      const b = e.target.closest(".aura-music-r17-tab");
      if (b) selectTab(b.dataset.tab || "player");
    });
    player.dataset.r17tab = player.dataset.r17tab || "player";
    playlistTitle("À SUIVRE");
    return true;
  }

  function openFullPlayer() {
    const nav = document.getElementById("aura-music-nav-v180");
    if (nav) {
      nav.click();
    } else {
      const player = root();
      if (player) player.classList.add("open");
    }
    setTimeout(() => selectTab("player"), 40);
  }

  function coreClick(id) {
    const b = document.getElementById(id);
    if (b) b.click();
  }

  function ensureMiniPlayer() {
    let mini = document.getElementById(MINI_ID);
    if (mini) return mini;
    mini = document.createElement("section");
    mini.id = MINI_ID;
    mini.setAttribute("aria-label", "Mini lecteur AURA Music");
    mini.innerHTML = `
      <div class="r17-mini-cover" title="Ouvrir AURA Music"></div>
      <div class="r17-mini-info" title="Ouvrir AURA Music">
        <div class="r17-mini-title">Aucun média</div>
        <div class="r17-mini-artist">Bibliothèque locale</div>
      </div>
      <div class="r17-mini-progress"><i></i></div>
      <div class="r17-mini-controls">
        <button type="button" class="r17-mini-btn prev" title="Précédent">◀</button>
        <button type="button" class="r17-mini-btn play" title="Lecture / pause">▶</button>
        <button type="button" class="r17-mini-btn next" title="Suivant">▶</button>
        <button type="button" class="r17-mini-open" title="Ouvrir le lecteur">OUVRIR</button>
      </div>`;
    document.body.appendChild(mini);

    q(".r17-mini-cover", mini).onclick = openFullPlayer;
    q(".r17-mini-info", mini).onclick = openFullPlayer;
    q(".r17-mini-open", mini).onclick = openFullPlayer;
    q(".r17-mini-btn.prev", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-prev-v180"); };
    q(".r17-mini-btn.play", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-play-v180"); };
    q(".r17-mini-btn.next", mini).onclick = e => { e.stopPropagation(); coreClick("aura-music-next-v180"); };
    return mini;
  }

  function syncMiniPlayer() {
    const player = root();
    if (!player) return;
    const mini = ensureMiniPlayer();
    const title = document.getElementById("aura-music-current-title-v180")?.textContent?.trim() || "";
    const artist = document.getElementById("aura-music-current-artist-v180")?.textContent?.trim() || "";
    const cover = document.getElementById("aura-music-cover-v180");
    const progress = document.getElementById("aura-music-progress-v180");
    const hasTrack = !!title && !/^Aucun média$/i.test(title);
    const fullOpen = player.classList.contains("open");

    mini.classList.toggle("show", hasTrack && !fullOpen);
    q(".r17-mini-title", mini).textContent = title || "Aucun média";
    q(".r17-mini-artist", mini).textContent = artist || "Bibliothèque locale";

    const bg = cover ? (cover.style.backgroundImage || getComputedStyle(cover).backgroundImage || "") : "";
    const miniCover = q(".r17-mini-cover", mini);
    miniCover.style.backgroundImage = bg && bg !== "none"
      ? bg
      : "linear-gradient(145deg,rgba(var(--r17-accent-rgb),.28),rgba(126,87,226,.22))";

    const pct = Math.max(0, Math.min(100, Number(progress?.value || 0)));
    q(".r17-mini-progress>i", mini).style.width = `${pct}%`;
    const playing = player.dataset.playing === "true";
    q(".r17-mini-btn.play", mini).textContent = playing ? "Ⅱ" : "▶";
  }

  function improveLabels() {
    const player = root();
    if (!player) return;
    const count = document.getElementById("aura-music-count-v180");
    if (count && player.dataset.r17tab === "player" && !count.dataset.r17Original) {
      count.dataset.r17Original = count.textContent || "";
    }
  }

  let booted = false;
  function refresh() {
    const player = root();
    if (!player) return;
    const subtitle = q(".aura-music-subtitle", player);
    if (subtitle) subtitle.textContent = "EXPRESSIVE PLAYER · LOCAL VLC";
    ensureTabs();
    ensureMiniPlayer();
    setTheme();
    updateArtworkAndAccent();
    syncMiniPlayer();
    improveLabels();
    if (!booted) {
      booted = true;
      player.dataset.r17tab = "player";
      selectTab("player");
    }
  }

  const observer = new MutationObserver(() => {
    clearTimeout(observer.__r17Timer);
    observer.__r17Timer = setTimeout(refresh, 35);
  });

  function boot() {
    refresh();
    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "style", "data-playing", "data-runtime"]
    });
    setInterval(() => {
      setTheme();
      updateArtworkAndAccent();
      syncMiniPlayer();
    }, 420);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();

