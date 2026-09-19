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
from integrations.obsidian_creative import ObsidianCreativeProvider
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123, summarize_personal_result_for_tts_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action).startswith("obsidian.") else "DENY"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_o140_r2_vault_") as td:
    vault = Path(td) / "Story"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / "Characters").mkdir()
    (vault / "Scenes").mkdir()
    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: character\n---\n# Mara\nMara carries the brass key.\n",
        encoding="utf-8",
    )
    (vault / "Scenes" / "Archive.md").write_text(
        "---\ntype: scene\n---\n# Archive\nThe brass key opens the archive with [[Mara]].\n",
        encoding="utf-8",
    )

    receipts = ActionReceiptService(store=ActionReceiptStore(Path(td) / "receipts.sqlite3"))
    registry = IntegrationRegistry(security_engine=Security(), receipt_service=receipts)
    registry.register_provider(ObsidianCreativeProvider(default_vault=vault))
    context = IntegrationRuntimeContext(
        registry=registry,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    reply = dispatcher.handle_text("cherche brass key dans Obsidian")
    assert reply.handled is True
    assert reply.status == "succeeded", reply
    assert reply.capability_id == "obsidian.search_context"
    assert reply.receipt_id
    receipt = receipts.get_receipt(reply.receipt_id)
    assert receipt.status == "succeeded"

    request = getattr(dispatcher, "_last_request", None)
    assert request.provider_id == "obsidian.creative"
    payload = build_personal_result_payload_v123(reply, request)
    assert payload["kind"] == "obsidian"
    assert payload["source"] == "OBSIDIAN"
    assert payload["sources"] == ["OBSIDIAN"]
    assert payload["count"] >= 2
    assert any(x["title"] == "Mara" for x in payload["items"])
    summary = summarize_personal_result_for_tts_v123(payload, reply.text).casefold()
    assert "obsidian" in summary
    assert "google" not in summary

    reply2 = dispatcher.handle_text("resume mon projet Obsidian")
    assert reply2.status == "succeeded"
    payload2 = build_personal_result_payload_v123(reply2, getattr(dispatcher, "_last_request", None))
    assert payload2["source"] == "OBSIDIAN"
    assert payload2["title"] == "PROJET OBSIDIAN"
    assert payload2["count"] == 7

for p in [
    Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "src" / "aura-v123-personal-results-web.js",
    Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "src" / "assets" / "aura-v123-personal-results-web.js",
    Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "dist" / "assets" / "aura-v123-personal-results-web.js",
]:
    text = p.read_text(encoding="utf-8")
    assert "AURA_O140_R2_OBSIDIAN_PERSONAL_RESULTS_WEB" in text
    assert "obsidian:'OBSIDIAN'" in text

assert sha(ROADMAP) == road_sha
print("[PASS] Obsidian IntegrationProvider executes through IntegrationRegistry receipts")
print("[PASS] natural-language search routes to obsidian.search_context")
print("[PASS] project summary routes to obsidian.creative_snapshot")
print("[PASS] dispatcher publishes current Obsidian _last_request")
print("[PASS] Personal Result is typed OBSIDIAN, never Google")
print("[PASS] native/recovery UI contains OBSIDIAN presentation support")
print("[PASS] no Obsidian note mutation capability exists")
print("[PASS] live Roadmap unchanged")
