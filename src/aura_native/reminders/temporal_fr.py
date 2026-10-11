"""Deterministic French reminder time parsing for the local product."""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

PARIS = None
DAYPART_DEFAULTS = {"matin": 8, "apres-midi": 15, "soir": 19}
WEEKDAYS = {"lundi": 0, "mardi": 1, "mercredi": 2, "jeudi": 3, "vendredi": 4, "samedi": 5, "dimanche": 6}

@dataclass(frozen=True)
class TemporalParseResult:
    status: str
    value: datetime | None = None
    source_kind: str = ""
    precision: str = ""
    error: str = ""

    @property
    def trigger_at(self):
        return self.value.strftime("%Y-%m-%dT%H:%M") if self.value else None

def _fold(text: str) -> str:
    text = unicodedata.normalize("NFD", str(text or "").casefold())
    return "".join(c for c in text if unicodedata.category(c) != "Mn").replace("’", "'")

def _paris():
    # Lazy resolution keeps the native core importable in the stdlib-only
    # Lot-1 validator, where tzdata is intentionally not installed.
    return ZoneInfo("Europe/Paris")

def _time(text: str):
    m = re.search(r"\b([01]?\d|2[0-3])h(?:([0-5]\d))?\b", _fold(text))
    return (int(m.group(1)), int(m.group(2) or 0), m) if m else None

def _aware(dt: datetime, now: datetime) -> datetime:
    return dt.replace(tzinfo=dt.tzinfo or now.tzinfo or _paris(), fold=0)

def parse_french_temporal(text: str, *, now: datetime | None = None) -> TemporalParseResult:
    """Parse a temporal phrase; never performs I/O or mutates a repository."""
    paris = _paris()
    now = (now or datetime.now(paris)).astimezone(paris)
    s = _fold(text).strip()
    if not s:
        return TemporalParseResult("NEEDS_TIME", error="time_required")
    if re.search(r"tous les |chaque ", s):
        return TemporalParseResult("UNSUPPORTED_RECURRENCE", error="recurrence_not_supported")
    tm = _time(s)
    if re.search(r"\b(31\s+fevrier|32\s+janvier)\b", s) or re.search(r"\b(?:[3-9]\d)\s+", s):
        return TemporalParseResult("INVALID_DATE", error="invalid_date")
    # ISO and numeric day/month forms.
    dm = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{4}))?\b", s)
    month_name = re.search(r"\b(\d{1,2})\s+(janvier|fevrier|mars|avril|mai|juin|juillet|aout|septembre|octobre|novembre|decembre)\b", s)
    iso = re.search(r"\b(\d{4})-(\d{2})-(\d{2})[t ](\d{2}):(\d{2})\b", s)
    if iso:
        try: dt = datetime(*map(int, iso.groups()), tzinfo=paris)
        except ValueError: return TemporalParseResult("INVALID_DATE", error="invalid_datetime")
        if dt <= now: return TemporalParseResult("INVALID_PAST_TIME", error="past_time")
        return TemporalParseResult("OK", dt, "absolute", "minute")
    if dm or month_name:
        if not tm: return TemporalParseResult("NEEDS_TIME", error="time_required")
        if dm: day, month, year = int(dm.group(1)), int(dm.group(2)), int(dm.group(3) or now.year)
        else:
            names = {n:i for i,n in enumerate(('janvier','fevrier','mars','avril','mai','juin','juillet','aout','septembre','octobre','novembre','decembre'),1)}
            day, month, year = int(month_name.group(1)), names[month_name.group(2)], now.year
        try: dt = datetime(year, month, day, tm[0], tm[1], tzinfo=paris)
        except ValueError: return TemporalParseResult("INVALID_DATE", error="invalid_date")
        if dt <= now: return TemporalParseResult("INVALID_PAST_TIME", error="past_time")
        return TemporalParseResult("OK", dt, "absolute", "minute")
    rel = re.search(r"dans\s+(\d+)\s+(minutes?|heures?|jours?|semaines?)\b", s)
    if rel:
        amount, unit = int(rel.group(1)), rel.group(2)
        if amount <= 0: return TemporalParseResult("INVALID_DURATION", error="invalid_duration")
        mult = 60 if unit.startswith("minute") else 3600 if unit.startswith("heure") else 86400 if unit.startswith("jour") else 604800
        return TemporalParseResult("OK", now + timedelta(seconds=amount * mult), "relative", "minute")
    rel_one = re.search(r"dans\s+une\s+(heure|semaine)\b", s)
    if rel_one:
        return TemporalParseResult("OK", now + timedelta(seconds=3600 if rel_one.group(1)=="heure" else 604800), "relative", "minute")
    # Dayparts have their own deterministic product defaults and must be
    # recognized before the generic ``demain`` branch.
    for phrase, hour in (("demain matin",8),("demain apres-midi",15),("demain soir",19)):
        if phrase in s:
            return TemporalParseResult("OK", (now+timedelta(days=1)).replace(hour=hour,minute=0,second=0,microsecond=0), "daypart", "hour")
    for phrase, hour in (("ce matin",8),("cet apres-midi",15),("ce soir",19)):
        if phrase in s:
            dt = now.replace(hour=hour,minute=0,second=0,microsecond=0)
            if dt <= now: return TemporalParseResult("INVALID_PAST_TIME", error="daypart_passed")
            return TemporalParseResult("OK", dt, "daypart", "hour")
    day_offset = 0
    if "apres-demain" in s: day_offset = 2
    elif "demain" in s: day_offset = 1
    elif "aujourd'hui" in s or "aujourd hui" in s: day_offset = 0
    if day_offset or "aujourd'hui" in s or "aujourd hui" in s:
        if not tm: return TemporalParseResult("NEEDS_TIME", error="time_required")
        dt = (now + timedelta(days=day_offset)).replace(hour=tm[0], minute=tm[1], second=0, microsecond=0)
        if dt <= now: return TemporalParseResult("INVALID_PAST_TIME", error="past_time")
        return TemporalParseResult("OK", dt, "relative_day", "minute")
    for name, weekday in WEEKDAYS.items():
        if re.search(rf"\b{name}\b", s):
            if not tm: return TemporalParseResult("NEEDS_TIME", error="time_required")
            delta = (weekday - now.weekday()) % 7
            if delta == 0: delta = 7
            if "prochain" in s: delta += 7
            dt = (now + timedelta(days=delta)).replace(hour=tm[0], minute=tm[1], second=0, microsecond=0)
            return TemporalParseResult("OK", dt, "weekday", "minute")
    if tm:
        dt = now.replace(hour=tm[0], minute=tm[1], second=0, microsecond=0)
        if dt <= now: dt += timedelta(days=1)
        return TemporalParseResult("OK", dt, "time_only", "minute")
    return TemporalParseResult("NEEDS_TIME", error="time_required")
