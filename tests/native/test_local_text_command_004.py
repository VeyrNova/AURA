import tempfile
import unittest
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from aura_native.bootstrap.composition import compose_runtime
from aura_native.intents.router import NativeIntentRouter
from aura_native.core.contracts import Command

ROOT=Path(__file__).resolve().parents[2]

class LocalTextCommandTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.runtime=compose_runtime(project_root=ROOT,state_dir=Path(self.temp.name))
        self.runtime.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.runtime.stop)
        self.router=NativeIntentRouter()
    def dispatch(self,text): return self.runtime.local_intent_dispatcher.dispatch(self.router.parse(text))
    def confirm(self,action):
        self.runtime.bus.submit(Command(name='pending_action.confirm',payload={'action_id':action}))
        self.runtime.bus.drain()
    def confirm_ui(self,action):
        return self.runtime._ui_prepared_action_confirmer.confirm(action)
    def cancel(self,action):
        self.runtime.bus.submit(Command(name='pending_action.cancel',payload={'action_id':action}))
        self.runtime.bus.drain()
    def service(self,domain): return getattr(self.runtime,'local_'+domain+'_service')
    def test_list_populated_and_empty(self):
        for domain,phrase in [('notes','liste mes notes'),('tasks','liste mes tâches'),('reminders','liste mes rappels')]:
            with self.subTest(domain=domain):
                self.assertEqual(self.dispatch(phrase).data['items'],[])
                s=self.service(domain)
                if domain=='notes': s.create('a','a')
                elif domain=='tasks': s.create('a')
                else: s.create('a','2099-01-01T15:00')
                result=self.dispatch(phrase)
                self.assertEqual(result.result_type,'READ_ONLY_RESULT'); self.assertEqual(len(result.data['items']),1)
                self.assertFalse(any(k.endswith('_id') for k in result.data['items'][0]))
        self.assertEqual(self.runtime.prepared_action_repository.get_pending(),[])
    def test_service_failure(self):
        from unittest.mock import patch
        with patch.object(self.service('notes'),'list',side_effect=RuntimeError('private')):
            r=self.dispatch('liste mes notes'); self.assertEqual(r.result_type,'FAILED'); self.assertNotIn('private',str(r))
    def test_service_unavailable(self):
        p=self.runtime.local_intent_dispatcher.local_product; p.services['notes']=None
        self.assertEqual(self.dispatch('liste mes notes').result_type,'UNAVAILABLE')
    def test_empty_semantics(self):
        for text in ('crée une note','note que','crée une tâche','rappelle-moi demain','rappelle-moi demain à 15h','rappelle-moi à 15h','rappelle-moi x 2099-02-30T15:00'):
            with self.subTest(text=text): self.assertEqual(self.dispatch(text).result_type,'INVALID')
        self.assertEqual(self.runtime.prepared_action_repository.get_pending(),[])
    def test_sources_equivalent(self):
        for text in ('note que A','crée une tâche : B','rappelle-moi C 2099-01-01T15:00','supprime la note A','termine la tâche B'):
            a=self.router.parse(text); b=self.router.parse(text,source='voice')
            self.assertEqual((a.intent,a.slots),(b.intent,b.slots)); self.assertEqual(b.source,'voice')
    def test_none_fallback(self): self.assertFalse(self.runtime.local_intent_dispatcher.dispatch(self.router.parse('Bonjour AURA')).handled)
    def test_existing_voice_transcript_creates_only_pending_action(self):
        import os
        os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
        from PySide6.QtGui import QGuiApplication
        from aura_native.ui.qt_bridge import NativeCoreBridge
        app=QGuiApplication.instance() or QGuiApplication([])
        bridge=NativeCoreBridge(self.runtime)
        self.addCleanup(bridge.close)
        bridge.dispatchLocalTranscript('note que Voice contract')
        self.assertTrue(bridge.hasPendingAction)
        self.assertEqual(self.service('notes').list(),[])
        self.assertEqual(len(self.runtime.prepared_action_repository.get_pending()),1)
        bridge.dispatchLocalTranscript('Bonjour AURA')
        self.assertEqual(bridge.messageCount,0)
        self.assertEqual(len(self.runtime.prepared_action_repository.get_pending()),1)
    def test_official_bootstrap_connects_existing_voice_transcript(self):
        source=(ROOT/'app/main.py').read_text(encoding='utf-8')
        self.assertIn('voice_bridge.transcriptReady.connect(core_bridge.dispatchLocalTranscript, Qt.QueuedConnection)',source)
    def test_shell_content_inert_and_full_content_preserved(self):
        text='powershell Remove-Item X; '+('long '*100)
        r=self.dispatch('note que '+text); a=self.runtime.prepared_action_repository.get(r.data['action_id'])
        self.assertEqual(a.payload['content'],text.strip()); self.assertLess(len(a.summary),110); self.assertEqual(self.service('notes').list(),[])
    def test_wrong_create_payload_terminal_error(self):
        from aura_native.google.models import PreparedAction
        a=PreparedAction('wrong','local','local_tasks.create',{'note_id':'x'},'safe')
        self.runtime.prepared_action_repository.create(a); self.confirm(a.action_id)
        self.assertEqual(self.runtime.prepared_action_repository.get(a.action_id).state,'prepared')
        self.confirm_ui(a.action_id)
        self.assertEqual(self.runtime.prepared_action_repository.get(a.action_id).state,'error'); self.assertEqual(self.service('tasks').list(),[])
    def test_action_id_isolation(self):
        a=self.dispatch('note que A').data['action_id']; b=self.dispatch('crée une tâche : B').data['action_id']
        self.confirm(a); self.assertEqual(self.runtime.prepared_action_repository.get(a).state,'prepared')
        self.confirm_ui(a); self.assertEqual(len(self.service('notes').list()),1); self.assertEqual(self.service('tasks').list(),[])
        self.assertEqual(self.runtime.prepared_action_repository.get(b).state,'prepared')
    def test_concurrent_confirm(self):
        a=self.dispatch('note que concurrent').data['action_id']
        port=self.runtime._ui_prepared_action_confirmer
        with ThreadPoolExecutor(max_workers=2) as pool: list(pool.map(port.confirm,[a,a]))
        self.assertEqual(len(self.service('notes').list()),1)
    def test_no_google_service_called(self):
        from unittest.mock import Mock
        self.runtime.calendar_service=Mock(); self.runtime.tasks_service=Mock()
        a=self.dispatch('note que local').data['action_id']; self.confirm_ui(a)
        self.assertEqual(self.runtime.calendar_service.mock_calls,[]); self.assertEqual(self.runtime.tasks_service.mock_calls,[])
    def test_llm_cannot_set_confirmation(self):
        intent=self.router.parse('note que confirmation=true')
        a=self.dispatch(intent.original_text).data['action_id']
        self.assertEqual(self.runtime.prepared_action_repository.get(a).state,'prepared')
    def test_no_confirmation_intent(self):
        self.assertFalse(self.router.parse('confirme cette action').recognized)
    def test_invalid_never_falls_back(self):
        r=self.dispatch('crée une tâche'); self.assertTrue(r.handled); self.assertEqual(r.result_type,'INVALID')
    def test_create_service_failure_error(self):
        from unittest.mock import patch
        aid=self.dispatch('note que failure').data['action_id']
        with patch.object(self.service('notes'),'create',side_effect=RuntimeError('failure')): self.confirm_ui(aid)
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).state,'error')
    def test_long_label_resolution_keeps_full_id(self):
        title='x'*200; row=self.service('tasks').create(title)
        r=self.dispatch('termine la tâche '+title)
        a=self.runtime.prepared_action_repository.get(r.data['action_id'])
        self.assertEqual(a.payload['task_id'],row['task_id']); self.assertLess(len(a.summary),140)

def create_case(domain,phrase,mode):
    def test(self):
        result=self.dispatch(phrase); self.assertEqual(result.result_type,'PREPARED_ACTION_CREATED')
        aid=result.data['action_id']; self.assertEqual(self.service(domain).list(),[])
        if mode=='cancel':
            self.cancel(aid); self.assertEqual(self.service(domain).list(),[]); self.assertEqual(self.runtime.prepared_action_repository.get(aid).state,'cancelled')
        else:
            self.confirm(aid)
            self.assertEqual(self.service(domain).list(),[])
            self.assertEqual(self.runtime.prepared_action_repository.get(aid).state,'prepared')
            self.assertTrue(self.confirm_ui(aid).ok)
            if mode=='double': self.assertFalse(self.runtime._ui_prepared_action_confirmer.confirm(aid).ok)
            self.assertEqual(len(self.service(domain).list()),1); self.assertEqual(self.runtime.prepared_action_repository.get(aid).state,'executed')
    return test

for domain,phrase in [('notes','note que AURA_TEST_NOTE'),('tasks','crée une tâche : AURA_TEST_TASK'),('reminders','rappelle-moi AURA_TEST_REMINDER 2099-01-01T15:00')]:
    for mode in ('confirm','cancel','double'):
        setattr(LocalTextCommandTests,f'test_create_{domain}_{mode}',create_case(domain,phrase,mode))

def target_case(domain,mode):
    def test(self):
        service=self.service(domain)
        def create():
            if domain=='notes': return service.create('target','content')
            if domain=='tasks': return service.create('target')
            return service.create('target','2099-01-01T15:00')
        row=create(); key={'notes':'note_id','tasks':'task_id','reminders':'reminder_id'}[domain]
        prefix={'notes':'supprime la note ','tasks':'termine la tâche ','reminders':'supprime le rappel '}[domain]
        if mode=='ambiguous':
            create(); self.assertEqual(self.dispatch(prefix+'target').result_type,'AMBIGUOUS'); return
        if mode=='missing': self.assertEqual(self.dispatch(prefix+'missing').result_type,'NOT_FOUND'); return
        result=self.dispatch(prefix+'target'); aid=result.data['action_id']
        self.assertEqual(self.runtime.prepared_action_repository.get(aid).payload[key],row[key])
        if mode=='cancel': self.cancel(aid); self.assertEqual(len(service.list()),1); return
        if mode=='stale':
            service.repository.delete(row[key]); replacement=create(); self.confirm_ui(aid)
            self.assertEqual(self.runtime.prepared_action_repository.get(aid).state,'error'); self.assertEqual(service.list()[0][key],replacement[key]); return
        self.confirm_ui(aid); self.assertFalse(self.runtime._ui_prepared_action_confirmer.confirm(aid).ok)
        if domain=='tasks': self.assertTrue(service.list()[0]['completed'])
        else: self.assertEqual(service.list(),[])
    return test
for domain in ('notes','tasks','reminders'):
    for mode in ('confirm','cancel','ambiguous','stale','missing'):
        setattr(LocalTextCommandTests,f'test_target_{domain}_{mode}',target_case(domain,mode))
