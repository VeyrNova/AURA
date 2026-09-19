
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlsplit
import hashlib
import json

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
class BrowserEvidence:
    capability: str
    source_url: str
    final_url: str
    retrieved_at: str
    result_summary: str
    state_changed: bool
    optional_content_sha256: str | None = None

    def to_dict(self):
        return asdict(self)

@dataclass(frozen=True)
class BrowserProviderResult:
    ok: bool
    status: str
    capability: str
    data: Any = None
    evidence: dict | None = None
    confirmation_required: bool = False
    state_changed: bool = False
    error: str | None = None

    def to_dict(self):
        return asdict(self)

class BrowserProvider:
    PROVIDER_ID = "browser.provider"
    CONTRACT_VERSION = "0.9.6"

    def __init__(
        self,
        *,
        search_adapter: Callable[[str], Any],
        read_adapter: Callable[[str], Any],
    ):
        self._search_adapter = search_adapter
        self._read_adapter = read_adapter

    @staticmethod
    def capabilities():
        return (
            "browser.open",
            "browser.navigate",
            "browser.read",
            "browser.extract",
            "browser.search",
            "browser.click",
            "browser.fill",
            "browser.submit",
            "browser.download",
            "browser.workflow",
        )

    @staticmethod
    def _evidence(capability, source_url, final_url, summary, content=None):
        digest = None
        if content is not None:
            raw = content if isinstance(content, bytes) else str(content).encode("utf-8")
            digest = hashlib.sha256(raw).hexdigest()

        return BrowserEvidence(
            capability=capability,
            source_url=source_url,
            final_url=final_url,
            retrieved_at=datetime.now(timezone.utc).isoformat(),
            result_summary=str(summary)[:500],
            state_changed=False,
            optional_content_sha256=digest,
        ).to_dict()

    def execute(self, capability: str, **kwargs):
        if capability in OUT_OF_SCOPE:
            return BrowserProviderResult(
                ok=False,
                status="DENIED_OUT_OF_SCOPE",
                capability=capability,
                error="out_of_scope_v096",
            )

        if capability == "browser.search":
            query = str(kwargs.get("query") or "").strip()
            if not query:
                return BrowserProviderResult(
                    ok=False,
                    status="INVALID_REQUEST",
                    capability=capability,
                    error="query_required",
                )

            data = self._search_adapter(query)

            return BrowserProviderResult(
                ok=True,
                status="SUCCESS",
                capability=capability,
                data=data,
                evidence=self._evidence(
                    capability,
                    "search://" + query,
                    "search://" + query,
                    "search results",
                    json.dumps(data, sort_keys=True, default=str),
                ),
            )

        if capability in {
            "browser.open",
            "browser.navigate",
            "browser.read",
            "browser.extract",
        }:
            url = str(kwargs.get("url") or "").strip()
            parsed = urlsplit(url)

            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                return BrowserProviderResult(
                    ok=False,
                    status="INVALID_REQUEST",
                    capability=capability,
                    error="valid_http_url_required",
                )

            data = self._read_adapter(url)

            if not isinstance(data, dict):
                data = {"content": data, "final_url": url}

            final_url = str(data.get("final_url") or url)
            content = data.get("content", data)

            return BrowserProviderResult(
                ok=True,
                status="SUCCESS",
                capability=capability,
                data=data,
                evidence=self._evidence(
                    capability,
                    url,
                    final_url,
                    "read-only browser result",
                    content,
                ),
            )

        if capability in STATE_CHANGING:
            return BrowserProviderResult(
                ok=False,
                status="CONFIRMATION_REQUIRED",
                capability=capability,
                confirmation_required=True,
                state_changed=False,
                error="state_change_not_executed_without_confirmation",
            )

        if capability == "browser.workflow":
            return BrowserProviderResult(
                ok=False,
                status="USE_WORKFLOW_ENGINE",
                capability=capability,
                error="workflow_engine_required",
            )

        return BrowserProviderResult(
            ok=False,
            status="UNKNOWN_CAPABILITY",
            capability=capability,
            error="unsupported_capability",
        )
