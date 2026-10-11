from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class DocumentItem:
    name: str
    path: str
    kind: str
    size: int
    modified_at: str
    extension: str
    readable: bool
    writable: bool

    def to_dict(self): return asdict(self)


@dataclass(frozen=True)
class TextDocument:
    path: str
    content: str
    size: int
    fingerprint: str

    def to_dict(self): return asdict(self)
