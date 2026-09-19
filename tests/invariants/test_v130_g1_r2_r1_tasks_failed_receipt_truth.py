from __future__ import annotations
from pathlib import Path
import ast
import sys

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2"
DIST = UI / "dist"

from runtime import personal_result_presenter_v123 as presenter

src = (ROOT / "runtime" / "personal_result_presenter_v123.py").read_text(
    encoding="utf-8-sig", errors="replace"
)
tree = ast.parse(src)
funcs = {
    node.name: ast.get_source_segment(src, node) or ""
    for node in ast.walk(tree)
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
assert "AURA_V130_TASKS_FAILED_RECEIPT_SUMMARY_TRUTH_BEGIN" in funcs["summarize_personal_result_for_tts_v123"]
assert "AURA_V130_TASKS_FAILED_RECEIPT_SUMMARY_TRUTH_BEGIN" not in funcs["build_personal_result_payload_v123"]

bad1 = {
    "title": "Action non executee : Afficher les tâches Google. Statut : failed.",
    "status": "failed",
    "source": "GOOGLE",
}
bad2 = {
    "title": "Recu d'action : rcp_demo - statut failed",
    "status": "failed",
    "source": "GOOGLE",
}
good = {
    "title": "Préparer la réunion",
    "status": "needsAction",
    "source": "GOOGLE",
}
assert presenter._is_failed_task_receipt_v130(bad1)
assert presenter._is_failed_task_receipt_v130(bad2)
assert not presenter._is_failed_task_receipt_v130(good)

class Reply:
    provider_id = "tasks.provider"
    capability_id = "tasks.list"
    status = "succeeded"
    text = ""
    items = [good]

class Request:
    provider_id = "tasks.provider"
    capability_id = "tasks.list"

built = presenter.build_personal_result_payload_v123(Reply(), Request())
assert isinstance(built, dict)
assert built.get("kind") == "tasks"

failed_only = {
    "kind": "tasks",
    "count": 4,
    "items": [{"title": "local", "source": "AURA"}] * 4,
    "source": "failed_receipt_filtered",
    "source_breakdown": {"google": 0, "aura_local": 4},
    "aggregated": True,
}
msg = presenter.summarize_personal_result_for_tts_v123(
    failed_only,
    "Action non executee : Afficher les tâches Google. Statut : failed.",
)
low = msg.casefold()
assert "google tasks" in low
assert ("échoué" in low) or ("echoue" in low)
assert "2 tâches google" not in low
assert "4" in msg

mixed = {
    "kind": "tasks",
    "count": 3,
    "items": [],
    "source": "reply_object",
    "source_breakdown": {"google": 2, "aura_local": 1},
    "aggregated": True,
}
msg2 = presenter.summarize_personal_result_for_tts_v123(mixed, "")
assert "2" in msg2 and "Google" in msg2
assert "1" in msg2 and "AURA" in msg2

js_paths = [
    UI / "src" / "aura-v123-personal-results-web.js",
    UI / "src" / "assets" / "aura-v123-personal-results-web.js",
    DIST / "assets" / "aura-v123-personal-results-web.js",
]
texts = [p.read_text(encoding="utf-8-sig", errors="replace") for p in js_paths]
assert len(set(texts)) == 1
js = texts[0]
assert "AURA_V130_TASKS_FAILED_RECEIPT_PERSONAL_RESULTS_GUARD" in js
assert "sanitizeTasksReceiptPayloadV130" in js
assert "payload=sanitizeTasksReceiptPayloadV130(payload);" in js

native = (DIST / "assets" / "aura-v123-visible-productivity-rebind.js").read_text(
    encoding="utf-8-sig", errors="replace"
)
assert "Réponse Google Tasks invalide — reçu d’action ignoré" in native

idx = (DIST / "index.html").read_text(encoding="utf-8-sig", errors="replace")
assert "v1.2.3 INTERACTIVE" in idx
assert "v1.2.2 INTERACTIVE" not in idx

print("[PASS] v1.3.0 G1 R2 R1 semantic summary placement + Tasks truth")
