from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_runtime_binding_v130 import (
    ActiveProjectRuntimeContext,
    WorkspaceRuntimeBindingV130,
    get_workspace_runtime_binding_v130,
)

WORKSPACE_UI_SCHEMA = "aura.workspace.ui-contract.v1"
PROJECT_ACTIVE_CARD_SCHEMA = "aura.workspace.ui.project-active-card.v1"


def _progress_percent(metadata: Mapping[str, Any] | None) -> int | None:
    meta = dict(metadata or {})
    value = None
    for key in ("progress_percent", "progress_pct", "progress"):
        if key in meta:
            value = meta.get(key)
            break
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip().rstrip("%").strip()
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return max(0, min(100, int(round(number))))


@dataclass(frozen=True)
class ProjectActiveUICardV130:
    schema: str
    visible: bool
    title: str
    workspace_id: str
    project_name: str
    status: str
    root_path: str
    last_action: str
    next_action: str
    artifact_count: int
    progress_percent: int | None
    progress_label: str
    tags: tuple[str, ...]
    updated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "visible": self.visible,
            "title": self.title,
            "workspace_id": self.workspace_id,
            "project_name": self.project_name,
            "status": self.status,
            "root_path": self.root_path,
            "last_action": self.last_action,
            "next_action": self.next_action,
            "artifact_count": self.artifact_count,
            "progress_percent": self.progress_percent,
            "progress_label": self.progress_label,
            "tags": list(self.tags),
            "updated_at": self.updated_at,
        }


def _empty_card() -> ProjectActiveUICardV130:
    return ProjectActiveUICardV130(
        schema=PROJECT_ACTIVE_CARD_SCHEMA,
        visible=False,
        title="PROJET ACTIF",
        workspace_id="",
        project_name="",
        status="",
        root_path="",
        last_action="",
        next_action="",
        artifact_count=0,
        progress_percent=None,
        progress_label="",
        tags=(),
        updated_at="",
    )


def _card_from_context(context: ActiveProjectRuntimeContext) -> ProjectActiveUICardV130:
    progress = _progress_percent(context.metadata)
    return ProjectActiveUICardV130(
        schema=PROJECT_ACTIVE_CARD_SCHEMA,
        visible=True,
        title="PROJET ACTIF",
        workspace_id=context.workspace_id,
        project_name=context.name,
        status=context.status,
        root_path=context.root_path,
        last_action=context.last_action,
        next_action=context.next_action,
        artifact_count=context.artifact_count,
        progress_percent=progress,
        progress_label="" if progress is None else f"{progress}%",
        tags=tuple(context.tags),
        updated_at=context.updated_at,
    )


def project_active_ui_card_v130(
    *,
    service: WorkspaceContextServiceV130 | None = None,
    binding: WorkspaceRuntimeBindingV130 | None = None,
) -> ProjectActiveUICardV130:
    runtime = binding or get_workspace_runtime_binding_v130(service=service)
    context = runtime.active_context()
    if context is None:
        return _empty_card()
    return _card_from_context(context)


def workspace_ui_snapshot_v130(
    *,
    service: WorkspaceContextServiceV130 | None = None,
    binding: WorkspaceRuntimeBindingV130 | None = None,
) -> dict[str, Any]:
    card = project_active_ui_card_v130(service=service, binding=binding)
    return {
        "schema": WORKSPACE_UI_SCHEMA,
        "project_active": card.to_dict(),
        "active_workspace_id": card.workspace_id if card.visible else None,
    }


__all__ = [
    "WORKSPACE_UI_SCHEMA",
    "PROJECT_ACTIVE_CARD_SCHEMA",
    "ProjectActiveUICardV130",
    "project_active_ui_card_v130",
    "workspace_ui_snapshot_v130",
]
