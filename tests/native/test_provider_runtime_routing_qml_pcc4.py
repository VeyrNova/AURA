import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


class ProviderRuntimeRoutingQmlTests(unittest.TestCase):
    def test_conversation_reports_selection_and_normalized_configuration_message(self):
        bridge=(ROOT/"src/aura_native/ui/qt_bridge.py").read_text(encoding="utf-8")
        view=(ROOT/"app/qml/views/NativeConversationView.qml").read_text(encoding="utf-8")
        self.assertIn("def agentErrorMessage",bridge)
        self.assertIn("Aucun fournisseur d’IA n’est sélectionné.", (ROOT/"src/aura_native/agent/service.py").read_text(encoding="utf-8"))
        self.assertIn("coreBridge.activeProvider",view)
        self.assertIn("coreBridge.activeModel",view)
        self.assertIn("coreBridge.agentErrorMessage",view)
        self.assertNotIn("api_key",view.lower())
        self.assertNotIn("credential",view.lower())

    def test_conversation_keeps_existing_cancel_control(self):
        composer=(ROOT/"app/qml/components/Composer.qml").read_text(encoding="utf-8")
        self.assertIn("coreBridge.cancelAgent(coreBridge.activeRequestId)",composer)
        self.assertIn("coreBridge.sendMessage(message)",composer)


if __name__=="__main__":
    unittest.main()
