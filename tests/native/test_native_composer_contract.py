"""Regression contract for the native Home composer capability boundary."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]


class NativeComposerContractTests(unittest.TestCase):
    def test_native_text_submission_uses_conversation_capability(self):
        source = (ROOT / "app/qml/components/Composer.qml").read_text(encoding="utf-8")
        self.assertIn("readonly property bool nativeConversationReady", source)
        self.assertIn("coreBridge.conversationAvailable", source)
        self.assertIn("enabled: root.textSubmissionReady", source)
        self.assertNotIn('enabled: runtimeMode !== "native" && coreBridge.connected && coreBridge.interactionReady', source)

    def test_voice_remains_bound_to_interaction_readiness(self):
        source = (ROOT / "app/qml/components/Composer.qml").read_text(encoding="utf-8")
        self.assertIn("coreBridge.connected && coreBridge.interactionReady", source)

    def test_native_microphone_is_push_to_talk_not_toggle(self):
        source = (ROOT / "app/qml/components/Composer.qml").read_text(encoding="utf-8")
        self.assertIn('MouseArea {', source)
        self.assertIn('onPressed:', source)
        self.assertIn('if (voiceBridge.state === "idle") {', source)
        self.assertIn('voiceBridge.startListening()', source)
        self.assertIn('onReleased:', source)
        self.assertIn('voiceBridge.stopListening()', source)
        self.assertIn('onCanceled:', source)
        self.assertNotIn('onClicked:', source[source.index('voiceBridge.startListening()') - 500:source.index('voiceBridge.startListening()') + 500])

    def test_native_conversation_has_no_competing_composer(self):
        main = (ROOT / "app/qml/Main.qml").read_text(encoding="utf-8")
        conversation = (ROOT / "app/qml/views/NativeConversationView.qml").read_text(encoding="utf-8")
        self.assertEqual(main.count("    Composer {"), 1)
        self.assertNotIn("TextField", conversation)
        self.assertNotIn("sendMessage(", conversation)
        self.assertIn("coreBridge.clearConversation()", conversation)

    def test_native_conversation_uses_main_dock_safe_margins(self):
        main = (ROOT / "app/qml/Main.qml").read_text(encoding="utf-8")
        conversation = (ROOT / "app/qml/views/NativeConversationView.qml").read_text(encoding="utf-8")
        self.assertIn("safeLeft: root.workspaceSafeLeft", main)
        self.assertIn("anchors.leftMargin: root.safeLeft", conversation)
        self.assertIn("anchors.rightMargin: root.safeRight", conversation)

    def test_native_composer_exposes_agent_stop_while_streaming(self):
        source = (ROOT / "app/qml/components/Composer.qml").read_text(encoding="utf-8")
        self.assertIn('text: "STOP"', source)
        self.assertIn("coreBridge.cancelAgent(coreBridge.activeRequestId)", source)

    def test_streaming_draft_is_a_listview_footer_not_header_text(self):
        source = (ROOT / "app/qml/views/NativeConversationView.qml").read_text(encoding="utf-8")
        self.assertIn("footer: Item", source)
        self.assertIn('visible: coreBridge.agentState === "responding" && coreBridge.agentStream.length > 0', source)
        self.assertIn("messages.positionViewAtEnd()", source)
