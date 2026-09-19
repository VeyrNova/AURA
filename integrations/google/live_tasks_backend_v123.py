from __future__ import annotations

from datetime import date

from googleapiclient.discovery import build

from accounts.google_tasks_oauth_v123 import credentials_for_tasks_v123
from integrations.tasks.provider import TaskItem, TaskListInfo
from runtime.connected_accounts_v120 import get_connected_accounts_service_v120


class GoogleTasksReconsentRequired(RuntimeError):
    pass


def _is_date(value: str) -> bool:
    if len(value) != 10:
        return False
    try:
        date.fromisoformat(value)
        return True
    except Exception:
        return False


def _due(value) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return text + "T00:00:00.000Z" if _is_date(text) else text


def _task(raw, tasklist_id="@default"):
    return TaskItem(
        task_id=str(raw.get("id", "")),
        tasklist_id=str(tasklist_id or "@default"),
        title=str(raw.get("title", "")),
        notes=str(raw.get("notes", "")),
        due=str(raw.get("due", "")),
        status=str(raw.get("status", "needsAction")),
        completed=str(raw.get("completed", "")),
        etag=str(raw.get("etag", "")),
        updated=str(raw.get("updated", "")),
        position=str(raw.get("position", "")),
        parent=str(raw.get("parent", "")),
        web_link=str(raw.get("webViewLink", raw.get("selfLink", ""))),
    )


class GoogleLiveTasksBackendV123:
    mode = "GOOGLE_LIVE"

    def __init__(self, *, service=None, api_factory=build):
        self.service = service or get_connected_accounts_service_v120()
        self.api_factory = api_factory

    def _account(self):
        rows = self.service.list_accounts("google")
        if not rows:
            raise GoogleTasksReconsentRequired("Google account is not connected")
        account = rows[0]
        if "tasks" not in tuple(str(x).lower() for x in account.services):
            raise GoogleTasksReconsentRequired("Google Tasks OAuth re-consent required")
        return account

    def _tasks(self):
        account = self._account()
        credentials = credentials_for_tasks_v123(self.service, account)
        return self.api_factory(
            "tasks",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def health_snapshot(self):
        rows = self.service.list_accounts("google")
        enabled = bool(
            rows
            and "tasks" in tuple(str(x).lower() for x in rows[0].services)
        )
        return {
            "provider": "google",
            "service": "tasks",
            "mode": self.mode,
            "available": enabled,
            "health_state": "ready" if enabled else "reconsent_required",
            "tasks_scope_required": True,
            "read_only": False,
        }

    def list_tasklists(self):
        response = self._tasks().tasklists().list(maxResults=100).execute()
        return tuple(
            TaskListInfo(
                tasklist_id=str(x.get("id", "")),
                title=str(x.get("title", "")),
                etag=str(x.get("etag", "")),
                updated=str(x.get("updated", "")),
            )
            for x in response.get("items", []) or []
        )

    def list_tasks(self, tasklist_id="@default", limit=100, include_completed=True):
        response = (
            self._tasks()
            .tasks()
            .list(
                tasklist=str(tasklist_id or "@default"),
                maxResults=max(1, min(int(limit or 100), 100)),
                showCompleted=bool(include_completed),
                showHidden=bool(include_completed),
            )
            .execute()
        )
        return tuple(
            _task(x, tasklist_id)
            for x in response.get("items", []) or []
        )

    def get_task(self, task_id, tasklist_id="@default"):
        raw = (
            self._tasks()
            .tasks()
            .get(tasklist=str(tasklist_id or "@default"), task=str(task_id))
            .execute()
        )
        return _task(raw, tasklist_id)

    def create_task(self, *, title, notes="", due="", tasklist_id="@default"):
        body = {"title": str(title)}
        if notes:
            body["notes"] = str(notes)
        due_value = _due(due)
        if due_value:
            body["due"] = due_value
        raw = (
            self._tasks()
            .tasks()
            .insert(tasklist=str(tasklist_id or "@default"), body=body)
            .execute()
        )
        return _task(raw, tasklist_id)

    def update_task(self, task_id, *, tasklist_id="@default", **changes):
        body = {}
        for key in ("title", "notes", "status"):
            if key in changes and changes[key] is not None:
                body[key] = str(changes[key])
        if "due" in changes:
            due_value = _due(changes.get("due"))
            body["due"] = due_value or None
        raw = (
            self._tasks()
            .tasks()
            .patch(
                tasklist=str(tasklist_id or "@default"),
                task=str(task_id),
                body=body,
            )
            .execute()
        )
        return _task(raw, tasklist_id)

    def complete_task(self, task_id, *, tasklist_id="@default"):
        return self.update_task(
            task_id,
            tasklist_id=tasklist_id,
            status="completed",
        )

    def delete_task(self, task_id, *, tasklist_id="@default"):
        (
            self._tasks()
            .tasks()
            .delete(tasklist=str(tasklist_id or "@default"), task=str(task_id))
            .execute()
        )
        return {
            "deleted": True,
            "task_id": str(task_id),
            "tasklist_id": str(tasklist_id or "@default"),
        }


__all__ = ["GoogleTasksReconsentRequired", "GoogleLiveTasksBackendV123"]
