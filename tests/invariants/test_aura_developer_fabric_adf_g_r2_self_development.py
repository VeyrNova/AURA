
from pathlib import Path
import json
import os
import sys
import tempfile
import threading
import urllib.request

ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

from runtime.aura_patch_transaction_engine import propose_edits,validate_in_staging
from runtime.aura_self_development_governance import (
    assess_proposal,apply_self_development,rollback_self_development,
    SelfDevelopmentDenied,SelfDevelopmentApprovalRequired,classify_path,
)
from runtime.aura_audit_ledger import AuditLedger
from runtime.aura_developer_mode import (
    handle_developer_mode_command,developer_mode_enabled,
    capability_snapshot as mode_capabilities,
)
from runtime.aura_fabric_http_gateway import GatewayConfig,build_test_service,create_server

assert classify_path("docs/x.md")=="standard"
assert classify_path("runtime/x.py")=="elevated"
assert classify_path("runtime/aura_patch_transaction_engine.py")=="critical"
assert classify_path("core/version.py")=="constitutional"
assert classify_path(".aura_audit/events.jsonl")=="forbidden"
assert classify_path("./.aura_audit/events.jsonl")=="forbidden"
assert classify_path(".aura_transactions/x.json")=="forbidden"
assert classify_path("_patch_backups/x")=="forbidden"
assert classify_path("AURA_X_RESULT.json")=="forbidden"

with tempfile.TemporaryDirectory(prefix="aura_selfdev_r2_") as td:
    root=Path(td).resolve()
    (root/"runtime").mkdir()
    (root/"core").mkdir()

    target=root/"runtime"/"aura_fabric_http_gateway.py"
    target.write_text("VALUE = 1\n",encoding="utf-8")
    proposal=propose_edits(
        root,
        [{"path":"runtime/aura_fabric_http_gateway.py","new_text":"VALUE = 2\n"}],
        task="critical self edit",
    )
    test_commands=[[
        sys.executable,"-c",
        "import pathlib; assert 'VALUE = 2' in pathlib.Path('runtime/aura_fabric_http_gateway.py').read_text()"
    ]]
    validation=validate_in_staging(proposal,test_commands)
    assessment=assess_proposal(proposal,root)
    assert assessment["max_risk"]=="critical"
    assert len(assessment["required_approvals"])==2

    # OFF by default and cannot self-apply.
    assert developer_mode_enabled(root) is False
    try:
        apply_self_development(
            proposal,validation,aura_root=root,
            approval_phrase=assessment["required_approvals"][0],
            critical_approval=assessment["required_approvals"][1],
            post_test_commands=test_commands,
        )
    except SelfDevelopmentDenied as exc:
        assert "developer mode is disabled" in str(exc)
    else:
        raise AssertionError("self-development applied while developer mode was disabled")

    # Voice activation.
    on=handle_developer_mode_command(
        "Aura, active le mode développeur",
        channel="voice",
        root=root,
    )
    assert on["recognized"] is True and on["enabled"] is True
    assert on["speak"]=="Mode développeur activé."

    # Developer mode does not bypass the second critical approval.
    try:
        apply_self_development(
            proposal,validation,aura_root=root,
            approval_phrase=assessment["required_approvals"][0],
            critical_approval="wrong",
            post_test_commands=test_commands,
        )
    except SelfDevelopmentApprovalRequired:
        pass
    else:
        raise AssertionError("developer mode bypassed critical approval")

    receipt=apply_self_development(
        proposal,validation,aura_root=root,
        approval_phrase=assessment["required_approvals"][0],
        critical_approval=assessment["required_approvals"][1],
        post_test_commands=test_commands,
    )
    assert target.read_text()=="VALUE = 2\n"
    assert receipt["spoken_summary"].startswith("J’ai modifié ")
    assert len(receipt["spoken_summary"])<=150
    assert "sha" not in receipt["spoken_summary"].lower()
    assert "receipt" not in receipt["spoken_summary"].lower()

    state=AuditLedger(root).verify()
    assert state["ok"] is True and state["count"]>=2

    rollback=rollback_self_development(receipt,approval_phrase=receipt["rollback_phrase"])
    assert rollback["rolled_back"] is True
    assert target.read_text()=="VALUE = 1\n"
    assert rollback["spoken_summary"].startswith("J’ai annulé")

    # Voice deactivation.
    off=handle_developer_mode_command(
        "Aura, désactive le mode développeur",
        channel="voice",
        root=root,
    )
    assert off["recognized"] is True and off["enabled"] is False
    assert off["speak"]=="Mode développeur désactivé."

    # Same parser is valid for typed commands.
    assert handle_developer_mode_command("passe en mode développeur",channel="text",root=root)["enabled"] is True
    assert handle_developer_mode_command("repasse en mode normal",channel="text",root=root)["enabled"] is False

    p2=propose_edits(root,[{"path":"core/version.py","new_text":"VERSION='9.9.9'\n"}],task="release")
    try:
        assess_proposal(p2,root)
    except SelfDevelopmentDenied:
        pass
    else:
        raise AssertionError("constitutional edit accepted without release mode")
    assert len(assess_proposal(p2,root,release_mode=True)["required_approvals"])==3

caps=mode_capabilities(ROOT)
assert caps["default_enabled"] is False
assert caps["text_command_toggle"] is True
assert caps["voice_command_toggle"] is True
assert caps["brief_spoken_summary_after_apply"] is True
assert caps["spoken_output_policy"]=="brief-change-summary-only"

def get_json(url):
    with urllib.request.urlopen(url,timeout=5) as response:
        return response.status,json.loads(response.read().decode("utf-8"))

service=build_test_service(include_failure_route=False,retries_per_model=2)
server=create_server(
    service=service,
    config=GatewayConfig(host="127.0.0.1",port=0,retries_per_model=2),
    host="127.0.0.1",
    port=0,
)
thread=threading.Thread(
    target=server.serve_forever,
    kwargs={"poll_interval":0.05},
    daemon=True,
)
thread.start()
base=f"http://{server.server_address[0]}:{server.server_address[1]}"
try:
    status,mode=get_json(base+"/aura/v1/developer-mode")
    assert status==200
    assert mode["capabilities"]["voice_command_toggle"] is True
    assert mode["capabilities"]["brief_spoken_summary_after_apply"] is True

    status,selfdev=get_json(base+"/aura/v1/self-development")
    assert status==200
    assert selfdev["governance"]["developer_mode_required_for_apply"] is True

    status,developer=get_json(base+"/aura/v1/developer")
    assert status==200

    status,health=get_json(base+"/health")
    assert status==200 and health["ready"] is True

    print("[PASS] ADF-G R2 self-development safety + developer-mode voice/text toggle + brief spoken summary")
finally:
    server.shutdown()
    server.server_close()
    thread.join(timeout=3)
