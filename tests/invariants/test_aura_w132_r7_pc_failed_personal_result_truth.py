from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

reply = SimpleNamespace(
    text="L'action Windows minimisation a echoue.",
    status="failed",
    capability_id="pc.minimize_window",
    receipt_id="rcp_w132_r7_test",
    payload=None,
)
request = SimpleNamespace(
    provider_id="pc-control.windows",
    capability_id="pc.minimize_window",
)

payload = build_personal_result_payload_v123(reply, request)
assert payload["source"] == "WINDOWS", payload
assert payload["sources"] == ["WINDOWS"], payload
assert payload["status"] == "failed", payload
assert payload["receipt_id"] == "rcp_w132_r7_test", payload
assert payload["fallback_text"] == reply.text, payload
assert payload["items"] == [], payload
assert payload["count"] == 0, payload

ui = Path.home() / "AppData" / "Local" / "AURA" / "ui" / "v0.7.2.2-rc4.2"
mirrors = [
    ui / "src" / "aura-v123-visible-productivity-rebind.js",
    ui / "src" / "assets" / "aura-v123-visible-productivity-rebind.js",
    ui / "dist" / "assets" / "aura-v123-visible-productivity-rebind.js",
]
for p in mirrors:
    text = p.read_text(encoding="utf-8")
    assert text.count("AURA_W132_R7_PC_FAILURE_META_TRUTH") == 1, p
    assert text.count("AURA_W132_R7_PC_FAILURE_BODY_TRUTH") == 1, p
    assert "const isFailed=isWindows&&(status==='failed'||status==='error');" in text, p
    assert "fallbackText||'Action Windows \\u00e9chou\\u00e9e.'" in text, p
    assert "Receipt ${receiptId}" in text, p

print("[PASS] failed PC presenter preserves WINDOWS/status/receipt/fallback text")
print("[PASS] failed PC result remains count=0/items=[]; no fake success item")
print("[PASS] recovery UI renders explicit WINDOWS failure state")
print("[PASS] receipt id is visible in failure state")
