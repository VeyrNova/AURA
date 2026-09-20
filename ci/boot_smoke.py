from __future__ import annotations

import importlib.util
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "ci" / "reports" / "boot_smoke_result.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def check_ui_root(path: Path) -> dict:
    return {
        "path": str(path),
        "exists": path.is_dir(),
        "launch_shell": (path / "tools" / "launch_shell.py").is_file(),
        "shell_host": (path / "tools" / "shell_host.py").is_file(),
        "dist_index": (path / "dist" / "index.html").is_file(),
    }


def main() -> int:
    checks: dict[str, bool] = {}
    details: dict[str, object] = {}

    root_resolver = load_module("aura_paths_root_smoke", ROOT / "aura_paths.py")
    core_resolver = load_module(
        "aura_paths_core_smoke", ROOT / "core" / "runtime" / "aura_paths.py"
    )

    with tempfile.TemporaryDirectory(prefix="AURA_BOOT_SMOKE_") as td:
        t = Path(td)
        local = t / "Local"
        roaming = t / "Roaming"
        local.mkdir()
        roaming.mkdir()

        for label, module in (
            ("root_resolver", root_resolver),
            ("core_resolver", core_resolver),
        ):
            portable = module.AuraPaths.resolve(
                core_root=ROOT,
                env={"AURA_DEPLOYMENT_MODE": "portable"},
                local_appdata=local,
                roaming_appdata=roaming,
            )
            installed = module.AuraPaths.resolve(
                core_root=ROOT,
                env={"AURA_DEPLOYMENT_MODE": "installed"},
                local_appdata=local,
                roaming_appdata=roaming,
            )

            portable_ui = check_ui_root(Path(portable.ui_root))
            installed_ui = check_ui_root(Path(installed.ui_root))
            details[f"{label}_portable"] = portable_ui
            details[f"{label}_installed"] = installed_ui

            checks[f"{label}_portable_ui"] = all(
                portable_ui[k] for k in ("exists", "launch_shell", "shell_host", "dist_index")
            )
            checks[f"{label}_installed_fallback_ui"] = all(
                installed_ui[k] for k in ("exists", "launch_shell", "shell_host", "dist_index")
            )

    old_root = os.environ.get("AURA_ROOT")
    os.environ["AURA_ROOT"] = str(ROOT)
    try:
        bootstrap = load_module(
            "aura_product_bootstrap_smoke",
            ROOT / "tools" / "aura_v2_product_bootstrap.py",
        )
    finally:
        if old_root is None:
            os.environ.pop("AURA_ROOT", None)
        else:
            os.environ["AURA_ROOT"] = old_root

    checks["bootstrap_root_is_checkout"] = Path(bootstrap.ROOT).resolve() == ROOT.resolve()
    details["bootstrap_root"] = str(Path(bootstrap.ROOT).resolve())

    required = {
        "venv_python": ROOT / "venv" / "Scripts" / "python.exe",
        "lifecycle": ROOT / "runtime" / "aura_ui_host_lifecycle_v200.py",
        "intent": ROOT / "runtime" / "aura_conversation_intent_handoff_v200.py",
        "ui_launcher": ROOT / "launch_aura_ui_v0722_rc42.py",
        "run_bat": ROOT / "RUN_AURA.bat",
    }
    for name, path in required.items():
        checks[f"required_{name}"] = path.is_file()
        details[f"required_{name}"] = str(path)

    launcher = load_module(
        "aura_ui_launcher_smoke",
        ROOT / "launch_aura_ui_v0722_rc42.py",
    )
    resolved_paths = launcher._aura_p08522_load_paths(ROOT)
    launcher_ui = check_ui_root(Path(resolved_paths.ui_root))
    details["launcher_resolved_ui"] = launcher_ui
    checks["launcher_resolves_embedded_ui"] = all(
        launcher_ui[k] for k in ("exists", "launch_shell", "shell_host", "dist_index")
    )

    result = {
        "schema": "aura.clean-checkout-boot-smoke.v1",
        "root": str(ROOT),
        "checks": checks,
        "details": details,
        "pass": all(checks.values()),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
