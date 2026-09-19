"""
scheduler.py
Verifie periodiquement les rappels arrives a echeance et notifie
(section 13 du cahier des charges).
"""
import logging
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger("aura.scheduler")


class ReminderScheduler(QObject):
    reminder_triggered = Signal(dict)

    def __init__(self, reminder_manager, interval_ms: int = 20000):
        super().__init__()
        self.reminder_manager = reminder_manager
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._check_due_reminders)
        self.timer.start(interval_ms)

    def _check_due_reminders(self):
        try:
            due = self.reminder_manager.get_due_reminders()
        except Exception as exc:
            logger.warning(f"Erreur lors de la verification des rappels : {exc}")
            return

        for reminder in due:
            self.reminder_manager.mark_done(reminder["id"])
            logger.info(f"Rappel declenche (id={reminder['id']})")
            self.reminder_triggered.emit(reminder)

    def stop(self):
        self.timer.stop()
