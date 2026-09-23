from __future__ import annotations

import copy
import json
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from runtime.aura_roadmap_service import RoadmapService
from runtime.aura_roadmap_schedule_engine import RoadmapScheduleEngine

BINDING_SCHEMA = "aura.project-active.roadmap-binding.v25d.v1"
DEFAULT_ROOT = Path(r"C:\AURA GPT version")
UI_VERSION = "v0.7.2.2-rc4.2"
SNAPSHOT_NAME = "workspace_project_active_v130.json"


def _live_ui_root() -> Path:
    explicit = str(os.environ.get("AURA_WORKSPACE_UI_ROOT") or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        if p.name.lower() == "dist":
            return p
        if (p / "dist").is_dir():
            return p / "dist"
        return p
    return Path.home() / "AppData" / "Local" / "AURA" / "ui" / UI_VERSION / "dist"


def _fmt_action(row: Dict[str, Any] | None) -> str:
    row = row or {}
    mid = str(row.get("id") or "").strip()
    title = str(row.get("title") or "").strip()
    if mid and title:
        return f"{mid} — {title}"
    return title or mid


def _progress_label(value: Any) -> str:
    try:
        n = float(value)
    except Exception:
        return "—"
    if abs(n - round(n)) < 0.05:
        return f"{int(round(n))}%"
    return f"{n:.1f}%"


def _variance_label(days: Any) -> str:
    try:
        n = int(days)
    except Exception:
        return "PLANNING INDISPONIBLE"
    if n > 0:
        return f"{n} JOURS D'AVANCE"
    if n < 0:
        return f"{abs(n)} JOURS DE RETARD"
    return "DANS LES TEMPS"


def _atomic_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".v25d.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _is_actual_live_ui_root(path: Path) -> bool:
    try:
        return path.resolve() == _live_ui_root().resolve()
    except Exception:
        return False


def project_active_overlay_v25d(
    base_snapshot: Dict[str, Any],
    schedule_state: Dict[str, Any],
) -> Dict[str, Any]:
    snapshot = copy.deepcopy(base_snapshot)
    if not isinstance(snapshot, dict):
        raise ValueError("Project Active snapshot root must be an object.")
    if snapshot.get("schema") != "aura.workspace.ui-contract.v1":
        raise ValueError(f"Unexpected Project Active snapshot schema: {snapshot.get('schema')!r}")

    card = snapshot.setdefault("project_active", {})
    if not isinstance(card, dict):
        raise ValueError("project_active must be an object.")

    project = schedule_state.get("project") or {}
    last_action = schedule_state.get("last_action") or {}
    next_action = schedule_state.get("next_action") or {}
    scope = schedule_state.get("scope") or {}

    total_progress = float(project.get("actual_total_progress_percent") or 0.0)
    card["progress_percent"] = round(total_progress, 1)
    card["progress_label"] = _progress_label(total_progress)
    card["last_action"] = _fmt_action(last_action) or "Aucune action certifiée"
    card["next_action"] = _fmt_action(next_action) or "Aucune prochaine action définie"
    card["baseline_finish"] = project.get("baseline_finish")
    card["forecast_finish"] = project.get("forecast_finish")
    card["optimistic_finish"] = project.get("optimistic_finish")
    card["conservative_finish"] = project.get("conservative_finish")
    card["schedule_variance_days"] = project.get("schedule_variance_days")
    card["schedule_status"] = project.get("schedule_status")
    card["schedule_label"] = _variance_label(project.get("schedule_variance_days"))
    card["planned_baseline_progress_percent"] = project.get("planned_baseline_progress_percent")
    card["actual_baseline_progress_percent"] = project.get("actual_baseline_progress_percent")
    card["earned_schedule_date"] = project.get("earned_schedule_date")
    card["execution_variance_days"] = project.get("execution_variance_days")
    card["confidence_percent"] = project.get("confidence_percent")
    card["confidence_label"] = project.get("confidence_label")
    card["scope_critical_path_impact_days"] = scope.get("scope_critical_path_impact_days")
    card["roadmap_live"] = True
    card["roadmap_binding_schema"] = BINDING_SCHEMA
    card["updated_at"] = schedule_state.get("generated_at") or datetime.now().astimezone().isoformat(timespec="seconds")
    return snapshot


def sync_project_active_projection_v25d(
    *,
    root: Path | str = DEFAULT_ROOT,
    ui_root: Path | str | None = None,
    service: RoadmapService | None = None,
    as_of: date | None = None,
    require_live_ui: bool = True,
    base_snapshot: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    root = Path(root)
    ui = Path(ui_root) if ui_root is not None else _live_ui_root()

    if require_live_ui and not _is_actual_live_ui_root(ui):
        return {
            "ok": False,
            "reason": "not_live_ui_root",
            "ui_root": str(ui),
        }

    snapshot_path = ui / SNAPSHOT_NAME
    if base_snapshot is None:
        if not snapshot_path.is_file():
            return {
                "ok": False,
                "reason": "snapshot_missing",
                "snapshot_path": str(snapshot_path),
            }
        base_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8-sig"))

    svc = service or RoadmapService(root=root)
    engine = RoadmapScheduleEngine(root=root, service=svc)
    schedule = engine.write_state(as_of=as_of)
    projected = project_active_overlay_v25d(base_snapshot, schedule)
    _atomic_json(snapshot_path, projected)

    card = projected["project_active"]
    return {
        "ok": True,
        "schema": BINDING_SCHEMA,
        "snapshot_path": str(snapshot_path),
        "schedule_state_path": str(engine.state_path),
        "progress_percent": card.get("progress_percent"),
        "progress_label": card.get("progress_label"),
        "last_action": card.get("last_action"),
        "next_action": card.get("next_action"),
        "forecast_finish": card.get("forecast_finish"),
        "baseline_finish": card.get("baseline_finish"),
        "schedule_variance_days": card.get("schedule_variance_days"),
        "schedule_label": card.get("schedule_label"),
        "confidence_percent": card.get("confidence_percent"),
    }


def overlay_live_export_if_applicable_v25d(
    payload: Dict[str, Any],
    *,
    root: Path | str = DEFAULT_ROOT,
    ui_root: Path | str | None = None,
) -> Dict[str, Any]:
    """Overlay only the real installed UI export.

    Unit/invariant exports to temporary directories remain untouched.
    """
    ui = Path(ui_root) if ui_root is not None else _live_ui_root()
    if not _is_actual_live_ui_root(ui):
        return payload
    result = sync_project_active_projection_v25d(
        root=root,
        ui_root=ui,
        require_live_ui=True,
        base_snapshot=payload,
    )
    if not result.get("ok"):
        return payload
    path = ui / SNAPSHOT_NAME
    return json.loads(path.read_text(encoding="utf-8-sig"))
