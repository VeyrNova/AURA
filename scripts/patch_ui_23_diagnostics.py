from pathlib import Path

root = Path(__file__).resolve().parents[1]
main = (root / 'ui' / 'main_window.py').read_text(encoding='utf-8')
mods = (root / 'ui' / 'final_modules.py').read_text(encoding='utf-8')
checks = {
    'sidebar_196px': 'nav.setFixedWidth(196)' in main,
    'right_column_360px': 'right_col.setFixedWidth(360)' in main,
    'compact_topbar_56px': 'top.setFixedHeight(56)' in main,
    'compact_footer_22px': 'footer.setFixedHeight(22)' in main,
    'vector_sidebar_icons': 'def paintEvent(self, event):' in mods and 'key == "ACCUEIL"' in mods and 'key == "PARAMÈTRES"' in mods,
    'structured_card_header': 'QFrame#moduleHeader' in mods and 'moduleGlyph' in mods,
    'system_metric_bars': 'QProgressBar#systemBar' in mods and 'self.metric_bars' in mods,
    'quick_access_6_actions': 'NOUVELLE TÂCHE' in mods and 'SYNTHÈSE VOCALE' in mods and 'RECHERCHE WEB' in mods,
    'no_profile_card_reintroduced': 'no user profile card in the final shell for now' in main,
    'ui_focus_contract_untouched': 'from ui.orb_widget import OrbWidget' in main,
}
print('=== PATCH UI 23 DIAGNOSTICS ===')
failed = False
for name, ok in checks.items():
    print(f'[{"PASS" if ok else "FAIL"}] {name}')
    failed |= not ok
if failed:
    raise SystemExit(1)
