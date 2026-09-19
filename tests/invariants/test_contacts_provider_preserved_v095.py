from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_receipts import ActionReceiptService, ActionReceiptStore
from core.version import AURA_VERSION
from integrations.contacts import (
    CONTACTS_CAPABILITIES,
    CONTACTS_PROVIDER_ID,
    ContactProvider,
    SyntheticContactsBackend,
)
from integrations.registry import IntegrationRequest
from runtime.personal_integrations import PersonalIntegrationDispatcher, build_synthetic_runtime_context
from ui.personal_integration_modules import ContactsModuleController, PersonalIntegrationModules

assert AURA_VERSION == '0.9.5', AURA_VERSION
assert CONTACTS_PROVIDER_ID == "contacts.provider"
assert tuple(CONTACTS_CAPABILITIES) == (
    "contacts.search",
    "contacts.read",
    "contacts.create",
    "contacts.update",
    "contacts.delete",
)

provider = ContactProvider(backend=SyntheticContactsBackend())
assert provider.manifest.provider_id == CONTACTS_PROVIDER_ID
assert len(provider.manifest.capabilities) == 5

cap_map = {
    capability.capability_id: capability
    for capability in provider.manifest.capabilities
}

for capability_id in CONTACTS_CAPABILITIES:
    capability = cap_map[capability_id]
    assert capability.risk_tier is not None
    assert capability.side_effect_class is not None

for capability_id in (
    "contacts.create",
    "contacts.update",
    "contacts.delete",
):
    assert cap_map[capability_id].requires_confirmation is True

for capability_id in (
    "contacts.search",
    "contacts.read",
):
    assert cap_map[capability_id].requires_confirmation is False

assert provider.health_snapshot()["available"] is True
assert provider.health_snapshot()["external_connection"] is False

search = provider.execute(IntegrationRequest.create(
    provider_id=CONTACTS_PROVIDER_ID,
    capability_id="contacts.search",
    params={"query": {"text": "Alice", "limit": 10}},
    origin="contacts-invariant",
))
assert len(search["contacts"]) == 1
assert search["contacts"][0]["contact_id"] == "ctc-001"

read = provider.execute(IntegrationRequest.create(
    provider_id=CONTACTS_PROVIDER_ID,
    capability_id="contacts.read",
    params={"contact_id": "ctc-001"},
    origin="contacts-invariant",
))
assert read["contact"]["display_name"] == "Alice Martin"

class Security:
    def authorize(self, action, params, user_confirmed=False):
        writes = {"contacts.create", "contacts.update", "contacts.delete"}
        if action in writes and not user_confirmed:
            return "REQUIRE_CONFIRMATION"
        return "ALLOW"

with tempfile.TemporaryDirectory(prefix="aura_contacts_v093_") as td:
    receipts = ActionReceiptService(store=ActionReceiptStore(Path(td) / "receipts.db"))
    context = build_synthetic_runtime_context(security_engine=Security(), receipt_service=receipts)
    dispatcher = PersonalIntegrationDispatcher(context=context)
    modules = PersonalIntegrationModules(dispatcher=dispatcher)

    catalog = modules.catalog()
    assert "mail" in catalog
    assert "calendar" in catalog
    assert "contacts" in catalog
    assert catalog["contacts"]["capabilities"] == 5
    assert isinstance(modules.contacts, ContactsModuleController)

    search_reply = modules.contacts.search("Alice")
    assert search_reply.status == "succeeded"

    read_reply = modules.contacts.read("ctc-001")
    assert read_reply.status == "succeeded"

    create_waiting = modules.contacts.create(
        display_name="Jean Dupont",
        emails=("jean@example.invalid",),
        phones=("0644556677",),
    )
    assert create_waiting.status == "waiting_confirmation"
    assert create_waiting.receipt_id
    create_done = modules.confirm()
    assert create_done.status == "succeeded"
    assert create_done.receipt_id == create_waiting.receipt_id

    update_waiting = modules.contacts.update("ctc-001", display_name="Alice Martin MAJ")
    assert update_waiting.status == "waiting_confirmation"
    update_done = modules.confirm()
    assert update_done.status == "succeeded"
    assert update_done.receipt_id == update_waiting.receipt_id

    delete_waiting = modules.contacts.delete("ctc-002")
    assert delete_waiting.status == "waiting_confirmation"
    delete_done = modules.confirm()
    assert delete_done.status == "succeeded"
    assert delete_done.receipt_id == delete_waiting.receipt_id

    text_search = dispatcher.handle_text("cherche le contact Alice")
    assert text_search.status == "succeeded"

print("[PASS] AURA v0.9.3 ContactsProvider")
print("[PASS] contacts.search/read are read-only")
print("[PASS] contacts.create/update/delete require confirmation")
print("[PASS] same ActionReceipt survives confirmation")
print("[PASS] ContactsModuleController + conversation intents")
print("[PASS] synthetic/local provider; no external OAuth")
raise SystemExit(0)
