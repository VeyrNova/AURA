# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import datetime as dt
import heapq
import json
import os
import stat
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_JSON = HERE / "AURA_GLOBAL_DISK_AUDIT_RESULT.json"
RESULT_TXT = HERE / "AURA_GLOBAL_DISK_AUDIT_RESULT.txt"

DRIVE = Path("C:/")
AURA = Path(r"C:\AURA GPT version")
USERPROFILE = Path(os.environ.get("USERPROFILE", r"C:\Users\Public"))
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA", str(USERPROFILE / "AppData" / "Local")))
APPDATA = Path(os.environ.get("APPDATA", str(USERPROFILE / "AppData" / "Roaming")))
PROGRAMDATA = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
TEMP = Path(os.environ.get("TEMP", str(LOCALAPPDATA / "Temp")))

FILE_ATTRIBUTE_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

# Aggregate directory sizes only through this depth relative to C:\.
# This gives a useful global Top 50 without storing every directory in RAM.
AGGREGATE_MAX_DEPTH = 6
TOP_FILES = 100
TOP_DIRS = 50

def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.2f} {u}"
        f /= 1024.0
    return f"{n} B"

def norm(p: Path) -> str:
    return os.path.normcase(os.path.abspath(str(p)))

def is_reparse(st) -> bool:
    attrs = getattr(st, "st_file_attributes", 0)
    return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)

def drive_usage():
    import shutil
    u = shutil.disk_usage(str(DRIVE))
    return {
        "total_bytes": u.total,
        "used_bytes": u.used,
        "free_bytes": u.free,
        "total": fmt_bytes(u.total),
        "used": fmt_bytes(u.used),
        "free": fmt_bytes(u.free),
        "free_percent": round(u.free / u.total * 100.0, 2) if u.total else None,
    }

def ancestor_keys(file_path: Path):
    try:
        rel = file_path.relative_to(DRIVE)
    except Exception:
        return []
    parts = rel.parts[:-1]  # directory components only
    keys = []
    # C:\ itself
    keys.append(str(DRIVE))
    upto = min(len(parts), AGGREGATE_MAX_DEPTH)
    cur = DRIVE
    for i in range(upto):
        cur = cur / parts[i]
        keys.append(str(cur))
    return keys

def scan_drive():
    dir_bytes = defaultdict(int)
    dir_files = defaultdict(int)
    dir_errors = defaultdict(int)
    top_files_heap = []  # (size, path, mtime)
    total_files = 0
    total_dirs = 0
    total_bytes = 0
    errors = []
    skipped_reparse = []
    started = dt.datetime.now()

    stack = [DRIVE]
    last_print = 0

    while stack:
        current = stack.pop()
        total_dirs += 1

        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        st = entry.stat(follow_symlinks=False)
                        ep = Path(entry.path)

                        if is_reparse(st) or entry.is_symlink():
                            if len(skipped_reparse) < 500:
                                skipped_reparse.append(str(ep))
                            continue

                        if entry.is_dir(follow_symlinks=False):
                            stack.append(ep)
                            continue

                        if entry.is_file(follow_symlinks=False):
                            size = st.st_size
                            total_files += 1
                            total_bytes += size

                            for k in ancestor_keys(ep):
                                dir_bytes[k] += size
                                dir_files[k] += 1

                            item = (size, str(ep), st.st_mtime)
                            if len(top_files_heap) < TOP_FILES:
                                heapq.heappush(top_files_heap, item)
                            elif size > top_files_heap[0][0]:
                                heapq.heapreplace(top_files_heap, item)

                    except (PermissionError, FileNotFoundError, OSError) as exc:
                        if len(errors) < 2000:
                            errors.append({
                                "path": entry.path,
                                "error": f"{type(exc).__name__}: {exc}",
                            })
                        for k in ancestor_keys(Path(entry.path)):
                            dir_errors[k] += 1

        except (PermissionError, FileNotFoundError, OSError) as exc:
            if len(errors) < 2000:
                errors.append({
                    "path": str(current),
                    "error": f"{type(exc).__name__}: {exc}",
                })
            # attribute the directory-level error to known ancestors
            fake = current / "_"
            for k in ancestor_keys(fake):
                dir_errors[k] += 1

        if total_files - last_print >= 100000:
            last_print = total_files
            elapsed = (dt.datetime.now() - started).total_seconds()
            print(f"[SCAN] {total_files:,} files / {total_dirs:,} dirs / {fmt_bytes(total_bytes)} scanned / {elapsed:.0f}s")

    dir_rows = []
    for p, size in dir_bytes.items():
        # Skip drive root itself from ranking.
        if norm(Path(p)) == norm(DRIVE):
            continue
        dir_rows.append({
            "path": p,
            "bytes": size,
            "human": fmt_bytes(size),
            "files": dir_files[p],
            "errors": dir_errors[p],
        })
    dir_rows.sort(key=lambda r: r["bytes"], reverse=True)

    top_files = [
        {
            "path": p,
            "bytes": s,
            "human": fmt_bytes(s),
            "mtime": dt.datetime.fromtimestamp(mt).isoformat(timespec="seconds"),
        }
        for s, p, mt in sorted(top_files_heap, reverse=True)
    ]

    return {
        "scanned_files": total_files,
        "scanned_dirs": total_dirs,
        "scanned_bytes": total_bytes,
        "scanned_human": fmt_bytes(total_bytes),
        "top_directories": dir_rows[:TOP_DIRS],
        "top_files": top_files,
        "errors": errors,
        "error_count_captured": len(errors),
        "skipped_reparse_points": skipped_reparse,
        "skipped_reparse_count_captured": len(skipped_reparse),
    }

def path_measurement_from_global(path: Path, top_lookup):
    pnorm = norm(path)
    # Exact aggregate match where available.
    for k, row in top_lookup.items():
        if norm(Path(k)) == pnorm:
            return dict(row)
    # If deeper than aggregate depth, we need a dedicated lightweight scan.
    return measure_tree(path)

def measure_tree(path: Path):
    total = 0
    files = 0
    dirs = 0
    errors = 0
    if not path.exists():
        return {"path": str(path), "exists": False, "bytes": 0, "human": "0.00 B", "files": 0, "dirs": 0, "errors": 0}

    if path.is_file():
        try:
            st = path.stat()
            return {"path": str(path), "exists": True, "bytes": st.st_size, "human": fmt_bytes(st.st_size), "files": 1, "dirs": 0, "errors": 0}
        except Exception:
            return {"path": str(path), "exists": True, "bytes": 0, "human": "0.00 B", "files": 0, "dirs": 0, "errors": 1}

    stack = [path]
    while stack:
        cur = stack.pop()
        dirs += 1
        try:
            with os.scandir(cur) as it:
                for e in it:
                    try:
                        st = e.stat(follow_symlinks=False)
                        if is_reparse(st) or e.is_symlink():
                            continue
                        if e.is_dir(follow_symlinks=False):
                            stack.append(Path(e.path))
                        elif e.is_file(follow_symlinks=False):
                            total += st.st_size
                            files += 1
                    except Exception:
                        errors += 1
        except Exception:
            errors += 1
    return {"path": str(path), "exists": True, "bytes": total, "human": fmt_bytes(total), "files": files, "dirs": dirs, "errors": errors}

def known_candidates(top_lookup):
    safe = []
    review = []
    keep = []

    def add(bucket, name, path, reason):
        m = path_measurement_from_global(path, top_lookup)
        if m["exists"] and m["bytes"] > 0:
            m.update({"name": name, "reason": reason})
            bucket.append(m)

    # SAFE CACHE: regenerable caches. Audit recommendation only, not deletion.
    add(safe, "pip cache", LOCALAPPDATA / "pip" / "Cache",
        "Cache de téléchargement pip régénérable.")
    add(safe, "D3DSCache", LOCALAPPDATA / "D3DSCache",
        "Cache Direct3D régénérable.")
    add(safe, "NVIDIA DXCache", LOCALAPPDATA / "NVIDIA" / "DXCache",
        "Cache shaders NVIDIA régénérable.")
    add(safe, "NVIDIA GLCache", LOCALAPPDATA / "NVIDIA" / "GLCache",
        "Cache OpenGL NVIDIA régénérable.")
    add(safe, "NVIDIA ComputeCache", LOCALAPPDATA / "NVIDIA" / "ComputeCache",
        "Cache de calcul NVIDIA régénérable.")
    add(safe, "CrashDumps", LOCALAPPDATA / "CrashDumps",
        "Dumps de crash. Utiles seulement pour diagnostic.")
    add(safe, "npm cache", LOCALAPPDATA / "npm-cache",
        "Cache npm régénérable.")
    add(safe, "uv cache", LOCALAPPDATA / "uv" / "cache",
        "Cache uv régénérable.")

    browser_roots = [
        ("Chrome Cache", LOCALAPPDATA / "Google" / "Chrome" / "User Data" / "Default" / "Cache"),
        ("Chrome Code Cache", LOCALAPPDATA / "Google" / "Chrome" / "User Data" / "Default" / "Code Cache"),
        ("Chrome GPUCache", LOCALAPPDATA / "Google" / "Chrome" / "User Data" / "Default" / "GPUCache"),
        ("Edge Cache", LOCALAPPDATA / "Microsoft" / "Edge" / "User Data" / "Default" / "Cache"),
        ("Edge Code Cache", LOCALAPPDATA / "Microsoft" / "Edge" / "User Data" / "Default" / "Code Cache"),
        ("Edge GPUCache", LOCALAPPDATA / "Microsoft" / "Edge" / "User Data" / "Default" / "GPUCache"),
    ]
    for name, p in browser_roots:
        add(safe, name, p, "Cache navigateur régénérable; fermer le navigateur avant nettoyage.")

    # REVIEW: potentially large but may contain useful/user data.
    add(review, "User TEMP", TEMP,
        "Fichiers temporaires. Nettoyage possible avec prudence après fermeture des applications/reboot.")
    add(review, "Downloads", USERPROFILE / "Downloads",
        "Fichiers utilisateur; examiner avant suppression.")
    add(review, "Recycle Bin", DRIVE / "$Recycle.Bin",
        "Corbeille; contenu supprimable si plus nécessaire.")
    add(review, "Windows Update Download", Path(r"C:\Windows\SoftwareDistribution\Download"),
        "Cache Windows Update; ne pas supprimer à chaud sans procédure adaptée.")
    add(review, "Windows Temp", Path(r"C:\Windows\Temp"),
        "Temporaires Windows; certains fichiers peuvent être en cours d'utilisation.")
    add(review, "Hugging Face cache", USERPROFILE / ".cache" / "huggingface",
        "Peut contenir des modèles IA; supprimer seulement ceux identifiés comme inutiles.")
    add(review, "Torch cache", USERPROFILE / ".cache" / "torch",
        "Peut contenir modèles/checkpoints/caches PyTorch.")
    add(review, "Ollama models", USERPROFILE / ".ollama" / "models",
        "Modèles Ollama locaux; potentiellement très volumineux et utilisés par AURA.")
    add(review, "Docker Desktop data", LOCALAPPDATA / "Docker",
        "Peut contenir images, volumes et VM Docker.")
    add(review, "Docker user data", USERPROFILE / ".docker",
        "Configuration/cache Docker; examiner avant suppression.")
    add(review, "WSL packages", LOCALAPPDATA / "Packages",
        "Peut contenir distributions WSL et données d'applications Microsoft Store.")
    add(review, "AURA _patch_backups", AURA / "_patch_backups",
        "Backups anciens AURA; audit précédent indique faible taille, à conserver si utiles.")
    add(review, "AURA logs", AURA / "logs",
        "Logs AURA; anciens logs peuvent être archivés.")
    add(review, "AURA _dev backups", AURA / "_dev" / "backups",
        "Rollbacks récents AURA; conserver les derniers points utiles.")

    # KEEP / INFORMATIONAL.
    add(keep, "AURA main venv", AURA / "venv",
        "Environnement Python certifié d'AURA.")
    add(keep, "AURA models", AURA / "models",
        "Modèles utilisés par AURA.")
    add(keep, "AURA exact locks", AURA / "requirements" / "locks",
        "Locks CORE/VOICE/GPU/FULL certifiés.")
    add(keep, "Windows Installer", Path(r"C:\Windows\Installer"),
        "Cache MSI système critique; ne pas supprimer manuellement.")
    add(keep, "ProgramData Package Cache", PROGRAMDATA / "Package Cache",
        "Cache d'installateurs/réparation; ne pas supprimer aveuglément.")

    for group in (safe, review, keep):
        group.sort(key=lambda r: r["bytes"], reverse=True)
    return safe, review, keep

def root_special_files():
    rows = []
    for name in ("hiberfil.sys", "pagefile.sys", "swapfile.sys", "MEMORY.DMP"):
        p = DRIVE / name
        try:
            st = p.stat()
            rows.append({
                "path": str(p),
                "bytes": st.st_size,
                "human": fmt_bytes(st.st_size),
                "classification": "SYSTEM_KEEP_OR_CONFIGURE",
                "reason": "Fichier système. Ne pas supprimer manuellement; configurer via Windows si nécessaire.",
            })
        except Exception:
            pass
    rows.sort(key=lambda r: r["bytes"], reverse=True)
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="Scan complet C:\\ (recommandé)")
    args = ap.parse_args()

    started = dt.datetime.now()
    print("=" * 110)
    print("AURA GLOBAL DISK AUDIT — READ ONLY")
    print("=" * 110)
    print("Aucune suppression. Aucun fichier modifié.")
    print("")
    print("Scan complet de C:\\ en cours. Selon le nombre de fichiers, cela peut prendre plusieurs minutes.")
    print("")

    scan = scan_drive()
    top_lookup = {r["path"]: r for r in scan["top_directories"]}

    # Build extra lookup from all aggregate dirs is unavailable after truncation to top50;
    # dedicated measurements fill gaps for known candidates.
    safe, review, keep = known_candidates(top_lookup)
    special = root_special_files()

    safe_total = sum(r["bytes"] for r in safe)
    review_total = sum(r["bytes"] for r in review)
    keep_total = sum(r["bytes"] for r in keep)

    result = {
        "schema": "aura.global-disk-audit.v1",
        "phase": "AURA Global Disk Audit — READ ONLY",
        "read_only": True,
        "deletions_performed": 0,
        "files_modified": 0,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        "drive": drive_usage(),
        "scan": {
            "scanned_files": scan["scanned_files"],
            "scanned_dirs": scan["scanned_dirs"],
            "scanned_bytes": scan["scanned_bytes"],
            "scanned_human": scan["scanned_human"],
            "error_count_captured": scan["error_count_captured"],
            "skipped_reparse_count_captured": scan["skipped_reparse_count_captured"],
        },
        "top_directories": scan["top_directories"],
        "top_files": scan["top_files"],
        "cleanup_candidates": {
            "SAFE_CACHE": safe,
            "REVIEW": review,
            "KEEP": keep,
            "totals": {
                "safe_cache_bytes": safe_total,
                "safe_cache": fmt_bytes(safe_total),
                "review_bytes": review_total,
                "review": fmt_bytes(review_total),
                "keep_measured_bytes": keep_total,
                "keep_measured": fmt_bytes(keep_total),
            },
        },
        "system_root_files": special,
        "scan_errors_sample": scan["errors"],
        "skipped_reparse_points_sample": scan["skipped_reparse_points"],
        "notes": [
            "SAFE_CACHE signifie régénérable en principe; fermer les applications avant tout nettoyage.",
            "REVIEW nécessite une décision humaine ou une procédure spécifique.",
            "KEEP ne doit pas être supprimé manuellement.",
            "Les jonctions/reparse points ne sont pas suivis afin d'éviter les doubles comptages et boucles.",
            "Les erreurs d'accès Windows sont enregistrées mais n'interrompent pas l'audit.",
        ],
        "pass": True,
    }

    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "=" * 110,
        "AURA GLOBAL DISK AUDIT — READ ONLY",
        "=" * 110,
        "",
        f"Disk free       : {result['drive']['free']} ({result['drive']['free_percent']}%)",
        f"Scanned files   : {scan['scanned_files']:,}",
        f"Scanned dirs    : {scan['scanned_dirs']:,}",
        f"Scanned payload : {scan['scanned_human']}",
        "",
        f"SAFE_CACHE measured : {fmt_bytes(safe_total)}",
        f"REVIEW measured     : {fmt_bytes(review_total)}",
        "",
        "-" * 110,
        "TOP 50 DIRECTORIES",
        "-" * 110,
    ]
    for i, r in enumerate(scan["top_directories"], 1):
        lines.append(f"{i:>2}. {r['human']:>12}  files={r['files']:>9}  {r['path']}")

    lines += ["", "-" * 110, "TOP 100 FILES", "-" * 110]
    for i, r in enumerate(scan["top_files"], 1):
        lines.append(f"{i:>3}. {r['human']:>12}  {r['path']}")

    lines += ["", "-" * 110, "SAFE_CACHE CANDIDATES", "-" * 110]
    if not safe:
        lines.append("(none)")
    for r in safe:
        lines.append(f"{r['human']:>12}  {r['name']}  ->  {r['path']}")
        lines.append(f"              {r['reason']}")

    lines += ["", "-" * 110, "REVIEW CANDIDATES", "-" * 110]
    if not review:
        lines.append("(none)")
    for r in review:
        lines.append(f"{r['human']:>12}  {r['name']}  ->  {r['path']}")
        lines.append(f"              {r['reason']}")

    lines += ["", "-" * 110, "SYSTEM ROOT FILES", "-" * 110]
    if not special:
        lines.append("(none visible)")
    for r in special:
        lines.append(f"{r['human']:>12}  {r['path']}")

    lines += [
        "",
        "=" * 110,
        "AUCUNE SUPPRESSION N'A ETE EFFECTUEE.",
        "=" * 110,
        "",
        f"JSON: {RESULT_JSON}",
    ]

    RESULT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:25]))
    print("")
    print("Audit terminé.")
    print("JSON :", RESULT_JSON)
    print("TXT  :", RESULT_TXT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
