from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import integrations.registry as registry
from runtime.personal_integrations import (
    get_notifications_provider_v095,
    notifications_capability_context_v095,
)
from ui.personal_integration_modules import NotificationsModuleController

descriptor = registry.AURA_V095_NOTIFICATIONS_PROVIDER_DESCRIPTOR

assert descriptor["id"] == "notifications.provider"
assert descriptor["mode"] == "BRIDGE_EXISTING_P081_P083"
assert descriptor["legacy"]["duplicate_history_ui"] is False
assert descriptor["legacy"]["duplicate_popup_layer"] is False
assert descriptor["external_delivery"] is False
assert descriptor["network_side_effects"] is False
assert descriptor["auto_action"] is False

provider_a = get_notifications_provider_v095()
provider_b = get_notifications_provider_v095()

assert provider_a is provider_b
assert provider_a.provider_id == "notifications.provider"

context = notifications_capability_context_v095()

assert context["provider"] == "notifications.provider"
assert context["mode"] == "BRIDGE_EXISTING_P081_P083"
assert context["legacy_bridge"]["reuse_existing_activity_center"] is True
assert context["legacy_bridge"]["duplicate_notification_surface"] is False
assert context["external_delivery"] is False
assert context["network_side_effects"] is False
assert context["auto_action"] is False

controller = NotificationsModuleController()
intent = controller.open_activity_center_intent()

assert intent["legacy_surface"] == "P0.8.1 Activity Center"
assert intent["browser_api"] == "window.AuraEventWatchers.open"
assert intent["presentation_api"] == "window.AuraProactiveNotifications"
assert intent["workspace"] == "talk"
assert intent["prefill_if_empty"] == "affiche mes notifications"
assert intent["preserve_non_empty_draft"] is True
assert intent["auto_submit"] is False
assert intent["duplicate_history_ui"] is False

created = controller.create_notification(
    title="Bridge invariant",
    message="No external delivery",
    priority="normal",
    source="runtime-invariant",
)

notification_id = created["notification"]["id"]

assert controller.read_notification(notification_id)["id"] == notification_id
assert controller.mark_read(notification_id)["notification"]["status"] == "read"
assert controller.dismiss(notification_id)["notification"]["status"] == "dismissed"

clear_blocked = False

try:
    controller.clear()
except PermissionError:
    clear_blocked = True

assert clear_blocked is True
assert controller.clear(confirmed=True)["cleared"] >= 1

print("[PASS] AURA v0.9.5 Notifications runtime bridge invariant")
print("[PASS] registry descriptor + runtime singleton + controller")
print("[PASS] legacy Activity Center / Proactive Notifications reused")
print("[PASS] no duplicate notification history UI contract")
