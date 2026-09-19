"""XTTS-v2 backend for AURA v0.7.1.3.6.5.

Preset speakers are resolved from the *installed XTTS model* at runtime. This
prevents AURA from silently testing a stale/invalid speaker name and falling
back to Piper while the UI claims another XTTS voice is active.
"""
from __future__ import annotations

# AURA I18N R2 â€” dynamic XTTS language
import os as _aura_i18n_r2_os

def _aura_i18n_tts_language() -> str:
    raw = str(
        _aura_i18n_r2_os.environ.get("AURA_TTS_LANGUAGE")
        or _aura_i18n_r2_os.environ.get("STT_LANGUAGE")
        or "fr"
    ).strip().lower()
    return "en" if raw.startswith("en") else "fr"


import gc
import importlib.util
import logging
import os
import queue
import re
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.text_to_speech import sanitize_for_speech, strip_terminal_punctuation_for_synthesis
from voice.audio_postprocess import polish_wav_tail
from voice.voice_profile import VoiceProfile

logger = logging.getLogger("aura.voice.xtts")


def _float32_pcm_peak(payload: bytes | bytearray | memoryview | None) -> float:
    """Return a bounded peak estimate for mono float32 PCM.

    Only a small sample of very large packets is inspected. This is visual-only
    telemetry and must remain much cheaper than synthesis/playback.
    """
    if not payload:
        return 0.0
    try:
        values = memoryview(payload).cast("f")
        if not values:
            return 0.0
        step = max(1, len(values) // 384)
        peak = max(abs(float(values[i])) for i in range(0, len(values), step))
        return max(0.0, min(1.0, peak))
    except Exception:
        return 0.0


@dataclass(frozen=True)
class XTTSRuntimeInfo:
    device: str
    gpu_name: str = ""
    allocated_mb: float = 0.0
    reserved_mb: float = 0.0
    total_mb: float = 0.0


@dataclass(frozen=True)
class XTTSSynthesisMetrics:
    device: str
    synthesis_seconds: float
    playback_seconds: float
    total_seconds: float
    text_chars: int
    model_load_seconds: float = 0.0
    time_to_audio_seconds: float = 0.0
    progressive: bool = False
    chunk_count: int = 1
    first_chunk_synthesis_seconds: float = 0.0


@dataclass(frozen=True)
class SpeechChunk:
    text: str
    boundary: str


@dataclass(frozen=True)
class XTTSPreparedSegment:
    """One synthesized realtime segment waiting for ordered playback."""
    wav_path: Path
    device: str
    text_chars: int
    synthesis_seconds: float
    model_load_seconds: float = 0.0
    prepared_at: float = 0.0


class _PersistentAudioSession:
    def __init__(self):
        self.first_audio = threading.Event()
        self.done = threading.Event()
        self.first_audio_at = 0.0
        self.error: BaseException | None = None


class _PersistentAudioBridge:
    """Keep one PortAudio stream hot between XTTS utterances.

    A tiny silence packet is written while idle so Windows/PortAudio does not
    tear the device path down. Speech packets are consumed by the same worker,
    avoiding device-open/start latency on every AURA reply.
    """
    def __init__(self, sd_module, *, samplerate: int, amplitude_callback=None):
        self.sd = sd_module
        self.samplerate = int(samplerate)
        self._amplitude_callback = amplitude_callback if callable(amplitude_callback) else None
        self._last_amplitude_emit = 0.0
        self._queue: queue.Queue[tuple[str, _PersistentAudioSession | None, bytes | None]] = queue.Queue(maxsize=24)
        self._closed = threading.Event()
        self._session_lock = threading.Lock()
        self._stream = self.sd.RawOutputStream(
            samplerate=self.samplerate,
            channels=1,
            dtype='float32',
            blocksize=0,
            latency='low',
        )
        self._stream.start()
        # 20 ms mono float32 silence: short enough to keep bridge latency tiny.
        frames = max(64, int(self.samplerate * 0.020))
        self._silence = b'\x00' * (frames * 4)
        self._worker = threading.Thread(target=self._run, name='aura-xtts-audio-bridge', daemon=True)
        self._worker.start()

    def set_amplitude_callback(self, callback) -> None:
        self._amplitude_callback = callback if callable(callback) else None

    def _emit_amplitude(self, payload: bytes | None = None, *, force: bool = False) -> None:
        callback = self._amplitude_callback
        if callback is None:
            return
        now = time.perf_counter()
        if not force and (now - self._last_amplitude_emit) < (1.0 / 30.0):
            return
        self._last_amplitude_emit = now
        try:
            callback(_float32_pcm_peak(payload))
        except Exception:
            # The callback is UI telemetry only. Never let it affect playback.
            pass

    def _run(self) -> None:
        stream = self._stream
        active: _PersistentAudioSession | None = None
        try:
            while not self._closed.is_set():
                try:
                    kind, session, payload = self._queue.get_nowait()
                except queue.Empty:
                    # Keep the endpoint warm and bounded to ~20 ms scheduling jitter.
                    # Windows/PortAudio may stop the stream during test teardown or
                    # device reconfiguration. An idle keepalive failure must not
                    # generate an unhandled worker traceback. Try one restart, then
                    # retire the bridge quietly so the next speech can recreate it.
                    try:
                        stream.write(self._silence)
                    except Exception as idle_exc:
                        if self._closed.is_set():
                            break
                        try:
                            stream.start()
                            stream.write(self._silence)
                        except Exception:
                            logger.warning(
                                'XTTS persistent audio bridge idle stream stopped; bridge retired: %s',
                                idle_exc,
                            )
                            self._closed.set()
                            break
                    continue
                if kind == 'audio' and session is not None and payload:
                    active = session
                    if not session.first_audio.is_set():
                        session.first_audio_at = time.perf_counter()
                        session.first_audio.set()
                    self._emit_amplitude(payload)
                    # AURA_R23_R5_R2_R1_XTTS_PERSISTENT_EMIT
                    _aura_ref_cb = getattr(self, "_aura_playback_reference_callback", None)
                    if callable(_aura_ref_cb):
                        try:
                            _aura_ref_cb(payload, sample_rate=self.samplerate, channels=1, dtype="float32")
                        except Exception:
                            pass
                    stream.write(payload)
                elif kind == 'end' and session is not None:
                    self._emit_amplitude(None, force=True)
                    session.done.set()
                    active = None
                elif kind == 'close':
                    break
        except BaseException as exc:
            if active is not None:
                active.error = exc
                active.first_audio.set()
                active.done.set()
            logger.exception('XTTS persistent audio bridge worker failed')
        finally:
            self._emit_amplitude(None, force=True)
            try:
                stream.abort()
            except Exception:
                pass
            try:
                stream.close()
            except Exception:
                pass

    def begin(self) -> _PersistentAudioSession:
        self._session_lock.acquire()
        return _PersistentAudioSession()

    def put(self, session: _PersistentAudioSession, payload: bytes) -> None:
        self._queue.put(('audio', session, payload))

    def finish(self, session: _PersistentAudioSession) -> None:
        self._queue.put(('end', session, None))

    def wait(self, session: _PersistentAudioSession, timeout: float = 60.0) -> None:
        if not session.done.wait(timeout=max(1.0, float(timeout))):
            raise SpeechSynthesisUnavailableError('Le pont audio XTTS persistant ne répond plus.')
        if session.error is not None:
            raise session.error

    def end(self) -> None:
        if self._session_lock.locked():
            self._session_lock.release()

    def close(self) -> None:
        if self._closed.is_set():
            return
        self._closed.set()
        try:
            self._queue.put_nowait(('close', None, None))
        except Exception:
            pass
        self._worker.join(timeout=1.0)

    @property
    def alive(self) -> bool:
        return self._worker.is_alive() and not self._closed.is_set()


class XTTSTTS:
    MODEL_NAME = "tts_models/multilingual/multi-dataset/xtts_v2"
    MODEL_CACHE_DIRNAME = "tts_models--multilingual--multi-dataset--xtts_v2"
    REQUIRED_MODEL_FILES = ("config.json", "model.pth", "speakers_xtts.pth", "vocab.json")
    _shared_api = None
    _shared_device = None
    _shared_lock = threading.Lock()
    _shared_inference_lock = threading.Lock()
    _conditioning_cache: dict[tuple[str, str, str, str], tuple[Any, Any]] = {}
    _shared_audio_bridge = None
    _shared_audio_bridge_lock = threading.Lock()

    # AURA_R23_R5_R2_R1_XTTS_REFERENCE_API
    def set_playback_reference_callback(self, callback):
        self._playback_reference_callback = callback if callable(callback) else None
        if not hasattr(self, "_playback_reference_generation"):
            self._playback_reference_generation = 0
        return self._playback_reference_callback is not None

    def _advance_playback_reference_generation(self):
        current = int(getattr(self, "_playback_reference_generation", 0) or 0)
        self._playback_reference_generation = current + 1
        return self._playback_reference_generation

    def _emit_playback_reference(self, payload, *, sample_rate, channels=1, dtype="float32"):
        callback = getattr(self, "_playback_reference_callback", None)
        if not callable(callback) or payload is None:
            return False
        try:
            import time as _aura_r23_time
            callback(bytes(payload), sample_rate=int(sample_rate), channels=max(1, int(channels)), dtype=str(dtype), generation=int(getattr(self, "_playback_reference_generation", 0) or 0), at_monotonic=float(_aura_r23_time.monotonic()))
            return True
        except Exception:
            return False

    def __init__(self, profile: VoiceProfile):
        self.profile = profile.normalized()
        self._device = "cpu"
        self._playback_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._custom_cached = False
        self._visual_amplitude_callback = None
        os.environ.setdefault("TTS_HOME", str(settings.XTTS_HOME))

    def set_visual_amplitude_callback(self, callback) -> None:
        """Bind optional real PCM amplitude telemetry for the AURA waveform."""
        self._visual_amplitude_callback = callback if callable(callback) else None
        bridge = self.__class__._shared_audio_bridge
        setter = getattr(bridge, "set_amplitude_callback", None)
        if callable(setter):
            try:
                setter(self._visual_amplitude_callback)
            except Exception:
                logger.debug("XTTS visual amplitude bridge rebind ignored", exc_info=True)

    def _emit_visual_amplitude(self, payload: bytes | None = None, *, force: bool = False) -> None:
        callback = self._visual_amplitude_callback
        if callback is None:
            return
        try:
            callback(_float32_pcm_peak(payload))
        except Exception:
            pass

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("TTS") is not None and importlib.util.find_spec("torch") is not None

    @staticmethod
    def install_marker() -> Path:
        # Legacy/diagnostic marker only. Real readiness is determined from the
        # Coqui model cache itself because a completed download may exist even
        # if a previous installer run stopped before writing this marker.
        return settings.VOICE_MODEL_DIR / "xtts" / ".installed"

    @classmethod
    def model_cache_candidates(cls) -> tuple[Path, ...]:
        # With AURA's TTS_HOME=<...>/models/voice/coqui, current Coqui versions
        # store named models under TTS_HOME/tts/<normalized-model-name>.
        candidates = [
            settings.XTTS_HOME / "tts" / cls.MODEL_CACHE_DIRNAME,
            # Keep this legacy layout as a compatibility fallback.
            settings.XTTS_HOME / cls.MODEL_CACHE_DIRNAME,
        ]
        return tuple(candidates)

    @classmethod
    def _cache_is_complete(cls, path: Path) -> bool:
        return path.is_dir() and all((path / name).is_file() for name in cls.REQUIRED_MODEL_FILES)

    @classmethod
    def model_cache_dir(cls) -> Path | None:
        for path in cls.model_cache_candidates():
            if cls._cache_is_complete(path):
                return path
        return None

    @classmethod
    def shared_model_loaded(cls) -> bool:
        return cls._shared_api is not None

    @classmethod
    def release_shared_model(cls) -> bool:
        """Drop the shared XTTS model and release unused CUDA cache safely."""
        with cls._shared_lock:
            api = cls._shared_api
            device = cls._shared_device
            cls._shared_api = None
            cls._shared_device = None
            cls._conditioning_cache.clear()
        with cls._shared_audio_bridge_lock:
            bridge = cls._shared_audio_bridge
            cls._shared_audio_bridge = None
        if bridge is not None:
            try:
                bridge.close()
                logger.info("XTTS persistent audio bridge closed")
            except Exception:
                logger.debug("Fermeture pont audio XTTS ignorée", exc_info=True)
        if api is None:
            return False
        try:
            del api
            gc.collect()
            if device == "cuda":
                try:
                    import torch
                    if torch.cuda.is_available():
                        torch.cuda.empty_cache()
                except Exception:
                    logger.debug("Nettoyage cache CUDA XTTS indisponible", exc_info=True)
            logger.info("XTTS partagé libéré (ancien device=%s)", device or "?")
            return True
        except Exception:
            logger.warning("Libération XTTS incomplète", exc_info=True)
            return False

    def model_ready(self) -> bool:
        # Fail-safe: a marker alone is not enough. Verify the actual XTTS
        # checkpoint assets that Coqui needs for inference.
        return self.model_cache_dir() is not None

    def reference_ready(self) -> bool:
        if self.profile.xtts_mode == "preset":
            return bool(self.profile.xtts_preset)
        if not self.profile.xtts_reference_wav:
            return False
        return Path(self.profile.xtts_reference_wav).expanduser().is_file()

    def is_available(self) -> bool:
        return bool(
            settings.VOICE_ENABLED
            and os.name == "nt"
            and self.dependency_available()
            and self.model_ready()
            and self.reference_ready()
        )


    @staticmethod
    def resolve_device(requested: str, allow_cuda: bool, torch_module) -> str:
        requested = (requested or "cpu").strip().lower()
        if requested != "cuda":
            return "cpu"
        if not allow_cuda:
            raise SpeechSynthesisUnavailableError(
                "XTTS CUDA est désactivé par sécurité. Lance XTTS_GPU_PROBE.bat puis active XTTS_ALLOW_CUDA=true si le test réussit."
            )
        if not torch_module.cuda.is_available():
            raise SpeechSynthesisUnavailableError("CUDA n'est pas disponible pour XTTS.")
        return "cuda"

    def runtime_info(self, *, load: bool = True) -> XTTSRuntimeInfo:
        if load:
            self._load_model()
        device = self._device or self.__class__._shared_device or "cpu"
        if device != "cuda":
            return XTTSRuntimeInfo(device="cpu")
        try:
            import torch
            idx = torch.cuda.current_device()
            props = torch.cuda.get_device_properties(idx)
            return XTTSRuntimeInfo(
                device="cuda",
                gpu_name=str(torch.cuda.get_device_name(idx)),
                allocated_mb=torch.cuda.memory_allocated(idx) / (1024 * 1024),
                reserved_mb=torch.cuda.memory_reserved(idx) / (1024 * 1024),
                total_mb=float(props.total_memory) / (1024 * 1024),
            )
        except Exception:
            logger.debug("Statistiques CUDA indisponibles", exc_info=True)
            return XTTSRuntimeInfo(device="cuda")

    @property
    def voice_label(self) -> str:
        if self.profile.xtts_mode == "custom":
            return "XTTS · AURA personnalisée"
        return f"XTTS · {self.profile.xtts_preset}"

    def _load_model(self):
        if self.__class__._shared_api is not None:
            self._device = self.__class__._shared_device or "cpu"
            return self.__class__._shared_api
        with self.__class__._shared_lock:
            if self.__class__._shared_api is not None:
                self._device = self.__class__._shared_device or "cpu"
                return self.__class__._shared_api
            if os.name != "nt":
                raise SpeechSynthesisUnavailableError("XTTS est configuré pour l'installation Windows d'AURA.")
            if not self.dependency_available():
                raise SpeechSynthesisUnavailableError("XTTS n'est pas installé. Lance INSTALL_XTTS.bat.")
            if not self.model_ready():
                raise SpeechSynthesisUnavailableError("Le modèle XTTS n'est pas installé. Lance INSTALL_XTTS.bat.")
            if not self.reference_ready():
                raise SpeechSynthesisUnavailableError("La voix XTTS personnalisée n'a pas de référence WAV valide.")
            try:
                import torch
                from TTS.api import TTS

                # Safety first on Windows: CUDA is never selected implicitly.
                # A GPU/driver problem must not be able to crash the AURA UI just
                # because the voice model is being preloaded or diagnosed.
                self._device = self.resolve_device(settings.XTTS_DEVICE, settings.XTTS_ALLOW_CUDA, torch)
                logger.info("Chargement XTTS device=%s", self._device)
                api = TTS(self.MODEL_NAME, progress_bar=False).to(self._device)
                self.__class__._shared_api = api
                self.__class__._shared_device = self._device
                return api
            except Exception as exc:
                logger.exception("Chargement XTTS impossible")
                raise SpeechSynthesisUnavailableError(
                    "Je n'arrive pas à charger XTTS. Consulte VOICE_DIAGNOSTICS.bat ou les logs."
                ) from exc

    def warmup(self) -> None:
        if self.is_available():
            self._load_model()
            logger.info("XTTS préchargé (%s)", self.voice_label)

    def available_speakers(self) -> tuple[str, ...]:
        """Return the actual preset speaker IDs exposed by this XTTS checkpoint."""
        api = self._load_model()
        speakers = getattr(api, "speakers", None) or ()
        return tuple(str(item) for item in speakers if str(item).strip())

    @staticmethod
    def _xtts_model(api):
        """Return the lower-level XTTS model exposed by the public TTS API."""
        synth = getattr(api, "synthesizer", None)
        model = getattr(synth, "tts_model", None) if synth is not None else None
        if model is None:
            raise SpeechSynthesisUnavailableError(
                "Le modèle XTTS natif n'est pas accessible dans cette installation Coqui."
            )
        return model

    def _conditioning_cache_key(self) -> tuple[str, str, str, str]:
        return (
            self.profile.xtts_mode,
            self.profile.xtts_preset if self.profile.xtts_mode == "preset" else self.profile.xtts_speaker_id,
            self.profile.xtts_reference_wav if self.profile.xtts_mode == "custom" else "",
            _aura_i18n_tts_language(),
        )

    def _native_conditioning(self, api):
        """Resolve and cache XTTS conditioning tensors for native streaming.

        Preset embeddings are already shipped with XTTS. Custom voices compute
        latents once from the reference WAV and reuse them for subsequent turns.
        """
        key = self._conditioning_cache_key()
        if settings.XTTS_CONDITIONING_CACHE_ENABLED:
            cached = self.__class__._conditioning_cache.get(key)
            if cached is not None:
                return cached, True

        model = self._xtts_model(api)
        if self.profile.xtts_mode == "preset":
            manager = getattr(model, "speaker_manager", None)
            speakers = getattr(manager, "speakers", {}) if manager is not None else {}
            entry = speakers.get(self.profile.xtts_preset) if hasattr(speakers, "get") else None
            if entry is None:
                raise SpeechSynthesisUnavailableError(
                    f"Conditionnement XTTS introuvable pour '{self.profile.xtts_preset}'."
                )
            if isinstance(entry, dict):
                gpt_cond = entry.get("gpt_cond_latent")
                speaker_emb = entry.get("speaker_embedding")
                if gpt_cond is None or speaker_emb is None:
                    values = tuple(entry.values())
                    if len(values) >= 2:
                        gpt_cond, speaker_emb = values[:2]
            else:
                try:
                    gpt_cond, speaker_emb = tuple(entry)[:2]
                except Exception as exc:
                    raise SpeechSynthesisUnavailableError("Format de voix XTTS preset non reconnu.") from exc
        else:
            reference = self.profile.xtts_reference_wav
            if not reference:
                raise SpeechSynthesisUnavailableError("Référence vocale XTTS absente.")
            started = time.perf_counter()
            gpt_cond, speaker_emb = model.get_conditioning_latents(audio_path=[reference])
            logger.info(
                "XTTS conditioning computed voice=%s elapsed=%.3fs",
                self.voice_label, time.perf_counter() - started,
            )

        if gpt_cond is None or speaker_emb is None:
            raise SpeechSynthesisUnavailableError("Conditionnement XTTS incomplet.")
        result = (gpt_cond, speaker_emb)
        if settings.XTTS_CONDITIONING_CACHE_ENABLED:
            self.__class__._conditioning_cache[key] = result
        return result, False

    def _speaker_kwargs(self, api=None) -> dict:
        if self.profile.xtts_mode == "custom":
            if self._custom_cached:
                return {"speaker": self.profile.xtts_speaker_id}
            return {
                "speaker_wav": [self.profile.xtts_reference_wav],
                "speaker": self.profile.xtts_speaker_id,
            }

        api = api or self._load_model()
        speakers = tuple(str(item) for item in (getattr(api, "speakers", None) or ()))
        requested = self.profile.xtts_preset
        if speakers and requested not in speakers:
            sample = ", ".join(speakers[:8])
            raise SpeechSynthesisUnavailableError(
                f"La voix XTTS '{requested}' n'existe pas dans le modèle installé. "
                f"Voix détectées : {sample}{'…' if len(speakers) > 8 else ''}"
            )
        return {"speaker": requested}

    _FORBIDDEN_FALLBACK_ENDINGS = frozenset({
        "a", "à", "au", "aux", "avec", "ce", "ces", "cet", "cette", "de", "des",
        "du", "en", "et", "la", "le", "les", "mais", "mon", "notre", "ou", "par",
        "pour", "que", "qui", "sans", "son", "sur", "ton", "très", "un", "une",
        "votre", "leur", "plus", "moins",
    })

    @staticmethod
    def _boundary_positions(pattern: str, window: str) -> list[int]:
        return [match.end() for match in re.finditer(pattern, window, flags=re.IGNORECASE)]

    @classmethod
    def _choose_fallback_cut(cls, remaining: str, *, target: int, floor: int, ceiling: int) -> int:
        positions = [m.start() + 1 for m in re.finditer(r"\s+", remaining[: ceiling + 1])]
        positions = [pos for pos in positions if floor <= pos <= ceiling]
        if not positions:
            return min(len(remaining), max(1, target))
        positions.sort(key=lambda pos: (abs(pos - target), -pos))
        for pos in positions:
            tail = remaining[:pos].rstrip().split()
            if not tail:
                continue
            token = re.sub(r"[^\wÀ-ÿ'-]", "", tail[-1]).lower()
            if token not in cls._FORBIDDEN_FALLBACK_ENDINGS:
                return pos
        return positions[0]

    @classmethod
    def _natural_chunk_plan(
        cls,
        text: str,
        *,
        first_limit: int,
        next_limit: int,
        min_chars: int,
        max_chunks: int,
    ) -> tuple[SpeechChunk, ...]:
        """Build speech chunks around prosodic boundaries, not raw character counts.

        Priority is: complete sentence -> clause punctuation -> conjunction ->
        whitespace fallback. A sentence is allowed to run beyond the soft target
        up to a bounded hard limit so XTTS does not reset its intonation in the
        middle of a grammatical group.
        """
        text = re.sub(r"\s+", " ", (text or "").strip())
        if not text:
            return ()

        first_limit = max(72, int(first_limit))
        next_limit = max(first_limit, int(next_limit))
        min_chars = max(24, min(int(min_chars), first_limit))
        max_chunks = max(1, int(max_chunks))
        max_sentence_chars = max(120, int(settings.FAST_SPEECH_MAX_SENTENCE_CHARS))

        chunks: list[SpeechChunk] = []
        remaining = text
        while remaining and len(chunks) < max_chunks:
            target = first_limit if not chunks else next_limit
            # Soft target may be exceeded to preserve a complete sentence.
            hard = max(target + 36, int(target * 1.38))
            hard = min(hard, 240)

            if len(chunks) == max_chunks - 1:
                boundary = "sentence" if re.search(r"[.!?…][\"'»)]*$", remaining) else "final"
                chunks.append(SpeechChunk(remaining.strip(), boundary))
                break

            if len(remaining) <= target:
                # v0.7.0.15.1: short multi-sentence tool replies (weather is a
                # common case) still start with their first complete sentence.
                # Previously a 100-120 char reply stayed monolithic simply
                # because it fit under first_limit, delaying first audio until
                # the whole reply had been synthesized.
                if not chunks:
                    positions = cls._boundary_positions(r"[.!?…](?:[\"'»)]*)\s+", remaining)
                    positions = [pos for pos in positions if pos >= min_chars and pos < len(remaining)]
                    if positions:
                        cut = positions[0]
                        chunks.append(SpeechChunk(remaining[:cut].strip(), "sentence"))
                        remaining = remaining[cut:].strip()
                        continue
                boundary = "sentence" if re.search(r"[.!?…][\"'»)]*$", remaining) else "final"
                chunks.append(SpeechChunk(remaining.strip(), boundary))
                break

            # A single sentence may exceed the soft target a little, but very
            # long sentences are split on a real clause. Independent XTTS calls
            # retain better prosody around a comma/conjunction than on a 200+
            # character monolith.
            internal_sentence = re.search(r"[.!?…](?:[\"'»)]*)\s+", remaining[: hard + 1])
            if (
                len(remaining) <= hard
                and len(remaining) <= max_sentence_chars
                and not internal_sentence
                and re.search(r"[.!?…][\"'»)]*$", remaining)
            ):
                chunks.append(SpeechChunk(remaining.strip(), "sentence"))
                break

            window = remaining[: hard + 1]
            cut = -1
            reason = "fallback"

            # 1. Strong sentence boundary. On the FIRST audio chunk, a complete
            # sentence is preferred as soon as it is long enough to sound
            # natural, even if it is below the old 72% soft-target heuristic.
            # This improves time-to-first-audio without reintroducing mid-phrase
            # prosody cuts. Later chunks still group nearby short sentences.
            sentence_positions = cls._boundary_positions(r"[.!?…](?:[\"'»)]*)\s+", window)
            sentence_positions = [
                pos for pos in sentence_positions
                if pos >= min_chars and pos <= max_sentence_chars
            ]
            if sentence_positions:
                if not chunks:
                    cut = sentence_positions[0]
                else:
                    after = [pos for pos in sentence_positions if pos >= int(target * 0.72)]
                    cut = (after[0] if after else sentence_positions[-1])
                reason = "sentence"

            # 2. Natural clause punctuation. Choose closest to target.
            if cut < 0:
                clause_positions = cls._boundary_positions(r"[,;:](?:[\"'»)]*)\s+", window)
                clause_positions = [pos for pos in clause_positions if pos >= min_chars]
                if clause_positions:
                    cut = min(clause_positions, key=lambda pos: (abs(pos - target), pos < target))
                    reason = "clause"

            # 3. Conjunction boundary for unusually long unpunctuated prose.
            if cut < 0:
                conj_positions = cls._boundary_positions(
                    r"\s+(?:mais|donc|puis|car|parce que|tandis que|alors que|cependant|pourtant)\s+",
                    window,
                )
                conj_positions = [pos for pos in conj_positions if pos >= min_chars]
                if conj_positions:
                    cut = min(conj_positions, key=lambda pos: abs(pos - target))
                    reason = "conjunction"

            # 4. Last resort only. Avoid ending on determiners/prepositions.
            if cut < 0:
                cut = cls._choose_fallback_cut(
                    remaining, target=target, floor=min_chars, ceiling=hard
                )
                reason = "fallback"

            part = remaining[:cut].strip()
            if not part:
                part = remaining[:target].strip()
                cut = max(1, len(part))
            chunks.append(SpeechChunk(part, reason))
            remaining = remaining[cut:].strip()

        chunks = [chunk for chunk in chunks if chunk.text]
        # Avoid a tiny orphan sentence at the very end. If it can be attached
        # to the previous complete phrase without creating an oversized block,
        # one XTTS inference gives noticeably smoother closing prosody.
        if len(chunks) >= 3 and len(chunks[-1].text) < min_chars:
            combined = f"{chunks[-2].text} {chunks[-1].text}".strip()
            merge_cap = min(240, max(next_limit + 60, first_limit + 72))
            if len(combined) <= merge_cap:
                boundary = "sentence" if chunks[-1].boundary == "sentence" else chunks[-2].boundary
                chunks[-2:] = [SpeechChunk(combined, boundary)]

        return tuple(chunks)

    @classmethod
    def _bounded_text_chunks(
        cls,
        text: str,
        *,
        first_limit: int,
        next_limit: int,
        min_chars: int,
        max_chunks: int,
    ) -> tuple[str, ...]:
        """Backward-compatible text-only view of the natural speech plan."""
        return tuple(
            chunk.text
            for chunk in cls._natural_chunk_plan(
                text,
                first_limit=first_limit,
                next_limit=next_limit,
                min_chars=min_chars,
                max_chunks=max_chunks,
            )
        )

    def _progressive_chunk_plan(self, spoken: str) -> tuple[SpeechChunk, ...]:
        return self._natural_chunk_plan(
            spoken,
            first_limit=settings.FAST_SPEECH_FIRST_CHUNK_CHARS,
            next_limit=settings.FAST_SPEECH_NEXT_CHUNK_CHARS,
            min_chars=settings.FAST_SPEECH_MIN_CHUNK_CHARS,
            max_chunks=settings.FAST_SPEECH_MAX_CHUNKS,
        )

    def _progressive_chunks(self, spoken: str) -> tuple[str, ...]:
        return tuple(chunk.text for chunk in self._progressive_chunk_plan(spoken))

    def _render_to_wav(self, api, text: str, wav_path: Path, *, split_sentences: bool = False) -> None:
        kwargs = self._speaker_kwargs(api)
        api.tts_to_file(
            text=text,
            language=_aura_i18n_tts_language(),
            file_path=str(wav_path),
            split_sentences=bool(split_sentences),
            speed=self.profile.xtts_speed,
            temperature=self.profile.xtts_temperature,
            **kwargs,
        )
        if self.profile.xtts_mode == "custom":
            self._custom_cached = True

    def _play_wav_blocking(self, wav_path: Path) -> None:
        import winsound
        with self._playback_lock:
            winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)

    @staticmethod
    def _wav_payload(wav_path: Path):
        import wave
        with wave.open(str(wav_path), "rb") as src:
            params = src.getparams()
            payload = src.readframes(params.nframes)
        dtype = {1: "uint8", 2: "int16", 4: "int32"}.get(int(params.sampwidth))
        if not dtype:
            raise ValueError(f"Unsupported PCM width: {params.sampwidth}")
        return params, payload, dtype

    # AURA P0.2.10 REALTIME PCM COVERAGE
    def _aura_p0210_start_wav_visual_telemetry(self, payload: bytes, *, dtype, sample_rate: int, channels: int) -> None:
        callback = getattr(self, "_visual_amplitude_callback", None)
        if not callable(callback) or not payload:
            return
        dtype_name = str(dtype or "").lower().strip()
        formats = {
            "int16": (2, "h", 32768.0),
            "int32": (4, "i", 2147483648.0),
            "float32": (4, "f", 1.0),
            "uint8": (1, "B", 128.0),
        }
        fmt = formats.get(dtype_name)
        if fmt is None:
            if not getattr(self, "_aura_p0210_dtype_warned", False):
                self._aura_p0210_dtype_warned = True
                logger.warning("AURA P0.2.10 realtime PCM telemetry unsupported dtype=%s", dtype_name)
            return

        sample_width, cast_code, scale = fmt
        rate = max(1, int(sample_rate or 0))
        channel_count = max(1, int(channels or 1))
        bytes_per_frame = sample_width * channel_count
        usable = (len(payload) // bytes_per_frame) * bytes_per_frame
        if usable <= 0:
            return

        frames_per_window = max(1, int(round(rate / 30.0)))
        window_bytes = max(bytes_per_frame, frames_per_window * bytes_per_frame)
        window_seconds = frames_per_window / float(rate)
        generation = int(getattr(self, "_aura_p0210_visual_generation", 0)) + 1
        self._aura_p0210_visual_generation = generation

        if not getattr(self, "_aura_p0210_ready_logged", False):
            self._aura_p0210_ready_logged = True
            logger.info(
                "AURA P0.2.10 realtime PCM telemetry ready dtype=%s rate=%d channels=%d hz=30 audio_write=unchanged",
                dtype_name, rate, channel_count,
            )

        def level_of(block: bytes) -> float:
            try:
                aligned = (len(block) // sample_width) * sample_width
                if aligned <= 0:
                    return 0.0
                vals = memoryview(block)[:aligned].cast(cast_code)
                if dtype_name == "uint8":
                    peak = max((abs(int(v) - 128) for v in vals), default=0)
                    return max(0.0, min(1.0, peak / scale))
                if dtype_name == "float32":
                    import math
                    peak = 0.0
                    for v in vals:
                        x = float(v)
                        if math.isfinite(x):
                            peak = max(peak, abs(x))
                    return max(0.0, min(1.0, peak))
                peak = max((abs(int(v)) for v in vals), default=0)
                return max(0.0, min(1.0, peak / scale))
            except Exception:
                return 0.0

        def worker() -> None:
            started = time.perf_counter()
            first = bool(getattr(self, "_aura_p0210_first_event_logged", False))
            try:
                idx = 0
                for off in range(0, usable, window_bytes):
                    if generation != int(getattr(self, "_aura_p0210_visual_generation", generation)):
                        return
                    if self._stop_event.is_set():
                        return
                    if idx:
                        delay = (started + idx * window_seconds) - time.perf_counter()
                        if delay > 0:
                            time.sleep(delay)
                    lvl = level_of(payload[off:min(off + window_bytes, usable)])
                    cb = getattr(self, "_visual_amplitude_callback", None)
                    if callable(cb):
                        try:
                            cb(lvl)
                        except Exception:
                            pass
                    if lvl > 0.01 and not first:
                        first = True
                        self._aura_p0210_first_event_logged = True
                        logger.info("AURA P0.2.10 realtime PCM first event level=%.4f dtype=%s", lvl, dtype_name)
                    idx += 1
            finally:
                if generation == int(getattr(self, "_aura_p0210_visual_generation", generation)):
                    cb = getattr(self, "_visual_amplitude_callback", None)
                    if callable(cb):
                        try:
                            cb(0.0)
                        except Exception:
                            pass

        threading.Thread(
            target=worker,
            name="aura-xtts-realtime-pcm-visual",
            daemon=True,
        ).start()

    def _play_progressive_path(self, wav_path: Path, stream_state: dict) -> None:
        """Play one progressive chunk, keeping one output stream when possible."""
        if not (settings.FAST_SPEECH_CONTINUOUS_PLAYBACK and os.name == "nt"):
            self._play_wav_blocking(wav_path)
            return
        try:
            import sounddevice as sd
            params, payload, dtype = self._wav_payload(wav_path)
            spec = (int(params.framerate), int(params.nchannels), dtype)
            stream = stream_state.get("stream")
            if stream is None or stream_state.get("spec") != spec:
                if stream is not None:
                    try:
                        stream.stop(); stream.close()
                    except Exception:
                        pass
                stream = sd.RawOutputStream(
                    samplerate=spec[0], channels=spec[1], dtype=spec[2],
                    blocksize=0, latency="low",
                )
                stream.start()
                stream_state["stream"] = stream
                stream_state["spec"] = spec
                logger.info("XTTS continuous playback stream=%sHz/%sch/%s", *spec)
            # AURA P0.2.10 visual telemetry mirrors the same WAV PCM.
            self._aura_p0210_start_wav_visual_telemetry(
                payload, dtype=dtype, sample_rate=spec[0], channels=spec[1]
            )
            # AURA_R23_R5_R2_R1_XTTS_PROGRESSIVE_EMIT
            self._emit_playback_reference(payload, sample_rate=spec[0], channels=spec[1], dtype=spec[2])
            stream.write(payload)
        except Exception:
            stream = stream_state.pop("stream", None)
            stream_state.pop("spec", None)
            if stream is not None:
                try:
                    stream.abort(); stream.close()
                except Exception:
                    pass
            logger.warning("Flux audio continu indisponible; fallback winsound", exc_info=True)
            self._play_wav_blocking(wav_path)

    @staticmethod
    def _close_progressive_stream(stream_state: dict) -> None:
        stream = stream_state.pop("stream", None)
        stream_state.pop("spec", None)
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                logger.debug("Fermeture flux audio continu ignorée", exc_info=True)

    def _new_temp_wav(self, prefix: str = "aura_xtts_") -> Path:
        fd, wav_name = tempfile.mkstemp(prefix=prefix, suffix=".wav", dir=settings.TEMP_DIR)
        os.close(fd)
        return Path(wav_name)

    def begin_realtime_pipeline(self) -> float:
        """Prepare one turn-wide XTTS producer/consumer session.

        The model is resolved once before the first sentence arrives. Later
        calls only synthesize WAV segments; playback is owned by a separate
        consumer thread in the UI worker.
        """
        # AURA_R23_R5_R2_R1_XTTS_REALTIME_GENERATION
        self._advance_playback_reference_generation()
        started = time.perf_counter()
        self._stop_event.clear()
        self._load_model()
        elapsed = time.perf_counter() - started
        logger.info("XTTS realtime pipeline ready device=%s load=%.3fs", self._device, elapsed)
        return elapsed

    def synthesize_realtime_segment(self, text: str, *, index: int = 0) -> XTTSPreparedSegment:
        """Synthesize without playback so segment N+1 can run during audio N."""
        spoken = sanitize_for_speech(text)
        if not spoken:
            raise SpeechSynthesisUnavailableError("Segment vocal temps réel vide.")
        if self._stop_event.is_set():
            raise SpeechSynthesisUnavailableError("Dialogue vocal temps réel annulé.")

        load_started = time.perf_counter()
        api = self._load_model()
        model_load_seconds = time.perf_counter() - load_started
        wav_path = self._new_temp_wav(prefix=f"aura_xtts_rt_{max(0, int(index)):02d}_")
        synth_started = time.perf_counter()
        try:
            render_text = strip_terminal_punctuation_for_synthesis(spoken)
            if not render_text:
                raise SpeechSynthesisUnavailableError("Segment XTTS sans contenu prononçable.")
            self._render_to_wav(api, render_text, wav_path, split_sentences=False)
            # Each independently generated sentence gets a tiny safety tail; the
            # persistent output stream prevents reopening the device between them.
            polish_wav_tail(
                wav_path,
                fade_ms=settings.TTS_TAIL_FADE_MS,
                safety_silence_ms=settings.TTS_TAIL_SILENCE_MS,
            )
            elapsed = time.perf_counter() - synth_started
            prepared_at = time.perf_counter()
            logger.info(
                "XTTS realtime synth segment=%d chars=%d render_chars=%d device=%s synth=%.3fs",
                int(index) + 1, len(spoken), len(render_text), self._device, elapsed,
            )
            return XTTSPreparedSegment(
                wav_path=wav_path, device=self._device, text_chars=len(spoken),
                synthesis_seconds=elapsed, model_load_seconds=model_load_seconds,
                prepared_at=prepared_at,
            )
        except Exception:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                pass
            raise

    def play_realtime_segment(self, segment: XTTSPreparedSegment, stream_state: dict) -> float:
        """Play one prepared segment on the turn-wide continuous output stream."""
        path = segment.wav_path
        try:
            if self._stop_event.is_set():
                return 0.0
            started = time.perf_counter()
            self._play_progressive_path(path, stream_state)
            return time.perf_counter() - started
        finally:
            try:
                path.unlink(missing_ok=True)
            except Exception:
                logger.debug("Nettoyage segment realtime XTTS impossible: %s", path, exc_info=True)

    def end_realtime_pipeline(self, stream_state: dict) -> None:
        self._close_progressive_stream(stream_state)

    @staticmethod
    def _native_chunk_bytes(chunk) -> bytes:
        """Convert one XTTS float tensor chunk to mono float32 PCM bytes."""
        try:
            tensor = chunk.detach().float().cpu().reshape(-1)
            return tensor.numpy().astype("float32", copy=False).tobytes()
        except Exception as exc:
            raise SpeechSynthesisUnavailableError("Chunk audio XTTS natif invalide.") from exc

    @classmethod
    def _persistent_bridge_ready(cls) -> bool:
        bridge = cls._shared_audio_bridge
        return bool(bridge is not None and getattr(bridge, 'alive', False))

    def _prepare_persistent_audio_bridge(self) -> bool:
        """Open and prime the XTTS output endpoint while AURA is preloading."""
        if self.__class__._persistent_bridge_ready():
            bridge = self.__class__._shared_audio_bridge
            setter = getattr(bridge, "set_amplitude_callback", None)
            if callable(setter):
                setter(self._visual_amplitude_callback)
            return True
        try:
            import sounddevice as sd
            with self.__class__._shared_audio_bridge_lock:
                if self.__class__._persistent_bridge_ready():
                    bridge = self.__class__._shared_audio_bridge
                    setter = getattr(bridge, "set_amplitude_callback", None)
                    if callable(setter):
                        setter(self._visual_amplitude_callback)
                    return True
                bridge = _PersistentAudioBridge(
                    sd,
                    samplerate=settings.XTTS_NATIVE_STREAM_SAMPLE_RATE,
                    amplitude_callback=self._visual_amplitude_callback,
                )
                # AURA_R23_R5_R2_R1_XTTS_PERSISTENT_BIND
                bridge._aura_playback_reference_callback = self._emit_playback_reference
                self.__class__._shared_audio_bridge = bridge
            logger.info(
                "XTTS persistent audio bridge READY sample_rate=%d idle_silence_ms=20",
                int(settings.XTTS_NATIVE_STREAM_SAMPLE_RATE),
            )
            return True
        except Exception:
            logger.warning("XTTS persistent audio bridge unavailable; per-turn stream fallback kept", exc_info=True)
            return False

    def native_silent_warmup(self, text: str = "Prêt.") -> dict:
        """Prime CUDA kernels + XTTS conditioning without opening an audio device."""
        started = time.perf_counter()
        self._stop_event.clear()
        spoken = sanitize_for_speech(text) or "Prête."
        api = self._load_model()
        model = self._xtts_model(api)
        (gpt_cond, speaker_emb), cache_hit = self._native_conditioning(api)
        render_text = strip_terminal_punctuation_for_synthesis(spoken) or "Prêt"
        first_chunk = 0.0
        chunks_seen = 0
        samples = 0
        inference_started = time.perf_counter()
        with self.__class__._shared_inference_lock:
            chunks = model.inference_stream(
                render_text,
                _aura_i18n_tts_language(),
                gpt_cond,
                speaker_emb,
                stream_chunk_size=settings.XTTS_NATIVE_STREAM_CHUNK_SIZE,
                overlap_wav_len=settings.XTTS_NATIVE_STREAM_OVERLAP_SAMPLES,
                temperature=self.profile.xtts_temperature,
                speed=self.profile.xtts_speed,
                enable_text_splitting=False,
            )
            for chunk in chunks:
                payload = self._native_chunk_bytes(chunk)
                if not payload:
                    continue
                chunks_seen += 1
                samples += len(payload) // 4
                if first_chunk <= 0.0:
                    first_chunk = time.perf_counter() - inference_started
        bridge_ready = self._prepare_persistent_audio_bridge()
        total = time.perf_counter() - started
        logger.info(
            "XTTS local-first silent warmup PASS device=%s cache_hit=%s first_chunk=%.3fs chunks=%d audio=%.3fs total=%.3fs audio_bridge_ready=%s",
            self._device, cache_hit, first_chunk, chunks_seen,
            samples / float(settings.XTTS_NATIVE_STREAM_SAMPLE_RATE), total, bridge_ready,
        )
        return {
            "ok": chunks_seen > 0, "device": self._device, "cache_hit": bool(cache_hit),
            "first_chunk_seconds": float(first_chunk), "chunk_count": int(chunks_seen),
            "total_seconds": float(total), "audio_bridge_ready": bool(bridge_ready),
        }

    def _speak_native_stream(self, text: str) -> XTTSSynthesisMetrics:
        """Stream XTTS with decoupled CUDA production and audio playback.

        v0.7.1.3.6.4 keeps ``inference_stream`` free to generate the next
        chunk while PortAudio is playing the current one.  The previous
        implementation called ``stream.write`` in the inference loop, so a
        blocking audio write could starve CUDA generation and create audible
        gaps between words/chunks.
        """
        request_start = time.perf_counter()
        self._stop_event.clear()
        spoken = sanitize_for_speech(text)
        if not spoken:
            return XTTSSynthesisMetrics(self._device, 0.0, 0.0, 0.0, 0, progressive=True, chunk_count=0)

        api = self._load_model()
        model_load_seconds = time.perf_counter() - request_start
        model = self._xtts_model(api)
        (gpt_cond, speaker_emb), cache_hit = self._native_conditioning(api)
        conditioning_ready = time.perf_counter()
        render_text = strip_terminal_punctuation_for_synthesis(spoken)
        if not render_text:
            return XTTSSynthesisMetrics(
                self._device, 0.0, 0.0, time.perf_counter() - request_start, len(spoken),
                model_load_seconds=model_load_seconds, time_to_audio_seconds=model_load_seconds,
                progressive=True, chunk_count=0,
            )

        try:
            import sounddevice as sd
        except Exception as exc:
            raise SpeechSynthesisUnavailableError(
                "Le streaming XTTS nécessite le moteur audio sounddevice déjà utilisé par AURA."
            ) from exc

        bridge = self.__class__._shared_audio_bridge if self.__class__._persistent_bridge_ready() else None
        if bridge is not None:
            session = bridge.begin()
            first_chunk_seconds = 0.0
            chunk_count = 0
            generated_samples = 0
            inference_started = time.perf_counter()
            logger.info(
                "XTTS native stream start voice=%s device=%s chars=%d cache_hit=%s chunk_size=%d overlap=%d mode=persistent-audio-bridge",
                self.voice_label, self._device, len(render_text), cache_hit,
                settings.XTTS_NATIVE_STREAM_CHUNK_SIZE, settings.XTTS_NATIVE_STREAM_OVERLAP_SAMPLES,
            )
            try:
                with self.__class__._shared_inference_lock:
                    chunks = model.inference_stream(
                        render_text,
                        _aura_i18n_tts_language(),
                        gpt_cond,
                        speaker_emb,
                        stream_chunk_size=settings.XTTS_NATIVE_STREAM_CHUNK_SIZE,
                        overlap_wav_len=settings.XTTS_NATIVE_STREAM_OVERLAP_SAMPLES,
                        temperature=self.profile.xtts_temperature,
                        speed=self.profile.xtts_speed,
                        enable_text_splitting=False,
                    )
                    for chunk in chunks:
                        if self._stop_event.is_set():
                            break
                        payload = self._native_chunk_bytes(chunk)
                        if not payload:
                            continue
                        now = time.perf_counter()
                        if chunk_count == 0:
                            first_chunk_seconds = now - inference_started
                        bridge.put(session, payload)
                        chunk_count += 1
                        generated_samples += len(payload) // 4
                inference_finished = time.perf_counter()
                bridge.finish(session)
                # The persistent stream is already running; this event is set as
                # soon as its worker begins consuming the first speech packet.
                session.first_audio.wait(timeout=5.0)
                bridge.wait(session, timeout=60.0)
                total_seconds = time.perf_counter() - request_start
                inference_seconds = max(0.0, inference_finished - inference_started)
                audio_duration = generated_samples / float(settings.XTTS_NATIVE_STREAM_SAMPLE_RATE)
                first_audio_seconds = (session.first_audio_at - request_start) if session.first_audio_at else 0.0
                playback_seconds = max(0.0, total_seconds - first_audio_seconds) if first_audio_seconds else 0.0
                bridge_delay = max(0.0, first_audio_seconds - (model_load_seconds + (conditioning_ready - (request_start + model_load_seconds)) + first_chunk_seconds))
                logger.info(
                    "XTTS native timing device=%s chars=%d load=%.3fs conditioning=%.3fs cache_hit=%s first_chunk=%.3fs first_audio=%.3fs audio_bridge_delay=%.3fs chunks=%d audio=%.3fs synth=%.3fs total=%.3fs seamless_queue=True persistent_stream=True",
                    self._device, len(spoken), model_load_seconds, conditioning_ready - (request_start + model_load_seconds),
                    cache_hit, first_chunk_seconds, first_audio_seconds, bridge_delay, chunk_count, audio_duration, inference_seconds, total_seconds,
                )
                return XTTSSynthesisMetrics(
                    device=self._device,
                    synthesis_seconds=inference_seconds,
                    playback_seconds=playback_seconds,
                    total_seconds=total_seconds,
                    text_chars=len(spoken),
                    model_load_seconds=model_load_seconds,
                    time_to_audio_seconds=first_audio_seconds or total_seconds,
                    progressive=True,
                    chunk_count=chunk_count,
                    first_chunk_synthesis_seconds=first_chunk_seconds,
                )
            except Exception as exc:
                logger.exception("XTTS persistent audio bridge failed; per-turn stream fallback will be used")
                # A broken persistent endpoint must not poison future replies.
                with self.__class__._shared_audio_bridge_lock:
                    if self.__class__._shared_audio_bridge is bridge:
                        self.__class__._shared_audio_bridge = None
                try:
                    bridge.close()
                except Exception:
                    pass
            finally:
                bridge.end()

        audio_queue: queue.Queue[bytes | object] = queue.Queue(maxsize=12)
        sentinel = object()
        playback_started_holder: list[float | None] = [None]
        playback_error: list[BaseException] = []
        stream_holder: list[Any | None] = [None]
        first_audio_ready = threading.Event()
        first_chunk_seconds = 0.0
        chunk_count = 0
        generated_samples = 0
        inference_started = time.perf_counter()

        def playback_worker() -> None:
            stream = None
            try:
                item = audio_queue.get()
                if item is sentinel:
                    return
                stream = sd.RawOutputStream(
                    samplerate=settings.XTTS_NATIVE_STREAM_SAMPLE_RATE,
                    channels=1, dtype="float32", blocksize=0, latency="low",
                )
                stream_holder[0] = stream
                stream.start()
                playback_started_holder[0] = time.perf_counter()
                first_audio_ready.set()
                while item is not sentinel:
                    if self._stop_event.is_set():
                        try:
                            stream.abort()
                        except Exception:
                            pass
                        return
                    self._emit_visual_amplitude(item)
                    # AURA_R23_R5_R2_R1_XTTS_NATIVE_EMIT
                    self._emit_playback_reference(item, sample_rate=settings.XTTS_NATIVE_STREAM_SAMPLE_RATE, channels=1, dtype="float32")
                    stream.write(item)
                    item = audio_queue.get()
                self._emit_visual_amplitude(None, force=True)
                stream.stop()
            except BaseException as exc:  # propagate worker failures to caller
                playback_error.append(exc)
                first_audio_ready.set()
            finally:
                self._emit_visual_amplitude(None, force=True)
                if stream is not None:
                    try:
                        stream.close()
                    except Exception:
                        logger.debug("Fermeture flux XTTS natif ignorée", exc_info=True)
                stream_holder[0] = None

        player = threading.Thread(target=playback_worker, name="aura-xtts-playback", daemon=True)
        player.start()

        logger.info(
            "XTTS native stream start voice=%s device=%s chars=%d cache_hit=%s chunk_size=%d overlap=%d mode=producer-consumer",
            self.voice_label, self._device, len(render_text), cache_hit,
            settings.XTTS_NATIVE_STREAM_CHUNK_SIZE, settings.XTTS_NATIVE_STREAM_OVERLAP_SAMPLES,
        )
        inference_finished = inference_started
        try:
            with self.__class__._shared_inference_lock:
                chunks = model.inference_stream(
                    render_text,
                    _aura_i18n_tts_language(),
                    gpt_cond,
                    speaker_emb,
                    stream_chunk_size=settings.XTTS_NATIVE_STREAM_CHUNK_SIZE,
                    overlap_wav_len=settings.XTTS_NATIVE_STREAM_OVERLAP_SAMPLES,
                    temperature=self.profile.xtts_temperature,
                    speed=self.profile.xtts_speed,
                    enable_text_splitting=False,
                )
                for chunk in chunks:
                    if self._stop_event.is_set():
                        break
                    payload = self._native_chunk_bytes(chunk)
                    if not payload:
                        continue
                    now = time.perf_counter()
                    if chunk_count == 0:
                        first_chunk_seconds = now - inference_started
                    audio_queue.put(payload)
                    chunk_count += 1
                    generated_samples += len(payload) // 4
            inference_finished = time.perf_counter()
            audio_queue.put(sentinel)
            player.join()
            if playback_error:
                raise playback_error[0]

            total_seconds = time.perf_counter() - request_start
            inference_seconds = max(0.0, inference_finished - inference_started)
            audio_duration = generated_samples / float(settings.XTTS_NATIVE_STREAM_SAMPLE_RATE)
            playback_started = playback_started_holder[0]
            first_audio_seconds = (playback_started - request_start) if playback_started else 0.0
            playback_seconds = max(0.0, total_seconds - (playback_started - request_start)) if playback_started else 0.0
            logger.info(
                "XTTS native timing device=%s chars=%d load=%.3fs conditioning=%.3fs cache_hit=%s first_chunk=%.3fs first_audio=%.3fs chunks=%d audio=%.3fs synth=%.3fs total=%.3fs seamless_queue=True",
                self._device, len(spoken), model_load_seconds, conditioning_ready - (request_start + model_load_seconds),
                cache_hit, first_chunk_seconds, first_audio_seconds, chunk_count, audio_duration, inference_seconds, total_seconds,
            )
            return XTTSSynthesisMetrics(
                device=self._device,
                synthesis_seconds=inference_seconds,
                playback_seconds=playback_seconds,
                total_seconds=total_seconds,
                text_chars=len(spoken),
                model_load_seconds=model_load_seconds,
                time_to_audio_seconds=first_audio_seconds or total_seconds,
                progressive=True,
                chunk_count=chunk_count,
                first_chunk_synthesis_seconds=first_chunk_seconds,
            )
        except SpeechSynthesisUnavailableError:
            raise
        except Exception as exc:
            logger.exception("XTTS native streaming impossible voice=%s", self.voice_label)
            raise SpeechSynthesisUnavailableError(
                f"Le streaming XTTS natif a échoué avec {self.voice_label}."
            ) from exc
        finally:
            if player.is_alive():
                try:
                    audio_queue.put_nowait(sentinel)
                except Exception:
                    pass
                player.join(timeout=1.0)
            stream = stream_holder[0]
            if stream is not None:
                try:
                    stream.abort(); stream.close()
                except Exception:
                    logger.debug("Fermeture flux XTTS natif ignorée", exc_info=True)

    def _speak_progressive(self, text: str) -> XTTSSynthesisMetrics:
        """Generate a short first chunk, then pipeline synthesis with playback.

        This intentionally uses the stable public ``tts_to_file`` path instead
        of XTTS' lower-level native streaming API. Audio chunk N can play while
        chunk N+1 is generated on the GPU, reducing perceived latency without
        changing the proven model-loading path.
        """
        request_start = time.perf_counter()
        self._stop_event.clear()
        spoken = sanitize_for_speech(text)
        if not spoken:
            return XTTSSynthesisMetrics(self._device, 0.0, 0.0, 0.0, 0, 0.0, 0.0, True, 0, 0.0)

        api = self._load_model()
        model_load_seconds = time.perf_counter() - request_start
        if self._stop_event.is_set():
            logger.info("XTTS fast-speech annulé pendant le chargement du modèle")
            return XTTSSynthesisMetrics(
                self._device, 0.0, 0.0, model_load_seconds, len(spoken),
                model_load_seconds, model_load_seconds, True, 0, 0.0,
            )
        chunk_plan = self._progressive_chunk_plan(spoken)
        chunks = tuple(item.text for item in chunk_plan)
        if not chunks:
            return XTTSSynthesisMetrics(self._device, 0.0, 0.0, 0.0, 0, model_load_seconds, model_load_seconds, True, 0, 0.0)

        audio_queue: queue.Queue[Path | None] = queue.Queue()
        state_lock = threading.Lock()
        playback_state = {
            "first_audio_at": None,
            "playback_seconds": 0.0,
            "played_chunks": 0,
        }
        generated_paths: set[Path] = set()

        def playback_worker() -> None:
            stream_state: dict = {}
            try:
                while True:
                    item = audio_queue.get()
                    try:
                        if item is None:
                            return
                        path = item
                        if self._stop_event.is_set():
                            continue
                        started = time.perf_counter()
                        with state_lock:
                            if playback_state["first_audio_at"] is None:
                                playback_state["first_audio_at"] = started
                        self._play_progressive_path(path, stream_state)
                        elapsed = time.perf_counter() - started
                        with state_lock:
                            playback_state["playback_seconds"] += elapsed
                            playback_state["played_chunks"] += 1
                    finally:
                        if item is not None:
                            try:
                                item.unlink(missing_ok=True)
                            except Exception:
                                logger.debug("Nettoyage chunk XTTS impossible: %s", item, exc_info=True)
                            generated_paths.discard(item)
                        audio_queue.task_done()
            finally:
                self._close_progressive_stream(stream_state)

        player = threading.Thread(target=playback_worker, name="AURA-XTTS-Playback", daemon=True)
        player.start()
        synthesis_total = 0.0
        first_chunk_synthesis = 0.0
        rendered = 0
        try:
            logger.info(
                "XTTS fast-speech start device=%s chunks=%d first_limit=%d next_limit=%d chars=%d",
                self._device, len(chunks), settings.FAST_SPEECH_FIRST_CHUNK_CHARS,
                settings.FAST_SPEECH_NEXT_CHUNK_CHARS, len(spoken),
            )
            for index, chunk in enumerate(chunks):
                if self._stop_event.is_set():
                    break
                wav_path = self._new_temp_wav(prefix=f"aura_xtts_fast_{index:02d}_")
                generated_paths.add(wav_path)
                synth_start = time.perf_counter()
                render_chunk = strip_terminal_punctuation_for_synthesis(chunk)
                if not render_chunk:
                    logger.debug("XTTS chunk ignoré: ponctuation terminale seule index=%d", index)
                    generated_paths.discard(wav_path)
                    wav_path.unlink(missing_ok=True)
                    continue
                self._render_to_wav(api, render_chunk, wav_path, split_sentences=False)
                if index == len(chunks) - 1:
                    polish_wav_tail(
                        wav_path, fade_ms=settings.TTS_TAIL_FADE_MS,
                        safety_silence_ms=settings.TTS_TAIL_SILENCE_MS,
                    )
                elapsed = time.perf_counter() - synth_start
                synthesis_total += elapsed
                if index == 0:
                    first_chunk_synthesis = elapsed
                rendered += 1
                boundary = chunk_plan[index].boundary if index < len(chunk_plan) else "unknown"
                logger.info(
                    "XTTS fast-speech chunk=%d/%d chars=%d render_chars=%d boundary=%s terminal_punct_stripped=%s synth=%.3fs",
                    index + 1, len(chunks), len(chunk), len(render_chunk), boundary,
                    len(render_chunk) != len(chunk), elapsed,
                )
                audio_queue.put(wav_path)

            audio_queue.put(None)
            player.join()
            total_seconds = time.perf_counter() - request_start
            with state_lock:
                first_audio_at = playback_state["first_audio_at"]
                playback_seconds = float(playback_state["playback_seconds"])
            time_to_audio = (
                float(first_audio_at) - request_start
                if first_audio_at is not None
                else model_load_seconds + first_chunk_synthesis
            )
            logger.info(
                "XTTS timing device=%s chars=%d progressive=True chunks=%d load=%.3fs synth=%.3fs first_chunk=%.3fs first_audio=%.3fs playback=%.3fs total=%.3fs",
                self._device, len(spoken), rendered, model_load_seconds, synthesis_total,
                first_chunk_synthesis, time_to_audio, playback_seconds, total_seconds,
            )
            return XTTSSynthesisMetrics(
                device=self._device,
                synthesis_seconds=synthesis_total,
                playback_seconds=playback_seconds,
                total_seconds=total_seconds,
                text_chars=len(spoken),
                model_load_seconds=model_load_seconds,
                time_to_audio_seconds=time_to_audio,
                progressive=True,
                chunk_count=rendered,
                first_chunk_synthesis_seconds=first_chunk_synthesis,
            )
        except SpeechSynthesisUnavailableError:
            self._stop_event.set()
            try:
                audio_queue.put_nowait(None)
            except Exception:
                pass
            player.join(timeout=2.0)
            raise
        except Exception as exc:
            self._stop_event.set()
            try:
                audio_queue.put_nowait(None)
            except Exception:
                pass
            player.join(timeout=2.0)
            logger.exception("Synthèse XTTS progressive impossible voice=%s", self.voice_label)
            raise SpeechSynthesisUnavailableError(
                f"La synthèse XTTS progressive a échoué avec {self.voice_label}."
            ) from exc
        finally:
            for path in tuple(generated_paths):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    logger.debug("Nettoyage final chunk XTTS impossible: %s", path, exc_info=True)

    def _speak_impl(self, text: str, *, fast_preview: bool = False) -> XTTSSynthesisMetrics:
        request_start = time.perf_counter()
        spoken = sanitize_for_speech(text)
        if fast_preview and settings.XTTS_PREVIEW_MAX_CHARS > 0:
            spoken = spoken[: settings.XTTS_PREVIEW_MAX_CHARS].rstrip()
        if not spoken:
            return XTTSSynthesisMetrics(self._device, 0.0, 0.0, 0.0, 0, 0.0, 0.0)
        api = self._load_model()
        model_load_seconds = time.perf_counter() - request_start
        wav_path = self._new_temp_wav()
        synth_start = time.perf_counter()
        try:
            logger.info(
                "XTTS synthèse voice=%s language=%s device=%s fast_preview=%s",
                self.voice_label, _aura_i18n_tts_language(), self._device, fast_preview,
            )
            render_text = strip_terminal_punctuation_for_synthesis(spoken)
            if not render_text:
                return XTTSSynthesisMetrics(
                    self._device, 0.0, 0.0, model_load_seconds, len(spoken),
                    model_load_seconds, model_load_seconds, False, 0, 0.0,
                )
            self._render_to_wav(
                api, render_text, wav_path,
                split_sentences=(not fast_preview and len(render_text) > settings.XTTS_SHORT_TEXT_NO_SPLIT_CHARS),
            )
            logger.info(
                "XTTS render payload chars=%d terminal_punct_stripped=%s",
                len(render_text), len(render_text) != len(spoken),
            )
            polish_wav_tail(
                wav_path, fade_ms=settings.TTS_TAIL_FADE_MS,
                safety_silence_ms=settings.TTS_TAIL_SILENCE_MS,
            )
            synthesis_seconds = time.perf_counter() - synth_start
            playback_start = time.perf_counter()
            self._play_wav_blocking(wav_path)
            playback_seconds = time.perf_counter() - playback_start
            total_seconds = time.perf_counter() - request_start
            time_to_audio = model_load_seconds + synthesis_seconds
            logger.info(
                "XTTS timing device=%s chars=%d load=%.3fs synth=%.3fs first_audio=%.3fs playback=%.3fs total=%.3fs",
                self._device, len(spoken), model_load_seconds, synthesis_seconds, time_to_audio, playback_seconds, total_seconds,
            )
            return XTTSSynthesisMetrics(
                device=self._device,
                synthesis_seconds=synthesis_seconds,
                playback_seconds=playback_seconds,
                total_seconds=total_seconds,
                text_chars=len(spoken),
                model_load_seconds=model_load_seconds,
                time_to_audio_seconds=time_to_audio,
            )
        except SpeechSynthesisUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Synthèse XTTS impossible voice=%s", self.voice_label)
            raise SpeechSynthesisUnavailableError(
                f"La synthèse XTTS a échoué avec {self.voice_label}. Piper n'est pas utilisé pour le test de voix."
            ) from exc
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("Impossible de supprimer le WAV temporaire XTTS")

    def _native_streaming_enabled(self) -> bool:
        return bool(
            settings.FAST_SPEECH_NATIVE_STREAMING
            and settings.XTTS_ALLOW_CUDA
            and str(self._device or settings.XTTS_DEVICE).strip().lower() == "cuda"
        )

    def speak(self, text: str) -> XTTSSynthesisMetrics:
        # AURA_R23_R5_R2_R1_XTTS_SPEAK_GENERATION
        self._advance_playback_reference_generation()
        spoken = sanitize_for_speech(text)
        # v0.7.1.3.5.9 local-first: once CUDA XTTS has been explicitly enabled,
        # native inference_stream is the preferred low-TTFA path for short AURA
        # replies. The stable WAV pipeline remains deterministic fallback.
        if settings.FAST_SPEECH_NATIVE_STREAMING and settings.XTTS_ALLOW_CUDA and hasattr(self, "_stop_event"):
            try:
                return self._speak_native_stream(spoken)
            except SpeechSynthesisUnavailableError as exc:
                logger.warning("XTTS native stream indisponible; fallback pipeline WAV: %s", exc)
        if (
            settings.FAST_SPEECH_ENABLED
            and self.profile.xtts_mode == "preset"
            and len(spoken) >= settings.FAST_SPEECH_MIN_TEXT_CHARS
        ):
            return self._speak_progressive(spoken)
        return self._speak_impl(spoken, fast_preview=False)

    def speak_preview(self, text: str, *, fast: bool = True) -> XTTSSynthesisMetrics:
        spoken = sanitize_for_speech(text)
        if settings.FAST_SPEECH_NATIVE_STREAMING and settings.XTTS_ALLOW_CUDA and hasattr(self, "_stop_event"):
            try:
                return self._speak_native_stream(spoken)
            except SpeechSynthesisUnavailableError as exc:
                logger.warning("XTTS preview native indisponible; fallback WAV: %s", exc)
        return self._speak_impl(spoken, fast_preview=fast)

    def stop(self) -> None:
        # AURA_R23_R5_R2_R1_XTTS_STOP_GENERATION
        self._advance_playback_reference_generation()
        self._stop_event.set()
        if os.name != "nt":
            return
        try:
            import winsound
            winsound.PlaySound(None, 0)
        except Exception:
            logger.exception("Impossible d'interrompre XTTS")

# ---------------------------------------------------------------------------
# AURA P0.1.1 VOICE CONTINUITY ROBUST
# Structural runtime wrapper. Deliberately independent from the visual-envelope
# implementation so UI/orb refactors cannot invalidate the voice hotfix.
# ---------------------------------------------------------------------------
def _aura_p011_env_float(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float(default)
    return max(low, min(high, value))


def _aura_p011_prebuffer_seconds() -> float:
    return _aura_p011_env_float("AURA_XTTS_CONTINUITY_PREBUFFER_S", 2.25, 0.80, 6.00)


def _aura_p011_min_rate() -> float:
    return _aura_p011_env_float("AURA_XTTS_CONTINUITY_MIN_RATE", 1.20, 1.00, 2.50)


def _aura_p011_chunk_floor() -> int:
    raw = os.getenv("AURA_XTTS_CONTINUITY_CHUNK_SIZE", "32").strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = 32
    return max(24, min(64, value))


def _aura_p011_patch_bridge() -> None:
    bridge_cls = globals().get("_PersistentAudioBridge")
    if bridge_cls is None:
        raise RuntimeError("AURA P0.1.1: _PersistentAudioBridge introuvable au chargement")
    if getattr(bridge_cls, "_aura_p011_continuity_installed", False):
        return

    original_put = bridge_cls.put
    original_finish = bridge_cls.finish

    def continuity_put(self, session, payload):
        payload = bytes(payload or b"")
        if not payload:
            return

        state = getattr(session, "_aura_p011_state", None)
        if state is None:
            state = {
                "created_at": time.perf_counter(),
                "pending": [],
                "samples": 0,
                "gate_open": False,
                "last_rate": 0.0,
            }
            setattr(session, "_aura_p011_state", state)

        if state["gate_open"]:
            return original_put(self, session, payload)

        state["pending"].append(payload)
        # Persistent bridge is mono float32 in the AURA XTTS path: 4 bytes/sample.
        state["samples"] += len(payload) // 4
        sample_rate = float(max(1, int(getattr(self, "samplerate", 24000) or 24000)))
        elapsed = max(0.001, time.perf_counter() - float(state["created_at"]))
        audio_seconds = float(state["samples"]) / sample_rate
        production_rate = audio_seconds / elapsed
        state["last_rate"] = production_rate

        if audio_seconds >= _aura_p011_prebuffer_seconds() and production_rate >= _aura_p011_min_rate():
            packets = state["pending"]
            state["pending"] = []
            state["samples"] = 0
            state["gate_open"] = True
            logger.info(
                "XTTS continuity gate OPEN prebuffer=%.3fs rate=%.2fx packets=%d target=%.2fs",
                audio_seconds, production_rate, len(packets), _aura_p011_prebuffer_seconds(),
            )
            for packet in packets:
                original_put(self, session, packet)

    def continuity_finish(self, session):
        state = getattr(session, "_aura_p011_state", None)
        if state is not None and state.get("pending"):
            packets = state["pending"]
            buffered_samples = int(state.get("samples", 0) or 0)
            state["pending"] = []
            state["samples"] = 0
            sample_rate = float(max(1, int(getattr(self, "samplerate", 24000) or 24000)))
            audio_seconds = buffered_samples / sample_rate
            elapsed = max(0.001, time.perf_counter() - float(state.get("created_at", time.perf_counter())))
            production_rate = audio_seconds / elapsed
            mode = "TAIL-FLUSH" if state.get("gate_open") else "FULL-BUFFER"
            logger.info(
                "XTTS continuity %s audio=%.3fs rate=%.2fx packets=%d target=%.2fs",
                mode, audio_seconds, production_rate, len(packets), _aura_p011_prebuffer_seconds(),
            )
            for packet in packets:
                original_put(self, session, packet)
        return original_finish(self, session)

    bridge_cls.put = continuity_put
    bridge_cls.finish = continuity_finish
    bridge_cls._aura_p011_continuity_installed = True

    # Raise XTTS native stream chunk floor without requiring any call-site anchor.
    try:
        current = int(getattr(settings, "XTTS_NATIVE_STREAM_CHUNK_SIZE", 18) or 18)
        desired = max(current, _aura_p011_chunk_floor())
        setattr(settings, "XTTS_NATIVE_STREAM_CHUNK_SIZE", desired)
        logger.info(
            "XTTS P0.1.1 continuity policy active chunk_size=%d prebuffer=%.2fs min_rate=%.2fx",
            desired, _aura_p011_prebuffer_seconds(), _aura_p011_min_rate(),
        )
    except Exception as exc:
        logger.warning("XTTS P0.1.1 chunk floor non appliqué: %s", exc)


_aura_p011_patch_bridge()

# ---------------------------------------------------------------------------
# AURA P0.1.2 XTTS SHORT ONESHOT
# Short Aura replies use regular XTTS inference instead of inference_stream.
# Rationale: if streaming production is slower than realtime, no prebuffer can
# simultaneously provide low latency and continuous speech. Regular inference
# avoids repeated streaming decoder passes, then sends one continuous PCM
# packet to the already-hot persistent audio bridge.
# ---------------------------------------------------------------------------
def _aura_p012_env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = int(default)
    return max(low, min(high, value))


def _aura_p012_max_chars() -> int:
    return _aura_p012_env_int("AURA_XTTS_ONESHOT_MAX_CHARS", 220, 48, 360)


def _aura_p012_pcm_bytes(wav) -> tuple[bytes, int]:
    import numpy as _np
    arr = _np.asarray(wav, dtype=_np.float32).reshape(-1)
    if arr.size <= 0:
        return b"", 0
    arr = _np.nan_to_num(arr, nan=0.0, posinf=1.0, neginf=-1.0)
    arr = _np.clip(arr, -1.0, 1.0)
    return arr.astype(_np.float32, copy=False).tobytes(), int(arr.size)


def _aura_p012_patch_short_oneshot() -> None:
    cls = globals().get("XTTSTTS")
    if cls is None:
        raise RuntimeError("AURA P0.1.2: XTTSTTS introuvable au chargement")
    if getattr(cls, "_aura_p012_oneshot_installed", False):
        return

    original = cls._speak_native_stream

    def short_oneshot(self, text: str):
        # Preserve all existing behavior for long replies and edge cases.
        spoken = sanitize_for_speech(text)
        render_text = strip_terminal_punctuation_for_synthesis(spoken) if spoken else ""
        if not render_text or len(render_text) > _aura_p012_max_chars():
            return original(self, text)
        if not self.__class__._persistent_bridge_ready():
            return original(self, text)

        request_start = time.perf_counter()
        self._stop_event.clear()
        try:
            api = self._load_model()
            model_load_seconds = time.perf_counter() - request_start
            model = self._xtts_model(api)
            (gpt_cond, speaker_emb), cache_hit = self._native_conditioning(api)
            conditioning_ready = time.perf_counter()

            logger.info(
                "XTTS P0.1.2 one-shot start voice=%s device=%s chars=%d cache_hit=%s max_chars=%d",
                self.voice_label, self._device, len(render_text), cache_hit, _aura_p012_max_chars(),
            )

            inference_started = time.perf_counter()
            with self.__class__._shared_inference_lock:
                out = model.inference(
                    render_text,
                    _aura_i18n_tts_language(),
                    gpt_cond,
                    speaker_emb,
                    temperature=self.profile.xtts_temperature,
                    speed=self.profile.xtts_speed,
                    enable_text_splitting=False,
                )
            inference_finished = time.perf_counter()

            wav = out.get("wav") if isinstance(out, dict) else None
            payload, sample_count = _aura_p012_pcm_bytes(wav)
            if not payload or sample_count <= 0:
                raise SpeechSynthesisUnavailableError("XTTS P0.1.2: sortie one-shot vide")
            if self._stop_event.is_set():
                raise SpeechSynthesisUnavailableError("XTTS P0.1.2: dialogue annulé")

            bridge = self.__class__._shared_audio_bridge if self.__class__._persistent_bridge_ready() else None
            if bridge is None:
                logger.info("XTTS P0.1.2 bridge indisponible après synthèse; fallback streaming")
                return original(self, text)

            session = bridge.begin()
            try:
                bridge.put(session, payload)
                bridge.finish(session)
                session.first_audio.wait(timeout=5.0)
                bridge.wait(session, timeout=60.0)
            finally:
                bridge.end()

            total_seconds = time.perf_counter() - request_start
            inference_seconds = max(0.0, inference_finished - inference_started)
            sample_rate = float(max(1, int(settings.XTTS_NATIVE_STREAM_SAMPLE_RATE)))
            audio_duration = float(sample_count) / sample_rate
            first_audio_seconds = (session.first_audio_at - request_start) if session.first_audio_at else 0.0
            playback_seconds = max(0.0, total_seconds - first_audio_seconds) if first_audio_seconds else 0.0
            conditioning_seconds = conditioning_ready - (request_start + model_load_seconds)
            rtf = inference_seconds / max(0.001, audio_duration)

            logger.info(
                "XTTS P0.1.2 one-shot timing device=%s chars=%d load=%.3fs conditioning=%.3fs "
                "first_audio=%.3fs audio=%.3fs synth=%.3fs rtf=%.2f total=%.3fs continuous=True",
                self._device, len(spoken), model_load_seconds, conditioning_seconds,
                first_audio_seconds, audio_duration, inference_seconds, rtf, total_seconds,
            )
            return XTTSSynthesisMetrics(
                device=self._device,
                synthesis_seconds=inference_seconds,
                playback_seconds=playback_seconds,
                total_seconds=total_seconds,
                text_chars=len(spoken),
                model_load_seconds=model_load_seconds,
                time_to_audio_seconds=first_audio_seconds or total_seconds,
                progressive=False,
                chunk_count=1,
                first_chunk_synthesis_seconds=inference_seconds,
            )
        except Exception:
            logger.exception("XTTS P0.1.2 one-shot failed; safe fallback to P0.1.1 streaming")
            return original(self, text)

    cls._aura_p012_original_speak_native_stream = original
    cls._speak_native_stream = short_oneshot
    cls._aura_p012_oneshot_installed = True
    logger.info(
        "XTTS P0.1.2 short one-shot policy active max_chars=%d fallback=P0.1.1",
        _aura_p012_max_chars(),
    )


_aura_p012_patch_short_oneshot()

# ---------------------------------------------------------------------------
# AURA P0.1.3 STREAM RECOVERY PERF GUARD
# ---------------------------------------------------------------------------
def _aura_p013_env_float(name: str, default: float, low: float, high: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try: value = float(raw)
    except (TypeError, ValueError): value = float(default)
    return max(low, min(high, value))


def _aura_p013_env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try: value = int(raw)
    except (TypeError, ValueError): value = int(default)
    return max(low, min(high, value))


def _aura_p013_prebuffer_seconds() -> float:
    return _aura_p013_env_float("AURA_XTTS_CONTINUITY_PREBUFFER_S", 0.85, 0.45, 3.00)


def _aura_p013_min_rate() -> float:
    return _aura_p013_env_float("AURA_XTTS_CONTINUITY_MIN_RATE", 1.08, 1.00, 1.80)


def _aura_p013_perf_snapshot() -> str:
    parts = []
    try:
        import ctypes as _ct
        class _SPS(_ct.Structure):
            _fields_ = [("ACLineStatus",_ct.c_ubyte),("BatteryFlag",_ct.c_ubyte),("BatteryLifePercent",_ct.c_ubyte),("SystemStatusFlag",_ct.c_ubyte),("BatteryLifeTime",_ct.c_ulong),("BatteryFullLifeTime",_ct.c_ulong)]
        s=_SPS()
        if _ct.windll.kernel32.GetSystemPowerStatus(_ct.byref(s)):
            ac="AC" if int(s.ACLineStatus)==1 else ("BATTERY" if int(s.ACLineStatus)==0 else "UNKNOWN")
            batt=int(s.BatteryLifePercent)
            parts.append(f"power={ac} battery={batt if batt <= 100 else -1}%")
    except Exception:
        pass
    try:
        import ctypes as _ct
        class _MEM(_ct.Structure):
            _fields_=[("dwLength",_ct.c_ulong),("dwMemoryLoad",_ct.c_ulong),("ullTotalPhys",_ct.c_ulonglong),("ullAvailPhys",_ct.c_ulonglong),("ullTotalPageFile",_ct.c_ulonglong),("ullAvailPageFile",_ct.c_ulonglong),("ullTotalVirtual",_ct.c_ulonglong),("ullAvailVirtual",_ct.c_ulonglong),("ullAvailExtendedVirtual",_ct.c_ulonglong)]
        m=_MEM(); m.dwLength=_ct.sizeof(_MEM)
        if _ct.windll.kernel32.GlobalMemoryStatusEx(_ct.byref(m)):
            parts.append(f"ram={int(m.dwMemoryLoad)}% avail={m.ullAvailPhys/(1024**3):.2f}GiB")
    except Exception:
        pass
    try:
        import subprocess as _sp
        cmd=["nvidia-smi","--query-gpu=pstate,temperature.gpu,utilization.gpu,clocks.current.sm,clocks.current.memory,power.draw,power.limit,memory.used,memory.total","--format=csv,noheader,nounits"]
        r=_sp.run(cmd,capture_output=True,text=True,timeout=2.0,creationflags=getattr(_sp,"CREATE_NO_WINDOW",0))
        if r.returncode==0 and r.stdout.strip():
            vals=[v.strip() for v in r.stdout.strip().splitlines()[0].split(",")]
            if len(vals)>=9:
                parts.append("gpu_pstate=%s temp=%sC util=%s%% sm=%sMHz memclk=%sMHz power=%s/%sW vram=%s/%sMiB" % tuple(vals[:9]))
    except Exception as exc:
        parts.append(f"gpu_telemetry=unavailable:{type(exc).__name__}")
    return " ".join(parts) if parts else "snapshot=unavailable"


def _aura_p013_apply() -> None:
    cls=globals().get("XTTSTTS")
    if cls is None: raise RuntimeError("AURA P0.1.3: XTTSTTS introuvable")
    if getattr(cls,"_aura_p013_installed",False): return
    native=getattr(cls,"_aura_p012_original_speak_native_stream",None)
    if native is None: raise RuntimeError("AURA P0.1.3: chemin natif P0.1.2 introuvable")
    # Disable P0.1.2 by restoring the exact native method it saved.
    cls._speak_native_stream=native
    # Keep P0.1.1 bridge protection but lower its gate for a healthy realtime GPU.
    globals()["_aura_p011_prebuffer_seconds"]=_aura_p013_prebuffer_seconds
    globals()["_aura_p011_min_rate"]=_aura_p013_min_rate
    desired=_aura_p013_env_int("AURA_XTTS_NATIVE_CHUNK_SIZE",18,12,32)
    try: setattr(settings,"XTTS_NATIVE_STREAM_CHUNK_SIZE",desired)
    except Exception as exc: logger.warning("XTTS P0.1.3 chunk restore failed: %s",exc)
    restored=cls._speak_native_stream
    def native_with_perf_snapshot(self,text: str):
        try: logger.info("XTTS P0.1.3 performance snapshot %s",_aura_p013_perf_snapshot())
        except Exception: logger.info("XTTS P0.1.3 performance snapshot unavailable",exc_info=True)
        return restored(self,text)
    cls._speak_native_stream=native_with_perf_snapshot
    cls._aura_p013_installed=True
    cls._aura_p012_oneshot_disabled_by_p013=True
    logger.info("XTTS P0.1.3 stream recovery active oneshot=disabled chunk_size=%d prebuffer=%.2fs min_rate=%.2fx",desired,_aura_p013_prebuffer_seconds(),_aura_p013_min_rate())


_aura_p013_apply()

# ---------------------------------------------------------------------------
# AURA P0.1.4 CUDA BOOST PRELUDE
# Wake the NVIDIA compute GPU immediately before XTTS without changing global
# Windows/NVIDIA settings. P0.1.1 continuity guard remains the safety net.
# ---------------------------------------------------------------------------
def _aura_p014_env_int(name: str, default: int, low: int, high: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try: value = int(raw)
    except (TypeError, ValueError): value = int(default)
    return max(low, min(high, value))


def _aura_p014_env_bool(name: str, default: bool=False) -> bool:
    raw = os.getenv(name, "1" if default else "0").strip().lower()
    return raw in {"1","true","yes","on","oui"}


def _aura_p014_on_ac() -> bool:
    try:
        import ctypes as _ct
        class _SPS(_ct.Structure):
            _fields_=[("ACLineStatus",_ct.c_ubyte),("BatteryFlag",_ct.c_ubyte),("BatteryLifePercent",_ct.c_ubyte),("SystemStatusFlag",_ct.c_ubyte),("BatteryLifeTime",_ct.c_ulong),("BatteryFullLifeTime",_ct.c_ulong)]
        s=_SPS()
        if _ct.windll.kernel32.GetSystemPowerStatus(_ct.byref(s)):
            return int(s.ACLineStatus)==1
    except Exception:
        pass
    return True


_AURA_P014_RAMP_CACHE = {}

def _aura_p014_cuda_ramp():
    if _aura_p014_env_bool("AURA_XTTS_CUDA_RAMP_DISABLE", False):
        return False, 0.0, 0, "disabled"
    if (not _aura_p014_on_ac()) and (not _aura_p014_env_bool("AURA_XTTS_CUDA_RAMP_ON_BATTERY", False)):
        return False, 0.0, 0, "battery-skip"
    try:
        import time as _time
        import torch as _torch
        if not _torch.cuda.is_available():
            return False, 0.0, 0, "cuda-unavailable"
        target_ms=_aura_p014_env_int("AURA_XTTS_CUDA_RAMP_MS",220,80,500)
        size=_aura_p014_env_int("AURA_XTTS_CUDA_RAMP_SIZE",1536,768,2048)
        dev=_torch.device("cuda")
        key=(int(_torch.cuda.current_device()),size)
        cache=_AURA_P014_RAMP_CACHE.get(key)
        if cache is None:
            a=_torch.randn((size,size),device=dev,dtype=_torch.float16)
            b=_torch.randn((size,size),device=dev,dtype=_torch.float16)
            c=_torch.empty((size,size),device=dev,dtype=_torch.float16)
            cache=(a,b,c); _AURA_P014_RAMP_CACHE[key]=cache
        a,b,c=cache
        _torch.cuda.synchronize()
        t0=_time.perf_counter(); loops=0
        with _torch.no_grad():
            while ((_time.perf_counter()-t0)*1000.0) < target_ms and loops < 64:
                for _ in range(4):
                    _torch.mm(a,b,out=c); loops += 1
                _torch.cuda.synchronize()
        elapsed=_time.perf_counter()-t0
        return True, elapsed, loops, f"size={size}"
    except Exception as exc:
        return False, 0.0, 0, f"{type(exc).__name__}:{exc}"


def _aura_p014_apply() -> None:
    cls=globals().get("XTTSTTS")
    if cls is None: raise RuntimeError("AURA P0.1.4: XTTSTTS introuvable")
    if getattr(cls,"_aura_p014_installed",False): return
    previous=getattr(cls,"_speak_native_stream",None)
    if previous is None: raise RuntimeError("AURA P0.1.4: _speak_native_stream introuvable")
    def native_with_cuda_boost(self,text: str):
        try:
            snap=globals().get("_aura_p013_perf_snapshot")
            if callable(snap): logger.info("XTTS P0.1.4 boost BEFORE %s",snap())
        except Exception:
            logger.info("XTTS P0.1.4 boost BEFORE unavailable",exc_info=True)
        ok,elapsed,loops,detail=_aura_p014_cuda_ramp()
        try:
            snap=globals().get("_aura_p013_perf_snapshot")
            after=snap() if callable(snap) else "snapshot=unavailable"
            logger.info("XTTS P0.1.4 boost AFTER ok=%s elapsed=%.3fs loops=%d %s %s",ok,elapsed,loops,detail,after)
        except Exception:
            logger.info("XTTS P0.1.4 boost AFTER ok=%s elapsed=%.3fs loops=%d %s",ok,elapsed,loops,detail)
        return previous(self,text)
    cls._aura_p014_previous_speak_native_stream=previous
    cls._speak_native_stream=native_with_cuda_boost
    cls._aura_p014_installed=True
    logger.info("XTTS P0.1.4 CUDA boost prelude active ramp_ms=%d size=%d battery=%s",_aura_p014_env_int("AURA_XTTS_CUDA_RAMP_MS",220,80,500),_aura_p014_env_int("AURA_XTTS_CUDA_RAMP_SIZE",1536,768,2048),"allowed" if _aura_p014_env_bool("AURA_XTTS_CUDA_RAMP_ON_BATTERY",False) else "skip")


_aura_p014_apply()

# ---------------------------------------------------------------------------
# AURA P0.1.5 WINDOWS PROCESS QOS RECOVERY
# Remove local process throttling / background QoS without changing the global
# Windows power plan. P0.1.1 continuity and P0.1.3 native streaming stay active.
# P0.1.4 CUDA pre-ramp is disabled because it did not improve XTTS throughput.
# ---------------------------------------------------------------------------
def _aura_p015_windows_qos_snapshot() -> str:
    parts=[]
    try:
        import ctypes as _ct
        from ctypes import wintypes as _wt
        k32=_ct.windll.kernel32
        h=k32.GetCurrentProcess()
        pr=int(k32.GetPriorityClass(h))
        parts.append(f"priority=0x{pr:04X}")
        class _PPT(_ct.Structure):
            _fields_=[("Version",_wt.DWORD),("ControlMask",_wt.DWORD),("StateMask",_wt.DWORD)]
        st=_PPT(); st.Version=1
        try:
            ok=bool(k32.GetProcessInformation(h,4,_ct.byref(st),_ct.sizeof(st)))
            if ok:
                parts.append(f"power_throttle_control=0x{int(st.ControlMask):X} state=0x{int(st.StateMask):X}")
        except Exception:
            pass
        class _MPI(_ct.Structure):
            _fields_=[("MemoryPriority",_wt.ULONG)]
        mi=_MPI()
        try:
            ok=bool(k32.GetProcessInformation(h,0,_ct.byref(mi),_ct.sizeof(mi)))
            if ok: parts.append(f"mem_priority={int(mi.MemoryPriority)}")
        except Exception:
            pass
    except Exception as exc:
        parts.append(f"win_qos=unavailable:{type(exc).__name__}")
    try:
        import psutil as _ps
        f=_ps.cpu_freq()
        if f:
            parts.append(f"cpu_mhz={float(f.current):.0f}/{float(f.max):.0f}")
        parts.append(f"cpu_load={float(_ps.cpu_percent(interval=None)):.0f}%")
        p=_ps.Process()
        try: parts.append(f"affinity={len(p.cpu_affinity())}")
        except Exception: pass
    except Exception:
        parts.append(f"logical_cpu={os.cpu_count() or 0}")
    try:
        import torch as _torch
        parts.append(f"torch_threads={int(_torch.get_num_threads())}/{int(_torch.get_num_interop_threads())}")
    except Exception:
        pass
    return " ".join(parts)


def _aura_p015_apply_windows_qos() -> str:
    result=[]
    if os.name != "nt":
        return "non-windows"
    try:
        import ctypes as _ct
        from ctypes import wintypes as _wt
        k32=_ct.windll.kernel32
        h=k32.GetCurrentProcess()
        # End explicit PROCESS_MODE_BACKGROUND if Aura inherited/entered it.
        try:
            PROCESS_MODE_BACKGROUND_END=0x00200000
            if k32.SetPriorityClass(h, PROCESS_MODE_BACKGROUND_END):
                result.append("background=end")
            else:
                result.append("background=not-active")
        except Exception:
            result.append("background=unknown")
        # ABOVE_NORMAL is intentionally below HIGH/REALTIME: enough to prevent
        # starvation while keeping the desktop responsive.
        try:
            current=int(k32.GetPriorityClass(h))
            HIGH_PRIORITY_CLASS=0x00000080
            REALTIME_PRIORITY_CLASS=0x00000100
            ABOVE_NORMAL_PRIORITY_CLASS=0x00008000
            if current not in (HIGH_PRIORITY_CLASS, REALTIME_PRIORITY_CLASS):
                if k32.SetPriorityClass(h, ABOVE_NORMAL_PRIORITY_CLASS):
                    result.append("priority=above-normal")
                else:
                    result.append("priority=set-failed")
            else:
                result.append(f"priority=kept-0x{current:X}")
        except Exception:
            result.append("priority=unknown")
        # Re-enable normal Windows dynamic priority boosts for the process.
        try:
            if k32.SetProcessPriorityBoost(h, False):
                result.append("priority_boost=enabled")
        except Exception:
            pass
        # Explicitly opt OUT of execution-speed power throttling / EcoQoS.
        try:
            class _PPT(_ct.Structure):
                _fields_=[("Version",_wt.DWORD),("ControlMask",_wt.DWORD),("StateMask",_wt.DWORD)]
            PROCESS_POWER_THROTTLING_CURRENT_VERSION=1
            PROCESS_POWER_THROTTLING_EXECUTION_SPEED=0x1
            st=_PPT(PROCESS_POWER_THROTTLING_CURRENT_VERSION, PROCESS_POWER_THROTTLING_EXECUTION_SPEED, 0)
            if k32.SetProcessInformation(h,4,_ct.byref(st),_ct.sizeof(st)):
                result.append("exec_throttle=off")
            else:
                result.append("exec_throttle=set-failed")
        except Exception:
            result.append("exec_throttle=unknown")
        # Normal/high memory priority reduces paging sensitivity when XTTS is
        # resident and physical headroom is only ~3-4 GiB.
        try:
            class _MPI(_ct.Structure):
                _fields_=[("MemoryPriority",_wt.ULONG)]
            mi=_MPI(5)
            if k32.SetProcessInformation(h,0,_ct.byref(mi),_ct.sizeof(mi)):
                result.append("mem_priority=5")
            else:
                result.append("mem_priority=set-failed")
        except Exception:
            result.append("mem_priority=unknown")
    except Exception as exc:
        result.append(f"qos_error={type(exc).__name__}:{exc}")
    return " ".join(result)


_AURA_P015_QOS_BEFORE=_aura_p015_windows_qos_snapshot()
_AURA_P015_QOS_RESULT=_aura_p015_apply_windows_qos()
_AURA_P015_QOS_AFTER=_aura_p015_windows_qos_snapshot()
logger.info("XTTS P0.1.5 QoS BEFORE %s", _AURA_P015_QOS_BEFORE)
logger.info("XTTS P0.1.5 QoS APPLY %s", _AURA_P015_QOS_RESULT)
logger.info("XTTS P0.1.5 QoS AFTER %s", _AURA_P015_QOS_AFTER)


def _aura_p015_apply() -> None:
    cls=globals().get("XTTSTTS")
    if cls is None: raise RuntimeError("AURA P0.1.5: XTTSTTS introuvable")
    if getattr(cls,"_aura_p015_installed",False): return
    # Disable the P0.1.4 CUDA ramp and return to its saved P0.1.3 method.
    base=getattr(cls,"_aura_p014_previous_speak_native_stream",None)
    if base is None:
        base=getattr(cls,"_speak_native_stream",None)
    if base is None: raise RuntimeError("AURA P0.1.5: chemin natif XTTS introuvable")
    cls._speak_native_stream=base
    def native_with_qos(self,text: str):
        # Re-assert process-local QoS in case Windows changed it while idle.
        try:
            applied=_aura_p015_apply_windows_qos()
            logger.info("XTTS P0.1.5 runtime QoS %s snapshot=%s",applied,_aura_p015_windows_qos_snapshot())
        except Exception:
            logger.info("XTTS P0.1.5 runtime QoS unavailable",exc_info=True)
        return base(self,text)
    cls._speak_native_stream=native_with_qos
    cls._aura_p015_installed=True
    cls._aura_p014_disabled_by_p015=True
    logger.info("XTTS P0.1.5 process QoS recovery active cuda_ramp=disabled priority=above-normal exec_throttle=off mem_priority=5")


_aura_p015_apply()

# ---------------------------------------------------------------------------
# AURA P0.1.5.1 PROCESS QOS WIN64 HANDLE FIX
# Correct Win32 ctypes prototypes used by P0.1.5.
# No global Windows/NVIDIA power-plan changes.
# ---------------------------------------------------------------------------
def _aura_p0151_kernel32():
    import ctypes as _ct
    from ctypes import wintypes as _wt
    k32=_ct.WinDLL("kernel32", use_last_error=True)

    k32.GetCurrentProcess.argtypes=[]
    k32.GetCurrentProcess.restype=_wt.HANDLE

    k32.GetPriorityClass.argtypes=[_wt.HANDLE]
    k32.GetPriorityClass.restype=_wt.DWORD

    k32.SetPriorityClass.argtypes=[_wt.HANDLE,_wt.DWORD]
    k32.SetPriorityClass.restype=_wt.BOOL

    k32.SetProcessPriorityBoost.argtypes=[_wt.HANDLE,_wt.BOOL]
    k32.SetProcessPriorityBoost.restype=_wt.BOOL

    k32.SetProcessInformation.argtypes=[_wt.HANDLE,_ct.c_int,_ct.c_void_p,_wt.DWORD]
    k32.SetProcessInformation.restype=_wt.BOOL

    k32.GetProcessInformation.argtypes=[_wt.HANDLE,_ct.c_int,_ct.c_void_p,_wt.DWORD]
    k32.GetProcessInformation.restype=_wt.BOOL
    return k32,_ct,_wt


def _aura_p0151_err(_ct) -> int:
    try:
        return int(_ct.get_last_error())
    except Exception:
        return -1


def _aura_p015_windows_qos_snapshot() -> str:
    parts=[]
    if os.name != "nt":
        return "non-windows"
    try:
        k32,_ct,_wt=_aura_p0151_kernel32()
        h=k32.GetCurrentProcess()

        pr=int(k32.GetPriorityClass(h))
        if pr:
            parts.append(f"priority=0x{pr:04X}")
        else:
            parts.append(f"priority=failed:{_aura_p0151_err(_ct)}")

        class _PPT(_ct.Structure):
            _fields_=[("Version",_wt.ULONG),("ControlMask",_wt.ULONG),("StateMask",_wt.ULONG)]
        st=_PPT()
        st.Version=1
        _ct.set_last_error(0)
        if k32.GetProcessInformation(h,4,_ct.byref(st),_ct.sizeof(st)):
            parts.append(f"power_throttle_control=0x{int(st.ControlMask):X} state=0x{int(st.StateMask):X}")
        else:
            parts.append(f"power_throttle_query_failed={_aura_p0151_err(_ct)}")

        class _MPI(_ct.Structure):
            _fields_=[("MemoryPriority",_wt.ULONG)]
        mi=_MPI()
        _ct.set_last_error(0)
        if k32.GetProcessInformation(h,0,_ct.byref(mi),_ct.sizeof(mi)):
            parts.append(f"mem_priority={int(mi.MemoryPriority)}")
        else:
            parts.append(f"mem_query_failed={_aura_p0151_err(_ct)}")
    except Exception as exc:
        parts.append(f"win_qos=unavailable:{type(exc).__name__}:{exc}")

    try:
        import psutil as _ps
        p=_ps.Process()
        try:
            parts.append(f"psutil_priority={int(p.nice())}")
        except Exception:
            pass
        f=_ps.cpu_freq()
        if f:
            parts.append(f"cpu_mhz={float(f.current):.0f}/{float(f.max):.0f}")
        parts.append(f"cpu_load={float(_ps.cpu_percent(interval=None)):.0f}%")
        try:
            parts.append(f"affinity={len(p.cpu_affinity())}")
        except Exception:
            pass
    except Exception:
        parts.append(f"logical_cpu={os.cpu_count() or 0}")

    try:
        import torch as _torch
        parts.append(f"torch_threads={int(_torch.get_num_threads())}/{int(_torch.get_num_interop_threads())}")
    except Exception:
        pass
    return " ".join(parts)


def _aura_p015_apply_windows_qos() -> str:
    result=[]
    if os.name != "nt":
        return "non-windows"
    try:
        k32,_ct,_wt=_aura_p0151_kernel32()
        h=k32.GetCurrentProcess()

        ABOVE_NORMAL_PRIORITY_CLASS=0x00008000
        HIGH_PRIORITY_CLASS=0x00000080
        REALTIME_PRIORITY_CLASS=0x00000100

        current=int(k32.GetPriorityClass(h))
        if current in (HIGH_PRIORITY_CLASS,REALTIME_PRIORITY_CLASS):
            result.append(f"priority=kept-0x{current:X}")
        else:
            _ct.set_last_error(0)
            if k32.SetPriorityClass(h,ABOVE_NORMAL_PRIORITY_CLASS):
                result.append("priority=above-normal")
            else:
                err=_aura_p0151_err(_ct)
                try:
                    import psutil as _ps
                    _ps.Process().nice(_ps.ABOVE_NORMAL_PRIORITY_CLASS)
                    result.append(f"priority=above-normal-psutil(winerr={err})")
                except Exception as pexc:
                    result.append(f"priority=set-failed:{err}:{type(pexc).__name__}")

        _ct.set_last_error(0)
        if k32.SetProcessPriorityBoost(h,False):
            result.append("priority_boost=enabled")
        else:
            result.append(f"priority_boost_failed={_aura_p0151_err(_ct)}")

        class _PPT(_ct.Structure):
            _fields_=[("Version",_wt.ULONG),("ControlMask",_wt.ULONG),("StateMask",_wt.ULONG)]
        PROCESS_POWER_THROTTLING_CURRENT_VERSION=1
        PROCESS_POWER_THROTTLING_EXECUTION_SPEED=0x1
        st=_PPT(PROCESS_POWER_THROTTLING_CURRENT_VERSION,
                PROCESS_POWER_THROTTLING_EXECUTION_SPEED,
                0)
        _ct.set_last_error(0)
        if k32.SetProcessInformation(h,4,_ct.byref(st),_ct.sizeof(st)):
            result.append("exec_throttle=off")
        else:
            result.append(f"exec_throttle=set-failed:{_aura_p0151_err(_ct)}")

        class _MPI(_ct.Structure):
            _fields_=[("MemoryPriority",_wt.ULONG)]
        mi=_MPI(5)
        _ct.set_last_error(0)
        if k32.SetProcessInformation(h,0,_ct.byref(mi),_ct.sizeof(mi)):
            result.append("mem_priority=5")
        else:
            result.append(f"mem_priority=set-failed:{_aura_p0151_err(_ct)}")
    except Exception as exc:
        result.append(f"qos_error={type(exc).__name__}:{exc}")
    return " ".join(result)


_AURA_P0151_BEFORE=_aura_p015_windows_qos_snapshot()
_AURA_P0151_APPLY=_aura_p015_apply_windows_qos()
_AURA_P0151_AFTER=_aura_p015_windows_qos_snapshot()
logger.info("XTTS P0.1.5.1 QoS BEFORE %s",_AURA_P0151_BEFORE)
logger.info("XTTS P0.1.5.1 QoS APPLY %s",_AURA_P0151_APPLY)
logger.info("XTTS P0.1.5.1 QoS AFTER %s",_AURA_P0151_AFTER)
logger.info("XTTS P0.1.5.1 Win64 handle fix active typed_kernel32=True getlasterror=True")

# ---------------------------------------------------------------------------
# AURA P0.1.5.2 QOS CONDITIONAL CUDA WAKE
# ---------------------------------------------------------------------------
def _aura_p0152_parse_perf_snapshot(text: str) -> dict:
    import re as _re
    out={}
    s=str(text or "")
    for key,pat in {
        "pstate":r"gpu_pstate=(P\d+)",
        "sm":r"\bsm=(\d+)MHz",
        "mem":r"\bmemclk=(\d+)MHz",
    }.items():
        m=_re.search(pat,s)
        if m:
            out[key]=m.group(1) if key=="pstate" else float(m.group(1))
    return out

def _aura_p0152_should_wake(snapshot: str):
    d=_aura_p0152_parse_perf_snapshot(snapshot)
    p=str(d.get("pstate",""))
    sm=float(d.get("sm",0.0) or 0.0)
    mem=float(d.get("mem",0.0) or 0.0)
    reasons=[]
    if p in {"P5","P8","P12"}: reasons.append(f"pstate={p}")
    if sm and sm < 900: reasons.append(f"sm={sm:.0f}MHz")
    if mem and mem < 3000: reasons.append(f"mem={mem:.0f}MHz")
    return bool(reasons), ",".join(reasons) if reasons else "gpu-ready"

def _aura_p0152_apply() -> None:
    cls=globals().get("XTTSTTS")
    if cls is None: raise RuntimeError("AURA P0.1.5.2: XTTSTTS introuvable")
    if getattr(cls,"_aura_p0152_installed",False): return
    previous=getattr(cls,"_speak_native_stream",None)
    if previous is None: raise RuntimeError("AURA P0.1.5.2: _speak_native_stream introuvable")
    os.environ.setdefault("AURA_XTTS_CUDA_RAMP_MS","140")

    def native_with_qos_cuda_wake(self,text: str):
        try:
            qos=globals().get("_aura_p015_apply_windows_qos")
            if callable(qos):
                logger.info("XTTS P0.1.5.2 prewake QoS %s",qos())
        except Exception:
            logger.info("XTTS P0.1.5.2 prewake QoS unavailable",exc_info=True)

        snap_fn=globals().get("_aura_p013_perf_snapshot")
        before="snapshot=unavailable"
        try:
            if callable(snap_fn): before=snap_fn()
        except Exception: pass

        run,reason=_aura_p0152_should_wake(before)
        if run:
            ramp=globals().get("_aura_p014_cuda_ramp")
            if callable(ramp):
                try:
                    ok,elapsed,loops,detail=ramp()
                    after=snap_fn() if callable(snap_fn) else "snapshot=unavailable"
                    logger.info("XTTS P0.1.5.2 CUDA WAKE run reason=%s ok=%s elapsed=%.3fs loops=%d %s before=[%s] after=[%s]",
                                reason,ok,elapsed,loops,detail,before,after)
                except Exception:
                    logger.info("XTTS P0.1.5.2 CUDA WAKE failed reason=%s before=[%s]",reason,before,exc_info=True)
            else:
                logger.info("XTTS P0.1.5.2 CUDA WAKE unavailable helper-missing before=[%s]",before)
        else:
            logger.info("XTTS P0.1.5.2 CUDA WAKE skip reason=%s before=[%s]",reason,before)

        return previous(self,text)

    cls._aura_p0152_previous_speak_native_stream=previous
    cls._speak_native_stream=native_with_qos_cuda_wake
    cls._aura_p0152_installed=True
    logger.info("XTTS P0.1.5.2 QoS conditional CUDA wake active threshold=pstate(P5/P8/P12)|sm<900|mem<3000 ramp_ms=%s",
                os.getenv("AURA_XTTS_CUDA_RAMP_MS","140"))

_aura_p0152_apply()

# AURA v0.8.6.7 - repeat XTTS warmup reuse
import time as _aura_v0867_time

_AURA_V0867_ORIGINAL_XTTS_WARMUP = XTTSTTS.warmup


def _aura_v0867_xtts_warmup(self):
    cls = self.__class__
    shared_loaded = False
    try:
        shared_loaded = bool(cls.shared_model_loaded())
    except Exception:
        shared_loaded = False

    if bool(getattr(cls, "_aura_v0867_warmup_ready", False)) and shared_loaded:
        logger.info("XTTS warmup reuse PASS shared_model_loaded=True elapsed=0.000s")
        return None

    started = _aura_v0867_time.perf_counter()
    result = _AURA_V0867_ORIGINAL_XTTS_WARMUP(self)
    elapsed = _aura_v0867_time.perf_counter() - started

    try:
        shared_loaded = bool(cls.shared_model_loaded())
    except Exception:
        shared_loaded = False

    if shared_loaded:
        setattr(cls, "_aura_v0867_warmup_ready", True)

    logger.info(
        "XTTS warmup v0867 completed elapsed=%.3fs shared_model_loaded=%s",
        elapsed,
        shared_loaded,
    )
    return result


XTTSTTS.warmup = _aura_v0867_xtts_warmup

# AURA I18N R5 — persisted TTS language authority
def _aura_i18n_tts_language() -> str:
    try:
        import json as _json
        from pathlib import Path as _Path
        _base = os.environ.get("APPDATA") or str(_Path.home() / "AppData" / "Roaming")
        _p = _Path(_base) / "AURA" / "config" / "locale.json"
        if _p.is_file():
            _loc = str(_json.loads(_p.read_text(encoding="utf-8")).get("locale") or "").strip()
            if _loc == "en-US": return "en"
            if _loc == "fr-FR": return "fr"
    except Exception:
        pass
    _raw = str(os.environ.get("AURA_TTS_LANGUAGE") or os.environ.get("STT_LANGUAGE") or "fr").strip().lower()
    return "en" if _raw.startswith("en") else "fr"
