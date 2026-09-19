# -*- coding: utf-8 -*-
"""
AURA P0.8.5.4.7.6.1.3-D1
Temporary process-local QThread tracing hook.

Loaded only through PYTHONPATH set by the diagnostic launcher.
It does not write to or patch AURA source/runtime files.
"""
from __future__ import annotations

import atexit
import json
import os
import sys
import threading
import time
import traceback
from pathlib import Path

TRACE_FILE = os.environ.get("AURA_QTHREAD_TRACE_FILE", "").strip()
TRACE_ENABLED = bool(TRACE_FILE)
_LOCK = threading.Lock()
_SEQ = 0
_STATE = {}


def _write(event: str, **payload):
    if not TRACE_ENABLED:
        return
    row = {
        "ts": time.time(),
        "event": event,
        "pid": os.getpid(),
        "thread_ident": threading.get_ident(),
        "argv": list(sys.argv),
    }
    row.update(payload)
    line = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
    try:
        with _LOCK:
            Path(TRACE_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(TRACE_FILE, "a", encoding="utf-8") as f:
                f.write(line)
                f.flush()
    except Exception:
        pass


def _origin():
    try:
        frames = traceback.extract_stack(limit=40)
        for frame in reversed(frames[:-2]):
            p = str(frame.filename or "").replace("\\", "/")
            if p.endswith("/qthread_diag_hook/sitecustomize.py"):
                continue
            if "PySide6" in p or "shiboken" in p.lower():
                continue
            return {
                "file": str(frame.filename),
                "line": int(frame.lineno or 0),
                "function": str(frame.name or ""),
                "code": str(frame.line or ""),
            }
    except Exception:
        pass
    return {"file": "", "line": 0, "function": "", "code": ""}


def _safe_running(obj):
    try:
        return bool(obj.isRunning())
    except Exception:
        return None


try:
    import PySide6.QtCore as _QtCore

    _OriginalQThread = _QtCore.QThread

    class AuraDiagnosticQThread(_OriginalQThread):
        def __init__(self, *args, **kwargs):
            global _SEQ
            super().__init__(*args, **kwargs)
            _SEQ += 1
            origin = _origin()
            base = Path(origin.get("file") or "unknown").name
            func = origin.get("function") or "unknown"
            line = origin.get("line") or 0
            diagnostic_name = f"AURA-D1-{os.getpid()}-{_SEQ:03d}-{base}:{line}:{func}"
            try:
                if not self.objectName():
                    self.setObjectName(diagnostic_name)
            except Exception:
                pass
            key = id(self)
            _STATE[key] = {
                "name": diagnostic_name,
                "object_name": self.objectName() if hasattr(self, "objectName") else "",
                "origin": origin,
                "started": False,
                "finished": False,
                "quit_calls": 0,
                "wait_calls": [],
            }
            _write(
                "qthread_create",
                qthread_id=key,
                name=diagnostic_name,
                object_name=_STATE[key]["object_name"],
                origin=origin,
                parent_type=type(args[0]).__name__ if args else None,
            )
            try:
                self.started.connect(
                    lambda key=key: (
                        _STATE.get(key, {}).update({"started": True}),
                        _write(
                            "qthread_started_signal",
                            qthread_id=key,
                            name=_STATE.get(key, {}).get("name"),
                            object_name=_STATE.get(key, {}).get("object_name"),
                        ),
                    )
                )
                self.finished.connect(
                    lambda key=key: (
                        _STATE.get(key, {}).update({"finished": True}),
                        _write(
                            "qthread_finished_signal",
                            qthread_id=key,
                            name=_STATE.get(key, {}).get("name"),
                            object_name=_STATE.get(key, {}).get("object_name"),
                        ),
                    )
                )
                self.destroyed.connect(
                    lambda _obj=None, key=key: _write(
                        "qthread_destroyed_signal",
                        qthread_id=key,
                        name=_STATE.get(key, {}).get("name"),
                        object_name=_STATE.get(key, {}).get("object_name"),
                        state=dict(_STATE.get(key, {})),
                    )
                )
            except Exception as exc:
                _write(
                    "qthread_signal_hook_error",
                    qthread_id=key,
                    name=diagnostic_name,
                    error=f"{type(exc).__name__}: {exc}",
                )

        def start(self, *args, **kwargs):
            key = id(self)
            state = _STATE.get(key, {})
            state["started"] = True
            _write(
                "qthread_start_call",
                qthread_id=key,
                name=state.get("name"),
                object_name=state.get("object_name"),
                running_before=_safe_running(self),
            )
            return super().start(*args, **kwargs)

        def quit(self, *args, **kwargs):
            key = id(self)
            state = _STATE.get(key, {})
            state["quit_calls"] = int(state.get("quit_calls") or 0) + 1
            _write(
                "qthread_quit_call",
                qthread_id=key,
                name=state.get("name"),
                object_name=state.get("object_name"),
                running_before=_safe_running(self),
            )
            return super().quit(*args, **kwargs)

        def wait(self, *args, **kwargs):
            key = id(self)
            state = _STATE.get(key, {})
            requested = None
            if args:
                try:
                    requested = int(args[0])
                except Exception:
                    requested = repr(args[0])
            _write(
                "qthread_wait_begin",
                qthread_id=key,
                name=state.get("name"),
                object_name=state.get("object_name"),
                timeout_arg=requested,
                running_before=_safe_running(self),
            )
            started = time.time()
            result = super().wait(*args, **kwargs)
            elapsed = time.time() - started
            state.setdefault("wait_calls", []).append({
                "timeout_arg": requested,
                "result": bool(result),
                "elapsed_s": elapsed,
            })
            _write(
                "qthread_wait_end",
                qthread_id=key,
                name=state.get("name"),
                object_name=state.get("object_name"),
                timeout_arg=requested,
                result=bool(result),
                elapsed_s=elapsed,
                running_after=_safe_running(self),
            )
            return result

        def terminate(self, *args, **kwargs):
            key = id(self)
            state = _STATE.get(key, {})
            _write(
                "qthread_terminate_call",
                qthread_id=key,
                name=state.get("name"),
                object_name=state.get("object_name"),
                running_before=_safe_running(self),
            )
            return super().terminate(*args, **kwargs)

    _QtCore.QThread = AuraDiagnosticQThread
    _write(
        "hook_installed",
        qthread_class="AuraDiagnosticQThread",
        original_qthread=repr(_OriginalQThread),
    )

except Exception as exc:
    _write("hook_install_error", error=f"{type(exc).__name__}: {exc}")


@atexit.register
def _snapshot_at_exit():
    try:
        snapshot = []
        for key, state in list(_STATE.items()):
            row = dict(state)
            row["qthread_id"] = key
            snapshot.append(row)
        _write("process_exit_snapshot", qthreads=snapshot)
    except Exception:
        pass
