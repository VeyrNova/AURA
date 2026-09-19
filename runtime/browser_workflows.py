
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
import uuid

READ_ONLY = {
    "browser.open",
    "browser.navigate",
    "browser.read",
    "browser.extract",
    "browser.search",
}
STATE_CHANGING = {
    "browser.click",
    "browser.fill",
    "browser.submit",
    "browser.download",
}
OUT_OF_SCOPE = {
    "browser.pay",
    "browser.purchase",
    "browser.transfer",
    "browser.credentials",
    "browser.captcha_bypass",
    "browser.antibot_bypass",
}

@dataclass(frozen=True)
class BrowserWorkflowResult:
    workflow_id: str
    status: str
    complete: bool
    steps_completed: int
    evidence: tuple
    pending_step: dict | None = None
    error: str | None = None

    def to_dict(self):
        return asdict(self)

class BrowserWorkflowEngine:
    MAX_INITIAL_STEPS = 8

    def __init__(self, provider):
        self.provider = provider

    def execute(self, steps):
        workflow_id = "browser-" + uuid.uuid4().hex
        steps = list(steps or [])

        if not steps:
            return BrowserWorkflowResult(
                workflow_id,
                "INVALID_WORKFLOW",
                False,
                0,
                (),
                error="steps_required",
            )

        if len(steps) > self.MAX_INITIAL_STEPS:
            return BrowserWorkflowResult(
                workflow_id,
                "INVALID_WORKFLOW",
                False,
                0,
                (),
                error="max_8_steps",
            )

        evidence = []

        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                return BrowserWorkflowResult(
                    workflow_id,
                    "INVALID_WORKFLOW",
                    False,
                    index,
                    tuple(evidence),
                    error="step_must_be_dict",
                )

            capability = str(step.get("capability") or "")

            if capability in OUT_OF_SCOPE:
                return BrowserWorkflowResult(
                    workflow_id,
                    "DENIED_OUT_OF_SCOPE",
                    False,
                    index,
                    tuple(evidence),
                    pending_step=step,
                    error="out_of_scope_v096",
                )

            if capability in STATE_CHANGING:
                return BrowserWorkflowResult(
                    workflow_id,
                    "WAITING_CONFIRMATION",
                    False,
                    index,
                    tuple(evidence),
                    pending_step={
                        **step,
                        "index": index,
                        "confirmation_required": True,
                    },
                )

            if capability not in READ_ONLY:
                return BrowserWorkflowResult(
                    workflow_id,
                    "UNKNOWN_CAPABILITY",
                    False,
                    index,
                    tuple(evidence),
                    pending_step=step,
                    error="unsupported_capability",
                )

            kwargs = dict(step.get("args") or {})
            result = self.provider.execute(capability, **kwargs)

            if not result.ok:
                return BrowserWorkflowResult(
                    workflow_id,
                    result.status,
                    False,
                    index,
                    tuple(evidence),
                    pending_step=step,
                    error=result.error,
                )

            if not result.evidence:
                return BrowserWorkflowResult(
                    workflow_id,
                    "EVIDENCE_REQUIRED",
                    False,
                    index,
                    tuple(evidence),
                    pending_step=step,
                    error="successful_step_without_evidence",
                )

            evidence.append(
                {
                    "step_id": index,
                    "capability": capability,
                    **dict(result.evidence),
                }
            )

        return BrowserWorkflowResult(
            workflow_id,
            "SUCCESS",
            True,
            len(steps),
            tuple(evidence),
        )
