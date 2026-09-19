from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_longform_revision_v141 import LongFormRevisionStudio, capability_snapshot

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)

caps = capability_snapshot()
assert caps["mutating_capabilities"] == []
assert caps["note_write"] is False
assert caps["note_delete"] is False
assert caps["read_only"] is True

with tempfile.TemporaryDirectory(prefix="aura_o141_r1_") as td:
    vault = Path(td) / "Novel"
    (vault / ".obsidian").mkdir(parents=True)
    for folder in ("Chapters", "Characters", "Locations", "World"):
        (vault / folder).mkdir()

    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: character\n---\n# Mara\nArchivist.\n",
        encoding="utf-8",
    )
    (vault / "Locations" / "Harbor.md").write_text(
        "---\ntype: location\n---\n# Harbor\nRain-soaked port.\n",
        encoding="utf-8",
    )
    (vault / "World" / "Key.md").write_text(
        "---\ntype: worldbuilding\n---\n# Brass Key\nAncient artifact.\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 01.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 01\n[[Mara]] reaches the [[Harbor]].\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 02.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 02\n[[Mara]] finds the [[Brass Key]].\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 04.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 04\n[[Mara]] enters [[Missing Archive]].\n",
        encoding="utf-8",
    )

    before = {p.relative_to(vault).as_posix(): sha(p) for p in vault.rglob("*.md")}

    studio = LongFormRevisionStudio(vault)
    outline = studio.manuscript_outline()
    assert outline["chapter_count"] == 3
    assert [x["chapter_number"] for x in outline["chapters"]] == [1, 2, 4]
    assert outline["chapters"][0]["references"]["characters"] == ["Mara"]
    assert outline["chapters"][0]["references"]["locations"] == ["Harbor"]

    ctx = studio.chapter_context("Chapters/Chapter 02.md", radius=1)
    assert [x["role"] for x in ctx["chapters"]] == ["previous", "current", "next"]
    assert ctx["chapters"][1]["title"] == "Chapter 02"

    audit = studio.continuity_audit()
    codes = [x["code"] for x in audit["issues"]]
    assert "chapter_sequence_gap" in codes
    assert "unresolved_wikilink" in codes
    assert any(x.get("chapter_number") == 3 for x in audit["issues"])

    brief = studio.revision_brief("Chapters/Chapter 02.md")
    assert brief["checks"]["has_previous_context"] is True
    assert brief["checks"]["has_next_context"] is True
    assert brief["checks"]["has_character_references"] is True

    pack = studio.context_search_pack("Mara")
    assert pack["count"] >= 3
    assert any(x.get("chapter_context") for x in pack["results"] if x.get("note_type") == "chapter")

    after = {p.relative_to(vault).as_posix(): sha(p) for p in vault.rglob("*.md")}
    assert before == after

assert sha(ROADMAP) == road_sha

print("[PASS] O141-R1 read-only long-form capability contract")
print("[PASS] deterministic chapter ordering + manuscript outline")
print("[PASS] previous/current/next chapter context pack")
print("[PASS] typed character/location/world references")
print("[PASS] continuity audit detects unresolved links + chapter-sequence gaps")
print("[PASS] chapter revision brief carries neighboring context")
print("[PASS] contextual search enriches chapter hits with long-form context")
print("[PASS] no Markdown note was modified")
print("[PASS] live Roadmap unchanged")
