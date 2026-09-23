from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from accounts.model import ConnectedAccountV120, GOOGLE_SERVICES_V120, PROVIDERS_V120
from accounts.registry import ConnectedAccountRegistryV120
from accounts.secret_store import ConnectedAccountSecretStoreV120
from accounts.google_oauth import GOOGLE_SCOPES_V120
from runtime.connected_accounts_v120 import ConnectedAccountsServiceV120

class MemoryKeyring:
    def __init__(self):
        self.data = {}
    def set_password(self, service, username, password):
        self.data[(service, username)] = password
    def get_password(self, service, username):
        return self.data.get((service, username))
    def delete_password(self, service, username):
        self.data.pop((service, username), None)

assert PROVIDERS_V120 == ("google",)
tmp = Path(tempfile.mkdtemp(prefix="aura-v120-google-"))
registry = ConnectedAccountRegistryV120(tmp / "accounts.json")
secrets = ConnectedAccountSecretStoreV120(backend=MemoryKeyring())
service = ConnectedAccountsServiceV120(registry=registry, secrets=secrets)

secrets.set_secret("google:test", "TOP-SECRET-TOKEN")
account = registry.create(
    provider="google",
    display_label="tester@example.invalid",
    services=GOOGLE_SERVICES_V120,
    credential_ref="google:test",
    state="connected",
    metadata={"email": "tester@example.invalid"},
)
raw = (tmp / "accounts.json").read_text(encoding="utf-8")
assert "TOP-SECRET-TOKEN" not in raw
assert "credential_ref" in raw

for provider in ("microsoft", "orange_mail"):
    try:
        ConnectedAccountV120(
            account_id="bad-" + provider,
            provider=provider,
            display_label=provider,
            services=("mail",),
            credential_ref=provider + ":bad",
        )
        raise AssertionError(provider + " must be excluded")
    except ValueError:
        pass

assert any("gmail.readonly" in s for s in GOOGLE_SCOPES_V120)
assert any("drive.readonly" in s for s in GOOGLE_SCOPES_V120)
assert service.provider_status("google")["state"] == "connected"
assert service.provider_status("microsoft")["state"] == "unsupported"

settings = (ROOT / "ui" / "final_modules.py").read_text(encoding="utf-8-sig")
block = settings[settings.index("class SettingsPage"):settings.index("class TasksPage")]
assert "COMPTES CONNECTÉS" in block
assert "Gmail · Agenda · Contacts · Drive" in block
assert "MICROSOFT" not in block.upper()
assert "OUTLOOK" not in block.upper()
assert "ORANGE" not in block.upper()
assert not (ROOT / "accounts" / "microsoft_oauth.py").exists()

print("[PASS] Connected Accounts v1.2.0 Google-only")
print("[PASS] Gmail / Calendar / Contacts / Drive")
print("[PASS] Microsoft excluded")
print("[PASS] Orange Mail excluded")
print("[PASS] secret values not persisted in registry")
print("[PASS] SettingsPage Google-only")
