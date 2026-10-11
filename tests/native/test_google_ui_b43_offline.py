import unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]
class B43OfflineTests(unittest.TestCase):
 def test_launcher_requires_explicit_launch_and_native_mode(self):
  t=(ROOT/'tests/native/_evidence/lot6b_b43_ui_real.py').read_text(encoding='utf-8'); self.assertIn("--launch',action='store_true'",t); self.assertIn("'--core-mode','native'",t); self.assertIn("'--state-dir'",t)
 def test_pending_action_ui_contracts_remain_bridge_only(self):
  q=(ROOT/'app/qml/components/PendingActionCard.qml').read_text(encoding='utf-8'); self.assertIn('nativeCore.confirmPendingAction()',q); self.assertIn('nativeCore.cancelPendingAction()',q); self.assertNotIn('GoogleCalendarProvider',q); self.assertNotIn('GoogleTasksProvider',q)
 def test_user_phrases_and_secret_isolation(self):
  t=(ROOT/'tests/native/_evidence/lot6b_b43_ui_real.py').read_text(encoding='utf-8'); self.assertNotIn('refresh_token',t); self.assertNotIn('client_secret',t)
