from collections import deque
from aura_native.reminders.notification_contract import (
    NotificationCapability, NotificationResult, notification_id,
)
class _Signal:
    def __init__(self): self._slots=[]
    def connect(self, slot): self._slots.append(slot)
    def emit(self, *args):
        for slot in tuple(self._slots): slot(*args)

class InternalReminderNotificationCenter:
    changed = None
    def __init__(self, bus, parent=None):
        self.changed = _Signal(); self._queue=deque(); self._current=None; self._seen=set(); self._closed=False
        self._subscription=bus.subscribe(self._on_due, name='reminder.due')
    def _on_due(self, event):
        p=dict(event.payload); self.enqueue(p, is_missed=bool(p.get('is_missed')))
    def enqueue(self, reminder, *, is_missed=False):
        if self._closed:
            return NotificationResult(False, NotificationCapability.UNAVAILABLE, "", "in_app", reason="closed")
        p=dict(reminder); p['is_missed']=bool(is_missed)
        ident=notification_id(p, is_missed=is_missed)
        if not ident:
            return NotificationResult(False, NotificationCapability.ERROR, "", "in_app", reason="identity_required")
        if ident in self._seen:
            return NotificationResult(False, NotificationCapability.SUPPORTED, ident, "in_app", reason="duplicate")
        self._seen.add(ident); p['notification_id']=ident; self._queue.append(p)
        if self._current is None: self._current=self._queue.popleft()
        print(f"REMINDER_UI_ENQUEUED queue_size={len(self._queue)+bool(self._current)} missed={str(bool(p.get('is_missed'))).lower()}", flush=True); self.changed.emit()
        return NotificationResult(True, NotificationCapability.SUPPORTED, ident, "in_app")
    @property
    def current(self): return self._current
    @property
    def queue_size(self): return len(self._queue)+(1 if self._current else 0)
    def dismiss(self):
        if self._current is None: return False
        self._current=self._queue.popleft() if self._queue else None
        print(f"REMINDER_UI_DISMISSED remaining={self.queue_size}", flush=True); self.changed.emit(); return True
    def close(self):
        if self._closed: return
        self._closed=True; self._subscription.close(); self._queue.clear(); self._current=None; self.changed._slots.clear()
