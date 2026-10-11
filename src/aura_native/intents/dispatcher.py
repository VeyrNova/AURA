from __future__ import annotations
from dataclasses import dataclass, field
from .models import IntentResult
@dataclass(frozen=True)
class DispatchResult:
    handled: bool
    intent: str | None = None
    route: str | None = None
    slots: dict = field(default_factory=dict)
    requires_confirmation: bool = False
    message: str = ''
    result_type: str = 'UNSUPPORTED'
    data: dict = field(default_factory=dict)
class NativeActionDispatcher:
    """Maps recognized intents to injected, testable handlers; no Legacy imports."""
    ROUTES={'OPEN_MODULE': 'module','DOCUMENTS_LIST':'documents','LIST_NOTES':'notes','LIST_TASKS':'tasks','LIST_REMINDERS':'reminders','CONTACT_SEARCH':'contacts','WEATHER_QUERY':'weather','WEB_SEARCH':'search'}
    def __init__(self, handlers=None, prepared_action_factory=None, local_product=None): self.handlers=dict(handlers or {}); self.prepared_action_factory=prepared_action_factory; self.local_product=local_product
    def dispatch(self,result:IntentResult):
        if not result.recognized:return DispatchResult(False)
        if self.local_product is not None and result.intent in self.local_product.INTENTS:
            return self.local_product.dispatch(result)
        handler=self.handlers.get(result.intent)
        if handler is not None:
            value=handler(result.slots); return DispatchResult(True,result.intent,slots=result.slots,requires_confirmation=result.requires_confirmation,message=str(value or ''),result_type='HANDLED')
        if result.requires_confirmation and result.intent.startswith('PC_'):
            if self.prepared_action_factory is None:
                return DispatchResult(False,result.intent,slots=result.slots,requires_confirmation=True,result_type='UNAVAILABLE',message='window target resolver unavailable')
            action=self.prepared_action_factory(result)
            return DispatchResult(True,result.intent,slots=result.slots,requires_confirmation=True,message=str(getattr(action,'summary','')),result_type='PREPARED_ACTION_CREATED')
        route=self.ROUTES.get(result.intent)
        if route: return DispatchResult(True,result.intent,route,result.slots,result.requires_confirmation,result_type='NAVIGATED')
        return DispatchResult(False,result.intent,slots=result.slots,requires_confirmation=result.requires_confirmation,result_type='UNSUPPORTED')
