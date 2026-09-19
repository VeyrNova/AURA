
from pathlib import Path
import os,sys
ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from ui.developer_mode_web_surface import developer_mode_script,workspace_script,capability_snapshot

on=developer_mode_script(True)
off=developer_mode_script(False)
assert "AURA // DEV" in on
assert "DEV ACTIVE · WRITE GATED · AUDIT ON" in on
assert "2147483000" in on
assert "AURA DEV // Que veux-tu modifier ?" in on
assert 'const enabled = true' in on
assert 'const enabled = false' in off

sample={"developer_mode":{"enabled":True},"safety":{"tests_required":True},"recent_transactions":[],"audit_head":None}
ws=workspace_script(sample)
assert "AURA // DEVELOPER WORKSPACE" in ws
assert "WRITE GATED · TESTS REQUIRED · AUDIT ON" in ws
assert "2147483100" in ws

caps=capability_snapshot()
assert caps["qwebengine_binding"] is True
assert caps["threejs_shell_overlay"] is True
assert caps["web_asset_mutation_required"] is False
print("[PASS] ADF-H R4 Web/Three.js visible-surface contract")
