from __future__ import annotations

import base64
from email.message import EmailMessage as MimeEmailMessage
from email.utils import getaddresses, parseaddr
from typing import Any

from googleapiclient.discovery import build

from integrations.email.provider import (
    EmailAddress,
    EmailAttachment,
    EmailDraft,
    EmailLookupError,
    EmailMessage,
    EmailQuery,
    EmailResult,
    EmailThread,
    EmailValidationError,
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


def _decode_b64(data: str) -> bytes:
    if not data:
        return b""
    pad = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode((data + pad).encode("ascii"))

def _headers(payload):
    return {
        str(item.get("name", "")).lower(): str(item.get("value", ""))
        for item in payload.get("headers", [])
    }

def _body_text(part) -> str:
    mime = str(part.get("mimeType", ""))
    body = part.get("body", {}) or {}
    if mime.startswith("text/plain") and body.get("data"):
        return _decode_b64(body["data"]).decode("utf-8", errors="replace")
    for child in part.get("parts", []) or []:
        text = _body_text(child)
        if text:
            return text
    if body.get("data"):
        return _decode_b64(body["data"]).decode("utf-8", errors="replace")
    return ""

def _addresses(raw: str):
    rows = []
    for name, addr in getaddresses([raw or ""]):
        if not addr:
            continue
        rows.append(
            _make(
                EmailAddress,
                {
                    "name": name,
                    "display_name": name,
                    "email": addr,
                    "address": addr,
                },
            )
        )
    return tuple(rows)

def _message(item):
    payload = item.get("payload", {}) or {}
    hdr = _headers(payload)
    message_id = str(item.get("id", ""))
    thread_id = str(item.get("threadId", ""))
    values = {
        "message_id": message_id,
        "id": message_id,
        "thread_id": thread_id,
        "subject": hdr.get("subject", ""),
        "sender": _addresses(hdr.get("from", ""))[0] if _addresses(hdr.get("from", "")) else _make(EmailAddress, {"email": ""}),
        "from_address": _addresses(hdr.get("from", ""))[0] if _addresses(hdr.get("from", "")) else _make(EmailAddress, {"email": ""}),
        "from_": _addresses(hdr.get("from", ""))[0] if _addresses(hdr.get("from", "")) else _make(EmailAddress, {"email": ""}),
        "to": _addresses(hdr.get("to", "")),
        "cc": _addresses(hdr.get("cc", "")),
        "bcc": _addresses(hdr.get("bcc", "")),
        "body": _body_text(payload),
        "text": _body_text(payload),
        "snippet": str(item.get("snippet", "")),
        "labels": tuple(item.get("labelIds", []) or []),
        "label_ids": tuple(item.get("labelIds", []) or []),
        "internal_date": str(item.get("internalDate", "")),
        "received_at": str(item.get("internalDate", "")),
        "date": hdr.get("date", ""),
        "headers": hdr,
        "attachments": (),
    }
    return _make(EmailMessage, values)

def _query_text(query) -> str:
    if isinstance(query, str):
        return query.strip()
    bits = []
    text = _value(query, "text", "query", "search", default="")
    if text:
        bits.append(str(text))
    sender = _value(query, "sender", "from_", "from_address", default="")
    if sender:
        bits.append("from:" + str(sender))
    subject = _value(query, "subject", default="")
    if subject:
        bits.append("subject:" + str(subject))
    unread = _value(query, "unread", "is_unread", default=None)
    if unread is True:
        bits.append("is:unread")
    return " ".join(bits).strip()

class GoogleLiveEmailBackendV121:
    mode = "GOOGLE_LIVE"

    def __init__(self, *, service=None, api_factory=build):
        self.service = service or get_connected_accounts_service_v120()
        self.api_factory = api_factory

    def _account(self):
        rows = self.service.list_accounts("google")
        if not rows:
            raise EmailLookupError("Google account is not connected")
        return rows[0]

    def _gmail(self):
        account = self._account()
        credentials = self.service._credentials(account)
        return self.api_factory(
            "gmail",
            "v1",
            credentials=credentials,
            cache_discovery=False,
        )

    def search_messages(self, query):
        gmail = self._gmail()
        limit = int(_value(query, "limit", "max_results", default=25) or 25)
        response = gmail.users().messages().list(
            userId="me",
            q=_query_text(query),
            maxResults=max(1, min(limit, 100)),
        ).execute()
        messages = tuple(
            _message(
                gmail.users().messages().get(
                    userId="me",
                    id=str(row["id"]),
                    format="full",
                ).execute()
            )
            for row in response.get("messages", []) or []
        )
        result = _make(
            EmailResult,
            {
                "messages": messages,
                "items": messages,
                "results": messages,
                "total": len(messages),
                "count": len(messages),
                "query": _query_text(query),
                "next_page_token": response.get("nextPageToken", ""),
            },
        )
        # AURA_V122_GOOGLE_LIVE_PROVIDER_CONTRACT_COMPAT
        # EmailProvider expects a sequence of EmailMessage for EmailQuery.
        # Preserve EmailResult for historical direct dict/string probes.
        return messages if isinstance(query, EmailQuery) else result

    def get_message(self, message_id):
        try:
            raw = self._gmail().users().messages().get(
                userId="me",
                id=str(message_id),
                format="full",
            ).execute()
        except Exception as exc:
            raise EmailLookupError(str(type(exc).__name__)) from exc
        return _message(raw)

    def get_thread(self, thread_id):
        raw = self._gmail().users().threads().get(
            userId="me",
            id=str(thread_id),
            format="full",
        ).execute()
        messages = tuple(_message(x) for x in raw.get("messages", []) or [])
        return _make(
            EmailThread,
            {
                "thread_id": str(raw.get("id", thread_id)),
                "id": str(raw.get("id", thread_id)),
                "messages": messages,
                "items": messages,
            },
        )

    def list_attachments(self, message_id):
        raw = self._gmail().users().messages().get(
            userId="me",
            id=str(message_id),
            format="full",
        ).execute()
        rows = []

        def visit(part):
            filename = str(part.get("filename", "") or "")
            body = part.get("body", {}) or {}
            attachment_id = str(body.get("attachmentId", "") or "")
            if filename or attachment_id:
                rows.append(
                    _make(
                        EmailAttachment,
                        {
                            "attachment_id": attachment_id,
                            "id": attachment_id,
                            "message_id": str(message_id),
                            "filename": filename,
                            "name": filename,
                            "mime_type": str(part.get("mimeType", "")),
                            "size": int(body.get("size", 0) or 0),
                            "size_bytes": int(body.get("size", 0) or 0),
                        },
                    )
                )
            for child in part.get("parts", []) or []:
                visit(child)

        visit(raw.get("payload", {}) or {})
        return tuple(rows)

    @staticmethod
    def _mime(*, to=(), cc=(), bcc=(), subject="", body="", reply_to=""):
        msg = MimeEmailMessage()
        def normalize(values):
            if isinstance(values, str):
                return values
            out = []
            for value in values or ():
                out.append(str(_value(value, "email", "address", default=value)))
            return ", ".join(x for x in out if x)
        msg["To"] = normalize(to)
        if cc:
            msg["Cc"] = normalize(cc)
        if bcc:
            msg["Bcc"] = normalize(bcc)
        if subject:
            msg["Subject"] = str(subject)
        if reply_to:
            msg["In-Reply-To"] = str(reply_to)
            msg["References"] = str(reply_to)
        msg.set_content(str(body or ""))
        return base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    def create_draft(self, draft=None, **kwargs):
        to = _value(draft, "to", "recipients", default=kwargs.get("to", ()))
        subject = _value(draft, "subject", default=kwargs.get("subject", ""))
        body = _value(draft, "body", "text", default=kwargs.get("body", ""))
        raw = self._mime(to=to, subject=subject, body=body)
        result = self._gmail().users().drafts().create(
            userId="me",
            body={"message": {"raw": raw}},
        ).execute()
        return _make(
            EmailDraft,
            {
                "draft_id": str(result.get("id", "")),
                "id": str(result.get("id", "")),
                "to": to,
                "subject": subject,
                "body": body,
            },
        )

    def send_message(self, *args, **kwargs):
        draft = args[0] if args else kwargs.get("draft")
        to = kwargs.get("to", _value(draft, "to", "recipients", default=()))
        subject = kwargs.get("subject", _value(draft, "subject", default=""))
        body = kwargs.get("body", _value(draft, "body", "text", default=""))
        raw = self._mime(to=to, cc=kwargs.get("cc", ()), bcc=kwargs.get("bcc", ()), subject=subject, body=body)
        result = self._gmail().users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        return self.get_message(result["id"])

    def reply_message(self, *args, **kwargs):
        message_id = str(kwargs.get("message_id") or (args[0] if args else ""))
        body = kwargs.get("body", kwargs.get("text", ""))
        original = self._gmail().users().messages().get(
            userId="me",
            id=message_id,
            format="metadata",
            metadataHeaders=["From", "Subject", "Message-ID"],
        ).execute()
        hdr = _headers(original.get("payload", {}) or {})
        to = [parseaddr(hdr.get("from", ""))[1]]
        subject = hdr.get("subject", "")
        if subject and not subject.lower().startswith("re:"):
            subject = "Re: " + subject
        raw = self._mime(
            to=to,
            subject=subject,
            body=body,
            reply_to=hdr.get("message-id", ""),
        )
        result = self._gmail().users().messages().send(
            userId="me",
            body={"raw": raw, "threadId": original.get("threadId")},
        ).execute()
        return self.get_message(result["id"])

    def forward_message(self, *args, **kwargs):
        message_id = str(kwargs.get("message_id") or (args[0] if args else ""))
        to = kwargs.get("to", kwargs.get("recipients", ()))
        original = self.get_message(message_id)
        subject = str(_value(original, "subject", default=""))
        if subject and not subject.lower().startswith("fwd:"):
            subject = "Fwd: " + subject
        body = kwargs.get("body", "") + "\n\n" + str(_value(original, "body", "text", default=""))
        raw = self._mime(to=to, subject=subject, body=body)
        result = self._gmail().users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        return self.get_message(result["id"])

    def archive_message(self, message_id):
        self._gmail().users().messages().modify(
            userId="me",
            id=str(message_id),
            body={"removeLabelIds": ["INBOX"]},
        ).execute()
        return self.get_message(message_id)

    def trash_message(self, message_id):
        self._gmail().users().messages().trash(
            userId="me",
            id=str(message_id),
        ).execute()
        return self.get_message(message_id)

    def set_labels(self, *args, **kwargs):
        message_id = str(kwargs.get("message_id") or (args[0] if args else ""))
        labels = kwargs.get("labels", kwargs.get("label_ids", ()))
        add_labels = kwargs.get("add_labels", labels)
        remove_labels = kwargs.get("remove_labels", ())
        self._gmail().users().messages().modify(
            userId="me",
            id=message_id,
            body={
                "addLabelIds": list(add_labels or ()),
                "removeLabelIds": list(remove_labels or ()),
            },
        ).execute()
        return self.get_message(message_id)

    def health_snapshot(self):
        account = self._account()
        return {
            "health_state": "google-live-ready",
            "mode": self.mode,
            "provider": "google",
            "account": account.display_label,
            "network_on_demand": True,
        }

__all__ = ["GoogleLiveEmailBackendV121"]
