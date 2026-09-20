from __future__ import annotations

from typing import Any


KEYRING_SERVICE_V120 = (
    "AURA.connected_accounts.v120"
)


class ConnectedAccountSecretStoreV120:
    """Opaque secret persistence via the OS-backed keyring only."""

    def __init__(
        self,
        backend: Any | None = None,
    ):
        if backend is None:
            import keyring
            backend = keyring
        self._backend = backend

    def set_secret(
        self,
        credential_ref: str,
        value: str,
    ) -> None:
        ref = str(
            credential_ref or ""
        ).strip()
        if not ref:
            raise ValueError(
                "credential_ref required"
            )
        if not isinstance(
            value,
            str,
        ) or not value:
            raise ValueError(
                "secret value required"
            )
        self._backend.set_password(
            KEYRING_SERVICE_V120,
            ref,
            value,
        )

    def get_secret(
        self,
        credential_ref: str,
    ) -> str | None:
        ref = str(
            credential_ref or ""
        ).strip()
        if not ref:
            raise ValueError(
                "credential_ref required"
            )
        return self._backend.get_password(
            KEYRING_SERVICE_V120,
            ref,
        )

    def delete_secret(
        self,
        credential_ref: str,
    ) -> bool:
        ref = str(
            credential_ref or ""
        ).strip()
        if not ref:
            return False
        try:
            self._backend.delete_password(
                KEYRING_SERVICE_V120,
                ref,
            )
            return True
        except Exception:
            return False


__all__ = [
    "KEYRING_SERVICE_V120",
    "ConnectedAccountSecretStoreV120",
]
