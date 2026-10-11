import tempfile,time,unittest
from pathlib import Path
from aura_native.agent.provider import FakeProvider
from aura_native.agent.service import AgentService
from aura_native.core.bus import LocalBus
from aura_native.core.contracts import Command
from aura_native.google.calendar_service import CalendarService
from aura_native.google.providers import FakeCalendarProvider
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
from aura_native.tools.registry import ToolRegistry,register_google_offline_tools
from aura_native.tools.router import ToolRouter

class A33(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.p=Path(self.t.name); self.registry=ToolRegistry(); self.provider=FakeCalendarProvider(); register_google_offline_tools(self.registry,CalendarService(self.provider,PreparedActionRepository(NativeDatabase(self.p/'a.db'))),type('Tasks',(),{})())
  self.agent=AgentService(self.p/'a.db',provider=FakeProvider('Réponse outil'),tool_router=ToolRouter(self.registry),tool_registry=self.registry);self.bus=LocalBus();self.agent.bind(self.bus);self.events=[];self.bus.subscribe(self.events.append)
 def tearDown(self):self.agent.stop();self.t.cleanup()
 def send(self,text):
  from aura_native.storage.conversation_repository import ConversationRepository
  convo=ConversationRepository(NativeDatabase(self.p/'a.db')).create('s'); msg=ConversationRepository(NativeDatabase(self.p/'a.db')).add_message(convo.conversation_id,'s','user',text,'test'); self.bus.submit(Command(name='agent.submit',payload={'text':text,'conversation_id':convo.conversation_id,'user_message_id':msg.message_id},session_id='s')); [self.bus.drain() or time.sleep(.01) for _ in range(30)]
 def test_clarification_does_not_call_tool(self): self.send('Ajoute une réunion');self.assertFalse(self.provider.calls);self.assertTrue(any(x.name=='agent.completed' for x in self.events))
 def test_write_prepares_without_mutation(self): self.send('Ajoute dentiste vendredi à 15h');self.assertFalse(self.provider.calls);self.assertTrue(any(x.name=='agent.completed' for x in self.events))
if __name__=='__main__':unittest.main()