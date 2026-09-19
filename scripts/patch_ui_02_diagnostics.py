from __future__ import annotations

import ast
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

checks = []

def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))

files = {
    "main": ROOT / "ui" / "main_window.py",
    "orb": ROOT / "ui" / "orb_widget.py",
    "gl": ROOT / "ui" / "opengl_orb_surface.py",
    "modules": ROOT / "ui" / "final_modules.py",
    "weather": ROOT / "ui" / "weather_workspace.py",
}

for key, path in files.items():
    try:
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        check(f"Python {path.name}", True)
    except Exception as exc:
        check(f"Python {path.name}", False, str(exc))

main = files["main"].read_text(encoding="utf-8")
orb = files["orb"].read_text(encoding="utf-8")
gl = files["gl"].read_text(encoding="utf-8")
modules = files["modules"].read_text(encoding="utf-8")
weather = files["weather"].read_text(encoding="utf-8")

check("Salutation visuelle supprimée", "Bonjour, que faisons" not in main and "Bonsoir, que faisons" not in main)
check("Phrase vocale officielle", "Initialisation terminée, les paramètres sont tous au vert. Version {settings.APP_VERSION}." in main)
check("Version dynamique", "settings.APP_VERSION" in main)
check("Boot particules OpenGL", "bootCloud" in gl and "particleThreshold" in gl and "buildParticles" in gl)
check("Boot vide réel", "sceneReveal" in gl and "* buildWaves" in gl and "* buildBeam" in gl and "* buildCore" in gl)
check("Boot fallback progressif", "particle_density = stage(0.06, 0.36)" in orb and "density: float = 1.0" in orb)
check("Police HUD", "Bahnschrift SemiCondensed" in main and "Bahnschrift SemiCondensed" in modules and "Bahnschrift SemiCondensed" in weather)
check("Météo Windy-like", "Windy-like weather workspace" in weather and "timeline_slider" in weather and "COUCHES" in weather)
check("Météo 8 jours", "PRÉVISIONS · 8 JOURS" in weather and "hourly_forecast" in weather and "daily_forecast" in weather)
check("Météo routée automatiquement", "Weather Windy Workspace shown" in main)
check("Accès rapide météo", '("☁","MÉTÉO","weather")' in modules and 'if key == "weather"' in main)

print("=" * 62)
print("AURA PATCH UI 02 — DIAGNOSTIC")
print("=" * 62)
failed = 0
for name, ok, detail in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failed += 1
print("-" * 62)
print(f"Résultat: {len(checks)-failed}/{len(checks)} contrôles PASS")
sys.exit(1 if failed else 0)
