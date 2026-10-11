import unittest, threading
from aura_native.system_control.models import SystemActionRequest, SystemActionType
from aura_native.system_control.service import SystemControlService
from aura_native.system_control.windows_adapter import WindowsSystemAdapter
class Fake:
 def __init__(self): self.calls=[]
 def discover_windows(self): return []
 def discover_processes(self): return []
 def foreground_window(self): return None
 def focus_window(self,hwnd): self.calls.append(('focus',hwnd)); return True
 def minimize_window(self,hwnd): self.calls.append(('min',hwnd)); return True
 def maximize_window(self,hwnd): self.calls.append(('max',hwnd)); return True
class SystemControlTests(unittest.TestCase):
 def setUp(self): self.fake=Fake(); self.s=SystemControlService(WindowsSystemAdapter(self.fake))
 def req(self,a,**kw): return SystemActionRequest(a,kw,confirmed=kw.pop('confirmed',False))
 def test_01_package_import(self): self.assertIsNotNone(SystemActionType)
 def test_02_constructor_side_effect_free(self): self.assertEqual(self.fake.calls,[])
 def test_03_discover_windows(self): self.assertEqual(self.s.execute(self.req(SystemActionType.DISCOVER_WINDOWS)).status,'SUCCESS')
 def test_04_discover_processes(self): self.assertEqual(self.s.execute(self.req(SystemActionType.DISCOVER_PROCESSES)).status,'SUCCESS')
 def test_05_foreground(self): self.assertEqual(self.s.execute(self.req(SystemActionType.GET_FOREGROUND_WINDOW)).status,'SUCCESS')
 def test_06_focus_confirmation(self): self.assertEqual(self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=1,title='x')).status,'CONFIRMATION_REQUIRED')
 def test_07_min_confirmation(self): self.assertEqual(self.s.execute(self.req(SystemActionType.MINIMIZE_WINDOW,hwnd=1,title='x')).status,'CONFIRMATION_REQUIRED')
 def test_08_max_confirmation(self): self.assertEqual(self.s.execute(self.req(SystemActionType.MAXIMIZE_WINDOW,hwnd=1,title='x')).status,'CONFIRMATION_REQUIRED')
 def test_09_no_mutation_preconfirm(self): self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=1,title='x')); self.assertEqual(self.fake.calls,[])
 def test_10_invalid_hwnd(self): self.assertEqual(self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=0,title='x')).status,'INVALID_TARGET')
 def test_11_wrong_pid_rejected(self): self.assertEqual(self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=1,pid=99,title='x',confirmed=True)).status,'NOT_FOUND')
 def test_12_stale_backend_target(self): self.fake.focus_window=lambda _: False; self.assertEqual(self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=1,title='x',confirmed=True)).status,'NOT_FOUND')
 def test_13_adapter_exception(self): self.fake.minimize_window=lambda _: (_ for _ in ()).throw(RuntimeError('x')); self.assertEqual(self.s.execute(self.req(SystemActionType.MINIMIZE_WINDOW,hwnd=1,title='x',confirmed=True)).status,'FAILED')
 def test_14_unsupported(self): self.assertEqual(self.s.execute(self.req('unknown')).status,'UNAVAILABLE')
 def test_15_malicious_data_inert(self): self.assertEqual(self.s.execute(self.req(SystemActionType.FOCUS_WINDOW,hwnd=0,title='; shutdown /s')).status,'INVALID_TARGET')
 def test_16_concurrent_isolation(self):
  reqs=[self.req(SystemActionType.MINIMIZE_WINDOW,hwnd=i,title=str(i),confirmed=True) for i in (1,2)]; ts=[threading.Thread(target=self.s.execute,args=(r,)) for r in reqs]; [t.start() for t in ts]; [t.join() for t in ts]; self.assertEqual(sorted(self.fake.calls),[('min',1),('min',2)])
 def test_17_exact_confirmation(self): self.assertEqual(self.s.execute(self.req(SystemActionType.MAXIMIZE_WINDOW,hwnd=1,title='x')).status,'CONFIRMATION_REQUIRED')
 def test_18_success_contract(self): self.assertEqual(self.s.execute(self.req(SystemActionType.MINIMIZE_WINDOW,hwnd=1,title='x',confirmed=True)).action,'minimize_window')
 def test_19_no_shell_interface(self): self.assertFalse(hasattr(self.s,'run_command'))
 def test_20_cleanup_contract(self): self.assertEqual(self.fake.calls,[])
if __name__=='__main__': unittest.main()



