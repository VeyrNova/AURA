from __future__ import annotations
import ast, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
SHELL = UI / "tools" / "shell_host.py"

text = SHELL.read_text(encoding="utf-8-sig", errors="replace")
tree = ast.parse(text)

allowed = None
for node in tree.body:
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "ALLOWED":
                allowed = ast.literal_eval(node.value)

assert isinstance(allowed, (set, frozenset))
assert "personal_result" in allowed
assert "aura_message" in allowed
assert "command_result" in allowed
assert text.count("AURA_V123_REAL_HOST_WEB_BRIDGE_BEGIN") == 1
assert text.count("AURA_V123_AWAITABLE_HUB_COMPLETION_BEGIN") == 1
assert text.count("AURA_V123_ESCAPE_WATCHDOG_BEGIN") == 1
assert text.count("new EventSource") == 0
assert "--start-fullscreen" in text

print("[PASS] shell EventHub ALLOWED includes personal_result")
