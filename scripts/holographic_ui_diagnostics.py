from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ui = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
orb = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
settings = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")

checks = {
    "version 0.7.0.13": 'APP_VERSION: str = "0.7.0.13"' in settings,
    "frameless native shell": "Qt.FramelessWindowHint" in ui and "Qt.WA_TranslucentBackground" in ui,
    "target desktop columns": all(x in ui for x in ("nav.setFixedWidth(72)", "conversation.setFixedWidth(380)", "dashboard.setFixedWidth(430)")),
    "vector navigation rail": all(x in ui for x in ("class HudIconButton", '"chat"', '"brain"', '"folder"', '"settings"')),
    "boot inside permanent state tray": "status_panel.setFixedHeight(148)" in ui and "self.boot_banner = QFrame()" in ui,
    "large state waveform": "class HudWaveformWidget" in ui and "self.setMinimumHeight(76)" in ui,
    "state emitters": "StatusPulseWidget" in ui and "ActivityRingWidget" in ui,
    "legacy utility row hidden": "self.utility_controls.setVisible(False)" in chat,
    "organic plasma torus": "_draw_plasma_torus" in orb and "Short, variable-width arclets" in orb,
    "electric micro-arcs": "_draw_electric_arcs" in orb,
    "inner plasma filaments": "_draw_inner_filaments" in orb,
    "smaller intelligence core": "Smaller dark intelligence core" in orb,
    "target tagline": "ÉCOUTE. COMPREND. AGIT." in orb,
}

print("=== AURA v0.7.0.13 - HOLOGRAPHIC UI FIDELITY ===")
ok = True
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL':4}  {name}")
    ok &= passed
print()
if ok:
    print("[PASS] Holographic UI source contract is complete.")
    print("NOTE: pixel-level appearance still requires the native Windows/PySide6 render.")
else:
    print("[FAIL] Holographic UI source contract is incomplete.")
sys.exit(0 if ok else 1)
