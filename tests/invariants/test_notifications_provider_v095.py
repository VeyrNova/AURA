from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.notifications.provider import (
    CAPABILITIES,
    LEGACY_BRIDGE,
    MODE,
    PROVIDER_ID,
    NotificationsProvider,
)

DB = ROOT / "database" / "aura.db"
EXPECTED_DB = "de473830987af1daca53a90cdba53a6558d5e2494a6556a5de2ff6c7dc4260fb"
EXPECTED_DB_SIZE = 425984


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = (
    sha(DB),
    DB.stat().st_size,
)

provider = NotificationsProvider()

assert PROVIDER_ID == "notifications.provider"
assert MODE == "BRIDGE_EXISTING_P081_P083"
assert list(CAPABILITIES) == [
    "notifications.list",
    "notifications.read",
    "notifications.create",
    "notifications.mark_read",
    "notifications.dismiss",
    "notifications.clear",
]

assert LEGACY_BRIDGE["duplicate_activity_center"] is False
assert LEGACY_BRIDGE["duplicate_popup_layer"] is False
assert LEGACY_BRIDGE["external_delivery"] is False
assert LEGACY_BRIDGE["network_access"] is False
assert LEGACY_BRIDGE["auto_action"] is False

assert provider.list() == []

created = provider.create(
    title="Test local notification",
    message="D2 R1 synthetic bridge record",
    priority="high",
    source="invariant",
    meta={"test": True},
)

record = created["notification"]
assert record["status"] == "new"
assert record["delivery"]["external"] is False
assert record["delivery"]["windows_notification"] is False
assert record["delivery"]["network"] is False
assert record["delivery"]["auto_action"] is False

assert len(provider.list()) == 1
assert len(provider.list(unread_only=True)) == 1
assert provider.read(record["id"])["id"] == record["id"]

read_result = provider.mark_read(record["id"])
assert read_result["notification"]["status"] == "read"
assert provider.list(unread_only=True) == []

dismissed = provider.dismiss(record["id"])
assert dismissed["notification"]["status"] == "dismissed"
assert provider.list() == []
assert len(provider.list(include_dismissed=True)) == 1

blocked = False

try:
    provider.clear()
except PermissionError:
    blocked = True

assert blocked is True

cleared = provider.clear(confirmed=True)
assert cleared["cleared"] == 1
assert provider.list(include_dismissed=True) == []

audit = provider.audit()
assert audit["network_access"] is False
assert audit["windows_notifications"] is False
assert audit["external_delivery"] is False
assert audit["background_llm"] is False
assert audit["auto_action"] is False
assert audit["user_database"] is False

after = (
    sha(DB),
    DB.stat().st_size,
)

assert before == after
assert after == (
    EXPECTED_DB,
    EXPECTED_DB_SIZE,
)

print("[PASS] AURA v0.9.5 Notifications Provider invariant")
print("[PASS] local bridge provider with no external side effects")
print("[PASS] clear requires explicit confirmation")
print("[PASS] user database unchanged")
