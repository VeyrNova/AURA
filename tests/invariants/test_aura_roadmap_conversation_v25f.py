from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT=Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.aura_roadmap_conversation_v25f import handle_roadmap_conversation_v25f

LIVE=ROOT/"data"/"roadmap"/"aura_master_roadmap_v2.json"

def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

live_sha=sha(LIVE)

with tempfile.TemporaryDirectory(prefix="aura_v25f1_") as td:
    troot=Path(td)
    roadmap=troot/"data"/"roadmap"/"aura_master_roadmap_v2.json"
    roadmap.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(LIVE,roadmap)

    ui=troot/"ui"/"dist"
    ui.mkdir(parents=True,exist_ok=True)
    (ui/"workspace_project_active_v130.json").write_text(json.dumps({
        "schema":"aura.workspace.ui-contract.v1",
        "project_active":{
            "schema":"aura.workspace.ui.project-active-card.v1",
            "title":"PROJET ACTIF","visible":True,"project_name":"AURA v2.0",
            "status":"active","root_path":str(troot),"last_action":"","next_action":"",
            "artifact_count":0,"progress_percent":0,"progress_label":"0%","tags":[],"updated_at":""
        }
    }),encoding="utf-8")
    os.environ["AURA_WORKSPACE_UI_ROOT"]=str(ui)

    r=handle_roadmap_conversation_v25f("Où en est le projet AURA ?",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_STATUS" and "%" in r["response"]

    r=handle_roadmap_conversation_v25f("Quelle est la prochaine étape ?",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_NEXT"

    r=handle_roadmap_conversation_v25f("Passe RM25F en cours",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_UPDATE_STATUS", r
    data=json.loads(roadmap.read_text(encoding="utf-8"))
    row=next(m for m in data["milestones"] if m["id"]=="RM25F")
    assert row["forecast"]["status"]=="in_progress"

    r=handle_roadmap_conversation_v25f("Mets RM25F en planifiée",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_UPDATE_STATUS", r
    data=json.loads(roadmap.read_text(encoding="utf-8"))
    row=next(m for m in data["milestones"] if m["id"]=="RM25F")
    assert row["forecast"]["status"]=="planned"

    r=handle_roadmap_conversation_v25f("Supprime RM25F",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_DELETE_CONFIRM"
    assert "confirme roadmap RF" in r["response"]

    r=handle_roadmap_conversation_v25f("Change la baseline du projet",root=troot)
    assert r["handled"] and r["intent"]=="ROADMAP_BASELINE_DENIED", r
    assert "verrouillée" in r["response"]

assert sha(LIVE)==live_sha
print("[PASS] V25-F1 conversational roadmap invariant")
print("[PASS] live roadmap unchanged by temporary invariant")
