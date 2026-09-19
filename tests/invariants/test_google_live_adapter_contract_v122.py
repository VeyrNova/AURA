from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GMAIL = ROOT / "integrations/google/live_email_backend_v121.py"
CAL = ROOT / "integrations/google/live_calendar_backend_v121.py"
CONTACTS = ROOT / "integrations/google/live_contacts_backend_v121.py"

g = GMAIL.read_text(encoding="utf-8-sig")
c = CAL.read_text(encoding="utf-8-sig")
p = CONTACTS.read_text(encoding="utf-8-sig")

assert "EmailQuery," in g
assert "return messages if isinstance(query, EmailQuery) else result" in g

assert "CalendarQuery," in c
assert 'str(calendar_id).strip().lower() == "cal-main"' in c
assert 'calendar_id = "primary"' in c
assert "return events if isinstance(query, CalendarQuery) else result" in c

assert "ContactQuery," in p
assert "return contacts if isinstance(query, ContactQuery) else result" in p

for text in (g, c, p):
    assert "# AURA_V122_GOOGLE_LIVE_PROVIDER_CONTRACT_COMPAT" in text

print("[PASS] v1.2.2 Google LIVE adapter provider-contract compatibility invariant")
