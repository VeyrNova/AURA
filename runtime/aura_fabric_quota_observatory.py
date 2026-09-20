from __future__ import annotations

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any
import json
import os

def _parse_dt(value: str) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

def _now() -> datetime:
    return datetime.now(timezone.utc)

class QuotaObservatory:
    def __init__(self, snapshot: dict[str, Any]):
        if snapshot.get("schema") != "aura.fabric.free-tier-observatory-snapshot.v1":
            raise ValueError("unsupported quota snapshot schema")
        self.snapshot = snapshot

    @classmethod
    def from_path(cls, path: Path | str) -> "QuotaObservatory":
        return cls(json.loads(Path(path).read_text(encoding="utf-8")))

    @staticmethod
    def _stale(item: dict[str, Any], now: datetime) -> bool:
        ttl = item.get("ttl_days")
        if ttl is None:
            return False
        observed = _parse_dt(item["observed_at"])
        return now > observed + timedelta(days=float(ttl))

    @staticmethod
    def _monthly_tokens(item: dict[str, Any]) -> int | None:
        if not item.get("convertible_to_monthly_tokens"):
            return None
        value = item.get("value")
        unit = item.get("unit")
        if not isinstance(value, (int, float)):
            return None
        if unit == "tokens/month":
            return int(value)
        if unit == "tokens/day":
            return int(value * 30)
        if unit == "tokens/week":
            return int(value * (30 / 7))
        return None

    def summary(self, *, now: datetime | None = None) -> dict[str, Any]:
        now = now or _now()
        headline = dict(self.snapshot.get("reference_headline") or {})
        headline_stale = self._stale(headline, now) if headline.get("observed_at") else True

        observations = []
        token_floor = 0
        stale_count = 0
        convertible_count = 0
        for raw in self.snapshot.get("observations", []):
            item = dict(raw)
            stale = self._stale(item, now)
            monthly = None if stale else self._monthly_tokens(item)
            if stale:
                stale_count += 1
            if monthly is not None:
                convertible_count += 1
                token_floor += monthly
            item["stale"] = stale
            item["monthly_token_equivalent"] = monthly
            observations.append(item)

        return {
            "schema": "aura.fabric.free-tier-observatory.v1",
            "generated_at": now.isoformat(),
            "guaranteed_free_tokens_per_month": int(self.snapshot.get("guaranteed_free_tokens_per_month") or 0),
            "reference_headline_tokens_per_month": headline.get("tokens_per_month"),
            "reference_headline_operator": headline.get("operator"),
            "reference_headline_stale": headline_stale,
            "reference_headline_independently_verified_by_aura": bool(headline.get("independently_verified_by_aura", False)),
            "reference_headline_guaranteed": bool(headline.get("guaranteed", False)),
            "known_token_equivalent_reference_floor_per_month": token_floor,
            "convertible_fresh_observations": convertible_count,
            "observation_count": len(observations),
            "stale_observation_count": stale_count,
            "observations": observations,
            "policy": {
                "never_convert_requests_or_compute_units_to_tokens": True,
                "never_count_unknown_or_unlimited_as_numeric_tokens": True,
                "stale_observations_excluded_from_token_floor": True,
                "provider_limits_may_change": True,
            },
        }

def default_quota_snapshot_path() -> Path:
    root = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()
    return root / "ci" / "aura_fabric_free_tier_snapshot_2026_08_30.json"

def load_default_observatory() -> QuotaObservatory:
    return QuotaObservatory.from_path(default_quota_snapshot_path())

def default_quota_summary() -> dict[str, Any]:
    return load_default_observatory().summary()
