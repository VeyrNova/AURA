from __future__ import annotations
import ast, asyncio, inspect, os, threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
UI = Path(os.environ["LOCALAPPDATA"]) / "AURA" / "ui" / "v0.7.2.2-rc4.2"
SHELL = UI / "tools" / "shell_host.py"

text = SHELL.read_text(encoding="utf-8-sig", errors="replace")
ast.parse(text)

assert text.count("AURA_V123_REAL_HOST_WEB_BRIDGE_BEGIN") == 1
assert text.count("AURA_V123_REAL_HOST_WEB_BRIDGE_END") == 1
assert text.count("AURA_V123_AWAITABLE_HUB_COMPLETION_BEGIN") == 1
assert text.count("AURA_V123_AWAITABLE_HUB_COMPLETION_END") == 1
assert "inspect.isawaitable" in text
assert "asyncio.run_coroutine_threadsafe" in text
assert "rt.hub.send('personal_result', data)" in text
assert "_aura_v123_complete_hub_send(rt, result)" in text
assert text.count("AURA_V123_ESCAPE_WATCHDOG_BEGIN") == 1
assert "--start-fullscreen" in text

def complete(rt, result):
    if not inspect.isawaitable(result):
        return True

    loops = []
    for owner in (rt, getattr(rt, "hub", None)):
        if owner is None:
            continue
        for name in ("loop", "_loop", "event_loop", "_event_loop"):
            candidate = getattr(owner, name, None)
            if candidate is not None and candidate not in loops:
                loops.append(candidate)

    for loop in loops:
        try:
            if loop.is_running():
                fut = asyncio.run_coroutine_threadsafe(result, loop)
                fut.result(timeout=3.0)
                return True
        except Exception:
            continue

    try:
        asyncio.run(result)
        return True
    except Exception:
        return False

class AsyncHub:
    def __init__(self, loop):
        self.loop = loop
        self.received = []
    async def send(self, kind, data):
        self.received.append((kind, data))
        await asyncio.sleep(0)

class RT:
    pass

loop = asyncio.new_event_loop()
ready = threading.Event()

def run_loop():
    asyncio.set_event_loop(loop)
    ready.set()
    loop.run_forever()

thread = threading.Thread(target=run_loop, daemon=True)
thread.start()
assert ready.wait(2)

try:
    rt = RT()
    rt.hub = AsyncHub(loop)
    result = rt.hub.send("personal_result", {"kind":"mail","count":1,"items":[]})
    assert complete(rt, result)
    assert rt.hub.received and rt.hub.received[0][0] == "personal_result"
finally:
    loop.call_soon_threadsafe(loop.stop)
    thread.join(timeout=2)
    loop.close()

print("[PASS] v1.2.3 awaitable hub completion compatibility invariant")
