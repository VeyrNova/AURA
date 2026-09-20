from __future__ import annotations

import copy
import hashlib
import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

SCHEMA_PREFIX = "aura.roadmap.master.v25."
SERVICE_SCHEMA = "aura.roadmap.service.v25b.v1"
ALLOWED_STATUSES = {
    "planned", "in_progress", "done", "blocked",
    "archived", "cancelled", "deleted"
}
IMMUTABLE_MILESTONE_FIELDS = {"id", "baseline"}
IMMUTABLE_PROJECT_FIELDS = {"baseline_target_v2", "project_start"}
DEFAULT_ROOT = Path(r"C:\AURA GPT version")


class RoadmapError(RuntimeError):
    pass


class RoadmapValidationError(RoadmapError):
    pass


class RoadmapConflictError(RoadmapError):
    pass


class RoadmapImmutableFieldError(RoadmapError):
    pass


@dataclass(frozen=True)
class RoadmapMutationResult:
    revision_id: str
    operation: str
    milestone_id: Optional[str]
    progress_percent: float
    roadmap_sha256: str
    changed_at: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _deep_merge(dst: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(dst)
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = copy.deepcopy(value)
    return out


def _is_protected_baseline_milestone(m: Dict[str, Any]) -> bool:
    """True only for milestones that belong to the immutable 2026-08-30 baseline.

    Post-baseline scope additions deliberately have null baseline dates and a
    not-in-baseline status. They may be added/moved/archived without changing
    the protected historical baseline fingerprint.
    """
    baseline = m.get("baseline")
    if not isinstance(baseline, dict):
        return False
    status = str(baseline.get("status") or "").strip().lower()
    if status in {"not_in_baseline", "not_in_2026_08_30_baseline"}:
        return False
    if baseline.get("start") is None and baseline.get("end") is None:
        return False
    return True


def _baseline_fingerprint(doc: Dict[str, Any]) -> str:
    rows = []
    for m in doc.get("milestones", []):
        if not _is_protected_baseline_milestone(m):
            continue
        rows.append({
            "id": m.get("id"),
            "baseline": copy.deepcopy(m.get("baseline")),
        })
    rows.sort(key=lambda row: str(row.get("id") or ""))
    payload = {
        "project_start": doc.get("project", {}).get("project_start"),
        "baseline_target_v2": doc.get("project", {}).get("baseline_target_v2"),
        "milestones": rows,
    }
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha_bytes(raw)


class RoadmapService:
    """Persistent editable AURA roadmap core.

    V25-B owns roadmap mutation semantics only.
    It does not bind to Project Active, UI, conversation, or Developer Fabric yet.
    """

    def __init__(
        self,
        root: Path | str = DEFAULT_ROOT,
        roadmap_path: Optional[Path | str] = None,
        revisions_dir: Optional[Path | str] = None,
        history_path: Optional[Path | str] = None,
        lock_path: Optional[Path | str] = None,
        lock_timeout_s: float = 5.0,
        stale_lock_s: float = 120.0,
    ) -> None:
        self.root = Path(root)
        self.roadmap_path = Path(roadmap_path) if roadmap_path else (
            self.root / "data" / "roadmap" / "aura_master_roadmap_v2.json"
        )
        self.revisions_dir = Path(revisions_dir) if revisions_dir else (
            self.root / "data" / "roadmap" / "revisions"
        )
        self.history_path = Path(history_path) if history_path else (
            self.root / "data" / "roadmap" / "aura_roadmap_history.jsonl"
        )
        self.lock_path = Path(lock_path) if lock_path else (
            self.root / "data" / "roadmap" / ".aura_roadmap.lock"
        )
        self.lock_timeout_s = float(lock_timeout_s)
        self.stale_lock_s = float(stale_lock_s)

    def capability_snapshot(self) -> Dict[str, Any]:
        return {
            "schema": SERVICE_SCHEMA,
            "roadmap_path": str(self.roadmap_path),
            "operations": [
                "read",
                "add_milestone",
                "update_milestone",
                "move_milestone",
                "set_status",
                "archive_milestone",
                "delete_milestone_soft",
                "restore_milestone",
                "restore_revision",
                "list_revisions",
            ],
            "baseline_dates_immutable": True,
            "project_baseline_immutable": True,
            "revision_before_every_mutation": True,
            "atomic_write": True,
            "soft_delete_default": True,
            "project_active_binding": False,
            "conversation_binding": False,
            "developer_fabric_binding": False,
        }

    def _read_raw(self) -> bytes:
        if not self.roadmap_path.is_file():
            raise RoadmapValidationError(f"Roadmap missing: {self.roadmap_path}")
        return self.roadmap_path.read_bytes()

    def load(self) -> Dict[str, Any]:
        try:
            doc = json.loads(self._read_raw().decode("utf-8-sig"))
        except Exception as exc:
            raise RoadmapValidationError(f"Invalid roadmap JSON: {exc}") from exc
        self.validate(doc)
        return doc

    def validate(self, doc: Dict[str, Any]) -> None:
        if not isinstance(doc, dict):
            raise RoadmapValidationError("Roadmap root must be an object.")
        schema = str(doc.get("schema") or "")
        if not schema.startswith(SCHEMA_PREFIX):
            raise RoadmapValidationError(f"Unexpected roadmap schema: {schema!r}")
        project = doc.get("project")
        if not isinstance(project, dict):
            raise RoadmapValidationError("Missing project object.")
        milestones = doc.get("milestones")
        if not isinstance(milestones, list):
            raise RoadmapValidationError("milestones must be a list.")
        ids: List[str] = []
        for i, m in enumerate(milestones):
            if not isinstance(m, dict):
                raise RoadmapValidationError(f"milestones[{i}] must be an object.")
            mid = str(m.get("id") or "").strip()
            if not mid:
                raise RoadmapValidationError(f"milestones[{i}] has no id.")
            ids.append(mid)
            if not isinstance(m.get("baseline"), dict):
                raise RoadmapValidationError(f"{mid}: missing baseline object.")
            if not isinstance(m.get("forecast"), dict):
                raise RoadmapValidationError(f"{mid}: missing forecast object.")
            if not isinstance(m.get("actual"), dict):
                raise RoadmapValidationError(f"{mid}: missing actual object.")
            if float(m.get("weight") or 0) < 0:
                raise RoadmapValidationError(f"{mid}: weight cannot be negative.")
            progress = m.get("forecast", {}).get("progress_percent")
            if progress is not None and not 0 <= float(progress) <= 100:
                raise RoadmapValidationError(f"{mid}: forecast progress must be 0..100.")
        if len(ids) != len(set(ids)):
            raise RoadmapValidationError("Duplicate milestone ids.")
        policy = doc.get("policy", {})
        if policy.get("baseline_dates_immutable") is not True:
            raise RoadmapValidationError("baseline_dates_immutable policy must remain true.")

    def get_milestone(self, milestone_id: str, doc: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        d = doc or self.load()
        rows = [m for m in d["milestones"] if m.get("id") == milestone_id]
        if len(rows) != 1:
            raise RoadmapValidationError(
                f"Milestone {milestone_id!r} expected once, found {len(rows)}."
            )
        return rows[0]

    def calculate_progress(self, doc: Dict[str, Any]) -> float:
        active = []
        for m in doc.get("milestones", []):
            life = m.get("lifecycle") or {}
            if life.get("archived") or life.get("cancelled") or life.get("deleted"):
                continue
            active.append(m)
        total = sum(float(m.get("weight") or 0) for m in active)
        if total <= 0:
            return 0.0
        earned = 0.0
        for m in active:
            w = float(m.get("weight") or 0)
            p = float(m.get("forecast", {}).get("progress_percent") or 0)
            earned += w * p / 100.0
        return round(earned / total * 100.0, 1)

    def _refresh_derived_fields(self, doc: Dict[str, Any]) -> None:
        progress = self.calculate_progress(doc)
        doc.setdefault("project", {})["current_progress_percent"] = progress

        total = sum(
            float(m.get("weight") or 0)
            for m in doc.get("milestones", [])
            if not any((m.get("lifecycle") or {}).get(k) for k in ("archived", "cancelled", "deleted"))
        )
        for m in doc.get("milestones", []):
            life = m.get("lifecycle") or {}
            if total > 0 and not any(life.get(k) for k in ("archived", "cancelled", "deleted")):
                m["weight_norm"] = float(m.get("weight") or 0) / total * 100.0
            else:
                m["weight_norm"] = 0.0

    @contextmanager
    def _lock(self):
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.monotonic() + self.lock_timeout_s
        token = f"{os.getpid()}:{uuid.uuid4().hex}"
        while True:
            try:
                fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    fh.write(token)
                break
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                    if age > self.stale_lock_s:
                        self.lock_path.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise RoadmapConflictError("Roadmap is locked by another process.")
                time.sleep(0.05)
        try:
            yield
        finally:
            try:
                if self.lock_path.is_file():
                    content = self.lock_path.read_text(encoding="utf-8", errors="replace")
                    if content == token:
                        self.lock_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _write_atomic(self, doc: Dict[str, Any]) -> str:
        self.validate(doc)
        self.roadmap_path.parent.mkdir(parents=True, exist_ok=True)
        payload = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        tmp = self.roadmap_path.with_suffix(
            self.roadmap_path.suffix + f".{os.getpid()}.{uuid.uuid4().hex}.tmp"
        )
        tmp.write_bytes(payload)
        os.replace(tmp, self.roadmap_path)
        return _sha_path(self.roadmap_path)

    def _revision_id(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:8]

    def _snapshot_before(self, doc: Dict[str, Any], operation: str, actor: str, reason: str) -> str:
        self.revisions_dir.mkdir(parents=True, exist_ok=True)
        rid = self._revision_id()
        path = self.revisions_dir / f"{rid}.json"
        wrapper = {
            "schema": "aura.roadmap.revision.v25b.v1",
            "revision_id": rid,
            "captured_at": _now_iso(),
            "operation": operation,
            "actor": actor,
            "reason": reason,
            "roadmap_sha256": _sha_path(self.roadmap_path),
            "baseline_fingerprint": _baseline_fingerprint(doc),
            "roadmap": doc,
        }
        path.write_text(json.dumps(wrapper, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return rid

    def _history(self, entry: Dict[str, Any]) -> None:
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        with self.history_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")

    def _commit(
        self,
        before: Dict[str, Any],
        after: Dict[str, Any],
        operation: str,
        milestone_id: Optional[str],
        actor: str,
        reason: str,
    ) -> RoadmapMutationResult:
        if _baseline_fingerprint(before) != _baseline_fingerprint(after):
            raise RoadmapImmutableFieldError(
                "Baseline/project baseline changed; V25-B forbids this mutation."
            )
        self._refresh_derived_fields(after)
        self.validate(after)
        rid = self._snapshot_before(before, operation, actor, reason)
        changed_at = _now_iso()
        after.setdefault("roadmap_service", {})
        after["roadmap_service"].update({
            "schema": SERVICE_SCHEMA,
            "last_mutation_at": changed_at,
            "last_operation": operation,
            "last_revision_id": rid,
        })
        out_sha = self._write_atomic(after)
        projection_sync = {"ok": False, "reason": "not_attempted"}
        try:
            from runtime.aura_project_active_roadmap_binding_v25d import sync_project_active_projection_v25d
            projection_sync = sync_project_active_projection_v25d(root=self.root)
        except Exception as exc:
            projection_sync = {
                "ok": False,
                "reason": "projection_sync_error",
                "error_type": type(exc).__name__,
                "error": str(exc)[:500],
            }
        self._history({
            "schema": "aura.roadmap.history-event.v25b.v1",
            "at": changed_at,
            "revision_id": rid,
            "operation": operation,
            "milestone_id": milestone_id,
            "actor": actor,
            "reason": reason,
            "roadmap_sha256": out_sha,
            "project_active_projection_sync": projection_sync,
        })
        return RoadmapMutationResult(
            revision_id=rid,
            operation=operation,
            milestone_id=milestone_id,
            progress_percent=float(after["project"].get("current_progress_percent") or 0.0),
            roadmap_sha256=out_sha,
            changed_at=changed_at,
        )

    def add_milestone(
        self,
        milestone: Dict[str, Any],
        *,
        after_id: Optional[str] = None,
        before_id: Optional[str] = None,
        actor: str = "manual",
        reason: str = "add milestone",
    ) -> RoadmapMutationResult:
        if after_id and before_id:
            raise RoadmapValidationError("Use after_id or before_id, not both.")
        with self._lock():
            before = self.load()
            after = copy.deepcopy(before)
            mid = str(milestone.get("id") or "").strip()
            if not mid:
                raise RoadmapValidationError("New milestone requires id.")
            if any(m.get("id") == mid for m in after["milestones"]):
                raise RoadmapValidationError(f"Milestone already exists: {mid}")
            m = copy.deepcopy(milestone)
            m.setdefault("phase", "Unassigned")
            m.setdefault("version", "")
            m.setdefault("title", mid)
            m.setdefault("description", "")
            m.setdefault("kind", "scope_addition")
            m.setdefault("confidence", "estimé")
            m.setdefault("weight", 1.0)
            m.setdefault("weight_norm", None)
            m["baseline"] = {
                "status": "not_in_baseline",
                "progress_percent": 0,
                "start": None,
                "end": None,
            }
            m.setdefault("forecast", {
                "status": "planned",
                "progress_percent": 0,
                "start": None,
                "end": None,
            })
            m.setdefault("actual", {"start": None, "end": None})
            m.setdefault("lifecycle", {
                "archived": False, "cancelled": False, "deleted": False
            })
            m.setdefault("dependencies", [])
            m.setdefault("scope_change", {
                "type": "added_post_baseline",
                "decided_at": _now_iso(),
                "baseline_impact_days": None,
                "reason": reason,
            })
            m.setdefault("history", [])
            if before_id:
                idx = next((i for i, x in enumerate(after["milestones"]) if x.get("id") == before_id), None)
                if idx is None:
                    raise RoadmapValidationError(f"before_id not found: {before_id}")
                after["milestones"].insert(idx, m)
            elif after_id:
                idx = next((i for i, x in enumerate(after["milestones"]) if x.get("id") == after_id), None)
                if idx is None:
                    raise RoadmapValidationError(f"after_id not found: {after_id}")
                after["milestones"].insert(idx + 1, m)
            else:
                after["milestones"].append(m)
            return self._commit(before, after, "add_milestone", mid, actor, reason)

    def update_milestone(
        self,
        milestone_id: str,
        patch: Dict[str, Any],
        *,
        actor: str = "manual",
        reason: str = "update milestone",
    ) -> RoadmapMutationResult:
        if not isinstance(patch, dict):
            raise RoadmapValidationError("patch must be an object.")
        forbidden = IMMUTABLE_MILESTONE_FIELDS.intersection(patch)
        if forbidden:
            raise RoadmapImmutableFieldError(
                "Immutable milestone field(s): " + ", ".join(sorted(forbidden))
            )
        with self._lock():
            before = self.load()
            after = copy.deepcopy(before)
            m = self.get_milestone(milestone_id, after)
            merged = _deep_merge(m, patch)
            m.clear()
            m.update(merged)
            return self._commit(before, after, "update_milestone", milestone_id, actor, reason)

    def move_milestone(
        self,
        milestone_id: str,
        *,
        after_id: Optional[str] = None,
        before_id: Optional[str] = None,
        actor: str = "manual",
        reason: str = "move milestone",
    ) -> RoadmapMutationResult:
        if bool(after_id) == bool(before_id):
            raise RoadmapValidationError("Exactly one of after_id/before_id is required.")
        if milestone_id in {after_id, before_id}:
            raise RoadmapValidationError("Cannot position milestone relative to itself.")
        with self._lock():
            before = self.load()
            after = copy.deepcopy(before)
            rows = after["milestones"]
            idx = next((i for i, x in enumerate(rows) if x.get("id") == milestone_id), None)
            if idx is None:
                raise RoadmapValidationError(f"Milestone not found: {milestone_id}")
            item = rows.pop(idx)
            anchor = after_id or before_id
            pos = next((i for i, x in enumerate(rows) if x.get("id") == anchor), None)
            if pos is None:
                raise RoadmapValidationError(f"Anchor not found: {anchor}")
            rows.insert(pos + (1 if after_id else 0), item)
            return self._commit(before, after, "move_milestone", milestone_id, actor, reason)

    def set_status(
        self,
        milestone_id: str,
        status: str,
        *,
        progress_percent: Optional[float] = None,
        actor: str = "manual",
        reason: str = "set milestone status",
    ) -> RoadmapMutationResult:
        status = str(status).strip().lower()
        if status not in ALLOWED_STATUSES:
            raise RoadmapValidationError(f"Unsupported status: {status}")
        if progress_percent is None:
            progress_percent = 100 if status == "done" else None
        patch: Dict[str, Any] = {"forecast": {"status": status}}
        if progress_percent is not None:
            patch["forecast"]["progress_percent"] = float(progress_percent)
        if status == "done":
            patch.setdefault("actual", {})["end"] = _now_iso()
        return self.update_milestone(
            milestone_id, patch, actor=actor, reason=reason
        )

    def archive_milestone(
        self,
        milestone_id: str,
        *,
        actor: str = "manual",
        reason: str = "archive milestone",
    ) -> RoadmapMutationResult:
        return self.update_milestone(
            milestone_id,
            {"lifecycle": {"archived": True}, "forecast": {"status": "archived"}},
            actor=actor,
            reason=reason,
        )

    def delete_milestone_soft(
        self,
        milestone_id: str,
        *,
        actor: str = "manual",
        reason: str = "soft delete milestone",
    ) -> RoadmapMutationResult:
        return self.update_milestone(
            milestone_id,
            {"lifecycle": {"deleted": True}, "forecast": {"status": "deleted"}},
            actor=actor,
            reason=reason,
        )

    def restore_milestone(
        self,
        milestone_id: str,
        *,
        status: str = "planned",
        actor: str = "manual",
        reason: str = "restore milestone",
    ) -> RoadmapMutationResult:
        if status not in ALLOWED_STATUSES - {"archived", "deleted"}:
            raise RoadmapValidationError("Invalid restore status.")
        return self.update_milestone(
            milestone_id,
            {
                "lifecycle": {"archived": False, "cancelled": False, "deleted": False},
                "forecast": {"status": status},
            },
            actor=actor,
            reason=reason,
        )

    def list_revisions(self) -> List[Dict[str, Any]]:
        if not self.revisions_dir.is_dir():
            return []
        out: List[Dict[str, Any]] = []
        for path in sorted(self.revisions_dir.glob("*.json"), reverse=True):
            try:
                obj = json.loads(path.read_text(encoding="utf-8-sig"))
                out.append({
                    "revision_id": obj.get("revision_id"),
                    "captured_at": obj.get("captured_at"),
                    "operation": obj.get("operation"),
                    "actor": obj.get("actor"),
                    "reason": obj.get("reason"),
                    "path": str(path),
                })
            except Exception:
                continue
        return out

    def restore_revision(
        self,
        revision_id: str,
        *,
        actor: str = "manual",
        reason: str = "restore roadmap revision",
    ) -> RoadmapMutationResult:
        path = self.revisions_dir / f"{revision_id}.json"
        if not path.is_file():
            raise RoadmapValidationError(f"Revision not found: {revision_id}")
        wrapper = json.loads(path.read_text(encoding="utf-8-sig"))
        target = wrapper.get("roadmap")
        if not isinstance(target, dict):
            raise RoadmapValidationError("Revision has no roadmap payload.")
        self.validate(target)
        with self._lock():
            before = self.load()
            if _baseline_fingerprint(before) != _baseline_fingerprint(target):
                raise RoadmapImmutableFieldError(
                    "Revision baseline differs from current immutable baseline."
                )
            after = copy.deepcopy(target)
            return self._commit(
                before, after, "restore_revision", None, actor,
                f"{reason}: {revision_id}"
            )


def build_default_service(root: Path | str = DEFAULT_ROOT) -> RoadmapService:
    return RoadmapService(root=root)


if __name__ == "__main__":
    svc = build_default_service()
    payload = {
        "capabilities": svc.capability_snapshot(),
        "project": svc.load().get("project", {}),
        "revision_count": len(svc.list_revisions()),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
