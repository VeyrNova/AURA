from aura_native.reminders.window_state import WindowState
from aura_native.reminders.notification_contract import NotificationCapability, NotificationResult, notification_id
class NotificationCoordinator:
    def __init__(self, center, window_state, windows_notifier=None): self.center=center; self.window_state=window_state; self.windows=windows_notifier
    def notify(self, reminder, *, is_missed=False):
        ident=notification_id(reminder, is_missed=is_missed)
        if not ident:
            return NotificationResult(False, NotificationCapability.ERROR, "", "none", reason="identity_required")
        state=self.window_state.state
        channel='internal'; result=None; attempted_windows=False
        if state in (WindowState.INACTIVE,WindowState.MINIMIZED,WindowState.HIDDEN) and self.windows:
            attempted_windows=True
            result=self.windows.notify(reminder,is_missed=is_missed)
            if bool(getattr(result, "accepted", result)): channel='windows'
        if result is None or not bool(getattr(result, "accepted", result)):
            center_result=self.center.enqueue(reminder, is_missed=is_missed)
            accepted=True if center_result is None else bool(getattr(center_result, "accepted", center_result))
            if accepted: channel='internal_fallback' if attempted_windows else 'internal'
            if hasattr(center_result, "accepted"):
                result=center_result if not attempted_windows else NotificationResult(center_result.accepted, center_result.capability, ident, channel, center_result.source, center_result.reason)
            else:
                result=NotificationResult(accepted, NotificationCapability.SUPPORTED if accepted else NotificationCapability.UNAVAILABLE, ident, channel)
        print(f'REMINDER_CHANNEL_SELECTED channel={channel} window_state={state.value}', flush=True)
        if channel == 'windows': print('WINDOWS_REMINDER_NOTIFY success=true', flush=True)
        return result
