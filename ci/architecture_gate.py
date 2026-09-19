# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, json
from pathlib import Path
from common import ROOT, load_baseline, line_count, resolve_active_ui, write_report

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portable", action="store_true")
    args = ap.parse_args()
    baseline = load_baseline()
    failures = []
    rows = []

    for rel, ceiling in baseline["architecture_ceilings"].items():
        path = ROOT / rel
        if not path.is_file():
            failures.append({"path": rel, "reason": "missing"})
            continue
        count = line_count(path)
        rows.append({"path": rel, "lines": count, "ceiling": ceiling})
        if count > ceiling:
            failures.append({"path": rel, "reason": "monolith-growth", "lines": count, "ceiling": ceiling})

    ui = resolve_active_ui()
    ui_status = "PASS"
    if ui is None:
        ui_status = "ENVIRONMENT"
        if not args.portable:
            failures.append({"path": "<active-ui>", "reason": "unavailable"})
    else:
        for rel, ceiling in baseline["active_ui_ceilings"].items():
            path = ui / rel
            if not path.is_file():
                failures.append({"path": f"ui::{rel}", "reason": "missing"})
                continue
            count = line_count(path)
            rows.append({"path": f"ui::{rel}", "lines": count, "ceiling": ceiling})
            if count > ceiling:
                failures.append({"path": f"ui::{rel}", "reason": "monolith-growth", "lines": count, "ceiling": ceiling})

    result = {
        "schema": "aura.ci.architecture-gate.v1",
        "portable": args.portable,
        "ui_status": ui_status,
        "rows": rows,
        "failures": failures,
        "pass": not failures,
    }
    path = write_report("architecture_gate.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Report:", path)
    return 0 if result["pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
