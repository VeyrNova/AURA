import unittest
from pathlib import Path

ROOT=Path(__file__).parents[2]
CARD=ROOT/'app/qml/components/PendingActionCard.qml'
MAIN=ROOT/'app/qml/Main.qml'

class PendingActionQmlTests(unittest.TestCase):
 def test_card_exists_and_is_integrated(self):
  source=CARD.read_text(encoding='utf-8');main=MAIN.read_text(encoding='utf-8')
  self.assertTrue(CARD.exists());self.assertIn('visible: nativeCore.hasPendingAction',source);self.assertIn('nativeCore.pendingActionSummary',source);self.assertIn('nativeCore.confirmPendingAction()',source);self.assertIn('nativeCore.cancelPendingAction()',source);self.assertIn('pendingActionState !== "confirmed"',source);self.assertIn('MouseArea',source);self.assertNotIn('Button {',source);self.assertIn('PendingActionCard {',main)
 def test_card_is_ui_only_and_responsive(self):
  source=CARD.read_text(encoding='utf-8');self.assertIn('wrapMode: Text.Wrap',source);self.assertIn('Math.min(parent ? parent.width - 32',source);self.assertNotIn('CalendarService',source);self.assertNotIn('TasksService',source);self.assertNotIn('PreparedActionRepository',source);self.assertNotIn('Dialog {',source);self.assertNotIn('MessageBox',source)
 def test_theme_and_restart_contract(self):
  source=CARD.read_text(encoding='utf-8');self.assertIn('lightMode',source);self.assertIn('coreBridge',source)
if __name__=='__main__':unittest.main()
