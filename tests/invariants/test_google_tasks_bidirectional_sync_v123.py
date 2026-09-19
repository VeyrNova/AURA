from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from accounts.model import GOOGLE_SERVICES_V120, GOOGLE_SERVICES_V123
from accounts.google_tasks_oauth_v123 import (
    GOOGLE_TASKS_SCOPE_V123,
    GOOGLE_PRODUCTIVITY_SCOPES_V123,
)
from integrations.tasks import TASKS_PROVIDER_ID, TasksProvider
from runtime.google_productivity_sync_v123 import (
    classify_reminder_target_v123,
    conflict_state_v123,
)
from runtime.integration_permissions_tasks_v123 import (
    ALLOW, DENY, REQUIRE_CONFIRMATION,
    evaluate_integration_permission_tasks_v123,
)
from security.permissions import Permission

assert GOOGLE_SERVICES_V120 == ("gmail", "calendar", "contacts", "drive")
assert GOOGLE_SERVICES_V123 == ("gmail", "calendar", "contacts", "drive", "tasks")
assert GOOGLE_TASKS_SCOPE_V123 in GOOGLE_PRODUCTIVITY_SCOPES_V123

class FakeBackend:
    def health_snapshot(self):
        return {"provider": "google", "service": "tasks", "available": True, "mode": "GOOGLE_LIVE"}
    def list_tasklists(self): return ()
    def list_tasks(self, tasklist_id="@default", limit=100, include_completed=True): return ()
    def get_task(self, task_id, tasklist_id="@default"): return {"task_id": task_id}
    def create_task(self, **kwargs): return {"created": True}
    def update_task(self, task_id, **kwargs): return {"updated": task_id}
    def complete_task(self, task_id, **kwargs): return {"completed": task_id}
    def delete_task(self, task_id, **kwargs): return {"deleted": task_id}

provider = TasksProvider(FakeBackend())
# Canonical IntegrationProvider contract: manifest is a property, not a method.
assert not callable(provider.manifest)
manifest = provider.manifest
assert manifest.provider_id == TASKS_PROVIDER_ID
assert {x.capability_id for x in manifest.capabilities} == {
    "tasks.tasklists", "tasks.list", "tasks.read",
    "tasks.create", "tasks.update", "tasks.complete", "tasks.delete",
}

assert evaluate_integration_permission_tasks_v123(
    "tasks.list", granted_permissions={Permission.WEB_READ}
).decision == ALLOW
assert evaluate_integration_permission_tasks_v123(
    "tasks.create",
    granted_permissions={Permission.EXTERNAL_NETWORK},
    user_confirmed=False,
).decision == REQUIRE_CONFIRMATION
assert evaluate_integration_permission_tasks_v123(
    "tasks.create",
    granted_permissions={Permission.EXTERNAL_NETWORK},
    user_confirmed=True,
).decision == ALLOW
assert evaluate_integration_permission_tasks_v123(
    "tasks.unknown", granted_permissions={Permission.WEB_READ}
).decision == DENY

assert classify_reminder_target_v123(
    due_at="2026-09-01", has_explicit_time=False
).provider == "tasks.provider"
assert classify_reminder_target_v123(
    due_at="2026-09-01T10:00:00+02:00", has_explicit_time=True
).provider == "calendar.provider"
assert conflict_state_v123(
    local_updated="L2",
    remote_updated="R2",
    last_synced_remote_updated="R1",
) == "conflict"

bridge = (ROOT / "runtime" / "google_personal_integrations_bridge_v121.py").read_text(encoding="utf-8-sig")
assert "GoogleLiveTasksBackendV123" in bridge
assert "TasksProvider(backend=tasks_backend)" in bridge

registry = (ROOT / "integrations" / "registry.py").read_text(encoding="utf-8-sig")
assert "AURA_V123_TASKS_PERMISSION_EXTENSION_BEGIN" in registry
assert "evaluate_integration_permission_tasks_v123" in registry

modules = (ROOT / "ui" / "personal_integration_modules.py").read_text(encoding="utf-8-sig")
assert "class TasksModuleController" in modules
assert "self.tasks = TasksModuleController" in modules
assert '"tasks": self.tasks.status().to_dict()' in modules

ui = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
renderer = (ui / "dist" / "assets" / "aura-v123-personal-results-web.js").read_text(encoding="utf-8-sig")
conversation_css = (ui / "dist" / "assets" / "aura-p0712-conversation-ui.css").read_text(encoding="utf-8-sig")
assert "AURA_V123_CONVERSATION_RESULTS_COEXISTENCE_BEGIN" in renderer
assert "--aura-v123-conversation-right-reserve" in renderer
assert "AURA_V123_CONVERSATION_RESULTS_COEXISTENCE" in conversation_css
assert "aura-v123-personal-results-open" in conversation_css

print("[PASS] v1.2.3 Google Tasks bidirectional sync foundation")
print("[PASS] Tasks permission extension + explicit confirmations")
print("[PASS] date-only reminders -> Tasks; timed reminders -> Calendar")
print("[PASS] Conversation | Results | SYSTEM LIVE coexistence contract")
print("[PASS] deterministic: no network / no Google mutation")
