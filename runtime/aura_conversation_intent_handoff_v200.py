"""AURA A200-R20 conversation intent handoff and plan preview.

This companion is a PREVIEW authority only. It cannot dispatch tools, execute
MissionEngine tasks, approve actions, or mutate Windows.

Runtime execution remains:
R20 deployed preview UI -> explicit read-only confirmation -> R18 transport
-> R16 adapter -> R15 bridge -> R14 ingress -> R13 -> MissionEngine.

Mutation/destructive natural-language intents never receive an executable
command from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import msvcrt
from pathlib import Path
import re
import threading
import unicodedata
from typing import Any, Mapping


A200_R20_MARKER = "AURA_A200_R20_CONVERSATION_INTENT_HANDOFF_PLAN_PREVIEW_V1"

LOOPBACK_HOST = "127.0.0.1"
DEFAULT_PORT = 18766
PREVIEW_PATH = "/aura/a200/intent/preview"
TOKEN_HEADER = "X-AURA-A200-Transport-Token"
TOKEN_FILE = Path(r"C:\AURA GPT version\data\a200_runtime\r18_ui_transport_token.txt")
LOCK_FILE = Path(r"C:\AURA GPT version\data\a200_runtime\r20_intent_preview.lock")

PREVIEW_ONLY_AUTHORITY = True
EXPLICIT_READONLY_CONFIRMATION_REQUIRED = True
READONLY_EXECUTION_ALLOWLIST = ("runtime.status", "pc.read_foreground")
DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED = False
MUTATION_EXECUTION_FROM_INTENT_ENABLED = False
DESTRUCTIVE_EXECUTION_ENABLED = False
AUTO_APPROVAL_ENABLED = False
AUTO_CANCEL_ENABLED = False
ARBITRARY_TOOL_EXECUTION_ENABLED = False
EXTERNAL_NETWORK_BINDING_ENABLED = False


class IntentPreviewError(RuntimeError):
    pass


def _ascii_normalize(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _digest(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(
        dict(payload),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class IntentPlanPreview:
    schema: str
    text: str
    normalized_text: str
    intent_kind: str
    risk: str
    title: str
    steps: tuple[str, ...]
    execution_allowed: bool
    requires_explicit_confirmation: bool
    requires_supervised_path: bool
    command_type: str | None
    command_payload: Mapping[str, Any]
    plan_digest: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["steps"] = list(self.steps)
        value["command_payload"] = dict(self.command_payload)
        return value


class A200ConversationIntentHandoff:
    def _preview_payload(
        self,
        *,
        text: str,
        normalized: str,
        intent_kind: str,
        risk: str,
        title: str,
        steps: tuple[str, ...],
        execution_allowed: bool,
        requires_explicit_confirmation: bool,
        requires_supervised_path: bool,
        command_type: str | None,
        command_payload: Mapping[str, Any] | None = None,
    ) -> IntentPlanPreview:
        base = {
            "schema": "aura.a200.intent-plan-preview.v1",
            "text": text,
            "normalized_text": normalized,
            "intent_kind": intent_kind,
            "risk": risk,
            "title": title,
            "steps": list(steps),
            "execution_allowed": bool(execution_allowed),
            "requires_explicit_confirmation": bool(
                requires_explicit_confirmation
            ),
            "requires_supervised_path": bool(requires_supervised_path),
            "command_type": command_type,
            "command_payload": dict(command_payload or {}),
        }
        plan_digest = _digest(base)
        return IntentPlanPreview(
            schema=base["schema"],
            text=text,
            normalized_text=normalized,
            intent_kind=intent_kind,
            risk=risk,
            title=title,
            steps=tuple(steps),
            execution_allowed=bool(execution_allowed),
            requires_explicit_confirmation=bool(
                requires_explicit_confirmation
            ),
            requires_supervised_path=bool(requires_supervised_path),
            command_type=command_type,
            command_payload=dict(command_payload or {}),
            plan_digest=plan_digest,
        )

    def preview(self, text: str) -> IntentPlanPreview:
        raw = str(text or "").strip()
        if not raw:
            raise IntentPreviewError("conversation text is required")
        if len(raw) > 2000:
            raise IntentPreviewError("conversation text exceeds preview limit")

        normalized = _ascii_normalize(raw)

        destructive_terms = (
            "supprime",
            "efface",
            "delete",
            "kill",
            "tue",
            "terminate",
            "termine le processus",
            "ferme le processus",
            "close process",
            "shutdown",
            "arrete le pc",
            "redemarre le pc",
            "format",
        )
        if any(term in normalized for term in destructive_terms):
            return self._preview_payload(
                text=raw,
                normalized=normalized,
                intent_kind="blocked_destructive",
                risk="destructive",
                title="Action destructive bloquée",
                steps=(
                    "do_not_dispatch",
                    "explain_safety_boundary",
                ),
                execution_allowed=False,
                requires_explicit_confirmation=False,
                requires_supervised_path=True,
                command_type=None,
            )

        mutation_terms = (
            "minimise",
            "minimize",
            "maximise",
            "maximize",
            "focus",
            "mets au premier plan",
            "bring to front",
            "ferme la fenetre",
            "close window",
        )
        if any(term in normalized for term in mutation_terms):
            return self._preview_payload(
                text=raw,
                normalized=normalized,
                intent_kind="supervised_mutation",
                risk="reversible_or_mutating",
                title="Plan supervisé requis",
                steps=(
                    "resolve_exact_target",
                    "build_structured_supervised_plan",
                    "present_exact_approval",
                    "execute_only_after_explicit_approval",
                    "verify_or_recover",
                ),
                execution_allowed=False,
                requires_explicit_confirmation=True,
                requires_supervised_path=True,
                command_type=None,
            )

        status_terms = (
            "statut supervision",
            "status supervision",
            "etat supervision",
            "supervision status",
            "statut aura",
            "etat aura",
        )
        if any(term in normalized for term in status_terms):
            return self._preview_payload(
                text=raw,
                normalized=normalized,
                intent_kind="runtime_status",
                risk="read_only",
                title="Lire l’état de supervision",
                steps=(
                    "request_runtime_status",
                    "display_structured_status",
                ),
                execution_allowed=True,
                requires_explicit_confirmation=True,
                requires_supervised_path=False,
                command_type="runtime.status",
            )

        foreground_terms = (
            "fenetre active",
            "quelle fenetre",
            "application active",
            "app active",
            "foreground window",
            "what window is active",
            "active window",
        )
        if any(term in normalized for term in foreground_terms):
            return self._preview_payload(
                text=raw,
                normalized=normalized,
                intent_kind="read_foreground",
                risk="read_only",
                title="Lire la fenêtre active",
                steps=(
                    "read_foreground_window",
                    "return_canonical_receipt",
                    "display_read_only_result",
                ),
                execution_allowed=True,
                requires_explicit_confirmation=True,
                requires_supervised_path=False,
                command_type="pc.read_foreground",
            )

        return self._preview_payload(
            text=raw,
            normalized=normalized,
            intent_kind="unsupported",
            risk="unknown",
            title="Demande non reconnue",
            steps=("do_not_dispatch",),
            execution_allowed=False,
            requires_explicit_confirmation=False,
            requires_supervised_path=False,
            command_type=None,
        )


def load_transport_token() -> str:
    token = TOKEN_FILE.read_text(encoding="ascii").strip().lower()
    if len(token) != 64:
        raise IntentPreviewError("R18 transport token invalid")
    int(token, 16)
    return token


def _origin_allowed(origin: str | None) -> bool:
    if origin in (None, "", "null"):
        return True
    origin = origin.lower()
    return (
        origin.startswith("http://127.0.0.1")
        or origin.startswith("http://localhost")
        or origin.startswith("https://127.0.0.1")
        or origin.startswith("https://localhost")
        or origin.startswith("aura://")
    )


class _ProcessFileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = None

    def acquire(self) -> None:
        if self.handle is not None:
            return
        try:
            handle = self.path.open("a+b")
        except OSError as exc:
            raise IntentPreviewError(
                "another R20 intent preview host is active"
            ) from exc
        try:
            handle.seek(0)
            if handle.read(1) == b"":
                handle.seek(0)
                handle.write(b"\0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            handle.close()
            raise IntentPreviewError(
                "another R20 intent preview host is active"
            ) from exc
        self.handle = handle

    def release(self) -> None:
        if self.handle is None:
            return
        try:
            self.handle.seek(0)
            msvcrt.locking(
                self.handle.fileno(),
                msvcrt.LK_UNLCK,
                1,
            )
        finally:
            self.handle.close()
            self.handle = None


class A200IntentPreviewHost:
    def __init__(
        self,
        *,
        token: str | None = None,
        host: str = LOOPBACK_HOST,
        port: int = DEFAULT_PORT,
        lock_file: str | Path = LOCK_FILE,
    ) -> None:
        if host != LOOPBACK_HOST:
            raise IntentPreviewError("R20 may bind only 127.0.0.1")
        self.token = (token or load_transport_token()).strip().lower()
        if len(self.token) != 64:
            raise IntentPreviewError("invalid R20 transport token")
        self.handoff = A200ConversationIntentHandoff()
        self.lock = _ProcessFileLock(Path(lock_file))
        parent = self

        class Handler(BaseHTTPRequestHandler):
            server_version = "AURA-A200-R20/1"

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
                self.send_header(
                    "Content-Type",
                    "application/json; charset=utf-8",
                )
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_OPTIONS(self):
                if self.path != PREVIEW_PATH:
                    self.send_error(404)
                    return
                if not _origin_allowed(self.headers.get("Origin")):
                    self.send_error(403)
                    return
                self.send_response(204)
                self._cors()
                self.send_header(
                    "Access-Control-Allow-Methods",
                    "POST, OPTIONS",
                )
                self.send_header(
                    "Access-Control-Allow-Headers",
                    "Content-Type, " + TOKEN_HEADER,
                )
                self.end_headers()

            def do_POST(self):
                if self.path != PREVIEW_PATH:
                    self._json(
                        404,
                        {"ok": False, "error": "route_not_found"},
                    )
                    return
                if not _origin_allowed(self.headers.get("Origin")):
                    self._json(
                        403,
                        {"ok": False, "error": "origin_not_allowed"},
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

                ctype = (
                    self.headers.get("Content-Type") or ""
                ).lower()
                if "application/json" not in ctype:
                    self._json(
                        415,
                        {
                            "ok": False,
                            "error": "application_json_required",
                        },
                    )
                    return

                try:
                    size = int(
                        self.headers.get("Content-Length") or "0"
                    )
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
                    request = json.loads(
                        self.rfile.read(size).decode("utf-8")
                    )
                    if not isinstance(request, dict):
                        raise ValueError("mapping request required")
                    if (
                        request.get("schema")
                        != "aura.a200.intent-preview-request.v1"
                    ):
                        raise ValueError(
                            "invalid intent preview request schema"
                        )
                    request_id = str(
                        request.get("request_id") or ""
                    ).strip()
                    if not request_id:
                        raise ValueError("request_id required")
                    preview = parent.handoff.preview(
                        str(request.get("text") or "")
                    )
                except Exception as exc:
                    self._json(
                        400,
                        {
                            "schema":
                                "aura.a200.intent-preview-response.v1",
                            "ok": False,
                            "error": type(exc).__name__,
                            "message": str(exc),
                        },
                    )
                    return

                self._json(
                    200,
                    {
                        "schema":
                            "aura.a200.intent-preview-response.v1",
                        "ok": True,
                        "request_id": request_id,
                        "preview": preview.to_dict(),
                    },
                )

        self.lock.acquire()
        try:
            self.server = ThreadingHTTPServer(
                (host, int(port)),
                Handler,
            )
        except Exception:
            self.lock.release()
            raise
        actual_host, actual_port = self.server.server_address[:2]
        if actual_host != LOOPBACK_HOST:
            self.server.server_close()
            self.lock.release()
            raise IntentPreviewError(
                "R20 bound outside loopback"
            )
        self.host = actual_host
        self.port = int(actual_port)
        self._thread: threading.Thread | None = None

    def start(self) -> tuple[str, int]:
        if self._thread is not None:
            return self.host, self.port
        thread = threading.Thread(
            target=self.server.serve_forever,
            name="AURA-A200-R20-IntentPreview",
            daemon=True,
        )
        thread.start()
        self._thread = thread
        return self.host, self.port

    def close(self) -> None:
        try:
            self.server.shutdown()
        finally:
            self.server.server_close()
            thread = self._thread
            if thread is not None and thread.is_alive():
                thread.join(timeout=3.0)
            self._thread = None
            self.lock.release()

    def serve_forever(self) -> None:
        try:
            self.server.serve_forever()
        finally:
            self.server.server_close()
            self.lock.release()


def assert_r20_safety_contract() -> None:
    if not PREVIEW_ONLY_AUTHORITY:
        raise RuntimeError("R20 must remain preview-only")
    if not EXPLICIT_READONLY_CONFIRMATION_REQUIRED:
        raise RuntimeError("explicit read-only confirmation required")
    if DIRECT_NATURAL_LANGUAGE_EXECUTION_ENABLED:
        raise RuntimeError("direct natural-language execution disabled")
    if MUTATION_EXECUTION_FROM_INTENT_ENABLED:
        raise RuntimeError("mutation execution from intent disabled")
    if DESTRUCTIVE_EXECUTION_ENABLED:
        raise RuntimeError("destructive execution disabled")
    if AUTO_APPROVAL_ENABLED or AUTO_CANCEL_ENABLED:
        raise RuntimeError("automatic approval/cancel disabled")
    if ARBITRARY_TOOL_EXECUTION_ENABLED:
        raise RuntimeError("arbitrary tool execution disabled")
    if EXTERNAL_NETWORK_BINDING_ENABLED:
        raise RuntimeError("external network binding disabled")


def main() -> int:
    assert_r20_safety_contract()
    host = A200IntentPreviewHost()
    print(
        f"AURA A200-R20 intent preview listening on "
        f"http://{host.host}:{host.port}{PREVIEW_PATH}"
    )
    try:
        host.serve_forever()
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
