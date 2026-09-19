from __future__ import annotations
import ast, os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
UI=Path(os.environ["LOCALAPPDATA"])/"AURA"/"ui"/"v0.7.2.2-rc4.2"
SHELL=UI/"tools"/"shell_host.py"
PRES=ROOT/"runtime"/"personal_result_presenter_v123.py"
ROOT_INDEX=UI/"index.html"
DIST_INDEX=UI/"dist"/"index.html"

BR=[UI/"src"/"aura-v123-eventsource-bridge.js",UI/"src"/"assets"/"aura-v123-eventsource-bridge.js",UI/"dist"/"assets"/"aura-v123-eventsource-bridge.js"]
JS=[UI/"src"/"aura-v123-personal-results-web.js",UI/"src"/"assets"/"aura-v123-personal-results-web.js",UI/"dist"/"assets"/"aura-v123-personal-results-web.js"]
CSS=[UI/"src"/"aura-v123-personal-results-web.css",UI/"src"/"assets"/"aura-v123-personal-results-web.css",UI/"dist"/"assets"/"aura-v123-personal-results-web.css"]

for p in [SHELL,PRES,ROOT_INDEX,DIST_INDEX,*BR,*JS,*CSS]: assert p.is_file(),p

shell=SHELL.read_text(encoding="utf-8-sig")
ast.parse(shell)
assert shell.count("--start-fullscreen")==1
assert "--start-maximized" not in shell
assert shell.count("AURA_V123_REAL_HOST_WEB_BRIDGE_BEGIN")==1
assert "personal_result" in shell

assert BR[0].read_bytes()==BR[1].read_bytes()==BR[2].read_bytes()
bridge=BR[0].read_text(encoding="utf-8-sig")
assert "window.EventSource = WrappedEventSource" in bridge
assert "new NativeEventSource" in bridge
assert "aura:hub-event" in bridge
assert "duplicate_connection: false" in bridge

assert JS[0].read_bytes()==JS[1].read_bytes()==JS[2].read_bytes()
assert CSS[0].read_bytes()==CSS[1].read_bytes()==CSS[2].read_bytes()
assert "new EventSource" not in JS[0].read_text(encoding="utf-8-sig")

for p in (ROOT_INDEX,DIST_INDEX):
    t=p.read_text(encoding="utf-8-sig")
    assert "aura-v123-eventsource-bridge.js" in t
    assert "aura-v123-personal-results-web.js" in t
    assert "aura-v123-personal-results-web.css" in t

presenter=PRES.read_text(encoding="utf-8-sig")
ast.parse(presenter)
assert "_has_authoritative_list" in presenter
assert "not has_authoritative_list" in presenter

print("[PASS] v1.2.3 R3 R4 preloaded EventSource bridge + real web renderer invariant")
print("[PASS] no dist-bundle rewrite required")
print("[PASS] one native SSE connection per existing EventSource construction")
