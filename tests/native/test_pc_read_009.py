import unittest
from types import SimpleNamespace
from aura_native.intents.router import NativeIntentRouter
from aura_native.system_control.models import SystemActionType, SystemActionRequest
from aura_native.system_control.service import SystemControlService
from aura_native.system_control.product import SystemControlProductService

class FakeAdapter:
    def __init__(self): self.calls=[]
    def execute(self, request):
        self.calls.append(request.action)
        if request.action is SystemActionType.DISCOVER_WINDOWS:
            return {'status':'SUCCESS','data':[SimpleNamespace(hwnd=1,pid=10,title='AURA_TEST_009_WINDOW_X',visible=True,foreground=False)]}
        if request.action is SystemActionType.DISCOVER_PROCESSES:
            return {'status':'SUCCESS','data':[SimpleNamespace(pid=10,image_name='aura.exe',parent_pid=0)]}
        if request.action is SystemActionType.GET_FOREGROUND_WINDOW:
            return {'status':'SUCCESS','data':{'title':'AURA_TEST_009_WINDOW_X','pid':10}}
        return {'status':'FAILED','data':None}

class PcRead009Tests(unittest.TestCase):
    def setUp(self):
        self.router=NativeIntentRouter(); self.fake=FakeAdapter()
        self.product=SystemControlProductService(SystemControlService(self.fake), object())
    def test_windows_grammar_and_presentation(self):
        for text in ('quelles fenêtres sont ouvertes','liste les fenêtres ouvertes','montre les fenêtres ouvertes','quelles applications ont une fenêtre ouverte'):
            i=self.router.parse(text); self.assertEqual(i.intent,'PC_LIST_WINDOWS'); self.assertFalse(i.requires_confirmation)
        r=self.product.read(self.router.parse('liste les fenêtres ouvertes'))
        self.assertEqual(r['count'],1); self.assertEqual(r['items'][0]['title'],'AURA_TEST_009_WINDOW_X')
        self.assertNotIn('hwnd',r['items'][0]); self.assertNotIn('pid',r['items'][0])
        self.assertIn(SystemActionType.DISCOVER_WINDOWS,self.fake.calls)
    def test_process_grammar_bounded(self):
        for text in ('liste les processus','quels processus tournent','quels programmes sont en cours d’exécution'):
            self.assertEqual(self.router.parse(text).intent,'PC_LIST_PROCESSES')
        r=self.product.read(self.router.parse('liste les processus')); self.assertEqual(r['count'],1); self.assertEqual(r['items'][0]['image_name'],'aura.exe')
    def test_foreground_and_no_mutation(self):
        for text in ('quelle fenêtre est active','quelle application est au premier plan','quel programme j’utilise actuellement'):
            self.assertEqual(self.router.parse(text).intent,'PC_GET_FOREGROUND_WINDOW')
        r=self.product.read(self.router.parse('quelle fenêtre est active')); self.assertEqual(r['count'],1); self.assertNotIn('hwnd',r['items'][0]); self.assertNotIn('pid',r['items'][0])
        self.assertNotIn(SystemActionType.FOCUS_WINDOW,self.fake.calls)
    def test_ambiguous_and_conversation_safety(self):
        self.assertNotEqual(self.router.parse('cherche les fenêtres PVC sur internet').intent,'PC_LIST_WINDOWS')
        self.assertIsNone(self.router.parse('explique-moi ce qu’est un processus Windows').intent)
    def test_failure_and_empty_results(self):
        class Empty(FakeAdapter):
            def execute(self, request): self.calls.append(request.action); return {'status':'SUCCESS','data':[]}
        p=SystemControlProductService(SystemControlService(Empty()), object())
        self.assertEqual(p.read(self.router.parse('liste les fenêtres ouvertes'))['count'],0)

if __name__=='__main__': unittest.main()
