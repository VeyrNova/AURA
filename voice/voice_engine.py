"""High-level voice facade used by AURA Core and the Qt UI (v0.5.2)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, replace

from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.microphone import MicrophoneRecorder
from voice.hybrid_stt import HybridSpeechToText
from voice.text_to_speech import PiperTTS, PiperPreparedSegment
from voice.voice_profile import VoiceProfile, VoiceProfileStore
from voice.xtts_tts import XTTSTTS, XTTSPreparedSegment
from voice.elevenlabs_tts import ElevenLabsTTS, ElevenLabsVoice
from voice.gradium_tts import GradiumTTS, GradiumVoice
from voice.resemble_tts import ResembleTTS, ResembleVoice
from voice.chatterbox_tts import ChatterboxTTS

logger = logging.getLogger("aura.voice.engine")


@dataclass(frozen=True)
class VoiceStatus:
    enabled: bool
    microphone_dependency: bool
    microphone_device_ready: bool
    microphone_device: str
    stt_dependency: bool
    stt_model_ready: bool
    tts_dependency: bool
    tts_model_ready: bool
    input_ready: bool
    output_ready: bool
    tts_engine: str = "none"
    tts_voice: str = ""
    fallback_active: bool = False
    last_engine_used: str = ""
    last_error: str = ""

    @property
    def fully_ready(self) -> bool:
        return self.input_ready and self.output_ready


class RealtimeXTTSVoiceSession:
    """Turn-wide XTTS session with independent synthesis and playback stages."""

    def __init__(self, backend: XTTSTTS, *, fallback_active: bool = False):
        self.backend = backend
        self.fallback_active = bool(fallback_active)
        self.stream_state: dict = {}
        self.model_load_seconds = float(self.backend.begin_realtime_pipeline())

    @property
    def device(self) -> str:
        return str(getattr(self.backend, "_device", "?"))

    def synthesize(self, text: str, *, index: int) -> XTTSPreparedSegment:
        return self.backend.synthesize_realtime_segment(text, index=index)

    def play(self, segment: XTTSPreparedSegment) -> float:
        return float(self.backend.play_realtime_segment(segment, self.stream_state))

    def cancel(self) -> None:
        self.backend.stop()

    def close(self) -> None:
        self.backend.end_realtime_pipeline(self.stream_state)


class RealtimePiperVoiceSession:
    """Turn-wide Piper session using native PCM chunk streaming."""

    def __init__(self, backend: PiperTTS, *, fallback_active: bool = False):
        self.backend = backend
        self.fallback_active = bool(fallback_active)
        self.stream_state: dict = {}
        self.model_load_seconds = float(self.backend.begin_realtime_pipeline())

    @property
    def device(self) -> str:
        return "cpu"

    def synthesize(self, text: str, *, index: int) -> PiperPreparedSegment:
        # Preparation stays intentionally light. Native Piper synthesis happens
        # lazily in play(), where each generated PCM chunk is written at once.
        return self.backend.prepare_realtime_segment(text, index=index)

    def play(self, segment: PiperPreparedSegment) -> float:
        return float(self.backend.play_realtime_segment(segment, self.stream_state))

    def cancel(self) -> None:
        self.backend.stop()

    def close(self) -> None:
        self.backend.end_realtime_pipeline(self.stream_state)


class VoiceEngine:
    def __init__(self):
        self.recorder = MicrophoneRecorder(
            sample_rate=settings.MIC_SAMPLE_RATE,
            channels=settings.MIC_CHANNELS,
            max_seconds=settings.MIC_MAX_SECONDS,
            min_seconds=settings.MIC_MIN_SECONDS,
            requested_device=settings.MIC_DEVICE,
        )
        self.stt = HybridSpeechToText()
        self.profile_store = VoiceProfileStore()
        self.profile = self.profile_store.load()
        # RC3.2: the UI may bind a live PCM amplitude callback before XTTS is
        # loaded. Keep the callback on the facade so backend reloads preserve it.
        self._visual_amplitude_callback = None
        self._apply_local_first_runtime_profile()
        self.tts = self._build_tts(self.profile.engine)
        self.cloud_fallback_tts = self._build_cloud_fallback()
        self.fallback_tts = self._build_tts(self.profile.fallback_engine) if self.profile.fallback_engine != self.profile.engine else None
        self._last_fallback_active = False
        self._last_engine_used = ""
        self._last_tts_error = ""
        # Runtime pause is owned by AuraCore/UI, not by the global Settings
        # singleton. Standalone VoiceEngine diagnostics/tests therefore retain
        # normal backend semantics even when FAST_TEXT_TEST_MODE is the app default.
        self._runtime_paused = False

    def _apply_local_first_runtime_profile(self) -> None:
        """Promote explicitly-enabled CUDA XTTS to runtime primary voice.

        Existing cloud selection is preserved as the secondary fallback. This is
        an in-memory migration only; the user can still disable local-first or
        explicitly choose another engine later from settings.
        """
        if not (settings.XTTS_LOCAL_FIRST_ENABLED and settings.XTTS_ALLOW_CUDA and str(settings.XTTS_DEVICE).strip().lower() == "cuda"):
            return
        current = str(getattr(self.profile, "engine", "") or "").strip().lower()
        if current in {"gradium", "elevenlabs", "resemble"}:
            self.profile.cloud_fallback_engine = current
            self.profile.engine = "xtts"
            self.profile.fallback_engine = "piper"
            logger.info("XTTS local-first runtime promoted cloud_fallback=%s", current)
        elif current == "xtts" and not str(getattr(self.profile, "cloud_fallback_engine", "") or "").strip():
            self.profile.cloud_fallback_engine = settings.XTTS_LOCAL_FIRST_CLOUD_FALLBACK

    def _build_cloud_fallback(self):
        engine = str(getattr(self.profile, "cloud_fallback_engine", "") or "none").strip().lower()
        if engine == self.profile.engine or engine == "none":
            return None
        backend = self._build_tts(engine)
        return backend if backend is not None else None

    def _fallback_candidates(self):
        seen = {id(self.tts)}
        for backend in (getattr(self, "cloud_fallback_tts", None), self.fallback_tts):
            if backend is not None and id(backend) not in seen:
                seen.add(id(backend))
                yield backend

    def _bind_visual_amplitude_backend(self, backend) -> bool:
        """Best-effort bind of the UI live waveform callback to one TTS backend."""
        binder = getattr(backend, "set_visual_amplitude_callback", None)
        if not callable(binder):
            return False
        try:
            binder(self._visual_amplitude_callback)
            return True
        except Exception:
            logger.debug("Voice visual amplitude backend bind ignored", exc_info=True)
            return False

    def set_visual_amplitude_callback(self, callback) -> bool:
        """Bind a thread-safe UI relay for real playback amplitude.

        The callback is optional and never participates in speech availability.
        Keeping it on VoiceEngine fixes the RC3.1 facade mismatch where the UI
        expected this method but the facade did not expose it.
        """
        self._visual_amplitude_callback = callback if callable(callback) else None
        bound = self._bind_visual_amplitude_backend(self.tts)
        for backend in self._fallback_candidates():
            bound = self._bind_visual_amplitude_backend(backend) or bound
        return bound

    def set_runtime_paused(self, paused: bool) -> None:
        self._runtime_paused = bool(paused)
        if self._runtime_paused:
            try:
                self.stop_speaking()
            except Exception:
                logger.debug("Pause audio: stop_speaking ignoré", exc_info=True)
            try:
                self.cancel_listening()
            except Exception:
                logger.debug("Pause audio: cancel_listening ignoré", exc_info=True)

    @property
    def runtime_paused(self) -> bool:
        return bool(self._runtime_paused)

    def _build_tts(self, engine: str):
        engine = (engine or "none").lower()
        if engine == "xtts":
            return XTTSTTS(self.profile)
        if engine == "piper":
            return PiperTTS()
        if engine == "elevenlabs":
            return ElevenLabsTTS(self.profile)
        if engine == "gradium":
            return GradiumTTS(self.profile)
        if engine == "resemble":
            return ResembleTTS(self.profile)
        if engine == "chatterbox":
            return ChatterboxTTS(self.profile)
        return None

    def reload_tts(self, profile: VoiceProfile | None = None) -> VoiceProfile:
        new_profile = self.profile_store.save(profile) if profile is not None else self.profile_store.load()

        # v0.7.1.3.5.5: settings previews save the profile before every test.
        # Rebuilding Gradium here destroyed the retained WebSocket, so every
        # preview paid another TLS/WS handshake and logged reused=False. Preserve
        # the backend when Gradium remains selected; its per-request setup frame
        # safely carries the current voice/model.
        if isinstance(self.tts, GradiumTTS) and str(new_profile.engine).casefold() == "gradium":
            self.profile = new_profile
            self.tts.update_profile(new_profile)
            if str(new_profile.fallback_engine).casefold() == "piper":
                if not isinstance(self.fallback_tts, PiperTTS):
                    self.fallback_tts = PiperTTS()
            elif str(new_profile.fallback_engine).casefold() == "gradium":
                self.fallback_tts = None
            else:
                self.fallback_tts = self._build_tts(new_profile.fallback_engine)
            self.cloud_fallback_tts = self._build_cloud_fallback()
            self._last_fallback_active = False
            self._last_engine_used = ""
            self._last_tts_error = ""
            self._bind_visual_amplitude_backend(self.tts)
            for backend in self._fallback_candidates():
                self._bind_visual_amplitude_backend(backend)
            logger.info("Gradium backend conservé après mise à jour du profil; WebSocket réutilisable")
            return self.profile

        self.stop_speaking()
        self.profile = new_profile
        self.tts = self._build_tts(self.profile.engine)
        self.cloud_fallback_tts = self._build_cloud_fallback()
        self.fallback_tts = self._build_tts(self.profile.fallback_engine) if self.profile.fallback_engine != self.profile.engine else None
        self._last_fallback_active = False
        self._last_engine_used = ""
        self._last_tts_error = ""
        self._bind_visual_amplitude_backend(self.tts)
        for backend in self._fallback_candidates():
            self._bind_visual_amplitude_backend(backend)
        return self.profile

    @staticmethod
    def _tts_dependency(tts) -> bool:
        return bool(tts and tts.dependency_available())

    @staticmethod
    def _tts_model_ready(tts) -> bool:
        return bool(tts and tts.model_ready())

    @staticmethod
    def _tts_available(tts) -> bool:
        return bool(tts and tts.is_available())

    def _output_backend(self):
        if self._tts_available(self.tts):
            return self.tts, False
        for backend in self._fallback_candidates():
            if self._tts_available(backend):
                return backend, True
        return None, False

    def refresh_microphone_detection(self, *, reinitialize_portaudio: bool = False) -> VoiceStatus:
        """Force a passive microphone rediscovery, then return fresh status.

        This never starts capture. RC3.1 uses it only from the UI recovery timer
        and performs at most one guarded PortAudio cache reinitialization.
        """
        try:
            self.recorder.refresh_device_state(reinitialize_portaudio=bool(reinitialize_portaudio))
        except Exception as exc:
            logger.warning("Microphone refresh request failed: %s", type(exc).__name__)
        return self.status()

    def status(self) -> VoiceStatus:
        # v0.7.0.15.6.12.1: Fast Text Test Mode is a real text-only runtime
        # state. Do not probe devices/backends and do not advertise voice-ready
        # capabilities while the user intentionally paused audio.
        if self._runtime_paused:
            return VoiceStatus(
                enabled=False,
                microphone_dependency=False,
                microphone_device_ready=False,
                microphone_device="Audio suspendu · mode test rapide",
                stt_dependency=False,
                stt_model_ready=False,
                tts_dependency=False,
                tts_model_ready=False,
                input_ready=False,
                output_ready=False,
                tts_engine="paused",
                tts_voice="",
                fallback_active=False,
                last_engine_used="",
                last_error="",
            )
        mic_dep = self.recorder.dependencies_available()
        mic_device_ready = bool(mic_dep and self.recorder.is_available())
        mic_device = self.recorder.device_label() if mic_dep else "Dépendance microphone absente"
        stt_dep = self.stt.dependency_available()
        stt_model = self.stt.model_ready()
        backend, fallback_active = self._output_backend()
        enabled = bool(settings.VOICE_ENABLED)
        primary_dep = self._tts_dependency(self.tts)
        primary_model = self._tts_model_ready(self.tts)
        voice_label = getattr(backend, "voice_label", "Piper · " + settings.TTS_VOICE) if backend else "Indisponible"
        engine_label = (
            "xtts" if isinstance(backend, XTTSTTS)
            else "piper" if isinstance(backend, PiperTTS)
            else "elevenlabs" if isinstance(backend, ElevenLabsTTS)
            else "gradium" if isinstance(backend, GradiumTTS)
            else "resemble" if isinstance(backend, ResembleTTS)
            else "chatterbox" if isinstance(backend, ChatterboxTTS)
            else "none"
        )
        return VoiceStatus(
            enabled=enabled,
            microphone_dependency=mic_dep,
            microphone_device_ready=mic_device_ready,
            microphone_device=mic_device,
            stt_dependency=stt_dep,
            stt_model_ready=stt_model,
            tts_dependency=primary_dep,
            tts_model_ready=primary_model,
            input_ready=enabled and mic_dep and mic_device_ready and stt_dep and stt_model,
            output_ready=enabled and backend is not None,
            tts_engine=engine_label,
            tts_voice=voice_label,
            fallback_active=bool(fallback_active or self._last_fallback_active),
            last_engine_used=self._last_engine_used,
            last_error=self._last_tts_error,
        )

    def warmup(self) -> None:
        if self._runtime_paused:
            logger.info("FAST_TEXT_TEST_MODE: voice warmup skipped")
            return
        if not settings.VOICE_PRELOAD:
            return
        if settings.RESOURCE_GUARDIAN_ENABLED and not settings.RESOURCE_ALLOW_HEAVY_PRELOAD:
            logger.info("Prechargement vocal lourd ignore par Resource Guardian")
            return
        self.stt.warmup()
        backend, _ = self._output_backend()
        if backend is not None:
            backend.warmup()

    def start_listening(self) -> None:
        if self._runtime_paused:
            raise RuntimeError("Audio suspendu pendant le mode test rapide.")
        self.stop_speaking()  # push-to-talk always wins
        self.recorder.start()

    def stop_listening(self):
        return self.recorder.stop()

    def cancel_listening(self) -> None:
        self.recorder.cancel()

    def transcribe(self, audio) -> str:
        if self._runtime_paused:
            raise RuntimeError("STT suspendu pendant le mode test rapide.")
        return self.stt.transcribe(audio)

    def output_backend_kind(self) -> str:
        backend, fallback_active = self._output_backend()
        if isinstance(backend, ElevenLabsTTS):
            return "elevenlabs"
        if isinstance(backend, GradiumTTS):
            return "gradium"
        if isinstance(backend, ResembleTTS):
            return "resemble"
        if isinstance(backend, ChatterboxTTS):
            return "chatterbox"
        if isinstance(backend, XTTSTTS):
            return "xtts"
        if isinstance(backend, PiperTTS):
            return "fallback" if fallback_active else "piper"
        return "none"

    def elevenlabs_configured(self) -> bool:
        return bool(settings.ELEVENLABS_ENABLED and settings.ELEVENLABS_API_KEY)

    def available_elevenlabs_voices(self, *, force_refresh: bool = False) -> tuple[ElevenLabsVoice, ...]:
        return ElevenLabsTTS.list_voices(force_refresh=force_refresh)

    def preview_elevenlabs_voice(self, voice_id: str, voice_name: str, text: str):
        voice_id = str(voice_id or "").strip()
        if not voice_id:
            raise SpeechSynthesisUnavailableError("Aucune voix ElevenLabs sélectionnée.")
        temp_profile = replace(
            self.profile,
            engine="elevenlabs",
            fallback_engine="piper",
            elevenlabs_voice_id=voice_id,
            elevenlabs_voice_name=str(voice_name or "").strip(),
        ).normalized()
        return ElevenLabsTTS(temp_profile).speak(text)


    def gradium_configured(self) -> bool:
        return bool(settings.GRADIUM_ENABLED and settings.GRADIUM_API_KEY)

    def available_gradium_voices(self, *, force_refresh: bool = False) -> tuple[GradiumVoice, ...]:
        return GradiumTTS.list_voices(force_refresh=force_refresh)

    def resemble_configured(self) -> bool:
        return bool(settings.RESEMBLE_ENABLED and settings.RESEMBLE_API_KEY)

    def available_resemble_voices(self, *, force_refresh: bool = False) -> tuple[ResembleVoice, ...]:
        return ResembleTTS.list_voices(force_refresh=force_refresh)

    def available_xtts_speakers(self) -> tuple[str, ...]:
        backend = self.tts if isinstance(self.tts, XTTSTTS) else (self.fallback_tts if isinstance(self.fallback_tts, XTTSTTS) else None)
        if backend is None:
            # The lab must still be usable when the current selected engine is Piper.
            backend = XTTSTTS(replace(self.profile, engine="xtts", xtts_mode="preset"))
        return backend.available_speakers()

    def preview_xtts_speaker(self, speaker: str, text: str, *, fast: bool = True):
        """Preview one XTTS preset without mutating AURA's persisted voice profile."""
        speaker = (speaker or "").strip()
        if not speaker:
            raise SpeechSynthesisUnavailableError("Aucune voix XTTS sélectionnée.")
        temp_profile = replace(
            self.profile,
            engine="xtts",
            xtts_mode="preset",
            xtts_preset=speaker,
        ).normalized()
        preview = XTTSTTS(temp_profile)
        return preview.speak_preview(text, fast=fast)


    def xtts_runtime_info(self):
        backend = self.tts if isinstance(self.tts, XTTSTTS) else (self.fallback_tts if isinstance(self.fallback_tts, XTTSTTS) else None)
        if backend is None:
            backend = XTTSTTS(replace(self.profile, engine="xtts", xtts_mode="preset"))
        return backend.runtime_info(load=True)

    def xtts_model_loaded(self) -> bool:
        return XTTSTTS.shared_model_loaded()

    def warmup_xtts_only(self) -> bool:
        """Load the configured XTTS backend without preloading STT/Piper."""
        backend = self.tts if isinstance(self.tts, XTTSTTS) else (
            self.fallback_tts if isinstance(self.fallback_tts, XTTSTTS) else None
        )
        if backend is None or not backend.is_available():
            return False
        backend.warmup()
        return True

    def warmup_xtts_native_silent(self) -> dict:
        """Run one silent native-stream inference to pay the first-turn CUDA warmup."""
        backend = self.tts if isinstance(self.tts, XTTSTTS) else None
        if backend is None or not backend.is_available():
            return {"ok": False, "reason": "xtts-primary-unavailable"}
        return backend.native_silent_warmup(settings.XTTS_LOCAL_FIRST_WARMUP_TEXT)

    def warmup_piper_fallback(self) -> bool:
        """Preload the lightweight CPU fallback without touching CUDA/XTTS."""
        candidates = (self.tts, self.fallback_tts)
        backend = next((item for item in candidates if isinstance(item, PiperTTS)), None)
        if backend is None or not backend.is_available():
            return False
        backend.warmup()
        return True

    def probe_xtts_inference(self, text: str = "Prêt.") -> dict:
        """Run one real XTTS inference without playback for CUDA validation.

        The generated WAV is deleted immediately. This is deliberately not a
        speech path and never falls back to Piper: callers need an honest XTTS
        success/failure signal for the hardware trial.
        """
        backend = self.tts if isinstance(self.tts, XTTSTTS) else (
            self.fallback_tts if isinstance(self.fallback_tts, XTTSTTS) else None
        )
        if backend is None or not backend.is_available():
            raise SpeechSynthesisUnavailableError("XTTS indisponible pour le probe d'inférence.")
        prepared = backend.synthesize_realtime_segment(str(text or "Prêt."), index=0)
        try:
            info = backend.runtime_info(load=False)
            return {
                "device": prepared.device,
                "synthesis_seconds": float(prepared.synthesis_seconds),
                "model_load_seconds": float(prepared.model_load_seconds),
                "text_chars": int(prepared.text_chars),
                "cuda_allocated_mb": float(getattr(info, "allocated_mb", 0.0) or 0.0),
                "cuda_reserved_mb": float(getattr(info, "reserved_mb", 0.0) or 0.0),
                "cuda_total_mb": float(getattr(info, "total_mb", 0.0) or 0.0),
                "gpu_name": str(getattr(info, "gpu_name", "") or ""),
            }
        finally:
            try:
                prepared.wav_path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Suppression WAV probe XTTS ignorée", exc_info=True)

    def release_xtts_model(self) -> bool:
        return XTTSTTS.release_shared_model()

    def release_stt_model(self) -> bool:
        return self.stt.release_model()

    def release_heavy_models(self) -> None:
        self.stop_speaking()
        self.release_xtts_model()
        self.release_stt_model()

    def open_realtime_voice_session(self, *, force_fallback: bool = False):
        """Open the best safe realtime TTS session, including Piper fallback."""
        if force_fallback:
            if self._tts_available(self.fallback_tts):
                backend, fallback_active = self.fallback_tts, True
            else:
                raise SpeechSynthesisUnavailableError(
                    "Resource Guardian a bloqué XTTS et aucun moteur de secours léger n'est disponible."
                )
        else:
            backend, fallback_active = self._output_backend()
        if backend is None:
            raise SpeechSynthesisUnavailableError("Aucun moteur vocal local n'est disponible.")
        self._last_fallback_active = bool(fallback_active)
        self._last_tts_error = ""
        if isinstance(backend, XTTSTTS):
            self._last_engine_used = "xtts"
            return RealtimeXTTSVoiceSession(backend, fallback_active=fallback_active)
        if isinstance(backend, PiperTTS) and settings.PIPER_STREAMING_ENABLED:
            self._last_engine_used = "piper"
            return RealtimePiperVoiceSession(backend, fallback_active=fallback_active)
        return None

    def open_realtime_xtts_session(self, *, force_fallback: bool = False) -> RealtimeXTTSVoiceSession | None:
        """Return a pipelined XTTS session, or None for non-XTTS fallback backends."""
        if force_fallback:
            if self._tts_available(self.fallback_tts):
                backend, fallback_active = self.fallback_tts, True
            else:
                raise SpeechSynthesisUnavailableError(
                    "Resource Guardian a bloqué XTTS et aucun moteur de secours léger n'est disponible."
                )
        else:
            backend, fallback_active = self._output_backend()
        if backend is None:
            raise SpeechSynthesisUnavailableError("Aucun moteur vocal local n'est disponible.")
        if not isinstance(backend, XTTSTTS):
            return None
        self._last_fallback_active = bool(fallback_active)
        self._last_engine_used = "xtts"
        self._last_tts_error = ""
        return RealtimeXTTSVoiceSession(backend, fallback_active=fallback_active)

    def speak(self, text: str, *, allow_fallback: bool = True, force_fallback: bool = False):
        if self._runtime_paused:
            raise SpeechSynthesisUnavailableError("TTS suspendu pendant le mode test rapide.")
        if force_fallback:
            if self._tts_available(self.fallback_tts):
                backend, fallback_active = self.fallback_tts, True
            else:
                raise SpeechSynthesisUnavailableError(
                    "Resource Guardian a bloqué XTTS et aucun moteur de secours léger n'est disponible."
                )
        else:
            backend, fallback_active = self._output_backend()
        if backend is None:
            raise SpeechSynthesisUnavailableError("Aucun moteur vocal local n'est disponible.")
        self._last_fallback_active = fallback_active
        self._last_tts_error = ""
        try:
            result = backend.speak(text)
            self._last_engine_used = (
                "xtts" if isinstance(backend, XTTSTTS)
                else "elevenlabs" if isinstance(backend, ElevenLabsTTS)
                else "gradium" if isinstance(backend, GradiumTTS)
                else "resemble" if isinstance(backend, ResembleTTS)
                else "chatterbox" if isinstance(backend, ChatterboxTTS)
                else "piper"
            )
            self._last_fallback_active = fallback_active
            return result
        except SpeechSynthesisUnavailableError as exc:
            self._last_tts_error = str(exc)
            if allow_fallback and not fallback_active:
                for candidate in self._fallback_candidates():
                    if not self._tts_available(candidate):
                        continue
                    label = (
                        "gradium" if isinstance(candidate, GradiumTTS) else
                        "elevenlabs" if isinstance(candidate, ElevenLabsTTS) else
                        "resemble" if isinstance(candidate, ResembleTTS) else
                        "piper" if isinstance(candidate, PiperTTS) else "fallback"
                    )
                    logger.warning("Moteur TTS principal en échec, bascule vers %s: %s", label, exc)
                    try:
                        result = candidate.speak(text)
                        self._last_fallback_active = True
                        self._last_engine_used = label
                        return result
                    except SpeechSynthesisUnavailableError as fallback_exc:
                        self._last_tts_error = str(fallback_exc)
                        logger.warning("Fallback TTS %s indisponible: %s", label, fallback_exc)
            raise

    def test_speak(self, text: str):
        """Strict voice preview: never hide an XTTS error behind Piper."""
        return self.speak(text, allow_fallback=False)

    def stop_speaking(self) -> None:
        for backend in (self.tts, getattr(self, "cloud_fallback_tts", None), self.fallback_tts):
            if backend is not None:
                try:
                    backend.stop()
                except Exception:
                    logger.debug("Arret TTS ignore", exc_info=True)
# ---------------------------------------------------------------------------
# AURA P0.2.1 VOICE AMPLITUDE PROXY ROBUST
# Restore/override the public VoiceEngine -> XTTS visual amplitude bridge.
# ---------------------------------------------------------------------------
def _aura_p021_set_visual_amplitude_callback(self, callback) -> None:
    from voice import xtts_tts as _aura_xtts
    setter = getattr(_aura_xtts, "set_visual_amplitude_callback", None)
    if not callable(setter):
        raise RuntimeError(
            "AURA P0.2.1: voice.xtts_tts.set_visual_amplitude_callback indisponible"
        )
    setter(callback)
    logger.info(
        "AURA P0.2.1 amplitude proxy bound callback=%s",
        callback is not None,
    )


# Override any stale/missing implementation from an older VoiceEngine revision.
VoiceEngine.set_visual_amplitude_callback = _aura_p021_set_visual_amplitude_callback
logger.info(
    "AURA P0.2.1 voice amplitude proxy active target=voice.xtts_tts.set_visual_amplitude_callback"
)
# ---------------------------------------------------------------------------
# AURA P0.2.3 ADAPTIVE XTTS AMPLITUDE RESOLVER
# Resolve the *actual live XTTS backend* used by this VoiceEngine instance.
# Supports both historical module-level setter and newer backend-instance setter.
# No synthesis/playback/performance path is changed.
# ---------------------------------------------------------------------------
def _aura_p023_set_visual_amplitude_callback(self, callback) -> None:
    import importlib as _importlib

    errors=[]
    visited=set()

    def _try_target(obj, label):
        if obj is None:
            return False
        ident=id(obj)
        if ident in visited:
            return False
        visited.add(ident)
        try:
            setter=getattr(obj, "set_visual_amplitude_callback", None)
        except Exception as exc:
            errors.append(f"{label}.getattr:{type(exc).__name__}:{exc}")
            return False
        if callable(setter):
            try:
                setter(callback)
                logger.info(
                    "AURA P0.2.3 amplitude proxy bound callback=%s target=%s type=%s",
                    callback is not None, label, type(obj).__name__,
                )
                return True
            except Exception as exc:
                errors.append(f"{label}.setter:{type(exc).__name__}:{exc}")
        return False

    # 1) Known VoiceEngine backend slots (historically self.tts).
    preferred=("tts","_tts","tts_backend","_tts_backend","backend","_backend",
               "fallback_tts","cloud_fallback_tts")
    for name in preferred:
        try:
            obj=getattr(self,name,None)
        except Exception:
            obj=None
        if _try_target(obj, f"voice_engine.{name}"):
            return

    # 2) Bounded inspection of direct VoiceEngine attributes.
    try:
        attrs=vars(self)
    except Exception:
        attrs={}
    for name,obj in list(attrs.items()):
        low=str(name).lower()
        if not any(tok in low for tok in ("tts","voice","backend","engine")):
            continue
        if _try_target(obj, f"voice_engine.{name}"):
            return

        # One nested level only; avoids recursive graph walking.
        try:
            nested=vars(obj)
        except Exception:
            nested={}
        for subname,subobj in list(nested.items()):
            slow=str(subname).lower()
            if not any(tok in slow for tok in ("tts","xtts","backend","engine")):
                continue
            if _try_target(subobj, f"voice_engine.{name}.{subname}"):
                return

    # 3) Historical module-level API.
    try:
        mod=_importlib.import_module("voice.xtts_tts")
        setter=getattr(mod,"set_visual_amplitude_callback",None)
        if callable(setter):
            setter(callback)
            logger.info(
                "AURA P0.2.3 amplitude proxy bound callback=%s target=voice.xtts_tts.module",
                callback is not None,
            )
            return
    except Exception as exc:
        errors.append(f"module.setter:{type(exc).__name__}:{exc}")

    # 4) Historical callback storage fallback. This is equivalent to the old
    # module setter when that thin wrapper was removed but its emitter storage
    # remains present.
    try:
        mod=_importlib.import_module("voice.xtts_tts")
        if hasattr(mod,"_visual_amplitude_callback"):
            lock=getattr(mod,"_visual_amplitude_lock",None)
            if lock is not None:
                with lock:
                    setattr(mod,"_visual_amplitude_callback",callback)
            else:
                setattr(mod,"_visual_amplitude_callback",callback)
            logger.info(
                "AURA P0.2.3 amplitude proxy bound callback=%s target=voice.xtts_tts._visual_amplitude_callback",
                callback is not None,
            )
            return
    except Exception as exc:
        errors.append(f"module.storage:{type(exc).__name__}:{exc}")

    detail=" | ".join(errors[-8:]) if errors else "no compatible target found"
    logger.warning("AURA P0.2.3 amplitude resolver failed: %s", detail)
    raise RuntimeError("AURA P0.2.3: aucun endpoint amplitude XTTS compatible trouvé: "+detail)


# Override P0.2.1 / any stale implementation with the adaptive runtime resolver.
VoiceEngine.set_visual_amplitude_callback = _aura_p023_set_visual_amplitude_callback
logger.info(
    "AURA P0.2.3 adaptive amplitude resolver active "
    "strategy=live-backend>nested-backend>module-setter>historical-storage"
)
# ---------------------------------------------------------------------------
# AURA P0.2.4 NATIVE PCM BRIDGE RESTORE
# ---------------------------------------------------------------------------
def _aura_p024_native_visual_amplitude_callback(self, callback) -> bool:
    self._visual_amplitude_callback = callback if callable(callback) else None
    bound = self._bind_visual_amplitude_backend(self.tts)
    for backend in self._fallback_candidates():
        bound = self._bind_visual_amplitude_backend(backend) or bound
    logger.info(
        "AURA P0.2.4 native amplitude facade callback=%s bound=%s primary=%s",
        callback is not None,
        bool(bound),
        type(getattr(self, "tts", None)).__name__,
    )
    return bool(bound)

VoiceEngine.set_visual_amplitude_callback = _aura_p024_native_visual_amplitude_callback
logger.info("AURA P0.2.4 native PCM facade restored contract=bool backend-instance-routing")
