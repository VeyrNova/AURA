from __future__ import annotations

import hashlib
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
DATA = ROOT / "data" / "youtube" / "neural_echo_youtube_snapshot_v150.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)
data_sha = sha(DATA)

with tempfile.TemporaryDirectory(prefix="aura_y151_r2_") as td:
    receipts = ActionReceiptService(
        store=ActionReceiptStore(Path(td) / "receipts.sqlite3")
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

    r1 = disp.handle_text("compare mes shorts et mes videos longues")
    assert r1.status == "succeeded", r1
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    p1 = build_personal_result_payload_v123(
        r1, getattr(disp, "_last_request", None)
    )
    assert p1["source"] == "YOUTUBE"
    assert p1["title"] == "COMPARAISON FORMATS"
    assert p1["count"] == 3

    r2 = disp.handle_text("quels sont mes meilleurs horaires de publication youtube")
    assert r2.status == "succeeded", r2
    p2 = build_personal_result_payload_v123(
        r2, getattr(disp, "_last_request", None)
    )
    assert p2["title"] == "FENETRES DE PUBLICATION"
    assert p2["count"] >= 1
    assert any(
        x["note_type"] in {"EXPLORATOIRE", "SIGNAL"}
        for x in p2["items"]
    )

    r3 = disp.handle_text("prepare un mix editorial youtube de 3 publications")
    assert r3.status == "succeeded", r3
    p3 = build_personal_result_payload_v123(
        r3, getattr(disp, "_last_request", None)
    )
    assert p3["title"] == "MIX EDITORIAL"
    assert p3["count"] == 3

    r4 = disp.handle_text(
        "prepare un workflow de publication youtube pour Neural Echo Friday Short"
    )
    assert r4.status == "succeeded", r4
    assert receipts.get_receipt(r4.receipt_id).status == "succeeded"
    p4 = build_personal_result_payload_v123(
        r4, getattr(disp, "_last_request", None)
    )
    assert p4["title"] == "WORKFLOW DE PUBLICATION"
    assert p4["count"] == 3
    assert any(x["title"] == "APPROBATION REQUISE" for x in p4["items"])
    assert any(x["title"] == "AUCUNE PUBLICATION EFFECTUEE" for x in p4["items"])
    assert r4.payload["y151_result"]["external_mutation_performed"] is False
    assert r4.payload["y151_result"]["youtube_upload_performed"] is False

    r5 = disp.handle_text("bonjour")
    assert r5.handled is False

assert sha(ROADMAP) == road_sha
assert sha(DATA) == data_sha

print("[PASS] Y151 dedicated registry + canonical ActionReceipts")
print("[PASS] natural-language Shorts vs long-form comparison")
print("[PASS] publishing-window route with confidence/sample labeling")
print("[PASS] editorial mix route")
print("[PASS] publishing workflow PLAN route")
print("[PASS] workflow remains approval_required / local only")
print("[PASS] no upload/edit/delete/comment mutation")
print("[PASS] typed YOUTUBE Personal Results")
print("[PASS] non-Y151 requests untouched")
print("[PASS] live snapshot unchanged")
print("[PASS] live Roadmap unchanged")
