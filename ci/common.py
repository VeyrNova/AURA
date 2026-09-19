# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_DIR = ROOT / "ci"
BASELINE_PATH = CI_DIR / "baseline_v0860.json"
REPORT_DIR = CI_DIR / "reports"

def load_baseline() -> dict:
    return json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def line_count(path: Path) -> int:
    return len(read_text(path).splitlines())

def resolve_active_ui() -> Path | None:
    explicit = os.environ.get("AURA_UI_ROOT", "").strip()
    if explicit and Path(explicit).is_dir():
        return Path(explicit)
    local = os.environ.get("LOCALAPPDATA", "").strip()
    if not local:
        return None
    locator = Path(local) / "AURA" / "ui" / "current.json"
    if not locator.is_file():
        return None
    try:
        data = json.loads(read_text(locator))
    except Exception:
        return None
    value = str(data.get("ui_root") or "").strip()
    return Path(value) if value and Path(value).is_dir() else None

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load module {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def test_module_paths():
    return [
        ROOT / "tests" / "invariants" / "test_critical_baseline_v094.py",
        ROOT / "tests" / "invariants" / "test_security_fail_closed_v0861.py",
        ROOT / "tests" / "invariants" / "test_security_policy_v2_v0866.py",
        ROOT / "tests" / "invariants" / "test_runtime_performance_v0867.py",
        ROOT / "tests" / "invariants" / "test_engineering_foundation_v094.py",
        ROOT / "tests" / "invariants" / "test_product_version_surfaces_v0871.py",
        ROOT / "tests" / "invariants" / "test_spoken_product_version_v0872.py",
        ROOT / "tests" / "invariants" / "test_mission_engine_v088.py",
        ROOT / "tests" / "invariants" / "test_action_receipts_v089.py",
        ROOT / "tests" / "invariants" / "test_integration_architecture_v090.py",
        ROOT / "tests" / "invariants" / "test_email_provider_v091.py",
        ROOT / "tests" / "invariants" / "test_calendar_provider_v092.py",
        ROOT / "tests" / "invariants" / "test_runtime_wiring_v0921.py",
        ROOT / "tests" / "invariants" / "test_runtime_wiring_ui_v0921.py",
        ROOT / "tests" / "invariants" / "test_modules_agenda_ui_v0922.py",
        ROOT / "tests" / "invariants" / "test_workspace_color_harmonization_v09221.py",
        ROOT / "tests" / "invariants" / "test_contacts_provider_v093.py",
        ROOT / "tests" / "invariants" / "test_contacts_module_ui_v093.py",
        ROOT / "tests" / "invariants" / "test_files_provider_v094.py",
        ROOT / "tests" / "invariants" / "test_documents_files_module_ui_v094.py",
        ROOT / "tests" / "invariants" / "test_modules_system_live_dedup_v094.py",
        ROOT / "tests" / "invariants" / "test_memorykernel_v2_v087.py",
        ROOT / "tests" / "invariants" / "test_shared_sse_v0861.py",
        ROOT / "tests" / "invariants" / "test_memory_forget_v0861.py",
        ROOT / "tests" / "invariants" / "test_weather_location_v0861.py",
        ROOT / "tests" / "invariants" / "test_maps_contract_v0861.py",
    ]

def run_invariant_module(path: Path, *, portable: bool = False) -> dict:
    try:
        mod = load_module(path, "aura_ci_" + path.stem)
        result = mod.check(ROOT, resolve_active_ui(), load_baseline(), portable=portable)
        if not isinstance(result, dict):
            raise TypeError("check() must return dict")
        result.setdefault("name", path.stem)
        result.setdefault("status", "FAIL")
        result.setdefault("blocking", True)
        return result
    except Exception as exc:
        return {
            "name": path.stem,
            "status": "FAIL",
            "blocking": True,
            "error": f"{type(exc).__name__}: {exc}",
        }

def compile_python_file(path: Path) -> tuple[bool, str]:
    try:
        compile(read_text(path), str(path), "exec")
        return True, ""
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"

def write_report(name: str, data: dict) -> Path:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path

def env_result(name: str, detail: str, *, blocking: bool) -> dict:
    return {"name": name, "status": "ENVIRONMENT", "blocking": blocking, "detail": detail}

def pass_result(name: str, **detail) -> dict:
    return {"name": name, "status": "PASS", "blocking": True, **detail}

def fail_result(name: str, **detail) -> dict:
    return {"name": name, "status": "FAIL", "blocking": True, **detail}
