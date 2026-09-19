
from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Optional


class SchedulerBackpressure(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkOutcome:
    turn_id: str
    executed: bool
    suppressed: bool
    reason: str
    value: Any = None
    error_type: Optional[str] = None


class LiveVoiceWorkScheduler:
    """Bounded worker scheduler subordinate to LiveVoiceSession cancellation.

    The scheduler does not own voice/session state and does not create its own
    cancellation token. The authoritative token must be supplied by the caller.

    It may cancel queued Future objects, but a running provider must still be
    stopped cooperatively through the provider adapter / LiveVoiceSession path.
    """

    def __init__(
        self,
        *,
        max_workers: int = 2,
        max_pending_per_turn: int = 2,
        thread_name_prefix: str = "aura-live-voice",
    ) -> None:
        max_workers = int(max_workers)
        max_pending_per_turn = int(max_pending_per_turn)
        if max_workers < 1:
            raise ValueError("max_workers must be >= 1")
        if max_pending_per_turn < 1:
            raise ValueError("max_pending_per_turn must be >= 1")

        self.max_workers = max_workers
        self.max_pending_per_turn = max_pending_per_turn
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix=str(thread_name_prefix),
        )
        self._lock = RLock()
        self._futures: dict[str, set[Future]] = {}
        self._closed = False

    def _cleanup_turn_locked(self, turn_id: str) -> None:
        bucket = self._futures.get(turn_id)
        if not bucket:
            self._futures.pop(turn_id, None)
            return
        dead = {future for future in bucket if future.done()}
        bucket.difference_update(dead)
        if not bucket:
            self._futures.pop(turn_id, None)

    def pending_count(self, turn_id: str) -> int:
        with self._lock:
            self._cleanup_turn_locked(str(turn_id))
            return len(self._futures.get(str(turn_id), set()))

    def submit(
        self,
        *,
        turn_id: str,
        cancellation: Any,
        fn: Callable[..., Any],
        args: tuple[Any, ...] = (),
        kwargs: Optional[dict[str, Any]] = None,
    ) -> Future:
        turn_id = str(turn_id)
        if not callable(fn):
            raise TypeError("fn must be callable")
        if not hasattr(cancellation, "cancelled"):
            raise TypeError("cancellation must expose canonical .cancelled state")

        kwargs = dict(kwargs or {})

        with self._lock:
            if self._closed:
                raise RuntimeError("scheduler is closed")
            self._cleanup_turn_locked(turn_id)

            if bool(cancellation.cancelled):
                future: Future = Future()
                future.set_result(
                    WorkOutcome(
                        turn_id=turn_id,
                        executed=False,
                        suppressed=True,
                        reason="cancelled_before_submit",
                    )
                )
                return future

            bucket = self._futures.setdefault(turn_id, set())
            if len(bucket) >= self.max_pending_per_turn:
                raise SchedulerBackpressure(
                    f"turn {turn_id} reached pending limit "
                    f"{self.max_pending_per_turn}"
                )

            def runner() -> WorkOutcome:
                if bool(cancellation.cancelled):
                    return WorkOutcome(
                        turn_id=turn_id,
                        executed=False,
                        suppressed=True,
                        reason="cancelled_before_execute",
                    )

                try:
                    value = fn(*args, **kwargs)
                except Exception as exc:
                    return WorkOutcome(
                        turn_id=turn_id,
                        executed=True,
                        suppressed=bool(cancellation.cancelled),
                        reason="work_error",
                        error_type=type(exc).__name__,
                    )

                if bool(cancellation.cancelled):
                    return WorkOutcome(
                        turn_id=turn_id,
                        executed=True,
                        suppressed=True,
                        reason="cancelled_after_execute",
                        value=value,
                    )

                return WorkOutcome(
                    turn_id=turn_id,
                    executed=True,
                    suppressed=False,
                    reason="completed",
                    value=value,
                )

            future = self._executor.submit(runner)
            bucket.add(future)

            def done_callback(done_future: Future) -> None:
                del done_future
                with self._lock:
                    self._cleanup_turn_locked(turn_id)

            future.add_done_callback(done_callback)
            return future

    def cancel_pending(self, *, turn_id: str) -> int:
        """Cancel queued Futures only.

        This does NOT cancel LiveVoiceSession's authoritative token and does not
        stop a currently running provider. Running providers must be stopped via
        the provider adapter after LiveVoiceSession has cancelled the turn.
        """
        turn_id = str(turn_id)
        cancelled = 0
        with self._lock:
            self._cleanup_turn_locked(turn_id)
            for future in tuple(self._futures.get(turn_id, set())):
                if future.cancel():
                    cancelled += 1
            self._cleanup_turn_locked(turn_id)
        return cancelled

    def shutdown(self, *, wait: bool = True) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self._executor.shutdown(wait=bool(wait), cancel_futures=True)
