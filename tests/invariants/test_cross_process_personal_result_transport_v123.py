from __future__ import annotations
import ast, os, subprocess, sys, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
CORE = ROOT / "core" / "aura_core.py"
IPC = ROOT / "runtime" / "personal_result_ipc_v123.py"
SHELL = UI / "tools" / "shell_host.py"
SRC = UI / "src" / "main.js"
DIST = UI / "dist" / "assets" / "index-Ckl5rwwJ.js"
RENDERER = UI / "dist" / "assets" / "aura-v123-personal-results-web.js"
for p in (CORE,IPC,SHELL,SRC,DIST,RENDERER): assert p.is_file(), p
core=CORE.read_text(encoding="utf-8-sig"); ipc=IPC.read_text(encoding="utf-8-sig"); shell=SHELL.read_text(encoding="utf-8-sig"); renderer=RENDERER.read_text(encoding="utf-8-sig")
ast.parse(core); ast.parse(ipc); ast.parse(shell)
assert core.count("AURA_V123_DIRECT_WEB_RESULT_SINK_BEGIN")==1
assert "publish_personal_result_ipc_v123" in core and "if not _aura_v123_local_delivered" in core
assert "start_personal_result_ipc_server_v123" in shell
assert "rt.hub.send('personal_result'" in shell or 'rt.hub.send("personal_result"' in shell
assert shell.count("AURA_V123_ESCAPE_WATCHDOG_BEGIN")==1
assert SRC.read_text(encoding="utf-8-sig").count("new EventSource")==1
assert DIST.read_text(encoding="utf-8-sig").count("new EventSource")==1
assert "aura:hub-event" in renderer and "personal_result" in renderer

from runtime.personal_result_ipc_v123 import start_personal_result_ipc_server_v123, stop_personal_result_ipc_server_v123
received=[]; ev=threading.Event()
def cb(payload):
    received.append(dict(payload)); ev.set()
start_personal_result_ipc_server_v123(cb)
try:
    code=("from runtime.personal_result_ipc_v123 import publish_personal_result_ipc_v123;"
          "import sys;"
          "sys.exit(0 if publish_personal_result_ipc_v123({'kind':'mail','count':1,'items':[{'subject':'synthetic'}]}) else 3)")
    cp=subprocess.run([sys.executable,"-c",code],cwd=str(ROOT),stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=15)
    assert cp.returncode==0, cp.stdout
    assert ev.wait(3.0)
    assert received and received[0].get("kind")=="mail"
finally:
    stop_personal_result_ipc_server_v123()
print("[PASS] cross-process personal_result IPC")
