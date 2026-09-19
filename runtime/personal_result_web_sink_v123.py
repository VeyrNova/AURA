from __future__ import annotations

from threading import RLock
from typing import Any, Callable, Mapping, Optional

_lock = RLock()
_sink: Optional[Callable[[Mapping[str, Any]], None]] = None


def register_personal_result_sink_v123(callback: Optional[Callable[[Mapping[str, Any]], None]]) -> None:
    global _sink
    with _lock:
        _sink = callback


def publish_personal_result_v123(payload: Mapping[str, Any]) -> bool:
    with _lock:
        callback = _sink
    if callback is None:
        return False
    callback(dict(payload or {}))
    return True
