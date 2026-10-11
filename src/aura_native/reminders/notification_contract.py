from dataclasses import dataclass
from enum import Enum


class NotificationCapability(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


@dataclass(frozen=True)
class NotificationResult:
    accepted: bool
    capability: NotificationCapability
    notification_id: str
    channel: str
    source: str = "reminder"
    reason: str = ""


def notification_id(reminder, *, is_missed=False):
    reminder_id = str(reminder.get("reminder_id", "")).strip()
    trigger_at = str(reminder.get("trigger_at", "")).strip()
    if not reminder_id or not trigger_at:
        return ""
    return f"reminder:{reminder_id}:{trigger_at}:{int(bool(is_missed))}"
