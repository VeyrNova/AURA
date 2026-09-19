from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SYNC_TOOL = ROOT / "tools" / "sync_product_version_surfaces.py"

cp = subprocess.run(
    [sys.executable, str(SYNC_TOOL), "--check", "--json"],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    encoding="utf-8",
    errors="replace",
)

if cp.returncode != 0:
    print(cp.stdout)
    raise SystemExit(cp.returncode)

data = json.loads(cp.stdout.strip().splitlines()[-1])
assert data.get("pass") is True, data
assert data.get("stale_hits") == [], data.get("stale_hits")
version_src = (ROOT / "core" / "version.py").read_text(encoding="utf-8-sig", errors="replace")
version_line = next(
    (line for line in version_src.splitlines() if line.strip().startswith("AURA_VERSION")),
    None,
)
assert version_line is not None, "AURA_VERSION not found"
canonical_version = version_line.split("=", 1)[1].strip()
if canonical_version[:1] in ('"', "'") and canonical_version[-1:] == canonical_version[:1]:
    canonical_version = canonical_version[1:-1]
assert data.get("display_version") == "v" + canonical_version, data.get("display_version")

print("[PASS] AURA product version surfaces synchronized")
raise SystemExit(0)
