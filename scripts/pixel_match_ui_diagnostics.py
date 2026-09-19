from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ui = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
orb = (ROOT / "ui" / "orb_widget.py").read_text(encoding="utf-8")
main = (ROOT / "main.py").read_text(encoding="utf-8")

checks = {
    "native Windows frame removed": "Qt.FramelessWindowHint" in ui,
    "transparent rounded application surface": "Qt.WA_TranslucentBackground" in ui and 'QFrame#appSurface' in ui,
    "integrated minimize/maximize/close": all(x in ui for x in ("windowButton", "closeButton", "_toggle_maximize")),
    "maximized production launch": "window.showMaximized()" in main,
    "reference proportions": all(x in ui for x in ("nav.setFixedWidth(72)", "conversation.setFixedWidth(380)", "dashboard.setFixedWidth(430)")),
    "message bubble feed": all(x in chat for x in ("_MessageBubble", "userBubbleCard", "auraBubbleCard", "composerFrame")),
    "dashboard row cards": all(x in ui for x in ("DashboardCard", "dashboardRow", "set_rows")),
    "large holographic core": all(x in orb for x in ("_draw_energy_wave", "_draw_telemetry_rings", "_draw_sphere", "_draw_platform", "_draw_particles")),
    "target orb tagline": "ÉCOUTE. COMPREND. AGIT." in orb,
    "startup telemetry removed from normal chat": "Resource Guardian protège" not in ui,
}

print("=== AURA v0.7.0.13 - PIXEL MATCH UI DIAGNOSTIC ===")
ok = True
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL':4}  {name}")
    ok &= passed
print()
if ok:
    print("[PASS] Pixel-match shell source contract is complete.")
    print("NOTE: exact native rendering still requires the Windows/PySide6 runtime.")
else:
    print("[FAIL] Pixel-match shell source contract is incomplete.")
sys.exit(0 if ok else 1)
