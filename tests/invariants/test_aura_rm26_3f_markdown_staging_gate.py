from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import runtime.aura_developer_general_live as general
from runtime.aura_patch_transaction_engine import propose_edits, validate_in_staging

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

roadmap_sha = sha(ROADMAP)

commands = general._test_commands("docs/RM26_LIVE_ACCEPTANCE.md")
assert isinstance(commands, list)
assert len(commands) >= 2, commands

joined = "\n".join(" ".join(map(str, cmd)) for cmd in commands)
assert "AURA_MARKDOWN_UTF8_ACCEPTANCE_PASS" in joined
assert "RM26_LIVE_ACCEPTANCE_SEMANTIC_PASS" in joined

with tempfile.TemporaryDirectory(prefix="aura_rm26_3f_") as td:
    troot = Path(td)
    (troot / "docs").mkdir(parents=True, exist_ok=True)

    content = (
        "# RM26 LIVE ACCEPTANCE\n"
        "AURA Developer production hook validated after POST-APPLY PASS.\n"
    )
    proposal = propose_edits(
        troot,
        [{
            "path": "docs/RM26_LIVE_ACCEPTANCE.md",
            "new_text": content,
            "reason": "RM26-3F synthetic staging acceptance",
        }],
        task="RM26 synthetic markdown staging acceptance",
    )
    validation = validate_in_staging(proposal, commands, timeout_s=120)
    assert validation.get("passed") is True, validation
    tests = validation.get("tests") or []
    assert len(tests) >= 2
    assert all(row.get("passed") is True for row in tests)

assert sha(ROADMAP) == roadmap_sha
print("[PASS] RM26-3F markdown test commands are non-empty")
print("[PASS] generic Markdown UTF-8/non-empty gate present")
print("[PASS] RM26 acceptance semantic marker gate present")
print("[PASS] validate_in_staging passes with the intended RM26 artifact")
print("[PASS] live Roadmap unchanged")
