"""AURA A200-R16 deployed UI bridge adapter.

Pure protocol adapter between a deployed UI transport and the certified R15
UI/conversation command bridge. It does not open sockets, execute shell
commands, mutate the UI tree, or become a mission/policy authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
import uuid


A200_R16_ADAPTER_MARKER = "AURA_A200_R16_DEPLOYED_UI_BRIDGE_ADAPTER_V1"
AURA_UI_BRIDGE_PROTOCOL = "aura.ui-supervised-bridge.v1"

STRUCTURED_ENVELOPE_ONLY = True
SESSION_BINDING_REQUIRED = True
REQUEST_ID_REQUIRED = True
DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED = False
ARBITRARY_TOOL_EXECUTION_ENABLED = False
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


class UiAdapterProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class UiBridgeEnvelope:
    protocol: str
    request_id: str
    type: str
    payload: Mapping[str, Any]
    session_id: str | None = None


class A200DeployedUiBridgeAdapter:
    ALLOWED_TYPES = frozenset(
        {
            "runtime.status",
            "pc.read_foreground",
            "pc.prepare_minimize_window",
            "approval.present",
            "approval.confirm",
            "mission.cancel",
        }
    )

    def __init__(self, *, bridge: Any) -> None:
        self.bridge = bridge
        self.runtime = bridge.runtime

    def _parse(self, envelope: Mapping[str, Any]) -> UiBridgeEnvelope:
        if not isinstance(envelope, Mapping):
            raise UiAdapterProtocolError("structured mapping envelope required")

        protocol = str(envelope.get("protocol") or "").strip()
        if protocol != AURA_UI_BRIDGE_PROTOCOL:
            raise UiAdapterProtocolError("unsupported UI bridge protocol")

        request_id = str(envelope.get("request_id") or "").strip()
        if not request_id:
            raise UiAdapterProtocolError("request_id is required")

        command_type = str(envelope.get("type") or "").strip()
        if command_type not in self.ALLOWED_TYPES:
            raise UiAdapterProtocolError(
                f"unsupported UI bridge command: {command_type!r}"
            )

        payload = envelope.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise UiAdapterProtocolError("payload must be a mapping")

        session_id_raw = envelope.get("session_id")
        session_id = (
            None
            if session_id_raw is None
            else str(session_id_raw).strip()
        )
        if session_id is not None and not session_id:
            raise UiAdapterProtocolError("empty session_id is invalid")

        return UiBridgeEnvelope(
            protocol=protocol,
            request_id=request_id,
            type=command_type,
            payload=dict(payload),
            session_id=session_id,
        )

    def _assert_session(self, parsed: UiBridgeEnvelope) -> None:
        if parsed.session_id is None:
            if parsed.type not in {"runtime.status", "pc.read_foreground"}:
                raise UiAdapterProtocolError(
                    "state-changing/supervisory command requires session_id"
                )
            return
        if parsed.session_id != self.runtime.session_id:
            raise UiAdapterProtocolError("runtime session binding mismatch")

    def _to_r15_command(self, parsed: UiBridgeEnvelope) -> dict[str, Any]:
        p = dict(parsed.payload)
        t = parsed.type

        if t == "runtime.status":
            return {"type": "runtime.status"}

        if t == "pc.read_foreground":
            return {
                "type": "pc.read_foreground",
                "request_id": parsed.request_id,
            }

        if t == "pc.prepare_minimize_window":
            return {
                "type": "pc.prepare_minimize_window",
                "hwnd": p.get("hwnd"),
                "title": p.get("title"),
                "goal": p.get("goal"),
            }

        if t == "approval.present":
            return {
                "type": "approval.present",
                "mission_id": p.get("mission_id"),
            }

        if t == "approval.confirm":
            return {
                "type": "approval.confirm",
                "approval_id": p.get("approval_id"),
                "presentation_digest": p.get("presentation_digest"),
                "confirm": p.get("confirm") is True,
            }

        if t == "mission.cancel":
            return {
                "type": "mission.cancel",
                "mission_id": p.get("mission_id"),
                "confirm_cancel": p.get("confirm_cancel") is True,
            }

        raise UiAdapterProtocolError("unreachable command mapping")

    def dispatch(self, envelope: Mapping[str, Any]) -> dict[str, Any]:
        parsed = self._parse(envelope)
        self._assert_session(parsed)
        command = self._to_r15_command(parsed)
        response = self.bridge.handle(command)
        body = response.to_dict()
        return {
            "protocol": AURA_UI_BRIDGE_PROTOCOL,
            "request_id": parsed.request_id,
            "session_id": self.runtime.session_id,
            "response_id": "uir_" + uuid.uuid4().hex,
            "kind": body["kind"],
            "ok": bool(body["ok"]),
            "payload": dict(body["payload"]),
        }


def assert_r16_adapter_safety_contract() -> None:
    if not STRUCTURED_ENVELOPE_ONLY:
        raise RuntimeError("R16 adapter must remain structured-envelope only")
    if not SESSION_BINDING_REQUIRED or not REQUEST_ID_REQUIRED:
        raise RuntimeError("session/request identity binding is mandatory")
    if DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED:
        raise RuntimeError("direct natural-language execution must remain disabled")
    if ARBITRARY_TOOL_EXECUTION_ENABLED:
        raise RuntimeError("arbitrary tool execution must remain disabled")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("automatic approval/cancel must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")
