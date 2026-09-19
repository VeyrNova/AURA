# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
LOCK_META = ROOT / "requirements" / "locks" / "windows-py314-cu130.lock.json"
REPORT_DIR = ROOT / "ci" / "reports"

EXPECTED_LOCK_SCHEMA = "aura.dependency-lock.v0862.2.v1"
EXPECTED_LOCK_PHASE = "AURA v0.8.6.2.2"
EXPECTED_PYTHON = "3.14.7"
EXPECTED_COUNTS = {"core": 11, "voice": 107, "gpu": 6, "full": 113}

OFFICIAL_GPU_INDEX = "https://download.pytorch.org/whl/cu130"
PYPI_INDEX = "https://pypi.org/simple"
OFFICIAL_GPU_HOSTS = {"download.pytorch.org", "download-r2.pytorch.org"}

IMPORT_MAP = {
    "PySide6": "PySide6",
    "python-dotenv": "dotenv",
    "requests": "requests",
    "psutil": "psutil",
    "numpy": "numpy",
    "sounddevice": "sounddevice",
    "faster-whisper": "faster_whisper",
    "piper-tts": "piper",
    "coqui-tts": "TTS",
    "websockets": "websockets",
    "torch": "torch",
    "torchaudio": "torchaudio",
}
BOOTSTRAP_IGNORED = {"pip"}

def canonical(name: str) -> str:
    return name.casefold().replace("_", "-")

def run(cmd, timeout=3600):
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, shell=False)
        return {"returncode": cp.returncode, "stdout": cp.stdout[-30000:], "stderr": cp.stderr[-16000:]}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "timeout", "timeout": True}
    except Exception as exc:
        return {"returncode": 99, "stdout": "", "stderr": f"{type(exc).__name__}: {exc}"}

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def parse_lock(path: Path):
    rows = {}
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        item = raw.strip()
        if not item or item.startswith("#"):
            continue
        if "==" not in item:
            raise RuntimeError(f"Unpinned entry in strict lock: {item}")
        name, version = item.split("==", 1)
        key = canonical(name.strip())
        if key in rows:
            raise RuntimeError(f"Duplicate strict lock entry: {name}")
        rows[key] = {"name": name.strip(), "version": version.strip()}
    return rows

def validate_lock_contract(meta: dict):
    if meta.get("schema") != EXPECTED_LOCK_SCHEMA:
        raise RuntimeError(f"Lock metadata schema mismatch: expected {EXPECTED_LOCK_SCHEMA}, got {meta.get('schema')!r}.")
    if meta.get("phase") != EXPECTED_LOCK_PHASE:
        raise RuntimeError(f"Lock metadata phase mismatch: expected {EXPECTED_LOCK_PHASE}, got {meta.get('phase')!r}.")
    if meta.get("platform", {}).get("python") != EXPECTED_PYTHON:
        raise RuntimeError("Lock Python reference must be 3.14.7.")

    exact = meta.get("exact_transitive_locks") or {}
    details = {"schema": meta["schema"], "phase": meta["phase"], "python": meta["platform"]["python"]}
    parsed = {}
    for name in ("core", "voice", "gpu", "full"):
        row = exact.get(name) or {}
        expected_count = EXPECTED_COUNTS[name]
        if row.get("status") != "strict-cold-install-ready":
            raise RuntimeError(f"{name.upper()} strict lock is not ready.")
        if row.get("package_count") != expected_count:
            raise RuntimeError(f"{name.upper()} strict lock count mismatch.")
        rel = row.get("path")
        if not isinstance(rel, str) or not rel:
            raise RuntimeError(f"{name.upper()} strict lock path missing.")
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f"{name.upper()} strict lock missing: {path}")
        rows = parse_lock(path)
        if len(rows) != expected_count:
            raise RuntimeError(f"{name.upper()} strict lock file count mismatch.")
        actual_sha = sha256(path)
        if actual_sha != row.get("sha256"):
            raise RuntimeError(f"{name.upper()} strict lock hash mismatch.")
        parsed[name] = {"path": path, "rows": rows}
        details[f"{name}_count"] = expected_count
        details[f"{name}_sha256"] = actual_sha

    provenance = meta.get("gpu_provenance") or {}
    if provenance.get("provenance_status") != "official-index-and-d3-cold-install-verified":
        raise RuntimeError("GPU provenance is not D3-certified.")
    if provenance.get("official_index") != OFFICIAL_GPU_INDEX:
        raise RuntimeError("GPU official index mismatch.")
    if "download-r2.pytorch.org" not in (provenance.get("verified_origin_hosts") or []):
        raise RuntimeError("GPU official origin host evidence missing.")
    details["gpu_provenance_status"] = provenance.get("provenance_status")
    details["gpu_official_index"] = provenance.get("official_index")

    policy = meta.get("strict_reproducibility") or {}
    required_true = (
        "compare_installed_set","compare_versions","unexpected_packages_fail",
        "missing_packages_fail","version_mismatch_fail","gpu_official_index_required"
    )
    if not all(policy.get(k) is True for k in required_true):
        raise RuntimeError("Strict reproducibility policy is incomplete.")
    if policy.get("torchcodec_required") is not False:
        raise RuntimeError("TorchCodec must remain non-required.")
    if "pip" not in (policy.get("bootstrap_packages_ignored") or []):
        raise RuntimeError("Bootstrap pip ignore rule missing.")
    details["torchcodec_required"] = False
    return parsed, details

def installed_map(python_exe: Path):
    code = r"""
import importlib.metadata as md, json
rows={}
for d in md.distributions():
    name=d.metadata.get("Name") or ""
    if name:
        rows[name.casefold().replace("_","-")]={"name":name,"version":d.version}
print(json.dumps(rows))
"""
    cp = run([str(python_exe), "-c", code], timeout=90)
    if cp["returncode"] != 0:
        raise RuntimeError("Unable to read temporary installed distributions.")
    return json.loads(cp["stdout"].strip().splitlines()[-1])

def compare_exact(expected, actual):
    expected_keys = set(expected)
    actual_keys = set(actual) - BOOTSTRAP_IGNORED
    missing = sorted(expected_keys - actual_keys)
    unexpected = sorted(actual_keys - expected_keys)
    mismatches = []
    for key in sorted(expected_keys & actual_keys):
        if actual[key]["version"] != expected[key]["version"]:
            mismatches.append({
                "distribution": expected[key]["name"],
                "expected": expected[key]["version"],
                "actual": actual[key]["version"],
            })
    return {
        "expected_count": len(expected_keys),
        "actual_count_excluding_bootstrap": len(actual_keys),
        "missing": missing,
        "unexpected": unexpected,
        "version_mismatches": mismatches,
        "exact": not missing and not unexpected and not mismatches,
    }

def import_checks(python_exe: Path, expected):
    checks = {}
    for dist, module in IMPORT_MAP.items():
        if canonical(dist) not in expected:
            continue
        code = "import importlib.util,sys;" + f"sys.exit(0 if importlib.util.find_spec({module!r}) else 2)"
        probe = run([str(python_exe), "-c", code], timeout=60)
        checks[module] = probe["returncode"] == 0
    return checks

def gpu_probe(python_exe: Path):
    code = r"""
import json,torch,torchaudio
if not torch.cuda.is_available():
    raise RuntimeError("CUDA unavailable")
x=torch.arange(1,5,dtype=torch.float32,device="cuda")
y=(x@x)
torch.cuda.synchronize()
print(json.dumps({
 "torch":torch.__version__,
 "torchaudio":torchaudio.__version__,
 "cuda_available":bool(torch.cuda.is_available()),
 "cuda_version":getattr(torch.version,"cuda",None),
 "cudnn":torch.backends.cudnn.version(),
 "device":torch.cuda.get_device_name(0),
 "cuda_dot":float(y.cpu())
}))
"""
    cp=run([str(python_exe),"-c",code],timeout=180)
    out={"returncode":cp["returncode"],"stderr":cp["stderr"]}
    if cp["returncode"]==0 and cp["stdout"].strip():
        out.update(json.loads(cp["stdout"].strip().splitlines()[-1]))
    return out

def report_origins(path: Path):
    data=json.loads(path.read_text(encoding="utf-8"))
    rows={}
    for item in data.get("install",[]):
        meta=item.get("metadata") or {}
        name=meta.get("name")
        if not name:
            continue
        url=(item.get("download_info") or {}).get("url")
        rows[canonical(name)]={
            "name":name,
            "version":meta.get("version"),
            "url":url,
            "host":urlparse(url).hostname if url else None,
        }
    return rows

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--profile",choices=["core","voice","gpu","full"],default="core")
    ap.add_argument("--network",action="store_true")
    ap.add_argument("--no-cache",action="store_true")
    ap.add_argument("--keep",action="store_true")
    args=ap.parse_args()

    report_path=REPORT_DIR/f"cold_install_{args.profile}_result.json"
    result={
        "schema":"aura.cold-install-verifier.v0862.2.v1",
        "gate_revision":"v0.8.6.2.2",
        "profile":args.profile,
        "strict_exact_lock":True,
        "network_install_requested":args.network,
        "no_cache_requested":args.no_cache,
        "errors":[],
        "steps":[],
        "pass":False,
    }
    temp_root=None
    try:
        if sys.version_info[:2] != (3,14):
            raise RuntimeError("Python 3.14 is required.")
        if sys.platform!="win32" or platform.machine().upper()!="AMD64":
            raise RuntimeError("Windows AMD64 is required.")

        meta=json.loads(LOCK_META.read_text(encoding="utf-8"))
        parsed,contract=validate_lock_contract(meta)
        result["lock_contract"]=contract

        selected=args.profile
        expected_profile="full" if selected in {"gpu","full"} else selected
        expected=parsed[expected_profile]["rows"]
        result["lock"]={
            "path":str(parsed[expected_profile]["path"]),
            "sha256":sha256(parsed[expected_profile]["path"]),
            "expected_package_count":len(expected),
        }

        temp_root=Path(tempfile.gettempdir())/f"AURA_V08622_COLD_{uuid.uuid4().hex[:10]}"
        result["temporary_root"]=str(temp_root)
        temp_root.mkdir(parents=True,exist_ok=False)

        create=run([sys.executable,"-m","venv",str(temp_root)],timeout=240)
        result["steps"].append({"name":"create_venv",**create})
        if create["returncode"]!=0:
            raise RuntimeError("Temporary venv creation failed.")
        py=temp_root/"Scripts"/"python.exe"

        if not args.network:
            result["steps"].append({
                "name":"network_install",
                "status":"SKIP",
                "detail":"All CORE/VOICE/GPU/FULL lock contracts validated; use --network for exact cold-install."
            })
            result["pass"]=True
        else:
            cache_flag=["--no-cache-dir"] if args.no_cache else []
            if selected in {"core","voice"}:
                lock_path=parsed[selected]["path"]
                cmd=[str(py),"-m","pip","install","--disable-pip-version-check",*cache_flag,"-r",str(lock_path)]
                install=run(cmd,timeout=3600)
                result["steps"].append({"name":"install",**install})
                if install["returncode"]!=0:
                    raise RuntimeError("Strict temporary dependency installation failed.")
            else:
                voice_path=parsed["voice"]["path"]
                voice_cmd=[str(py),"-m","pip","install","--disable-pip-version-check",*cache_flag,"-r",str(voice_path)]
                voice_install=run(voice_cmd,timeout=3600)
                result["steps"].append({"name":"voice_base_install",**voice_install})
                if voice_install["returncode"]!=0:
                    raise RuntimeError("VOICE exact base installation failed.")

                gpu_path=parsed["gpu"]["path"]
                report=temp_root/"gpu_install_report.json"
                gpu_cmd=[
                    str(py),"-m","pip","install","--disable-pip-version-check",*cache_flag,
                    "--report",str(report),
                    "--index-url",OFFICIAL_GPU_INDEX,
                    "--extra-index-url",PYPI_INDEX,
                    "-c",str(voice_path),
                    "-r",str(gpu_path),
                ]
                gpu_install=run(gpu_cmd,timeout=5400)
                result["steps"].append({"name":"gpu_layer_install",**gpu_install})
                if gpu_install["returncode"]!=0:
                    raise RuntimeError("GPU exact layer installation failed.")

                origins=report_origins(report)
                result["gpu_install_origins"]=origins
                for target in ("torch","torchaudio"):
                    row=origins.get(target)
                    if not row or row.get("host") not in OFFICIAL_GPU_HOSTS:
                        raise RuntimeError(f"{target} did not originate from official PyTorch hosts.")

            actual=installed_map(py)
            exact=compare_exact(expected,actual)
            result["exact_comparison"]=exact
            checks=import_checks(py,expected)
            result["import_checks"]=checks

            pipcheck=run([str(py),"-m","pip","check"],timeout=120)
            result["steps"].append({"name":"pip_check",**pipcheck})

            acceptance={
                "installation":True,
                "imports":all(checks.values()),
                "pip_check":pipcheck["returncode"]==0,
                "packages_missing_zero":not exact["missing"],
                "packages_unexpected_zero":not exact["unexpected"],
                "version_mismatches_zero":not exact["version_mismatches"],
                "exact_lock_match":exact["exact"],
            }

            if selected in {"gpu","full"}:
                origins=result["gpu_install_origins"]
                probe=gpu_probe(py)
                result["gpu_probe"]=probe
                acceptance.update({
                    "torch_official_origin":origins.get("torch",{}).get("host") in OFFICIAL_GPU_HOSTS,
                    "torchaudio_official_origin":origins.get("torchaudio",{}).get("host") in OFFICIAL_GPU_HOSTS,
                    "torch_version":probe.get("torch")=="2.13.0+cu130",
                    "torchaudio_version":probe.get("torchaudio")=="2.11.0+cu130",
                    "cuda_available":probe.get("cuda_available") is True,
                    "cuda_13":str(probe.get("cuda_version"))=="13.0",
                    "cuda_operation":probe.get("cuda_dot")==30.0,
                    "torchcodec_not_installed":"torchcodec" not in actual,
                })

            result["acceptance"]=acceptance
            result["pass"]=all(acceptance.values())

    except Exception as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        if temp_root and temp_root.exists() and not args.keep:
            try:
                shutil.rmtree(temp_root)
                result["temporary_venv_removed"]=True
            except Exception as exc:
                result["temporary_venv_removed"]=False
                result["errors"].append(f"CleanupError: {type(exc).__name__}: {exc}")
                result["pass"]=False
        elif temp_root and temp_root.exists():
            result["temporary_venv_removed"]=False
            result["temporary_venv_kept"]=True

        REPORT_DIR.mkdir(parents=True,exist_ok=True)
        report_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        print("PASS GLOBAL" if result["pass"] else "FAIL GLOBAL")
        print("Report:",report_path)

    return 0 if result["pass"] else 2

if __name__=="__main__":
    raise SystemExit(main())
