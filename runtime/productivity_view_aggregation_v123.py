"""AURA v1.2.3 productivity view aggregation.

Read-only presentation helper.
It combines AURA's existing local productivity stores with already-fetched
Google Personal Result payloads. It never writes local or Google data.
"""
from __future__ import annotations

from typing import Any, Mapping

MARKER = "AURA_V123_PRODUCTIVITY_VIEW_AGGREGATION"


def _text(row: Mapping[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None:
            value = str(value).strip()
            if value:
                return value
    return ""


def _safe_rows(callable_obj, *args, **kwargs) -> list[dict[str, Any]]:
    if not callable(callable_obj):
        return []
    try:
        rows = callable_obj(*args, **kwargs)
    except TypeError:
        try:
            rows = callable_obj()
        except Exception:
            return []
    except Exception:
        return []
    out = []
    for row in rows or ():
        if isinstance(row, Mapping):
            out.append(dict(row))
        elif hasattr(row, "to_dict"):
            try:
                value = row.to_dict()
                if isinstance(value, Mapping):
                    out.append(dict(value))
            except Exception:
                pass
    return out


def collect_local_task_items_v123(task_manager, limit: int = 100) -> list[dict[str, Any]]:
    if task_manager is None:
        return []
    rows = _safe_rows(
        getattr(task_manager, "list_tasks", None),
        status="TODO",
        limit=max(1, int(limit)),
    )
    out: list[dict[str, Any]] = []
    for row in rows:
        title = _text(row, "title", "content", "name")
        if not title:
            continue
        local_id = _text(row, "id", "task_id", "uuid")
        due = _text(row, "due_at", "due", "scheduled_at", "deadline")
        status = _text(row, "status") or "TODO"
        notes = _text(row, "notes", "description")
        out.append(
            {
                "source": "AURA",
                "source_kind": "local_task",
                "local_id": local_id,
                "title": title,
                "due": due,
                "status": status,
                "notes": notes,
                "completed": status.casefold() in {"done", "completed", "complete"},
            }
        )
    return out


def collect_local_agenda_items_v123(
    reminder_manager,
    task_manager=None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    if reminder_manager is not None:
        rows = _safe_rows(
            getattr(reminder_manager, "list_reminders", None),
            include_done=False,
            limit=max(1, int(limit)),
        )
        for row in rows:
            title = _text(row, "content", "title", "message")
            if not title:
                continue
            out.append(
                {
                    "source": "AURA RAPPEL",
                    "source_kind": "local_reminder",
                    "local_id": _text(row, "id", "reminder_id", "uuid"),
                    "title": title,
                    "start_time": _text(
                        row, "due_at", "scheduled_at", "due", "remind_at"
                    ),
                    "duration": "Rappel AURA",
                }
            )

    # Dated local tasks are also useful in the Agenda view, but undated tasks
    # remain only in the Tasks module.
    for row in collect_local_task_items_v123(task_manager, limit=limit):
        due = str(row.get("due") or "").strip()
        if not due:
            continue
        out.append(
            {
                "source": "AURA TÂCHE",
                "source_kind": "local_task",
                "local_id": str(row.get("local_id") or ""),
                "title": str(row.get("title") or ""),
                "start_time": due,
                "duration": "Échéance tâche AURA",
            }
        )
    return out


def _copy_google_items(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("items")
    if not isinstance(rows, (list, tuple)):
        rows = payload.get("results")
    if not isinstance(rows, (list, tuple)):
        return []
    out = []
    for raw in rows:
        if isinstance(raw, Mapping):
            item = dict(raw)
        else:
            continue
        if not str(item.get("source") or "").strip():
            item["source"] = "GOOGLE"
        item.setdefault("source_kind", "google")
        out.append(item)
    return out


def merge_productivity_result_payload_v123(
    payload: Mapping[str, Any] | None,
    aura_core,
) -> dict[str, Any]:
    """Merge local AURA rows into an already-normalized Personal Result."""
    data = dict(payload or {})
    kind = str(data.get("kind") or "").casefold().strip()
    if kind not in {"tasks", "calendar"}:
        return data

    google_items = _copy_google_items(data)
    if kind == "tasks":
        local_items = collect_local_task_items_v123(
            getattr(aura_core, "task_manager", None),
            limit=100,
        )
    else:
        local_items = collect_local_agenda_items_v123(
            getattr(aura_core, "reminder_manager", None),
            getattr(aura_core, "task_manager", None),
            limit=100,
        )

    # Do not guess duplicates by title. Stable cross-store IDs are required
    # before an item may be considered the same record.
    merged = google_items + local_items
    data["items"] = merged
    data["count"] = len(merged)
    data["source_breakdown"] = {
        "google": len(google_items),
        "aura_local": len(local_items),
    }
    data["aggregated"] = True
    return data
