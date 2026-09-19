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
from runtime.personal_integrations import (
    IntegrationRuntimeContext,
    PersonalIntegrationDispatcher,
)
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_l170_r2_") as td:
    td = Path(td)
    os.environ["AURA_L170_CANDIDATE_STORE"] = str(td / "candidates.json")

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

    cmd = "propose un souvenir : Neural Echo | rythme de sortie | une chanson chaque vendredi"
    r1 = disp.handle_text(cmd)
    assert r1.status == "succeeded", r1
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    p1 = build_personal_result_payload_v123(
        r1, getattr(disp, "_last_request", None)
    )
    assert p1["source"] == "MEMORY"
    assert p1["title"] == "CANDIDAT MEMOIRE"
    assert p1["count"] == 4
    assert r1.payload["l170_result"]["state"] == "candidate"
    assert r1.payload["live_memory_mutation_performed"] is False
    assert r1.payload["model_weight_mutation_performed"] is False

    r2 = disp.handle_text(cmd)
    assert r2.status == "succeeded", r2
    assert r2.payload["l170_result"]["state"] == "duplicate"

    r3 = disp.handle_text(
        "propose un souvenir : Neural Echo | rythme de sortie | une chanson chaque dimanche"
    )
    assert r3.status == "succeeded", r3
    assert r3.payload["l170_result"]["state"] == "conflict_review"

    r4 = disp.handle_text("montre les candidats memoire")
    assert r4.status == "succeeded", r4
    p4 = build_personal_result_payload_v123(
        r4, getattr(disp, "_last_request", None)
    )
    assert p4["title"] == "CANDIDATS MEMOIRE"
    assert p4["count"] == 3

    r5 = disp.handle_text("montre les conflits memoire")
    assert r5.status == "succeeded", r5
    p5 = build_personal_result_payload_v123(
        r5, getattr(disp, "_last_request", None)
    )
    assert p5["title"] == "CONFLITS MEMOIRE"
    assert p5["count"] == 1

    r6 = disp.handle_text("prepare la consolidation memoire")
    assert r6.status == "succeeded", r6
    p6 = build_personal_result_payload_v123(
        r6, getattr(disp, "_last_request", None)
    )
    assert p6["title"] == "PLAN DE CONSOLIDATION"
    assert p6["count"] == 1
    assert p6["items"][0]["title"] == "AUCUN CANDIDAT APPROUVE"

    r7 = disp.handle_text("bonjour")
    assert r7.handled is False

assert sha(ROADMAP) == road_sha

print("[PASS] provenance-aware conversation candidate -> persistent local store")
print("[PASS] canonical ActionReceipt for local candidate proposal")
print("[PASS] duplicate detection across persisted candidates")
print("[PASS] conflict detection across persisted candidates")
print("[PASS] candidate-list natural-language route")
print("[PASS] conflict-list natural-language route")
print("[PASS] non-mutating consolidation-plan route")
print("[PASS] typed MEMORY Personal Results")
print("[PASS] no approval/consolidation mutation capability exposed in R2")
print("[PASS] no live-memory mutation")
print("[PASS] no model-weight mutation")
print("[PASS] non-L170 requests untouched")
print("[PASS] live Roadmap unchanged")
