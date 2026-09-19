from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


class PublishingWorkflowError(RuntimeError):
    pass


class PublishingWorkflowApprovalRequired(PublishingWorkflowError):
    pass


class PublishingWorkflowExternalMutationUnavailable(PublishingWorkflowError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _workflow_id(title: str, fmt: str, created_at: str) -> str:
    raw = f"{title}|{fmt}|{created_at}".encode("utf-8")
    return "ytwf_" + hashlib.sha256(raw).hexdigest()[:16]


class PublishingWorkflowStateMachine:
    def __init__(self, store_path: str | Path) -> None:
        self.store_path = Path(store_path).expanduser().resolve()

    def _load(self) -> dict[str, Any]:
        if not self.store_path.exists():
            return {"schema": "aura.publishing-workflows.v151", "workflows": []}
        data = json.loads(self.store_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("workflows"), list):
            raise PublishingWorkflowError("invalid workflow store")
        return data

    def _save(self, data: Mapping[str, Any]) -> None:
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=self.store_path.name + ".",
            suffix=".tmp",
            dir=str(self.store_path.parent),
        )
        os.close(fd)
        temp = Path(temp_name)
        try:
            temp.write_text(
                json.dumps(dict(data), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            os.replace(temp, self.store_path)
        finally:
            if temp.exists():
                temp.unlink()

    def create_from_plan(self, plan: Mapping[str, Any]) -> dict[str, Any]:
        if bool(plan.get("external_mutation_performed")):
            raise PublishingWorkflowError("plan already reports external mutation")
        if not bool(plan.get("requires_explicit_confirmation")):
            raise PublishingWorkflowError("plan must require explicit confirmation")

        draft = plan.get("draft")
        if not isinstance(draft, Mapping):
            raise PublishingWorkflowError("plan draft missing")

        title = str(draft.get("title") or "").strip()
        fmt = str(draft.get("format") or "").strip().casefold()
        if not title or fmt not in {"short", "video"}:
            raise PublishingWorkflowError("invalid workflow draft")

        created_at = _now()
        record = {
            "workflow_id": _workflow_id(title, fmt, created_at),
            "state": "approval_required",
            "title": title,
            "format": fmt,
            "description": str(draft.get("description") or ""),
            "scheduled_for": draft.get("scheduled_for"),
            "created_at": created_at,
            "updated_at": created_at,
            "requires_explicit_confirmation": True,
            "local_approval": False,
            "publish_available": False,
            "external_mutation_performed": False,
            "youtube_upload_performed": False,
            "youtube_edit_performed": False,
            "youtube_delete_performed": False,
            "youtube_comment_reply_performed": False,
            "gates": list(plan.get("gates") or []),
        }

        data = self._load()
        data["workflows"].append(record)
        self._save(data)
        return dict(record)

    def list_workflows(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._load().get("workflows") or []]

    def latest(self) -> dict[str, Any] | None:
        rows = self.list_workflows()
        return dict(rows[-1]) if rows else None

    def get(self, workflow_id: str) -> dict[str, Any]:
        for row in self.list_workflows():
            if str(row.get("workflow_id") or "") == str(workflow_id or ""):
                return dict(row)
        raise PublishingWorkflowError("workflow not found")

    def approve_local(self, workflow_id: str, *, user_confirmed: bool) -> dict[str, Any]:
        if not user_confirmed:
            raise PublishingWorkflowApprovalRequired("explicit user confirmation required")

        data = self._load()
        for row in data.get("workflows") or []:
            if str(row.get("workflow_id") or "") != str(workflow_id or ""):
                continue
            if str(row.get("state") or "") != "approval_required":
                raise PublishingWorkflowError("workflow is not awaiting approval")
            row["state"] = "approved_local"
            row["local_approval"] = True
            row["updated_at"] = _now()
            row["publish_available"] = False
            row["external_mutation_performed"] = False
            self._save(data)
            return dict(row)
        raise PublishingWorkflowError("workflow not found")

    def publish(self, workflow_id: str) -> None:
        self.get(workflow_id)
        raise PublishingWorkflowExternalMutationUnavailable(
            "YouTube publish capability is not bound in Y151"
        )
