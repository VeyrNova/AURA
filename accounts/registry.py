from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, Optional
from uuid import uuid4

from .model import (
    ConnectedAccountV120,
    utc_now_v120,
)


def default_account_registry_path_v120() -> Path:
    local = os.environ.get(
        "LOCALAPPDATA"
    )
    if local:
        base = Path(local) / "AURA"
    else:
        base = (
            Path.home()
            / ".aura"
        )
    return (
        base
        / "accounts"
        / "accounts.json"
    )


class ConnectedAccountRegistryV120:
    def __init__(
        self,
        path: Path | None = None,
    ):
        self.path = (
            Path(path)
            if path is not None
            else (
                default_account_registry_path_v120()
            )
        )

    def _load(
        self,
    ) -> list[ConnectedAccountV120]:
        if not self.path.is_file():
            return []
        payload = json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )
        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "invalid account registry"
            )
        if (
            payload.get("schema")
            != "aura.connected-accounts.v120"
        ):
            raise ValueError(
                "unsupported account registry schema"
            )
        accounts = payload.get(
            "accounts",
            [],
        )
        if not isinstance(
            accounts,
            list,
        ):
            raise ValueError(
                "accounts must be list"
            )
        return [
            ConnectedAccountV120.from_dict(
                item
            )
            for item in accounts
        ]

    def _save(
        self,
        accounts: Iterable[
            ConnectedAccountV120
        ],
    ) -> None:
        rows = sorted(
            list(accounts),
            key=lambda item: (
                item.provider,
                item.display_label.lower(),
                item.account_id,
            ),
        )
        payload = {
            "schema": (
                "aura.connected-accounts.v120"
            ),
            "accounts": [
                item.to_dict()
                for item in rows
            ],
        }
        text = json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            sort_keys=True,
        )
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        tmp = self.path.with_suffix(
            ".tmp"
        )
        tmp.write_text(
            text,
            encoding="utf-8",
        )
        os.replace(
            tmp,
            self.path,
        )

    def list_accounts(
        self,
        provider: str | None = None,
    ) -> tuple[
        ConnectedAccountV120,
        ...,
    ]:
        accounts = self._load()
        if provider is not None:
            wanted = str(
                provider
            ).strip().lower()
            accounts = [
                item
                for item in accounts
                if item.provider == wanted
            ]
        return tuple(accounts)

    def get(
        self,
        account_id: str,
    ) -> Optional[
        ConnectedAccountV120
    ]:
        key = str(
            account_id or ""
        ).strip()
        for item in self._load():
            if item.account_id == key:
                return item
        return None

    def create(
        self,
        *,
        provider: str,
        display_label: str,
        services: Iterable[str],
        credential_ref: str,
        state: str = "connected",
        metadata: dict | None = None,
    ) -> ConnectedAccountV120:
        account = ConnectedAccountV120(
            account_id=uuid4().hex,
            provider=provider,
            display_label=display_label,
            services=tuple(
                services
            ),
            credential_ref=credential_ref,
            state=state,
            metadata=dict(
                metadata or {}
            ),
        )
        accounts = list(
            self._load()
        )
        accounts.append(account)
        self._save(accounts)
        return account

    def upsert(
        self,
        account: ConnectedAccountV120,
    ) -> ConnectedAccountV120:
        accounts = list(
            self._load()
        )
        replaced = False
        for index, item in enumerate(
            accounts
        ):
            if (
                item.account_id
                == account.account_id
            ):
                accounts[index] = account
                replaced = True
                break
        if not replaced:
            accounts.append(account)
        self._save(accounts)
        return account

    def update_state(
        self,
        account_id: str,
        state: str,
    ) -> ConnectedAccountV120:
        current = self.get(
            account_id
        )
        if current is None:
            raise KeyError(
                account_id
            )
        updated = ConnectedAccountV120(
            account_id=(
                current.account_id
            ),
            provider=current.provider,
            display_label=(
                current.display_label
            ),
            services=current.services,
            credential_ref=(
                current.credential_ref
            ),
            state=state,
            is_default_for=(
                current.is_default_for
            ),
            created_at=(
                current.created_at
            ),
            updated_at=utc_now_v120(),
            metadata=current.metadata,
        )
        return self.upsert(
            updated
        )

    def set_default(
        self,
        account_id: str,
        service: str,
    ) -> ConnectedAccountV120:
        current = self.get(
            account_id
        )
        if current is None:
            raise KeyError(
                account_id
            )
        service = str(
            service
        ).strip().lower()
        if service not in (
            current.services
        ):
            raise ValueError(
                "service not enabled:"
                + service
            )

        accounts = list(
            self._load()
        )
        result = None
        updated_accounts = []

        for item in accounts:
            defaults = set(
                item.is_default_for
            )
            if (
                item.provider
                == current.provider
            ):
                defaults.discard(
                    service
                )
            if (
                item.account_id
                == current.account_id
            ):
                defaults.add(
                    service
                )

            updated = ConnectedAccountV120(
                account_id=item.account_id,
                provider=item.provider,
                display_label=(
                    item.display_label
                ),
                services=item.services,
                credential_ref=(
                    item.credential_ref
                ),
                state=item.state,
                is_default_for=tuple(
                    sorted(defaults)
                ),
                created_at=(
                    item.created_at
                ),
                updated_at=utc_now_v120(),
                metadata=item.metadata,
            )
            updated_accounts.append(
                updated
            )
            if (
                updated.account_id
                == current.account_id
            ):
                result = updated

        self._save(
            updated_accounts
        )
        assert result is not None
        return result

    def remove(
        self,
        account_id: str,
    ) -> bool:
        key = str(
            account_id or ""
        ).strip()
        accounts = list(
            self._load()
        )
        remaining = [
            item
            for item in accounts
            if item.account_id != key
        ]
        if len(remaining) == len(
            accounts
        ):
            return False
        self._save(remaining)
        return True


__all__ = [
    "default_account_registry_path_v120",
    "ConnectedAccountRegistryV120",
]
