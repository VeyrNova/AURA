import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]; CARD=ROOT/'app'/'qml'/'components'/'PendingActionCard.qml'; BRIDGE=ROOT/'src'/'aura_native'/'ui'/'qt_bridge.py'
class PreparedActionQml003Tests(unittest.TestCase):
 def setUp(self): self.qml=CARD.read_text(encoding='utf-8'); self.py=BRIDGE.read_text(encoding='utf-8')
 def test_confirmation_surface_is_bound_to_pending(self): self.assertIn('nativeCore.hasPendingAction',self.qml)
 def test_summary_and_id_are_separate(self): self.assertIn('nativeCore.pendingActionSummary',self.qml); self.assertIn('nativeCore.pendingActionId',self.qml)
 def test_confirm_uses_exact_id(self): self.assertIn('confirmPreparedAction(nativeCore.pendingActionId)',self.qml); self.assertIn('payload={"action_id": action_id}',self.py)
 def test_cancel_uses_exact_id(self): self.assertIn('cancelPreparedAction(nativeCore.pendingActionId)',self.qml)
 def test_terminal_states_hide_surface(self): self.assertIn('pendingActionState !== "error"',self.qml); self.assertIn('pendingActionState !== "expired"',self.qml)
 def test_no_raw_json_or_hwnd_pid(self): self.assertNotIn('payload_json',self.qml); self.assertNotIn('hwnd',self.qml); self.assertNotIn('pid',self.qml)
 def test_processing_disables_buttons(self): self.assertIn('pendingActionState !== "confirmed"',self.qml)
 def test_bridge_slots_exist(self): self.assertIn('def confirmPreparedAction',self.py); self.assertIn('def cancelPreparedAction',self.py)
if __name__=='__main__': unittest.main()
