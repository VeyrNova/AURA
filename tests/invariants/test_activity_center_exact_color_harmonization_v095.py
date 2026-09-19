from pathlib import Path
import os,sys,hashlib
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from core.version import AURA_VERSION
UI=Path(os.environ.get("LOCALAPPDATA",""))/"AURA"/"ui"/"v0.7.2.2-rc4.2"
paths=[ROOT/"aura-p081-event-watchers.js",UI/"src"/"aura-p081-event-watchers.js",UI/"src"/"assets"/"aura-p081-event-watchers.js",UI/"dist"/"assets"/"aura-p081-event-watchers.js"]
assert AURA_VERSION=="0.9.4"
for p in paths:
 s=p.read_text(encoding="utf-8-sig",errors="replace")
 for t in ["AURA V0.9.5 D2 R6 EXACT NAVY CYAN ACTIVITY CENTER","aura-p095-activity-center-exact-theme","#020914","#04111f","#061827","#55dcff","#94ebff",'data-module="notifications"',"legacy.remove()"]: assert t in s,t
print("[PASS] Activity Center exact navy/cyan harmonization")
