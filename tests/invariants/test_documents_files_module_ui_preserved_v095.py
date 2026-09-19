from __future__ import annotations

import hashlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION

UI_RELEASE = "0.7.2.2-rc4.2"
UI_ROOT = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "AURA"
    / "ui"
    / ("v" + UI_RELEASE)
)

rail_js = [
    UI_ROOT / "src" / "aura-p0702-left-rail.js",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.js",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.js",
]

rail_css = [
    UI_ROOT / "src" / "aura-p0702-left-rail.css",
    UI_ROOT / "src" / "assets" / "aura-p0702-left-rail.css",
    UI_ROOT / "dist" / "assets" / "aura-p0702-left-rail.css",
]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def count_cards(source, module_id):
    return len(
        re.findall(
            r"<button\b[^>]*\bdata-module=['\"]"
            + re.escape(module_id)
            + r"['\"][^>]*>",
            source,
            flags=re.I,
        )
    )

def function_body(source, name):
    match = re.search(
        r"function\s+"
        + re.escape(name)
        + r"\s*\(\)\s*\{",
        source,
    )
    assert match, name

    start = match.start()
    pos = match.end()
    depth = 1

    while pos < len(source):
        char = source[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:pos + 1]
        pos += 1

    raise AssertionError("unclosed function " + name)

assert AURA_VERSION == '0.9.5', AURA_VERSION
assert all(path.is_file() for path in rail_js)
assert all(path.is_file() for path in rail_css)
assert {sha(path) for path in rail_js} == {"c9cc3a363344d7148cf2ad85deda5a9c779aca223f17d2c5f27cbfb7e5ba9b02"}
assert {sha(path) for path in rail_css} == {"2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"}

text = rail_js[0].read_text(
    encoding="utf-8-sig",
    errors="replace",
)

assert text.count("AURA V0.9.4 D2 R7 DOCUMENTS FILES VISUAL REBUILD") == 1
assert count_cards(text, "system") == 0
assert count_cards(text, "mail") == 1
assert count_cards(text, "agenda") == 1
assert count_cards(text, "contacts") == 1
assert count_cards(text, "documents") == 1

assert "Gerer, rechercher ou joindre un fichier" in text
assert "Joindre et analyser un fichier" not in text

open_documents = function_body(
    text,
    "openDocuments",
)

assert "manager()?.open?.('talk')" in open_documents
assert "composerInput()" in open_documents
assert "if(!String(input.value||'').trim())" in open_documents
assert "input.value='liste mes fichiers'" in open_documents
assert "attach.click()" not in open_documents
assert ".click()" not in open_documents
assert "send" not in open_documents.lower()

print("[PASS] AURA v0.9.4 DOCUMENTS Files UI invariant")
print("[PASS] guarded Conversation prefill")
print("[PASS] no auto-submit and non-empty draft preserved")
print("[PASS] SYSTEM LIVE remains de-duplicated")
