# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as md
import importlib.util
import json
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "environment" / "aura_environment_v0862.json"
LOCK = ROOT / "requirements" / "locks" / "windows-py314-cu130.lock.json"
REPORT = ROOT / "ci" / "reports" / "environment_v0862_result.json"

EXPECTED_LOCK_SCHEMA = "aura.dependency-lock.v0862.2.v1"
EXPECTED_LOCK_PHASE = "AURA v0.8.6.2.2"
EXPECTED_PYTHON = "3.14.7"
EXPECTED_CORE_COUNT = 11
EXPECTED_VOICE_COUNT = 107
EXPECTED_GPU_COUNT = 6
EXPECTED_FULL_COUNT = 113

def norm(name: str) -> str:
    return name.casefold().replace("_", "-")

def dist_version(name: str):
    try:
        return md.version(name)
    except md.PackageNotFoundError:
        return None

def import_ok(name: str):
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

def run(cmd, timeout=45):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return cp.returncode, cp.stdout, cp.stderr
    except Exception as exc:
        return 99, "", f"{type(exc).__name__}: {exc}"

def sha256(path: Path) -> str:
    # Exact lock hashes are certified over canonical UTF-8/LF text so the
    # verification is independent of Windows checkout CRLF conversion.
    data = path.read_bytes()
    if path.suffix.lower() == ".txt":
        text = data.decode("utf-8-sig")
        data = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    return hashlib.sha256(data).hexdigest()

def count_lock_entries(path: Path) -> int:
    return sum(
        1
        for raw in path.read_text(encoding="utf-8-sig").splitlines()
        if raw.strip() and not raw.lstrip().startswith("#")
    )

def verify_exact_lock(lock: dict, profile: str, expected_count: int):
    row = (lock.get("exact_transitive_locks") or {}).get(profile) or {}
    rel = row.get("path")
    details = {
        "profile": profile,
        "declared_path": rel,
        "declared_sha256": row.get("sha256"),
        "declared_package_count": row.get("package_count"),
        "status": row.get("status"),
    }
    if not isinstance(rel, str) or not rel:
        details["error"] = "missing lock path"
        return False, details

    path = ROOT / Path(rel)
    details["resolved_path"] = str(path)
    if not path.is_file():
        details["error"] = "lock file missing"
        return False, details

    actual_sha = sha256(path)
    actual_count = count_lock_entries(path)
    details["actual_sha256"] = actual_sha
    details["actual_package_count"] = actual_count

    ok = (
        row.get("status") == "strict-cold-install-ready"
        and row.get("package_count") == expected_count
        and actual_count == expected_count
        and isinstance(row.get("sha256"), str)
        and actual_sha == row.get("sha256")
    )
    return ok, details

def verify_strict_policy(lock: dict):
    policy = lock.get("strict_reproducibility") or {}
    expected_true = (
        "compare_installed_set",
        "compare_versions",
        "unexpected_packages_fail",
        "missing_packages_fail",
        "version_mismatch_fail",
    )
    checks = {key: policy.get(key) is True for key in expected_true}
    checks["torchcodec_not_required"] = policy.get("torchcodec_required") is False
    checks["bootstrap_pip_ignored"] = "pip" in (policy.get("bootstrap_packages_ignored") or [])
    checks["gpu_official_index_required"] = policy.get("gpu_official_index_required") is True
    return all(checks.values()), checks

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--portable",
        action="store_true",
        help="CI mode: validate lock/platform schema, not the full local installed set.",
    )
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    checks = {}
    details = {}

    checks["lock_schema"] = lock.get("schema") == EXPECTED_LOCK_SCHEMA
    checks["lock_phase"] = lock.get("phase") == EXPECTED_LOCK_PHASE
    checks["lock_python_3147"] = lock.get("platform", {}).get("python") == EXPECTED_PYTHON
    checks["environment_schema"] = manifest.get("schema") == "aura.environment.v0862.v1"
    checks["python_3_14"] = sys.version_info[:2] == (3, 14)
    checks["windows_amd64"] = sys.platform == "win32" and platform.machine().upper() == "AMD64"

    core_ok, core_details = verify_exact_lock(lock, "core", EXPECTED_CORE_COUNT)
    voice_ok, voice_details = verify_exact_lock(lock, "voice", EXPECTED_VOICE_COUNT)
    gpu_ok, gpu_details = verify_exact_lock(lock, "gpu", EXPECTED_GPU_COUNT)
    full_ok, full_details = verify_exact_lock(lock, "full", EXPECTED_FULL_COUNT)
    checks["core_exact_lock"] = core_ok
    checks["voice_exact_lock"] = voice_ok
    checks["gpu_exact_lock"] = gpu_ok
    checks["full_exact_lock"] = full_ok
    details["exact_locks"] = {
        "core": core_details,
        "voice": voice_details,
        "gpu": gpu_details,
        "full": full_details,
    }

    provenance = lock.get("gpu_provenance") or {}
    checks["gpu_provenance_frozen"] = (
        provenance.get("provenance_status") == "official-index-and-d3-cold-install-verified"
        and provenance.get("official_index") == "https://download.pytorch.org/whl/cu130"
        and "download-r2.pytorch.org" in (provenance.get("verified_origin_hosts") or [])
    )
    details["gpu_provenance"] = provenance

    strict_ok, strict_details = verify_strict_policy(lock)
    checks["strict_reproducibility_policy"] = strict_ok
    details["strict_reproducibility"] = strict_details

    if not args.portable:
        version_rows = {}
        for dist, expected in manifest["required_direct"].items():
            actual = dist_version(dist)
            version_rows[dist] = {"expected": expected, "actual": actual}
        checks["required_versions_exact"] = all(
            row["actual"] == row["expected"] for row in version_rows.values()
        )
        details["required_versions"] = version_rows

        import_rows = {}
        for module, dist in manifest["required_imports"].items():
            import_rows[module] = import_ok(module)
        checks["required_imports_resolvable"] = all(import_rows.values())
        details["required_imports"] = import_rows

        code = (
            "import json,torch,torchaudio;"
            "x=torch.arange(1,5,dtype=torch.float32,device='cuda');"
            "y=(x@x);torch.cuda.synchronize();"
            "print(json.dumps({"
            "'torch':torch.__version__,"
            "'torchaudio':torchaudio.__version__,"
            "'cuda':bool(torch.cuda.is_available()),"
            "'cuda_version':getattr(torch.version,'cuda',None),"
            "'device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,"
            "'cuda_dot':float(y.cpu())"
            "}))"
        )
        rc, stdout, stderr = run([sys.executable, "-c", code], timeout=60)
        gpu = None
        if rc == 0 and stdout.strip():
            try:
                gpu = json.loads(stdout.strip().splitlines()[-1])
            except Exception:
                gpu = None
        checks["gpu_probe"] = (
            isinstance(gpu, dict)
            and gpu.get("torch") == "2.13.0+cu130"
            and gpu.get("torchaudio") == "2.11.0+cu130"
            and gpu.get("cuda") is True
            and str(gpu.get("cuda_version")) == "13.0"
            and gpu.get("cuda_dot") == 30.0
        )
        details["gpu"] = gpu or {"returncode": rc, "stderr": stderr[-4000:]}

        rc, stdout, stderr = run(
            [sys.executable, "-m", "pip", "check"], timeout=60
        )
        checks["pip_check"] = rc == 0
        details["pip_check"] = {
            "returncode": rc,
            "stdout": stdout[-4000:],
            "stderr": stderr[-4000:],
        }

        optional = {}
        for module in manifest["optional_absent"]:
            optional[module] = import_ok(module)
        details["optional_modules_present_now"] = optional

        torchcodec_version = dist_version("torchcodec")
        details["torchcodec"] = {
            "installed_version": torchcodec_version,
            "required": False,
            "import_is_not_a_gate": True,
        }
    else:
        details["portable_note"] = (
            "Full installed-package/CUDA verification is intentionally local-only."
        )

    result = {
        "schema": "aura.environment-verification.v0862.2.v1",
        "gate_revision": "v0.8.6.2.2",
        "portable": args.portable,
        "python": sys.version,
        "platform": sys.platform,
        "machine": platform.machine(),
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
