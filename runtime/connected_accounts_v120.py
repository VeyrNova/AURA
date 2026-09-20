from __future__ import annotations

from typing import Any
from uuid import uuid4

from accounts.google_oauth import (
    authorize_google_v120,
    credentials_from_json_v120,
    google_identity_v120,
    google_sync_summary_v120,
    load_google_client_config_v120,
)
from accounts.model import GOOGLE_SERVICES_V120, ConnectedAccountV120
from accounts.registry import ConnectedAccountRegistryV120
from accounts.secret_store import ConnectedAccountSecretStoreV120

class ConnectedAccountsRuntimeError(RuntimeError):
    pass

class ConnectedAccountsServiceV120:
    def __init__(self, *, registry=None, secrets=None):
        self.registry = registry or ConnectedAccountRegistryV120()
        self.secrets = secrets or ConnectedAccountSecretStoreV120()

    def list_accounts(self, provider: str | None = None):
        return self.registry.list_accounts(provider)

    def connect_google_from_client_file(self, path: str) -> ConnectedAccountV120:
        config = load_google_client_config_v120(path)
        credentials = authorize_google_v120(config)
        identity = google_identity_v120(credentials)
        email = identity.get("email") or "Google"
        credential_ref = "google:" + uuid4().hex
        self.secrets.set_secret(credential_ref, credentials.to_json())
        try:
            return self.registry.create(
                provider="google",
                display_label=email,
                services=GOOGLE_SERVICES_V120,
                credential_ref=credential_ref,
                state="connected",
                metadata={"email": email},
            )
        except Exception:
            self.secrets.delete_secret(credential_ref)
            raise

    def disconnect(self, account_id: str) -> bool:
        account = self.registry.get(account_id)
        if account is None:
            return False
        self.secrets.delete_secret(account.credential_ref)
        return self.registry.remove(account.account_id)

    def _credentials(self, account: ConnectedAccountV120):
        serialized = self.secrets.get_secret(account.credential_ref)
        if not serialized:
            self.registry.update_state(account.account_id, "expired")
            raise ConnectedAccountsRuntimeError("Google credentials unavailable")
        credentials = credentials_from_json_v120(serialized)
        refreshed = credentials.to_json()
        if refreshed != serialized:
            self.secrets.set_secret(account.credential_ref, refreshed)
        return credentials

    def test_account(self, account_id: str) -> dict[str, Any]:
        account = self.registry.get(account_id)
        if account is None:
            raise KeyError(account_id)
        if account.provider != "google":
            raise ConnectedAccountsRuntimeError("Google-only runtime")
        try:
            identity = google_identity_v120(self._credentials(account))
            self.registry.update_state(account.account_id, "connected")
            return {"ok": True, "provider": "google", "account_id": account.account_id, "identity": identity}
        except Exception as exc:
            try:
                self.registry.update_state(account.account_id, "degraded")
            except Exception:
                pass
            return {"ok": False, "provider": "google", "account_id": account.account_id, "error": type(exc).__name__}

    def sync_summary(self, account_id: str) -> dict[str, Any]:
        account = self.registry.get(account_id)
        if account is None:
            raise KeyError(account_id)
        if account.provider != "google":
            raise ConnectedAccountsRuntimeError("Google-only runtime")
        try:
            summary = google_sync_summary_v120(self._credentials(account))
            self.registry.update_state(account.account_id, "connected")
            return {"ok": True, "provider": "google", "account_id": account.account_id, "summary": summary}
        except Exception as exc:
            try:
                self.registry.update_state(account.account_id, "degraded")
            except Exception:
                pass
            return {"ok": False, "provider": "google", "account_id": account.account_id, "error": type(exc).__name__}

    def provider_status(self, provider: str = "google") -> dict[str, Any]:
        provider = str(provider or "").strip().lower()
        if provider != "google":
            return {"provider": provider, "state": "unsupported", "accounts": []}
        accounts = self.list_accounts("google")
        if not accounts:
            return {"provider": "google", "state": "disconnected", "accounts": []}
        return {
            "provider": "google",
            "state": "connected" if any(x.state == "connected" for x in accounts) else accounts[0].state,
            "accounts": [
                {
                    "account_id": x.account_id,
                    "display_label": x.display_label,
                    "state": x.state,
                    "services": list(x.services),
                }
                for x in accounts
            ],
        }

_SERVICE_V120 = None

def get_connected_accounts_service_v120() -> ConnectedAccountsServiceV120:
    global _SERVICE_V120
    if _SERVICE_V120 is None:
        _SERVICE_V120 = ConnectedAccountsServiceV120()
    return _SERVICE_V120

__all__ = [
    "ConnectedAccountsRuntimeError",
    "ConnectedAccountsServiceV120",
    "get_connected_accounts_service_v120",
]
