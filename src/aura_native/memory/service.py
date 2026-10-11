"""Bus-facing native memory service."""
from __future__ import annotations

from pathlib import Path

from aura_native.core.contracts import CommandError, CommandResult, Event
from aura_native.memory.privacy import looks_sensitive
from aura_native.storage.database import NativeDatabase
from aura_native.storage.memory_repository import MemoryRepository

class MemoryService:
    def __init__(self, db_path: str | Path) -> None:
        self.database = NativeDatabase(db_path)
        self.repository = MemoryRepository(self.database)
        self._bus = None

    def bind(self, bus) -> None:
        self._bus = bus
        bus.register_handler("memory.create", self._create)
        bus.register_handler("memory.get", self._get)
        bus.register_handler("memory.list", self._list)
        bus.register_handler("memory.search", self._search)
        bus.register_handler("memory.forget", self._forget)
        bus.register_handler("memory.clear_session", self._clear_session)

    @staticmethod
    def _result(command, *, ok: bool, status: str, payload=None, error=None):
        return CommandResult(
            command.command_id,
            ok,
            status,
            payload=payload or {},
            error=error,
            correlation_id=command.correlation_id,
            session_id=command.session_id,
            source="memory",
        )

    def _publish(self, command, name: str, payload: dict[str, object]) -> None:
        if self._bus is not None:
            self._bus.publish(
                Event(
                    name=name,
                    payload=payload,
                    correlation_id=command.correlation_id,
                    session_id=command.session_id,
                    source="memory",
                )
            )

    def _create(self, command, token):
        if token.cancelled:
            return self._result(command, ok=False, status="cancelled", error=CommandError("cancelled", "command cancelled"))
        p = command.payload
        try:
            content = str(p.get("content") or "").strip()
            if not content:
                raise ValueError("content is required")
            scope = str(p.get("scope") or "user").lower()
            scope_id = str(p.get("scope_id") or (command.session_id if scope == "session" else "default"))
            sensitive = bool(p.get("is_sensitive", False)) or looks_sensitive(content)
            record, created = self.repository.create(
                content,
                memory_type=str(p.get("memory_type") or "fact"),
                scope=scope,
                scope_id=scope_id,
                importance=int(p.get("importance") or 3),
                confidence=float(p.get("confidence") if p.get("confidence") is not None else 1.0),
                source=str(p.get("source") or "explicit_user"),
                is_sensitive=sensitive,
            )
            payload = {"memory": record.as_payload(), "created": created}
            self._publish(command, "memory.created" if created else "memory.updated", payload)
            return self._result(command, ok=True, status="created" if created else "existing", payload=payload)
        except (TypeError, ValueError) as exc:
            return self._result(command, ok=False, status="invalid", error=CommandError("invalid_memory", str(exc)))

    def _get(self, command, token):
        record = self.repository.get(
            str(command.payload.get("memory_id") or ""),
            include_sensitive=bool(command.payload.get("include_sensitive", False)),
        )
        payload = {"memory": record.as_payload() if record else None}
        self._publish(command, "memory.read", payload)
        return self._result(command, ok=record is not None, status="ok" if record else "not_found", payload=payload)

    def _list(self, command, token):
        p = command.payload
        records = self.repository.list(
            limit=int(p.get("limit") or 20),
            scope=str(p.get("scope")) if p.get("scope") is not None else None,
            scope_id=str(p.get("scope_id")) if p.get("scope_id") is not None else None,
            include_sensitive=bool(p.get("include_sensitive", False)),
        )
        payload = {"memories": tuple(record.as_payload() for record in records), "count": len(records)}
        self._publish(command, "memory.listed", payload)
        return self._result(command, ok=True, status="ok", payload=payload)

    def _search(self, command, token):
        p = command.payload
        records = self.repository.search(
            str(p.get("query") or ""),
            limit=int(p.get("limit") or 10),
            include_sensitive=bool(p.get("include_sensitive", False)),
        )
        payload = {"memories": tuple(record.as_payload() for record in records), "count": len(records)}
        self._publish(command, "memory.search_completed", payload)
        return self._result(command, ok=True, status="ok", payload=payload)

    def _forget(self, command, token):
        memory_id = str(command.payload.get("memory_id") or "").strip()
        record = self.repository.forget(memory_id)
        payload = {"memory_id": memory_id, "forgotten": record is not None}
        if record is not None:
            self._publish(command, "memory.forgotten", payload)
        return self._result(command, ok=record is not None, status="forgotten" if record else "not_found", payload=payload)

    def _clear_session(self, command, token):
        session_id = str(command.payload.get("session_id") or command.session_id)
        count = self.repository.clear_session(session_id)
        payload = {"session_id": session_id, "count": count}
        self._publish(command, "memory.session_cleared", payload)
        return self._result(command, ok=True, status="ok", payload=payload)

    def execute_prepared_action(self, action_id, repository):
        action = repository.get(action_id)
        if not action or action.state != "confirmed" or action.action_type not in ("memory.create", "memory.forget"):
            raise ValueError("invalid_prepared_action")
        if action.action_type == "memory.create":
            content = str(action.payload.get("content") or "").strip()
            if not content: raise ValueError("invalid_memory")
            self.repository.create(content, memory_type="fact", scope="user", scope_id="default", importance=3, confidence=1.0, source="explicit_user", is_sensitive=looks_sensitive(content))
        else:
            if self.repository.forget(str(action.payload.get("memory_id") or "")) is None:
                raise ValueError("memory_not_found")
        repository.mark_executed(action_id)
