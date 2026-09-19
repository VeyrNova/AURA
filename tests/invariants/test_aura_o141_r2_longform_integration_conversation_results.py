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
from integrations.longform_revision import LongFormRevisionProvider
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAllOuterSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_o141_r2_") as td:
    vault = Path(td) / "Novel"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Chapters").mkdir()
    (vault / "Characters").mkdir()
    (vault / "Chapters" / "Chapter 01.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 01\n[[Mara]] enters the city.\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 02.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 02\n[[Mara]] enters [[Missing Place]].\n",
        encoding="utf-8",
    )
    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: character\n---\n# Mara\nProtagonist.\n",
        encoding="utf-8",
    )

    receipts = ActionReceiptService(
        store=ActionReceiptStore(Path(td) / "receipts.sqlite3")
    )
    outer_registry = IntegrationRegistry(
        security_engine=DenyAllOuterSecurity(),
        receipt_service=receipts,
    )
    outer_registry.register_provider(LongFormRevisionProvider(default_vault=vault))

    context = IntegrationRuntimeContext(
        registry=outer_registry,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    r1 = dispatcher.handle_text("affiche le plan du manuscrit")
    assert r1.status == "succeeded", r1
    assert r1.receipt_id
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    p1 = build_personal_result_payload_v123(r1, getattr(dispatcher, "_last_request", None))
    assert p1["source"] == "OBSIDIAN"
    assert p1["title"] == "PLAN DU MANUSCRIT"
    assert p1["count"] == 2

    r2 = dispatcher.handle_text("analyse la continuite du roman")
    assert r2.status == "succeeded"
    p2 = build_personal_result_payload_v123(r2, getattr(dispatcher, "_last_request", None))
    assert p2["title"] == "AUDIT DE CONTINUITE"
    assert p2["count"] >= 1

    r3 = dispatcher.handle_text("prepare le contexte du chapitre 2")
    assert r3.status == "succeeded"
    p3 = build_personal_result_payload_v123(r3, getattr(dispatcher, "_last_request", None))
    assert p3["title"] == "CONTEXTE DE CHAPITRE"
    assert any(x["note_type"] == "current" for x in p3["items"])

    r4 = dispatcher.handle_text("fais un brief de revision du chapitre 1")
    assert r4.status == "succeeded"
    p4 = build_personal_result_payload_v123(r4, getattr(dispatcher, "_last_request", None))
    assert p4["title"] == "BRIEF DE REVISION"

    r5 = dispatcher.handle_text("cherche Mara dans le roman")
    assert r5.status == "succeeded"
    p5 = build_personal_result_payload_v123(r5, getattr(dispatcher, "_last_request", None))
    assert p5["title"] == "CONTEXTE LONG-FORM"
    assert p5["count"] >= 2

    r6 = dispatcher.handle_text("bonjour")
    assert r6.handled is False

assert sha(ROADMAP) == road_sha

print("[PASS] dedicated long-form registry works even when outer registry DENIES all")
print("[PASS] canonical ActionReceiptService is preserved")
print("[PASS] plan manuscript natural-language route")
print("[PASS] continuity audit natural-language route")
print("[PASS] chapter context resolves chapter number")
print("[PASS] revision brief resolves chapter number")
print("[PASS] contextual manuscript search")
print("[PASS] Personal Results use existing typed OBSIDIAN surface")
print("[PASS] non-long-form requests remain untouched")
print("[PASS] live Roadmap unchanged")
