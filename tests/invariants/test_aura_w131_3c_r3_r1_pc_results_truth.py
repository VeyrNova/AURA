from __future__ import annotations
import hashlib, sys, tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from integrations.pc_control import PcControlWindowsProvider
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123, summarize_personal_result_for_tts_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action).startswith("pc.") else "DENY"

class FakeBackend:
    def __init__(self):
        self.windows = [
            WindowSnapshot(hwnd=7001,pid=8001,title="W131 Notepad Test",visible=True,foreground=True),
            WindowSnapshot(hwnd=7002,pid=8002,title="W131 Browser Test",visible=True,foreground=False),
        ]
    def discover_windows(self, limit=256): return list(self.windows)
    def discover_processes(self, limit=512):
        return [ProcessSnapshot(8001,"notepad.exe",100), ProcessSnapshot(8002,"msedge.exe",100)]
    def foreground_window(self): return self.windows[0]
    def focus_window(self, hwnd): return int(hwnd) in {7001,7002}
    def minimize_window(self, hwnd): return int(hwnd) in {7001,7002}
    def maximize_window(self, hwnd): return int(hwnd) in {7001,7002}

roadmap_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_w131_r3_") as td:
    receipts = ActionReceiptService(store=ActionReceiptStore(Path(td)/"receipts.sqlite3"))
    registry = IntegrationRegistry(security_engine=Security(), receipt_service=receipts)
    registry.register_provider(PcControlWindowsProvider(backend=FakeBackend()))
    context = IntegrationRuntimeContext(
        registry=registry, receipt_service=receipts,
        email_backend=None, calendar_backend=None, timezone_name="Europe/Paris"
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    reply = dispatcher.handle_text("liste les fenetres Windows")
    request = getattr(dispatcher, "_last_request", None)
    assert request is not None
    assert request.provider_id == "pc-control.windows"
    assert request.capability_id == "pc.discover_windows"
    payload = build_personal_result_payload_v123(reply, request)
    assert payload["w131_pc_control"] is True
    assert payload["source"] == "WINDOWS"
    assert payload["sources"] == ["WINDOWS"]
    assert payload["count"] == 2
    assert payload["items"][0]["source"] == "WINDOWS"
    assert payload["items"][0]["title"] == "W131 Notepad Test"
    summary = summarize_personal_result_for_tts_v123(payload, reply.text).casefold()
    assert "fenetre" in summary and "mail" not in summary and "google" not in summary

    reply = dispatcher.handle_text("liste les processus")
    request = getattr(dispatcher, "_last_request", None)
    assert request.capability_id == "pc.discover_processes"
    payload = build_personal_result_payload_v123(reply, request)
    assert payload["source"] == "WINDOWS" and payload["count"] == 2

    reply = dispatcher.handle_text("quelle est la fenetre active")
    request = getattr(dispatcher, "_last_request", None)
    assert request.capability_id == "pc.get_foreground_window"
    payload = build_personal_result_payload_v123(reply, request)
    assert payload["title"] == "FENETRE ACTIVE"
    assert payload["items"][0]["title"] == "W131 Notepad Test"

assert sha(ROADMAP) == roadmap_sha
print("[PASS] W131 R3 dispatcher publishes current PC _last_request")
print("[PASS] W131 R3 presenter classifies PC results as WINDOWS")
print("[PASS] W131 R3 window/process/foreground payloads are typed")
print("[PASS] W131 R3 PC summary never says mail/Google")
print("[PASS] live Roadmap unchanged")
