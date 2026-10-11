"""Offline FakeProvider flows: user -> agent -> assistant, cancellation and recovery."""
import tempfile
import time
import unittest
from pathlib import Path
from aura_native.agent.provider import FakeProvider
from aura_native.agent.models import AgentRequest, AgentState
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import Command
from aura_native.storage.agent_repository import AgentRepository
from aura_native.storage.database import NativeDatabase

ROOT=Path(__file__).resolve().parents[2]
class AgentOfflineTests(unittest.TestCase):
    def setUp(self): self.tmp=tempfile.TemporaryDirectory(prefix="aura-agent-offline-");self.state=Path(self.tmp.name);self.provider=FakeProvider("Assistant offline");self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state,provider=self.provider);self.runtime.start()
    def tearDown(self): self.runtime.stop();self.tmp.cleanup()
    def command(self,name,payload=None): return Command(name=name,payload=payload or {},session_id="native",source="test")
    def wait(self,seen):
        for _ in range(40):
            self.runtime.bus.drain()
            if seen:return seen
            time.sleep(.01)
        return seen
    def test_user_to_agent_to_assistant_offline(self):
        messages=[];completed=[];self.runtime.bus.subscribe(messages.append,name="conversation.message_created");self.runtime.bus.subscribe(completed.append,name="agent.completed")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"Bonjour"}));self.runtime.bus.drain()
        self.wait(completed)
        self.assertEqual(len(completed),1); self.assertEqual([event.payload["message"]["role"] for event in messages],["user","assistant"]);self.assertEqual(messages[-1].payload["message"]["content"],"Assistant offline");self.assertEqual(self.provider.calls[0][-1]["content"],"Bonjour")
    def test_duplicate_submit_is_idempotent(self):
        done=[];self.runtime.bus.subscribe(done.append,name="agent.completed");self.runtime.bus.submit(self.command("conversation.send",{"text":"Unique"}));self.runtime.bus.drain(); self.wait(done); request=done[-1].payload["request"]
        created=[];self.runtime.bus.subscribe(created.append,name="agent.request_created")
        result=self.runtime.bus.submit(self.command("agent.submit",{"text":"Unique","conversation_id":request["conversation_id"],"user_message_id":request["user_message_id"]}));self.runtime.bus.drain();self.assertEqual(result.status,"queued");self.assertEqual(created,[])
    def test_cancel_prevents_late_assistant(self):
        class BlockingFake(FakeProvider):
            def generate(self,messages): time.sleep(.12); return super().generate(messages)
        self.runtime.stop();self.provider=BlockingFake("late");self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state,provider=self.provider);self.runtime.start(); created=[];messages=[];self.runtime.bus.subscribe(created.append,name="agent.request_created");self.runtime.bus.subscribe(messages.append,name="conversation.message_created")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"Annule"}));self.runtime.bus.drain();request_id=created[-1].payload["request"]["request_id"];self.runtime.bus.submit(self.command("agent.cancel",{"request_id":request_id}));self.runtime.bus.drain();time.sleep(.16);self.runtime.bus.drain();self.assertEqual([x.payload["message"]["role"] for x in messages],["user"])
    def test_recovery_marks_interrupted_request(self):
        repo=AgentRepository(NativeDatabase(self.state/"data"/"aura_native.db")); active=repo.create(AgentRequest(session_id="native",conversation_id="c",user_message_id="u",prompt="x",state=AgentState.THINKING))
        self.runtime.stop();self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state,provider=FakeProvider());self.runtime.start();self.runtime.bus.submit(self.command("agent.status",{"request_id":active.request_id}));self.runtime.bus.drain();self.assertEqual(repo.get(active.request_id,"native").state,AgentState.ERROR);self.assertEqual(repo.get(active.request_id,"native").error_code,"recovered_interrupted")
