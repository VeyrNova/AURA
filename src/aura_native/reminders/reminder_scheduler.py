from datetime import timedelta
from aura_native.reminders.time import ProductionClock, local_trigger_to_utc

class _CoreTimer:
    """Small stdlib timer contract used by the importable core and tests."""
    def __init__(self): self._interval = -1; self._active = False
    def start(self, interval): self._interval = int(interval); self._active = True
    def stop(self): self._active = False
    def interval(self): return self._interval
    def isActive(self): return self._active

class ReminderScheduler:
    """Pure reminder policy; Qt is injected by the UI adapter."""
    def __init__(self, repository, *, bus=None, clock=None, notifier=None, missed_window=timedelta(hours=24), claim_lease=timedelta(minutes=5), on_time_grace=timedelta(seconds=60), timer=None, parent=None, emit_logs=False):
        self.repository=repository; self.bus=bus; self.clock=clock or ProductionClock(); self.notifier=notifier; self.missed_window=missed_window; self.claim_lease=claim_lease; self.on_time_grace=on_time_grace; self.timer=timer or _CoreTimer(); self._running=False; self.emit_logs=emit_logs
    def _log(self, message):
        if self.emit_logs: print(message, flush=True)
    def start(self):
        if self._running: return False
        self._running=True; self._log("REMINDER_SCHEDULER_STARTED"); self.rescan_due(); return True
    def stop(self):
        if not self._running:
            self.timer.stop()
            return False
        self.timer.stop(); self._running=False; self._log("REMINDER_SCHEDULER_STOPPED"); return True
    def rescan_due(self): self.process_due()
    def reschedule(self):
        if not self._running: return
        pending=self.repository.list_due(self.clock.now_utc().isoformat(), int(self.missed_window.total_seconds()))
        future=[local_trigger_to_utc(row['trigger_at']) for row in pending if local_trigger_to_utc(row['trigger_at']) > self.clock.now_utc()]
        if not future: self.timer.stop(); return
        delay=max(0, int((min(future)-self.clock.now_utc()).total_seconds()*1000)); self.timer.start(min(delay, 2147483647)); print(f"REMINDER_SCHEDULED delay_ms={delay}", flush=True)
    def process_due(self):
        if not self._running: return
        now=self.clock.now_utc(); now_text=now.isoformat(); stale=(now-self.claim_lease).isoformat()
        for row in self.repository.list_due(now_text, int(self.missed_window.total_seconds())):
            due=local_trigger_to_utc(row['trigger_at']); age=now-due
            if age.total_seconds() < 0: continue
            if age > self.missed_window:
                self.repository.mark_expired(row['reminder_id'], now_text); self._log("REMINDER_MARK_EXPIRED success=true"); continue
            if not self.repository.try_claim(row['reminder_id'], now_text, stale): continue
            try:
                result = self.notifier.notify(row, is_missed=age > self.on_time_grace) if self.notifier else True
                if hasattr(result, "accepted") and not result.accepted:
                    self._log("REMINDER_NOTIFY_RESULT success=false")
                    continue
                self.repository.mark_notified(row['reminder_id'], now_text); self._log("REMINDER_MARK_NOTIFIED success=true")
            except Exception:
                self._log("REMINDER_NOTIFY_RESULT success=false")
        self.reschedule()

class QtReminderSchedulerAdapter(ReminderScheduler):
    """Qt event-loop adapter kept outside the pure Reminder core."""
    def __init__(self, repository, **kwargs):
        from PySide6.QtCore import QObject, QTimer
        self._qt_parent = kwargs.pop("parent", None)
        self._qobject = QObject(self._qt_parent)
        timer = QTimer(self._qobject); timer.setSingleShot(True)
        super().__init__(repository, timer=timer, emit_logs=False, **kwargs)
        timer.timeout.connect(self.process_due)

    def start(self):
        """Start without touching SQLite until Qt is servicing events.

        Native composition can be constructed for probes and tests without an
        event loop.  Deferring the initial scan keeps database-backed services
        lazy in that phase while the real UI still performs the scan as soon
        as its event loop starts.
        """
        if self._running: return False
        self._running = True
        from PySide6.QtCore import QTimer
        QTimer.singleShot(0, self.process_due)
        return True
