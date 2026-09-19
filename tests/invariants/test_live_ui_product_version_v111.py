from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = (
    ROOT
    / "tools"
    / "sync_live_ui_version_surfaces.py"
)

assert TOOL.is_file(), TOOL

cp = subprocess.run(
    [
        sys.executable,
        str(TOOL),
        "--check",
        "--json",
    ],
    cwd=str(ROOT),
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=120,
)

assert cp.returncode == 0, cp.stdout
payload = json.loads(
    cp.stdout.splitlines()[-1]
)

assert payload["pass"] is True, payload
assert payload["stale_hits"] == [], payload
assert len(payload["ui_roots"]) >= 1, payload
assert len(payload["marker_hits"]) >= 2, payload

expected = "v" + payload["canonical_version"]
for item in payload["marker_hits"]:
    for version in item["versions"]:
        assert version == expected, (
            item,
            expected,
        )

print(
    "[PASS] live UI version surfaces "
    + expected
)
print(
    "[PASS] active UI roots="
    + str(len(payload["ui_roots"]))
)
print(
    "[PASS] marker hits="
    + str(len(payload["marker_hits"]))
)
print("[PASS] stale live UI versions=0")
