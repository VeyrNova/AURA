"""Explicit push-to-talk microphone capture for AURA v0.5.1.1.

No continuous/background recording is performed. The recorder selects a real
Windows input device, records at a rate the device supports, then resamples in
RAM to 16 kHz for Whisper. This fixes common USB/Bluetooth devices that reject
native 16 kHz capture.
"""
from __future__ import annotations

import importlib.util
import logging
import threading
from dataclasses import dataclass
from typing import Any, Sequence

from config.settings import settings
from voice.errors import MicrophoneUnavailableError

logger = logging.getLogger("aura.voice.microphone")


# AURA v0.8.6.7 - stale microphone warning dedup
class _AURAV0867StaleMicWarningDedupFilter(logging.Filter):
    # Emit one stale-index warning per requested stale index in this process.
    _seen: set[str] = set()

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
            if "requested microphone index stale" not in message:
                return True
            key = message.split(";", 1)[0]
            if key in self.__class__._seen:
                return False
            self.__class__._seen.add(key)
            return True
        except Exception:
            return True


logger.addFilter(_AURAV0867StaleMicWarningDedupFilter())
@dataclass(frozen=True)
class InputDeviceInfo:
    index: int
    name: str
    channels: int
    default_samplerate: float

    @property
    def label(self) -> str:
        return f"[{self.index}] {self.name} ({int(self.default_samplerate or 0)} Hz)"


class MicrophoneRecorder:
    def __init__(
        self,
        sample_rate: int = 16_000,
        channels: int = 1,
        max_seconds: float = 30.0,
        min_seconds: float = 0.15,
        requested_device: str = "",
    ):
        self.sample_rate = int(sample_rate)
        self.channels = max(1, int(channels))
        self.max_seconds = float(max_seconds)
        self.min_seconds = float(min_seconds)
        self.requested_device = str(requested_device or "").strip()
        self._stream: Any = None
        self._frames: list[Any] = []
        self._lock = threading.Lock()
        self._recording = False
        self._overflowed = False
        self._capture_rate = self.sample_rate
        self._active_device: InputDeviceInfo | None = None

    @staticmethod
    def dependencies_available() -> bool:
        return bool(importlib.util.find_spec("sounddevice") and importlib.util.find_spec("numpy"))

    @property
    def is_recording(self) -> bool:
        return self._recording

    @staticmethod
    def _device_infos(devices: Sequence[Any]) -> list[InputDeviceInfo]:
        infos: list[InputDeviceInfo] = []
        for idx, dev in enumerate(devices):
            try:
                channels = int(dev["max_input_channels"])
            except Exception:
                channels = int(getattr(dev, "max_input_channels", 0) or 0)
            if channels <= 0:
                continue
            try:
                name = str(dev["name"])
                rate = float(dev["default_samplerate"] or 0.0)
            except Exception:
                name = str(getattr(dev, "name", f"Device {idx}"))
                rate = float(getattr(dev, "default_samplerate", 0.0) or 0.0)
            infos.append(InputDeviceInfo(idx, name, channels, rate))
        return infos

    @staticmethod
    def _coerce_device_index(value: Any) -> int | None:
        """Return an input-device index from sounddevice's different default forms.

        On Windows, ``sd.default.device`` may be an ``_InputOutputPair`` rather
        than a tuple/list.  Treating that object as an int caused AURA v0.5.1
        to reject every microphone even though devices were correctly listed.
        """
        if value is None:
            return None

        # sounddevice _InputOutputPair exposes ``input``/``output`` attributes.
        for attr in ("input", "_input"):
            try:
                candidate = getattr(value, attr)
            except (AttributeError, TypeError):
                continue
            try:
                return int(candidate)
            except (TypeError, ValueError):
                pass

        if isinstance(value, dict):
            for key in ("input", 0):
                try:
                    return int(value[key])
                except (KeyError, TypeError, ValueError):
                    pass

        if isinstance(value, (tuple, list)):
            if not value:
                return None
            try:
                return int(value[0])
            except (TypeError, ValueError):
                return None

        # Some pair-like implementations are indexable without inheriting from
        # tuple/list. Avoid indexing strings/bytes.
        if not isinstance(value, (str, bytes)):
            try:
                return int(value[0])
            except (TypeError, ValueError, KeyError, IndexError):
                pass

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fallback_score(info: InputDeviceInfo) -> tuple[int, int]:
        """Prefer real microphones over Windows mapper/loopback pseudo devices."""
        name = info.name.casefold()
        score = 0

        # Strong positive indicators of a physical capture device.
        if "microphone" in name or " mic" in f" {name}":
            score += 120
        if "réseau de microphones" in name or "microphone array" in name or "mic array" in name:
            score += 90
        if "mic input" in name:
            score += 80

        # Windows/API aliases and loopback-style inputs are poor automatic defaults.
        penalties = {
            "mappeur de sons microsoft": 100,
            "microsoft sound mapper": 100,
            "pilote de capture audio principal": 80,
            "primary sound capture driver": 80,
            "mixage stéréo": 160,
            "stereo mix": 160,
            "haut-parleur": 180,
            "speaker": 180,
        }
        for token, penalty in penalties.items():
            if token in name:
                score -= penalty

        # Stable deterministic tie-break: smaller device index first.
        return score, -info.index

    @classmethod
    def choose_input_device(
        cls,
        devices: Sequence[Any],
        default_input: Any = None,
        requested: str = "",
    ) -> InputDeviceInfo | None:
        """Pure selection logic, easy to test and deterministic."""
        infos = cls._device_infos(devices)
        if not infos:
            return None

        requested = str(requested or "").strip()
        if requested:
            # AURA P0.8.5.4.7.4 — STALE MIC DEVICE FALLBACK
            # MIC_DEVICE can outlive a Windows/PortAudio device-index change.
            # Keep an exact configured device when it still exists, but never
            # turn a stale index/name into a permanent microphone outage.
            try:
                requested_index = int(requested)
            except ValueError:
                requested_index = None

            if requested_index is not None:
                for info in infos:
                    if info.index == requested_index:
                        return info
                logger.warning(
                    "P0.8.5.4.7.4 requested microphone index stale index=%r; "
                    "falling back to Windows default/input scoring",
                    requested,
                )
            else:
                needle = requested.casefold()
                for info in infos:
                    if needle in info.name.casefold():
                        return info
                logger.warning(
                    "P0.8.5.4.7.4 requested microphone name stale name=%r; "
                    "falling back to Windows default/input scoring",
                    requested,
                )

        default_index = cls._coerce_device_index(default_input)
        if default_index is not None and default_index >= 0:
            for info in infos:
                if info.index == default_index:
                    return info

        return max(infos, key=cls._fallback_score)

    def list_input_devices(self) -> list[InputDeviceInfo]:
        if not self.dependencies_available():
            return []
        try:
            import sounddevice as sd

            return self._device_infos(sd.query_devices())
        except Exception:
            logger.exception("Impossible d'enumerer les microphones")
            return []

    def resolve_input_device(self) -> InputDeviceInfo | None:
        if not self.dependencies_available():
            return None
        try:
            import sounddevice as sd

            default_device = sd.default.device
            default_input = self._coerce_device_index(default_device)
            return self.choose_input_device(sd.query_devices(), default_input, self.requested_device)
        except Exception:
            logger.exception("Impossible de resoudre le microphone d'entree")
            return None

    def refresh_device_state(self, *, reinitialize_portaudio: bool = False) -> InputDeviceInfo | None:
        """Refresh Windows/PortAudio device discovery without opening capture.

        ``sounddevice`` can keep an input-device snapshot that predates a late
        Windows audio-service/device arrival. RC3.1 permits one guarded backend
        reinitialization from the passive recovery timer. No recording stream is
        opened here. The caller must avoid invoking this while output/capture is
        active.
        """
        if not self.dependencies_available():
            logger.info("Microphone device refresh skipped: dependency unavailable")
            return None
        try:
            import sounddevice as sd

            refreshed = False
            if reinitialize_portaudio and not self._recording:
                terminate = getattr(sd, "_terminate", None)
                initialize = getattr(sd, "_initialize", None)
                if callable(terminate) and callable(initialize):
                    try:
                        terminate()
                        initialize()
                        refreshed = True
                        logger.info("Microphone PortAudio device cache reinitialized")
                    except Exception as exc:
                        logger.warning("Microphone PortAudio refresh unavailable: %s", type(exc).__name__)

            devices = sd.query_devices()
            infos = self._device_infos(devices)
            default_input = self._coerce_device_index(sd.default.device)
            selected = self.choose_input_device(devices, default_input, self.requested_device)
            logger.info(
                "Microphone device refresh reinitialized=%s inputs=%d default=%r requested=%r selected=%r",
                refreshed, len(infos), default_input, self.requested_device,
                selected.label if selected else "",
            )
            return selected
        except Exception as exc:
            logger.warning("Microphone device refresh failed: %s", type(exc).__name__)
            return None

    def is_available(self) -> bool:
        return self.dependencies_available() and self.resolve_input_device() is not None

    def device_label(self) -> str:
        info = self.resolve_input_device()
        return info.label if info else "Aucun microphone utilisable"

    def _pick_capture_rate(self, sd, device: InputDeviceInfo) -> int:
        """Prefer 16 kHz; gracefully fall back to the device native rate."""
        for rate in (self.sample_rate, int(device.default_samplerate or 0)):
            if rate <= 0:
                continue
            try:
                sd.check_input_settings(device=device.index, channels=self.channels, samplerate=rate, dtype="float32")
                return rate
            except Exception:
                continue
        raise MicrophoneUnavailableError(
            f"Le microphone '{device.name}' est détecté mais son format audio n'est pas compatible. "
            "Choisis un autre périphérique d'entrée Windows ou configure MIC_DEVICE."
        )

    def start(self) -> None:
        if self._recording:
            return
        if not self.dependencies_available():
            raise MicrophoneUnavailableError(
                "Le module microphone n'est pas installé. Lance INSTALL_VOICE.bat puis redémarre AURA."
            )

        import sounddevice as sd

        device = self.resolve_input_device()
        if device is None:
            requested = f" ('{self.requested_device}')" if self.requested_device else ""
            raise MicrophoneUnavailableError(
                "Aucun microphone d'entrée utilisable n'a été détecté" + requested + ". "
                "Vérifie Paramètres Windows > Confidentialité et sécurité > Microphone, puis VOICE_DIAGNOSTICS.bat."
            )
        capture_rate = self._pick_capture_rate(sd, device)

        with self._lock:
            self._frames = []
            self._overflowed = False

        def callback(indata, frames, time_info, status):
            del time_info
            if status:
                logger.warning("Statut audio micro: %s", status)
            if not self._recording:
                return
            with self._lock:
                max_samples = int(capture_rate * self.max_seconds)
                current_samples = sum(frame.shape[0] for frame in self._frames)
                remaining = max_samples - current_samples
                if remaining <= 0:
                    self._overflowed = True
                    return
                self._frames.append(indata[:remaining].copy())
                if frames > remaining:
                    self._overflowed = True

        try:
            self._stream = sd.InputStream(
                device=device.index,
                samplerate=capture_rate,
                channels=min(self.channels, device.channels),
                dtype="float32",
                callback=callback,
            )
            self._recording = True
            self._capture_rate = capture_rate
            self._active_device = device
            self._stream.start()
            logger.info("Microphone push-to-talk actif: %s capture=%dHz", device.label, capture_rate)
        except Exception as exc:
            self._recording = False
            self._stream = None
            self._active_device = None
            logger.exception("Impossible d'ouvrir le microphone %s", device.label)
            raise MicrophoneUnavailableError(
                f"Je détecte '{device.name}', mais je n'arrive pas à l'ouvrir. "
                "Ferme les applications qui monopolisent le micro et vérifie les autorisations Windows."
            ) from exc

    @staticmethod
    def _resample(audio, source_rate: int, target_rate: int):
        import numpy as np

        if source_rate == target_rate or audio.size == 0:
            return np.ascontiguousarray(audio, dtype=np.float32)
        duration = audio.shape[0] / float(source_rate)
        target_length = max(1, int(round(duration * target_rate)))
        old_x = np.linspace(0.0, duration, num=audio.shape[0], endpoint=False)
        new_x = np.linspace(0.0, duration, num=target_length, endpoint=False)
        resampled = np.interp(new_x, old_x, audio).astype(np.float32)
        return np.ascontiguousarray(resampled)

    @staticmethod
    def _normalize(audio):
        import numpy as np

        if audio.size == 0 or not settings.MIC_NORMALIZE:
            return audio
        peak = float(np.max(np.abs(audio)))
        if peak < 1e-5:
            return audio
        # Do not crush normal microphones. Only lift quiet-but-real recordings.
        if peak < 0.35:
            gain = min(float(settings.MIC_MAX_GAIN), 0.75 / peak)
            audio = np.clip(audio * gain, -1.0, 1.0).astype(np.float32)
            logger.info("Gain micro logiciel applique: %.2fx (peak avant=%.4f)", gain, peak)
        return np.ascontiguousarray(audio, dtype=np.float32)

    def stop(self):
        """Stop capture and return mono float32 16 kHz waveform, or None if too short."""
        if not self._recording:
            return None

        self._recording = False
        stream = self._stream
        self._stream = None
        try:
            if stream is not None:
                stream.stop()
                stream.close()
        except Exception:
            logger.exception("Erreur lors de la fermeture du microphone")

        import numpy as np

        with self._lock:
            frames = self._frames
            self._frames = []

        if not frames:
            return None

        audio = np.concatenate(frames, axis=0)
        if audio.ndim == 2:
            audio = audio.mean(axis=1)
        audio = np.ascontiguousarray(audio, dtype=np.float32)

        capture_rate = int(self._capture_rate or self.sample_rate)
        duration = audio.shape[0] / float(capture_rate)
        if self._overflowed:
            logger.warning("Enregistrement limite a %.1f secondes", self.max_seconds)
        self._overflowed = False

        if duration < self.min_seconds:
            logger.info("Enregistrement ignore: %.3fs < minimum %.3fs", duration, self.min_seconds)
            return None

        peak_before = float(np.max(np.abs(audio))) if audio.size else 0.0
        rms_before = float(np.sqrt(np.mean(np.square(audio)))) if audio.size else 0.0
        audio = self._normalize(audio)
        audio = self._resample(audio, capture_rate, self.sample_rate)
        logger.info(
            "Capture micro terminee: %.2fs device=%s source=%dHz peak=%.4f rms=%.4f -> %dHz",
            duration,
            self._active_device.label if self._active_device else "?",
            capture_rate,
            peak_before,
            rms_before,
            self.sample_rate,
        )
        self._active_device = None
        return audio

    def cancel(self) -> None:
        """Stop capture and discard buffered audio."""
        if self._recording:
            self._recording = False
            stream = self._stream
            self._stream = None
            try:
                if stream is not None:
                    stream.stop()
                    stream.close()
            except Exception:
                logger.exception("Erreur lors de l'annulation du microphone")
        with self._lock:
            self._frames = []
        self._overflowed = False
        self._active_device = None
