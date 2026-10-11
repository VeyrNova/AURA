from .models import SystemActionRequest, SystemActionResult, SystemActionType
from .windows_adapter import WindowsSystemAdapter

MUTATING = {SystemActionType.FOCUS_WINDOW, SystemActionType.MINIMIZE_WINDOW, SystemActionType.MAXIMIZE_WINDOW}

class SystemControlService:
    def __init__(self, adapter=None): self.adapter = adapter or WindowsSystemAdapter()
    def execute(self, request: SystemActionRequest):
        if not isinstance(getattr(request, "action", None), SystemActionType):
            return SystemActionResult(getattr(request, "request_id", ""), "UNAVAILABLE", "", error="unsupported_action")
        if not isinstance(request, SystemActionRequest) or not request.validate():
            return SystemActionResult(getattr(request, "request_id", ""), "INVALID_TARGET", "", error="invalid_target")
        if request.action in MUTATING and not request.confirmed:
            return SystemActionResult(request.request_id, "CONFIRMATION_REQUIRED", request.action.value)
        try:
            result = self.adapter.execute(request)
            return SystemActionResult(request.request_id, str(result.get("status", "FAILED")), request.action.value, result.get("data"))
        except Exception as exc:
            return SystemActionResult(request.request_id, "FAILED", request.action.value, error=type(exc).__name__)
