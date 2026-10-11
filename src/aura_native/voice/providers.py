from __future__ import annotations

from typing import Any, Protocol
import importlib
import os
import threading
import time


ASSISTANT_NAME = "AURA"
ASSISTANT_CONTEXT_PROMPT = f"Vous parlez avec l'assistante {ASSISTANT_NAME}."


def _ptt_trace(message: str) -> None:
    if os.environ.get("AURA_PTT_DIAGNOSTICS") == "1":
        print(message, flush=True)


class AudioInputAdapter(Protocol):
    """Explicitly-started audio input. Construction must be side-effect free."""
    def start(self) -> None: ...
    def stop(self) -> Any: ...
    def cancel(self) -> None: ...


class STTProvider(Protocol):
    def transcribe(self, audio: Any) -> str: ...


class TTSProvider(Protocol):
    def speak(self, text: str) -> Any: ...
    def stop(self) -> None: ...


class FakeSTT:
    """Deterministic offline STT used by tests and evidence harnesses."""
    def __init__(self, transcript: str = "") -> None:
        self.transcript = str(transcript)
        self.calls = 0

    def transcribe(self, audio: Any) -> str:
        self.calls += 1
        return self.transcript


class FakeTTS:
    """Offline TTS recorder; never opens an audio device."""
    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stop_calls = 0

    def speak(self, text: str) -> None:
        self.spoken.append(str(text))

    def stop(self) -> None:
        self.stop_calls += 1


class FakeAudioInput:
    """Small explicit adapter for controller tests; no microphone access."""
    def __init__(self, audio: Any = b"") -> None:
        self.audio = audio
        self.started = 0
        self.stopped = 0
        self.cancelled = 0

    def start(self) -> None:
        self.started += 1

    def stop(self) -> Any:
        self.stopped += 1
        return self.audio

    def cancel(self) -> None:
        self.cancelled += 1


class SoundDeviceAudioInput:
    """Lazy Windows sounddevice adapter; never opens a device on construction."""
    def __init__(self, *, device=None, samplerate: int = 16000,
                 channels: int = 1, max_seconds: float = 30.0) -> None:
        self.device = device
        self.samplerate = int(samplerate)
        self.channels = max(1, int(channels))
        self.max_seconds = max(0.1, float(max_seconds))
        self._sd = None
        self._stream = None
        self._frames: list[Any] = []
        self._started = False
        self._callback_seen = False

    @staticmethod
    def _module():
        try:
            sd = importlib.import_module("sounddevice")
        except Exception as exc:
            raise RuntimeError("AUDIO_UNAVAILABLE") from exc
        return sd

    @classmethod
    def list_input_devices(cls) -> list[dict[str, Any]]:
        sd = cls._module()
        result = []
        default = getattr(getattr(sd, "default", None), "device", None)
        default_input = getattr(default, "input", default[0] if isinstance(default, (tuple, list)) else None)
        for index, info in enumerate(sd.query_devices()):
            channels = int(info.get("max_input_channels", 0) or 0)
            if channels <= 0:
                continue
            result.append({"id": index, "index": index, "name": str(info.get("name", index)),
                           "default": index == default_input,
                           "max_input_channels": channels,
                           "default_samplerate": float(info.get("default_samplerate", 0) or 0)})
        return result

    def resolve_input_device(self) -> int:
        """Resolve one concrete compatible input device without opening it."""
        sd = self._module()
        _ptt_trace("PTT_AUDIO_RESOLVE_START")
        devices = self.list_input_devices()
        compatible: list[dict[str, Any]] = []
        for item in devices:
            try:
                sd.check_input_settings(
                    device=item["index"], samplerate=self.samplerate,
                    channels=self.channels, dtype="float32"
                )
                compatible.append(item)
            except Exception:
                continue
        if not compatible:
            raise RuntimeError("NO_COMPATIBLE_INPUT_DEVICE")

        selected = None
        if isinstance(self.device, int):
            selected = next((item for item in compatible if item["index"] == self.device), None)
        elif isinstance(self.device, str) and self.device.strip():
            wanted = self.device.strip().casefold()
            selected = next((item for item in compatible if item["name"].casefold() == wanted), None)
            if selected is None:
                selected = next((item for item in compatible if wanted in item["name"].casefold()), None)
        if selected is None:
            selected = next((item for item in compatible if item.get("default")), None)
        if selected is None:
            selected = max(
                compatible,
                key=lambda item: (
                    int(item.get("max_input_channels", 0)),
                    float(item.get("default_samplerate", 0)),
                    -int(item["index"]),
                ),
            )
        resolved = int(selected["index"])
        _ptt_trace(f"PTT_AUDIO_RESOLVE_OK index={resolved}")
        return resolved

    def start(self) -> None:
        if self._started:
            return
        self._sd = self._module()
        self._frames = []
        self._callback_seen = False
        _ptt_trace(f"PTT_AUDIO_START_REQUEST device={self.device!r} samplerate={self.samplerate} channels={self.channels}")
        def callback(indata, frames, time_info, status):
            if status:
                return
            if not self._callback_seen:
                self._callback_seen = True
                _ptt_trace("PTT_AUDIO_CALLBACK_ACTIVE")
            self._frames.append(indata.copy())
        try:
            resolved_device = self.resolve_input_device()
            self._sd.check_input_settings(device=resolved_device, samplerate=self.samplerate,
                                          channels=self.channels, dtype="float32")
            _ptt_trace("PTT_AUDIO_CHECK_SETTINGS_OK")
            _ptt_trace("PTT_AUDIO_STREAM_CREATE_BEGIN")
            try:
                self._stream = self._sd.InputStream(device=resolved_device, samplerate=self.samplerate,
                                                    channels=self.channels, dtype="float32",
                                                    callback=callback, blocksize=0)
            except Exception as exc:
                _ptt_trace(f"PTT_AUDIO_STREAM_CREATE_ERROR:{type(exc).__name__}")
                raise
            _ptt_trace("PTT_AUDIO_STREAM_CREATE_OK")
            _ptt_trace("PTT_AUDIO_STREAM_START_BEGIN")
            try:
                self._stream.start()
            except Exception as exc:
                _ptt_trace(f"PTT_AUDIO_STREAM_START_ERROR:{type(exc).__name__}")
                raise
            _ptt_trace("PTT_AUDIO_STREAM_START_OK")
            self._started = True
        except Exception as exc:
            stream = self._stream
            self._stream = None
            if stream is not None:
                try:
                    stream.close()
                except Exception:
                    pass
            _ptt_trace(f"PTT_AUDIO_START_ERROR type={type(exc).__name__}")
            raise RuntimeError("DEVICE_UNAVAILABLE") from exc

    def stop(self) -> Any:
        stream = self._stream
        self._stream = None
        self._started = False
        if stream is not None:
            try:
                stream.stop(); stream.close()
            except Exception:
                pass
        _ptt_trace(f"PTT_AUDIO_STOP frames={len(self._frames)}")
        if not self._frames:
            raise RuntimeError("NO_AUDIO")
        try:
            np = importlib.import_module("numpy")
            audio = np.asarray(np.concatenate(self._frames, axis=0), dtype=np.float32)
            if audio.ndim == 2 and audio.shape[1] == 1:
                audio = audio[:, 0]
            elif audio.ndim != 1:
                audio = audio.reshape(-1)
            samples = int(audio.size)
            duration_ms = int(round(samples * 1000 / self.samplerate))
            _ptt_trace(f"PTT_AUDIO_STOP_RESULT_TYPE={type(audio).__name__}")
            _ptt_trace(f"PTT_AUDIO_STOP_CHUNKS={len(self._frames)}")
            _ptt_trace(f"PTT_AUDIO_STOP_SAMPLES={samples}")
            _ptt_trace(f"PTT_AUDIO_STOP_SHAPE={audio.shape}")
            _ptt_trace(f"PTT_AUDIO_STOP_DTYPE={audio.dtype}")
            _ptt_trace(f"PTT_AUDIO_STOP_DURATION_MS={duration_ms}")
            _ptt_trace(f"PTT_AUDIO_STOP_EMPTY={'true' if samples == 0 else 'false'}")
            return audio
        except Exception:
            return list(self._frames)

    def cancel(self) -> None:
        self._frames = []
        stream = self._stream
        self._stream = None
        self._started = False
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass

    def capabilities(self) -> list[dict[str, Any]]:
        """Validate candidate input settings without opening a stream."""
        sd = self._module()
        result = []
        for item in self.list_input_devices():
            try:
                sd.check_input_settings(device=item["index"], samplerate=self.samplerate,
                                        channels=self.channels, dtype="float32")
                item = dict(item)
                item["valid"] = True
            except Exception:
                item = dict(item)
                item["valid"] = False
            result.append(item)
        return result


class WhisperSTTProvider:
    """Lazy local Whisper/faster-whisper provider with no model download."""
    def __init__(self, *, model_path: str = "", language: str = "fr",
                 assistant_name: str = ASSISTANT_NAME) -> None:
        self.model_path, self.language = str(model_path or ""), str(language or "fr")
        self.assistant_name = str(assistant_name or ASSISTANT_NAME)
        self._model = None
        self._bias_method = "none"

    def initialize(self) -> None:
        if not self.model_path:
            raise RuntimeError("MODEL_MISSING")
        started = time.perf_counter()
        try:
            WhisperModel = getattr(importlib.import_module("faster_whisper"), "WhisperModel")
            self._model = WhisperModel(self.model_path, device="cpu", compute_type="int8")
        except ImportError:
            try:
                whisper = importlib.import_module("whisper")
                self._model = whisper.load_model(self.model_path, download_root=self.model_path)
            except Exception as exc:
                raise RuntimeError("STT_UNAVAILABLE") from exc
        except Exception as exc:
            raise RuntimeError("MODEL_MISSING") from exc
        finally:
            if self._model is not None:
                _ptt_trace(f"PTT_STT_MODEL_READY load_ms={int((time.perf_counter()-started)*1000)} thread={threading.get_ident()}")

    def transcribe(self, audio: Any) -> str:
        if audio is None:
            raise RuntimeError("NO_AUDIO")
        call_started = time.perf_counter()
        _ptt_trace(f"PTT_STT_CALL_BEGIN thread={threading.get_ident()}")
        if self._model is None:
            self.initialize()
        else:
            _ptt_trace("PTT_STT_MODEL_READY cached=true")
        try:
            if hasattr(self._model, "transcribe"):
                transcribe_started = time.perf_counter()
                kwargs = {"language": self.language, "task": "transcribe"}
                try:
                    import inspect
                    parameters = inspect.signature(self._model.transcribe).parameters
                    accepts_kwargs = any(parameter.kind is inspect.Parameter.VAR_KEYWORD
                                         for parameter in parameters.values())
                    supports_hotwords = "hotwords" in parameters or accepts_kwargs
                    supports_prompt = "initial_prompt" in parameters or accepts_kwargs
                    if self.assistant_name and supports_hotwords:
                        kwargs["hotwords"] = self.assistant_name
                    if self.assistant_name and supports_prompt:
                        kwargs["initial_prompt"] = ASSISTANT_CONTEXT_PROMPT.replace(ASSISTANT_NAME, self.assistant_name)
                    if "hotwords" in kwargs and "initial_prompt" in kwargs:
                        self._bias_method = "hotwords+initial_prompt"
                    elif "hotwords" in kwargs:
                        self._bias_method = "hotwords"
                    elif "initial_prompt" in kwargs:
                        self._bias_method = "initial_prompt"
                    else:
                        self._bias_method = "none"
                except (TypeError, ValueError):
                    self._bias_method = "none"
                _ptt_trace(f"PTT_STT_CONTEXT_BIAS assistant_name={self.assistant_name} method={self._bias_method}")
                result = self._model.transcribe(audio, **kwargs)
                _ptt_trace(f"PTT_STT_TRANSCRIBE_RETURNED duration_ms={int((time.perf_counter()-transcribe_started)*1000)}")
                if isinstance(result, tuple):
                    result = result[0]
                if isinstance(result, str):
                    text = result.strip()
                    _ptt_trace(f"PTT_STT_TEXT_LENGTH={len(text)}")
                    _ptt_trace(f"PTT_STT_CALL_END duration_ms={int((time.perf_counter()-call_started)*1000)}")
                    if not text: _ptt_trace("PTT_STT_EMPTY")
                    if text: _ptt_trace(f'PTT_STT_TRANSCRIPT text="{text}"')
                    _ptt_trace("PTT_STT_TRANSCRIPT_READY")
                    return text
                if isinstance(result, dict):
                    segments = result.get("segments", [])
                    _ptt_trace("PTT_STT_SEGMENT_ITERATION_BEGIN")
                    texts = [str(x.get("text", "")).strip() for x in segments]
                    _ptt_trace("PTT_STT_SEGMENT_ITERATION_END")
                    text = " ".join(x for x in texts if x)
                    _ptt_trace(f"PTT_STT_SEGMENT_COUNT={len(texts)}")
                    _ptt_trace(f"PTT_STT_TEXT_LENGTH={len(text)}")
                    _ptt_trace(f"PTT_STT_CALL_END duration_ms={int((time.perf_counter()-call_started)*1000)}")
                    if not text: _ptt_trace("PTT_STT_EMPTY")
                    if text: _ptt_trace(f'PTT_STT_TRANSCRIPT text="{text}"')
                    _ptt_trace("PTT_STT_TRANSCRIPT_READY")
                    return text
                try:
                    _ptt_trace("PTT_STT_SEGMENT_ITERATION_BEGIN")
                    texts = (str(getattr(segment, "text", "")).strip() for segment in result)
                    collected = [text for text in texts if text]
                    _ptt_trace("PTT_STT_SEGMENT_ITERATION_END")
                    text = " ".join(collected)
                    _ptt_trace(f"PTT_STT_SEGMENT_COUNT={len(collected)}")
                    _ptt_trace(f"PTT_STT_TEXT_LENGTH={len(text)}")
                    _ptt_trace(f"PTT_STT_CALL_END duration_ms={int((time.perf_counter()-call_started)*1000)}")
                    if not text: _ptt_trace("PTT_STT_EMPTY")
                    if text: _ptt_trace(f'PTT_STT_TRANSCRIPT text="{text}"')
                    _ptt_trace("PTT_STT_TRANSCRIPT_READY")
                    return text
                except TypeError:
                    return str(result).strip()
        except Exception as exc:
            _ptt_trace(f"PTT_STT_ERROR type={type(exc).__name__} message={str(exc)[:120]!r}")
            raise RuntimeError("TRANSCRIPTION_FAILED") from exc
        raise RuntimeError("STT_UNAVAILABLE")


class PiperTTSProvider:
    """Lazy Piper contract; requires an explicit local voice/model path."""
    def __init__(self, *, model_path: str = "", voice: str = "") -> None:
        self.model_path, self.voice = str(model_path or ""), str(voice or "")
        self._speaking = False
        self._voice = None
        self._last_wav = None

    def initialize(self) -> None:
        if not self.model_path:
            raise RuntimeError("MODEL_MISSING")
        try:
            PiperVoice = getattr(importlib.import_module("piper"), "PiperVoice")
            self._voice = PiperVoice.load(self.model_path)
        except Exception as exc:
            raise RuntimeError("TTS_UNAVAILABLE") from exc

    def is_available(self) -> bool:
        try:
            importlib.import_module("piper")
            return bool(self.model_path)
        except Exception:
            return False

    def list_voices(self) -> list[str]:
        return [self.voice] if self.voice else []

    def speak(self, text: str) -> None:
        if self._voice is None:
            self.initialize()
        import tempfile, wave
        self._speaking = True
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as handle:
                self._last_wav = handle.name
            with wave.open(self._last_wav, "wb") as wav:
                self._voice.synthesize_wav(str(text), wav)
        except Exception as exc:
            raise RuntimeError("TTS_UNAVAILABLE") from exc
        finally:
            self._speaking = False

    def stop(self) -> None:
        self._speaking = False

    def is_speaking(self) -> bool:
        return self._speaking


class XTTSProvider(PiperTTSProvider):
    """Explicit placeholder until a local XTTS dependency is provisioned."""
    def is_available(self) -> bool:
        return False
