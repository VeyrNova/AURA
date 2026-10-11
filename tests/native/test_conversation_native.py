import tempfile
import unittest
from pathlib import Path
from aura_native.bootstrap.composition import compose_runtime
from aura_native.core.contracts import CapabilityState, Command

ROOT=Path(__file__).resolve().parents[2]
class ConversationNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="aura-native-conversation-"); self.state=Path(self.temp.name); self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state); self.runtime.start()
    def tearDown(self): self.runtime.stop(); self.temp.cleanup()
    def command(self,name,payload=None): return Command(name=name,payload=payload or {},session_id="conversation-test",source="test")
    def events(self,name):
        out=[];self.runtime.bus.subscribe(out.append,name=name);return out
    def test_capability_and_v2_migration_are_idempotent(self):
        self.assertEqual({x.name:x.state for x in self.runtime.capabilities}["conversation"],CapabilityState.AVAILABLE)
        self.runtime.bus.submit(self.command("conversation.list"));self.runtime.bus.drain()
        self.assertTrue((self.runtime.paths.data_dir/"aura_native.db").exists())
        self.runtime.stop();self.runtime.start();self.runtime.bus.submit(self.command("conversation.list"));self.runtime.bus.drain()
    def test_send_persists_user_message_without_assistant(self):
        created=self.events("conversation.created"); messages=self.events("conversation.message_created")
        self.runtime.bus.submit(self.command("conversation.send",{"text":"Bonjour AURA"}));self.runtime.bus.drain()
        self.assertEqual(len(created),1); self.assertEqual(messages[-1].payload["message"]["role"],"user")
        ident=messages[-1].payload["conversation_id"]; loaded=self.events("conversation.loaded")
        self.runtime.bus.submit(self.command("conversation.get",{"conversation_id":ident}));self.runtime.bus.drain()
        self.assertEqual([x["content"] for x in loaded[-1].payload["messages"]],["Bonjour AURA"])
    def test_new_list_get_clear_and_invalid_message(self):
        created=self.events("conversation.created");self.runtime.bus.submit(self.command("conversation.new",{"title":"Essai"}));self.runtime.bus.drain();ident=created[-1].payload["conversation"]["conversation_id"]
        self.runtime.bus.submit(self.command("conversation.send",{"conversation_id":ident,"text":"x"}));self.runtime.bus.drain();cleared=self.events("conversation.cleared")
        self.runtime.bus.submit(self.command("conversation.clear",{"conversation_id":ident}));self.runtime.bus.drain();self.assertTrue(cleared[-1].payload["cleared"])
        result=self.runtime.bus.submit(self.command("conversation.send",{"conversation_id":ident,"text":"   "}));self.runtime.bus.drain();self.assertEqual(result.status,"queued")
    def test_sessions_are_isolated_and_order_is_deterministic(self):
        created=self.events("conversation.created"); self.runtime.bus.submit(self.command("conversation.new",{},)); self.runtime.bus.drain(); ident=created[-1].payload["conversation"]["conversation_id"]
        for text in ("un","deux","trois"): self.runtime.bus.submit(self.command("conversation.send",{"conversation_id":ident,"text":text}))
        self.runtime.bus.drain(); loaded=self.events("conversation.loaded")
        self.runtime.bus.submit(self.command("conversation.get",{"conversation_id":ident})); self.runtime.bus.drain(); self.assertEqual([x["sequence"] for x in loaded[-1].payload["messages"]],[1,2,3])
        foreign=Command(name="conversation.get",payload={"conversation_id":ident},session_id="other-session",source="test"); self.runtime.bus.submit(foreign);self.runtime.bus.drain();self.assertIsNone(loaded[-1].payload["conversation"])
    def test_reconstructed_runtime_restores_same_session_history(self):
        sent=self.events("conversation.message_created"); self.runtime.bus.submit(self.command("conversation.send",{"text":"persistant"}));self.runtime.bus.drain(); ident=sent[-1].payload["conversation_id"]
        self.runtime.stop(); self.runtime=compose_runtime(project_root=ROOT,state_dir=self.state);self.runtime.start();loaded=[];self.runtime.bus.subscribe(loaded.append,name="conversation.loaded");self.runtime.bus.submit(self.command("conversation.get",{"conversation_id":ident}));self.runtime.bus.drain();self.assertEqual(loaded[-1].payload["messages"][0]["content"],"persistant")
    def test_v2_schema_migrates_without_dropping_legacy_messages(self):
        from aura_native.storage.database import NativeDatabase
        import sqlite3
        path=self.state/"data"/"v2.db"; path.parent.mkdir(parents=True,exist_ok=True); conn=sqlite3.connect(path)
        conn.executescript("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL); INSERT INTO schema_migrations VALUES(2,'now'); CREATE TABLE conversations(conversation_id TEXT PRIMARY KEY,title TEXT,created_at TEXT,updated_at TEXT,status TEXT); CREATE TABLE messages(message_id TEXT PRIMARY KEY,conversation_id TEXT,role TEXT,content TEXT,created_at TEXT,source TEXT);")
        conn.execute("INSERT INTO conversations VALUES('c','t','a','a','active')");conn.execute("INSERT INTO messages VALUES('m','c','user','ancien','a','test')");conn.commit();conn.close()
        db=NativeDatabase(path)
        with db.reader() as migrated:
            self.assertEqual(migrated.execute("SELECT session_id FROM conversations WHERE conversation_id='c'").fetchone()[0],"legacy-v2")
            self.assertEqual(migrated.execute("SELECT content,sequence FROM conversation_messages WHERE message_id='m'").fetchone()[0],"ancien")
            self.assertEqual(migrated.execute("SELECT count(*) FROM messages").fetchone()[0],1)
