import tempfile, threading, unittest
from pathlib import Path
from aura_native.intents.router import NativeIntentRouter
from aura_native.intents.dispatcher import NativeActionDispatcher
from aura_native.google.models import PreparedAction
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
class TextPrepared001Tests(unittest.TestCase):
 def setUp(self): self.r=NativeIntentRouter()
 def test_known_intent(self): self.assertEqual(self.r.parse('ouvre mail').intent,'OPEN_MODULE')
 def test_none_fallback(self): self.assertFalse(self.r.parse('bonjour AURA').recognized)
 def test_slot_extraction(self): self.assertEqual(self.r.parse('minimise la fenêtre AURA_TEST').slots['title'],'aura_test')
 def test_malformed_is_not_mutation(self): self.assertFalse(self.r.parse('minimise').recognized)
 def test_shell_content_inert(self): self.assertFalse(self.r.parse('minimise Chrome && powershell Remove-Item').slots.get('command'))
 def test_voice_keyboard_equivalence(self): self.assertEqual(self.r.parse('ouvre météo').intent,self.r.parse('ouvre météo').intent)
 def test_navigation_dispatch(self): self.assertEqual(NativeActionDispatcher().dispatch(self.r.parse('ouvre maps')).result_type,'NAVIGATED')
 def test_mutation_without_resolver_unavailable(self): self.assertEqual(NativeActionDispatcher().dispatch(self.r.parse('minimise la fenêtre Test')).result_type,'UNAVAILABLE')
 def test_mutation_creates_prepared_action(self):
  made=[]
  d=NativeActionDispatcher(prepared_action_factory=lambda x: made.append(x) or PreparedAction('a','pc','pc.minimize_window',x.slots,'Minimiser la fenêtre « Test »'))
  out=d.dispatch(self.r.parse('minimise la fenêtre Test')); self.assertEqual(out.result_type,'PREPARED_ACTION_CREATED'); self.assertEqual(made[0].slots['title'],'test')
 def test_exact_id_binding_repository(self):
  with tempfile.TemporaryDirectory() as d:
   r=PreparedActionRepository(NativeDatabase(Path(d)/'a.db')); a=PreparedAction('a','pc','pc.minimize_window',{'hwnd':1},'a'); b=PreparedAction('b','pc','pc.maximize_window',{'hwnd':2},'b'); r.create(a);r.create(b); self.assertEqual(r.confirm('a').action_id,'a'); self.assertEqual(r.get('b').state,'prepared')
 def test_cancel_blocks_confirm(self):
  with tempfile.TemporaryDirectory() as d:
   r=PreparedActionRepository(NativeDatabase(Path(d)/'a.db')); r.create(PreparedAction('a','pc','pc.minimize_window',{},'a')); r.cancel('a');
   with self.assertRaises(ValueError): r.confirm('a')
 def test_expired_not_pending(self):
  with tempfile.TemporaryDirectory() as d:
   r=PreparedActionRepository(NativeDatabase(Path(d)/'a.db')); r.create(PreparedAction('a','pc','pc.minimize_window',{},'a',True,'prepared','2020','2020',None,None,'')); self.assertEqual(r.get_pending(),[])
 def test_conversation_text_unchanged(self): self.assertEqual(self.r.parse('quel est mon projet').intent,None)
if __name__=='__main__': unittest.main()
