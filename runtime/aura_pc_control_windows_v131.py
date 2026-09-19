from __future__ import annotations

import ctypes
import os
from dataclasses import asdict, dataclass
from typing import Any, Callable, Mapping, Protocol

from runtime.aura_pc_control_contract_v131 import (
    PcControlContractError,
    normalize_request,
    plan_request,
)

SCHEMA = "aura.pc-control.windows-adapter.v131"
RESULT_SCHEMA = "aura.pc-control.execution-result.v131"

SUPPORTED_ACTIONS = frozenset({
    "DISCOVER_WINDOWS",
    "DISCOVER_PROCESSES",
    "GET_FOREGROUND_WINDOW",
    "FOCUS_WINDOW",
    "MINIMIZE_WINDOW",
    "MAXIMIZE_WINDOW",
})

MUTATING_ACTIONS = frozenset({
    "FOCUS_WINDOW",
    "MINIMIZE_WINDOW",
    "MAXIMIZE_WINDOW",
})


class PcControlPlatformUnavailable(RuntimeError):
    pass


class PcControlExecutionDenied(RuntimeError):
    pass


class PcControlTargetChanged(RuntimeError):
    pass


ReceiptHook = Callable[[str, Mapping[str, Any]], None]


@dataclass(frozen=True)
class WindowSnapshot:
    hwnd: int
    pid: int
    title: str
    visible: bool
    foreground: bool = False


@dataclass(frozen=True)
class ProcessSnapshot:
    pid: int
    image_name: str
    parent_pid: int = 0


class PcControlBackend(Protocol):
    def discover_windows(self, limit: int = 256) -> list[WindowSnapshot]: ...
    def discover_processes(self, limit: int = 512) -> list[ProcessSnapshot]: ...
    def foreground_window(self) -> WindowSnapshot | None: ...
    def focus_window(self, hwnd: int) -> bool: ...
    def minimize_window(self, hwnd: int) -> bool: ...
    def maximize_window(self, hwnd: int) -> bool: ...


class WindowsNativeBackend:
    """
    Bounded Windows-native backend.

    No shell strings, no PowerShell, no arbitrary executable invocation.
    Only fixed Win32 APIs are used.
    """

    SW_MINIMIZE = 6
    SW_MAXIMIZE = 3

    def __init__(self) -> None:
        if os.name != "nt":
            raise PcControlPlatformUnavailable("Windows PC control is available only on Windows")

        from ctypes import wintypes

        self.wintypes = wintypes
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        self.WNDENUMPROC = ctypes.WINFUNCTYPE(
            wintypes.BOOL, wintypes.HWND, wintypes.LPARAM
        )

        self.user32.EnumWindows.argtypes = [self.WNDENUMPROC, wintypes.LPARAM]
        self.user32.EnumWindows.restype = wintypes.BOOL
        self.user32.IsWindow.argtypes = [wintypes.HWND]
        self.user32.IsWindow.restype = wintypes.BOOL
        self.user32.IsWindowVisible.argtypes = [wintypes.HWND]
        self.user32.IsWindowVisible.restype = wintypes.BOOL
        self.user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        self.user32.GetWindowTextLengthW.restype = ctypes.c_int
        self.user32.GetWindowTextW.argtypes = [
            wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
        ]
        self.user32.GetWindowTextW.restype = ctypes.c_int
        self.user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        ]
        self.user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        self.user32.GetForegroundWindow.argtypes = []
        self.user32.GetForegroundWindow.restype = wintypes.HWND
        self.user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        self.user32.SetForegroundWindow.restype = wintypes.BOOL
        self.user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        self.user32.ShowWindow.restype = wintypes.BOOL

        ulong_ptr = getattr(wintypes, "ULONG_PTR", wintypes.WPARAM)

        class PROCESSENTRY32W(ctypes.Structure):
            _fields_ = [
                ("dwSize", wintypes.DWORD),
                ("cntUsage", wintypes.DWORD),
                ("th32ProcessID", wintypes.DWORD),
                ("th32DefaultHeapID", ulong_ptr),
                ("th32ModuleID", wintypes.DWORD),
                ("cntThreads", wintypes.DWORD),
                ("th32ParentProcessID", wintypes.DWORD),
                ("pcPriClassBase", wintypes.LONG),
                ("dwFlags", wintypes.DWORD),
                ("szExeFile", wintypes.WCHAR * 260),
            ]

        self.PROCESSENTRY32W = PROCESSENTRY32W
        self.kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
        self.kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
        self.kernel32.Process32FirstW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
        ]
        self.kernel32.Process32FirstW.restype = wintypes.BOOL
        self.kernel32.Process32NextW.argtypes = [
            wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)
        ]
        self.kernel32.Process32NextW.restype = wintypes.BOOL
        self.kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel32.CloseHandle.restype = wintypes.BOOL

    @staticmethod
    def _positive_limit(limit: int, maximum: int) -> int:
        try:
            value = int(limit)
        except Exception:
            value = maximum
        return max(1, min(value, maximum))

    def _window_snapshot(self, hwnd: int, *, foreground_hwnd: int = 0) -> WindowSnapshot | None:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return None
        length = int(self.user32.GetWindowTextLengthW(hwnd))
        if length <= 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        self.user32.GetWindowTextW(hwnd, buf, length + 1)
        title = str(buf.value or "").strip()
        if not title:
            return None
        pid = self.wintypes.DWORD(0)
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return WindowSnapshot(
            hwnd=hwnd,
            pid=int(pid.value),
            title=title,
            visible=bool(self.user32.IsWindowVisible(hwnd)),
            foreground=hwnd == int(foreground_hwnd or 0),
        )

    def discover_windows(self, limit: int = 256) -> list[WindowSnapshot]:
        max_items = self._positive_limit(limit, 1024)
        foreground = int(self.user32.GetForegroundWindow() or 0)
        out: list[WindowSnapshot] = []

        @self.WNDENUMPROC
        def callback(hwnd, _lparam):
            if len(out) >= max_items:
                return False
            if not self.user32.IsWindowVisible(hwnd):
                return True
            snap = self._window_snapshot(int(hwnd), foreground_hwnd=foreground)
            if snap is not None:
                out.append(snap)
            return True

        self.user32.EnumWindows(callback, 0)
        return out

    def discover_processes(self, limit: int = 512) -> list[ProcessSnapshot]:
        max_items = self._positive_limit(limit, 4096)
        TH32CS_SNAPPROCESS = 0x00000002
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        handle = self.kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
        if not handle or int(handle) == int(INVALID_HANDLE_VALUE):
            raise OSError(ctypes.get_last_error(), "CreateToolhelp32Snapshot failed")

        out: list[ProcessSnapshot] = []
        try:
            entry = self.PROCESSENTRY32W()
            entry.dwSize = ctypes.sizeof(self.PROCESSENTRY32W)
            ok = self.kernel32.Process32FirstW(handle, ctypes.byref(entry))
            while ok and len(out) < max_items:
                out.append(
                    ProcessSnapshot(
                        pid=int(entry.th32ProcessID),
                        image_name=str(entry.szExeFile or ""),
                        parent_pid=int(entry.th32ParentProcessID),
                    )
                )
                ok = self.kernel32.Process32NextW(handle, ctypes.byref(entry))
        finally:
            self.kernel32.CloseHandle(handle)
        return out

    def foreground_window(self) -> WindowSnapshot | None:
        hwnd = int(self.user32.GetForegroundWindow() or 0)
        if hwnd <= 0:
            return None
        return self._window_snapshot(hwnd, foreground_hwnd=hwnd)

    def focus_window(self, hwnd: int) -> bool:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return False
        return bool(self.user32.SetForegroundWindow(hwnd))

    def minimize_window(self, hwnd: int) -> bool:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return False
        self.user32.ShowWindow(hwnd, self.SW_MINIMIZE)
        return True

    def maximize_window(self, hwnd: int) -> bool:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return False
        self.user32.ShowWindow(hwnd, self.SW_MAXIMIZE)
        return True


    # AURA W132-R8 - bounded native window-state recovery
    def window_state(self, hwnd: int) -> dict[str, Any] | None:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return None
        try:
            minimized = bool(self.user32.IsIconic(hwnd))
        except Exception:
            minimized = False
        try:
            maximized = bool(self.user32.IsZoomed(hwnd))
        except Exception:
            maximized = False
        show_state = "minimized" if minimized else ("maximized" if maximized else "normal")
        try:
            foreground = int(self.user32.GetForegroundWindow() or 0) == hwnd
        except Exception:
            foreground = False
        return {
            "show_state": show_state,
            "foreground": bool(foreground),
        }

    def restore_window_state(self, hwnd: int, state: Mapping[str, Any]) -> bool:
        hwnd = int(hwnd)
        if hwnd <= 0 or not self.user32.IsWindow(hwnd):
            return False
        show_state = str((state or {}).get("show_state") or "").strip().lower()
        if show_state == "minimized":
            self.user32.ShowWindow(hwnd, self.SW_MINIMIZE)
        elif show_state == "maximized":
            self.user32.ShowWindow(hwnd, self.SW_MAXIMIZE)
        elif show_state == "normal":
            self.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        else:
            return False
        return True

class WindowsPcControlAdapter:
    def __init__(
        self,
        backend: PcControlBackend | None = None,
        *,
        receipt_hook: ReceiptHook | None = None,
        external_receipt_managed: bool = False,
    ) -> None:
        self.backend = backend if backend is not None else WindowsNativeBackend()
        self.receipt_hook = receipt_hook
        self.external_receipt_managed = bool(external_receipt_managed)

    def _find_window(self, hwnd: int) -> WindowSnapshot:
        for snap in self.backend.discover_windows(limit=1024):
            if int(snap.hwnd) == int(hwnd):
                return snap
        raise PcControlTargetChanged(f"window no longer exists: hwnd={hwnd}")

    def _validate_window_target(self, params: Mapping[str, Any]) -> WindowSnapshot:
        snap = self._find_window(int(params["hwnd"]))
        expected = str(params["title"])
        if snap.title != expected:
            raise PcControlTargetChanged(
                f"window title changed for hwnd={snap.hwnd}: "
                f"expected {expected!r}, found {snap.title!r}"
            )
        return snap

    @staticmethod
    def _payload(obj: Any) -> Any:
        if obj is None:
            return None
        if hasattr(obj, "__dataclass_fields__"):
            return asdict(obj)
        if isinstance(obj, list):
            return [WindowsPcControlAdapter._payload(x) for x in obj]
        return obj

    # AURA W132-R8 - capture exact reversible preimage
    def _capture_recovery_state(
        self,
        before: WindowSnapshot,
        rollback_of_request_id: str,
    ) -> dict[str, Any]:
        state_fn = getattr(self.backend, "window_state", None)
        restore_fn = getattr(self.backend, "restore_window_state", None)
        if not callable(state_fn) or not callable(restore_fn):
            return {
                "schema": "aura.pc-control.window-recovery.v1",
                "available": False,
                "rollback_of_request_id": str(rollback_of_request_id or ""),
            }

        state = state_fn(before.hwnd)
        if not isinstance(state, Mapping):
            return {
                "schema": "aura.pc-control.window-recovery.v1",
                "available": False,
                "rollback_of_request_id": str(rollback_of_request_id or ""),
            }

        show_state = str(state.get("show_state") or "").strip().lower()
        if show_state not in {"normal", "minimized", "maximized"}:
            return {
                "schema": "aura.pc-control.window-recovery.v1",
                "available": False,
                "rollback_of_request_id": str(rollback_of_request_id or ""),
            }

        foreground_before = None
        try:
            fg = self.backend.foreground_window()
        except Exception:
            fg = None
        if fg is not None:
            foreground_before = {
                "hwnd": int(fg.hwnd),
                "title": str(fg.title),
            }

        return {
            "schema": "aura.pc-control.window-recovery.v1",
            "available": True,
            "rollback_of_request_id": str(rollback_of_request_id or ""),
            "target": {
                "hwnd": int(before.hwnd),
                "title": str(before.title),
                "show_state": show_state,
            },
            "foreground_before": foreground_before,
        }

    def restore_window_state(
        self,
        recovery: Mapping[str, Any],
        *,
        origin: str = "local-core",
    ) -> dict[str, Any]:
        if self.receipt_hook is None and not self.external_receipt_managed:
            raise PcControlExecutionDenied(
                "window recovery denied: existing AURA receipt layer is not bound"
            )
        if not isinstance(recovery, Mapping):
            raise PcControlExecutionDenied("invalid window recovery descriptor")
        if str(recovery.get("schema") or "") != "aura.pc-control.window-recovery.v1":
            raise PcControlExecutionDenied("invalid window recovery schema")
        if recovery.get("available") is not True:
            raise PcControlExecutionDenied("window recovery descriptor is not available")

        allowed = {
            "schema", "available", "rollback_of_request_id",
            "target", "foreground_before",
        }
        if set(recovery.keys()) - allowed:
            raise PcControlExecutionDenied("unexpected window recovery fields")

        rollback_of = str(recovery.get("rollback_of_request_id") or "").strip()
        if not rollback_of:
            raise PcControlExecutionDenied("rollback_of_request_id is required")

        target = recovery.get("target")
        if not isinstance(target, Mapping):
            raise PcControlExecutionDenied("window recovery target is required")
        if set(target.keys()) != {"hwnd", "title", "show_state"}:
            raise PcControlExecutionDenied("invalid window recovery target fields")

        try:
            hwnd = int(target.get("hwnd"))
        except Exception as exc:
            raise PcControlExecutionDenied("invalid recovery hwnd") from exc
        title = str(target.get("title") or "")
        show_state = str(target.get("show_state") or "").strip().lower()
        if hwnd <= 0 or not title or show_state not in {"normal", "minimized", "maximized"}:
            raise PcControlExecutionDenied("invalid window recovery target")

        before = self._validate_window_target({"hwnd": hwnd, "title": title})

        fg_before_desc = recovery.get("foreground_before")
        fg_before = None
        if fg_before_desc is not None:
            if not isinstance(fg_before_desc, Mapping):
                raise PcControlExecutionDenied("invalid foreground recovery target")
            if set(fg_before_desc.keys()) != {"hwnd", "title"}:
                raise PcControlExecutionDenied("invalid foreground recovery fields")
            try:
                fg_hwnd = int(fg_before_desc.get("hwnd"))
            except Exception as exc:
                raise PcControlExecutionDenied("invalid foreground recovery hwnd") from exc
            fg_title = str(fg_before_desc.get("title") or "")
            if fg_hwnd <= 0 or not fg_title:
                raise PcControlExecutionDenied("invalid foreground recovery target")
            if fg_hwnd == hwnd:
                if fg_title != title:
                    raise PcControlTargetChanged("foreground recovery title mismatch")
                fg_before = before
            else:
                fg_before = self._validate_window_target(
                    {"hwnd": fg_hwnd, "title": fg_title}
                )

        audit = {
            "schema": SCHEMA,
            "action": "RESTORE_WINDOW_STATE",
            "origin": str(origin or "local-core"),
            "rollback_of_request_id": rollback_of,
            "before": self._payload(before),
            "target_show_state": show_state,
            "foreground_before": self._payload(fg_before),
        }
        if self.receipt_hook is not None:
            self.receipt_hook("PREPARED", audit)

        restore_fn = getattr(self.backend, "restore_window_state", None)
        if not callable(restore_fn):
            raise PcControlExecutionDenied("native window recovery is unavailable")

        ok = bool(restore_fn(hwnd, {"show_state": show_state}))
        if not ok:
            failure = dict(audit)
            failure["status"] = "FAILED"
            if self.receipt_hook is not None:
                self.receipt_hook("FAILED", failure)
            raise PcControlExecutionDenied("native window state restoration failed")

        foreground_restored = True
        if fg_before is not None:
            # Never re-resolve by title: use only the exact prevalidated HWND.
            foreground_restored = bool(self.backend.focus_window(fg_before.hwnd))
            if not foreground_restored:
                failure = dict(audit)
                failure["status"] = "FAILED"
                failure["partial_restore"] = True
                if self.receipt_hook is not None:
                    self.receipt_hook("FAILED", failure)
                raise PcControlExecutionDenied("foreground restoration failed")

        try:
            after = self._find_window(hwnd)
        except Exception:
            after = None

        completed = dict(audit)
        completed["status"] = "SUCCEEDED"
        completed["after"] = self._payload(after)
        completed["foreground_restored"] = bool(foreground_restored)
        if self.receipt_hook is not None:
            self.receipt_hook("COMPLETED", completed)

        return {
            "schema": RESULT_SCHEMA,
            "action": "RESTORE_WINDOW_STATE",
            "status": "SUCCEEDED",
            "mutating": True,
            "data": {
                "before": self._payload(before),
                "after": self._payload(after),
                "rollback_of_request_id": rollback_of,
                "restored_show_state": show_state,
                "foreground_restored": bool(foreground_restored),
            },
        }

    def execute(
        self,
        action: str,
        params: Mapping[str, Any] | None = None,
        *,
        origin: str = "local-core",
    ) -> dict[str, Any]:
        request = normalize_request(action, params, origin=origin)
        plan = plan_request(request)
        action = request["action"]

        if action not in SUPPORTED_ACTIONS:
            raise PcControlExecutionDenied(
                f"W131-2 adapter does not own action: {action}"
            )

        if action == "DISCOVER_WINDOWS":
            data = self.backend.discover_windows()
            return {
                "schema": RESULT_SCHEMA,
                "request_id": request["request_id"],
                "action": action,
                "status": "SUCCEEDED",
                "mutating": False,
                "data": self._payload(data),
            }

        if action == "DISCOVER_PROCESSES":
            data = self.backend.discover_processes()
            return {
                "schema": RESULT_SCHEMA,
                "request_id": request["request_id"],
                "action": action,
                "status": "SUCCEEDED",
                "mutating": False,
                "data": self._payload(data),
            }

        if action == "GET_FOREGROUND_WINDOW":
            data = self.backend.foreground_window()
            return {
                "schema": RESULT_SCHEMA,
                "request_id": request["request_id"],
                "action": action,
                "status": "SUCCEEDED",
                "mutating": False,
                "data": self._payload(data),
            }

        if action in MUTATING_ACTIONS:
            if self.receipt_hook is None and not self.external_receipt_managed:
                raise PcControlExecutionDenied(
                    "mutating Windows action denied: existing AURA receipt layer is not bound"
                )

            before = self._validate_window_target(request["params"])
            recovery = self._capture_recovery_state(before, request["request_id"])
            audit_base = {
                "schema": SCHEMA,
                "request_id": request["request_id"],
                "action": action,
                "params": dict(request["params"]),
                "risk_tier": request["risk_tier"],
                "before": self._payload(before),
                "recovery": recovery,
                "owner": "pc-control.windows.v131",
            }
            if self.receipt_hook is not None:
                self.receipt_hook("AUTHORIZED", audit_base)

            if action == "FOCUS_WINDOW":
                ok = bool(self.backend.focus_window(before.hwnd))
            elif action == "MINIMIZE_WINDOW":
                ok = bool(self.backend.minimize_window(before.hwnd))
            elif action == "MAXIMIZE_WINDOW":
                ok = bool(self.backend.maximize_window(before.hwnd))
            else:  # fail closed
                raise PcControlExecutionDenied(action)

            if not ok:
                failure = dict(audit_base)
                failure["status"] = "FAILED"
                if self.receipt_hook is not None:
                    self.receipt_hook("FAILED", failure)
                raise PcControlExecutionDenied(f"native Windows action failed: {action}")

            after = None
            try:
                after = self._find_window(before.hwnd)
            except Exception:
                # A focus/minimize/maximize command can transiently alter discoverability;
                # the result still carries the authoritative preimage and action status.
                after = None

            completed = dict(audit_base)
            completed["status"] = "SUCCEEDED"
            completed["after"] = self._payload(after)
            if self.receipt_hook is not None:
                self.receipt_hook("COMPLETED", completed)

            return {
                "schema": RESULT_SCHEMA,
                "request_id": request["request_id"],
                "action": action,
                "status": "SUCCEEDED",
                "mutating": True,
                "data": {
                    "before": self._payload(before),
                    "after": self._payload(after),
                    "recovery": recovery,
                },
            }

        raise PcControlExecutionDenied(f"unreachable action: {action}")


def capability_snapshot() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "supported_actions": sorted(SUPPORTED_ACTIONS),
        "mutating_actions": sorted(MUTATING_ACTIONS),
        "native_backend": "ctypes.Win32",
        "shell_execution": False,
        "powershell_execution": False,
        "arbitrary_executable_execution": False,
        "receipt_hook_required_for_mutation": True,
        "close_window_bound": False,
        "terminate_process_bound": False,
        "router_bound": True,
    }

# AURA ROADMAP W131-3D2 R2 — WINDOWS FOREGROUND ACTIVATION OVERRIDE
def _aura_w131_3d2_prepare_focus_apis(backend) -> None:
    try:
        wintypes = backend.wintypes
    except Exception:
        return

    specs = (
        (backend.user32, "IsIconic", [wintypes.HWND], wintypes.BOOL),
        (backend.user32, "BringWindowToTop", [wintypes.HWND], wintypes.BOOL),
        (backend.user32, "SetFocus", [wintypes.HWND], wintypes.HWND),
        (
            backend.user32,
            "AttachThreadInput",
            [wintypes.DWORD, wintypes.DWORD, wintypes.BOOL],
            wintypes.BOOL,
        ),
        (backend.kernel32, "GetCurrentThreadId", [], wintypes.DWORD),
    )
    for owner, name, argtypes, restype in specs:
        try:
            fn = getattr(owner, name)
            fn.argtypes = argtypes
            fn.restype = restype
        except Exception:
            pass


def _aura_w131_3d2_focus_window(self, hwnd: int) -> bool:
    hwnd = int(hwnd)
    if hwnd <= 0 or not self.user32.IsWindow(hwnd):
        return False

    _aura_w131_3d2_prepare_focus_apis(self)
    SW_RESTORE = 9

    try:
        if bool(self.user32.IsIconic(hwnd)):
            self.user32.ShowWindow(hwnd, SW_RESTORE)
    except Exception:
        pass

    current_tid = 0
    foreground_hwnd = 0
    foreground_tid = 0
    target_tid = 0

    try:
        current_tid = int(self.kernel32.GetCurrentThreadId() or 0)
    except Exception:
        pass
    try:
        foreground_hwnd = int(self.user32.GetForegroundWindow() or 0)
    except Exception:
        pass
    try:
        if foreground_hwnd > 0:
            foreground_tid = int(
                self.user32.GetWindowThreadProcessId(foreground_hwnd, None) or 0
            )
    except Exception:
        pass
    try:
        target_tid = int(self.user32.GetWindowThreadProcessId(hwnd, None) or 0)
    except Exception:
        pass

    attached: list[int] = []
    try:
        for tid in (foreground_tid, target_tid):
            if tid and current_tid and tid != current_tid and tid not in attached:
                try:
                    if bool(self.user32.AttachThreadInput(current_tid, tid, True)):
                        attached.append(tid)
                except Exception:
                    pass

        try:
            self.user32.BringWindowToTop(hwnd)
        except Exception:
            pass

        set_foreground_ok = False
        try:
            set_foreground_ok = bool(self.user32.SetForegroundWindow(hwnd))
        except Exception:
            pass

        try:
            self.user32.SetFocus(hwnd)
        except Exception:
            pass

        actual_foreground = 0
        try:
            actual_foreground = int(self.user32.GetForegroundWindow() or 0)
        except Exception:
            pass

        return actual_foreground == hwnd or set_foreground_ok

    finally:
        for tid in reversed(attached):
            try:
                self.user32.AttachThreadInput(current_tid, tid, False)
            except Exception:
                pass


WindowsNativeBackend.focus_window = _aura_w131_3d2_focus_window
