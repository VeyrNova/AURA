from pathlib import Path
from aura_native.reminders.notification_contract import (
    NotificationCapability, NotificationResult, notification_id,
)
class QtWindowsReminderNotifier:
    def __init__(self, icon_path=None, tray=None):
        self.tray=tray; self.icon_path=icon_path
    def set_tray(self, tray): self.tray=tray
    def capability(self):
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            if self.tray is None or not QSystemTrayIcon.isSystemTrayAvailable() or not self.tray.supportsMessages():
                return NotificationCapability.UNAVAILABLE
            return NotificationCapability.SUPPORTED
        except Exception:
            return NotificationCapability.ERROR
    def notify(self, reminder, *, is_missed=False):
        ident=notification_id(reminder, is_missed=is_missed)
        if not ident:
            return NotificationResult(False, NotificationCapability.ERROR, "", "windows", reason="identity_required")
        capability=self.capability()
        if capability is not NotificationCapability.SUPPORTED:
            return NotificationResult(False, capability, ident, "windows", reason="backend_unavailable")
        try:
            from PySide6.QtWidgets import QSystemTrayIcon
            title='AURA · RAPPEL MANQUÉ' if is_missed else 'AURA · RAPPEL'
            self.tray.showMessage(title, str(reminder.get('content','')), QSystemTrayIcon.Information, 10000)
            return NotificationResult(True, capability, ident, "windows")
        except Exception as exc:
            return NotificationResult(False, NotificationCapability.ERROR, ident, "windows", reason=type(exc).__name__)
