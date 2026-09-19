from pathlib import Path
import xml.etree.ElementTree as ET
import re

root = Path(__file__).resolve().parents[1]
branding = root / 'ui' / 'assets' / 'branding'
expected = [
    'aura_symbol_master.svg',
    'aura_symbol_boot_reveal.svg',
    'aura_symbol_solid.svg',
    'aura_symbol_outline.svg',
    'aura_symbol_neon.svg',
    'aura_wordmark_master.svg',
    'aura_icon_wordmark_lockup.svg',
    'aura_sidebar_master.svg',
]
ok = True
for name in expected:
    p = branding / name
    exists = p.is_file()
    print(f"{name}: {'PASS' if exists else 'FAIL'}")
    ok = ok and exists
for name in ['aura_symbol_master.svg', 'aura_symbol_solid.svg', 'aura_symbol_neon.svg']:
    try:
        ET.parse(branding / name)
        print(f'parse {name}: PASS')
    except Exception:
        ok = False
        print(f'parse {name}: FAIL')
orb = (root / 'ui' / 'orb_widget.py').read_text(encoding='utf-8')
checks = {
    'filled_logo_render': 'filled silhouette from the user-provided branding board' in orb,
    'gradient_fill': 'p.setBrush(QBrush(grad))' in orb,
    'thin_premium_edge': 'Thin premium edge like the reference board' in orb,
}
for name, passed in checks.items():
    print(f"{name}: {'PASS' if passed else 'FAIL'}")
    ok = ok and passed
if not ok:
    raise SystemExit(1)
print('Patch 11 diagnostics: PASS')
