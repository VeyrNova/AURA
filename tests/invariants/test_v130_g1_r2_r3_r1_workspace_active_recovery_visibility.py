from pathlib import Path
import json

UI = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "dist"
JS = UI / "aura_workspace_project_active_v130.js"
SNAP = UI / "workspace_project_active_v130.json"

js = JS.read_text(encoding="utf-8-sig", errors="replace")
assert "function actuallyVisibleV130(el)" in js
assert "function foregroundPanelRectV130()" in js
assert "function placeProjectCardV130(root)" in js
assert "Project Active remains available across Home / Conversation / modules." in js
assert "placeProjectCardV130(root);" in js
assert "if (productivityCoreVisible())" not in js

snap = json.loads(SNAP.read_text(encoding="utf-8-sig"))
card = snap.get("project_active") or {}
assert card.get("visible") is True
assert card.get("workspace_id") == "ws_aura_main"
assert card.get("project_name") == "AURA v2.0"

print("[PASS] v1.3.0 Workspace active recovery + persistent visibility")
