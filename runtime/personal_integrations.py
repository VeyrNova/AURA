"""AURA v0.9.2.1 Personal Integration Runtime Wiring - D2 R1.

Provider-neutral conversation/runtime boundary for certified Email + Calendar.
Google-live personal integrations are the v1.2.1 production default; synthetic wiring is retained only as an internal compatibility fallback.
"""
from __future__ import annotations

import os
import re
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone, tzinfo
from pathlib import Path
from typing import Any, Mapping, Optional
from zoneinfo import ZoneInfo

from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations import IntegrationRegistry, IntegrationRequest, IntegrationResult
from integrations.email import (
    CONFIRMATION_CAPABILITIES as EMAIL_CONFIRMATION_CAPABILITIES,
    EmailAddress,
    EmailAttachment,
    EmailMessage,
    EmailProvider,
    SyntheticEmailBackend,
)
from integrations.calendar import (
    CONFIRMATION_CAPABILITIES as CALENDAR_CONFIRMATION_CAPABILITIES,
    CalendarAttendee,
    CalendarEvent,
    CalendarInfo,
    CalendarProvider,
    SyntheticCalendarBackend,
)
from integrations.contacts import (
    CONFIRMATION_CAPABILITIES as CONTACTS_CONFIRMATION_CAPABILITIES,
    ContactProvider,
    SyntheticContactsBackend,
)
from integrations.files import (
    CONFIRMATION_CAPABILITIES as FILES_CONFIRMATION_CAPABILITIES,
    FilesProvider,
    SyntheticFilesBackend,
)
from integrations.tasks import (
    TASKS_CONFIRMATION_CAPABILITIES,
)

EMAIL_PROVIDER_ID = "email.provider"
CALENDAR_PROVIDER_ID = "calendar.provider"
CONTACTS_PROVIDER_ID = "contacts.provider"
FILES_PROVIDER_ID = "files.provider"
TASKS_PROVIDER_ID = "tasks.provider"
WRITE_CAPABILITIES = frozenset(
    tuple(EMAIL_CONFIRMATION_CAPABILITIES)
    + tuple(CALENDAR_CONFIRMATION_CAPABILITIES)
    + tuple(CONTACTS_CONFIRMATION_CAPABILITIES)
    + tuple(FILES_CONFIRMATION_CAPABILITIES)
    + tuple(TASKS_CONFIRMATION_CAPABILITIES)
)
CONFIRM_WORDS = frozenset(
    {"confirme", "confirmer", "je confirme", "oui confirme", "ok confirme"}
)
CANCEL_WORDS = frozenset(
    {"annule", "annuler", "non annule", "cancel"}
)


class RuntimeWiringError(RuntimeError):
    pass


class AmbiguousIntegrationIntent(RuntimeWiringError):
    pass


class _EuropeParisFallback(tzinfo):
    """Dependency-free Europe/Paris fallback for Windows without tzdata."""

    @staticmethod
    def _last_sunday(year: int, month: int) -> int:
        last = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
        return last.day - ((last.weekday() + 1) % 7)

    def dst(self, dt):
        if dt is None:
            return timedelta(0)
        y = dt.year
        march = self._last_sunday(y, 3)
        october = self._last_sunday(y, 10)
        naive = dt.replace(tzinfo=None)
        start = datetime(y, 3, march, 2, 0, 0)
        end = datetime(y, 10, october, 3, 0, 0)
        return timedelta(hours=1) if start <= naive < end else timedelta(0)

    def utcoffset(self, dt):
        return timedelta(hours=1) + self.dst(dt)

    def tzname(self, dt):
        return "CEST" if self.dst(dt) else "CET"


def resolve_timezone(name: str = "Europe/Paris") -> tzinfo:
    """Resolve IANA timezone; stay functional on Windows without tzdata."""
    try:
        return ZoneInfo(name)
    except Exception:
        if str(name).casefold() == "europe/paris":
            return _EuropeParisFallback()
        local = datetime.now().astimezone().tzinfo
        return local if local is not None else timezone.utc


def _normalize(text: str) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"\s+", " ", value.casefold().strip())
    return value


def _extract_email(text: str) -> Optional[str]:
    match = re.search(
        r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
        text,
        flags=re.I,
    )
    return match.group(0) if match else None


def _extract_message_id(text: str) -> Optional[str]:
    match = re.search(r"\bmsg[-_][A-Za-z0-9._\-]+\b", text, flags=re.I)
    return match.group(0) if match else None


def _extract_event_id(text: str) -> Optional[str]:
    match = re.search(r"\bevt[-_][A-Za-z0-9._\-]+\b", text, flags=re.I)
    return match.group(0) if match else None


def _next_weekday(base, weekday: int):
    delta = (weekday - base.weekday()) % 7
    if delta == 0:
        delta = 7
    return base + timedelta(days=delta)


@dataclass(frozen=True)
class ResolvedIntegrationIntent:
    provider_id: str
    capability_id: str
    params: Mapping[str, Any]
    summary: str
    confidence: float = 1.0


@dataclass(frozen=True)
class IntegrationRuntimeReply:
    handled: bool
    text: str = ""
    status: str = "not_handled"
    capability_id: Optional[str] = None
    receipt_id: Optional[str] = None
    pending_confirmation: bool = False
    clarification_required: bool = False
    payload: Optional[Mapping[str, Any]] = None


@dataclass
class PendingIntegrationAction:
    request: IntegrationRequest
    summary: str
    receipt_id: str
    capability_id: str


@dataclass
class IntegrationRuntimeContext:
    registry: IntegrationRegistry
    receipt_service: ActionReceiptService
    email_backend: SyntheticEmailBackend
    calendar_backend: SyntheticCalendarBackend
    timezone_name: str = "Europe/Paris"


class IntegrationConfirmationBroker:
    def __init__(self):
        self._pending: Optional[PendingIntegrationAction] = None

    @property
    def pending(self):
        return self._pending

    def set_pending(self, *, request, summary, receipt_id, capability_id):
        self._pending = PendingIntegrationAction(
            request=request,
            summary=summary,
            receipt_id=receipt_id,
            capability_id=capability_id,
        )
        return self._pending

    def clear(self):
        current = self._pending
        self._pending = None
        return current



def _extract_virtual_file_path(text: str) -> str:
    raw = str(text or "")

    quoted = re.search(
        r'["\']([^"\']+)["\']',
        raw,
    )
    if quoted:
        return quoted.group(1).strip()

    match = re.search(
        r"\bfichier\s+([A-Za-z0-9_. /\\-]+\.[A-Za-z0-9]{1,12})",
        raw,
        flags=re.I,
    )
    if match:
        return match.group(1).strip()

    return ""


def _extract_two_virtual_file_paths(text: str) -> tuple[str, str]:
    raw = str(text or "")

    quoted = re.findall(
        r'["\']([^"\']+)["\']',
        raw,
    )
    if len(quoted) >= 2:
        return quoted[0].strip(), quoted[1].strip()

    match = re.search(
        r"\bfichier\s+(\S+)\s+(?:vers|dans)\s+(\S+)",
        raw,
        flags=re.I,
    )
    if match:
        return match.group(1).strip(), match.group(2).strip()

    return "", ""


class IntegrationIntentResolver:
    """Deterministic French-first Email/Calendar intent resolver."""

    def __init__(self, *, timezone_name: str = "Europe/Paris"):
        self.timezone_name = timezone_name

    def _now(self) -> datetime:
        return datetime.now(resolve_timezone(self.timezone_name))

    def resolve_integration_intent(self, text: str):
        raw = str(text or "").strip()
        normalized = _normalize(raw)
        if not normalized:
            return None

        # EMAIL -----------------------------------------------------
        # AURA_V122_GOOGLE_CONVERSATIONAL_COVERAGE_BEGIN

        # AURA_V123_PRODUCTIVITY_NL_PARITY_BEGIN
        if (
            re.search(
                r"\b(prochains?|agenda|rendez[- ]?vous|rdv|evenements?)\b",
                normalized,
            )
            and not re.search(
                r"\b(cree|creer|ajoute|ajouter|modifie|modifier|supprime|supprimer|efface|effacer)\b",
                normalized,
            )
        ):
            return ResolvedIntegrationIntent(
                provider_id=CALENDAR_PROVIDER_ID,
                capability_id="calendar.search_events",
                params={
                    "query": {
                        "calendar_id": "cal-main",
                        "text": "",
                        "limit": 20,
                    }
                },
                summary="Afficher les prochains rendez-vous Google",
            )

        if (
            re.search(
                r"\b(affiche|montre|liste|lister|voir)\b.*\bcontacts?\b",
                normalized,
            )
            or normalized in {"contacts", "mes contacts"}
        ):
            return ResolvedIntegrationIntent(
                provider_id=CONTACTS_PROVIDER_ID,
                capability_id="contacts.search",
                params={"query": {"text": "", "limit": 100}},
                summary="Afficher les contacts Google",
            )

        if (
            re.search(
                r"\b(affiche|montre|liste|lister|voir)\b.*\b(tache|taches|todo|tasks?)\b",
                normalized,
            )
            or normalized in {"tache", "taches", "mes taches", "google tasks"}
        ):
            return ResolvedIntegrationIntent(
                provider_id=TASKS_PROVIDER_ID,
                capability_id="tasks.list",
                params={
                    "query": {
                        "tasklist_id": "@default",
                        "limit": 100,
                        "include_completed": True,
                    }
                },
                summary="Afficher les taches Google",
            )
        # AURA_V123_PRODUCTIVITY_NL_PARITY_END
        # Natural Gmail list/plural requests. Keep the historical singular
        # "affiche/lis le mail <id>" branch below untouched for email.read.
        if (
            re.search(
                r"\b(affiche|afficher|montre|montrer|liste|lister)\b"
                r".*\b(mails|emails|courriels)\b",
                normalized,
            )
            or re.search(
                r"\b(derniers?|dernieres?|recents?|recentes?)\b"
                r".*\b(mails|emails|courriels)\b",
                normalized,
            )
        ):
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.search",
                {"query": {"text": "", "limit": 10}},
                "Lister les derniers emails",
            )

        # Google Drive is the live backend behind AURA's existing Files
        # provider. Add only conversational aliases; do not create a new API
        # stack and do not weaken Drive's read-only mutation policy.
        if re.search(
            r"\b(cherche|chercher|trouve|trouver|recherche)\b"
            r".*\b(?:google\s+drive|drive)\b",
            normalized,
        ):
            query = re.sub(
                r"(?i)\b(aura|cherche|chercher|trouve|trouver|recherche|"
                r"dans|sur|mes|mon|ma|le|la|les|google|drive)\b",
                " ",
                raw,
            )
            query = re.sub(r"[\s,:;-]+", " ", query).strip()
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.search",
                {
                    "query": {
                        "text": query,
                        "limit": 20,
                    }
                },
                "Rechercher dans Google Drive"
                + (f" concernant {query}" if query else ""),
            )

        if re.search(
            r"\b(affiche|afficher|montre|montrer|liste|lister)\b"
            r".*\b(?:google\s+drive|drive)\b",
            normalized,
        ):
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.list",
                {"path": ""},
                "Lister les fichiers Google Drive",
            )
        # AURA_V122_GOOGLE_CONVERSATIONAL_COVERAGE_END

        if re.search(r"\b(cherche|recherche|trouve)\b.*\b(mail|mails|email|emails)\b", normalized):
            subject = re.sub(
                r"^.*?\b(mail|mails|email|emails)\b",
                "",
                normalized,
                count=1,
            ).strip(" :,-")
            subject = re.sub(
                r"^(sur|concernant|pour|avec|au sujet de)\s+",
                "",
                subject,
            ).strip()
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.search",
                {"query": {"text": subject, "limit": 10}},
                "Rechercher les emails" + (f" concernant  {subject} " if subject else ""),
            )

        if re.search(r"\b(lis|lire|ouvre|affiche)\b.*\b(mail|email)\b", normalized):
            message_id = _extract_message_id(raw)
            if not message_id:
                if re.search(r"\b(dernier|derniere|recent|recente)\b", normalized):
                    return ResolvedIntegrationIntent(
                        EMAIL_PROVIDER_ID,
                        "email.search",
                        {"query": {"text": "", "limit": 1}},
                        "Lire le dernier email disponible",
                    )
                raise AmbiguousIntegrationIntent(
                    "Indique l'identifiant du mail, par exemple  lis le mail msg-001 ."
                )
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.read",
                {"message_id": message_id},
                f"Lire le mail {message_id}",
            )

        if re.search(r"\b(piece|pieces|pj|jointes|attachments?)\b.*\b(mail|email)\b", normalized):
            message_id = _extract_message_id(raw)
            if not message_id:
                raise AmbiguousIntegrationIntent("Indique l'identifiant du mail.")
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.list_attachments",
                {"message_id": message_id},
                f"Lister les pieces jointes du mail {message_id}",
            )

        if re.search(r"\b(cree|creer|prepare|preparer)\b.*\b(brouillon|draft)\b", normalized):
            address = _extract_email(raw)
            if not address:
                raise AmbiguousIntegrationIntent("Indique une adresse email explicite.")
            body_match = re.search(r"\b(?:message|texte)\s+(.+)$", raw, flags=re.I)
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.create_draft",
                {
                    "to": [address],
                    "subject": "Brouillon AURA",
                    "body_text": body_match.group(1).strip() if body_match else "Brouillon synthetique AURA.",
                },
                f"Creer un brouillon pour {address}",
            )

        if re.search(r"\b(envoie|envoyer)\b.*\b(mail|email)\b", normalized):
            address = _extract_email(raw)
            if not address:
                raise AmbiguousIntegrationIntent("Indique l'adresse du destinataire.")
            body_match = re.search(r"\b(?:message|texte)\s+(.+)$", raw, flags=re.I)
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.send",
                {
                    "to": [address],
                    "subject": "Message AURA",
                    "body_text": body_match.group(1).strip() if body_match else "Message synthetique AURA.",
                },
                f"Envoyer un email a {address}",
            )

        # AURA_V22_ROUTER_R1_EMAIL_REPLY_SCOPE_GUARD
        if (
            re.search(r"\b(reponds|repondre|reply)\b", normalized)
            and (
                re.search(
                    r"\b(mail|mails|email|emails|courriel|courriels)\b",
                    normalized,
                )
                or _extract_message_id(raw)
            )
        ):
            message_id = _extract_message_id(raw)
            if not message_id:
                raise AmbiguousIntegrationIntent("Indique l'identifiant du mail auquel repondre.")
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.reply",
                {"message_id": message_id, "body_text": "Reponse synthetique AURA."},
                f"Repondre au mail {message_id}",
            )

        if re.search(r"\b(transfere|transferer|forward)\b", normalized):
            message_id = _extract_message_id(raw)
            address = _extract_email(raw)
            if not message_id or not address:
                raise AmbiguousIntegrationIntent("Indique le mail et l'adresse de destination.")
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.forward",
                {
                    "message_id": message_id,
                    "to": [address],
                    "body_text": "Transfert synthetique AURA.",
                },
                f"Transferer {message_id} vers {address}",
            )

        if re.search(r"\b(archive|archiver)\b", normalized):
            message_id = _extract_message_id(raw)
            if not message_id:
                raise AmbiguousIntegrationIntent("Indique le mail a archiver.")
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.archive",
                {"message_id": message_id},
                f"Archiver le mail {message_id}",
            )

        if re.search(r"\b(corbeille|supprime|supprimer|trash)\b.*\b(mail|email)?\b", normalized):
            message_id = _extract_message_id(raw)
            if not message_id:
                raise AmbiguousIntegrationIntent("Indique le mail a mettre a la corbeille.")
            return ResolvedIntegrationIntent(
                EMAIL_PROVIDER_ID,
                "email.trash",
                {"message_id": message_id},
                f"Mettre le mail {message_id} a la corbeille",
            )

        # FILES / DOCUMENTS ----------------------------------------
        if re.search(
            r"\b(supprime|supprimer|efface|effacer|delete)\b.*\bfichier\b",
            normalized,
        ):
            path = _extract_virtual_file_path(raw)
            if not path:
                raise AmbiguousIntegrationIntent(
                    "Indique le chemin du fichier entre guillemets."
                )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.delete",
                {"path": path},
                f"Supprimer le fichier {path}",
            )

        if re.search(
            r"\b(deplace|deplacer|move)\b.*\bfichier\b",
            normalized,
        ):
            source_path, destination = _extract_two_virtual_file_paths(raw)
            if not source_path or not destination:
                raise AmbiguousIntegrationIntent(
                    "Indique le fichier source et la destination entre guillemets."
                )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.move",
                {
                    "source": source_path,
                    "destination": destination,
                },
                f"Deplacer {source_path} vers {destination}",
            )

        if re.search(
            r"\b(modifie|modifier|mets? a jour|update)\b.*\bfichier\b",
            normalized,
        ):
            path = _extract_virtual_file_path(raw)
            if not path:
                raise AmbiguousIntegrationIntent(
                    "Indique le chemin du fichier entre guillemets."
                )
            content_match = re.search(
                r"\b(?:texte|contenu)\s+(.+)$",
                raw,
                flags=re.I,
            )
            if not content_match:
                raise AmbiguousIntegrationIntent(
                    "Indique le nouveau texte apres le mot contenu."
                )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.update",
                {
                    "path": path,
                    "text": content_match.group(1).strip(),
                    "append": False,
                },
                f"Modifier le fichier {path}",
            )

        if re.search(
            r"\b(cree|creer|ajoute|ajouter)\b.*\bfichier\b",
            normalized,
        ):
            path = _extract_virtual_file_path(raw)
            if not path:
                raise AmbiguousIntegrationIntent(
                    "Indique le chemin du fichier entre guillemets."
                )
            content_match = re.search(
                r"\b(?:texte|contenu)\s+(.+)$",
                raw,
                flags=re.I,
            )
            text_value = (
                content_match.group(1).strip()
                if content_match
                else ""
            )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.create",
                {
                    "path": path,
                    "text": text_value,
                },
                f"Creer le fichier {path}",
            )

        if re.search(
            r"\b(lis|lire|ouvre|affiche)\b.*\bfichier\b",
            normalized,
        ):
            path = _extract_virtual_file_path(raw)
            if not path:
                raise AmbiguousIntegrationIntent(
                    "Indique le chemin du fichier entre guillemets."
                )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.read",
                {"path": path},
                f"Lire le fichier {path}",
            )

        if re.search(
            r"\b(liste|lister|affiche)\b.*\b(fichier|fichiers|documents)\b",
            normalized,
        ):
            folder_match = re.search(
                r"\b(?:dans|dossier)\s+([A-Za-z0-9_. /\\-]+)$",
                raw,
                flags=re.I,
            )
            folder = (
                folder_match.group(1).strip()
                if folder_match
                else ""
            )
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.list",
                {"path": folder},
                "Lister les fichiers"
                + (f" dans {folder}" if folder else ""),
            )

        if re.search(
            r"\b(cherche|chercher|trouve|trouver|recherche)\b"
            r".*\b(fichier|fichiers|document|documents)\b",
            normalized,
        ):
            query = re.sub(
                r"(?i)\b(cherche|chercher|trouve|trouver|recherche|"
                r"fichier|fichiers|document|documents|dans|mes|mon|le|la|les|un|une)\b",
                " ",
                raw,
            )
            query = re.sub(r"\s+", " ", query).strip()
            return ResolvedIntegrationIntent(
                FILES_PROVIDER_ID,
                "files.search",
                {
                    "query": {
                        "text": query,
                        "limit": 20,
                    }
                },
                "Rechercher les fichiers"
                + (f" concernant {query}" if query else ""),
            )

        # CONTACTS -------------------------------------------------
        if re.search(r"\b(lis|lire|ouvre|affiche)\b.*\bcontact\b.*\bctc-[a-z0-9-]+\b", normalized):
            match = re.search(r"\bctc-[a-z0-9-]+\b", normalized)
            contact_id = match.group(0) if match else ""
            return ResolvedIntegrationIntent(
                CONTACTS_PROVIDER_ID,
                "contacts.read",
                {"contact_id": contact_id},
                f"Lire le contact {contact_id}",
            )

        if re.search(r"\b(cherche|chercher|trouve|trouver|recherche|liste|lister|affiche)\b.*\b(contact|contacts|personne|personnes)\b", normalized):
            query = re.sub(
                r"(?i)\b(cherche|chercher|trouve|trouver|recherche|liste|lister|affiche|contact|contacts|personne|personnes|dans|mes|mon|le|la|les|un|une)\b",
                " ",
                raw,
            )
            query = re.sub(r"\s+", " ", query).strip()
            return ResolvedIntegrationIntent(
                CONTACTS_PROVIDER_ID,
                "contacts.search",
                {"query": {"text": query, "limit": 10}},
                "Rechercher les contacts" + (f" concernant {query}" if query else ""),
            )

        if re.search(r"\b(cree|creer|ajoute|ajouter)\b.*\b(contact|personne)\b", normalized):
            email = _extract_email(raw)
            name_match = re.search(r"\b(?:nom|contact|personne)\s+([^,;]+)", raw, flags=re.I)
            display_name = name_match.group(1).strip() if name_match else "Nouveau contact AURA"
            display_name = re.sub(r"\b(?:email|mail)\b.*$", "", display_name, flags=re.I).strip() or "Nouveau contact AURA"
            phone_match = re.search(r"(?<!\d)(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)", raw)
            phone = phone_match.group(0).strip() if phone_match else ""
            return ResolvedIntegrationIntent(
                CONTACTS_PROVIDER_ID,
                "contacts.create",
                {
                    "display_name": display_name,
                    "emails": [email] if email else [],
                    "phones": [phone] if phone else [],
                },
                f"Creer le contact {display_name}",
            )

        if re.search(r"\b(modifie|modifier|mets? a jour|update)\b.*\bcontact\b", normalized):
            match = re.search(r"\bctc-[a-z0-9-]+\b", normalized)
            if not match:
                raise AmbiguousIntegrationIntent("Indique l'identifiant du contact, par exemple ctc-001.")
            contact_id = match.group(0)
            email = _extract_email(raw)
            params = {"contact_id": contact_id}
            if email:
                params["emails"] = [email]
            phone_match = re.search(r"(?<!\d)(?:\+33|0)[1-9](?:[\s.-]?\d{2}){4}(?!\d)", raw)
            if phone_match:
                params["phones"] = [phone_match.group(0).strip()]
            name_match = re.search(r"\b(?:nom|renomme|renommer)\s+([^,;]+)", raw, flags=re.I)
            if name_match:
                params["display_name"] = name_match.group(1).strip()
            if len(params) == 1:
                raise AmbiguousIntegrationIntent("Indique le nouveau nom, email ou telephone du contact.")
            return ResolvedIntegrationIntent(
                CONTACTS_PROVIDER_ID,
                "contacts.update",
                params,
                f"Modifier le contact {contact_id}",
            )

        if re.search(r"\b(supprime|supprimer|efface|effacer|delete)\b.*\bcontact\b", normalized):
            match = re.search(r"\bctc-[a-z0-9-]+\b", normalized)
            if not match:
                raise AmbiguousIntegrationIntent("Indique l'identifiant du contact a supprimer.")
            contact_id = match.group(0)
            return ResolvedIntegrationIntent(
                CONTACTS_PROVIDER_ID,
                "contacts.delete",
                {"contact_id": contact_id},
                f"Supprimer le contact {contact_id}",
            )

        # CALENDAR READS -------------------------------------------
        if re.search(r"\b(prochains?|rendez[- ]?vous|rdv|agenda|evenements?)\b", normalized) and not re.search(
            r"\b(cree|creer|ajoute|ajouter|modifie|supprime)\b", normalized
        ):
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.search_events",
                {"query": {"calendar_id": "cal-main", "text": "", "limit": 10}},
                "Afficher les prochains rendez-vous synthetiques",
            )

        if re.search(r"\b(liste|affiche)\b.*\b(calendrier|calendriers|agenda)\b", normalized):
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.list",
                {},
                "Lister les calendriers synthetiques",
            )

        if re.search(r"\b(libre|disponible|disponibilite)\b", normalized):
            now = self._now()
            target = (now + timedelta(days=1)).date() if "demain" in normalized else now.date()
            hours = re.findall(r"\b([01]?\d|2[0-3])\s*h(?:\s*([0-5]\d))?\b", normalized)
            if len(hours) < 2:
                raise AmbiguousIntegrationIntent(
                    "Indique une plage, par exemple  suis-je libre demain entre 14h et 16h ."
                )
            h1, m1 = int(hours[0][0]), int(hours[0][1] or 0)
            h2, m2 = int(hours[1][0]), int(hours[1][1] or 0)
            tz = resolve_timezone(self.timezone_name)
            start = datetime(target.year, target.month, target.day, h1, m1, tzinfo=tz)
            end = datetime(target.year, target.month, target.day, h2, m2, tzinfo=tz)
            if end <= start:
                raise AmbiguousIntegrationIntent("La fin doit etre apres le debut.")
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.free_busy",
                {
                    "calendar_id": "cal-main",
                    "time_min": start.isoformat(),
                    "time_max": end.isoformat(),
                },
                f"Verifier la disponibilite de {start.strftime('%H:%M')} a {end.strftime('%H:%M')}",
            )

        if re.search(r"\b(lis|affiche|ouvre)\b.*\b(evenement|rendez[- ]?vous|rdv)\b", normalized):
            event_id = _extract_event_id(raw)
            if not event_id:
                raise AmbiguousIntegrationIntent("Indique l'identifiant evt-...")
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.read_event",
                {"event_id": event_id},
                f"Lire l'evenement {event_id}",
            )

        # CALENDAR WRITES ------------------------------------------
        if re.search(r"\b(cree|creer|ajoute|ajouter)\b.*\b(rendez[- ]?vous|rdv|evenement)\b", normalized):
            now = self._now()
            target = (now + timedelta(days=1)).date() if "demain" in normalized else now.date()
            weekdays = {
                "lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3,
                "vendredi": 4, "samedi": 5, "dimanche": 6,
            }
            for label, weekday in weekdays.items():
                if label in normalized:
                    target = _next_weekday(now.date(), weekday)
                    break
            hour_match = re.search(
                r"\b(?:a|a)\s*([01]?\d|2[0-3])\s*h(?:\s*([0-5]\d))?\b",
                raw,
                flags=re.I,
            )
            if not hour_match:
                raise AmbiguousIntegrationIntent("Indique une heure, par exemple 15h.")
            hour = int(hour_match.group(1))
            minute = int(hour_match.group(2) or 0)
            tz = resolve_timezone(self.timezone_name)
            start = datetime(target.year, target.month, target.day, hour, minute, tzinfo=tz)
            end = start + timedelta(hours=1)
            title_match = re.search(r"\b(?:intitule|intitule|titre)\s+(.+)$", raw, flags=re.I)
            title = title_match.group(1).strip() if title_match else "Rendez-vous AURA"
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.create_event",
                {
                    "calendar_id": "cal-main",
                    "title": title,
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                    "timezone": self.timezone_name,
                    "attendees": [{"address": "boris@example.invalid"}],
                },
                f"Creer  {title}  le {start.strftime('%d/%m/%Y')} a {start.strftime('%H:%M')}",
            )

        if re.search(r"\b(accepte|accepter|decline|decliner|refuse|tentative)\b", normalized):
            event_id = _extract_event_id(raw)
            if not event_id:
                raise AmbiguousIntegrationIntent("Indique l'identifiant de l'invitation.")
            if "tentative" in normalized:
                response = "tentative"
            elif re.search(r"\b(decline|decliner|refuse)\b", normalized):
                response = "declined"
            else:
                response = "accepted"
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.respond_invitation",
                {
                    "event_id": event_id,
                    "attendee_address": "boris@example.invalid",
                    "response_status": response,
                },
                f"Repondre  {response}  a l'invitation {event_id}",
            )

        if re.search(r"\b(supprime|supprimer|efface|effacer)\b.*\b(evenement|rendez[- ]?vous|rdv)\b", normalized):
            event_id = _extract_event_id(raw)
            if not event_id:
                raise AmbiguousIntegrationIntent("Indique l'identifiant de l'evenement.")
            return ResolvedIntegrationIntent(
                CALENDAR_PROVIDER_ID,
                "calendar.delete_event",
                {"event_id": event_id},
                f"Supprimer l'evenement {event_id}",
            )

        return None


def _build_synthetic_runtime_context_v121_fallback(
    *,
    security_engine: Any,
    receipt_service: Optional[ActionReceiptService] = None,
    receipt_db: Optional[Path] = None,
    timezone_name: str = "Europe/Paris",
) -> IntegrationRuntimeContext:
    if receipt_service is None:
        if receipt_db is None:
            receipt_db = (
                Path(tempfile.gettempdir())
                / f"aura_v0921_runtime_receipts_{os.getpid()}.db"
            )
        receipt_service = ActionReceiptService(
            store=ActionReceiptStore(receipt_db)
        )

    tz = resolve_timezone(timezone_name)
    now = datetime.now(tz)
    tomorrow = now + timedelta(days=1)

    email_message = EmailMessage(
        message_id="msg-001",
        thread_id="thr-001",
        subject="Dossier assurance - pieces complementaires",
        sender=EmailAddress("dupont@example.invalid", "Jean Dupont"),
        to=(EmailAddress("boris@example.invalid", "Boris"),),
        date=now.isoformat(timespec="seconds"),
        body_text="Bonjour, voici les pieces complementaires du dossier assurance.",
        labels=("INBOX", "UNREAD"),
        attachments=(
            EmailAttachment(
                attachment_id="att-001",
                filename="assurance.pdf",
                content_type="application/pdf",
                size_bytes=4096,
            ),
        ),
    )
    email_backend = SyntheticEmailBackend(messages=(email_message,))

    calendar_info = CalendarInfo(
        calendar_id="cal-main",
        name="Agenda AURA Synthetique",
        timezone=timezone_name,
        primary=True,
    )
    event_start = tomorrow.replace(
        hour=15, minute=0, second=0, microsecond=0
    )
    calendar_event = CalendarEvent(
        event_id="evt-001",
        calendar_id="cal-main",
        title="Rendez-vous assurance",
        start=event_start.isoformat(),
        end=(event_start + timedelta(hours=1)).isoformat(),
        timezone=timezone_name,
        description="Evenement synthetique AURA",
        attendees=(
            CalendarAttendee(
                address="boris@example.invalid",
                display_name="Boris",
            ),
        ),
    )
    calendar_backend = SyntheticCalendarBackend(
        calendars=(calendar_info,),
        events=(calendar_event,),
    )

    registry = IntegrationRegistry(
        security_engine=security_engine,
        receipt_service=receipt_service,
    )
    registry.register_provider(EmailProvider(backend=email_backend))
    registry.register_provider(CalendarProvider(backend=calendar_backend))
    contacts_backend = SyntheticContactsBackend()
    contacts_provider = ContactProvider(backend=contacts_backend)
    registry.register_provider(contacts_provider)
    files_backend = SyntheticFilesBackend()
    files_provider = FilesProvider(backend=files_backend)
    registry.register_provider(files_provider)

    return IntegrationRuntimeContext(
        registry=registry,
        receipt_service=receipt_service,
        email_backend=email_backend,
        calendar_backend=calendar_backend,
        timezone_name=timezone_name,
    )


class PersonalIntegrationDispatcher:
    """Canonical runtime boundary shared by conversation and modules."""

    def __init__(self, *, context, resolver=None, confirmation_broker=None):
        self.context = context
        self.resolver = resolver or IntegrationIntentResolver(
            timezone_name=context.timezone_name
        )
        self.confirmation_broker = confirmation_broker or IntegrationConfirmationBroker()
        # AURA_W131_3C_PC_PROVIDER_LAZY_REGISTRATION_BEGIN
        try:
            from runtime.aura_pc_control_registry_binding_v131 import (
                register_pc_control_provider_v131,
            )
            register_pc_control_provider_v131(self.context.registry)
        except Exception:
            pass
        # AURA_W131_3C_PC_PROVIDER_LAZY_REGISTRATION_END
        self._last_request = None

    def build_integration_request(self, intent):
        return IntegrationRequest.create(
            provider_id=intent.provider_id,
            capability_id=intent.capability_id,
            params=dict(intent.params),
            origin="runtime.personal_integrations",
        )

    def render_action_receipt(self, receipt_id):
        if not receipt_id:
            return ""
        try:
            receipt = self.context.receipt_service.get_receipt(receipt_id)
        except Exception:
            return ""
        if receipt is None:
            return ""
        return f"Recu d'action : {receipt.receipt_id} - statut {receipt.status}"

    def _render_result(self, result: IntegrationResult, *, summary: str):
        output = result.output or {}
        capability = result.capability_id

        if result.status == "waiting_confirmation":
            return (
                f"{summary}\nCette action necessite ta confirmation. "
                "Reponds  confirmer  pour l'executer ou  annuler ."
            )
        if result.status in {"denied", "failed"}:
            return f"Action non executee : {summary}. Statut : {result.status}."

        if capability == "email.search":
            messages = output.get("messages") or []
            if not messages:
                return "Aucun email synthetique correspondant."
            return "Emails synthetiques trouves :\n" + "\n".join(
                f"- {m.get('message_id')} - {m.get('subject')} - "
                f"{(m.get('sender') or {}).get('address')}"
                for m in messages[:5]
            )
        if capability == "email.read":
            m = output.get("message") or {}
            return (
                f"Mail {m.get('message_id')} - {m.get('subject')}\n"
                f"De : {(m.get('sender') or {}).get('address')}\n"
                f"{m.get('body_text') or ''}"
            )
        if capability == "email.list_attachments":
            items = output.get("attachments") or []
            return "Pieces jointes :\n" + "\n".join(
                f"- {a.get('filename')} ({a.get('content_type')})"
                for a in items
            )
        if capability == "email.create_draft":
            d = output.get("draft") or {}
            return f"Brouillon synthetique cree : {d.get('draft_id')}"
        if capability.startswith("email."):
            return "Action Email synthetique executee."

        if capability in {"files.list", "files.search"}:

            items = output.get("items") or []

            if not items:

                return "Aucun fichier synthetique correspondant."

            return "Fichiers synthetiques :\n" + "\n".join(

                f"- {item.get('path')} ({item.get('size')} octets)"

                for item in items[:20]

            )

        if capability == "files.read":

            content = output.get("content") or {}

            return (

                f"Fichier {content.get('path')} :\n"

                f"{content.get('text') or ''}"

            )

        if capability in {"files.create", "files.update", "files.move", "files.delete"}:

            operation = output.get("operation") or {}

            destination = operation.get("destination") or ""

            suffix = f" -> {destination}" if destination else ""

            return (

                f"Operation fichier synthetique {operation.get('operation')} : "

                f"{operation.get('path')}{suffix}"

            )

        if capability.startswith("files."):

            return "Action Files synthetique executee."


        if capability == "contacts.search":

            items = output.get("contacts") or []

            if not items:

                return "Aucun contact synthetique correspondant."

            return "Contacts synthetiques trouves:\n" + "\n".join(

                f"- {c.get('contact_id')} - {c.get('display_name')} - "

                f"{', '.join(c.get('emails') or [])}"

                for c in items[:10]

            )

        if capability == "contacts.read":

            c = output.get("contact") or {}

            return (

                f"Contact {c.get('contact_id')} - {c.get('display_name')}\n"

                f"Emails : {', '.join(c.get('emails') or [])}\n"

                f"Telephones : {', '.join(c.get('phones') or [])}"

            )

        if capability == "contacts.create":

            c = output.get("contact") or {}

            return f"Contact synthetique cree : {c.get('contact_id')} - {c.get('display_name')}"

        if capability == "contacts.update":

            c = output.get("contact") or {}

            return f"Contact synthetique modifie : {c.get('contact_id')} - {c.get('display_name')}"

        if capability == "contacts.delete":

            return "Contact synthetique supprime."

        if capability.startswith("contacts."):

            return "Action Contacts synthetique executee."


        if capability == "calendar.list":
            items = output.get("calendars") or []
            return "Calendriers synthetiques :\n" + "\n".join(
                f"- {c.get('calendar_id')} - {c.get('name')}"
                for c in items
            )
        if capability == "calendar.search_events":
            items = output.get("events") or []
            if not items:
                return "Aucun rendez-vous synthetique."
            return "Rendez-vous synthetiques :\n" + "\n".join(
                f"- {e.get('event_id')} - {e.get('title')} - {e.get('start')}"
                for e in items[:10]
            )
        if capability == "calendar.read_event":
            e = output.get("event") or {}
            return (
                f"Evenement {e.get('event_id')} - {e.get('title')}\n"
                f"Debut : {e.get('start')}\nFin : {e.get('end')}"
            )
        if capability == "calendar.free_busy":
            fb = output.get("free_busy") or {}
            busy = fb.get("busy") or []
            return (
                "Tu n'es pas entierement libre sur cette plage."
                if busy
                else "Tu es libre sur cette plage dans l'agenda synthetique."
            )
        if capability.startswith("calendar."):
            return "Action Calendar synthetique executee."

        return f"Action synthetique executee : {summary}."

    def _reply_from_result(self, result, *, summary):
        if result.status == "waiting_confirmation":
            self.confirmation_broker.set_pending(
                request=self._last_request,
                summary=summary,
                receipt_id=result.receipt_id,
                capability_id=result.capability_id,
            )
        text = self._render_result(result, summary=summary)
        receipt = self.render_action_receipt(result.receipt_id)
        if receipt:
            text += "\n" + receipt
        return IntegrationRuntimeReply(
            handled=True,
            text=text,
            status=result.status,
            capability_id=result.capability_id,
            receipt_id=result.receipt_id,
            pending_confirmation=result.status == "waiting_confirmation",
            payload=dict(result.output) if isinstance(result.output, Mapping) else None,
        )

    def dispatch_capability(self, *, provider_id, capability_id, params, summary):
        if self.confirmation_broker.pending is not None:
            return self.request_confirmation(self.confirmation_broker.pending)
        request = IntegrationRequest.create(
            provider_id=provider_id,
            capability_id=capability_id,
            params=dict(params),
            origin="runtime.personal_integration_module",
        )
        self._last_request = request
        result = self.context.registry.execute_integration(
            request,
            user_confirmed=False,
        )
        return self._reply_from_result(result, summary=summary)

    def request_confirmation(self, pending):
        receipt = self.render_action_receipt(pending.receipt_id)
        return IntegrationRuntimeReply(
            handled=True,
            text=(
                f"{pending.summary}\nCette action attend ta confirmation. "
                "Reponds  confirmer  ou  annuler ."
                + (("\n" + receipt) if receipt else "")
            ),
            status="waiting_confirmation",
            capability_id=pending.capability_id,
            receipt_id=pending.receipt_id,
            pending_confirmation=True,
        )

    def resume_confirmation(self):
        pending = self.confirmation_broker.pending
        if pending is None:
            return IntegrationRuntimeReply(
                handled=True,
                text="Aucune action Email ou Calendar n'attend de confirmation.",
                status="no_pending_confirmation",
            )
        self._last_request = pending.request
        result = self.context.registry.execute_integration(
            pending.request,
            user_confirmed=True,
        )
        self.confirmation_broker.clear()
        return self._reply_from_result(result, summary=pending.summary)

    def cancel_confirmation(self):
        pending = self.confirmation_broker.clear()
        if pending is None:
            return IntegrationRuntimeReply(
                handled=True,
                text="Aucune action Email ou Calendar a annuler.",
                status="no_pending_confirmation",
            )
        # The provider is intentionally never called on cancellation.
        # Receipt terminalization is delegated to ActionReceiptService when
        # the installed service exposes a compatible cancellation API.
        status = "cancelled"
        for method_name in ("cancel_receipt", "cancel"):
            method = getattr(self.context.receipt_service, method_name, None)
            if callable(method):
                try:
                    result = method(pending.receipt_id)
                    status = getattr(result, "status", status)
                    break
                except Exception:
                    pass
        receipt = self.render_action_receipt(pending.receipt_id)
        text = (
            f"Action annulee : {pending.summary}. "
            "Le provider n'a pas ete execute."
        )
        if receipt:
            text += "\n" + receipt
        return IntegrationRuntimeReply(
            handled=True,
            text=text,
            status=status,
            capability_id=pending.capability_id,
            receipt_id=pending.receipt_id,
        )


    # AURA ROADMAP W131-3C — TYPED CONVERSATIONAL PC ROUTING
    @staticmethod
    def _w131_pc_reply(
        *,
        text: str,
        status: str,
        capability_id: str | None = None,
        receipt_id: str | None = None,
        payload=None,
        clarification_required: bool = False,
    ):
        return IntegrationRuntimeReply(
            handled=True,
            text=text,
            status=status,
            capability_id=capability_id,
            receipt_id=receipt_id,
            pending_confirmation=False,
            clarification_required=clarification_required,
            payload=payload,
        )

    def _w131_pc_registry(self):
        try:
            from runtime.aura_pc_control_registry_binding_v131 import (
                register_pc_control_provider_v131,
            )
            register_pc_control_provider_v131(self.context.registry)
        except Exception:
            pass
        return self.context.registry

    @staticmethod
    def _w131_extract_window_query(normalized: str, action: str) -> str:
        patterns = {
            "pc.focus_window": (
                r"\b(?:mets?|mettre|bascule|focalise|focus)\s+"
                r"(?:la\s+)?(?:fenetre\s+)?(.+?)\s+"
                r"(?:au|en)\s+premier\s+plan\b",
                r"\b(?:mets?|mettre)\s+(.+?)\s+(?:au|en)\s+premier\s+plan\b",
            ),
            "pc.minimize_window": (
                r"\b(?:minimise|minimiser|reduis|reduire)\s+"
                r"(?:la\s+)?(?:fenetre\s+)?(.+)$",
            ),
            "pc.maximize_window": (
                r"\b(?:maximise|maximiser|agrandis|agrandir)\s+"
                r"(?:la\s+)?(?:fenetre\s+)?(.+)$",
            ),
        }
        for pattern in patterns.get(action, ()):
            match = re.search(pattern, normalized)
            if match:
                query = str(match.group(1) or "").strip(" .,:;!?-")
                query = re.sub(
                    r"\b(?:s'il te plait|stp|svp|maintenant)\b",
                    " ",
                    query,
                )
                return re.sub(r"\s+", " ", query).strip()
        return ""

    def _w131_pc_execute_result(self, capability_id: str, params: Mapping[str, Any]):
        from integrations import IntegrationRequest
        request = IntegrationRequest.create(
            provider_id="pc-control.windows",
            capability_id=capability_id,
            params=dict(params),
            origin="conversation.pc-control.w131",
        )
        # AURA ROADMAP W131-3C R3 R1 — CURRENT PC REQUEST TRUTH
        # Core/Presenter consume dispatcher._last_request. Without this, a PC
        # reply can inherit a stale Mail/Google request from a previous turn.
        self._last_request = request
        return self._w131_pc_registry().execute_integration(request)

    def _w131_pc_window_candidates(self):
        result = self._w131_pc_execute_result("pc.discover_windows", {})
        if result.status != "succeeded" or not result.ok:
            return result, []
        output = result.output if isinstance(result.output, Mapping) else {}
        pc_result = output.get("pc_result") if isinstance(output, Mapping) else {}
        data = pc_result.get("data") if isinstance(pc_result, Mapping) else []
        return result, [row for row in (data or []) if isinstance(row, Mapping)]

    def _w131_pc_match_window(self, query: str):
        discovery, rows = self._w131_pc_window_candidates()
        if discovery.status != "succeeded":
            return discovery, None, "discovery_failed"

        needle = _normalize(query)
        matches = [
            row for row in rows
            if needle and needle in _normalize(str(row.get("title") or ""))
        ]
        if len(matches) == 1:
            return discovery, matches[0], None
        if not matches:
            titles = [str(row.get("title") or "") for row in rows[:8]]
            return discovery, None, "Aucune fenetre ne correspond a " + repr(query) + (
                ". Fenetres visibles : " + " | ".join(titles) if titles else "."
            )
        titles = [str(row.get("title") or "") for row in matches[:8]]
        return discovery, None, (
            "Plusieurs fenetres correspondent. Precise le titre : "
            + " | ".join(titles)
        )

    def _dispatch_w131_pc_text(self, text: str):
        raw = str(text or "").strip()
        normalized = _normalize(raw)
        if not normalized:
            return None

        # AURA W132-R8 - explicit rollback of the last reversible Windows action.
        if (
            re.search(
                r"\b(?:annule|annuler|retablis|retablir|restaure|restaurer)\b",
                normalized,
            )
            and re.search(r"\b(?:windows|fenetre)\b", normalized)
        ):
            recovery = getattr(self, "_w132_last_pc_recovery", None)
            if not isinstance(recovery, Mapping):
                return self._w131_pc_reply(
                    text="Aucune action Windows reversible n'est disponible a restaurer.",
                    status="no_recovery_available",
                    capability_id="pc.restore_window_state",
                )
            result = self._w131_pc_execute_result(
                "pc.restore_window_state",
                dict(recovery),
            )
            if result.status == "succeeded":
                self._w132_last_pc_recovery = None
            return self._w131_pc_reply(
                text=(
                    "La derniere action Windows a ete restauree."
                    if result.status == "succeeded"
                    else "La restauration de la derniere action Windows a echoue."
                ),
                status=result.status,
                capability_id="pc.restore_window_state",
                receipt_id=result.receipt_id,
                payload=result.output,
            )

        if re.search(
            r"\b(?:ferme|fermer|tue|tuer|termine|terminer|kill)\b.*"
            r"\b(?:fenetre|processus|programme|application)\b",
            normalized,
        ):
            return self._w131_pc_reply(
                text=(
                    "Cette action PC destructive n'est pas encore activee dans W131. "
                    "CLOSE_WINDOW et TERMINATE_PROCESS restent bloques."
                ),
                status="denied",
                capability_id="pc.destructive_unbound",
            )

        if (
            re.search(
                r"\b(?:liste|lister|affiche|afficher|montre|montrer|voir)\b.*"
                r"\bfenetres?\b",
                normalized,
            )
            or normalized in {"fenetres", "mes fenetres", "fenetres windows"}
        ):
            result = self._w131_pc_execute_result("pc.discover_windows", {})
            if result.status != "succeeded":
                return self._w131_pc_reply(
                    text="Impossible de lire les fenetres Windows via le provider PC-control.",
                    status=result.status,
                    capability_id="pc.discover_windows",
                    receipt_id=result.receipt_id,
                    payload=result.output,
                )
            output = result.output if isinstance(result.output, Mapping) else {}
            pc_result = output.get("pc_result") if isinstance(output, Mapping) else {}
            rows = pc_result.get("data") if isinstance(pc_result, Mapping) else []
            rows = [row for row in (rows or []) if isinstance(row, Mapping)]
            titles = [str(row.get("title") or "") for row in rows[:20]]
            return self._w131_pc_reply(
                text=(
                    f"J'ai detecte {len(rows)} fenetre(s) Windows visible(s)."
                    + ("\n" + "\n".join(f"- {title}" for title in titles) if titles else "")
                ),
                status="succeeded",
                capability_id="pc.discover_windows",
                receipt_id=result.receipt_id,
                payload=result.output,
            )

        if re.search(
            r"\b(?:liste|lister|affiche|afficher|montre|montrer|voir)\b.*"
            r"\bprocessus\b",
            normalized,
        ):
            result = self._w131_pc_execute_result("pc.discover_processes", {})
            if result.status != "succeeded":
                return self._w131_pc_reply(
                    text="Impossible de lire les processus Windows via le provider PC-control.",
                    status=result.status,
                    capability_id="pc.discover_processes",
                    receipt_id=result.receipt_id,
                    payload=result.output,
                )
            output = result.output if isinstance(result.output, Mapping) else {}
            pc_result = output.get("pc_result") if isinstance(output, Mapping) else {}
            rows = pc_result.get("data") if isinstance(pc_result, Mapping) else []
            rows = [row for row in (rows or []) if isinstance(row, Mapping)]
            names = [
                f"{row.get('image_name')} (PID {row.get('pid')})"
                for row in rows[:20]
            ]
            return self._w131_pc_reply(
                text=(
                    f"J'ai detecte {len(rows)} processus Windows."
                    + ("\n" + "\n".join(f"- {name}" for name in names) if names else "")
                ),
                status="succeeded",
                capability_id="pc.discover_processes",
                receipt_id=result.receipt_id,
                payload=result.output,
            )

        if (
            re.search(
                r"\b(?:quelle|quel|montre|affiche)\b.*"
                r"\b(?:fenetre|application)\b.*\b(?:active|premier plan)\b",
                normalized,
            )
            or normalized in {
                "fenetre active",
                "application active",
                "fenetre au premier plan",
            }
        ):
            result = self._w131_pc_execute_result("pc.get_foreground_window", {})
            if result.status != "succeeded":
                return self._w131_pc_reply(
                    text="Impossible de lire la fenetre active.",
                    status=result.status,
                    capability_id="pc.get_foreground_window",
                    receipt_id=result.receipt_id,
                    payload=result.output,
                )
            output = result.output if isinstance(result.output, Mapping) else {}
            pc_result = output.get("pc_result") if isinstance(output, Mapping) else {}
            row = pc_result.get("data") if isinstance(pc_result, Mapping) else None
            title = str((row or {}).get("title") or "") if isinstance(row, Mapping) else ""
            return self._w131_pc_reply(
                text=(
                    f"La fenetre au premier plan est : {title}."
                    if title else
                    "Aucune fenetre de premier plan exploitable n'a ete trouvee."
                ),
                status="succeeded",
                capability_id="pc.get_foreground_window",
                receipt_id=result.receipt_id,
                payload=result.output,
            )

        action = None
        if re.search(r"\b(?:minimise|minimiser|reduis|reduire)\b", normalized):
            action = "pc.minimize_window"
        elif re.search(r"\b(?:maximise|maximiser|agrandis|agrandir)\b", normalized):
            action = "pc.maximize_window"
        elif (
            re.search(r"\b(?:premier plan|focus|focalise|bascule)\b", normalized)
            and re.search(r"\b(?:fenetre|mets?|mettre|application)\b", normalized)
        ):
            action = "pc.focus_window"

        if action is None:
            return None

        query = self._w131_extract_window_query(normalized, action)
        if not query:
            return self._w131_pc_reply(
                text="Precise le titre de la fenetre Windows cible.",
                status="clarification_required",
                capability_id=action,
                clarification_required=True,
            )

        discovery, row, error = self._w131_pc_match_window(query)
        if row is None:
            if error == "discovery_failed":
                return self._w131_pc_reply(
                    text="Impossible de decouvrir les fenetres Windows avant l'action.",
                    status=discovery.status,
                    capability_id=action,
                    receipt_id=discovery.receipt_id,
                    payload=discovery.output,
                )
            return self._w131_pc_reply(
                text=str(error),
                status="clarification_required",
                capability_id=action,
                receipt_id=discovery.receipt_id,
                clarification_required=True,
            )

        result = self._w131_pc_execute_result(
            action,
            {
                "hwnd": int(row["hwnd"]),
                "title": str(row["title"]),
            },
        )
        if result.status == "succeeded" and isinstance(result.output, Mapping):
            _pc_output = result.output.get("pc_result")
            _pc_data = _pc_output.get("data") if isinstance(_pc_output, Mapping) else None
            _recovery = _pc_data.get("recovery") if isinstance(_pc_data, Mapping) else None
            if isinstance(_recovery, Mapping) and _recovery.get("available") is True:
                self._w132_last_pc_recovery = dict(_recovery)
        verb = {
            "pc.focus_window": "mise au premier plan",
            "pc.minimize_window": "minimisation",
            "pc.maximize_window": "maximisation",
        }[action]
        return self._w131_pc_reply(
            text=(
                f"Action Windows effectuee : {verb} de {row['title']}."
                if result.status == "succeeded"
                else f"L'action Windows {verb} a echoue."
            ),
            status=result.status,
            capability_id=action,
            receipt_id=result.receipt_id,
            payload=result.output,
        )
    def dispatch_integration(self, text: str):
        # AURA_W131_3C_PC_TEXT_ROUTE_BEGIN
        _aura_pc_reply = self._dispatch_w131_pc_text(text)
        if _aura_pc_reply is not None:
            return _aura_pc_reply
        # AURA_W131_3C_PC_TEXT_ROUTE_END
        normalized = _normalize(text)
        if normalized in CONFIRM_WORDS:
            return self.resume_confirmation()
        if normalized in CANCEL_WORDS:
            return self.cancel_confirmation()
        if self.confirmation_broker.pending is not None:
            return self.request_confirmation(self.confirmation_broker.pending)

        try:
            intent = self.resolver.resolve_integration_intent(text)
        except AmbiguousIntegrationIntent as exc:
            return IntegrationRuntimeReply(
                handled=True,
                text=str(exc),
                status="clarification_required",
                clarification_required=True,
            )

        if intent is None:
            return IntegrationRuntimeReply(handled=False)

        request = self.build_integration_request(intent)
        self._last_request = request
        result = self.context.registry.execute_integration(
            request,
            user_confirmed=False,
        )
        return self._reply_from_result(result, summary=intent.summary)

    def handle_text(self, text: str):
        # AURA_V130_W130_D_R1_LIVE_WORKSPACE_CONVERSATION_BRIDGE
        if getattr(getattr(self, "confirmation_broker", None), "pending", None) is not None:
            return self.dispatch_integration(text)
        try:
            from runtime.workspace_live_conversation_bridge_v130 import dispatch_workspace_conversation_intent_v130
            _aura_workspace_reply = dispatch_workspace_conversation_intent_v130(text)
        except Exception:
            _aura_workspace_reply = None
        if _aura_workspace_reply is not None and bool(getattr(_aura_workspace_reply, "handled", False)):
            return IntegrationRuntimeReply(
                handled=True,
                text=str(getattr(_aura_workspace_reply, "text", "") or ""),
                status=str(getattr(_aura_workspace_reply, "status", "succeeded") or "succeeded"),
                capability_id=getattr(_aura_workspace_reply, "capability_id", None),
                clarification_required=bool(getattr(_aura_workspace_reply, "clarification_required", False)),
                payload=getattr(_aura_workspace_reply, "payload", None),
            )
        return self.dispatch_integration(text)



def build_google_live_runtime_context_v121(
    *,
    security_engine,
    receipt_service=None,
    receipt_db=None,
    timezone_name="Europe/Paris",
    service=None,
):
    """Default v1.2.1 personal integration wiring using the connected Google account."""
    from runtime.google_personal_integrations_bridge_v121 import (
        build_google_live_runtime_context_v121 as _build_google_live,
    )
    return _build_google_live(
        security_engine=security_engine,
        receipt_service=receipt_service,
        receipt_db=receipt_db,
        timezone_name=timezone_name,
        service=service,
    )


def build_synthetic_runtime_context(
    *,
    security_engine,
    receipt_service=None,
    receipt_db=None,
    timezone_name="Europe/Paris",
):
    """Compatibility entrypoint. v1.2.1 routes production wiring to Google Live."""
    return build_google_live_runtime_context_v121(
        security_engine=security_engine,
        receipt_service=receipt_service,
        receipt_db=receipt_db,
        timezone_name=timezone_name,
    )


__all__ = [
    "EMAIL_PROVIDER_ID",
    "CALENDAR_PROVIDER_ID",
    "WRITE_CAPABILITIES",
    "resolve_timezone",
    "RuntimeWiringError",
    "AmbiguousIntegrationIntent",
    "ResolvedIntegrationIntent",
    "IntegrationRuntimeReply",
    "PendingIntegrationAction",
    "IntegrationRuntimeContext",
    "IntegrationConfirmationBroker",
    "IntegrationIntentResolver",
    "build_google_live_runtime_context_v121",
    "build_synthetic_runtime_context",
    "PersonalIntegrationDispatcher",
]

# AURA V0.9.5 D2 R1 NOTIFICATIONS RUNTIME BRIDGE
_AURA_V095_NOTIFICATIONS_PROVIDER_SINGLETON = None


def get_notifications_provider_v095():
    global _AURA_V095_NOTIFICATIONS_PROVIDER_SINGLETON

    if _AURA_V095_NOTIFICATIONS_PROVIDER_SINGLETON is None:
        from integrations.notifications.provider import NotificationsProvider

        _AURA_V095_NOTIFICATIONS_PROVIDER_SINGLETON = NotificationsProvider()

    return _AURA_V095_NOTIFICATIONS_PROVIDER_SINGLETON


def notifications_capability_context_v095():
    provider = get_notifications_provider_v095()

    return {
        "provider": provider.provider_id,
        "mode": provider.mode,
        "capabilities": list(provider.capabilities),
        "legacy_bridge": {
            "history_ui": "P0.8.1 Activity Center",
            "presentation": "P0.8.3 AuraProactiveNotifications",
            "reuse_existing_activity_center": True,
            "duplicate_notification_surface": False,
        },
        "external_delivery": False,
        "network_side_effects": False,
        "windows_notifications": False,
        "auto_action": False,
    }

# AURA_V096_BROWSER_RUNTIME_WIRING_BEGIN
def register_browser_provider_v096(
    registry,
    *,
    search_adapter,
    read_adapter,
):
    from runtime.browser_wiring_v096 import BrowserIntegrationProviderAdapter
    provider = BrowserIntegrationProviderAdapter(
        search_adapter=search_adapter,
        read_adapter=read_adapter,
    )
    registry.register_provider(provider)
    return provider


def build_browser_wiring_adapter_v096(
    *,
    provider,
    authorize_read,
    request_confirmation,
    create_receipt,
):
    from runtime.browser_wiring_v096 import BrowserWiringAdapter
    return BrowserWiringAdapter(
        provider=provider,
        authorize_read=authorize_read,
        request_confirmation=request_confirmation,
        create_receipt=create_receipt,
    )
# AURA_V096_BROWSER_RUNTIME_WIRING_END

# AURA ROADMAP W131-3D1 — ROBUST WINDOW TARGET RESOLUTION
def _aura_w131_3d1_window_key(value):
    import re as _re
    import unicodedata as _unicodedata

    text = str(value or "").strip().casefold()
    text = _unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not _unicodedata.combining(ch))
    text = text.translate({
        ord("‐"): " ", ord("‑"): " ", ord("‒"): " ",
        ord("–"): " ", ord("—"): " ", ord("−"): " ",
        ord("-"): " ",
    })
    text = _re.sub(r"[^a-z0-9]+", " ", text)
    return _re.sub(r"\s+", " ", text).strip()


def _aura_w131_3d1_match_window(self, query: str):
    discovery, rows = self._w131_pc_window_candidates()
    if discovery.status != "succeeded":
        return discovery, None, "discovery_failed"

    query_key = _aura_w131_3d1_window_key(query)
    if not query_key:
        return discovery, None, "Precise le titre de la fenetre Windows cible."

    q_tokens = tuple(tok for tok in query_key.split() if tok)
    scored = []
    for row in rows:
        title = str(row.get("title") or "").strip()
        title_key = _aura_w131_3d1_window_key(title)
        if not title_key:
            continue

        score = 0
        if title_key == query_key:
            score = 1000
        elif query_key in title_key:
            score = 900 + min(len(query_key), 80)
        elif title_key in query_key:
            score = 850 + min(len(title_key), 80)
        else:
            title_tokens = set(title_key.split())
            qset = set(q_tokens)
            if qset and qset.issubset(title_tokens):
                score = 700 + len(qset) * 10
            else:
                overlap = len(qset.intersection(title_tokens))
                if len(qset) >= 2 and overlap == len(qset):
                    score = 650 + overlap * 10

        if score:
            scored.append((score, len(title_key), title.casefold(), row))

    if not scored:
        titles = [str(row.get("title") or "") for row in rows[:12]]
        return discovery, None, (
            "Aucune fenetre ne correspond a "
            + repr(query)
            + (
                ". Fenetres visibles : " + " | ".join(titles)
                if titles else
                "."
            )
        )

    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    best_score = scored[0][0]
    best = [item for item in scored if item[0] == best_score]

    if len(best) == 1:
        return discovery, best[0][3], None

    # If multiple windows tie but only one is foreground, prefer it.
    foreground = [item for item in best if bool(item[3].get("foreground"))]
    if len(foreground) == 1:
        return discovery, foreground[0][3], None

    titles = [str(item[3].get("title") or "") for item in best[:8]]
    return discovery, None, (
        "Plusieurs fenetres correspondent. Precise le titre : "
        + " | ".join(titles)
    )


PersonalIntegrationDispatcher._w131_pc_match_window = _aura_w131_3d1_match_window

# AURA_O140_R2_OBSIDIAN_CONVERSATION_ROUTE
_AURA_O140_R2_ORIGINAL_DISPATCH_INTEGRATION = PersonalIntegrationDispatcher.dispatch_integration


def _aura_o140_r2_execute(self, capability_id: str, params: Mapping[str, Any]):
    from integrations import IntegrationRequest
    from runtime.aura_obsidian_registry_binding_v140 import register_obsidian_creative_provider_v140

    register_obsidian_creative_provider_v140(self.context.registry)
    request = IntegrationRequest.create(
        provider_id="obsidian.creative",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.obsidian.o140",
    )
    self._last_request = request
    return self.context.registry.execute_integration(request, user_confirmed=False)


def _aura_o140_r2_reply(result, text_ok: str, text_fail: str):
    return IntegrationRuntimeReply(
        handled=True,
        text=text_ok if result.status == "succeeded" else text_fail,
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=result.output,
    )


def _aura_o140_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_O140_R2_ORIGINAL_DISPATCH_INTEGRATION(self, text)

    obsidian_explicit = bool(re.search(r"\b(?:obsidian|vault)\b", normalized))
    if not obsidian_explicit:
        return _AURA_O140_R2_ORIGINAL_DISPATCH_INTEGRATION(self, text)

    if re.search(r"\b(?:liste|lister|montre|affiche|quels|quelles)\b.*\b(?:vault|vaults)\b", normalized):
        result = _aura_o140_r2_execute(self, "obsidian.discover_vaults", {})
        return _aura_o140_r2_reply(result, "J'ai trouve les vaults Obsidian disponibles.", "Je n'ai pas pu inventorier les vaults Obsidian.")

    if re.search(r"\b(?:resume|resumer|structure|organise|organisation|projet)\b", normalized):
        result = _aura_o140_r2_execute(self, "obsidian.creative_snapshot", {})
        return _aura_o140_r2_reply(result, "J'ai analyse la structure de ton projet Obsidian.", "Je n'ai pas pu analyser la structure du projet Obsidian.")

    m = re.search(r"\b(?:cherche|chercher|recherche|rechercher|trouve|trouver)\b\s+(.+?)(?:\s+\b(?:dans|sur)\b\s+(?:mon\s+)?(?:obsidian|vault).*)?$", normalized)
    if m:
        query = str(m.group(1) or "").strip()
        query = re.sub(r"\b(?:dans|sur)\s+(?:mon\s+)?(?:obsidian|vault)\b.*$", "", query).strip()
        if not query:
            return IntegrationRuntimeReply(
                handled=True,
                text="Que veux-tu chercher dans Obsidian ?",
                status="clarification_required",
                capability_id="obsidian.search_context",
                clarification_required=True,
            )
        result = _aura_o140_r2_execute(self, "obsidian.search_context", {"query": query, "limit": 12})
        return _aura_o140_r2_reply(result, "J'ai cherche " + repr(query) + " dans ton projet Obsidian.", "La recherche Obsidian a echoue.")

    return IntegrationRuntimeReply(
        handled=True,
        text="Je peux lister les vaults, analyser la structure ou chercher un element dans Obsidian.",
        status="clarification_required",
        capability_id="obsidian.search_context",
        clarification_required=True,
    )


PersonalIntegrationDispatcher.dispatch_integration = _aura_o140_r2_dispatch

# AURA_O140_R3_DEDICATED_READONLY_REGISTRY_AND_CONTEXT_COMMANDS
_AURA_O140_R3_PREVIOUS_OBSIDIAN_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


class _AuraO140R3ReadOnlySecurity:
    _ALLOWED = frozenset({
        "obsidian.discover_vaults",
        "obsidian.creative_snapshot",
        "obsidian.search_context",
        "obsidian.read_note",
    })

    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"


def _aura_o140_r2_execute(self, capability_id: str, params: Mapping[str, Any]):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_obsidian_registry_binding_v140 import register_obsidian_creative_provider_v140

    registry = getattr(self, "_aura_o140_r3_obsidian_registry", None)
    if registry is None:
        # Preserve an explicitly bound/default vault from the outer runtime
        # (used by deterministic tests and any future explicit vault binding),
        # while still executing through the dedicated read-only registry.
        default_vault = None
        try:
            outer_provider = self.context.registry.get_provider("obsidian.creative")
        except Exception:
            outer_provider = None
        if outer_provider is not None:
            default_vault = getattr(outer_provider, "default_vault", None)

        registry = IntegrationRegistry(
            security_engine=_AuraO140R3ReadOnlySecurity(),
            receipt_service=self.context.receipt_service,
        )
        register_obsidian_creative_provider_v140(
            registry,
            default_vault=default_vault,
        )
        self._aura_o140_r3_obsidian_registry = registry

    request = IntegrationRequest.create(
        provider_id="obsidian.creative",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.obsidian.o140",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=False)


def _aura_o140_r3_category_reply(self, category: str):
    result = _aura_o140_r2_execute(self, "obsidian.creative_snapshot", {})
    if result.status != "succeeded":
        return _aura_o140_r2_reply(
            result,
            "J'ai analyse la categorie Obsidian.",
            "Je n'ai pas pu lire cette categorie Obsidian.",
        )

    output = result.output if isinstance(result.output, Mapping) else {}
    ob = output.get("obsidian_result") if isinstance(output, Mapping) else {}
    ob = ob if isinstance(ob, Mapping) else {}
    groups = ob.get("groups") if isinstance(ob.get("groups"), Mapping) else {}
    rows = groups.get(category) if isinstance(groups, Mapping) else []
    rows = [dict(x) for x in (rows or []) if isinstance(x, Mapping)]

    payload = dict(output)
    payload["obsidian_result"] = {
        "kind": "category",
        "category": category,
        "count": len(rows),
        "items": rows,
        "vault": ob.get("vault"),
        "read_only": True,
    }

    label = {
        "chapters": "chapitres",
        "characters": "personnages",
        "scenes": "scenes",
        "continuity": "notes de continuite",
        "world": "notes d'univers",
        "locations": "lieux",
        "notes": "notes",
    }.get(category, category)

    return IntegrationRuntimeReply(
        handled=True,
        text=f"J'ai trouve {len(rows)} {label} dans ton projet Obsidian.",
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=payload,
    )


def _aura_o140_r3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized or not re.search(r"\b(?:obsidian|vault)\b", normalized):
        return _AURA_O140_R3_PREVIOUS_OBSIDIAN_DISPATCH(self, text)

    category_patterns = (
        ("characters", r"\b(?:personnage|personnages|characters?)\b"),
        ("chapters", r"\b(?:chapitre|chapitres|chapters?)\b"),
        ("locations", r"\b(?:lieu|lieux|locations?)\b"),
        ("scenes", r"\b(?:scene|scenes)\b"),
        ("continuity", r"\b(?:continuite|chronologie|timeline)\b"),
        ("world", r"\b(?:univers|world|worldbuilding|lore)\b"),
        ("notes", r"\b(?:notes?)\b"),
    )
    if re.search(r"\b(?:liste|lister|montre|montrer|affiche|afficher|quels|quelles)\b", normalized):
        for category, pattern in category_patterns:
            if re.search(pattern, normalized):
                return _aura_o140_r3_category_reply(self, category)

    if not re.search(r"\b(?:mon\s+projet|projet\s+obsidian|structure)\b", normalized):
        m = re.search(
            r"\b(?:qui\s+est|qui\s+etait|parle\s+moi\s+de|parle-moi\s+de|resume|resumer)\s+(.+?)(?:\s+\b(?:dans|sur)\b\s+(?:mon\s+)?(?:obsidian|vault).*)?$",
            normalized,
        )
        if m:
            query = str(m.group(1) or "").strip()
            query = re.sub(r"\b(?:dans|sur)\s+(?:mon\s+)?(?:obsidian|vault)\b.*$", "", query).strip()
            if query:
                result = _aura_o140_r2_execute(
                    self,
                    "obsidian.search_context",
                    {"query": query, "limit": 12},
                )
                return _aura_o140_r2_reply(
                    result,
                    "J'ai cherche " + repr(query) + " dans ton projet Obsidian.",
                    "La recherche contextuelle Obsidian a echoue.",
                )

    return _AURA_O140_R3_PREVIOUS_OBSIDIAN_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_o140_r3_dispatch

# AURA_O141_R2_LONGFORM_CONVERSATION_ROUTE
_AURA_O141_R2_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


class _AuraO141R2ReadOnlySecurity:
    _ALLOWED = frozenset({
        "longform.manuscript_outline",
        "longform.chapter_context",
        "longform.continuity_audit",
        "longform.revision_brief",
        "longform.context_search_pack",
    })

    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"


def _aura_o141_r2_execute(self, capability_id: str, params: Mapping[str, Any]):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_longform_registry_binding_v141 import register_longform_revision_provider_v141

    registry = getattr(self, "_aura_o141_r2_longform_registry", None)
    if registry is None:
        default_vault = None
        try:
            outer_provider = self.context.registry.get_provider("longform.revision")
        except Exception:
            outer_provider = None
        if outer_provider is not None:
            default_vault = getattr(outer_provider, "default_vault", None)

        registry = IntegrationRegistry(
            security_engine=_AuraO141R2ReadOnlySecurity(),
            receipt_service=self.context.receipt_service,
        )
        register_longform_revision_provider_v141(
            registry,
            default_vault=default_vault,
        )
        self._aura_o141_r2_longform_registry = registry

    request = IntegrationRequest.create(
        provider_id="longform.revision",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.longform.o141",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=False)


def _aura_o141_r2_reply(result, success_text: str, fail_text: str):
    return IntegrationRuntimeReply(
        handled=True,
        text=success_text if result.status == "succeeded" else fail_text,
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=result.output,
    )


def _aura_o141_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_O141_R2_PREVIOUS_DISPATCH(self, text)

    longform_hint = bool(re.search(
        r"\b(?:roman|manuscrit|chapitre|chapitres|continuite|revision|obsidian)\b",
        normalized,
    ))
    if not longform_hint:
        return _AURA_O141_R2_PREVIOUS_DISPATCH(self, text)

    if re.search(
        r"\b(?:plan|outline|structure)\b.*\b(?:manuscrit|roman|chapitres?)\b",
        normalized,
    ):
        result = _aura_o141_r2_execute(self, "longform.manuscript_outline", {})
        return _aura_o141_r2_reply(
            result,
            "J'ai prepare le plan long-form du manuscrit.",
            "Je n'ai pas pu preparer le plan du manuscrit.",
        )

    if re.search(r"\b(?:analyse|audit|verifie|verifier)\b.*\bcontinuite\b", normalized):
        result = _aura_o141_r2_execute(self, "longform.continuity_audit", {})
        return _aura_o141_r2_reply(
            result,
            "J'ai analyse la continuite du manuscrit.",
            "L'audit de continuite a echoue.",
        )

    m = re.search(
        r"\b(?:contexte|prepare|preparer)\b.*\bchapitre\s+([^\n]+)$",
        normalized,
    )
    if m:
        selector = str(m.group(1) or "").strip()
        result = _aura_o141_r2_execute(
            self,
            "longform.chapter_context",
            {"chapter": selector, "radius": 1},
        )
        return _aura_o141_r2_reply(
            result,
            "J'ai prepare le contexte du chapitre " + repr(selector) + ".",
            "Je n'ai pas pu preparer ce contexte de chapitre.",
        )

    m = re.search(
        r"\b(?:brief|revision|reviser|revise|revoir)\b.*\bchapitre\s+([^\n]+)$",
        normalized,
    )
    if m:
        selector = str(m.group(1) or "").strip()
        result = _aura_o141_r2_execute(
            self,
            "longform.revision_brief",
            {"chapter": selector},
        )
        return _aura_o141_r2_reply(
            result,
            "J'ai prepare le brief de revision du chapitre " + repr(selector) + ".",
            "Je n'ai pas pu preparer ce brief de revision.",
        )

    m = re.search(
        r"\b(?:cherche|recherche|trouve|contexte)\b\s+(.+?)\s+\b(?:dans|sur)\b\s+(?:le\s+)?(?:roman|manuscrit|obsidian)\b",
        normalized,
    )
    if m:
        query = str(m.group(1) or "").strip()
        if query:
            result = _aura_o141_r2_execute(
                self,
                "longform.context_search_pack",
                {"query": query, "limit": 8},
            )
            return _aura_o141_r2_reply(
                result,
                "J'ai construit le contexte long-form pour " + repr(query) + ".",
                "La recherche de contexte long-form a echoue.",
            )

    return _AURA_O141_R2_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_o141_r2_dispatch

# AURA_O141_R3_R1_REVISION_INTELLIGENCE_ROUTES
_AURA_O141_R3_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

# R3-R1: extend the already-certified O141-R2 dedicated read-only policy
# with ONLY the three new deterministic read capabilities introduced by R3.
# No mutation capability is added.
_AURA_O141_R3_R1_NEW_READ_CAPABILITIES = frozenset({
    "longform.chapter_transition",
    "longform.chapter_revision_report",
    "longform.manuscript_revision_report",
})
_AuraO141R2ReadOnlySecurity._ALLOWED = frozenset(
    set(_AuraO141R2ReadOnlySecurity._ALLOWED)
    | set(_AURA_O141_R3_R1_NEW_READ_CAPABILITIES)
)



def _aura_o141_r3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_O141_R3_PREVIOUS_DISPATCH(self, text)

    m = re.search(
        r"\b(?:analyse|analyser|rapport|audit)\b.*\bchapitre\s+(\d{1,4})\b",
        normalized,
    )
    if m and not re.search(r"\b(?:transition|entre)\b", normalized):
        selector = m.group(1)
        result = _aura_o141_r2_execute(
            self,
            "longform.chapter_revision_report",
            {"chapter": selector},
        )
        return _aura_o141_r2_reply(
            result,
            "J'ai prepare le rapport de revision du chapitre " + selector + ".",
            "Je n'ai pas pu analyser ce chapitre.",
        )

    m = re.search(
        r"\b(?:analyse|analyser|audit|verifie|verifier)\b.*\btransition\b.*\bchapitre\s+(\d{1,4})\b.*\bchapitre\s+(\d{1,4})\b",
        normalized,
    )
    if m:
        left, right = m.group(1), m.group(2)
        result = _aura_o141_r2_execute(
            self,
            "longform.chapter_transition",
            {"from_chapter": left, "to_chapter": right},
        )
        return _aura_o141_r2_reply(
            result,
            "J'ai analyse la transition entre les chapitres " + left + " et " + right + ".",
            "Je n'ai pas pu analyser cette transition.",
        )

    if re.search(
        r"\b(?:rapport|audit|analyse)\b.*\b(?:revision|global|globale)\b.*\b(?:manuscrit|roman)\b",
        normalized,
    ):
        result = _aura_o141_r2_execute(
            self,
            "longform.manuscript_revision_report",
            {},
        )
        return _aura_o141_r2_reply(
            result,
            "J'ai prepare le rapport global de revision du manuscrit.",
            "Je n'ai pas pu preparer le rapport global du manuscrit.",
        )

    return _AURA_O141_R3_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_o141_r3_dispatch

# AURA_Y150_R2_YOUTUBE_CONVERSATION_ROUTE
_AURA_Y150_R2_PREVIOUS_DISPATCH=PersonalIntegrationDispatcher.dispatch_integration
class _AuraY150R2ReadOnlySecurity:
 _ALLOWED=frozenset({"youtube.channel_snapshot","youtube.opportunity_board","youtube.next_upload_brief","youtube.publishing_cadence","youtube.scorecards"})
 def authorize(self,action,params,*,user_confirmed=False):return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"
def _aura_y150_r2_exec(self,cap):
 from integrations import IntegrationRegistry,IntegrationRequest
 from runtime.aura_youtube_registry_binding_v150 import register_youtube_studio_copilot_provider_v150
 reg=getattr(self,"_aura_y150_r2_registry",None)
 if reg is None:
  reg=IntegrationRegistry(security_engine=_AuraY150R2ReadOnlySecurity(),receipt_service=self.context.receipt_service); register_youtube_studio_copilot_provider_v150(reg); self._aura_y150_r2_registry=reg
 req=IntegrationRequest.create(provider_id="youtube.studio-copilot",capability_id=cap,params={},origin="conversation.youtube.y150"); self._last_request=req
 return reg.execute_integration(req,user_confirmed=False)
def _aura_y150_r2_reply(r,ok,fail):return IntegrationRuntimeReply(handled=True,text=ok if r.status=="succeeded" else fail,status=r.status,capability_id=r.capability_id,receipt_id=r.receipt_id,payload=r.output)
def _aura_y150_r2_dispatch(self,text):
 n=_normalize(str(text or "").strip())
 if not n or not re.search(r"\b(?:youtube|chaine|channel|video|videos)\b",n):return _AURA_Y150_R2_PREVIOUS_DISPATCH(self,text)
 if re.search(r"\b(?:analyse|resume|bilan|stats|statistiques)\b",n):r=_aura_y150_r2_exec(self,"youtube.channel_snapshot");return _aura_y150_r2_reply(r,"J'ai analyse Neural Echo Music.","L'analyse YouTube a echoue.")
 if re.search(r"\b(?:opportunite|opportunites|pousser|ameliorer|optimiser)\b",n):r=_aura_y150_r2_exec(self,"youtube.opportunity_board");return _aura_y150_r2_reply(r,"J'ai classe les opportunites YouTube.","L'analyse des opportunites a echoue.")
 if re.search(r"\b(?:publier|publication|prochaine|prochain)\b",n):r=_aura_y150_r2_exec(self,"youtube.next_upload_brief");return _aura_y150_r2_reply(r,"J'ai prepare la prochaine publication YouTube.","Le brief YouTube a echoue.")
 if re.search(r"\b(?:cadence|rythme|frequence)\b",n):r=_aura_y150_r2_exec(self,"youtube.publishing_cadence");return _aura_y150_r2_reply(r,"J'ai analyse la cadence YouTube.","La cadence YouTube a echoue.")
 if re.search(r"\b(?:meilleure|meilleures|top|classe|classement)\b",n):r=_aura_y150_r2_exec(self,"youtube.scorecards");return _aura_y150_r2_reply(r,"J'ai classe les videos YouTube.","Le classement YouTube a echoue.")
 return _AURA_Y150_R2_PREVIOUS_DISPATCH(self,text)
PersonalIntegrationDispatcher.dispatch_integration=_aura_y150_r2_dispatch

# AURA_Y151_R2_CHANNEL_ANALYTICS_PUBLISHING_ROUTES
_AURA_Y151_R2_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


class _AuraY151R2ReadOnlySecurity:
    _ALLOWED = frozenset({
        "channel.compare_formats",
        "channel.publishing_windows",
        "channel.recommendation_matrix",
        "channel.editorial_mix",
        "publishing.create_workflow_plan",
    })

    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"


def _aura_y151_r2_execute(self, capability_id: str, params: Mapping[str, Any] | None = None):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_channel_analytics_registry_binding_v151 import (
        register_channel_analytics_publishing_provider_v151,
    )

    registry = getattr(self, "_aura_y151_r2_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraY151R2ReadOnlySecurity(),
            receipt_service=self.context.receipt_service,
        )
        register_channel_analytics_publishing_provider_v151(registry)
        self._aura_y151_r2_registry = registry

    request = IntegrationRequest.create(
        provider_id="channel.analytics-publishing",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.youtube.y151",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=False)


def _aura_y151_r2_reply(result, ok_text: str, fail_text: str):
    return IntegrationRuntimeReply(
        handled=True,
        text=ok_text if result.status == "succeeded" else fail_text,
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=result.output,
    )


def _aura_y151_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_Y151_R2_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:compare|comparaison|comparer)\b", normalized)
        and re.search(r"\b(?:short|shorts)\b", normalized)
        and re.search(r"\b(?:video|videos|longue|longues|long)\b", normalized)
    ):
        result = _aura_y151_r2_execute(self, "channel.compare_formats")
        return _aura_y151_r2_reply(
            result,
            "J'ai compare les Shorts et les videos longues de la chaine.",
            "Je n'ai pas pu comparer les formats YouTube.",
        )

    if (
        re.search(r"\b(?:horaire|horaires|heure|heures|jour|jours|fenetre|fenetres)\b", normalized)
        and re.search(r"\b(?:publication|publier|youtube|video|videos)\b", normalized)
    ):
        result = _aura_y151_r2_execute(self, "channel.publishing_windows")
        return _aura_y151_r2_reply(
            result,
            "J'ai analyse les fenetres historiques de publication.",
            "Je n'ai pas pu analyser les fenetres de publication.",
        )

    if (
        re.search(r"\b(?:mix|planning|rythme|cadence)\b", normalized)
        and re.search(r"\b(?:editorial|youtube|publication|publier)\b", normalized)
    ):
        m = re.search(r"\b(\d{1,2})\b", normalized)
        uploads = int(m.group(1)) if m else 3
        result = _aura_y151_r2_execute(
            self,
            "channel.editorial_mix",
            {"uploads_per_week": uploads},
        )
        return _aura_y151_r2_reply(
            result,
            "J'ai prepare un mix editorial YouTube controle.",
            "Je n'ai pas pu preparer le mix editorial.",
        )

    if (
        re.search(r"\b(?:workflow|preparer|prepare|plan)\b", normalized)
        and re.search(r"\b(?:publication|publier|youtube)\b", normalized)
    ):
        title = raw
        for pattern in (
            r"(?i)^.*?\bpour\s+",
            r"(?i)^.*?\bintitulee?\s+",
            r"(?i)^.*?\bappelee?\s+",
        ):
            candidate = re.sub(pattern, "", raw, count=1).strip(" .:-")
            if candidate != raw and candidate:
                title = candidate
                break

        fmt = "short" if re.search(r"\bshorts?\b", normalized) else "video"
        result = _aura_y151_r2_execute(
            self,
            "publishing.create_workflow_plan",
            {
                "title": title,
                "format": fmt,
                "description": "Plan local cree par AURA; aucune publication externe.",
            },
        )
        return _aura_y151_r2_reply(
            result,
            "J'ai prepare le workflow local. Il reste en attente d'approbation et rien n'a ete publie.",
            "Je n'ai pas pu preparer le workflow de publication.",
        )

    if (
        re.search(r"\b(?:format|formats|recommandation|recommandations)\b", normalized)
        and re.search(r"\b(?:youtube|chaine|channel)\b", normalized)
    ):
        result = _aura_y151_r2_execute(self, "channel.recommendation_matrix")
        return _aura_y151_r2_reply(
            result,
            "J'ai prepare la matrice de recommandation des formats.",
            "Je n'ai pas pu preparer la matrice des formats.",
        )

    return _AURA_Y151_R2_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_y151_r2_dispatch

# AURA_Y151_R3_R2_CONTROLLED_WORKFLOW_STATUS_ROUTE
_AuraY151R2ReadOnlySecurity._ALLOWED = frozenset(
    set(_AuraY151R2ReadOnlySecurity._ALLOWED)
    | {"publishing.workflow_status"}
)
_AURA_Y151_R3_R2_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


def _aura_y151_r3_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if (
        normalized
        and re.search(r"\b(?:workflow|brouillon)\b", normalized)
        and re.search(r"\b(?:etat|statut|status|montre|affiche)\b", normalized)
        and re.search(r"\b(?:youtube|publication|publier)\b", normalized)
    ):
        result = _aura_y151_r2_execute(
            self,
            "publishing.workflow_status",
            {},
        )
        return _aura_y151_r2_reply(
            result,
            "J'ai affiche l'etat du dernier workflow de publication.",
            "Je n'ai pas pu lire l'etat du workflow de publication.",
        )
    return _AURA_Y151_R3_R2_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_y151_r3_r2_dispatch

# AURA_L170_R2_CONTROLLED_LEARNING_ROUTES
_AURA_L170_R2_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


class _AuraL170R2Security:
    _ALLOWED = frozenset({
        "learning.propose_candidate",
        "learning.list_candidates",
        "learning.list_conflicts",
        "learning.consolidation_plan",
    })

    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"


def _aura_l170_r2_execute(self, capability_id: str, params: Mapping[str, Any] | None = None):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_controlled_learning_registry_binding_v170 import (
        register_controlled_learning_provider_v170,
    )

    registry = getattr(self, "_aura_l170_r2_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraL170R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_controlled_learning_provider_v170(registry)
        self._aura_l170_r2_registry = registry

    request = IntegrationRequest.create(
        provider_id="controlled.learning",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.memory.l170",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=False)


def _aura_l170_r2_reply(result, ok_text: str, fail_text: str):
    return IntegrationRuntimeReply(
        handled=True,
        text=ok_text if result.status == "succeeded" else fail_text,
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=result.output,
    )


def _aura_l170_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_L170_R2_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:propose|apprends|apprendre|retiens|retenir)\b", normalized)
        and re.search(r"\b(?:souvenir|memoire|controle|candidate|candidat)\b", normalized)
        and raw.count("|") >= 2
    ):
        body = raw.split(":", 1)[1] if ":" in raw else raw
        parts = [part.strip() for part in body.split("|")]
        if len(parts) >= 3 and all(parts[:3]):
            subject, predicate, value = parts[:3]
            result = _aura_l170_r2_execute(
                self,
                "learning.propose_candidate",
                {
                    "subject": subject,
                    "predicate": predicate,
                    "value": value,
                    "source_kind": "conversation",
                    "raw_source_text": raw,
                    "confidence": 1.0,
                    "importance": 0.6,
                },
            )
            return _aura_l170_r2_reply(
                result,
                "J'ai cree un candidat memoire local avec provenance. Il n'est pas encore consolide dans la memoire.",
                "Je n'ai pas pu creer le candidat memoire.",
            )

    if (
        re.search(r"\b(?:montre|affiche|liste|voir)\b", normalized)
        and re.search(r"\b(?:candidat|candidats)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r2_execute(
            self,
            "learning.list_candidates",
            {},
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai affiche les candidats memoire controles.",
            "Je n'ai pas pu lire les candidats memoire.",
        )

    if (
        re.search(r"\b(?:montre|affiche|liste|voir)\b", normalized)
        and re.search(r"\b(?:conflit|conflits|contradiction|contradictions)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r2_execute(
            self,
            "learning.list_conflicts",
            {},
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai affiche les conflits memoire a resoudre.",
            "Je n'ai pas pu lire les conflits memoire.",
        )

    if (
        re.search(r"\b(?:prepare|plan|montre|affiche)\b", normalized)
        and re.search(r"\b(?:consolidation|consolider)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r2_execute(
            self,
            "learning.consolidation_plan",
            {},
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai prepare le plan de consolidation. Aucune memoire live n'a ete modifiee.",
            "Je n'ai pas pu preparer le plan de consolidation.",
        )

    return _AURA_L170_R2_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_l170_r2_dispatch

# AURA_L170_R3_EXPLICIT_APPROVAL_CONTROLLED_CONSOLIDATION
_AuraL170R2Security._ALLOWED = frozenset(
    set(_AuraL170R2Security._ALLOWED)
    | {
        "learning.approve_candidate",
        "learning.resolve_conflict",
        "learning.consolidate_candidate",
        "learning.list_consolidated",
    }
)
_AURA_L170_R3_MUTATIONS = frozenset({
    "learning.approve_candidate",
    "learning.resolve_conflict",
    "learning.consolidate_candidate",
})

def _aura_l170_r3_authorize(self, action, params, *, user_confirmed=False):
    action = str(action or "")
    if action not in self._ALLOWED:
        return "DENY"
    if action in _AURA_L170_R3_MUTATIONS and not user_confirmed:
        return "DENY"
    return "ALLOW"

_AuraL170R2Security.authorize = _aura_l170_r3_authorize

def _aura_l170_r3_execute(self, capability_id: str, params: Mapping[str, Any] | None = None, *, user_confirmed: bool):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_controlled_learning_registry_binding_v170 import (
        register_controlled_learning_provider_v170,
    )
    registry = getattr(self, "_aura_l170_r3_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraL170R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_controlled_learning_provider_v170(registry)
        self._aura_l170_r3_registry = registry
    request = IntegrationRequest.create(
        provider_id="controlled.learning",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.memory.l170.r3",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=user_confirmed)

_AURA_L170_R3_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

def _aura_l170_r3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_L170_R3_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:approuve|approuver|confirme|confirmer|valide|valider)\b", normalized)
        and re.search(r"\b(?:dernier|derniere|candidat|candidate)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r3_execute(
            self, "learning.approve_candidate",
            {"explicit_confirmation": True}, user_confirmed=True
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai approuve explicitement le candidat memoire. Il n'est pas encore consolide.",
            "Je n'ai pas pu approuver le candidat memoire.",
        )

    if (
        re.search(r"\b(?:garde|conserve|keep)\b", normalized)
        and re.search(r"\b(?:conflit|contradiction)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r3_execute(
            self, "learning.resolve_conflict",
            {"keep_candidate": True, "explicit_confirmation": True},
            user_confirmed=True
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai garde le candidat en conflit. Il redevient un candidat a approuver.",
            "Je n'ai pas pu resoudre le conflit memoire.",
        )

    if (
        re.search(r"\b(?:rejette|rejeter|supprime|ecarte)\b", normalized)
        and re.search(r"\b(?:conflit|contradiction)\b", normalized)
        and re.search(r"\b(?:memoire|souvenir|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r3_execute(
            self, "learning.resolve_conflict",
            {"keep_candidate": False, "explicit_confirmation": True},
            user_confirmed=True
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai rejete explicitement le candidat en conflit.",
            "Je n'ai pas pu resoudre le conflit memoire.",
        )

    if (
        re.search(r"\b(?:consolide|consolider)\b", normalized)
        and re.search(r"\b(?:dernier|derniere|candidat|candidate|memoire|souvenir)\b", normalized)
    ):
        result = _aura_l170_r3_execute(
            self, "learning.consolidate_candidate",
            {"explicit_confirmation": True}, user_confirmed=True
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai consolide le candidat approuve dans le registre d'apprentissage controle. Aucun poids modele n'a ete modifie.",
            "Je n'ai pas pu consolider le candidat memoire.",
        )

    if (
        re.search(r"\b(?:montre|affiche|liste|voir)\b", normalized)
        and re.search(r"\b(?:souvenir|souvenirs|memoire|memoires)\b", normalized)
        and re.search(r"\b(?:consolide|consolides|appris|apprentissage)\b", normalized)
    ):
        result = _aura_l170_r3_execute(
            self, "learning.list_consolidated", {}, user_confirmed=False
        )
        return _aura_l170_r2_reply(
            result,
            "J'ai affiche les souvenirs consolides du registre d'apprentissage controle.",
            "Je n'ai pas pu lire les souvenirs consolides.",
        )

    return _AURA_L170_R3_PREVIOUS_DISPATCH(self, text)

PersonalIntegrationDispatcher.dispatch_integration = _aura_l170_r3_dispatch

# AURA_M180_R2_LOCAL_MEDIA_ROUTES
_AURA_M180_R2_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


class _AuraM180R2Security:
    _ALLOWED = frozenset({
        "media.catalog_summary",
        "media.search",
        "media.smart_queue",
        "media.playlist_proposal",
        "media.playback_intent",
    })

    def authorize(self, action, params, *, user_confirmed=False):
        return "ALLOW" if str(action or "") in self._ALLOWED else "DENY"


def _aura_m180_r2_execute(self, capability_id: str, params: Mapping[str, Any] | None = None):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_music_media_registry_binding_v180 import (
        register_music_media_center_provider_v180,
    )

    registry = getattr(self, "_aura_m180_r2_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraM180R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_music_media_center_provider_v180(registry)
        self._aura_m180_r2_registry = registry

    request = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.media.m180",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=False)


def _aura_m180_r2_reply(result, ok_text: str, fail_text: str):
    return IntegrationRuntimeReply(
        handled=True,
        text=ok_text if result.status == "succeeded" else fail_text,
        status=result.status,
        capability_id=result.capability_id,
        receipt_id=result.receipt_id,
        pending_confirmation=False,
        clarification_required=False,
        payload=result.output,
    )


def _aura_m180_r2_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_R2_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:bibliotheque|catalogue|mediatheque)\b", normalized)
        and re.search(r"\b(?:media|medias|musique|video|videos)\b", normalized)
    ):
        result = _aura_m180_r2_execute(self, "media.catalog_summary", {})
        return _aura_m180_r2_reply(
            result,
            "J'ai analyse le catalogue media local.",
            "Je n'ai pas pu lire le catalogue media local.",
        )

    if (
        re.search(r"\b(?:cherche|chercher|trouve|trouver)\b", normalized)
        and re.search(r"\b(?:media|medias|musique|musiques|video|videos)\b", normalized)
    ):
        query = raw
        query = re.sub(
            r"(?i)^.*?\b(?:cherche|chercher|trouve|trouver)\b",
            "",
            query,
            count=1,
        )
        query = re.sub(
            r"(?i)\b(?:dans|parmi)\b.*$",
            "",
            query,
            count=1,
        ).strip(" .:-")
        result = _aura_m180_r2_execute(
            self,
            "media.search",
            {"query": query, "limit": 20},
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai cherche dans le catalogue media local.",
            "Je n'ai pas pu effectuer la recherche media.",
        )

    if (
        re.search(r"\b(?:file|queue|selection)\b", normalized)
        and re.search(r"\b(?:media|musique|ecoute)\b", normalized)
        and re.search(r"\b(?:prepare|cree|creer|genere|generer)\b", normalized)
    ):
        mood = re.sub(
            r"(?i)^.*?\b(?:file|queue|selection)\b",
            "",
            raw,
            count=1,
        ).strip(" .:-")
        result = _aura_m180_r2_execute(
            self,
            "media.smart_queue",
            {
                "mood": mood,
                "media_type": "audio",
                "max_items": 10,
            },
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai prepare une file d'ecoute explicable. Aucune lecture n'a commence.",
            "Je n'ai pas pu preparer la file media.",
        )

    if (
        re.search(r"\bplaylist\b", normalized)
        and re.search(r"\b(?:prepare|cree|creer|propose)\b", normalized)
    ):
        query = re.sub(
            r"(?i)^.*?\bplaylist\b",
            "",
            raw,
            count=1,
        ).strip(" .:-")
        result = _aura_m180_r2_execute(
            self,
            "media.playlist_proposal",
            {
                "name": "AURA Media Playlist",
                "query": query,
                "max_items": 20,
            },
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai prepare une proposition de playlist locale. Rien n'a ete ecrit sur un service externe.",
            "Je n'ai pas pu preparer la playlist.",
        )

    if (
        re.search(r"\b(?:lecture|lire|jouer|play)\b", normalized)
        and re.search(r"\b(?:prepare|plan|intention)\b", normalized)
        and re.search(r"\b(?:media|musique|video|lecture)\b", normalized)
    ):
        query = re.sub(
            r"(?i)^.*?\b(?:de|du|des)\b",
            "",
            raw,
            count=1,
        ).strip(" .:-")
        result = _aura_m180_r2_execute(
            self,
            "media.playback_intent",
            {
                "query": query,
                "action": "play",
            },
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai prepare l'intention de lecture. Elle reste en attente d'approbation et aucune lecture n'a commence.",
            "Je n'ai pas pu preparer l'intention de lecture.",
        )

    return _AURA_M180_R2_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_r2_dispatch

# AURA_M180_R3_CONTROLLED_LOCAL_PLAYER
_AuraM180R2Security._ALLOWED = frozenset(
    set(_AuraM180R2Security._ALLOWED)
    | {
        "media.list_items",
        "media.play_confirmed",
        "media.player_status",
    }
)


def _aura_m180_r3_authorize(self, action, params, *, user_confirmed=False):
    action = str(action or "")
    if action not in self._ALLOWED:
        return "DENY"
    if action == "media.play_confirmed" and not user_confirmed:
        return "DENY"
    return "ALLOW"


_AuraM180R2Security.authorize = _aura_m180_r3_authorize


def _aura_m180_r3_execute(
    self,
    capability_id: str,
    params: Mapping[str, Any] | None = None,
    *,
    user_confirmed: bool,
):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_music_media_registry_binding_v180 import (
        register_music_media_center_provider_v180,
    )

    registry = getattr(self, "_aura_m180_r3_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraM180R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_music_media_center_provider_v180(registry)
        self._aura_m180_r3_registry = registry

    request = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id=capability_id,
        params=dict(params or {}),
        origin="conversation.media.m180.r3",
    )
    self._last_request = request
    return registry.execute_integration(
        request,
        user_confirmed=user_confirmed,
    )


_AURA_M180_R3_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration


def _aura_m180_r3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_R3_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:montre|affiche|liste|voir)\b", normalized)
        and re.search(r"\b(?:media|medias)\b", normalized)
        and re.search(r"\b(?:locaux|local|indexes|indexes)\b", normalized)
        and not re.search(r"\b(?:statut|status|etat|lecteur|lecture|player)\b", normalized)
    ):
        result = _aura_m180_r3_execute(
            self,
            "media.list_items",
            {"limit": 20},
            user_confirmed=False,
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai affiche les medias locaux indexes.",
            "Je n'ai pas pu lire les medias locaux indexes.",
        )

    if (
        re.search(r"\b(?:confirme|confirmer|confirmee|valide|valider)\b", normalized)
        and re.search(r"\b(?:lecture|lire|jouer|play)\b", normalized)
        and re.search(r"\b(?:media|musique|video|local)\b", normalized)
    ):
        first = bool(
            re.search(r"\b(?:premier|premiere)\b", normalized)
        )
        query = ""
        if not first:
            query = re.sub(
                r"(?i)^.*?\b(?:de|du|des)\b",
                "",
                raw,
                count=1,
            ).strip(" .:-")
        result = _aura_m180_r3_execute(
            self,
            "media.play_confirmed",
            {
                "first": first,
                "query": query,
                "explicit_confirmation": True,
            },
            user_confirmed=True,
        )
        return _aura_m180_r2_reply(
            result,
            "Lecture locale confirmee. J'ai transmis le media au lecteur local.",
            "Je n'ai pas pu lancer le media local.",
        )

    if (
        re.search(r"\b(?:statut|status|etat)\b", normalized)
        and re.search(r"\b(?:lecteur|lecture|player)\b", normalized)
        and re.search(r"\b(?:media|local)\b", normalized)
    ):
        result = _aura_m180_r3_execute(
            self,
            "media.player_status",
            {},
            user_confirmed=False,
        )
        return _aura_m180_r2_reply(
            result,
            "J'ai affiche le statut de la derniere lecture locale controlee.",
            "Je n'ai pas pu lire le statut du lecteur local.",
        )

    return _AURA_M180_R3_PREVIOUS_DISPATCH(self, text)


PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_r3_dispatch

# AURA_M180_UI1_MUSIC_PLAYER_PANEL
_AuraM180R2Security._ALLOWED = frozenset(
    set(_AuraM180R2Security._ALLOWED) | {"media.player_key"}
)

def _aura_m180_ui1_execute(self, action: str):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_music_media_registry_binding_v180 import register_music_media_center_provider_v180
    registry = getattr(self, "_aura_m180_ui1_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraM180R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_music_media_center_provider_v180(registry)
        self._aura_m180_ui1_registry = registry
    request = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id="media.player_key",
        params={"action": action},
        origin="conversation.media.m180.ui1",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=True)

_AURA_M180_UI1_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

def _aura_m180_ui1_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_UI1_PREVIOUS_DISPATCH(self, text)

    action = None
    ok = None
    if re.search(r"\b(?:pause|reprends|reprendre)\b", normalized) and re.search(r"\b(?:musique|media|lecture)\b", normalized):
        action, ok = "play_pause", "J'ai bascule lecture/pause sur le lecteur local."
    elif re.search(r"\b(?:suivant|suivante|next)\b", normalized) and re.search(r"\b(?:musique|media|titre|piste)\b", normalized):
        action, ok = "next", "Je suis passe au media suivant."
    elif re.search(r"\b(?:precedent|precedente|previous)\b", normalized) and re.search(r"\b(?:musique|media|titre|piste)\b", normalized):
        action, ok = "previous", "Je suis revenu au media precedent."
    elif re.search(r"\b(?:arrete|arreter|stop)\b", normalized) and re.search(r"\b(?:musique|media|lecture)\b", normalized):
        action, ok = "stop", "J'ai envoye l'ordre d'arret au lecteur local."
    elif re.search(r"\b(?:monte|augmenter|augmente)\b", normalized) and re.search(r"\bvolume\b", normalized):
        action, ok = "volume_up", "J'ai augmente le volume media."
    elif re.search(r"\b(?:baisse|diminuer|diminue)\b", normalized) and re.search(r"\bvolume\b", normalized):
        action, ok = "volume_down", "J'ai baisse le volume media."
    elif re.search(r"\b(?:mute|muet|coupe)\b", normalized) and re.search(r"\bvolume\b", normalized):
        action, ok = "volume_mute", "J'ai bascule le mode muet du lecteur."

    if action:
        result = _aura_m180_ui1_execute(self, action)
        return _aura_m180_r2_reply(result, ok, "Je n'ai pas pu controler le lecteur local.")
    return _AURA_M180_UI1_PREVIOUS_DISPATCH(self, text)

PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_ui1_dispatch

# AURA_M180_UI3_PC_BROWSER
_AuraM180R2Security._ALLOWED = frozenset(
    set(_AuraM180R2Security._ALLOWED)
    | {
        "media.pick_local_music",
        "media.pick_local_playlist",
        "media.pick_local_folder",
    }
)

def _aura_m180_ui3_execute(self, capability_id: str):
    from integrations import IntegrationRegistry, IntegrationRequest
    from runtime.aura_music_media_registry_binding_v180 import (
        register_music_media_center_provider_v180,
    )

    registry = getattr(self, "_aura_m180_ui3_registry", None)
    if registry is None:
        registry = IntegrationRegistry(
            security_engine=_AuraM180R2Security(),
            receipt_service=self.context.receipt_service,
        )
        register_music_media_center_provider_v180(registry)
        self._aura_m180_ui3_registry = registry

    request = IntegrationRequest.create(
        provider_id="music.media-center",
        capability_id=capability_id,
        params={},
        origin="conversation.media.m180.ui3",
    )
    self._last_request = request
    return registry.execute_integration(request, user_confirmed=True)

_AURA_M180_UI3_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

def _aura_m180_ui3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_UI3_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:choisis|choisir|ouvre|ouvrir|selectionne|selectionner)\b", normalized)
        and re.search(r"\b(?:musique|media|morceau|titre)\b", normalized)
        and re.search(r"\b(?:pc|ordinateur|disque|local)\b", normalized)
    ):
        result = _aura_m180_ui3_execute(self, "media.pick_local_music")
        return _aura_m180_r2_reply(
            result,
            "J'ai ouvert le selecteur Windows pour choisir une musique sur le PC.",
            "Je n'ai pas pu ouvrir le selecteur de musique.",
        )

    if (
        re.search(r"\b(?:choisis|choisir|ouvre|ouvrir|selectionne|selectionner)\b", normalized)
        and re.search(r"\bplaylist\b", normalized)
        and re.search(r"\b(?:pc|ordinateur|disque|local)\b", normalized)
    ):
        result = _aura_m180_ui3_execute(self, "media.pick_local_playlist")
        return _aura_m180_r2_reply(
            result,
            "J'ai ouvert le selecteur Windows pour choisir une playlist sur le PC.",
            "Je n'ai pas pu ouvrir le selecteur de playlist.",
        )

    if (
        re.search(r"\b(?:choisis|choisir|ouvre|ouvrir|ajoute|ajouter|selectionne|selectionner)\b", normalized)
        and re.search(r"\b(?:dossier|repertoire)\b", normalized)
        and re.search(r"\b(?:musique|media|pc|ordinateur|local)\b", normalized)
    ):
        result = _aura_m180_ui3_execute(self, "media.pick_local_folder")
        return _aura_m180_r2_reply(
            result,
            "J'ai ouvert le selecteur Windows pour choisir un dossier media.",
            "Je n'ai pas pu ouvrir le selecteur de dossier.",
        )

    return _AURA_M180_UI3_PREVIOUS_DISPATCH(self, text)

PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_ui3_dispatch

# AURA_M180_UI4_R3_R1_R1_VLC_PREMIUM_PLAYER
_AuraM180R2Security._ALLOWED = frozenset(
    set(_AuraM180R2Security._ALLOWED) | {"media.player_control"}
)

_AURA_M180_UI4_R3_R1_PREVIOUS_AUTHORIZE = _AuraM180R2Security.authorize

def _aura_m180_ui4_r3_r1_authorize(self, action, params, *, user_confirmed=False):
    if str(action or "") == "media.player_control":
        return "ALLOW"
    return _AURA_M180_UI4_R3_R1_PREVIOUS_AUTHORIZE(
        self,
        action,
        params,
        user_confirmed=user_confirmed,
    )

_AuraM180R2Security.authorize = _aura_m180_ui4_r3_r1_authorize

def _aura_m180_ui4_r3_r1_control(self, action, value=None):
    return _aura_m180_r3_execute(
        self,
        "media.player_control",
        {"action": action, "value": value},
        user_confirmed=True,
    )

_AURA_M180_UI4_R3_R1_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

def _aura_m180_ui4_r3_r1_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_UI4_R3_R1_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:pause|mets en pause)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_r1_control(self, "pause")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale mise en pause.",
            "Je n'ai pas pu mettre la lecture locale en pause.",
        )

    if (
        re.search(r"\b(?:reprends|reprendre|continue|continuer|resume)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_r1_control(self, "resume")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale reprise.",
            "Je n'ai pas pu reprendre la lecture locale.",
        )

    if (
        re.search(r"\b(?:arrete|arreter|stop|stoppe)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_r1_control(self, "stop")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale arretee.",
            "Je n'ai pas pu arreter la lecture locale.",
        )

    m = re.search(
        r"\b(?:volume|son)\b.*?\b(\d{1,3})\s*(?:%|pourcent)?\b",
        normalized,
    )
    if m and re.search(r"\b(?:musique|media|local)\b", normalized):
        pct = max(0, min(100, int(m.group(1))))
        result = _aura_m180_ui4_r3_r1_control(self, "volume_percent", pct)
        return _aura_m180_r2_reply(
            result,
            f"Volume local regle a {pct} pourcent.",
            "Je n'ai pas pu regler le volume local.",
        )

    m = re.search(
        r"\b(?:positionne|avance|va|seek)\b.*?\b(\d{1,3})\s*(?:%|pourcent)\b",
        normalized,
    )
    if m and re.search(r"\b(?:musique|media|lecture|local)\b", normalized):
        pct = max(0, min(100, int(m.group(1))))
        result = _aura_m180_ui4_r3_r1_control(self, "seek_percent", pct)
        return _aura_m180_r2_reply(
            result,
            f"Position de lecture reglee a {pct} pourcent.",
            "Je n'ai pas pu deplacer la position de lecture.",
        )

    return _AURA_M180_UI4_R3_R1_PREVIOUS_DISPATCH(self, text)

PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_ui4_r3_r1_dispatch

# AURA_M180_UI4_R3_R2_VLC_PREMIUM_PLAYER
_AuraM180R2Security._ALLOWED = frozenset(
    set(_AuraM180R2Security._ALLOWED) | {"media.player_control"}
)

_AURA_M180_UI4_R3_PREVIOUS_AUTHORIZE = _AuraM180R2Security.authorize

def _aura_m180_ui4_r3_authorize(self, action, params, *, user_confirmed=False):
    if str(action or "") == "media.player_control":
        return "ALLOW"
    return _AURA_M180_UI4_R3_PREVIOUS_AUTHORIZE(
        self,
        action,
        params,
        user_confirmed=user_confirmed,
    )

_AuraM180R2Security.authorize = _aura_m180_ui4_r3_authorize

def _aura_m180_ui4_r3_control(self, action, value=None):
    return _aura_m180_r3_execute(
        self,
        "media.player_control",
        {"action": action, "value": value},
        user_confirmed=True,
    )

_AURA_M180_UI4_R3_PREVIOUS_DISPATCH = PersonalIntegrationDispatcher.dispatch_integration

def _aura_m180_ui4_r3_dispatch(self, text: str):
    raw = str(text or "").strip()
    normalized = _normalize(raw)
    if not normalized:
        return _AURA_M180_UI4_R3_PREVIOUS_DISPATCH(self, text)

    if (
        re.search(r"\b(?:pause|mets en pause)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_control(self, "pause")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale mise en pause.",
            "Je n'ai pas pu mettre la lecture locale en pause.",
        )

    if (
        re.search(r"\b(?:reprends|reprendre|continue|continuer|resume)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_control(self, "resume")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale reprise.",
            "Je n'ai pas pu reprendre la lecture locale.",
        )

    if (
        re.search(r"\b(?:arrete|arreter|stop|stoppe)\b", normalized)
        and re.search(r"\b(?:musique|media|lecture|local)\b", normalized)
    ):
        result = _aura_m180_ui4_r3_control(self, "stop")
        return _aura_m180_r2_reply(
            result,
            "Lecture locale arretee.",
            "Je n'ai pas pu arreter la lecture locale.",
        )

    m = re.search(
        r"\b(?:volume|son)\b.*?\b(\d{1,3})\s*(?:%|pourcent)?\b",
        normalized,
    )
    if m and re.search(r"\b(?:musique|media|local)\b", normalized):
        pct = max(0, min(100, int(m.group(1))))
        result = _aura_m180_ui4_r3_control(self, "volume_percent", pct)
        return _aura_m180_r2_reply(
            result,
            f"Volume local regle a {pct} pourcent.",
            "Je n'ai pas pu regler le volume local.",
        )

    m = re.search(
        r"\b(?:positionne|avance|va|seek)\b.*?\b(\d{1,3})\s*(?:%|pourcent)\b",
        normalized,
    )
    if m and re.search(r"\b(?:musique|media|lecture|local)\b", normalized):
        pct = max(0, min(100, int(m.group(1))))
        result = _aura_m180_ui4_r3_control(self, "seek_percent", pct)
        return _aura_m180_r2_reply(
            result,
            f"Position de lecture reglee a {pct} pourcent.",
            "Je n'ai pas pu deplacer la position de lecture.",
        )

    return _AURA_M180_UI4_R3_PREVIOUS_DISPATCH(self, text)

PersonalIntegrationDispatcher.dispatch_integration = _aura_m180_ui4_r3_dispatch
