from pathlib import Path

root = Path(__file__).resolve().parents[1]
checks = [
    root / 'ui' / 'aura_logo.py',
    root / 'ui' / 'orb_widget.py',
    root / 'ui' / 'opengl_orb_surface.py',
    root / 'ui' / 'assets' / 'branding' / 'aura_symbol_master.svg',
    root / 'ui' / 'assets' / 'branding' / 'aura_symbol_outline.svg',
    root / 'ui' / 'assets' / 'branding' / 'aura_symbol_neon.svg',
]
print('=== PATCH UI 12 DIAGNOSTICS ===')
for item in checks:
    print(f'[{"OK" if item.exists() else "MISSING"}] {item.relative_to(root)}')
