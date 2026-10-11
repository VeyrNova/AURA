from __future__ import annotations

from collections.abc import Callable
from typing import Any

from aura_native.intents.dispatcher import NativeActionDispatcher
from aura_native.intents.router import NativeIntentRouter

from .models import VoiceEvent, VoiceResult, VoiceState
from .providers import AudioInputAdapter, STTProvider, TTSProvider
import os


def _ptt_trace(message: str) -> None:
    if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
        print(message, flush=True)


class VoiceController:
    """Native voice lifecycle with explicit I/O and confirmation boundaries."""

    def __init__(self, *, audio: AudioInputAdapter | None = None,
                 stt: STTProvider | None = None, tts: TTSProvider | None = None,
                 router: NativeIntentRouter | None = None,
                 dispatcher: NativeActionDispatcher | None = None,
                 conversation_fallback: Callable[[str], Any] | None = None,
                 on_event: Callable[[VoiceEvent], None] | None = None) -> None:
        self.audio, self.stt, self.tts = audio, stt, tts
        self.router = router or NativeIntentRouter()
        self.dispatcher = dispatcher or NativeActionDispatcher()
        self.conversation_fallback = conversation_fallback
        self.on_event = on_event
        self.state = VoiceState.IDLE
        self._pending_confirmation: VoiceResult | None = None

    def _emit(self, kind: str, **kwargs: Any) -> None:
        if self.on_event:
            self.on_event(VoiceEvent(kind, self.state, **kwargs))

    def start(self) -> VoiceResult:
        _ptt_trace(f"PTT_CONTROLLER_START state={self.state.value} audio={self.audio is not None}")
        if self.state not in (VoiceState.IDLE, VoiceState.ERROR):
            return VoiceResult(False, self.state, error="voice_busy")
        if self.audio is None:
            self.state = VoiceState.ERROR
            self._emit("error", error="audio_unavailable")
            return VoiceResult(False, self.state, error="audio_unavailable")
        try:
            self.audio.start()
            self.state = VoiceState.LISTENING
            self._emit("started")
            return VoiceResult(True, self.state)
        except Exception as exc:
            self.state = VoiceState.ERROR
            self._emit("error", error="device_unavailable")
            return VoiceResult(False, self.state, error="device_unavailable")

    def stop(self) -> VoiceResult:
        _ptt_trace(f"PTT_CONTROLLER_STOP state={self.state.value}")
        if self.state != VoiceState.LISTENING:
            return VoiceResult(False, self.state, error="not_listening")
        try:
            audio = self.audio.stop() if self.audio else None
            sample_count = 0 if audio is None else int(getattr(audio, "size", len(audio) if hasattr(audio, "__len__") else 0))
            _ptt_trace(f"PTT_CONTROLLER_AUDIO_SAMPLES={sample_count}")
            if sample_count <= 0:
                if not bool(getattr(self.conversation_fallback, "keep_thinking", False)):
                    self.state = VoiceState.IDLE
                self._emit("no_audio", error="no_audio")
                return VoiceResult(False, self.state, error="no_audio")
            if self.stt is None:
                self.state = VoiceState.ERROR
                return VoiceResult(False, self.state, error="stt_unavailable")
            self.state = VoiceState.TRANSCRIBING
            _ptt_trace("PTT_CONTROLLER_STATE state=transcribing")
            self._emit("transcribing")
            _ptt_trace("PTT_STT_REQUEST")
            transcript = str(self.stt.transcribe(audio) or "").strip()
            return self.submit_transcript(transcript)
        except RuntimeError as exc:
            if str(exc) == "NO_AUDIO":
                if not bool(getattr(self.conversation_fallback, "keep_thinking", False)):
                    self.state = VoiceState.IDLE
                self._emit("no_audio", error="no_audio")
                return VoiceResult(False, self.state, error="no_audio")
            self.state = VoiceState.ERROR
            self._emit("error", error="transcription_failed")
            return VoiceResult(False, self.state, error="transcription_failed")
        except Exception:
            self.state = VoiceState.ERROR
            self._emit("error", error="transcription_failed")
            return VoiceResult(False, self.state, error="transcription_failed")

    def cancel(self) -> None:
        if self.audio:
            self.audio.cancel()
        self._pending_confirmation = None
        self.state = VoiceState.IDLE
        self._emit("cancelled")

    def submit_transcript(self, transcript: str) -> VoiceResult:
        text = str(transcript or "").strip()
        _ptt_trace(f"PTT_CONTROLLER_STATE_BEFORE={self.state.value}")
        if not text:
            self.state = VoiceState.IDLE
            self._emit("empty_transcript", error="empty_transcript")
            _ptt_trace(f"PTT_CONTROLLER_STATE_AFTER={self.state.value}")
            return VoiceResult(False, self.state, error="empty_transcript")
        self.state = VoiceState.THINKING
        _ptt_trace("PTT_INTENT_PARSE_BEGIN")
        intent = self.router.parse(text)
        _ptt_trace("PTT_INTENT_PARSE_END")
        _ptt_trace(f"PTT_INTENT_RESULT intent={intent.intent or 'NONE'}")
        for slot_name in ("location", "module"):
            if slot_name in intent.slots:
                _ptt_trace(f"PTT_INTENT_SLOT {slot_name}={intent.slots[slot_name]}")
        if not intent.recognized:
            if self.conversation_fallback:
                _ptt_trace("PTT_CONVERSATION_FALLBACK=true")
                _ptt_trace("PTT_CONVERSATION_REQUEST_BEGIN")
                try:
                    value = self.conversation_fallback(text)
                except Exception:
                    _ptt_trace("PTT_CONVERSATION_REQUEST_ACCEPTED=false")
                    self.state = VoiceState.IDLE
                    return VoiceResult(False, self.state, transcript=text, error="conversation_failed")
                accepted = value is not False
                _ptt_trace(f"PTT_CONVERSATION_REQUEST_ACCEPTED={str(accepted).lower()}")
                if not bool(getattr(self.conversation_fallback, "keep_thinking", False)):
                    self.state = VoiceState.IDLE
                _ptt_trace(f"PTT_CONTROLLER_STATE_AFTER={self.state.value}")
                return VoiceResult(accepted, self.state, transcript=text, message=str(value or ""),
                                   error="conversation_rejected" if not accepted else "")
            _ptt_trace("PTT_CONVERSATION_FALLBACK=false")
            self.state = VoiceState.IDLE
            _ptt_trace(f"PTT_CONTROLLER_STATE_AFTER={self.state.value}")
            return VoiceResult(False, self.state, transcript=text, error="unrecognized")
        # Destructive intents are only inspected here.  Dispatch is deferred
        # until the caller explicitly confirms, so parsing can never mutate.
        dispatched = None
        if not intent.requires_confirmation:
            _ptt_trace("PTT_DISPATCH_BEGIN")
            dispatched = self.dispatcher.dispatch(intent)
            _ptt_trace(f"PTT_DISPATCH_RESULT accepted={str(dispatched.handled).lower()}")
        else:
            _ptt_trace("PTT_DISPATCH_DEFERRED confirmation=true")
        result = VoiceResult(True, self.state, text, intent.intent,
                             intent.requires_confirmation,
                             dispatched.message if dispatched is not None else "")
        if intent.requires_confirmation:
            self._pending_confirmation = result
        else:
            self.state = VoiceState.IDLE
        self._emit("transcript", transcript=text, payload={"intent": intent.intent or ""})
        _ptt_trace(f"PTT_CONTROLLER_STATE_AFTER={self.state.value}")
        return result

    def confirm(self) -> VoiceResult:
        if self._pending_confirmation is None:
            return VoiceResult(False, self.state, error="no_pending_confirmation")
        result = self._pending_confirmation
        self._pending_confirmation = None
        intent = self.router.parse(result.transcript)
        self.dispatcher.dispatch(intent)
        self.state = VoiceState.IDLE
        self._emit("confirmed", transcript=result.transcript,
                   payload={"intent": result.intent or ""})
        return result

    def speak(self, text: str) -> VoiceResult:
        if self.tts is None:
            self.state = VoiceState.ERROR
            return VoiceResult(False, self.state, error="tts_unavailable")
        try:
            self.state = VoiceState.SPEAKING
            self.tts.speak(str(text))
            self.state = VoiceState.IDLE
            return VoiceResult(True, self.state, message=str(text))
        except Exception:
            self.state = VoiceState.ERROR
            return VoiceResult(False, self.state, error="synthesis_failed")

    def stop_speaking(self) -> None:
        if self.tts:
            self.tts.stop()
        self.state = VoiceState.IDLE
