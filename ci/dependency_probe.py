# -*- coding: utf-8 -*-
from __future__ import annotations

# AURA v0.8.6.2.2 — dependency declaration + exact CORE/VOICE/GPU/FULL lock gate.
# Runtime application imports must be represented by requirements/*.in.
# The v0.8.6.2.1 exact CORE/VOICE locks are also integrity-gated.

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from common import ROOT, read_text, write_report

STDLIB = set(getattr(sys, "stdlib_module_names", set())) | {
    "__future__", "winreg", "msvcrt", "winsound", "tkinter"
}
APP_DIRS = {
    "agent", "ai", "config", "consciousness", "core", "database",
    "grounding", "memory", "modules", "runtime", "security",
    "services", "tools", "ui", "voice",
}
APP_ROOT_FILES = {
    "adaptive_profile.py",
    "aura_profile_portability.py",
    "installed_model_policy.py",
    "launch_aura_ui_v0722_rc42.py",
    "main.py",
}
EXCLUDED_PARTS = {
    ".git", ".idea", ".vscode", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "venv", ".venv",
    "_patch_backups", "_dev", "backup", "backups",
    "tests", "ci", "scripts", "logs", "cache", "caches",
}
ALIASES = {
    "dotenv": "python-dotenv",
    "PIL": "pillow",
    "fitz": "pymupdf",
    "cv2": "opencv-python",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "bs4": "beautifulsoup4",
    "serial": "pyserial",
    "docx": "python-docx",
    "faster_whisper": "faster-whisper",
    "TTS": "coqui-tts",
    "piper": "piper-tts",
    "PyPDF2": "pypdf2",
}
DECLARED_IMPORT_ONLY = {"chatterbox"}

DECLARATION_FILES = [
    ROOT / "requirements.txt",
    ROOT / "requirements" / "core.in",
    ROOT / "requirements" / "voice.in",
    ROOT / "requirements" / "gpu-cu130.in",
    ROOT / "requirements" / "documents.optional.in",
]

EXPECTED_LOCK_SCHEMA = "aura.dependency-lock.v0862.2.v1"
EXPECTED_LOCK_PHASE = "AURA v0.8.6.2.2"
EXPECTED_PYTHON = "3.14.7"
EXPECTED_LOCK_COUNTS = {"core": 11, "voice": 107, "gpu": 6, "full": 113}

def _is_vendor(part: str) -> bool:
    f = part.casefold()
    return (
        f in {"vendor", "vendors", "third_party", "third-party"}
        or f.endswith("_vendor")
    )

def _runtime_files():
    rows = []
    for dirname in sorted(APP_DIRS):
        base = ROOT / dirname
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            rel = path.relative_to(ROOT)
            parts = [x.casefold() for x in rel.parts[:-1]]
            if any(x in EXCLUDED_PARTS for x in parts):
                continue
            if any(_is_vendor(x) for x in rel.parts[:-1]):
                continue
            rows.append(path)
    for filename in sorted(APP_ROOT_FILES):
        path = ROOT / filename
        if path.is_file():
            rows.append(path)
    return sorted(set(rows), key=lambda p: p.as_posix().casefold())

def _local_roots(files):
    local = set(APP_DIRS)
    local.update(Path(x).stem for x in APP_ROOT_FILES if x.endswith(".py"))
    for path in files:
        rel = path.relative_to(ROOT)
        local.add(path.stem)
        for part in rel.parts[:-1]:
            if part.isidentifier():
                local.add(part)
    return local

def _declared_distributions():
    declared = set()
    sources = {}
    for path in DECLARATION_FILES:
        if not path.is_file():
            continue
        entries = []
        for raw in read_text(path).splitlines():
            item = raw.strip()
            if not item or item.startswith("#"):
                continue
            name = re.split(r"[<>=!~\[\]\s]", item, 1)[0]
            key = name.casefold().replace("_", "-")
            if key:
                declared.add(key)
                entries.append(name)
        sources[path.relative_to(ROOT).as_posix()] = entries
    return declared, sources

def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def _count_lock(path: Path) -> int:
    return sum(
        1
        for raw in read_text(path).splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    )

def _verify_exact_lock(lock: dict, profile: str):
    expected_count = EXPECTED_LOCK_COUNTS[profile]
    row = (lock.get("exact_transitive_locks") or {}).get(profile) or {}
    rel = row.get("path")
    detail = {
        "profile": profile,
        "declared_path": rel,
        "declared_sha256": row.get("sha256"),
        "declared_package_count": row.get("package_count"),
        "status": row.get("status"),
    }
    if not isinstance(rel, str) or not rel:
        detail["error"] = "missing lock path"
        return False, detail

    path = ROOT / Path(rel)
    detail["resolved_path"] = str(path)
    if not path.is_file():
        detail["error"] = "lock file missing"
        return False, detail

    actual_sha = _sha(path)
    actual_count = _count_lock(path)
    detail["actual_sha256"] = actual_sha
    detail["actual_package_count"] = actual_count

    ok = (
        row.get("status") == "strict-cold-install-ready"
        and row.get("package_count") == expected_count
        and actual_count == expected_count
        and actual_sha == row.get("sha256")
    )
    return ok, detail

def _verify_lock_contract():
    lock_path = ROOT / "requirements" / "locks" / "windows-py314-cu130.lock.json"
    result = {
        "path": str(lock_path),
        "schema_ok": False,
        "phase_ok": False,
        "python_ok": False,
        "core_exact_ok": False,
        "voice_exact_ok": False,
        "gpu_exact_ok": False,
        "full_exact_ok": False,
        "gpu_provenance_ok": False,
        "strict_policy_ok": False,
        "error": None,
    }
    if not lock_path.is_file():
        result["error"] = "lock metadata missing"
        return False, result

    try:
        lock = json.loads(read_text(lock_path))
        result["schema_ok"] = lock.get("schema") == EXPECTED_LOCK_SCHEMA
        result["phase_ok"] = lock.get("phase") == EXPECTED_LOCK_PHASE
        result["python_ok"] = lock.get("platform", {}).get("python") == EXPECTED_PYTHON

        for profile in ("core", "voice", "gpu", "full"):
            ok_profile, detail = _verify_exact_lock(lock, profile)
            result[f"{profile}_exact_ok"] = ok_profile
            result[profile] = detail

        provenance = lock.get("gpu_provenance") or {}
        result["gpu_provenance_ok"] = (
            provenance.get("provenance_status") == "official-index-and-d3-cold-install-verified"
            and provenance.get("official_index") == "https://download.pytorch.org/whl/cu130"
            and "download-r2.pytorch.org" in (provenance.get("verified_origin_hosts") or [])
        )
        result["gpu_provenance"] = provenance

        policy = lock.get("strict_reproducibility") or {}
        result["strict_policy_ok"] = (
            policy.get("compare_installed_set") is True
            and policy.get("compare_versions") is True
            and policy.get("unexpected_packages_fail") is True
            and policy.get("missing_packages_fail") is True
            and policy.get("version_mismatch_fail") is True
            and policy.get("torchcodec_required") is False
            and policy.get("gpu_official_index_required") is True
            and "pip" in (policy.get("bootstrap_packages_ignored") or [])
        )
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        return False, result

    ok = all(
        result[key]
        for key in (
            "schema_ok",
            "phase_ok",
            "python_ok",
            "core_exact_ok",
            "voice_exact_ok",
            "gpu_exact_ok",
            "full_exact_ok",
            "gpu_provenance_ok",
            "strict_policy_ok",
        )
    )
    return ok, result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-fail", action="store_true")
    args = ap.parse_args()

    files = _runtime_files()
    local = _local_roots(files)
    imports = Counter()
    parse_errors = []

    for path in files:
        try:
            tree = ast.parse(read_text(path), filename=str(path))
        except Exception as exc:
            parse_errors.append({
                "path": path.relative_to(ROOT).as_posix(),
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports[alias.name.split(".")[0]] += 1
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module
            ):
                imports[node.module.split(".")[0]] += 1

    declared, declaration_sources = _declared_distributions()
    external = sorted(
        name for name in imports
        if name not in STDLIB and name not in local
    )

    undeclared = []
    resolution = []
    for module in external:
        dist = ALIASES.get(module, module)
        key = dist.casefold().replace("_", "-")
        ok = key in declared or module in DECLARED_IMPORT_ONLY
        resolution.append({
            "import_root": module,
            "distribution": dist,
            "declared": ok,
            "occurrences": imports[module],
        })
        if not ok:
            undeclared.append(module)

    lock_ok, lock_contract = _verify_lock_contract()

    result = {
        "schema": "aura.ci.dependency-probe.v3.3",
        "gate_revision": "v0.8.6.2.2",
        "scope": {
            "python_files_scanned": len(files),
            "tests_scanned": False,
            "ci_scanned": False,
            "vendor_scanned": False,
        },
        "declaration_sources": declaration_sources,
        "external_import_roots": external,
        "resolution": resolution,
        "undeclared_external": undeclared,
        "parse_errors": parse_errors,
        "lock_contract": lock_contract,
        "lock_schema_ok": lock_contract.get("schema_ok", False),
        "exact_core_lock_ok": lock_contract.get("core_exact_ok", False),
        "exact_voice_lock_ok": lock_contract.get("voice_exact_ok", False),
        "gpu_pending_ok": lock_contract.get("gpu_pending_ok", False),
        "strict_policy_ok": lock_contract.get("strict_policy_ok", False),
        "runtime_classified_local": "runtime" in local and "runtime" not in external,
        "pass": (
            not undeclared
            and not parse_errors
            and lock_ok
            and "runtime" not in external
        ),
    }

    report = write_report("dependency_probe.json", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("Report:", report)
    return 0 if result["pass"] or args.no_fail else 2

if __name__ == "__main__":
    raise SystemExit(main())
