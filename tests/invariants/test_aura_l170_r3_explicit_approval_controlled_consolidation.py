
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
from integrations import IntegrationRegistry, IntegrationRequest
from runtime.aura_controlled_learning_registry_binding_v170 import register_controlled_learning_provider_v170
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"

class R3Security:
    MUT = {"learning.approve_candidate", "learning.resolve_conflict", "learning.consolidate_candidate"}
    def authorize(self, action, params, *, user_confirmed=False):
        if action in self.MUT:
            return "ALLOW" if user_confirmed else "DENY"
        return "ALLOW"

road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_l170_r3_") as td:
    td = Path(td)
    os.environ["AURA_L170_CANDIDATE_STORE"] = str(td / "candidates.json")
    receipts = ActionReceiptService(store=ActionReceiptStore(td / "receipts.sqlite3"))

    registry = IntegrationRegistry(security_engine=R3Security(), receipt_service=receipts)
    register_controlled_learning_provider_v170(registry)

    create_req = IntegrationRequest.create(
        provider_id="controlled.learning",
        capability_id="learning.propose_candidate",
        params={
            "subject": "Neural Echo",
            "predicate": "L170 controlled test",
            "value": "enabled",
            "source_kind": "manual",
            "source_ref": "l170-r3-test",
        },
        origin="test",
    )
    assert registry.execute_integration(create_req, user_confirmed=False).status == "succeeded"

    approve_req = IntegrationRequest.create(
        provider_id="controlled.learning",
        capability_id="learning.approve_candidate",
        params={"explicit_confirmation": True},
        origin="test",
    )
    assert registry.execute_integration(approve_req, user_confirmed=False).status != "succeeded"
    approved = registry.execute_integration(approve_req, user_confirmed=True)
    assert approved.status == "succeeded"
    assert approved.output["l170_result"]["state"] == "approved"

    consolidate_req = IntegrationRequest.create(
        provider_id="controlled.learning",
        capability_id="learning.consolidate_candidate",
        params={"explicit_confirmation": True},
        origin="test",
    )
    consolidated = registry.execute_integration(consolidate_req, user_confirmed=True)
    assert consolidated.status == "succeeded"
    cres = consolidated.output["l170_result"]
    assert cres["candidate"]["state"] == "consolidated"
    assert cres["controlled_learning_ledger_write_performed"] is True
    assert cres["live_memory_backend_injection_performed"] is False
    assert cres["model_weight_mutation_performed"] is False

    outer = IntegrationRegistry(security_engine=DenyAll(), receipt_service=receipts)
    ctx = IntegrationRuntimeContext(
        registry=outer,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    disp = PersonalIntegrationDispatcher(context=ctx)

    assert disp.handle_text(
        "propose un souvenir : Neural Echo | test conversation L170 | actif"
    ).status == "succeeded"

    r2 = disp.handle_text("approuve le dernier candidat memoire")
    assert r2.status == "succeeded"
    p2 = build_personal_result_payload_v123(r2, getattr(disp, "_last_request", None))
    assert p2["title"] == "CANDIDAT APPROUVE"
    assert p2["count"] == 2

    r3 = disp.handle_text("consolide le dernier candidat memoire")
    assert r3.status == "succeeded"
    p3 = build_personal_result_payload_v123(r3, getattr(disp, "_last_request", None))
    assert p3["title"] == "MEMOIRE CONSOLIDEE"
    assert p3["count"] == 3

    r4 = disp.handle_text("montre les souvenirs consolides")
    assert r4.status == "succeeded"
    p4 = build_personal_result_payload_v123(r4, getattr(disp, "_last_request", None))
    assert p4["title"] == "MEMOIRES CONSOLIDEES"
    assert p4["count"] >= 1

    assert disp.handle_text(
        "propose un souvenir : Neural Echo | test conflit L170 | valeur A"
    ).status == "succeeded"
    conflict = disp.handle_text(
        "propose un souvenir : Neural Echo | test conflit L170 | valeur B"
    )
    assert conflict.status == "succeeded"
    assert conflict.payload["l170_result"]["state"] == "conflict_review"
    resolved = disp.handle_text("rejette le dernier conflit memoire")
    assert resolved.status == "succeeded"
    assert resolved.payload["l170_result"]["state"] == "rejected"

assert sha(ROADMAP) == road_sha

print("[PASS] unconfirmed approval is denied")
print("[PASS] explicit approval -> canonical succeeded ActionReceipt")
print("[PASS] explicit controlled consolidation")
print("[PASS] consolidated memory persisted in local L170 ledger")
print("[PASS] no live-memory backend injection")
print("[PASS] no model-weight mutation")
print("[PASS] natural-language approve/consolidate/list routes")
print("[PASS] explicit conflict rejection route")
print("[PASS] typed MEMORY Personal Results")
print("[PASS] live Roadmap unchanged")
