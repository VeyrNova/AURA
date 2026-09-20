
from pathlib import Path
import argparse, json, os, sys
ROOT=Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parent).resolve()
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from runtime.aura_self_development_governance import assess_proposal, capability_snapshot
from runtime.aura_audit_ledger import AuditLedger

def main():
    p=argparse.ArgumentParser(description="AURA self-development governance inspector")
    sub=p.add_subparsers(dest="cmd",required=True)
    a=sub.add_parser("assess"); a.add_argument("proposal"); a.add_argument("--release-mode",action="store_true")
    sub.add_parser("audit-verify")
    sub.add_parser("capabilities")
    args=p.parse_args()
    if args.cmd=="capabilities":
        print(json.dumps(capability_snapshot(),indent=2)); return 0
    if args.cmd=="audit-verify":
        print(json.dumps(AuditLedger(ROOT).verify(),indent=2)); return 0
    proposal=json.loads(Path(args.proposal).read_text(encoding="utf-8"))
    print(json.dumps(assess_proposal(proposal,ROOT,release_mode=args.release_mode),indent=2,ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
