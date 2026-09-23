"""AURA ADF-H R7.2.2 — Native Coding Agent Executor Foundation.

Clean-room AURA-owned process boundary for external coding-agent clients.

Safety contract:
- consumes the certified declarative build_launch_plan() output;
- never auto-installs an agent;
- never executes an agent in the canonical AURA repository by default;
- executes only in an explicit isolated workspace supplied by the caller;
- shell=False always;
- sanitized child environment (no arbitrary inherited secrets);
- runtime gateway secret is injected only into the exact plan-declared env names;
- bounded stdout/stderr capture;
- timeout + termination;
- no direct ADF-F/G approval or write authority;
- no network logic of its own.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
import os
import re
import subprocess
import time

from runtime.aura_fabric_agent_bridge import build_launch_plan

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
EXECUTOR_ID = "ADF-H-R7.2.2-NATIVE-CODING-AGENT-EXECUTOR"

_DEFAULT_TIMEOUT_SECONDS = 180.0
_DEFAULT_MAX_OUTPUT_BYTES = 2 * 1024 * 1024

_SAFE_INHERITED_ENV = (
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "APPDATA",
    "PROGRAMDATA",
    "PROGRAMFILES",
    "PROGRAMFILES(X86)",
    "COMMONPROGRAMFILES",
    "COMMONPROGRAMFILES(X86)",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "LANG",
    "LC_ALL",
)


@dataclass(frozen=True)
class ExecutorPolicy:
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    max_output_bytes: int = _DEFAULT_MAX_OUTPUT_BYTES
    allow_canonical_workspace: bool = False
    inherit_safe_environment: bool = True

    def validated(self) -> "ExecutorPolicy":
        timeout = float(self.timeout_seconds)
        output = int(self.max_output_bytes)
        if timeout <= 0 or timeout > 3600:
            raise ValueError("timeout_seconds must be > 0 and <= 3600")
        if output < 4096 or output > 32 * 1024 * 1024:
            raise ValueError("max_output_bytes must be between 4096 and 33554432")
        return self


@dataclass(frozen=True)
class AgentExecutionResult:
    schema: str
    executor_id: str
    agent_id: str
    model: str
    workspace: str
    executable: str
    arguments: tuple[str, ...]
    returncode: int | None
    timed_out: bool
    elapsed_ms: float
    stdout: str
    stderr: str
    stdout_truncated: bool
    stderr_truncated: bool
    environment_keys: tuple[str, ...]
    runtime_secret_env_names: tuple[str, ...]
    direct_canonical_workspace: bool
    shell: bool
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _within(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_isolated_workspace(
    workspace: str | Path,
    *,
    allow_canonical_workspace: bool = False,
) -> Path:
    """Resolve and validate the process cwd.

    Self-development execution must use a staging/sandbox workspace.  The
    canonical AURA repository is rejected by default so an external agent
    cannot bypass ADF-F/G by editing production files directly.
    """
    raw = Path(workspace).expanduser()
    resolved = raw.resolve(strict=False)

    if not resolved.exists() or not resolved.is_dir():
        raise ValueError(f"isolated workspace does not exist or is not a directory: {resolved}")

    canonical = resolved == ROOT or _within(resolved, ROOT)
    if canonical and not allow_canonical_workspace:
        raise PermissionError(
            "Coding Agent Executor refuses the canonical AURA repository. "
            "Use an isolated staging/sandbox workspace."
        )

    # Do not permit running inside AURA governance/transaction authority dirs
    # even when a caller opts into another repository subtree later.
    protected_names = {
        ".git",
        ".aura_audit",
        ".aura_transactions",
        "_patch_backups",
    }
    if any(part.casefold() in {x.casefold() for x in protected_names} for part in resolved.parts):
        raise PermissionError("executor workspace is inside a protected authority directory")

    return resolved


def _sanitized_base_environment(*, inherit_safe: bool = True) -> dict[str, str]:
    env: dict[str, str] = {}
    if inherit_safe:
        folded = {k.casefold(): k for k in os.environ}
        for wanted in _SAFE_INHERITED_ENV:
            actual = folded.get(wanted.casefold())
            if actual:
                env[wanted] = os.environ[actual]

    env["AURA_ROOT"] = str(ROOT)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def _redaction_values(values: Iterable[str | None]) -> tuple[str, ...]:
    out = []
    for value in values:
        text = str(value or "")
        if len(text) >= 4 and text not in out:
            out.append(text)
    return tuple(out)


def _redact(text: str, secret_values: Iterable[str | None]) -> str:
    value = str(text or "")
    for secret in _redaction_values(secret_values):
        value = value.replace(secret, "[REDACTED]")
    # Defensive redaction for obvious credential-like output.
    value = re.sub(
        r"(?i)\b(api[_-]?key|auth[_-]?token|access[_-]?token|secret)\s*[:=]\s*([^\s]+)",
        r"\1=[REDACTED]",
        value,
    )
    return value


def _truncate_utf8(text: str, max_bytes: int) -> tuple[str, bool]:
    raw = str(text or "").encode("utf-8", errors="replace")
    if len(raw) <= max_bytes:
        return raw.decode("utf-8", errors="replace"), False
    clipped = raw[:max_bytes]
    return clipped.decode("utf-8", errors="ignore"), True


def prepare_agent_execution(
    agent_id: str,
    *,
    model: str,
    workspace: str | Path,
    policy: ExecutorPolicy | None = None,
) -> dict[str, Any]:
    """Build and validate an execution plan without starting a process."""
    policy = (policy or ExecutorPolicy()).validated()
    isolated = validate_isolated_workspace(
        workspace,
        allow_canonical_workspace=policy.allow_canonical_workspace,
    )

    # First call is strictly declarative and must not materialize configs.
    plan = build_launch_plan(
        str(agent_id),
        model=str(model),
        workspace=isolated,
        materialize=False,
    )
    detection = dict(plan.get("detection") or {})

    if not detection.get("platform_supported"):
        raise RuntimeError("coding agent bridge does not support the current platform")
    if not detection.get("installed") or not detection.get("executable"):
        raise FileNotFoundError(
            f"coding agent is not installed/detected: {agent_id}. "
            "AURA does not auto-install coding agents."
        )

    executable = Path(str(detection["executable"])).resolve(strict=False)
    if not executable.exists():
        raise FileNotFoundError(f"resolved coding-agent executable does not exist: {executable}")

    return {
        "schema": "aura.fabric.coding-agent-execution-preflight.v1",
        "executor_id": EXECUTOR_ID,
        "agent_id": str(plan.get("agent_id") or agent_id),
        "model": str(plan.get("model") or model),
        "workspace": str(isolated),
        "executable": str(executable),
        "arguments": [str(x) for x in (plan.get("arguments") or [])],
        "environment_static": {
            str(k): str(v) for k, v in dict(plan.get("environment_static") or {}).items()
        },
        "runtime_secret_env_names": sorted(
            str(k) for k in dict(plan.get("environment_runtime_secret_refs") or {})
        ),
        "managed_files": [str(x) for x in (plan.get("managed_files") or [])],
        "materialized": False,
        "plan_will_execute": bool(plan.get("will_execute")),
        "executor_will_execute": True,
        "direct_canonical_workspace": isolated == ROOT or _within(isolated, ROOT),
        "shell": False,
    }


def _materialize_managed_plan_files(agent_id: str, *, model: str, workspace: Path) -> dict[str, Any]:
    """Materialize only AURA-managed bridge config files after preflight passed."""
    return build_launch_plan(
        str(agent_id),
        model=str(model),
        workspace=workspace,
        materialize=True,
    )


def _child_environment(
    plan: dict[str, Any],
    *,
    inherit_safe: bool,
) -> tuple[dict[str, str], tuple[str, ...], tuple[str, ...]]:
    env = _sanitized_base_environment(inherit_safe=inherit_safe)

    for key, value in dict(plan.get("environment_static") or {}).items():
        env[str(key)] = str(value)

    runtime_names = tuple(
        sorted(str(k) for k in dict(plan.get("environment_runtime_secret_refs") or {}))
    )
    local_gateway_token = os.environ.get("AURA_FABRIC_LOCAL_TOKEN") or "aura-local"

    for name in runtime_names:
        env[name] = local_gateway_token

    return env, tuple(sorted(env)), _redaction_values((local_gateway_token,))


def _run_process(
    executable: str | Path,
    arguments: Iterable[str],
    *,
    workspace: str | Path,
    environment: dict[str, str],
    timeout_seconds: float,
    max_output_bytes: int,
    redaction_values: Iterable[str | None] = (),
) -> dict[str, Any]:
    """Low-level bounded process runner. Always shell=False."""
    command = [str(executable), *[str(x) for x in arguments]]
    started = time.monotonic()
    timed_out = False
    returncode: int | None = None

    process = subprocess.Popen(
        command,
        cwd=str(workspace),
        env=dict(environment),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=False,
        shell=False,
    )

    try:
        stdout_b, stderr_b = process.communicate(timeout=float(timeout_seconds))
        returncode = process.returncode
    except subprocess.TimeoutExpired:
        timed_out = True
        try:
            process.kill()
        except Exception:
            pass
        stdout_b, stderr_b = process.communicate()
        returncode = process.returncode

    elapsed_ms = round((time.monotonic() - started) * 1000.0, 3)

    stdout_text = bytes(stdout_b or b"").decode("utf-8", errors="replace")
    stderr_text = bytes(stderr_b or b"").decode("utf-8", errors="replace")

    stdout_text = _redact(stdout_text, redaction_values)
    stderr_text = _redact(stderr_text, redaction_values)

    stdout_text, stdout_truncated = _truncate_utf8(stdout_text, int(max_output_bytes))
    stderr_text, stderr_truncated = _truncate_utf8(stderr_text, int(max_output_bytes))

    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "elapsed_ms": elapsed_ms,
        "stdout": stdout_text,
        "stderr": stderr_text,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
        "shell": False,
    }


def execute_agent(
    agent_id: str,
    *,
    model: str,
    workspace: str | Path,
    agent_arguments: Iterable[str] = (),
    policy: ExecutorPolicy | None = None,
) -> AgentExecutionResult:
    """Execute a detected coding agent inside an isolated workspace.

    This function has process authority only. It has NO authority to approve,
    commit or write canonical AURA changes. The caller must convert any agent
    result/staging diff into ADF-F proposed edits and then pass through ADF-G.
    """
    policy = (policy or ExecutorPolicy()).validated()

    preflight = prepare_agent_execution(
        agent_id,
        model=model,
        workspace=workspace,
        policy=policy,
    )
    isolated = Path(preflight["workspace"])

    # Materialization happens only after all preflight safety checks pass.
    materialized_plan = _materialize_managed_plan_files(
        agent_id,
        model=model,
        workspace=isolated,
    )

    env, env_keys, secret_values = _child_environment(
        materialized_plan,
        inherit_safe=policy.inherit_safe_environment,
    )

    arguments = [
        *[str(x) for x in (materialized_plan.get("arguments") or [])],
        *[str(x) for x in agent_arguments],
    ]

    run = _run_process(
        preflight["executable"],
        arguments,
        workspace=isolated,
        environment=env,
        timeout_seconds=policy.timeout_seconds,
        max_output_bytes=policy.max_output_bytes,
        redaction_values=secret_values,
    )

    return AgentExecutionResult(
        schema="aura.fabric.coding-agent-execution-result.v1",
        executor_id=EXECUTOR_ID,
        agent_id=str(materialized_plan.get("agent_id") or agent_id),
        model=str(materialized_plan.get("model") or model),
        workspace=str(isolated),
        executable=str(preflight["executable"]),
        arguments=tuple(arguments),
        returncode=run["returncode"],
        timed_out=bool(run["timed_out"]),
        elapsed_ms=float(run["elapsed_ms"]),
        stdout=str(run["stdout"]),
        stderr=str(run["stderr"]),
        stdout_truncated=bool(run["stdout_truncated"]),
        stderr_truncated=bool(run["stderr_truncated"]),
        environment_keys=env_keys,
        runtime_secret_env_names=tuple(preflight["runtime_secret_env_names"]),
        direct_canonical_workspace=bool(preflight["direct_canonical_workspace"]),
        shell=False,
        success=(run["returncode"] == 0 and not run["timed_out"]),
    )


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.fabric.coding-agent-executor-capabilities.v1",
        "executor_id": EXECUTOR_ID,
        "declarative_launch_plan_reused": True,
        "auto_install": False,
        "canonical_workspace_execution_default": False,
        "isolated_workspace_required": True,
        "shell": False,
        "sanitized_child_environment": True,
        "runtime_secret_env_names_only": True,
        "stdout_stderr_bounded": True,
        "timeout_and_kill": True,
        "output_secret_redaction": True,
        "direct_adf_f_write_authority": False,
        "direct_adf_g_approval_authority": False,
        "network_logic": False,
        "intended_downstream": "agent staging output -> ADF-F proposal/tests -> ADF-G approval",
    }
