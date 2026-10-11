import unittest
from aura_native.developer_fabric.resilience import CircuitBreaker
class CircuitTests(unittest.TestCase):
 def test_open_half_open_close(self):
  now=[0]; c=CircuitBreaker(2,10,lambda:now[0]); c.failure(); c.failure(); self.assertFalse(c.allow()); now[0]=11; self.assertTrue(c.allow()); c.success(); self.assertEqual(c.state,'CLOSED')
 def test_half_open_failure(self):
  now=[0]; c=CircuitBreaker(1,2,lambda:now[0]); c.failure(); now[0]=3; self.assertTrue(c.allow()); c.failure(); self.assertEqual(c.state,'OPEN')
if __name__=='__main__':unittest.main()
