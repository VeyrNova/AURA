from pathlib import Path
import re

root = Path(__file__).resolve().parents[1]
settings = (root / "config" / "settings.py").read_text(encoding="utf-8")
gl = (root / "ui" / "opengl_orb_surface.py").read_text(encoding="utf-8")
focus = gl[gl.index("FOCUS_FRAGMENT_SHADER = r\"\"\""):gl.index("\nFRAGMENT_SHADER = r\"\"\"", gl.index("FOCUS_FRAGMENT_SHADER = r\"\"\"") + 1)]
checks = {
    "public_version_0_7_2": 'APP_VERSION: str = "0.7.2"' in settings,
    "legacy_build_version_removed_from_settings": '0.7.1.3.6.8.6.2' not in settings,
    "focus_mode_enabled": "UI_FOCUS_MODE = True" in gl,
    "reserved_glsl_active_removed": re.search(r"\bfloat\s+active\s*=", focus) is None,
    "state_activity_present": "float stateActivity =" in focus,
    "waveform_uses_state_activity": "stateActivity" in focus and "voiceGain" in focus,
}
failed = False
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    failed |= not ok
if failed:
    raise SystemExit(1)
print(f"Patch 22.3 diagnostics: {sum(checks.values())}/{len(checks)} PASS")
