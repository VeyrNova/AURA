from __future__ import annotations

import ctypes
import os
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).expanduser().resolve(strict=False)
LOG_ROOT = ROOT / "logs" / "product_launcher"

PY = ROOT / "venv" / "Scripts" / "python.exe"
PYW = ROOT / "venv" / "Scripts" / "pythonw.exe"

LIFECYCLE = ROOT / "runtime" / "aura_ui_host_lifecycle_v200.py"
TRANSPORT = ROOT / "runtime" / "aura_ui_host_transport_v200.py"
INTENT = ROOT / "runtime" / "aura_conversation_intent_handoff_v200.py"
FABRIC = ROOT / "launch_aura_fabric_gateway.py"
UI_LAUNCHER = ROOT / "launch_aura_ui_v0722_rc42.py"

def port_open(port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False

def wait_port(port: int, seconds: float) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(0.20)
    return port_open(port)

def message(text: str, title: str = "AURA v2") -> None:
    try:
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x10)
    except Exception:
        pass

def write_boot_log(text: str) -> None:
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    with (LOG_ROOT / "bootstrap.log").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')} {text}\n")

def hidden_creationflags() -> int:
    return (
        getattr(subprocess, "CREATE_NO_WINDOW", 0)
        | getattr(subprocess, "DETACHED_PROCESS", 0)
    )

def start_hidden(script: Path, log_name: str, args: list[str] | None = None):
    if not script.is_file():
        return None

    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["AURA_ROOT"] = str(ROOT)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")

    exe = PYW if PYW.is_file() else PY
    cmd = [str(exe), str(script)] + list(args or [])

    stream = (LOG_ROOT / log_name).open("ab", buffering=0)
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(ROOT),
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            creationflags=hidden_creationflags(),
            close_fds=True,
        )
    except Exception:
        stream.close()
        raise
    return proc

def self_check() -> int:
    required = [PY, LIFECYCLE, TRANSPORT, INTENT, UI_LAUNCHER]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        print("MISSING:")
        for item in missing:
            print(item)
        return 2
    print("AURA_PRODUCT_BOOTSTRAP_SELF_CHECK=PASS")
    print(f"pythonw={PYW.is_file()}")
    return 0

def main() -> int:
    if "--self-check" in sys.argv:
        return self_check()

    if not PY.is_file():
        message("Python AURA introuvable.")
        return 10

    try:
        if not port_open(18765):
            write_boot_log("starting A200 lifecycle hidden")
            start_hidden(LIFECYCLE, "a200_lifecycle.log")
            if not wait_port(18765, 12):
                message(
                    "Le runtime A200 n'a pas pu démarrer.\n"
                    "Consultez logs\\product_launcher\\a200_lifecycle.log"
                )
                return 20
        else:
            write_boot_log("A200 lifecycle already reachable")

        if not port_open(18766):
            write_boot_log("starting intent preview hidden")
            start_hidden(INTENT, "intent_preview.log")
            wait_port(18766, 5)
        else:
            write_boot_log("intent preview already reachable")

        if FABRIC.is_file():
            try:
                write_boot_log("starting developer fabric hidden (best effort)")
                start_hidden(FABRIC, "developer_fabric.log")
            except Exception as exc:
                write_boot_log("developer fabric start error: " + repr(exc))

        write_boot_log("starting AURA UI launcher hidden")
        p = start_hidden(UI_LAUNCHER, "ui_launcher.log")
        if p is None:
            message("Le launcher UI AURA est introuvable.")
            return 30

        return 0

    except Exception as exc:
        write_boot_log("fatal bootstrap error: " + repr(exc))
        message(
            "AURA n'a pas pu démarrer.\n"
            "Consultez logs\\product_launcher\\bootstrap.log"
        )
        return 99

if __name__ == "__main__":
    raise SystemExit(main())
