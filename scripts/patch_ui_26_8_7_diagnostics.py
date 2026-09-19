from pathlib import Path
import sys

root=Path(__file__).resolve().parents[1]
checks = [
    ("HOME attachment origin", 'origin="home"', root/"ui"/"main_window.py"),
    ("Conversation attachment origin", 'origin="conversation"', root/"ui"/"main_window.py"),
    ("HOME no auto popup marker", "Document attachment retained on Home; conversation popup unchanged", root/"ui"/"main_window.py"),
    ("Document Fast Lane preserved", "Document FAST lane dispatched", root/"ui"/"main_window.py"),
    ("Gemini remote routing preserved", 'in {"groq", "gemini"}', root/"runtime"/"resource_guardian.py"),
    ("Voice Identity Lock", "voice_identity_lock=True", root/"runtime"/"resource_guardian.py"),
    ("Emergency fallback", "voice_identity_emergency=True", root/"runtime"/"resource_guardian.py"),
]
fail=0
for name, marker, path in checks:
    text=path.read_text(encoding="utf-8")
    ok=marker in text
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
    fail += 0 if ok else 1
print(f"\nDiagnostic Patch 26.8.7: {len(checks)-fail}/{len(checks)} PASS")
raise SystemExit(1 if fail else 0)
