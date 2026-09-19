from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'ui' / 'main_window.py').read_text(encoding='utf-8')
mods = (root / 'ui' / 'final_modules.py').read_text(encoding='utf-8')
checks = {
    'sidebar_208px': 'nav.setFixedWidth(208)' in main,
    'right_column_410px': 'right_col.setFixedWidth(410)' in main,
    'topbar_62px': 'top.setFixedHeight(62)' in main,
    'home_composer_840px': 'self.home_composer.setMaximumWidth(840)' in main,
    'home_composer_50px_min': 'self.setMinimumHeight(50)' in mods,
    'memory_core_runtime_label': '◇ MEMORY CORE ACTIVE' in main and 'MÉMOIRE PERSISTANTE' in main,
    'no_security_core_runtime_label': '◇ SECURITY CORE ACTIVE' not in main,
    'system_bars_wider': 'bar.setFixedWidth(92)' in mods,
    'vector_sidebar_icons_preserved': 'def paintEvent(self, event):' in mods and 'key == "ACCUEIL"' in mods and 'key == "PARAMÈTRES"' in mods,
    'ui_focus_orb_wrapper_preserved': 'from ui.orb_widget import OrbWidget' in main,
    'app_version_not_hardcoded': '0.7.2' not in main and '0.7.2' not in mods,
    'right_cards_readable': 'self.system_compact.setFixedHeight(288)' in main and 'self.quick_access.setFixedHeight(166)' in main,
}
print('=== PATCH UI 24 DIAGNOSTICS ===')
failed = False
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed |= not ok
if failed:
    raise SystemExit(1)
