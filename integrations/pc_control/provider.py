from __future__ import annotations

from typing import Any, Mapping

from integrations.registry import (
    IntegrationCapability,
    IntegrationManifest,
    IntegrationRequest,
)
from runtime.aura_pc_control_windows_v131 import WindowsPcControlAdapter

PC_CONTROL_PROVIDER_ID = "pc-control.windows"

CAPABILITY_TO_ACTION = {
    "pc.discover_windows": "DISCOVER_WINDOWS",
    "pc.discover_processes": "DISCOVER_PROCESSES",
    "pc.get_foreground_window": "GET_FOREGROUND_WINDOW",
    "pc.focus_window": "FOCUS_WINDOW",
    "pc.minimize_window": "MINIMIZE_WINDOW",
    "pc.maximize_window": "MAXIMIZE_WINDOW",
}


class PcControlWindowsProvider:
    def __init__(self, backend=None) -> None:
        self.adapter = WindowsPcControlAdapter(
            backend,
            external_receipt_managed=True,
        )
        self._manifest = IntegrationManifest(
            provider_id=PC_CONTROL_PROVIDER_ID,
            display_name="AURA Windows PC Control",
            provider_version="1.3.2-w132.r8",
            capabilities=(
                IntegrationCapability(
                    "pc.discover_windows",
                    "pc.discover_windows",
                    "Discover visible Windows desktop windows.",
                    "low",
                    False,
                    "read",
                    True,
                ),
                IntegrationCapability(
                    "pc.discover_processes",
                    "pc.discover_processes",
                    "Discover running Windows processes.",
                    "low",
                    False,
                    "read",
                    True,
                ),
                IntegrationCapability(
                    "pc.get_foreground_window",
                    "pc.get_foreground_window",
                    "Read the current foreground window.",
                    "low",
                    False,
                    "read",
                    True,
                ),
                IntegrationCapability(
                    "pc.focus_window",
                    "pc.focus_window",
                    "Focus one exact HWND + title target.",
                    "low",
                    False,
                    "window_state",
                    True,
                ),
                IntegrationCapability(
                    "pc.minimize_window",
                    "pc.minimize_window",
                    "Minimize one exact HWND + title target.",
                    "low",
                    False,
                    "window_state",
                    True,
                ),
                IntegrationCapability(
                    "pc.maximize_window",
                    "pc.maximize_window",
                    "Maximize one exact HWND + title target.",
                    "low",
                    False,
                    "window_state",
                    True,
                ),
                IntegrationCapability(
                    "pc.restore_window_state",
                    "pc.restore_window_state",
                    "Restore the exact preimage of the last reversible window action.",
                    "low",
                    False,
                    "window_state",
                    True,
                ),
            ),
            auth_kind="local",
            metadata={
                "receipt_owner": "IntegrationRegistry/ActionReceiptService",
                "shell_execution": False,
                "powershell_execution": False,
                "arbitrary_executable_execution": False,
                "close_window_bound": False,
                "terminate_process_bound": False,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def health_snapshot(self) -> Mapping[str, Any]:
        return {
            "provider_id": PC_CONTROL_PROVIDER_ID,
            "available": True,
            "health_state": "healthy",
            "native_backend": "ctypes.Win32",
        }

    def execute(self, request: IntegrationRequest) -> Any:
        capability = str(request.capability_id or "")
        if capability == "pc.restore_window_state":
            result = self.adapter.restore_window_state(
                request.params,
                origin=request.origin,
            )
        else:
            action = CAPABILITY_TO_ACTION.get(capability)
            if action is None:
                raise ValueError(f"unsupported PC-control capability: {capability}")
            result = self.adapter.execute(
                action,
                request.params,
                origin=request.origin,
            )
        return {
            "provider_id": PC_CONTROL_PROVIDER_ID,
            "capability_id": capability,
            "pc_result": result,
            "evidence_refs": (),
        }
