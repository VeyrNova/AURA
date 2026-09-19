from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.workspace_ui_live_export_v130 import discover_live_ui_root_v130

ui=discover_live_ui_root_v130()
assert ui is not None
assert (ui/"index.html").is_file()
assert (ui/"aura_workspace_project_active_v130.js").is_file()
assert (ui/"aura_workspace_project_active_v130.css").is_file()
assert (ui/"workspace_project_active_v130.json").is_file()

idx=(ui/"index.html").read_text(encoding="utf-8-sig",errors="replace")
assert idx.count("AURA_V130_W130_F_PROJECT_ACTIVE_UI")==2

js=(ui/"aura_workspace_project_active_v130.js").read_text(encoding="utf-8")
assert "workspace_project_active_v130.json" in js
assert "PROJET ACTIF" in js

css=(ui/"aura_workspace_project_active_v130.css").read_text(encoding="utf-8")
assert ".aura-project-active-v130" in css

snap=json.loads((ui/"workspace_project_active_v130.json").read_text(encoding="utf-8-sig"))
assert snap["schema"]=="aura.workspace.ui-contract.v1"
assert snap["project_active"]["title"]=="PROJET ACTIF"

print("[PASS] W130-F native Project Active UI binding")
