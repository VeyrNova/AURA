# -*- coding: utf-8 -*-
from __future__ import annotations

import ast
import importlib.metadata as md
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "ci" / "reports" / "reference_machine_audit.json"

SKIP_DIRS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules", "vendor",
    "_patch_backups", "_github_preflight", "payload",
}
SKIP_PARTS = {"aura_qr_vendor"}

STDLIB = set(getattr(sys, "stdlib_module_names", set()))


def run(cmd: list[str], timeout: int = 20) -> dict:
    try:
        cp = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "returncode": cp.returncode,
            "stdout": cp.stdout.strip(),
            "stderr": cp.stderr.strip(),
        }
    except Exception as exc:
        return {
            "returncode": 99,
            "stdout": "",
            "stderr": f"{type(exc).__name__}: {exc}",
        }


def version_of(dist: str) -> str | None:
    try:
        return md.version(dist)
    except md.PackageNotFoundError:
        return None


def iter_python_files():
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        yield path


def top_level_imports() -> set[str]:
    imports: set[str] = set()
    for path in iter_python_files():
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".", 1)[0])
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".", 1)[0])
    return imports


def local_top_levels() -> set[str]:
    result = set()
    for child in ROOT.iterdir():
        if child.is_dir() and (child / "__init__.py").is_file():
            result.add(child.name)
        elif child.is_file() and child.suffix == ".py":
            result.add(child.stem)
    return result


def imported_distributions() -> dict[str, list[str]]:
    package_map = md.packages_distributions()
    external = sorted(
        top_level_imports() - local_top_levels() - STDLIB
    )
    mapped: dict[str, list[str]] = {}
    for module in external:
        dists = package_map.get(module) or []
        mapped[module] = sorted(set(dists))
    return mapped


def installed_versions_for_imports(mapping: dict[str, list[str]]) -> dict[str, str | None]:
    names = sorted({dist for rows in mapping.values() for dist in rows})
    return {name: version_of(name) for name in names}


def exe_info(name: str, args: list[str]) -> dict:
    path = shutil.which(name)
    row = {"available": bool(path)}
    if not path:
        return row
    probe = run([path, *args])
    row["version_probe_returncode"] = probe["returncode"]
    # Do not publish paths/usernames. Keep only first safe output line.
    text = probe["stdout"] or probe["stderr"]
    row["version"] = text.splitlines()[0][:300] if text else None
    return row


def ollama_info() -> dict:
    row = exe_info("ollama", ["--version"])
    if not row.get("available"):
        return row
    # Model names are safe enough for dependency capability audit; no prompts/data.
    probe = run(["ollama", "list"], timeout=15)
    models = []
    if probe["returncode"] == 0:
        lines = probe["stdout"].splitlines()
        for line in lines[1:]:
            cols = line.split()
            if cols:
                models.append(cols[0])
    row["installed_models"] = models
    return row


def gpu_info() -> dict:
    if not shutil.which("nvidia-smi"):
        return {"nvidia_smi": False}
    probe = run([
        "nvidia-smi",
        "--query-gpu=name,driver_version,memory.total",
        "--format=csv,noheader,nounits",
    ])
    row = {"nvidia_smi": probe["returncode"] == 0}
    if probe["returncode"] == 0:
        rows = []
        for line in probe["stdout"].splitlines():
            parts = [x.strip() for x in line.split(",")]
            if len(parts) >= 3:
                rows.append({
                    "name": parts[0],
                    "driver_version": parts[1],
                    "memory_total_mb": parts[2],
                })
        row["gpus"] = rows
    return row


def torch_info() -> dict:
    code = (
        "import json,torch;"
        "print(json.dumps({"
        "'version':torch.__version__,"
        "'cuda_available':bool(torch.cuda.is_available()),"
        "'cuda_version':getattr(torch.version,'cuda',None),"
        "'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None"
        "}))"
    )
    probe = run([sys.executable, "-c", code], timeout=30)
    if probe["returncode"] != 0:
        return {"available": False}
    try:
        return {"available": True, **json.loads(probe["stdout"].splitlines()[-1])}
    except Exception:
        return {"available": True, "parse_error": True}


def main() -> int:
    mapping = imported_distributions()
    installed = installed_versions_for_imports(mapping)

    required_reference = {}
    manifest = ROOT / "environment" / "aura_environment_v0862.json"
    if manifest.is_file():
        try:
            required_reference = json.loads(
                manifest.read_text(encoding="utf-8-sig")
            ).get("required_direct") or {}
        except Exception:
            required_reference = {}

    report = {
        "schema": "aura.reference-machine-audit.v1",
        "source_of_truth_policy": "REFERENCE_PC_RUNTIME_SOURCE",
        "privacy": {
            "user_profile_path_included": False,
            "environment_variable_values_included": False,
            "api_keys_included": False,
            "oauth_tokens_included": False,
            "conversation_or_memory_content_included": False,
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        },
        "executables": {
            "git": exe_info("git", ["--version"]),
            "ollama": ollama_info(),
            "ffmpeg": exe_info("ffmpeg", ["-version"]),
            "ffprobe": exe_info("ffprobe", ["-version"]),
        },
        "gpu": gpu_info(),
        "torch": torch_info(),
        "python_import_dependency_map": mapping,
        "python_distributions_used_by_source": installed,
        "certified_reference_direct_dependencies": required_reference,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("[PASS] Reference-machine audit completed.")
    print(f"[PASS] Report: {REPORT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
