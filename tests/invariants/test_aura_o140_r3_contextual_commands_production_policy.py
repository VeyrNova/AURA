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
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAllOuterSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_o140_r3_") as td:
    vault = Path(td) / "Vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Characters").mkdir()
    (vault / "Chapters").mkdir()
    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: character\ntags: [ally]\n---\n# Mara\nMara carries the brass key.\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 01.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 01\nMara enters the archive.\n",
        encoding="utf-8",
    )

    # Make this synthetic vault the only R3 provider target without changing
    # production code: monkeypatch provider discovery for this process.
    import integrations.obsidian_creative.provider as provider_mod
    from runtime.aura_obsidian_creative_studio_v140 import VaultInfo

    provider_mod.discover_vaults = lambda: [VaultInfo(str(vault), vault.name, True)]

    receipts = ActionReceiptService(store=ActionReceiptStore(Path(td) / "receipts.sqlite3"))
    outer_registry = IntegrationRegistry(
        security_engine=DenyAllOuterSecurity(),
        receipt_service=receipts,
    )
    context = IntegrationRuntimeContext(
        registry=outer_registry,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    # The OUTER registry denies everything. R3 must still succeed through the
    # bounded dedicated read-only Obsidian registry using the SAME receipt service.
    # The explicit synthetic default_vault bound in provider_mod discovery above
    # must also remain authoritative for R2 regression compatibility.
    r1 = dispatcher.handle_text("liste les personnages dans Obsidian")
    assert r1.status == "succeeded", r1
    assert r1.receipt_id
    assert receipts.get_receipt(r1.receipt_id).status == "succeeded"
    p1 = build_personal_result_payload_v123(r1, getattr(dispatcher, "_last_request", None))
    assert p1["source"] == "OBSIDIAN"
    assert p1["title"] == "PERSONNAGES OBSIDIAN"
    assert p1["count"] == 1
    assert p1["items"][0]["title"] == "Mara"

    r2 = dispatcher.handle_text("liste les chapitres dans Obsidian")
    assert r2.status == "succeeded"
    p2 = build_personal_result_payload_v123(r2, getattr(dispatcher, "_last_request", None))
    assert p2["title"] == "CHAPITRES OBSIDIAN"
    assert p2["count"] == 1

    r3 = dispatcher.handle_text("qui est Mara dans Obsidian")
    assert r3.status == "succeeded"
    p3 = build_personal_result_payload_v123(r3, getattr(dispatcher, "_last_request", None))
    assert p3["source"] == "OBSIDIAN"
    assert any(x["title"] == "Mara" for x in p3["items"])

    # Non-Obsidian request must not be swallowed by R3.
    r4 = dispatcher.handle_text("bonjour")
    assert r4.handled is False

assert sha(ROADMAP) == road_sha

print("[PASS] dedicated Obsidian policy works even when outer registry DENIES all")
print("[PASS] canonical ActionReceiptService is preserved")
print("[PASS] list characters / chapters contextual routes")
print("[PASS] 'qui est ... dans Obsidian' contextual search")
print("[PASS] category Personal Result typed OBSIDIAN")
print("[PASS] non-Obsidian requests remain untouched")
print("[PASS] live Roadmap unchanged")
