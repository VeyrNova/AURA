from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from googleapiclient.discovery import build

from integrations.calendar.provider import (
    CalendarAttendee,
    CalendarEvent,
    CalendarFreeBusy,
    CalendarInfo,
    CalendarLookupError,
    CalendarQuery,
    CalendarReminder,
    CalendarResult,
    CalendarValidationError,
)
from runtime.connected_accounts_v120 import (
    get_connected_accounts_service_v120,
)


def _default_for(name: str):
    low = name.lower()
    if low.startswith(("is_", "has_", "can_")) or low in {"primary", "all_day", "read", "trashed"}:
        return False
    if low.endswith(("s", "_ids", "_emails", "_phones", "_labels", "_attachments", "_messages", "_items", "_results")):
        return ()
    if low in {"count", "total", "size", "size_bytes", "minutes"}:
        return 0
    return ""

def _make(cls, values):
    import inspect
    sig = inspect.signature(cls)
    kwargs = {}
    for name, param in sig.parameters.items():
        if name in values:
            kwargs[name] = values[name]
        elif param.default is inspect._empty:
            kwargs[name] = _default_for(name)
    return cls(**kwargs)

def _value(obj, *names, default=None):
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _event(raw):
    start = raw.get("start", {}) or {}
    end = raw.get("end", {}) or {}
    attendees = tuple(
        _make(
            CalendarAttendee,
            {
                "email": str(x.get("email", "")),
                "display_name": str(x.get("displayName", "")),
                "name": str(x.get("displayName", "")),
                "response_status": str(x.get("responseStatus", "")),
                "status": str(x.get("responseStatus", "")),
                "optional": bool(x.get("optional", False)),
            },
        )
        for x in raw.get("attendees", []) or []
    )
    reminders = tuple(
        _make(
            CalendarReminder,
            {
                "method": str(x.get("method", "")),
                # AURA_V123_CALENDAR_REMINDER_FIELD_MAPPING_FIX
                "minutes_before": int(x.get("minutes", 0) or 0),
            },
        )
        for x in (raw.get("reminders", {}) or {}).get("overrides", []) or []
    )
    values = {
        "event_id": str(raw.get("id", "")),
        "id": str(raw.get("id", "")),
        "calendar_id": "primary",
        "title": str(raw.get("summary", "")),
        "summary": str(raw.get("summary", "")),
        "description": str(raw.get("description", "")),
        "location": str(raw.get("location", "")),
        "start": start.get("dateTime") or start.get("date") or "",
        "start_at": start.get("dateTime") or start.get("date") or "",
        "end": end.get("dateTime") or end.get("date") or "",
        "end_at": end.get("dateTime") or end.get("date") or "",
        "timezone": start.get("timeZone") or end.get("timeZone") or "",
        "all_day": bool(start.get("date") and not start.get("dateTime")),
        "attendees": attendees,
        "reminders": reminders,
        "status": str(raw.get("status", "")),
        "html_link": str(raw.get("htmlLink", "")),
        "organizer": str((raw.get("organizer", {}) or {}).get("email", "")),
    }
    return _make(CalendarEvent, values)

class GoogleLiveCalendarBackendV121:
    mode = "GOOGLE_LIVE"

    def __init__(self, *, service=None, api_factory=build):
        self.service = service or get_connected_accounts_service_v120()
        self.api_factory = api_factory

    def _account(self):
        rows = self.service.list_accounts("google")
        if not rows:
            raise CalendarLookupError("Google account is not connected")
        return rows[0]

    def _calendar(self):
        account = self._account()
        credentials = self.service._credentials(account)
        return self.api_factory(
            "calendar",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

    def list_calendars(self):
        result = self._calendar().calendarList().list().execute()
        return tuple(
            _make(
                CalendarInfo,
                {
                    "calendar_id": str(x.get("id", "")),
                    "id": str(x.get("id", "")),
                    "name": str(x.get("summary", "")),
                    "summary": str(x.get("summary", "")),
                    "description": str(x.get("description", "")),
                    "timezone": str(x.get("timeZone", "")),
                    "primary": bool(x.get("primary", False)),
                    "access_role": str(x.get("accessRole", "")),
                    "color": str(x.get("backgroundColor", "")),
                },
            )
            for x in result.get("items", []) or []
        )

    def search_events(self, query):
        text = _value(query, "text", "query", "search", default="")
        calendar_id = _value(query, "calendar_id", default="primary") or "primary"
        # AURA_V122_GOOGLE_LIVE_PROVIDER_CONTRACT_COMPAT
        # "cal-main" is AURA synthetic logical default; Google uses "primary".
        if isinstance(query, CalendarQuery) and str(calendar_id).strip().lower() == "cal-main":
            calendar_id = "primary"
        time_min = _value(query, "time_min", "start", "from_", default=None)
        time_max = _value(query, "time_max", "end", "to", default=None)
        limit = int(_value(query, "limit", "max_results", default=50) or 50)
        kwargs = {
            "calendarId": str(calendar_id),
            "maxResults": max(1, min(limit, 250)),
            "singleEvents": True,
            "orderBy": "startTime",
        }
        if text:
            kwargs["q"] = str(text)
        if time_min:
            kwargs["timeMin"] = str(time_min)
        else:
            kwargs["timeMin"] = datetime.now(timezone.utc).isoformat()
        if time_max:
            kwargs["timeMax"] = str(time_max)
        response = self._calendar().events().list(**kwargs).execute()
        events = tuple(_event(x) for x in response.get("items", []) or [])
        result = _make(
            CalendarResult,
            {
                "events": events,
                "items": events,
                "results": events,
                "total": len(events),
                "count": len(events),
                "query": text,
                "next_page_token": response.get("nextPageToken", ""),
            },
        )
        # CalendarProvider expects a sequence of CalendarEvent for CalendarQuery.
        # Preserve CalendarResult for historical direct dict probes.
        return events if isinstance(query, CalendarQuery) else result

    def get_event(self, event_id):
        raw = self._calendar().events().get(
            calendarId="primary",
            eventId=str(event_id),
        ).execute()
        return _event(raw)

    def free_busy(self, *args, **kwargs):
        calendars = kwargs.get("calendar_ids") or kwargs.get("calendars") or ["primary"]
        time_min = kwargs.get("time_min") or kwargs.get("start") or datetime.now(timezone.utc).isoformat()
        time_max = kwargs.get("time_max") or kwargs.get("end")
        if not time_max:
            from datetime import timedelta
            time_max = (datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
        raw = self._calendar().freebusy().query(
            body={
                "timeMin": str(time_min),
                "timeMax": str(time_max),
                "items": [{"id": str(x)} for x in calendars],
            }
        ).execute()
        busy = []
        for calendar_id, data in (raw.get("calendars", {}) or {}).items():
            for item in data.get("busy", []) or []:
                busy.append({"calendar_id": calendar_id, **item})
        return _make(
            CalendarFreeBusy,
            {
                "time_min": str(time_min),
                "time_max": str(time_max),
                "busy": tuple(busy),
                "intervals": tuple(busy),
                "calendars": tuple(str(x) for x in calendars),
            },
        )

    @staticmethod
    def _event_body(event=None, **kwargs):
        title = kwargs.get("title", kwargs.get("summary", _value(event, "title", "summary", default="")))
        description = kwargs.get("description", _value(event, "description", default=""))
        location = kwargs.get("location", _value(event, "location", default=""))
        start = kwargs.get("start", kwargs.get("start_at", _value(event, "start", "start_at", default="")))
        end = kwargs.get("end", kwargs.get("end_at", _value(event, "end", "end_at", default="")))
        timezone_name = kwargs.get("timezone", _value(event, "timezone", default=""))
        attendees = kwargs.get("attendees", _value(event, "attendees", default=()))
        body = {
            "summary": str(title),
            "description": str(description or ""),
            "location": str(location or ""),
            "start": {"dateTime": str(start)},
            "end": {"dateTime": str(end)},
        }
        if timezone_name:
            body["start"]["timeZone"] = str(timezone_name)
            body["end"]["timeZone"] = str(timezone_name)
        if attendees:
            body["attendees"] = [
                {"email": str(_value(x, "email", default=x))}
                for x in attendees
                if str(_value(x, "email", default=x))
            ]
        return body

    def create_event(self, event=None, **kwargs):
        raw = self._calendar().events().insert(
            calendarId=str(kwargs.get("calendar_id", "primary")),
            body=self._event_body(event, **kwargs),
            sendUpdates="all",
        ).execute()
        return _event(raw)

    def update_event(self, *args, **kwargs):
        event_id = str(kwargs.get("event_id") or (args[0] if args else ""))
        event = kwargs.get("event")
        raw = self._calendar().events().patch(
            calendarId=str(kwargs.get("calendar_id", "primary")),
            eventId=event_id,
            body=self._event_body(event, **kwargs),
            sendUpdates="all",
        ).execute()
        return _event(raw)

    def delete_event(self, event_id):
        self._calendar().events().delete(
            calendarId="primary",
            eventId=str(event_id),
            sendUpdates="all",
        ).execute()
        return True

    def respond_invitation(self, *args, **kwargs):
        event_id = str(kwargs.get("event_id") or (args[0] if args else ""))
        response = str(kwargs.get("response", kwargs.get("status", "accepted"))).lower()
        if response not in {"accepted", "declined", "tentative"}:
            raise CalendarValidationError("invalid invitation response")
        raw = self._calendar().events().get(
            calendarId="primary",
            eventId=event_id,
        ).execute()
        account = self._account().display_label.lower()
        attendees = raw.get("attendees", []) or []
        for attendee in attendees:
            if str(attendee.get("email", "")).lower() == account:
                attendee["responseStatus"] = response
        updated = self._calendar().events().patch(
            calendarId="primary",
            eventId=event_id,
            body={"attendees": attendees},
            sendUpdates="all",
        ).execute()
        return _event(updated)

    def health_snapshot(self):
        account = self._account()
        return {
            "health_state": "google-live-ready",
            "mode": self.mode,
            "provider": "google",
            "account": account.display_label,
            "network_on_demand": True,
        }

__all__ = ["GoogleLiveCalendarBackendV121"]
