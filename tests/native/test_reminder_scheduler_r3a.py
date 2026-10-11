import tempfile, unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from PySide6.QtGui import QGuiApplication
from aura_native.storage.database import NativeDatabase
from aura_native.storage.local_reminders_repository import LocalRemindersRepository
from aura_native.reminders.reminder_scheduler import ReminderScheduler
from aura_native.reminders.notifier import FakeReminderNotifier
from aura_native.reminders.time import FakeClock, local_trigger_to_utc

class ReminderSchedulerR3ATests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = QGuiApplication.instance() or QGuiApplication([])
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.repo=LocalRemindersRepository(NativeDatabase(Path(self.tmp.name)/'aura.db'))
        self.now=datetime(2026,10,2,14,30,tzinfo=timezone.utc); self.clock=FakeClock(self.now); self.out=FakeReminderNotifier([])
        self.scheduler=ReminderScheduler(self.repo, clock=self.clock, notifier=self.out)
    def tearDown(self): self.scheduler.stop(); self.tmp.cleanup()
    def add(self, value): return self.repo.create('r', value)
    def due_row(self, value): return next(r for r in self.repo.list() if r['trigger_at']==value)
    def test_claim_recent_is_not_reclaimed(self):
        row=self.add('2026-10-02T16:00'); self.repo.try_claim(row['reminder_id'], self.now.isoformat(), (self.now-timedelta(minutes=1)).isoformat()); self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(self.out.notifications, []); self.assertIsNone(self.due_row('2026-10-02T16:00')['notified_at'])
    def test_claim_stale_is_reclaimed_once(self):
        row=self.add('2026-10-02T16:00'); old=(self.now-timedelta(minutes=6)).isoformat(); self.repo.try_claim(row['reminder_id'], old, (self.now-timedelta(minutes=10)).isoformat()); self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),1); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),1)
    def test_notifier_failure_and_retry_after_lease(self):
        self.add('2026-10-02T16:00'); self.out.fail_count=1; self.scheduler.start(); self.scheduler.process_due(); self.assertIsNone(self.due_row('2026-10-02T16:00')['notified_at']); self.clock.set(self.now+timedelta(minutes=6)); self.scheduler.process_due(); self.assertIsNotNone(self.due_row('2026-10-02T16:00')['notified_at']); self.assertEqual(len(self.out.notifications),2)
    def test_three_same_minute_and_second_process(self):
        for _ in range(3): self.add('2026-10-02T16:00')
        self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),3); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),3)
    def test_delete_before_due(self):
        row=self.add('2026-10-02T16:00'); self.assertTrue(self.repo.delete(row['reminder_id'])); self.clock.set(self.now+timedelta(hours=3)); self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(self.out.notifications, [])
    def test_create_closer_reschedules(self):
        self.add('2026-10-02T18:00'); self.scheduler.start(); self.assertGreater(self.scheduler.timer.interval(), 0); self.add('2026-10-02T16:00'); self.scheduler.reschedule(); self.assertLess(self.scheduler.timer.interval(), 7200000)
    def test_stop_is_idempotent(self):
        self.add('2026-10-02T18:00'); self.scheduler.start(); self.scheduler.stop(); self.scheduler.stop(); self.scheduler.process_due(); self.assertEqual(self.out.notifications, []); self.assertFalse(self.scheduler.timer.isActive())
    def test_missed_window_boundaries(self):
        for trigger in ('2026-10-01T16:31','2026-10-01T16:30','2026-10-01T16:29'): self.add(trigger)
        self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),2); self.assertIsNotNone(self.due_row('2026-10-01T16:29')['expired_at'])
    def test_on_time_grace_classification(self):
        self.clock.set(datetime(2026,10,2,14,0,tzinfo=timezone.utc))
        for seconds in (0, 5, 30, 60, 61, 600):
            row=self.add('2026-10-02T16:00')
            self.clock.set(datetime(2026,10,2,14,0,tzinfo=timezone.utc)+timedelta(seconds=seconds))
            self.scheduler.start(); self.scheduler.process_due()
            result=next(item for item in self.out.notifications if item[0]['reminder_id']==row['reminder_id'])
            self.assertEqual(result[1], seconds > 60)
            self.scheduler.stop()
    def test_dst_results(self):
        from zoneinfo import ZoneInfo
        for value in ('02:00','02:15','02:30','02:59'):
            local=local_trigger_to_utc('2026-03-29T'+value).astimezone(ZoneInfo('Europe/Paris'))
            self.assertEqual((local.hour,local.minute),(3,0))
        for value in ('01:59','03:00','03:30'):
            local=local_trigger_to_utc('2026-03-29T'+value).astimezone(ZoneInfo('Europe/Paris'))
            self.assertEqual((local.hour,local.minute),tuple(map(int,value.split(':'))))
        autumn=local_trigger_to_utc('2026-10-25T02:30'); self.assertEqual(autumn.fold,0); self.assertEqual(autumn.isoformat(),'2026-10-25T00:30:00+00:00')
    def test_restart_notified_expired_and_stale(self):
        row=self.add('2026-10-02T16:00'); self.repo.try_claim(row['reminder_id'], self.now.isoformat(), (self.now-timedelta(minutes=1)).isoformat()); self.repo.mark_notified(row['reminder_id'], self.now.isoformat()); self.assertIsNotNone(self.due_row('2026-10-02T16:00')['notified_at'])
        expired=self.add('2026-10-01T15:00'); self.repo.mark_expired(expired['reminder_id'], self.now.isoformat()); self.assertIsNotNone(self.due_row('2026-10-01T15:00')['expired_at'])
        stale=self.add('2026-10-02T16:00'); self.repo.try_claim(stale['reminder_id'], (self.now-timedelta(minutes=6)).isoformat(), (self.now-timedelta(minutes=10)).isoformat()); self.scheduler.start(); self.scheduler.process_due(); self.assertEqual(len(self.out.notifications),1)

if __name__=='__main__': unittest.main()
