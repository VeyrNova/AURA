from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / "main.py").read_text(encoding="utf-8")
ui = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui" / "chat_panel.py").read_text(encoding="utf-8")
settings = (ROOT / "config" / "settings.py").read_text(encoding="utf-8")

show_pos = main.find("window.showMaximized()")
begin_pos = main.find("window.begin_startup()")
checks = {
    "version 0.7.0.13": 'APP_VERSION: str = "0.7.0.13"' in settings,
    "single MainWindow shell": "MainWindow(startup_gate=True)" in main,
    "legacy splash unused": "StartupWindow()" not in main and "splash.close()" not in main,
    "shell visible before begin_startup": show_pos >= 0 and begin_pos >= 0 and show_pos < begin_pos,
    "frameless shell": "Qt.FramelessWindowHint" in ui,
    "custom app surface": 'setObjectName("appSurface")' in ui,
    "custom title controls": all(x in ui for x in ("self.minimize_button", "self.maximize_button", "self.close_button")),
    "left navigation rail": 'setObjectName("navRail")' in ui,
    "structured conversation": "class _MessageBubble" in chat and "QScrollArea" in chat,
    "dynamic hero orb": "self.orb = OrbWidget()" in ui and "self.orb.setMinimumSize(500, 500)" in ui,
    "structured dashboard": "class DashboardCard" in ui,
    "boot progress in final shell": 'self.boot_banner.setObjectName("bootBanner")' in ui,
    "unlock after warmup": "self._set_startup_locked(False)" in ui and "self.startup_ready.emit()" in ui,
}

print("=== AURA v0.7.0.13 - FINAL SHELL STARTUP DIAGNOSTIC ===")
ok = True
for name, passed in checks.items():
    print(f"{'PASS' if passed else 'FAIL':4}  {name}")
    ok &= passed

print()
print("[PASS] Frameless final shell startup contract ready." if ok else "[FAIL] Final-shell startup contract incomplete.")
sys.exit(0 if ok else 1)
