import unittest
from aura_native.reminders.notification_coordinator import NotificationCoordinator
from aura_native.reminders.window_state import WindowState, WindowStateAdapter

class Center:
    def __init__(self): self.items=[]
    def enqueue(self, item, *, is_missed=False): self.items.append((dict(item),is_missed))
class Windows:
    def __init__(self, ok=True): self.ok=ok; self.calls=[]
    def notify(self, item, *, is_missed=False): self.calls.append((item,is_missed)); return self.ok
class ReminderCoordinatorR3CTests(unittest.TestCase):
    def run_case(self,state,ok=True):
        c=Center(); w=Windows(ok); a=WindowStateAdapter(); a.state=state; result=NotificationCoordinator(c,a,w).notify({'reminder_id':'id','trigger_at':'2026-10-02T14:30','content':'r'},is_missed=False); self.assertTrue(getattr(result, 'accepted', result)); return c,w
    def test_active_internal_only(self): c,w=self.run_case(WindowState.ACTIVE); self.assertEqual(len(c.items),1); self.assertEqual(w.calls,[])
    def test_inactive_minimized_hidden_windows(self):
        for state in (WindowState.INACTIVE,WindowState.MINIMIZED,WindowState.HIDDEN): c,w=self.run_case(state); self.assertEqual(len(c.items),0); self.assertEqual(len(w.calls),1)
    def test_unknown_internal_only(self): c,w=self.run_case(WindowState.UNKNOWN); self.assertEqual(w.calls,[])
    def test_windows_failure_falls_back(self): c,w=self.run_case(WindowState.MINIMIZED,False); self.assertEqual(len(c.items),1); self.assertEqual(len(w.calls),1)
if __name__=='__main__': unittest.main()
