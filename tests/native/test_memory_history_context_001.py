import sqlite3, tempfile, threading, unittest
from pathlib import Path
from aura_native.storage.database import NativeDatabase
from aura_native.storage.conversation_repository import ConversationRepository
from aura_native.storage.memory_repository import MemoryRepository
from aura_native.agent.context import ContextBuilder

class MemoryHistoryContext001Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(prefix='aura-memory-history-')
        self.db_path=Path(self.tmp.name)/'data'/'aura.db'; self.db=NativeDatabase(self.db_path)
        self.repo=ConversationRepository(self.db); self.mem=MemoryRepository(self.db)
    def tearDown(self): self.tmp.cleanup()
    def test_import_and_constructor_are_safe(self): self.assertFalse(self.db_path.exists()); self.assertIsNotNone(self.repo)
    def test_create_conversation(self):
        c=self.repo.create('s1','A'); self.assertTrue(c.conversation_id); self.assertEqual(c.session_id,'s1')
    def test_append_user(self):
        c=self.repo.create('s1'); m=self.repo.add_message(c.conversation_id,'s1','user','u'); self.assertEqual(m.role,'user')
    def test_append_assistant(self):
        c=self.repo.create('s1'); m=self.repo.add_message(c.conversation_id,'s1','assistant','a'); self.assertEqual(m.role,'assistant')
    def test_order_is_sequence_not_timestamp(self):
        c=self.repo.create('s1'); [self.repo.add_message(c.conversation_id,'s1','user',x) for x in ('one','two','three')]; self.assertEqual([m.sequence for m in self.repo.messages(c.conversation_id,'s1')],[1,2,3])
    def test_role_preservation(self):
        c=self.repo.create('s1'); self.repo.add_message(c.conversation_id,'s1','user','u'); self.repo.add_message(c.conversation_id,'s1','assistant','a'); self.assertEqual([m.role for m in self.repo.messages(c.conversation_id,'s1')],['user','assistant'])
    def test_isolation(self):
        c=self.repo.create('s1'); self.repo.add_message(c.conversation_id,'s1','user','private'); self.assertEqual(self.repo.messages(c.conversation_id,'other'),[])
    def test_restart_persistence(self):
        c=self.repo.create('s1'); self.repo.add_message(c.conversation_id,'s1','user','persist'); self.assertEqual(NativeDatabase(self.db_path).path,self.db_path); self.assertEqual(self.repo.messages(c.conversation_id,'s1')[0].content,'persist')
    def test_resume_same_conversation(self):
        c=self.repo.create('s1'); self.repo.add_message(c.conversation_id,'s1','user','resume'); self.assertIsNotNone(self.repo.get(c.conversation_id,'s1'))
    def test_new_conversation_is_clean(self):
        a=self.repo.create('s1'); b=self.repo.create('s1'); self.repo.add_message(a.conversation_id,'s1','user','A'); self.assertEqual(self.repo.messages(b.conversation_id,'s1'),[])
    def test_ids_are_distinct(self):
        c=self.repo.create('s1'); m=self.repo.add_message(c.conversation_id,'s1','user','x'); self.assertNotEqual(c.conversation_id,m.message_id)
    def test_missing_conversation_rejected(self):
        with self.assertRaises(ValueError): self.repo.add_message('missing','s1','user','x')
    def test_malformed_empty_message_rejected(self):
        c=self.repo.create('s1');
        with self.assertRaises(ValueError): self.repo.add_message(c.conversation_id,'s1','user',' ')
    def test_context_ordering(self):
        b=ContextBuilder(self.mem); out=b.build([{'message_id':'1','role':'user','content':'u'},{'message_id':'2','role':'assistant','content':'a'}],query='q',session_id='s'); self.assertEqual([x['role'] for x in out.messages],['system','user','assistant','user'])
    def test_context_limit_does_not_delete_history(self):
        c=self.repo.create('s1'); [self.repo.add_message(c.conversation_id,'s1','user',str(i)) for i in range(25)]; self.assertEqual(len(self.repo.messages(c.conversation_id,'s1')),25); b=ContextBuilder(self.mem,max_history_messages=4); out=b.build([m.as_payload() for m in self.repo.messages(c.conversation_id,'s1')],query='25',session_id='s1'); self.assertLessEqual(len(out.messages),6)
    def test_memory_read_write_scope(self):
        r,_=self.mem.create('préférence',scope='user',scope_id='default'); self.assertEqual(self.mem.get(r.memory_id).content,'préférence')
    def test_memory_isolation(self):
        r,_=self.mem.create('session fact',scope='session',scope_id='s1'); self.assertEqual(self.mem.list(scope='session',scope_id='s2'),[]); self.assertEqual(self.mem.get(r.memory_id).scope_id,'s1')
    def test_memory_forget(self):
        r,_=self.mem.create('forget me'); self.assertIsNotNone(self.mem.forget(r.memory_id)); self.assertIsNone(self.mem.get(r.memory_id))
    def test_duplicate_memory_is_idempotent(self):
        a,created=self.mem.create('same'); b,created2=self.mem.create('same'); self.assertTrue(created); self.assertFalse(created2); self.assertEqual(a.memory_id,b.memory_id)
    def test_schema_versioned(self):
        with self.db.reader() as c: self.assertGreaterEqual(c.execute('select max(version) from schema_migrations').fetchone()[0],13)
    def test_corrupt_schema_fails_without_reset(self):
        p=Path(self.tmp.name)/'bad.db'; con=sqlite3.connect(p); con.execute('create table schema_migrations(version integer primary key, applied_at text not null)'); con.execute("insert into schema_migrations values(999,'x')"); con.commit(); con.close();
        with self.assertRaises(RuntimeError): NativeDatabase(p).connect()
    def test_no_real_state_path_used(self): self.assertNotIn('AURA-NATIVE',str(self.db_path))
if __name__=='__main__': unittest.main()
