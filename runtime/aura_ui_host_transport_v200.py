"""AURA A200-R18 loopback host transport.

Binds the R17 deployed UI CustomEvent transport client to the certified R16
runtime adapter through an authenticated loopback-only HTTP endpoint.

Security invariants:
- bind address is exactly 127.0.0.1;
- one fixed route only;
- install-scoped 256-bit transport token required on every POST;
- R16 still owns protocol/session/command validation;
- no shell/process execution;
- no automatic approval/cancellation;
- no external network destination;
- no direct natural-language execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from typing import Any, Mapping

from runtime.aura_deployed_ui_bridge_adapter_v200 import (
    A200DeployedUiBridgeAdapter,
)
from runtime.aura_persistent_runtime_bootstrap_v200 import (
    A200PersistentRuntimeBootstrap,
    DEFAULT_RUNTIME_STATE_ROOT,
)
from runtime.aura_supervised_runtime_ingress_v200 import (
    A200SupervisedRuntimeIngress,
)
from runtime.aura_ui_conversation_supervised_bridge_v200 import (
    A200UiConversationCommandBridge,
)


A200_R18_MARKER = "AURA_A200_R18_HOST_TRANSPORT_LOOPBACK_BINDING_V1"

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 18765
BRIDGE_PATH = "/aura/a200/bridge"
TOKEN_HEADER = "X-AURA-A200-Transport-Token"
TOKEN_FILE = Path(r"C:\AURA GPT version\data\a200_runtime\r18_ui_transport_token.txt")

LOOPBACK_ONLY_REQUIRED = True
TRANSPORT_TOKEN_REQUIRED = True
STRUCTURED_R16_ADAPTER_REQUIRED = True
SESSION_BINDING_DELEGATED_TO_R16 = True
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED = False
ARBITRARY_TOOL_EXECUTION_ENABLED = False
EXTERNAL_NETWORK_BINDING_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False


class UiHostTransportError(RuntimeError):
    pass


def load_transport_token(path: str | Path = TOKEN_FILE) -> str:
    token = Path(path).read_text(encoding="ascii").strip()
    if len(token) != 64:
        raise UiHostTransportError("transport token must be 64 hex characters")
    try:
        int(token, 16)
    except Exception as exc:
        raise UiHostTransportError("transport token is not hexadecimal") from exc
    return token.lower()


def _origin_allowed(origin: str | None) -> bool:
    if origin is None or origin == "" or origin == "null":
        return True
    origin = origin.lower()
    return (
        origin.startswith("http://127.0.0.1")
        or origin.startswith("http://localhost")
        or origin.startswith("https://127.0.0.1")
        or origin.startswith("https://localhost")
        or origin.startswith("aura://")
    )


@dataclass(frozen=True)
class HostTransportAddress:
    host: str
    port: int
    path: str


class A200UiHostTransport:
    def __init__(
        self,
        *,
        token: str | None = None,
        host: str = LOOPBACK_HOST,
        port: int = DEFAULT_PORT,
        state_root: str | Path = DEFAULT_RUNTIME_STATE_ROOT,
        backend: Any = None,
        owner_id: str = "aura-r18-ui-host",
    ) -> None:
        if host != LOOPBACK_HOST:
            raise UiHostTransportError("R18 transport may bind only 127.0.0.1")
        self.token = (token or load_transport_token()).strip().lower()
        if len(self.token) != 64:
            raise UiHostTransportError("invalid R18 transport token")

        self.runtime = A200PersistentRuntimeBootstrap(
            state_root=state_root,
            backend=backend,
            owner_id=owner_id,
        )
        self.ingress = A200SupervisedRuntimeIngress(runtime=self.runtime)
        self.bridge = A200UiConversationCommandBridge(ingress=self.ingress)
        self.adapter = A200DeployedUiBridgeAdapter(bridge=self.bridge)

        parent = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "AURA-A200-R18/1"

            def log_message(self, fmt, *args):
                return

            def _cors(self):
                origin = self.headers.get("Origin")
                if _origin_allowed(origin):
                    self.send_header(
                        "Access-Control-Allow-Origin",
                        "null" if origin in (None, "") else origin,
                    )
                    self.send_header("Vary", "Origin")

            def _json(self, status: int, payload: Mapping[str, Any]):
                body = json.dumps(
                    dict(payload),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                    default=str,
                ).encode("utf-8")
                self.send_response(status)
                self._cors()
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                if self.path != BRIDGE_PATH:
                    self.send_error(404)
                    return
                if not _origin_allowed(self.headers.get("Origin")):
                    self.send_error(403)
                    return
                self.send_response(204)
                self._cors()
                self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, " + TOKEN_HEADER,
                )
                self.send_header("Access-Control-Max-Age", "600")
                self.end_headers()

            def do_POST(self):
                if self.path != BRIDGE_PATH:
                    self._json(
                        404,
                        {
                            "ok": False,
                            "error": "route_not_found",
                        },
                    )
                    return

                if not _origin_allowed(self.headers.get("Origin")):
                    self._json(
                        403,
                        {
                            "ok": False,
                            "error": "origin_not_allowed",
                        },
                    )
                    return

                supplied = (
                    self.headers.get(TOKEN_HEADER) or ""
                ).strip().lower()
                if supplied != parent.token:
                    self._json(
                        403,
                        {
                            "ok": False,
                            "error": "transport_token_invalid",
                        },
                    )
                    return

                content_type = (
                    self.headers.get("Content-Type") or ""
                ).lower()
                if "application/json" not in content_type:
                    self._json(
                        415,
                        {
                            "ok": False,
                            "error": "application_json_required",
                        },
                    )
                    return

                try:
                    size = int(self.headers.get("Content-Length") or "0")
                except Exception:
                    size = 0
                if size <= 0 or size > 65536:
                    self._json(
                        413,
                        {
                            "ok": False,
                            "error": "invalid_payload_size",
                        },
                    )
                    return

                try:
                    raw = self.rfile.read(size)
                    envelope = json.loads(raw.decode("utf-8"))
                    if not isinstance(envelope, dict):
                        raise ValueError("mapping envelope required")
                    response = parent.adapter.dispatch(envelope)
                except Exception as exc:
                    self._json(
                        400,
                        {
                            "protocol": "aura.ui-supervised-bridge.v1",
                            "ok": False,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                    return

                self._json(200, response)

        self.server = ThreadingHTTPServer((host, int(port)), Handler)
        actual_host, actual_port = self.server.server_address[:2]
        if actual_host != LOOPBACK_HOST:
            self.server.server_close()
            raise UiHostTransportError("server bound outside loopback")
        self.address = HostTransportAddress(
            host=actual_host,
            port=int(actual_port),
            path=BRIDGE_PATH,
        )
        self._thread: threading.Thread | None = None

    def start(self) -> HostTransportAddress:
        if self._thread is not None:
            return self.address
        thread = threading.Thread(
            target=self.server.serve_forever,
            name="AURA-A200-R18-Loopback",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        return self.address

    def close(self) -> None:
        try:
            self.server.shutdown()
        finally:
            self.server.server_close()
            self.runtime.close()
            thread = self._thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=3.0)
            self._thread = None

    def serve_forever(self) -> None:
        try:
            self.server.serve_forever()
        finally:
            self.server.server_close()
            self.runtime.close()


def build_default_transport() -> A200UiHostTransport:
    return A200UiHostTransport()


def assert_r18_safety_contract() -> None:
    if not LOOPBACK_ONLY_REQUIRED:
        raise RuntimeError("R18 loopback-only binding is mandatory")
    if not TRANSPORT_TOKEN_REQUIRED:
        raise RuntimeError("R18 transport token is mandatory")
    if not STRUCTURED_R16_ADAPTER_REQUIRED:
        raise RuntimeError("R16 adapter must remain transport authority")
    if not SESSION_BINDING_DELEGATED_TO_R16:
        raise RuntimeError("R16 session binding must remain mandatory")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("automatic approval/cancellation must remain disabled")
    if DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED:
        raise RuntimeError("direct natural language execution must remain disabled")
    if ARBITRARY_TOOL_EXECUTION_ENABLED:
        raise RuntimeError("arbitrary tool execution must remain disabled")
    if EXTERNAL_NETWORK_BINDING_ENABLED:
        raise RuntimeError("external network binding must remain disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution must remain disabled")


def main() -> int:
    transport = build_default_transport()
    address = transport.address
    print(
        f"AURA A200-R18 host transport listening on "
        f"http://{address.host}:{address.port}{address.path}"
    )
    print("Loopback-only; Ctrl+C to stop.")
    try:
        transport.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
