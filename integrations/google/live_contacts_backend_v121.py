from __future__ import annotations

from googleapiclient.discovery import build

from integrations.contacts.provider import (
    Contact,
    ContactLookupError,
    ContactQuery,
    ContactResult,
    ContactValidationError,
)
from runtime.connected_accounts_v120 import (
    get_connected_accounts_service_v120,
)


def _default_for(name: str):
    low = name.lower()
    if low.startswith(("is_", "has_", "can_")) or low in {"primary", "all_day", "read", "trashed"}:
        return False
    if low.endswith(("s", "_ids", "_emails", "_phones", "_labels", "_attachments", "_messages", "_items", "_results")):
        return ()
    if low in {"count", "total", "size", "size_bytes", "minutes"}:
        return 0
    return ""

def _make(cls, values):
    import inspect
    sig = inspect.signature(cls)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name in values:
            kwargs[name] = values[name]
        elif param.default is inspect._empty:
            kwargs[name] = _default_for(name)
    return cls(**kwargs)

def _value(obj, *names, default=None):
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _contact(raw):
    names = raw.get("names", []) or []
    emails = raw.get("emailAddresses", []) or []
    phones = raw.get("phoneNumbers", []) or []
    orgs = raw.get("organizations", []) or []
    bios = raw.get("biographies", []) or []
    display = str((names[0] if names else {}).get("displayName", ""))
    values = {
        "contact_id": str(raw.get("resourceName", "")),
        "id": str(raw.get("resourceName", "")),
        "resource_name": str(raw.get("resourceName", "")),
        "display_name": display,
        "name": display,
        "emails": tuple(str(x.get("value", "")) for x in emails if x.get("value")),
        "email_addresses": tuple(str(x.get("value", "")) for x in emails if x.get("value")),
        "phones": tuple(str(x.get("value", "")) for x in phones if x.get("value")),
        "phone_numbers": tuple(str(x.get("value", "")) for x in phones if x.get("value")),
        "organization": str((orgs[0] if orgs else {}).get("name", "")),
        "notes": str((bios[0] if bios else {}).get("value", "")),
        "etag": str(raw.get("etag", "")),
    }
    return _make(Contact, values)

class GoogleLiveContactsBackendV121:
    mode = "GOOGLE_LIVE"

    def __init__(self, *, service=None, api_factory=build):
        self.service = service or get_connected_accounts_service_v120()
        self.api_factory = api_factory

    def _account(self):
        rows = self.service.list_accounts("google")
        if not rows:
            raise ContactLookupError("Google account is not connected")
        return rows[0]

    def _people(self):
        account = self._account()
        credentials = self.service._credentials(account)
        return self.api_factory(
            "people",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def search_contacts(self, query):
        text = str(_value(query, "text", "query", "search", default=query if isinstance(query, str) else "") or "").strip().lower()
        response = self._people().people().connections().list(
            resourceName="people/me",
            pageSize=500,
            personFields="names,emailAddresses,phoneNumbers,organizations,biographies",
        ).execute()
        contacts = tuple(_contact(x) for x in response.get("connections", []) or [])
        if text:
            contacts = tuple(
                c for c in contacts
                if text in " ".join(
                    [
                        str(_value(c, "display_name", "name", default="")),
                        " ".join(_value(c, "emails", "email_addresses", default=()) or ()),
                        " ".join(_value(c, "phones", "phone_numbers", default=()) or ()),
                        str(_value(c, "organization", default="")),
                    ]
                ).lower()
            )
        result = _make(
            ContactResult,
            {
                "contacts": contacts,
                "items": contacts,
                "results": contacts,
                "total": len(contacts),
                "count": len(contacts),
                "query": text,
            },
        )
        # AURA_V122_GOOGLE_LIVE_PROVIDER_CONTRACT_COMPAT
        # ContactProvider expects a sequence of Contact for ContactQuery.
        # Preserve ContactResult for historical direct string/dict probes.
        return contacts if isinstance(query, ContactQuery) else result

    def get_contact(self, contact_id):
        raw = self._people().people().get(
            resourceName=str(contact_id),
            personFields="names,emailAddresses,phoneNumbers,organizations,biographies",
        ).execute()
        return _contact(raw)

    def create_contact(self, *args, **kwargs):
        value = args[0] if args else kwargs.get("contact")
        display_name = kwargs.get("display_name", _value(value, "display_name", "name", default=""))
        emails = kwargs.get("emails", _value(value, "emails", "email_addresses", default=()))
        phones = kwargs.get("phones", _value(value, "phones", "phone_numbers", default=()))
        organization = kwargs.get("organization", _value(value, "organization", default=""))
        notes = kwargs.get("notes", _value(value, "notes", default=""))
        body = {
            "names": [{"givenName": str(display_name)}],
            "emailAddresses": [{"value": str(x)} for x in emails or () if str(x)],
            "phoneNumbers": [{"value": str(x)} for x in phones or () if str(x)],
        }
        if organization:
            body["organizations"] = [{"name": str(organization)}]
        if notes:
            body["biographies"] = [{"value": str(notes), "contentType": "TEXT_PLAIN"}]
        raw = self._people().people().createContact(body=body).execute()
        return _contact(raw)

    def update_contact(self, contact_id, **changes):
        current = self._people().people().get(
            resourceName=str(contact_id),
            personFields="names,emailAddresses,phoneNumbers,organizations,biographies,metadata",
        ).execute()
        fields = []
        if "display_name" in changes or "name" in changes:
            current["names"] = [{"givenName": str(changes.get("display_name", changes.get("name", "")))}]
            fields.append("names")
        if "emails" in changes:
            current["emailAddresses"] = [{"value": str(x)} for x in changes["emails"] or () if str(x)]
            fields.append("emailAddresses")
        if "phones" in changes:
            current["phoneNumbers"] = [{"value": str(x)} for x in changes["phones"] or () if str(x)]
            fields.append("phoneNumbers")
        if "organization" in changes:
            current["organizations"] = [{"name": str(changes["organization"])}]
            fields.append("organizations")
        if "notes" in changes:
            current["biographies"] = [{"value": str(changes["notes"]), "contentType": "TEXT_PLAIN"}]
            fields.append("biographies")
        if not fields:
            raise ContactValidationError("no contact fields to update")
        raw = self._people().people().updateContact(
            resourceName=str(contact_id),
            updatePersonFields=",".join(fields),
            body=current,
        ).execute()
        return _contact(raw)

    def delete_contact(self, contact_id):
        self._people().people().deleteContact(
            resourceName=str(contact_id),
        ).execute()
        return True

    def health_snapshot(self):
        account = self._account()
        return {
            "health_state": "google-live-ready",
            "mode": self.mode,
            "provider": "google",
            "account": account.display_label,
            "network_on_demand": True,
        }

__all__ = ["GoogleLiveContactsBackendV121"]
