import tempfile, unittest, threading
from pathlib import Path
from aura_native.google.models import PreparedAction
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
class ExpandedPreparedActionTests(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory(); self.r=PreparedActionRepository(NativeDatabase(Path(self.t.name)/'a.db'))
 def tearDown(self): self.t.cleanup()
 def a(self,i='a',state='prepared',exp=None): return PreparedAction(i,'system_control','system.window.minimize',{'hwnd':1,'pid':2,'title':'x'},'Minimiser x',True,state,'2026-01-01',exp,None,None,'')
 def test_create(self): self.assertEqual(self.r.create(self.a()).state,'prepared')
 def test_confirm(self): self.r.create(self.a()); self.assertEqual(self.r.confirm('a').state,'confirmed')
 def test_cancel(self): self.r.create(self.a()); self.assertEqual(self.r.cancel('a').state,'cancelled')
 def test_confirm_after_cancel(self): self.r.create(self.a()); self.r.cancel('a');
 def test_confirm_after_cancel_rejected(self): self.r.create(self.a()); self.r.cancel('a');
 def test_double_confirm_rejected(self): self.r.create(self.a()); self.r.confirm('a');
 def test_action_id_binding(self): self.r.create(self.a('a')); self.r.create(self.a('b')); self.r.confirm('a'); self.assertEqual(self.r.get('b').state,'prepared')
 def test_two_pending_isolated(self): self.r.create(self.a('a')); self.r.create(self.a('b')); self.assertEqual({x.action_id for x in self.r.get_pending()},{'a','b'})
 def test_executed_terminal(self): self.r.create(self.a()); self.r.confirm('a'); self.r.mark_executed('a'); self.assertEqual(self.r.get('a').state,'executed')
 def test_executed_cannot_reexecute(self): self.r.create(self.a()); self.r.confirm('a'); self.r.mark_executed('a');
 def test_error_terminal(self): self.r.create(self.a()); self.r.confirm('a'); self.assertEqual(self.r.mark_error('a','stale').error_code,'stale')
 def test_malformed_id(self): self.assertIsNone(self.r.get(''))
 def test_unknown_id(self): self.assertIsNone(self.r.get('missing'))
 def test_expired(self): self.r.create(self.a('e',exp='2000-01-01')); self.assertEqual(self.r.get_pending(),[])
 def test_persistence_reload(self): self.r.create(self.a()); self.assertEqual(PreparedActionRepository(self.r.db).get('a').action_id,'a')
 def test_concurrent_confirm_one_winner(self):
  self.r.create(self.a()); results=[]
  def f():
   try: results.append(self.r.confirm('a').state)
   except ValueError: results.append('rejected')
  ts=[threading.Thread(target=f) for _ in range(2)]; [x.start() for x in ts]; [x.join() for x in ts]; self.assertEqual(results.count('confirmed'),1)
if __name__=='__main__': unittest.main()
