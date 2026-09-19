from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_v11_version_and_typography_contract():
    settings = (ROOT / "config/settings.py").read_text(encoding="utf-8")
    orb = (ROOT / "ui/orb_widget.py").read_text(encoding="utf-8")
    assert '0.7.0.15.6.11' in settings
    assert 'Orbitron' in orb and 'Rajdhani' in orb and 'Bahnschrift' in orb
    assert 'QFontDatabase.families' in orb
    assert 'A U R A' in orb
    assert "font-family: 'Segoe UI'; font-size: 38px" not in orb

def test_v11_material_contract():
    src = (ROOT / "ui/opengl_orb_surface.py").read_text(encoding="utf-8")
    for marker in ("V11 MATERIAL MATCH", "microMatter", "microArcA", "hudBars", "waveMicro"):
        assert marker in src
    assert 'float baseY = p.y + 0.600;' in src
    assert 'u_bloom_strength' in src

def test_v11_hud_font_contract():
    src = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    assert "font-family: 'Bahnschrift', 'Segoe UI'" in src
    assert 'QLabel#metricTitle' in src
