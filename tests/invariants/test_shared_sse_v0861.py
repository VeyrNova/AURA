from __future__ import annotations
import re
from pathlib import Path

def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    if ui is None:
        return {
            "name": "shared_sse",
            "status": "ENVIRONMENT",
            "blocking": not portable,
            "detail": "Active UI unavailable. Local Fast Lane is authoritative for this invariant.",
        }
    assets = ui / "dist" / "assets"
    rows = []
    total = 0
    for path in sorted(assets.glob("*.js")):
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        count = len(re.findall(r"""new\s+EventSource\s*\(\s*[`'"]/api/events""", text))
        if count:
            rows.append({"file": path.name, "count": count})
            total += count
    ok = total == 1 and rows == [{"file": "index-Ckl5rwwJ.js", "count": 1}]
    return {
        "name": "shared_sse",
        "status": "PASS" if ok else "FAIL",
        "blocking": True,
        "count": total,
        "files": rows,
    }
