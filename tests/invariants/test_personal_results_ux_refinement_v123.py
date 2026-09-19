from __future__ import annotations
import os
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
UI=Path(os.environ["LOCALAPPDATA"])/"AURA"/"ui"/"v0.7.2.2-rc4.2"

js_files=[
    UI/"src"/"aura-v123-personal-results-web.js",
    UI/"src"/"assets"/"aura-v123-personal-results-web.js",
    UI/"dist"/"assets"/"aura-v123-personal-results-web.js",
]
css_files=[
    UI/"src"/"aura-v123-personal-results-web.css",
    UI/"src"/"assets"/"aura-v123-personal-results-web.css",
    UI/"dist"/"assets"/"aura-v123-personal-results-web.css",
]

for p in js_files+css_files:
    assert p.is_file(), p

js=[p.read_text(encoding="utf-8-sig") for p in js_files]
css=[p.read_text(encoding="utf-8-sig") for p in css_files]

assert len(set(js))==1
assert len(set(css))==1

j=js[0]
c=css[0]

assert "version: '1.2.3-ft5-ux1'" in j
assert "sender:'Expéditeur'" in j
assert "function senderValue(item)" in j
assert "Expéditeur non renseigné" in j
assert "item&&item.from_address" in j
assert "item&&item.sender_email" in j
assert "JSON.stringify(v)" not in j
assert "internalFields" in j

assert "width:clamp(430px,34vw,620px)" in c
assert "rgba(8,22,38,.985)" in c
assert "rgba(3,10,19,.99)" in c
assert "rgba(3,14,23,.82)" in c
assert "rgba(113,224,255,.32)" in c
assert "rgba(105,232,255,.34)" in c
assert "white-space:pre-line" in c
assert "@media(max-width:760px)" in c

print("[PASS] v1.2.3 FT5 personal-results UX refinement invariant")
