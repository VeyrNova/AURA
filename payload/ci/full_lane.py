# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, datetime as dt, json, os, re, subprocess, sys, time
from pathlib import Path
from common import ROOT, write_report

ENV_PATTERNS = (
    "ModuleNotFoundError", "No module named", "ImportError while importing",
    "DLL load failed", "Could not find", "not installed", "CUDA is not available",
)
SMOKE_NAMES = [
    "test_security_policy.py",
    "test_router_security.py",
    "test_memory_intents_v060.py",
    "test_internet_tools_v070.py",
    "test_microphone_selection.py",
    "test_resource_guardian_v062.py",
    "test_redaction.py",
    "test_validators.py",
]

def classify(cp, timed_out=False):
    if timed_out:
        return "TIMEOUT"
    if cp.returncode == 0:
        text = (cp.stdout or "") + "\n" + (cp.stderr or "")
        if re.search(r"\bskipped\b", text, re.I) and not re.search(r"\bpassed\b", text, re.I):
            return "SKIP"
        return "PASS"
    text = (cp.stdout or "") + "\n" + (cp.stderr or "")
    if cp.returncode == 5:
        return "SKIP"
    if any(token.casefold() in text.casefold() for token in ENV_PATTERNS):
        return "ENVIRONMENT"
    return "FAIL"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=("smoke", "canonical"), default="smoke")
    ap.add_argument("--timeout", type=int, default=180)
    ap.add_argument("--strict-environment", action="store_true")
    args = ap.parse_args()

    tests_dir = ROOT / "tests"
    if args.mode == "smoke":
        files = [tests_dir / n for n in SMOKE_NAMES if (tests_dir / n).is_file()]
    else:
        files = sorted(tests_dir.glob("test_*.py"))

    rows = []
    started = dt.datetime.now().isoformat()
    for idx, path in enumerate(files, 1):
        print(f"[{idx}/{len(files)}] {path.name}")
        t0 = time.monotonic()
        try:
            cp = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", str(path)],
                cwd=str(ROOT), capture_output=True, text=True, timeout=args.timeout
            )
            status = classify(cp)
            rows.append({
                "file": path.relative_to(ROOT).as_posix(),
                "status": status,
                "returncode": cp.returncode,
                "seconds": round(time.monotonic() - t0, 3),
                "stdout_tail": cp.stdout[-6000:],
                "stderr_tail": cp.stderr[-4000:],
            })
        except subprocess.TimeoutExpired as exc:
            rows.append({
                "file": path.relative_to(ROOT).as_posix(),
                "status": "TIMEOUT",
                "returncode": None,
                "seconds": round(time.monotonic() - t0, 3),
                "stdout_tail": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
                "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
            })

    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    fail = counts.get("FAIL", 0) + counts.get("TIMEOUT", 0)
    if args.strict_environment:
        fail += counts.get("ENVIRONMENT", 0)

    result = {
        "schema": "aura.ci.full-lane.v0861.v1",
        "mode": args.mode,
        "started_at": started,
        "finished_at": dt.datetime.now().isoformat(),
        "strict_environment": args.strict_environment,
        "counts": counts,
        "files": rows,
        "pass": fail == 0,
        "note": "ENVIRONMENT is reported separately; use --strict-environment after dependency lock v0.8.6.2.",
    }
    report = write_report(f"full_lane_{args.mode}_result.json", result)
    print("=" * 100)
    print("AURA v0.8.6.1 — FULL LANE", args.mode.upper())
    print("Counts:", counts)
    print("Report:", report)
    print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
    return 0 if result["pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
