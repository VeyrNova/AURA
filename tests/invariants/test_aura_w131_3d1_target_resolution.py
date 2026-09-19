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
from runtime.personal_result_presenter_v123 import (
    build_personal_result_payload_v123,
    summarize_personal_result_for_tts_v123,
)

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action).startswith("pc.") else "DENY"

class FakeBackend:
    def __init__(self):
        self.windows = [
            WindowSnapshot(
                hwnd=7001,
                pid=8001,
                title="test aura.txt – Bloc-notes",
                visible=True,
                foreground=False,
            ),
            WindowSnapshot(
                hwnd=7002,
                pid=8002,
                title="AURA",
                visible=True,
                foreground=True,
            ),
        ]
        self.focused = False
        self.minimized = False
        self.maximized = False

    def discover_windows(self, limit=256):
        return list(self.windows)

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(8001, "notepad.exe", 100),
            ProcessSnapshot(8002, "aura.exe", 100),
        ]

    def foreground_window(self):
        return self.windows[1]

    def focus_window(self, hwnd):
        assert int(hwnd) == 7001
        self.focused = True
        return True

    def minimize_window(self, hwnd):
        assert int(hwnd) == 7001
        self.minimized = True
        return True

    def maximize_window(self, hwnd):
        assert int(hwnd) == 7001
        self.maximized = True
        return True

roadmap_sha = sha(ROADMAP)

with tempfile.TemporaryDirectory(prefix="aura_w131_3d1_") as td:
    receipts = ActionReceiptService(
        store=ActionReceiptStore(Path(td) / "receipts.sqlite3")
    )
    registry = IntegrationRegistry(
        security_engine=Security(),
        receipt_service=receipts,
    )
    backend = FakeBackend()
    registry.register_provider(PcControlWindowsProvider(backend=backend))
    dispatcher = PersonalIntegrationDispatcher(
        context=IntegrationRuntimeContext(
            registry=registry,
            receipt_service=receipts,
            email_backend=None,
            calendar_backend=None,
            timezone_name="Europe/Paris",
        )
    )

    # Exact title with a normal hyphen must match a real title containing EN DASH.
    reply = dispatcher.handle_text(
        "mets la fenetre test aura.txt - Bloc-notes au premier plan"
    )
    assert reply.status == "succeeded", reply
    assert backend.focused is True

    # Short stable user label must also match.
    reply = dispatcher.handle_text("minimise la fenetre test aura.txt")
    assert reply.status == "succeeded", reply
    assert backend.minimized is True

    reply = dispatcher.handle_text(
        "maximise la fenetre test aura txt bloc notes"
    )
    assert reply.status == "succeeded", reply
    assert backend.maximized is True

    # No-match must be a truthful clarification, not "0 Windows windows".
    reply = dispatcher.handle_text("minimise la fenetre CetteFenetreNExistePas")
    assert reply.clarification_required is True
    request = getattr(dispatcher, "_last_request", None)
    payload = build_personal_result_payload_v123(reply, request)
    summary = summarize_personal_result_for_tts_v123(payload, reply.text)
    assert "aucune fenetre" in summary.casefold()
    assert "0 fenetre" not in summary.casefold()

assert sha(ROADMAP) == roadmap_sha

print("[PASS] W131-3D1 punctuation-insensitive title matching")
print("[PASS] W131-3D1 short title substring matching")
print("[PASS] W131-3D1 token-normalized title matching")
print("[PASS] W131-3D1 focus/minimize/maximize still use exact HWND after resolution")
print("[PASS] W131-3D1 no-match returns truthful clarification, not fake 0-window discovery")
print("[PASS] live Roadmap unchanged")
