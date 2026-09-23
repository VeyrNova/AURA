
from __future__ import annotations
from pathlib import Path
import json, os, sys, tempfile, threading, urllib.request

ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from runtime.aura_repository_context import RepositoryScanner, build_context_pack, WorkspaceBoundaryError
from runtime.aura_developer_planner import build_development_plan
from runtime.aura_patch_transaction_engine import (
    propose_edits, validate_in_staging, apply_approved, rollback_receipt,
    ApprovalRequired, StaleWorkspace, TestCommandDenied, capability_snapshot as txn_caps,
)
from runtime.aura_fabric_http_gateway import GatewayConfig, build_test_service, create_server

with tempfile.TemporaryDirectory(prefix="aura_adf_f_repo_") as td:
    ws=Path(td)/"repo"; ws.mkdir()
    (ws/"calc.py").write_text("def add(a, b):\n    return a - b\n",encoding="utf-8")
    (ws/"test_calc.py").write_text("from calc import add\nassert add(2, 3) == 5\nprint('tests-pass')\n",encoding="utf-8")
    (ws/"README.md").write_text("# Demo repository\nBug is in calc add function.\n",encoding="utf-8")
    (ws/".env").write_text("SECRET_TOKEN=do-not-index\n",encoding="utf-8")
    (ws/"node_modules").mkdir(); (ws/"node_modules"/"noise.js").write_text("x"*2000,encoding="utf-8")
    (ws/"binary.bin").write_bytes(b"\x00\x01\x02")

    scan=RepositoryScanner(ws).scan()
    paths={f["path"] for f in scan["files"]}
    assert "calc.py" in paths and "test_calc.py" in paths and "README.md" in paths
    assert ".env" not in paths and "node_modules/noise.js" not in paths and "binary.bin" not in paths
    assert scan["policy"]["sensitive_files_excluded"] is True
    assert scan["policy"]["follow_symlinks"] is False

    ctx=build_context_pack(ws,query="fix calc add function",max_bytes=65536)
    assert any(f["path"]=="calc.py" for f in ctx["files"])
    assert all(f["path"]!=".env" for f in ctx["files"])
    plan=build_development_plan("Fix the add function",ctx)
    stage_ids=[x["id"] for x in plan["stages"]]
    assert "approval_gate" in stage_ids and "transaction_apply" in stage_ids and "rollback_guard" in stage_ids
    assert plan["guardrails"]["shell_execution"] is False

    old=(ws/"calc.py").read_text(encoding="utf-8")
    prop=propose_edits(ws,[{"path":"calc.py","new_text":"def add(a, b):\n    return a + b\n","reason":"correct arithmetic"}],task="Fix add")
    assert (ws/"calc.py").read_text(encoding="utf-8")==old
    assert "return a + b" in prop["edits"][0]["diff"]
    assert prop["approval_phrase"].startswith("APPLY txn_")

    validation=validate_in_staging(prop,[[sys.executable,"test_calc.py"]])
    assert validation["passed"] is True
    assert validation["workspace_written"] is False
    assert (ws/"calc.py").read_text(encoding="utf-8")==old

    try:
        apply_approved(prop,validation,approval_phrase="yes")
    except ApprovalRequired:
        pass
    else:
        raise AssertionError("wrong approval must be denied")
    assert (ws/"calc.py").read_text(encoding="utf-8")==old

    receipt=apply_approved(prop,validation,approval_phrase=prop["approval_phrase"])
    assert receipt["applied"] is True and receipt["rolled_back"] is False
    assert "return a + b" in (ws/"calc.py").read_text(encoding="utf-8")
    assert Path(receipt["backup_root"]).is_dir()
    assert receipt["post_apply_tests"][-1]["passed"] is True

    rb=rollback_receipt(receipt)
    assert rb["rolled_back"] is True
    assert (ws/"calc.py").read_text(encoding="utf-8")==old

    try:
        propose_edits(ws,[{"path":"../escape.txt","new_text":"no"}])
    except WorkspaceBoundaryError:
        pass
    else:
        raise AssertionError("outside-workspace edit must be denied")

    try:
        propose_edits(ws,[{"path":"calc.py","expected_sha256":"0"*64,"new_text":"x"}])
    except StaleWorkspace:
        pass
    else:
        raise AssertionError("stale preimage must be denied")

    denied=propose_edits(ws,[{"path":"calc.py","new_text":"def add(a,b):\n return a+b\n"}])
    try:
        validate_in_staging(denied,[["cmd.exe","/c","echo unsafe"]])
    except TestCommandDenied:
        pass
    else:
        raise AssertionError("shell-style test executable must be denied")

caps=txn_caps()
assert caps["explicit_approval_phrase"] is True and caps["automatic_rollback_on_post_test_failure"] is True

def get_json(url):
    with urllib.request.urlopen(url,timeout=5) as r:
        return r.status,json.loads(r.read().decode("utf-8"))

service=build_test_service(include_failure_route=False,retries_per_model=2)
server=create_server(service=service,config=GatewayConfig(host="127.0.0.1",port=0,retries_per_model=2),host="127.0.0.1",port=0)
th=threading.Thread(target=server.serve_forever,kwargs={"poll_interval":0.05},daemon=True); th.start()
base=f"http://{server.server_address[0]}:{server.server_address[1]}"
try:
    s,dev=get_json(base+"/aura/v1/developer")
    assert s==200
    assert dev["repository"]["bounded_context_pack"] is True
    assert dev["planner"]["explicit_approval_gate"] is True
    assert dev["transaction"]["ephemeral_staging"] is True
    s,eff=get_json(base+"/aura/v1/efficiency"); assert s==200
    s,voice=get_json(base+"/aura/v1/voice"); assert s==200
    s,agents=get_json(base+"/aura/v1/agents"); assert s==200 and agents["agent_count"]==10
    s,health=get_json(base+"/health"); assert s==200 and health["ready"] is True
    print("[PASS] ADF-F repository context + planner + patch/test/diff transaction engine")
finally:
    server.shutdown(); server.server_close(); th.join(timeout=3)
