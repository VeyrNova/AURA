from __future__ import annotations

import hashlib
import json
import os
import threading
import uuid
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

WORKSPACE_SCHEMA = "aura.workspace.registry.v1"
WORKSPACE_RECORD_SCHEMA = "aura.workspace.record.v1"
WORKSPACE_STATUSES = frozenset({"active", "paused", "archived"})


class WorkspaceContextError(RuntimeError):
    pass


class WorkspaceNotFoundError(WorkspaceContextError):
    pass


class WorkspaceValidationError(WorkspaceContextError):
    pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_path(value: str | os.PathLike[str] | None) -> str:
    if value is None:
        return ""
    raw = str(value).strip()
    if not raw:
        return ""
    return str(Path(raw).expanduser().resolve(strict=False))


def _clean_text(value: Any, *, field_name: str, required: bool = False, max_len: int = 2000) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise WorkspaceValidationError(f"{field_name} is required")
    if len(text) > max_len:
        raise WorkspaceValidationError(f"{field_name} exceeds {max_len} characters")
    return text


def _clean_metadata(value: Mapping[str, Any] | None) -> dict[str, Any]:
    if not value:
        return {}
    # Round-trip through JSON so only serializable plain data survives.
    try:
        return json.loads(json.dumps(dict(value), ensure_ascii=False, default=str))
    except Exception as exc:
        raise WorkspaceValidationError(f"metadata is not serializable: {exc}") from exc


@dataclass(frozen=True)
class WorkspaceArtifact:
    artifact_id: str
    kind: str
    path: str
    label: str
    created_at: str
    updated_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def stable_id(kind: str, path: str) -> str:
        raw = f"{kind.strip().lower()}|{_normalize_path(path)}".encode("utf-8", "surrogatepass")
        return "art_" + hashlib.sha256(raw).hexdigest()[:20]

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkspaceArtifact":
        return cls(
            artifact_id=str(data.get("artifact_id") or ""),
            kind=str(data.get("kind") or "file"),
            path=str(data.get("path") or ""),
            label=str(data.get("label") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class WorkspaceActivity:
    activity_id: str
    at: str
    action: str
    detail: str = ""
    result: str = ""

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkspaceActivity":
        return cls(
            activity_id=str(data.get("activity_id") or ""),
            at=str(data.get("at") or ""),
            action=str(data.get("action") or ""),
            detail=str(data.get("detail") or ""),
            result=str(data.get("result") or ""),
        )


@dataclass(frozen=True)
class WorkspaceRecord:
    schema: str
    workspace_id: str
    name: str
    status: str
    root_path: str
    created_at: str
    updated_at: str
    tags: tuple[str, ...] = ()
    last_action: str = ""
    next_action: str = ""
    notes: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    artifacts: tuple[WorkspaceArtifact, ...] = ()
    activity: tuple[WorkspaceActivity, ...] = ()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "WorkspaceRecord":
        return cls(
            schema=str(data.get("schema") or WORKSPACE_RECORD_SCHEMA),
            workspace_id=str(data.get("workspace_id") or ""),
            name=str(data.get("name") or ""),
            status=str(data.get("status") or "active"),
            root_path=str(data.get("root_path") or ""),
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            tags=tuple(str(x) for x in (data.get("tags") or [])),
            last_action=str(data.get("last_action") or ""),
            next_action=str(data.get("next_action") or ""),
            notes=str(data.get("notes") or ""),
            metadata=dict(data.get("metadata") or {}),
            artifacts=tuple(WorkspaceArtifact.from_dict(x) for x in (data.get("artifacts") or [])),
            activity=tuple(WorkspaceActivity.from_dict(x) for x in (data.get("activity") or [])),
        )

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["tags"] = list(self.tags)
        data["artifacts"] = [asdict(x) for x in self.artifacts]
        data["activity"] = [asdict(x) for x in self.activity]
        return data


class WorkspaceContextServiceV130:
    """Persistent project/workspace context foundation for AURA v1.3.0.

    The service is intentionally storage-only at W130-A:
    - no LLM calls
    - no network
    - no UI mutation
    - no file-content writes outside its own registry directory
    """

    def __init__(self, storage_root: str | os.PathLike[str] | None = None) -> None:
        if storage_root is None:
            local = os.environ.get("LOCALAPPDATA")
            if local:
                storage_root = Path(local) / "AURA" / "workspaces" / "v1.3.0"
            else:
                storage_root = Path.home() / ".aura" / "workspaces" / "v1.3.0"
        self.storage_root = Path(storage_root).expanduser().resolve(strict=False)
        self.registry_path = self.storage_root / "workspace_registry.json"
        self._lock = threading.RLock()

    def _empty_registry(self) -> dict[str, Any]:
        return {
            "schema": WORKSPACE_SCHEMA,
            "updated_at": _now_iso(),
            "active_workspace_id": None,
            "workspaces": {},
        }

    def _load_registry(self) -> dict[str, Any]:
        if not self.registry_path.exists():
            return self._empty_registry()
        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise WorkspaceContextError(f"workspace registry is unreadable: {exc}") from exc
        if data.get("schema") != WORKSPACE_SCHEMA:
            raise WorkspaceContextError(
                f"unsupported workspace registry schema: {data.get('schema')!r}"
            )
        if not isinstance(data.get("workspaces"), dict):
            raise WorkspaceContextError("workspace registry workspaces must be an object")
        return data

    def _atomic_write(self, data: Mapping[str, Any]) -> None:
        self.storage_root.mkdir(parents=True, exist_ok=True)
        tmp = self.registry_path.with_suffix(".json.tmp-" + uuid.uuid4().hex)
        payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True)
        try:
            tmp.write_text(payload, encoding="utf-8", newline="\n")
            os.replace(tmp, self.registry_path)
        finally:
            try:
                if tmp.exists():
                    tmp.unlink()
            except Exception:
                pass

    def _save_registry(self, data: dict[str, Any]) -> None:
        data["updated_at"] = _now_iso()
        self._atomic_write(data)
        # AURA_V130_W130_F_LIVE_UI_SNAPSHOT_EXPORT
        try:
            from runtime.workspace_ui_live_export_v130 import export_workspace_ui_snapshot_v130
            export_workspace_ui_snapshot_v130(service=self)
        except Exception:
            pass

    def _record(self, data: Mapping[str, Any], workspace_id: str) -> WorkspaceRecord:
        raw = (data.get("workspaces") or {}).get(workspace_id)
        if raw is None:
            raise WorkspaceNotFoundError(workspace_id)
        rec = WorkspaceRecord.from_dict(raw)
        if rec.status not in WORKSPACE_STATUSES:
            raise WorkspaceContextError(f"invalid stored workspace status: {rec.status!r}")
        return rec

    def create_workspace(
        self,
        name: str,
        *,
        root_path: str | os.PathLike[str] | None = None,
        tags: Iterable[str] = (),
        metadata: Mapping[str, Any] | None = None,
        activate: bool = True,
        workspace_id: str | None = None,
    ) -> WorkspaceRecord:
        name = _clean_text(name, field_name="name", required=True, max_len=180)
        clean_tags = tuple(dict.fromkeys(
            _clean_text(x, field_name="tag", required=True, max_len=80) for x in tags
        ))
        now = _now_iso()
        wid = _clean_text(
            workspace_id or ("ws_" + uuid.uuid4().hex[:20]),
            field_name="workspace_id",
            required=True,
            max_len=96,
        )
        with self._lock:
            data = self._load_registry()
            if wid in data["workspaces"]:
                raise WorkspaceValidationError(f"workspace_id already exists: {wid}")
            rec = WorkspaceRecord(
                schema=WORKSPACE_RECORD_SCHEMA,
                workspace_id=wid,
                name=name,
                status="active",
                root_path=_normalize_path(root_path),
                created_at=now,
                updated_at=now,
                tags=clean_tags,
                metadata=_clean_metadata(metadata),
            )
            data["workspaces"][wid] = rec.to_dict()
            if activate:
                data["active_workspace_id"] = wid
            self._save_registry(data)
            return rec

    def list_workspaces(self, *, include_archived: bool = False) -> tuple[WorkspaceRecord, ...]:
        with self._lock:
            data = self._load_registry()
            rows = [WorkspaceRecord.from_dict(x) for x in data["workspaces"].values()]
            if not include_archived:
                rows = [x for x in rows if x.status != "archived"]
            rows.sort(key=lambda x: (x.updated_at, x.workspace_id), reverse=True)
            return tuple(rows)

    def get_workspace(self, workspace_id: str) -> WorkspaceRecord:
        with self._lock:
            return self._record(self._load_registry(), workspace_id)

    def get_active_workspace(self) -> WorkspaceRecord | None:
        with self._lock:
            data = self._load_registry()
            wid = data.get("active_workspace_id")
            if not wid:
                return None
            try:
                return self._record(data, str(wid))
            except WorkspaceNotFoundError:
                return None

    def set_active_workspace(self, workspace_id: str) -> WorkspaceRecord:
        with self._lock:
            data = self._load_registry()
            rec = self._record(data, workspace_id)
            if rec.status == "archived":
                raise WorkspaceValidationError("archived workspace cannot become active")
            if rec.status != "active":
                rec = replace(rec, status="active", updated_at=_now_iso())
                data["workspaces"][workspace_id] = rec.to_dict()
            data["active_workspace_id"] = workspace_id
            self._save_registry(data)
            return rec

    def update_workspace(
        self,
        workspace_id: str,
        *,
        name: str | None = None,
        status: str | None = None,
        root_path: str | os.PathLike[str] | None = None,
        tags: Iterable[str] | None = None,
        metadata_patch: Mapping[str, Any] | None = None,
        last_action: str | None = None,
        next_action: str | None = None,
        notes: str | None = None,
    ) -> WorkspaceRecord:
        with self._lock:
            data = self._load_registry()
            rec = self._record(data, workspace_id)
            if status is not None and status not in WORKSPACE_STATUSES:
                raise WorkspaceValidationError(f"invalid workspace status: {status}")
            meta = dict(rec.metadata)
            if metadata_patch:
                meta.update(_clean_metadata(metadata_patch))
            new = replace(
                rec,
                name=rec.name if name is None else _clean_text(name, field_name="name", required=True, max_len=180),
                status=rec.status if status is None else status,
                root_path=rec.root_path if root_path is None else _normalize_path(root_path),
                tags=rec.tags if tags is None else tuple(dict.fromkeys(
                    _clean_text(x, field_name="tag", required=True, max_len=80) for x in tags
                )),
                metadata=meta,
                last_action=rec.last_action if last_action is None else _clean_text(last_action, field_name="last_action"),
                next_action=rec.next_action if next_action is None else _clean_text(next_action, field_name="next_action"),
                notes=rec.notes if notes is None else _clean_text(notes, field_name="notes", max_len=10000),
                updated_at=_now_iso(),
            )
            data["workspaces"][workspace_id] = new.to_dict()
            if new.status == "archived" and data.get("active_workspace_id") == workspace_id:
                data["active_workspace_id"] = None
            self._save_registry(data)
            return new

    def add_artifact(
        self,
        workspace_id: str,
        path: str | os.PathLike[str],
        *,
        kind: str = "file",
        label: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> WorkspaceArtifact:
        norm = _normalize_path(path)
        if not norm:
            raise WorkspaceValidationError("artifact path is required")
        kind = _clean_text(kind, field_name="artifact kind", required=True, max_len=80).lower()
        aid = WorkspaceArtifact.stable_id(kind, norm)
        now = _now_iso()
        with self._lock:
            data = self._load_registry()
            rec = self._record(data, workspace_id)
            artifacts = list(rec.artifacts)
            existing = next((x for x in artifacts if x.artifact_id == aid), None)
            if existing:
                merged = dict(existing.metadata)
                merged.update(_clean_metadata(metadata))
                updated = replace(
                    existing,
                    label=_clean_text(label if label is not None else existing.label, field_name="artifact label", max_len=240),
                    metadata=merged,
                    updated_at=now,
                )
                artifacts[artifacts.index(existing)] = updated
                artifact = updated
            else:
                artifact = WorkspaceArtifact(
                    artifact_id=aid,
                    kind=kind,
                    path=norm,
                    label=_clean_text(label or Path(norm).name, field_name="artifact label", max_len=240),
                    created_at=now,
                    updated_at=now,
                    metadata=_clean_metadata(metadata),
                )
                artifacts.append(artifact)
            new = replace(rec, artifacts=tuple(artifacts), updated_at=now)
            data["workspaces"][workspace_id] = new.to_dict()
            self._save_registry(data)
            return artifact

    def remove_artifact(self, workspace_id: str, artifact_id: str) -> bool:
        with self._lock:
            data = self._load_registry()
            rec = self._record(data, workspace_id)
            artifacts = tuple(x for x in rec.artifacts if x.artifact_id != artifact_id)
            removed = len(artifacts) != len(rec.artifacts)
            if removed:
                new = replace(rec, artifacts=artifacts, updated_at=_now_iso())
                data["workspaces"][workspace_id] = new.to_dict()
                self._save_registry(data)
            return removed

    def record_activity(
        self,
        workspace_id: str,
        action: str,
        *,
        detail: str = "",
        result: str = "",
    ) -> WorkspaceActivity:
        now = _now_iso()
        entry = WorkspaceActivity(
            activity_id="act_" + uuid.uuid4().hex[:20],
            at=now,
            action=_clean_text(action, field_name="activity action", required=True, max_len=300),
            detail=_clean_text(detail, field_name="activity detail", max_len=3000),
            result=_clean_text(result, field_name="activity result", max_len=3000),
        )
        with self._lock:
            data = self._load_registry()
            rec = self._record(data, workspace_id)
            activity = (entry, *rec.activity)[:100]
            new = replace(rec, activity=activity, updated_at=now)
            data["workspaces"][workspace_id] = new.to_dict()
            self._save_registry(data)
            return entry

    def resume_workspace(self, workspace_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            if workspace_id:
                rec = self.set_active_workspace(workspace_id)
            else:
                rec = self.get_active_workspace()
            if rec is None:
                raise WorkspaceNotFoundError("no active workspace")
            return {
                "workspace_id": rec.workspace_id,
                "name": rec.name,
                "status": rec.status,
                "root_path": rec.root_path,
                "tags": list(rec.tags),
                "last_action": rec.last_action,
                "next_action": rec.next_action,
                "notes": rec.notes,
                "metadata": dict(rec.metadata),
                "artifacts": [asdict(x) for x in rec.artifacts],
                "recent_activity": [asdict(x) for x in rec.activity[:10]],
                "updated_at": rec.updated_at,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            data = self._load_registry()
            active = self.get_active_workspace()
            return {
                "schema": WORKSPACE_SCHEMA,
                "active_workspace_id": data.get("active_workspace_id"),
                "active_workspace": None if active is None else active.to_dict(),
                "workspace_count": len(data["workspaces"]),
                "updated_at": data.get("updated_at"),
            }


def get_workspace_context_service_v130(
    storage_root: str | os.PathLike[str] | None = None,
) -> WorkspaceContextServiceV130:
    return WorkspaceContextServiceV130(storage_root=storage_root)
