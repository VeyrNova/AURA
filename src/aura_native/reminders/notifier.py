from dataclasses import dataclass

class ReminderNotifier:
    def notify(self, reminder, *, is_missed=False): raise NotImplementedError

@dataclass
class FakeReminderNotifier(ReminderNotifier):
    notifications: list
    fail_count: int = 0
    def notify(self, reminder, *, is_missed=False):
        self.notifications.append((dict(reminder), bool(is_missed)))
        if self.fail_count:
            self.fail_count -= 1
            raise RuntimeError("fake_notifier_failure")

class BusReminderNotifier(ReminderNotifier):
    def __init__(self, bus): self.bus = bus
    def notify(self, reminder, *, is_missed=False):
        from aura_native.core.contracts import Event
        self.bus.publish(Event(name="reminder.due", payload={"reminder_id": str(reminder["reminder_id"]), "content": str(reminder["content"]), "trigger_at": str(reminder["trigger_at"]), "is_missed": bool(is_missed)}, source="reminder_scheduler"))
