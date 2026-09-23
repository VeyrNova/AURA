
from __future__ import annotations
from pathlib import Path
import argparse, os, subprocess, sys
ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from runtime.aura_terminal_reduction_kernel import SavingsLedger, reduce_terminal_output

def main():
    p=argparse.ArgumentParser(description="AURA Terminal Reduction Kernel")
    p.add_argument("--raw",action="store_true")
    p.add_argument("command",nargs=argparse.REMAINDER)
    a=p.parse_args()
    cmd=list(a.command)
    if cmd and cmd[0]=="--": cmd=cmd[1:]
    if not cmd: p.error("command required after --")
    cp=subprocess.run(cmd,capture_output=True,text=True,errors="replace")
    raw=(cp.stdout or "")+(cp.stderr or "")
    if a.raw:
        sys.stdout.write(raw)
    else:
        result=reduce_terminal_output(" ".join(cmd),raw)
        sys.stdout.write(result.output)
        ledger=SavingsLedger(ROOT/"runtime"/"developer_fabric"/"trk"/"savings.jsonl")
        ledger.append(result,exit_code=cp.returncode)
    return cp.returncode
if __name__=="__main__": raise SystemExit(main())
