"""Native memory domain records."""
from __future__ import annotations

from dataclasses import dataclass

@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    content: str
    normalized_content: str
    memory_type: str
    scope: str
    scope_id: str
    importance: int
    confidence: float
    source: str
    is_sensitive: bool
    created_at: str
    updated_at: str
    expires_at: str | None
    status: str

    def as_payload(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "content": self.content,
            "memory_type": self.memory_type,
            "scope": self.scope,
            "scope_id": self.scope_id,
            "importance": self.importance,
            "confidence": self.confidence,
            "source": self.source,
            "is_sensitive": self.is_sensitive,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "expires_at": self.expires_at,
            "status": self.status,
        }
