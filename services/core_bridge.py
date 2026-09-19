"""AURA P0.6.2.2 — Core Service Bridge Foundation.

This module is intentionally thin: it exposes existing AURA engines through
stable service contracts without duplicating Voice, Research, Memory, Tasks or
Document logic.  MainWindow remains a compatibility host during the migration,
but new Three.js surfaces can start consuming Core services directly.
"""
from __future__ import annotations

import hashlib
import json
import re
import logging
import queue
import threading
import time
from datetime import datetime
from pathlib import Path
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any

from core.event_bus import event_bus
from services.document_analysis import DocumentAnalysisError, extract_document
from services.local_document_intelligence import (
    LocalDocumentIntelligenceError,
    analyze_local_document,
)
from services.local_project_intelligence import (
    LocalProjectIntelligenceError,
    ProjectSource,
    analyze_local_project,
)

logger = logging.getLogger("aura.services.bridge")


def _safe(value: Any, depth: int = 0) -> Any:
    if depth > 7:
        return None
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if is_dataclass(value):
        try:
            return _safe(asdict(value), depth + 1)
        except Exception:
            return str(value)[:300]
    if isinstance(value, dict):
        return {str(k)[:80]: _safe(v, depth + 1) for k, v in list(value.items())[:120]}
    if isinstance(value, (list, tuple, set)):
        return [_safe(v, depth + 1) for v in list(value)[:200]]
    return str(value)[:500]


def _emit(name: str, payload: dict[str, Any] | None = None) -> None:
    """Publish one typed Runtime-v2 event. No network side effect happens here."""
    try:
        event_bus.runtime_event.emit(str(name), _safe(payload or {}))
    except Exception:
        logger.debug("Service event unavailable name=%s", name, exc_info=True)


class VoiceService:
    """Stable facade over the already-proven VoiceEngine.

    Microphone capture still uses the legacy MainWindow flow in P0.6.2.2 because
    that path also owns STT worker scheduling and chat handoff.  TTS/stop/status
    can already be consumed without routing through MainWindow.
    """

    def __init__(self, aura_core):
        self.core = aura_core
        self.engine = aura_core.voice_engine
        self._speak_lock = threading.Lock()

    def status(self) -> dict[str, Any]:
        try:
            st = self.engine.status()
            payload = _safe(st)
            if not isinstance(payload, dict):
                payload = {"status": str(payload)}
        except Exception as exc:
            payload = {"error": type(exc).__name__}
        try:
            payload["output_backend"] = str(self.engine.output_backend_kind())
        except Exception:
            payload.setdefault("output_backend", "unknown")
        try:
            payload["xtts_loaded"] = bool(self.engine.xtts_model_loaded())
        except Exception:
            payload["xtts_loaded"] = False
        payload["microphone_control"] = "legacy-mainwindow-p0622"
        payload["service"] = "voice"
        return payload

    def stop_speaking(self) -> None:
        self.engine.stop_speaking()
        _emit("voice.service.stopped", {"source": "core-service"})

    def speak(self, text: str, *, source: str = "core-service") -> None:
        text = str(text or "").strip()
        if not text:
            raise ValueError("empty_speech")
        _emit("voice.service.started", {"source": source, "chars": len(text)})
        try:
            self.engine.speak(text)
        except Exception as exc:
            _emit("voice.service.error", {"source": source, "error": type(exc).__name__})
            raise
        else:
            _emit("voice.service.completed", {"source": source, "chars": len(text)})


class ResearchService:
    """Direct, non-UI facade over AURA's existing InternetToolManager path.

    Planning/security authorization happens on the Qt/Core main thread via
    :meth:`start`. Network execution happens on a worker. :meth:`poll` must be
    called from the main thread so AuraCore.handle_tool_result can safely commit
    history/continuity using the thread-affine SQLite connection.
    """

    def __init__(self, aura_core):
        self.core = aura_core
        self._lock = threading.Lock()
        self._busy = False
        self._results: queue.Queue = queue.Queue(maxsize=4)
        self._sequence = 0

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._busy)

    def _set_busy(self, value: bool) -> None:
        with self._lock:
            self._busy = bool(value)

    def start(self, query: str) -> dict[str, Any]:
        query = " ".join(str(query or "").replace("\x00", " ").split()).strip()[:800]
        if not query:
            return {"accepted": False, "error": "empty_query"}
        if self.busy:
            return {"accepted": False, "error": "research_busy"}

        # Direct service calls are explicit by definition. Reuse the official
        # planner/security path rather than constructing an unchecked ToolPlan.
        planner_text = query
        try:
            from tools.search_intent import is_explicit_search_request
            explicit = bool(is_explicit_search_request(query))
        except Exception:
            explicit = False
        if not explicit:
            planner_text = f"Fais des recherches sur {query}"

        try:
            plan = self.core.plan_internet_tool(planner_text)
        except Exception as exc:
            logger.exception("Research planning failed")
            _emit("research.error", {"query": query, "stage": "planning", "error": type(exc).__name__})
            return {"accepted": False, "error": "planning_failed"}

        if plan is None or str(getattr(plan, "name", "") or "") != "web_search":
            _emit("research.error", {"query": query, "stage": "planning", "error": "research_plan_unavailable"})
            return {"accepted": False, "error": "research_plan_unavailable"}

        self._sequence += 1
        request_id = f"research-{self._sequence}"

        # P0.6.2.2.1: direct ResearchService turns must own the visible user
        # message too.  The canonical history commit remains in
        # handle_tool_result(), avoiding duplicate conversation-history rows.
        try:
            event_bus.user_message.emit(query)
        except Exception:
            logger.debug("Research user_message event unavailable", exc_info=True)

        self._set_busy(True)
        try:
            self.core.set_state("SEARCHING", reason="research_service")
        except Exception:
            pass
        args = dict(getattr(plan, "args", {}) or {})
        _emit("research.started", {
            "request_id": request_id,
            "query": query,
            "engine": str(args.get("engine") or "free-web-search"),
            "requested_count": int(args.get("count") or 0),
        })

        def worker():
            started = time.perf_counter()
            _emit("research.searching", {"request_id": request_id, "query": query})
            try:
                result = self.core.execute_internet_tool(plan)
                self._results.put((request_id, query, plan, result, started, None), timeout=1.0)
            except Exception as exc:
                logger.exception("Research execution failed")
                try:
                    self._results.put((request_id, query, plan, None, started, exc), timeout=1.0)
                except Exception:
                    self._set_busy(False)
                    _emit("research.error", {"request_id": request_id, "query": query, "stage": "execution", "error": type(exc).__name__})

        threading.Thread(target=worker, daemon=True, name="AuraResearchService").start()
        return {"accepted": True, "request_id": request_id}

    def poll(self) -> int:
        handled = 0
        while handled < 4:
            try:
                request_id, query, plan, result, started, exc = self._results.get_nowait()
            except queue.Empty:
                break
            handled += 1
            try:
                if exc is not None or result is None:
                    _emit("research.error", {
                        "request_id": request_id, "query": query, "stage": "execution",
                        "error": type(exc).__name__ if exc is not None else "unknown_error",
                    })
                    try:
                        self.core.set_state("IDLE", reason="research_service_error")
                    except Exception:
                        pass
                    continue

                sources = []
                for src in tuple(getattr(result, "sources", ()) or ())[:24]:
                    sources.append({
                        "name": str(getattr(src, "name", "") or "")[:220],
                        "host": str(getattr(src, "host", "") or "")[:180],
                        "url": str(getattr(src, "url", "") or "")[:1200],
                        "checked_at": str(getattr(src, "checked_at", "") or "")[:80],
                    })
                if sources:
                    _emit("research.sources", {"request_id": request_id, "query": query, "sources": sources})

                # Canonical commit: history, continuity, state and aura_message.
                self.core.handle_tool_result(query, result, plan=plan)
                data = dict(getattr(result, "data", {}) or {})
                _emit("research.completed", {
                    "request_id": request_id,
                    "query": query,
                    "ok": bool(getattr(result, "ok", False)),
                    "response": str(getattr(result, "response", "") or "")[:16000],
                    "source": str(getattr(result, "source", "") or "")[:120],
                    "category": str(getattr(result, "category", "") or "")[:80],
                    "item_count": int(getattr(result, "item_count", 0) or 0),
                    "expected_items": int(getattr(result, "expected_items", 0) or 0),
                    "complete": bool(getattr(result, "complete", True)),
                    "backend": str(data.get("backend") or "")[:80],
                    "backend_label": str(data.get("backend_label") or "")[:120],
                    "synthesis": str(data.get("synthesis") or "")[:80],
                    "latency_seconds": round(time.perf_counter() - started, 3),
                })
            except Exception as finalize_exc:
                logger.exception("Research finalize failed")
                _emit("research.error", {
                    "request_id": request_id, "query": query, "stage": "finalize",
                    "error": type(finalize_exc).__name__,
                })
            finally:
                self._set_busy(False)
        return handled


class WeatherService:
    """Passive current-location weather facade."""

    def __init__(self, aura_core):
        self.core = aura_core
        self._lock = threading.Lock()
        self._busy = False
        self._results: queue.Queue = queue.Queue(maxsize=3)
        self._sequence = 0

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._busy)

    def _set_busy(self, value: bool) -> None:
        with self._lock:
            self._busy = bool(value)

    def start_current(self, latitude: float, longitude: float, *, accuracy: float | None = None) -> dict[str, Any]:
        try:
            lat, lon = float(latitude), float(longitude)
        except (TypeError, ValueError):
            return {"accepted": False, "error": "invalid_coordinates"}
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return {"accepted": False, "error": "invalid_coordinates"}
        if self.busy:
            return {"accepted": False, "error": "weather_busy"}
        self._sequence += 1
        request_id = f"weather-{self._sequence}"
        self._set_busy(True)

        def worker():
            started = time.perf_counter()
            try:
                result = self.core.internet_tools.weather.execute_coordinates(lat, lon)
                self._results.put((request_id, lat, lon, accuracy, result, started, None), timeout=1.0)
            except Exception as exc:
                self._results.put((request_id, lat, lon, accuracy, None, started, exc), timeout=1.0)

        threading.Thread(target=worker, daemon=True, name="AuraCurrentWeatherService").start()
        return {"accepted": True, "request_id": request_id}

    def poll(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        while True:
            try:
                request_id, lat, lon, accuracy, result, started, exc = self._results.get_nowait()
            except queue.Empty:
                break
            try:
                if exc is not None or result is None:
                    payloads.append({"location":"Position actuelle","place_label":"Position actuelle","condition":"MÉTÉO INDISPONIBLE","raw":"AURA n'a pas pu récupérer la météo de la position actuelle.","source":"WEATHER ERROR"})
                    continue
                data = dict(getattr(result, "data", {}) or {})
                data.setdefault("location", "Position actuelle")
                data.setdefault("place_label", "Position actuelle")
                data["latitude"] = lat
                data["longitude"] = lon
                data["accuracy_m"] = round(float(accuracy), 1) if accuracy is not None else None
                data["location_source"] = "device_geolocation"
                data["current_position"] = True
                data["request_id"] = request_id
                payloads.append(_safe(data))
            finally:
                self._set_busy(False)
        return payloads


class FileService:
    """Session-scoped document loader exposed to the Three.js shell.

    P0.6.2.3 deliberately reuses ``services.document_analysis`` for extraction.
    The mature 26.8.x document LLM fast lane remains hosted by MainWindow for
    this patch; the shell synchronises ``active_context`` into that compatibility
    host. This gives Three.js attachments now without copying the analysis engine.
    """

    def __init__(self, aura_core):
        self.core = aura_core
        self._lock = threading.Lock()
        self._busy = False
        self._results: queue.Queue = queue.Queue(maxsize=2)
        self._active = None
        self._revision = 0

    @property
    def busy(self) -> bool:
        with self._lock:
            return bool(self._busy)

    @property
    def active_context(self):
        with self._lock:
            return self._active

    @property
    def revision(self) -> int:
        with self._lock:
            return int(self._revision)

    def status(self) -> dict[str, Any]:
        active = self.active_context
        payload = {
            "ok": True,
            "service": "files",
            "busy": self.busy,
            "active": bool(active),
            "analysis_route": "existing-26.8-document-fast-lane",
        }
        if active is not None:
            payload.update({
                "name": str(getattr(active, "name", "") or "")[:260],
                "mime_type": str(getattr(active, "mime_type", "") or "")[:120],
                "size_bytes": int(getattr(active, "size_bytes", 0) or 0),
                "text_chars": int(getattr(active, "text_chars", 0) or 0),
                "truncated": bool(getattr(active, "truncated", False)),
                "native_required": bool(getattr(active, "native_required", False)),
                "meta": str(getattr(active, "meta", "") or "")[:300],
            })
        return payload

    def load(self, path: str) -> dict[str, Any]:
        path = str(path or "").strip()
        if not path:
            return {"accepted": False, "error": "empty_file_path"}
        if self.busy:
            return {"accepted": False, "error": "file_service_busy"}
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            return {"accepted": False, "error": "file_not_found"}
        with self._lock:
            self._busy = True
        _emit("file.loading", {"name": p.name[:260], "size_bytes": int(p.stat().st_size)})

        def worker():
            try:
                from services.document_analysis import extract_document
                document = extract_document(str(p))
                self._results.put((document, None), timeout=1.0)
            except Exception as exc:
                logger.exception("File extraction failed path=%r", str(p))
                try:
                    self._results.put((None, exc), timeout=1.0)
                except Exception:
                    with self._lock:
                        self._busy = False
                    _emit("file.error", {"name": p.name[:260], "stage": "extract", "error": type(exc).__name__})

        threading.Thread(target=worker, daemon=True, name="AuraFileServiceLoad").start()
        return {"accepted": True, "name": p.name}

    def clear(self) -> dict[str, Any]:
        previous = self.active_context
        with self._lock:
            self._active = None
            self._revision += 1
        _emit("file.cleared", {"name": str(getattr(previous, "name", "") or "")[:260]})
        return {"ok": True}

    def poll(self) -> int:
        handled = 0
        while handled < 2:
            try:
                document, exc = self._results.get_nowait()
            except queue.Empty:
                break
            handled += 1
            try:
                if exc is not None or document is None:
                    _emit("file.error", {
                        "stage": "extract",
                        "error": type(exc).__name__ if exc is not None else "unknown_error",
                        "message": str(exc or "Impossible de charger le document.")[:300],
                    })
                    continue
                with self._lock:
                    self._active = document
                    self._revision += 1
                _emit("file.ready", self.status())
            finally:
                with self._lock:
                    self._busy = False
        return handled


class ProductivityService:
    """Direct main-thread facade over Tasks, Reminders and Notes managers.

    The existing SQLite managers remain the source of truth. The service only
    exposes bounded CRUD operations and a cached read snapshot to Three.js.
    """

    def __init__(self, aura_core):
        self.core = aura_core
        self._snapshot: dict[str, Any] = {"tasks": [], "reminders": [], "notes": []}
        self._snapshot_key = ""
        self._last_refresh = 0.0
        self._last_due_check = 0.0
        self._due_check_interval = 1.0
        self.refresh(force=True, emit=False)

    @staticmethod
    def _bounded_text(value: Any, limit: int) -> str:
        return " ".join(str(value or "").replace("\\x00", " ").split()).strip()[:limit]

    def _read_snapshot(self) -> dict[str, Any]:
        return {
            "tasks": _safe(self.core.task_manager.list_tasks(limit=40)),
            "reminders": _safe(self.core.reminder_manager.list_reminders(include_done=False, limit=40)),
            "notes": _safe(self.core.notes_manager.list_notes(limit=30)),
        }

    def refresh(self, *, force: bool = False, emit: bool = True) -> dict[str, Any]:
        now = time.monotonic()
        if not force and now - self._last_refresh < 0.85:
            return self.snapshot()
        self._last_refresh = now
        data = self._read_snapshot()
        key = json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        changed = key != self._snapshot_key
        self._snapshot = data
        self._snapshot_key = key
        if changed and emit:
            _emit("productivity.snapshot", self.snapshot())
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "ok": True,
            "service": "productivity",
            "tasks": _safe(self._snapshot.get("tasks") or []),
            "reminders": _safe(self._snapshot.get("reminders") or []),
            "notes": _safe(self._snapshot.get("notes") or []),
        }

    def create_task(self, title: str, *, due_date: str = "") -> dict[str, Any]:
        title = self._bounded_text(title, 280)
        due_date = self._bounded_text(due_date, 64)
        if not title:
            raise ValueError("empty_task_title")
        task_id = int(self.core.task_manager.create_task(title, due_date=due_date or None))
        task = self.core.task_manager.get_task(task_id) or {"id": task_id, "title": title}
        _emit("task.created", {"task": _safe(task), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": True, "task": _safe(task)}

    def complete_task(self, identifier: str) -> dict[str, Any]:
        identifier = self._bounded_text(identifier, 280)
        if not identifier:
            raise ValueError("empty_task_identifier")
        task = self.core.task_manager.complete_task(identifier)
        if task is None:
            return {"ok": False, "error": "task_not_found"}
        _emit("task.completed", {"task": _safe(task), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": True, "task": _safe(task)}

    def create_reminder(self, content: str, trigger_at: str) -> dict[str, Any]:
        content = self._bounded_text(content, 500)
        trigger_at = self._bounded_text(trigger_at, 80)
        if not content:
            raise ValueError("empty_reminder_content")
        try:
            when = datetime.fromisoformat(trigger_at)
        except Exception as exc:
            raise ValueError("invalid_reminder_datetime") from exc
        reminder_id = int(self.core.reminder_manager.create_reminder(content, when))
        reminder = self.core.reminder_manager.get_reminder(reminder_id) or {"id": reminder_id, "content": content, "trigger_at": trigger_at}
        _emit("reminder.created", {"reminder": _safe(reminder), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": True, "reminder": _safe(reminder)}

    def delete_reminder(self, reminder_id: int) -> dict[str, Any]:
        rid = int(reminder_id)
        reminder = self.core.reminder_manager.get_reminder(rid)
        ok = bool(self.core.reminder_manager.delete_reminder(rid))
        if ok:
            _emit("reminder.deleted", {"reminder": _safe(reminder or {"id": rid}), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": ok, "error": "" if ok else "reminder_not_found"}

    def create_note(self, content: str, *, title: str = "") -> dict[str, Any]:
        content = str(content or "").replace("\\x00", " ").strip()[:8000]
        title = self._bounded_text(title, 220)
        if not content:
            raise ValueError("empty_note_content")
        note_id = int(self.core.notes_manager.create_note(content, title=title or None))
        note = self.core.notes_manager.get_note(note_id) or {"id": note_id, "title": title, "content": content}
        _emit("note.created", {"note": _safe(note), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": True, "note": _safe(note)}

    def delete_note(self, note_id: int) -> dict[str, Any]:
        nid = int(note_id)
        note = self.core.notes_manager.get_note(nid)
        ok = bool(self.core.notes_manager.delete_note(nid))
        if ok:
            _emit("note.deleted", {"note": _safe(note or {"id": nid}), "source": "threejs-productivity"})
        self.refresh(force=True)
        return {"ok": ok, "error": "" if ok else "note_not_found"}

    def _poll_due_reminders(self) -> list[dict[str, Any]]:
        """Check and atomically retire due reminders without a Qt scheduler.

        P0.6.2.5 keeps SQLite ReminderManager as the source of truth. The
        Core Service Bridge only performs a throttled due check on its normal
        runtime poll, then hands triggered reminders to the shell for the
        existing Conversation + Windows notification presentation.
        """
        now = time.monotonic()
        if now - self._last_due_check < self._due_check_interval:
            return []
        self._last_due_check = now

        try:
            due = list(self.core.reminder_manager.get_due_reminders() or [])
        except Exception as exc:
            logger.warning("Reminder runtime due-check failed error=%s", type(exc).__name__)
            _emit("reminder.runtime.error", {"stage": "due-check", "error": type(exc).__name__})
            return []

        triggered: list[dict[str, Any]] = []
        for reminder in due[:20]:
            try:
                reminder_id = int(reminder.get("id"))
            except Exception:
                continue
            try:
                marked = bool(self.core.reminder_manager.mark_done(reminder_id))
            except Exception as exc:
                logger.warning("Reminder runtime mark-done failed id=%s error=%s", reminder_id, type(exc).__name__)
                _emit("reminder.runtime.error", {
                    "stage": "mark-done",
                    "reminder_id": reminder_id,
                    "error": type(exc).__name__,
                })
                continue
            if not marked:
                continue
            item = dict(reminder)
            triggered.append(item)
            _emit("reminder.triggered", {
                "reminder": _safe(item),
                "source": "core-productivity-runtime",
            })

        if triggered:
            self.refresh(force=True, emit=True)
        return [_safe(item) for item in triggered]

    def poll(self) -> list[dict[str, Any]]:
        triggered = self._poll_due_reminders()
        self.refresh(force=False, emit=True)
        return triggered


class MemoryService:
    """Three.js facade over AURA's existing local MemoryManager.

    All SQLite reads/writes stay on the Qt/Core thread. HTTP handlers only read
    this service's cached snapshots, avoiding cross-thread SQLite access.
    """

    def __init__(self, aura_core):
        self.core = aura_core
        self._snapshot: dict[str, Any] = {}
        self._snapshot_sensitive: dict[str, Any] = {}
        self._last_refresh = 0.0
        self._refresh_interval = 0.75
        self.refresh(force=True, emit=False)

    @staticmethod
    def _record_payload(manager, record) -> dict[str, Any]:
        try:
            source_label = manager.source_label(record)
        except Exception:
            source_label = str(getattr(record, "source", "") or "")
        return {
            "id": int(getattr(record, "id", 0) or 0),
            "content": str(getattr(record, "content", "") or "")[:1800],
            "type": str(getattr(record, "type", "fact") or "fact")[:40],
            "importance": int(getattr(record, "importance", 1) or 1),
            "source": str(getattr(record, "source", "") or "")[:80],
            "source_label": str(source_label or "")[:220],
            "confidence": round(float(getattr(record, "confidence", 1.0) or 0.0), 3),
            "created_at": str(getattr(record, "created_at", "") or "")[:80],
            "updated_at": str(getattr(record, "updated_at", "") or "")[:80],
            "last_accessed_at": str(getattr(record, "last_accessed_at", "") or "")[:80],
            "access_count": int(getattr(record, "access_count", 0) or 0),
            "is_sensitive": bool(getattr(record, "is_sensitive", False)),
            "tags": str(getattr(record, "tags", "") or "")[:300],
        }

    def _build_snapshot(self, *, include_sensitive: bool) -> dict[str, Any]:
        from config.settings import settings
        manager = self.core.memory_manager
        records = manager.list_memories(
            200,
            include_sensitive=include_sensitive,
            track=False,
        )
        try:
            context = manager.explain_last_context()
        except Exception:
            context = []
        if not include_sensitive:
            context = [r for r in context if not bool(getattr(r, "is_sensitive", False))]

        active_total = int(
            manager.db.conn.execute(
                "SELECT COUNT(*) FROM memories WHERE status='ACTIVE'"
            ).fetchone()[0]
        )
        sensitive_total = int(
            manager.db.conn.execute(
                "SELECT COUNT(*) FROM memories WHERE status='ACTIVE' AND is_sensitive=1"
            ).fetchone()[0]
        )
        return {
            "ok": True,
            "enabled": bool(settings.MEMORY_ENABLED),
            "auto_capture": bool(settings.MEMORY_AUTO_CAPTURE),
            "allow_sensitive_context": bool(settings.MEMORY_ALLOW_SENSITIVE_CONTEXT),
            "private_mode": bool(manager.private_mode),
            "count": active_total,
            "sensitive_count": sensitive_total,
            "include_sensitive": bool(include_sensitive),
            "records": [
                self._record_payload(manager, record)
                for record in records
            ],
            "context": [
                self._record_payload(manager, record)
                for record in context[:8]
            ],
        }

    def refresh(self, *, force: bool = False, emit: bool = True) -> None:
        now = time.monotonic()
        if not force and now - self._last_refresh < self._refresh_interval:
            return
        self._last_refresh = now
        try:
            normal = self._build_snapshot(include_sensitive=False)
            sensitive = self._build_snapshot(include_sensitive=True)
        except Exception as exc:
            logger.warning("Memory snapshot refresh failed error=%s", type(exc).__name__)
            _emit("memory.error", {"stage": "snapshot", "error": type(exc).__name__})
            return
        changed = json.dumps(normal, sort_keys=True, ensure_ascii=False) != json.dumps(
            self._snapshot, sort_keys=True, ensure_ascii=False
        )
        self._snapshot = normal
        self._snapshot_sensitive = sensitive
        if emit and changed:
            _emit("memory.snapshot", {
                "count": int(normal.get("count", 0) or 0),
                "sensitive_count": int(normal.get("sensitive_count", 0) or 0),
                "private_mode": bool(normal.get("private_mode")),
                "auto_capture": bool(normal.get("auto_capture")),
            })

    def snapshot(self, *, include_sensitive: bool = False) -> dict[str, Any]:
        src = self._snapshot_sensitive if include_sensitive else self._snapshot
        return _safe(dict(src or {"ok": False, "error": "memory_snapshot_unavailable"}))

    def remember(
        self,
        content: str,
        *,
        memory_type: str = "",
        importance: int = 3,
    ) -> dict[str, Any]:
        content = str(content or "").replace("\x00", " ").strip()[:1800]
        if not content:
            raise ValueError("empty_memory")
        allowed_types = {"", "fact", "preference", "project", "goal", "habit"}
        memory_type = str(memory_type or "").casefold().strip()
        if memory_type not in allowed_types:
            raise ValueError("invalid_memory_type")
        importance = max(1, min(5, int(importance or 3)))
        record, created = self.core.memory_manager.remember(
            content,
            memory_type=memory_type or None,
            importance=importance,
            source="explicit_user",
            confidence=1.0,
            allow_sensitive=True,
        )
        payload = self._record_payload(self.core.memory_manager, record)
        _emit("memory.created" if created else "memory.updated", {
            "memory": payload,
            "source": "threejs-memory",
        })
        self.refresh(force=True, emit=True)
        return {"ok": True, "created": bool(created), "memory": payload}

    def forget(self, memory_id: int) -> dict[str, Any]:
        memory_id = int(memory_id)
        record = self.core.memory_manager.get(memory_id)
        if record is None:
            return {"ok": False, "error": "memory_not_found"}
        removed = self.core.memory_manager.forget(str(memory_id), all_matches=False)
        ok = bool(removed)
        if ok:
            _emit("memory.deleted", {
                "memory": self._record_payload(self.core.memory_manager, record),
                "source": "threejs-memory",
            })
        self.refresh(force=True, emit=True)
        return {"ok": ok, "error": "" if ok else "memory_delete_failed"}

    def set_private_mode(self, enabled: bool) -> dict[str, Any]:
        self.core.memory_manager.set_private_mode(bool(enabled))
        _emit("memory.private_mode", {
            "enabled": bool(enabled),
            "source": "threejs-memory",
        })
        self.refresh(force=True, emit=True)
        return {"ok": True, "private_mode": bool(enabled)}

    def clear_profile(self) -> dict[str, Any]:
        counts = self.core.memory_manager.forget_all_profile_data()
        _emit("memory.profile_cleared", {
            "counts": _safe(counts),
            "source": "threejs-memory",
        })
        self.refresh(force=True, emit=True)
        return {"ok": True, "counts": _safe(counts)}

    def poll(self) -> None:
        self.refresh(force=False, emit=True)


@dataclass(frozen=True)
class AuthorizedProjectAnalysisPlan:
    """Internal authority object for bounded multi-file local project intelligence."""

    action: str
    analysis_mode: str
    query: str
    folder_id: str
    folder_label: str
    folder_path: str
    file_ids: tuple[str, ...]
    risk: str
    permission: str
    authorized: bool
    created_at: float


@dataclass(frozen=True)
class AuthorizedFileAnalysisPlan:
    """Internal authority object for deterministic local document intelligence."""

    action: str
    analysis_mode: str
    query: str
    folder_id: str
    file_id: str
    folder_label: str
    name: str
    path: str
    risk: str
    permission: str
    authorized: bool
    created_at: float


@dataclass(frozen=True)
class AuthorizedFileReadPlan:
    """Internal authority object for one direct-child file in an authorized folder."""

    action: str
    folder_id: str
    file_id: str
    folder_label: str
    name: str
    path: str
    risk: str
    permission: str
    authorized: bool
    created_at: float


@dataclass(frozen=True)
class AuthorizedFolderActionPlan:
    """Internal authority object for one action over an authorized folder id."""

    action: str
    folder_id: str
    label: str
    path: str
    risk: str
    permission: str
    authorized: bool
    created_at: float


@dataclass(frozen=True)
class SafeDesktopActionPlan:
    """Internal, non-serializable authority object for one fixed safe-app launch."""

    action: str
    app_id: str
    label: str
    risk: str
    permission: str
    authorized: bool
    created_at: float


class SystemService:
    """Read-only local system/runtime telemetry for the Three.js SYS workspace.

    P0.6.5.0 exposes only the already-proven fixed safe application launcher.
    SecurityPolicyEngine remains authoritative. Arbitrary processes, paths,
    arguments, filesystem mutation and system changes stay locked.
    """

    _CAPABILITY_ACTIONS = (
        "SYSTEM_STATUS",
        "OPEN_SAFE_APP",
        "AUTHORIZE_FOLDER",
        "REVOKE_AUTHORIZED_FOLDER",
        "LIST_AUTHORIZED_FOLDER",
        "OPEN_AUTHORIZED_FOLDER",
        "READ_AUTHORIZED_FILE",
        "ANALYZE_AUTHORIZED_FILE",
        "ANALYZE_AUTHORIZED_PROJECT",
        "RUN_PROGRAM",
        "DELETE_FILE",
        "INSTALL_SOFTWARE",
        "MODIFY_SYSTEM",
        "DISABLE_SECURITY",
        "READ_SECRET",
        "LOCATION_CURRENT",
    )

    _SAFE_APPS: dict[str, dict[str, Any]] = {
        "calculator": {
            "label": "Calculatrice",
            "command": ("calc.exe",),
            "aliases": ("calculatrice", "calculator", "calc"),
        },
        "notepad": {
            "label": "Bloc-notes",
            "command": ("notepad.exe",),
            "aliases": ("bloc notes", "bloc-notes", "notepad", "editeur de texte", "éditeur de texte"),
        },
        "explorer": {
            "label": "Explorateur de fichiers",
            "command": ("explorer.exe",),
            "aliases": ("explorateur", "explorateur de fichiers", "file explorer", "fichiers"),
        },
        "paint": {
            "label": "Paint",
            "command": ("mspaint.exe",),
            "aliases": ("paint", "mspaint"),
        },
    }

    def __init__(self, aura_core):
        self.core = aura_core
        self._snapshot: dict[str, Any] = {}
        self._last_refresh = 0.0
        self._refresh_interval = 2.5
        self._authorized_folders: list[dict[str, Any]] = []
        self._last_folder_listing: dict[str, Any] = {}
        self._last_folder_action: dict[str, Any] = {}
        self._last_file_read: dict[str, Any] = {}
        self._last_file_analysis: dict[str, Any] = {}
        self._last_project_analysis: dict[str, Any] = {}
        self._load_authorized_folder_registry()

        # P0.6.2.8.2 — integrity guard. If the fixed allowlist ever leaves
        # SystemService again, fail loudly instead of silently falling back
        # to the LLM route.
        if not isinstance(getattr(self, "_SAFE_APPS", None), dict) or not self._SAFE_APPS:
            raise RuntimeError("system_safe_app_allowlist_missing")

        self._status_decision = self.core.security_engine.authorize("SYSTEM_STATUS", {})
        self.refresh(force=True, emit=False)

    @staticmethod
    def _pct(value: float) -> float:
        return round(max(0.0, min(100.0, float(value or 0.0))), 1)

    @staticmethod
    def _normalize_command_text(text: str) -> str:
        import re
        import unicodedata
        value = unicodedata.normalize("NFKD", str(text or ""))
        value = "".join(ch for ch in value if not unicodedata.combining(ch))
        value = value.casefold().replace("’", "'").replace("-", " ")
        # P0.6.2.8.1 — conversational commands nearly always contain terminal
        # punctuation ("ouvre la calculatrice."). Token matching must compare
        # words, not raw punctuation. Keep letters/digits/apostrophes only.
        value = re.sub(r"[^a-z0-9' ]+", " ", value)
        return " ".join(value.split())

    _AUTHORIZED_FILE_EXTENSIONS = frozenset({
        ".txt", ".md", ".log", ".py", ".json", ".csv", ".tsv", ".xml",
        ".yaml", ".yml", ".ini", ".cfg", ".toml", ".html", ".htm",
        ".pdf", ".docx", ".pptx", ".xlsx",
    })
    _AUTHORIZED_FILE_MAX_BYTES = 8 * 1024 * 1024
    _AUTHORIZED_FILE_MAX_CHARS = 60000
    _AUTHORIZED_FILE_UI_CHARS = 18000
    # P0.6.5.4 aggregate project limits. Direct children only.
    _AUTHORIZED_PROJECT_MAX_FILES = 24
    _AUTHORIZED_PROJECT_MAX_TOTAL_BYTES = 24 * 1024 * 1024
    _AUTHORIZED_PROJECT_MAX_TOTAL_CHARS = 240000
    _AUTHORIZED_PROJECT_MAX_RESULT_CHARS = 12000

    @staticmethod
    def _authorized_file_id(folder_id: str, name: str) -> str:
        payload = (
            str(folder_id or "").casefold().strip()
            + "\x00"
            + str(name or "").casefold()
        ).encode("utf-8", errors="ignore")
        return hashlib.sha256(payload).hexdigest()[:16]

    def _resolve_authorized_file(
        self,
        folder_id: str,
        file_id: str,
    ) -> dict[str, Any] | None:
        """Resolve one direct-child regular file using opaque ids only."""
        import os

        folder = self._folder_by_id(folder_id)
        if folder is None:
            return None
        try:
            root = Path(str(folder.get("path") or "")).resolve(strict=True)
        except Exception:
            return None
        if not root.is_dir():
            return None

        expected = str(file_id or "").casefold().strip()
        if len(expected) != 16 or any(ch not in "0123456789abcdef" for ch in expected):
            return None

        try:
            with os.scandir(root) as scan:
                for entry in scan:
                    try:
                        if entry.is_symlink():
                            continue
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        name = str(entry.name)
                        if self._authorized_file_id(folder_id, name) != expected:
                            continue
                        ext = Path(name).suffix.casefold()
                        if ext not in self._AUTHORIZED_FILE_EXTENSIONS:
                            return None
                        candidate = (root / name).resolve(strict=True)
                        if candidate.parent != root:
                            return None
                        return {
                            "folder_id": str(folder.get("id") or ""),
                            "folder_label": str(folder.get("label") or "Projet"),
                            "file_id": expected,
                            "name": name,
                            "path": str(candidate),
                            "extension": ext,
                            "size_bytes": int(candidate.stat().st_size),
                        }
                    except Exception:
                        continue
        except Exception:
            return None
        return None

    def plan_authorized_file_read(
        self,
        folder_id: str,
        file_id: str,
    ) -> dict[str, Any]:
        item = self._resolve_authorized_file(folder_id, file_id)
        if item is None:
            self._last_file_read = {
                "ok": False,
                "error": "authorized_file_not_found",
                "folder_id": str(folder_id or "")[:32],
                "file_id": str(file_id or "")[:32],
                "timestamp": time.time(),
            }
            self.refresh(force=True, emit=True)
            return {"ok": False, "error": "authorized_file_not_found"}

        # P0.6.5.2.1 — an empty file is still a valid authorized file.
        # It must not be treated as a security denial. The execution phase
        # returns a successful local "empty file" result without invoking the
        # document extractor.
        if int(item["size_bytes"]) > self._AUTHORIZED_FILE_MAX_BYTES:
            return {
                "ok": False,
                "error": "authorized_file_too_large",
                "max_bytes": self._AUTHORIZED_FILE_MAX_BYTES,
            }

        decision = self.core.security_engine.authorize(
            "READ_AUTHORIZED_FILE",
            {
                "folder_id": item["folder_id"],
                "file_id": item["file_id"],
            },
            user_confirmed=True,
        )
        if not decision.allowed:
            return {
                "ok": False,
                "authorized": False,
                "error": "security_denied",
                "reason": decision.reason,
            }

        plan = AuthorizedFileReadPlan(
            action="READ_AUTHORIZED_FILE",
            folder_id=item["folder_id"],
            file_id=item["file_id"],
            folder_label=item["folder_label"],
            name=item["name"],
            path=item["path"],
            risk=decision.risk.name,
            permission="authorized_file_read",
            authorized=True,
            created_at=time.time(),
        )
        return {"ok": True, "authorized": True, "plan": plan}

    def execute_authorized_file_read(
        self,
        plan: AuthorizedFileReadPlan,
    ) -> dict[str, Any]:
        """Extract locally; no LLM call, upload, file mutation or recursive access."""
        if (
            not isinstance(plan, AuthorizedFileReadPlan)
            or plan.action != "READ_AUTHORIZED_FILE"
            or not plan.authorized
            or plan.permission != "authorized_file_read"
        ):
            return {"ok": False, "error": "invalid_authorized_file_plan"}

        current = self._resolve_authorized_file(plan.folder_id, plan.file_id)
        if current is None:
            return {"ok": False, "error": "authorized_file_not_found"}
        if str(current.get("path") or "") != str(plan.path or ""):
            return {"ok": False, "error": "authorized_file_changed"}

        if int(current.get("size_bytes") or 0) == 0:
            preview = "(Fichier vide.)"
            self._last_file_read = {
                "ok": True,
                "folder_id": plan.folder_id,
                "file_id": plan.file_id,
                "folder_label": plan.folder_label,
                "name": plan.name,
                "mime_type": "text/plain",
                "size_bytes": 0,
                "text_chars": 0,
                "truncated": False,
                "preview": preview,
                "local_only": True,
                "cloud_upload": False,
                "content_read": True,
                "empty": True,
                "timestamp": time.time(),
            }
            _emit("system.file.read", {
                "folder_id": plan.folder_id,
                "file_id": plan.file_id,
                "name": plan.name,
                "text_chars": 0,
                "local_only": True,
                "empty": True,
            })
            self.refresh(force=True, emit=True)
            return {
                "ok": True,
                "action": plan.action,
                "folder_id": plan.folder_id,
                "file_id": plan.file_id,
                "folder_label": plan.folder_label,
                "name": plan.name,
                "mime_type": "text/plain",
                "size_bytes": 0,
                "text_chars": 0,
                "truncated": False,
                "preview": preview,
                "local_only": True,
                "cloud_upload": False,
                "empty": True,
            }

        try:
            document = extract_document(
                str(current["path"]),
                max_bytes=self._AUTHORIZED_FILE_MAX_BYTES,
                max_chars=self._AUTHORIZED_FILE_MAX_CHARS,
            )
        except DocumentAnalysisError as exc:
            self._last_file_read = {
                "ok": False,
                "error": "document_extract_failed",
                "detail": str(exc)[:260],
                "folder_id": plan.folder_id,
                "file_id": plan.file_id,
                "folder_label": plan.folder_label,
                "name": plan.name,
                "timestamp": time.time(),
            }
            self.refresh(force=True, emit=True)
            return {
                "ok": False,
                "error": "document_extract_failed",
                "detail": str(exc)[:260],
            }
        except Exception:
            logger.warning("Authorized file extraction failed", exc_info=True)
            return {"ok": False, "error": "authorized_file_read_failed"}

        if bool(document.native_required):
            self._last_file_read = {
                "ok": False,
                "error": "native_document_requires_document_lane",
                "folder_id": plan.folder_id,
                "file_id": plan.file_id,
                "folder_label": plan.folder_label,
                "name": plan.name,
                "mime_type": document.mime_type,
                "size_bytes": document.size_bytes,
                "timestamp": time.time(),
            }
            self.refresh(force=True, emit=True)
            return {
                "ok": False,
                "error": "native_document_requires_document_lane",
                "detail": "PDF visuel : aucun upload cloud n'est autorisé par P0.6.5.2.",
            }

        text = str(document.text or "")
        ui_text = text[: self._AUTHORIZED_FILE_UI_CHARS]
        self._last_file_read = {
            "ok": True,
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "folder_label": plan.folder_label,
            "name": plan.name,
            "mime_type": document.mime_type,
            "size_bytes": document.size_bytes,
            "text_chars": document.text_chars,
            "truncated": bool(document.truncated or len(text) > len(ui_text)),
            "preview": ui_text,
            "local_only": True,
            "cloud_upload": False,
            "content_read": True,
            "timestamp": time.time(),
        }
        _emit("system.file.read", {
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "name": plan.name,
            "text_chars": document.text_chars,
            "local_only": True,
        })
        self.refresh(force=True, emit=True)
        return {
            "ok": True,
            "action": plan.action,
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "folder_label": plan.folder_label,
            "name": plan.name,
            "mime_type": document.mime_type,
            "size_bytes": document.size_bytes,
            "text_chars": document.text_chars,
            "truncated": bool(document.truncated),
            "preview": ui_text,
            "local_only": True,
            "cloud_upload": False,
        }

    def _scan_authorized_project_files(self, folder_id: str) -> dict[str, Any]:
        """Return a deterministic, bounded set of readable direct-child files."""
        import os
        folder=self._folder_by_id(folder_id)
        if folder is None:
            return {"ok":False,"error":"folder_not_authorized"}
        try:
            root=Path(str(folder.get("path") or "")).resolve(strict=True)
        except Exception:
            return {"ok":False,"error":"folder_not_found"}
        if not root.is_dir():
            return {"ok":False,"error":"folder_not_found"}

        rows=[];skipped=[]
        try:
            with os.scandir(root) as scan:
                entries=sorted(list(scan),key=lambda e:str(e.name).casefold())
        except Exception:
            return {"ok":False,"error":"folder_scan_failed"}

        for entry in entries[:240]:
            try:
                if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                    continue
                name=str(entry.name)
                ext=Path(name).suffix.casefold()
                if ext not in self._AUTHORIZED_FILE_EXTENSIONS:
                    continue
                candidate=(root/name).resolve(strict=True)
                if candidate.parent!=root:
                    continue
                size=int(candidate.stat().st_size)
                if size>self._AUTHORIZED_FILE_MAX_BYTES:
                    skipped.append({"name":name,"reason":"too_large"})
                    continue
                rows.append({
                    "file_id":self._authorized_file_id(str(folder.get("id") or ""),name),
                    "name":name,"size_bytes":size,"extension":ext,
                })
            except Exception:
                continue

        selected=[];total_bytes=0
        for row in rows:
            if len(selected)>=self._AUTHORIZED_PROJECT_MAX_FILES:
                skipped.append({"name":row["name"],"reason":"file_limit"})
                continue
            size=int(row.get("size_bytes") or 0)
            if selected and total_bytes+size>self._AUTHORIZED_PROJECT_MAX_TOTAL_BYTES:
                skipped.append({"name":row["name"],"reason":"aggregate_byte_limit"})
                continue
            selected.append(row);total_bytes+=size
        return {
            "ok":True,
            "folder_id":str(folder.get("id") or ""),
            "label":str(folder.get("label") or "Projet"),
            "path":str(root),
            "files":selected,
            "skipped":skipped[:80],
            "candidate_count":len(rows),
            "selected_count":len(selected),
            "selected_bytes":total_bytes,
        }

    def plan_authorized_project_analysis(
        self,
        folder_id: str,
        *,
        analysis_mode: str,
        query: str = "",
    ) -> dict[str, Any]:
        analysis_mode=str(analysis_mode or "").strip().casefold()
        query=re.sub(r"\s+"," ",str(query or "").strip())[:600]
        if analysis_mode not in {"summary","search","context"}:
            return {"ok":False,"error":"invalid_project_analysis_mode"}
        if analysis_mode in {"search","context"} and not query:
            return {"ok":False,"error":"project_query_required"}

        scan=self._scan_authorized_project_files(folder_id)
        if not scan.get("ok"):
            return scan
        files=list(scan.get("files") or [])
        if not files:
            return {"ok":False,"error":"authorized_project_has_no_readable_files"}

        decision=self.core.security_engine.authorize(
            "ANALYZE_AUTHORIZED_PROJECT",
            {
                "folder_id":str(scan.get("folder_id") or ""),
                "mode":analysis_mode,
                "file_count":len(files),
            },
            user_confirmed=True,
        )
        if not decision.allowed:
            return {"ok":False,"authorized":False,"error":"security_denied","reason":decision.reason}

        plan=AuthorizedProjectAnalysisPlan(
            action="ANALYZE_AUTHORIZED_PROJECT",
            analysis_mode=analysis_mode,
            query=query,
            folder_id=str(scan.get("folder_id") or ""),
            folder_label=str(scan.get("label") or "Projet"),
            folder_path=str(scan.get("path") or ""),
            file_ids=tuple(str(f.get("file_id") or "") for f in files),
            risk=decision.risk.name,
            permission="authorized_file_read",
            authorized=True,
            created_at=time.time(),
        )
        return {
            "ok":True,"authorized":True,"plan":plan,
            "selected_count":len(files),"selected_bytes":int(scan.get("selected_bytes") or 0),
            "skipped":list(scan.get("skipped") or []),
        }

    def execute_authorized_project_analysis(
        self,
        plan: AuthorizedProjectAnalysisPlan,
    ) -> dict[str, Any]:
        if (
            not isinstance(plan,AuthorizedProjectAnalysisPlan)
            or plan.action!="ANALYZE_AUTHORIZED_PROJECT"
            or plan.analysis_mode not in {"summary","search","context"}
            or not plan.authorized
            or plan.permission!="authorized_file_read"
            or not plan.file_ids
            or len(plan.file_ids)>self._AUTHORIZED_PROJECT_MAX_FILES
        ):
            return {"ok":False,"error":"invalid_project_analysis_plan"}

        folder=self._folder_by_id(plan.folder_id)
        if folder is None:
            return {"ok":False,"error":"folder_not_authorized"}
        try:
            current_root=Path(str(folder.get("path") or "")).resolve(strict=True)
            planned_root=Path(str(plan.folder_path or "")).resolve(strict=True)
        except Exception:
            return {"ok":False,"error":"authorized_project_changed"}
        if current_root!=planned_root or not current_root.is_dir():
            return {"ok":False,"error":"authorized_project_changed"}

        sources=[];skipped=[];total_chars=0;total_bytes=0
        for file_id in plan.file_ids:
            item=self._resolve_authorized_file(plan.folder_id,file_id)
            if item is None:
                skipped.append({"file_id":str(file_id),"name":"","reason":"file_changed_or_missing"})
                continue
            size=int(item.get("size_bytes") or 0)
            total_bytes+=size
            if size<=0:
                skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"empty"})
                continue
            try:
                document=extract_document(
                    str(item["path"]),
                    max_bytes=self._AUTHORIZED_FILE_MAX_BYTES,
                    max_chars=self._AUTHORIZED_FILE_MAX_CHARS,
                )
                if document.native_required:
                    skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"native_required"})
                    continue
                remaining=self._AUTHORIZED_PROJECT_MAX_TOTAL_CHARS-total_chars
                if remaining<=0:
                    skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"aggregate_char_limit"})
                    continue
                text=str(document.text or "")[:remaining]
                if not text.strip():
                    skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"no_text"})
                    continue
                total_chars+=len(text)
                sources.append(ProjectSource(
                    file_id=str(file_id),name=str(item.get("name") or document.name),
                    text=text,size_bytes=size,
                    truncated=bool(document.truncated or len(text)<len(str(document.text or ""))),
                ))
            except DocumentAnalysisError as exc:
                skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"extract_failed","detail":str(exc)[:120]})
            except Exception:
                logger.warning("Authorized project file extraction failed",exc_info=True)
                skipped.append({"file_id":str(file_id),"name":item.get("name",""),"reason":"extract_failed"})

        if not sources:
            self._last_project_analysis={
                "ok":False,"error":"authorized_project_no_extractable_text",
                "folder_id":plan.folder_id,"folder_label":plan.folder_label,
                "files_planned":len(plan.file_ids),"files_extracted":0,
                "skipped":skipped[:80],"timestamp":time.time(),
            }
            self.refresh(force=True,emit=True)
            return dict(self._last_project_analysis)

        try:
            local=analyze_local_project(
                sources,mode=plan.analysis_mode,query=plan.query,
                max_result_chars=self._AUTHORIZED_PROJECT_MAX_RESULT_CHARS,
            )
        except LocalProjectIntelligenceError as exc:
            return {"ok":False,"error":"local_project_analysis_failed","detail":str(exc)[:320]}
        except Exception:
            logger.warning("Local project intelligence failed",exc_info=True)
            return {"ok":False,"error":"local_project_analysis_failed"}

        result={
            "ok":True,"action":plan.action,
            "folder_id":plan.folder_id,"folder_label":plan.folder_label,
            "mode":local.mode,"query":local.query,"text":local.text,
            "files_planned":len(plan.file_ids),
            "files_extracted":local.files_considered,
            "files_matched":local.files_matched,
            "source_chars":local.source_chars,"result_chars":local.result_chars,
            "provenance":[dict(p) for p in local.provenance],
            "skipped":skipped[:80],
            "selected_bytes":total_bytes,
            "extractive":True,"local_only":True,
            "cloud_upload":False,"network_access":False,"llm_used":False,
        }
        self._last_project_analysis={**result,"timestamp":time.time()}
        _emit("system.project.analysis",{
            "folder_id":plan.folder_id,"label":plan.folder_label,
            "mode":plan.analysis_mode,"files":local.files_considered,
            "matched":local.files_matched,"local_only":True,"llm_used":False,
        })
        self.refresh(force=True,emit=True)
        return result

    def _match_authorized_project_target(self, requested_folder: str) -> dict[str, str] | None:
        requested=self._normalize_command_text(str(requested_folder or "").strip(" \"'.,;!?"))
        if not requested:
            return None
        matches=[]
        for item in self._authorized_folders:
            label=self._normalize_command_text(str(item.get("label") or ""))
            basename=self._normalize_command_text(Path(str(item.get("path") or "")).name)
            if requested in {label,basename}:
                matches.append(item)
        if len(matches)!=1:
            return None
        item=matches[0]
        return {"folder_id":str(item.get("id") or ""),"label":str(item.get("label") or "Projet")}

    def match_authorized_project_analysis_request(self, text: str) -> dict[str, str] | None:
        """Exact project-level multi-file commands; no raw path or fuzzy project match."""
        raw=re.sub(r"\s+"," ",str(text or "").strip())
        if not raw:
            return None
        summary=re.match(
            r"(?i)^(?:résume|resume|fais\s+un\s+résumé\s+de|fais\s+un\s+resume\s+de)\s+"
            r"(?:le\s+)?(?:projet|dossier)\s+(.+?)\s*[?.!]*$",raw,
        )
        if summary:
            target=self._match_authorized_project_target(summary.group(1))
            return {**target,"mode":"summary","query":""} if target else None
        search=re.match(
            r"(?i)^(?:cherche|recherche|trouve)\s+(.+?)\s+dans\s+"
            r"(?:le\s+)?(?:projet|dossier)\s+(.+?)\s*[?.!]*$",raw,
        )
        if search:
            target=self._match_authorized_project_target(search.group(2))
            return {**target,"mode":"search","query":search.group(1).strip(" \"'.,;!?")[:600]} if target else None
        context=re.match(
            r"(?i)^(?:que\s+dit|qu['’]est-ce\s+que\s+dit|que\s+contient)\s+"
            r"(?:le\s+)?(?:projet|dossier)\s+(.+?)\s+sur\s+(.+?)\s*[?.!]*$",raw,
        )
        if context:
            target=self._match_authorized_project_target(context.group(1))
            return {**target,"mode":"context","query":context.group(2).strip(" \"'.,;!?")[:600]} if target else None
        return None

    def plan_authorized_file_analysis(
        self,
        folder_id: str,
        file_id: str,
        *,
        analysis_mode: str,
        query: str = "",
    ) -> dict[str, Any]:
        analysis_mode = str(analysis_mode or "").strip().casefold()
        query = re.sub(r"\s+", " ", str(query or "").strip())[:600]
        if analysis_mode not in {"summary", "search", "context"}:
            return {"ok": False, "error": "invalid_local_document_mode"}
        if analysis_mode in {"search", "context"} and not query:
            return {"ok": False, "error": "local_document_query_required"}

        item = self._resolve_authorized_file(folder_id, file_id)
        if item is None:
            return {"ok": False, "error": "authorized_file_not_found"}
        if int(item["size_bytes"]) > self._AUTHORIZED_FILE_MAX_BYTES:
            return {"ok": False, "error": "authorized_file_too_large"}

        decision = self.core.security_engine.authorize(
            "ANALYZE_AUTHORIZED_FILE",
            {
                "folder_id": item["folder_id"],
                "file_id": item["file_id"],
                "mode": analysis_mode,
            },
            user_confirmed=True,
        )
        if not decision.allowed:
            return {
                "ok": False,
                "authorized": False,
                "error": "security_denied",
                "reason": decision.reason,
            }

        plan = AuthorizedFileAnalysisPlan(
            action="ANALYZE_AUTHORIZED_FILE",
            analysis_mode=analysis_mode,
            query=query,
            folder_id=item["folder_id"],
            file_id=item["file_id"],
            folder_label=item["folder_label"],
            name=item["name"],
            path=item["path"],
            risk=decision.risk.name,
            permission="authorized_file_read",
            authorized=True,
            created_at=time.time(),
        )
        return {"ok": True, "authorized": True, "plan": plan}

    def execute_authorized_file_analysis(
        self,
        plan: AuthorizedFileAnalysisPlan,
    ) -> dict[str, Any]:
        """Run bounded extractive intelligence locally, never via provider/LLM."""
        if (
            not isinstance(plan, AuthorizedFileAnalysisPlan)
            or plan.action != "ANALYZE_AUTHORIZED_FILE"
            or plan.analysis_mode not in {"summary", "search", "context"}
            or not plan.authorized
            or plan.permission != "authorized_file_read"
        ):
            return {"ok": False, "error": "invalid_local_document_plan"}

        current = self._resolve_authorized_file(plan.folder_id, plan.file_id)
        if current is None or str(current.get("path") or "") != str(plan.path or ""):
            return {"ok": False, "error": "authorized_file_changed"}

        if int(current.get("size_bytes") or 0) == 0:
            result = {
                "mode": plan.analysis_mode,
                "query": plan.query,
                "text": "(Document vide.)",
                "matches": 0,
                "source_chars": 0,
                "result_chars": len("(Document vide.)"),
                "extractive": True,
                "local_only": True,
            }
        else:
            try:
                document = extract_document(
                    str(current["path"]),
                    max_bytes=self._AUTHORIZED_FILE_MAX_BYTES,
                    max_chars=self._AUTHORIZED_FILE_MAX_CHARS,
                )
                if document.native_required:
                    return {
                        "ok": False,
                        "error": "native_document_requires_document_lane",
                        "detail": "PDF visuel : analyse locale impossible sans la lane Document native.",
                    }
                local = analyze_local_document(
                    document,
                    mode=plan.analysis_mode,
                    query=plan.query,
                )
                result = {
                    "mode": local.mode,
                    "query": local.query,
                    "text": local.text,
                    "matches": local.matches,
                    "source_chars": local.source_chars,
                    "result_chars": local.result_chars,
                    "extractive": local.extractive,
                    "local_only": local.local_only,
                }
            except (DocumentAnalysisError, LocalDocumentIntelligenceError) as exc:
                return {
                    "ok": False,
                    "error": "local_document_analysis_failed",
                    "detail": str(exc)[:320],
                }
            except Exception:
                logger.warning("Local authorized document analysis failed", exc_info=True)
                return {"ok": False, "error": "local_document_analysis_failed"}

        self._last_file_analysis = {
            "ok": True,
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "folder_label": plan.folder_label,
            "name": plan.name,
            **result,
            "cloud_upload": False,
            "llm_used": False,
            "timestamp": time.time(),
        }
        _emit("system.file.analysis", {
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "name": plan.name,
            "mode": plan.analysis_mode,
            "local_only": True,
            "llm_used": False,
        })
        self.refresh(force=True, emit=True)
        return {
            "ok": True,
            "action": plan.action,
            "folder_id": plan.folder_id,
            "file_id": plan.file_id,
            "folder_label": plan.folder_label,
            "name": plan.name,
            **result,
            "cloud_upload": False,
            "llm_used": False,
        }

    def _match_authorized_file_target(
        self,
        requested_name: str,
        requested_folder: str,
    ) -> dict[str, str] | None:
        requested_name = str(requested_name or "").strip(" \"'.,;!?")
        requested_folder = self._normalize_command_text(
            str(requested_folder or "").strip(" \"'.,;!?")
        )
        if not requested_name or not requested_folder:
            return None

        folders = []
        for item in self._authorized_folders:
            label = self._normalize_command_text(str(item.get("label") or ""))
            basename = self._normalize_command_text(Path(str(item.get("path") or "")).name)
            if requested_folder in {label, basename}:
                folders.append(dict(item))
        if len(folders) != 1:
            return None

        folder = folders[0]
        try:
            root = Path(str(folder.get("path") or "")).resolve(strict=True)
        except Exception:
            return None

        matches = []
        try:
            import os
            with os.scandir(root) as scan:
                for entry in scan:
                    try:
                        if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                            continue
                        if str(entry.name).casefold() != requested_name.casefold():
                            continue
                        if Path(entry.name).suffix.casefold() not in self._AUTHORIZED_FILE_EXTENSIONS:
                            continue
                        matches.append({
                            "folder_id": str(folder.get("id") or ""),
                            "file_id": self._authorized_file_id(
                                str(folder.get("id") or ""),
                                str(entry.name),
                            ),
                            "name": str(entry.name),
                        })
                    except Exception:
                        continue
        except Exception:
            return None
        return matches[0] if len(matches) == 1 else None

    def match_authorized_file_analysis_request(
        self,
        text: str,
    ) -> dict[str, str] | None:
        """Exact filename/project commands for local summary/search/context."""
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        if not raw:
            return None

        summary = re.match(
            r"(?i)^(?:résume|resume|fais\s+un\s+résumé\s+de|fais\s+un\s+resume\s+de)\s+"
            r"(?:le\s+)?fichier\s+(.+?)\s+(?:du|dans\s+le|dans)\s+"
            r"(?:projet|dossier)\s+(.+?)\s*[?.!]*$",
            raw,
        )
        if summary:
            target = self._match_authorized_file_target(summary.group(1), summary.group(2))
            return {**target, "mode": "summary", "query": ""} if target else None

        search = re.match(
            r"(?i)^(?:cherche|recherche|trouve)\s+(.+?)\s+dans\s+"
            r"(?:le\s+)?fichier\s+(.+?)\s+(?:du|dans\s+le|dans)\s+"
            r"(?:projet|dossier)\s+(.+?)\s*[?.!]*$",
            raw,
        )
        if search:
            target = self._match_authorized_file_target(search.group(2), search.group(3))
            return (
                {**target, "mode": "search", "query": search.group(1).strip(" \"'.,;!?")[:600]}
                if target else None
            )

        context = re.match(
            r"(?i)^(?:que\s+dit|qu['’]est-ce\s+que\s+dit)\s+"
            r"(?:le\s+)?fichier\s+(.+?)\s+(?:du|dans\s+le|dans)\s+"
            r"(?:projet|dossier)\s+(.+?)\s+sur\s+(.+?)\s*[?.!]*$",
            raw,
        )
        if context:
            target = self._match_authorized_file_target(context.group(1), context.group(2))
            return (
                {**target, "mode": "context", "query": context.group(3).strip(" \"'.,;!?")[:600]}
                if target else None
            )
        return None

    def match_authorized_file_read_request(
        self,
        text: str,
    ) -> dict[str, str] | None:
        """Exact filename + exact authorized project label; no raw path matching."""
        raw = re.sub(r"\s+", " ", str(text or "").strip())
        if not raw:
            return None
        match = re.match(
            r"(?i)^(?:lis|lire|affiche|affiche-moi|montre|montre-moi)\s+"
            r"(?:le\s+)?fichier\s+(.+?)\s+"
            r"(?:du|dans\s+le|dans)\s+(?:projet|dossier)\s+(.+?)\s*[?.!]*$",
            raw,
        )
        if not match:
            return None
        return self._match_authorized_file_target(match.group(1), match.group(2))


    @staticmethod
    def _folder_registry_file() -> Path:
        from config.settings import settings
        return Path(settings.CONFIG_DIR) / "authorized_folders.json"

    @staticmethod
    def _safe_folder_label(value: str, fallback: str = "Projet") -> str:
        label = re.sub(r"[\x00-\x1f\x7f]+", " ", str(value or ""))
        label = re.sub(r"\s+", " ", label).strip(" .")
        return (label or fallback)[:80]

    def _load_authorized_folder_registry(self) -> None:
        path = self._folder_registry_file()
        items: list[dict[str, Any]] = []
        try:
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                rows = data.get("folders", []) if isinstance(data, dict) else []
                for row in rows[:120]:
                    if not isinstance(row, dict):
                        continue
                    folder_id = str(row.get("id") or "").casefold().strip()
                    folder_path = str(row.get("path") or "").strip()
                    label = self._safe_folder_label(
                        row.get("label") or "",
                        Path(folder_path).name or "Projet",
                    )
                    if (
                        len(folder_id) == 16
                        and all(ch in "0123456789abcdef" for ch in folder_id)
                        and folder_path
                    ):
                        items.append({
                            "id": folder_id,
                            "label": label,
                            "path": folder_path[:1024],
                            "authorized_at": float(row.get("authorized_at") or 0.0),
                        })
        except Exception:
            logger.warning("Authorized folder registry load failed", exc_info=True)
        self._authorized_folders = items

    def _save_authorized_folder_registry(self) -> None:
        target = self._folder_registry_file()
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "folders": self._authorized_folders[:120]}
        tmp = target.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp.replace(target)

    def authorized_folders(self) -> list[dict[str, Any]]:
        out = []
        for item in self._authorized_folders[:120]:
            row = dict(item)
            try:
                row["exists"] = bool(Path(str(row.get("path") or "")).is_dir())
            except Exception:
                row["exists"] = False
            out.append(row)
        return out

    def _folder_by_id(self, folder_id: str) -> dict[str, Any] | None:
        folder_id = str(folder_id or "").casefold().strip()
        for item in self._authorized_folders:
            if str(item.get("id") or "") == folder_id:
                return dict(item)
        return None

    def _set_folder_action(
        self,
        *,
        ok: bool,
        action: str,
        label: str = "",
        detail: str = "",
        folder_id: str = "",
    ) -> None:
        self._last_folder_action = {
            "ok": bool(ok),
            "action": str(action or "")[:60],
            "label": self._safe_folder_label(label, "") if label else "",
            "detail": str(detail or "")[:260],
            "folder_id": str(folder_id or "")[:32],
            "timestamp": time.time(),
        }

    @staticmethod
    def _is_protected_authorization_root(path: Path) -> bool:
        import os

        try:
            resolved = path.resolve(strict=True)
        except Exception:
            return True
        if resolved == Path(resolved.anchor):
            return True

        # Exact profile root / C:\Users root are too broad.
        exact_roots = []
        try:
            home = Path.home().resolve(strict=False)
            exact_roots.extend([home, home.parent])
        except Exception:
            pass
        for root in exact_roots:
            if str(resolved).casefold().rstrip("\\/") == str(root).casefold().rstrip("\\/"):
                return True

        # Windows / Program Files / ProgramData and descendants are blocked.
        protected = []
        for raw in (
            os.environ.get("WINDIR"),
            os.environ.get("ProgramFiles"),
            os.environ.get("ProgramFiles(x86)"),
            os.environ.get("ProgramData"),
        ):
            if raw:
                try:
                    protected.append(Path(raw).resolve(strict=False))
                except Exception:
                    pass

        key = str(resolved).casefold().rstrip("\\/")
        for root in protected:
            root_key = str(root).casefold().rstrip("\\/")
            if key == root_key or key.startswith(root_key + "\\") or key.startswith(root_key + "/"):
                return True
        return False

    def _validate_authorizable_folder(
        self,
        raw_path: str,
        label: str = "",
    ) -> dict[str, Any]:
        import os

        value = os.path.expandvars(os.path.expanduser(str(raw_path or ""))).strip()
        value = value.strip('"').strip("'").strip()
        if not value or "\x00" in value or len(value) > 1024:
            return {"ok": False, "error": "invalid_folder_path"}

        try:
            path = Path(value).resolve(strict=True)
        except Exception:
            return {"ok": False, "error": "folder_not_found"}
        if not path.is_dir():
            return {"ok": False, "error": "not_a_folder"}
        if self._is_protected_authorization_root(path):
            return {"ok": False, "error": "folder_scope_too_broad"}

        canonical = str(path)
        canonical_key = canonical.casefold().rstrip("\\/")
        for item in self._authorized_folders:
            if str(item.get("path") or "").casefold().rstrip("\\/") == canonical_key:
                return {
                    "ok": False,
                    "error": "folder_already_authorized",
                    "folder_id": str(item.get("id") or ""),
                    "label": str(item.get("label") or ""),
                }

        safe_label = self._safe_folder_label(label, path.name or "Projet")
        normalized_label = self._normalize_command_text(safe_label)
        if not normalized_label:
            return {"ok": False, "error": "invalid_folder_label"}
        for item in self._authorized_folders:
            if self._normalize_command_text(str(item.get("label") or "")) == normalized_label:
                return {"ok": False, "error": "folder_label_in_use"}

        folder_id = hashlib.sha256(
            canonical_key.encode("utf-8", errors="ignore")
        ).hexdigest()[:16]
        return {
            "ok": True,
            "folder_id": folder_id,
            "path": canonical,
            "label": safe_label,
        }

    def plan_authorize_folder(self, raw_path: str, label: str = "") -> dict[str, Any]:
        validated = self._validate_authorizable_folder(raw_path, label)
        if not validated.get("ok"):
            self._set_folder_action(
                ok=False,
                action="AUTHORIZE_FOLDER",
                label=str(validated.get("label") or ""),
                detail=str(validated.get("error") or "folder_validation_failed"),
                folder_id=str(validated.get("folder_id") or ""),
            )
            self.refresh(force=True, emit=True)
            return validated

        decision = self.core.security_engine.authorize(
            "AUTHORIZE_FOLDER",
            {"folder_id": validated["folder_id"]},
            user_confirmed=True,
        )
        if not decision.allowed:
            self._set_folder_action(
                ok=False,
                action="AUTHORIZE_FOLDER",
                label=validated["label"],
                detail=decision.reason,
                folder_id=validated["folder_id"],
            )
            self.refresh(force=True, emit=True)
            return {
                "ok": False,
                "authorized": False,
                "error": "security_denied",
                "reason": decision.reason,
            }

        plan = AuthorizedFolderActionPlan(
            action="AUTHORIZE_FOLDER",
            folder_id=validated["folder_id"],
            label=validated["label"],
            path=validated["path"],
            risk=decision.risk.name,
            permission="authorized_folder_access",
            authorized=True,
            created_at=time.time(),
        )
        return {"ok": True, "authorized": True, "plan": plan}

    def execute_authorize_folder(
        self,
        plan: AuthorizedFolderActionPlan,
    ) -> dict[str, Any]:
        if (
            not isinstance(plan, AuthorizedFolderActionPlan)
            or plan.action != "AUTHORIZE_FOLDER"
            or not plan.authorized
            or plan.permission != "authorized_folder_access"
        ):
            return {"ok": False, "error": "invalid_folder_plan"}

        try:
            path = Path(plan.path).resolve(strict=True)
        except Exception:
            return {"ok": False, "error": "folder_not_found"}
        if not path.is_dir() or self._is_protected_authorization_root(path):
            return {"ok": False, "error": "folder_scope_invalid"}

        item = {
            "id": plan.folder_id,
            "label": plan.label,
            "path": str(path),
            "authorized_at": time.time(),
        }
        self._authorized_folders.append(item)
        self._authorized_folders = self._authorized_folders[-120:]
        self._save_authorized_folder_registry()
        self._set_folder_action(
            ok=True,
            action=plan.action,
            label=plan.label,
            detail="Dossier autorisé.",
            folder_id=plan.folder_id,
        )
        _emit("system.folder.authorized", {
            "folder_id": plan.folder_id,
            "label": plan.label,
        })
        self.refresh(force=True, emit=True)
        return {"ok": True, **item, "action": plan.action}

    def plan_folder_action(self, action: str, folder_id: str) -> dict[str, Any]:
        action = str(action or "").strip().upper()
        if action not in {
            "REVOKE_AUTHORIZED_FOLDER",
            "LIST_AUTHORIZED_FOLDER",
            "OPEN_AUTHORIZED_FOLDER",
        }:
            return {"ok": False, "error": "unsupported_folder_action"}

        item = self._folder_by_id(folder_id)
        if item is None:
            self._set_folder_action(
                ok=False,
                action=action,
                detail="folder_not_authorized",
                folder_id=folder_id,
            )
            self.refresh(force=True, emit=True)
            return {"ok": False, "error": "folder_not_authorized"}

        decision = self.core.security_engine.authorize(
            action,
            {"folder_id": item["id"]},
            user_confirmed=action in {
                "REVOKE_AUTHORIZED_FOLDER",
                "OPEN_AUTHORIZED_FOLDER",
            },
        )
        if not decision.allowed:
            self._set_folder_action(
                ok=False,
                action=action,
                label=item["label"],
                detail=decision.reason,
                folder_id=item["id"],
            )
            self.refresh(force=True, emit=True)
            return {
                "ok": False,
                "authorized": False,
                "error": "security_denied",
                "reason": decision.reason,
            }

        plan = AuthorizedFolderActionPlan(
            action=action,
            folder_id=item["id"],
            label=item["label"],
            path=item["path"],
            risk=decision.risk.name,
            permission="authorized_folder_access",
            authorized=True,
            created_at=time.time(),
        )
        return {"ok": True, "authorized": True, "plan": plan}

    def execute_folder_action(
        self,
        plan: AuthorizedFolderActionPlan,
    ) -> dict[str, Any]:
        import os

        if (
            not isinstance(plan, AuthorizedFolderActionPlan)
            or plan.action not in {
                "REVOKE_AUTHORIZED_FOLDER",
                "LIST_AUTHORIZED_FOLDER",
                "OPEN_AUTHORIZED_FOLDER",
            }
            or not plan.authorized
            or plan.permission != "authorized_folder_access"
        ):
            return {"ok": False, "error": "invalid_folder_plan"}

        current = self._folder_by_id(plan.folder_id)
        if current is None:
            return {"ok": False, "error": "folder_not_authorized"}

        if plan.action == "REVOKE_AUTHORIZED_FOLDER":
            self._authorized_folders = [
                item for item in self._authorized_folders
                if str(item.get("id") or "") != plan.folder_id
            ]
            self._save_authorized_folder_registry()
            if str(self._last_folder_listing.get("folder_id") or "") == plan.folder_id:
                self._last_folder_listing = {}
            if str(self._last_file_read.get("folder_id") or "") == plan.folder_id:
                self._last_file_read = {}
            if str(self._last_file_analysis.get("folder_id") or "") == plan.folder_id:
                self._last_file_analysis = {}
            if str(self._last_project_analysis.get("folder_id") or "") == plan.folder_id:
                self._last_project_analysis = {}
            self._set_folder_action(
                ok=True,
                action=plan.action,
                label=plan.label,
                detail="Autorisation retirée. Aucun fichier supprimé.",
                folder_id=plan.folder_id,
            )
            _emit("system.folder.revoked", {
                "folder_id": plan.folder_id,
                "label": plan.label,
            })
            self.refresh(force=True, emit=True)
            return {
                "ok": True,
                "action": plan.action,
                "folder_id": plan.folder_id,
                "label": plan.label,
                "files_deleted": 0,
            }

        try:
            root = Path(str(current.get("path") or "")).resolve(strict=True)
        except Exception:
            return {"ok": False, "error": "folder_unavailable"}
        if not root.is_dir():
            return {"ok": False, "error": "folder_unavailable"}

        if plan.action == "OPEN_AUTHORIZED_FOLDER":
            if os.name != "nt" or not hasattr(os, "startfile"):
                return {"ok": False, "error": "windows_required"}
            try:
                os.startfile(str(root))  # type: ignore[attr-defined]
            except Exception:
                logger.warning("Authorized folder open failed", exc_info=True)
                return {"ok": False, "error": "folder_open_failed"}

            self._set_folder_action(
                ok=True,
                action=plan.action,
                label=plan.label,
                detail="Dossier ouvert.",
                folder_id=plan.folder_id,
            )
            _emit("system.folder.opened", {
                "folder_id": plan.folder_id,
                "label": plan.label,
            })
            self.refresh(force=True, emit=True)
            return {
                "ok": True,
                "action": plan.action,
                "folder_id": plan.folder_id,
                "label": plan.label,
            }

        entries = []
        try:
            with os.scandir(root) as scan:
                rows = sorted(
                    list(scan),
                    key=lambda e: (
                        not e.is_dir(follow_symlinks=False),
                        e.name.casefold(),
                    ),
                )
            for entry in rows[:120]:
                try:
                    is_dir = entry.is_dir(follow_symlinks=False)
                    is_file = entry.is_file(follow_symlinks=False)
                    stat = entry.stat(follow_symlinks=False)
                    suffix = Path(entry.name).suffix.casefold()[:20] if is_file else ""
                    entries.append({
                        "name": str(entry.name)[:240],
                        "kind": "folder" if is_dir else ("file" if is_file else "link"),
                        "size_bytes": int(stat.st_size) if is_file else 0,
                        "modified_at": float(stat.st_mtime),
                        "suffix": suffix,
                        "file_id": (
                            self._authorized_file_id(plan.folder_id, entry.name)
                            if is_file and suffix in self._AUTHORIZED_FILE_EXTENSIONS
                            else ""
                        ),
                        "read_supported": bool(
                            is_file
                            and suffix in self._AUTHORIZED_FILE_EXTENSIONS
                            and int(stat.st_size) <= self._AUTHORIZED_FILE_MAX_BYTES
                        ),
                    })
                except Exception:
                    continue
        except Exception:
            logger.warning("Authorized folder listing failed", exc_info=True)
            return {"ok": False, "error": "folder_list_failed"}

        self._last_folder_listing = {
            "folder_id": plan.folder_id,
            "label": plan.label,
            "entries": entries,
            "count": len(entries),
            "truncated": len(rows) > 120,
            "scanned_at": time.time(),
            "recursive": False,
            "content_read": False,
        }
        self._set_folder_action(
            ok=True,
            action=plan.action,
            label=plan.label,
            detail=f"{len(entries)} élément(s) listé(s), métadonnées uniquement.",
            folder_id=plan.folder_id,
        )
        _emit("system.folder.listed", {
            "folder_id": plan.folder_id,
            "label": plan.label,
            "count": len(entries),
        })
        self.refresh(force=True, emit=True)
        return {
            "ok": True,
            "action": plan.action,
            "folder_id": plan.folder_id,
            "label": plan.label,
            "count": len(entries),
        }

    def match_authorized_folder_request(self, text: str) -> str:
        """Match explicit OPEN commands by an already-authorized exact label."""
        value = self._normalize_command_text(text)
        prefixes = (
            "ouvre le dossier ",
            "ouvre mon dossier ",
            "ouvre dossier ",
            "ouvre le projet ",
            "ouvre mon projet ",
            "affiche le dossier ",
            "affiche le projet ",
            "open folder ",
            "open project ",
        )
        target = ""
        for prefix in prefixes:
            if value.startswith(prefix):
                target = value[len(prefix):].strip()
                break
        if not target:
            return ""

        matches = []
        for item in self._authorized_folders:
            label = self._normalize_command_text(str(item.get("label") or ""))
            basename = self._normalize_command_text(Path(str(item.get("path") or "")).name)
            if target and target in {label, basename}:
                matches.append(str(item.get("id") or ""))
        unique = list(dict.fromkeys(matches))
        return unique[0] if len(unique) == 1 else ""

    _BLOCKED_PROCESS_ALIASES = frozenset({
        "powershell", "powershell.exe", "pwsh", "pwsh.exe",
        "cmd", "cmd.exe", "regedit", "regedit.exe",
        "msconfig", "msconfig.exe", "taskmgr", "taskmgr.exe",
        "wt", "wt.exe", "windows terminal",
    })

    def match_unallowlisted_process_request(self, text: str) -> str:
        """Return an explicit process target that is outside the fixed safe allowlist.

        This intentionally does not classify generic "ouvre X" phrases. It only
        catches strong process/executable signals so Maps/Documents/UI commands
        are not accidentally intercepted.
        """
        raw = str(text or "").strip()
        value = self._normalize_command_text(raw)
        if not value:
            return ""

        launch_prefixes = (
            "ouvre ", "ouvrir ", "lance ", "lancer ", "demarre ", "demarrer ",
            "execute ", "executer ", "run ", "open ", "launch ", "start ",
        )
        if not any(value.startswith(prefix) for prefix in launch_prefixes):
            return ""

        # A safe alias always wins.
        if self.match_safe_app_request(raw):
            return ""

        # Preserve dots/path syntax from the original string for executable tests.
        lowered = raw.casefold().replace("’", "'").strip()
        exe = re.search(r"(?i)(?:^|\s)([a-z0-9_.-]+\.exe)(?:\s|$)", lowered)
        if exe:
            return exe.group(1)

        # Explicit Windows path / command path.
        path_match = re.search(
            r"(?i)([a-z]:[\\/][^\r\n]+|\\\\[^\r\n]+)",
            raw,
        )
        if path_match:
            return path_match.group(1).strip()[:120]

        padded = f" {value} "
        for alias in sorted(self._BLOCKED_PROCESS_ALIASES, key=len, reverse=True):
            normalized = self._normalize_command_text(alias)
            if normalized and f" {normalized} " in padded:
                return alias
        return ""

    def deny_unallowlisted_process_request(self, target: str) -> dict[str, Any]:
        """Audit and deny arbitrary program launch through SecurityPolicyEngine."""
        target = str(target or "").strip()[:120]
        decision = self.core.security_engine.authorize(
            "RUN_PROGRAM",
            {"target": target},
            user_confirmed=True,
        )

        # P0.6.5.0.1 never executes RUN_PROGRAM even if a future configuration
        # were to grant process_control. This phase is fixed-allowlist only.
        payload = {
            "ok": True,
            "blocked": True,
            "authorized": False,
            "action": "RUN_PROGRAM",
            "target": target,
            "risk": decision.risk.name,
            "reason": (
                decision.reason
                if not decision.allowed
                else "RUN_PROGRAM reste hors périmètre P0.6.5.0."
            ),
            "policy_allowed": bool(decision.allowed),
            "execution": False,
        }
        _emit("system.desktop.denied", payload)
        self.refresh(force=True, emit=True)
        return payload

    def match_safe_app_request(self, text: str) -> str:
        """Return an allowlisted app id only for an explicit launch request."""
        value = self._normalize_command_text(text)
        if not value:
            return ""
        launch_verbs = (
            "ouvre ", "ouvrir ", "lance ", "lancer ", "demarre ", "demarrer ",
            "open ", "launch ", "start ",
        )
        padded = f" {value} "
        if not any(f" {verb}" in padded for verb in launch_verbs):
            return ""
        for app_id, spec in self._SAFE_APPS.items():
            aliases = tuple(self._normalize_command_text(alias) for alias in spec.get("aliases", ()))
            if any(f" {alias} " in padded for alias in aliases if alias):
                return app_id
        return ""

    def safe_apps(self) -> list[dict[str, Any]]:
        return [
            {"id": app_id, "label": str(spec.get("label") or app_id)}
            for app_id, spec in self._SAFE_APPS.items()
        ]

    def plan_safe_app_launch(self, app_id: str) -> dict[str, Any]:
        """Validate the fixed app id and authorize it before any OS execution."""
        app_id = str(app_id or "").casefold().strip()
        spec = self._SAFE_APPS.get(app_id)
        if spec is None:
            return {
                "ok": False,
                "authorized": False,
                "error": "app_not_allowlisted",
                "app_id": app_id,
            }

        decision = self.core.security_engine.authorize(
            "OPEN_SAFE_APP",
            {"app_id": app_id},
            user_confirmed=True,
        )
        if not decision.allowed:
            self.refresh(force=True, emit=True)
            return {
                "ok": False,
                "authorized": False,
                "error": "security_denied",
                "reason": decision.reason,
                "app_id": app_id,
                "action": "OPEN_SAFE_APP",
                "risk": decision.risk.name,
            }

        plan = SafeDesktopActionPlan(
            action="OPEN_SAFE_APP",
            app_id=app_id,
            label=str(spec.get("label") or app_id),
            risk=decision.risk.name,
            permission="safe_app_launch",
            authorized=True,
            created_at=time.time(),
        )
        return {
            "ok": True,
            "authorized": True,
            "plan": plan,
            "app_id": app_id,
            "label": plan.label,
            "action": plan.action,
            "risk": plan.risk,
            "permission": plan.permission,
        }

    def execute_safe_app_launch(self, plan: SafeDesktopActionPlan) -> dict[str, Any]:
        """Execute only a valid internal plan; command is reloaded from fixed registry."""
        import os
        import subprocess

        if not isinstance(plan, SafeDesktopActionPlan):
            return {"ok": False, "error": "invalid_safe_app_plan"}
        if (
            plan.action != "OPEN_SAFE_APP"
            or not plan.authorized
            or plan.permission != "safe_app_launch"
            or plan.app_id not in self._SAFE_APPS
        ):
            return {"ok": False, "error": "invalid_safe_app_plan"}

        spec = self._SAFE_APPS[plan.app_id]
        if os.name != "nt":
            return {"ok": False, "error": "windows_required"}

        command = tuple(str(x) for x in spec.get("command", ()) if str(x))
        if len(command) != 1:
            return {"ok": False, "error": "invalid_allowlist_entry"}

        try:
            subprocess.Popen(
                [command[0]],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                close_fds=True,
            )
        except Exception as exc:
            logger.warning(
                "Safe app launch failed app=%s error=%s",
                plan.app_id, type(exc).__name__,
            )
            _emit("system.safe_app.error", {
                "app_id": plan.app_id,
                "error": type(exc).__name__,
            })
            return {"ok": False, "error": "launch_failed"}

        payload = {
            "ok": True,
            "authorized": True,
            "action": plan.action,
            "app_id": plan.app_id,
            "label": plan.label,
            "risk": plan.risk,
            "permission": plan.permission,
            "rollback": "not-applicable",
        }
        _emit("system.safe_app.opened", payload)
        self.refresh(force=True, emit=True)
        return payload

    def launch_safe_app(self, app_id: str) -> dict[str, Any]:
        """Compatibility wrapper over the new authorize-then-execute contract."""
        prepared = self.plan_safe_app_launch(app_id)
        plan = prepared.get("plan") if isinstance(prepared, dict) else None
        if plan is None:
            return {
                key: value
                for key, value in dict(prepared or {}).items()
                if key != "plan"
            }
        return self.execute_safe_app_launch(plan)

    @staticmethod
    def _policy_posture(action: str, granted_permissions) -> str:
        """Read-only ALLOW / CONFIRM / DENY projection without creating audit rows."""
        from security.permissions import ACTION_POLICIES
        from security.risk import RiskLevel

        policy = ACTION_POLICIES.get(str(action or "").strip().upper())
        if policy is None:
            return "DENY"
        if policy.risk is RiskLevel.CRITICAL:
            return "DENY"
        if policy.permission not in set(granted_permissions or ()):
            return "DENY"
        if policy.confirmation_required:
            return "CONFIRM"
        return "ALLOW"


    def _security_capabilities(self) -> list[dict[str, Any]]:
        from security.permissions import ACTION_POLICIES
        from security.risk import RiskLevel

        granted = set(getattr(self.core.security_engine, "granted_permissions", ()) or ())
        items: list[dict[str, Any]] = []
        for action in self._CAPABILITY_ACTIONS:
            policy = ACTION_POLICIES.get(action)
            if policy is None:
                continue
            permission_granted = policy.permission in granted
            if policy.risk is RiskLevel.CRITICAL:
                status = "blocked"
            elif not permission_granted:
                status = "locked"
            elif policy.confirmation_required:
                status = "confirmation-required"
            else:
                status = "enabled"
            items.append({
                "action": action,
                "risk": policy.risk.name,
                "permission": policy.permission.value,
                "permission_granted": permission_granted,
                "confirmation_required": bool(policy.confirmation_required),
                "status": status,
            })
        return items

    def _recent_audit(self, limit: int = 12) -> list[dict[str, Any]]:
        try:
            rows = self.core.db.conn.execute(
                "SELECT id,timestamp,action,risk,allowed,reason "
                "FROM security_audit ORDER BY id DESC LIMIT ?",
                (max(1, min(30, int(limit))),),
            ).fetchall()
        except Exception:
            return []
        out = []
        for row in rows:
            try:
                out.append({
                    "id": int(row["id"]),
                    "timestamp": str(row["timestamp"] or "")[:80],
                    "action": str(row["action"] or "")[:80],
                    "risk": str(row["risk"] or "")[:30],
                    "allowed": bool(row["allowed"]),
                    "reason": str(row["reason"] or "")[:300],
                })
            except Exception:
                continue
        return out

    def _build_snapshot(self) -> dict[str, Any]:
        import os
        import platform
        import shutil
        import sys
        from pathlib import Path
        from security.permissions import Permission

        if not self._status_decision.allowed:
            return {
                "ok": False,
                "error": "system_status_denied",
                "reason": self._status_decision.reason,
            }

        guardian = getattr(self.core, "resource_guardian", None)
        resource = None
        if guardian is not None:
            try:
                resource = guardian.sample(include_ollama=False, force_gpu=False)
            except Exception:
                resource = None

        cpu_percent = 0.0
        cpu_physical = 0
        cpu_logical = int(os.cpu_count() or 0)
        process_rss_mb = 0.0
        try:
            import psutil
            cpu_percent = float(psutil.cpu_percent(interval=None))
            cpu_physical = int(psutil.cpu_count(logical=False) or 0)
            cpu_logical = int(psutil.cpu_count(logical=True) or cpu_logical)
            process_rss_mb = float(psutil.Process().memory_info().rss) / (1024.0 * 1024.0)
        except Exception:
            pass

        system_drive = Path.home().anchor or os.environ.get("SystemDrive", "C:") + "\\"
        try:
            disk = shutil.disk_usage(system_drive)
            disk_total_gb = disk.total / (1024.0 ** 3)
            disk_free_gb = disk.free / (1024.0 ** 3)
            disk_used_pct = (100.0 * disk.used / disk.total) if disk.total else 0.0
        except Exception:
            disk_total_gb = disk_free_gb = disk_used_pct = 0.0

        granted = sorted(
            str(getattr(permission, "value", permission))
            for permission in (getattr(self.core.security_engine, "granted_permissions", ()) or ())
        )

        ram_used = float(getattr(resource, "ram_used_pct", 0.0) or 0.0)
        ram_total = float(getattr(resource, "ram_total_gb", 0.0) or 0.0)
        ram_avail = float(getattr(resource, "ram_available_gb", 0.0) or 0.0)
        vram_used = float(getattr(resource, "vram_used_mb", 0.0) or 0.0)
        vram_total = float(getattr(resource, "vram_total_mb", 0.0) or 0.0)
        vram_pct = float(getattr(resource, "vram_used_pct", 0.0) or 0.0)
        gpu_name = str(getattr(resource, "gpu_name", "") or "")

        return {
            "ok": True,
            "read_only": False,
            "execution_enabled": True,
            "execution_scope": "safe-apps-authorized-folders-files-and-project-intelligence",
            "safe_apps": self.safe_apps(),
            "updated_at": time.time(),
            "machine": {
                "name": str(platform.node() or "PC local")[:120],
                "os": str(platform.system() or "")[:80],
                "release": str(platform.release() or "")[:80],
                "version": str(platform.version() or "")[:180],
                "architecture": str(platform.machine() or "")[:80],
                "processor": str(platform.processor() or "")[:180],
                "python": str(sys.version.split()[0])[:30],
            },
            "resources": {
                "cpu_percent": self._pct(cpu_percent),
                "cpu_physical": cpu_physical,
                "cpu_logical": cpu_logical,
                "ram_used_pct": self._pct(ram_used),
                "ram_total_gb": round(ram_total, 2),
                "ram_available_gb": round(ram_avail, 2),
                "vram_used_pct": self._pct(vram_pct),
                "vram_used_mb": round(vram_used, 0),
                "vram_total_mb": round(vram_total, 0),
                "gpu_name": gpu_name[:180],
                "disk_used_pct": self._pct(disk_used_pct),
                "disk_total_gb": round(disk_total_gb, 1),
                "disk_free_gb": round(disk_free_gb, 1),
                "aura_process_rss_mb": round(process_rss_mb, 1),
            },
            "desktop_intelligence": {
                "phase": "P0.6.5.4",
                "launcher": {
                    "mode": "fixed-safe-app-allowlist",
                    "apps": self.safe_apps(),
                    "arbitrary_executable": False,
                    "arbitrary_path": False,
                    "arbitrary_arguments": False,
                    "shell_execution": False,
                },
                "authorized_folders": self.authorized_folders(),
                "last_folder_listing": dict(self._last_folder_listing or {}),
                "last_folder_action": dict(self._last_folder_action or {}),
                "last_file_read": dict(self._last_file_read or {}),
                "last_file_analysis": dict(self._last_file_analysis or {}),
                "last_project_analysis": dict(self._last_project_analysis or {}),
                "authorized_project_intelligence": {
                    "modes": ["summary", "search", "context"],
                    "direct_child_only": True,
                    "max_files": self._AUTHORIZED_PROJECT_MAX_FILES,
                    "max_total_bytes": self._AUTHORIZED_PROJECT_MAX_TOTAL_BYTES,
                    "max_total_chars": self._AUTHORIZED_PROJECT_MAX_TOTAL_CHARS,
                    "max_result_chars": self._AUTHORIZED_PROJECT_MAX_RESULT_CHARS,
                    "provenance_by_file": True,
                    "extractive_only": True,
                    "llm_used": False,
                    "cloud_upload": False,
                    "network_access": False,
                    "recursive_scan": False,
                    "file_write": False,
                    "file_delete": False,
                },
                "local_document_intelligence": {
                    "modes": ["summary", "search", "context"],
                    "extractive_only": True,
                    "llm_used": False,
                    "cloud_upload": False,
                    "network_access": False,
                },
                "file_intelligence": {
                    "mode": "local-read-only",
                    "direct_child_only": True,
                    "supported_extensions": sorted(self._AUTHORIZED_FILE_EXTENSIONS),
                    "max_bytes": self._AUTHORIZED_FILE_MAX_BYTES,
                    "max_extract_chars": self._AUTHORIZED_FILE_MAX_CHARS,
                    "max_ui_chars": self._AUTHORIZED_FILE_UI_CHARS,
                    "cloud_upload": False,
                    "llm_analysis": False,
                    "file_write": False,
                    "file_delete": False,
                },
                "folder_access": {
                    "model": "explicit-registry-id-only",
                    "registry_file": "config/authorized_folders.json",
                    "recursive_listing": False,
                    "file_content_read": False,
                    "filesystem_write": False,
                    "filesystem_delete": False,
                    "raw_path_open": False,
                    "max_entries_per_scan": 120,
                },
                "policy": {
                    "model": "ALLOW_CONFIRM_DENY",
                    "OPEN_SAFE_APP": self._policy_posture(
                        "OPEN_SAFE_APP",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "AUTHORIZE_FOLDER": self._policy_posture(
                        "AUTHORIZE_FOLDER",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "OPEN_AUTHORIZED_FOLDER": self._policy_posture(
                        "OPEN_AUTHORIZED_FOLDER",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "LIST_AUTHORIZED_FOLDER": self._policy_posture(
                        "LIST_AUTHORIZED_FOLDER",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "READ_AUTHORIZED_FILE": self._policy_posture(
                        "READ_AUTHORIZED_FILE",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "ANALYZE_AUTHORIZED_FILE": self._policy_posture(
                        "ANALYZE_AUTHORIZED_FILE",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "ANALYZE_AUTHORIZED_PROJECT": self._policy_posture(
                        "ANALYZE_AUTHORIZED_PROJECT",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "RUN_PROGRAM": self._policy_posture(
                        "RUN_PROGRAM",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "DELETE_FILE": self._policy_posture(
                        "DELETE_FILE",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                    "MODIFY_SYSTEM": self._policy_posture(
                        "MODIFY_SYSTEM",
                        getattr(self.core.security_engine, "granted_permissions", ()),
                    ),
                },
                "audit": {
                    "source": "security_audit",
                    "safe_launch_rollback": "not-applicable",
                },
            },
            "security": {
                "policy": "SecurityPolicyEngine",
                "fail_closed": True,
                "granted_permissions": granted,
                "capabilities": self._security_capabilities(),
                "recent_audit": self._recent_audit(),
            },
        }

    def refresh(self, *, force: bool = False, emit: bool = True) -> None:
        now = time.monotonic()
        if not force and now - self._last_refresh < self._refresh_interval:
            return
        self._last_refresh = now
        try:
            snapshot = self._build_snapshot()
        except Exception as exc:
            logger.warning("System snapshot refresh failed error=%s", type(exc).__name__)
            snapshot = {"ok": False, "error": type(exc).__name__, "read_only": True}
        changed_security = json.dumps(
            (snapshot.get("security") or {}).get("capabilities") or [],
            sort_keys=True,
            ensure_ascii=False,
        ) != json.dumps(
            (self._snapshot.get("security") or {}).get("capabilities") or [],
            sort_keys=True,
            ensure_ascii=False,
        )
        self._snapshot = snapshot
        if emit and changed_security:
            _emit("system.security_snapshot", {
                "read_only": False,
                "execution_enabled": True,
                "execution_scope": "safe-apps-authorized-folders-files-and-project-intelligence",
                "capabilities": _safe((snapshot.get("security") or {}).get("capabilities") or []),
            })

    def snapshot(self) -> dict[str, Any]:
        return _safe(dict(self._snapshot or {"ok": False, "error": "system_snapshot_unavailable"}))

    def poll(self) -> None:
        self.refresh(force=False, emit=True)


class AuraCoreServiceBridge:
    """Registry of stable service facades consumed by the Three.js shell."""

    VERSION = "P0.6.5.4"

    def __init__(self, aura_core):
        self.core = aura_core
        self.voice = VoiceService(aura_core)
        self.research = ResearchService(aura_core)
        self.weather = WeatherService(aura_core)
        self.files = FileService(aura_core)
        self.productivity = ProductivityService(aura_core)
        self.memory = MemoryService(aura_core)
        self.system = SystemService(aura_core)
        _emit("bridge.services_ready", {"version": self.VERSION, "services": list(self.manifest()["services"].keys())})

    def poll(self) -> dict[str, Any]:
        self.research.poll()
        weather_payloads = self.weather.poll()
        self.files.poll()
        reminder_payloads = self.productivity.poll()
        self.memory.poll()
        self.system.poll()
        return {
            "weather": weather_payloads,
            "reminders_triggered": reminder_payloads,
        }

    def manifest(self) -> dict[str, Any]:
        core = self.core
        services = {
            "voice": {
                "available": hasattr(core, "voice_engine"),
                "exposure": "core-service",
                "operations": ["status", "stop_speaking", "speak"],
                "legacy": ["mic_start", "mic_stop"],
            },
            "research": {
                "available": hasattr(core, "internet_tools"),
                "exposure": "core-service",
                "operations": ["research_query"],
                "busy": self.research.busy,
                "chat_auto_route": True,
            },
            "weather": {
                "available": hasattr(core, "internet_tools"),
                "exposure": "core-service-passive-workspace",
                "operations": ["weather_current"],
                "busy": self.weather.busy,
                "chat_history": False,
            },
            "files": {
                "available": True,
                "exposure": "core-service-load + existing-document-fast-lane",
                "engine": "services.document_analysis",
                "operations": ["upload", "status", "clear", "ask-via-send_message"],
                "active": bool(self.files.active_context),
                "busy": self.files.busy,
            },
            "tasks": {
                "available": hasattr(core, "task_manager"),
                "exposure": "core-productivity-service + legacy-intent-via-chat",
                "operations": ["list", "create", "complete"],
            },
            "reminders": {
                "available": hasattr(core, "reminder_manager"),
                "exposure": "core-productivity-service + legacy-intent-via-chat",
                "operations": ["list", "create", "delete", "trigger-due"],
                "scheduler": "core-service-runtime-poll",
                "scheduler_interval_seconds": 1.0,
                "legacy_mainwindow_scheduler": False,
            },
            "notes": {
                "available": hasattr(core, "notes_manager"),
                "exposure": "core-productivity-service + legacy-intent-via-chat",
                "operations": ["list", "create", "delete"],
            },
            "memory": {
                "available": hasattr(core, "memory_manager"),
                "exposure": "core-memory-service + legacy-intent-via-chat",
                "operations": ["list", "create", "delete", "private-mode", "clear-profile"],
                "cached_http_snapshot": True,
                "sensitive_default": "hidden",
                "private_mode": bool(getattr(core.memory_manager, "private_mode", False)),
            },
            "agent": {
                "available": hasattr(core, "agent_orchestrator"),
                "exposure": "legacy-chat-route",
            },
            "system": {
                "available": True,
                "exposure": "core-system-service-safe-actions",
                "operations": ["status", "security-posture", "audit-read", "open-safe-app"],
                "execution_enabled": True,
                "execution_scope": "fixed-safe-app-allowlist",
                "arbitrary_process_execution": False,
                "security_engine": "SecurityPolicyEngine",
                "fail_closed": True,
                "note": "P0.6.5.3 adds deterministic local summary/search/context over authorized file content; no provider or cloud path.",
            },
        }
        return {
            "ok": True,
            "bridge_version": self.VERSION,
            "architecture": "threejs -> loopback shell -> core services -> existing engines",
            "services": services,
            "voice_status": self.voice.status(),
        }

# === AURA v2.1.1 R4 canonical MemoryService binding BEGIN ===
_AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER = MemoryService.remember


def _aura_v211_r4_memoryservice_remember(
    self,
    content: str,
    *,
    memory_type: str = "",
    importance: int = 3,
) -> dict[str, Any]:
    raw = str(content or "").replace("\x00", " ").strip()[:1800]
    if not raw:
        raise ValueError("empty_memory")

    manager = getattr(getattr(self, "core", None), "memory_manager", None)
    if manager is None:
        return _AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER(
            self,
            content,
            memory_type=memory_type,
            importance=importance,
        )

    if bool(getattr(manager, "private_mode", False)):
        # Preserve the existing service's exact private-mode behavior/error.
        return _AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER(
            self,
            content,
            memory_type=memory_type,
            importance=importance,
        )

    from runtime.aura_conversation_memory_integration_v211 import (
        ConversationMemoryIntegration,
    )

    adapter = getattr(self, "_aura_v211_conversation_memory", None)
    if adapter is None or getattr(adapter, "memory_manager", None) is not manager:
        adapter = ConversationMemoryIntegration(manager)
        self._aura_v211_conversation_memory = adapter

    decision = adapter.plan_message(raw, scope="user")
    if decision.operation == "IGNORE":
        return _AURA_V211_R4_PREVIOUS_MEMORYSERVICE_REMEMBER(
            self,
            content,
            memory_type=memory_type,
            importance=importance,
        )

    result = adapter.commit_explicit_fact(
        decision,
        explicit_user_authorization=True,
    )

    # Memory panel refresh is best-effort compatibility only. It remains a
    # legacy presentation surface and never decides canonical truth.
    refresh = getattr(self, "refresh", None)
    if callable(refresh):
        try:
            refresh(force=True, emit=True)
        except TypeError:
            try:
                refresh()
            except Exception:
                pass
        except Exception:
            pass

    fact = result.get("fact") or {}
    payload = {
        "ok": True,
        "created": decision.operation not in {"UNCHANGED"},
        "canonical": True,
        "authority": "MemoryKernelV2",
        "operation": decision.operation,
        "fact": fact,
        "conflicts": result.get("conflicts") or result.get("resolved_conflicts") or [],
        "memory": {
            "id": fact.get("fact_id"),
            "content": raw,
            "type": memory_type or "fact",
            "importance": max(1, min(5, int(importance or 3))),
            "source": "explicit_user",
            "canonical": True,
        },
    }
    return _safe(payload)


MemoryService.remember = _aura_v211_r4_memoryservice_remember
# === AURA v2.1.1 R4 canonical MemoryService binding END ===
