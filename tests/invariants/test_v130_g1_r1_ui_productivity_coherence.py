from __future__ import annotations
from pathlib import Path

UI = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2"
DIST = UI / "dist"

idx = (DIST / "index.html").read_text(encoding="utf-8-sig", errors="replace")
assert "v1.2.2 INTERACTIVE" not in idx
assert "v1.2.3 INTERACTIVE" in idx

system = DIST / "assets" / "aura-p0627-system-p06541.js"
assert system.is_file()
system_text = system.read_text(encoding="utf-8-sig", errors="replace")
assert "v1.2.2 · Project UI Asset Refresh" not in system_text
assert "v1.2.3 · Project UI Asset Refresh" in system_text

rebind_paths = [
    UI / "src" / "aura-v123-visible-productivity-rebind.js",
    UI / "src" / "assets" / "aura-v123-visible-productivity-rebind.js",
    DIST / "assets" / "aura-v123-visible-productivity-rebind.js",
]
texts = [p.read_text(encoding="utf-8-sig", errors="replace") for p in rebind_paths]
assert len(set(texts)) == 1
js = texts[0]
assert "const isReceiptArtifact" in js
assert "rr.every(artifact)" in js
assert "aucun reçu d’action n’est affiché comme tâche" in js
assert "Réponse Google Tasks invalide — reçu d’action ignoré" in js

print("[PASS] v1.3.0 G1 R1 UI/productivity coherence")
