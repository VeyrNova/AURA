# -*- coding: utf-8 -*-
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULT_JSON = HERE / "AURA_DISK_CLEANUP_AUDIT_RESULT.json"
RESULT_TXT = HERE / "AURA_DISK_CLEANUP_AUDIT_RESULT.txt"

AURA_ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[2]).resolve()
LOCALAPPDATA = Path(os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
USERPROFILE = Path(os.environ.get("USERPROFILE") or Path.home())
TEMP = Path(os.environ.get("TEMP", str(LOCALAPPDATA / "Temp")))

# Read-only audit. No path below is ever deleted or modified.
SAFE_RULES = [
    {
        "name": "pip_cache",
        "category": "SAFE_TO_CLEAN",
        "reason": "Cache de téléchargement pip. Les packages déjà installés dans le venv AURA ne dépendent pas de ce cache.",
        "paths": [
            LOCALAPPDATA / "pip" / "Cache",
        ],
    },
    {
        "name": "aura_test_temp_leftovers",
        "category": "SAFE_TO_CLEAN",
        "reason": "Restes de venv temporaires créés uniquement pour les tests de reproductibilité AURA.",
        "glob_parent": TEMP,
        "patterns": [
            "AURA_V086*",
            "AURA_V0_8_6*",
        ],
    },
    {
        "name": "pip_temp_leftovers",
        "category": "SAFE_TO_CLEAN",
        "reason": "Dossiers temporaires pip/build laissés après interruption ou fin de tests.",
        "glob_parent": TEMP,
        "patterns": [
            "pip-build-*",
            "pip-install-*",
            "pip-unpack-*",
            "pip-ephem-wheel-cache-*",
            "pip-modern-metadata-*",
        ],
    },
    {
        "name": "torch_inductor_cache",
        "category": "SAFE_TO_CLEAN",
        "reason": "Caches de compilation/runtime PyTorch régénérables.",
        "paths": [
            TEMP / "torchinductor_leclerc",
            USERPROFILE / ".cache" / "torch" / "inductor",
        ],
    },
    {
        "name": "python_bytecode_cache_project",
        "category": "SAFE_TO_CLEAN",
        "reason": "Caches __pycache__ générés automatiquement. Ils seront recréés si nécessaire.",
        "scan_pycache_under": AURA_ROOT,
    },
]

REVIEW_RULES = [
    {
        "name": "aura_patch_backups",
        "category": "REVIEW",
        "reason": "Backups de rollback. Ne pas supprimer en bloc : conserver au minimum les derniers points de retour utiles.",
        "paths": [
            AURA_ROOT / "_dev" / "backups",
        ],
    },
    {
        "name": "aura_logs",
        "category": "REVIEW",
        "reason": "Logs AURA. Les anciens peuvent être archivés/supprimés après vérification, mais les plus récents restent utiles au diagnostic.",
        "paths": [
            AURA_ROOT / "logs",
        ],
    },
    {
        "name": "huggingface_cache",
        "category": "REVIEW",
        "reason": "Peut contenir des modèles téléchargés. Supprimer uniquement des modèles identifiés comme inutiles.",
        "paths": [
            USERPROFILE / ".cache" / "huggingface",
            LOCALAPPDATA / "huggingface",
        ],
    },
    {
        "name": "torch_cache",
        "category": "REVIEW",
        "reason": "Peut contenir des modèles/checkpoints ou artefacts PyTorch réutilisés par AURA.",
        "paths": [
            USERPROFILE / ".cache" / "torch",
            LOCALAPPDATA / "torch",
        ],
    },
]

KEEP_RULES = [
    {
        "name": "aura_main_venv",
        "category": "KEEP",
        "reason": "Environnement Python principal certifié d'AURA.",
        "paths": [
            AURA_ROOT / "venv",
        ],
    },
    {
        "name": "aura_requirements_locks",
        "category": "KEEP",
        "reason": "Locks CORE/VOICE/GPU/FULL certifiés et métadonnées de reproductibilité.",
        "paths": [
            AURA_ROOT / "requirements" / "locks",
        ],
    },
    {
        "name": "aura_models_candidates",
        "category": "KEEP",
        "reason": "Emplacements susceptibles de contenir des modèles/voix. Audit de taille uniquement, aucune suppression recommandée.",
        "paths": [
            AURA_ROOT / "models",
            AURA_ROOT / "voice" / "models",
            AURA_ROOT / "tts_models",
        ],
    },
]

def fmt_bytes(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    for u in units:
        if f < 1024 or u == units[-1]:
            return f"{f:.2f} {u}"
        f /= 1024.0
    return f"{n} B"

def safe_stat(path: Path):
    try:
        return path.stat()
    except Exception:
        return None

def dir_size(path: Path):
    total = 0
    files = 0
    dirs = 0
    errors = 0
    newest = 0.0
    oldest = None

    if not path.exists():
        return {
            "exists": False,
            "bytes": 0,
            "files": 0,
            "dirs": 0,
            "errors": 0,
            "newest_mtime": None,
            "oldest_mtime": None,
        }

    if path.is_file():
        st = safe_stat(path)
        if not st:
            return {"exists": True, "bytes": 0, "files": 0, "dirs": 0, "errors": 1, "newest_mtime": None, "oldest_mtime": None}
        return {
            "exists": True,
            "bytes": st.st_size,
            "files": 1,
            "dirs": 0,
            "errors": 0,
            "newest_mtime": st.st_mtime,
            "oldest_mtime": st.st_mtime,
        }

    stack = [path]
    while stack:
        current = stack.pop()
        dirs += 1
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_symlink():
                            continue
                        st = entry.stat(follow_symlinks=False)
                        mt = st.st_mtime
                        newest = max(newest, mt)
                        oldest = mt if oldest is None else min(oldest, mt)
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(Path(entry.path))
                        elif entry.is_file(follow_symlinks=False):
                            total += st.st_size
                            files += 1
                    except Exception:
                        errors += 1
        except Exception:
            errors += 1

    return {
        "exists": True,
        "bytes": total,
        "files": files,
        "dirs": dirs,
        "errors": errors,
        "newest_mtime": newest or None,
        "oldest_mtime": oldest,
    }

def iso_ts(ts):
    if not ts:
        return None
    try:
        return dt.datetime.fromtimestamp(ts).isoformat(timespec="seconds")
    except Exception:
        return None

def row_for(path: Path, category: str, rule_name: str, reason: str):
    info = dir_size(path)
    return {
        "rule": rule_name,
        "category": category,
        "reason": reason,
        "path": str(path),
        "exists": info["exists"],
        "bytes": info["bytes"],
        "human": fmt_bytes(info["bytes"]),
        "files": info["files"],
        "dirs": info["dirs"],
        "errors": info["errors"],
        "newest_mtime": iso_ts(info["newest_mtime"]),
        "oldest_mtime": iso_ts(info["oldest_mtime"]),
    }

def resolve_rule(rule):
    rows = []
    if "paths" in rule:
        for p in rule["paths"]:
            rows.append(row_for(p, rule["category"], rule["name"], rule["reason"]))

    if "glob_parent" in rule:
        parent = rule["glob_parent"]
        seen = set()
        if parent.exists():
            for pattern in rule["patterns"]:
                try:
                    for p in parent.glob(pattern):
                        key = str(p).casefold()
                        if key in seen:
                            continue
                        seen.add(key)
                        rows.append(row_for(p, rule["category"], rule["name"], rule["reason"]))
                except Exception:
                    pass

    if "scan_pycache_under" in rule:
        root = rule["scan_pycache_under"]
        if root.exists():
            seen = set()
            for current, dirnames, filenames in os.walk(root):
                # Avoid descending into the certified venv; its bytecode is part of the installed environment footprint.
                rel = Path(current)
                if rel == AURA_ROOT / "venv" or (AURA_ROOT / "venv") in rel.parents:
                    dirnames[:] = []
                    continue
                # Avoid backup trees; measured separately as REVIEW.
                if rel == AURA_ROOT / "_dev" / "backups" or (AURA_ROOT / "_dev" / "backups") in rel.parents:
                    dirnames[:] = []
                    continue
                if rel.name == "__pycache__":
                    key = str(rel).casefold()
                    if key not in seen:
                        seen.add(key)
                        rows.append(row_for(rel, rule["category"], rule["name"], rule["reason"]))
                    dirnames[:] = []
    return rows

def top_children(path: Path, limit=20):
    out = []
    if not path.exists() or not path.is_dir():
        return out
    try:
        children = list(path.iterdir())
    except Exception:
        return out
    for child in children:
        info = dir_size(child)
        if info["exists"]:
            out.append({
                "path": str(child),
                "bytes": info["bytes"],
                "human": fmt_bytes(info["bytes"]),
                "files": info["files"],
                "dirs": info["dirs"],
            })
    out.sort(key=lambda r: r["bytes"], reverse=True)
    return out[:limit]

def drive_space(path: Path):
    try:
        usage = shutil.disk_usage(str(path))
        return {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "total": fmt_bytes(usage.total),
            "used": fmt_bytes(usage.used),
            "free": fmt_bytes(usage.free),
            "free_percent": round((usage.free / usage.total * 100.0), 2) if usage.total else None,
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

def pip_cache_info():
    py = AURA_ROOT / "venv" / "Scripts" / "python.exe"
    result = {"python": str(py), "available": py.is_file()}
    if not py.is_file():
        return result
    for name, args in (
        ("dir", [str(py), "-m", "pip", "cache", "dir"]),
        ("info", [str(py), "-m", "pip", "cache", "info"]),
    ):
        try:
            cp = subprocess.run(args, capture_output=True, text=True, timeout=60)
            result[name] = {
                "returncode": cp.returncode,
                "stdout": cp.stdout.strip(),
                "stderr": cp.stderr.strip(),
            }
        except Exception as exc:
            result[name] = {"error": f"{type(exc).__name__}: {exc}"}
    return result

def backup_breakdown():
    root = AURA_ROOT / "_dev" / "backups"
    rows = top_children(root, limit=100)
    return rows

def log_breakdown():
    root = AURA_ROOT / "logs"
    return top_children(root, limit=100)

def main():
    started = dt.datetime.now()
    rows = []
    for rule in SAFE_RULES + REVIEW_RULES + KEEP_RULES:
        rows.extend(resolve_rule(rule))

    # Deduplicate exact path/category pairs.
    dedup = {}
    for row in rows:
        key = (row["category"], row["path"].casefold())
        if key not in dedup or row["bytes"] > dedup[key]["bytes"]:
            dedup[key] = row
    rows = list(dedup.values())
    rows.sort(key=lambda r: (r["category"], -r["bytes"], r["path"].casefold()))

    totals = {}
    for cat in ("SAFE_TO_CLEAN", "REVIEW", "KEEP"):
        total = sum(r["bytes"] for r in rows if r["category"] == cat and r["exists"])
        totals[cat] = {"bytes": total, "human": fmt_bytes(total)}

    disk = drive_space(AURA_ROOT if AURA_ROOT.exists() else Path("C:/"))

    result = {
        "schema": "aura.disk-cleanup-audit.v1",
        "phase": "AURA Disk Cleanup Audit — READ ONLY",
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": dt.datetime.now().isoformat(timespec="seconds"),
        "read_only": True,
        "deletions_performed": 0,
        "files_modified": 0,
        "aura_root": str(AURA_ROOT),
        "temp_root": str(TEMP),
        "disk": disk,
        "pip_cache": pip_cache_info(),
        "totals": totals,
        "rows": rows,
        "aura_backup_children": backup_breakdown(),
        "aura_log_children": log_breakdown(),
        "recommendation": {
            "safe_recoverable_bytes": totals["SAFE_TO_CLEAN"]["bytes"],
            "safe_recoverable": totals["SAFE_TO_CLEAN"]["human"],
            "review_bytes": totals["REVIEW"]["bytes"],
            "review": totals["REVIEW"]["human"],
            "important_note": "SAFE_TO_CLEAN est conçu pour être régénérable. REVIEW nécessite validation avant toute suppression. KEEP ne doit pas être nettoyé automatiquement.",
        },
    }

    RESULT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = []
    lines.append("=" * 100)
    lines.append("AURA DISK CLEANUP AUDIT — READ ONLY")
    lines.append("=" * 100)
    lines.append("")
    lines.append(f"AURA root : {AURA_ROOT}")
    lines.append(f"TEMP      : {TEMP}")
    lines.append(f"Disk free : {disk.get('free', 'n/a')} ({disk.get('free_percent', 'n/a')}%)")
    lines.append("")
    lines.append(f"SAFE TO CLEAN : {totals['SAFE_TO_CLEAN']['human']}")
    lines.append(f"REVIEW        : {totals['REVIEW']['human']}")
    lines.append(f"KEEP measured : {totals['KEEP']['human']}")
    lines.append("")
    for cat in ("SAFE_TO_CLEAN", "REVIEW", "KEEP"):
        lines.append("-" * 100)
        lines.append(cat)
        lines.append("-" * 100)
        category_rows = [r for r in rows if r["category"] == cat and r["exists"] and r["bytes"] > 0]
        if not category_rows:
            lines.append("(aucun espace mesurable)")
        for r in category_rows:
            lines.append(f"{r['human']:>12}  {r['path']}")
            lines.append(f"              {r['reason']}")
        lines.append("")
    lines.append("=" * 100)
    lines.append("AUCUNE SUPPRESSION N'A ETE EFFECTUEE.")
    lines.append("=" * 100)

    RESULT_TXT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    print("")
    print("JSON :", RESULT_JSON)
    print("TXT  :", RESULT_TXT)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
