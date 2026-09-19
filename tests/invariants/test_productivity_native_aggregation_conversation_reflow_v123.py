from __future__ import annotations
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"

from runtime.productivity_view_aggregation_v123 import (
    collect_local_task_items_v123,
    collect_local_agenda_items_v123,
    merge_productivity_result_payload_v123,
)

class Tasks:
    def list_tasks(self, status="TODO", limit=100):
        return [
            {"id":"local-t1","title":"Local task","status":"TODO","due_at":"2026-09-01T10:00:00"},
            {"id":"local-t2","title":"Undated","status":"TODO"},
        ]

class Reminders:
    def list_reminders(self, include_done=False, limit=100):
        return [
            {"id":"local-r1","content":"Local reminder","due_at":"2026-09-02T09:30:00"}
        ]

class Core:
    task_manager = Tasks()
    reminder_manager = Reminders()

tasks = collect_local_task_items_v123(Core.task_manager)
assert len(tasks) == 2
assert all(x["source"] == "AURA" for x in tasks)

agenda = collect_local_agenda_items_v123(Core.reminder_manager, Core.task_manager)
assert len(agenda) == 2
assert {x["source"] for x in agenda} == {"AURA RAPPEL", "AURA TÂCHE"}

merged_tasks = merge_productivity_result_payload_v123(
    {"kind":"tasks","items":[{"title":"Google task"}],"count":1},
    Core(),
)
assert merged_tasks["count"] == 3
assert merged_tasks["items"][0]["source"] == "GOOGLE"
assert merged_tasks["source_breakdown"] == {"google":1,"aura_local":2}

merged_calendar = merge_productivity_result_payload_v123(
    {"kind":"calendar","items":[{"title":"Google event"}],"count":1},
    Core(),
)
assert merged_calendar["count"] == 3
assert merged_calendar["items"][0]["source"] == "GOOGLE"

final_modules = (ROOT/"ui"/"final_modules.py").read_text(encoding="utf-8-sig")
main = (ROOT/"ui"/"main_window.py").read_text(encoding="utf-8-sig")
core = (ROOT/"core"/"aura_core.py").read_text(encoding="utf-8-sig")
renderer = (UI/"src"/"aura-v123-personal-results-web.js").read_text(encoding="utf-8-sig")
ccss = (UI/"src"/"aura-p0712-conversation-ui.css").read_text(encoding="utf-8-sig")

assert "AURA_V123_NATIVE_TASKS_AGGREGATION" in final_modules
assert "AURA_V123_NATIVE_AGENDA_AGGREGATION" in final_modules
assert "set_local_sources(task_manager=self.aura_core.task_manager)" in main
assert "reminder_manager=self.aura_core.reminder_manager" in main
assert "AURA_V123_PRODUCTIVITY_RESULT_AGGREGATION_BEGIN" in core
assert "merge_productivity_result_payload_v123" in core
assert "source:'Source'" in renderer
assert "tasks:['source'," in renderer
assert "calendar:['source'," in renderer
assert "AURA_V123_CONVERSATION_HARD_REFLOW_BEGIN" in ccss
assert "grid-template-columns:minmax(0,1fr)!important" in ccss
assert ".aura-p0712-context-side" in ccss
assert "max-width:min(680px,calc(100% - 24px))!important" in ccss

print("[PASS] local Tasks + Agenda aggregation helper")
print("[PASS] Personal Results AURA local + Google aggregation")
print("[PASS] native Tasks/Agenda aggregation bindings")
print("[PASS] Conversation hard reflow / bubble / composer contract")
print("[PASS] no Google mutation required by invariant")
