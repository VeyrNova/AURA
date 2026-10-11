import unittest
from aura_native.system_control.product import WindowTargetResolver, TargetResolution
from aura_native.system_control.models import SystemActionType
class FakeControl:
 def __init__(self, rows): self.rows=rows
 def execute(self, req): return type('R',(),{'data':self.rows,'status':'SUCCESS'})()
class ResolverTests(unittest.TestCase):
 def test_resolved_exact_identity(self):
  x=WindowTargetResolver(FakeControl([{'hwnd':1,'pid':2,'title':'Bloc-notes'}])).resolve(' bloc-notes '); self.assertEqual(x.status,'RESOLVED'); self.assertEqual(x.target.pid,2)
 def test_not_found(self): self.assertEqual(WindowTargetResolver(FakeControl([])).resolve('x').status,'NOT_FOUND')
 def test_ambiguity(self): self.assertEqual(WindowTargetResolver(FakeControl([{'hwnd':1,'pid':2,'title':'X'},{'hwnd':3,'pid':4,'title':'X'}])).resolve('x').status,'AMBIGUOUS')
 def test_invalid_empty(self): self.assertEqual(WindowTargetResolver(FakeControl([])).resolve('').status,'INVALID')
if __name__=='__main__': unittest.main()
