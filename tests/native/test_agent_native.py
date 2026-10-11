import tempfile
import unittest
from pathlib import Path

from aura_native.agent.models import AgentRequest, AgentState
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import CapabilityState, Command
from aura_native.storage.agent_repository import AgentRepository
from aura_native.storage.database import NativeDatabase


ROOT=Path(__file__).resolve().parents[2]


class AgentNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="aura-native-agent-")
        self.runtime=compose_runtime(project_root=ROOT,state_dir=Path(self.temp.name)); self.runtime.start()
    def tearDown(self): self.runtime.stop(); self.temp.cleanup()
    def command(self,name,payload=None): return Command(name=name,payload=payload or {},session_id="agent-test",source="test")
    def events(self,name): out=[]; self.runtime.bus.subscribe(out.append,name=name); return out
    def submit(self,text="bonjour",conversation="c1",message="m1"):
        self.runtime.bus.submit(self.command("agent.submit",{"text":text,"conversation_id":conversation,"user_message_id":message})); self.runtime.bus.drain()

    def test_capabilities_honestly_separate_orchestrator_and_inference(self):
        caps={item.name:item.state for item in self.runtime.capabilities}
        self.assertEqual(caps["agent"],CapabilityState.AVAILABLE)
        self.assertEqual(caps["inference"],CapabilityState.NOT_MIGRATED)

    def test_submit_creates_unique_persisted_unavailable_request(self):
        created=self.events("agent.request_created"); errors=self.events("agent.error")
        self.submit(); self.submit("salut","c2","m2")
        self.assertEqual(len(created),2); self.assertNotEqual(created[0].payload["request"]["request_id"],created[1].payload["request"]["request_id"])
        request=created[0].payload["request"]
        self.assertEqual((request["session_id"],request["conversation_id"],request["user_message_id"]),("agent-test","c1","m1"))
        self.assertEqual(errors[-1].payload["request"]["error_code"],"provider_not_selected")
        self.assertEqual(errors[-1].payload["request"]["state"],"unavailable")

    def test_invalid_request_and_terminal_cancel_are_refused(self):
        result=self.runtime.bus.submit(self.command("agent.submit",{"text":"x"})); self.runtime.bus.drain(); self.assertEqual(result.status,"queued")
        self.submit(); created=self.events("agent.request_created"); self.submit("again","c3","m3")
        request_id=created[-1].payload["request"]["request_id"]
        self.runtime.bus.submit(self.command("agent.cancel",{"request_id":request_id})); self.runtime.bus.drain()
        # A provider-unavailable request is terminal and cannot be cancelled.
        repo=AgentRepository(NativeDatabase(self.runtime.paths.data_dir/"aura_native.db"))
        self.assertEqual(repo.get(request_id,"agent-test").state,AgentState.UNAVAILABLE)

    def test_active_request_can_be_cancelled_and_reset_is_idle(self):
        repo=AgentRepository(NativeDatabase(self.runtime.paths.data_dir/"aura_native.db"))
        request=repo.create(AgentRequest(session_id="agent-test",conversation_id="c",user_message_id="m",prompt="x"))
        cancelled=self.events("agent.cancelled")
        self.runtime.bus.submit(self.command("agent.cancel",{"request_id":request.request_id})); self.runtime.bus.drain()
        self.assertEqual(cancelled[-1].payload["request"]["state"],"cancelled")
        states=self.events("agent.state_changed"); self.runtime.bus.submit(self.command("agent.reset")); self.runtime.bus.drain(); self.assertEqual(states[-1].payload["state"],"idle")

    def test_no_assistant_message_is_created_and_runtime_rebinds(self):
        messages=self.events("conversation.message_created"); self.submit(); self.assertEqual(messages,[])
        self.runtime.stop(); self.runtime.start(); created=self.events("agent.request_created"); self.submit("after restart","c4","m4"); self.assertEqual(len(created),1)
