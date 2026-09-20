from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Iterable
import time

@dataclass(frozen=True)
class CatalogEntry:
    public_id: str
    provider_id: str
    provider_model_id: str
    display_name: str
    capabilities: tuple[str, ...] = ("text", "streaming")
    context_window: int | None = None
    max_output_tokens: int | None = None
    aliases: tuple[str, ...] = ()
    local: bool = False
    enabled: bool = True
    tos_status: str = "unknown"
    free_tier: bool = False
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def slug(self) -> str:
        return f"{self.provider_id}/{self.provider_model_id}"

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "id": self.public_id,
            "object": "model",
            "created": 0,
            "owned_by": self.provider_id,
            "provider_id": self.provider_id,
            "provider_model_id": self.provider_model_id,
            "route_slug": self.slug,
            "display_name": self.display_name,
            "capabilities": list(self.capabilities),
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "aliases": list(self.aliases),
            "local": self.local,
            "enabled": self.enabled,
            "tos_status": self.tos_status,
            "free_tier": self.free_tier,
            "pricing": {
                "input_per_million": self.input_cost_per_million,
                "output_per_million": self.output_cost_per_million,
            },
        }

class ModelCatalog:
    def __init__(self):
        self._entries: dict[str, CatalogEntry] = {}
        self._aliases: dict[str, list[str]] = {}
        self.updated_at = int(time.time())

    def register(self, entry: CatalogEntry, *, replace: bool = False) -> None:
        if not entry.public_id.strip():
            raise ValueError("public_id is required")
        if entry.public_id in self._entries and not replace:
            raise ValueError(f"model already registered: {entry.public_id}")
        self._entries[entry.public_id] = entry
        for alias in entry.aliases:
            self._aliases.setdefault(alias, [])
            if entry.public_id not in self._aliases[alias]:
                self._aliases[alias].append(entry.public_id)
        self._aliases.setdefault(entry.public_id, [entry.public_id])
        self._aliases.setdefault(entry.slug, [entry.public_id])
        self.updated_at = int(time.time())

    def set_alias(self, alias: str, model_ids: Iterable[str]) -> None:
        values = [m for m in model_ids if m in self._entries]
        if not alias.strip() or not values:
            raise ValueError("alias requires at least one registered model")
        self._aliases[alias] = values
        self.updated_at = int(time.time())

    def get(self, public_id: str) -> CatalogEntry:
        return self._entries[public_id]

    def entries(self, *, enabled_only: bool = True) -> tuple[CatalogEntry, ...]:
        values = list(self._entries.values())
        if enabled_only:
            values = [e for e in values if e.enabled]
        values.sort(key=lambda e: (e.provider_id, e.public_id))
        return tuple(values)

    def resolve_ids(self, alias_or_id: str) -> tuple[str, ...]:
        if alias_or_id in self._aliases:
            return tuple(self._aliases[alias_or_id])
        if alias_or_id in self._entries:
            return (alias_or_id,)
        return ()

    def route_slugs(self, alias_or_id: str) -> tuple[str, ...]:
        return tuple(self._entries[mid].slug for mid in self.resolve_ids(alias_or_id))

    def openai_list(self) -> dict[str, Any]:
        return {
            "object": "list",
            "data": [entry.to_public_dict() for entry in self.entries()],
        }

    def aura_catalog(self) -> dict[str, Any]:
        return {
            "schema": "aura.fabric.model-catalog.v1",
            "updated_at": self.updated_at,
            "count": len(self.entries()),
            "models": [entry.to_public_dict() for entry in self.entries()],
            "aliases": {k: list(v) for k, v in sorted(self._aliases.items())},
        }
