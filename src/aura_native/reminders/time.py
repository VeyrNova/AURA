from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

PARIS = None

def _paris():
    # Resolve timezone data only when reminder wall-clock conversion is used.
    # This keeps the stdlib-only core importable under isolated -S validation.
    return ZoneInfo("Europe/Paris")

def local_trigger_to_utc(value):
    raw = str(value or "").strip()
    naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M")
    # Deterministic fold=0. For a spring gap, ZoneInfo maps each invalid
    # wall-minute forward by the gap size (02:30 -> 03:30). The policy is
    # instead the first valid wall-minute after the gap (03:00), so scan the
    # local wall clock from the start of that hour until round-trip identity.
    paris = _paris()
    aware = naive.replace(tzinfo=paris, fold=0)
    roundtrip = aware.astimezone(timezone.utc).astimezone(paris).replace(tzinfo=None)
    if roundtrip != naive:
        candidate = naive.replace(minute=0, second=0, microsecond=0)
        for _ in range(240):
            probe = candidate.replace(tzinfo=paris, fold=0)
            if probe.astimezone(timezone.utc).astimezone(paris).replace(tzinfo=None) == candidate:
                aware = probe
                break
            candidate += timedelta(minutes=1)
    return aware.astimezone(timezone.utc)

class ProductionClock:
    def now_utc(self): return datetime.now(timezone.utc)

class FakeClock:
    def __init__(self, value): self.value = value.astimezone(timezone.utc)
    def now_utc(self): return self.value
    def set(self, value): self.value = value.astimezone(timezone.utc)
