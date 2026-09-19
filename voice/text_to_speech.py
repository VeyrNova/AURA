"""Local neural text-to-speech using Piper on Windows."""
from __future__ import annotations

import html
import importlib.util
import logging
import os
import queue
import re
import tempfile
import threading
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from config.settings import settings
from voice.errors import SpeechSynthesisUnavailableError
from voice.audio_postprocess import polish_wav_tail

logger = logging.getLogger("aura.voice.tts")


_AURA_FEMININE_PATTERNS = (
    (re.compile(r"\bje suis pr[êe]t\b", re.IGNORECASE), "je suis prête"),
    (re.compile(r"\bje suis connect[ée] et pr[êe]t\b", re.IGNORECASE), "je suis connectée et prête"),
    (re.compile(r"\bje suis connect[ée]\b", re.IGNORECASE), "je suis connectée"),
    (re.compile(r"\bje suis d[ée]sol[ée]\b", re.IGNORECASE), "je suis désolée"),
    (re.compile(r"\bje suis disponible et pr[êe]t\b", re.IGNORECASE), "je suis disponible et prête"),
    (re.compile(r"\bje suis op[ée]rationnel\b", re.IGNORECASE), "je suis opérationnelle"),
    (re.compile(r"\bje suis initialis[ée]\b", re.IGNORECASE), "je suis initialisée"),
)


def normalize_aura_feminine_speech(text: str) -> str:
    """Correct only high-confidence first-person AURA gender agreements.

    This is intentionally not a general grammar checker. It never rewrites
    nouns such as ``le système est prêt`` or quoted user content.
    """
    value = str(text or "")
    for pattern, replacement in _AURA_FEMININE_PATTERNS:
        value = pattern.sub(replacement, value)
    # A standalone readiness acknowledgement is spoken by AURA herself.
    value = re.sub(r"^\s*pr[êe]t([.!?…]*)\s*$", r"Prête\1", value, flags=re.IGNORECASE)
    return value


def normalize_french_speech(text: str) -> str:
    """Expand common UI/weather notation into natural spoken French.

    This is intentionally deterministic and conservative. It changes only
    well-delimited numeric/unit patterns so normal prose remains untouched.
    """
    value = normalize_aura_feminine_speech(str(text or ""))

    # Clock notation: 13:15 -> 13 heures 15; 1:00 -> 1 heure.
    def clock_repl(match: re.Match) -> str:
        hour = int(match.group(1))
        minute = int(match.group(2))
        unit = "heure" if hour == 1 else "heures"
        if minute == 0:
            return f"{hour} {unit}"
        return f"{hour} {unit} {minute:02d}"

    value = re.sub(r"(?<![\d:])(\d{1,2}):(\d{2})(?!\d)", clock_repl, value)

    # Explicit h notation: 9 h 30 / 1h / 14 h.
    def h_repl(match: re.Match) -> str:
        hour = int(match.group(1))
        minute = match.group(2)
        unit = "heure" if hour == 1 else "heures"
        return f"{hour} {unit}" + (f" {int(minute):02d}" if minute else "")

    value = re.sub(r"(?<![/\w])(\d{1,2})\s*h(?:eures?)?\s*(\d{1,2})?(?!\w)", h_repl, value, flags=re.IGNORECASE)

    # Temperature keeps grammatical singular/plural.
    def temp_repl(match: re.Match) -> str:
        raw = match.group(1)
        try:
            numeric = float(raw.replace(",", "."))
        except ValueError:
            numeric = 2.0
        unit = "degré Celsius" if abs(numeric - 1.0) < 1e-9 else "degrés Celsius"
        return f"{raw} {unit}"

    value = re.sub(r"(?<!\w)(\d+(?:[.,]\d+)?)\s*°\s*C\b", temp_repl, value, flags=re.IGNORECASE)
    value = re.sub(r"\bkm\s*/\s*h\b", "kilomètres par heure", value, flags=re.IGNORECASE)
    value = re.sub(r"(?<=\d)\s*%", " pour cent", value)
    value = re.sub(r"(?<=\d)\s*mm\b", " millimètres", value, flags=re.IGNORECASE)

    # Standalone French decimal pronunciation: 36.1 -> 36 virgule 1.
    value = re.sub(r"(?<![\d.])(\d+)\.(\d+)(?![\d.])", r"\1 virgule \2", value)
    return value


_SYNTH_TERMINAL_PUNCT_RE = re.compile(r"[.!?…,:;]+(?P<closers>[\"»”\'\)\]\}]*)$")

# Emoji stay intact in the visual/LLM conversation. The speech renderer keeps
# decorative glyphs silent so XTTS/Piper never try to pronounce raw Unicode
# symbols such as "smiling face" in the middle of an otherwise natural reply.
_EMOJI_FOR_SPEECH_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"          # misc symbols / dingbats
    "\uFE0F\u200D"            # variation selector / ZWJ
    "]+"
)


def strip_terminal_punctuation_for_synthesis(text: str) -> str:
    """Remove terminal punctuation from the exact TTS render payload.

    Sentence punctuation is still preserved upstream for segmentation and
    prosody planning. Some XTTS voices can occasionally verbalize a terminal
    glyph at a chunk boundary (for example saying "point"). The renderer
    therefore receives the same text minus only the final punctuation run.
    Internal punctuation and decimal points remain untouched.
    """
    value = str(text or "").strip()
    if not value:
        return ""
    return _SYNTH_TERMINAL_PUNCT_RE.sub(lambda m: m.group("closers"), value).strip()


_PIPER_CLAUSE_BOUNDARY_RE = re.compile(r"(?<=[.!?…;:,])\s+")


def split_piper_progressive_segments(
    text: str,
    *,
    first_limit: int | None = None,
    next_limit: int | None = None,
) -> tuple[str, ...]:
    """Split speech into bounded natural chunks for low Piper TTFA.

    Piper latency grows sharply with the amount of text passed to one
    ``synthesize`` call.  The first segment is deliberately shorter so the
    first PCM bytes can be emitted quickly; following segments may be larger.
    Boundaries prefer sentence/clause punctuation and otherwise fall back to
    the last whitespace.  No text is dropped or reordered.
    """
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ()
    first = max(24, int(first_limit if first_limit is not None else settings.PIPER_FIRST_SEGMENT_CHARS))
    nxt = max(first, int(next_limit if next_limit is not None else settings.PIPER_NEXT_SEGMENT_CHARS))

    out: list[str] = []
    remaining = value
    limit = first
    while remaining:
        if len(remaining) <= limit:
            out.append(remaining.strip())
            break
        window = remaining[: limit + 1]
        # Prefer a natural clause ending. The very first Piper call is allowed
        # to be a true micro-phrase: traces on the target Windows laptop showed
        # that 55-60 character first calls can have 4-5s TTFA, while 30-40
        # character calls are materially faster. Later chunks retain the older
        # larger minimum for smoother prosody.
        if not out:
            min_cut = min(limit, max(int(settings.PIPER_FIRST_SEGMENT_MIN_CHARS), int(limit * 0.28)))
        else:
            min_cut = max(18, int(limit * 0.42))
        cut = -1
        for match in _PIPER_CLAUSE_BOUNDARY_RE.finditer(window):
            if match.start() >= min_cut:
                cut = match.start()
                # For the first utterance choose the earliest useful clause,
                # not the last one before the limit. This is the TTFA-critical
                # path; later chunks can stay longer for smoother prosody.
                if not out:
                    break
        if cut < min_cut:
            cut = window.rfind(" ", min_cut, limit + 1)
        if cut < min_cut:
            cut = limit
        segment = remaining[:cut].strip()
        if not segment:
            segment = remaining[:limit].strip()
            cut = len(segment)
        out.append(segment)
        remaining = remaining[cut:].strip()
        limit = nxt
    return tuple(item for item in out if item)


def sanitize_for_speech(text: str, max_chars: int | None = None) -> str:
    """Convert UI/HTML/Markdown-heavy assistant text into clean spoken French.

    UI formatting must never leak into TTS. In particular, tags such as
    ``<br>`` are display instructions, not words AURA should pronounce.
    """
    value = html.unescape(str(text or ""))

    # Preserve semantic separation from UI HTML/SSML without pronouncing it.
    # Also accept the legacy malformed ``<br `` fragment found in old memory
    # output so historical strings are safe if they reappear.
    value = re.sub(r"(?i)<\s*br(?:\s*/?\s*>|\s+)", "\n", value)
    value = re.sub(
        r"(?i)</?\s*(?:p|div|li|ul|ol|section|article|header|footer|h[1-6])\b[^>]*>",
        "\n",
        value,
    )
    value = re.sub(r"<[^>]+>", " ", value)

    value = re.sub(r"```.*?```", " Le code est affiché à l'écran. ", value, flags=re.DOTALL)
    value = re.sub(r"`([^`]+)`", r"\1", value)
    value = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", value)
    value = re.sub(r"https?://\S+", " lien affiché à l'écran ", value)
    value = re.sub(r"[*_#>|~]+", " ", value)
    value = _EMOJI_FOR_SPEECH_RE.sub(" ", value)

    # Decorative list markers are useful on screen but should be silent.
    value = re.sub(r"(?m)^\s*(?:[-+•▪◦·]|\d+[.)])\s*", "", value)
    value = re.sub(r"[•▪◦]", " ", value)
    value = normalize_french_speech(value)
    value = re.sub(r"\s*\n+\s*", " ", value)
    value = re.sub(r"\s+", " ", value).strip()

    limit = settings.TTS_MAX_CHARS if max_chars is None else int(max_chars)
    if limit > 0 and len(value) > limit:
        clipped = value[:limit]
        last_boundary = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"), clipped.rfind(";"))
        if last_boundary >= max(80, int(limit * 0.55)):
            clipped = clipped[: last_boundary + 1]
        value = clipped.rstrip() + " La suite est affichée à l'écran."
    return value


class PiperStreamingError(SpeechSynthesisUnavailableError):
    def __init__(self, message: str, *, audio_started: bool = False):
        super().__init__(message)
        self.audio_started = bool(audio_started)


@dataclass(frozen=True)
class PiperSynthesisMetrics:
    device: str
    model_load_seconds: float
    synthesis_seconds: float
    playback_seconds: float
    text_chars: int
    time_to_audio_seconds: float
    chunk_count: int = 0
    streaming: bool = True

    @property
    def total_seconds(self) -> float:
        return float(self.model_load_seconds + self.synthesis_seconds + self.playback_seconds)

    @property
    def progressive(self) -> bool:
        return bool(self.streaming)

    @property
    def first_chunk_synthesis_seconds(self) -> float:
        # Piper exposes first PCM rather than a separate pre-rendered WAV chunk.
        # This keeps the common UI metric meaningful across XTTS and Piper.
        return max(0.0, float(self.time_to_audio_seconds) - float(self.model_load_seconds))


@dataclass
class PiperPreparedSegment:
    text: str
    text_chars: int
    model_load_seconds: float
    prepared_at: float
    synthesis_seconds: float = 0.0
    time_to_audio_seconds: float = 0.0
    first_audio_at: float = 0.0
    chunk_count: int = 0


class PiperTTS:
    def __init__(self):
        self._voice: Any = None
        self._playback_lock = threading.Lock()
        self._load_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._active_stream = None
        self._active_stream_lock = threading.Lock()
        # AURA_R23_R3_PLAYBACK_REFERENCE_STATE
        self._playback_reference_callback = None
        self._playback_reference_generation = 0
        self._playback_reference_last_spec = None

    @staticmethod
    def dependency_available() -> bool:
        return importlib.util.find_spec("piper") is not None

    def model_path(self) -> Path:
        configured = settings.TTS_MODEL_PATH.strip()
        if configured:
            return Path(configured).expanduser().resolve()
        return settings.VOICE_MODEL_DIR / "piper" / f"{settings.TTS_VOICE}.onnx"

    def config_path(self) -> Path:
        model = self.model_path()
        return Path(str(model) + ".json")

    def model_ready(self) -> bool:
        return self.model_path().is_file() and self.config_path().is_file()

    def is_available(self) -> bool:
        return (
            settings.VOICE_ENABLED
            and os.name == "nt"
            and self.dependency_available()
            and self.model_ready()
        )

    def _load_voice(self):
        if self._voice is not None:
            return self._voice
        with self._load_lock:
            if self._voice is not None:
                return self._voice
            if os.name != "nt":
                raise SpeechSynthesisUnavailableError("La sortie vocale v0.5.1 est actuellement prévue pour Windows.")
            if not self.dependency_available():
                raise SpeechSynthesisUnavailableError(
                    "La synthèse vocale locale n'est pas installée. Lance INSTALL_VOICE.bat puis redémarre AURA."
                )
            if not self.model_ready():
                raise SpeechSynthesisUnavailableError(
                    "La voix locale d'AURA n'est pas installée. Lance INSTALL_VOICE.bat puis redémarre AURA."
                )

            try:
                from piper import PiperVoice

                self._voice = PiperVoice.load(str(self.model_path()))
            except Exception as exc:
                logger.exception("Chargement de la voix Piper impossible")
                raise SpeechSynthesisUnavailableError(
                    "Je n'arrive pas à charger ma voix locale. Consulte les logs ou relance INSTALL_VOICE.bat."
                ) from exc
            return self._voice

    def _prewarm_inference(self, voice: Any) -> float:
        """Run one silent tiny Piper inference to warm the ONNX execution path.

        PiperVoice.load() makes the model resident, but the first real
        ``synthesize`` call can still pay one-time ONNX/session execution cost.
        This deliberately consumes generated PCM without opening PortAudio.
        """
        if not settings.PIPER_INFERENCE_PREWARM:
            return 0.0
        text = strip_terminal_punctuation_for_synthesis(sanitize_for_speech(settings.PIPER_PREWARM_TEXT, max_chars=48))
        if not text:
            return 0.0
        started = time.perf_counter()
        syn_config = self._synthesis_config()
        chunks = 0
        try:
            iterator = voice.synthesize(text, syn_config=syn_config) if syn_config is not None else voice.synthesize(text)
            for chunk in iterator:
                if bytes(getattr(chunk, "audio_int16_bytes", b"")):
                    chunks += 1
            elapsed = time.perf_counter() - started
            logger.info("Piper inference prewarm PASS elapsed=%.3fs chunks=%d chars=%d", elapsed, chunks, len(text))
            return elapsed
        except Exception:
            # Warmup is an optimization only. A failure must never disable the
            # normal deterministic Piper path.
            logger.warning("Piper inference prewarm ignoré après erreur")
            return 0.0

    def warmup(self) -> None:
        """Load Piper and prime one silent inference, keeping voice enabled."""
        if self.is_available():
            started = time.perf_counter()
            voice = self._load_voice()
            load_elapsed = time.perf_counter() - started
            logger.info("Voix Piper préchargée en %.3fs", load_elapsed)
            self._prewarm_inference(voice)

    @staticmethod
    def _streaming_dependency_available() -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except Exception:
            return False

    @staticmethod
    def _dtype_for_chunk(chunk) -> str:
        width = int(getattr(chunk, "sample_width", 2) or 2)
        if width != 2:
            raise ValueError(f"Piper PCM width unsupported: {width}")
        return "int16"

    @staticmethod
    def _synthesis_config():
        try:
            from piper import SynthesisConfig
        except ImportError:
            return None
        return SynthesisConfig(
            volume=settings.TTS_VOLUME,
            length_scale=settings.TTS_LENGTH_SCALE,
            noise_scale=settings.TTS_NOISE_SCALE,
            noise_w_scale=settings.TTS_NOISE_W_SCALE,
            normalize_audio=True,
        )

    def _close_stream_state(self, stream_state: dict, *, abort: bool = False) -> None:
        stream = stream_state.pop("stream", None)
        stream_state.pop("spec", None)
        if stream is None:
            return
        with self._active_stream_lock:
            if self._active_stream is stream:
                self._active_stream = None
        try:
            if abort:
                stream.abort()
            else:
                stream.stop()
        finally:
            try:
                stream.close()
            except Exception:
                logger.debug("Fermeture flux Piper ignorée", exc_info=True)

    # AURA_R23_R3_PLAYBACK_REFERENCE_METHODS
    def set_playback_reference_callback(self, callback) -> None:
        """Bind optional raw PCM playback telemetry. Never controls playback."""
        self._playback_reference_callback = callback if callable(callback) else None

    def _advance_playback_reference_generation(self) -> int:
        self._playback_reference_generation = int(
            getattr(self, "_playback_reference_generation", 0)
        ) + 1
        return self._playback_reference_generation

    def _emit_playback_reference(self, payload) -> None:
        callback = getattr(self, "_playback_reference_callback", None)
        spec = getattr(self, "_playback_reference_last_spec", None)
        if not callable(callback) or not payload or not spec:
            return
        try:
            callback(
                payload,
                sample_rate=int(spec[0]),
                channels=int(spec[1]),
                dtype=str(spec[2]),
                generation=int(getattr(self, "_playback_reference_generation", 0)),
                at_monotonic=time.monotonic(),
            )
        except Exception:
            logger.debug(
                "AURA R23 playback reference callback ignored",
                exc_info=True,
            )

    def _ensure_stream(self, chunk, stream_state: dict):
        import sounddevice as sd
        spec = (
            int(getattr(chunk, "sample_rate")),
            int(getattr(chunk, "sample_channels", 1) or 1),
            self._dtype_for_chunk(chunk),
        )
        # AURA_R23_R3_PLAYBACK_REFERENCE_SPEC
        self._playback_reference_last_spec = spec
        stream = stream_state.get("stream")
        if stream is not None and stream_state.get("spec") == spec:
            return stream
        if stream is not None:
            self._close_stream_state(stream_state)
        stream = sd.RawOutputStream(
            samplerate=spec[0], channels=spec[1], dtype=spec[2],
            blocksize=0, latency="low",
        )
        stream.start()
        stream_state["stream"] = stream
        stream_state["spec"] = spec
        with self._active_stream_lock:
            self._active_stream = stream
        logger.info("Piper streaming output=%sHz/%sch/%s", *spec)
        return stream

    def _stream_text(self, spoken: str, stream_state: dict, *, close_stream: bool, on_first_audio: Callable[[float], None] | None = None) -> PiperSynthesisMetrics:
        """Write Piper 1.6 native PCM chunks as soon as they are generated."""
        turn_started = time.perf_counter()
        load_started = time.perf_counter()
        voice = self._load_voice()
        model_load_seconds = time.perf_counter() - load_started
        syn_config = self._synthesis_config()
        first_audio_at = 0.0
        chunk_count = 0
        iterator_started = time.perf_counter()
        try:
            iterator = voice.synthesize(spoken, syn_config=syn_config) if syn_config is not None else voice.synthesize(spoken)
            for chunk in iterator:
                if self._stop_event.is_set():
                    break
                payload = bytes(getattr(chunk, "audio_int16_bytes", b""))
                if not payload:
                    continue
                stream = self._ensure_stream(chunk, stream_state)
                # AURA_R23_R3_PLAYBACK_REFERENCE_EMIT
                self._emit_playback_reference(payload)
                stream.write(payload)
                chunk_count += 1
                if first_audio_at <= 0.0:
                    first_audio_at = time.perf_counter()
                    if on_first_audio is not None:
                        on_first_audio(first_audio_at)
            end_write = time.perf_counter()
            if close_stream:
                self._close_stream_state(stream_state, abort=self._stop_event.is_set())
            finished = time.perf_counter()
            if chunk_count <= 0 and not self._stop_event.is_set():
                raise SpeechSynthesisUnavailableError("Piper n'a produit aucun échantillon audio.")
            return PiperSynthesisMetrics(
                device="cpu", model_load_seconds=model_load_seconds,
                synthesis_seconds=max(0.0, end_write - iterator_started),
                playback_seconds=max(0.0, finished - end_write), text_chars=len(spoken),
                time_to_audio_seconds=max(0.0, (first_audio_at or finished) - turn_started),
                chunk_count=chunk_count, streaming=True,
            )
        except SpeechSynthesisUnavailableError:
            if close_stream:
                self._close_stream_state(stream_state, abort=True)
            raise
        except Exception as exc:
            if close_stream:
                self._close_stream_state(stream_state, abort=True)
            raise PiperStreamingError(
                "Le flux audio Piper temps réel a rencontré un problème.",
                audio_started=first_audio_at > 0.0,
            ) from exc

    def _stream_progressive_text(
        self,
        spoken: str,
        stream_state: dict,
        *,
        close_stream: bool,
        on_first_audio: Callable[[float], None] | None = None,
    ) -> PiperSynthesisMetrics:
        """Stream progressive Piper segments with bounded synthesis/playback overlap.

        One producer owns Piper/ONNX and synthesizes segments strictly in order.
        One consumer owns PortAudio and writes PCM chunks. The bounded queue lets
        synthesis of segment N+1 progress while segment N is still audible,
        without concurrent calls into PiperVoice and without unbounded RAM use.
        """
        turn_started = time.perf_counter()
        segments = split_piper_progressive_segments(spoken)
        if not segments:
            raise SpeechSynthesisUnavailableError("Segment Piper temps réel vide.")

        logger.info(
            "Piper progressive start segments=%d first_limit=%d next_limit=%d chars=%d async=%s queue_chunks=%d",
            len(segments), int(settings.PIPER_FIRST_SEGMENT_CHARS),
            int(settings.PIPER_NEXT_SEGMENT_CHARS), len(spoken),
            len(segments) > 1, int(settings.PIPER_AUDIO_QUEUE_CHUNKS),
        )

        # A single short segment is already optimal on the native streaming path.
        if len(segments) == 1:
            metric = self._stream_text(
                segments[0], stream_state, close_stream=close_stream, on_first_audio=on_first_audio
            )
            logger.info(
                "Piper progressive segment=1/1 chars=%d ttfa=%.3fs synth=%.3fs chunks=%d async=False",
                len(segments[0]), metric.time_to_audio_seconds, metric.synthesis_seconds, metric.chunk_count,
            )
            return PiperSynthesisMetrics(
                device=metric.device, model_load_seconds=metric.model_load_seconds,
                synthesis_seconds=metric.synthesis_seconds, playback_seconds=metric.playback_seconds,
                text_chars=len(spoken), time_to_audio_seconds=metric.time_to_audio_seconds,
                chunk_count=metric.chunk_count, streaming=True,
            )

        load_started = time.perf_counter()
        voice = self._load_voice()
        model_load_seconds = time.perf_counter() - load_started
        syn_config = self._synthesis_config()
        pcm_queue: queue.Queue = queue.Queue(maxsize=max(1, int(settings.PIPER_AUDIO_QUEUE_CHUNKS)))
        sentinel = object()
        errors: list[BaseException] = []
        segment_stats = [
            {"started": 0.0, "first_generated": 0.0, "first_audio": 0.0, "synth": 0.0, "chunks": 0}
            for _ in segments
        ]
        first_audio_at = 0.0
        first_audio_gate = threading.Event()
        total_chunks = 0
        playback_block_seconds = 0.0

        def put_pcm(item) -> bool:
            while not self._stop_event.is_set():
                try:
                    pcm_queue.put(item, timeout=0.05)
                    return True
                except queue.Full:
                    continue
            return False

        def producer() -> None:
            try:
                for index, segment_text in enumerate(segments):
                    if self._stop_event.is_set():
                        return
                    stat = segment_stats[index]
                    stat["started"] = time.perf_counter()
                    iterator = voice.synthesize(segment_text, syn_config=syn_config) if syn_config is not None else voice.synthesize(segment_text)
                    for chunk in iterator:
                        if self._stop_event.is_set():
                            return
                        payload = bytes(getattr(chunk, "audio_int16_bytes", b""))
                        if not payload:
                            continue
                        now = time.perf_counter()
                        if not stat["first_generated"]:
                            stat["first_generated"] = now
                        stat["chunks"] += 1
                        if not put_pcm((index, chunk, payload)):
                            return
                    stat["synth"] = max(0.0, time.perf_counter() - stat["started"])
                    if index == 0 and len(segments) > 1:
                        # Do not start segment 2 until segment 1 has actually
                        # reached PortAudio. This preserves immediate barge-in:
                        # a stop raised on first audio prevents any later Piper call.
                        while not self._stop_event.is_set() and not first_audio_gate.wait(0.01):
                            pass
                        if self._stop_event.is_set():
                            return
            except BaseException as exc:
                errors.append(exc)
                self._stop_event.set()
            finally:
                # Ensure the consumer can terminate even when cancellation fills the queue.
                while True:
                    try:
                        pcm_queue.put(sentinel, timeout=0.05)
                        break
                    except queue.Full:
                        if self._stop_event.is_set():
                            try:
                                pcm_queue.get_nowait()
                                pcm_queue.task_done()
                            except queue.Empty:
                                pass

        def consumer() -> None:
            nonlocal first_audio_at, total_chunks, playback_block_seconds
            try:
                while True:
                    try:
                        item = pcm_queue.get(timeout=0.05)
                    except queue.Empty:
                        if self._stop_event.is_set() and errors:
                            return
                        continue
                    try:
                        if item is sentinel:
                            return
                        index, chunk, payload = item
                        if self._stop_event.is_set():
                            return
                        stream = self._ensure_stream(chunk, stream_state)
                        now = time.perf_counter()
                        stat = segment_stats[index]
                        if not stat["first_audio"]:
                            stat["first_audio"] = now
                        if first_audio_at <= 0.0:
                            # Dispatch-to-PortAudio is the first-audio boundary.
                            # Fire cancellation hooks before releasing synthesis
                            # of segment 2 so barge-in remains deterministic.
                            first_audio_at = now
                            if on_first_audio is not None:
                                on_first_audio(first_audio_at)
                            first_audio_gate.set()
                        write_started = time.perf_counter()
                        # AURA_R23_R3_PLAYBACK_REFERENCE_EMIT
                        self._emit_playback_reference(payload)
                        stream.write(payload)
                        playback_block_seconds += max(0.0, time.perf_counter() - write_started)
                        total_chunks += 1
                    finally:
                        pcm_queue.task_done()
            except BaseException as exc:
                errors.append(exc)
                self._stop_event.set()

        synth_thread = threading.Thread(target=producer, name="AURA-Piper-Synth", daemon=True)
        play_thread = threading.Thread(target=consumer, name="AURA-Piper-Playback", daemon=True)
        synth_thread.start()
        play_thread.start()
        synth_thread.join()
        play_thread.join()

        if close_stream:
            close_started = time.perf_counter()
            self._close_stream_state(stream_state, abort=self._stop_event.is_set())
            playback_block_seconds += max(0.0, time.perf_counter() - close_started)

        if errors:
            exc = errors[0]
            raise PiperStreamingError(
                "Le pipeline Piper asynchrone a rencontré un problème.",
                audio_started=first_audio_at > 0.0,
            ) from exc
        if total_chunks <= 0 and not self._stop_event.is_set():
            raise SpeechSynthesisUnavailableError("Piper n'a produit aucun échantillon audio.")

        for index, (segment_text, stat) in enumerate(zip(segments, segment_stats)):
            ttfa = max(0.0, (stat["first_audio"] or time.perf_counter()) - (stat["started"] or turn_started))
            logger.info(
                "Piper progressive segment=%d/%d chars=%d ttfa=%.3fs synth=%.3fs chunks=%d async=True",
                index + 1, len(segments), len(segment_text), ttfa, float(stat["synth"]), int(stat["chunks"]),
            )

        finished = time.perf_counter()
        total_synthesis = sum(float(stat["synth"]) for stat in segment_stats)
        return PiperSynthesisMetrics(
            device="cpu", model_load_seconds=model_load_seconds,
            synthesis_seconds=total_synthesis, playback_seconds=playback_block_seconds,
            text_chars=len(spoken),
            time_to_audio_seconds=max(0.0, (first_audio_at or finished) - turn_started),
            chunk_count=total_chunks, streaming=True,
        )

    def begin_realtime_pipeline(self) -> float:
        # AURA_R23_R3_PLAYBACK_REFERENCE_BEGIN
        self._advance_playback_reference_generation()
        self._stop_event.clear()
        started = time.perf_counter()
        self._load_voice()
        elapsed = time.perf_counter() - started
        logger.info("Piper realtime pipeline ready load=%.3fs", elapsed)
        return elapsed

    def prepare_realtime_segment(self, text: str, *, index: int = 0) -> PiperPreparedSegment:
        spoken = strip_terminal_punctuation_for_synthesis(sanitize_for_speech(text))
        if not spoken:
            raise SpeechSynthesisUnavailableError("Segment Piper temps réel vide.")
        if self._stop_event.is_set():
            raise SpeechSynthesisUnavailableError("Dialogue vocal temps réel annulé.")
        started = time.perf_counter()
        self._load_voice()
        return PiperPreparedSegment(spoken, len(spoken), time.perf_counter() - started, time.perf_counter())

    def play_realtime_segment(self, segment: PiperPreparedSegment, stream_state: dict) -> float:
        started = time.perf_counter()
        def first_audio(ts: float) -> None:
            segment.first_audio_at = float(ts)
            segment.time_to_audio_seconds = max(0.0, float(ts) - started)
        metrics = self._stream_progressive_text(segment.text, stream_state, close_stream=False, on_first_audio=first_audio)
        segment.synthesis_seconds = float(metrics.synthesis_seconds)
        segment.chunk_count = int(metrics.chunk_count)
        return max(0.0, time.perf_counter() - started)

    def end_realtime_pipeline(self, stream_state: dict) -> None:
        self._close_stream_state(stream_state, abort=self._stop_event.is_set())

    def _legacy_wav_speak(self, spoken: str) -> None:
        voice = self._load_voice()
        syn_config = self._synthesis_config()
        fd, wav_name = tempfile.mkstemp(prefix="aura_tts_", suffix=".wav", dir=settings.TEMP_DIR)
        os.close(fd)
        wav_path = Path(wav_name)
        try:
            with wave.open(str(wav_path), "wb") as wav_file:
                if syn_config is not None:
                    voice.synthesize_wav(spoken, wav_file, syn_config=syn_config)
                else:
                    voice.synthesize_wav(spoken, wav_file)
            polish_wav_tail(wav_path)
            import winsound
            with self._playback_lock:
                winsound.PlaySound(str(wav_path), winsound.SND_FILENAME)
        finally:
            try:
                wav_path.unlink(missing_ok=True)
            except Exception:
                logger.warning("Impossible de supprimer le WAV temporaire TTS")

    # AURA_V2_2_R11_FIRST_AUDIO_BEGIN
    @staticmethod
    def _aura_chain_first_audio(existing_callback, external_callback):
        callbacks = []
        if callable(existing_callback):
            callbacks.append(existing_callback)
        if callable(external_callback) and external_callback is not existing_callback:
            callbacks.append(external_callback)
        if not callbacks:
            return None
        fired = False
        def _once(*callback_args, **callback_kwargs):
            nonlocal fired
            if fired:
                return
            fired = True
            if callable(existing_callback):
                existing_callback(*callback_args, **callback_kwargs)
            if callable(external_callback) and external_callback is not existing_callback:
                try:
                    external_callback(*callback_args, **callback_kwargs)
                except Exception:
                    pass
        return _once
    # AURA_V2_2_R11_FIRST_AUDIO_END

    def speak(self, text: str, on_first_audio=None) -> PiperSynthesisMetrics | None:
        # AURA_R23_R3_PLAYBACK_REFERENCE_SPEAK
        self._advance_playback_reference_generation()
        spoken = strip_terminal_punctuation_for_synthesis(sanitize_for_speech(text))
        if not spoken:
            return None
        try:
            if settings.PIPER_STREAMING_ENABLED and self._streaming_dependency_available():
                self._stop_event.clear()
                try:
                    return self._stream_progressive_text(spoken, {}, close_stream=True, on_first_audio=self._aura_chain_first_audio(None, on_first_audio))
                except PiperStreamingError as exc:
                    if exc.audio_started:
                        raise
                    logger.warning("Piper streaming indisponible avant premier audio; fallback WAV", exc_info=True)
            self._stop_event.clear()
            started = time.perf_counter()
            self._legacy_wav_speak(spoken)
            total = time.perf_counter() - started
            return PiperSynthesisMetrics("cpu", 0.0, total, 0.0, len(spoken), total, 1, False)
        except SpeechSynthesisUnavailableError:
            raise
        except Exception as exc:
            logger.exception("Synthese/lecture vocale Piper impossible")
            raise SpeechSynthesisUnavailableError("Je n'arrive pas à utiliser ma voix Piper pour le moment. Le chat texte reste disponible.") from exc

    def stop(self) -> None:
        # AURA_R23_R3_PLAYBACK_REFERENCE_STOP
        # AURA_R15_R3_FIX7_R2_OWNER_THREAD_STREAM_CLOSE
        # Signal cancellation here; the playback owner thread performs
        # final PortAudio shutdown after play_thread.join().
        self._advance_playback_reference_generation()
        self._stop_event.set()
        if os.name == "nt":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                logger.debug("Interruption winsound Piper ignorÃ©e", exc_info=True)

# AURA v0.8.7.2 - spoken product version normalization
from core.spoken_version import rewrite_aura_product_version_for_speech as _aura_v0872_rewrite_product_version_for_speech


_aura_v0872_original_sanitize_for_speech = sanitize_for_speech


def sanitize_for_speech(text, *args, **kwargs):
    _text = _aura_v0872_rewrite_product_version_for_speech(str(text or ""))
    return _aura_v0872_original_sanitize_for_speech(_text, *args, **kwargs)

