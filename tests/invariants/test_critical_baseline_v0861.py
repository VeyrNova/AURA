from __future__ import annotations
from pathlib import Path

def check(root: Path, ui: Path | None, baseline: dict, *, portable: bool = False) -> dict:
    failures = []
    checked = []
    for name, info in baseline["critical"].items():
        path = Path(info["path"])
        is_ui = name.startswith("ui_")
        if is_ui and portable and (ui is None or not path.is_file()):
            continue
        if is_ui and ui is not None:
            # Rebase the frozen relative UI path onto the currently active UI root.
            old = str(info["path"]).replace("/", "\\")
            marker = "\\v0.7.2.2-rc4.2\\"
            if marker in old:
                rel = old.split(marker, 1)[1]
                path = ui / Path(rel)
        if not path.is_file():
            failures.append({"name": name, "reason": "missing", "path": str(path)})
            continue
        import hashlib
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        checked.append({"name": name, "path": str(path), "sha256": h})
        if h != info["sha256"]:
            failures.append({
                "name": name, "reason": "hash-drift",
                "expected": info["sha256"], "actual": h, "path": str(path)
            })
    if portable and ui is None:
        ui_status = "ENVIRONMENT"
    else:
        ui_status = "PASS"
    return {
        "name": "critical_baseline",
        "status": "PASS" if not failures else "FAIL",
        "blocking": True,
        "portable": portable,
        "active_ui_status": ui_status,
        "checked": checked,
        "failures": failures,
    }
