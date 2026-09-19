from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry
from integrations.pc_control import PcControlWindowsProvider
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action).startswith("pc.") else "DENY"

class FakeBackend:
    def __init__(self):
        self.window = WindowSnapshot(
            hwnd=4545,
            pid=5656,
            title="W131 Synthetic Window",
            visible=True,
            foreground=False,
        )
        self.focused = False
        self.minimized = False
        self.maximized = False

    def discover_windows(self, limit=256):
        return [self.window]

    def discover_processes(self, limit=512):
        return [ProcessSnapshot(5656, "w131-synthetic.exe", 100)]

    def foreground_window(self):
        return self.window

    def focus_window(self, hwnd):
        assert hwnd == 4545
        self.focused = True
        return True

    def minimize_window(self, hwnd):
        assert hwnd == 4545
        self.minimized = True
        return True

    def maximize_window(self, hwnd):
        assert hwnd == 4545
        self.maximized = True
        return True

roadmap_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_w131_3c_") as td:
    receipts = ActionReceiptService(
        store=ActionReceiptStore(Path(td) / "receipts.sqlite3")
    )
    registry = IntegrationRegistry(
        security_engine=Security(),
        receipt_service=receipts,
    )
    backend = FakeBackend()
    registry.register_provider(PcControlWindowsProvider(backend=backend))

    context = IntegrationRuntimeContext(
        registry=registry,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)

    r = dispatcher.handle_text("liste les fenetres Windows")
    assert r.handled is True
    assert r.status == "succeeded"
    assert r.capability_id == "pc.discover_windows"
    assert "W131 Synthetic Window" in r.text

    r = dispatcher.handle_text("quelle est la fenetre active")
    assert r.handled is True
    assert r.capability_id == "pc.get_foreground_window"
    assert "W131 Synthetic Window" in r.text

    r = dispatcher.handle_text("mets la fenetre W131 Synthetic Window au premier plan")
    assert r.handled is True and r.status == "succeeded"
    assert backend.focused is True
    assert r.receipt_id

    r = dispatcher.handle_text("minimise la fenetre W131 Synthetic Window")
    assert r.handled is True and r.status == "succeeded"
    assert backend.minimized is True

    r = dispatcher.handle_text("maximise la fenetre W131 Synthetic Window")
    assert r.handled is True and r.status == "succeeded"
    assert backend.maximized is True

    before = (backend.focused, backend.minimized, backend.maximized)
    r = dispatcher.handle_text("ferme la fenetre W131 Synthetic Window")
    assert r.handled is True and r.status == "denied"
    assert before == (backend.focused, backend.minimized, backend.maximized)

    r = dispatcher.handle_text("minimise la fenetre inconnue")
    assert r.handled is True
    assert r.clarification_required is True

assert sha(ROADMAP) == roadmap_sha

print("[PASS] W131-3C natural-language window discovery routed locally")
print("[PASS] W131-3C foreground-window query routed locally")
print("[PASS] W131-3C focus/minimize/maximize resolve title -> exact HWND")
print("[PASS] W131-3C PC actions execute through IntegrationRegistry receipts")
print("[PASS] W131-3C unknown window requires clarification")
print("[PASS] W131-3C destructive close remains explicitly denied")
print("[PASS] live Roadmap unchanged")
