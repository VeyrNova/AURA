from pathlib import Path
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
branding = root / 'ui' / 'assets' / 'branding'
expected = [
    'aura_symbol_master.svg',
    'aura_symbol_boot_reveal.svg',
    'aura_symbol_neon.svg',
    'aura_sidebar_master.svg',
    'aura_symbol_solid.svg',
    'aura_wordmark_master.svg',
]
ok = True
for name in expected:
    p = branding / name
    exists = p.is_file()
    print(f'{name}: {'PASS' if exists else 'FAIL'}')
    ok = ok and exists
# simple svg parse check
for name in ['aura_symbol_master.svg', 'aura_symbol_neon.svg', 'aura_sidebar_master.svg']:
    p = branding / name
    try:
        ET.parse(p)
        print(f'parse {name}: PASS')
    except Exception:
        ok = False
        print(f'parse {name}: FAIL')
if not ok:
    raise SystemExit(1)
print('Patch 10 diagnostics: PASS')
