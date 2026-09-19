"""AURA v0.9.2 provider-neutral Calendar integration.

No Google Calendar, Microsoft Graph, CalDAV, OAuth, external network client,
or real-account connection exists in this module. CalendarProvider translates
normalized Calendar operations to an injected CalendarBackend while
IntegrationRegistry remains the integration execution authority.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, timezone
from typing import Any, Mapping, Optional, Protocol, Sequence, runtime_checkable

from integrations.registry import (
    IntegrationCapability,
    IntegrationManifest,
    IntegrationRequest,
)

READ_CAPABILITIES = (
    "calendar.list",
    "calendar.search_events",
    "calendar.read_event",
    "calendar.free_busy",
)

WRITE_CAPABILITIES = (
    "calendar.create_event",
    "calendar.update_event",
    "calendar.delete_event",
    "calendar.respond_invitation",
)

CONFIRMATION_CAPABILITIES = WRITE_CAPABILITIES
CALENDAR_CAPABILITIES = READ_CAPABILITIES + WRITE_CAPABILITIES


class CalendarProviderError(RuntimeError):
    pass


class CalendarValidationError(CalendarProviderError):
    pass


class CalendarLookupError(CalendarProviderError):
    pass


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _stable_id(prefix: str, *parts: Any) -> str:
    return prefix + hashlib.sha256(
        _canonical_json(parts).encode("utf-8")
    ).hexdigest()[:24]


def _parse_datetime(value: str) -> datetime:
    text = str(value).strip()
    if not text:
        raise CalendarValidationError("datetime is required")
    parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise CalendarValidationError("datetime must be timezone-aware")
    return parsed


def _validate_date(value: str) -> str:
    text = str(value).strip()
    date.fromisoformat(text)
    return text


@dataclass(frozen=True)
class CalendarInfo:
    calendar_id: str
    name: str
    timezone: str
    primary: bool = False

    def __post_init__(self) -> None:
        if not self.calendar_id.strip():
            raise CalendarValidationError("calendar_id is required")
        if not self.name.strip():
            raise CalendarValidationError("calendar name is required")
        if not self.timezone.strip():
            raise CalendarValidationError("calendar timezone is required")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarAttendee:
    address: str
    display_name: Optional[str] = None
    response_status: str = "needs_action"
    optional: bool = False

    def __post_init__(self) -> None:
        if "@" not in self.address or not self.address.strip():
            raise CalendarValidationError("invalid attendee address")
        if self.response_status not in {
            "needs_action",
            "accepted",
            "declined",
            "tentative",
        }:
            raise CalendarValidationError("invalid attendee response status")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarReminder:
    method: str
    minutes_before: int

    def __post_init__(self) -> None:
        if self.method not in {"popup", "email", "notification"}:
            raise CalendarValidationError("invalid reminder method")
        if self.minutes_before < 0:
            raise CalendarValidationError("minutes_before must be >= 0")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarEvent:
    event_id: str
    calendar_id: str
    title: str
    start: str
    end: str
    timezone: str
    all_day: bool = False
    description: str = ""
    location: str = ""
    attendees: tuple[CalendarAttendee, ...] = ()
    reminders: tuple[CalendarReminder, ...] = ()
    recurrence: tuple[str, ...] = ()
    status: str = "confirmed"

    def __post_init__(self) -> None:
        if not self.event_id.strip():
            raise CalendarValidationError("event_id is required")
        if not self.calendar_id.strip():
            raise CalendarValidationError("calendar_id is required")
        if not self.title.strip():
            raise CalendarValidationError("event title is required")
        if not self.timezone.strip():
            raise CalendarValidationError("event timezone is required")

        if self.all_day:
            start_date = date.fromisoformat(_validate_date(self.start))
            end_date = date.fromisoformat(_validate_date(self.end))
            if end_date <= start_date:
                raise CalendarValidationError(
                    "all-day end date must be after start date"
                )
        else:
            start_dt = _parse_datetime(self.start)
            end_dt = _parse_datetime(self.end)
            if end_dt <= start_dt:
                raise CalendarValidationError(
                    "event end must be after start"
                )

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "calendar_id": self.calendar_id,
            "title": self.title,
            "start": self.start,
            "end": self.end,
            "timezone": self.timezone,
            "all_day": self.all_day,
            "description": self.description,
            "location": self.location,
            "attendees": [item.to_dict() for item in self.attendees],
            "reminders": [item.to_dict() for item in self.reminders],
            "recurrence": list(self.recurrence),
            "status": self.status,
        }


@dataclass(frozen=True)
class CalendarQuery:
    calendar_id: Optional[str] = None
    text: str = ""
    time_min: Optional[str] = None
    time_max: Optional[str] = None
    limit: int = 50

    def __post_init__(self) -> None:
        if self.limit < 1 or self.limit > 500:
            raise CalendarValidationError("query limit must be 1..500")
        if self.time_min:
            _parse_datetime(self.time_min)
        if self.time_max:
            _parse_datetime(self.time_max)
        if self.time_min and self.time_max:
            if _parse_datetime(self.time_max) <= _parse_datetime(self.time_min):
                raise CalendarValidationError(
                    "time_max must be after time_min"
                )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalendarFreeBusy:
    calendar_id: str
    time_min: str
    time_max: str
    timezone: str
    busy: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        window_start = _parse_datetime(self.time_min)
        window_end = _parse_datetime(self.time_max)
        if window_end <= window_start:
            raise CalendarValidationError(
                "free/busy window end must be after start"
            )
        for start, end in self.busy:
            if _parse_datetime(end) <= _parse_datetime(start):
                raise CalendarValidationError("invalid busy interval")

    def to_dict(self) -> dict[str, Any]:
        return {
            "calendar_id": self.calendar_id,
            "time_min": self.time_min,
            "time_max": self.time_max,
            "timezone": self.timezone,
            "busy": [
                {"start": start, "end": end}
                for start, end in self.busy
            ],
        }


@dataclass(frozen=True)
class CalendarResult:
    operation: str
    ok: bool
    event_ids: tuple[str, ...] = ()
    calendar_ids: tuple[str, ...] = ()
    detail: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@runtime_checkable
class CalendarBackend(Protocol):
    def list_calendars(self) -> Sequence[CalendarInfo]:
        ...

    def search_events(
        self,
        query: CalendarQuery,
    ) -> Sequence[CalendarEvent]:
        ...

    def get_event(
        self,
        event_id: str,
    ) -> CalendarEvent:
        ...

    def free_busy(
        self,
        *,
        calendar_id: str,
        time_min: str,
        time_max: str,
    ) -> CalendarFreeBusy:
        ...

    def create_event(
        self,
        event: CalendarEvent,
    ) -> CalendarEvent:
        ...

    def update_event(
        self,
        *,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> CalendarEvent:
        ...

    def delete_event(
        self,
        event_id: str,
    ) -> CalendarResult:
        ...

    def respond_invitation(
        self,
        *,
        event_id: str,
        attendee_address: str,
        response_status: str,
    ) -> CalendarEvent:
        ...

    def health_snapshot(self) -> Mapping[str, Any]:
        ...


def _attendee(value: Any) -> CalendarAttendee:
    if isinstance(value, CalendarAttendee):
        return value
    if isinstance(value, str):
        return CalendarAttendee(address=value)
    if isinstance(value, Mapping):
        return CalendarAttendee(
            address=str(value.get("address") or ""),
            display_name=(
                str(value.get("display_name"))
                if value.get("display_name") is not None
                else None
            ),
            response_status=str(
                value.get("response_status") or "needs_action"
            ),
            optional=bool(value.get("optional", False)),
        )
    raise CalendarValidationError("invalid attendee payload")


def _attendees(value: Any) -> tuple[CalendarAttendee, ...]:
    if value is None:
        return ()
    if isinstance(value, (str, Mapping, CalendarAttendee)):
        value = [value]
    if not isinstance(value, (list, tuple, set)):
        raise CalendarValidationError("invalid attendee list")
    return tuple(_attendee(item) for item in value)


def _reminder(value: Any) -> CalendarReminder:
    if isinstance(value, CalendarReminder):
        return value
    if isinstance(value, Mapping):
        return CalendarReminder(
            method=str(value.get("method") or "popup"),
            minutes_before=int(value.get("minutes_before", 0)),
        )
    raise CalendarValidationError("invalid reminder payload")


def _reminders(value: Any) -> tuple[CalendarReminder, ...]:
    if value is None:
        return ()
    if not isinstance(value, (list, tuple, set)):
        raise CalendarValidationError("invalid reminder list")
    return tuple(_reminder(item) for item in value)


def _cap(
    capability_id: str,
    *,
    risk_tier: str,
    requires_confirmation: bool,
    side_effect_class: str,
) -> IntegrationCapability:
    return IntegrationCapability(
        capability_id=capability_id,
        action=capability_id,
        description=capability_id,
        risk_tier=risk_tier,
        requires_confirmation=requires_confirmation,
        side_effect_class=side_effect_class,
        evidence_required=True,
    )


CALENDAR_MANIFEST = IntegrationManifest(
    provider_id="calendar.provider",
    display_name="AURA Calendar Provider",
    provider_version="0.9.2-contract",
    capabilities=(
        _cap(
            "calendar.list",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="read",
        ),
        _cap(
            "calendar.search_events",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="read",
        ),
        _cap(
            "calendar.read_event",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="read",
        ),
        _cap(
            "calendar.free_busy",
            risk_tier="low",
            requires_confirmation=False,
            side_effect_class="read",
        ),
        _cap(
            "calendar.create_event",
            risk_tier="high",
            requires_confirmation=True,
            side_effect_class="external_write",
        ),
        _cap(
            "calendar.update_event",
            risk_tier="high",
            requires_confirmation=True,
            side_effect_class="external_write",
        ),
        _cap(
            "calendar.delete_event",
            risk_tier="high",
            requires_confirmation=True,
            side_effect_class="external_write",
        ),
        _cap(
            "calendar.respond_invitation",
            risk_tier="medium",
            requires_confirmation=True,
            side_effect_class="external_write",
        ),
    ),
    auth_kind="external-provider-owned",
    metadata={
        "provider_neutral": True,
        "real_network_connection": False,
    },
)


class CalendarProvider:
    def __init__(self, *, backend: CalendarBackend):
        if not isinstance(backend, CalendarBackend):
            raise CalendarValidationError(
                "backend does not satisfy CalendarBackend protocol"
            )
        self.backend = backend

    @property
    def manifest(self) -> IntegrationManifest:
        return CALENDAR_MANIFEST

    def health_snapshot(self) -> Mapping[str, Any]:
        try:
            snapshot = dict(self.backend.health_snapshot())
        except Exception:
            return {
                "available": False,
                "health_state": "degraded",
            }
        return {
            "available": bool(snapshot.get("available", True)),
            "health_state": str(
                snapshot.get("health_state", "unknown")
            ),
        }

    def execute(self, request: IntegrationRequest) -> Any:
        capability = request.capability_id
        params = dict(request.params or {})

        if capability == "calendar.list":
            return {
                "calendars": [
                    item.to_dict()
                    for item in self.backend.list_calendars()
                ],
                "evidence_refs": (),
            }

        if capability == "calendar.search_events":
            raw = params.get("query") or {}
            if isinstance(raw, CalendarQuery):
                query = raw
            else:
                query = CalendarQuery(
                    calendar_id=(
                        str(raw.get("calendar_id"))
                        if raw.get("calendar_id")
                        else None
                    ),
                    text=str(raw.get("text") or ""),
                    time_min=(
                        str(raw.get("time_min"))
                        if raw.get("time_min")
                        else None
                    ),
                    time_max=(
                        str(raw.get("time_max"))
                        if raw.get("time_max")
                        else None
                    ),
                    limit=int(raw.get("limit", 50)),
                )
            return {
                "events": [
                    item.to_dict()
                    for item in self.backend.search_events(query)
                ],
                "evidence_refs": (),
            }

        if capability == "calendar.read_event":
            event = self.backend.get_event(
                str(params.get("event_id") or "")
            )
            return {
                "event": event.to_dict(),
                "evidence_refs": (),
            }

        if capability == "calendar.free_busy":
            result = self.backend.free_busy(
                calendar_id=str(
                    params.get("calendar_id") or ""
                ),
                time_min=str(
                    params.get("time_min") or ""
                ),
                time_max=str(
                    params.get("time_max") or ""
                ),
            )
            return {
                "free_busy": result.to_dict(),
                "evidence_refs": (),
            }

        if capability == "calendar.create_event":
            event = CalendarEvent(
                event_id=str(
                    params.get("event_id")
                    or _stable_id(
                        "evt_",
                        params.get("calendar_id"),
                        params.get("title"),
                        params.get("start"),
                        params.get("end"),
                    )
                ),
                calendar_id=str(
                    params.get("calendar_id") or ""
                ),
                title=str(params.get("title") or ""),
                start=str(params.get("start") or ""),
                end=str(params.get("end") or ""),
                timezone=str(
                    params.get("timezone") or ""
                ),
                all_day=bool(
                    params.get("all_day", False)
                ),
                description=str(
                    params.get("description") or ""
                ),
                location=str(
                    params.get("location") or ""
                ),
                attendees=_attendees(
                    params.get("attendees")
                ),
                reminders=_reminders(
                    params.get("reminders")
                ),
                recurrence=tuple(
                    str(item)
                    for item in (
                        params.get("recurrence") or ()
                    )
                ),
                status=str(
                    params.get("status") or "confirmed"
                ),
            )
            created = self.backend.create_event(event)
            return {
                "event": created.to_dict(),
                "evidence_refs": (),
            }

        if capability == "calendar.update_event":
            updated = self.backend.update_event(
                event_id=str(
                    params.get("event_id") or ""
                ),
                changes=dict(
                    params.get("changes") or {}
                ),
            )
            return {
                "event": updated.to_dict(),
                "evidence_refs": (),
            }

        if capability == "calendar.delete_event":
            result = self.backend.delete_event(
                str(params.get("event_id") or "")
            )
            return {
                "result": result.to_dict(),
                "evidence_refs": (),
            }

        if capability == "calendar.respond_invitation":
            event = self.backend.respond_invitation(
                event_id=str(
                    params.get("event_id") or ""
                ),
                attendee_address=str(
                    params.get("attendee_address") or ""
                ),
                response_status=str(
                    params.get("response_status") or ""
                ),
            )
            return {
                "event": event.to_dict(),
                "evidence_refs": (),
            }

        raise CalendarValidationError(
            "unsupported calendar capability"
        )


class SyntheticCalendarBackend:
    """In-memory synthetic calendars/events for v0.9.2 D2 only."""

    def __init__(
        self,
        *,
        calendars: Sequence[CalendarInfo] = (),
        events: Sequence[CalendarEvent] = (),
    ):
        self.calendars = {
            item.calendar_id: item
            for item in calendars
        }
        self.events = {
            item.event_id: item
            for item in events
        }
        self.calls: list[str] = []

    def _calendar(self, calendar_id: str) -> CalendarInfo:
        item = self.calendars.get(calendar_id)
        if item is None:
            raise CalendarLookupError("calendar not found")
        return item

    def _event(self, event_id: str) -> CalendarEvent:
        item = self.events.get(event_id)
        if item is None:
            raise CalendarLookupError("event not found")
        return item

    def list_calendars(self) -> Sequence[CalendarInfo]:
        self.calls.append("list_calendars")
        return tuple(
            self.calendars[key]
            for key in sorted(self.calendars)
        )

    def search_events(
        self,
        query: CalendarQuery,
    ) -> Sequence[CalendarEvent]:
        self.calls.append("search_events")
        if query.calendar_id:
            self._calendar(query.calendar_id)

        time_min = (
            _parse_datetime(query.time_min)
            if query.time_min
            else None
        )
        time_max = (
            _parse_datetime(query.time_max)
            if query.time_max
            else None
        )
        text = query.text.casefold().strip()
        result = []

        for event in self.events.values():
            if (
                query.calendar_id
                and event.calendar_id != query.calendar_id
            ):
                continue

            if text and text not in (
                event.title + "\n" + event.description
            ).casefold():
                continue

            if not event.all_day:
                start_dt = _parse_datetime(event.start)
                end_dt = _parse_datetime(event.end)

                if time_min and end_dt <= time_min:
                    continue
                if time_max and start_dt >= time_max:
                    continue

            result.append(event)

        result.sort(
            key=lambda item: (
                item.start,
                item.event_id,
            )
        )
        return tuple(result[: query.limit])

    def get_event(self, event_id: str) -> CalendarEvent:
        self.calls.append("get_event")
        return self._event(event_id)

    def free_busy(
        self,
        *,
        calendar_id: str,
        time_min: str,
        time_max: str,
    ) -> CalendarFreeBusy:
        self.calls.append("free_busy")
        calendar = self._calendar(calendar_id)
        window_start = _parse_datetime(time_min)
        window_end = _parse_datetime(time_max)

        busy = []
        for event in self.events.values():
            if (
                event.calendar_id != calendar_id
                or event.status == "cancelled"
                or event.all_day
            ):
                continue

            start_dt = _parse_datetime(event.start)
            end_dt = _parse_datetime(event.end)
            if end_dt <= window_start or start_dt >= window_end:
                continue

            busy.append(
                (
                    max(start_dt, window_start).isoformat(),
                    min(end_dt, window_end).isoformat(),
                )
            )

        busy.sort()
        return CalendarFreeBusy(
            calendar_id=calendar_id,
            time_min=time_min,
            time_max=time_max,
            timezone=calendar.timezone,
            busy=tuple(busy),
        )

    def create_event(
        self,
        event: CalendarEvent,
    ) -> CalendarEvent:
        self.calls.append("create_event")
        self._calendar(event.calendar_id)
        if event.event_id in self.events:
            raise CalendarValidationError("event already exists")
        self.events[event.event_id] = event
        return event

    def update_event(
        self,
        *,
        event_id: str,
        changes: Mapping[str, Any],
    ) -> CalendarEvent:
        self.calls.append("update_event")
        source = self._event(event_id)

        allowed = {
            "title",
            "start",
            "end",
            "timezone",
            "all_day",
            "description",
            "location",
            "attendees",
            "reminders",
            "recurrence",
            "status",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise CalendarValidationError(
                "unsupported update fields"
            )

        normalized = dict(changes)
        if "attendees" in normalized:
            normalized["attendees"] = _attendees(
                normalized["attendees"]
            )
        if "reminders" in normalized:
            normalized["reminders"] = _reminders(
                normalized["reminders"]
            )
        if "recurrence" in normalized:
            normalized["recurrence"] = tuple(
                str(item)
                for item in normalized["recurrence"]
            )

        updated = replace(source, **normalized)
        self.events[event_id] = updated
        return updated

    def delete_event(
        self,
        event_id: str,
    ) -> CalendarResult:
        self.calls.append("delete_event")
        self._event(event_id)
        del self.events[event_id]
        return CalendarResult(
            operation="delete_event",
            ok=True,
            event_ids=(event_id,),
        )

    def respond_invitation(
        self,
        *,
        event_id: str,
        attendee_address: str,
        response_status: str,
    ) -> CalendarEvent:
        self.calls.append("respond_invitation")
        source = self._event(event_id)

        if response_status not in {
            "accepted",
            "declined",
            "tentative",
        }:
            raise CalendarValidationError(
                "invalid invitation response"
            )

        updated_attendees = []
        matched = False

        for attendee in source.attendees:
            if (
                attendee.address.casefold()
                == attendee_address.casefold()
            ):
                matched = True
                updated_attendees.append(
                    replace(
                        attendee,
                        response_status=response_status,
                    )
                )
            else:
                updated_attendees.append(attendee)

        if not matched:
            raise CalendarLookupError("attendee not found")

        updated = replace(
            source,
            attendees=tuple(updated_attendees),
        )
        self.events[event_id] = updated
        return updated

    def health_snapshot(self) -> Mapping[str, Any]:
        return {
            "available": True,
            "health_state": "healthy",
        }


__all__ = [
    "READ_CAPABILITIES",
    "WRITE_CAPABILITIES",
    "CONFIRMATION_CAPABILITIES",
    "CALENDAR_CAPABILITIES",
    "CALENDAR_MANIFEST",
    "CalendarProviderError",
    "CalendarValidationError",
    "CalendarLookupError",
    "CalendarInfo",
    "CalendarEvent",
    "CalendarAttendee",
    "CalendarReminder",
    "CalendarQuery",
    "CalendarFreeBusy",
    "CalendarResult",
    "CalendarBackend",
    "CalendarProvider",
    "SyntheticCalendarBackend",
]
