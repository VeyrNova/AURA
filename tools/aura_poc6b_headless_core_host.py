from __future__ import annotations

import argparse
import importlib.util
import json
import os
import socket
import sys
import time
from pathlib import Path


RELEASE_UI = "v0.7.2.2-rc4.2"


def _is_core_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "core" / "version.py").is_file()
        and (path / "VERSION").is_file()
        and (path / "main.py").is_file()
        and (path / "venv" / "Scripts" / "python.exe").is_file()
    )


def _find_core(explicit: str = "") -> Path:
    candidates = []

    if explicit:
        candidates.append(Path(explicit))

    env_root = str(os.environ.get("AURA_ROOT") or "").strip()
    if env_root:
        candidates.append(Path(env_root))

    override = Path(__file__).resolve().parents[1] / "AURA_ROOT_OVERRIDE.txt"
    if override.is_file():
        try:
            raw = override.read_text(encoding="utf-8").strip().strip('"')
            if raw:
                candidates.append(Path(raw))
        except Exception:
            pass

    if os.name == "nt":
        candidates.extend([
            Path(r"C:\AURA GPT version"),
            Path(r"C:\AURA"),
        ])

    seen = set()
    for raw in candidates:
        try:
            p = raw.expanduser().resolve(strict=False)
        except Exception:
            p = raw.expanduser().absolute()
        key = str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _is_core_root(p):
            return p

    raise RuntimeError(
        "AURA Core introuvable. Configure AURA_ROOT_OVERRIDE.txt "
        "avec le chemin du dossier racine AURA."
    )


def _valid_ui_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / "tools" / "shell_host.py").is_file()
        and (path / "dist" / "index.html").is_file()
    )


def _find_ui_root(core: Path, explicit: str = "") -> Path:
    candidates = []

    if explicit:
        candidates.append(Path(explicit))

    env_ui = str(os.environ.get("AURA_UI_ROOT") or "").strip()
    if env_ui:
        candidates.append(Path(env_ui))

    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        base = Path(local) / "AURA" / "ui"
        candidates.extend([
            base / RELEASE_UI,
            base / "chromium" / RELEASE_UI,
        ])
        if base.is_dir():
            try:
                dynamic = sorted(
                    [
                        p for p in base.rglob("shell_host.py")
                        if p.parent.name == "tools"
                    ],
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                candidates.extend([p.parent.parent for p in dynamic[:8]])
            except Exception:
                pass

    candidates.extend([
        core / "ui" / "chromium" / RELEASE_UI,
        core / "ui" / RELEASE_UI,
    ])

    seen = set()
    for raw in candidates:
        try:
            p = raw.expanduser().resolve(strict=False)
        except Exception:
            p = raw.expanduser().absolute()
        key = str(p).casefold()
        if key in seen:
            continue
        seen.add(key)
        if _valid_ui_root(p):
            return p

    raise RuntimeError(
        "UI RC4.2 active introuvable. Le Core AURA complet doit être installé."
    )


def _port_open(port: int, timeout: float = 0.25) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", int(port)), timeout=timeout):
            return True
    except OSError:
        return False


def _write_status(poc_root: Path, **payload) -> None:
    path = poc_root / "runtime" / "poc6b_headless_core_status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    body = {
        "schema": "aura.poc6b.headless-core-status.v1",
        "timestamp": time.time(),
        "pid": os.getpid(),
        "no_browser": True,
        **payload,
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(body, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)



def _install_native_text_contract(core: Path, poc_root: Path) -> None:
    """Make typed Qt turns text-first while preserving normal final TTS.

    This patch is process-local. It does not edit ui/main_window.py.

    The validated MainWindow currently computes `voice_response` from
    `_voice_output_enabled` inside `_continue_after_agent_router()`. That is
    correct for microphone turns, but a typed message arriving from the native
    Qt composer should use the full text profile. We temporarily disable only
    the generation-time voice flag for that exact typed turn, then restore it
    immediately. The final aura_message still reaches the normal TTS listener,
    so auto-speak remains available after the full text answer is committed.
    """
    if str(core) not in sys.path:
        sys.path.insert(0, str(core))

    from ui.main_window import MainWindow

    if getattr(MainWindow, "_aura_poc6d_native_text_contract", False):
        return

    original_user = MainWindow._on_user_message
    original_continue = MainWindow._continue_after_agent_router

    diag_path = poc_root / "runtime" / "poc6e_direct_text_contract.jsonl"
    diag_path.parent.mkdir(parents=True, exist_ok=True)

    def diag(kind: str, **payload) -> None:
        try:
            item = {
                "ts": time.time(),
                "kind": str(kind),
                **payload,
            }
            with diag_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, ensure_ascii=False, default=str) + "\n")
        except Exception:
            pass

    def wrapped_user(self, text, *args, **kwargs):
        raw = str(text or "")
        channel = str(
            getattr(self, "_aura_developer_input_channel", "text") or "text"
        ).strip().casefold()

        # `_on_stt_finished()` sets this field to "voice" immediately before
        # invoking _on_user_message(). Shell/Qt typed input remains "text".
        if channel != "voice" and raw.strip():
            self._aura_poc6d_typed_turn_text = raw.strip()
            self._aura_poc6d_typed_turn_started = time.monotonic()
            diag(
                "typed_turn_marked",
                chars=len(raw.strip()),
                channel=channel or "text",
            )
        else:
            self._aura_poc6d_typed_turn_text = ""
            self._aura_poc6d_typed_turn_started = 0.0
            diag(
                "voice_turn_preserved",
                chars=len(raw.strip()),
                channel=channel or "voice",
            )

        return original_user(self, text, *args, **kwargs)

    def wrapped_continue(self, text, document_context=None):
        raw = str(text or "").strip()
        marked = str(
            getattr(self, "_aura_poc6d_typed_turn_text", "") or ""
        ).strip()
        started = float(
            getattr(self, "_aura_poc6d_typed_turn_started", 0.0) or 0.0
        )
        fresh = bool(started and (time.monotonic() - started) < 120.0)
        typed_turn = bool(raw and marked == raw and fresh)

        if not typed_turn:
            return original_continue(
                self,
                text,
                document_context=document_context,
            )

        previous_voice_output = bool(
            getattr(self, "_voice_output_enabled", False)
        )
        previous_fabric_auto = os.environ.get("AURA_CONVERSATION_FABRIC_AUTO")

        # Generation only:
        # 1) typed Qt input uses the full text-generation contract;
        # 2) ordinary Conversation Fabric is bypassed for this exact dispatch.
        #
        # Why: the validated legacy Gemini client applies
        # thinking_level=minimal + >=768 visible-token budget for Gemini 3.x.
        # The current Fabric Gemini adapter does not forward thinkingConfig,
        # so Gemini can spend the output ceiling on internal thinking and return
        # no visible text.
        self._voice_output_enabled = False
        os.environ["AURA_CONVERSATION_FABRIC_AUTO"] = "0"

        diag(
            "direct_text_profile_enter",
            chars=len(raw),
            previous_voice_output=previous_voice_output,
            previous_fabric_auto=previous_fabric_auto,
            fabric_temporarily_disabled=True,
        )

        try:
            return original_continue(
                self,
                text,
                document_context=document_context,
            )
        finally:
            # _continue_after_agent_router() has already constructed the profile
            # and LLMWorker before it returns. Restoring here cannot re-enable
            # Fabric for that already-dispatched worker.
            self._voice_output_enabled = previous_voice_output

            if previous_fabric_auto is None:
                os.environ.pop("AURA_CONVERSATION_FABRIC_AUTO", None)
            else:
                os.environ["AURA_CONVERSATION_FABRIC_AUTO"] = previous_fabric_auto

            self._aura_poc6d_typed_turn_text = ""
            self._aura_poc6d_typed_turn_started = 0.0

            diag(
                "direct_text_profile_exit",
                chars=len(raw),
                restored_voice_output=previous_voice_output,
                restored_fabric_auto=previous_fabric_auto,
            )

    wrapped_user._aura_poc6d = True
    wrapped_continue._aura_poc6d = True

    MainWindow._on_user_message = wrapped_user
    MainWindow._continue_after_agent_router = wrapped_continue
    MainWindow._aura_poc6d_native_text_contract = True

    diag(
        "patch_installed",
        core=str(core),
        mode="typed-text-direct-provider-full-answer-final-tts-preserved",
    )

# AURA_QT_HEADLESS_GOOGLE_BRIDGE_FIX19
def _install_qt_google_bridge(module) -> None:
    """Read-only Qt bridge to the existing AURA Google account."""
    original_make_handler = getattr(module, "make_handler", None)
    if not callable(original_make_handler):
        raise RuntimeError("shell_host.make_handler unavailable")
    if getattr(original_make_handler, "_aura_qt_google_fix19", False):
        return

    def make_handler(rt):
        Base = original_make_handler(rt)

        class QtGoogleHandler(Base):
            def _qt_google_service(self):
                from runtime.connected_accounts_v120 import get_connected_accounts_service_v120
                return get_connected_accounts_service_v120()

            def _qt_google_status(self):
                service = self._qt_google_service()
                state = service.provider_status("google")
                accounts = list(state.get("accounts") or [])
                account = accounts[0] if accounts else {}
                services = [str(x).lower() for x in list(account.get("services") or [])]
                return {
                    "ok": True,
                    "connected": bool(accounts),
                    "state": str(state.get("state") or "disconnected"),
                    "account_label": str(account.get("display_label") or "Google"),
                    "services": services,
                    "tasks_supported": "tasks" in services,
                    "calendar_supported": "calendar" in services,
                    "notes_supported": False,
                    "notes_reason": "google_keep_backend_not_configured",
                }

            def do_GET(self):
                import urllib.parse
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                if path not in {
                    "/api/qt/google/status",
                    "/api/qt/google/tasks",
                    "/api/qt/google/calendar",
                }:
                    return super().do_GET()
                if not self.auth():
                    return self.send_json(403, {"ok": False, "error": "forbidden"})
                try:
                    status = self._qt_google_status()
                    if path == "/api/qt/google/status":
                        return self.send_json(200, status)
                    if not status.get("connected"):
                        return self.send_json(409, {"ok": False, "error": "google_account_not_connected", **status})
                    service = self._qt_google_service()
                    if path == "/api/qt/google/tasks":
                        if not status.get("tasks_supported"):
                            return self.send_json(409, {"ok": False, "error": "google_tasks_reconsent_required", **status})
                        from integrations.google.live_tasks_backend_v123 import GoogleLiveTasksBackendV123
                        backend = GoogleLiveTasksBackendV123(service=service)
                        rows = backend.list_tasks(tasklist_id="@default", limit=100, include_completed=False)
                        items = []
                        for row in rows:
                            items.append({
                                "external_id": str(getattr(row, "task_id", "") or ""),
                                "tasklist_id": str(getattr(row, "tasklist_id", "@default") or "@default"),
                                "title": str(getattr(row, "title", "") or ""),
                                "status": str(getattr(row, "status", "") or ""),
                                "due_date": str(getattr(row, "due", "") or ""),
                                "description": str(getattr(row, "notes", "") or ""),
                                "source": "GOOGLE",
                                "source_label": "GOOGLE TASKS",
                            })
                        return self.send_json(200, {"ok": True, "kind": "tasks", "count": len(items), "items": items})

                    query = urllib.parse.parse_qs(parsed.query)
                    try:
                        year = int((query.get("year") or ["0"])[0])
                        month = int((query.get("month") or ["0"])[0])
                    except Exception:
                        year = month = 0
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    if year < 2000 or year > 2200:
                        year = now.year
                    if month < 1 or month > 12:
                        month = now.month
                    start = datetime(year, month, 1, tzinfo=timezone.utc)
                    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc) if month == 12 else datetime(year, month + 1, 1, tzinfo=timezone.utc)
                    from integrations.google.live_calendar_backend_v121 import GoogleLiveCalendarBackendV121
                    backend = GoogleLiveCalendarBackendV121(service=service)
                    response = backend._calendar().events().list(
                        calendarId="primary",
                        timeMin=start.isoformat(),
                        timeMax=end.isoformat(),
                        maxResults=250,
                        singleEvents=True,
                        orderBy="startTime",
                    ).execute()
                    items = []
                    for raw in response.get("items", []) or []:
                        if str(raw.get("status") or "").lower() == "cancelled":
                            continue
                        start_raw = raw.get("start", {}) or {}
                        end_raw = raw.get("end", {}) or {}
                        when = start_raw.get("dateTime") or start_raw.get("date") or ""
                        end_when = end_raw.get("dateTime") or end_raw.get("date") or ""
                        items.append({
                            "external_id": str(raw.get("id") or ""),
                            "title": str(raw.get("summary") or "Événement"),
                            "trigger_at": str(when),
                            "end_at": str(end_when),
                            "description": str(raw.get("location") or raw.get("description") or ""),
                            "source": "GOOGLE",
                            "source_label": "GOOGLE CALENDAR",
                        })
                    return self.send_json(200, {"ok": True, "kind": "calendar", "year": year, "month": month, "count": len(items), "items": items})
                except Exception as exc:
                    try:
                        rt.log("Qt Google bridge failed path=%s error=%s", path, type(exc).__name__, exc_info=True)
                    except Exception:
                        pass
                    return self.send_json(502, {"ok": False, "error": type(exc).__name__, "detail": str(exc)[:240]})

        return QtGoogleHandler

    make_handler._aura_qt_google_fix19 = True
    module.make_handler = make_handler


# AURA_GOOGLE_ACCOUNT_CONNECT_FIX20
def _install_qt_google_connect_bridge_fix20(module) -> None:
    """Add Google connect/re-consent POST route on top of FIX19."""
    previous_make_handler = getattr(module, "make_handler", None)
    if not callable(previous_make_handler):
        raise RuntimeError("shell_host.make_handler unavailable")
    if getattr(previous_make_handler, "_aura_qt_google_connect_fix20", False):
        return

    def make_handler(rt):
        Base = previous_make_handler(rt)

        class QtGoogleConnectHandler(Base):
            def do_POST(self):
                import json
                import urllib.parse

                parsed = urllib.parse.urlparse(self.path)
                if parsed.path != "/api/qt/google/connect":
                    return super().do_POST()

                if not self.auth():
                    return self.send_json(403, {"ok": False, "error": "forbidden"})

                try:
                    try:
                        length = int(self.headers.get("Content-Length", "0") or "0")
                    except Exception:
                        length = 0

                    if length <= 0 or length > 65536:
                        return self.send_json(400, {"ok": False, "error": "invalid_request_size"})

                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    client_file = str(payload.get("client_file") or "").strip()
                    if not client_file:
                        return self.send_json(400, {"ok": False, "error": "google_oauth_client_file_required"})

                    client_path = Path(client_file).expanduser().resolve()
                    if not client_path.is_file() or client_path.suffix.casefold() != ".json":
                        return self.send_json(400, {"ok": False, "error": "invalid_google_oauth_client_file"})

                    from runtime.connected_accounts_v120 import get_connected_accounts_service_v120
                    service = get_connected_accounts_service_v120()
                    rows = list(service.list_accounts("google"))

                    if rows:
                        from accounts.google_tasks_oauth_v123 import upgrade_google_account_for_tasks_v123
                        account = upgrade_google_account_for_tasks_v123(
                            service=service,
                            client_file=str(client_path),
                            account_id=rows[0].account_id,
                        )
                    else:
                        from uuid import uuid4
                        from accounts.google_oauth import google_identity_v120, load_google_client_config_v120
                        from accounts.google_tasks_oauth_v123 import authorize_google_productivity_v123
                        from accounts.model import GOOGLE_SERVICES_V123

                        config = load_google_client_config_v120(client_path)
                        credentials = authorize_google_productivity_v123(config)
                        if not getattr(credentials, "refresh_token", None):
                            return self.send_json(502, {"ok": False, "error": "google_oauth_no_refresh_token"})

                        identity = google_identity_v120(credentials)
                        email = str(identity.get("email") or "Google").strip()
                        credential_ref = "google:" + uuid4().hex
                        service.secrets.set_secret(credential_ref, credentials.to_json())
                        try:
                            account = service.registry.create(
                                provider="google",
                                display_label=email,
                                services=GOOGLE_SERVICES_V123,
                                credential_ref=credential_ref,
                                state="connected",
                                metadata={"email": email},
                            )
                        except Exception:
                            service.secrets.delete_secret(credential_ref)
                            raise

                    services = tuple(str(x).casefold() for x in (getattr(account, "services", ()) or ()))
                    status = {
                        "connected": True,
                        "state": "connected",
                        "account_label": str(getattr(account, "display_label", "Google") or "Google"),
                        "services": list(services),
                        "tasks_supported": "tasks" in services,
                        "calendar_supported": "calendar" in services,
                    }
                    return self.send_json(200, {
                        "ok": True,
                        "account_id": str(getattr(account, "account_id", "") or ""),
                        "account_label": status["account_label"],
                        "status": status,
                    })

                except Exception as exc:
                    try:
                        rt.log("Qt Google OAuth connect failed error=%s", type(exc).__name__, exc_info=True)
                    except Exception:
                        pass
                    return self.send_json(502, {
                        "ok": False,
                        "error": type(exc).__name__,
                        "detail": str(exc)[:260],
                    })

        return QtGoogleConnectHandler

    make_handler._aura_qt_google_connect_fix20 = True
    module.make_handler = make_handler


# AURA_GOOGLE_BIDIRECTIONAL_HOST_FIX21
def _install_qt_google_bidirectional_fix21(module) -> None:
    """Native Qt write bridge for Google Tasks and Google Calendar."""
    previous_make_handler = getattr(module, "make_handler", None)
    if not callable(previous_make_handler):
        raise RuntimeError("shell_host.make_handler unavailable")
    if getattr(previous_make_handler, "_aura_qt_google_bidirectional_fix21", False):
        return

    def make_handler(rt):
        Base = previous_make_handler(rt)

        class QtGoogleWriteHandler(Base):
            @staticmethod
            def _json_body(handler):
                import json
                try:
                    length = int(handler.headers.get("Content-Length", "0") or "0")
                except Exception:
                    length = 0
                if length <= 0 or length > 262144:
                    raise ValueError("invalid_request_size")
                raw = handler.rfile.read(length)
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("json_object_required")
                return payload

            @staticmethod
            def _local_rfc3339(value):
                from datetime import datetime
                text = str(value or "").strip()
                if not text:
                    return ""
                candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
                dt = datetime.fromisoformat(candidate)
                if dt.tzinfo is None:
                    dt = dt.astimezone()
                return dt.isoformat(timespec="seconds")


            # AURA_GOOGLE_TASKS_WRITE_REPAIR_FIX22
# AURA_PRODUCTIVITY_EDIT_ACTIONS_FIX23
            @staticmethod
            def _google_task_due(value):
                """Normalize user input to the date-only RFC3339 Google Tasks accepts."""
                from datetime import datetime

                text = str(value or "").strip()
                if not text:
                    return ""

                # Google Tasks stores only the date component. Accept the formats
                # users naturally type in the Qt field and normalize to UTC midnight.
                candidates = []
                if "T" in text:
                    candidates.append(text.split("T", 1)[0])
                else:
                    candidates.append(text)

                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
                    for candidate in candidates:
                        try:
                            dt = datetime.strptime(candidate.strip(), fmt)
                            return dt.strftime("%Y-%m-%dT00:00:00.000Z")
                        except Exception:
                            pass

                # Also accept valid ISO datetimes and keep only their calendar date.
                try:
                    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
                    dt = datetime.fromisoformat(candidate)
                    return dt.strftime("%Y-%m-%dT00:00:00.000Z")
                except Exception:
                    raise ValueError(
                        "Google Task date format must be YYYY-MM-DD or DD/MM/YYYY"
                    )

            def do_POST(self):
                import urllib.parse
                parsed = urllib.parse.urlparse(self.path)
                path = parsed.path
                routes = {
                    "/api/qt/google/task/create",
                    "/api/qt/google/task/update",
                    "/api/qt/google/task/complete",
                    "/api/qt/google/task/delete",
                    "/api/qt/google/calendar/create",
                    "/api/qt/google/calendar/update",
                    "/api/qt/google/calendar/delete",
                }
                if path not in routes:
                    return super().do_POST()

                if not self.auth():
                    return self.send_json(403, {"ok": False, "error": "forbidden"})

                try:
                    payload = self._json_body(self)

                    from runtime.connected_accounts_v120 import (
                        get_connected_accounts_service_v120,
                    )
                    service = get_connected_accounts_service_v120()

                    if path.startswith("/api/qt/google/task/"):
                        from integrations.google.live_tasks_backend_v123 import (
                            GoogleLiveTasksBackendV123,
                        )
                        backend = GoogleLiveTasksBackendV123(service=service)

                        if path.endswith("/create"):
                            title = str(payload.get("title") or "").strip()[:280]
                            notes = str(payload.get("notes") or "").strip()[:4000]
                            due_raw = str(payload.get("due") or "").strip()[:80]
                            if not title:
                                return self.send_json(
                                    400,
                                    {"ok": False, "error": "task_title_required"},
                                )
                            try:
                                due = self._google_task_due(due_raw)
                            except ValueError as exc:
                                return self.send_json(
                                    400,
                                    {
                                        "ok": False,
                                        "error": "google_task_due_invalid_format",
                                        "detail": str(exc),
                                    },
                                )
                            row = backend.create_task(
                                title=title,
                                notes=notes,
                                due=due,
                                tasklist_id="@default",
                            )
                            return self.send_json(
                                200,
                                {
                                    "ok": True,
                                    "kind": "task_created",
                                    "external_id": str(getattr(row, "task_id", "") or ""),
                                    "title": str(getattr(row, "title", "") or ""),
                                },
                            )

                        task_id = str(payload.get("task_id") or "").strip()
                        if not task_id:
                            return self.send_json(
                                400,
                                {"ok": False, "error": "task_id_required"},
                            )

                        if path.endswith("/update"):
                            title = str(payload.get("title") or "").strip()[:280]
                            notes = str(payload.get("notes") or "").strip()[:4000]
                            due_raw = str(payload.get("due") or "").strip()[:80]
                            if not title:
                                return self.send_json(
                                    400,
                                    {"ok": False, "error": "task_title_required"},
                                )
                            try:
                                due = self._google_task_due(due_raw)
                            except ValueError as exc:
                                return self.send_json(
                                    400,
                                    {
                                        "ok": False,
                                        "error": "google_task_due_invalid_format",
                                        "detail": str(exc),
                                    },
                                )
                            row = backend.update_task(
                                task_id,
                                tasklist_id="@default",
                                title=title,
                                notes=notes,
                                due=due,
                            )
                            return self.send_json(
                                200,
                                {
                                    "ok": True,
                                    "kind": "task_updated",
                                    "external_id": str(
                                        getattr(row, "task_id", "")
                                        or task_id
                                    ),
                                    "title": str(
                                        getattr(row, "title", "")
                                        or title
                                    ),
                                },
                            )

                        if path.endswith("/complete"):
                            row = backend.complete_task(
                                task_id,
                                tasklist_id="@default",
                            )
                            return self.send_json(
                                200,
                                {
                                    "ok": True,
                                    "kind": "task_completed",
                                    "external_id": str(getattr(row, "task_id", "") or task_id),
                                },
                            )

                        backend.delete_task(task_id, tasklist_id="@default")
                        return self.send_json(
                            200,
                            {
                                "ok": True,
                                "kind": "task_deleted",
                                "external_id": task_id,
                            },
                        )

                    from integrations.google.live_calendar_backend_v121 import (
                        GoogleLiveCalendarBackendV121,
                    )
                    backend = GoogleLiveCalendarBackendV121(service=service)

                    if path.endswith("/create"):
                        from datetime import datetime, timedelta
                        title = str(payload.get("title") or "").strip()[:280]
                        description = str(payload.get("description") or "").strip()[:4000]
                        start_text = self._local_rfc3339(payload.get("start"))
                        end_text = self._local_rfc3339(payload.get("end"))

                        if not title or not start_text:
                            return self.send_json(
                                400,
                                {
                                    "ok": False,
                                    "error": "calendar_title_and_start_required",
                                },
                            )

                        start_dt = datetime.fromisoformat(start_text)
                        if end_text:
                            end_dt = datetime.fromisoformat(end_text)
                        else:
                            end_dt = start_dt + timedelta(hours=1)
                            end_text = end_dt.isoformat(timespec="seconds")

                        if end_dt <= start_dt:
                            return self.send_json(
                                400,
                                {
                                    "ok": False,
                                    "error": "calendar_end_must_follow_start",
                                },
                            )

                        row = backend.create_event(
                            title=title,
                            description=description,
                            start=start_text,
                            end=end_text,
                            calendar_id="primary",
                        )
                        return self.send_json(
                            200,
                            {
                                "ok": True,
                                "kind": "calendar_created",
                                "external_id": str(getattr(row, "event_id", "") or ""),
                                "title": str(getattr(row, "title", "") or title),
                            },
                        )

                    event_id = str(payload.get("event_id") or "").strip()
                    if not event_id:
                        return self.send_json(
                            400,
                            {"ok": False, "error": "calendar_event_id_required"},
                        )

                    if path.endswith("/update"):
                        from datetime import datetime, timedelta

                        title = str(payload.get("title") or "").strip()[:280]
                        description = str(payload.get("description") or "").strip()[:4000]
                        start_text = self._local_rfc3339(
                            payload.get("start")
                        )
                        end_text = self._local_rfc3339(
                            payload.get("end")
                        )

                        if not title or not start_text:
                            return self.send_json(
                                400,
                                {
                                    "ok": False,
                                    "error": "calendar_title_and_start_required",
                                },
                            )

                        if not end_text:
                            start_dt = datetime.fromisoformat(start_text)
                            end_text = (
                                start_dt + timedelta(hours=1)
                            ).isoformat(timespec="seconds")

                        row = backend.update_event(
                            event_id=event_id,
                            calendar_id="primary",
                            title=title,
                            description=description,
                            start=start_text,
                            end=end_text,
                        )
                        return self.send_json(
                            200,
                            {
                                "ok": True,
                                "kind": "calendar_updated",
                                "external_id": str(
                                    getattr(row, "event_id", "")
                                    or event_id
                                ),
                                "title": str(
                                    getattr(row, "title", "")
                                    or title
                                ),
                            },
                        )

                    backend.delete_event(event_id)
                    return self.send_json(
                        200,
                        {
                            "ok": True,
                            "kind": "calendar_deleted",
                            "external_id": event_id,
                        },
                    )

                except Exception as exc:
                    try:
                        rt.log(
                            "Qt Google write failed path=%s error=%s",
                            path,
                            type(exc).__name__,
                            exc_info=True,
                        )
                    except Exception:
                        pass
                    return self.send_json(
                        502,
                        {
                            "ok": False,
                            "error": type(exc).__name__,
                            "detail": str(exc)[:260],
                        },
                    )

        return QtGoogleWriteHandler

    make_handler._aura_qt_google_bidirectional_fix21 = True
    module.make_handler = make_handler

def main() -> int:
    parser = argparse.ArgumentParser(
        description="AURA POC6B headless compatibility host"
    )
    parser.add_argument("--aura-root", default="")
    parser.add_argument("--ui-root", default="")
    args = parser.parse_args()

    poc_root = Path(__file__).resolve().parents[1]
    core = _find_core(args.aura_root)
    ui_root = _find_ui_root(core, args.ui_root)
    shell = ui_root / "tools" / "shell_host.py"

    os.environ["AURA_ROOT"] = str(core)
    os.environ["AURA_UI_ROOT"] = str(ui_root)
    os.environ["AURA_UI_HOST"] = "qt-native-headless-poc6b"
    os.environ["AURA_POC6B_NO_BROWSER"] = "1"

    if str(core) not in sys.path:
        sys.path.insert(0, str(core))

    spec = importlib.util.spec_from_file_location(
        "aura_poc6b_validated_shell_host",
        shell,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Impossible de charger shell_host.py")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # POC6E: typed Qt messages use the full text-generation contract while
    # microphone turns keep the validated voice-generation contract.
    _install_native_text_contract(core, poc_root)
    _install_qt_google_bridge(module)
    _install_qt_google_connect_bridge_fix20(module)
    _install_qt_google_bidirectional_fix21(module)

    original_launch_browser = getattr(module, "launch_browser", None)
    if not callable(original_launch_browser):
        raise RuntimeError("Contrat launch_browser introuvable dans shell_host.py")

    def no_browser(rt):
        rt.browser = None
        try:
            rt.log(
                "AURA POC6B native headless mode: Chromium launch suppressed; "
                "Qt Quick is the only visible shell"
            )
        except Exception:
            pass

    module.launch_browser = no_browser

    _write_status(
        poc_root,
        state="starting",
        aura_root=str(core),
        ui_root=str(ui_root),
        shell_host=str(shell),
    )

    old_argv = list(sys.argv)
    try:
        sys.argv = [
            str(shell),
            "--core",
            str(core),
            "--ui-root",
            str(ui_root),
        ]
        _write_status(
            poc_root,
            state="running",
            aura_root=str(core),
            ui_root=str(ui_root),
            shell_host=str(shell),
        )
        return int(module.main() or 0)
    finally:
        sys.argv = old_argv
        try:
            _write_status(
                poc_root,
                state="stopped",
                aura_root=str(core),
                ui_root=str(ui_root),
                shell_host=str(shell),
            )
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
