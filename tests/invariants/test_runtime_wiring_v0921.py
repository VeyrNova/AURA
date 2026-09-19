from __future__ import annotations

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from action_receipts import ActionReceiptService, ActionReceiptStore
from runtime.personal_integrations import (
    PersonalIntegrationDispatcher,
    build_synthetic_runtime_context,
    resolve_timezone,
)
from ui.personal_integration_modules import PersonalIntegrationModules

assert AURA_VERSION == '0.9.4', AURA_VERSION


class RuntimeSecurity:
    def authorize(self, action, params, user_confirmed=False):
        if action in {
            "email.send",
            "email.reply",
            "email.forward",
            "email.archive",
            "email.trash",
            "email.label",
            "calendar.create_event",
            "calendar.update_event",
            "calendar.delete_event",
            "calendar.respond_invitation",
        } and not user_confirmed:
            return "REQUIRE_CONFIRMATION"
        return "ALLOW"


with tempfile.TemporaryDirectory(prefix="aura_v0921_r1_") as td:
    receipt_db = Path(td) / "receipts.db"
    receipts = ActionReceiptService(store=ActionReceiptStore(receipt_db))
    context = build_synthetic_runtime_context(
        security_engine=RuntimeSecurity(),
        receipt_service=receipts,
        timezone_name="Europe/Paris",
    )
    dispatcher = PersonalIntegrationDispatcher(context=context)
    modules = PersonalIntegrationModules(dispatcher=dispatcher)

    # Windows/tzdata regression: Europe/Paris must resolve without external package.
    tz = resolve_timezone("Europe/Paris")
    now = datetime.now(tz)
    assert now.utcoffset() is not None
    assert now.utcoffset() in {timedelta(hours=1), timedelta(hours=2)}

    # Module catalog visible and shares exact dispatcher/context.
    catalog = modules.catalog()
    assert catalog["mail"]["title"] == "MAIL"
    assert catalog["mail"]["mode"] == "SYNTHETIC"
    assert catalog["mail"]["capabilities"] == 11
    assert catalog["mail"]["available"] is True
    assert catalog["calendar"]["title"] == "CALENDAR"
    assert catalog["calendar"]["capabilities"] == 8
    assert catalog["calendar"]["available"] is True
    assert modules.mail.dispatcher is dispatcher
    assert modules.calendar.dispatcher is dispatcher

    # Conversation -> Email.
    ordinary = dispatcher.handle_text("Bonjour AURA")
    assert ordinary.handled is False

    mail_search = dispatcher.handle_text("cherche mes mails sur assurance")
    assert mail_search.status == "succeeded"
    assert mail_search.capability_id == "email.search"
    assert "msg-001" in mail_search.text
    assert "Recu d'action" in mail_search.text

    # Mail module uses same backend and same runtime authority.
    inbox = modules.mail.inbox()
    assert inbox.status == "succeeded"
    assert "msg-001" in inbox.text

    read = modules.mail.read("msg-001")
    assert read.status == "succeeded"
    assert "Dossier assurance" in read.text

    attachments = modules.mail.attachments("msg-001")
    assert attachments.status == "succeeded"
    assert "assurance.pdf" in attachments.text

    # Mail write waits then same receipt executes once.
    before_send = len(context.email_backend.calls)
    waiting_send = modules.mail.send(
        to="alice@example.invalid",
        subject="Test module",
        body_text="Bonjour Alice",
    )
    assert waiting_send.status == "waiting_confirmation"
    assert len(context.email_backend.calls) == before_send
    confirmed_send = modules.confirm()
    assert confirmed_send.status == "succeeded"
    assert confirmed_send.receipt_id == waiting_send.receipt_id
    assert len(context.email_backend.calls) == before_send + 1

    # Conversation -> Calendar.
    events = dispatcher.handle_text("quels sont mes prochains rendez-vous")
    assert events.status == "succeeded"
    assert events.capability_id == "calendar.search_events"
    assert "evt-001" in events.text

    free_busy = dispatcher.handle_text("suis-je libre demain entre 14h et 16h")
    assert free_busy.status == "succeeded"
    assert free_busy.capability_id == "calendar.free_busy"
    assert "pas entierement libre" in free_busy.text

    # Calendar module sees same event.
    module_events = modules.calendar.events()
    assert module_events.status == "succeeded"
    assert "evt-001" in module_events.text

    # Calendar write cancellation: provider call count remains zero.
    start = (now + timedelta(days=2)).replace(
        hour=18, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(hours=1)
    before_create = len(context.calendar_backend.calls)
    waiting_create = modules.calendar.create_event(
        title="Test module Calendar",
        start=start.isoformat(),
        end=end.isoformat(),
    )
    assert waiting_create.status == "waiting_confirmation"
    assert len(context.calendar_backend.calls) == before_create
    cancelled = modules.cancel()
    assert cancelled.handled is True
    assert len(context.calendar_backend.calls) == before_create

    # Calendar write confirmation executes exactly once and same receipt.
    waiting_create_2 = modules.calendar.create_event(
        title="Test module Calendar 2",
        start=start.isoformat(),
        end=end.isoformat(),
    )
    before_confirm = len(context.calendar_backend.calls)
    confirmed_create = modules.confirm()
    assert confirmed_create.status == "succeeded"
    assert confirmed_create.receipt_id == waiting_create_2.receipt_id
    assert len(context.calendar_backend.calls) == before_confirm + 1

    # Missing critical fields ask clarification and never execute.
    before_ambiguous = len(context.email_backend.calls)
    ambiguous = dispatcher.handle_text("envoie un mail")
    assert ambiguous.status == "clarification_required"
    assert ambiguous.clarification_required is True
    assert len(context.email_backend.calls) == before_ambiguous

    receipt_db.unlink()
    assert not receipt_db.exists()

print("[PASS] v0.9.2.1 D2 R1 runtime wiring + Mail/Calendar modules synthetic E2E")
raise SystemExit(0)
