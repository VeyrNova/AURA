from __future__ import annotations

"""AURA v0.7.2.1 active release diagnostics.

This suite deliberately validates the current canonical architecture rather than
historical implementation contracts that were superseded by Cloud Intelligence /
Local Control. It never performs live Groq/Gemini calls and never requires Ollama.
"""

import argparse
import hashlib
import os
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PRODUCTION_FILES = [
    "core/version.py",
    "core/event_bus.py",
    "runtime/state_manager.py",
    "runtime/intelligence_router.py",
    "runtime/hybrid_runtime.py",
    "runtime/resource_guardian.py",
    "config/settings.py",
    "consciousness/self_model.py",
    "core/aura_core.py",
    "ai/local_first_voice.py",
    "ai/llm_manager.py",
    "ai/visual_routing.py",
    "services/document_analysis.py",
    "voice/microphone.py",
    "voice/voice_engine.py",
    "tools/search_intent.py",
    "tools/internet_manager.py",
    "tools/web_search.py",
    "agent/tool_selector.py",
    "ui/action_icons.py",
    "ui/text_rendering.py",
    "ui/chat_panel.py",
    "ui/holographic_results_panel.py",
    "ui/final_modules.py",
    "ui/main_window.py",
    "scripts/web_tools_status.py",
]

ACTIVE_TEST_MODULES = [
    "tests.test_runtime_v2_foundation_v0721",
    "tests.test_runtime_v2_rc2_v0721",
    "tests.test_runtime_v2_rc3_async_voice_v0721",
    "tests.test_runtime_v2_rc31_hardening_v0721",
    "tests.test_runtime_v2_rc32_voice_visual_bridge_v0721",
    "tests.test_hybrid_runtime_v0712",
    "tests.test_ai_research_routing_lock_patch266_v072",
    "tests.test_patch2683_multibrain_documents",
    "tests.test_patch2684_document_fast_lane",
    "tests.test_patch2685_gemini_response_integrity",
    "tests.test_patch2686_response_text_integrity",
    "tests.test_patch2687_home_attachment_voice_identity",
    "tests.test_patch2688_response_math_sanitizer",
    "tests.test_security_policy",
    "tests.test_router_security",
    "tests.test_memory_v060",
    "tests.test_memory_context_v060",
    "tests.test_memory_human_v061",
    "tests.test_memory_intents_v060",
    "tests.test_memory_profile_recall_v0662",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def compile_check() -> None:
    for rel in PRODUCTION_FILES:
        path = ROOT / rel
        if not path.is_file():
            raise RuntimeError(f"missing production file: {rel}")
        py_compile.compile(str(path), doraise=True)
    print(f"[PASS] compile: {len(PRODUCTION_FILES)} production files")


def contract_check() -> None:
    from config.settings import settings
    from core.version import AURA_BUILD, AURA_RELEASE_CHANNEL, AURA_VERSION
    from runtime.intelligence_router import choose_document_route, choose_llm_route
    from runtime.state_manager import normalize_state

    if AURA_VERSION != "0.7.2.1" or settings.APP_VERSION != AURA_VERSION:
        raise RuntimeError(f"version mismatch: core={AURA_VERSION} settings={settings.APP_VERSION}")
    if not AURA_BUILD.startswith("2026.08.15"):
        raise RuntimeError(f"unexpected build: {AURA_BUILD}")
    if AURA_RELEASE_CHANNEL != "consolidation-rc3.2":
        raise RuntimeError(f"unexpected release channel: {AURA_RELEASE_CHANNEL}")
    if normalize_state("PROCESSING") != "ANALYZING" or normalize_state("EXECUTING") != "ACTING":
        raise RuntimeError("legacy state aliases are not normalized")

    # Do not require secrets. If providers are configured, policy must route to
    # a real cloud provider. If none are configured, local-disabled is allowed.
    conversational = choose_llm_route("Bonjour Aura", voice_output=True)
    if conversational.provider not in {"groq", "gemini", "local"}:
        raise RuntimeError(f"invalid conversation provider: {conversational}")
    document = choose_document_route("analyse ce document")
    if document.provider not in {"gemini", "groq", "local"}:
        raise RuntimeError(f"invalid document provider: {document}")

    # Critical release contract: local generation is optional by default.
    if "LOCAL_LLM_ENABLED" not in settings.__dict__:
        # Dataclass/settings object implementations may expose class attrs.
        if not hasattr(settings, "LOCAL_LLM_ENABLED"):
            raise RuntimeError("LOCAL_LLM_ENABLED setting missing")

    main_src = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8", errors="replace")
    guardian_src = (ROOT / "runtime" / "resource_guardian.py").read_text(encoding="utf-8", errors="replace")
    rendering_src = (ROOT / "ui" / "text_rendering.py").read_text(encoding="utf-8", errors="replace")
    for marker in [
        "Document attachment retained on Home; conversation popup unchanged",
        "Document FAST lane dispatched",
        "Voice Identity Lock",
    ]:
        if marker not in main_src and marker not in guardian_src:
            raise RuntimeError(f"missing regression marker: {marker}")
    if "normalize_markdown_text" not in rendering_src:
        raise RuntimeError("response text sanitizer missing")
    visual_routing_src = (ROOT / "ai" / "visual_routing.py").read_text(encoding="utf-8", errors="replace")
    if "visual-structured" not in visual_routing_src or "LLM_VISUAL_STRUCTURED_NUM_PREDICT" not in visual_routing_src:
        raise RuntimeError("RC3.1 structured visual output budget missing")
    if "SEARCH READY" not in main_src or "INSTALLER DDGS" not in main_src:
        raise RuntimeError("zero-cost Web Search UI status marker missing")
    for marker in [
        "XTTS async voice warmup active: UI remains interactive",
        "Microphone recovery scheduled",
        "User message accepted while Camilla warms asynchronously",
        "Voice Identity Lock: TTS suppressed while Camilla warms",
    ]:
        if marker not in main_src:
            raise RuntimeError(f"RC3.1 async voice contract missing: {marker}")
    voice_engine_src = (ROOT / "voice" / "voice_engine.py").read_text(encoding="utf-8", errors="replace")
    xtts_src = (ROOT / "voice" / "xtts_tts.py").read_text(encoding="utf-8", errors="replace")
    if "def set_visual_amplitude_callback" not in voice_engine_src:
        raise RuntimeError("RC3.2 VoiceEngine visual amplitude facade missing")
    for marker in [
        "Live voice amplitude bridge bound: real PCM waveform enabled",
        'amplitude_binder = getattr',
    ]:
        if marker not in main_src:
            raise RuntimeError(f"RC3.2 optional live amplitude UI contract missing: {marker}")
    for marker in [
        "_float32_pcm_peak",
        "amplitude_callback=self._visual_amplitude_callback",
        "self._emit_amplitude(payload)",
    ]:
        if marker not in xtts_src:
            raise RuntimeError(f"RC3.2 XTTS live PCM amplitude contract missing: {marker}")

    microphone_src = (ROOT / "voice" / "microphone.py").read_text(encoding="utf-8", errors="replace")
    if "Microphone PortAudio device cache reinitialized" not in microphone_src:
        raise RuntimeError("RC3.1 microphone PortAudio refresh contract missing")
    if "aucun LLM local résident" not in guardian_src:
        raise RuntimeError("cloud voice resource marker missing")
    web_search_src = (ROOT / "tools" / "web_search.py").read_text(encoding="utf-8", errors="replace")
    for marker in [
        "class FreeWebSearchTool",
        '"google", "duckduckgo", "startpage", "yahoo", "mojeek"',
        "free_search_unavailable",
        "paid_fallback=False",
        "dependency_missing",
    ]:
        if marker not in web_search_src:
            raise RuntimeError(f"zero-cost Web Search contract missing: {marker}")
    manager_src = (ROOT / "tools" / "internet_manager.py").read_text(encoding="utf-8", errors="replace")
    if '"engine": "free-web-search"' not in manager_src:
        raise RuntimeError("free Web Search routing marker missing")
    if not (ROOT / "scripts" / "web_tools_status.py").is_file():
        raise RuntimeError("free Web Search readiness diagnostic missing")

    print(
        "[PASS] contracts: version/runtime/state/document/home-attachment/voice/text-integrity/zero-cost-web-search/async-voice/live-pcm-bridge"
    )


def active_tests(verbose: bool) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(ROOT), str(ROOT / "tests")] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    cmd = [sys.executable, "-m", "unittest"]
    if verbose:
        cmd.append("-v")
    cmd.extend(ACTIVE_TEST_MODULES)
    proc = subprocess.run(cmd, cwd=ROOT, env=env)
    if proc.returncode:
        raise RuntimeError(f"active regression suite failed with code {proc.returncode}")
    print(f"[PASS] active regression suite: {len(ACTIVE_TEST_MODULES)} modules")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    try:
        compile_check()
        contract_check()
        active_tests(args.verbose)
        print("[PASS] AURA v0.7.2.1 RC3.2 diagnostics complete")
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
