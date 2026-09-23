from __future__ import annotations

import copy
import json
import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from runtime.aura_roadmap_service import RoadmapService, RoadmapValidationError

SCHEDULE_SCHEMA = "aura.roadmap.schedule-state.v25c.v1"
ENGINE_SCHEMA = "aura.roadmap.schedule-engine.v25c.v1"
DEFAULT_ROOT = Path(r"C:\AURA GPT version")


def _date_of(value: Any) -> Optional[date]:
    if value in (None, ""):
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise RoadmapValidationError(f"Invalid schedule date: {value!r}") from exc


def _iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def _days_inclusive(start: Optional[date], end: Optional[date]) -> int:
    if not start or not end:
        return 0
    return max(0, (end - start).days + 1)


def _status(m: Dict[str, Any]) -> str:
    return str((m.get("forecast") or {}).get("status") or "").strip().lower()


def _progress(m: Dict[str, Any]) -> float:
    try:
        return max(0.0, min(100.0, float((m.get("forecast") or {}).get("progress_percent") or 0.0)))
    except Exception:
        return 0.0


def _weight(m: Dict[str, Any]) -> float:
    try:
        return max(0.0, float(m.get("weight") or 0.0))
    except Exception:
        return 0.0


def _is_inactive(m: Dict[str, Any]) -> bool:
    life = m.get("lifecycle") or {}
    return any(bool(life.get(k)) for k in ("archived", "cancelled", "deleted"))


def _is_baseline_milestone(m: Dict[str, Any]) -> bool:
    baseline = m.get("baseline")
    if not isinstance(baseline, dict):
        return False
    status = str(baseline.get("status") or "").strip().lower()
    if status in {"not_in_baseline", "not_in_2026_08_30_baseline"}:
        return False
    return _date_of(baseline.get("start")) is not None and _date_of(baseline.get("end")) is not None


class RoadmapScheduleEngine:
    """Pure deterministic schedule projection for the editable AURA roadmap.

    Source of truth: aura_master_roadmap_v2.json
    Derived cache: aura_roadmap_schedule_state.json

    V25-C intentionally does not bind to Project Active/UI/conversation/ADF.
    """

    def __init__(
        self,
        root: Path | str = DEFAULT_ROOT,
        service: Optional[RoadmapService] = None,
        state_path: Optional[Path | str] = None,
    ) -> None:
        self.root = Path(root)
        self.service = service or RoadmapService(root=self.root)
        self.state_path = Path(state_path) if state_path else (
            self.root / "data" / "roadmap" / "aura_roadmap_schedule_state.json"
        )

    def capability_snapshot(self) -> Dict[str, Any]:
        return {
            "schema": ENGINE_SCHEMA,
            "baseline_planned_progress": True,
            "baseline_actual_progress": True,
            "earned_schedule_date": True,
            "execution_variance_days": True,
            "forecast_finish": True,
            "project_schedule_variance_days": True,
            "scope_addition_workload": True,
            "scope_critical_path_impact": True,
            "confidence_range": True,
            "last_next_action_derivation": True,
            "project_active_binding": False,
            "ui_binding": False,
            "conversation_binding": False,
            "developer_fabric_binding": False,
        }

    def _baseline_rows(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [m for m in doc.get("milestones", []) if _is_baseline_milestone(m) and not _is_inactive(m)]

    def _post_baseline_rows(self, doc: Dict[str, Any]) -> List[Dict[str, Any]]:
        return [m for m in doc.get("milestones", []) if not _is_baseline_milestone(m) and not _is_inactive(m)]

    def _planned_fraction(self, m: Dict[str, Any], when: date) -> float:
        b = m.get("baseline") or {}
        start = _date_of(b.get("start"))
        end = _date_of(b.get("end"))
        if not start or not end:
            return 0.0
        if when < start:
            return 0.0
        if when > end:
            return 1.0
        span = max(1, (end - start).days + 1)
        elapsed = (when - start).days + 1
        return max(0.0, min(1.0, elapsed / span))

    def baseline_planned_progress(self, doc: Dict[str, Any], when: date) -> float:
        rows = self._baseline_rows(doc)
        total = sum(_weight(m) for m in rows)
        if total <= 0:
            return 0.0
        earned = sum(_weight(m) * self._planned_fraction(m, when) for m in rows)
        return round(earned / total * 100.0, 1)

    def baseline_actual_progress(self, doc: Dict[str, Any]) -> float:
        rows = self._baseline_rows(doc)
        total = sum(_weight(m) for m in rows)
        if total <= 0:
            return 0.0
        earned = sum(_weight(m) * _progress(m) / 100.0 for m in rows)
        return round(earned / total * 100.0, 1)

    def earned_schedule_date(
        self,
        doc: Dict[str, Any],
        actual_baseline_progress: float,
        start: date,
        finish: date,
    ) -> date:
        if finish < start:
            raise RoadmapValidationError("Baseline finish is before project start.")
        best = start
        best_delta = float("inf")
        cursor = start
        while cursor <= finish:
            p = self.baseline_planned_progress(doc, cursor)
            delta = abs(p - actual_baseline_progress)
            if delta < best_delta:
                best = cursor
                best_delta = delta
            cursor += timedelta(days=1)
        return best

    def _scope_metrics(self, doc: Dict[str, Any], pace_adjusted_finish: date) -> Dict[str, Any]:
        rows = self._post_baseline_rows(doc)
        total_weight = sum(_weight(m) for m in rows)
        remaining_weight = sum(_weight(m) * (100.0 - _progress(m)) / 100.0 for m in rows)

        total_workload_days = 0
        remaining_workload_days = 0
        explicit_remaining_ends: List[date] = []
        completed = 0

        for m in rows:
            f = m.get("forecast") or {}
            fs = _date_of(f.get("start"))
            fe = _date_of(f.get("end"))
            duration = _days_inclusive(fs, fe)
            total_workload_days += duration
            if _progress(m) >= 100 or _status(m) == "done":
                completed += 1
            else:
                if duration:
                    remaining_workload_days += max(1, round(duration * (100.0 - _progress(m)) / 100.0))
                if fe:
                    explicit_remaining_ends.append(fe)

        scope_floor = max(explicit_remaining_ends) if explicit_remaining_ends else None
        impact = 0
        if scope_floor and scope_floor > pace_adjusted_finish:
            impact = (scope_floor - pace_adjusted_finish).days

        return {
            "added_scope_count": len(rows),
            "added_scope_completed_count": completed,
            "added_scope_weight": round(total_weight, 3),
            "added_scope_remaining_weight": round(remaining_weight, 3),
            "added_scope_workload_days": total_workload_days,
            "added_scope_remaining_workload_days": remaining_workload_days,
            "scope_schedule_floor": _iso(scope_floor),
            "scope_critical_path_impact_days": impact,
            "dependency_model": "date-floor until explicit dependencies are populated",
        }

    def _confidence(self, doc: Dict[str, Any], as_of: date) -> Tuple[int, str, Dict[str, float]]:
        baseline = self._baseline_rows(doc)
        post = self._post_baseline_rows(doc)
        all_active = baseline + post

        baseline_date_coverage = (
            sum(1 for m in baseline if _date_of((m.get("baseline") or {}).get("start")) and _date_of((m.get("baseline") or {}).get("end")))
            / max(1, len(baseline))
        )
        done = [m for m in all_active if _progress(m) >= 100 or _status(m) == "done"]
        actual_coverage = (
            sum(1 for m in done if _date_of((m.get("actual") or {}).get("end")))
            / max(1, len(done))
        )
        remaining = [m for m in all_active if _progress(m) < 100 and _status(m) not in {"done", "archived", "cancelled", "deleted"}]
        forecast_coverage = (
            sum(1 for m in remaining if _date_of((m.get("forecast") or {}).get("end")))
            / max(1, len(remaining))
        )

        confidence_labels = {"certifié", "certified", "réel", "reel"}
        evidence_quality = (
            sum(1 for m in done if str(m.get("reconciled_confidence") or m.get("confidence") or "").strip().lower() in confidence_labels)
            / max(1, len(done))
        )

        score = round(100 * (
            0.30 * baseline_date_coverage
            + 0.30 * actual_coverage
            + 0.25 * forecast_coverage
            + 0.15 * evidence_quality
        ))
        score = max(35, min(95, score))
        label = "élevée" if score >= 80 else ("moyenne" if score >= 60 else "prudente")
        return score, label, {
            "baseline_date_coverage": round(baseline_date_coverage, 3),
            "actual_completion_date_coverage": round(actual_coverage, 3),
            "remaining_forecast_date_coverage": round(forecast_coverage, 3),
            "certified_evidence_ratio": round(evidence_quality, 3),
        }

    def _last_next(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        rows = [m for m in doc.get("milestones", []) if not _is_inactive(m)]

        def completion_timestamp(value: Any) -> float:
            if value in (None, ""):
                return float("-inf")
            text = str(value).strip()
            try:
                dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
                if dt.tzinfo is not None:
                    return dt.timestamp()
                return (dt - datetime(1970, 1, 1)).total_seconds()
            except (TypeError, ValueError, OverflowError):
                d = _date_of(value)
                if d is None:
                    return float("-inf")
                return float(d.toordinal() * 86400)

        done_rows = []
        for idx, m in enumerate(rows):
            if _progress(m) >= 100 or _status(m) == "done":
                raw_end = (m.get("actual") or {}).get("end")
                done_rows.append((completion_timestamp(raw_end), idx, m))
        last = max(done_rows, default=(float("-inf"), -1, None), key=lambda x: (x[0], x[1]))[2]

        in_progress = [m for m in rows if _status(m) == "in_progress" and _progress(m) < 100]
        if in_progress:
            next_m = in_progress[0]
        else:
            planned = [m for m in rows if _progress(m) < 100 and _status(m) in {"planned", "blocked", ""}]
            planned.sort(key=lambda m: (
                _date_of((m.get("forecast") or {}).get("start")) or date.max,
                rows.index(m),
            ))
            next_m = planned[0] if planned else None

        return {
            "last_action": {
                "id": last.get("id") if last else None,
                "title": last.get("title") if last else None,
                "completed_at": _iso(_date_of((last.get("actual") or {}).get("end"))) if last else None,
            },
            "next_action": {
                "id": next_m.get("id") if next_m else None,
                "title": next_m.get("title") if next_m else None,
                "forecast_start": _iso(_date_of((next_m.get("forecast") or {}).get("start"))) if next_m else None,
                "forecast_end": _iso(_date_of((next_m.get("forecast") or {}).get("end"))) if next_m else None,
                "status": _status(next_m) if next_m else None,
            },
        }

    def compute(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        doc = self.service.load()
        when = as_of or date.today()
        project = doc.get("project") or {}

        start = _date_of(project.get("project_start"))
        baseline_finish = _date_of(project.get("baseline_target_v2"))
        if not start or not baseline_finish:
            raise RoadmapValidationError("project_start/baseline_target_v2 are required.")

        planned = self.baseline_planned_progress(doc, when)
        baseline_actual = self.baseline_actual_progress(doc)
        total_actual = float(project.get("current_progress_percent") or self.service.calculate_progress(doc))

        earned_date = self.earned_schedule_date(doc, baseline_actual, start, baseline_finish)
        execution_variance_days = (earned_date - when).days  # positive = ahead

        pace_adjusted_finish = baseline_finish - timedelta(days=execution_variance_days)
        if pace_adjusted_finish < when:
            pace_adjusted_finish = when

        scope = self._scope_metrics(doc, pace_adjusted_finish)
        scope_floor = _date_of(scope.get("scope_schedule_floor"))
        forecast_finish = pace_adjusted_finish
        if scope_floor and scope_floor > forecast_finish:
            forecast_finish = scope_floor
        if forecast_finish < when:
            forecast_finish = when

        schedule_variance_days = (baseline_finish - forecast_finish).days  # positive = ahead
        status = "ahead" if schedule_variance_days > 0 else ("late" if schedule_variance_days < 0 else "on_track")

        confidence, confidence_label, confidence_components = self._confidence(doc, when)
        remaining_baseline_days = max(1, (baseline_finish - when).days)
        uncertainty_days = max(2, round((100 - confidence) / 100.0 * max(14, remaining_baseline_days) * 0.6))
        optimistic = max(when, forecast_finish - timedelta(days=max(1, uncertainty_days // 2)))
        conservative = forecast_finish + timedelta(days=uncertainty_days)

        actions = self._last_next(doc)

        return {
            "schema": SCHEDULE_SCHEMA,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "as_of": when.isoformat(),
            "method": {
                "name": "weighted-earned-schedule-with-post-baseline-scope-floor",
                "baseline_source": "immutable 2026-08-30 roadmap",
                "execution_variance_sign": "positive = days ahead; negative = days late",
                "project_variance_sign": "positive = forecast days early; negative = forecast days late",
                "scope_note": "Post-baseline workload is reported separately. Only its explicit date floor delays the current forecast until dependency data is richer.",
            },
            "project": {
                "project_start": start.isoformat(),
                "baseline_finish": baseline_finish.isoformat(),
                "pace_adjusted_finish": pace_adjusted_finish.isoformat(),
                "forecast_finish": forecast_finish.isoformat(),
                "optimistic_finish": optimistic.isoformat(),
                "conservative_finish": conservative.isoformat(),
                "schedule_variance_days": schedule_variance_days,
                "schedule_status": status,
                "planned_baseline_progress_percent": planned,
                "actual_baseline_progress_percent": baseline_actual,
                "actual_total_progress_percent": round(total_actual, 1),
                "earned_schedule_date": earned_date.isoformat(),
                "execution_variance_days": execution_variance_days,
                "confidence_percent": confidence,
                "confidence_label": confidence_label,
                "uncertainty_days": uncertainty_days,
            },
            "scope": scope,
            "confidence_components": confidence_components,
            **actions,
        }

    def write_state(self, as_of: Optional[date] = None) -> Dict[str, Any]:
        state = self.compute(as_of=as_of)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.state_path)
        return state


def build_default_engine(root: Path | str = DEFAULT_ROOT) -> RoadmapScheduleEngine:
    return RoadmapScheduleEngine(root=root)


if __name__ == "__main__":
    engine = build_default_engine()
    print(json.dumps(engine.write_state(), indent=2, ensure_ascii=False))
