from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\AURA GPT version")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations.registry import IntegrationRegistry, IntegrationRequest
from integrations.pc_control import PC_CONTROL_PROVIDER_ID
from runtime.aura_pc_control_registry_binding_v131 import register_pc_control_provider_v131
from runtime.aura_pc_control_windows_v131 import WindowSnapshot, ProcessSnapshot
from runtime.integration_permissions_pc_v131 import evaluate_integration_permission_pc_v131

ROADMAP = ROOT / "data" / "roadmap" / "aura_master_roadmap_v2.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DenyFallbackSecurity:
    def authorize(self, action, params, *, user_confirmed=False):
        return "DENY"


class FakeBackend:
    def __init__(self):
        self.window = WindowSnapshot(
            hwnd=2222,
            pid=3333,
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
        return [ProcessSnapshot(3333, "w131-synthetic.exe", 100)]

    def foreground_window(self):
        return self.window

    def focus_window(self, hwnd):
        assert hwnd == 2222
        self.focused = True
        return True

    def minimize_window(self, hwnd):
        assert hwnd == 2222
        self.minimized = True
        return True

    def maximize_window(self, hwnd):
        assert hwnd == 2222
        self.maximized = True
        return True


roadmap_sha = sha(ROADMAP)

assert evaluate_integration_permission_pc_v131(
    "pc.discover_windows"
).decision == "ALLOW"
assert evaluate_integration_permission_pc_v131(
    "pc.close_window"
).decision == "DENY"
assert evaluate_integration_permission_pc_v131(
    "pc.terminate_process"
).decision == "DENY"
assert evaluate_integration_permission_pc_v131(
    "pc.focus_window", params={"command": "whoami"}
).decision == "DENY"

with tempfile.TemporaryDirectory(prefix="aura_w131_3b_") as td:
    store = ActionReceiptStore(Path(td) / "receipts.sqlite3")
    receipts = ActionReceiptService(store=store)
    registry = IntegrationRegistry(
        security_engine=DenyFallbackSecurity(),
        receipt_service=receipts,
    )

    backend = FakeBackend()
    register_pc_control_provider_v131(registry, backend=backend)

    manifests = registry.list_providers()
    assert any(m.provider_id == PC_CONTROL_PROVIDER_ID for m in manifests)

    req = IntegrationRequest.create(
        provider_id=PC_CONTROL_PROVIDER_ID,
        capability_id="pc.discover_windows",
        params={},
        origin="w131-invariant",
    )
    result = registry.execute_integration(req)
    assert result.status == "succeeded", result
    assert result.ok is True
    receipt = receipts.get_receipt(result.receipt_id)
    assert receipt.status == "succeeded"

    focus = IntegrationRequest.create(
        provider_id=PC_CONTROL_PROVIDER_ID,
        capability_id="pc.focus_window",
        params={"hwnd": 2222, "title": "W131 Synthetic Window"},
        origin="w131-invariant",
    )
    focused = registry.execute_integration(focus)
    assert focused.status == "succeeded", focused
    assert backend.focused is True
    focus_receipt = receipts.get_receipt(focused.receipt_id)
    assert focus_receipt.status == "succeeded"
    assert store.event_count(focus_receipt.receipt_id) >= 3

    stale = IntegrationRequest.create(
        provider_id=PC_CONTROL_PROVIDER_ID,
        capability_id="pc.maximize_window",
        params={"hwnd": 2222, "title": "Wrong Title"},
        origin="w131-invariant",
    )
    stale_result = registry.execute_integration(stale)
    assert stale_result.status == "failed"
    stale_receipt = receipts.get_receipt(stale_result.receipt_id)
    assert stale_receipt.status == "failed"

assert sha(ROADMAP) == roadmap_sha

print("[PASS] W131-3B provider satisfies canonical IntegrationProvider protocol")
print("[PASS] IntegrationRegistry owns policy + ActionReceiptService lifecycle")
print("[PASS] read-only discovery produces canonical succeeded receipt")
print("[PASS] bounded focus produces canonical succeeded receipt")
print("[PASS] stale target failure captured in canonical failed receipt")
print("[PASS] close/terminate remain denied and unregistered")
print("[PASS] raw shell material denied")
print("[PASS] live Roadmap unchanged")
