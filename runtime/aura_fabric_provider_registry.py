from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import json
import os

ALLOWED_TOS_STATUSES = {"reference_allowed", "official_allowed", "local", "pending_review", "blocked"}

def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _now() -> datetime:
    return datetime.now(timezone.utc)

@dataclass(frozen=True)
class ProviderPolicyDecision:
    provider_id: str
    eligible: bool
    state: str
    reason: str
    stale: bool
    configured: bool

class ProviderRegistry:
    def __init__(self, seed: dict[str, Any]):
        if seed.get("schema") != "aura.fabric.provider-registry-seed.v1":
            raise ValueError("unsupported provider registry seed schema")
        self.seed = seed
        self._providers: dict[str, dict[str, Any]] = {}
        for raw in seed.get("providers", []):
            item = dict(raw)
            pid = str(item.get("provider_id") or "").strip()
            if not pid or pid in self._providers:
                raise ValueError(f"invalid/duplicate provider id: {pid!r}")
            tos = item.get("tos_status")
            if tos not in ALLOWED_TOS_STATUSES:
                raise ValueError(f"invalid tos status for {pid}: {tos}")
            self._providers[pid] = item

    @classmethod
    def from_path(cls, path: Path | str) -> "ProviderRegistry":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    def ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._providers))

    def get(self, provider_id: str) -> dict[str, Any]:
        return dict(self._providers[provider_id])

    def evaluate(
        self,
        provider_id: str,
        *,
        now: datetime | None = None,
        configured: bool | None = None,
    ) -> ProviderPolicyDecision:
        item = self._providers[provider_id]
        now = now or _now()
        tos = item["tos_status"]
        configured_value = bool(item.get("default_configured", False) if configured is None else configured)

        if tos == "blocked":
            return ProviderPolicyDecision(provider_id, False, "blocked", "provider policy explicitly blocked", False, configured_value)
        if tos == "pending_review":
            return ProviderPolicyDecision(provider_id, False, "pending_review", "provider requires terms/policy review", False, configured_value)
        if tos == "local":
            return ProviderPolicyDecision(provider_id, True, "eligible_local", "local provider has no remote ToS freshness dependency", False, configured_value)

        ttl_days = item.get("verification_ttl_days")
        verified = _parse_dt(item["last_verified_at"])
        stale = bool(ttl_days is not None and now > verified + timedelta(days=float(ttl_days)))
        if stale:
            return ProviderPolicyDecision(
                provider_id,
                False,
                "stale_review_required",
                "remote provider policy snapshot expired; re-verification required",
                True,
                configured_value,
            )

        if not bool(item.get("default_policy_eligible", False)):
            return ProviderPolicyDecision(provider_id, False, "policy_disabled", "provider is not policy eligible", False, configured_value)

        return ProviderPolicyDecision(
            provider_id,
            True,
            "eligible_reference" if tos == "reference_allowed" else "eligible_official",
            "fresh policy snapshot and no blocking policy state",
            False,
            configured_value,
        )

    def public_snapshot(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or _now()
        providers = []
        eligible = 0
        stale = 0
        blocked = 0
        local = 0
        for pid in self.ids():
            raw = self._providers[pid]
            decision = self.evaluate(pid, now=now)
            if decision.eligible:
                eligible += 1
            if decision.stale:
                stale += 1
            if decision.state == "blocked":
                blocked += 1
            if raw.get("tos_status") == "local":
                local += 1
            providers.append({
                "provider_id": pid,
                "display_name": raw.get("display_name"),
                "connection_mode": raw.get("connection_mode"),
                "credential_env_names": list(raw.get("credential_env_names") or []),
                "tos_status": raw.get("tos_status"),
                "policy_basis": raw.get("policy_basis"),
                "last_verified_at": raw.get("last_verified_at"),
                "verification_ttl_days": raw.get("verification_ttl_days"),
                "source_url": raw.get("source_url"),
                "policy": {
                    "eligible": decision.eligible,
                    "state": decision.state,
                    "reason": decision.reason,
                    "stale": decision.stale,
                },
            })
        return {
            "schema": "aura.fabric.provider-registry-public.v1",
            "provider_count": len(providers),
            "policy_eligible_count": eligible,
            "stale_count": stale,
            "blocked_count": blocked,
            "local_count": local,
            "clean_room": bool(self.seed.get("clean_room")),
            "source_policy": dict(self.seed.get("source_policy") or {}),
            "providers": providers,
        }

    def secret_scan(self) -> dict[str, Any]:
        suspicious = []
        for pid, item in self._providers.items():
            for key, value in item.items():
                if key in {"credential_value", "api_key", "token", "secret"} and value:
                    suspicious.append({"provider_id": pid, "field": key})
            for env_name in item.get("credential_env_names") or []:
                if "=" in str(env_name):
                    suspicious.append({"provider_id": pid, "field": "credential_env_names"})
        return {"ok": not suspicious, "findings": suspicious}

def default_registry_path() -> Path:
    root = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
    return root / "ci" / "aura_fabric_provider_registry_seed.json"

def load_default_registry() -> ProviderRegistry:
    return ProviderRegistry.from_path(default_registry_path())

def default_public_provider_snapshot() -> dict[str, Any]:
    return load_default_registry().public_snapshot()
