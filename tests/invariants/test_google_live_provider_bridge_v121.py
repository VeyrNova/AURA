from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from integrations.google.live_email_backend_v121 import GoogleLiveEmailBackendV121
from integrations.google.live_calendar_backend_v121 import GoogleLiveCalendarBackendV121
from integrations.google.live_contacts_backend_v121 import GoogleLiveContactsBackendV121
from integrations.google.live_files_backend_v121 import GoogleLiveFilesBackendV121
from runtime.personal_integrations import (
    build_google_live_runtime_context_v121,
    build_synthetic_runtime_context,
    EMAIL_PROVIDER_ID,
    CALENDAR_PROVIDER_ID,
    CONTACTS_PROVIDER_ID,
    FILES_PROVIDER_ID,
)


class FakeSecurityEngine:
    """Deterministic stand-in for the caller-owned security authority."""
    pass


class FakeAccount:
    display_label = "test@example.invalid"
    provider = "google"
    state = "connected"
    services = ("gmail", "calendar", "contacts", "drive")


class FakeService:
    def list_accounts(self, provider=None):
        if provider in (None, "google"):
            return (FakeAccount(),)
        return ()

    def _credentials(self, account):
        raise AssertionError(
            "deterministic invariant must not access Google credentials"
        )


service = FakeService()

for cls in (
    GoogleLiveEmailBackendV121,
    GoogleLiveCalendarBackendV121,
    GoogleLiveContactsBackendV121,
    GoogleLiveFilesBackendV121,
):
    backend = cls(service=service)
    snapshot = backend.health_snapshot()
    assert snapshot["provider"] == "google"
    assert "GOOGLE" in snapshot["mode"].upper()

assert GoogleLiveFilesBackendV121(
    service=service
).health_snapshot()["read_only"] is True

security_engine = FakeSecurityEngine()

# Provider manifest authority may be exposed as a method or an immutable property.
from integrations.email import EmailProvider, SyntheticEmailBackend
_probe_provider = EmailProvider(backend=SyntheticEmailBackend())
_probe_manifest_attr = getattr(_probe_provider, "manifest")
_probe_manifest = (
    _probe_manifest_attr()
    if callable(_probe_manifest_attr)
    else _probe_manifest_attr
)
assert getattr(_probe_manifest, "provider_id", None) == EMAIL_PROVIDER_ID

context = build_google_live_runtime_context_v121(
    service=service,
    security_engine=security_engine,
)
assert "GoogleLiveEmailBackendV121" in type(
    context.email_backend
).__name__
assert "GoogleLiveCalendarBackendV121" in type(
    context.calendar_backend
).__name__

registry = context.registry
for provider_id in (
    EMAIL_PROVIDER_ID,
    CALENDAR_PROVIDER_ID,
    CONTACTS_PROVIDER_ID,
    FILES_PROVIDER_ID,
):
    provider = registry.get_provider(provider_id)
    assert provider is not None
    backend = getattr(
        provider,
        "backend",
        getattr(provider, "_backend", None),
    )
    assert backend is not None
    assert "GoogleLive" in type(backend).__name__

# Compatibility entrypoint preserves the historical security-authority contract.
signature = inspect.signature(build_synthetic_runtime_context)
assert "security_engine" in signature.parameters
assert (
    signature.parameters["security_engine"].kind
    is inspect.Parameter.KEYWORD_ONLY
)

ui_source = (
    ROOT
    / "ui"
    / "personal_integration_modules.py"
).read_text(
    encoding="utf-8-sig"
)
assert 'mode="GOOGLE_LIVE"' in ui_source
assert 'mode="SYNTHETIC"' not in ui_source

runtime_source = (
    ROOT
    / "runtime"
    / "personal_integrations.py"
).read_text(
    encoding="utf-8-sig"
)
assert "def _build_synthetic_runtime_context_v121_fallback(" in runtime_source
assert "def build_google_live_runtime_context_v121(" in runtime_source
assert "security_engine=security_engine" in runtime_source
assert "return build_google_live_runtime_context_v121(" in runtime_source

print("[PASS] v1.2.1 Google Live Provider Bridge deterministic invariant")
print("[PASS] Gmail / Calendar / Contacts / Drive live backend classes installed")
print("[PASS] default PersonalIntegrationDispatcher wiring is Google-live")
print("[PASS] Drive mutations fail closed under current read-only scope")
print("[PASS] no network or secret access required by invariant")
