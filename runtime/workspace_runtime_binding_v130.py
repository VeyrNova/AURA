from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from runtime.workspace_context_v130 import (
    WorkspaceContextServiceV130,
    WorkspaceNotFoundError,
    WorkspaceRecord,
    get_workspace_context_service_v130,
)

RUNTIME_CONTEXT_SCHEMA = "aura.workspace.runtime-context.v1"


@dataclass(frozen=True)
class ActiveProjectRuntimeContext:
    schema: str
    workspace_id: str
    name: str
    status: str
    root_path: str
    tags: tuple[str, ...]
    last_action: str
    next_action: str
    notes: str
    metadata: dict[str, Any]
    artifact_count: int
    artifacts: tuple[dict[str, Any], ...]
    recent_activity: tuple[dict[str, Any], ...]
    updated_at: str

    @classmethod
    def from_record(cls, record: WorkspaceRecord) -> "ActiveProjectRuntimeContext":
        return cls(
            schema=RUNTIME_CONTEXT_SCHEMA,
            workspace_id=record.workspace_id,
            name=record.name,
            status=record.status,
            root_path=record.root_path,
            tags=tuple(record.tags),
            last_action=record.last_action,
            next_action=record.next_action,
            notes=record.notes,
            metadata=dict(record.metadata),
            artifact_count=len(record.artifacts),
            artifacts=tuple(asdict(x) for x in record.artifacts),
            recent_activity=tuple(asdict(x) for x in record.activity[:10]),
            updated_at=record.updated_at,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "workspace_id": self.workspace_id,
            "name": self.name,
            "status": self.status,
            "root_path": self.root_path,
            "tags": list(self.tags),
            "last_action": self.last_action,
            "next_action": self.next_action,
            "notes": self.notes,
            "metadata": dict(self.metadata),
            "artifact_count": self.artifact_count,
            "artifacts": [dict(x) for x in self.artifacts],
            "recent_activity": [dict(x) for x in self.recent_activity],
            "updated_at": self.updated_at,
        }


class WorkspaceRuntimeBindingV130:
    """Runtime-facing binding for AURA project context.

    W130-B intentionally does not patch AuraCore/Conversation yet.
    It gives those layers one stable API to consume in W130-C.
    """

    def __init__(self, service: WorkspaceContextServiceV130 | None = None) -> None:
        self.service = service or get_workspace_context_service_v130()

    def active_context(self) -> ActiveProjectRuntimeContext | None:
        record = self.service.get_active_workspace()
        if record is None:
            return None
        return ActiveProjectRuntimeContext.from_record(record)

    def require_active_context(self) -> ActiveProjectRuntimeContext:
        context = self.active_context()
        if context is None:
            raise WorkspaceNotFoundError("no active workspace")
        return context

    def activate(self, workspace_id: str) -> ActiveProjectRuntimeContext:
        record = self.service.set_active_workspace(workspace_id)
        self.service.record_activity(
            workspace_id,
            "workspace.runtime.activated",
            detail="Active workspace bound to AURA runtime.",
            result="active",
        )
        return ActiveProjectRuntimeContext.from_record(
            self.service.get_workspace(workspace_id)
        )

    def update_resume_state(
        self,
        *,
        last_action: str | None = None,
        next_action: str | None = None,
        notes: str | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
    ) -> ActiveProjectRuntimeContext:
        current = self.require_active_context()
        self.service.update_workspace(
            current.workspace_id,
            last_action=last_action,
            next_action=next_action,
            notes=notes,
            metadata_patch=metadata_patch,
        )
        self.service.record_activity(
            current.workspace_id,
            "workspace.runtime.resume_state.updated",
            detail=last_action or "",
            result=next_action or "",
        )
        return self.require_active_context()

    def bind_artifact(
        self,
        path: str | Path,
        *,
        kind: str = "file",
        label: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ActiveProjectRuntimeContext:
        current = self.require_active_context()
        artifact = self.service.add_artifact(
            current.workspace_id,
            path,
            kind=kind,
            label=label,
            metadata=metadata,
        )
        self.service.record_activity(
            current.workspace_id,
            "workspace.runtime.artifact.bound",
            detail=artifact.path,
            result=artifact.artifact_id,
        )
        return self.require_active_context()

    def resume_payload(self) -> dict[str, Any]:
        context = self.require_active_context()
        return {
            "schema": RUNTIME_CONTEXT_SCHEMA,
            "workspace": context.to_dict(),
            "resume": {
                "last_action": context.last_action,
                "next_action": context.next_action,
                "root_path": context.root_path,
                "artifact_count": context.artifact_count,
            },
        }

    def prompt_context_block(self, *, max_artifacts: int = 8) -> str:
        context = self.require_active_context()
        artifact_lines = []
        for artifact in context.artifacts[:max(0, int(max_artifacts))]:
            artifact_lines.append(
                f"- [{artifact.get('kind','file')}] "
                f"{artifact.get('label') or Path(str(artifact.get('path') or '')).name}: "
                f"{artifact.get('path','')}"
            )
        if not artifact_lines:
            artifact_lines.append("- Aucun artefact lié.")

        tags = ", ".join(context.tags) if context.tags else "aucun"
        lines = [
            "[AURA_ACTIVE_PROJECT]",
            f"ID: {context.workspace_id}",
            f"Nom: {context.name}",
            f"Statut: {context.status}",
            f"Racine: {context.root_path or 'non définie'}",
            f"Tags: {tags}",
            f"Dernière action: {context.last_action or 'aucune'}",
            f"Prochaine action: {context.next_action or 'aucune'}",
            f"Notes: {context.notes or 'aucune'}",
            "Artefacts:",
            *artifact_lines,
            "[/AURA_ACTIVE_PROJECT]",
        ]
        return "\n".join(lines)

    def runtime_snapshot(self) -> dict[str, Any]:
        context = self.active_context()
        return {
            "schema": RUNTIME_CONTEXT_SCHEMA,
            "active": context is not None,
            "workspace": None if context is None else context.to_dict(),
        }


def get_workspace_runtime_binding_v130(
    service: WorkspaceContextServiceV130 | None = None,
) -> WorkspaceRuntimeBindingV130:
    return WorkspaceRuntimeBindingV130(service=service)
