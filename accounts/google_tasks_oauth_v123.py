from __future__ import annotations

import json
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from accounts.google_oauth import (
    GOOGLE_SCOPES_V120,
    google_identity_v120,
    load_google_client_config_v120,
)
from accounts.model import ConnectedAccountV120, GOOGLE_SERVICES_V123, utc_now_v120

GOOGLE_TASKS_SCOPE_V123 = "https://www.googleapis.com/auth/tasks"
GOOGLE_PRODUCTIVITY_SCOPES_V123 = tuple(
    dict.fromkeys(tuple(GOOGLE_SCOPES_V120) + (GOOGLE_TASKS_SCOPE_V123,))
)


def authorize_google_productivity_v123(client_config: dict) -> Credentials:
    flow = InstalledAppFlow.from_client_config(
        client_config,
        scopes=list(GOOGLE_PRODUCTIVITY_SCOPES_V123),
    )
    return flow.run_local_server(
        host="localhost",
        port=0,
        authorization_prompt_message=(
            "AURA ouvre Google pour autoriser Gmail, Agenda, "
            "Contacts, Drive et Google Tasks."
        ),
        success_message=(
            "Connexion Google AURA mise a jour. "
            "Vous pouvez fermer cette fenetre."
        ),
        open_browser=True,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )


def credentials_from_json_productivity_v123(serialized: str) -> Credentials:
    payload = json.loads(serialized)
    credentials = Credentials.from_authorized_user_info(
        payload,
        scopes=list(GOOGLE_PRODUCTIVITY_SCOPES_V123),
    )
    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())
    return credentials


def _assert_tasks_scope_v123(credentials: Credentials) -> None:
    granted = tuple(getattr(credentials, "granted_scopes", None) or ())
    if granted and GOOGLE_TASKS_SCOPE_V123 not in granted:
        raise RuntimeError("Google Tasks OAuth re-consent required")


def credentials_for_tasks_v123(service, account):
    serialized = service.secrets.get_secret(account.credential_ref)
    if not serialized:
        raise RuntimeError("Google credentials unavailable")
    credentials = credentials_from_json_productivity_v123(serialized)
    _assert_tasks_scope_v123(credentials)
    refreshed = credentials.to_json()
    if refreshed != serialized:
        service.secrets.set_secret(account.credential_ref, refreshed)
    return credentials


def upgrade_google_account_for_tasks_v123(
    *,
    service,
    client_file: str,
    account_id: str | None = None,
):
    # Installed by D2. D3 is the only gate allowed to call this live.
    rows = service.list_accounts("google")
    if not rows:
        raise RuntimeError("AURA Google account is not connected")
    current = service.registry.get(account_id) if account_id else rows[0]
    if current is None:
        raise KeyError(account_id)

    config = load_google_client_config_v120(Path(client_file))
    credentials = authorize_google_productivity_v123(config)
    if not credentials.refresh_token:
        raise RuntimeError("Google OAuth did not return a durable refresh token")
    credentials.refresh(Request())
    _assert_tasks_scope_v123(credentials)
    identity = google_identity_v120(credentials)
    email = identity.get("email") or current.display_label

    service.secrets.set_secret(current.credential_ref, credentials.to_json())
    upgraded = ConnectedAccountV120(
        account_id=current.account_id,
        provider=current.provider,
        display_label=email,
        services=GOOGLE_SERVICES_V123,
        credential_ref=current.credential_ref,
        state="connected",
        is_default_for=tuple(
            x for x in current.is_default_for if x in GOOGLE_SERVICES_V123
        ),
        created_at=current.created_at,
        updated_at=utc_now_v120(),
        metadata=current.metadata,
    )
    return service.registry.upsert(upgraded)


__all__ = [
    "GOOGLE_TASKS_SCOPE_V123",
    "GOOGLE_PRODUCTIVITY_SCOPES_V123",
    "authorize_google_productivity_v123",
    "credentials_from_json_productivity_v123",
    "_assert_tasks_scope_v123",
    "credentials_for_tasks_v123",
    "upgrade_google_account_for_tasks_v123",
]
