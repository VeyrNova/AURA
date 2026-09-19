# -*- coding: utf-8 -*-
from __future__ import annotations
import argparse, datetime as dt, json, subprocess, sys
from pathlib import Path
from common import ROOT, test_module_paths, run_invariant_module, compile_python_file, write_report

def run_child(script: Path, portable: bool):
    cmd = [sys.executable, str(script)]
    if portable:
        cmd.append("--portable")
    cp = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=90)
    return {
        "name": script.stem,
        "status": "PASS" if cp.returncode == 0 else "FAIL",
        "blocking": True,
        "returncode": cp.returncode,
        "stdout_tail": cp.stdout[-8000:],
        "stderr_tail": cp.stderr[-4000:],
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--portable", action="store_true", help="CI mode: active LocalAppData UI checks may be ENVIRONMENT/non-blocking.")
    args = ap.parse_args()
    started = dt.datetime.now().isoformat()

    compile_targets = [
        ROOT / "ui" / "main_window.py",
        ROOT / "core" / "intent_manager.py",
        ROOT / "tools" / "internet_manager.py",
        ROOT / "security" / "policy_engine.py",
        ROOT / "tools" / "safe_http.py",
        ROOT / "memory" / "manager.py",
        ROOT / "runtime" / "resource_guardian.py",
        ROOT / "voice" / "microphone.py",
        ROOT / "services" / "core_bridge.py",
        ROOT / "voice" / "xtts_tts.py",
    ]
    compile_rows = []
    for path in compile_targets:
        ok, detail = compile_python_file(path)
        compile_rows.append({"path": path.relative_to(ROOT).as_posix(), "status": "PASS" if ok else "FAIL", "detail": detail})

    checks = [run_invariant_module(path, portable=args.portable) for path in test_module_paths()]
    checks.append(run_child(ROOT / "ci" / "architecture_gate.py", args.portable))
    # dependency_probe has no --portable and intentionally fails only on NEW dependency debt.
    cp = subprocess.run(
        [sys.executable, str(ROOT / "ci" / "dependency_probe.py")],
        cwd=str(ROOT), capture_output=True, text=True, timeout=90
    )
    checks.append({
        "name": "dependency_probe",
        "status": "PASS" if cp.returncode == 0 else "FAIL",
        "blocking": True,
        "returncode": cp.returncode,
        "stdout_tail": cp.stdout[-8000:],
        "stderr_tail": cp.stderr[-4000:],
    })

    blocking_failures = [
        x for x in checks if x.get("status") == "FAIL" and x.get("blocking", True)
    ]
    blocking_environment = [
        x for x in checks if x.get("status") == "ENVIRONMENT" and x.get("blocking", True)
    ]
    compile_failures = [x for x in compile_rows if x["status"] != "PASS"]

    result = {
        "schema": "aura.ci.fast-lane.v0861.v1",
        "started_at": started,
        "finished_at": dt.datetime.now().isoformat(),
        "portable": args.portable,
        "compile": compile_rows,
        "checks": checks,
        "blocking_failures": [x["name"] for x in blocking_failures],
        "blocking_environment": [x["name"] for x in blocking_environment],
        "pass": not compile_failures and not blocking_failures and not blocking_environment,
    }
    report = write_report("fast_lane_result.json", result)
    print("=" * 100)
    print("AURA v0.8.6.1 — FAST LANE")
    print("=" * 100)
    for row in compile_rows:
        print(f"[{row['status']}] compile {row['path']}")
    for row in checks:
        print(f"[{row.get('status')}] {row.get('name')}")
    print("Report:", report)
    print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
    return 0 if result["pass"] else 2

if __name__ == "__main__":
    raise SystemExit(main())
