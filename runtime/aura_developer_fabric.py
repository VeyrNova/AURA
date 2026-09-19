from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Mapping, Sequence

DeveloperMode = Literal["native_gateway", "managed_agent"]
DeveloperAction = Literal[
    "inspect", "plan", "read", "patch_proposal", "test", "diff",
    "apply", "rollback", "provider_call"
]

@dataclass(frozen=True)
class DeveloperFabricPolicy:
    workspace_root: Path
    mode: DeveloperMode = "native_gateway"
    read_only_default: bool = True
    require_explicit_apply_approval: bool = True
    require_transaction_backup: bool = True
    require_test_before_apply: bool = True
    deny_outside_workspace: bool = True
    provider_calls_require_policy_gate: bool = True

    def normalize(self, path: Path | str) -> Path:
        candidate = Path(path).expanduser().resolve()
        root = self.workspace_root.expanduser().resolve()
        if self.deny_outside_workspace and candidate != root and root not in candidate.parents:
            raise PermissionError(f"Developer Fabric path outside workspace: {candidate}")
        return candidate

    def can_execute(
        self,
        action: DeveloperAction,
        *,
        explicitly_approved: bool = False,
        provider_policy_approved: bool = False,
    ) -> bool:
        if action in {"inspect", "plan", "read", "patch_proposal", "test", "diff"}:
            return True
        if action in {"apply", "rollback"}:
            return explicitly_approved
        if action == "provider_call":
            return provider_policy_approved
        return False

@dataclass(frozen=True)
class DeveloperTaskPlan:
    task_id: str
    objective: str
    workspace_root: str
    mode: DeveloperMode
    stages: tuple[str, ...] = (
        "planner",
        "repo_scan",
        "context_pack",
        "route_plan",
        "patch_proposal",
        "test_runner",
        "diff_review",
        "approval_gate",
        "transaction_apply",
        "rollback_guard",
    )
    metadata: Mapping[str, object] = field(default_factory=dict)

ROADMAP_OVERLAY = (
    ("ADF-A", "Native clean-room Developer Fabric + AURA Fabric Gateway foundation"),
    ("ADF-B", "Protocol gateway + provider adapters + model/health contract"),
    ("ADF-C", "Repository scanner + Workspace context pack"),
    ("ADF-D", "Planner + patch proposal + test + diff transaction engine"),
    ("ADF-E", "Approval gates + rollback + self-development safety"),
    ("ADF-F", "Native AURA Developer Workspace UI + live acceptance"),
    ("RETURN", "Resume product roadmap at AURA v1.3.1 Windows App & PC Control Orchestration"),
)

def build_task_plan(
    *,
    task_id: str,
    objective: str,
    workspace_root: Path | str,
    mode: DeveloperMode = "native_gateway",
    metadata: Mapping[str, object] | None = None,
) -> DeveloperTaskPlan:
    root = Path(workspace_root).expanduser().resolve()
    if not task_id.strip():
        raise ValueError("task_id is required")
    if not objective.strip():
        raise ValueError("objective is required")
    return DeveloperTaskPlan(
        task_id=task_id.strip(),
        objective=objective.strip(),
        workspace_root=str(root),
        mode=mode,
        metadata=dict(metadata or {}),
    )

def build_workspace_context_pack(
    *,
    workspace_id: str,
    project_name: str,
    root_path: Path | str,
    last_action: str | None = None,
    next_action: str | None = None,
    artifacts: Sequence[str] = (),
) -> dict[str, object]:
    root = Path(root_path).expanduser().resolve()
    return {
        "schema": "aura.developer-fabric.context-pack.v2",
        "workspace_id": workspace_id,
        "project_name": project_name,
        "root_path": str(root),
        "last_action": last_action,
        "next_action": next_action,
        "artifacts": list(artifacts),
        "gateway": {
            "implementation": "AURA Fabric Gateway",
            "dependency": "native",
            "clean_room": True,
        },
        "guardrails": {
            "read_only_default": True,
            "explicit_apply_approval": True,
            "transaction_backup": True,
            "test_before_apply": True,
            "deny_outside_workspace": True,
            "provider_policy_gate": True,
        },
    }
