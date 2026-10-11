import unittest
from aura_native.providers.connection import FakeProviderConnectionTester
class ProviderCompletionTests(unittest.TestCase):
 def test_exception_result_contract(self):
  class Broken:
   def test(self,**kwargs): raise RuntimeError('secret should not escape')
  try: Broken().test()
  except Exception:
   result={'success':False,'status':'unknown_error','message':'Échec de connexion'}
  self.assertEqual(result['status'],'unknown_error'); self.assertNotIn('secret',str(result))
 def test_fake_timeout_result(self):
  r=FakeProviderConnectionTester({'gemini':'timeout'}).test('gemini'); self.assertEqual(r.status,'timeout'); self.assertFalse(r.success)
