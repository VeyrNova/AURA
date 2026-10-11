from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4

class SystemActionType(str, Enum):
    DISCOVER_WINDOWS = "discover_windows"
    DISCOVER_PROCESSES = "discover_processes"
    GET_FOREGROUND_WINDOW = "get_foreground_window"
    FOCUS_WINDOW = "focus_window"
    MINIMIZE_WINDOW = "minimize_window"
    MAXIMIZE_WINDOW = "maximize_window"

class SystemAction(str, Enum):
    R0 = "R0"
    R1 = "R1"

@dataclass(frozen=True)
class SystemActionRequest:
    action: SystemActionType
    target: dict = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: str(uuid4()))
    confirmed: bool = False
    def validate(self):
        if self.action in {SystemActionType.FOCUS_WINDOW, SystemActionType.MINIMIZE_WINDOW, SystemActionType.MAXIMIZE_WINDOW}:
            if int(self.target.get("hwnd", 0)) <= 0 or not str(self.target.get("title", "")):
                return False
        return True

@dataclass(frozen=True)
class SystemActionResult:
    request_id: str
    status: str
    action: str
    data: object = None
    error: str = ""
