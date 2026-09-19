
from __future__ import annotations
from pathlib import Path
import argparse, json, os, shlex, sys

ROOT=Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from runtime.aura_repository_context import RepositoryScanner, build_context_pack
from runtime.aura_developer_planner import build_development_plan
from runtime.aura_patch_transaction_engine import propose_edits, validate_in_staging, apply_approved, rollback_receipt

def _load(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def _dump(obj,path=None):
    text=json.dumps(obj,indent=2,ensure_ascii=False)
    if path: Path(path).write_text(text,encoding="utf-8")
    else: print(text)

def main():
    p=argparse.ArgumentParser(description="AURA Developer Fabric repository transaction CLI")
    sub=p.add_subparsers(dest="cmd",required=True)
    s=sub.add_parser("scan"); s.add_argument("--workspace",required=True)
    c=sub.add_parser("context"); c.add_argument("--workspace",required=True); c.add_argument("--query",default=""); c.add_argument("--max-bytes",type=int,default=262144)
    pl=sub.add_parser("plan"); pl.add_argument("--workspace",required=True); pl.add_argument("--task",required=True); pl.add_argument("--query",default="")
    pr=sub.add_parser("propose"); pr.add_argument("--workspace",required=True); pr.add_argument("--edits",required=True); pr.add_argument("--task",default=""); pr.add_argument("--out")
    va=sub.add_parser("validate"); va.add_argument("--proposal",required=True); va.add_argument("--test-json",action="append",required=True); va.add_argument("--out")
    ap=sub.add_parser("apply"); ap.add_argument("--proposal",required=True); ap.add_argument("--validation",required=True); ap.add_argument("--approve",required=True); ap.add_argument("--out")
    rb=sub.add_parser("rollback"); rb.add_argument("--receipt",required=True)
    a=p.parse_args()
    if a.cmd=="scan": _dump(RepositoryScanner(a.workspace).scan()); return 0
    if a.cmd=="context": _dump(build_context_pack(a.workspace,query=a.query,max_bytes=a.max_bytes)); return 0
    if a.cmd=="plan":
        ctx=build_context_pack(a.workspace,query=a.query or a.task); _dump(build_development_plan(a.task,ctx)); return 0
    if a.cmd=="propose":
        edits=_load(a.edits); obj=propose_edits(a.workspace,edits,task=a.task); _dump(obj,a.out); return 0
    if a.cmd=="validate":
        prop=_load(a.proposal); commands=[json.loads(x) for x in a.test_json]; obj=validate_in_staging(prop,commands); _dump(obj,a.out); return 0 if obj["passed"] else 6
    if a.cmd=="apply":
        prop=_load(a.proposal); val=_load(a.validation); obj=apply_approved(prop,val,approval_phrase=a.approve); _dump(obj,a.out); return 0
    if a.cmd=="rollback":
        _dump(rollback_receipt(_load(a.receipt))); return 0
    return 2
if __name__=="__main__": raise SystemExit(main())
