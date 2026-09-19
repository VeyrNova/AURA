from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
manager = (ROOT / "ai" / "llm_manager.py").read_text(encoding="utf-8")
ui = (ROOT / "ui" / "main_window.py").read_text(encoding="utf-8")
checks = []

def check(name, ok):
    checks.append((name, bool(ok)))

check("gemini_thinking_level_payload", '"thinkingConfig"' in manager and '"thinkingLevel"' in manager)
check("gemini3_default_sampling_preserved", 'effective_model.startswith("gemini-3")' in manager and 'generation_config["temperature"]' in manager)
check("thought_tokens_logged", 'thoughtsTokenCount' in manager and 'Gemini usage thoughts=' in manager)
check("max_tokens_short_answer_guard", 'Gemini document short MAX_TOKENS recovery' in manager)
check("retry_uses_minimal_thinking", 'retry_generation["thinkingConfig"] = {"thinkingLevel": "minimal"}' in manager)
check("document_stream_buffered", 'protected_document_stream' in manager and 'buffered_chunks' in manager)
check("worker_forwards_thinking_level", 'stream_kwargs["thinking_level"]' in ui)
check("document_budget_4096", 'DOCUMENT_GEMINI_OUTPUT_TOKENS", 4096' in ui)
check("document_thinking_low", 'DOCUMENT_GEMINI_THINKING_LEVEL", "low"' in ui)
check("fast_lane_preserved", 'Document FAST lane dispatched provider=%s' in ui)

failed = [name for name, ok in checks if not ok]
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
print(f"\nPatch 26.8.5 diagnostics: {len(checks)-len(failed)}/{len(checks)} PASS")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
