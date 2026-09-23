"""AURA ADF-H R7.2.7 — Coding Agent -> AFG -> Sandbox Binding.

This layer joins the already-certified AURA components without granting a
third-party coding client production-write authority:

    coding agent -> AURA Fabric Gateway -> provider/model
                 -> isolated working copy
                 -> harvested proposed edits only

The source tree is never the agent cwd. Explicit source inputs and critical
AURA authority files are guarded and restored if an external agent attempts
to mutate them. The child receives the local AFG credential only; provider
credentials are not inherited.

R7.2.7 intentionally does NOT call ADF-F/G and does NOT apply sandbox edits.
A later gate will convert harvested text edits into ADF-F proposals.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

from runtime import aura_fabric_coding_agent_executor as _executor
from runtime.aura_fabric_agent_bridge import detection_snapshot
from runtime.aura_fabric_http_gateway import (
    GatewayConfig,
    build_production_service,
    create_server,
)

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
BINDING_ID = "ADF-H-R7.2.7-CODING-AGENT-AFG-SANDBOX"

_DEFAULT_MODEL = "aura-code"
_DEFAULT_TIMEOUT_SECONDS = 300.0
_DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024
_MAX_TEXT_EDIT_BYTES = 2 * 1024 * 1024

_PROTECTED_NAMES = {
    ".git",
    ".aura_audit",
    ".aura_transactions",
    "_patch_backups",
}
_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    "credentials.json",
    "secrets.json",
    "id_rsa",
    "id_ed25519",
}
_SECRET_SUFFIXES = {".pem", ".p12", ".pfx", ".key"}

_AUTHORITY_FILES = (
    ROOT / "core" / "version.py",
    ROOT / "runtime" / "aura_fabric_http_gateway.py",
    ROOT / "runtime" / "aura_fabric_live_provider_adapters.py",
    ROOT / "runtime" / "aura_fabric_protocols.py",
    ROOT / "runtime" / "aura_fabric_provider_adapter.py",
    ROOT / "runtime" / "aura_fabric_resilience.py",
    ROOT / "runtime" / "aura_fabric_agent_bridge.py",
    ROOT / "runtime" / "aura_fabric_coding_agent_executor.py",
    ROOT / "runtime" / "aura_patch_transaction_engine.py",
    ROOT / "runtime" / "aura_self_development_governance.py",
    ROOT / "runtime" / "aura_developer_general_live.py",
    ROOT / "ui" / "main_window.py",
)

_ENV_LOCK = threading.RLock()


@dataclass(frozen=True)
class SandboxFile:
    relative_path: str
    source_path: str
    sandbox_path: str
    baseline_sha256: str
    size_bytes: int


@dataclass(frozen=True)
class SandboxManifest:
    schema: str
    session_id: str
    source_root: str
    sandbox_root: str
    include_paths: tuple[str, ...]
    files: tuple[SandboxFile, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SandboxChange:
    relative_path: str
    source_path: str
    sandbox_path: str
    change_type: str
    before_sha256: str | None
    after_sha256: str | None
    size_bytes: int | None
    text_edit: bool
    new_text: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GatewayLease:
    root_url: str
    local_token: str
    owned: bool
    server: Any = None
    thread: threading.Thread | None = None

    def close(self) -> None:
        if not self.owned or self.server is None:
            return
        try:
            self.server.shutdown()
        except Exception:
            pass
        try:
            self.server.server_close()
        except Exception:
            pass
        if self.thread is not None:
            try:
                self.thread.join(timeout=3.0)
            except Exception:
                pass
        self.server = None
        self.thread = None


class SourceIntegrityError(RuntimeError):
    pass


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def _is_secret_path(path: Path) -> bool:
    name = path.name.casefold()
    if name in _SECRET_NAMES:
        return True
    if path.suffix.casefold() in _SECRET_SUFFIXES:
        return True
    folded_parts = {part.casefold() for part in path.parts}
    return bool(folded_parts.intersection({x.casefold() for x in _PROTECTED_NAMES}))


def _safe_relative(raw: str | Path) -> Path:
    path = Path(str(raw))
    if path.is_absolute():
        raise ValueError(f"include path must be relative: {path}")
    if any(part in ("", ".", "..") for part in path.parts):
        if ".." in path.parts:
            raise ValueError(f"include path escapes source root: {path}")
    return path


def _iter_regular_files(path: Path) -> Iterable[Path]:
    if path.is_symlink():
        raise PermissionError(f"symlink/reparse source input is not allowed: {path}")
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        raise FileNotFoundError(path)
    for item in sorted(path.rglob("*")):
        if item.is_symlink():
            raise PermissionError(f"symlink/reparse source input is not allowed: {item}")
        if item.is_file():
            yield item


def _copy_input_file(source: Path, destination: Path) -> None:
    if _is_secret_path(source):
        raise PermissionError(f"secret/protected source file refused: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def prepare_sandbox(
    source_root: str | Path,
    include_paths: Iterable[str | Path],
    *,
    sandbox_parent: str | Path | None = None,
) -> SandboxManifest:
    """Copy only explicit inputs into an external working directory."""
    source = Path(source_root).expanduser().resolve(strict=True)
    if not source.is_dir():
        raise ValueError(f"source_root is not a directory: {source}")

    includes = tuple(str(_safe_relative(x)).replace("\\", "/") for x in include_paths)
    if not includes:
        raise ValueError("at least one explicit include path is required")

    if sandbox_parent is None:
        parent = Path(tempfile.gettempdir()) / "aura_fabric_coding_sessions"
    else:
        parent = Path(sandbox_parent).expanduser().resolve(strict=False)

    if parent == ROOT or _within(parent, ROOT):
        raise PermissionError("sandbox parent must be outside the canonical AURA repository")
    parent.mkdir(parents=True, exist_ok=True)

    session_id = "coding_" + uuid.uuid4().hex
    sandbox = Path(tempfile.mkdtemp(prefix=session_id + "_", dir=str(parent))).resolve()

    copied: list[SandboxFile] = []
    seen: set[str] = set()

    try:
        for rel_text in includes:
            rel = Path(rel_text)
            src_item = (source / rel).resolve(strict=True)
            if src_item != source and not _within(src_item, source):
                raise PermissionError(f"source input escapes root: {rel_text}")

            for src_file in _iter_regular_files(src_item):
                if _is_secret_path(src_file):
                    raise PermissionError(f"secret/protected source file refused: {src_file}")
                file_rel = src_file.relative_to(source)
                rel_key = file_rel.as_posix()
                if rel_key in seen:
                    continue
                seen.add(rel_key)
                dst = sandbox / file_rel
                _copy_input_file(src_file, dst)
                copied.append(SandboxFile(
                    relative_path=rel_key,
                    source_path=str(src_file),
                    sandbox_path=str(dst),
                    baseline_sha256=_sha256(dst),
                    size_bytes=dst.stat().st_size,
                ))

        if not copied:
            raise ValueError("explicit inputs produced no regular files")

        return SandboxManifest(
            schema="aura.fabric.coding-sandbox-manifest.v1",
            session_id=session_id,
            source_root=str(source),
            sandbox_root=str(sandbox),
            include_paths=includes,
            files=tuple(copied),
        )
    except Exception:
        shutil.rmtree(sandbox, ignore_errors=True)
        raise


def remove_sandbox(manifest: SandboxManifest) -> None:
    sandbox = Path(manifest.sandbox_root).resolve(strict=False)
    parent = Path(tempfile.gettempdir()).resolve(strict=False)
    if sandbox == ROOT or _within(sandbox, ROOT):
        raise PermissionError("refusing to remove an AURA repository path")
    # A custom external sandbox_parent is allowed; session-id prefix is required.
    if not sandbox.name.startswith(manifest.session_id + "_"):
        raise PermissionError("sandbox identity mismatch")
    shutil.rmtree(sandbox, ignore_errors=True)


def _current_sandbox_files(manifest: SandboxManifest) -> dict[str, Path]:
    root = Path(manifest.sandbox_root).resolve(strict=True)
    out: dict[str, Path] = {}
    for item in root.rglob("*"):
        if item.is_symlink():
            raise SourceIntegrityError(f"agent created a symlink/reparse entry: {item}")
        if not item.is_file():
            continue
        rel = item.relative_to(root).as_posix()
        if _is_secret_path(item):
            raise SourceIntegrityError(f"agent created a secret/protected file in sandbox: {rel}")
        out[rel] = item
    return out


def _read_text_edit(path: Path) -> tuple[bool, str | None]:
    size = path.stat().st_size
    if size > _MAX_TEXT_EDIT_BYTES:
        return False, None
    raw = path.read_bytes()
    if b"\x00" in raw:
        return False, None
    try:
        return True, raw.decode("utf-8")
    except UnicodeDecodeError:
        return False, None


def collect_sandbox_changes(manifest: SandboxManifest) -> tuple[SandboxChange, ...]:
    baseline = {item.relative_path: item for item in manifest.files}
    current = _current_sandbox_files(manifest)
    changes: list[SandboxChange] = []

    for rel, before in sorted(baseline.items()):
        now = current.pop(rel, None)
        if now is None:
            changes.append(SandboxChange(
                relative_path=rel,
                source_path=before.source_path,
                sandbox_path=before.sandbox_path,
                change_type="deleted",
                before_sha256=before.baseline_sha256,
                after_sha256=None,
                size_bytes=None,
                text_edit=False,
                new_text=None,
            ))
            continue
        after_hash = _sha256(now)
        if after_hash == before.baseline_sha256:
            continue
        is_text, new_text = _read_text_edit(now)
        changes.append(SandboxChange(
            relative_path=rel,
            source_path=before.source_path,
            sandbox_path=str(now),
            change_type="modified",
            before_sha256=before.baseline_sha256,
            after_sha256=after_hash,
            size_bytes=now.stat().st_size,
            text_edit=is_text,
            new_text=new_text,
        ))

    source_root = Path(manifest.source_root)
    for rel, now in sorted(current.items()):
        is_text, new_text = _read_text_edit(now)
        changes.append(SandboxChange(
            relative_path=rel,
            source_path=str(source_root / Path(rel)),
            sandbox_path=str(now),
            change_type="created",
            before_sha256=None,
            after_sha256=_sha256(now),
            size_bytes=now.stat().st_size,
            text_edit=is_text,
            new_text=new_text,
        ))

    return tuple(changes)


def changes_to_adf_f_edits(changes: Iterable[SandboxChange]) -> tuple[dict[str, str], ...]:
    """Convert non-destructive UTF-8 changes to the ADF-F full-file edit shape.

    This function performs no proposal/apply action itself.
    """
    edits: list[dict[str, str]] = []
    for change in changes:
        if change.change_type == "deleted":
            raise ValueError("R7.2.7 does not translate deletions to ADF-F edits")
        if not change.text_edit or change.new_text is None:
            raise ValueError(f"non-UTF8 or oversized edit cannot be translated: {change.relative_path}")
        edits.append({"path": change.relative_path, "new_text": change.new_text})
    return tuple(edits)


def _guard_scope_files(manifest: SandboxManifest) -> tuple[Path, ...]:
    source_root = Path(manifest.source_root).resolve(strict=True)
    files: set[Path] = {Path(item.source_path).resolve(strict=True) for item in manifest.files}
    for path in _AUTHORITY_FILES:
        if path.is_file():
            files.add(path.resolve(strict=True))
    return tuple(sorted(files, key=lambda x: str(x).casefold()))


def _make_source_guard(manifest: SandboxManifest) -> tuple[Path, dict[str, dict[str, Any]]]:
    # R7.2.7 R1: guard backups must not live inside the agent working copy.
    # Keeping them external prevents the agent from seeing them through cwd
    # traversal and prevents collect_sandbox_changes() from harvesting guard
    # backups as false "created" edits.
    guard_parent = Path(tempfile.gettempdir()) / "aura_fabric_source_guards"
    guard_parent.mkdir(parents=True, exist_ok=True)
    guard_root = Path(tempfile.mkdtemp(
        prefix=manifest.session_id + "_guard_",
        dir=str(guard_parent),
    )).resolve()
    sandbox_root = Path(manifest.sandbox_root).resolve(strict=True)
    if guard_root == sandbox_root or _within(guard_root, sandbox_root):
        shutil.rmtree(guard_root, ignore_errors=True)
        raise PermissionError("source guard must be outside the coding-agent sandbox")
    if guard_root == ROOT or _within(guard_root, ROOT):
        shutil.rmtree(guard_root, ignore_errors=True)
        raise PermissionError("source guard must be outside the canonical AURA repository")

    records: dict[str, dict[str, Any]] = {}
    for index, source in enumerate(_guard_scope_files(manifest)):
        backup = guard_root / f"{index:04d}.bin"
        shutil.copy2(source, backup)
        records[str(source)] = {
            "sha256": _sha256(source),
            "backup": str(backup),
        }
    return guard_root, records


def _restore_source_guard(records: dict[str, dict[str, Any]]) -> tuple[str, ...]:
    restored: list[str] = []
    for raw_path, record in records.items():
        path = Path(raw_path)
        before_hash = str(record["sha256"])
        current_hash = _sha256(path) if path.is_file() else None
        if current_hash == before_hash:
            continue
        backup = Path(str(record["backup"]))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".aura-r727-restore")
        shutil.copy2(backup, tmp)
        os.replace(tmp, path)
        restored.append(str(path))
    return tuple(restored)


def _validate_agent_arguments(
    agent_arguments: Iterable[str],
    *,
    source_root: Path,
) -> tuple[str, ...]:
    args = tuple(str(x) for x in agent_arguments)
    forbidden = {
        str(ROOT).casefold(),
        str(source_root).casefold(),
    }
    for arg in args:
        folded = arg.casefold()
        for raw in forbidden:
            if raw and raw in folded:
                raise PermissionError(
                    "agent arguments must reference sandbox-relative paths, not production/source absolute paths"
                )
    return args


def _http_json(
    url: str,
    *,
    local_token: str | None = None,
    timeout_s: float = 2.0,
) -> tuple[int, dict[str, Any]]:
    headers = {"Accept": "application/json"}
    if local_token:
        headers["Authorization"] = "Bearer " + local_token
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read().decode("utf-8")
            payload = json.loads(body) if body else {}
            return int(response.status), payload if isinstance(payload, dict) else {}
    except urllib.error.HTTPError as exc:
        try:
            body = exc.read().decode("utf-8")
            payload = json.loads(body) if body else {}
        except Exception:
            payload = {}
        return int(exc.code), payload if isinstance(payload, dict) else {}


def validate_gateway_root(root_url: str) -> str:
    parsed = urllib.parse.urlparse(str(root_url))
    if parsed.scheme != "http":
        raise PermissionError("coding-agent AFG endpoint must use local HTTP")
    if parsed.hostname not in {"127.0.0.1", "::1", "localhost"}:
        raise PermissionError("coding-agent AFG endpoint must be loopback")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise PermissionError("coding-agent AFG endpoint contains forbidden URL components")
    if parsed.path not in ("", "/"):
        raise PermissionError("coding-agent AFG root URL must not contain a path")
    port = parsed.port or 80
    host = parsed.hostname or "127.0.0.1"
    display_host = "[::1]" if host == "::1" else host
    return f"http://{display_host}:{port}"


def probe_gateway(
    root_url: str,
    *,
    local_token: str | None = None,
) -> dict[str, Any]:
    root = validate_gateway_root(root_url)
    try:
        health_status, health = _http_json(root + "/health", timeout_s=1.5)
    except Exception as exc:
        return {
            "schema": "aura.fabric.coding-gateway-probe.v1",
            "root_url": root,
            "reachable": False,
            "ready": False,
            "authorized": False,
            "aura_code_alias": False,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }

    if health_status != 200 or health.get("schema") != "aura.fabric.health.v1":
        return {
            "schema": "aura.fabric.coding-gateway-probe.v1",
            "root_url": root,
            "reachable": True,
            "ready": False,
            "authorized": False,
            "aura_code_alias": False,
            "health_status": health_status,
            "error": "listener is not a compatible AURA Fabric Gateway",
        }

    try:
        catalog_status, catalog = _http_json(
            root + "/aura/v1/catalog",
            local_token=local_token,
            timeout_s=1.5,
        )
    except Exception as exc:
        return {
            "schema": "aura.fabric.coding-gateway-probe.v1",
            "root_url": root,
            "reachable": True,
            "ready": bool(health.get("ready")),
            "authorized": False,
            "aura_code_alias": False,
            "health": health,
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }

    aliases = catalog.get("aliases") if isinstance(catalog.get("aliases"), dict) else {}
    return {
        "schema": "aura.fabric.coding-gateway-probe.v1",
        "root_url": root,
        "reachable": True,
        "ready": bool(health.get("ready")),
        "authorized": catalog_status == 200 and catalog.get("schema") == "aura.fabric.model-catalog.v1",
        "aura_code_alias": bool(aliases.get("aura-code")),
        "health": health,
        "registered_model_count": int(catalog.get("count") or 0) if catalog_status == 200 else 0,
        "aura_code_routes": list(aliases.get("aura-code") or ()),
    }


def acquire_gateway(
    root_url: str,
    *,
    local_token: str | None = None,
    auto_start: bool = True,
) -> GatewayLease:
    root = validate_gateway_root(root_url)
    token = str(local_token or os.environ.get("AURA_FABRIC_LOCAL_TOKEN") or "aura-local")

    existing = probe_gateway(root, local_token=token)
    if (
        existing.get("reachable")
        and existing.get("authorized")
        and existing.get("ready")
        and existing.get("aura_code_alias")
    ):
        return GatewayLease(root_url=root, local_token=token, owned=False)

    if existing.get("reachable"):
        raise RuntimeError(
            "A listener already occupies the AFG endpoint but is not ready/authorized "
            "with the aura-code alias; refusing to replace it."
        )
    if not auto_start:
        raise RuntimeError("AURA Fabric Gateway is not running")

    parsed = urllib.parse.urlparse(root)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 80)

    service = build_production_service(retries_per_model=1)
    registration = getattr(service, "live_adapter_registration", {})
    if int(registration.get("registered_count") or 0) <= 0:
        raise RuntimeError(
            "No configured ADF-C-eligible live provider is registered in AFG. "
            "Configure at least one provider before a real coding-agent session."
        )

    config = GatewayConfig(
        host=host,
        port=port,
        retries_per_model=1,
        local_token=token,
        allow_non_loopback=False,
    )
    server = create_server(service=service, config=config, host=host, port=port)
    thread = threading.Thread(
        target=server.serve_forever,
        kwargs={"poll_interval": 0.05},
        daemon=True,
        name="AURA-AFG-CodingSession",
    )
    thread.start()

    lease = GatewayLease(root_url=root, local_token=token, owned=True, server=server, thread=thread)
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        probe = probe_gateway(root, local_token=token)
        if probe.get("ready") and probe.get("authorized") and probe.get("aura_code_alias"):
            return lease
        time.sleep(0.05)

    lease.close()
    raise RuntimeError("AURA Fabric Gateway did not become coding-ready")


def runtime_readiness_snapshot() -> dict[str, Any]:
    """No network: detect installed clients and configured/eligible AFG adapters."""
    agents = detection_snapshot()
    try:
        service = build_production_service(retries_per_model=1)
        registration = dict(getattr(service, "live_adapter_registration", {}) or {})
    except Exception as exc:
        registration = {
            "schema": "aura.fabric.live-adapter-pack-1.registration.v1",
            "registered_count": 0,
            "registered_provider_ids": [],
            "providers": [],
            "aliases_created": [],
            "error": f"{type(exc).__name__}: {str(exc)[:200]}",
        }

    installed = [
        item["agent_id"]
        for item in agents.get("agents", [])
        if item.get("installed") and item.get("platform_supported")
    ]
    providers = list(registration.get("registered_provider_ids") or ())
    return {
        "schema": "aura.fabric.coding-session-readiness.v1",
        "binding_id": BINDING_ID,
        "installed_agent_count": len(installed),
        "installed_agent_ids": installed,
        "registered_live_provider_count": len(providers),
        "registered_live_provider_ids": providers,
        "aura_code_alias_available": "aura-code" in set(registration.get("aliases_created") or ()),
        "ready_for_real_agent_session": bool(installed and providers),
        "network_used": False,
        "provider_calls_made": False,
    }


def _run_process_visible(
    executable: Path,
    arguments: list[str],
    *,
    workspace: Path,
    environment: dict[str, str],
    timeout_seconds: float,
    max_output_bytes: int,
    redaction_values: tuple[str, ...],
) -> dict[str, Any]:
    """Run Aider headlessly while mirroring sanitized live telemetry into AURA UI.

    R7.2.12 R5 R28:
    - no visible cmd.exe / PowerShell / console window;
    - direct shell=False child with CREATE_NO_WINDOW on Windows;
    - stdout+stderr streamed and redacted into forensic evidence;
    - a small non-authoritative JSON mirror feeds the native Developer UI;
    - canonical source authority remains unchanged.
    """
    started = time.monotonic()
    timed_out = False
    max_bytes = max(1024, int(max_output_bytes))
    captured: list[str] = []
    ui_lines: list[str] = []

    meta_keys = (
        "AURA_DEV_LIVE_AGENT_ID",
        "AURA_DEV_LIVE_MODEL",
        "AURA_DEV_LIVE_TARGET",
    )
    child_env = dict(environment)
    agent_id = str(child_env.pop("AURA_DEV_LIVE_AGENT_ID", "aider") or "aider")
    model = str(child_env.pop("AURA_DEV_LIVE_MODEL", "aura-code") or "aura-code")
    target = str(child_env.pop("AURA_DEV_LIVE_TARGET", "") or "")
    child_env["PYTHONUNBUFFERED"] = "1"

    local_appdata = Path(
        os.environ.get("LOCALAPPDATA")
        or r"C:\Users\leclerc\AppData\Local"
    ).resolve()
    ui_dist = (
        local_appdata
        / "AURA" / "ui" / "v0.7.2.2-rc4.2" / "dist"
    )
    state_path = ui_dist / "aura_developer_fabric_live_state.json"

    forensic_dir = ROOT / "runtime" / "developer_fabric" / "live_logs"
    forensic_dir.mkdir(parents=True, exist_ok=True)
    run_id = "live_" + uuid.uuid4().hex
    forensic_path = forensic_dir / f"{run_id}.log"

    secrets = tuple(
        str(value)
        for value in redaction_values
        if str(value or "")
    )

    def redact(value: str) -> str:
        text = str(value or "")
        for secret in secrets:
            text = text.replace(secret, "<redacted>")
        return text

    def atomic_state(
        *,
        active: bool,
        phase: str,
        phase_label: str,
        status: str,
        returncode: int | None = None,
    ) -> None:
        try:
            ui_dist.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema": "aura.developer-fabric-live-ui.v1",
                "run_id": run_id,
                "updated_at": time.time(),
                "active": bool(active),
                "phase": str(phase),
                "phase_label": str(phase_label),
                "status": str(status),
                "agent": agent_id,
                "model": model,
                "target": target,
                "elapsed_s": round(time.monotonic() - started, 2),
                "returncode": returncode,
                "canonical_write": False,
                "forensic_log": str(forensic_path),
                "lines": ui_lines[-240:],
            }
            tmp = state_path.with_suffix(".json.tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, state_path)
        except Exception:
            # Telemetry must never change coding-agent success/failure semantics.
            pass

    def append_line(raw: str) -> None:
        safe = redact(str(raw).rstrip("\r\n"))
        captured.append(safe + "\n")
        ui_lines.append(safe)
        if len(ui_lines) > 240:
            del ui_lines[:-240]
        try:
            with forensic_path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(safe + "\n")
        except Exception:
            pass

        folded = safe.casefold()
        if "applied edit to" in folded:
            atomic_state(
                active=True,
                phase="harvest",
                phase_label="Candidate edit generated · harvest follows",
                status="edit_generated",
            )
        elif "has hit a token limit" in folded:
            atomic_state(
                active=True,
                phase="aider",
                phase_label="Aider token limit detected",
                status="token_limit",
            )
        elif "rate limit" in folded or "http 429" in folded or "http 413" in folded:
            atomic_state(
                active=True,
                phase="afg",
                phase_label="Provider route warning",
                status="running",
            )
        else:
            atomic_state(
                active=True,
                phase="aider",
                phase_label="Aider implementation in progress",
                status="running",
            )

    header = [
        "============================================================",
        " AURA DEVELOPER FABRIC · LIVE",
        "============================================================",
        f"Agent    : {agent_id}",
        f"Model    : {model}",
        f"Target   : {target or '(managed target)'}",
        "Pipeline : sandbox -> Aider -> AFG -> harvest -> staging",
        "Source   : READ-ONLY until explicit ADF-G approval",
        "[START] Headless Aider output is mirrored into the AURA Developer UI.",
        "",
    ]
    try:
        forensic_path.write_text(
            "\n".join(header) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    ui_lines.extend(header)
    atomic_state(
        active=True,
        phase="aider",
        phase_label="Starting certified Aider subprocess",
        status="running",
    )

    proc = subprocess.Popen(
        [str(executable), *[str(x) for x in arguments]],
        cwd=str(workspace),
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        shell=False,
        creationflags=(
            getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt"
            else 0
        ),
    )

    reader_done = threading.Event()

    def reader() -> None:
        try:
            if proc.stdout is not None:
                for line in iter(proc.stdout.readline, ""):
                    if line == "":
                        break
                    append_line(line)
        finally:
            reader_done.set()

    reader_thread = threading.Thread(
        target=reader,
        name="aura-adf-live-output-reader",
        daemon=True,
    )
    reader_thread.start()

    deadline = time.monotonic() + float(timeout_seconds)
    last_heartbeat = 0.0

    while not reader_done.wait(0.2):
        now = time.monotonic()
        if now >= deadline:
            timed_out = True
            try:
                if os.name == "nt":
                    taskkill = (
                        Path(os.environ.get("SystemRoot") or r"C:\Windows")
                        / "System32" / "taskkill.exe"
                    )
                    subprocess.run(
                        [str(taskkill), "/PID", str(proc.pid), "/T", "/F"],
                        stdin=subprocess.DEVNULL,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                        timeout=10,
                    )
                else:
                    proc.kill()
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
            break

        if now - last_heartbeat >= 1.0:
            last_heartbeat = now
            atomic_state(
                active=True,
                phase="afg",
                phase_label="AFG / model generation in progress",
                status="running",
            )

    try:
        proc.wait(timeout=8)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=3)
        except Exception:
            pass

    reader_thread.join(timeout=2)

    returncode = proc.returncode
    output = "".join(captured)
    raw = output.encode("utf-8", errors="replace")
    truncated = len(raw) > max_bytes
    if truncated:
        output = (
            "<truncated-to-last-bytes>\n"
            + raw[-max_bytes:].decode("utf-8", errors="replace")
        )

    combined = output.casefold()
    if timed_out:
        final_status = "failed"
        final_phase = "aider"
        final_label = "Aider timed out · no canonical write"
    elif "applied edit to" in combined:
        final_status = "edit_generated"
        final_phase = "harvest"
        final_label = "Candidate edit generated · AURA harvesting sandbox"
    elif "has hit a token limit" in combined:
        final_status = "token_limit"
        final_phase = "aider"
        final_label = "Token limit · no canonical write"
    elif returncode == 0:
        final_status = "complete"
        final_phase = "harvest"
        final_label = "Aider complete · AURA inspecting sandbox"
    else:
        final_status = "failed"
        final_phase = "aider"
        final_label = "Aider failed · evidence preserved"

    append_line("")
    append_line("------------------------------------------------------------")
    append_line(
        f"[END] Aider exit={returncode} "
        f"elapsed={round(time.monotonic() - started, 2)}s"
    )
    atomic_state(
        active=False,
        phase=final_phase,
        phase_label=final_label,
        status=final_status,
        returncode=returncode,
    )

    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_ms": round((time.monotonic() - started) * 1000.0, 3),
        "stdout": output,
        "stderr": "",
        "stdout_truncated": truncated,
        "stderr_truncated": False,
    }




def _run_executor_bound_process(
    preflight: dict[str, Any],
    *,
    agent_id: str,
    model: str,
    workspace: Path,
    agent_arguments: tuple[str, ...],
    policy: _executor.ExecutorPolicy,
    local_token: str,
) -> _executor.AgentExecutionResult:
    """Run the certified coding agent with AFG metadata and visible live telemetry.

    R7.2.12 R5 R16:
    - keep R5 R15 Aider metadata/diff/headless protections;
    - use bounded per-model completion budgets for OpenAI-compatible AFG;
    - show a separate AURA Developer Live console with phase/elapsed telemetry;
    - keep canonical source writes, proposal, staging and approval outside this layer.
    """
    materialized = _executor._materialize_managed_plan_files(
        agent_id,
        model=model,
        workspace=workspace,
    )
    env, env_keys, secret_values = _executor._child_environment(
        materialized,
        inherit_safe=policy.inherit_safe_environment,
    )

    env.pop("AURA_ROOT", None)
    env["AURA_AGENT_WORKSPACE"] = str(workspace)

    isolated_home = Path(tempfile.mkdtemp(prefix="aura_agent_home_")).resolve()
    isolated_appdata = isolated_home / "AppData" / "Roaming"
    isolated_localappdata = isolated_home / "AppData" / "Local"
    isolated_xdg = isolated_home / ".config"
    for directory in (isolated_appdata, isolated_localappdata, isolated_xdg):
        directory.mkdir(parents=True, exist_ok=True)

    env["HOME"] = str(isolated_home)
    env["USERPROFILE"] = str(isolated_home)
    env["APPDATA"] = str(isolated_appdata)
    env["LOCALAPPDATA"] = str(isolated_localappdata)
    env["XDG_CONFIG_HOME"] = str(isolated_xdg)
    env["XDG_CACHE_HOME"] = str(isolated_home / ".cache")
    env["XDG_DATA_HOME"] = str(isolated_home / ".local" / "share")
    if os.name == "nt":
        drive, tail = os.path.splitdrive(str(isolated_home))
        env["HOMEDRIVE"] = drive or "C:"
        env["HOMEPATH"] = tail or "\\"

    runtime_names = tuple(preflight.get("runtime_secret_env_names") or ())
    for name in runtime_names:
        env[str(name)] = local_token

    live_log: Path | None = None
    monitor = None
    heartbeat_stop = threading.Event()
    heartbeat_thread = None
    run_started = time.monotonic()

    def _append_live(line: str) -> None:
        if live_log is None:
            return
        try:
            with live_log.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(str(line).rstrip() + "\n")
        except Exception:
            pass

    if str(agent_id) == "aider":
        model_metadata = {
            "openai/aura-code": {
                "max_tokens": 16384,
                "max_input_tokens": 114688,
                "max_output_tokens": 16384,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "litellm_provider": "openai",
                "mode": "chat",
            },
            "openai/groq/qwen/qwen3.6-27b": {
                "max_tokens": 16384,
                "max_input_tokens": 114688,
                "max_output_tokens": 16384,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "litellm_provider": "openai",
                "mode": "chat",
            },
            "openai/gemini/gemini-3.6-flash": {
                "max_tokens": 16384,
                "max_input_tokens": 114688,
                "max_output_tokens": 16384,
                "input_cost_per_token": 0.0,
                "output_cost_per_token": 0.0,
                "litellm_provider": "openai",
                "mode": "chat",
            },
        }
        metadata_path = isolated_home / ".aider.model.metadata.json"
        metadata_path.write_text(
            json.dumps(model_metadata, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        env["AIDER_MODEL_METADATA_FILE"] = str(metadata_path)

        # Important: Aider metadata describes limits, but does not necessarily
        # send max_tokens to arbitrary OpenAI-compatible endpoints. The explicit
        # extra_params value prevents providers from falling back to ~2K output.
        settings_path = isolated_home / ".aider.model.settings.yml"
        settings_path.write_text(
            "\n".join([
                "- name: openai/aura-code",
                "  edit_format: diff",
                "  use_repo_map: false",
                "  streaming: false",
                "  extra_params:",
                "    max_tokens: 2048",
                "- name: openai/groq/qwen/qwen3.6-27b",
                "  edit_format: diff",
                "  use_repo_map: false",
                "  streaming: false",
                "  extra_params:",
                "    max_tokens: 2048",
                "- name: openai/gemini/gemini-3.6-flash",
                "  edit_format: diff",
                "  use_repo_map: false",
                "  streaming: false",
                "  extra_params:",
                "    max_tokens: 8192",
                "",
            ]),
            encoding="utf-8",
        )
        env["AIDER_MODEL_SETTINGS_FILE"] = str(settings_path)

        no_browser = isolated_home / "aura_no_browser.cmd"
        no_browser.write_text("@echo off\r\nexit /b 0\r\n", encoding="utf-8")
        env["BROWSER"] = str(no_browser)

        if env.get("AIDER_OPENAI_API_BASE"):
            env["OPENAI_API_BASE"] = env["AIDER_OPENAI_API_BASE"]
        if env.get("AIDER_OPENAI_API_KEY"):
            env["OPENAI_API_KEY"] = env["AIDER_OPENAI_API_KEY"]

        # R5 R16 — visible operator telemetry. This monitor contains no secret
        # and only tails an ephemeral local text file.
        monitor_enabled = False and (
            os.name == "nt"
            and os.environ.get("AURA_DEV_LIVE_CONSOLE", "1") != "0"
        )
        if monitor_enabled:
            live_log = isolated_home / "aura_developer_live.log"
            target_name = next(
                (
                    str(x)
                    for x in agent_arguments
                    if str(x).lower().endswith((".js", ".py", ".css", ".html"))
                ),
                "(managed target)",
            )
            live_log.write_text(
                "\n".join([
                    "============================================================",
                    " AURA DEVELOPER FABRIC - LIVE",
                    "============================================================",
                    f"Agent      : {agent_id}",
                    f"Model      : {model}",
                    f"Target     : {target_name}",
                    "Pipeline   : sandbox -> Aider -> local AFG -> harvest -> ADF-F/G",
                    "Write      : canonical source NOT writable from this process",
                    "Status     : starting Aider...",
                    "------------------------------------------------------------",
                    "",
                ]),
                encoding="utf-8",
            )

            ps1 = isolated_home / "aura_developer_live_monitor.ps1"
            ps1.write_text(
                "\n".join([
                    "$Host.UI.RawUI.WindowTitle='AURA Developer Fabric - LIVE'",
                    "Clear-Host",
                    f"Get-Content -LiteralPath '{str(live_log).replace(chr(39), chr(39)*2)}' -Wait",
                ]),
                encoding="utf-8",
            )
            try:
                monitor = subprocess.Popen(
                    [
                        "powershell.exe",
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(ps1),
                    ],
                    stdout=None,
                    stderr=None,
                    stdin=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                    shell=False,
                )
            except Exception:
                monitor = None

            def _heartbeat() -> None:
                tick = 0
                while not heartbeat_stop.wait(2.0):
                    tick += 1
                    elapsed = int(time.monotonic() - run_started)
                    if tick == 1:
                        state = "AFG/model generation in progress"
                    else:
                        state = "still working - generation/edit/validation inside sandbox"
                    _append_live(f"[{elapsed:>4}s] {state}")

            heartbeat_thread = threading.Thread(
                target=_heartbeat,
                name="aura-dev-live-heartbeat",
                daemon=True,
            )
            heartbeat_thread.start()

    # R7.2.12 R5 R31 — native LIVE UI telemetry metadata only.
    # _run_process_visible pops these keys before spawning Aider.
    env["AURA_DEV_LIVE_AGENT_ID"] = str(agent_id)
    env["AURA_DEV_LIVE_MODEL"] = str(model)
    env["AURA_DEV_LIVE_TARGET"] = next(
        (
            str(x)
            for x in agent_arguments
            if str(x).lower().endswith((".js", ".py", ".css", ".html"))
        ),
        "(managed target)",
    )

    arguments = [
        *[str(x) for x in (materialized.get("arguments") or ())],
        *agent_arguments,
    ]

    try:
        _append_live("[RUN] Launching certified Aider subprocess...")
        run = _run_process_visible(
            preflight["executable"],
            arguments,
            workspace=workspace,
            environment=env,
            timeout_seconds=policy.timeout_seconds,
            max_output_bytes=policy.max_output_bytes,
            redaction_values=tuple(secret_values) + (local_token,),
        )
        elapsed_s = round((time.monotonic() - run_started), 2)
        _append_live("")
        _append_live("------------------------------------------------------------")
        _append_live(f"[RESULT] returncode={run['returncode']} timeout={bool(run['timed_out'])} elapsed={elapsed_s}s")

        stdout_tail = str(run.get("stdout") or "")[-14000:]
        stderr_tail = str(run.get("stderr") or "")[-6000:]
        if stdout_tail:
            _append_live("[AIDER OUTPUT - tail]")
            _append_live(stdout_tail)
        if stderr_tail:
            _append_live("[AIDER STDERR - tail]")
            _append_live(stderr_tail)

        combined = (stdout_tail + "\n" + stderr_tail).casefold()
        if "applied edit to" in combined:
            _append_live("[AURA] Candidate edit detected. Harvest/governance follows after this window.")
        elif "has hit a token limit" in combined:
            _append_live("[AURA] Aider reported token truncation. No APPLY will occur.")
        elif run["returncode"] == 0:
            _append_live("[AURA] Aider process finished. AURA will now inspect sandbox changes.")
        else:
            _append_live("[AURA] Aider process failed. AURA will preserve evidence and refuse write.")

        _append_live("------------------------------------------------------------")
        _append_live("This live console will close automatically in ~6 seconds.")
    finally:
        heartbeat_stop.set()
        if heartbeat_thread is not None:
            try:
                heartbeat_thread.join(timeout=1.0)
            except Exception:
                pass

        if monitor is not None:
            try:
                time.sleep(6.0)
                if monitor.poll() is None:
                    monitor.terminate()
            except Exception:
                pass

        shutil.rmtree(isolated_home, ignore_errors=True)

    return _executor.AgentExecutionResult(
        schema="aura.fabric.coding-agent-execution-result.v1",
        executor_id=_executor.EXECUTOR_ID,
        agent_id=str(materialized.get("agent_id") or agent_id),
        model=str(materialized.get("model") or model),
        workspace=str(workspace),
        executable=str(preflight["executable"]),
        arguments=tuple(arguments),
        returncode=run["returncode"],
        timed_out=bool(run["timed_out"]),
        elapsed_ms=float(run["elapsed_ms"]),
        stdout=str(run["stdout"]),
        stderr=str(run["stderr"]),
        stdout_truncated=bool(run["stdout_truncated"]),
        stderr_truncated=bool(run["stderr_truncated"]),
        environment_keys=tuple(sorted(k for k in env if k != "AURA_ROOT")),
        runtime_secret_env_names=runtime_names,
        direct_canonical_workspace=False,
        shell=False,
        success=(run["returncode"] == 0 and not run["timed_out"]),
    )






def run_agent_in_sandbox(
    agent_id: str,
    *,
    manifest: SandboxManifest,
    model: str = _DEFAULT_MODEL,
    agent_arguments: Iterable[str] = (),
    auto_start_gateway: bool = True,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES,
) -> dict[str, Any]:
    """Run an installed coding client against AFG and harvest sandbox-only edits."""
    sandbox = Path(manifest.sandbox_root).resolve(strict=True)
    source_root = Path(manifest.source_root).resolve(strict=True)
    _executor.validate_isolated_workspace(sandbox)

    args = _validate_agent_arguments(agent_arguments, source_root=source_root)
    policy = _executor.ExecutorPolicy(
        timeout_seconds=timeout_seconds,
        max_output_bytes=max_output_bytes,
        allow_canonical_workspace=False,
        inherit_safe_environment=True,
    ).validated()

    preflight = _executor.prepare_agent_execution(
        agent_id,
        model=model,
        workspace=sandbox,
        policy=policy,
    )
    static_env = dict(preflight.get("environment_static") or {})
    gateway_root = static_env.get("AURA_FABRIC_GATEWAY")
    if not gateway_root:
        raise RuntimeError("coding-agent launch plan does not expose AURA_FABRIC_GATEWAY")

    token = str(os.environ.get("AURA_FABRIC_LOCAL_TOKEN") or "aura-local")
    guard_root, guard_records = _make_source_guard(manifest)
    lease: GatewayLease | None = None
    restored: tuple[str, ...] = ()

    try:
        lease = acquire_gateway(
            str(gateway_root),
            local_token=token,
            auto_start=auto_start_gateway,
        )

        with _ENV_LOCK:
            old_token = os.environ.get("AURA_FABRIC_LOCAL_TOKEN")
            try:
                os.environ["AURA_FABRIC_LOCAL_TOKEN"] = token
                execution = _run_executor_bound_process(
                    preflight,
                    agent_id=agent_id,
                    model=model,
                    workspace=sandbox,
                    agent_arguments=args,
                    policy=policy,
                    local_token=token,
                )
            finally:
                if old_token is None:
                    os.environ.pop("AURA_FABRIC_LOCAL_TOKEN", None)
                else:
                    os.environ["AURA_FABRIC_LOCAL_TOKEN"] = old_token

        restored = _restore_source_guard(guard_records)
        changes = collect_sandbox_changes(manifest)
        gateway_probe = probe_gateway(lease.root_url, local_token=token)

        if restored:
            raise SourceIntegrityError(
                "External coding agent attempted to mutate guarded production/source files; "
                "AURA restored them automatically."
            )

        return {
            "schema": "aura.fabric.coding-agent-sandbox-session-result.v1",
            "binding_id": BINDING_ID,
            "agent_id": agent_id,
            "model": model,
            "source_root": str(source_root),
            "sandbox_root": str(sandbox),
            "gateway": {
                "root_url": lease.root_url,
                "owned_by_session": lease.owned,
                "ready": bool(gateway_probe.get("ready")),
                "aura_code_alias": bool(gateway_probe.get("aura_code_alias")),
            },
            "execution": execution.to_dict(),
            "changes": [item.to_dict() for item in changes],
            "change_count": len(changes),
            "adf_f_edits_ready": all(
                item.change_type != "deleted" and item.text_edit and item.new_text is not None
                for item in changes
            ),
            "guard_restored_files": [],
            "source_write_applied": False,
            "adf_f_called": False,
            "adf_g_called": False,
        }
    finally:
        try:
            if not restored:
                restored = _restore_source_guard(guard_records)
        finally:
            if lease is not None:
                lease.close()
            shutil.rmtree(guard_root, ignore_errors=True)


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.fabric.coding-agent-afg-sandbox-binding-capabilities.v1",
        "binding_id": BINDING_ID,
        "coding_agent_executor_reused": True,
        "agent_launch_plan_reused": True,
        "production_afg_reused": True,
        "model_alias": _DEFAULT_MODEL,
        "sandbox_external_to_aura_required": True,
        "explicit_source_inputs_only": True,
        "secret_source_inputs_denied": True,
        "symlink_inputs_denied": True,
        "source_guard_backup_restore": True,
        "authority_guard_backup_restore": True,
        "guard_backups_external_to_agent_sandbox": True,
        "production_paths_rejected_in_agent_arguments": True,
        "child_aura_root_env_removed": True,
        "isolated_child_home": True,
        "home_dotenv_autoload_mitigated": True,
        "aider_openai_compat_env_aliases": True,
        "provider_credentials_inherited_by_agent": False,
        "local_gateway_token_only": True,
        "shell": False,
        "bounded_output": True,
        "timeout": True,
        "direct_source_write": False,
        "adf_f_called": False,
        "adf_g_called": False,
        "harvests_full_text_edits": True,
        "deletions_auto_translated": False,
        "os_filesystem_confinement_claimed": False,
        "isolation_statement": (
            "Logical working-copy isolation plus guarded-source automatic restoration; "
            "this is not an operating-system filesystem sandbox."
        ),
        "next_stage": "harvested edits -> ADF-F proposal/tests -> ADF-G approval",
    }
