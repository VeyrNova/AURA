from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from runtime.aura_roadmap_service import (
    ALLOWED_STATUSES,
    RoadmapImmutableFieldError,
    RoadmapService,
    RoadmapValidationError,
)
from runtime.aura_roadmap_schedule_engine import RoadmapScheduleEngine

BRIDGE_SCHEMA = "aura.roadmap.http-bridge.v25e1.v1"
DEFAULT_ROOT = Path(r"C:\AURA GPT version")
ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,48}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ].{1,40})?$")


def _text(value: Any, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _date(value: Any) -> Optional[str]:
    raw = _text(value, 48)
    if not raw:
        return None
    if not DATE_RE.match(raw):
        raise RoadmapValidationError(f"Invalid date value: {raw!r}")
    return raw


def _number(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        number = float(value)
    except Exception:
        return float(default)
    return max(minimum, min(maximum, number))


def _dependencies(value: Any) -> List[str]:
    if value is None:
        return []
    rows = value if isinstance(value, list) else str(value).split(",")
    out: List[str] = []
    for item in rows:
        token = _text(item, 48)
        if token and ID_RE.match(token) and token not in out:
            out.append(token)
    return out[:32]


def _phase(value: Any) -> str:
    raw = _text(value, 100)
    return raw or "Unassigned"


def _milestone_patch(payload: Dict[str, Any]) -> Dict[str, Any]:
    patch: Dict[str, Any] = {}
    for key, limit in (
        ("phase", 100),
        ("version", 80),
        ("title", 240),
        ("description", 1600),
        ("confidence", 80),
    ):
        if key in payload:
            patch[key] = _phase(payload[key]) if key == "phase" else _text(payload[key], limit)

    if "weight" in payload:
        patch["weight"] = _number(payload.get("weight"), 0.0, 100.0, 1.0)
    if "dependencies" in payload:
        patch["dependencies"] = _dependencies(payload.get("dependencies"))

    forecast_in = payload.get("forecast")
    if isinstance(forecast_in, dict):
        forecast: Dict[str, Any] = {}
        if "status" in forecast_in:
            status = _text(forecast_in.get("status"), 40).lower()
            if status not in ALLOWED_STATUSES:
                raise RoadmapValidationError(f"Unsupported status: {status}")
            forecast["status"] = status
        if "progress_percent" in forecast_in:
            forecast["progress_percent"] = _number(
                forecast_in.get("progress_percent"), 0.0, 100.0, 0.0
            )
        if "start" in forecast_in:
            forecast["start"] = _date(forecast_in.get("start"))
        if "end" in forecast_in:
            forecast["end"] = _date(forecast_in.get("end"))
        if forecast:
            patch["forecast"] = forecast

    actual_in = payload.get("actual")
    if isinstance(actual_in, dict):
        actual: Dict[str, Any] = {}
        if "start" in actual_in:
            actual["start"] = _date(actual_in.get("start"))
        if "end" in actual_in:
            actual["end"] = _date(actual_in.get("end"))
        if actual:
            patch["actual"] = actual

    return patch


class RoadmapHttpBridgeV25E:
    """Small authenticated-loopback-facing facade over RoadmapService.

    The HTTP server remains responsible for token/origin checks.
    This class validates all mutation payloads and never exposes baseline edits.
    """

    def __init__(self, root: Path | str = DEFAULT_ROOT) -> None:
        self.root = Path(root)
        self.service = RoadmapService(root=self.root)
        self.engine = RoadmapScheduleEngine(root=self.root, service=self.service)

    def capability_snapshot(self) -> Dict[str, Any]:
        caps = self.service.capability_snapshot()
        return {
            "schema": BRIDGE_SCHEMA,
            "roadmap_service": caps,
            "operations": [
                "validate",
                "add_milestone",
                "update_milestone",
                "move_milestone",
                "archive_milestone",
                "delete_milestone_soft",
                "restore_milestone",
                "rename_phase",
                "archive_phase",
                "restore_revision",
            ],
            "baseline_mutation": False,
            "project_field_mutation": False,
        }

    def snapshot(self) -> Dict[str, Any]:
        roadmap = self.service.load()
        schedule = self.engine.write_state()
        phases: List[str] = []
        for m in roadmap.get("milestones", []):
            phase = _phase(m.get("phase"))
            if phase not in phases:
                phases.append(phase)
        return {
            "ok": True,
            "schema": BRIDGE_SCHEMA,
            "roadmap": roadmap,
            "schedule": schedule,
            "phases": phases,
            "revisions": self.service.list_revisions()[:60],
            "capabilities": self.capability_snapshot(),
        }

    def _after(self, result: Any = None) -> Dict[str, Any]:
        out = self.snapshot()
        if result is not None:
            out["mutation"] = {
                "revision_id": getattr(result, "revision_id", None),
                "operation": getattr(result, "operation", None),
                "milestone_id": getattr(result, "milestone_id", None),
                "progress_percent": getattr(result, "progress_percent", None),
                "roadmap_sha256": getattr(result, "roadmap_sha256", None),
                "changed_at": getattr(result, "changed_at", None),
            }
        return out

    def mutate(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise RoadmapValidationError("Mutation payload must be an object.")

        operation = _text(payload.get("operation"), 64).lower()
        actor = _text(payload.get("actor"), 80) or "roadmap-ui-v25e"
        reason = _text(payload.get("reason"), 300) or f"Roadmap UI {operation}"

        if operation == "validate":
            return self.snapshot()

        if operation == "add_milestone":
            raw = payload.get("milestone")
            if not isinstance(raw, dict):
                raise RoadmapValidationError("milestone object required.")
            mid = _text(raw.get("id"), 48)
            if not ID_RE.match(mid):
                raise RoadmapValidationError("Invalid milestone id.")
            milestone = _milestone_patch(raw)
            milestone["id"] = mid
            milestone.setdefault("phase", _phase(raw.get("phase")))
            milestone.setdefault("version", _text(raw.get("version"), 80))
            milestone.setdefault("title", _text(raw.get("title"), 240) or mid)
            milestone.setdefault("description", _text(raw.get("description"), 1600))
            milestone.setdefault("weight", _number(raw.get("weight"), 0.0, 100.0, 1.0))
            milestone.setdefault("forecast", {
                "status": "planned",
                "progress_percent": 0,
                "start": None,
                "end": None,
            })
            milestone.setdefault("actual", {"start": None, "end": None})
            result = self.service.add_milestone(
                milestone,
                after_id=_text(payload.get("after_id"), 48) or None,
                before_id=_text(payload.get("before_id"), 48) or None,
                actor=actor,
                reason=reason,
            )
            return self._after(result)

        mid = _text(payload.get("milestone_id"), 48)
        if operation not in {"rename_phase", "archive_phase", "restore_revision"}:
            if not ID_RE.match(mid):
                raise RoadmapValidationError("Valid milestone_id required.")

        if operation == "update_milestone":
            raw_patch = payload.get("patch")
            if not isinstance(raw_patch, dict):
                raise RoadmapValidationError("patch object required.")
            patch = _milestone_patch(raw_patch)
            if not patch:
                raise RoadmapValidationError("No editable field supplied.")
            result = self.service.update_milestone(
                mid, patch, actor=actor, reason=reason
            )
            return self._after(result)

        if operation == "move_milestone":
            before_id = _text(payload.get("before_id"), 48) or None
            after_id = _text(payload.get("after_id"), 48) or None
            result = self.service.move_milestone(
                mid,
                before_id=before_id,
                after_id=after_id,
                actor=actor,
                reason=reason,
            )
            return self._after(result)

        if operation == "archive_milestone":
            return self._after(
                self.service.archive_milestone(mid, actor=actor, reason=reason)
            )

        if operation == "delete_milestone_soft":
            return self._after(
                self.service.delete_milestone_soft(mid, actor=actor, reason=reason)
            )

        if operation == "restore_milestone":
            status = _text(payload.get("status"), 40).lower() or "planned"
            return self._after(
                self.service.restore_milestone(
                    mid, status=status, actor=actor, reason=reason
                )
            )

        if operation == "rename_phase":
            old_phase = _phase(payload.get("old_phase"))
            new_phase = _phase(payload.get("new_phase"))
            if old_phase == new_phase:
                raise RoadmapValidationError("Phase name unchanged.")
            doc = self.service.load()
            ids = [
                str(m.get("id"))
                for m in doc.get("milestones", [])
                if _phase(m.get("phase")) == old_phase
            ]
            if not ids:
                raise RoadmapValidationError("Phase not found.")
            revisions = []
            for item_id in ids:
                result = self.service.update_milestone(
                    item_id,
                    {"phase": new_phase},
                    actor=actor,
                    reason=f"{reason}: {old_phase} -> {new_phase}",
                )
                revisions.append(result.revision_id)
            out = self.snapshot()
            out["mutation"] = {
                "operation": operation,
                "count": len(ids),
                "revision_ids": revisions,
                "old_phase": old_phase,
                "new_phase": new_phase,
            }
            return out

        if operation == "archive_phase":
            target_phase = _phase(payload.get("phase"))
            doc = self.service.load()
            ids = [
                str(m.get("id"))
                for m in doc.get("milestones", [])
                if _phase(m.get("phase")) == target_phase
                and not (m.get("lifecycle") or {}).get("archived")
                and not (m.get("lifecycle") or {}).get("deleted")
            ]
            if not ids:
                raise RoadmapValidationError("No active milestone in phase.")
            revisions = []
            for item_id in ids:
                result = self.service.archive_milestone(
                    item_id,
                    actor=actor,
                    reason=f"{reason}: phase {target_phase}",
                )
                revisions.append(result.revision_id)
            out = self.snapshot()
            out["mutation"] = {
                "operation": operation,
                "count": len(ids),
                "revision_ids": revisions,
                "phase": target_phase,
            }
            return out

        if operation == "restore_revision":
            revision_id = _text(payload.get("revision_id"), 120)
            if not revision_id:
                raise RoadmapValidationError("revision_id required.")
            return self._after(
                self.service.restore_revision(
                    revision_id, actor=actor, reason=reason
                )
            )

        raise RoadmapValidationError(f"Unsupported operation: {operation}")
