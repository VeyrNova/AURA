from __future__ import annotations

from pathlib import Path
import tempfile
from unittest.mock import patch
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.llm_manager import GeminiProvider, LLMProviderError
from config.settings import settings
from runtime.hybrid_runtime import (
    choose_document_route,
    choose_llm_route,
    gemini_configured,
    groq_configured,
)
from services.document_analysis import extract_document, select_document_context

checks: list[tuple[str, bool]] = []

def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

# Configuration surface.
for attr in (
    "GEMINI_ENABLED", "GEMINI_API_KEY", "GEMINI_BASE_URL", "GEMINI_UPLOAD_BASE_URL",
    "GEMINI_FAST_MODEL", "GEMINI_DOCUMENT_MODEL", "DOCUMENT_ANALYSIS_PROVIDER",
    "DOCUMENT_CLOUD_ENABLED", "DOCUMENT_GEMINI_CONTEXT_CHARS", "DOCUMENT_GROQ_CONTEXT_CHARS",
):
    check("settings_" + attr.lower(), hasattr(settings, attr))
check("gemini_default_model_stable", str(settings.GEMINI_FAST_MODEL).startswith("gemini-3."))

# Deterministic route policy without requiring real API keys.
with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
     patch.object(settings, "GROQ_ENABLED", True), \
     patch.object(settings, "GROQ_API_KEY", "gsk_test_key_abcdefghijklmnopqrstuvwxyz"), \
     patch.object(settings, "GEMINI_ENABLED", True), \
     patch.object(settings, "GEMINI_API_KEY", "AIzaSy_test_key_abcdefghijklmnopqrstuvwxyz"), \
     patch.object(settings, "DOCUMENT_CLOUD_ENABLED", True), \
     patch.object(settings, "DOCUMENT_ANALYSIS_PROVIDER", "auto"):
    check("conversation_prefers_groq", choose_llm_route("bonjour", voice_output=True).provider == "groq")
    check("document_prefers_gemini", choose_document_route("analyse le document").provider == "gemini")

with patch.object(settings, "AURA_RUNTIME_MODE", "hybrid"), \
     patch.object(settings, "GROQ_ENABLED", True), \
     patch.object(settings, "GROQ_API_KEY", "gsk_test_key_abcdefghijklmnopqrstuvwxyz"), \
     patch.object(settings, "GEMINI_ENABLED", True), \
     patch.object(settings, "GEMINI_API_KEY", ""), \
     patch.object(settings, "DOCUMENT_CLOUD_ENABLED", True), \
     patch.object(settings, "DOCUMENT_ANALYSIS_PROVIDER", "auto"):
    check("document_fallback_groq", choose_document_route("analyse le document").provider == "groq")

# Gemini provider fail-closed host + native file_data payload.
try:
    GeminiProvider("https://example.com/v1beta", settings.GEMINI_UPLOAD_BASE_URL, "test")
    check("gemini_fail_closed_host", False)
except LLMProviderError:
    check("gemini_fail_closed_host", True)

provider = GeminiProvider(settings.GEMINI_BASE_URL, settings.GEMINI_UPLOAD_BASE_URL, "test-key")
payload = provider._payload(
    [{"role": "system", "content": "Analyse précisément."}, {"role": "user", "content": "Résume."}],
    model=settings.GEMINI_DOCUMENT_MODEL, num_predict=300, temperature=.2, top_p=.9,
    file_uri="https://generativelanguage.googleapis.com/v1beta/files/test", file_mime="application/pdf",
)
parts = payload.get("contents", [{}])[-1].get("parts", [])
check("gemini_native_file_payload", any("file_data" in part for part in parts))
check("gemini_system_instruction", "systemInstruction" in payload)

# Log/document retention: recent tail and errors must survive bounding.
with tempfile.TemporaryDirectory() as td:
    p = Path(td) / "aura.log"
    p.write_text(("INFO routine\n" * 25000) + "ERROR attachment failure\nTraceback boom\nFINAL RECENT EVENT\n", encoding="utf-8")
    doc = extract_document(str(p))
    selected = select_document_context(doc, query="analyse les erreurs", max_chars=12000)
    check("document_tail_preserved", "FINAL RECENT EVENT" in doc.text)
    check("document_error_preserved", "ERROR attachment failure" in selected.text)

main = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
manager = (ROOT / "ai" / "llm_manager.py").read_text(encoding="utf-8")
guardian = (ROOT / "runtime" / "resource_guardian.py").read_text(encoding="utf-8")
service = (ROOT / "services" / "document_analysis.py").read_text(encoding="utf-8")

check("ui_document_profile", "document_request_profile(user_text=text)" in main)
check("ui_native_pdf_gemini", 'provider_name == "gemini"' in main and 'profile["attachment_path"]' in main)
check("ui_cloud_failover", 'candidates = ["gemini", "groq"]' in main)
check("ui_native_no_bad_fallback", 'and not bool(profile.get("native_document"))' in main)
check("ui_shutdown_completion_guard", 'LLM completion ignored because AURA is closing' in main)
check("ui_shutdown_cleanup_guard", 'if not self._closing:\n            self._reconcile_interaction_state("llm-thread-cleanup")' in main)
check("ui_multibrain_hud", "NEURAL LINK · MULTI" in main and "GROQ + GEMINI + LOCAL" in main)
check("gemini_provider_present", "class GeminiProvider" in manager and ":streamGenerateContent" in manager)
check("gemini_files_upload_present", "X-Goog-Upload-Protocol" in manager and "upload, finalize" in manager)
check("guardian_document_profile", "def document_request_profile" in guardian)
check("guardian_remote_gemini", '{"groq", "gemini"}' in guardian)
check("scanned_pdf_native_support", "native_required=True" in service)
check("research_route_preserved", "Explicit research route=ai-search-engine" in main)
check("native_icons_preserved", (ROOT / "ui" / "action_icons.py").is_file())
check("gemini_configurator_present", (ROOT / "scripts" / "configure_gemini.py").is_file())

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print()
print(f"Groq configured on this installation: {groq_configured()}")
print(f"Gemini configured on this installation: {gemini_configured()}")
print(f"Patch 26.8.3 diagnostics: {len(checks) - len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
