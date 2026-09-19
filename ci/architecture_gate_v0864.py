from __future__ import annotations
import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "ui" / "main_window.py"
WORKER = ROOT / "ui" / "workers" / "realtime_tts_worker.py"
INIT = ROOT / "ui" / "workers" / "__init__.py"
REPORT = ROOT / "ci" / "reports" / "architecture_gate_v0864.json"

EXPECTED_MAIN = "b95314824d32f93f1f26b82368440fbc55f225f4117aaee77d909e5c0cc65f4d"
EXPECTED_WORKER = "d3438289116983beebfcc7d0f680017ce660753e64e9bd92f28eaeaf180e2df3"

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

checks = []
def add(name, ok, detail=""):
    checks.append({"name": name, "pass": bool(ok), "detail": str(detail)})

add("main_window present", MAIN.is_file(), MAIN)
add("worker present", WORKER.is_file(), WORKER)
add("workers package present", INIT.is_file(), INIT)

if MAIN.is_file() and WORKER.is_file():
    main_src = MAIN.read_text(encoding="utf-8-sig")
    worker_src = WORKER.read_text(encoding="utf-8-sig")
    main_tree = ast.parse(main_src, filename=str(MAIN))
    worker_tree = ast.parse(worker_src, filename=str(WORKER))

    main_classes = [n.name for n in main_tree.body if isinstance(n, ast.ClassDef)]
    worker_classes = [
        n for n in worker_tree.body
        if isinstance(n, ast.ClassDef) and n.name == "RealtimeTTSWorker"
    ]

    compat_import = False
    for node in main_tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == "ui.workers.realtime_tts_worker":
            if any(alias.name == "RealtimeTTSWorker" for alias in node.names):
                compat_import = True

    reverse_import = any(
        isinstance(node, ast.ImportFrom) and node.module == "ui.main_window"
        for node in ast.walk(worker_tree)
    ) or any(
        isinstance(node, ast.Import) and any(alias.name == "ui.main_window" for alias in node.names)
        for node in ast.walk(worker_tree)
    )

    method_count = 0
    if len(worker_classes) == 1:
        method_count = sum(
            1 for item in worker_classes[0].body
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
        )

    add("main_window exact modularized hash", sha(MAIN) == EXPECTED_MAIN, sha(MAIN))
    add("worker exact certified hash", sha(WORKER) == EXPECTED_WORKER, sha(WORKER))
    add("RealtimeTTSWorker removed from main_window", "RealtimeTTSWorker" not in main_classes, main_classes.count("RealtimeTTSWorker"))
    add("compatibility import preserved", compat_import, compat_import)
    add("worker owns RealtimeTTSWorker exactly once", len(worker_classes) == 1, len(worker_classes))
    add("worker method count preserved", method_count == 8, method_count)
    add("no reverse import to main_window", not reverse_import, reverse_import)
    add("main_window LOC reduced", len(main_src.splitlines()) == 5767, len(main_src.splitlines()))
    add("worker module LOC bounded", 180 <= len(worker_src.splitlines()) <= 260, len(worker_src.splitlines()))

    cp1 = subprocess.run(
        [sys.executable, "-m", "py_compile", str(MAIN), str(WORKER)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    add("modularized sources compile", cp1.returncode == 0, cp1.stdout.strip())

    cp2 = subprocess.run(
        [
            sys.executable,
            "-c",
            "import ui.main_window as m;"
            "from ui.workers.realtime_tts_worker import RealtimeTTSWorker as W;"
            "assert m.RealtimeTTSWorker is W;"
            "print(W.__module__)"
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    add("public import identity preserved", cp2.returncode == 0, cp2.stdout.strip())

passed = sum(1 for c in checks if c["pass"])
failed = len(checks) - passed
result = {
    "schema": "aura.ci.architecture-gate.v0864.v1",
    "pass": failed == 0,
    "checks_total": len(checks),
    "checks_passed": passed,
    "checks_failed": failed,
    "checks": checks,
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(result, indent=2), encoding="utf-8")
for c in checks:
    print(("[PASS] " if c["pass"] else "[FAIL] ") + c["name"] + " - " + c["detail"])
print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
raise SystemExit(0 if result["pass"] else 2)
