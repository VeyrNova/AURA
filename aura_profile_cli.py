from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from aura_profile_portability import (
    PROFILE_EXTENSION,
    export_profile,
    import_profile,
    latest_backup,
    preview_import,
    rollback_import,
)

def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))

def main():
    p=argparse.ArgumentParser(prog="aura-profile",description="AURA portable profile export / preview / import / rollback")
    sub=p.add_subparsers(dest="cmd",required=True)

    ex=sub.add_parser("export",help="Exporter un profil sans secrets")
    ex.add_argument("-o","--output")

    pv=sub.add_parser("preview",help="Prévisualiser un import sans modification")
    pv.add_argument("profile")

    im=sub.add_parser("import",help="Importer un profil avec backup")
    im.add_argument("profile")
    im.add_argument("--apply",action="store_true",help="Appliquer réellement l'import")

    rb=sub.add_parser("rollback",help="Restaurer un import précédent")
    rb.add_argument("--backup")
    rb.add_argument("--latest",action="store_true")

    args=p.parse_args()

    if args.cmd=="export":
        result=export_profile(args.output)
        emit(result)
        return 0
    if args.cmd=="preview":
        emit(preview_import(args.profile))
        return 0
    if args.cmd=="import":
        result=import_profile(args.profile,apply=args.apply)
        emit(result)
        if not args.apply:
            print("\n[AUCUNE MODIFICATION] Ajoutez --apply pour appliquer après validation.")
        return 0
    if args.cmd=="rollback":
        backup=Path(args.backup) if args.backup else (latest_backup() if args.latest else None)
        if backup is None:
            print("[BLOQUE] Indiquez --backup <dossier> ou --latest.",file=sys.stderr)
            return 2
        emit(rollback_import(backup))
        return 0
    return 1

if __name__=="__main__":
    raise SystemExit(main())
