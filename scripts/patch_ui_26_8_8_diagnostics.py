from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
rendering = root / "ui" / "text_rendering.py"
panel = root / "ui" / "holographic_results_panel.py"
chat = root / "ui" / "chat_panel.py"

checks = [
    ("Central Markdown normalizer", "def normalize_markdown_text", rendering),
    ("Math sanitizer", "def normalize_markdown_math", rendering),
    ("Gemini arrow conversion", "\\rightarrow", rendering),
    ("Balanced inline math cleanup", "(?<!\\\\)\\$", rendering),
    ("Visual Result uses sanitizer", "normalize_markdown_text", panel),
    ("Visual Result Markdown renderer", "self.body.setMarkdown(clean_text)", panel),
    ("Conversation cards use sanitizer", "normalize_markdown_text", chat),
]

fail = 0
for name, marker, path in checks:
    text = path.read_text(encoding="utf-8")
    ok = marker in text
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
    fail += 0 if ok else 1

print(f"\nDiagnostic Patch 26.8.8: {len(checks)-fail}/{len(checks)} PASS")
raise SystemExit(1 if fail else 0)
