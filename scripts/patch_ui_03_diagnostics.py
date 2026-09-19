from __future__ import annotations

import ast
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
checks: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    checks.append((name, bool(ok), detail))

files = {
    "main": ROOT / "ui" / "main_window.py",
    "orb": ROOT / "ui" / "orb_widget.py",
    "gl": ROOT / "ui" / "opengl_orb_surface.py",
    "logo": ROOT / "ui" / "aura_logo.py",
}

for path in files.values():
    try:
        text = path.read_text(encoding="utf-8")
        ast.parse(text)
        check(f"Python {path.name}", True)
    except Exception as exc:
        check(f"Python {path.name}", False, str(exc))

assets = ROOT / "ui" / "assets" / "branding"
expected_assets = (
    "aura_symbol_master.svg",
    "aura_symbol_neon.svg",
    "aura_symbol_boot_reveal.svg",
    "aura_sidebar_master.svg",
)
for name in expected_assets:
    path = assets / name
    ok = path.is_file()
    detail = ""
    if ok:
        try:
            root = ET.parse(path).getroot()
            ok = any(e.tag.rsplit("}", 1)[-1] == "path" and e.attrib.get("d") for e in root.iter())
        except Exception as exc:
            ok = False
            detail = str(exc)
    check(f"Asset vectoriel {name}", ok, detail)

main = files["main"].read_text(encoding="utf-8")
orb = files["orb"].read_text(encoding="utf-8")
gl = files["gl"].read_text(encoding="utf-8")
logo = files["logo"].read_text(encoding="utf-8")

check("Logo maître chargé depuis SVG", "master_symbol_path()" in orb and "aura_symbol_master.svg" in logo)
check("A central non redessiné à la main", "path.moveTo(cx - half" not in orb and "self._master_path = master_symbol_path()" in orb)
check("Révélation logo 60–72%", "0.60, 0.72" in orb)
check("Sphère neuronale OpenGL", "V12 neural sphere" in gl and "neuralNode" in gl and "segmentDistance" in gl)
check("Particules -> liens -> volume", all(token in gl for token in ("neuralDensityBoot", "neuralLinksGate", "neuralCoreGate")))
check("Mécanique retirée du composite", "finalCol += mix(u_primary, u_secondary, 0.42) * rings" not in gl and "finalCol += u_primary * beamWide" not in gl and "finalCol += reactor" not in gl)
check("Signal horizontal fin", "Thin signal crossing the orb" in gl and "signalCore" in gl)
check("Réflexion holographique discrète", "Restrained holographic reflection" in gl and "reflectionGlow" in gl)
check("Fallback neural", "_draw_neural_field" in orb and "_neural_nodes" in orb)
check("Boot réellement vide", "At 0% the central stage is genuinely empty" in orb)
check("Chronologie UI canonique", all(token in main for token in (
    "APPARITION DES PARTICULES",
    "CONSTRUCTION DU RÉSEAU NEURAL",
    "CONSTRUCTION DU LOGO AURA",
    "STABILISATION DES SYSTÈMES",
)))
check("Aucune salutation visuelle", "Bonjour, que faisons" not in main and "Bonsoir, que faisons" not in main)
check("Phrase vocale finale conservée", "Initialisation terminée, les paramètres sont tous au vert. Version {settings.APP_VERSION}." in main)
check("Police Windows prioritaire", "Bahnschrift SemiCondensed" in orb)

print("=" * 66)
print("AURA PATCH UI 03 — NEURAL ORB + VECTOR BRAND — DIAGNOSTIC")
print("=" * 66)
failed = 0
for name, ok, detail in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    failed += 0 if ok else 1
print("-" * 66)
print(f"Résultat: {len(checks)-failed}/{len(checks)} contrôles PASS")
sys.exit(1 if failed else 0)
