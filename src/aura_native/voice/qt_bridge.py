from __future__ import annotations

from PySide6.QtCore import QObject, Property, Signal, Slot, QThread, QMetaObject, Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from pathlib import Path
import os
from collections.abc import Callable


def _ptt_trace(message: str) -> None:
    if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
        print(message, flush=True)

from .controller import VoiceController
from .models import VoiceState
from .providers import SoundDeviceAudioInput, WhisperSTTProvider, PiperTTSProvider
from .speech_text import prepare_text_for_speech
from uuid import uuid4
import time
import threading
import time as _time

def _voice_trace(message: str) -> None:
    if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
        print(f"{message} t={_time.monotonic():.6f} thread={threading.get_ident()}", flush=True)


class _VoiceWorker(QObject):
    stateChanged = Signal(str)
    transcriptReady = Signal(str)
    localTranscriptReady = Signal(str, str)
    errorOccurred = Signal(str)
    finished = Signal()
    startCompleted = Signal(bool)
    def __init__(self, controller):
        super().__init__(); self.controller = controller
        self.controller.on_event = self._event
        self._last_emitted_state = None
    def _event(self, event):
        self._emit_state(event.state.value)

    def _emit_state(self, value: str):
        if value == self._last_emitted_state:
            return
        self._last_emitted_state = value
        _ptt_trace(f"PTT_BRIDGE_STATE_EMIT={value}")
        self.stateChanged.emit(value)
    @Slot()
    def start(self):
        _ptt_trace("PTT_WORKER_RECEIVE_START")
        result = self.controller.start()
        _ptt_trace(f"PTT_CONTROLLER_RESULT_START accepted={result.accepted} state={result.state.value}")
        self.startCompleted.emit(bool(result.accepted))
    @Slot()
    def stop(self):
        _ptt_trace("PTT_WORKER_RECEIVE_STOP")
        result = self.controller.stop()
        _ptt_trace(f"PTT_CONTROLLER_RESULT_STOP accepted={result.accepted} state={result.state.value}")
        # VoiceController emits intermediate states through on_event, but its
        # terminal state may be assigned after the final event (for example
        # conversation fallback returns to IDLE). Forward that authoritative
        # state through the worker signal so QML cannot remain TRANSCRIBING.
        self._emit_state(self.controller.state.value)
        if result.transcript: self.transcriptReady.emit(result.transcript)
        if result.error: self.errorOccurred.emit(result.error)
    @Slot()
    def cancel(self):
        _ptt_trace("PTT_WORKER_RECEIVE_CANCEL")
        self.controller.cancel()
    @Slot()
    def speak(self, text): self.controller.speak(text)
    @Slot()
    def shutdown(self):
        _voice_trace("VOICE_STOP_WORKER_REQUEST")
        self.controller.cancel(); self.controller.stop_speaking(); self.finished.emit()


class NativeVoiceBridge(QObject):
    """Small Qt facade; it never starts listening automatically."""
    stateChanged = Signal()
    statusChanged = Signal()
    availabilityChanged = Signal()
    transcriptReady = Signal(str)
    localTranscriptReady = Signal(str, str)
    responseReady = Signal(str)
    errorOccurred = Signal(str)
    conversationRequested = Signal(str)
    voiceConversationRequested = Signal(str, str)

    def __init__(self, controller: VoiceController | None = None,
                 conversation_fallback: Callable[[str], object] | None = None,
                 parent=None):
        super().__init__(parent)
        if controller is None:
            root = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "AURA-NATIVE" / "models" / "voice"
            audio = SoundDeviceAudioInput()
            stt = WhisperSTTProvider(model_path=str(root / "stt" / "Systran--faster-whisper-small"), language="fr")
            tts = PiperTTSProvider(model_path=str(root / "tts" / "fr_FR-siwis-medium" / "fr_FR-siwis-medium.onnx"))
            fallback = conversation_fallback
            if fallback is None:
                def fallback(text):
                    return self._queue_conversation(text)
                fallback.keep_thinking = True
            controller = VoiceController(audio=audio, stt=stt, tts=tts,
                                         conversation_fallback=fallback)
        self.controller = controller
        if self.controller.conversation_fallback is None:
            self.controller.conversation_fallback = self._queue_conversation
        self._thread = QThread(self)
        self._worker = _VoiceWorker(self.controller)
        self._worker.moveToThread(self._thread)
        self._worker.stateChanged.connect(self._state_from_worker)
        self._worker.transcriptReady.connect(self._on_transcript)
        self._worker.errorOccurred.connect(self.errorOccurred)
        self._worker.startCompleted.connect(self._start_completed)
        self._thread.finished.connect(self._worker.deleteLater)
        self._start_pending = False
        self._stop_pending = False
        self._cancel_pending = False
        self._playback_thread = None
        self._playback_stop = threading.Event()
        self._wav_path = None
        self._terminalized_local_requests = set()
        self._audio_output = QAudioOutput(self)
        self._player = QMediaPlayer(self)
        self._player.setAudioOutput(self._audio_output)
        self._player.mediaStatusChanged.connect(self._media_status_changed)
        self._player.errorOccurred.connect(self._media_error)

    def _finish_playback(self, stopped=False):
        path = self._wav_path
        self._wav_path = None
        if path:
            try: Path(path).unlink(missing_ok=True)
            except OSError: pass
        self.controller.state = VoiceState.IDLE
        self._worker._emit_state(VoiceState.IDLE.value)
        if stopped: _voice_trace("VOICE_AUDIO_PLAYBACK_STOPPED")
        else: _voice_trace("VOICE_AUDIO_PLAYBACK_END")

    def _media_status_changed(self, status):
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._finish_playback(False)

    def _media_error(self, *_args):
        if self.state == VoiceState.SPEAKING.value:
            self._player.stop(); self._finish_playback(True)

    def _queue_conversation(self, text: str) -> bool:
        request_id = str(uuid4())
        _ptt_trace(f"VOICE_REQUEST_CREATED voice_request_id={request_id}")
        self.conversationRequested.emit(str(text))
        self.voiceConversationRequested.emit(str(text), request_id)
        # The conversation remains pending while the correlated final answer
        # is produced; this is bridge state only and does not alter STT.
        self.controller.state = VoiceState.THINKING
        self._worker._emit_state(VoiceState.THINKING.value)
        return True

    @Slot(str)
    def _on_transcript(self, text):
        value = str(text or "")
        self.transcriptReady.emit(value)
        self.localTranscriptReady.emit(value, str(uuid4()))

    @Slot(str, str)
    def onLocalActionTerminal(self, voice_request_id, status):
        ident = str(voice_request_id or "").strip()
        if not ident or ident in self._terminalized_local_requests:
            return
        self._terminalized_local_requests.add(ident)
        if self.state == VoiceState.THINKING.value:
            self.controller.state = VoiceState.IDLE
            self._state_from_worker(VoiceState.IDLE.value)
            _ptt_trace(f"VOICE_LOCAL_ACTION_TERMINAL voice_request_id={ident[:32]} status={status}")
            _ptt_trace("VOICE_LOCAL_STATE_RELEASED state=IDLE")

    @Slot(str, str)
    def onVoiceResponseFinal(self, text, request_id):
        value = str(text or "").strip()
        if not value or self.state != VoiceState.THINKING.value:
            return
        _ptt_trace(f"VOICE_RESPONSE_FINAL_RECEIVED request_id={str(request_id)[:32]}")
        _ptt_trace(f"VOICE_RESPONSE_CORRELATED request_id={str(request_id)[:32]}")
        speech_text = prepare_text_for_speech(value)
        _ptt_trace(f"VOICE_TTS_TEXT_PREPARE original_chars={len(value)}")
        _ptt_trace(f"VOICE_TTS_TEXT_READY speech_chars={len(speech_text)}")
        _ptt_trace(f"VOICE_TTS_MARKDOWN_REMOVED={'true' if speech_text != value else 'false'}")
        _ptt_trace(f"VOICE_TTS_REQUEST chars={len(speech_text)}")
        if self.controller.tts is None:
            self.controller.state = VoiceState.IDLE
            self._state_from_worker(VoiceState.IDLE.value)
            self.errorOccurred.emit("tts_unavailable")
            return
        started = time.perf_counter()
        try:
            _ptt_trace("VOICE_TTS_PROVIDER_READY")
            _ptt_trace("VOICE_TTS_SYNTHESIS_BEGIN")
            result = self.controller.speak(speech_text)
            _ptt_trace(f"VOICE_TTS_SYNTHESIS_END duration_ms={int((time.perf_counter()-started)*1000)}")
            if not result.accepted:
                self.controller.state = VoiceState.IDLE
                self._state_from_worker(VoiceState.IDLE.value)
                self.errorOccurred.emit(result.error or "tts_failed")
                return
            _ptt_trace("VOICE_TTS_AUDIO_READY duration_ms=0")
            self.controller.state = VoiceState.SPEAKING
            self._worker._emit_state(VoiceState.SPEAKING.value)
            _voice_trace("VOICE_AUDIO_PLAYBACK_BEGIN")
            wav_path = getattr(self.controller.tts, "_last_wav", None)
            self._wav_path = wav_path
            if not wav_path:
                self._finish_playback(False)
            else:
                self._player.setSource(QUrl.fromLocalFile(str(wav_path)))
                self._player.play()
        except Exception:
            self.controller.state = VoiceState.IDLE
            self._state_from_worker(VoiceState.IDLE.value)
            self.errorOccurred.emit("tts_failed")

    @Property(str, notify=stateChanged)
    def state(self):
        return self.controller.state.value

    @Property(str, notify=statusChanged)
    def statusText(self):
        return {VoiceState.IDLE: "Prêt", VoiceState.LISTENING: "Écoute en cours",
                VoiceState.TRANSCRIBING: "Transcription…", VoiceState.THINKING: "Réflexion…",
                VoiceState.SPEAKING: "Parle", VoiceState.ERROR: "Erreur"}.get(self.controller.state, "Erreur")

    @Property(bool, notify=availabilityChanged)
    def available(self):
        return self.controller.audio is not None

    @Property(bool, notify=availabilityChanged)
    def microphoneAvailable(self):
        return self.controller.audio is not None

    @Property(bool, notify=availabilityChanged)
    def sttAvailable(self):
        return self.controller.stt is not None and bool(getattr(self.controller.stt, "model_path", ""))

    @Property(bool, notify=availabilityChanged)
    def ttsAvailable(self):
        return self.controller.tts is not None and bool(getattr(self.controller.tts, "model_path", ""))

    @Property(bool, notify=stateChanged)
    def listening(self): return self.isListening

    @Property(bool, notify=stateChanged)
    def speaking(self): return self.isSpeaking

    @Slot(str)
    def _state_from_worker(self, value):
        self.stateChanged.emit(); self.statusChanged.emit()

    @Property(bool, notify=stateChanged)
    def isListening(self):
        return self.controller.state is VoiceState.LISTENING

    @Property(bool, notify=stateChanged)
    def isSpeaking(self):
        return self.controller.state is VoiceState.SPEAKING

    @Slot(result=bool)
    def startListening(self):
        _ptt_trace(f"PTT_BRIDGE_START_REQUEST thread_running={self._thread.isRunning()} state={self.state}")
        if self._start_pending:
            _ptt_trace("PTT_START_REJECTED_PENDING")
            return False
        if not self.available:
            _ptt_trace("PTT_BRIDGE_START_REJECT reason=unavailable")
            return False
        if self.state not in (VoiceState.IDLE.value, VoiceState.ERROR.value):
            _ptt_trace(f"PTT_BRIDGE_START_REJECT reason=busy state={self.state}")
            return False
        self._start_pending = True
        self._stop_pending = False
        self._cancel_pending = False
        if not self._thread.isRunning():
            _ptt_trace("PTT_THREAD_START")
            self._thread.start()
        QMetaObject.invokeMethod(self._worker, "start", Qt.QueuedConnection)
        return True

    @Slot(result=bool)
    def stopListening(self):
        _ptt_trace(f"PTT_BRIDGE_STOP_REQUEST thread_running={self._thread.isRunning()} state={self.state}")
        if self._start_pending:
            self._stop_pending = True
            _ptt_trace("PTT_STOP_REMEMBERED_PENDING")
        elif self._thread.isRunning() and self.state == VoiceState.LISTENING.value:
            QMetaObject.invokeMethod(self._worker, "stop", Qt.QueuedConnection)
        return True

    @Slot()
    def cancel(self):
        _ptt_trace(f"PTT_BRIDGE_CANCEL_REQUEST thread_running={self._thread.isRunning()} state={self.state}")
        if self._start_pending:
            self._cancel_pending = True
            self._stop_pending = False
            _ptt_trace("PTT_CANCEL_REMEMBERED_PENDING")
        elif self._thread.isRunning():
            QMetaObject.invokeMethod(self._worker, "cancel", Qt.QueuedConnection)

    @Slot(bool)
    def _start_completed(self, accepted: bool):
        self._start_pending = False
        if self._cancel_pending:
            self._cancel_pending = False
            QMetaObject.invokeMethod(self._worker, "cancel", Qt.QueuedConnection)
        elif self._stop_pending and accepted:
            self._stop_pending = False
            QMetaObject.invokeMethod(self._worker, "stop", Qt.QueuedConnection)
        else:
            self._stop_pending = False

    @Slot(str)
    def diagnosticTrace(self, marker: str):
        _ptt_trace(str(marker))

    @Slot(str, result=bool)
    def injectTranscriptForDiagnostics(self, text):
        """Inject one transcript through the production-correlated path.

        This is deliberately inert unless the explicit PTT diagnostics flag is
        enabled.  It never opens audio and emits the same signal used by the
        real STT worker, allowing a test harness to exercise the real QML and
        local-action boundary without bypassing routing or persistence.
        """
        if os.environ.get("AURA_PTT_DIAGNOSTICS") != "1":
            return False
        value = str(text or "").strip()
        if not value:
            return False
        request_id = str(uuid4())
        self.controller.state = VoiceState.THINKING
        self._state_from_worker(VoiceState.THINKING.value)
        _ptt_trace(f"VOICE_LOCAL_TRANSCRIPT_INJECTED voice_request_id={request_id}")
        self.localTranscriptReady.emit(value, request_id)
        return True

    @Slot(result="QVariantList")
    def inputCapabilities(self):
        """Report input capability without opening an audio stream."""
        try:
            return self.controller.audio.capabilities() if self.controller.audio else []
        except Exception as exc:
            _ptt_trace(f"PTT_AUDIO_CAPABILITY_ERROR type={type(exc).__name__}")
            return []

    @Slot()
    def stopSpeaking(self):
        _voice_trace("VOICE_STOP_UI_REQUEST")
        _voice_trace("VOICE_STOP_BRIDGE_REQUEST")
        _ptt_trace("VOICE_STOP_SPEAKING_REQUEST")
        self._playback_stop.set()
        _voice_trace("VOICE_STOP_PLAYBACK_CALL")
        if self.state == VoiceState.SPEAKING.value:
            self._player.stop()
            self._finish_playback(True)
        _voice_trace("VOICE_STOP_PLAYBACK_RESULT")
        self.controller.stop_speaking()
        if self._thread.isRunning(): QMetaObject.invokeMethod(self._worker, "shutdown", Qt.QueuedConnection)

    @Slot(result="QVariantList")
    def listInputDevices(self):
        try:
            return SoundDeviceAudioInput.list_input_devices()
        except RuntimeError:
            return []

    def close(self):
        self._playback_stop.set()
        if self.state == VoiceState.SPEAKING.value:
            self._player.stop(); self._finish_playback(True)
        if self._thread.isRunning():
            QMetaObject.invokeMethod(self._worker, "shutdown", Qt.QueuedConnection)
            self._thread.quit(); self._thread.wait(2000)

