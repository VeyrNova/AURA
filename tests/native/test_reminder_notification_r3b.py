import unittest
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Event
from aura_native.reminders.notification_center import InternalReminderNotificationCenter

class ReminderNotificationR3BTests(unittest.TestCase):
    def setUp(self): self.bus=LocalBus(); self.center=InternalReminderNotificationCenter(self.bus)
    def tearDown(self): self.center.close(); self.bus.close()
    def publish(self, content, missed=False):
        self.bus.publish(Event(name='reminder.due', payload={'reminder_id':content,'content':content,'trigger_at':'2026-10-02T14:30','is_missed':missed})); self.bus.drain()
    def test_enqueue_and_dismiss(self):
        self.publish('A'); self.assertTrue(self.center.current); self.assertEqual(self.center.queue_size,1); self.assertTrue(self.center.dismiss()); self.assertFalse(self.center.current)
    def test_queue_order(self):
        self.publish('A'); self.publish('B'); self.publish('C'); self.assertEqual(self.center.queue_size,3); self.center.dismiss(); self.assertEqual(self.center.current['content'],'B'); self.center.dismiss(); self.assertEqual(self.center.current['content'],'C')
    def test_missed_payload(self):
        self.publish('A', True); self.assertTrue(self.center.current['is_missed'])

if __name__=='__main__': unittest.main()
