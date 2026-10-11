from __future__ import annotations
from dataclasses import dataclass, asdict

@dataclass(frozen=True)
class Contact:
    contact_id: str
    display_name: str
    emails: tuple[str, ...] = ()
    phones: tuple[str, ...] = ()
    organization: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    version: int = 1

    def to_dict(self) -> dict:
        d = asdict(self)
        d["emails"] = list(self.emails); d["phones"] = list(self.phones)
        return d
