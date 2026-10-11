import os, tempfile, unittest
from pathlib import Path
class Pcc2eFreshStateTests(unittest.TestCase):
 def test_fake_seed_on_empty_state(self):
  from aura_native.bootstrap.composition import compose_runtime
  from aura_native.storage.database import NativeDatabase
  with tempfile.TemporaryDirectory() as d:
   old=os.environ.get('AURA_PCC_FAKE'); os.environ['AURA_PCC_FAKE']='1'
   try:
    rt=compose_runtime(project_root=Path(__file__).parents[2],state_dir=Path(d)); cfg=rt.provider_settings_service
    self.assertEqual(cfg.get_active_provider(),'ollama'); self.assertEqual(cfg.get_active_model(),'qwen3:8b')
    rows=NativeDatabase(Path(d)/'data/aura_native.db').reader()
    with rows as c:
     self.assertTrue(c.execute("SELECT 1 FROM sqlite_master WHERE name='provider_settings'").fetchone())
     self.assertNotIn('fake-openai-secret', c.execute("SELECT * FROM provider_settings").fetchall().__str__())
   finally:
    if old is None: os.environ.pop('AURA_PCC_FAKE',None)
    else: os.environ['AURA_PCC_FAKE']=old
