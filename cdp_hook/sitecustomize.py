# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

PORT = str(os.environ.get("AURA_P08547615_CDP_PORT", "")).strip()
TRACE = str(os.environ.get("AURA_P08547615_BROWSER_TRACE", "")).strip()
_ORIGINAL_POPEN = subprocess.Popen

def _log(payload):
    if not TRACE:
        return
    try:
        p = Path(TRACE)
        p.parent.mkdir(parents=True, exist_ok=True)
        row = {"ts": time.time(), "pid": os.getpid(), **payload}
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    except Exception:
        pass

class AuraCertPopen(_ORIGINAL_POPEN):
    def __init__(self, args, *a, **kw):
        patched = args
        try:
            seq = list(args) if isinstance(args, (list, tuple)) else None
            if seq:
                exe = str(seq[0]).lower()
                browser = "chrome.exe" in exe or "msedge.exe" in exe or exe.endswith("/chrome") or exe.endswith("/msedge")
                app_arg = any(str(x).startswith("--app=http://127.0.0.1:") for x in seq[1:])
                if browser and app_arg and PORT:
                    if not any(str(x).startswith("--remote-debugging-port=") for x in seq):
                        seq.append(f"--remote-debugging-port={PORT}")
                    if not any(str(x).startswith("--remote-allow-origins=") for x in seq):
                        seq.append("--remote-allow-origins=*")
                    patched = seq
                    _log({"event": "browser_debug_enabled", "args": [str(x) for x in seq]})
        except Exception as exc:
            _log({"event": "hook_error", "error": f"{type(exc).__name__}: {exc}"})
        super().__init__(patched, *a, **kw)

subprocess.Popen = AuraCertPopen
_log({"event": "sitecustomize_loaded", "port": PORT})
