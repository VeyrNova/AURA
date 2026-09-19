from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
main = root / "ui" / "main_window.py"
policy = root / "ui" / "display_policy.py"
mt = main.read_text(encoding="utf-8") if main.exists() else ""
pt = policy.read_text(encoding="utf-8") if policy.exists() else ""
checks = {
    "main_window present": main.exists(),
    "display policy present": policy.exists(),
    "ambient policy import": "from ui.display_policy import is_explicit_conversation_ui_request" in mt,
    "ambient home route": "Home display policy=ambient conversation_autoshow=False" in mt,
    "explicit conversation route": "Home display policy=conversation explicit request" in mt,
    "old unconditional home switch removed": 'def _on_home_message(self, text: str) -> None:\n        self._switch_page("conversation")' not in mt,
    "policy handles explicit conversation": "is_explicit_conversation_ui_request" in pt and "conversation|chat" in pt,
    "visual local routes retained": 'visual_local = {"LIST_NOTES", "SEARCH_NOTE", "LIST_TASKS", "LIST_REMINDERS", "LIST_MEMORIES", "SEARCH_MEMORY"}' in mt,
}
failed=[]
for name, ok in checks.items():
    print(("PASS" if ok else "FAIL") + " - " + name)
    if not ok: failed.append(name)
print(f"\n{len(checks)-len(failed)}/{len(checks)} checks PASS")
sys.exit(1 if failed else 0)
