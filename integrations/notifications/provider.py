from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4


PROVIDER_ID = "notifications.provider"
MODE = "BRIDGE_EXISTING_P081_P083"
CAPABILITIES = (
    "notifications.list",
    "notifications.read",
    "notifications.create",
    "notifications.mark_read",
    "notifications.dismiss",
    "notifications.clear",
)

LEGACY_BRIDGE = {
    "event_history_authority": "P0.8.1 AuraEventWatchers / Activity Center",
    "presentation_authority": "P0.8.3 AuraProactiveNotifications",
    "provider_authority": PROVIDER_ID,
    "duplicate_activity_center": False,
    "duplicate_popup_layer": False,
    "external_delivery": False,
    "windows_notifications": False,
    "network_access": False,
    "background_llm": False,
    "auto_action": False,
}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _receipt(action, target=None, status="completed"):
    return {
        "schema": "aura.notification-action-receipt.v1",
        "provider": PROVIDER_ID,
        "action": action,
        "target": target,
        "status": status,
        "at": _now(),
        "external_side_effect": False,
    }


class NotificationsProvider:
    provider_id = PROVIDER_ID
    mode = MODE
    capabilities = CAPABILITIES

    def __init__(self):
        self._lock = RLock()
        self._records = []

    def _clone(self, record):
        return deepcopy(record)

    def list(self, *, include_dismissed=False, unread_only=False):
        with self._lock:
            rows = []

            for record in self._records:
                if (
                    not include_dismissed
                    and record["status"] == "dismissed"
                ):
                    continue

                if (
                    unread_only
                    and record["status"] != "new"
                ):
                    continue

                rows.append(
                    self._clone(record)
                )

            rows.sort(
                key=lambda item: item["created_at"],
                reverse=True,
            )

            return rows

    def read(self, notification_id):
        with self._lock:
            for record in self._records:
                if record["id"] == notification_id:
                    return self._clone(record)

        return None

    def create(
        self,
        *,
        title,
        message="",
        priority="normal",
        source="aura",
        meta=None,
    ):
        priority = str(priority or "normal").lower()

        if priority not in {
            "normal",
            "high",
            "urgent",
        }:
            priority = "normal"

        record = {
            "id": "notif-" + uuid4().hex,
            "title": str(title or "").strip()[:240],
            "message": str(message or "").strip()[:4000],
            "priority": priority,
            "source": str(source or "aura").strip()[:160],
            "status": "new",
            "created_at": _now(),
            "read_at": None,
            "dismissed_at": None,
            "meta": deepcopy(meta or {}),
            "delivery": {
                "type": "local_bridge_record",
                "external": False,
                "windows_notification": False,
                "network": False,
                "auto_action": False,
            },
        }

        if not record["title"]:
            raise ValueError("notification title is required")

        with self._lock:
            self._records.append(record)

        return {
            "notification": self._clone(record),
            "receipt": _receipt(
                "notifications.create",
                record["id"],
            ),
        }

    def mark_read(self, notification_id):
        with self._lock:
            for record in self._records:
                if record["id"] != notification_id:
                    continue

                if record["status"] != "dismissed":
                    record["status"] = "read"
                    record["read_at"] = (
                        record["read_at"]
                        or _now()
                    )

                return {
                    "notification": self._clone(record),
                    "receipt": _receipt(
                        "notifications.mark_read",
                        notification_id,
                    ),
                }

        return None

    def dismiss(self, notification_id):
        with self._lock:
            for record in self._records:
                if record["id"] != notification_id:
                    continue

                record["status"] = "dismissed"
                record["dismissed_at"] = _now()

                return {
                    "notification": self._clone(record),
                    "receipt": _receipt(
                        "notifications.dismiss",
                        notification_id,
                    ),
                }

        return None

    def clear(self, *, confirmed=False):
        if confirmed is not True:
            raise PermissionError(
                "notifications.clear requires explicit confirmation"
            )

        with self._lock:
            count = len(self._records)
            self._records = []

        return {
            "cleared": count,
            "receipt": _receipt(
                "notifications.clear",
                "all",
            ),
        }

    def bridge_snapshot(self):
        with self._lock:
            unread = sum(
                1
                for record in self._records
                if record["status"] == "new"
            )

            return {
                "provider": PROVIDER_ID,
                "mode": MODE,
                "capabilities": list(CAPABILITIES),
                "legacy_bridge": deepcopy(LEGACY_BRIDGE),
                "record_count": len(self._records),
                "unread": unread,
            }

    def audit(self):
        snapshot = self.bridge_snapshot()

        return {
            **snapshot,
            "persistence": "provider-owned in-memory D2 sandbox",
            "user_database": False,
            "network_access": False,
            "windows_notifications": False,
            "external_delivery": False,
            "background_llm": False,
            "auto_action": False,
        }
