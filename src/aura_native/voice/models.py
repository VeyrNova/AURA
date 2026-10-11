from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class VoiceState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    TRANSCRIBING = "transcribing"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"


@dataclass(frozen=True)
class VoiceEvent:
    kind: str
    state: VoiceState
    transcript: str = ""
    error: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class VoiceResult:
    accepted: bool
    state: VoiceState
    transcript: str = ""
    intent: str | None = None
    requires_confirmation: bool = False
    message: str = ""
    error: str = ""
