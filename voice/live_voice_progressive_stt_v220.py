
from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Full, Queue
from threading import Event, RLock, Thread
from typing import Any, Callable, Optional

import numpy as np


PartialCallback = Callable[[str, str], Any]
ErrorCallback = Callable[[str, str], Any]
TranscribeCallable = Callable[[Any], str]


@dataclass(frozen=True)
class ProgressiveSTTStatus:
    running: bool
    active: bool
    turn_id: Optional[str]
    buffered_source_samples: int
    source_sample_rate: int
    target_sample_rate: int
    scheduled_snapshots: int
    completed_snapshots: int
    dropped_snapshots: int
    emitted_partials: int
    last_partial_text: str
    worker_error: Optional[str]


@dataclass(frozen=True)
class _SnapshotTask:
    generation: int
    turn_id: str
    source_audio: np.ndarray


class ProgressiveSTTRuntime:
    # Provider-neutral progressive retranscription worker.
    #
    # Invariants:
    # - push_audio() never calls the STT provider.
    # - provider calls run only on AURA-Progressive-STT-Worker.
    # - queue capacity is bounded and latest-snapshot biased.
    # - stale results are rejected with a generation token.
    # - final authoritative STT remains owned by existing STTWorker.

    THREAD_NAME = "AURA-Progressive-STT-Worker"

    def __init__(
        self,
        *,
        transcribe: TranscribeCallable,
        on_partial: PartialCallback,
        on_error: Optional[ErrorCallback] = None,
        source_sample_rate: int = 48_000,
        target_sample_rate: int = 16_000,
        min_audio_seconds: float = 0.80,
        interval_seconds: float = 0.90,
        max_audio_seconds: float = 20.0,
        queue_capacity: int = 1,
    ) -> None:
        if not callable(transcribe):
            raise TypeError("transcribe must be callable")
        if not callable(on_partial):
            raise TypeError("on_partial must be callable")
        if on_error is not None and not callable(on_error):
            raise TypeError("on_error must be callable")
        if int(source_sample_rate) <= 0 or int(target_sample_rate) <= 0:
            raise ValueError("sample rates must be positive")
        if float(min_audio_seconds) <= 0:
            raise ValueError("min_audio_seconds must be positive")
        if float(interval_seconds) <= 0:
            raise ValueError("interval_seconds must be positive")
        if float(max_audio_seconds) <= 0:
            raise ValueError("max_audio_seconds must be positive")
        if int(queue_capacity) < 1:
            raise ValueError("queue_capacity must be >= 1")

        self._transcribe = transcribe
        self._on_partial = on_partial
        self._on_error = on_error
        self.source_sample_rate = int(source_sample_rate)
        self.target_sample_rate = int(target_sample_rate)
        self.min_audio_seconds = float(min_audio_seconds)
        self.interval_seconds = float(interval_seconds)
        self.max_audio_seconds = float(max_audio_seconds)

        self._min_source_samples = max(
            1, int(round(self.source_sample_rate * self.min_audio_seconds))
        )
        self._interval_source_samples = max(
            1, int(round(self.source_sample_rate * self.interval_seconds))
        )
        self._max_source_samples = max(
            self._min_source_samples,
            int(round(self.source_sample_rate * self.max_audio_seconds)),
        )

        self._lock = RLock()
        self._queue: Queue = Queue(maxsize=int(queue_capacity))
        self._stop = Event()
        self._thread: Optional[Thread] = None

        self._generation = 0
        self._active = False
        self._turn_id: Optional[str] = None
        self._chunks: list[np.ndarray] = []
        self._source_samples = 0
        self._last_scheduled_samples = 0

        self._scheduled_snapshots = 0
        self._completed_snapshots = 0
        self._dropped_snapshots = 0
        self._emitted_partials = 0
        self._last_partial_text = ""
        self._worker_error: Optional[str] = None

    @staticmethod
    def _mono_float32(audio: Any) -> np.ndarray:
        arr = np.asarray(audio, dtype=np.float32)
        if arr.ndim == 0:
            arr = arr.reshape(1)
        elif arr.ndim == 2:
            arr = np.mean(arr, axis=1, dtype=np.float32)
        elif arr.ndim != 1:
            arr = arr.reshape(-1)
        return np.ascontiguousarray(arr.reshape(-1), dtype=np.float32)

    def _resample(self, audio: np.ndarray) -> np.ndarray:
        if self.source_sample_rate == self.target_sample_rate or audio.size < 2:
            return np.ascontiguousarray(audio, dtype=np.float32)

        out_n = max(
            1,
            int(round(
                audio.size * self.target_sample_rate / self.source_sample_rate
            )),
        )
        old_x = np.linspace(0.0, 1.0, num=audio.size, endpoint=False)
        new_x = np.linspace(0.0, 1.0, num=out_n, endpoint=False)
        out = np.interp(new_x, old_x, audio).astype(np.float32)
        return np.ascontiguousarray(out, dtype=np.float32)

    def start(self) -> bool:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return True
            self._stop.clear()
            self._worker_error = None
            thread = Thread(
                target=self._worker_loop,
                name=self.THREAD_NAME,
                daemon=True,
            )
            self._thread = thread
            thread.start()
            return True

    def stop(self, *, join_timeout: float = 3.0) -> None:
        self.cancel("runtime_stop")
        self._stop.set()
        try:
            self._queue.put_nowait(None)
        except Full:
            self._drop_oldest_snapshot()
            try:
                self._queue.put_nowait(None)
            except Full:
                pass

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=max(0.0, float(join_timeout)))

        with self._lock:
            self._thread = None

    def begin_turn(self, turn_id: str) -> None:
        turn_id = str(turn_id or "").strip()
        if not turn_id:
            raise ValueError("turn_id is required")

        self.start()
        with self._lock:
            self._generation += 1
            self._active = True
            self._turn_id = turn_id
            self._chunks = []
            self._source_samples = 0
            self._last_scheduled_samples = 0
            self._last_partial_text = ""
            self._worker_error = None
        self._clear_pending_snapshots()

    def cancel(self, reason: str = "cancelled") -> None:
        del reason
        with self._lock:
            self._generation += 1
            self._active = False
            self._turn_id = None
            self._chunks = []
            self._source_samples = 0
            self._last_scheduled_samples = 0
            self._last_partial_text = ""
        self._clear_pending_snapshots()

    def end_turn(self) -> None:
        self.cancel("turn_ended")

    def push_audio(self, audio: Any) -> bool:
        arr = self._mono_float32(audio)
        if arr.size == 0:
            return False

        task = None
        with self._lock:
            if not self._active or self._turn_id is None:
                return False

            self._chunks.append(arr.copy())
            self._source_samples += int(arr.size)

            while self._chunks and self._source_samples > self._max_source_samples:
                first = self._chunks.pop(0)
                self._source_samples -= int(first.size)

            enough = self._source_samples >= self._min_source_samples
            due = (
                self._source_samples - self._last_scheduled_samples
                >= self._interval_source_samples
            )
            if not (enough and due):
                return False

            snapshot = np.concatenate(self._chunks).astype(np.float32, copy=False)
            task = _SnapshotTask(
                generation=self._generation,
                turn_id=self._turn_id,
                source_audio=np.ascontiguousarray(
                    snapshot.copy(), dtype=np.float32
                ),
            )
            self._last_scheduled_samples = self._source_samples
            self._scheduled_snapshots += 1

        self._put_latest(task)
        return True

    def status(self) -> ProgressiveSTTStatus:
        with self._lock:
            thread = self._thread
            return ProgressiveSTTStatus(
                running=bool(thread is not None and thread.is_alive()),
                active=bool(self._active),
                turn_id=self._turn_id,
                buffered_source_samples=int(self._source_samples),
                source_sample_rate=self.source_sample_rate,
                target_sample_rate=self.target_sample_rate,
                scheduled_snapshots=int(self._scheduled_snapshots),
                completed_snapshots=int(self._completed_snapshots),
                dropped_snapshots=int(self._dropped_snapshots),
                emitted_partials=int(self._emitted_partials),
                last_partial_text=str(self._last_partial_text),
                worker_error=self._worker_error,
            )

    def _clear_pending_snapshots(self) -> None:
        while True:
            try:
                self._queue.get_nowait()
            except Empty:
                return
            else:
                try:
                    self._queue.task_done()
                except Exception:
                    pass

    def _drop_oldest_snapshot(self) -> None:
        try:
            self._queue.get_nowait()
        except Empty:
            return
        else:
            with self._lock:
                self._dropped_snapshots += 1
            try:
                self._queue.task_done()
            except Exception:
                pass

    def _put_latest(self, task: _SnapshotTask) -> None:
        try:
            self._queue.put_nowait(task)
            return
        except Full:
            pass

        self._drop_oldest_snapshot()
        try:
            self._queue.put_nowait(task)
        except Full:
            with self._lock:
                self._dropped_snapshots += 1

    @staticmethod
    def _normalize_text(value: Any) -> str:
        return " ".join(str(value or "").strip().split())

    def _is_current(self, task: _SnapshotTask) -> bool:
        with self._lock:
            return bool(
                self._active
                and self._turn_id == task.turn_id
                and self._generation == task.generation
            )

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                task = self._queue.get(timeout=0.20)
            except Empty:
                continue

            if task is None:
                try:
                    self._queue.task_done()
                except Exception:
                    pass
                break

            try:
                if not self._is_current(task):
                    continue

                audio = self._resample(task.source_audio)
                if not self._is_current(task):
                    continue

                raw = self._transcribe(audio)
                text = self._normalize_text(raw)

                with self._lock:
                    self._completed_snapshots += 1

                if not text or not self._is_current(task):
                    continue

                emit = False
                with self._lock:
                    if text != self._last_partial_text:
                        self._last_partial_text = text
                        self._emitted_partials += 1
                        emit = True

                if emit:
                    self._on_partial(task.turn_id, text)

            except Exception as exc:
                error = f"{type(exc).__name__}:{exc}"
                with self._lock:
                    self._worker_error = error
                if self._is_current(task) and callable(self._on_error):
                    try:
                        self._on_error(task.turn_id, error)
                    except Exception:
                        pass
            finally:
                try:
                    self._queue.task_done()
                except Exception:
                    pass
