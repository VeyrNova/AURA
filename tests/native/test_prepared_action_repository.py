import tempfile,unittest
from pathlib import Path
from aura_native.google.models import PreparedAction
from aura_native.storage.database import NativeDatabase
from aura_native.storage.prepared_action_repository import PreparedActionRepository
class Tests(unittest.TestCase):
 def setUp(self):self.t=tempfile.TemporaryDirectory();self.r=PreparedActionRepository(NativeDatabase(Path(self.t.name)/'a.db'))
 def tearDown(self):self.t.cleanup()
 def a(self,i='a',exp=None):return PreparedAction(i,'calendar.prepare','create',{'x':[1]},'test',expires_at=exp)
 def test_create_roundtrip_pending_and_restart(self):self.r.create(self.a());self.assertEqual(self.r.get('a').payload,{'x':[1]});self.assertEqual(len(self.r.get_pending()),1);self.assertEqual(len(PreparedActionRepository(self.r.db).get_pending()),1)
 def test_transitions(self):
  self.r.create(self.a());self.r.confirm('a');self.r.mark_executed('a');self.assertEqual(self.r.get('a').state,'executed');self.assertEqual(self.r.get_pending(),[])
  with self.assertRaises(ValueError):self.r.confirm('a')
 def test_cancel_error_and_expire(self):
  self.r.create(self.a('b'));self.r.cancel('b');self.assertEqual(self.r.get('b').state,'cancelled')
  self.r.create(self.a('c','2000-01-01T00:00:00+00:00'));self.assertEqual(self.r.expire_old('2100-01-01T00:00:00+00:00'),1);self.assertEqual(self.r.get('c').state,'expired')
  self.r.create(self.a('d'));self.r.confirm('d');self.r.mark_error('d','google_rate_limited');self.assertEqual(self.r.get('d').error_code,'google_rate_limited')
if __name__=='__main__':unittest.main()
