import tempfile,unittest,sys
from pathlib import Path
from aura_native.developer_fabric.adf import *
class ADFTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name); (self.root/'sample.py').write_text('def answer():\n return 41\n'); self.s=ADFService(self.root,self.root/'state',[FakeProvider('a','unavailable'),FakeProvider('b')]); self.s.enable(); self.s.select_project(ActiveProject('p','P',self.root)); self.j=self.s.create_job('change'); self.s.plan(self.j); self.s.stage(self.j,'sample.py','def answer():\n return 42\n')
 def tearDown(self): self.s.close(); self.t.cleanup()
 def test_pipeline_stale_and_rollback(self):
  self.s.test(self.j,[sys.executable,'-c','print(1)']); self.s.approve(self.j); self.s.apply(self.j); self.assertIn('42',(self.root/'sample.py').read_text()); self.s.rollback(self.j); self.assertIn('41',(self.root/'sample.py').read_text())
 def test_stale_refuses(self):
  self.s.test(self.j,[sys.executable,'-c','pass']); (self.root/'sample.py').write_text('external'); self.s.approve(self.j)
  with self.assertRaises(RuntimeError): self.s.apply(self.j)
  self.assertEqual(self.j.state,'STALE')
 def test_failover_and_catalog(self):
  out,attempts=self.s.providers.execute(self.j,'x'); self.assertEqual(attempts,['a','b']); self.assertEqual(out['provider_id'],'b'); self.assertEqual(len(self.s.agents.agents),10)
 def test_persistence(self):
  self.assertIsNotNone(self.s.jobs.load(self.j.job_id)); self.assertEqual(self.s.jobs.load(self.j.job_id).state,'STAGED')
if __name__=='__main__': unittest.main()

