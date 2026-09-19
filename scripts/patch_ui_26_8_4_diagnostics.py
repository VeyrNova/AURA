from __future__ import annotations
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / 'ui' / 'main_window.py').read_text(encoding='utf-8')
core = (ROOT / 'core' / 'aura_core.py').read_text(encoding='utf-8') if (ROOT / 'core' / 'aura_core.py').exists() else ''
checks = [
 ('document_fast_lane', 'def _start_document_analysis_fast_lane' in main),
 ('fast_lane_preempts_generic', 'Document analysis route=fast-lane' in main),
 ('gemini_native_pdf', 'profile["attachment_path"] = document_context.path' in main),
 ('minimal_document_prompt', 'Minimal prompt: no memory history and no previous long chat' in main),
 ('remote_skips_local_guardian', 'if provider_name == "local":' in main and 'self.aura_core.prepare_for_llm(profile=profile)' in main),
 ('bounded_context_selection', 'select_document_context(document_context, query=text, max_chars=max_chars)' in main),
 ('old_core_document_compat', 'def _document_request_profile_compat' in main),
 ('adaptive_compat_guard', 'adaptive_dialogue_context unavailable; compatibility mode active' in main),
 ('closing_guard_preserved', 'LLM completion ignored because AURA is closing' in main),
 ('document_service_present', (ROOT / 'services' / 'document_analysis.py').is_file()),
]
# Informational, not fatal: 26.8.4 installer attempts to restore the pre-26.8.3
# AuraCore from the automatic 26.8.3 backup.
adaptive = ('adaptive_dialogue_context' in core and 'adaptive_learning' in core)
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"[INFO] adaptive_core_restored={adaptive}")
failed=[n for n,o in checks if not o]
print(f"\nPatch 26.8.4 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit('FAILED: '+', '.join(failed))
