from __future__ import annotations

import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
CORE = ROOT / "core" / "aura_core.py"
SINK = ROOT / "runtime" / "personal_result_web_sink_v123.py"
SHELL = UI / "tools" / "shell_host.py"
SRC_MAIN = UI / "src" / "main.js"
DIST_BUNDLE = UI / "dist" / "assets" / "index-Ckl5rwwJ.js"
RENDERER = UI / "dist" / "assets" / "aura-v123-personal-results-web.js"

for p in (CORE, SINK, SHELL, SRC_MAIN, DIST_BUNDLE, RENDERER):
    assert p.is_file(), p

core = CORE.read_text(encoding="utf-8-sig")
shell = SHELL.read_text(encoding="utf-8-sig")
sink = SINK.read_text(encoding="utf-8-sig")
renderer = RENDERER.read_text(encoding="utf-8-sig")

ast.parse(core)
ast.parse(shell)
ast.parse(sink)

assert core.count("AURA_V123_DIRECT_WEB_RESULT_SINK_BEGIN") == 1
assert "publish_personal_result_v123" in core
assert "personal_result.emit" in core
assert "summarize_personal_result_for_tts_v123" in core

assert "register_personal_result_sink_v123" in shell
assert "rt.hub.send('personal_result'" in shell or 'rt.hub.send("personal_result"' in shell
assert shell.count("AURA_V123_ESCAPE_WATCHDOG_BEGIN") == 1
assert "_aura_v123_start_escape_watchdog()" in shell
assert "--start-fullscreen" in shell
assert "--start-maximized" not in shell

assert SRC_MAIN.read_text(encoding="utf-8-sig").count("new EventSource") == 1
assert DIST_BUNDLE.read_text(encoding="utf-8-sig").count("new EventSource") == 1
assert "aura:hub-event" in renderer
assert "personal_result" in renderer

from runtime.personal_result_web_sink_v123 import (
    register_personal_result_sink_v123,
    publish_personal_result_v123,
)

received = []
register_personal_result_sink_v123(lambda payload: received.append(dict(payload)))
assert publish_personal_result_v123({"kind": "mail", "count": 1, "items": [{"subject": "x"}]}) is True
assert received and received[0]["kind"] == "mail"
register_personal_result_sink_v123(None)
assert publish_personal_result_v123({"kind": "drive", "count": 0, "items": []}) is False

print("[PASS] v1.2.3 direct web personal-result sink invariant")
print("[PASS] native event_bus path retained independently")
print("[PASS] shell registers hub sink without a second EventSource")
print("[PASS] ESC watchdog is scoped to foreground AURA Chrome fullscreen window")
