from pathlib import Path
import ast
import re
import xml.etree.ElementTree as ET

root = Path(__file__).resolve().parents[1]
ui = root / 'ui'
brand = ui / 'assets' / 'branding'

checks = {}
for rel in [
    'ui/aura_logo.py',
    'ui/orb_widget.py',
    'ui/opengl_orb_surface.py',
    'ui/assets/branding/aura_symbol_master.svg',
    'ui/assets/branding/aura_symbol_outline.svg',
    'ui/assets/branding/aura_symbol_boot_reveal.svg',
    'ui/assets/branding/aura_symbol_neon.svg',
]:
    checks[f'file:{rel}'] = (root / rel).is_file()

for name in ['aura_symbol_master.svg', 'aura_symbol_outline.svg', 'aura_symbol_boot_reveal.svg', 'aura_symbol_neon.svg']:
    try:
        ET.parse(brand / name)
        checks[f'xml:{name}'] = True
    except Exception:
        checks[f'xml:{name}'] = False

for name in ['aura_logo.py', 'orb_widget.py', 'opengl_orb_surface.py']:
    try:
        ast.parse((ui / name).read_text(encoding='utf-8'))
        checks[f'python:{name}'] = True
    except SyntaxError:
        checks[f'python:{name}'] = False

orb = (ui / 'orb_widget.py').read_text(encoding='utf-8')
gl = (ui / 'opengl_orb_surface.py').read_text(encoding='utf-8')
master = (brand / 'aura_symbol_master.svg').read_text(encoding='utf-8')
checks['logo:outline-master'] = 'fill="none"' in master and 'stroke="#F4FBFF"' in master
checks['logo:no-filled-orb'] = 'Main brand rail — the interior remains transparent.' in orb
checks['logo:tagline-hidden'] = 'self._tagline.setVisible(False)' in orb
checks['fallback:no-straight-link'] = 'p.drawLine(a, b)' not in orb
checks['shader:analytic-filaments'] = 'float curvedFilament' in gl and gl.count('curvedFilament(') >= 9
checks['shader:three-depth-layers'] = 'vec2 frontP' in gl and 'vec2 midP' in gl and 'vec2 backP' in gl
checks['shader:no-fbm-heavy-cortex'] = (gl.count('fbm(') - 1) <= 5
checks['shader:balanced-braces'] = gl.count('{') == gl.count('}')
checks['shader:balanced-parens'] = gl.count('(') == gl.count(')')

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{name}: {'PASS' if ok else 'FAIL'}")
print(f'Patch 13 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS')
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
