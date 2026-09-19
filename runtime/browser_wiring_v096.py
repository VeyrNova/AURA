
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Callable

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

@dataclass(frozen=True)
class BrowserWiringResult:
    ok: bool
    status: str
    capability: str
    provider_result: Any = None
    receipt_id: str | None = None
    confirmation_id: str | None = None
    evidence: Any = None
    error: str | None = None

    def to_dict(self):
        return asdict(self)

class BrowserWiringAdapter:
    PROVIDER_ID = "browser.provider"

    def __init__(
        self,
        *,
        provider,
        authorize_read: Callable[[str, dict], bool],
        request_confirmation: Callable[[str, dict], dict],
        create_receipt: Callable[[str, dict], dict],
    ):
        self.provider = provider
        self.authorize_read = authorize_read
        self.request_confirmation = request_confirmation
        self.create_receipt = create_receipt

    def execute(self, capability: str, **kwargs):
        if capability in READ_ONLY:
            if not self.authorize_read(capability, kwargs):
                return BrowserWiringResult(
                    ok=False,
                    status="DENIED_BY_POLICY",
                    capability=capability,
                    error="read_not_authorized",
                )

            result = self.provider.execute(capability, **kwargs)

            if not result.ok:
                return BrowserWiringResult(
                    ok=False,
                    status=result.status,
                    capability=capability,
                    provider_result=result.to_dict(),
                    error=result.error,
                )

            if not result.evidence:
                return BrowserWiringResult(
                    ok=False,
                    status="EVIDENCE_REQUIRED",
                    capability=capability,
                    provider_result=result.to_dict(),
                    error="provider_success_without_evidence",
                )

            return BrowserWiringResult(
                ok=True,
                status="SUCCESS",
                capability=capability,
                provider_result=result.to_dict(),
                evidence=result.evidence,
            )

        if capability in STATE_CHANGING:
            # D2 R4 wiring only: no state-changing browser executor yet.
            pending = self.provider.execute(capability, **kwargs)

            if pending.status != "CONFIRMATION_REQUIRED":
                return BrowserWiringResult(
                    ok=False,
                    status="FAIL_CLOSED",
                    capability=capability,
                    provider_result=pending.to_dict(),
                    error="provider_did_not_stop_for_confirmation",
                )

            receipt = self.create_receipt(
                capability,
                {
                    "provider_id": self.PROVIDER_ID,
                    "capability": capability,
                    "args": kwargs,
                    "state_changed": False,
                },
            )

            confirmation = self.request_confirmation(
                capability,
                {
                    "provider_id": self.PROVIDER_ID,
                    "capability": capability,
                    "args": kwargs,
                    "receipt_id": receipt.get("receipt_id"),
                },
            )

            return BrowserWiringResult(
                ok=False,
                status="WAITING_CONFIRMATION",
                capability=capability,
                provider_result=pending.to_dict(),
                receipt_id=receipt.get("receipt_id"),
                confirmation_id=confirmation.get("confirmation_id"),
                error="state_change_not_executed_in_D2_R4",
            )

        return BrowserWiringResult(
            ok=False,
            status="UNKNOWN_CAPABILITY",
            capability=capability,
            error="unsupported_capability",
        )

from integrations.registry import (
    INTEGRATION_RESULT_STATUSES,
    IntegrationCapability,
    IntegrationManifest,
    IntegrationProvider,
    IntegrationResult,
)
from integrations.browser import BrowserProvider


def _pick_integration_status(kind):
    values = tuple(INTEGRATION_RESULT_STATUSES)
    normalized = {str(value).casefold(): value for value in values}
    candidates = {
        "success": ("success", "succeeded", "ok", "completed", "complete"),
        "error": ("error", "failed", "failure", "denied", "blocked"),
    }[kind]
    for candidate in candidates:
        if candidate in normalized:
            return normalized[candidate]
    for value in values:
        lower = str(value).casefold()
        if kind == "success" and (
            "success" in lower or lower == "ok" or "complete" in lower
        ):
            return value
        if kind == "error" and (
            "error" in lower or "fail" in lower or "deny" in lower or "block" in lower
        ):
            return value
    raise RuntimeError("IntegrationResult status family unavailable for " + kind)


class BrowserIntegrationProviderAdapter(IntegrationProvider):
    PROVIDER_ID = "browser.provider"

    def __init__(self, *, search_adapter, read_adapter):
        self.provider = BrowserProvider(
            search_adapter=search_adapter,
            read_adapter=read_adapter,
        )
        rows = (
            ("browser.open", "BROWSER_OPEN", "LOW", False, "read_only"),
            ("browser.navigate", "BROWSER_NAVIGATE", "LOW", False, "read_only"),
            ("browser.read", "BROWSER_READ", "LOW", False, "read_only"),
            ("browser.extract", "BROWSER_EXTRACT", "LOW", False, "read_only"),
            ("browser.search", "BROWSER_SEARCH", "LOW", False, "read_only"),
            ("browser.click", "BROWSER_CLICK", "MEDIUM", True, "state_change"),
            ("browser.fill", "BROWSER_FILL", "MEDIUM", True, "state_change"),
            ("browser.submit", "BROWSER_SUBMIT", "MEDIUM", True, "state_change"),
            ("browser.download", "BROWSER_DOWNLOAD", "MEDIUM", True, "local_side_effect"),
            ("browser.workflow", "BROWSER_WORKFLOW", "LOW", False, "orchestrated"),
        )
        self._manifest = IntegrationManifest(
            provider_id=self.PROVIDER_ID,
            display_name="Browser / Web Workflows",
            provider_version="0.9.6",
            capabilities=tuple(
                IntegrationCapability(
                    capability_id=capability,
                    action=action,
                    description="AURA v0.9.6 " + capability,
                    risk_tier=risk,
                    requires_confirmation=requires_confirmation,
                    side_effect_class=side_effect_class,
                    evidence_required=True,
                )
                for capability, action, risk, requires_confirmation, side_effect_class in rows
            ),
            auth_kind="none",
            metadata={
                "strategy": "ADAPTER_OVER_EXISTING_WEB_FOUNDATION",
                "external_content_trust": "UNTRUSTED_BY_DEFAULT",
                "state_changing_executor": "DISABLED",
            },
        )

    @property
    def manifest(self):
        return self._manifest

    def health_snapshot(self):
        return {
            "provider_id": self.PROVIDER_ID,
            "available": True,
            "health_state": "HEALTHY",
            "state_changing_executor": "DISABLED",
        }

    def execute(self, request):
        capability = str(request.capability_id)
        params = dict(request.params or {})
        result = self.provider.execute(capability, **params)

        evidence_refs = ()
        if result.evidence:
            refs = []
            for key in ("source_url", "final_url"):
                value = result.evidence.get(key)
                if value and value not in refs:
                    refs.append(str(value))
            evidence_refs = tuple(refs)

        status = _pick_integration_status("success" if result.ok else "error")

        return IntegrationResult(
            request_id=request.request_id,
            provider_id=self.PROVIDER_ID,
            capability_id=capability,
            status=status,
            ok=bool(result.ok),
            receipt_id=None,
            output=result.to_dict(),
            error=result.error,
            evidence_refs=evidence_refs,
        )

