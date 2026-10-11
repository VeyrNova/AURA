from pathlib import Path
import unittest

ROOT = Path(__file__).parents[2]


class PendingActionCardReconcileTests(unittest.TestCase):
    def test_card_uses_native_pending_state(self):
        card = (ROOT / "app/qml/components/PendingActionCard.qml").read_text(encoding="utf-8")
        self.assertIn("visible: nativeCore.hasPendingAction", card)
        self.assertIn("nativeCore.pendingActionSummary", card)

    def test_bridge_reconciles_persisted_pending_action(self):
        bridge = (ROOT / "src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        self.assertIn("self._prepared_repository.get_pending()", bridge)
        self.assertIn("self._set_pending({", bridge)


if __name__ == "__main__": unittest.main()
