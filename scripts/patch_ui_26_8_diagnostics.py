from __future__ import annotations

from pathlib import Path
import tempfile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import settings
from runtime.hybrid_runtime import choose_llm_route, groq_configured, use_groq_stt
from services.document_analysis import extract_document, inject_document_context

checks: list[tuple[str, bool]] = []

def check(name: str, ok: bool) -> None:
    checks.append((name, bool(ok)))

main = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
chat = (ROOT / "ui/chat_panel.py").read_text(encoding="utf-8")
home = (ROOT / "ui/final_modules.py").read_text(encoding="utf-8")
icons = (ROOT / "ui/action_icons.py").read_text(encoding="utf-8")
service = (ROOT / "services/document_analysis.py").read_text(encoding="utf-8")

# Visual/icon contract
check("native_vector_icon_module", "QPainter vectors instead of emoji/font glyphs" in icons)
check("legacy_emoji_icon_router_removed", "COMPOSER_ACTION_GLYPHS" not in main)
check("chat_attachment_icon", 'apply_action_icon(self.attach_button, "attach"' in chat)
check("chat_microphone_icon", 'apply_action_icon(self.mic_button, "microphone"' in chat)
check("chat_send_icon", 'apply_action_icon(self.send_button, "send"' in chat)
check("home_attachment_icon", 'self.attach_button.setObjectName("homeAttachButton")' in home)
check("home_microphone_icon", 'self.mic_button.setObjectName("homeMicButton")' in home)
check("home_send_icon", 'self.send_button.setObjectName("homeSendButton")' in home)

# Functional attachment contract
check("attachment_signal_chat", "attachment_requested = Signal()" in chat)
check("attachment_picker_connected", "QFileDialog.getOpenFileName" in main)
check("document_worker_present", "class DocumentLoadWorker(QObject):" in main)
check("document_extractor_present", "def extract_document(" in service)
check("pdf_support_present", 'ext == ".pdf"' in service)
check("docx_support_present", 'ext == ".docx"' in service)
check("xlsx_support_present", 'ext == ".xlsx"' in service)
check("document_context_injected", "inject_document_context(messages, document_context, query=text)" in main)
check("document_context_has_clear", "def _clear_document_attachment(self)" in main)
check("explicit_web_search_still_preempts_doc", "self._active_document_context is not None and not is_explicit_search_request(text)" in main)

# Voice recovery contract
check("home_microphone_status_wired", "self.home_composer.set_microphone_available(status.input_ready)" in main)
check("voice_local_retry_present", "Voice-safe local fallback: releasing XTTS temporarily" in main)
check("voice_local_retry_unprotects_xtts", 'retry_profile["preserve_xtts_for_voice"] = False' in main)
check("voice_local_retry_releases_xtts", "self.aura_core.voice_engine.release_xtts_model()" in main)

# Groq contract: validate the route without making a network request or printing a secret.
old_mode = settings.AURA_RUNTIME_MODE
old_enabled = settings.GROQ_ENABLED
old_key = settings.GROQ_API_KEY
old_stt = settings.GROQ_STT_ENABLED
try:
    settings.AURA_RUNTIME_MODE = "hybrid"
    settings.GROQ_ENABLED = True
    settings.GROQ_API_KEY = "gsk_patch268_diagnostic_key_1234567890"
    settings.GROQ_STT_ENABLED = True
    route = choose_llm_route("Bonjour Aura", voice_output=True)
    check("groq_hybrid_route_available", route.provider == "groq" and route.remote)
    check("groq_stt_route_available", use_groq_stt())
finally:
    settings.AURA_RUNTIME_MODE = old_mode
    settings.GROQ_ENABLED = old_enabled
    settings.GROQ_API_KEY = old_key
    settings.GROQ_STT_ENABLED = old_stt

check("groq_hud_state_present", "NEURAL LINK · GROQ" in main)
check("groq_setup_script_present", (ROOT / "scripts/configure_groq.py").is_file())

# Real extraction + prompt injection smoke test (no Qt needed).
try:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "diagnostic.txt"
        path.write_text("AURA diagnostic document : pompe P-17 = opérationnelle.", encoding="utf-8")
        document = extract_document(str(path))
        enriched = inject_document_context(
            [{"role": "system", "content": "base"}, {"role": "user", "content": "État de P-17 ?"}],
            document,
            query="P-17",
        )
        check("document_smoke_extract", "P-17" in document.text)
        check("document_smoke_inject", "P-17" in enriched[-2]["content"] and enriched[-1]["role"] == "user")
except Exception:
    check("document_smoke_extract", False)
    check("document_smoke_inject", False)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nPatch 26.8 diagnostics: {len(checks) - len(failed)}/{len(checks)} PASS")
print(f"Groq configured on this installation: {groq_configured()}")
if not groq_configured():
    print("INFO: launch CONFIGURE_GROQ.bat if you want the hybrid Groq route.")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
