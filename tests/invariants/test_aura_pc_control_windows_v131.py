from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

from runtime.aura_pc_control_contract_v131 import PcControlContractError
from runtime.aura_pc_control_windows_v131 import (
    PcControlExecutionDenied,
    WindowSnapshot,
    ProcessSnapshot,
    WindowsPcControlAdapter,
    capability_snapshot,
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class FakeBackend:
    def __init__(self):
        self.window = WindowSnapshot(
            hwnd=1234, pid=4321, title="Synthetic Window", visible=True, foreground=False
        )
        self.focused = False
        self.minimized = False
        self.maximized = False

    def discover_windows(self, limit=256):
        return [self.window]

    def discover_processes(self, limit=512):
        return [ProcessSnapshot(pid=4321, image_name="synthetic.exe", parent_pid=100)]

    def foreground_window(self):
        return self.window

    def focus_window(self, hwnd):
        assert hwnd == 1234
        self.focused = True
        return True

    def minimize_window(self, hwnd):
        assert hwnd == 1234
        self.minimized = True
        return True

    def maximize_window(self, hwnd):
        assert hwnd == 1234
        self.maximized = True
        return True


roadmap_sha = sha(ROADMAP)

snap = capability_snapshot()
assert snap["shell_execution"] is False
assert snap["powershell_execution"] is False
assert snap["arbitrary_executable_execution"] is False
assert snap["receipt_hook_required_for_mutation"] is True
assert snap["close_window_bound"] is False
assert snap["terminate_process_bound"] is False
assert snap["router_bound"] is True  # W131-3C router is now intentionally bound

fake = FakeBackend()
adapter = WindowsPcControlAdapter(fake)

# Read-only discovery works without a receipt hook.
assert adapter.execute("DISCOVER_WINDOWS")["status"] == "SUCCEEDED"
assert adapter.execute("DISCOVER_PROCESSES")["status"] == "SUCCEEDED"
assert adapter.execute("GET_FOREGROUND_WINDOW")["status"] == "SUCCEEDED"

# Mutating actions fail closed until the existing receipt layer is bound.
try:
    adapter.execute("FOCUS_WINDOW", {"hwnd": 1234, "title": "Synthetic Window"})
except PcControlExecutionDenied:
    pass
else:
    raise AssertionError("mutation executed without receipt hook")
assert fake.focused is False

events = []
def receipt_hook(phase, payload):
    events.append((phase, dict(payload)))

bound = WindowsPcControlAdapter(fake, receipt_hook=receipt_hook)
for action in ("FOCUS_WINDOW", "MINIMIZE_WINDOW", "MAXIMIZE_WINDOW"):
    result = bound.execute(action, {"hwnd": 1234, "title": "Synthetic Window"})
    assert result["status"] == "SUCCEEDED"

assert fake.focused and fake.minimized and fake.maximized
assert [x[0] for x in events] == [
    "AUTHORIZED", "COMPLETED",
    "AUTHORIZED", "COMPLETED",
    "AUTHORIZED", "COMPLETED",
]

# Stale or changed target evidence is denied before mutation.
try:
    bound.execute("FOCUS_WINDOW", {"hwnd": 1234, "title": "Wrong Title"})
except Exception:
    pass
else:
    raise AssertionError("changed window title accepted")

# Raw command fields are still denied by W131-1 contract.
try:
    bound.execute(
        "FOCUS_WINDOW",
        {"hwnd": 1234, "title": "Synthetic Window", "command": "whoami"},
    )
except PcControlContractError:
    pass
else:
    raise AssertionError("raw command input accepted")

# On the real Windows host, read-only discovery must work without mutating anything.
if os.name == "nt":
    live = WindowsPcControlAdapter()
    windows = live.execute("DISCOVER_WINDOWS")
    processes = live.execute("DISCOVER_PROCESSES")
    foreground = live.execute("GET_FOREGROUND_WINDOW")
    assert windows["status"] == "SUCCEEDED"
    assert processes["status"] == "SUCCEEDED"
    assert foreground["status"] == "SUCCEEDED"
    assert isinstance(windows["data"], list)
    assert isinstance(processes["data"], list)
    print(f"[PASS] live Windows discovery windows={len(windows['data'])} processes={len(processes['data'])}")
else:
    print("[SKIP] live Windows discovery: non-Windows host")

assert sha(ROADMAP) == roadmap_sha

print("[PASS] W131-2 fixed Win32 backend has no shell/PowerShell execution")
print("[PASS] read-only Windows/process discovery contract")
print("[PASS] focus/minimize/maximize are bounded to exact hwnd + title")
print("[PASS] mutation denied until an existing AURA receipt hook is bound")
print("[PASS] close-window and terminate-process remain unbound")
print("[PASS] live Roadmap unchanged")
