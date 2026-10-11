from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4

@dataclass(frozen=True)
class IntentResult:
    intent: str | None
    original_text: str
    normalized_text: str
    slots: dict = field(default_factory=dict)
    deterministic: bool = False
    requires_confirmation: bool = False
    source: str = "keyboard"
    request_id: str = field(default_factory=lambda: str(uuid4()))
    voice_request_id: str = ""

    @property
    def recognized(self): return bool(self.intent)

    @property
    def intent_type(self): return self.intent
