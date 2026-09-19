"""Pure-Python producer/consumer audio pipeline for AURA v0.7.0.15.6.2."""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol


class RealtimeSynthesisSession(Protocol):
    def synthesize(self, text: str, *, index: int): ...
    def play(self, prepared) -> float: ...


@dataclass(frozen=True)
class PipelineSynthesisEvent:
    index: int
    text: str
    ready_at: float
    synth_started: float
    prepared: object


@dataclass
class RealtimePipelineCallbacks:
    on_synthesized: Callable[[PipelineSynthesisEvent], None] | None = None
    on_playback_started: Callable[[PipelineSynthesisEvent, float], None] | None = None
    on_playback_finished: Callable[[PipelineSynthesisEvent, float, float], None] | None = None


def run_realtime_audio_pipeline(
    sentence_queue: queue.Queue,
    session: RealtimeSynthesisSession,
    cancel_event: threading.Event,
    *,
    audio_queue_size: int = 2,
    callbacks: RealtimePipelineCallbacks | None = None,
    audio_queue_ref: Callable[[queue.Queue], None] | None = None,
) -> int:
    """Synthesize sentence N+1 while sentence N is being played.

    The caller owns the sentence queue and writes ``None`` when LLM generation
    ends. This function owns a bounded audio queue so synthesis cannot run far
    ahead of playback. It returns the number of segments whose playback stage
    was reached.
    """
    callbacks = callbacks or RealtimePipelineCallbacks()
    audio_queue: queue.Queue = queue.Queue(maxsize=max(1, int(audio_queue_size)))
    if audio_queue_ref is not None:
        audio_queue_ref(audio_queue)

    errors: list[BaseException] = []
    played = 0
    played_lock = threading.Lock()

    def put_audio(item) -> bool:
        while not cancel_event.is_set():
            try:
                audio_queue.put(item, timeout=0.10)
                return True
            except queue.Full:
                continue
        return False

    def synth_loop() -> None:
        index = 0
        try:
            while not cancel_event.is_set():
                item = sentence_queue.get()
                try:
                    if item is None:
                        put_audio(None)
                        return
                    text, ready_at = item
                    synth_started = time.perf_counter()
                    prepared = session.synthesize(text, index=index)
                    event = PipelineSynthesisEvent(index, text, ready_at, synth_started, prepared)
                    if callbacks.on_synthesized is not None:
                        callbacks.on_synthesized(event)
                    if not put_audio(event):
                        return
                    index += 1
                finally:
                    sentence_queue.task_done()
        except BaseException as exc:  # transferred to caller thread below
            errors.append(exc)
            cancel_event.set()
            try:
                audio_queue.put_nowait(None)
            except queue.Full:
                pass

    def playback_loop() -> None:
        nonlocal played
        try:
            while True:
                try:
                    event = audio_queue.get(timeout=0.10)
                except queue.Empty:
                    if cancel_event.is_set():
                        return
                    continue
                try:
                    if event is None:
                        return
                    play_started = time.perf_counter()
                    if callbacks.on_playback_started is not None:
                        callbacks.on_playback_started(event, play_started)
                    playback_seconds = float(session.play(event.prepared))
                    with played_lock:
                        played += 1
                    if callbacks.on_playback_finished is not None:
                        callbacks.on_playback_finished(event, play_started, playback_seconds)
                finally:
                    audio_queue.task_done()
        except BaseException as exc:
            errors.append(exc)
            cancel_event.set()
            try:
                sentence_queue.put_nowait(None)
            except queue.Full:
                pass

    synth_thread = threading.Thread(target=synth_loop, name="AURA-Realtime-XTTS-Synth", daemon=True)
    play_thread = threading.Thread(target=playback_loop, name="AURA-Realtime-XTTS-Playback", daemon=True)
    synth_thread.start()
    play_thread.start()
    synth_thread.join()
    if cancel_event.is_set():
        try:
            audio_queue.put_nowait(None)
        except queue.Full:
            pass
    play_thread.join()

    if errors:
        raise errors[0]
    return int(played)
