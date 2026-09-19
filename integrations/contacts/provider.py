"""AURA v0.9.3 provider-neutral Contacts integration.

Synthetic/local provider only. No external OAuth or cloud contact service.
"""
from __future__ import annotations

import inspect
import re
from dataclasses import dataclass, replace
from typing import Any, Mapping, Optional, Sequence

from integrations.registry import IntegrationCapability, IntegrationManifest, IntegrationRequest
from integrations.email import EmailProvider, SyntheticEmailBackend
from integrations.calendar import CalendarProvider, SyntheticCalendarBackend

CONTACTS_PROVIDER_ID = "contacts.provider"
READ_CAPABILITIES = ("contacts.search", "contacts.read")
WRITE_CAPABILITIES = ("contacts.create", "contacts.update", "contacts.delete")
CONFIRMATION_CAPABILITIES = WRITE_CAPABILITIES
CONTACTS_CAPABILITIES = (*READ_CAPABILITIES, *WRITE_CAPABILITIES)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _tuple_strings(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        value = [value]
    return tuple(item for item in (_clean(v) for v in value) if item)


@dataclass(frozen=True)
class Contact:
    contact_id: str
    display_name: str
    emails: tuple[str, ...] = ()
    phones: tuple[str, ...] = ()
    organization: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not _clean(self.contact_id):
            raise ValueError("contact_id is required")
        if not _clean(self.display_name):
            raise ValueError("display_name is required")

    def to_dict(self) -> dict[str, Any]:
        return {
            "contact_id": self.contact_id,
            "display_name": self.display_name,
            "emails": list(self.emails),
            "phones": list(self.phones),
            "organization": self.organization,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ContactQuery:
    text: str = ""
    limit: int = 10

    @classmethod
    def from_value(cls, value: Any) -> "ContactQuery":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                text=_clean(value.get("text")),
                limit=max(1, min(100, int(value.get("limit") or 10))),
            )
        return cls(text=_clean(value), limit=10)


@dataclass(frozen=True)
class ContactResult:
    contacts: tuple[Contact, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {"contacts": [item.to_dict() for item in self.contacts]}


class ContactsProviderError(RuntimeError):
    pass


class ContactLookupError(ContactsProviderError):
    pass


class ContactValidationError(ContactsProviderError):
    pass


class SyntheticContactsBackend:
    def __init__(self, contacts: Optional[Sequence[Contact]] = None) -> None:
        seed = tuple(contacts or (
            Contact("ctc-001", "Alice Martin", ("alice@example.invalid",), ("0611223344",), "AURA Demo"),
            Contact("ctc-002", "Thomas Bernard", ("thomas@example.invalid",), ("0622334455",), "AURA Demo"),
            Contact("ctc-003", "Sophie Leroy", ("sophie@example.invalid",), ("0633445566",), "AURA Demo"),
        ))
        self._contacts = {item.contact_id: item for item in seed}
        self._counter = max([
            int(m.group(1))
            for key in self._contacts
            for m in [re.match(r"ctc-(\d+)$", key)]
            if m
        ] or [0])

    def search_contacts(self, query: ContactQuery) -> tuple[Contact, ...]:
        needle = query.text.casefold().strip()
        rows = []
        for contact in self._contacts.values():
            haystack = " ".join([
                contact.contact_id,
                contact.display_name,
                *contact.emails,
                *contact.phones,
                contact.organization,
                contact.notes,
            ]).casefold()
            if needle and needle not in haystack:
                continue
            rows.append(contact)
        rows.sort(key=lambda item: (item.display_name.casefold(), item.contact_id))
        return tuple(rows[:query.limit])

    def get_contact(self, contact_id: str) -> Contact:
        contact_id = _clean(contact_id)
        try:
            return self._contacts[contact_id]
        except KeyError as exc:
            raise ContactLookupError("unknown contact_id: " + contact_id) from exc

    def create_contact(self, *, display_name: str, emails=(), phones=(), organization: str = "", notes: str = "") -> Contact:
        display_name = _clean(display_name)
        if not display_name:
            raise ContactValidationError("display_name is required")
        self._counter += 1
        contact = Contact(
            "ctc-" + str(self._counter).zfill(3),
            display_name,
            _tuple_strings(emails),
            _tuple_strings(phones),
            _clean(organization),
            _clean(notes),
        )
        self._contacts[contact.contact_id] = contact
        return contact

    def update_contact(self, contact_id: str, **changes: Any) -> Contact:
        old = self.get_contact(contact_id)
        allowed = {"display_name", "emails", "phones", "organization", "notes"}
        clean_changes = {key: value for key, value in changes.items() if key in allowed}
        if "display_name" in clean_changes:
            clean_changes["display_name"] = _clean(clean_changes["display_name"])
            if not clean_changes["display_name"]:
                raise ContactValidationError("display_name cannot be empty")
        if "emails" in clean_changes:
            clean_changes["emails"] = _tuple_strings(clean_changes["emails"])
        if "phones" in clean_changes:
            clean_changes["phones"] = _tuple_strings(clean_changes["phones"])
        if "organization" in clean_changes:
            clean_changes["organization"] = _clean(clean_changes["organization"])
        if "notes" in clean_changes:
            clean_changes["notes"] = _clean(clean_changes["notes"])
        if not clean_changes:
            raise ContactValidationError("no supported contact changes supplied")
        updated = replace(old, **clean_changes)
        self._contacts[contact_id] = updated
        return updated

    def delete_contact(self, contact_id: str) -> Contact:
        old = self.get_contact(contact_id)
        del self._contacts[contact_id]
        return old


def _reference_capabilities() -> dict[str, IntegrationCapability]:
    email_manifest = EmailProvider(
        backend=SyntheticEmailBackend()
    ).manifest
    calendar_manifest = CalendarProvider(
        backend=SyntheticCalendarBackend()
    ).manifest

    refs = {
        getattr(capability, "capability_id", ""): capability
        for capability in (
            tuple(email_manifest.capabilities)
            + tuple(calendar_manifest.capabilities)
        )
    }

    required = {
        "email.search",
        "email.read",
        "calendar.create_event",
        "calendar.update_event",
        "calendar.delete_event",
    }
    missing = sorted(required.difference(refs))
    if missing:
        raise RuntimeError(
            "missing certified reference capabilities: "
            + ", ".join(missing)
        )
    return refs


_REFERENCE_CAPS = _reference_capabilities()

_REFERENCE_BY_CONTACT_CAPABILITY = {
    "contacts.search": "email.search",
    "contacts.read": "email.read",
    "contacts.create": "calendar.create_event",
    "contacts.update": "calendar.update_event",
    "contacts.delete": "calendar.delete_event",
}


def _cap(capability_id: str, *, mutating: bool) -> IntegrationCapability:
    signature = inspect.signature(IntegrationCapability)
    reference_id = _REFERENCE_BY_CONTACT_CAPABILITY[capability_id]
    reference = _REFERENCE_CAPS[reference_id]

    values = {
        "capability_id": capability_id,
        "action": capability_id,
        "description": capability_id,
        "mutating": mutating,
        "read_only": not mutating,
        "requires_confirmation": mutating,
        "kind": "write" if mutating else "read",
        "risk_tier": getattr(reference, "risk_tier", None),
        "side_effect_class": getattr(reference, "side_effect_class", None),
        "evidence_required": getattr(reference, "evidence_required", None),
    }

    kwargs = {}

    for name, parameter in signature.parameters.items():
        if name in values and values[name] is not None:
            kwargs[name] = values[name]
        elif hasattr(reference, name):
            kwargs[name] = getattr(reference, name)
        elif parameter.default is inspect._empty:
            raise RuntimeError(
                "cannot derive required IntegrationCapability field "
                + name
                + " from certified reference "
                + reference_id
            )

    capability = IntegrationCapability(**kwargs)

    if getattr(capability, "risk_tier", None) is None:
        raise RuntimeError(
            "Contacts capability missing risk_tier: "
            + capability_id
        )

    if getattr(capability, "side_effect_class", None) is None:
        raise RuntimeError(
            "Contacts capability missing side_effect_class: "
            + capability_id
        )

    return capability


def _manifest() -> IntegrationManifest:
    signature = inspect.signature(IntegrationManifest)
    values = {
        "provider_id": CONTACTS_PROVIDER_ID,
        "display_name": "Contacts",
        "provider_version": "0.9.3",
        "capabilities": tuple(_cap(capability_id, mutating=capability_id in WRITE_CAPABILITIES) for capability_id in CONTACTS_CAPABILITIES),
        "auth_kind": "none",
        "metadata": {"mode": "synthetic", "provider_neutral": True, "external_connection": False},
    }
    return IntegrationManifest(**{name: values[name] for name in signature.parameters if name in values})


CONTACTS_MANIFEST = _manifest()


class ContactProvider:
    def __init__(self, *, backend: Optional[SyntheticContactsBackend] = None) -> None:
        self.backend = backend if backend is not None else SyntheticContactsBackend()

    @property
    def manifest(self) -> IntegrationManifest:
        return CONTACTS_MANIFEST

    def health_snapshot(self) -> Mapping[str, Any]:
        return {
            "available": True,
            "health_state": "synthetic-ready",
            "provider_id": CONTACTS_PROVIDER_ID,
            "mode": "SYNTHETIC",
            "external_connection": False,
        }

    def execute(self, request: IntegrationRequest) -> Mapping[str, Any]:
        if request.provider_id != CONTACTS_PROVIDER_ID:
            raise ContactsProviderError("wrong provider_id: " + str(request.provider_id))
        capability = request.capability_id
        params = dict(request.params or {})
        if capability == "contacts.search":
            return ContactResult(self.backend.search_contacts(ContactQuery.from_value(params.get("query")))).to_dict()
        if capability == "contacts.read":
            return {"contact": self.backend.get_contact(params.get("contact_id")).to_dict()}
        if capability == "contacts.create":
            contact = self.backend.create_contact(
                display_name=params.get("display_name"),
                emails=params.get("emails") or (),
                phones=params.get("phones") or (),
                organization=params.get("organization") or "",
                notes=params.get("notes") or "",
            )
            return {"contact": contact.to_dict()}
        if capability == "contacts.update":
            contact_id = params.pop("contact_id", None)
            return {"contact": self.backend.update_contact(contact_id, **params).to_dict()}
        if capability == "contacts.delete":
            return {"deleted_contact": self.backend.delete_contact(params.get("contact_id")).to_dict()}
        raise ContactsProviderError("unsupported Contacts capability: " + str(capability))


ContactsProvider = ContactProvider

__all__ = [
    "CONTACTS_PROVIDER_ID",
    "CONTACTS_CAPABILITIES",
    "READ_CAPABILITIES",
    "WRITE_CAPABILITIES",
    "CONFIRMATION_CAPABILITIES",
    "CONTACTS_MANIFEST",
    "Contact",
    "ContactQuery",
    "ContactResult",
    "ContactProvider",
    "ContactsProvider",
    "SyntheticContactsBackend",
    "ContactsProviderError",
    "ContactLookupError",
    "ContactValidationError",
]
