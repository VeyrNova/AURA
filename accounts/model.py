from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
import re

ACCOUNT_STATES_V120 = ("disconnected", "connecting", "connected", "degraded", "expired")
PROVIDERS_V120 = ("google",)
GOOGLE_SERVICES_V120 = ("gmail", "calendar", "contacts", "drive")

# AURA_V123_GOOGLE_TASKS_SERVICE_EXTENSION
GOOGLE_SERVICES_V123 = GOOGLE_SERVICES_V120 + ("tasks",)

_SECRET_KEY_RE = re.compile(r"(password|secret|token|authorization|credential_value)", re.I)

def utc_now_v120() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")

def _safe_metadata_v120(value: Mapping[str, Any] | None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, item in dict(value or {}).items():
        key = str(key)
        if _SECRET_KEY_RE.search(key):
            raise ValueError("secret-like metadata key forbidden:" + key)
        if item is None or isinstance(item, (str, int, float, bool)):
            out[key] = item
        elif isinstance(item, (list, tuple)) and all(
            entry is None or isinstance(entry, (str, int, float, bool))
            for entry in item
        ):
            out[key] = list(item)
        else:
            raise ValueError("non-scalar metadata forbidden:" + key)
    return out

@dataclass(frozen=True)
class ConnectedAccountV120:
    account_id: str
    provider: str
    display_label: str
    services: tuple[str, ...]
    credential_ref: str
    state: str = "disconnected"
    is_default_for: tuple[str, ...] = ()
    created_at: str = field(default_factory=utc_now_v120)
    updated_at: str = field(default_factory=utc_now_v120)
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        account_id = str(self.account_id or "").strip()
        provider = str(self.provider or "").strip().lower()
        label = str(self.display_label or "").strip()
        credential_ref = str(self.credential_ref or "").strip()
        state = str(self.state or "").strip().lower()
        if not account_id:
            raise ValueError("account_id required")
        if provider != "google":
            raise ValueError("unsupported provider:" + provider)
        if not label:
            raise ValueError("display_label required")
        if not credential_ref:
            raise ValueError("credential_ref required")
        if state not in ACCOUNT_STATES_V120:
            raise ValueError("invalid account state:" + state)
        services = tuple(dict.fromkeys(str(x).strip().lower() for x in self.services if str(x).strip()))
        if not services:
            raise ValueError("services required")
        unknown = sorted(set(services) - set(GOOGLE_SERVICES_V123))
        if unknown:
            raise ValueError("unsupported services:" + ",".join(unknown))
        defaults = tuple(dict.fromkeys(str(x).strip().lower() for x in self.is_default_for if str(x).strip()))
        if not set(defaults).issubset(set(services)):
            raise ValueError("default service not enabled")
        object.__setattr__(self, "account_id", account_id)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "display_label", label)
        object.__setattr__(self, "credential_ref", credential_ref)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "services", services)
        object.__setattr__(self, "is_default_for", defaults)
        object.__setattr__(self, "metadata", _safe_metadata_v120(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_id": self.account_id,
            "provider": self.provider,
            "display_label": self.display_label,
            "services": list(self.services),
            "credential_ref": self.credential_ref,
            "state": self.state,
            "is_default_for": list(self.is_default_for),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ConnectedAccountV120":
        return cls(
            account_id=str(payload["account_id"]),
            provider=str(payload["provider"]),
            display_label=str(payload["display_label"]),
            services=tuple(payload.get("services", ())),
            credential_ref=str(payload["credential_ref"]),
            state=str(payload.get("state", "disconnected")),
            is_default_for=tuple(payload.get("is_default_for", ())),
            created_at=str(payload.get("created_at", utc_now_v120())),
            updated_at=str(payload.get("updated_at", utc_now_v120())),
            metadata=dict(payload.get("metadata", {})),
        )

__all__ = [
    "ACCOUNT_STATES_V120",
    "PROVIDERS_V120",
    "GOOGLE_SERVICES_V120",
    "GOOGLE_SERVICES_V123",
    "ConnectedAccountV120",
    "utc_now_v120",
]
