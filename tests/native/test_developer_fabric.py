import tempfile, unittest
from pathlib import Path
from aura_native.developer_fabric import DeveloperFabric

class DeveloperFabricTests(unittest.TestCase):
 def setUp(self): self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name); (self.root/'sample.py').write_text('def answer():\n    return 41\n'); self.f=DeveloperFabric(self.root)
 def tearDown(self): self.tmp.cleanup()
 def test_mode_default_off_enable_disable(self):
  with self.assertRaises(PermissionError): self.f.plan('x')
  self.f.mode.enable(); self.f.plan('x'); self.f.mode.disable(); self.assertFalse(self.f.mode.enabled)
 def test_workspace_rejects_escape(self):
  with self.assertRaises(ValueError): self.f.workspace.resolve('../outside.txt')
  with self.assertRaises(ValueError): self.f.workspace.resolve(str(Path(self.tmp.name).parent/'outside.txt'))
 def test_plan_stage_diff_cancel_no_mutation(self):
  self.f.mode.enable(); p=self.f.plan('Change answer to 42'); self.assertEqual(p.files,('sample.py',)); before=(self.root/'sample.py').read_text(); diff=self.f.stage('sample.py','def answer():\n    return 42\n'); self.assertIn('-    return 41',diff); self.assertEqual((self.root/'sample.py').read_text(),before); self.f.cancel(); self.assertEqual((self.root/'sample.py').read_text(),before)
 def test_approve_apply_double_apply_and_rollback(self):
  self.f.mode.enable(); self.f.plan('change'); self.f.stage('sample.py','def answer():\n    return 42\n'); self.f.approve(); self.f.apply(); self.assertIn('42',(self.root/'sample.py').read_text())
  with self.assertRaises(PermissionError): self.f.apply()
  self.f.rollback(); self.assertIn('41',(self.root/'sample.py').read_text())
 def test_runner_success_failure_timeout(self):
  import sys
  self.f.mode.enable(); self.assertEqual(self.f.run_test([sys.executable,'-c','print(1)'])[0],0); self.assertNotEqual(self.f.run_test([sys.executable,'-c','raise SystemExit(3)'])[0],0)
  with self.assertRaises(TimeoutError): self.f.run_test([sys.executable,'-c','import time; time.sleep(1)'],timeout=.05)
 def test_e2e_plan_stage_approve_apply_test_rollback(self):
  import sys
  self.f.mode.enable(); self.f.plan('Change answer to 42 and verify it'); self.f.stage('sample.py','def answer():\n    return 42\n'); self.assertIn('42',self.f.diff()); self.f.approve(); self.f.apply(); self.assertEqual(self.f.run_test([sys.executable,'-c','from sample import answer; assert answer()==42'])[0],0); self.f.rollback(); self.assertEqual((self.root/'sample.py').read_text(),'def answer():\n    return 41\n'); self.assertIn('ROLLBACK',[x['event'] for x in self.f.audit])

if __name__=='__main__': unittest.main()
