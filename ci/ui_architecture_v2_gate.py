from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "ci" / "reports" / "ui_architecture_v2_result.json"

FOUNDATION = ROOT / "ui" / "chromium" / "v2"
ACTIVE = ROOT / "ui" / "chromium" / "v0.7.2.2-rc4.2"

REQUIRED = (
    FOUNDATION / "README.md",
    FOUNDATION / "PARITY_MATRIX.md",
    FOUNDATION / "index.html",
    FOUNDATION / "migration-manifest.json",
    FOUNDATION / "src" / "main.js",
    FOUNDATION / "src" / "app" / "aura-app.js",
    FOUNDATION / "src" / "components" / "aura-shell.js",
    FOUNDATION / "src" / "components" / "neural-orb.js",
    FOUNDATION / "src" / "components" / "top-bar.js",
    FOUNDATION / "src" / "components" / "primary-nav.js",
    FOUNDATION / "src" / "components" / "telemetry-panel.js",
    FOUNDATION / "src" / "components" / "conversation-surface.js",
    FOUNDATION / "src" / "components" / "composer.js",
    FOUNDATION / "src" / "runtime" / "aura-state.js",
    FOUNDATION / "src" / "runtime" / "aura-event-bus.js",
    FOUNDATION / "src" / "styles" / "tokens.css",
    FOUNDATION / "src" / "styles" / "shell.css",
)

ACTIVATION_AUTHORITIES = (
    ROOT / "aura_paths.py",
    ROOT / "core" / "runtime" / "aura_paths.py",
    ROOT / "tools" / "aura_v2_product_bootstrap.py",
    ROOT / "launch_aura_ui_v0722_rc42.py",
)

LEGACY_MARKERS = (
    "aura-p0",
    "aura-v123",
    "aura-v130",
    "aura-a200",
)

EXPECTED_SHELL_COMPONENTS = (
    "top-bar",
    "primary-nav",
    "neural-orb",
    "telemetry-panel",
    "conversation-surface",
    "composer",
    "aura-shell",
)

def main() -> int:
    checks: dict[str, dict[str, object]] = {}

    missing = [str(path.relative_to(ROOT)) for path in REQUIRED if not path.is_file()]
    checks["foundation_files_present"] = {"pass": not missing, "missing": missing}

    active_index = ACTIVE / "dist" / "index.html"
    checks["active_rc42_present"] = {
        "pass": active_index.is_file(),
        "path": str(active_index.relative_to(ROOT)),
    }

    manifest_path = FOUNDATION / "migration-manifest.json"
    manifest = {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        checks["migration_manifest_valid"] = {"pass": False, "error": str(exc)}
    else:
        phases = {
            str(item.get("id")): str(item.get("status"))
            for item in manifest.get("phases", [])
            if isinstance(item, dict)
        }
        checks["migration_manifest_valid"] = {
            "pass": (
                manifest.get("status") == "dormant"
                and manifest.get("activation_allowed") is False
                and manifest.get("active_production_root") == "ui/chromium/v0.7.2.2-rc4.2"
                and phases.get("foundation") == "complete"
                and phases.get("shell-parity") == "active"
                and phases.get("activation") == "blocked"
            ),
            "status": manifest.get("status"),
            "activation_allowed": manifest.get("activation_allowed"),
            "phases": phases,
        }
        components = tuple(str(x) for x in manifest.get("shell_components", []))
        checks["shell_component_manifest_complete"] = {
            "pass": all(name in components for name in EXPECTED_SHELL_COMPONENTS),
            "components": components,
        }

    index_path = FOUNDATION / "index.html"
    index_text = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    module_scripts = re.findall(
        r'<script[^>]+type=["\\\']module["\\\'][^>]+src=["\\\']([^"\\\']+)["\\\']',
        index_text,
        flags=re.IGNORECASE,
    )
    checks["single_v2_entrypoint"] = {
        "pass": module_scripts == ["./src/main.js"],
        "module_scripts": module_scripts,
    }

    lower_index = index_text.lower()
    legacy_hits = [marker for marker in LEGACY_MARKERS if marker in lower_index]
    checks["no_legacy_overlay_chain_in_v2_index"] = {"pass": not legacy_hits, "hits": legacy_hits}

    activation_hits = []
    for path in ACTIVATION_AUTHORITIES:
        if not path.is_file():
            activation_hits.append({"path": str(path.relative_to(ROOT)), "reason": "missing-authority"})
            continue
        text = path.read_text(encoding="utf-8", errors="replace").replace("\\\\", "/").lower()
        if "ui/chromium/v2" in text:
            activation_hits.append({"path": str(path.relative_to(ROOT)), "reason": "v2-reference"})
    checks["v2_not_activated_by_runtime"] = {"pass": not activation_hits, "hits": activation_hits}

    source_text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in REQUIRED
        if path.suffix in {".js", ".css", ".html"} and path.is_file()
    )
    checks["foundation_has_normal_and_developer_modes"] = {
        "pass": '"developer"' in source_text and '"normal"' in source_text,
    }
    checks["foundation_has_canonical_states"] = {
        "pass": all(
            state in source_text
            for state in (
                "IDLE",
                "LISTENING",
                "THINKING",
                "SEARCHING",
                "ACTING",
                "WAITING_APPROVAL",
                "SPEAKING",
                "ERROR",
            )
        ),
    }

    shell_path = FOUNDATION / "src" / "components" / "aura-shell.js"
    shell_text = shell_path.read_text(encoding="utf-8", errors="replace") if shell_path.is_file() else ""
    expected_imports = (
        "./top-bar.js",
        "./primary-nav.js",
        "./neural-orb.js",
        "./telemetry-panel.js",
        "./conversation-surface.js",
        "./composer.js",
    )
    checks["shell_composes_named_components"] = {
        "pass": all(item in shell_text for item in expected_imports),
        "imports": expected_imports,
    }

    passed = all(bool(item.get("pass")) for item in checks.values())
    result = {
        "schema": "aura.ui.v2.foundation-gate.v2",
        "status": "PASS" if passed else "FAIL",
        "active_ui": "ui/chromium/v0.7.2.2-rc4.2",
        "v2_status": "dormant",
        "v2_phase": "shell-parity",
        "checks": checks,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print("AURA UI Architecture V2 gate")
    for name, item in checks.items():
        print(f"[{'PASS' if item.get('pass') else 'FAIL'}] {name}")
    print(f"[{'PASS' if passed else 'FAIL'}] GLOBAL")
    return 0 if passed else 1

if __name__ == "__main__":
    raise SystemExit(main())
