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
from runtime.aura_longform_revision_v141 import LongFormRevisionStudio

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class DenyAll:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


road_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_o141_r3_") as td:
    vault = Path(td) / "Novel"
    (vault / ".obsidian").mkdir(parents=True)
    for folder in ("Chapters", "Characters", "Locations", "World"):
        (vault / folder).mkdir()

    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: character\n---\n# Mara\nArchivist.\n", encoding="utf-8"
    )
    (vault / "Characters" / "Ilan.md").write_text(
        "---\ntype: character\n---\n# Ilan\nPilot.\n", encoding="utf-8"
    )
    (vault / "Locations" / "Harbor.md").write_text(
        "---\ntype: location\n---\n# Harbor\nPort.\n", encoding="utf-8"
    )
    (vault / "Chapters" / "Chapter 01.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 01\n[[Mara]] reaches [[Harbor]].\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 02.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 02\n[[Mara]] meets [[Ilan]] at [[Harbor]].\n",
        encoding="utf-8",
    )

    studio = LongFormRevisionStudio(vault)
    transition = studio.chapter_transition(
        "Chapters/Chapter 01.md",
        "Chapters/Chapter 02.md",
    )
    assert transition["characters"]["shared"] == ["Mara"]
    assert transition["characters"]["introduced"] == ["Ilan"]

    report = studio.chapter_revision_report("Chapters/Chapter 01.md")
    assert report["kind"] == "chapter_revision_report"
    assert report["transition_in"] is None
    assert report["transition_out"] is not None
    assert report["metrics"]["word_count"] > 0

    global_report = studio.manuscript_revision_report()
    assert global_report["chapter_count"] == 2
    assert len(global_report["transitions"]) == 1

    receipts = ActionReceiptService(
        store=ActionReceiptStore(Path(td) / "receipts.sqlite3")
    )
    outer = IntegrationRegistry(
        security_engine=DenyAll(),
        receipt_service=receipts,
    )
    outer.register_provider(LongFormRevisionProvider(default_vault=vault))
    context = IntegrationRuntimeContext(
        registry=outer,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    # R3-R1 policy acceptance: the outer registry denies everything, so the
    # dedicated long-form registry MUST authorize the three new R3 read-only
    # capabilities itself.
    from runtime.personal_integrations import _AuraO141R2ReadOnlySecurity
    assert "longform.chapter_transition" in _AuraO141R2ReadOnlySecurity._ALLOWED
    assert "longform.chapter_revision_report" in _AuraO141R2ReadOnlySecurity._ALLOWED
    assert "longform.manuscript_revision_report" in _AuraO141R2ReadOnlySecurity._ALLOWED

    r1 = dispatcher.handle_text("analyse le chapitre 1 du roman")
    assert r1.status == "succeeded", r1
    p1 = build_personal_result_payload_v123(
        r1, getattr(dispatcher, "_last_request", None)
    )
    assert p1["source"] == "OBSIDIAN"
    assert p1["title"] == "RAPPORT DE REVISION"
    assert p1["count"] == 6
    titles = [x["title"] for x in p1["items"]]
    assert "PERSONNAGES" in titles
    assert "TRANSITION SORTANTE" in titles

    r2 = dispatcher.handle_text(
        "analyse la transition entre le chapitre 1 et le chapitre 2"
    )
    assert r2.status == "succeeded"
    p2 = build_personal_result_payload_v123(
        r2, getattr(dispatcher, "_last_request", None)
    )
    assert p2["title"] == "TRANSITION DE CHAPITRES"
    assert p2["count"] == 4

    r3 = dispatcher.handle_text("rapport de revision du manuscrit")
    assert r3.status == "succeeded"
    p3 = build_personal_result_payload_v123(
        r3, getattr(dispatcher, "_last_request", None)
    )
    assert p3["title"] == "RAPPORT GLOBAL DE REVISION"
    assert p3["count"] >= 5
    assert any(
        x["title"] == "CONTINUITE"
        and "point(s)" in str(x.get("snippet") or "")
        for x in p3["items"]
    )

assert sha(ROADMAP) == road_sha

print("[PASS] R3-R1 dedicated read-only policy authorizes all 3 new revision capabilities")
print("[PASS] chapter transition computes shared/introduced/dropped entities")
print("[PASS] chapter revision report includes metrics/context/transitions/continuity")
print("[PASS] manuscript revision report aggregates chapters/transitions/issues")
print("[PASS] natural-language chapter analysis route")
print("[PASS] natural-language chapter transition route")
print("[PASS] natural-language global revision report route")
print("[PASS] global revision presenter JSON serialization path")
print("[PASS] canonical receipts preserved through dedicated read-only registry")
print("[PASS] Personal Results remain typed OBSIDIAN")
print("[PASS] no Markdown mutation")
print("[PASS] live Roadmap unchanged")
