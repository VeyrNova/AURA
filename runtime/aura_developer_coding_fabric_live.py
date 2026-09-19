"""AURA ADF-H R7.2.11 — native Coding Fabric generation binding.

This module replaces only the generation phase of the R7.1 general
self-development path:

    explicit target
    -> isolated working copy
    -> Aider
    -> AFG / aura-code
    -> harvested target edit

It does NOT propose, validate, assess, approve or apply edits. Those
responsibilities remain exclusively owned by the already-certified ADF-F
and ADF-G path in runtime.aura_developer_general_live.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable
import os
import json
import shutil
import tempfile

from runtime.aura_fabric_coding_agent_session import (
    SandboxChange,
    changes_to_adf_f_edits,
    collect_sandbox_changes,
    prepare_sandbox,
    remove_sandbox,
    run_agent_in_sandbox,
    runtime_readiness_snapshot,
)

ROOT = Path(os.environ.get("AURA_ROOT") or r"C:\AURA GPT version").resolve()
BINDING_ID = "ADF-H-R7.2.11-GENERAL-CODING-FABRIC-BINDING"
PRIMARY_AGENT_ID = "claude_code"
FALLBACK_AGENT_ID = "aider"
MODEL_ALIAS = "aura-code"
FALLBACK_MODEL = "gemini/gemini-3.6-flash"
CLAUDE_TOOLS = "PowerShell,Edit,Read,Write,Grep,Glob"
ZERO_EDIT_RETRY_POLICY = "claude-aura-code-then-aider-aura-code-then-aider-direct-gemini"

_SIDE_EFFECT_EXACT = {
    ".aider.chat.history.md",
    ".aider.input.history",
    ".aider.tags.cache.v4",
    ".aider.repo.map",
}
_SIDE_EFFECT_PREFIXES = (".aider.", ".aider_")


class CodingFabricGenerationError(RuntimeError):
    pass


def _safe_relative_path(raw: str | Path) -> str:
    path = Path(str(raw))
    if path.is_absolute():
        raise CodingFabricGenerationError(f"target must be relative: {path}")
    if not path.parts or str(path) in ("", "."):
        raise CodingFabricGenerationError("target path is required")
    if any(part in ("", ".", "..") for part in path.parts):
        raise CodingFabricGenerationError(f"unsafe target path: {path}")
    return path.as_posix()


def _is_aider_side_effect(relative_path: str) -> bool:
    rel = str(relative_path or "").replace("\\", "/")
    name = Path(rel).name.casefold()
    if name in {x.casefold() for x in _SIDE_EFFECT_EXACT}:
        return True
    return any(name.startswith(prefix.casefold()) for prefix in _SIDE_EFFECT_PREFIXES)



# AURA ROADMAP RM26-3C — SYNTHETIC NEW-FILE TARGET ALIAS GUARD
def _is_synthetic_duplicate_parent_alias(relative_path: str, target_relative_path: str) -> bool:
    try:
        rel = _safe_relative_path(relative_path)
        target = _safe_relative_path(target_relative_path)
    except Exception:
        return False
    parent = Path(target).parent.as_posix()
    if parent in ("", "."):
        return False
    return rel == f"{parent}/{target}"


def _canonical_single_target_edit(
    selected,
    target_relative_path: str,
    *,
    allow_synthetic_duplicate_parent_alias: bool = False,
) -> dict[str, str]:
    target = _safe_relative_path(target_relative_path)
    edits = changes_to_adf_f_edits(selected)
    if len(edits) != 1:
        raise CodingFabricGenerationError(
            "Coding Fabric did not produce exactly one target edit"
        )
    produced = _safe_relative_path(edits[0].get("path") or "")
    if produced == target:
        return {"path": target, "new_text": str(edits[0]["new_text"])}
    if (
        allow_synthetic_duplicate_parent_alias
        and _is_synthetic_duplicate_parent_alias(produced, target)
    ):
        return {"path": target, "new_text": str(edits[0]["new_text"])}
    raise CodingFabricGenerationError(
        f"Coding Fabric did not produce the canonical target path: {produced}; "
        f"expected only {target}"
    )


def _select_target_changes(
    changes: Iterable[SandboxChange],
    target_relative_path: str,
    *,
    allow_synthetic_duplicate_parent_alias: bool = False,
) -> tuple[tuple[SandboxChange, ...], tuple[str, ...]]:
    target = _safe_relative_path(target_relative_path)
    selected: list[SandboxChange] = []
    dropped: list[str] = []

    for change in changes:
        rel = str(change.relative_path).replace("\\", "/")
        if _is_aider_side_effect(rel):
            dropped.append(rel)
            continue
        if rel != target:
            alias_ok = (
                allow_synthetic_duplicate_parent_alias
                and _is_synthetic_duplicate_parent_alias(rel, target)
            )
            if not alias_ok:
                raise CodingFabricGenerationError(
                    f"coding agent changed an unexpected path: {rel}; expected only {target}"
                )
        if change.change_type == "deleted":
            raise CodingFabricGenerationError(
                f"coding agent deletion is not accepted by R7.2.11: {target}"
            )
        if not change.text_edit or change.new_text is None:
            raise CodingFabricGenerationError(
                f"coding agent produced a non-UTF8/oversized target edit: {target}"
            )
        selected.append(change)

    if len(selected) > 1:
        raise CodingFabricGenerationError(
            f"multiple target changes were harvested for {target}"
        )
    return tuple(selected), tuple(sorted(set(dropped)))


def _agent_arguments(
    agent_id: str,
    target: str,
    user_text: str,
    model_name: str,
) -> tuple[str, ...]:
    rel = _safe_relative_path(target)
    agent = str(agent_id or "").strip()
    instruction = (
        "You are AURA's coding implementation agent. "
        f"Edit exactly this file: {rel}. "
        "Make the requested change now. "
        "Do not explain, plan, summarize, restate, or verify the work. "
        "Modify no other project file. "
        "Preserve unrelated behavior and formatting as much as possible. "
        "Return a real file edit, not an explanation-only answer. "
        "User request: " + str(user_text or "").strip()
    )
    if agent == "claude_code":
        return (
            "--bare",
            "--tools", CLAUDE_TOOLS,
            "--model", str(model_name or MODEL_ALIAS),
            "-p", instruction,
            "--output-format", "json",
            "--dangerously-skip-permissions",
        )
    if agent == "aider":
        aider_instruction = (
            instruction
            + " Spend output only on the complete edit in Aider's required edit format "
            "and finish every required edit before stopping. "
            "Do not edit Aider history/config files intentionally."
        )
        return (
            "--no-git", "--no-gitignore", "--no-auto-commits", "--no-dirty-commits",
            "--no-analytics", "--no-check-update", "--no-show-release-notes",
            "--no-show-model-warnings", "--no-check-model-accepts-settings",
            "--no-stream", "--no-auto-lint", "--no-suggest-shell-commands",
            "--disable-playwright", "--yes-always", rel, "--message", aider_instruction,
        )
    raise CodingFabricGenerationError(f"unsupported coding agent route: {agent}")

def _prepare_generation_source(
    source_root: Path,
    rel: str,
    *,
    existed: bool,
    current_text: str,
) -> tuple[Path, tuple[str, ...], Path | None]:
    target = (source_root / Path(rel)).resolve(strict=False)
    if existed:
        if not target.is_file():
            raise CodingFabricGenerationError(f"existing target is not a file: {target}")
        return source_root, (rel,), None

    synthetic = Path(tempfile.mkdtemp(prefix="aura_coding_fabric_new_file_")).resolve()
    seeded = synthetic / Path(rel)
    seeded.parent.mkdir(parents=True, exist_ok=True)
    seeded.write_text(str(current_text or ""), encoding="utf-8")
    return synthetic, (rel,), synthetic


def generate_edit_via_coding_fabric(
    user_text: str,
    rel: str,
    existed: bool,
    current_text: str,
    *,
    source_root: str | Path = ROOT,
    timeout_seconds: float = 300.0,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Generate one full-text edit through Aider -> AFG without ADF-F/G writes.

    R7.2.12 R5 R9:
    - preserve R5 R2 primary + direct-Gemini retry behavior;
    - preserve bounded forensic evidence on zero-target-edit;
    - no direct write, proposal, staging, assessment or apply here.
    """
    target = _safe_relative_path(rel)
    root = Path(source_root).expanduser().resolve(strict=True)

    readiness = runtime_readiness_snapshot()
    if readiness.get("ready_for_real_agent_session") is not True:
        raise CodingFabricGenerationError(
            "Coding Fabric is not ready for a real agent session: "
            + str({
                "installed_agent_ids": readiness.get("installed_agent_ids"),
                "registered_live_provider_ids": readiness.get("registered_live_provider_ids"),
                "aura_code_alias_available": readiness.get("aura_code_alias_available"),
            })
        )
    installed_agents = set(readiness.get("installed_agent_ids") or ())
    attempt_routes: list[tuple[str, str]] = []
    if PRIMARY_AGENT_ID in installed_agents:
        attempt_routes.append((PRIMARY_AGENT_ID, MODEL_ALIAS))
    if FALLBACK_AGENT_ID in installed_agents:
        attempt_routes.append((FALLBACK_AGENT_ID, MODEL_ALIAS))
        attempt_routes.append((FALLBACK_AGENT_ID, FALLBACK_MODEL))
    if not attempt_routes:
        raise CodingFabricGenerationError(
            "No supported coding agent is installed/detected: "
            + str({"preferred": PRIMARY_AGENT_ID, "fallback": FALLBACK_AGENT_ID, "installed_agent_ids": sorted(installed_agents)})
        )

    attempt_traces: list[dict[str, Any]] = []

    for attempt_index, (agent_id, model_name) in enumerate(attempt_routes, start=1):
        generation_root: Path | None = None
        manifest = None

        try:
            working_source, include_paths, generation_root = _prepare_generation_source(
                root,
                target,
                existed=bool(existed),
                current_text=str(current_text or ""),
            )
            manifest = prepare_sandbox(working_source, include_paths)

            result = run_agent_in_sandbox(
                agent_id,
                manifest=manifest,
                model=model_name,
                agent_arguments=_agent_arguments(agent_id, target, user_text, model_name),
                auto_start_gateway=True,
                timeout_seconds=float(timeout_seconds),
                max_output_bytes=2 * 1024 * 1024,
            )

            execution = dict(result.get("execution") or {})
            gateway = dict(result.get("gateway") or {})

            trace = {
                "attempt": attempt_index,
                "agent": agent_id,
                "model": model_name,
                "execution_success": execution.get("success") is True,
                "returncode": execution.get("returncode"),
                "timed_out": bool(execution.get("timed_out")),
                "elapsed_ms": execution.get("elapsed_ms"),
                "stdout_tail": str(execution.get("stdout") or "")[-6000:],
                "stderr_tail": str(execution.get("stderr") or "")[-6000:],
                "stdout_truncated": bool(execution.get("stdout_truncated")),
                "stderr_truncated": bool(execution.get("stderr_truncated")),
                "execution_arguments": [
                    str(x) for x in (execution.get("arguments") or ())
                ],
                "execution_workspace": str(execution.get("workspace") or ""),
                "gateway_ready": bool(gateway.get("ready")),
                "gateway_owned_by_session": bool(gateway.get("owned_by_session")),
                "gateway_aura_code_alias": bool(gateway.get("aura_code_alias")),
            }

            forensic_changes = []
            for item in (result.get("changes") or ()):
                row = dict(item or {})
                forensic_changes.append({
                    "relative_path": str(row.get("relative_path") or ""),
                    "change_type": row.get("change_type"),
                    "before_sha256": row.get("before_sha256"),
                    "after_sha256": row.get("after_sha256"),
                    "size_bytes": row.get("size_bytes"),
                    "text_edit": bool(row.get("text_edit")),
                    "new_text_tail": (
                        str(row.get("new_text") or "")[-6000:]
                        if row.get("new_text") is not None
                        else None
                    ),
                })

            trace["session_change_count"] = int(result.get("change_count") or 0)
            trace["session_changes"] = forensic_changes

            if execution.get("success") is not True:
                trace["outcome"] = "execution-failed"
                attempt_traces.append(trace)
                continue

            harvested = collect_sandbox_changes(manifest)
            selected, dropped = _select_target_changes(
                harvested,
                target,
                allow_synthetic_duplicate_parent_alias=not bool(existed),
            )

            trace["sandbox_change_count"] = len(harvested)
            trace["target_change_count"] = len(selected)
            trace["dropped_agent_side_effects"] = list(dropped)

            if not selected:
                trace["outcome"] = "no-target-edit"
                attempt_traces.append(trace)
                continue

            edit = _canonical_single_target_edit(
                selected,
                target,
                allow_synthetic_duplicate_parent_alias=not bool(existed),
            )
            if edit["new_text"] == str(current_text or ""):
                trace["outcome"] = "unchanged-target-text"
                attempt_traces.append(trace)
                continue

            trace["outcome"] = "target-edit"
            attempt_traces.append(trace)

            generator = {
                "binding": BINDING_ID,
                "agent": agent_id,
                "primary_agent": PRIMARY_AGENT_ID,
                "fallback_agent": FALLBACK_AGENT_ID,
                "selected_agent": agent_id,
                "model": MODEL_ALIAS,
                "selected_model": model_name,
                "fallback_model": FALLBACK_MODEL,
                "fallback_used": attempt_index > 1,
                "attempt_count": len(attempt_traces),
                "attempts": attempt_traces,
                "provider": "afg",
                "provider_owner": "AURA Fabric Gateway",
                "resilience_owner": "AFG",
                "conversation_llm_manager_used": False,
                "direct_source_write": False,
                "adf_f_called": False,
                "adf_g_called": False,
                "gateway_ready": bool(gateway.get("ready")),
                "gateway_owned_by_session": bool(gateway.get("owned_by_session")),
                "sandbox_change_count": len(harvested),
                "dropped_agent_side_effects": list(dropped),
                "target_change_count": len(selected),
                "source_mode": "existing" if existed else "synthetic-create-seed",
                "zero_edit_is_failure": True,
                "zero_edit_forensic_evidence": True,
            }
            return edit, generator

        finally:
            if manifest is not None:
                try:
                    remove_sandbox(manifest)
                except Exception:
                    pass
            if generation_root is not None:
                shutil.rmtree(generation_root, ignore_errors=True)

    forensic = []
    for x in attempt_traces:
        forensic.append({
            "attempt": x.get("attempt"),
            "agent": x.get("agent"),
            "model": x.get("model"),
            "outcome": x.get("outcome"),
            "execution_success": x.get("execution_success"),
            "returncode": x.get("returncode"),
            "timed_out": x.get("timed_out"),
            "elapsed_ms": x.get("elapsed_ms"),
            "gateway_ready": x.get("gateway_ready"),
            "gateway_owned_by_session": x.get("gateway_owned_by_session"),
            "gateway_aura_code_alias": x.get("gateway_aura_code_alias"),
            "sandbox_change_count": x.get("sandbox_change_count"),
            "target_change_count": x.get("target_change_count"),
            "session_change_count": x.get("session_change_count"),
            "dropped_agent_side_effects": x.get("dropped_agent_side_effects"),
            "execution_workspace": x.get("execution_workspace"),
            "execution_arguments": x.get("execution_arguments"),
            "stdout_tail": str(x.get("stdout_tail") or "")[-6000:],
            "stderr_tail": str(x.get("stderr_tail") or "")[-6000:],
            "stdout_truncated": x.get("stdout_truncated"),
            "stderr_truncated": x.get("stderr_truncated"),
            "session_changes": x.get("session_changes") or [],
        })

    raise CodingFabricGenerationError(
        "Coding Fabric produced no target edit after Claude primary + Aider fallbacks. "
        "R5R9_FORENSIC="
        + json.dumps(forensic, ensure_ascii=False, default=str)
    )




def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": "aura.developer.coding-fabric-live.v1",
        "binding": BINDING_ID,
        "agent": PRIMARY_AGENT_ID,
        "primary_agent": PRIMARY_AGENT_ID,
        "fallback_agent": FALLBACK_AGENT_ID,
        "agent_route_policy": ZERO_EDIT_RETRY_POLICY,
        "claude_tools": CLAUDE_TOOLS,
        "model_alias": MODEL_ALIAS,
        "fallback_model": FALLBACK_MODEL,
        "zero_edit_retry_policy": ZERO_EDIT_RETRY_POLICY,
        "zero_edit_is_failure": True,
        "zero_edit_forensic_evidence": True,
        "zero_edit_forensic_gate": "ADF-H-R7.2.12-R5-R9",
        "generation_via_coding_fabric": True,
        "conversation_llm_manager_used": False,
        "working_copy_required": True,
        "aider_side_effects_filtered": True,
        "unexpected_path_changes_rejected": True,
        "deletions_rejected": True,
        "non_utf8_edits_rejected": True,
        "direct_source_write": False,
        "adf_f_called": False,
        "adf_g_called": False,
        "next_owner_after_generation": "runtime.aura_developer_general_live -> ADF-F/ADF-G",
    }

