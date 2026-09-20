from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google.auth.transport.requests import (
    Request,
)
from google.oauth2.credentials import (
    Credentials,
)
from google_auth_oauthlib.flow import (
    InstalledAppFlow,
)
from googleapiclient.discovery import (
    build,
)


GOOGLE_SCOPES_V120 = (
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/contacts.readonly",
    "https://www.googleapis.com/auth/contacts",
    "https://www.googleapis.com/auth/drive.readonly",
)


def load_google_client_config_v120(
    path: str | Path,
) -> dict[str, Any]:
    file_path = Path(
        path
    ).expanduser().resolve()
    payload = json.loads(
        file_path.read_text(
            encoding="utf-8-sig"
        )
    )
    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Google OAuth client config must be object"
        )
    if not any(
        key in payload
        for key in (
            "installed",
            "web",
        )
    ):
        raise ValueError(
            "Google OAuth desktop client configuration required"
        )
    return payload


def authorize_google_v120(
    client_config: dict[str, Any],
) -> Credentials:
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=list(
            GOOGLE_SCOPES_V120
        ),
    )
    return flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message=(
            "AURA ouvre Google pour autoriser "
            "Gmail, Agenda, Contacts et Drive."
        ),
        success_message=(
            "Connexion Google réussie. "
            "Vous pouvez fermer cette fenêtre."
        ),
        open_browser=True,
    )


def credentials_from_json_v120(
    serialized: str,
) -> Credentials:
    payload = json.loads(
        serialized
    )
    credentials = Credentials.from_authorized_user_info(
        payload,
        scopes=list(
            GOOGLE_SCOPES_V120
        ),
    )
    if (
        credentials.expired
        and credentials.refresh_token
    ):
        credentials.refresh(
            Request()
        )
    return credentials


def google_identity_v120(
    credentials: Credentials,
) -> dict[str, str]:
    gmail = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    profile = (
        gmail.users()
        .getProfile(
            userId="me"
        )
        .execute()
    )
    return {
        "email": str(
            profile.get(
                "emailAddress",
                "",
            )
        ),
        "messages_total": str(
            profile.get(
                "messagesTotal",
                0,
            )
        ),
        "threads_total": str(
            profile.get(
                "threadsTotal",
                0,
            )
        ),
    }


def google_sync_summary_v120(
    credentials: Credentials,
) -> dict[str, Any]:
    gmail = build(
        "gmail",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    calendar = build(
        "calendar",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )
    people = build(
        "people",
        "v1",
        credentials=credentials,
        cache_discovery=False,
    )
    drive = build(
        "drive",
        "v3",
        credentials=credentials,
        cache_discovery=False,
    )

    inbox = (
        gmail.users()
        .messages()
        .list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=10,
        )
        .execute()
    )
    unread = (
        gmail.users()
        .messages()
        .list(
            userId="me",
            labelIds=[
                "INBOX",
                "UNREAD",
            ],
            maxResults=10,
        )
        .execute()
    )
    events = (
        calendar.events()
        .list(
            calendarId="primary",
            maxResults=10,
            singleEvents=True,
            orderBy="startTime",
            timeMin=__import__(
                "datetime"
            ).datetime.now(
                __import__(
                    "datetime"
                ).timezone.utc
            ).isoformat(),
        )
        .execute()
    )
    contacts = (
        people.people()
        .connections()
        .list(
            resourceName="people/me",
            pageSize=10,
            personFields=(
                "names,emailAddresses,"
                "phoneNumbers"
            ),
        )
        .execute()
    )
    files = (
        drive.files()
        .list(
            pageSize=10,
            fields=(
                "files(id,name,mimeType,"
                "modifiedTime,webViewLink)"
            ),
            orderBy="modifiedTime desc",
        )
        .execute()
    )

    return {
        "gmail": {
            "inbox_sample_count": len(
                inbox.get(
                    "messages",
                    [],
                )
            ),
            "unread_sample_count": len(
                unread.get(
                    "messages",
                    [],
                )
            ),
        },
        "calendar": {
            "upcoming": events.get(
                "items",
                [],
            ),
        },
        "contacts": {
            "sample": contacts.get(
                "connections",
                [],
            ),
        },
        "drive": {
            "recent": files.get(
                "files",
                [],
            ),
        },
    }


__all__ = [
    "GOOGLE_SCOPES_V120",
    "load_google_client_config_v120",
    "authorize_google_v120",
    "credentials_from_json_v120",
    "google_identity_v120",
    "google_sync_summary_v120",
]
