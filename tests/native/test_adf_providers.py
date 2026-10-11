import unittest
from aura_native.developer_fabric.adf import *
class ProviderTests(unittest.TestCase):
 def test_states_skip(self):
  a=FakeProvider('a',state=ProviderState.QUOTA_EXHAUSTED); b=FakeProvider('b'); r=ProviderRouter([a,b]); out,attempts=r.execute(type('J',(),{'job_id':'j'})(),'x'); self.assertEqual(out['provider_id'],'b'); self.assertEqual(attempts,['b']); self.assertEqual(r.skip_reasons['a'],ProviderState.QUOTA_EXHAUSTED)
 def test_all_rejected(self):
  r=ProviderRouter([FakeProvider('a',state=ProviderState.POLICY_BLOCKED)]); 
  with self.assertRaises(RuntimeError): r.execute(type('J',(),{'job_id':'j'})(),'x')
 def test_available(self): self.assertEqual(ProviderRouter([FakeProvider('a')]).execute(type('J',(),{'job_id':'j'})(),'x')[0]['provider_id'],'a')
if __name__=='__main__':unittest.main()
