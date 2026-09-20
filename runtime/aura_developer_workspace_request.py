from __future__ import annotations
from pathlib import Path
from typing import Any
import json
import os
import time

ROOT = Path(os.environ.get("AURA_ROOT") or Path(__file__).resolve().parents[1]).resolve()

def request_path(root: Path | str | None = None) -> Path:
    base = Path(root).resolve() if root is not None else ROOT
    return base / "runtime" / "developer_fabric" / "developer_workspace_request.json"

def request_snapshot(root: Path | str | None = None) -> dict[str, Any]:
    path = request_path(root)
    if not path.exists():
        return {"schema":"aura.developer-workspace-request.v1","serial":0,"requested_at":None}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raw = {}
    return {
        "schema":"aura.developer-workspace-request.v1",
        "serial":max(0, int(raw.get("serial") or 0)),
        "requested_at":raw.get("requested_at"),
    }

def record_workspace_request(root: Path | str | None = None) -> dict[str, Any]:
    path = request_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = request_snapshot(root)
    payload = {
        "schema":"aura.developer-workspace-request.v1",
        "serial":int(previous.get("serial") or 0) + 1,
        "requested_at":int(time.time()),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)
    return payload
