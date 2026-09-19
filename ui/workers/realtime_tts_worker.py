"""AURA v0.8.6.4 - extracted realtime TTS worker.

Behavior-preserving extraction from ui.main_window.
Do not add product metadata authority here.
"""
from __future__ import annotations

import logging

import queue

import threading

import time

from PySide6.QtCore import QObject, QPointF, QRect, QRectF, QThread, QTimer, Qt, Signal

from config.settings import settings

from core.aura_core import AuraCore, AuraState

from runtime.resource_guardian import ResourcePressureError

from voice.errors import VoiceError

from voice.realtime_pipeline import RealtimePipelineCallbacks, run_realtime_audio_pipeline

logger = logging.getLogger("aura.ui")

class RealtimeTTSWorker(QObject):
    """True producer/consumer realtime speech for complete LLM sentences.

    v0.7.0.15.2 separates sentence intake, TTS synthesis and audio playback.
    Segment N+1 is therefore synthesized while segment N is already playing.
    """

    finished = Signal()
    failed = Signal(str)
    speaking_started = Signal()

    def __init__(self, aura_core: AuraCore, profile: dict, *, turn_started: float):
        super().__init__()
        self.aura_core = aura_core
        self.profile = dict(profile or {})
        self.turn_started = float(turn_started)
        self._queue: queue.Queue[tuple[str, float] | None] = queue.Queue(
            maxsize=max(1, int(settings.REALTIME_DIALOGUE_MAX_QUEUE_SEGMENTS))
        )
        self._audio_queue: queue.Queue | None = None
        self._cancel_event = threading.Event()
        self._session = None

    @property
    def _cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def enqueue(self, text: str) -> bool:
        text = str(text or "").strip()
        if not text or self._cancelled:
            return False
        try:
            self._queue.put_nowait((text, time.perf_counter()))
            return True
        except queue.Full:
            logger.warning("Realtime dialogue queue pleine; segment retenu pour la fin")
            return False

    def finish_input(self) -> None:
        if self._cancelled:
            return
        try:
            self._queue.put_nowait(None)
        except queue.Full:
            self._queue.put(None)

    def cancel(self) -> None:
        self._cancel_event.set()
        session = self._session
        if session is not None:
            try:
                session.cancel()
            except Exception:
                logger.debug("Annulation session TTS realtime ignorée", exc_info=True)
        try:
            self.aura_core.voice_engine.stop_speaking()
        except Exception:
            pass
        for target in (self._queue, self._audio_queue):
            if target is None:
                continue
            try:
                target.put_nowait(None)
            except queue.Full:
                pass

    def _run_sequential_fallback(self, decision) -> int:
        """Preserve the legacy path only when the selected backend is not XTTS."""
        total_segments = 0
        first_segment = True
        while not self._cancelled:
            item = self._queue.get()
            try:
                if item is None:
                    break
                text, ready_at = item
                if first_segment:
                    self.speaking_started.emit()
                segment_started = time.perf_counter()
                metrics = self.aura_core.voice_engine.speak(text, force_fallback=decision.use_fallback)
                total_segments += 1
                if metrics is not None and hasattr(metrics, "synthesis_seconds"):
                    first_audio = float(getattr(metrics, "time_to_audio_seconds", metrics.synthesis_seconds))
                    turn_to_audio = (segment_started - self.turn_started) + first_audio
                    logger.info(
                        "Realtime dialogue sequential fallback segment=%d chars=%d queue_wait=%.3fs first_audio_from_turn=%.3fs synth=%.3fs playback=%.3fs",
                        total_segments, len(text), max(0.0, segment_started - ready_at), turn_to_audio,
                        float(metrics.synthesis_seconds), float(metrics.playback_seconds),
                    )
                first_segment = False
            finally:
                self._queue.task_done()
        return total_segments

    def _run_xtts_pipeline(self, session) -> int:
        first_playback = {"value": True}

        def bind_audio_queue(audio_queue) -> None:
            self._audio_queue = audio_queue

        def on_synthesized(event) -> None:
            prepared = event.prepared
            logger.info(
                "Realtime pipeline synthesized segment=%d chars=%d sentence_wait=%.3fs synth=%.3fs",
                event.index + 1, len(event.text), max(0.0, event.synth_started - event.ready_at),
                float(prepared.synthesis_seconds),
            )

        def on_playback_started(event, play_started: float) -> None:
            if first_playback["value"]:
                self.speaking_started.emit()
                first_playback["value"] = False

        def on_playback_finished(event, play_started: float, playback_seconds: float) -> None:
            prepared = event.prepared
            first_audio_at = float(getattr(prepared, "first_audio_at", 0.0) or 0.0)
            first_audio_from_turn = max(0.0, (first_audio_at or play_started) - self.turn_started)
            logger.info(
                "Realtime pipeline playback segment=%d chars=%d sentence_wait=%.3fs audio_wait=%.3fs first_audio_from_turn=%.3fs synth=%.3fs playback=%.3fs chunks=%d",
                event.index + 1, len(event.text), max(0.0, event.synth_started - event.ready_at),
                max(0.0, play_started - float(prepared.prepared_at)),
                first_audio_from_turn, float(getattr(prepared, "synthesis_seconds", 0.0)),
                float(playback_seconds), int(getattr(prepared, "chunk_count", 1) or 1),
            )

        return run_realtime_audio_pipeline(
            self._queue,
            session,
            self._cancel_event,
            audio_queue_size=max(1, int(settings.REALTIME_DIALOGUE_AUDIO_QUEUE_SEGMENTS)),
            callbacks=RealtimePipelineCallbacks(
                on_synthesized=on_synthesized,
                on_playback_started=on_playback_started,
                on_playback_finished=on_playback_finished,
            ),
            audio_queue_ref=bind_audio_queue,
        )

    def run(self):
        decision = None
        total_segments = 0
        try:
            # Important: reserve resources immediately when the worker starts,
            # while the LLM is still generating. The previous implementation did
            # this only after sentence 1 was ready, adding Guardian latency to the
            # critical first-audio path.
            decision = self.aura_core.resource_guardian.prepare_for_realtime_tts(self.profile)
            session = self.aura_core.voice_engine.open_realtime_voice_session(
                force_fallback=decision.use_fallback
            )
            self._session = session
            if session is None:
                logger.info("Realtime dialogue pipeline backend=sequential-fallback")
                total_segments = self._run_sequential_fallback(decision)
            else:
                engine = "piper" if session.__class__.__name__.startswith("RealtimePiper") else "xtts"
                logger.info(
                    "Realtime dialogue pipeline backend=%s producer-consumer device=%s audio_queue=%d",
                    engine, session.device, max(1, int(settings.REALTIME_DIALOGUE_AUDIO_QUEUE_SEGMENTS)),
                )
                total_segments = self._run_xtts_pipeline(session)
            logger.info("Realtime dialogue TTS complete segments=%d pipeline=%s", total_segments, session is not None)
            self.finished.emit()
        except ResourcePressureError as exc:
            logger.info("Realtime dialogue TTS fallback: %s", exc)
            self.failed.emit(str(exc))
        except VoiceError as exc:
            logger.warning("Realtime dialogue TTS indisponible: %s", exc)
            self.failed.emit(str(exc))
        except Exception:
            logger.exception("Erreur TTS realtime inattendue")
            self.failed.emit("Le dialogue vocal temps réel a été interrompu. Je repasse au mode vocal normal.")
        finally:
            session = self._session
            if session is not None:
                try:
                    session.close()
                except Exception:
                    logger.debug("Fermeture session XTTS realtime ignorée", exc_info=True)
            self._session = None
            self._audio_queue = None
            self.aura_core.after_tts()
