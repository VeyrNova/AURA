from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ReminderSyncTargetV123:
    provider: str
    capability: str
    reason: str


def classify_reminder_target_v123(*, due_at: str = "", has_explicit_time: bool = False):
    if bool(has_explicit_time):
        return ReminderSyncTargetV123(
            "calendar.provider",
            "calendar.create_event",
            "timed_reminder_requires_calendar_notification",
        )
    return ReminderSyncTargetV123(
        "tasks.provider",
        "tasks.create",
        "date_only_reminder_maps_to_google_tasks",
    )


def remote_identity_v123(provider: str, container_id: str, item_id: str) -> str:
    return f"{str(provider).strip()}:{str(container_id).strip()}:{str(item_id).strip()}"


def conflict_state_v123(
    *,
    local_updated: str = "",
    remote_updated: str = "",
    last_synced_remote_updated: str = "",
) -> str:
    local_changed = bool(local_updated)
    remote_changed = bool(
        remote_updated and remote_updated != last_synced_remote_updated
    )
    if local_changed and remote_changed:
        return "conflict"
    if remote_changed:
        return "pull_remote"
    if local_changed:
        return "push_local"
    return "in_sync"


__all__ = [
    "ReminderSyncTargetV123",
    "classify_reminder_target_v123",
    "remote_identity_v123",
    "conflict_state_v123",
]
