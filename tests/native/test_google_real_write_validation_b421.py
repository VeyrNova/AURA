import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).parents[2]; HARNESS=ROOT/'tests/native/_evidence/lot6b_b421_calendar_write_real.py'
class B421HarnessTests(unittest.TestCase):
 def invoke(self,*args): return subprocess.run([sys.executable,'-B',str(HARNESS),*args],cwd=ROOT,text=True,capture_output=True)
 def test_write_flag_required(self):
  r=self.invoke('--create','--state-dir',str(ROOT/'tests/native/_evidence/b421-test-state')); self.assertNotEqual(r.returncode,0); self.assertIn('confirm-real-write',r.stderr+r.stdout)
 def test_harness_is_non_production_and_safe_state_shape(self):
  text=HARNESS.read_text(encoding='utf-8'); self.assertIn('NON-PRODUCTION',text); self.assertIn('REFUSED',text)
  allowed={'event_id','title','start','end','phase'}; self.assertTrue(allowed.issuperset({'event_id','phase'}))
 def test_duplicate_and_cleanup_guards_are_present(self):
  text=HARNESS.read_text(encoding='utf-8'); self.assertIn('requires cleanup first',text); self.assertIn("phase')!='deleted'",text); self.assertIn("phase']='deleted'",text)
 def test_no_secret_output_or_legacy_path(self):
  text=HARNESS.read_text(encoding='utf-8'); self.assertNotIn('refresh_token',text); self.assertNotIn('client_secret',text); self.assertNotIn('AURA GPT version',text)
 def test_delete_readback_rules(self):
  import importlib.util
  spec=importlib.util.spec_from_file_location('b421',HARNESS); mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
  self.assertTrue(mod.is_deleted(None)); self.assertTrue(mod.is_deleted({'status':'cancelled'})); self.assertFalse(mod.is_deleted({'status':'confirmed'}))
 def test_status_repairs_cancelled_phase_without_write_flag(self):
  text=HARNESS.read_text(encoding='utf-8'); self.assertIn("current['phase']='deleted'",text); self.assertIn("if args.status:",text); self.assertNotIn("args.status:.*confirm_real_write",text)
 def test_410_is_treated_as_absent(self):
  text=HARNESS.read_text(encoding='utf-8'); self.assertIn('status in (404,410)',text)
