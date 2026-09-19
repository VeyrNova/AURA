from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from runtime.workspace_context_v130 import WorkspaceContextServiceV130
from runtime.workspace_ui_contract_v130 import workspace_ui_snapshot_v130

WORKSPACE_UI_EXPORT_FILENAME = "workspace_project_active_v130.json"


def discover_live_ui_root_v130() -> Path | None:
    explicit = str(os.environ.get("AURA_WORKSPACE_UI_ROOT") or "").strip()
    if explicit:
        root = Path(explicit).expanduser().resolve(strict=False)
        return root if (root / "index.html").is_file() else None

    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if not local:
        return None

    base = Path(local) / "AURA" / "ui"
    if not base.is_dir():
        return None

    candidates: list[tuple[float, Path]] = []
    for index in base.rglob("index.html"):
        try:
            rel = index.relative_to(base)
        except Exception:
            continue
        if len(rel.parts) > 5:
            continue
        lowered = "\\".join(rel.parts).lower()
        if any(token in lowered for token in ("backup", "_old", ".old", "archive")):
            continue
        try:
            mtime = index.stat().st_mtime
        except OSError:
            mtime = 0.0
        candidates.append((mtime, index.parent.resolve(strict=False)))

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x[0], str(x[1]).lower()), reverse=True)
    return candidates[0][1]


def workspace_ui_export_path_v130(ui_root: str | os.PathLike[str] | None = None) -> Path | None:
    root = Path(ui_root).expanduser().resolve(strict=False) if ui_root is not None else discover_live_ui_root_v130()
    if root is None:
        return None
    return root / WORKSPACE_UI_EXPORT_FILENAME


def export_workspace_ui_snapshot_v130(
    *,
    service: WorkspaceContextServiceV130 | None = None,
    ui_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    service = service or WorkspaceContextServiceV130()
    snapshot = workspace_ui_snapshot_v130(service=service)
    target = workspace_ui_export_path_v130(ui_root)
    if target is None:
        return {"written": False, "reason": "live_ui_root_not_found", "snapshot": snapshot}

    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    try:
        tmp.write_text(payload, encoding="utf-8", newline="\n")
        os.replace(tmp, target)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

    return {"written": True, "path": str(target), "snapshot": snapshot}


# AURA ROADMAP V25-D — LIVE PROJECT ACTIVE OVERLAY
_AURA_V25D_ORIGINAL_EXPORT_WORKSPACE_UI_SNAPSHOT = export_workspace_ui_snapshot_v130

def export_workspace_ui_snapshot_v130(
    *,
    service: WorkspaceContextServiceV130 | None = None,
    ui_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    payload = _AURA_V25D_ORIGINAL_EXPORT_WORKSPACE_UI_SNAPSHOT(
        service=service,
        ui_root=ui_root,
    )
    try:
        from runtime.aura_project_active_roadmap_binding_v25d import overlay_live_export_if_applicable_v25d
        return overlay_live_export_if_applicable_v25d(payload, ui_root=ui_root)
    except Exception:
        # Workspace export remains available even if the derived roadmap projection is temporarily unavailable.
        return payload
