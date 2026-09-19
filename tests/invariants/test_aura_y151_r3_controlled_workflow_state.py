from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from runtime.aura_publishing_workflow_state_v151 import (
    PublishingWorkflowApprovalRequired,
    PublishingWorkflowExternalMutationUnavailable,
    PublishingWorkflowStateMachine,
)
from runtime.personal_integrations import (
    IntegrationRuntimeContext,
    PersonalIntegrationDispatcher,
)
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
DATA = ROOT / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)
data_sha = sha(DATA)

with tempfile.TemporaryDirectory(prefix="aura_y151_r3_") as td:
    td = Path(td)
    direct_store = td / "direct.json"
    machine = PublishingWorkflowStateMachine(direct_store)
    plan = {
        "state": "approval_required",
        "requires_explicit_confirmation": True,
        "external_mutation_performed": False,
        "draft": {
            "title": "Direct State Test",
            "format": "short",
            "description": "local",
            "scheduled_for": None,
        },
        "gates": [
            "explicit_user_confirmation",
            "provider_write_capability_required",
            "canonical_action_receipt_required",
        ],
    }
    record = machine.create_from_plan(plan)
    assert record["state"] == "approval_required"
    assert record["publish_available"] is False
    assert record["external_mutation_performed"] is False

    try:
        machine.approve_local(record["workflow_id"], user_confirmed=False)
        raise AssertionError("approval without explicit confirmation must fail")
    except PublishingWorkflowApprovalRequired:
        pass

    approved = machine.approve_local(
        record["workflow_id"],
        user_confirmed=True,
    )
    assert approved["state"] == "approved_local"
    assert approved["local_approval"] is True
    assert approved["publish_available"] is False
    assert approved["external_mutation_performed"] is False

    try:
        machine.publish(record["workflow_id"])
        raise AssertionError("publish must remain unavailable")
    except PublishingWorkflowExternalMutationUnavailable:
        pass

    integration_store = td / "integration.json"
    os.environ["AURA_Y151_WORKFLOW_STORE"] = str(integration_store)

    receipts = ActionReceiptService(
        store=ActionReceiptStore(td / "receipts.sqlite3")
    )
    outer = IntegrationRegistry(
        security_engine=DenyAll(),
        receipt_service=receipts,
    )
    ctx = IntegrationRuntimeContext(
        registry=outer,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    disp = PersonalIntegrationDispatcher(context=ctx)

    r1 = disp.handle_text(
        "prepare un workflow de publication youtube pour Neural Echo Friday Short"
    )
    assert r1.status == "succeeded", r1
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    result = r1.payload["y151_result"]
    record = result["workflow_record"]
    assert record["state"] == "approval_required"
    assert record["publish_available"] is False
    assert record["external_mutation_performed"] is False

    p1 = build_personal_result_payload_v123(
        r1, getattr(disp, "_last_request", None)
    )
    assert p1["title"] == "WORKFLOW DE PUBLICATION"
    assert p1["count"] == 3
    assert p1.get("workflow_id") == record["workflow_id"]
    assert p1.get("workflow_state") == "approval_required"
    assert record["workflow_id"] in str(p1["items"][0].get("snippet") or "")
    assert any(x["title"] == "APPROBATION REQUISE" for x in p1["items"])
    assert any(x["title"] == "AUCUNE PUBLICATION EFFECTUEE" for x in p1["items"])

    r2 = disp.handle_text("montre le statut du workflow de publication youtube")
    assert r2.status == "succeeded", r2
    p2 = build_personal_result_payload_v123(
        r2, getattr(disp, "_last_request", None)
    )
    assert p2["title"] == "ETAT WORKFLOW"
    assert p2["count"] == 4
    assert any(x["title"] == "PUBLICATION BLOQUEE" for x in p2["items"])

assert sha(ROADMAP) == road_sha
assert sha(DATA) == data_sha

print("[PASS] persisted local workflow id/state")
print("[PASS] explicit local approval required")
print("[PASS] approved_local still has publish_available=false")
print("[PASS] publish operation remains unavailable")
print("[PASS] workflow create route persists approval_required state")
print("[PASS] workflow status route")
print("[PASS] canonical ActionReceipts")
print("[PASS] Personal Results preserve R2 count=3 while exposing workflow id/state")
print("[PASS] live snapshot unchanged")
print("[PASS] live Roadmap unchanged")
