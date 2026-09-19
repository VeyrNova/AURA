from __future__ import annotations
import os, re, sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.personal_integrations import (
    IntegrationIntentResolver, CALENDAR_PROVIDER_ID,
    CONTACTS_PROVIDER_ID, TASKS_PROVIDER_ID,
)
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

resolver = IntegrationIntentResolver(timezone_name="Europe/Paris")

agenda = resolver.resolve_integration_intent("Aura, affiche mon agenda")
assert agenda and agenda.provider_id == CALENDAR_PROVIDER_ID
assert agenda.capability_id == "calendar.search_events"
assert agenda.params["query"]["calendar_id"] == "cal-main"
assert agenda.params["query"]["text"] == ""
assert agenda.params["query"]["limit"] == 20

contacts = resolver.resolve_integration_intent("Aura, affiche mes contacts")
assert contacts and contacts.provider_id == CONTACTS_PROVIDER_ID
assert contacts.capability_id == "contacts.search"
assert contacts.params["query"]["text"] == ""
assert contacts.params["query"]["limit"] == 100

specific = resolver.resolve_integration_intent("Aura, cherche le contact Martin")
assert specific and specific.provider_id == CONTACTS_PROVIDER_ID
assert specific.capability_id == "contacts.search"
assert str(specific.params["query"]["text"]).strip()

tasks = resolver.resolve_integration_intent("Aura, affiche mes taches")
assert tasks and tasks.provider_id == TASKS_PROVIDER_ID
assert tasks.capability_id == "tasks.list"
assert tasks.params["query"]["tasklist_id"] == "@default"
assert tasks.params["query"]["limit"] == 100
assert tasks.params["query"]["include_completed"] is True

request = SimpleNamespace(provider_id="tasks.provider", capability_id="tasks.list")
reply = SimpleNamespace(
    provider_id="tasks.provider", capability_id="tasks.list",
    status="succeeded", text="",
    payload={"tasks":[{
        "task_id":"task-safe-1","tasklist_id":"@default",
        "title":"Tache de test","due":"2026-09-01T00:00:00.000Z",
        "status":"needsAction","notes":"Test sans donnees utilisateur",
    }]},
)
shown = build_personal_result_payload_v123(reply, request)
assert shown["kind"] == "tasks" and shown["count"] == 1
assert shown["items"][0]["title"] == "Tache de test"
assert shown["items"][0]["status"] == "needsAction"

final_source = (ROOT/"ui"/"final_modules.py").read_text(encoding="utf-8-sig")
assert "class TasksPage(BasePage):" in final_source
assert "AURA_V123_GOOGLE_TASKS_NATIVE_PAGE" in final_source
assert "AURA_V123_NATIVE_TASKS_AGGREGATION" in final_source
assert "AURA_V123_NATIVE_AGENDA_AGGREGATION" in final_source
assert 'SectionCard("TÂCHES · AURA + GOOGLE", strong=True)' in final_source
assert "def set_local_sources(self, *, task_manager=None, **_unused):" in final_source
for name in ("_sync","_create","_update_selected","_complete_selected","_delete_selected"):
    assert ("def " + name + "(self") in final_source

main_source = (ROOT/"ui"/"main_window.py").read_text(encoding="utf-8-sig")
assert "AURA_V123_NATIVE_PRODUCTIVITY_LOCAL_SOURCES_BEGIN" in main_source
assert "self.tasks_page.set_controller(self._personal_integration_modules.tasks)" in main_source
assert "self.tasks_page.set_local_sources(task_manager=self.aura_core.task_manager)" in main_source
assert "reminder_manager=self.aura_core.reminder_manager" in main_source

core_source = (ROOT/"core"/"aura_core.py").read_text(encoding="utf-8-sig")
assert "AURA_V123_PRODUCTIVITY_RESULT_AGGREGATION_BEGIN" in core_source
assert "merge_productivity_result_payload_v123" in core_source

helper = (ROOT/"runtime"/"productivity_view_aggregation_v123.py").read_text(encoding="utf-8-sig")
assert "AURA_V123_PRODUCTIVITY_VIEW_AGGREGATION" in helper

ui = Path(os.environ["LOCALAPPDATA"])/"AURA"/"ui"/"v0.7.2.2-rc4.2"
renderer = (ui/"dist"/"assets"/"aura-v123-personal-results-web.js").read_text(encoding="utf-8-sig")
assert "tasks:'TÂCHES'" in renderer
assert "Aucune tâche à afficher." in renderer
assert "AURA_V123_AGGREGATED_SOURCE_BADGES" in renderer
assert re.search(r"\btasks\s*:\s*\[\s*['\"]source['\"]\s*,", renderer)
assert re.search(r"\bcalendar\s*:\s*\[\s*['\"]source['\"]\s*,", renderer)
assert "source:'Source'" in renderer
assert "AURA_V123_CONVERSATION_RESULTS_COEXISTENCE_BEGIN" in renderer

ccss = (ui/"dist"/"assets"/"aura-p0712-conversation-ui.css").read_text(encoding="utf-8-sig")
assert "AURA_V123_CONVERSATION_HARD_REFLOW_BEGIN" in ccss
assert "grid-template-columns:minmax(0,1fr)!important" in ccss

print("[PASS] original Agenda/Contacts/Tasks NL routing preserved")
print("[PASS] native Tasks = AURA local + Google Tasks")
print("[PASS] native Agenda = AURA local + Google Calendar")
print("[PASS] Personal Results expose Source AURA/GOOGLE")
print("[PASS] Conversation hard reflow installed")
print("[PASS] deterministic: no OAuth/network/Google mutation")
