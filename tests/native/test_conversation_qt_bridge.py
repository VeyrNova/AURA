import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import time
import unittest
from pathlib import Path
from aura_native.bootstrap.composition import compose_runtime

ROOT=Path(__file__).resolve().parents[2]
class ConversationQtBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.app=QGuiApplication.instance() or QGuiApplication([])
    def test_empty_rejected_and_message_accepted(self):
        from aura_native.ui.qt_bridge import NativeCoreBridge
        from aura_native.ui.qt_dispatcher import QtBusDispatcher
        with tempfile.TemporaryDirectory(prefix="aura-native-bridge-") as state:
            runtime=compose_runtime(project_root=ROOT,state_dir=Path(state));runtime.start();dispatcher=QtBusDispatcher(runtime.bus);bridge=NativeCoreBridge(runtime)
            self.assertTrue(bridge.conversationAvailable)
            self.assertFalse(bridge.interactionReady)
            agent = next(capability for capability in runtime.capabilities if capability.name == "agent")
            self.assertEqual(agent.state.value,"available")
            self.assertFalse(bridge.providerAvailable)
            self.assertEqual(bridge.agentState,"unavailable")
            self.assertFalse(bridge.sendMessage("  "));self.assertEqual(bridge.conversationStatus,"empty")
            self.assertTrue(bridge.sendMessage("Message local"));
            for _ in range(10): self.app.processEvents()
            self.assertEqual(bridge.messageCount,1);self.assertEqual(bridge.messages[0]["role"],"user");self.assertTrue(bridge.conversationAvailable)
            bridge.clearConversation()
            for _ in range(10): self.app.processEvents()
            self.assertEqual(bridge.messageCount,0)
            self.assertEqual(bridge.conversationStatus,"cleared")
            bridge.close();dispatcher.close()

    def test_provider_availability_is_dynamic_for_offline_fake(self):
        from aura_native.agent.provider import FakeProvider
        from aura_native.ui.qt_bridge import NativeCoreBridge
        from aura_native.ui.qt_dispatcher import QtBusDispatcher
        with tempfile.TemporaryDirectory(prefix="aura-native-bridge-fake-") as state:
            runtime=compose_runtime(project_root=ROOT,state_dir=Path(state),provider=FakeProvider("ok"));runtime.start();dispatcher=QtBusDispatcher(runtime.bus);bridge=NativeCoreBridge(runtime)
            self.assertTrue(bridge.sendMessage("provider"))
            for _ in range(50):
                self.app.processEvents(); runtime.bus.drain()
                if bridge.providerAvailable and bridge.messageCount == 2: break
                time.sleep(.01)
            self.assertTrue(bridge.providerAvailable); self.assertEqual(bridge.messageCount,2); bridge.close();dispatcher.close();runtime.stop()

    def test_stream_accumulator_reaches_bridge_before_terminal_reset(self):
        from aura_native.agent.provider import StreamingFakeProvider
        from aura_native.ui.qt_bridge import NativeCoreBridge
        from aura_native.ui.qt_dispatcher import QtBusDispatcher
        with tempfile.TemporaryDirectory(prefix="aura-native-bridge-stream-") as state:
            runtime=compose_runtime(project_root=ROOT,state_dir=Path(state),provider=StreamingFakeProvider(("Bon","jour","")));runtime.start();dispatcher=QtBusDispatcher(runtime.bus);bridge=NativeCoreBridge(runtime); values=[];bridge.agentStreamChanged.connect(lambda: values.append(bridge.agentStream))
            self.assertTrue(bridge.sendMessage("provider"))
            for _ in range(50):
                self.app.processEvents(); runtime.bus.drain()
                if bridge.messageCount == 2: break
                time.sleep(.01)
            self.assertIn("Bonjour",values);self.assertEqual(bridge.agentStream,"")
            bridge.close();dispatcher.close();runtime.stop()
