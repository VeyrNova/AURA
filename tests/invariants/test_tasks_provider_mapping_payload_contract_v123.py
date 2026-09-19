from __future__ import annotations

import sys
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.registry import IntegrationRequest
from integrations.tasks.provider import (
    TaskItem,
    TaskListInfo,
    TasksProvider,
)

class FakeBackend:
    def health_snapshot(self):
        return {"available": True, "health_state": "ready", "mode": "GOOGLE_LIVE"}

    def list_tasklists(self):
        return (TaskListInfo("list-1", "Test"),)

    def list_tasks(self, tasklist_id="@default", limit=100, include_completed=True):
        return (
            TaskItem(
                task_id="task-1",
                tasklist_id=tasklist_id,
                title="Synthetic",
            ),
        )

    def get_task(self, task_id, tasklist_id="@default"):
        return TaskItem(task_id, tasklist_id, "Synthetic")

    def create_task(self, *, title, notes="", due="", tasklist_id="@default"):
        return TaskItem("created-1", tasklist_id, title, notes=notes, due=due)

    def update_task(self, task_id, *, tasklist_id="@default", **changes):
        return TaskItem(task_id, tasklist_id, changes.get("title", "Updated"))

    def complete_task(self, task_id, *, tasklist_id="@default"):
        return TaskItem(task_id, tasklist_id, "Completed", status="completed")

    def delete_task(self, task_id, *, tasklist_id="@default"):
        return {"deleted": True, "task_id": task_id, "tasklist_id": tasklist_id}

provider = TasksProvider(FakeBackend())

def req(capability, params):
    return IntegrationRequest.create(
        provider_id="tasks.provider",
        capability_id=capability,
        params=params,
        origin="v123.tasks.mapping.invariant",
    )

tasklists = provider.execute(req("tasks.tasklists", {}))
assert isinstance(tasklists, Mapping)
assert tasklists["count"] == 1
assert len(tasklists["tasklists"]) == 1

listed = provider.execute(req(
    "tasks.list",
    {"query":{"tasklist_id":"@default","limit":100,"include_completed":True}},
))
assert isinstance(listed, Mapping)
assert listed["count"] == 1
assert len(listed["tasks"]) == 1
assert listed["tasks"][0]["task_id"] == "task-1"

for capability, params in (
    ("tasks.read", {"task_id":"task-1"}),
    ("tasks.create", {"title":"Synthetic"}),
    ("tasks.update", {"task_id":"task-1","title":"Updated"}),
    ("tasks.complete", {"task_id":"task-1"}),
):
    out = provider.execute(req(capability, params))
    assert isinstance(out, Mapping), capability
    assert out["count"] == 1, capability
    assert len(out["tasks"]) == 1, capability
    assert isinstance(out["tasks"][0], Mapping), capability

deleted = provider.execute(req("tasks.delete", {"task_id":"task-1"}))
assert isinstance(deleted, Mapping)
assert deleted["deleted"] is True

runtime = (ROOT / "runtime" / "personal_integrations.py").read_text(
    encoding="utf-8-sig"
)
assert (
    "payload=dict(result.output) if isinstance(result.output, Mapping) else None"
    in runtime
)

source = (ROOT / "integrations" / "tasks" / "provider.py").read_text(
    encoding="utf-8-sig"
)
assert "AURA_V123_TASKS_MAPPING_PAYLOAD_CONTRACT" in source
assert ").to_dict()" in source

print("[PASS] TasksProvider execute outputs are Mapping-compatible")
print("[PASS] list/tasklists preserve count + item arrays")
print("[PASS] single-task read/write replies expose uniform tasks/items payload")
print("[PASS] dispatcher Mapping payload contract is satisfied")
