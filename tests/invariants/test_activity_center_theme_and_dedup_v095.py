from __future__ import annotations
import hashlib, os, re, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from core.version import AURA_VERSION
UI_ROOT = Path(os.environ.get("LOCALAPPDATA", "")) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
p081 = [ROOT / "aura-p081-event-watchers.js", UI_ROOT / "src" / "aura-p081-event-watchers.js", UI_ROOT / "src" / "assets" / "aura-p081-event-watchers.js", UI_ROOT / "dist" / "assets" / "aura-p081-event-watchers.js"]
rail = UI_ROOT / "src" / "aura-p0702-left-rail.js"
css = UI_ROOT / "src" / "aura-p0702-left-rail.css"
def function_body(source, name):
    m=re.search(r"function\s+" + re.escape(name) + r"\s*\(\)\s*\{", source); assert m, name
    start=m.start(); pos=m.end(); depth=1
    while pos < len(source):
        ch=source[pos]
        if ch == "{": depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0: return source[start:pos+1]
        pos += 1
    raise AssertionError("unclosed function " + name)
assert AURA_VERSION == "0.9.4"
assert hashlib.sha256(rail.read_bytes()).hexdigest() == "c9cc3a363344d7148cf2ad85deda5a9c779aca223f17d2c5f27cbfb7e5ba9b02"
assert hashlib.sha256(css.read_bytes()).hexdigest() == "2162fb9b4f39cd1b0113e2cd06d949fc19bff360251143ef438a37f3b44be4d5"
for path in p081:
    assert path.is_file()
    text=path.read_text(encoding="utf-8-sig", errors="replace")
    fn=function_body(text, "ensureEntry")
    assert 'data-module="notifications"' in fn
    assert 'data-module="activity-center"' in fn
    assert 'legacy.remove()' in fn
    assert 'document.createElement' not in fn
    assert '// --- AURA V0.9.5 D2 R5 ACTIVITY CENTER THEME START ---' in text
    assert '// --- AURA V0.9.5 D2 R5 ACTIVITY CENTER THEME END ---' in text
    assert 'data-aura-p095-activity-center-theme' in text
print("[PASS] AURA v0.9.5 Activity Center theme + dedup invariant")
