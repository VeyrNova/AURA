"""
settings.py
Configuration centralisee d'AURA.
Aucun autre module ne doit lire os.environ directement : tout passe par `settings`.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_RELEASE_DATE, AURA_VERSION
from core.runtime.aura_paths import AuraPaths
from adaptive_profile import resolve_adaptive_profile

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
# P0.8.5.2.4 — Portable writable paths. AuraPaths is the source of truth for
# database, logs, models, user configuration, cache and temporary runtime data.
_AURA_PATHS = AuraPaths.resolve(core_root=BASE_DIR)
# P0.8.5.3.1 — adaptive runtime defaults. Environment values keep priority.
_ADAPTIVE_PROFILE = resolve_adaptive_profile(core_root=BASE_DIR)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def valid_cloud_api_token(value: str) -> bool:
    """Conservative shape check for optional provider secrets."""
    raw = str(value or "").strip()
    if not raw or raw.lower() in {"your_api_key", "your_api_token", "api_key", "token", "..."}:
        return False
    return len(raw) >= 16 and " " not in raw and "\n" not in raw and "\r" not in raw


def valid_elevenlabs_api_key(value: str) -> bool:
    """Validate the secret key shape without exposing or transmitting it.

    ElevenLabs secret API keys currently start with ``sk_``. Key IDs and
    placeholders are deliberately rejected locally so they never reach the API.
    """
    raw = str(value or "").strip()
    if not raw or raw in {"sk_...", "xi-api-key", "your_api_key", "YOUR_API_KEY"}:
        return False
    return raw.startswith("sk_") and len(raw) >= 16 and " " not in raw and "\n" not in raw and "\r" not in raw


def read_elevenlabs_env_import(path: str | Path) -> dict[str, str]:
    """Read only ElevenLabs settings from a user-selected .env-like file."""
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError("Le fichier .env sélectionné n'existe pas.")
    values: dict[str, str] = {}
    allowed = {"ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL", "ELEVENLABS_SPEED"}
    for raw_line in source.read_text(encoding="utf-8-sig", errors="strict").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key not in allowed:
            continue
        value = value.strip().strip('"').strip("'")
        if "\n" in value or "\r" in value:
            continue
        values[key] = value
    return values


def persist_local_env_value(name: str, value: str, *, env_path: Path | None = None) -> Path:
    """Persist one simple setting in AURA's local .env without logging it.

    Used for secrets entered explicitly by the local user. The caller remains
    responsible for deciding which setting may be written. Newlines are refused
    so one value cannot inject additional environment entries.
    """
    key = str(name or "").strip()
    raw = str(value or "").strip()
    if not key or not key.replace("_", "").isalnum() or key.upper() != key:
        raise ValueError("Nom de variable .env invalide.")
    if "\n" in raw or "\r" in raw:
        raise ValueError("Valeur .env invalide.")
    target = Path(env_path) if env_path is not None else (BASE_DIR / ".env")
    target.parent.mkdir(parents=True, exist_ok=True)
    lines = target.read_text(encoding="utf-8").splitlines() if target.exists() else []
    prefix = key + "="
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.lstrip().startswith(prefix):
            if not replaced:
                output.append(prefix + raw)
                replaced = True
            continue
        output.append(line)
    if not replaced:
        output.append(prefix + raw)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")
    tmp.replace(target)
    os.environ[key] = raw
    return target


def _env_float_upgrade(name: str, default: float, legacy_values=()) -> float:
    """Read a float while migrating exact historical stock defaults.

    v0.7.0.15 deliberately keeps the user's .env file untouched. Older AURA
    installs may therefore still contain the stock v0.7.0.14.1 RAM thresholds.
    When an exact known stock value is seen, use the new safe default. Any other
    custom value is preserved.
    """
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return float(default)
    value = float(raw)
    if any(abs(value - float(old)) < 1e-9 for old in legacy_values):
        return float(default)
    return value


def _env_int_upgrade(name: str, default: int, legacy_values=()) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return int(default)
    value = int(raw)
    if value in {int(old) for old in legacy_values}:
        return int(default)
    return value


class Settings:
    APP_NAME: str = os.getenv("APP_NAME", "AURA")
    APP_VERSION: str = AURA_VERSION
    APP_BUILD: str = AURA_BUILD
    APP_RELEASE_CHANNEL: str = AURA_RELEASE_CHANNEL
    APP_RELEASE_DATE: str = AURA_RELEASE_DATE
    ADAPTIVE_PROFILE_ENABLED: bool = _ADAPTIVE_PROFILE.enabled
    ADAPTIVE_PROFILE_ID: str = _ADAPTIVE_PROFILE.id
    ADAPTIVE_PROFILE_CODE: str = _ADAPTIVE_PROFILE.code
    ADAPTIVE_PROFILE_LABEL: str = _ADAPTIVE_PROFILE.label
    ADAPTIVE_PROFILE_SOURCE: str = _ADAPTIVE_PROFILE.source
    ADAPTIVE_PROFILE_OVERRIDES: tuple[str, ...] = _ADAPTIVE_PROFILE.override_keys
    ADAPTIVE_MODEL_POLICY_ENABLED: bool = _env_bool("AURA_ADAPTIVE_MODEL_SELECTION", True)
    ADAPTIVE_MODEL_SWITCH_ENABLED: bool = False  # finalized after LOCAL_LLM_ENABLED below
    ADAPTIVE_UI_SWITCH_ENABLED: bool = False
    ADAPTIVE_VISUAL_BUDGET_ENABLED: bool = _env_bool("AURA_ADAPTIVE_VISUAL_BUDGET", True)
    ADAPTIVE_WORKLOAD_BUDGET_ENABLED: bool = _env_bool("AURA_ADAPTIVE_WORKLOAD_BUDGET", True)
    SHELL_SERVICE_POLL_MS: int = int(os.getenv("AURA_SHELL_SERVICE_POLL_MS", str(_ADAPTIVE_PROFILE.shell_service_poll_ms)))

    # Runtime v2: local generative AI is optional. Normal AURA startup no longer
    # requires Ollama or a resident local model. Set LOCAL_LLM_ENABLED=true to
    # opt back into the compatibility/local-survival backend.
    LOCAL_LLM_ENABLED: bool = _env_bool("LOCAL_LLM_ENABLED", False)
    LOCAL_LLM_PROVIDER: str = os.getenv("LOCAL_LLM_PROVIDER", "ollama")
    LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "llama3.1")
    # Dual Brain v0.6.4: keep the stronger model for text/reasoning and use a
    # smaller multilingual model for low-latency spoken conversation. The fast
    # model is never downloaded silently; INSTALL_DUAL_BRAIN.bat is explicit.
    LLM_TEXT_MODEL: str = os.getenv("LLM_TEXT_MODEL", LOCAL_LLM_MODEL)
    LLM_VOICE_MODEL: str = os.getenv("LLM_VOICE_MODEL", "llama3.2:3b")
    LLM_TEXT_MODEL_EXPLICIT: bool = bool(str(os.getenv("LLM_TEXT_MODEL") or os.getenv("LOCAL_LLM_MODEL") or "").strip())
    LLM_VOICE_MODEL_EXPLICIT: bool = bool(str(os.getenv("LLM_VOICE_MODEL") or "").strip())
    DUAL_BRAIN_ENABLED: bool = _env_bool("DUAL_BRAIN_ENABLED", False)
    ADAPTIVE_MODEL_SWITCH_ENABLED = bool(
        ADAPTIVE_PROFILE_ENABLED and ADAPTIVE_MODEL_POLICY_ENABLED and LOCAL_LLM_ENABLED
    )
    DUAL_BRAIN_FALLBACK_TO_TEXT: bool = _env_bool("DUAL_BRAIN_FALLBACK_TO_TEXT", True)
    DUAL_BRAIN_AUTO_COHABITATION: bool = _env_bool("DUAL_BRAIN_AUTO_COHABITATION", True)
    DUAL_BRAIN_VOICE_KEEP_ALIVE: str = os.getenv("DUAL_BRAIN_VOICE_KEEP_ALIVE", _ADAPTIVE_PROFILE.dual_brain_voice_keep_alive)
    DUAL_BRAIN_MAX_VRAM_PCT: float = float(os.getenv("DUAL_BRAIN_MAX_VRAM_PCT", "86"))
    DUAL_BRAIN_MIN_FREE_VRAM_MB: float = float(os.getenv("DUAL_BRAIN_MIN_FREE_VRAM_MB", "700"))
    DUAL_BRAIN_XTTS_ESTIMATE_MB: float = float(os.getenv("DUAL_BRAIN_XTTS_ESTIMATE_MB", "2800"))
    DUAL_BRAIN_XTTS_IDLE_SECONDS: float = float(os.getenv("DUAL_BRAIN_XTTS_IDLE_SECONDS", "300"))
    DUAL_BRAIN_PROBE_MAX_VRAM_PCT: float = float(os.getenv("DUAL_BRAIN_PROBE_MAX_VRAM_PCT", "88"))
    # v0.7.0.5: predict the transient system-RAM cost of loading the voice brain
    # while XTTS is already resident. This prevents crossing the critical zone
    # before the Guardian has a chance to react.
    DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB: float = float(os.getenv("DUAL_BRAIN_VOICE_RAM_ESTIMATE_GB", "4.0"))
    DUAL_BRAIN_LLM_PRELOAD_MAX_RAM_PCT: float = _env_float_upgrade("DUAL_BRAIN_LLM_PRELOAD_MAX_RAM_PCT", 93, (84, 86))
    DUAL_BRAIN_LLM_PRELOAD_MIN_AVAILABLE_RAM_GB: float = _env_float_upgrade("DUAL_BRAIN_LLM_PRELOAD_MIN_AVAILABLE_RAM_GB", 1.15, (2.0, 2.2))
    # v0.7.0.6: under post-TTS memory pressure, keep the warm XTTS voice
    # resident and evict the fast voice LLM first. This avoids a 15s-class XTTS
    # reload for deterministic tool replies such as weather/reminders.
    VOICE_RESIDENCY_PRIORITY: bool = _env_bool("VOICE_RESIDENCY_PRIORITY", True)
    VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT: float = _env_float_upgrade("VOICE_RESIDENCY_RELEASE_LLM_RAM_PCT", 94, (88,))
    # v0.7.0.7: once the Startup Gate has opened and XTTS is already warm,
    # opportunistically warm the small voice brain in the background. This never
    # delays the gate and is refused unless the predicted system-RAM headroom is
    # still conservative.
    VOICE_BRAIN_POST_START_PREWARM: bool = _env_bool("VOICE_BRAIN_POST_START_PREWARM", _ADAPTIVE_PROFILE.voice_brain_post_start_prewarm)
    VOICE_BRAIN_PREWARM_DELAY_MS: int = _env_int_upgrade("VOICE_BRAIN_PREWARM_DELAY_MS", 1800, (800,))
    VOICE_BRAIN_PREWARM_MAX_RAM_PCT: float = _env_float_upgrade("VOICE_BRAIN_PREWARM_MAX_RAM_PCT", 93, (84, 86))
    VOICE_BRAIN_PREWARM_MIN_AVAILABLE_RAM_GB: float = _env_float_upgrade("VOICE_BRAIN_PREWARM_MIN_AVAILABLE_RAM_GB", 1.15, (2.0, 2.2))
    # v0.7.0.15.6.3: adaptive startup residency.  On 16 GiB-class systems the
    # expensive mistake is warming the 3B brain after XTTS has already consumed
    # enough RAM to predict a 90%+ resident set.  Keep XTTS hot and lazy-load the
    # voice brain instead of immediately forcing an unload/reload cycle.
    VOICE_BRAIN_PREWARM_CURRENT_SOFT_PCT: float = float(os.getenv("VOICE_BRAIN_PREWARM_CURRENT_SOFT_PCT", "55"))
    VOICE_BRAIN_PREWARM_CURRENT_CUTOFF_PCT: float = float(os.getenv("VOICE_BRAIN_PREWARM_CURRENT_CUTOFF_PCT", "65"))
    VOICE_BRAIN_PREWARM_PREDICTED_SOFT_MAX_PCT: float = float(os.getenv("VOICE_BRAIN_PREWARM_PREDICTED_SOFT_MAX_PCT", "88"))
    VOICE_BRAIN_PREWARM_PREDICTED_LOW_MAX_PCT: float = float(os.getenv("VOICE_BRAIN_PREWARM_PREDICTED_LOW_MAX_PCT", "91"))
    VOICE_BRAIN_PREWARM_SOFT_MIN_AVAILABLE_GB: float = float(os.getenv("VOICE_BRAIN_PREWARM_SOFT_MIN_AVAILABLE_GB", "2.0"))
    VOICE_BRAIN_PREWARM_LOW_MIN_AVAILABLE_GB: float = float(os.getenv("VOICE_BRAIN_PREWARM_LOW_MIN_AVAILABLE_GB", "1.5"))
    OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    ALLOW_REMOTE_LLM: bool = _env_bool("ALLOW_REMOTE_LLM", False)

    # Latency profile. Ollama officially supports keep_alive and runtime options.
    LLM_STREAM: bool = _env_bool("LLM_STREAM", True)
    LLM_PRELOAD: bool = _env_bool("LLM_PRELOAD", True)
    LLM_KEEP_ALIVE: str = os.getenv("LLM_KEEP_ALIVE", "30m")
    # Resource Guardian overrides legacy long keep-alive values while enabled.
    RESOURCE_LLM_KEEP_ALIVE: str = os.getenv("RESOURCE_LLM_KEEP_ALIVE", "2m")
    # v0.6.3 latency profiles: text keeps Ollama warm briefly, while spoken
    # answers unload it immediately so XTTS can claim the 6 GB GPU safely.
    RESOURCE_LLM_KEEP_ALIVE_TEXT: str = os.getenv("RESOURCE_LLM_KEEP_ALIVE_TEXT", RESOURCE_LLM_KEEP_ALIVE)
    RESOURCE_LLM_KEEP_ALIVE_VOICE: str = os.getenv("RESOURCE_LLM_KEEP_ALIVE_VOICE", "0")
    # v0.7.1.2.5: when the display GPU guard permanently blocks CUDA XTTS,
    # the small voice brain no longer needs to be evicted before CPU Piper.
    # Keep it warm independently without changing the legacy sequential XTTS
    # policy on machines where CUDA XTTS is actually safe.
    VOICE_BRAIN_INDEPENDENT_RESIDENCY: bool = _env_bool("VOICE_BRAIN_INDEPENDENT_RESIDENCY", True)
    VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE: str = os.getenv("VOICE_BRAIN_INDEPENDENT_KEEP_ALIVE", "5m").strip() or "5m"
    LLM_VOICE_NUM_CTX: int = int(os.getenv("LLM_VOICE_NUM_CTX", str(_ADAPTIVE_PROFILE.llm_voice_num_ctx)))
    LLM_VOICE_NUM_PREDICT: int = int(os.getenv("LLM_VOICE_NUM_PREDICT", str(_ADAPTIVE_PROFILE.llm_voice_num_predict)))
    LLM_VOICE_TEMPERATURE: float = float(os.getenv("LLM_VOICE_TEMPERATURE", "0.42"))
    LLM_VOICE_TOP_P: float = float(os.getenv("LLM_VOICE_TOP_P", "0.82"))
    LLM_VOICE_COMPLETION_GUARD: bool = _env_bool("LLM_VOICE_COMPLETION_GUARD", True)
    LLM_VOICE_COMPLETION_NUM_PREDICT: int = int(os.getenv("LLM_VOICE_COMPLETION_NUM_PREDICT", "48"))
    LLM_VOICE_COMPLETION_TRIGGER_MARGIN: int = int(os.getenv("LLM_VOICE_COMPLETION_TRIGGER_MARGIN", "4"))
    # v0.7.0.7: high-confidence French quality gate. It only runs an extra
    # micro-correction when deterministic heuristics flag an obvious language
    # problem; normal replies pay no extra generation cost.
    LLM_VOICE_QUALITY_GATE: bool = _env_bool("LLM_VOICE_QUALITY_GATE", True)
    LLM_VOICE_QUALITY_NUM_PREDICT: int = int(os.getenv("LLM_VOICE_QUALITY_NUM_PREDICT", "80"))
    LLM_VOICE_QUALITY_MAX_SENTENCES: int = int(os.getenv("LLM_VOICE_QUALITY_MAX_SENTENCES", "2"))
    # v0.7.0.8: spoken answers are short by default. A deterministic policy
    # appends a compact voice-output contract and trims only complete trailing
    # sentences if the model ignores that contract.
    LLM_VOICE_MAX_SENTENCES: int = int(os.getenv("LLM_VOICE_MAX_SENTENCES", "3"))
    LLM_VOICE_MAX_CHARS: int = int(os.getenv("LLM_VOICE_MAX_CHARS", "320"))
    LLM_VOICE_DETAIL_MAX_SENTENCES: int = int(os.getenv("LLM_VOICE_DETAIL_MAX_SENTENCES", "5"))
    LLM_VOICE_DETAIL_MAX_CHARS: int = int(os.getenv("LLM_VOICE_DETAIL_MAX_CHARS", "560"))
    LLM_VOICE_FIRST_SENTENCE_TARGET: int = int(os.getenv("LLM_VOICE_FIRST_SENTENCE_TARGET", "85"))
    # v0.7.0.14: realtime dialogue streams text immediately and releases only
    # complete, deterministic-safe sentences to TTS while generation continues.
    REALTIME_DIALOGUE_ENABLED: bool = _env_bool("REALTIME_DIALOGUE_ENABLED", True)
    REALTIME_DIALOGUE_REQUIRE_CORESIDENCE: bool = _env_bool("REALTIME_DIALOGUE_REQUIRE_CORESIDENCE", True)
    REALTIME_DIALOGUE_MAX_RAM_PCT: float = _env_float_upgrade("REALTIME_DIALOGUE_MAX_RAM_PCT", 92, (87,))
    REALTIME_DIALOGUE_MAX_QUEUE_SEGMENTS: int = int(os.getenv("REALTIME_DIALOGUE_MAX_QUEUE_SEGMENTS", "6"))
    # v0.7.0.15.2: true producer/consumer speech. Keep at most two rendered
    # segments ahead so interruption remains responsive and temp audio stays small.
    REALTIME_DIALOGUE_AUDIO_QUEUE_SEGMENTS: int = int(os.getenv("REALTIME_DIALOGUE_AUDIO_QUEUE_SEGMENTS", "2"))
    REALTIME_DIALOGUE_MIN_SENTENCE_CHARS: int = int(os.getenv("REALTIME_DIALOGUE_MIN_SENTENCE_CHARS", "4"))
    # Stable-knowledge self-check. It is never used for live/current facts and
    # only runs when conservative heuristics flag a factual-explanation sentence.
    LLM_VOICE_KNOWLEDGE_GATE: bool = _env_bool("LLM_VOICE_KNOWLEDGE_GATE", True)
    LLM_VOICE_KNOWLEDGE_NUM_PREDICT: int = int(os.getenv("LLM_VOICE_KNOWLEDGE_NUM_PREDICT", "72"))
    LLM_VOICE_KNOWLEDGE_MAX_SENTENCES: int = int(os.getenv("LLM_VOICE_KNOWLEDGE_MAX_SENTENCES", "1"))
    # v0.7.0.9: never accept a flagged factual sentence merely because the same
    # small conversational model says "OK". Unknown flagged claims fail closed.
    LLM_VOICE_KNOWLEDGE_SELF_VERIFY: bool = _env_bool("LLM_VOICE_KNOWLEDGE_SELF_VERIFY", False)
    # Direct definition requests are routed through a deterministic reference
    # layer before the conversational LLM. A tiny local core works offline;
    # controlled Internet may query only the fixed French Wikipedia API.
    KNOWLEDGE_REFERENCE_ENABLED: bool = _env_bool("KNOWLEDGE_REFERENCE_ENABLED", True)
    KNOWLEDGE_REFERENCE_WEB_ENABLED: bool = _env_bool("KNOWLEDGE_REFERENCE_WEB_ENABLED", True)
    KNOWLEDGE_REFERENCE_MAX_SENTENCES: int = int(os.getenv("KNOWLEDGE_REFERENCE_MAX_SENTENCES", "3"))
    KNOWLEDGE_REFERENCE_MAX_CHARS: int = int(os.getenv("KNOWLEDGE_REFERENCE_MAX_CHARS", "420"))
    LLM_VOICE_MAX_HISTORY_MESSAGES: int = _env_int_upgrade("LLM_VOICE_MAX_HISTORY_MESSAGES", _ADAPTIVE_PROFILE.llm_voice_history, (6,))
    LLM_VOICE_MEMORY_LIMIT: int = _env_int_upgrade("LLM_VOICE_MEMORY_LIMIT", _ADAPTIVE_PROFILE.llm_voice_memory, (3,))
    LLM_NUM_CTX: int = int(os.getenv("LLM_NUM_CTX", str(_ADAPTIVE_PROFILE.llm_num_ctx)))
    LLM_NUM_PREDICT: int = int(os.getenv("LLM_NUM_PREDICT", str(_ADAPTIVE_PROFILE.llm_num_predict)))
    # Visual answers are not constrained by the spoken-answer budget.
    # v0.7.0.15.3 keeps ordinary non-tool visual generation on the warm 3B
    # brain; only explicitly complex analyses are allowed to cold-load llama3.1.
    LLM_VISUAL_NUM_PREDICT: int = int(os.getenv("LLM_VISUAL_NUM_PREDICT", str(_ADAPTIVE_PROFILE.llm_visual_num_predict)))
    LLM_VISUAL_FAST_NUM_PREDICT: int = int(os.getenv("LLM_VISUAL_FAST_NUM_PREDICT", str(_ADAPTIVE_PROFILE.llm_visual_fast_num_predict)))
    # RC3.1: structured screen lists need enough output budget to finish instead
    # of stopping at the old 420-token visual-fast ceiling.
    LLM_VISUAL_STRUCTURED_NUM_PREDICT: int = int(os.getenv("LLM_VISUAL_STRUCTURED_NUM_PREDICT", "900"))
    # v0.7.0.15.6.11 Material & Orb Typography Match V11. V10 composition + denser plasma/HUD matter and technical orb typography.
    OPENGL_ORB_ENABLED: bool = _env_bool("OPENGL_ORB_ENABLED", True)
    OPENGL_ORB_FPS: int = int(os.getenv("OPENGL_ORB_FPS", str(_ADAPTIVE_PROFILE.native_opengl_fps)))
    VISUAL_FOLLOWUP_TTL_SECONDS: float = float(os.getenv("VISUAL_FOLLOWUP_TTL_SECONDS", "600"))
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.62"))
    LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "0.90"))
    LLM_MAX_HISTORY_MESSAGES: int = int(os.getenv("LLM_MAX_HISTORY_MESSAGES", "12"))
    LLM_CONNECT_TIMEOUT: float = float(os.getenv("LLM_CONNECT_TIMEOUT", "3.0"))
    LLM_READ_TIMEOUT: float = float(os.getenv("LLM_READ_TIMEOUT", "75.0"))

    # v0.7.1.2 Hybrid Groq/Local Runtime. Groq is never used without an
    # explicitly configured API key; Security Core, memory, tools and TTS stay local.
    # Runtime v2 philosophy: Cloud Intelligence / Local Control. Legacy
    # ``hybrid`` remains accepted by the router for existing .env files.
    AURA_RUNTIME_MODE: str = os.getenv("AURA_RUNTIME_MODE", "cloud").strip().lower()
    GROQ_ENABLED: bool = _env_bool("GROQ_ENABLED", True)
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "").strip()
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").strip().rstrip("/")
    GROQ_FAST_MODEL: str = os.getenv("GROQ_FAST_MODEL", "llama-3.1-8b-instant").strip() or "llama-3.1-8b-instant"
    GROQ_REASONING_MODEL: str = os.getenv("GROQ_REASONING_MODEL", "llama-3.3-70b-versatile").strip() or "llama-3.3-70b-versatile"
    GROQ_ROUTER_MODEL: str = os.getenv("GROQ_ROUTER_MODEL", GROQ_FAST_MODEL).strip() or GROQ_FAST_MODEL
    GROQ_CONNECT_TIMEOUT: float = float(os.getenv("GROQ_CONNECT_TIMEOUT", "2.5"))
    GROQ_READ_TIMEOUT_SECONDS: float = float(os.getenv("GROQ_READ_TIMEOUT_SECONDS", "12.0"))
    GROQ_STT_ENABLED: bool = _env_bool("GROQ_STT_ENABLED", True)
    GROQ_STT_MODEL: str = os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo").strip() or "whisper-large-v3-turbo"
    GROQ_STT_TIMEOUT_SECONDS: float = float(os.getenv("GROQ_STT_TIMEOUT_SECONDS", "8.0"))

    # Patch 26.8.3 — Gemini is AURA's secondary cloud brain and preferred
    # document/multimodal engine. Ordinary hybrid conversation keeps Groq first
    # when both providers are configured. No Gemini request is possible without
    # an explicitly persisted local API key.
    GEMINI_ENABLED: bool = _env_bool("GEMINI_ENABLED", True)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "").strip()
    GEMINI_BASE_URL: str = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta"
    ).strip().rstrip("/")
    GEMINI_UPLOAD_BASE_URL: str = os.getenv(
        "GEMINI_UPLOAD_BASE_URL", "https://generativelanguage.googleapis.com/upload/v1beta"
    ).strip().rstrip("/")
    GEMINI_FAST_MODEL: str = os.getenv("GEMINI_FAST_MODEL", "gemini-3.6-flash").strip() or "gemini-3.6-flash"
    GEMINI_REASONING_MODEL: str = os.getenv("GEMINI_REASONING_MODEL", GEMINI_FAST_MODEL).strip() or GEMINI_FAST_MODEL
    GEMINI_DOCUMENT_MODEL: str = os.getenv("GEMINI_DOCUMENT_MODEL", GEMINI_REASONING_MODEL).strip() or GEMINI_REASONING_MODEL
    GEMINI_CONNECT_TIMEOUT: float = float(os.getenv("GEMINI_CONNECT_TIMEOUT", "3.0"))
    GEMINI_READ_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_READ_TIMEOUT_SECONDS", "35.0"))
    GEMINI_FILE_UPLOAD_TIMEOUT_SECONDS: float = float(os.getenv("GEMINI_FILE_UPLOAD_TIMEOUT_SECONDS", "45.0"))
    GEMINI_NATIVE_PDF_ENABLED: bool = _env_bool("GEMINI_NATIVE_PDF_ENABLED", True)

    # Document routing. AUTO = Gemini -> Groq -> local, but explicit local-only
    # language always wins. The provider label is shown in the attachment UI.
    DOCUMENT_ANALYSIS_PROVIDER: str = os.getenv("DOCUMENT_ANALYSIS_PROVIDER", "auto").strip().lower()
    DOCUMENT_CLOUD_ENABLED: bool = _env_bool("DOCUMENT_CLOUD_ENABLED", True)
    DOCUMENT_LOCAL_CONTEXT_CHARS: int = int(os.getenv("DOCUMENT_LOCAL_CONTEXT_CHARS", "6000"))
    DOCUMENT_GROQ_CONTEXT_CHARS: int = int(os.getenv("DOCUMENT_GROQ_CONTEXT_CHARS", "12000"))
    DOCUMENT_GEMINI_CONTEXT_CHARS: int = int(os.getenv("DOCUMENT_GEMINI_CONTEXT_CHARS", "18000"))
    DOCUMENT_NUM_PREDICT: int = int(os.getenv("DOCUMENT_NUM_PREDICT", "4096"))
    DOCUMENT_GEMINI_OUTPUT_TOKENS: int = int(os.getenv("DOCUMENT_GEMINI_OUTPUT_TOKENS", "4096"))
    DOCUMENT_GEMINI_THINKING_LEVEL: str = os.getenv("DOCUMENT_GEMINI_THINKING_LEVEL", "low").strip().lower() or "low"

    HYBRID_LOCAL_FALLBACK: bool = _env_bool("HYBRID_LOCAL_FALLBACK", False)
    HYBRID_PRIVATE_MEMORY_LOCAL_ONLY: bool = _env_bool("HYBRID_PRIVATE_MEMORY_LOCAL_ONLY", True)
    HYBRID_KEEP_OLLAMA_COLD: bool = _env_bool("HYBRID_KEEP_OLLAMA_COLD", True)
    HYBRID_LOCAL_ONLY_MARKERS: tuple[str, ...] = (
        "local uniquement", "reste en local", "mode privé", "mode prive",
        "ne l'envoie pas", "ne l’envoie pas",
    )

    USER_NAME: str = os.getenv("USER_NAME", "")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # Memory & Continuity v0.6. All storage stays in the local SQLite database.
    MEMORY_ENABLED: bool = _env_bool("MEMORY_ENABLED", True)
    # Conservative automatic capture only for explicit preference/project/habit
    # patterns. Obviously sensitive text is never passively captured.
    MEMORY_AUTO_CAPTURE: bool = _env_bool("MEMORY_AUTO_CAPTURE", True)
    MEMORY_CONTEXT_LIMIT: int = int(os.getenv("MEMORY_CONTEXT_LIMIT", "5"))
    MEMORY_RELEVANCE_THRESHOLD: float = float(os.getenv("MEMORY_RELEVANCE_THRESHOLD", "0.55"))
    # Sensitive memories can be stored on explicit request but are excluded from
    # automatic LLM context unless this advanced opt-in is enabled.
    MEMORY_ALLOW_SENSITIVE_CONTEXT: bool = _env_bool("MEMORY_ALLOW_SENSITIVE_CONTEXT", False)

    # Grounded Intelligence + controlled Internet tools v0.7.0. The LLM never
    # receives arbitrary socket/network access. Deterministic tools authorize a
    # structured read-only action before any HTTP request.
    GROUNDED_INTELLIGENCE_ENABLED: bool = _env_bool("GROUNDED_INTELLIGENCE_ENABLED", True)
    INTERNET_TOOLS_ENABLED: bool = _env_bool("INTERNET_TOOLS_ENABLED", True)
    WEATHER_TOOL_ENABLED: bool = _env_bool("WEATHER_TOOL_ENABLED", True)
    # v0.7.1.2.5: detailed weather remains visible in the HUD/text result, but
    # spoken weather is deliberately compact to reduce CPU TTS latency.
    WEATHER_VOICE_CONCISE: bool = _env_bool("WEATHER_VOICE_CONCISE", True)
    WEATHER_VOICE_FEELS_LIKE_DELTA_C: float = float(os.getenv("WEATHER_VOICE_FEELS_LIKE_DELTA_C", "2.0"))
    WEATHER_VOICE_WIND_THRESHOLD_KMH: float = float(os.getenv("WEATHER_VOICE_WIND_THRESHOLD_KMH", "25"))
    WEATHER_VOICE_RAIN_PROB_THRESHOLD: int = int(os.getenv("WEATHER_VOICE_RAIN_PROB_THRESHOLD", "40"))
    # v0.7.1.2.7: weather semantics + lightweight Jarvis-style HUD motion.
    WEATHER_HUD_ANIMATIONS_ENABLED: bool = _env_bool("WEATHER_HUD_ANIMATIONS_ENABLED", True)
    WEATHER_HUD_ANIMATION_FPS: int = max(8, min(30, int(os.getenv("WEATHER_HUD_ANIMATION_FPS", "20"))))
    WEB_FETCH_ENABLED: bool = _env_bool("WEB_FETCH_ENABLED", True)
    WEB_SEARCH_ENABLED: bool = _env_bool("WEB_SEARCH_ENABLED", True)
    # v0.7.2.1 RC2.3 — official Google Search grounding through Gemini Interactions
    # API using the existing Gemini API key. No Brave/Tavily account is required.
    GOOGLE_SEARCH_GROUNDING_ENABLED: bool = _env_bool("GOOGLE_SEARCH_GROUNDING_ENABLED", True)
    GOOGLE_SEARCH_MODEL: str = os.getenv("GOOGLE_SEARCH_MODEL", "auto").strip() or "auto"
    # User requirement: search must never opt into Gemini 3 / paid-grounding routes
    # unless explicitly enabled. RC2.3 auto-selects only free-tier-capable 2.5 Flash models.
    GOOGLE_SEARCH_ALLOW_PAID_TIER: bool = _env_bool("GOOGLE_SEARCH_ALLOW_PAID_TIER", False)
    # Conservative local ceiling below Google's documented 500 RPD free-tier
    # grounding allowance for Flash/Flash-Lite. It is a safety brake, not a
    # billing-status detector: AURA never auto-upgrades or chooses a paid fallback.
    GOOGLE_SEARCH_DAILY_SAFETY_LIMIT: int = max(1, min(500, int(os.getenv("GOOGLE_SEARCH_DAILY_SAFETY_LIMIT", "450"))))
    GOOGLE_SEARCH_MAX_OUTPUT_TOKENS: int = max(256, int(os.getenv("GOOGLE_SEARCH_MAX_OUTPUT_TOKENS", "1600")))
    GOOGLE_SEARCH_TIMEOUT_SECONDS: float = float(os.getenv("GOOGLE_SEARCH_TIMEOUT_SECONDS", "25.0"))

    # v0.7.2.1 RC2.4 — zero-cost Web Search. New Gemini projects may no
    # longer be allowed to use the 2.5 Flash Search Grounding models even
    # though they remain listed by model discovery. Normal explicit research
    # therefore uses DDGS locally and tries free public search backends one at
    # a time. No search API key and no paid fallback are required.
    FREE_WEB_SEARCH_ENABLED: bool = _env_bool("FREE_WEB_SEARCH_ENABLED", True)
    FREE_WEB_SEARCH_BACKENDS: str = os.getenv(
        "FREE_WEB_SEARCH_BACKENDS", "google,duckduckgo,startpage,yahoo,mojeek"
    ).strip() or "google,duckduckgo,startpage,yahoo,mojeek"
    FREE_WEB_SEARCH_REGION: str = os.getenv("FREE_WEB_SEARCH_REGION", "fr-fr").strip() or "fr-fr"
    FREE_WEB_SEARCH_SAFESEARCH: str = os.getenv("FREE_WEB_SEARCH_SAFESEARCH", "moderate").strip().lower() or "moderate"
    FREE_WEB_SEARCH_TIMEOUT_SECONDS: float = float(os.getenv("FREE_WEB_SEARCH_TIMEOUT_SECONDS", "8.0"))
    FREE_WEB_SEARCH_SYNTHESIS_ENABLED: bool = _env_bool("FREE_WEB_SEARCH_SYNTHESIS_ENABLED", True)

    # Deprecated compatibility field. RC2.1 never transmits this value.
    BRAVE_SEARCH_API_KEY: str = os.getenv("BRAVE_SEARCH_API_KEY", "").strip()
    WEB_HTTP_TIMEOUT: float = float(os.getenv("WEB_HTTP_TIMEOUT", "8.0"))
    WEB_MAX_RESPONSE_BYTES: int = int(os.getenv("WEB_MAX_RESPONSE_BYTES", "262144"))
    WEB_MAX_REDIRECTS: int = int(os.getenv("WEB_MAX_REDIRECTS", "3"))
    WEB_FETCH_MAX_TEXT_CHARS: int = int(os.getenv("WEB_FETCH_MAX_TEXT_CHARS", "1800"))
    WEB_SEARCH_RESULT_COUNT: int = int(os.getenv("WEB_SEARCH_RESULT_COUNT", "4"))
    # Short-lived conversational tool state. Never persisted to SQLite.
    WEB_TOOL_PENDING_TTL_SECONDS: float = float(os.getenv("WEB_TOOL_PENDING_TTL_SECONDS", "120"))
    WEB_TOOL_CONTEXT_TTL_SECONDS: float = float(os.getenv("WEB_TOOL_CONTEXT_TTL_SECONDS", "300"))
    # v0.7.0.15.6.12: temporary fast text-only test mode. It suppresses
    # STT/TTS warmup/output and routes normal text turns through the small local
    # model so functional testing is not dominated by audio latency. Set false
    # later to restore the normal voice stack without reverting code.
    # Legacy fast-test switch is retained for diagnostics, but audio now has an
    # independent runtime switch so an old FAST_TEXT_TEST_MODE=true in .env no
    # longer leaves AURA permanently muted after this hotfix.
    FAST_TEXT_TEST_MODE: bool = _env_bool("FAST_TEXT_TEST_MODE", False)
    AUDIO_RUNTIME_ENABLED: bool = _env_bool("AUDIO_RUNTIME_ENABLED", True)
    AUDIO_RUNTIME_PAUSED: bool = not AUDIO_RUNTIME_ENABLED
    AUDIO_BACKGROUND_XTTS_PREWARM: bool = _env_bool("AUDIO_BACKGROUND_XTTS_PREWARM", True)
    AUDIO_XTTS_PREWARM_DELAY_MS: int = int(os.getenv("AUDIO_XTTS_PREWARM_DELAY_MS", "350"))
    FAST_TEXT_TEST_USE_VOICE_MODEL: bool = _env_bool("FAST_TEXT_TEST_USE_VOICE_MODEL", True)
    # v0.7.0.15.6.12.2: warm the small text-test brain after the Startup Gate
    # opens. The UI becomes interactive immediately; the background warmup only
    # removes cold-load latency when the user has not already started a turn.
    FAST_TEXT_TEST_PREWARM: bool = _env_bool("FAST_TEXT_TEST_PREWARM", True)
    FAST_TEXT_TEST_PREWARM_DELAY_MS: int = int(os.getenv("FAST_TEXT_TEST_PREWARM_DELAY_MS", "0"))
    FAST_TEXT_TEST_KEEP_ALIVE: str = os.getenv("FAST_TEXT_TEST_KEEP_ALIVE", "30m").strip() or "30m"

    # v0.7.1.0 Agent Kernel Foundation. Multi-tool execution is bounded,
    # registry-based and read-only in this first increment. Every step is still
    # authorized independently by SecurityPolicyEngine before worker execution.
    AGENT_KERNEL_ENABLED: bool = _env_bool("AGENT_KERNEL_ENABLED", True)
    AGENT_MULTI_TOOL_ENABLED: bool = _env_bool("AGENT_MULTI_TOOL_ENABLED", True)
    AGENT_MAX_STEPS: int = int(os.getenv("AGENT_MAX_STEPS", "6"))
    AGENT_STOP_ON_ERROR: bool = _env_bool("AGENT_STOP_ON_ERROR", False)
    # v0.7.1.1: one-pass Fast Intelligence Router. It is invoked only when the
    # deterministic planner declined and the request still looks multi-tool.
    AGENT_LLM_PLANNER_ENABLED: bool = _env_bool("AGENT_LLM_PLANNER_ENABLED", True)
    AGENT_ROUTER_MODEL: str = os.getenv("AGENT_ROUTER_MODEL", LLM_VOICE_MODEL).strip() or LLM_VOICE_MODEL
    AGENT_ROUTER_MODEL_EXPLICIT: bool = bool(str(os.getenv("AGENT_ROUTER_MODEL") or "").strip())
    AGENT_ROUTER_KEEP_ALIVE: str = os.getenv("AGENT_ROUTER_KEEP_ALIVE", FAST_TEXT_TEST_KEEP_ALIVE).strip() or "30m"
    AGENT_ROUTER_NUM_CTX: int = int(os.getenv("AGENT_ROUTER_NUM_CTX", str(LLM_VOICE_NUM_CTX)))
    AGENT_ROUTER_NUM_PREDICT: int = int(os.getenv("AGENT_ROUTER_NUM_PREDICT", "96"))
    AGENT_ROUTER_TEMPERATURE: float = float(os.getenv("AGENT_ROUTER_TEMPERATURE", "0.05"))
    AGENT_ROUTER_TOP_P: float = float(os.getenv("AGENT_ROUTER_TOP_P", "0.70"))
    AGENT_ROUTER_MIN_CONFIDENCE: float = float(os.getenv("AGENT_ROUTER_MIN_CONFIDENCE", "0.62"))
    AGENT_ROUTER_READ_TIMEOUT: float = float(os.getenv("AGENT_ROUTER_READ_TIMEOUT", "6.0"))
    # Never evict a hot expressive voice merely to run an optional routing pass.
    # If safe co-residency is unavailable, the mature legacy route wins instead.
    AGENT_ROUTER_PRESERVE_HOT_XTTS: bool = _env_bool("AGENT_ROUTER_PRESERVE_HOT_XTTS", True)
    AGENT_TOOL_SELECTOR_MAX: int = int(os.getenv("AGENT_TOOL_SELECTOR_MAX", "5"))
    AGENT_LOOP_MAX_SAME_SIGNATURE: int = int(os.getenv("AGENT_LOOP_MAX_SAME_SIGNATURE", "2"))
    AGENT_LOOP_MAX_SAME_ACTION: int = int(os.getenv("AGENT_LOOP_MAX_SAME_ACTION", "4"))

    # Short-lived deterministic slot filling (not persistent user memory).
    LOCAL_ACTION_PENDING_TTL_SECONDS: float = float(os.getenv("LOCAL_ACTION_PENDING_TTL_SECONDS", "120"))

    # Dedicated visual tool surfaces. Weather stays Open-Meteo-backed; Maps uses
    # universal Google Maps URLs for the final interactive map/navigation handoff.
    WEATHER_HUD_POPUP_ENABLED: bool = _env_bool("WEATHER_HUD_POPUP_ENABLED", True)
    MAPS_TOOL_ENABLED: bool = _env_bool("MAPS_TOOL_ENABLED", True)
    MAPS_HUD_POPUP_ENABLED: bool = _env_bool("MAPS_HUD_POPUP_ENABLED", True)
    AGENT_COMPOSITE_HUD_ENABLED: bool = _env_bool("AGENT_COMPOSITE_HUD_ENABLED", True)
    MAPS_DEFAULT_ORIGIN: str = os.getenv("MAPS_DEFAULT_ORIGIN", "").strip()
    MAPS_MIN_ZOOM: int = int(os.getenv("MAPS_MIN_ZOOM", "3"))
    MAPS_MAX_ZOOM: int = int(os.getenv("MAPS_MAX_ZOOM", "19"))
    MAPS_LOCATION_ZOOM: int = int(os.getenv("MAPS_LOCATION_ZOOM", "13"))
    MAPS_TILE_CACHE_MB: int = int(os.getenv("MAPS_TILE_CACHE_MB", "96"))
    MAPS_MAX_PENDING_TILES: int = int(os.getenv("MAPS_MAX_PENDING_TILES", "18"))

    # Conditional XTTS prewarm. It is allowed only after the explicit Dual Brain
    # co-residency probe and only when RAM/VRAM have conservative headroom.
    XTTS_CONDITIONAL_PREWARM: bool = _env_bool("XTTS_CONDITIONAL_PREWARM", True)
    XTTS_PREWARM_MAX_RAM_PCT: float = _env_float_upgrade("XTTS_PREWARM_MAX_RAM_PCT", 86, (60,))
    XTTS_PREWARM_MIN_AVAILABLE_RAM_GB: float = _env_float_upgrade("XTTS_PREWARM_MIN_AVAILABLE_RAM_GB", _ADAPTIVE_PROFILE.xtts_prewarm_min_available_ram_gib, (5.0,))
    XTTS_PREWARM_MAX_PREDICTED_VRAM_PCT: float = float(os.getenv("XTTS_PREWARM_MAX_PREDICTED_VRAM_PCT", "55"))
    XTTS_PREWARM_MIN_FREE_VRAM_MB: float = float(os.getenv("XTTS_PREWARM_MIN_FREE_VRAM_MB", "2800"))
    XTTS_PREWARM_POSTLOAD_MAX_RAM_PCT: float = _env_float_upgrade("XTTS_PREWARM_POSTLOAD_MAX_RAM_PCT", 91, (88,))
    XTTS_PREWARM_POSTLOAD_MIN_AVAILABLE_RAM_GB: float = float(os.getenv("XTTS_PREWARM_POSTLOAD_MIN_AVAILABLE_RAM_GB", "2.0"))

    # Resource Guardian v0.6.2 -- conservative defaults for 16 GB RAM / 6 GB VRAM
    # class machines. Ollama and XTTS are treated as exclusive heavyweight GPU
    # workloads to prevent display resets and system-wide OutOfMemory failures.
    RESOURCE_GUARDIAN_ENABLED: bool = _env_bool("RESOURCE_GUARDIAN_ENABLED", True)
    RESOURCE_ALLOW_HEAVY_PRELOAD: bool = _env_bool("RESOURCE_ALLOW_HEAVY_PRELOAD", False)
    RESOURCE_RAM_WARN_PCT: float = _env_float_upgrade("RESOURCE_RAM_WARN_PCT", 88, (80,))
    RESOURCE_RAM_CRITICAL_PCT: float = _env_float_upgrade("RESOURCE_RAM_CRITICAL_PCT", 94, (88,))
    RESOURCE_RAM_EMERGENCY_PCT: float = _env_float_upgrade("RESOURCE_RAM_EMERGENCY_PCT", 97, (93,))
    # v0.7.0.15: dedicated Dual-Brain hysteresis. 88% is warning only; a hot
    # voice brain survives the normal ~90% transient observed on the target PC.
    VOICE_MEMORY_WARN_PCT: float = float(os.getenv("VOICE_MEMORY_WARN_PCT", "88"))
    VOICE_MEMORY_SOFT_PCT: float = float(os.getenv("VOICE_MEMORY_SOFT_PCT", "91"))
    VOICE_MEMORY_CRITICAL_PCT: float = float(os.getenv("VOICE_MEMORY_CRITICAL_PCT", "94"))
    VOICE_MEMORY_HARD_MIN_AVAILABLE_GB: float = float(os.getenv("VOICE_MEMORY_HARD_MIN_AVAILABLE_GB", "1.15"))
    VOICE_MEMORY_RECOVER_PCT: float = float(os.getenv("VOICE_MEMORY_RECOVER_PCT", "87"))
    VOICE_MEMORY_RECOVER_AVAILABLE_GB: float = float(os.getenv("VOICE_MEMORY_RECOVER_AVAILABLE_GB", "2.15"))
    # v0.7.1.3.5.5 -- fail closed before a cold local voice-brain load can
    # saturate 16 GB class systems. If NVIDIA compute is present but Ollama is
    # CPU-only, AURA will unload the model under pressure rather than allowing
    # Windows to reach the 98-99% RAM zone observed on the target laptop.
    VOICE_COLD_LOAD_MAX_PREDICTED_RAM_PCT: float = float(os.getenv("VOICE_COLD_LOAD_MAX_PREDICTED_RAM_PCT", "92"))
    VOICE_COLD_LOAD_MIN_AVAILABLE_AFTER_GB: float = float(os.getenv("VOICE_COLD_LOAD_MIN_AVAILABLE_AFTER_GB", "1.25"))
    VOICE_GPU_OFFLOAD_MIN_RATIO: float = float(os.getenv("VOICE_GPU_OFFLOAD_MIN_RATIO", "0.10"))
    VOICE_REQUIRE_GPU_WHEN_NVIDIA: bool = _env_bool("VOICE_REQUIRE_GPU_WHEN_NVIDIA", True)
    # v0.7.1.3.5.6 -- a cold voice model may perform one controlled Ollama
    # preload only when its /api/tags size fits comfortably inside dedicated
    # NVIDIA VRAM. The probe is verified immediately with /api/ps; CPU-only
    # placement is unloaded and rejected before the user generation starts.
    VOICE_GPU_PROBE_ENABLED: bool = _env_bool("VOICE_GPU_PROBE_ENABLED", True)
    VOICE_GPU_PROBE_VRAM_RESERVE_MB: float = float(os.getenv("VOICE_GPU_PROBE_VRAM_RESERVE_MB", "1536"))
    VOICE_GPU_PROBE_MAX_RAM_PCT: float = float(os.getenv("VOICE_GPU_PROBE_MAX_RAM_PCT", "82"))
    VOICE_GPU_PROBE_MIN_AVAILABLE_GB: float = float(os.getenv("VOICE_GPU_PROBE_MIN_AVAILABLE_GB", "3.0"))
    # v0.7.1.3.5.7 -- /api/ps may report "GPU" without identifying the
    # physical adapter. On hybrid laptops AURA therefore cross-checks the
    # Ollama claim against trusted NVIDIA telemetry (nvidia-smi/NVML). A
    # mismatch is fail-closed; no automatic Ollama restart or shell command is
    # performed. Host RAM is also rechecked after the preload before generation.
    VOICE_NVIDIA_PHYSICAL_CONFIRM_ENABLED: bool = _env_bool("VOICE_NVIDIA_PHYSICAL_CONFIRM_ENABLED", True)
    VOICE_NVIDIA_CONFIRM_MIN_USED_MB: float = float(os.getenv("VOICE_NVIDIA_CONFIRM_MIN_USED_MB", "256"))
    VOICE_NVIDIA_CONFIRM_MIN_DELTA_MB: float = float(os.getenv("VOICE_NVIDIA_CONFIRM_MIN_DELTA_MB", "64"))
    VOICE_GPU_POSTLOAD_MAX_RAM_PCT: float = float(os.getenv("VOICE_GPU_POSTLOAD_MAX_RAM_PCT", "90"))
    VOICE_GPU_POSTLOAD_MIN_AVAILABLE_GB: float = float(os.getenv("VOICE_GPU_POSTLOAD_MIN_AVAILABLE_GB", "1.50"))
    RESOURCE_VRAM_WARN_PCT: float = float(os.getenv("RESOURCE_VRAM_WARN_PCT", "75"))
    RESOURCE_VRAM_CRITICAL_PCT: float = float(os.getenv("RESOURCE_VRAM_CRITICAL_PCT", "85"))
    RESOURCE_OLLAMA_RESIDUAL_VRAM_MB: float = float(os.getenv("RESOURCE_OLLAMA_RESIDUAL_VRAM_MB", "256"))
    RESOURCE_OLLAMA_UNLOAD_TIMEOUT: float = float(os.getenv("RESOURCE_OLLAMA_UNLOAD_TIMEOUT", "4.0"))
    RESOURCE_GPU_QUERY_TIMEOUT: float = float(os.getenv("RESOURCE_GPU_QUERY_TIMEOUT", "4.0"))
    RESOURCE_GPU_SAMPLE_SECONDS: float = float(os.getenv("RESOURCE_GPU_SAMPLE_SECONDS", "10"))
    RESOURCE_XTTS_IDLE_SECONDS: float = float(os.getenv("RESOURCE_XTTS_IDLE_SECONDS", "300"))
    RESOURCE_RELEASE_STT_AFTER_USE: bool = _env_bool("RESOURCE_RELEASE_STT_AFTER_USE", True)
    RESOURCE_RELEASE_STT_BEFORE_LLM: bool = _env_bool("RESOURCE_RELEASE_STT_BEFORE_LLM", True)
    RESOURCE_RELEASE_STT_BEFORE_TTS: bool = _env_bool("RESOURCE_RELEASE_STT_BEFORE_TTS", True)

    # Voice v0.5.1 -- explicit push-to-talk only. Runtime recording is never
    # started by AURA herself. Voice models are local after INSTALL_VOICE.bat.
    VOICE_ENABLED: bool = _env_bool("VOICE_ENABLED", True)
    VOICE_AUTO_SPEAK: bool = _env_bool("VOICE_AUTO_SPEAK", True)
    VOICE_PRELOAD: bool = _env_bool("VOICE_PRELOAD", True)

    # Empty = Windows/default input with safe fallback to first usable input.
    # Can also be an integer device index or a case-insensitive name fragment.
    MIC_DEVICE: str = os.getenv("MIC_DEVICE", "")
    MIC_SAMPLE_RATE: int = int(os.getenv("MIC_SAMPLE_RATE", "16000"))
    MIC_CHANNELS: int = int(os.getenv("MIC_CHANNELS", "1"))
    MIC_MAX_SECONDS: float = float(os.getenv("MIC_MAX_SECONDS", "30"))
    MIC_MIN_SECONDS: float = float(os.getenv("MIC_MIN_SECONDS", "0.15"))
    MIC_NORMALIZE: bool = _env_bool("MIC_NORMALIZE", True)
    MIC_MAX_GAIN: float = float(os.getenv("MIC_MAX_GAIN", "8.0"))
    # RC3: Windows can expose PortAudio input devices a few seconds after the
    # shell appears. Recovery is status-only: it never starts recording and
    # never opens the microphone without a user push-to-talk action.
    MIC_RECOVERY_ENABLED: bool = _env_bool("MIC_RECOVERY_ENABLED", True)
    MIC_RECOVERY_INITIAL_DELAY_MS: int = max(250, int(os.getenv("MIC_RECOVERY_INITIAL_DELAY_MS", "2000")))
    MIC_RECOVERY_SECOND_DELAY_MS: int = max(500, int(os.getenv("MIC_RECOVERY_SECOND_DELAY_MS", "5000")))
    MIC_RECOVERY_RETRY_DELAY_MS: int = max(1000, int(os.getenv("MIC_RECOVERY_RETRY_DELAY_MS", "15000")))
    # RC3.1: one guarded PortAudio cache refresh can recover Windows input
    # devices that appear after process start. It is never performed while
    # capture is active and is limited to the first recovery attempt.
    MIC_RECOVERY_PORTAUDIO_REFRESH: bool = _env_bool("MIC_RECOVERY_PORTAUDIO_REFRESH", True)

    STT_MODEL: str = os.getenv("STT_MODEL", "small")
    STT_MODEL_PATH: str = os.getenv("STT_MODEL_PATH", "")
    STT_DEVICE: str = os.getenv("STT_DEVICE", "cpu")
    STT_COMPUTE_TYPE: str = os.getenv("STT_COMPUTE_TYPE", "int8")
    STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "fr")
    # Beam 1 is much faster for interactive push-to-talk than the old beam 5.
    STT_BEAM_SIZE: int = int(os.getenv("STT_BEAM_SIZE", "1"))
    # Push-to-talk already brackets speech; disabling VAD avoids discarding quiet voices.
    STT_VAD_FILTER: bool = _env_bool("STT_VAD_FILTER", False)
    STT_ALLOW_MODEL_DOWNLOAD: bool = _env_bool("STT_ALLOW_MODEL_DOWNLOAD", False)

    # TTS v0.5.2: XTTS primary with Piper fallback. Runtime stays local after
    # explicit INSTALL_XTTS.bat / INSTALL_VOICE.bat.
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "xtts").strip().lower()
    TTS_FALLBACK_ENGINE: str = os.getenv("TTS_FALLBACK_ENGINE", "piper").strip().lower()
    TTS_VOICE: str = os.getenv("TTS_VOICE", "fr_FR-siwis-medium")
    TTS_MODEL_PATH: str = os.getenv("TTS_MODEL_PATH", "")
    TTS_VOLUME: float = float(os.getenv("TTS_VOLUME", "0.92"))
    # v0.7.1.3.4: concise spoken channel + optional ElevenLabs. The API
    # key is read from the local environment only and is never persisted in
    # AURA's voice profile or included in hotfix archives.
    VOICE_CONCISE_ENABLED: bool = _env_bool("VOICE_CONCISE_ENABLED", True)
    VOICE_CONCISE_MAX_CHARS: int = int(os.getenv("VOICE_CONCISE_MAX_CHARS", "120"))
    VOICE_CONCISE_MAX_SENTENCES: int = int(os.getenv("VOICE_CONCISE_MAX_SENTENCES", "2"))
    VOICE_CONCISE_LONG_REPLY: str = os.getenv(
        "VOICE_CONCISE_LONG_REPLY",
        "Je t'ai préparé une réponse détaillée. Je te l'affiche à l'écran.",
    ).strip()
    ELEVENLABS_ENABLED: bool = _env_bool("ELEVENLABS_ENABLED", True)
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "").strip()
    ELEVENLABS_API_BASE: str = os.getenv("ELEVENLABS_API_BASE", "https://api.elevenlabs.io").strip()
    ELEVENLABS_MODEL: str = os.getenv("ELEVENLABS_MODEL", "eleven_flash_v2_5").strip()
    ELEVENLABS_TIMEOUT_SECONDS: float = float(os.getenv("ELEVENLABS_TIMEOUT_SECONDS", "8"))
    ELEVENLABS_VOICE_CACHE_SECONDS: float = float(os.getenv("ELEVENLABS_VOICE_CACHE_SECONDS", "300"))
    ELEVENLABS_MAX_SPEECH_CHARS: int = int(os.getenv("ELEVENLABS_MAX_SPEECH_CHARS", "100"))
    ELEVENLABS_LONG_REPLY: str = os.getenv(
        "ELEVENLABS_LONG_REPLY",
        "Je t'affiche le détail à l'écran.",
    ).strip()
    ELEVENLABS_LOW_QUOTA_RATIO: float = max(0.0, min(1.0, float(os.getenv("ELEVENLABS_LOW_QUOTA_RATIO", "0.25"))))
    ELEVENLABS_LOW_QUOTA_MAX_CHARS: int = int(os.getenv("ELEVENLABS_LOW_QUOTA_MAX_CHARS", "55"))
    ELEVENLABS_CRITICAL_QUOTA_RATIO: float = max(0.0, min(1.0, float(os.getenv("ELEVENLABS_CRITICAL_QUOTA_RATIO", "0.05"))))
    ELEVENLABS_STREAM_CHUNK_BYTES: int = int(os.getenv("ELEVENLABS_STREAM_CHUNK_BYTES", "8192"))
    ELEVENLABS_OPTIMIZE_STREAMING_LATENCY: int = max(0, min(4, int(os.getenv("ELEVENLABS_OPTIMIZE_STREAMING_LATENCY", "3"))))
    ELEVENLABS_SPEAKER_BOOST: bool = _env_bool("ELEVENLABS_SPEAKER_BOOST", True)
    ELEVENLABS_REQUIRE_QUOTA_CHECK: bool = _env_bool("ELEVENLABS_REQUIRE_QUOTA_CHECK", True)
    ELEVENLABS_QUOTA_CACHE_SECONDS: float = float(os.getenv("ELEVENLABS_QUOTA_CACHE_SECONDS", "60"))
    ELEVENLABS_PRIVATE_CONTENT_LOCAL_ONLY: bool = _env_bool("ELEVENLABS_PRIVATE_CONTENT_LOCAL_ONLY", True)
    # v0.7.1.3.5: optional multi-provider voice foundation. Cloud providers are
    # never required; Piper remains the deterministic local fallback.
    CLOUD_TTS_MAX_SPEECH_CHARS: int = int(os.getenv("CLOUD_TTS_MAX_SPEECH_CHARS", "100"))
    CLOUD_TTS_PRIVATE_CONTENT_LOCAL_ONLY: bool = _env_bool("CLOUD_TTS_PRIVATE_CONTENT_LOCAL_ONLY", True)
    GRADIUM_ENABLED: bool = _env_bool("GRADIUM_ENABLED", True)
    GRADIUM_API_KEY: str = os.getenv("GRADIUM_API_KEY", "").strip()
    GRADIUM_API_BASE: str = os.getenv("GRADIUM_API_BASE", "https://api.gradium.ai/api").strip()
    GRADIUM_WS_TTS_URL: str = os.getenv("GRADIUM_WS_TTS_URL", "wss://api.gradium.ai/api/speech/tts").strip()
    GRADIUM_MODEL: str = os.getenv("GRADIUM_MODEL", "default").strip()
    GRADIUM_TIMEOUT_SECONDS: float = float(os.getenv("GRADIUM_TIMEOUT_SECONDS", "8"))
    GRADIUM_VOICE_CACHE_SECONDS: float = float(os.getenv("GRADIUM_VOICE_CACHE_SECONDS", "300"))
    GRADIUM_PREFER_WEBSOCKET: bool = _env_bool("GRADIUM_PREFER_WEBSOCKET", True)
    GRADIUM_INCLUDE_CATALOG: bool = _env_bool("GRADIUM_INCLUDE_CATALOG", True)
    RESEMBLE_ENABLED: bool = _env_bool("RESEMBLE_ENABLED", True)
    RESEMBLE_API_KEY: str = os.getenv("RESEMBLE_API_KEY", "").strip()
    RESEMBLE_API_BASE: str = os.getenv("RESEMBLE_API_BASE", "https://app.resemble.ai/api/v2").strip()
    RESEMBLE_STREAM_URL: str = os.getenv("RESEMBLE_STREAM_URL", "https://f.cluster.resemble.ai/stream").strip()
    RESEMBLE_TIMEOUT_SECONDS: float = float(os.getenv("RESEMBLE_TIMEOUT_SECONDS", "10"))
    RESEMBLE_VOICE_CACHE_SECONDS: float = float(os.getenv("RESEMBLE_VOICE_CACHE_SECONDS", "300"))
    RESEMBLE_STREAM_CHUNK_BYTES: int = int(os.getenv("RESEMBLE_STREAM_CHUNK_BYTES", "8192"))
    CHATTERBOX_ENABLED: bool = _env_bool("CHATTERBOX_ENABLED", False)
    CHATTERBOX_ALLOW_MODEL_LOAD: bool = _env_bool("CHATTERBOX_ALLOW_MODEL_LOAD", False)
    CHATTERBOX_DEVICE: str = os.getenv("CHATTERBOX_DEVICE", "cuda").strip().lower()
    XTTS_DEVICE: str = os.getenv("XTTS_DEVICE", "cpu")
    # CUDA is opt-in after the dedicated safe probe. This avoids a display/GPU
    # driver reset merely because XTTS is being diagnosed or preloaded.
    XTTS_ALLOW_CUDA: bool = _env_bool("XTTS_ALLOW_CUDA", False)
    # Crash guard: XTTS CUDA shares the physical display adapter with the
    # OpenGL shell on most laptops. 6 GiB-class GPUs have repeatedly proven
    # vulnerable to WDDM/TDR resets under concurrent CUDA + animated OpenGL.
    # Keep voice enabled, but force the Guardian to select the lightweight
    # local fallback unless enough dedicated VRAM is measured.
    XTTS_CUDA_DISPLAY_MIN_VRAM_MB: float = float(os.getenv("XTTS_CUDA_DISPLAY_MIN_VRAM_MB", "8192"))
    RESOURCE_DISPLAY_GPU_RESERVE_MB: float = float(os.getenv("RESOURCE_DISPLAY_GPU_RESERVE_MB", "1536"))
    # v0.7.1.3.1: hardware-aware XTTS residency probe. The probe is dry-run by
    # default: it measures eligibility but never loads XTTS/CUDA or changes GPU
    # preferences. Shared GPU memory is never counted as CUDA VRAM.
    XTTS_SAFE_RESIDENCY_PROBE: bool = _env_bool("XTTS_SAFE_RESIDENCY_PROBE", True)
    XTTS_SAFE_PROBE_MIN_RAM_AVAILABLE_GB: float = float(os.getenv("XTTS_SAFE_PROBE_MIN_RAM_AVAILABLE_GB", "4.0"))
    XTTS_SAFE_PROBE_POSTLOAD_RAM_RESERVE_GB: float = float(os.getenv("XTTS_SAFE_PROBE_POSTLOAD_RAM_RESERVE_GB", "2.75"))
    XTTS_SAFE_PROBE_VRAM_RESERVE_MB: float = float(os.getenv("XTTS_SAFE_PROBE_VRAM_RESERVE_MB", "1200"))
    XTTS_SAFE_PROBE_FRAGMENTATION_MB: float = float(os.getenv("XTTS_SAFE_PROBE_FRAGMENTATION_MB", "384"))
    # v0.7.1.3.2: one controlled real CUDA residency trial after the dry-run
    # probe passes. The trial is non-persistent by default and always releases
    # XTTS afterwards; Piper remains the production fallback.
    XTTS_CONTROLLED_TRIAL_ENABLED: bool = _env_bool("XTTS_CONTROLLED_TRIAL_ENABLED", False)
    XTTS_CONTROLLED_TRIAL_KEEP_LOADED: bool = _env_bool("XTTS_CONTROLLED_TRIAL_KEEP_LOADED", False)
    XTTS_CONTROLLED_TRIAL_TEXT: str = os.getenv("XTTS_CONTROLLED_TRIAL_TEXT", "Prêt.")
    XTTS_CONTROLLED_TRIAL_MAX_RAM_PCT: float = float(os.getenv("XTTS_CONTROLLED_TRIAL_MAX_RAM_PCT", "88"))
    XTTS_CONTROLLED_TRIAL_MIN_RAM_AVAILABLE_GB: float = float(os.getenv("XTTS_CONTROLLED_TRIAL_MIN_RAM_AVAILABLE_GB", "3.0"))
    XTTS_CONTROLLED_TRIAL_MIN_FREE_VRAM_MB: float = float(os.getenv("XTTS_CONTROLLED_TRIAL_MIN_FREE_VRAM_MB", "1200"))
    XTTS_LANGUAGE: str = os.getenv("XTTS_LANGUAGE", "fr")
    XTTS_VOICE_MODE: str = os.getenv("XTTS_VOICE_MODE", "preset")
    XTTS_PRESET_SPEAKER: str = os.getenv("XTTS_PRESET_SPEAKER", "Nova Hogarth")
    XTTS_SPEAKER_ID: str = os.getenv("XTTS_SPEAKER_ID", "AURA_CUSTOM")
    XTTS_REFERENCE_WAV: str = os.getenv("XTTS_REFERENCE_WAV", "")
    XTTS_SPEED: float = float(os.getenv("XTTS_SPEED", "0.96"))
    XTTS_TEMPERATURE: float = float(os.getenv("XTTS_TEMPERATURE", "0.68"))
    # Voice Lab fast audition: reduces click-to-audio latency while comparing many speakers.
    XTTS_PREVIEW_MAX_CHARS: int = int(os.getenv("XTTS_PREVIEW_MAX_CHARS", "120"))
    XTTS_PREVIEW_FAST: bool = _env_bool("XTTS_PREVIEW_FAST", True)
    XTTS_SHORT_TEXT_NO_SPLIT_CHARS: int = int(os.getenv("XTTS_SHORT_TEXT_NO_SPLIT_CHARS", "360"))

    # Fast Speech v0.6.5. Stable progressive synthesis uses the public TTS API
    # and overlaps generation of later chunks with playback of earlier chunks.
    # Native XTTS inference_stream remains opt-in/experimental for a later probe.
    FAST_SPEECH_ENABLED: bool = _env_bool("FAST_SPEECH_ENABLED", True)
    FAST_SPEECH_FIRST_CHUNK_CHARS: int = int(os.getenv("FAST_SPEECH_FIRST_CHUNK_CHARS", "120"))
    FAST_SPEECH_NEXT_CHUNK_CHARS: int = int(os.getenv("FAST_SPEECH_NEXT_CHUNK_CHARS", "170"))
    FAST_SPEECH_MIN_CHUNK_CHARS: int = int(os.getenv("FAST_SPEECH_MIN_CHUNK_CHARS", "48"))
    # A complete sentence may exceed the normal chunk target, but beyond this
    # size XTTS prosody is usually smoother when split on a real clause.
    FAST_SPEECH_MAX_SENTENCE_CHARS: int = int(os.getenv("FAST_SPEECH_MAX_SENTENCE_CHARS", "180"))
    FAST_SPEECH_MAX_CHUNKS: int = int(os.getenv("FAST_SPEECH_MAX_CHUNKS", "8"))
    FAST_SPEECH_MIN_TEXT_CHARS: int = int(os.getenv("FAST_SPEECH_MIN_TEXT_CHARS", "64"))
    FAST_SPEECH_NATIVE_STREAMING: bool = _env_bool("FAST_SPEECH_NATIVE_STREAMING", True)
    # v0.7.1.3.5.9: XTTS native streaming / local-first tuning. These knobs
    # apply only to the already opt-in XTTS CUDA path; they never enable CUDA.
    XTTS_NATIVE_STREAM_CHUNK_SIZE: int = max(8, min(60, int(os.getenv("XTTS_NATIVE_STREAM_CHUNK_SIZE", "18"))))
    XTTS_NATIVE_STREAM_OVERLAP_SAMPLES: int = max(256, min(4096, int(os.getenv("XTTS_NATIVE_STREAM_OVERLAP_SAMPLES", "1024"))))
    XTTS_NATIVE_STREAM_SAMPLE_RATE: int = 24000
    XTTS_CONDITIONING_CACHE_ENABLED: bool = _env_bool("XTTS_CONDITIONING_CACHE_ENABLED", True)
    XTTS_LOCAL_FIRST_ENABLED: bool = _env_bool("XTTS_LOCAL_FIRST_ENABLED", True)
    XTTS_LOCAL_FIRST_CLOUD_FALLBACK: str = os.getenv("XTTS_LOCAL_FIRST_CLOUD_FALLBACK", "gradium").strip().lower()
    XTTS_LOCAL_FIRST_SILENT_WARMUP: bool = _env_bool("XTTS_LOCAL_FIRST_SILENT_WARMUP", True)
    XTTS_LOCAL_FIRST_WARMUP_TEXT: str = os.getenv("XTTS_LOCAL_FIRST_WARMUP_TEXT", "Prêt.").strip() or "Prêt."
    XTTS_LOCAL_FIRST_KEEP_RESIDENT: bool = _env_bool("XTTS_LOCAL_FIRST_KEEP_RESIDENT", True)
    # v0.7.1.3.6.2: a warm local-first voice owns residency priority. A cold local
    # LLM must never evict XTTS merely to run a speculative Ollama GPU probe.
    XTTS_LOCAL_FIRST_PROTECT_RESIDENCY: bool = _env_bool("XTTS_LOCAL_FIRST_PROTECT_RESIDENCY", True)
    XTTS_LOCAL_FIRST_IDLE_SECONDS: float = float(os.getenv("XTTS_LOCAL_FIRST_IDLE_SECONDS", "1800"))
    FAST_SPEECH_CONTINUOUS_PLAYBACK: bool = _env_bool("FAST_SPEECH_CONTINUOUS_PLAYBACK", True)
    TTS_TAIL_FADE_MS: float = float(os.getenv("TTS_TAIL_FADE_MS", "32"))
    TTS_TAIL_SILENCE_MS: float = float(os.getenv("TTS_TAIL_SILENCE_MS", "36"))
    # Slightly slower delivery: warmer and less synthetic without exaggeration.
    TTS_LENGTH_SCALE: float = float(os.getenv("TTS_LENGTH_SCALE", "1.14"))
    TTS_NOISE_SCALE: float = float(os.getenv("TTS_NOISE_SCALE", "0.667"))
    TTS_NOISE_W_SCALE: float = float(os.getenv("TTS_NOISE_W_SCALE", "0.80"))
    TTS_MAX_CHARS: int = int(os.getenv("TTS_MAX_CHARS", "900"))
    PIPER_STREAMING_ENABLED: bool = _env_bool("PIPER_STREAMING_ENABLED", True)
    PIPER_BACKGROUND_PREWARM: bool = _env_bool("PIPER_BACKGROUND_PREWARM", True)
    # v0.7.1.2.4/8: bounded speech calls reduce Piper time-to-first-audio.
    # The first clause is intentionally much shorter than later clauses. Real
    # Windows traces showed 55-60 character first calls occasionally taking
    # 4-5 seconds even with a resident model.
    PIPER_FIRST_SEGMENT_CHARS: int = max(28, int(os.getenv("PIPER_FIRST_SEGMENT_CHARS", "44")))
    PIPER_NEXT_SEGMENT_CHARS: int = max(PIPER_FIRST_SEGMENT_CHARS, int(os.getenv("PIPER_NEXT_SEGMENT_CHARS", "110")))
    PIPER_FIRST_SEGMENT_MIN_CHARS: int = max(10, int(os.getenv("PIPER_FIRST_SEGMENT_MIN_CHARS", "14")))
    PIPER_AUDIO_QUEUE_CHUNKS: int = max(1, min(12, int(os.getenv("PIPER_AUDIO_QUEUE_CHUNKS", "4"))))
    # Loading the ONNX session is not enough to warm the first inference. Consume
    # one tiny synthesis silently during background prewarm so the first real
    # user turn does not pay ONNX execution/setup cost.
    PIPER_INFERENCE_PREWARM: bool = _env_bool("PIPER_INFERENCE_PREWARM", True)
    PIPER_PREWARM_TEXT: str = os.getenv("PIPER_PREWARM_TEXT", "Prêt.").strip() or "Prêt."

    # v0.7.0.15 Smart Speech + Visual Result Handoff. Long/search answers stay
    # fully visible while AURA speaks one short natural handoff sentence.
    VISUAL_RESULT_HANDOFF_ENABLED: bool = _env_bool("VISUAL_RESULT_HANDOFF_ENABLED", True)
    VISUAL_RESULT_MIN_CHARS: int = int(os.getenv("VISUAL_RESULT_MIN_CHARS", "360"))
    VISUAL_RESULT_TOOL_MIN_CHARS: int = int(os.getenv("VISUAL_RESULT_TOOL_MIN_CHARS", "220"))
    VISUAL_RESULT_LONG_TOOL_CHARS: int = int(os.getenv("VISUAL_RESULT_LONG_TOOL_CHARS", "650"))
    VISUAL_RESULT_INTENT_ENABLED: bool = _env_bool("VISUAL_RESULT_INTENT_ENABLED", True)

    BASE_DIR: Path = BASE_DIR
    CONFIG_DIR: Path = _AURA_PATHS.config_root
    LOG_DIR: Path = _AURA_PATHS.logs_root
    DB_PATH: Path = _AURA_PATHS.database_file
    MODEL_DIR: Path = _AURA_PATHS.models_root
    VOICE_MODEL_DIR: Path = MODEL_DIR / "voice"
    XTTS_HOME: Path = VOICE_MODEL_DIR / "coqui"
    CACHE_DIR: Path = _AURA_PATHS.cache_root
    DUAL_BRAIN_MARKER: Path = CONFIG_DIR / "dual_brain_gpu_ok.json"
    TEMP_DIR: Path = _AURA_PATHS.temp_root

    def __init__(self):
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.VOICE_MODEL_DIR.mkdir(parents=True, exist_ok=True)
        self.XTTS_HOME.mkdir(parents=True, exist_ok=True)
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)


settings = Settings()
