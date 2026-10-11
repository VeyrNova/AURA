from dataclasses import asdict, dataclass
import os
from .models import SystemActionType

@dataclass(frozen=True)
class WindowSnapshot:
    hwnd: int; pid: int; title: str; visible: bool; foreground: bool = False

@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int; image_name: str; parent_pid: int = 0

class _Win32Backend:
    def __init__(self):
        import ctypes
        from ctypes import wintypes
        self.ctypes, self.w = ctypes, wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.TH32CS_SNAPPROCESS = 0x00000002
        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [("dwSize", wintypes.DWORD), ("cntUsage", wintypes.DWORD),
                        ("th32ProcessID", wintypes.DWORD), ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
                        ("th32ModuleID", wintypes.DWORD), ("cntThreads", wintypes.DWORD),
                        ("th32ParentProcessID", wintypes.DWORD), ("pcPriClassBase", ctypes.c_long),
                        ("dwFlags", wintypes.DWORD), ("szExeFile", wintypes.WCHAR * 260)]
        self.PROCESSENTRY32W = PROCESSENTRY32W
    def _snap(self, hwnd, fg=0):
        if not self.user32.IsWindow(hwnd) or not self.user32.IsWindowVisible(hwnd): return None
        n=self.user32.GetWindowTextLengthW(hwnd)
        if n <= 0: return None
        b=self.ctypes.create_unicode_buffer(n+1); self.user32.GetWindowTextW(hwnd,b,n+1)
        pid=self.w.DWORD(0); self.user32.GetWindowThreadProcessId(hwnd,self.ctypes.byref(pid))
        return WindowSnapshot(int(hwnd),int(pid.value),str(b.value),True,int(hwnd)==int(fg))
    def discover_windows(self):
        out=[]; fg=int(self.user32.GetForegroundWindow() or 0); cbtype=self.ctypes.WINFUNCTYPE(self.w.BOOL,self.w.HWND,self.w.LPARAM)
        @cbtype
        def cb(hwnd,_):
            s=self._snap(hwnd,fg)
            if s: out.append(s)
            return True
        self.user32.EnumWindows(cb,0); return out
    def discover_processes(self):
        entry = self.PROCESSENTRY32W(); entry.dwSize = self.ctypes.sizeof(entry)
        snap = self.kernel32.CreateToolhelp32Snapshot(self.TH32CS_SNAPPROCESS, 0)
        invalid = self.w.HANDLE(-1).value
        if snap in (0, invalid): return []
        out = []
        try:
            first = self.kernel32.Process32FirstW
            nxt = self.kernel32.Process32NextW
            if first(snap, self.ctypes.byref(entry)):
                while True:
                    out.append(ProcessSnapshot(int(entry.th32ProcessID), str(entry.szExeFile), int(entry.th32ParentProcessID)))
                    if not nxt(snap, self.ctypes.byref(entry)): break
        finally:
            self.kernel32.CloseHandle(snap)
        return out
    def foreground_window(self): return self._snap(self.user32.GetForegroundWindow(),self.user32.GetForegroundWindow())
    def focus_window(self,hwnd): return bool(self.user32.SetForegroundWindow(hwnd))
    def minimize_window(self,hwnd): return bool(self.user32.ShowWindow(hwnd,6))
    def maximize_window(self,hwnd): return bool(self.user32.ShowWindow(hwnd,3))

class WindowsSystemAdapter:
    """Typed Win32 adapter; never accepts shell text or commands."""
    def __init__(self, backend=None):
        self.backend = backend
    def execute(self, request):
        backend = self.backend or (_Win32Backend() if os.name == "nt" else None)
        if backend is None:
            return {"status": "UNAVAILABLE", "data": []}
        a, t = request.action, request.target
        if a in {SystemActionType.FOCUS_WINDOW, SystemActionType.MINIMIZE_WINDOW, SystemActionType.MAXIMIZE_WINDOW} and t.get("pid"):
            matches = [x for x in backend.discover_windows() if int(getattr(x, "hwnd", 0)) == int(t["hwnd"])]
            if not matches or int(matches[0].pid) != int(t["pid"]):
                return {"status": "NOT_FOUND", "data": None}
        if a is SystemActionType.DISCOVER_WINDOWS: data = backend.discover_windows()
        elif a is SystemActionType.DISCOVER_PROCESSES: data = backend.discover_processes()
        elif a is SystemActionType.GET_FOREGROUND_WINDOW: data = backend.foreground_window()
        elif a is SystemActionType.FOCUS_WINDOW: data = backend.focus_window(int(t["hwnd"]))
        elif a is SystemActionType.MINIMIZE_WINDOW: data = backend.minimize_window(int(t["hwnd"]))
        elif a is SystemActionType.MAXIMIZE_WINDOW: data = backend.maximize_window(int(t["hwnd"]))
        else: return {"status": "UNAVAILABLE", "data": None}
        if a in {SystemActionType.FOCUS_WINDOW, SystemActionType.MINIMIZE_WINDOW, SystemActionType.MAXIMIZE_WINDOW} and data is False:
            return {"status": "NOT_FOUND", "data": None}
        return {"status": "SUCCESS", "data": [asdict(x) for x in data] if isinstance(data, list) else (asdict(data) if hasattr(data, "__dataclass_fields__") else data)}
