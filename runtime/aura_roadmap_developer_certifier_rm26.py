from __future__ import annotations

import copy
import inspect
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

SCHEMA = "aura.roadmap.developer-certifier.rm26.v1"
DEFAULT_ROOT = Path(__file__).resolve().parents[1]


class RoadmapDeveloperCertificationError(RuntimeError):
    pass


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _state_path(root: Path) -> Path:
    return root / "runtime" / "developer_fabric" / "roadmap_auto_certification_rm26.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        obj = json.loads(path.read_text(encoding="utf-8"))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _metadata(proposal: Dict[str, Any]) -> Dict[str, Any]:
    value = proposal.get("metadata")
    return value if isinstance(value, dict) else {}


def _milestone(snapshot: Dict[str, Any], milestone_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(milestone_id or "").strip().upper()
    for item in snapshot.get("milestones", []):
        if str(item.get("id") or "").strip().upper() == wanted:
            return item
    return None


def _base_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    base = receipt.get("base_transaction_receipt")
    return base if isinstance(base, dict) else {}


def _post_apply_acceptance(receipt: Dict[str, Any]) -> tuple[bool, str]:
    base = _base_receipt(receipt)
    if base.get("applied") is not True:
        return False, "base transaction was not applied"
    if base.get("rolled_back") is True:
        return False, "base transaction was rolled back"

    tests = base.get("post_apply_tests")
    if not isinstance(tests, list) or not tests:
        return False, "post-apply tests are missing"
    if any(not isinstance(row, dict) or row.get("passed") is not True for row in tests):
        return False, "post-apply tests did not all pass"
    return True, "post-apply acceptance passed"


def certification_candidate(proposal: Dict[str, Any]) -> Dict[str, Any]:
    meta = _metadata(proposal)
    milestone_id = str(meta.get("roadmap_milestone_id") or "").strip().upper()
    return {
        "enabled": meta.get("roadmap_auto_certify") is True,
        "milestone_id": milestone_id or None,
        "source": str(meta.get("roadmap_source") or ""),
    }


def _roadmap_snapshot(service: Any) -> Dict[str, Any]:
    path = Path(getattr(service, "roadmap_path"))
    snapshot = _read_json(path)
    if not snapshot:
        raise RoadmapDeveloperCertificationError(f"Roadmap unreadable: {path}")
    return snapshot


def _service_update_milestone(
    service: Any,
    milestone_id: str,
    patch: Dict[str, Any],
    *,
    actor: str,
    reason: str,
):
    fn = getattr(service, "update_milestone", None)
    if not callable(fn):
        raise RoadmapDeveloperCertificationError(
            "RoadmapService.update_milestone is unavailable"
        )

    sig = inspect.signature(fn)
    params = list(sig.parameters.values())
    kwargs: Dict[str, Any] = {}
    if "actor" in sig.parameters:
        kwargs["actor"] = actor
    if "reason" in sig.parameters:
        kwargs["reason"] = reason

    # Bound method: self is already removed from inspect.signature().
    # Normal contract is update_milestone(milestone_id, patch, *, actor, reason).
    positional = [
        p for p in params
        if p.kind in (inspect.Parameter.POSITIONAL_ONLY,
                      inspect.Parameter.POSITIONAL_OR_KEYWORD)
    ]
    if len(positional) >= 2:
        return fn(milestone_id, patch, **kwargs)

    # Defensive compatibility for keyword-only update payload names.
    payload_name = next(
        (name for name in ("patch", "changes", "updates", "data")
         if name in sig.parameters),
        None,
    )
    id_name = next(
        (name for name in ("milestone_id", "id", "milestone")
         if name in sig.parameters),
        None,
    )
    if payload_name and id_name:
        kwargs[id_name] = milestone_id
        kwargs[payload_name] = patch
        return fn(**kwargs)

    raise RoadmapDeveloperCertificationError(
        f"Unsupported RoadmapService.update_milestone signature: {sig}"
    )


def _result_value(result: Any, name: str, default=None):
    if isinstance(result, dict):
        return result.get(name, default)
    return getattr(result, name, default)


def certify_after_post_apply(
    proposal: Dict[str, Any],
    receipt: Dict[str, Any],
    *,
    root: Path | str = DEFAULT_ROOT,
) -> Dict[str, Any]:
    root = Path(root)
    candidate = certification_candidate(proposal)

    if not candidate["enabled"]:
        return {
            "ok": True,
            "schema": SCHEMA,
            "status": "SKIPPED",
            "reason": "transaction is not roadmap-scoped",
            "milestone_id": candidate["milestone_id"],
        }
    if not candidate["milestone_id"]:
        raise RoadmapDeveloperCertificationError(
            "roadmap_auto_certify requires explicit roadmap_milestone_id metadata"
        )

    txn = str(proposal.get("transaction_id") or "")
    if not txn or txn != str(receipt.get("transaction_id") or ""):
        raise RoadmapDeveloperCertificationError("transaction id mismatch")

    accepted, reason = _post_apply_acceptance(receipt)
    if not accepted:
        raise RoadmapDeveloperCertificationError(reason)

    state_path = _state_path(root)
    state = _read_json(state_path)
    entries = state.setdefault("entries", {})
    key = f"{txn}:{candidate['milestone_id']}"
    previous = entries.get(key)
    if isinstance(previous, dict) and previous.get("status") == "CERTIFIED":
        return {
            "ok": True,
            "schema": SCHEMA,
            "status": "IDEMPOTENT",
            "milestone_id": candidate["milestone_id"],
            "transaction_id": txn,
            "revision_id": previous.get("revision_id"),
        }

    from runtime.aura_roadmap_service import RoadmapService
    from runtime.aura_project_active_roadmap_binding_v25d import (
        sync_project_active_projection_v25d,
    )

    svc = RoadmapService(root=root)
    snapshot = _roadmap_snapshot(svc)
    milestone = _milestone(snapshot, candidate["milestone_id"])
    if milestone is None:
        raise RoadmapDeveloperCertificationError(
            f"roadmap milestone not found: {candidate['milestone_id']}"
        )

    pre_state = {
        "forecast": copy.deepcopy(milestone.get("forecast") or {}),
        "actual": copy.deepcopy(milestone.get("actual") or {}),
        "reconciled_confidence": milestone.get("reconciled_confidence"),
    }

    now = _now()
    actual = copy.deepcopy(milestone.get("actual") or {})
    if not actual.get("start"):
        actual["start"] = now
    actual["end"] = now

    result = _service_update_milestone(
        svc,
        candidate["milestone_id"],
        {
            "forecast": {"status": "done", "progress_percent": 100},
            "actual": actual,
            "reconciled_confidence": "certifié",
        },
        actor="developer-fabric-rm26",
        reason=f"Automatic certification after successful post-apply acceptance for {txn}",
    )

    projection = sync_project_active_projection_v25d(
        root=root,
        require_live_ui=False,
    )
    if not projection.get("ok"):
        raise RoadmapDeveloperCertificationError("Project Active projection sync failed")

    revision_id = _result_value(result, "revision_id")
    progress_percent = _result_value(result, "progress_percent")

    entries[key] = {
        "status": "CERTIFIED",
        "transaction_id": txn,
        "milestone_id": candidate["milestone_id"],
        "revision_id": revision_id,
        "certified_at": now,
        "pre_state": pre_state,
        "proposal_digest": proposal.get("proposal_digest"),
    }
    state.update({"schema": SCHEMA, "updated_at": now})
    _write_json(state_path, state)

    return {
        "ok": True,
        "schema": SCHEMA,
        "status": "CERTIFIED",
        "milestone_id": candidate["milestone_id"],
        "transaction_id": txn,
        "revision_id": revision_id,
        "progress_percent": progress_percent,
        "projection": projection,
    }


def reconcile_rollback(
    proposal: Dict[str, Any],
    receipt: Dict[str, Any],
    rollback_result: Dict[str, Any],
    *,
    root: Path | str = DEFAULT_ROOT,
) -> Dict[str, Any]:
    root = Path(root)
    candidate = certification_candidate(proposal)
    if not candidate["enabled"] or not candidate["milestone_id"]:
        return {"ok": True, "schema": SCHEMA, "status": "SKIPPED"}

    if rollback_result.get("rolled_back") is not True:
        raise RoadmapDeveloperCertificationError("source rollback did not succeed")

    txn = str(proposal.get("transaction_id") or "")
    state_path = _state_path(root)
    state = _read_json(state_path)
    entries = state.get("entries") or {}
    key = f"{txn}:{candidate['milestone_id']}"
    entry = entries.get(key)
    if not isinstance(entry, dict) or entry.get("status") != "CERTIFIED":
        return {
            "ok": True,
            "schema": SCHEMA,
            "status": "NO_CERTIFICATION_TO_REVERT",
            "milestone_id": candidate["milestone_id"],
        }

    pre = entry.get("pre_state")
    if not isinstance(pre, dict):
        raise RoadmapDeveloperCertificationError(
            "missing pre-certification Roadmap state"
        )

    from runtime.aura_roadmap_service import RoadmapService
    from runtime.aura_project_active_roadmap_binding_v25d import (
        sync_project_active_projection_v25d,
    )

    svc = RoadmapService(root=root)
    patch = {
        "forecast": copy.deepcopy(pre.get("forecast") or {}),
        "actual": copy.deepcopy(pre.get("actual") or {}),
    }
    if "reconciled_confidence" in pre:
        patch["reconciled_confidence"] = pre.get("reconciled_confidence")

    result = _service_update_milestone(
        svc,
        candidate["milestone_id"],
        patch,
        actor="developer-fabric-rm26",
        reason=f"Roadmap reconciliation after source rollback for {txn}",
    )

    projection = sync_project_active_projection_v25d(
        root=root,
        require_live_ui=False,
    )
    if not projection.get("ok"):
        raise RoadmapDeveloperCertificationError(
            "Project Active projection sync failed after rollback"
        )

    entry["status"] = "REVERTED"
    entry["reverted_at"] = _now()
    entry["revert_revision_id"] = _result_value(result, "revision_id")
    state["updated_at"] = _now()
    _write_json(state_path, state)

    return {
        "ok": True,
        "schema": SCHEMA,
        "status": "REVERTED",
        "milestone_id": candidate["milestone_id"],
        "transaction_id": txn,
        "revision_id": _result_value(result, "revision_id"),
        "projection": projection,
    }


# AURA ROADMAP RM26-2 — receipt-only rollback reconciliation
def reconcile_rollback_from_receipt(
    receipt: Dict[str, Any],
    rollback_result: Dict[str, Any],
    *,
    root: Path | str = DEFAULT_ROOT,
) -> Dict[str, Any]:
    root = Path(root)
    if rollback_result.get("rolled_back") is not True:
        raise RoadmapDeveloperCertificationError("source rollback did not succeed")

    txn = str(receipt.get("transaction_id") or "")
    if not txn:
        raise RoadmapDeveloperCertificationError("receipt transaction id missing")

    state_path = _state_path(root)
    state = _read_json(state_path)
    entries = state.get("entries") or {}

    matches = [
        (key, entry)
        for key, entry in entries.items()
        if isinstance(entry, dict)
        and str(entry.get("transaction_id") or "") == txn
        and entry.get("status") == "CERTIFIED"
    ]
    if not matches:
        return {
            "ok": True,
            "schema": SCHEMA,
            "status": "NO_CERTIFICATION_TO_REVERT",
            "transaction_id": txn,
        }
    if len(matches) != 1:
        raise RoadmapDeveloperCertificationError(
            f"ambiguous Roadmap certifications for transaction {txn}"
        )

    key, entry = matches[0]
    milestone_id = str(entry.get("milestone_id") or "").strip().upper()
    pre = entry.get("pre_state")
    if not milestone_id or not isinstance(pre, dict):
        raise RoadmapDeveloperCertificationError(
            "certification state is missing milestone/pre_state"
        )

    from runtime.aura_roadmap_service import RoadmapService
    from runtime.aura_project_active_roadmap_binding_v25d import (
        sync_project_active_projection_v25d,
    )

    svc = RoadmapService(root=root)
    patch = {
        "forecast": copy.deepcopy(pre.get("forecast") or {}),
        "actual": copy.deepcopy(pre.get("actual") or {}),
    }
    if "reconciled_confidence" in pre:
        patch["reconciled_confidence"] = pre.get("reconciled_confidence")

    result = _service_update_milestone(
        svc,
        milestone_id,
        patch,
        actor="developer-fabric-rm26",
        reason=f"Roadmap reconciliation after source rollback for {txn}",
    )

    projection = sync_project_active_projection_v25d(
        root=root,
        require_live_ui=False,
    )
    if not projection.get("ok"):
        raise RoadmapDeveloperCertificationError(
            "Project Active projection sync failed after rollback"
        )

    entry["status"] = "REVERTED"
    entry["reverted_at"] = _now()
    entry["revert_revision_id"] = _result_value(result, "revision_id")
    state["updated_at"] = _now()
    _write_json(state_path, state)

    return {
        "ok": True,
        "schema": SCHEMA,
        "status": "REVERTED",
        "milestone_id": milestone_id,
        "transaction_id": txn,
        "revision_id": _result_value(result, "revision_id"),
        "projection": projection,
    }
