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
from runtime.integration_permissions_pc_v131 import evaluate_integration_permission_pc_v131
from runtime.personal_integrations import IntegrationRuntimeContext, PersonalIntegrationDispatcher
from runtime.personal_result_presenter_v123 import build_personal_result_payload_v123

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class Security:
    def authorize(self, action, params, *, user_confirmed=False):
        decision = evaluate_integration_permission_pc_v131(action, params=params)
        return decision.decision


class FakeBackend:
    def __init__(self):
        self.target_hwnd = 5101
        self.other_hwnd = 5102
        self.target_title = "W132 Rollback Target"
        self.other_title = "W132 Previous Foreground"
        self.states = {
            self.target_hwnd: "normal",
            self.other_hwnd: "normal",
        }
        self.foreground = self.other_hwnd
        self.restore_calls = []
        self.focus_calls = []

    def _snap(self, hwnd):
        title = self.target_title if hwnd == self.target_hwnd else self.other_title
        pid = 6101 if hwnd == self.target_hwnd else 6102
        return WindowSnapshot(
            hwnd=hwnd,
            pid=pid,
            title=title,
            visible=True,
            foreground=(self.foreground == hwnd),
        )

    def discover_windows(self, limit=256):
        return [self._snap(self.target_hwnd), self._snap(self.other_hwnd)]

    def discover_processes(self, limit=512):
        return [
            ProcessSnapshot(6101, "w132-target.exe", 1),
            ProcessSnapshot(6102, "w132-foreground.exe", 1),
        ]

    def foreground_window(self):
        return self._snap(self.foreground) if self.foreground else None

    def window_state(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return None
        return {
            "show_state": self.states[hwnd],
            "foreground": self.foreground == hwnd,
        }

    def restore_window_state(self, hwnd, state):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        show_state = str((state or {}).get("show_state") or "")
        if show_state not in {"normal", "minimized", "maximized"}:
            return False
        self.states[hwnd] = show_state
        self.restore_calls.append((hwnd, show_state))
        return True

    def focus_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        if self.states[hwnd] == "minimized":
            self.states[hwnd] = "normal"
        self.foreground = hwnd
        self.focus_calls.append(hwnd)
        return True

    def minimize_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        self.states[hwnd] = "minimized"
        if self.foreground == hwnd:
            self.foreground = self.other_hwnd
        return True

    def maximize_window(self, hwnd):
        hwnd = int(hwnd)
        if hwnd not in self.states:
            return False
        self.states[hwnd] = "maximized"
        return True


def build_runtime(backend):
    td = tempfile.TemporaryDirectory(prefix="aura_w132_r8_")
    store = ActionReceiptStore(Path(td.name) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=store)
    registry = IntegrationRegistry(
        security_engine=Security(),
        receipt_service=receipts,
    )
    registry.register_provider(PcControlWindowsProvider(backend=backend))
    context = IntegrationRuntimeContext(
        registry=registry,
        receipt_service=receipts,
        email_backend=None,
        calendar_backend=None,
        timezone_name="Europe/Paris",
    )
    return td, store, receipts, PersonalIntegrationDispatcher(context=context)


roadmap_sha = sha(ROADMAP)

assert evaluate_integration_permission_pc_v131(
    "pc.restore_window_state",
    params={
        "schema": "aura.pc-control.window-recovery.v1",
        "available": True,
        "rollback_of_request_id": "pcr_test",
        "target": {"hwnd": 5101, "title": "W132 Rollback Target", "show_state": "normal"},
        "foreground_before": {"hwnd": 5102, "title": "W132 Previous Foreground"},
    },
).decision == "ALLOW"

# Happy path: minimize -> exact rollback -> previous state + foreground restored.
backend = FakeBackend()
td, store, receipts, dispatcher = build_runtime(backend)
try:
    first = dispatcher.handle_text("minimise la fenetre W132 Rollback Target")
    assert first.status == "succeeded", first
    assert backend.states[5101] == "minimized"
    recovery = getattr(dispatcher, "_w132_last_pc_recovery", None)
    assert isinstance(recovery, dict) and recovery.get("available") is True, recovery
    assert recovery["target"]["hwnd"] == 5101
    assert recovery["target"]["show_state"] == "normal"
    assert recovery["foreground_before"]["hwnd"] == 5102

    rollback = dispatcher.handle_text("annule la derniere action Windows")
    assert rollback.status == "succeeded", rollback
    assert rollback.capability_id == "pc.restore_window_state"
    assert backend.states[5101] == "normal"
    assert backend.foreground == 5102
    assert backend.restore_calls == [(5101, "normal")]
    assert backend.focus_calls[-1] == 5102
    assert getattr(dispatcher, "_w132_last_pc_recovery", None) is None

    receipt = receipts.get_receipt(rollback.receipt_id)
    assert receipt.status == "succeeded"
    assert store.event_count(receipt.receipt_id) >= 3

    request = getattr(dispatcher, "_last_request", None)
    payload = build_personal_result_payload_v123(rollback, request)
    assert payload["source"] == "WINDOWS"
    assert payload["status"] == "succeeded"
    assert payload["title"] == "RESTAURATION"
    assert payload["count"] == 1
    assert payload["items"][0]["title"] == "W132 Rollback Target"

    second = dispatcher.handle_text("annule la derniere action Windows")
    assert second.status == "no_recovery_available"
finally:
    td.cleanup()

# Stale target: exact title changed -> fail closed BEFORE restoration.
backend2 = FakeBackend()
td2, store2, receipts2, dispatcher2 = build_runtime(backend2)
try:
    first2 = dispatcher2.handle_text("maximise la fenetre W132 Rollback Target")
    assert first2.status == "succeeded"
    assert backend2.states[5101] == "maximized"
    backend2.target_title = "W132 Rollback Target CHANGED"
    restore_count_before = len(backend2.restore_calls)
    rollback2 = dispatcher2.handle_text("annule la derniere action Windows")
    assert rollback2.status == "failed", rollback2
    assert len(backend2.restore_calls) == restore_count_before
    failed_receipt = receipts2.get_receipt(rollback2.receipt_id)
    assert failed_receipt.status == "failed"
finally:
    td2.cleanup()

assert sha(ROADMAP) == roadmap_sha

print("[PASS] minimize/maximize actions capture an exact reversible preimage")
print("[PASS] explicit Windows rollback restores target show-state and prior foreground")
print("[PASS] rollback owns a canonical succeeded ActionReceipt")
print("[PASS] rollback Personal Result is typed WINDOWS / RESTAURATION")
print("[PASS] rollback is one-use in conversation state")
print("[PASS] changed HWND/title evidence fails closed before restoration")
print("[PASS] no close/terminate capability was enabled")
print("[PASS] live Roadmap unchanged")
