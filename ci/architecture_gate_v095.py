from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYTHON=Path(sys.executable)

required=[
    ROOT/"integrations"/"notifications"/"provider.py",
    ROOT/"runtime"/"personal_integrations.py",
    ROOT/"ui"/"personal_integration_modules.py",
    ROOT/"tests"/"invariants"/"test_notifications_provider_v095.py",
    ROOT/"tests"/"invariants"/"test_notifications_runtime_bridge_v095.py",
    ROOT/"tests"/"invariants"/"test_notifications_module_ui_v095.py",
    ROOT/"tests"/"invariants"/"test_activity_center_structural_color_fix_v095.py",
    ROOT/"tests"/"invariants"/"test_color_charter_lock_v095.py",
    ROOT/"ci"/"color_charter_lock_v095.json",
]

for path in required:
    assert path.is_file(), str(path)

for rel in [
    "tests/invariants/test_notifications_provider_v095.py",
    "tests/invariants/test_notifications_runtime_bridge_v095.py",
    "tests/invariants/test_notifications_module_ui_v095.py",
    "tests/invariants/test_activity_center_structural_color_fix_v095.py",
    "tests/invariants/test_color_charter_lock_v095.py",
]:
    cp=subprocess.run(
        [str(PYTHON),str(ROOT/rel)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    assert cp.returncode==0, cp.stdout

print("[PASS] AURA v0.9.5 architecture gate")
print("[PASS] Notifications + Activity Center + Color Charter architecture")
