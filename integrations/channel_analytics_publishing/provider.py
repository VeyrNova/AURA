from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from integrations import IntegrationCapability, IntegrationManifest, IntegrationRequest
from runtime.aura_channel_analytics_publishing_v151 import ChannelAnalyticsPublishingWorkflows
from runtime.aura_publishing_workflow_state_v151 import PublishingWorkflowStateMachine

PROVIDER_ID = "channel.analytics-publishing"


class ChannelAnalyticsPublishingProvider:
    def __init__(
        self,
        snapshot_path: str | Path,
        *,
        workflow_store_path: str | Path | None = None,
    ) -> None:
        self.snapshot_path = Path(snapshot_path).expanduser().resolve()
        default_store = Path(
            os.environ.get(
                "AURA_Y151_WORKFLOW_STORE",
                str(Path(__file__).resolve().parents[2] / "data" / "youtube" / "publishing_workflows_v151.json"),
            )
        )
        self.workflow_store_path = Path(
            workflow_store_path or default_store
        ).expanduser().resolve()
        self._manifest = IntegrationManifest(
            provider_id=PROVIDER_ID,
            display_name="AURA Channel Analytics & Publishing Workflows",
            provider_version="1.5.1-y151.r3",
            capabilities=(
                IntegrationCapability("channel.compare_formats", "channel.compare_formats", "Compare Shorts and long-form analytics.", "low", False, "read", True),
                IntegrationCapability("channel.publishing_windows", "channel.publishing_windows", "Analyze historical publishing windows.", "low", False, "read", True),
                IntegrationCapability("channel.recommendation_matrix", "channel.recommendation_matrix", "Compare format signals and recommendations.", "low", False, "read", True),
                IntegrationCapability("channel.editorial_mix", "channel.editorial_mix", "Build a controlled editorial mix proposal.", "low", False, "read", True),
                IntegrationCapability("publishing.create_workflow_plan", "publishing.create_workflow_plan", "Create and persist a local workflow awaiting approval.", "low", False, "read", True),
                IntegrationCapability("publishing.workflow_status", "publishing.workflow_status", "Read the latest local publishing workflow state.", "low", False, "read", True),
            ),
            auth_kind="local_snapshot",
            metadata={
                "read_only_external_account": True,
                "workflow_plan_local_only": True,
                "workflow_store_path": str(self.workflow_store_path),
                "upload_video": False,
                "edit_video": False,
                "delete_video": False,
                "reply_comment": False,
                "future_publish_requires_explicit_confirmation": True,
                "future_publish_requires_canonical_receipt": True,
            },
        )

    @property
    def manifest(self) -> IntegrationManifest:
        return self._manifest

    def _load(self) -> dict[str, Any]:
        if not self.snapshot_path.exists():
            raise RuntimeError(f"YouTube snapshot missing: {self.snapshot_path}")
        data = json.loads(self.snapshot_path.read_text(encoding="utf-8-sig"))
        if not isinstance(data, dict) or not isinstance(data.get("videos"), list):
            raise RuntimeError("Invalid YouTube snapshot")
        return data

    def health_snapshot(self) -> Mapping[str, Any]:
        try:
            data = self._load()
            channel = data.get("channel") or {}
            return {
                "provider_id": PROVIDER_ID,
                "available": True,
                "health_state": "healthy",
                "channel_id": channel.get("channel_id"),
                "channel_title": channel.get("title"),
                "read_only_external_account": True,
            }
        except Exception as exc:
            return {
                "provider_id": PROVIDER_ID,
                "available": False,
                "health_state": "degraded",
                "error": type(exc).__name__,
            }

    def execute(self, request: IntegrationRequest) -> Any:
        data = self._load()
        studio = ChannelAnalyticsPublishingWorkflows(data.get("videos") or [])
        workflow_state = PublishingWorkflowStateMachine(self.workflow_store_path)
        capability = str(request.capability_id or "")
        params = dict(request.params or {})

        if capability == "channel.compare_formats":
            result = studio.compare_formats()
        elif capability == "channel.publishing_windows":
            result = studio.publishing_windows()
        elif capability == "channel.recommendation_matrix":
            result = studio.recommendation_matrix()
        elif capability == "channel.editorial_mix":
            result = studio.editorial_mix(
                uploads_per_week=int(params.get("uploads_per_week") or 3)
            )
        elif capability == "publishing.create_workflow_plan":
            result = studio.create_publishing_workflow(
                title=str(params.get("title") or ""),
                format=str(params.get("format") or "short"),
                description=str(params.get("description") or ""),
                scheduled_for=params.get("scheduled_for"),
            )
            if str(result.get("state") or "") == "approval_required":
                result["workflow_record"] = workflow_state.create_from_plan(result)
        elif capability == "publishing.workflow_status":
            workflow_id = str(params.get("workflow_id") or "").strip()
            record = workflow_state.get(workflow_id) if workflow_id else workflow_state.latest()
            result = {
                "schema": "aura.channel-analytics-publishing.v151",
                "kind": "publishing_workflow_status",
                "workflow_record": record,
                "external_mutation_performed": False,
                "publish_available": False,
            }
        else:
            raise ValueError(f"unsupported Y151 capability: {capability}")

        return {
            "provider_id": PROVIDER_ID,
            "capability_id": capability,
            "y151_result": result,
            "external_mutation_performed": False,
        }
