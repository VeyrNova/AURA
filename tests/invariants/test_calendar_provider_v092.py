from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.version import AURA_VERSION
from action_receipts import ActionReceiptService, ActionReceiptStore
from integrations import IntegrationRegistry, IntegrationRequest
from integrations.calendar import (
    CALENDAR_CAPABILITIES,
    CONFIRMATION_CAPABILITIES,
    READ_CAPABILITIES,
    CalendarAttendee,
    CalendarEvent,
    CalendarFreeBusy,
    CalendarInfo,
    CalendarProvider,
    CalendarQuery,
    CalendarReminder,
    CalendarResult,
    CalendarValidationError,
    SyntheticCalendarBackend,
)

assert AURA_VERSION == '0.9.4', AURA_VERSION
assert len(CALENDAR_CAPABILITIES) == 8
assert len(READ_CAPABILITIES) == 4
assert len(CONFIRMATION_CAPABILITIES) == 4


class CalendarSecurity:
    def authorize(self, action, params, user_confirmed=False):
        if (
            action in CONFIRMATION_CAPABILITIES
            and not user_confirmed
        ):
            return "REQUIRE_CONFIRMATION"
        return "ALLOW"


class ExplodingSecurity:
    def authorize(self, action, params, user_confirmed=False):
        raise RuntimeError("synthetic security failure")


calendar = CalendarInfo(
    calendar_id="cal-main",
    name="Synthetic Calendar",
    timezone="Europe/Paris",
    primary=True,
)

attendee = CalendarAttendee(
    address="boris@example.invalid",
    display_name="Boris",
)

event = CalendarEvent(
    event_id="evt-001",
    calendar_id="cal-main",
    title="Synthetic meeting",
    start="2026-08-27T10:00:00+02:00",
    end="2026-08-27T11:00:00+02:00",
    timezone="Europe/Paris",
    description="Calendar invariant meeting",
    attendees=(attendee,),
    reminders=(
        CalendarReminder(
            method="popup",
            minutes_before=15,
        ),
    ),
)

assert isinstance(
    CalendarQuery(
        calendar_id="cal-main",
        text="Synthetic",
        time_min="2026-08-27T00:00:00+02:00",
        time_max="2026-08-28T00:00:00+02:00",
    ),
    CalendarQuery,
)

assert isinstance(
    CalendarFreeBusy(
        calendar_id="cal-main",
        time_min="2026-08-27T00:00:00+02:00",
        time_max="2026-08-28T00:00:00+02:00",
        timezone="Europe/Paris",
        busy=(
            (
                "2026-08-27T10:00:00+02:00",
                "2026-08-27T11:00:00+02:00",
            ),
        ),
    ),
    CalendarFreeBusy,
)

assert isinstance(
    CalendarResult(
        operation="probe",
        ok=True,
    ),
    CalendarResult,
)

# Naive timestamp must be rejected.
try:
    CalendarEvent(
        event_id="bad",
        calendar_id="cal-main",
        title="Bad",
        start="2026-08-27T10:00:00",
        end="2026-08-27T11:00:00",
        timezone="Europe/Paris",
    )
except CalendarValidationError:
    pass
else:
    raise AssertionError("naive Calendar timestamps must fail")


with tempfile.TemporaryDirectory(
    prefix="aura_v092_calendar_"
) as td:
    db = Path(td) / "receipts.db"
    receipts = ActionReceiptService(
        store=ActionReceiptStore(db)
    )
    backend = SyntheticCalendarBackend(
        calendars=(calendar,),
        events=(event,),
    )
    provider = CalendarProvider(
        backend=backend
    )
    registry = IntegrationRegistry(
        security_engine=CalendarSecurity(),
        receipt_service=receipts,
    )
    registry.register_provider(provider)

    caps = {
        item.capability_id: item
        for item in provider.manifest.capabilities
    }

    for capability_id in READ_CAPABILITIES:
        assert caps[
            capability_id
        ].requires_confirmation is False

    for capability_id in CONFIRMATION_CAPABILITIES:
        assert caps[
            capability_id
        ].requires_confirmation is True

    # Read-only operations.
    read_cases = [
        (
            "calendar.list",
            {},
        ),
        (
            "calendar.search_events",
            {
                "query": {
                    "calendar_id": "cal-main",
                    "text": "Synthetic",
                    "time_min": "2026-08-27T00:00:00+02:00",
                    "time_max": "2026-08-28T00:00:00+02:00",
                }
            },
        ),
        (
            "calendar.read_event",
            {"event_id": "evt-001"},
        ),
        (
            "calendar.free_busy",
            {
                "calendar_id": "cal-main",
                "time_min": "2026-08-27T00:00:00+02:00",
                "time_max": "2026-08-28T00:00:00+02:00",
            },
        ),
    ]

    for capability_id, params in read_cases:
        result = registry.execute_integration(
            IntegrationRequest.create(
                provider_id="calendar.provider",
                capability_id=capability_id,
                params=params,
                origin="calendar.synthetic.read",
            )
        )
        assert result.status == "succeeded", (
            capability_id,
            result.status,
            result.error,
        )

    free_busy = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.free_busy",
            params={
                "calendar_id": "cal-main",
                "time_min": "2026-08-27T09:30:00+02:00",
                "time_max": "2026-08-27T10:30:00+02:00",
            },
            origin="calendar.synthetic.freebusy",
        )
    )
    assert free_busy.status == "succeeded"
    busy = free_busy.output["free_busy"]["busy"]
    assert busy == [
        {
            "start": "2026-08-27T10:00:00+02:00",
            "end": "2026-08-27T10:30:00+02:00",
        }
    ]

    # Every side-effecting Calendar operation pauses first.
    write_cases = [
        (
            "calendar.create_event",
            {
                "event_id": "evt-create",
                "calendar_id": "cal-main",
                "title": "Created",
                "start": "2026-08-28T09:00:00+02:00",
                "end": "2026-08-28T09:30:00+02:00",
                "timezone": "Europe/Paris",
                "attendees": [
                    {"address": "boris@example.invalid"}
                ],
            },
        ),
        (
            "calendar.update_event",
            {
                "event_id": "evt-001",
                "changes": {
                    "title": "Updated meeting",
                },
            },
        ),
        (
            "calendar.respond_invitation",
            {
                "event_id": "evt-001",
                "attendee_address": "boris@example.invalid",
                "response_status": "accepted",
            },
        ),
    ]

    for capability_id, params in write_cases:
        request = IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id=capability_id,
            params=params,
            origin="calendar.synthetic.write",
        )

        before_calls = len(backend.calls)

        waiting = registry.execute_integration(
            request,
            user_confirmed=False,
        )
        assert waiting.status == "waiting_confirmation"
        assert len(backend.calls) == before_calls

        waiting_receipt = receipts.get_receipt(
            waiting.receipt_id
        )
        assert waiting_receipt.confirmation_state == "pending"

        confirmed = registry.execute_integration(
            request,
            user_confirmed=True,
        )
        assert confirmed.status == "succeeded"
        assert confirmed.receipt_id == waiting.receipt_id
        assert len(backend.calls) == before_calls + 1

    # Delete after prior writes.
    delete_request = IntegrationRequest.create(
        provider_id="calendar.provider",
        capability_id="calendar.delete_event",
        params={"event_id": "evt-create"},
        origin="calendar.synthetic.delete",
    )
    before_delete = len(backend.calls)
    waiting_delete = registry.execute_integration(
        delete_request
    )
    assert waiting_delete.status == "waiting_confirmation"
    assert len(backend.calls) == before_delete
    confirmed_delete = registry.execute_integration(
        delete_request,
        user_confirmed=True,
    )
    assert confirmed_delete.status == "succeeded"
    assert confirmed_delete.receipt_id == waiting_delete.receipt_id
    assert len(backend.calls) == before_delete + 1

    # Unknown event/calendar fail closed as failed result with no output.
    missing_event = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.read_event",
            params={"event_id": "missing-event"},
            origin="calendar.synthetic.missing",
        )
    )
    assert missing_event.status == "failed"
    assert missing_event.ok is False
    assert missing_event.output is None
    assert missing_event.error == "CalendarLookupError"

    missing_calendar = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.free_busy",
            params={
                "calendar_id": "missing-calendar",
                "time_min": "2026-08-27T00:00:00+02:00",
                "time_max": "2026-08-28T00:00:00+02:00",
            },
            origin="calendar.synthetic.missing",
        )
    )
    assert missing_calendar.status == "failed"
    assert missing_calendar.output is None
    assert missing_calendar.error == "CalendarLookupError"

    # Unknown capability denied before backend call.
    before_unknown = len(backend.calls)
    unknown = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.force_delete",
            params={"event_id": "evt-001"},
            origin="calendar.synthetic.unknown",
        )
    )
    assert unknown.status == "denied"
    assert len(backend.calls) == before_unknown

    # Security exception must fail closed.
    secure_db = Path(td) / "secure.db"
    secure_backend = SyntheticCalendarBackend(
        calendars=(calendar,),
        events=(event,),
    )
    secure_registry = IntegrationRegistry(
        security_engine=ExplodingSecurity(),
        receipt_service=ActionReceiptService(
            store=ActionReceiptStore(secure_db)
        ),
    )
    secure_registry.register_provider(
        CalendarProvider(
            backend=secure_backend
        )
    )

    before_secure = len(secure_backend.calls)
    secure_result = secure_registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.read_event",
            params={"event_id": "evt-001"},
            origin="calendar.synthetic.security",
        )
    )
    assert secure_result.status == "denied"
    assert len(secure_backend.calls) == before_secure

    # Credential-like values must never be persisted raw by receipts.
    secret = "CALENDAR-TOKEN-SECRET-987"
    secret_result = registry.execute_integration(
        IntegrationRequest.create(
            provider_id="calendar.provider",
            capability_id="calendar.search_events",
            params={
                "query": {
                    "calendar_id": "cal-main",
                    "text": "Synthetic",
                },
                "token": secret,
                "credential": secret,
            },
            origin="calendar.synthetic.secret",
        )
    )
    assert secret_result.status == "succeeded"
    assert secret.encode("utf-8") not in db.read_bytes()

    health = registry.health_snapshot(
        "calendar.provider"
    )
    assert len(health) == 1
    assert health[0].available is True

    db.unlink()
    assert not db.exists()
    secure_db.unlink()
    assert not secure_db.exists()

print("[PASS] Calendar Provider v0.9.2 synthetic lifecycle invariant")
raise SystemExit(0)
