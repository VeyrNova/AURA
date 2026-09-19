
from __future__ import annotations
import hashlib
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_fabric_coding_agent_session import SandboxChange
from runtime.aura_developer_coding_fabric_live import (
    CodingFabricGenerationError,
    _canonical_single_target_edit,
    _is_synthetic_duplicate_parent_alias,
    _select_target_changes,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

roadmap_sha = sha(ROADMAP)
target = "docs/RM26_LIVE_ACCEPTANCE.md"
alias = "docs/docs/RM26_LIVE_ACCEPTANCE.md"

assert _is_synthetic_duplicate_parent_alias(alias, target) is True
assert _is_synthetic_duplicate_parent_alias(target, target) is False
assert _is_synthetic_duplicate_parent_alias("evil/docs/RM26_LIVE_ACCEPTANCE.md", target) is False
assert _is_synthetic_duplicate_parent_alias("../docs/RM26_LIVE_ACCEPTANCE.md", target) is False

change = SandboxChange(
    relative_path=alias,
    source_path="",
    sandbox_path="",
    change_type="created",
    before_sha256=None,
    after_sha256="synthetic",
    size_bytes=12,
    text_edit=True,
    new_text="# RM26 LIVE ACCEPTANCE\n",
)

selected, dropped = _select_target_changes(
    (change,),
    target,
    allow_synthetic_duplicate_parent_alias=True,
)
assert len(selected) == 1 and dropped == ()
edit = _canonical_single_target_edit(
    selected,
    target,
    allow_synthetic_duplicate_parent_alias=True,
)
assert edit["path"] == target
assert edit["new_text"] == "# RM26 LIVE ACCEPTANCE\n"

try:
    _select_target_changes((change,), target)
except CodingFabricGenerationError:
    pass
else:
    raise AssertionError("alias accepted without synthetic-create gate")

wrong = SandboxChange(
    relative_path="docs/other/RM26_LIVE_ACCEPTANCE.md",
    source_path="",
    sandbox_path="",
    change_type="created",
    before_sha256=None,
    after_sha256="wrong",
    size_bytes=6,
    text_edit=True,
    new_text="WRONG\n",
)
try:
    _select_target_changes(
        (wrong,),
        target,
        allow_synthetic_duplicate_parent_alias=True,
    )
except CodingFabricGenerationError:
    pass
else:
    raise AssertionError("arbitrary unexpected path accepted")

assert sha(ROADMAP) == roadmap_sha
print("[PASS] RM26-3C duplicate-parent alias accepted only for synthetic create")
print("[PASS] canonical path rebound to docs/RM26_LIVE_ACCEPTANCE.md")
print("[PASS] existing-file strict policy preserved")
print("[PASS] arbitrary unexpected paths remain denied")
print("[PASS] live Roadmap unchanged")
