from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PARENT_CERT=ROOT/"AURA_V0_9_1_FINAL_CERTIFICATE.json"
def run(path,*args):
    return subprocess.run([sys.executable,str(path),*args],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,encoding="utf-8",errors="replace")
checks=[]
cert=json.loads(PARENT_CERT.read_text(encoding="utf-8-sig")); checks.append(("v0.9.1 certified parent",cert.get("status")=="CERTIFIED"))
routes=[
("visual version surfaces",ROOT/"tests"/"invariants"/"test_product_version_surfaces_v0871.py",()),
("spoken product version",ROOT/"tests"/"invariants"/"test_spoken_product_version_v0872.py",()),
("MissionEngine reverified v0.9.2",ROOT/"tests"/"invariants"/"test_mission_engine_v088.py",()),
("Action Receipts reverified v0.9.2",ROOT/"tests"/"invariants"/"test_action_receipts_v089.py",()),
("Integration Architecture reverified v0.9.2",ROOT/"tests"/"invariants"/"test_integration_architecture_v090.py",()),
("Email Provider reverified v0.9.2",ROOT/"tests"/"invariants"/"test_email_provider_v091.py",()),
("Calendar Provider v0.9.2",ROOT/"tests"/"invariants"/"test_calendar_provider_v092.py",()),
("MemoryKernel v2",ROOT/"tests"/"invariants"/"test_memorykernel_v2_v087.py",()),
("SecurityPolicyEngine v2",ROOT/"tests"/"invariants"/"test_security_policy_v2_v0866.py",()),
("runtime performance",ROOT/"tests"/"invariants"/"test_runtime_performance_v0867.py",()),
("source-driven UI",ROOT/"tools"/"ui_source_build_v0865.py",("--check",)),]
for name,path,args in routes:
    cp=run(path,*args); checks.append((name,cp.returncode==0))
passed=sum(1 for _,ok in checks if ok)
for name,ok in checks: print(("[PASS] " if ok else "[FAIL] ")+name)
print("PASS GLOBAL" if passed==len(checks) else "FAIL GLOBAL")
raise SystemExit(0 if passed==len(checks) else 2)
