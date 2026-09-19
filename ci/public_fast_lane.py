from __future__ import annotations

import json
import py_compile
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "ci" / "reports" / "public_fast_lane.json"

REQUIRED = [
    "README.md",
    "LICENSE",
    "SECURITY.md",
    ".env.example",
    "core/aura_core.py",
    "runtime/aura_intelligence_gateway_v3.py",
    "runtime/aura_v3_conversation_route_adapter.py",
    "runtime/aura_conversation_fabric_bridge.py",
    "runtime/aura_skill_executor_v230.py",
    "skills/developer/skill.json",
    "voice/voice_engine.py",
    "voice/microphone.py",
    "voice/xtts_tts.py",
    "voice/chatterbox_tts.py",
    "localization/aura_locale.py",
    "aura_profile_portability.py",
    "aura_profile_cli.py",
    "ui/chromium/v0.7.2.2-rc4.2/src/main.js",
    "ui/chromium/v0.7.2.2-rc4.2/dist/index.html",
    "ui/chromium/v0.7.2.2-rc4.2/tools/shell_host.py",
]

FORBIDDEN_EXACT = {
    ".env",
    "config/authorized_folders.json",
    "config/dual_brain_gpu_ok.json",
    "config/voice_audition.json",
    "config/voice_profile.json",
    "database/google_search_usage.json",
    "runtime/developer_fabric/developer_mode_state.json",
    "runtime/developer_fabric/developer_workspace_request.json",
    "runtime/developer_fabric/roadmap_auto_certification_rm26.json",
}

FORBIDDEN_PREFIXES = (
    ".aura_audit/",
    "_patch_backups/",
    "_dev/staging/",
    "_github_preflight/",
    "data/a200_runtime/",
    "data/media/",
    "data/youtube/",
)

SECRET_PATTERNS = {
    "OPENAI_STYLE": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "ANTHROPIC": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "GROQ": re.compile(r"\bgsk_[A-Za-z0-9_-]{20,}\b"),
    "GOOGLE": re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    "HUGGINGFACE": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "GITHUB": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "AWS_ACCESS": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
}

TEXT_SUFFIXES = {
    ".py", ".pyi", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx",
    ".html", ".htm", ".css", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".ini", ".cfg", ".conf", ".md", ".rst", ".txt",
    ".bat", ".cmd", ".ps1", ".sh", ".xml", ".properties",
}

COMPILE_ROOTS = [
    "core",
    "runtime",
    "voice",
    "skills",
    "security",
    "integrations",
    "services",
    "tools",
    "localization",
    "mission_engine",
    "action_receipts",
]

def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()

def check_required() -> tuple[bool, list[str]]:
    missing = [p for p in REQUIRED if not (ROOT / p).is_file()]
    return not missing, missing

def check_forbidden() -> tuple[bool, list[str]]:
    bad: list[str] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rp = rel(p)
        if rp in FORBIDDEN_EXACT or any(rp.startswith(prefix) for prefix in FORBIDDEN_PREFIXES):
            bad.append(rp)
    return not bad, sorted(bad)

def check_env_example() -> tuple[bool, list[str]]:
    path = ROOT / ".env.example"
    if not path.is_file():
        return False, ["missing .env.example"]
    bad = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().upper()
        value = value.strip()

        # Public templates may contain explicit non-secret policy values such as
        # AURA_ALLOW_PROFILE_EXPORT_SECRETS=false. Only credential-like values
        # should fail the gate.
        safe_literals = {
            "", "false", "0", "no", "off", "disabled", "none", "null",
            "changeme", "change_me", "your_key_here", "your_api_key_here",
            "replace_me", "example", "<key>", "<token>", "<secret>",
        }
        if (
            any(word in key for word in ("KEY", "TOKEN", "SECRET", "PASSWORD"))
            and value.casefold() not in safe_literals
        ):
            bad.append(key)
    return not bad, bad

def scan_secrets() -> tuple[bool, list[dict]]:
    hits: list[dict] = []
    for p in ROOT.rglob("*"):
        if not p.is_file():
            continue
        rp = rel(p)
        if rp.startswith(".git/") or rp.startswith("ci/reports/"):
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES and p.name not in {".env.example", ".gitignore", ".gitattributes"}:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        kinds = [name for name, rx in SECRET_PATTERNS.items() if rx.search(text)]
        if kinds:
            hits.append({"path": rp, "types": kinds})
    return not hits, hits

def compile_python() -> tuple[bool, list[dict], int]:
    failures: list[dict] = []
    count = 0
    for root_name in COMPILE_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for p in root.rglob("*.py"):
            if "__pycache__" in p.parts:
                continue
            count += 1
            try:
                py_compile.compile(str(p), doraise=True)
            except Exception as exc:
                failures.append({"path": rel(p), "error": f"{type(exc).__name__}: {exc}"})
    for p in (ROOT / "aura_profile_portability.py", ROOT / "aura_profile_cli.py"):
        if p.is_file():
            count += 1
            try:
                py_compile.compile(str(p), doraise=True)
            except Exception as exc:
                failures.append({"path": rel(p), "error": f"{type(exc).__name__}: {exc}"})
    return not failures, failures, count

def check_public_identity() -> tuple[bool, list[str]]:
    warnings: list[str] = []
    readme = (ROOT / "README.md").read_text(encoding="utf-8", errors="ignore")
    if "AURA-v2.3" not in readme and "AURA v2.3" not in readme:
        warnings.append("README does not advertise the current AURA v2.3 product line")
    if "push-to-talk" not in readme.casefold():
        warnings.append("README does not document the push-to-talk microphone policy")
    if "All Rights Reserved" not in (ROOT / "LICENSE").read_text(encoding="utf-8", errors="ignore"):
        warnings.append("LICENSE is not the expected proprietary license")
    return not warnings, warnings

def main() -> int:
    checks = {}

    ok, details = check_required()
    checks["required_public_sources"] = {"pass": ok, "details": details}

    ok, details = check_forbidden()
    checks["private_runtime_state_excluded"] = {"pass": ok, "details": details}

    ok, details = check_env_example()
    checks["env_template_has_no_credentials"] = {"pass": ok, "details": details}

    ok, details = scan_secrets()
    checks["known_secret_patterns_absent"] = {"pass": ok, "details": details}

    ok, failures, compiled = compile_python()
    checks["python_syntax"] = {
        "pass": ok,
        "compiled_files": compiled,
        "failures": failures,
    }

    ok, details = check_public_identity()
    checks["public_identity"] = {"pass": ok, "details": details}

    passed = all(row["pass"] for row in checks.values())

    result = {
        "schema": "aura.public-fast-lane.v1",
        "product": "AURA",
        "product_line": "v2.3",
        "runtime": "v3",
        "public_distribution": True,
        "checks": checks,
        "pass": passed,
    }

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    for name, row in checks.items():
        print(("[PASS] " if row["pass"] else "[FAIL] ") + name)
        if not row["pass"]:
            print(json.dumps(row, ensure_ascii=False, indent=2))

    print(json.dumps(result, ensure_ascii=False, indent=2))
    print("PASS GLOBAL" if passed else "FAIL GLOBAL")
    return 0 if passed else 2

if __name__ == "__main__":
    raise SystemExit(main())
