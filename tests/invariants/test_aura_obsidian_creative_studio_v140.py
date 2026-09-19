from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_obsidian_creative_studio_v140 import (
    ObsidianCreativeStudio,
    VaultBoundaryError,
    capability_snapshot,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


road_sha = sha(ROADMAP)

caps = capability_snapshot()
assert caps["version"] == "v1.4.0-o140.r1"
assert caps["mutating_capabilities"] == []
assert caps["note_write"] is False
assert caps["note_delete"] is False
assert caps["shell_execution"] is False
assert caps["subprocess_execution"] is False
assert caps["vault_boundary_enforced"] is True

with tempfile.TemporaryDirectory(prefix="aura_o140_r1_") as td:
    vault = Path(td) / "NovelVault"
    (vault / ".obsidian").mkdir(parents=True)
    for name in ("Chapters", "Characters", "Scenes", "Continuity", "World"):
        (vault / name).mkdir()

    (vault / "Characters" / "Alice.md").write_text(
        "---\ntype: character\naliases: [Alicia]\ntags: [protagonist, pilot]\n---\n"
        "# Alice\nAlice is the protagonist and a former orbital pilot.\n"
        "She meets [[Mara]] on the rooftop.\n",
        encoding="utf-8",
    )
    (vault / "Characters" / "Mara.md").write_text(
        "---\ntype: personnage\ntags: [ally]\n---\n"
        "# Mara\nMara carries the brass key.\n",
        encoding="utf-8",
    )
    (vault / "Chapters" / "Chapter 01.md").write_text(
        "---\ntype: chapter\n---\n# Chapter 01\n"
        "Alice enters the city during neon rain.\n"
        "The chapter ends at [[Rooftop Meeting]].\n",
        encoding="utf-8",
    )
    (vault / "Scenes" / "Rooftop Meeting.md").write_text(
        "---\ntype: scene\ncharacters: [Alice, Mara]\n---\n"
        "# Rooftop Meeting\nAlice and [[Mara]] meet beneath the antenna.\n"
        "The brass key is revealed.\n",
        encoding="utf-8",
    )
    (vault / "Continuity" / "Timeline.md").write_text(
        "---\ntype: timeline\n---\n# Timeline\n"
        "1. Alice arrives.\n2. Rooftop meeting.\n3. The brass key opens the archive.\n",
        encoding="utf-8",
    )
    (vault / "World" / "City.md").write_text(
        "---\ntype: worldbuilding\n---\n# The City\n"
        "A rain-soaked orbital port.\nBroken reference: [[Missing District]]\n",
        encoding="utf-8",
    )

    before = {p.relative_to(vault).as_posix(): sha(p) for p in vault.rglob("*.md")}

    studio = ObsidianCreativeStudio(vault)
    idx = studio.build_index()
    assert idx["note_count"] == 6, idx
    assert idx["type_counts"]["chapter"] == 1
    assert idx["type_counts"]["character"] == 2
    assert idx["type_counts"]["scene"] == 1
    assert idx["type_counts"]["continuity"] == 1
    assert idx["type_counts"]["world"] == 1
    assert idx["unresolved_wikilink_count"] == 1, idx

    snap = studio.creative_snapshot()
    assert snap["counts"]["chapters"] == 1
    assert snap["counts"]["characters"] == 2
    assert snap["counts"]["scenes"] == 1
    assert snap["counts"]["continuity"] == 1

    search = studio.search_context("brass key", 10)
    titles = [r["title"] for r in search["results"]]
    assert "Mara" in titles
    assert "Rooftop Meeting" in titles
    assert "Timeline" in titles

    search2 = studio.search_context("orbital pilot", 5)
    assert search2["results"][0]["title"] == "Alice", search2

    note = studio.read_note("Characters/Alice.md")
    assert note["title"] == "Alice"
    assert note["note_type"] == "character"
    assert "Mara" in note["wikilinks"]

    try:
        studio.read_note("../outside.md")
    except VaultBoundaryError:
        pass
    else:
        raise AssertionError("vault traversal was not denied")

    after = {p.relative_to(vault).as_posix(): sha(p) for p in vault.rglob("*.md")}
    assert before == after, (before, after)

assert sha(ROADMAP) == road_sha

print("[PASS] O140-R1 read-only capability contract")
print("[PASS] synthetic Obsidian vault indexed without mutation")
print("[PASS] chapters / characters / scenes / continuity / world classification")
print("[PASS] wikilink graph + unresolved link truth")
print("[PASS] contextual creative search")
print("[PASS] exact note read is vault-bound; traversal denied")
print("[PASS] no Markdown note was modified")
print("[PASS] live Roadmap unchanged")
