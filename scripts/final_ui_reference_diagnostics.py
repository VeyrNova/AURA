"""Read-only diagnostics for the final AURA neural interface integration."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]

CHECKS = {
    "final modules": (ROOT / "ui" / "final_modules.py", [
        "class PreheatOverlay", "class WarmupConstructionWidget", "class MemoryPage",
        "class AgendaPage", "class SystemPage", "class ProjectsPage", "class FilesPage",
        "class MusicPage", "class SettingsPage", "class TasksPage",
    ]),
    "final shell": (ROOT / "ui" / "main_window.py", [
        'nav.setFixedWidth(208)', 'self.page_stack = QStackedWidget()',
        'self.preheat_overlay = PreheatOverlay(central)', 'self.home_composer = HomeComposer()',
        'self.system_compact = SystemCompactCard()', 'self.tasks_compact = TasksCompactCard()',
    ]),
    "neural orb": (ROOT / "ui" / "orb_widget.py", [
        "class _AuraMarkWidget", "_draw_plasma_torus", "_draw_inner_filaments",
        "set_voice_amplitude", "set_preload_visual_safety",
    ]),
}


def main() -> int:
    print("=== AURA FINAL UI REFERENCE DIAGNOSTICS ===")
    failures = 0
    for name, (path, markers) in CHECKS.items():
        if not path.is_file():
            print(f"[FAIL] {name}: fichier absent {path.relative_to(ROOT)}")
            failures += 1
            continue
        text = path.read_text(encoding="utf-8")
        missing = [m for m in markers if m not in text]
        if missing:
            print(f"[FAIL] {name}: {len(missing)} marqueur(s) absent(s)")
            for marker in missing:
                print(f"       - {marker}")
            failures += 1
        else:
            print(f"[PASS] {name}: {path.relative_to(ROOT)}")
    ref = ROOT / "docs" / "ui_final_reference" / "00_manifest.txt"
    if ref.is_file():
        print("[PASS] références UI finales archivées")
    else:
        print("[INFO] références UI non incluses dans ce paquet")
    print("RESULT:", "PASS" if failures == 0 else f"FAIL ({failures})")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
