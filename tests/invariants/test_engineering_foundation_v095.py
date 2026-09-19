from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
PYTHON=Path(sys.executable)

gates=[
    ROOT/"tests"/"invariants"/"test_critical_baseline_v095.py",
    ROOT/"ci"/"architecture_gate_v095.py",
    ROOT/"tests"/"invariants"/"test_metadata_contract_v095.py",
    ROOT/"tests"/"invariants"/"test_color_charter_lock_v095.py",
]

for gate in gates:
    assert gate.is_file(), str(gate)
    cp=subprocess.run(
        [str(PYTHON),str(gate)],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        timeout=900,
    )
    assert cp.returncode==0, cp.stdout

print("[PASS] AURA v0.9.5 engineering foundation")
