from __future__ import annotations

from dataclasses import fields, is_dataclass, replace

from integrations.email import EmailProvider
from integrations.calendar import CalendarProvider
from integrations.contacts import ContactProvider
from integrations.files import FilesProvider
from integrations.google.live_email_backend_v121 import (
    GoogleLiveEmailBackendV121,
)
from integrations.google.live_calendar_backend_v121 import (
    GoogleLiveCalendarBackendV121,
)
from integrations.google.live_contacts_backend_v121 import (
    GoogleLiveContactsBackendV121,
)
from integrations.google.live_files_backend_v121 import (
    GoogleLiveFilesBackendV121,
)
from runtime.connected_accounts_v120 import (
    get_connected_accounts_service_v120,
)


def _provider_manifest(provider):
    """Support both certified provider contracts seen in AURA: method or property."""
    manifest_attr = getattr(provider, "manifest", None)
    if manifest_attr is None:
        raise RuntimeError(
            "Integration provider has no manifest authority"
        )
    return (
        manifest_attr()
        if callable(manifest_attr)
        else manifest_attr
    )

from integrations.tasks import TasksProvider
from integrations.google.live_tasks_backend_v123 import GoogleLiveTasksBackendV123


def _replace_provider(registry, provider):
    manifest = _provider_manifest(provider)
    provider_id = str(manifest.provider_id)
    if not hasattr(registry, "unregister_provider"):
        raise RuntimeError(
            "IntegrationRegistry.unregister_provider is required "
            "for Google live bridge activation"
        )
    registry.unregister_provider(provider_id)
    registry.register_provider(provider)
    return provider_id


def build_google_live_runtime_context_v121(
    *,
    security_engine,
    receipt_service=None,
    receipt_db=None,
    timezone_name="Europe/Paris",
    service=None,
):
    from runtime.personal_integrations import (
        _build_synthetic_runtime_context_v121_fallback,
    )

    service = service or get_connected_accounts_service_v120()
    accounts = service.list_accounts("google")
    if not accounts:
        raise RuntimeError(
            "AURA Google account is not connected"
        )

    context = _build_synthetic_runtime_context_v121_fallback(
        security_engine=security_engine,
        receipt_service=receipt_service,
        receipt_db=receipt_db,
        timezone_name=timezone_name,
    )
    registry = getattr(context, "registry", None)
    if registry is None:
        raise RuntimeError(
            "IntegrationRuntimeContext has no registry"
        )

    email_backend = GoogleLiveEmailBackendV121(service=service)
    calendar_backend = GoogleLiveCalendarBackendV121(service=service)
    contacts_backend = GoogleLiveContactsBackendV121(service=service)
    files_backend = GoogleLiveFilesBackendV121(service=service)
    tasks_backend = GoogleLiveTasksBackendV123(service=service)

    _replace_provider(
        registry,
        EmailProvider(backend=email_backend),
    )
    _replace_provider(
        registry,
        CalendarProvider(backend=calendar_backend),
    )
    _replace_provider(
        registry,
        ContactProvider(backend=contacts_backend),
    )
    _replace_provider(
        registry,
        FilesProvider(backend=files_backend),
    )
    _replace_provider(
        registry,
        TasksProvider(backend=tasks_backend),
    )

    updates = {}
    if is_dataclass(context):
        names = {item.name for item in fields(context)}
        for name, value in (
            ("email_backend", email_backend),
            ("calendar_backend", calendar_backend),
            ("contacts_backend", contacts_backend),
            ("files_backend", files_backend),
        ):
            if name in names:
                updates[name] = value

    if updates:
        context = replace(context, **updates)

    return context


__all__ = [
    "build_google_live_runtime_context_v121",
]
