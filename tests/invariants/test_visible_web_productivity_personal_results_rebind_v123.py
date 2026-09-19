from pathlib import Path
import hashlib, os
ROOT=Path(__file__).resolve().parents[2]
UI=Path(os.environ["LOCALAPPDATA"])/"AURA"/"ui"/"v0.7.2.2-rc4.2"
rail=[UI/"src"/"aura-p0702-left-rail.js",UI/"src"/"assets"/"aura-p0702-left-rail.js",UI/"dist"/"assets"/"aura-p0702-left-rail.js"]
prod=[UI/"src"/"aura-p0623-file-productivity.js",UI/"dist"/"assets"/"aura-p0623-file-productivity.js"]
js=[UI/"src"/"aura-v123-visible-productivity-rebind.js",UI/"src"/"assets"/"aura-v123-visible-productivity-rebind.js",UI/"dist"/"assets"/"aura-v123-visible-productivity-rebind.js"]
css=[UI/"src"/"aura-v123-visible-productivity-rebind.css",UI/"src"/"assets"/"aura-v123-visible-productivity-rebind.css",UI/"dist"/"assets"/"aura-v123-visible-productivity-rebind.css"]
bridge=[UI/"src"/"aura-v123-eventsource-bridge.js",UI/"src"/"assets"/"aura-v123-eventsource-bridge.js",UI/"dist"/"assets"/"aura-v123-eventsource-bridge.js"]
renderer=[UI/"src"/"aura-v123-personal-results-web.js",UI/"src"/"assets"/"aura-v123-personal-results-web.js",UI/"dist"/"assets"/"aura-v123-personal-results-web.js"]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
assert len(set(sha(p) for p in rail))==1
assert len(set(sha(p) for p in js))==1
assert len(set(sha(p) for p in css))==1
assert all(sha(p)=="4dd82de83bacbedc61c99ba39b9e230a402bddd55b24a4e6a03a121cd2885d58" for p in prod)
assert len(prod)==2
assert not (UI/"src"/"assets"/"aura-p0623-file-productivity.js").exists()
assert all(sha(p)=="90ba33ad359aec4a00f6cec882ed533d1c4c7c0bd1f0e8dcd68ceded1c1b8a57" for p in bridge)
assert all(sha(p)=="025d83640b86da69ab1483b6557f3d759f9a9fec6eef330494cf7ccb95637320" for p in renderer)
r=rail[0].read_text(encoding="utf-8-sig")
assert 'data-tab="calendar"' in r
assert '.aura-p0623-drawer [data-tab="calendar"]' in r
j=js[0].read_text(encoding="utf-8-sig")
assert "JSON.stringify({action,...payload})" in j
assert "JSON.stringify({action,payload})" not in j
for token in ("AURA_V123_VISIBLE_WEB_PRODUCTIVITY_REBIND","AURA_V123_NATIVE_TASKS_GOOGLE_SECTION","AURA_V123_NATIVE_CALENDAR_MONTH_GRID","ACTUALISER TOUT","aura:hub-event","send_message",'data-tab="calendar"'): assert token in j
c=css[0].read_text(encoding="utf-8-sig")
assert "aura-v123-cal-grid" in c and "grid-template-columns:repeat(7" in c
di=(UI/"dist"/"index.html").read_text(encoding="utf-8-sig")
assert di.index("aura-v123-eventsource-bridge.js") < di.index("index-Ckl5rwwJ.js")
assert di.index("aura-v123-personal-results-web.js") < di.index("index-Ckl5rwwJ.js")
assert "aura-v123-visible-productivity-rebind.js" in di
ri=(UI/"index.html").read_text(encoding="utf-8-sig")
assert ri.index("aura-v123-eventsource-bridge.js") < ri.index("main.js")
print("[PASS] visible web Tasks = AURA local + Google section")
print("[PASS] visible web Agenda = real month calendar AURA + Google")
print("[PASS] ACTUALISER TOUT + native refresh bridge")
print("[PASS] Personal Results bridge preloads before dist EventSource owner")
