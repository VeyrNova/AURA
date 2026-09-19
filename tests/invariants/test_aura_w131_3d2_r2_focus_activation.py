from __future__ import annotations
import hashlib, sys
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.aura_pc_control_windows_v131 import WindowsNativeBackend

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class FakeKernel32:
    def GetCurrentThreadId(self): return 101

class FakeUser32:
    def __init__(self):
        self.foreground = 9999
        self.calls = []
    def IsWindow(self, hwnd): return int(hwnd) == 7001
    def IsIconic(self, hwnd): self.calls.append(("IsIconic", int(hwnd))); return True
    def ShowWindow(self, hwnd, cmd): self.calls.append(("ShowWindow", int(hwnd), int(cmd))); return True
    def GetForegroundWindow(self): return self.foreground
    def GetWindowThreadProcessId(self, hwnd, pid_ptr):
        hwnd = int(hwnd)
        return 303 if hwnd == 7001 else (202 if hwnd == 9999 else 0)
    def AttachThreadInput(self, src, dst, attach):
        self.calls.append(("AttachThreadInput", int(src), int(dst), bool(attach))); return True
    def BringWindowToTop(self, hwnd): self.calls.append(("BringWindowToTop", int(hwnd))); return True
    def SetForegroundWindow(self, hwnd):
        self.calls.append(("SetForegroundWindow", int(hwnd))); self.foreground = int(hwnd); return False
    def SetFocus(self, hwnd): self.calls.append(("SetFocus", int(hwnd))); return int(hwnd)

roadmap_sha = sha(ROADMAP)
backend = object.__new__(WindowsNativeBackend)
backend.user32 = FakeUser32(); backend.kernel32 = FakeKernel32()
assert backend.focus_window(7001) is True
calls = backend.user32.calls
assert ("IsIconic",7001) in calls
assert ("ShowWindow",7001,9) in calls
assert ("BringWindowToTop",7001) in calls
assert ("SetForegroundWindow",7001) in calls
assert ("SetFocus",7001) in calls
attached=[c for c in calls if c[0]=="AttachThreadInput" and c[3] is True]
detached=[c for c in calls if c[0]=="AttachThreadInput" and c[3] is False]
assert attached and detached and len(attached)==len(detached)
assert backend.focus_window(9998) is False
assert sha(ROADMAP) == roadmap_sha
print("[PASS] W131-3D2 R2 bounded focus activation")
print("[PASS] final foreground HWND verification")
print("[PASS] input-thread bridge detach symmetry")
print("[PASS] invalid HWND denied")
print("[PASS] live Roadmap unchanged")
