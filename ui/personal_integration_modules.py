"""AURA v0.9.2.1 Mail + Calendar module controllers.

D2 R1 exposes UI-ready module controllers using the SAME
PersonalIntegrationDispatcher as conversation. Actual insertion into the
existing AURA module surface is deferred to D3 to preserve v0.9.2 baseline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from runtime.personal_integrations import (
    CALENDAR_PROVIDER_ID,
    EMAIL_PROVIDER_ID,
    IntegrationRuntimeContext,
    IntegrationRuntimeReply,
    PersonalIntegrationDispatcher,
    CONTACTS_PROVIDER_ID,
    FILES_PROVIDER_ID,
)


@dataclass(frozen=True)
class IntegrationModuleStatus:
    module_id: str
    title: str
    provider_id: str
    available: bool
    health_state: str
    mode: str
    capabilities: int

    def to_dict(self):
        return {
            "module_id": self.module_id,
            "title": self.title,
            "provider_id": self.provider_id,
            "available": self.available,
            "health_state": self.health_state,
            "mode": self.mode,
            "capabilities": self.capabilities,
        }


class _BaseIntegrationModule:
    module_id = ""
    title = ""
    provider_id = ""
    capability_count = 0

    def __init__(self, *, dispatcher: PersonalIntegrationDispatcher):
        self.dispatcher = dispatcher

    @property
    def context(self) -> IntegrationRuntimeContext:
        return self.dispatcher.context

    def status(self) -> IntegrationModuleStatus:
        snapshots = self.context.registry.health_snapshot(self.provider_id)
        available = False
        health_state = "unknown"
        if snapshots:
            snapshot = snapshots[0]
            available = bool(getattr(snapshot, "available", False))
            health_state = str(getattr(snapshot, "health_state", "unknown"))
        return IntegrationModuleStatus(
            module_id=self.module_id,
            title=self.title,
            provider_id=self.provider_id,
            available=available,
            health_state=health_state,
            mode="GOOGLE_LIVE",
            capabilities=self.capability_count,
        )


class MailModuleController(_BaseIntegrationModule):
    module_id = "mail"
    title = "MAIL"
    provider_id = EMAIL_PROVIDER_ID
    capability_count = 11

    def search(self, text: str = "") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.search",
            params={"query": {"text": text, "limit": 20}},
            summary="Rechercher dans le module Mail",
        )

    def inbox(self) -> IntegrationRuntimeReply:
        return self.search("")

    def read(self, message_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.read",
            params={"message_id": message_id},
            summary=f"Lire le mail {message_id}",
        )

    def attachments(self, message_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.list_attachments",
            params={"message_id": message_id},
            summary=f"Afficher les pieces jointes de {message_id}",
        )

    def create_draft(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.create_draft",
            params={
                "to": [to],
                "subject": subject,
                "body_text": body_text,
            },
            summary=f"Creer un brouillon pour {to}",
        )

    def send(
        self,
        *,
        to: str,
        subject: str,
        body_text: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.send",
            params={
                "to": [to],
                "subject": subject,
                "body_text": body_text,
            },
            summary=f"Envoyer un email a {to}",
        )


    def reply(
        self,
        *,
        message_id: str,
        body_text: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.reply",
            params={
                "message_id": message_id,
                "body_text": body_text,
            },
            summary=f"Repondre au mail {message_id}",
        )

    def forward(
        self,
        *,
        message_id: str,
        to: str,
        body_text: str = "",
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.forward",
            params={
                "message_id": message_id,
                "to": [to],
                "body_text": body_text,
            },
            summary=f"Transferer {message_id} vers {to}",
        )

    def label(
        self,
        *,
        message_id: str,
        add=(),
        remove=(),
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.label",
            params={
                "message_id": message_id,
                "add": list(add),
                "remove": list(remove),
            },
            summary=f"Modifier les labels de {message_id}",
        )

    def archive(self, message_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.archive",
            params={"message_id": message_id},
            summary=f"Archiver le mail {message_id}",
        )

    def trash(self, message_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="email.trash",
            params={"message_id": message_id},
            summary=f"Mettre le mail {message_id} a la corbeille",
        )


class CalendarModuleController(_BaseIntegrationModule):
    module_id = "calendar"
    title = "CALENDAR"
    provider_id = CALENDAR_PROVIDER_ID
    capability_count = 8

    def calendars(self) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.list",
            params={},
            summary="Lister les calendriers",
        )

    def events(self) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.search_events",
            params={
                "query": {
                    "calendar_id": "cal-main",
                    "text": "",
                    "limit": 20,
                }
            },
            summary="Afficher les rendez-vous",
        )

    def read(self, event_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.read_event",
            params={"event_id": event_id},
            summary=f"Lire l'evenement {event_id}",
        )

    def free_busy(
        self,
        *,
        time_min: str,
        time_max: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.free_busy",
            params={
                "calendar_id": "cal-main",
                "time_min": time_min,
                "time_max": time_max,
            },
            summary="Verifier la disponibilite",
        )

    def create_event(
        self,
        *,
        title: str,
        start: str,
        end: str,
        timezone_name: str = "Europe/Paris",
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.create_event",
            params={
                "calendar_id": "cal-main",
                "title": title,
                "start": start,
                "end": end,
                "timezone": timezone_name,
                "attendees": [{"address": "boris@example.invalid"}],
            },
            summary=f"Creer le rendez-vous {title}",
        )


    def update_event(
        self,
        *,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.update_event",
            params={
                "event_id": event_id,
                "changes": dict(changes),
            },
            summary=f"Modifier l'evenement {event_id}",
        )

    def delete_event(self, event_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.delete_event",
            params={"event_id": event_id},
            summary=f"Supprimer l'evenement {event_id}",
        )

    def respond_invitation(
        self,
        *,
        event_id: str,
        response_status: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="calendar.respond_invitation",
            params={
                "event_id": event_id,
                "attendee_address": "boris@example.invalid",
                "response_status": response_status,
            },
            summary=f"Repondre a l'invitation {event_id}",
        )


class ContactsModuleController(_BaseIntegrationModule):
    module_id = "contacts"
    title = "CONTACTS"
    provider_id = CONTACTS_PROVIDER_ID
    capability_count = 5

    def search(self, text: str = "") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="contacts.search",
            params={"query": {"text": text, "limit": 10}},
            summary="Rechercher les contacts" + (f" concernant {text}" if text else ""),
        )

    def read(self, contact_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="contacts.read",
            params={"contact_id": contact_id},
            summary=f"Lire le contact {contact_id}",
        )

    def create(self, *, display_name: str, emails=(), phones=(), organization: str = "", notes: str = "") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="contacts.create",
            params={
                "display_name": display_name,
                "emails": list(emails),
                "phones": list(phones),
                "organization": organization,
                "notes": notes,
            },
            summary=f"Creer le contact {display_name}",
        )

    def update(self, contact_id: str, **changes) -> IntegrationRuntimeReply:
        params = {"contact_id": contact_id}
        params.update(changes)
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="contacts.update",
            params=params,
            summary=f"Modifier le contact {contact_id}",
        )

    def delete(self, contact_id: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="contacts.delete",
            params={"contact_id": contact_id},
            summary=f"Supprimer le contact {contact_id}",
        )


class FilesModuleController(_BaseIntegrationModule):
    module_id = "documents"
    title = "DOCUMENTS"
    provider_id = FILES_PROVIDER_ID
    capability_count = 7

    def list(self, path: str = "") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.list",
            params={"path": path},
            summary=(
                "Lister les fichiers"
                + (f" dans {path}" if path else "")
            ),
        )

    def search(self, text: str = "") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.search",
            params={
                "query": {
                    "text": text,
                    "limit": 20,
                }
            },
            summary=(
                "Rechercher les fichiers"
                + (f" concernant {text}" if text else "")
            ),
        )

    def read(self, path: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.read",
            params={"path": path},
            summary=f"Lire le fichier {path}",
        )

    def create(
        self,
        path: str,
        text: str = "",
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.create",
            params={
                "path": path,
                "text": text,
            },
            summary=f"Creer le fichier {path}",
        )

    def update(
        self,
        path: str,
        text: str,
        append: bool = False,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.update",
            params={
                "path": path,
                "text": text,
                "append": bool(append),
            },
            summary=f"Modifier le fichier {path}",
        )

    def move(
        self,
        source: str,
        destination: str,
    ) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.move",
            params={
                "source": source,
                "destination": destination,
            },
            summary=f"Deplacer {source} vers {destination}",
        )

    def delete(self, path: str) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id,
            capability_id="files.delete",
            params={"path": path},
            summary=f"Supprimer le fichier {path}",
        )


class TasksModuleController(_BaseIntegrationModule):
    module_id = "tasks"
    title = "TACHES"
    provider_id = "tasks.provider"
    capability_count = 7

    def tasklists(self) -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.tasklists",
            params={}, summary="Lister les listes Google Tasks",
        )

    def list(self, tasklist_id: str = "@default") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.list",
            params={"query":{"tasklist_id":tasklist_id,"limit":100,"include_completed":True}},
            summary="Afficher les taches Google",
        )

    def read(self, task_id: str, tasklist_id: str = "@default") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.read",
            params={"task_id":task_id,"tasklist_id":tasklist_id},
            summary=f"Lire la tache {task_id}",
        )

    def create(self, *, title: str, notes: str = "", due: str = "", tasklist_id: str = "@default") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.create",
            params={"title":title,"notes":notes,"due":due,"tasklist_id":tasklist_id},
            summary=f"Creer la tache {title}",
        )

    def update(self, task_id: str, *, tasklist_id: str = "@default", **changes) -> IntegrationRuntimeReply:
        params={"task_id":task_id,"tasklist_id":tasklist_id}; params.update(changes)
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.update",
            params=params, summary=f"Modifier la tache {task_id}",
        )

    def complete(self, task_id: str, *, tasklist_id: str = "@default") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.complete",
            params={"task_id":task_id,"tasklist_id":tasklist_id},
            summary=f"Terminer la tache {task_id}",
        )

    def delete(self, task_id: str, *, tasklist_id: str = "@default") -> IntegrationRuntimeReply:
        return self.dispatcher.dispatch_capability(
            provider_id=self.provider_id, capability_id="tasks.delete",
            params={"task_id":task_id,"tasklist_id":tasklist_id},
            summary=f"Supprimer la tache {task_id}",
        )


class PersonalIntegrationModules:
    """UI-ready shared module catalog."""

    def __init__(self, *, dispatcher: PersonalIntegrationDispatcher):
        self.dispatcher = dispatcher
        self.mail = MailModuleController(dispatcher=dispatcher)
        self.calendar = CalendarModuleController(dispatcher=dispatcher)
        self.contacts = ContactsModuleController(dispatcher=dispatcher)
        self.documents = FilesModuleController(dispatcher=dispatcher)
        self.tasks = TasksModuleController(dispatcher=dispatcher)

    def catalog(self):
        return {
            "mail": self.mail.status().to_dict(),
            "calendar": self.calendar.status().to_dict(),
            "contacts": self.contacts.status().to_dict(),
            "documents": self.documents.status().to_dict(),
            "tasks": self.tasks.status().to_dict(),
        }

    def confirm(self):
        return self.dispatcher.resume_confirmation()

    def cancel(self):
        return self.dispatcher.cancel_confirmation()


__all__ = [
    "IntegrationModuleStatus",
    "MailModuleController",
    "CalendarModuleController",
    "ContactsModuleController",
    "FilesModuleController",
    "TasksModuleController",
    "PersonalIntegrationModules",
]

# AURA V0.9.5 D2 R1 NOTIFICATIONS MODULE CONTROLLER
class NotificationsModuleController:
    provider_id = "notifications.provider"

    def _provider(self):
        from runtime.personal_integrations import get_notifications_provider_v095

        return get_notifications_provider_v095()

    def list_notifications(self, *, include_dismissed=False, unread_only=False):
        return self._provider().list(
            include_dismissed=include_dismissed,
            unread_only=unread_only,
        )

    def read_notification(self, notification_id):
        return self._provider().read(notification_id)

    def create_notification(
        self,
        *,
        title,
        message="",
        priority="normal",
        source="aura",
        meta=None,
    ):
        return self._provider().create(
            title=title,
            message=message,
            priority=priority,
            source=source,
            meta=meta,
        )

    def mark_read(self, notification_id):
        return self._provider().mark_read(notification_id)

    def dismiss(self, notification_id):
        return self._provider().dismiss(notification_id)

    def clear(self, *, confirmed=False):
        return self._provider().clear(
            confirmed=confirmed,
        )

    def open_activity_center_intent(self):
        return {
            "intent": "notifications.open",
            "legacy_surface": "P0.8.1 Activity Center",
            "browser_api": "window.AuraEventWatchers.open",
            "presentation_api": "window.AuraProactiveNotifications",
            "workspace": "talk",
            "prefill_if_empty": "affiche mes notifications",
            "preserve_non_empty_draft": True,
            "auto_submit": False,
            "duplicate_history_ui": False,
        }

    def audit(self):
        return {
            "provider": self._provider().audit(),
            "open_intent": self.open_activity_center_intent(),
        }

