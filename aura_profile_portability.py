from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Iterable, Mapping

SCHEMA = "aura.profile.v1"
PATCH = "P0.8.5.4.1.1"
PROFILE_EXTENSION = ".auraprofile"

# Explicit, secret-free, machine-portable settings only.
PORTABLE_ENV_KEYS = (
    "AURA_RUNTIME_MODE",
    "AURA_ADAPTIVE_ENABLED",
    "AURA_ADAPTIVE_PROFILE",
    "AURA_ADAPTIVE_MODEL_SELECTION",
    "AURA_ADAPTIVE_VISUAL_BUDGET",
    "AURA_ADAPTIVE_WORKLOAD_BUDGET",
    "DOCUMENT_ANALYSIS_PROVIDER",
    "DOCUMENT_CLOUD_ENABLED",
    "GEMINI_ENABLED",
    "GROQ_ENABLED",
    "GROQ_STT_ENABLED",
    "LOCAL_LLM_ENABLED",
    "LOCAL_LLM_PROVIDER",
    "LOCAL_LLM_MODEL",
    "LLM_TEXT_MODEL",
    "LLM_VOICE_MODEL",
    "DUAL_BRAIN_ENABLED",
    "DUAL_BRAIN_VOICE_KEEP_ALIVE",
    "VOICE_ENABLED",
    "TTS_ENGINE",
    "XTTS_LOCAL_FIRST_ENABLED",
    "XTTS_LOCAL_FIRST_KEEP_RESIDENT",
    "XTTS_LOCAL_FIRST_IDLE_SECONDS",
    "XTTS_PREVIEW_FAST",
    "LOG_LEVEL",
    "AGENT_ROUTER_MODEL",
)

# Machine-bound values are deliberately excluded from normal export/import.
MACHINE_ENV_KEYS = (
    "MIC_DEVICE",
    "OLLAMA_HOST",
    "XTTS_DEVICE",
    "XTTS_ALLOW_CUDA",
    "STT_DEVICE",
    "STT_MODEL_PATH",
    "OPENGL_ORB_FPS",
)

SECRET_KEY_RE = re.compile(
    r"(?i)(api[_-]?key|token|password|passwd|secret|authorization|bearer|cookie|credential|private[_-]?key)"
)
PATH_KEY_RE = re.compile(r"(?i)(path|file|folder|directory|reference_wav|wav_path)$")
ABS_WIN_RE = re.compile(r"(?i)^[a-z]:[\\/]")
URL_RE = re.compile(r"(?i)^https?://")

MODEL_ENV_KEYS = {"LOCAL_LLM_MODEL", "LLM_TEXT_MODEL", "LLM_VOICE_MODEL", "AGENT_ROUTER_MODEL"}

# JSON payloads allowed in a portable profile.
VOICE_PROFILE_NAME = "voice_profile.json"
VOICE_AUDITION_NAME = "voice_audition.json"
AUTHORIZED_HINTS_NAME = "authorized_folder_hints.json"

def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _utc_now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat()

def _resolve(path: Path) -> Path:
    try:
        return path.expanduser().resolve(strict=False)
    except Exception:
        return path.expanduser().absolute()

def _find_core(start: Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    e = dict(os.environ if env is None else env)
    seeds = []
    if e.get("AURA_ROOT"):
        seeds.append(Path(e["AURA_ROOT"]))
    if start is not None:
        seeds.append(Path(start))
    seeds += [Path.cwd(), Path(__file__).resolve().parent]
    for seed in seeds:
        p = _resolve(seed)
        if p.is_file():
            p = p.parent
        for candidate in (p, *p.parents):
            if (candidate/"core"/"version.py").is_file() and (candidate/"VERSION").is_file():
                return candidate
    raise RuntimeError("AURA Core introuvable.")

def _load_paths(core: Path, env: Mapping[str, str] | None = None):
    mod = core/"core"/"runtime"/"aura_paths.py"
    spec = importlib.util.spec_from_file_location("aura_paths_profile_p08541", mod)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.AuraPaths.resolve(core_root=core, env=dict(os.environ if env is None else env))

def _parse_env(path: Path) -> dict[str, str]:
    result = {}
    if not path.is_file():
        return result
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        result[key] = value
    return result

def _looks_machine_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    return bool(ABS_WIN_RE.match(s) or s.startswith(("/", "\\\\")) or s.startswith("%USERPROFILE%"))

def _safe_env_export(env_values: Mapping[str, str]) -> tuple[dict, list[dict]]:
    exported = {}
    omitted = []
    for key in PORTABLE_ENV_KEYS:
        if key not in env_values:
            continue
        value = str(env_values[key])
        if SECRET_KEY_RE.search(key):
            omitted.append({"key": key, "reason": "secret-key-name"})
            continue
        if _looks_machine_path(value):
            omitted.append({"key": key, "reason": "machine-path-value"})
            continue
        exported[key] = value
    for key in MACHINE_ENV_KEYS:
        if key in env_values:
            omitted.append({"key": key, "reason": "machine-bound-setting"})
    for key in env_values:
        if SECRET_KEY_RE.search(key):
            omitted.append({"key": key, "reason": "secret-excluded"})
    # stable unique omission rows
    seen = set()
    unique = []
    for row in omitted:
        token = (row["key"], row["reason"])
        if token not in seen:
            seen.add(token)
            unique.append(row)
    return exported, unique

def _scrub_json(value, key: str = "", omitted: list[dict] | None = None):
    omitted = omitted if omitted is not None else []
    if SECRET_KEY_RE.search(str(key)):
        omitted.append({"key": str(key), "reason": "secret-key"})
        return None, False
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if SECRET_KEY_RE.search(str(k)):
                omitted.append({"key": str(k), "reason": "secret-key"})
                continue
            if PATH_KEY_RE.search(str(k)) and isinstance(v, str) and v.strip():
                omitted.append({"key": str(k), "reason": "machine-path"})
                continue
            clean, keep = _scrub_json(v, str(k), omitted)
            if keep:
                out[k] = clean
        return out, True
    if isinstance(value, list):
        arr = []
        for v in value:
            clean, keep = _scrub_json(v, key, omitted)
            if keep:
                arr.append(clean)
        return arr, True
    if isinstance(value, str):
        if _looks_machine_path(value):
            omitted.append({"key": str(key), "reason": "machine-path-value"})
            return None, False
        return value, True
    if value is None or isinstance(value, (bool, int, float)):
        return value, True
    return str(value), True

def _read_scrubbed_json(path: Path) -> tuple[dict | list | None, list[dict]]:
    omitted: list[dict] = []
    if not path.is_file():
        return None, omitted
    data = json.loads(path.read_text(encoding="utf-8"))
    clean, keep = _scrub_json(data, path.name, omitted)
    return clean if keep else None, omitted

def _authorized_hints(path: Path) -> dict:
    result = {"schema": "aura.authorized-folder-hints.v1", "folders": []}
    if not path.is_file():
        return result
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return result
    for row in data.get("folders") or []:
        if not isinstance(row, dict):
            continue
        label = str(row.get("label") or "").strip()
        if label:
            result["folders"].append({"label": label, "requires_reauthorization": True})
    return result

def _canonical_model_match(requested: str, actual: str) -> bool:
    req = str(requested or "").strip().casefold()
    act = str(actual or "").strip().casefold()
    if not req or not act:
        return False
    if req == act:
        return True
    if ":" not in req:
        return act.split(":", 1)[0] == req
    return False

def _ollama_models(host: str = "http://127.0.0.1:11434") -> tuple[str, ...]:
    parsed = urllib.parse.urlparse(host)
    if (parsed.hostname or "").casefold() not in {"127.0.0.1", "localhost", "::1"}:
        return ()
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/api/tags", timeout=2.0) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        return tuple(
            str(item.get("name") or item.get("model") or "").strip()
            for item in (data.get("models") or [])
            if str(item.get("name") or item.get("model") or "").strip()
        )
    except Exception:
        return ()

def _profile_payloads(profile_path: Path) -> tuple[dict, dict[str, bytes]]:
    with zipfile.ZipFile(profile_path, "r") as z:
        names = set(z.namelist())
        if "manifest.json" not in names:
            raise ValueError("manifest.json absent")
        manifest = json.loads(z.read("manifest.json"))
        if manifest.get("schema") != SCHEMA:
            raise ValueError("schema profil non supporte")
        payloads = {}
        for name, expected in (manifest.get("checksums") or {}).items():
            if name not in names:
                raise ValueError(f"payload absent: {name}")
            data = z.read(name)
            if _sha_bytes(data) != expected:
                raise ValueError(f"checksum invalide: {name}")
            payloads[name] = data
        return manifest, payloads

def export_profile(
    output: Path | str | None = None,
    *,
    core_root: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict:
    core = _find_core(core_root, env)
    paths = _load_paths(core, env)
    env_values = _parse_env(core/".env")
    portable_env, env_omitted = _safe_env_export(env_values)

    voice_profile, voice_omitted = _read_scrubbed_json(paths.config_root/VOICE_PROFILE_NAME)
    voice_audition, audition_omitted = _read_scrubbed_json(paths.config_root/VOICE_AUDITION_NAME)
    hints = _authorized_hints(paths.config_root/"authorized_folders.json")

    preferences = {
        "schema": "aura.profile.preferences.v1",
        "environment": portable_env,
    }
    payload_objs: dict[str, object] = {
        "preferences.json": preferences,
        AUTHORIZED_HINTS_NAME: hints,
    }
    if voice_profile is not None:
        payload_objs[VOICE_PROFILE_NAME] = voice_profile
    if voice_audition is not None:
        payload_objs[VOICE_AUDITION_NAME] = voice_audition

    payload_bytes = {
        name: (json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        for name, obj in payload_objs.items()
    }

    omitted = env_omitted + voice_omitted + audition_omitted
    manifest = {
        "schema": SCHEMA,
        "patch": PATCH,
        "format_version": 1,
        "created_at": _utc_now(),
        "source_version": (core/"VERSION").read_text(encoding="utf-8").strip(),
        "source_deployment_mode": paths.deployment_mode,
        "portable": True,
        "contains_secrets": False,
        "payloads": sorted(payload_bytes),
        "checksums": {name: _sha_bytes(data) for name, data in payload_bytes.items()},
        "omitted": omitted,
        "guarantees": {
            "api_keys": "excluded",
            "tokens_passwords": "excluded",
            "database": "excluded",
            "logs": "excluded",
            "cache_temp": "excluded",
            "model_weights": "excluded",
            "hardware_cache": "excluded",
            "authorized_folder_paths": "excluded-label-hints-only",
            "machine_paths": "excluded",
        },
    }
    manifest_bytes = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    if output is None:
        stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        output = Path.cwd()/f"AURA_Profile_{stamp}{PROFILE_EXTENSION}"
    output = Path(output)
    if output.suffix.lower() != PROFILE_EXTENSION:
        output = output.with_suffix(PROFILE_EXTENSION)
    output.parent.mkdir(parents=True, exist_ok=True)

    tmp = output.with_suffix(output.suffix + ".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", manifest_bytes)
        for name, data in payload_bytes.items():
            z.writestr(name, data)
    os.replace(tmp, output)

    return {
        "profile": str(output.resolve()),
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "manifest": manifest,
        "exported_env_keys": sorted(portable_env),
        "authorized_folder_hints": len(hints["folders"]),
    }

def preview_import(
    profile_path: Path | str,
    *,
    core_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    installed_models: Iterable[str] | None = None,
) -> dict:
    core = _find_core(core_root, env)
    paths = _load_paths(core, env)
    profile_path = Path(profile_path)
    manifest, payloads = _profile_payloads(profile_path)

    prefs = json.loads(payloads.get("preferences.json", b'{"environment":{}}'))
    incoming_env = dict(prefs.get("environment") or {})
    current_env = _parse_env(core/".env")

    changes = []
    skipped = []
    for key in sorted(incoming_env):
        if key not in PORTABLE_ENV_KEYS or SECRET_KEY_RE.search(key):
            skipped.append({"key": key, "reason": "not-portable-or-sensitive"})
            continue
        value = str(incoming_env[key])
        if _looks_machine_path(value):
            skipped.append({"key": key, "reason": "machine-path"})
            continue
        changes.append({
            "kind": "env",
            "key": key,
            "current": current_env.get(key),
            "incoming": value,
            "changed": current_env.get(key) != value,
        })

    models = tuple(installed_models) if installed_models is not None else _ollama_models(
        current_env.get("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    model_warnings = []
    model_decisions = []
    for row in changes:
        if row["key"] not in MODEL_ENV_KEYS or not row["incoming"]:
            row["will_apply"] = True
            row["skip_reason"] = None
            continue
        if not models:
            decision = {
                "key": row["key"],
                "requested": row["incoming"],
                "installed_match": None,
                "will_apply": False,
                "reason": "model-catalog-unavailable",
                "action": "skip-on-import",
            }
        else:
            match = next((m for m in models if _canonical_model_match(row["incoming"], m)), None)
            if match:
                decision = {
                    "key": row["key"],
                    "requested": row["incoming"],
                    "installed_match": match,
                    "will_apply": True,
                    "reason": "model-installed",
                    "action": "apply",
                }
            else:
                decision = {
                    "key": row["key"],
                    "requested": row["incoming"],
                    "installed_match": None,
                    "will_apply": False,
                    "reason": "model-not-installed",
                    "action": "skip-on-import",
                }
        row["will_apply"] = bool(decision["will_apply"])
        row["skip_reason"] = None if decision["will_apply"] else decision["reason"]
        model_decisions.append(decision)
        if not decision["will_apply"]:
            model_warnings.append(dict(decision))

    json_changes = []
    for name in (VOICE_PROFILE_NAME, VOICE_AUDITION_NAME):
        if name not in payloads:
            continue
        incoming = json.loads(payloads[name])
        target = paths.config_root/name
        current = {}
        if target.is_file():
            try:
                current = json.loads(target.read_text(encoding="utf-8"))
            except Exception:
                current = {}
        if isinstance(incoming, dict):
            keys = sorted(incoming)
            changed = [k for k in keys if current.get(k) != incoming.get(k)]
        else:
            changed = ["<payload>"] if current != incoming else []
        json_changes.append({
            "name": name,
            "target": str(target),
            "changed_keys": changed,
            "will_merge": True,
        })

    hints = json.loads(payloads.get(AUTHORIZED_HINTS_NAME, b'{"folders":[]}'))
    configured_secret_names = [
        key for key, value in current_env.items()
        if SECRET_KEY_RE.search(key) and str(value).strip()
    ]
    warnings = list(model_warnings)
    if hints.get("folders"):
        warnings.append({
            "reason": "authorized-folders-require-reauthorization",
            "labels": [x.get("label") for x in hints["folders"] if x.get("label")],
            "action": "no-path-import",
        })

    return {
        "schema": "aura.profile.preview.v1",
        "profile": str(profile_path.resolve()),
        "source_version": manifest.get("source_version"),
        "target_version": (core/"VERSION").read_text(encoding="utf-8").strip(),
        "contains_secrets": bool(manifest.get("contains_secrets")),
        "checksum_validation": "PASS",
        "env_changes": changes,
        "json_changes": json_changes,
        "skipped": skipped,
        "warnings": warnings,
        "model_decisions": model_decisions,
        "installed_models": list(models),
        "configured_secret_key_names": sorted(configured_secret_names),
        "database_changes": False,
        "model_downloads": False,
        "authorized_folder_paths_imported": False,
        "requires_explicit_apply": True,
    }

def _write_env_updates(path: Path, updates: Mapping[str, str], skip_keys: set[str]) -> None:
    original = path.read_text(encoding="utf-8", errors="replace").splitlines() if path.is_file() else []
    done = set()
    out = []
    for raw in original:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            out.append(raw)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in updates and key not in skip_keys:
            value = str(updates[key]).replace("\r", "").replace("\n", "")
            out.append(f"{key}={value}")
            done.add(key)
        else:
            out.append(raw)
    missing = [k for k in sorted(updates) if k not in done and k not in skip_keys]
    if missing:
        if out and out[-1].strip():
            out.append("")
        out.append("# AURA portable profile import")
        for key in missing:
            value = str(updates[key]).replace("\r", "").replace("\n", "")
            out.append(f"{key}={value}")
    tmp = path.with_suffix(path.suffix + ".profile.tmp")
    tmp.write_text("\n".join(out) + "\n", encoding="utf-8", newline="\n")
    os.replace(tmp, path)

def _merge_json(target: Path, incoming):
    current = {}
    if target.is_file():
        try:
            current = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    if isinstance(current, dict) and isinstance(incoming, dict):
        merged = dict(current)
        merged.update(incoming)
    else:
        merged = incoming
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".profile.tmp")
    tmp.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, target)

def import_profile(
    profile_path: Path | str,
    *,
    apply: bool = False,
    core_root: Path | None = None,
    env: Mapping[str, str] | None = None,
    installed_models: Iterable[str] | None = None,
) -> dict:
    preview = preview_import(
        profile_path,
        core_root=core_root,
        env=env,
        installed_models=installed_models,
    )
    if not apply:
        return {"applied": False, "preview": preview}

    core = _find_core(core_root, env)
    paths = _load_paths(core, env)
    profile_path = Path(profile_path)
    manifest, payloads = _profile_payloads(profile_path)

    prefs = json.loads(payloads.get("preferences.json", b'{"environment":{}}'))
    incoming_env = {
        k: str(v) for k, v in (prefs.get("environment") or {}).items()
        if k in PORTABLE_ENV_KEYS and not SECRET_KEY_RE.search(k) and not _looks_machine_path(str(v))
    }

    skip_keys = {
        d["key"] for d in preview.get("model_decisions", [])
        if isinstance(d, dict) and d.get("action") == "skip-on-import" and d.get("key")
    }

    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = paths.config_root/"profile_backups"/f"import_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    targets = [core/".env", paths.config_root/VOICE_PROFILE_NAME, paths.config_root/VOICE_AUDITION_NAME]
    backup_manifest = {"schema": "aura.profile.rollback.v1", "created_at": _utc_now(), "files": []}
    for target in targets:
        row = {"target": str(target), "existed": target.is_file(), "backup": None}
        if target.is_file():
            backup = backup_dir/(target.name + ".before")
            shutil.copy2(target, backup)
            row["backup"] = str(backup)
        backup_manifest["files"].append(row)
    (backup_dir/"rollback.json").write_text(
        json.dumps(backup_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    try:
        _write_env_updates(core/".env", incoming_env, skip_keys)
        for name in (VOICE_PROFILE_NAME, VOICE_AUDITION_NAME):
            if name in payloads:
                incoming = json.loads(payloads[name])
                _merge_json(paths.config_root/name, incoming)

        result = {
            "applied": True,
            "profile": str(profile_path.resolve()),
            "backup_dir": str(backup_dir),
            "env_keys_applied": sorted(k for k in incoming_env if k not in skip_keys),
            "env_keys_skipped": sorted(skip_keys),
            "json_payloads_applied": [n for n in (VOICE_PROFILE_NAME, VOICE_AUDITION_NAME) if n in payloads],
            "authorized_folder_paths_imported": False,
            "hardware_cache_imported": False,
            "database_changed": False,
            "model_downloads": False,
            "secrets_changed": False,
        }
        (backup_dir/"import_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result
    except Exception:
        rollback_import(backup_dir)
        raise

def rollback_import(backup_dir: Path | str) -> dict:
    backup_dir = Path(backup_dir)
    manifest_path = backup_dir/"rollback.json"
    if not manifest_path.is_file():
        raise FileNotFoundError("rollback.json absent")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    restored = []
    removed = []
    for row in data.get("files") or []:
        target = Path(row["target"])
        if row.get("existed"):
            backup = Path(row.get("backup") or "")
            if not backup.is_file():
                raise FileNotFoundError(f"backup absent: {backup}")
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored.append(str(target))
        elif target.exists():
            target.unlink()
            removed.append(str(target))
    return {"rolled_back": True, "restored": restored, "removed": removed, "backup_dir": str(backup_dir)}

def latest_backup(*, core_root: Path | None = None, env: Mapping[str, str] | None = None) -> Path | None:
    core = _find_core(core_root, env)
    paths = _load_paths(core, env)
    root = paths.config_root/"profile_backups"
    if not root.is_dir():
        return None
    dirs = [p for p in root.iterdir() if p.is_dir() and (p/"rollback.json").is_file()]
    return max(dirs, key=lambda p: p.stat().st_mtime) if dirs else None

def self_test() -> bool:
    assert SECRET_KEY_RE.search("GROQ_API_KEY")
    assert "LOCAL_LLM_MODEL" in PORTABLE_ENV_KEYS
    assert "XTTS_DEVICE" not in PORTABLE_ENV_KEYS
    clean, omitted = _safe_env_export({
        "LOCAL_LLM_MODEL": "llama3.1",
        "GROQ_API_KEY": "never-export",
        "XTTS_DEVICE": "cuda",
    })
    return (
        clean == {"LOCAL_LLM_MODEL": "llama3.1"}
        and any(x["key"] == "GROQ_API_KEY" for x in omitted)
        and any(x["key"] == "XTTS_DEVICE" for x in omitted)
        and _canonical_model_match("llama3.1", "llama3.1:latest")
        and not _canonical_model_match("llama3.1", "llama3.2:3b")
    )

if __name__ == "__main__":
    print(json.dumps({"self_test": self_test(), "schema": SCHEMA}, indent=2))
