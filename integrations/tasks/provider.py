from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping, Protocol

from integrations.registry import (
    IntegrationCapability,
    IntegrationManifest,
    IntegrationRequest,
)

TASKS_PROVIDER_ID = "tasks.provider"
TASKS_CONFIRMATION_CAPABILITIES = frozenset(
    {"tasks.create", "tasks.update", "tasks.complete", "tasks.delete"}
)


@dataclass(frozen=True)
class TaskListInfo:
    tasklist_id: str
    title: str
    etag: str = ""
    updated: str = ""

    @property
    def id(self) -> str:
        return self.tasklist_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskItem:
    task_id: str
    tasklist_id: str
    title: str
    notes: str = ""
    due: str = ""
    status: str = "needsAction"
    completed: str = ""
    etag: str = ""
    updated: str = ""
    position: str = ""
    parent: str = ""
    web_link: str = ""

    @property
    def id(self) -> str:
        return self.task_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TaskResult:
    tasks: tuple[TaskItem, ...] = ()
    tasklists: tuple[TaskListInfo, ...] = ()
    count: int = 0
    total: int = 0
    tasklist_id: str = "@default"

    @property
    def items(self):
        return self.tasks or self.tasklists

    @property
    def results(self):
        return self.items

    def to_dict(self) -> dict[str, Any]:
        items = self.items
        return {
            "tasks": [x.to_dict() for x in self.tasks],
            "tasklists": [x.to_dict() for x in self.tasklists],
            "items": [x.to_dict() if hasattr(x, "to_dict") else x for x in items],
            "count": self.count,
            "total": self.total,
            "tasklist_id": self.tasklist_id,
        }


class TasksBackend(Protocol):
    def list_tasklists(self): ...
    def list_tasks(self, tasklist_id="@default", limit=100, include_completed=True): ...
    def get_task(self, task_id, tasklist_id="@default"): ...
    def create_task(self, *, title, notes="", due="", tasklist_id="@default"): ...
    def update_task(self, task_id, *, tasklist_id="@default", **changes): ...
    def complete_task(self, task_id, *, tasklist_id="@default"): ...
    def delete_task(self, task_id, *, tasklist_id="@default"): ...
    def health_snapshot(self) -> Mapping[str, Any]: ...


def _cap(capability_id, description, risk, confirm, effect):
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id,
        description=description,
        risk_tier=risk,
        requires_confirmation=confirm,
        side_effect_class=effect,
        evidence_required=True,
    )


_CAPABILITIES = (
    _cap("tasks.tasklists", "Lister les listes Google Tasks", "LOW", False, "read_only"),
    _cap("tasks.list", "Lister les taches Google", "LOW", False, "read_only"),
    _cap("tasks.read", "Lire une tache Google", "LOW", False, "read_only"),
    _cap("tasks.create", "Creer une tache Google", "MEDIUM", True, "state_change"),
    _cap("tasks.update", "Modifier une tache Google", "MEDIUM", True, "state_change"),
    _cap("tasks.complete", "Terminer une tache Google", "MEDIUM", True, "state_change"),
    _cap("tasks.delete", "Supprimer une tache Google", "HIGH", True, "state_change"),
)


# AURA_V123_TASKS_MAPPING_PAYLOAD_CONTRACT
def _mapping_payload(value):
    if isinstance(value, Mapping):
        return dict(value)
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        out = to_dict()
        if isinstance(out, Mapping):
            return dict(out)
    raise TypeError("Tasks provider backend result must be mapping-compatible")


def _single_task_payload(value, tasklist_id="@default"):
    item = _mapping_payload(value)
    rows = [item] if item else []
    return {
        "task": item,
        "tasks": rows,
        "items": rows,
        "results": rows,
        "count": len(rows),
        "total": len(rows),
        "tasklist_id": str(item.get("tasklist_id") or tasklist_id or "@default"),
    }


class TasksProvider:
    def __init__(self, backend: TasksBackend):
        self.backend = backend
        self._backend = backend

    @property
    def manifest(self) -> IntegrationManifest:
        return IntegrationManifest(
            provider_id=TASKS_PROVIDER_ID,
            display_name="Google Tasks",
            provider_version="1.2.3",
            capabilities=_CAPABILITIES,
            auth_kind="google_oauth",
            metadata={
                "mode": "GOOGLE_LIVE",
                "bidirectional": True,
                "requires_tasks_scope": True,
            },
        )

    def health_snapshot(self) -> Mapping[str, Any]:
        try:
            out = dict(self.backend.health_snapshot())
        except Exception as exc:
            return {
                "available": False,
                "health_state": "degraded",
                "error": type(exc).__name__,
            }
        out.setdefault("available", True)
        out.setdefault("health_state", "ready" if out.get("available") else "degraded")
        return out

    def execute(self, request: IntegrationRequest):
        cap = str(request.capability_id or "")
        params = dict(request.params or {})

        if cap == "tasks.tasklists":
            rows = tuple(self.backend.list_tasklists())
            return TaskResult(tasklists=rows, count=len(rows), total=len(rows)).to_dict()

        if cap == "tasks.list":
            q = params.get("query") or params
            tasklist_id = str(q.get("tasklist_id") or q.get("tasklist") or "@default")
            limit = int(q.get("limit", 100) or 100)
            include_completed = bool(q.get("include_completed", True))
            rows = tuple(
                self.backend.list_tasks(
                    tasklist_id=tasklist_id,
                    limit=limit,
                    include_completed=include_completed,
                )
            )
            return TaskResult(
                tasks=rows,
                count=len(rows),
                total=len(rows),
                tasklist_id=tasklist_id,
            ).to_dict()

        if cap == "tasks.read":
            tasklist_id = str(params.get("tasklist_id") or "@default")
            return _single_task_payload(
                self.backend.get_task(
                    str(params.get("task_id") or params.get("id") or ""),
                    tasklist_id=tasklist_id,
                ),
                tasklist_id,
            )

        if cap == "tasks.create":
            tasklist_id = str(params.get("tasklist_id") or "@default")
            return _single_task_payload(
                self.backend.create_task(
                    title=str(params.get("title") or ""),
                    notes=str(params.get("notes") or ""),
                    due=str(params.get("due") or ""),
                    tasklist_id=tasklist_id,
                ),
                tasklist_id,
            )

        if cap == "tasks.update":
            task_id = str(params.pop("task_id", params.pop("id", "")))
            tasklist_id = str(params.pop("tasklist_id", "@default"))
            return _single_task_payload(
                self.backend.update_task(
                    task_id,
                    tasklist_id=tasklist_id,
                    **params,
                ),
                tasklist_id,
            )

        if cap == "tasks.complete":
            tasklist_id = str(params.get("tasklist_id") or "@default")
            return _single_task_payload(
                self.backend.complete_task(
                    str(params.get("task_id") or params.get("id") or ""),
                    tasklist_id=tasklist_id,
                ),
                tasklist_id,
            )

        if cap == "tasks.delete":
            return self.backend.delete_task(
                str(params.get("task_id") or params.get("id") or ""),
                tasklist_id=str(params.get("tasklist_id") or "@default"),
            )

        raise ValueError("unsupported Tasks capability: " + cap)


__all__ = [
    "TASKS_PROVIDER_ID",
    "TASKS_CONFIRMATION_CAPABILITIES",
    "TaskListInfo",
    "TaskItem",
    "TaskResult",
    "TasksBackend",
    "TasksProvider",
]
